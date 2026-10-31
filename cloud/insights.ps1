# Runs on GitHub Actions (PowerShell 7) once a day. Records how each post and the account are doing
# in stats/insights.json; the workflow commits that file back to the repo.
# Needs the instagram_manage_insights permission on IG_PAGE_TOKEN. Without it the run writes down what is
# missing and ends without failing, so it never blocks anything else.
$ErrorActionPreference = 'Stop'
$repo  = Split-Path $PSScriptRoot -Parent
$cfg   = Get-Content (Join-Path $PSScriptRoot 'config.json') -Raw | ConvertFrom-Json
# IG_API_BASE points the script at a local mock when testing it
$api   = if ($env:IG_API_BASE) { $env:IG_API_BASE } else { "https://graph.facebook.com/$($cfg.apiVersion)" }
$token = $env:IG_PAGE_TOKEN
if (-not $token) { throw 'IG_PAGE_TOKEN secret is not set' }
$headers = @{ Authorization = "Bearer $token" }
$ig = $cfg.igUserId
$statsFile = Join-Path $repo 'stats/insights.json'
$stats = if (Test-Path $statsFile) { Get-Content $statsFile -Raw | ConvertFrom-Json -AsHashtable } else { @{} }
foreach ($k in 'account', 'media') { if (-not $stats[$k]) { $stats[$k] = @{} } }
$jst = [TimeSpan]::FromHours(9)
$now = [DateTimeOffset]::UtcNow.ToOffset($jst)
$today = $now.ToString('yyyy-MM-dd')

function Log([string]$m) { Write-Host ("{0:yyyy-MM-dd HH:mm} {1}" -f [DateTimeOffset]::UtcNow.ToOffset($jst), $m) }
function GET([string]$path) { Invoke-RestMethod -Uri "$api/$path" -Headers $headers }
function Err-Text($err) { $m = $err.ErrorDetails.Message; if (-not $m) { $m = $err.Exception.Message }; $m }
function Save { New-Item -ItemType Directory -Force (Split-Path $statsFile) | Out-Null; $stats | ConvertTo-Json -Depth 8 | Set-Content $statsFile -Encoding utf8 }
# (#10) and other 2xx codes mean the token lacks a permission; 190 and 102 mean the token itself is refused
function Is-Permission([string]$m) {
  try { $x = ($m | ConvertFrom-Json).error } catch { return $false }
  $x.code -in @(10, 102, 190) -or ($x.code -ge 200 -and $x.code -le 299)
}
function Stop-Missing([string]$why) {
  try { $why = ($why | ConvertFrom-Json).error.message } catch {}
  $stats.problem = "insights not available: $why. Add instagram_manage_insights to IG_PAGE_TOKEN."
  $stats.updatedAt = $now.ToString('o')
  Save
  Write-Host "::warning title=Insights not recorded::$($stats.problem)"
  exit 0
}
function Value($m) { if ($null -ne $m.total_value) { $m.total_value.value } elseif ($m.values) { $m.values[-1].value } else { $null } }
# Asks for all metrics at once; when the API refuses the set (one of them does not apply to this post), asks one at a time.
function Metrics([string]$node, [string[]]$names, [string]$extra = '') {
  $out = [ordered]@{}
  try {
    foreach ($m in (GET "$node/insights?metric=$($names -join ',')$extra").data) { $out[$m.name] = Value $m }
    return $out
  } catch {
    $first = Err-Text $_
    if ($first -match 'permission|\(#10\)') { throw }
  }
  foreach ($n in $names) {
    try { foreach ($m in (GET "$node/insights?metric=$n$extra").data) { $out[$m.name] = Value $m } } catch {}
  }
  if (-not $out.Count) { throw $first }
  return $out
}

# account size; this needs only instagram_basic
$me = GET "$($ig)?fields=username,followers_count,media_count"
$day = $stats.account[$today]; if (-not $day) { $day = @{}; $stats.account[$today] = $day }
$day.followers = $me.followers_count; $day.posts = $me.media_count
Log "@$($me.username): $($me.followers_count) followers"

# yesterday's account numbers (JST day)
$start = [DateTimeOffset]::new($now.Date.AddDays(-1), $jst)
$yesterday = $start.ToString('yyyy-MM-dd')
try {
  $acct = Metrics $ig @('profile_views', 'profile_links_taps', 'website_clicks', 'accounts_engaged', 'reach', 'views') `
    "&period=day&metric_type=total_value&since=$($start.ToUnixTimeSeconds())&until=$($start.AddDays(1).ToUnixTimeSeconds())"
  $y = $stats.account[$yesterday]; if (-not $y) { $y = @{}; $stats.account[$yesterday] = $y }
  $y.insights = $acct
  Log "account $($yesterday): $(($acct.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ' ')"
} catch {
  $msg = Err-Text $_
  if (Is-Permission $msg) { Stop-Missing $msg }
  Log "account insights: $msg"
}

# posts from the last 90 days; queue ids come from the autopost state
$state = Get-Content (Join-Path $repo 'queue/state.json') -Raw | ConvertFrom-Json -AsHashtable
$queueIdOf = @{}; foreach ($k in $state.Keys) { if ($state[$k].mediaId) { $queueIdOf[$state[$k].mediaId] = $k } }
$reelMetrics = @('views', 'reach', 'saved', 'shares', 'likes', 'comments', 'total_interactions', 'ig_reels_avg_watch_time', 'ig_reels_video_view_total_time')
$feedMetrics = @('views', 'reach', 'saved', 'shares', 'likes', 'comments', 'total_interactions', 'profile_visits', 'follows')
$list = GET "$($ig)/media?fields=id,caption,media_product_type,permalink,timestamp&limit=50"
foreach ($p in $list.data) {
  $posted = [DateTimeOffset]::Parse([string]$p.timestamp)
  if ($now - $posted -gt [TimeSpan]::FromDays(90)) { continue }
  try {
    $vals = Metrics $p.id ($(if ($p.media_product_type -eq 'REELS') { $reelMetrics } else { $feedMetrics }))
  } catch {
    $msg = Err-Text $_
    if (Is-Permission $msg) { Stop-Missing $msg }
    Log "$($p.id): $msg"
    continue
  }
  $e = $stats.media[$p.id]; if (-not $e) { $e = @{ history = @{} }; $stats.media[$p.id] = $e }
  $e.permalink = $p.permalink; $e.postedAt = $posted.ToOffset($jst).ToString('o'); $e.type = $p.media_product_type
  $e.caption = ([string]$p.caption -split "`n")[0]
  if ($queueIdOf[$p.id]) { $e.queueId = $queueIdOf[$p.id] }
  $e.latest = $vals; $e.history[$today] = $vals
  Log "$($e.queueId ?? $p.id): $(($vals.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ' ')"
}
$stats.Remove('problem')
$stats.updatedAt = $now.ToString('o')
Save
