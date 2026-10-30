# Runs on GitHub Actions (PowerShell 7). Publishes approved posts in queue/ when they are due,
# and records the result in queue/state.json. The workflow commits that file back to the repo.
# Secret: IG_PAGE_TOKEN (Facebook Page token linked to the Instagram account).
$ErrorActionPreference = 'Stop'
$repo  = Split-Path $PSScriptRoot -Parent
$cfg   = Get-Content (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
$api   = "https://graph.facebook.com/$($cfg.apiVersion)"
$token = $env:IG_PAGE_TOKEN
if (-not $token) { throw 'IG_PAGE_TOKEN secret is not set' }
$headers = @{ Authorization = "Bearer $token" }
$queue = Join-Path $repo 'queue'
$stateFile = Join-Path $queue 'state.json'
$state = if (Test-Path $stateFile) { Get-Content $stateFile -Raw | ConvertFrom-Json -AsHashtable } else { @{} }
$now = [DateTimeOffset]::UtcNow
$late = [TimeSpan]::FromHours([double]$cfg.lateLimitHours)
# after an outage, overdue posts go out one at a time instead of all in the same minute
$gap = [TimeSpan]::FromMinutes([double]$cfg.minGapMinutes)

function Save-State { $state | ConvertTo-Json -Depth 6 | Set-Content $stateFile -Encoding utf8 }
function Log([string]$m) { Write-Host ("{0:yyyy-MM-dd HH:mm} {1}" -f [DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)), $m) }
# pwsh 7 turns ISO strings into DateTime while parsing JSON, so accept either form
function To-Time($v) { if ($v -is [datetime]) { [DateTimeOffset]$v } else { [DateTimeOffset]::Parse([string]$v) } }
function Err-Text($err) { $m = $err.ErrorDetails.Message; if (-not $m) { $m = $err.Exception.Message }; $m }
# token or permission problems (190 invalid token, 102 session, 10 and 2xx permission) are not the post's fault
function Auth-Error([string]$m) {
  try { $x = ($m | ConvertFrom-Json).error } catch { return $null }
  if ($x.code -in @(10, 102, 190) -or ($x.code -ge 200 -and $x.code -le 299)) { return "(#$($x.code)) $($x.message)" }
}
function Stop-Auth([string]$why) {
  Write-Host "::error title=IG_PAGE_TOKEN rejected::Meta refused the token: $why. Check the Facebook account and the app in Meta, issue a new Page token, update the IG_PAGE_TOKEN secret, then run autopost by hand."
  exit 1
}
function IG([string]$method, [string]$path, $body) {
  if ($method -eq 'GET') { return Invoke-RestMethod -Uri "$api/$path" -Headers $headers }
  Invoke-RestMethod -Method Post -Uri "$api/$path" -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ($body | ConvertTo-Json -Compress)
}
function Wait-Ready([string]$id, [int]$maxSec) {
  $deadline = (Get-Date).AddSeconds($maxSec)
  while ($true) {
    $s = (IG GET "$($id)?fields=status_code").status_code
    if ($s -eq 'FINISHED') { return }
    if ($s -in @('ERROR', 'EXPIRED')) { throw "container $id $s" }
    if ((Get-Date) -gt $deadline) { throw "container $id still $s" }
    Start-Sleep -Seconds 15
  }
}
function Wait-Url([string]$url) {
  for ($i = 0; $i -lt 20; $i++) {
    try { if ((Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 20 -SkipHttpErrorCheck).StatusCode -eq 200) { return } } catch {}
    Start-Sleep -Seconds 15
  }
  throw "media URL not reachable: $url"
}

try { $me = IG GET "$($cfg.igUserId)?fields=username" } catch { $why = Auth-Error (Err-Text $_); if ($why) { Stop-Auth $why }; throw }
Log "account @$($me.username)"
if (-not (Test-Path $queue)) { New-Item -ItemType Directory $queue | Out-Null }
$failed = $false
$lastPost = $state.Values | Where-Object { $_.postedAt } | ForEach-Object { To-Time $_.postedAt } | Sort-Object -Descending | Select-Object -First 1

foreach ($dir in Get-ChildItem $queue -Directory | Sort-Object Name) {
  $id = $dir.Name
  $p = Get-Content (Join-Path $dir.FullName 'post.json') -Raw | ConvertFrom-Json
  if (-not $p.approved) { continue }
  $at = To-Time $p.publishAt
  $slot = $at.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  $e = $state[$id]
  if ($e -and $e.status -in @('published', 'publishing', 'missed', 'failed')) {
    if (-not ($e.status -eq 'missed' -and $e.scheduledFor -ne $slot)) { continue }
  }
  if ($at -gt $now) { continue }
  if (-not $e) { $e = @{ attempts = 0 }; $state[$id] = $e }
  if ($now - $at -gt $late) { $e.status = 'missed'; $e.scheduledFor = $slot; Save-State; Log "$($id): missed (more than $($cfg.lateLimitHours)h late)"; $failed = $true; continue }
  if ($lastPost -and [DateTimeOffset]::UtcNow - $lastPost -lt $gap) { Log "$($id): waiting, last post was less than $($cfg.minGapMinutes) min ago"; continue }

  try {
    $e.attempts = [int]$e.attempts + 1
    $caption = (Get-Content (Join-Path $dir.FullName $p.captionFile) -Raw).Trim()
    $urls = @($p.media | ForEach-Object { "$($cfg.pagesBaseUrl.TrimEnd('/'))/media/$id/$_" })
    $urls | ForEach-Object { Wait-Url $_ }
    $ig = $cfg.igUserId
    if ($p.type -eq 'carousel') {
      $children = foreach ($u in $urls) { (IG POST "$ig/media" @{ image_url = $u; is_carousel_item = $true }).id }
      $container = (IG POST "$ig/media" @{ media_type = 'CAROUSEL'; children = ($children -join ','); caption = $caption }).id
      Wait-Ready $container 300
    } elseif ($p.type -eq 'reel') {
      $req = @{ media_type = 'REELS'; video_url = $urls[0]; caption = $caption; share_to_feed = $true }
      if ($p.thumbOffsetMs) { $req.thumb_offset = [int]$p.thumbOffsetMs }
      $container = (IG POST "$ig/media" $req).id
      Wait-Ready $container 600
    } else {
      $container = (IG POST "$ig/media" @{ image_url = $urls[0]; caption = $caption }).id
      Wait-Ready $container 300
    }
    # mark before publishing so a crash can never cause a double post
    $e.status = 'publishing'; $e.containerId = $container; Save-State
    $mediaId = (IG POST "$ig/media_publish" @{ creation_id = $container }).id
    $lastPost = [DateTimeOffset]::UtcNow
    $e.status = 'published'; $e.mediaId = $mediaId; $e.postedAt = $lastPost.ToString('o'); $e.Remove('error')
    try { $e.permalink = (IG GET "$($mediaId)?fields=permalink").permalink } catch {}
    Save-State
    Log "$($id): published $($e.permalink)"
  } catch {
    $msg = Err-Text $_
    $why = Auth-Error $msg
    if ($e.status -ne 'publishing') {
      # a bad token must not use up the post's attempts and leave it 'failed'
      if ($why) { $e.attempts = [int]$e.attempts - 1 } else { $e.error = $msg; if ($e.attempts -ge 3) { $e.status = 'failed' } }
    }
    Save-State
    Log "$($id): error: $msg"
    if ($why) { Stop-Auth $why }
    $failed = $true
  }
}
# a failed run makes GitHub email the account owner
if ($failed) { exit 1 }
