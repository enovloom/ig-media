#!/usr/bin/env bash
# Collects account and per-post numbers from the Instagram Graph API (read-only).
# The repo is public, so the results are encrypted with cloud/insights.pub.pem before
# they are printed; only the holder of the matching private key can read them.
# Secret: IG_PAGE_TOKEN (same token autopost uses).
set -uo pipefail
cd "$(dirname "$0")/.."
: "${IG_PAGE_TOKEN:?IG_PAGE_TOKEN secret is not set}"
api="https://graph.facebook.com/$(jq -r .apiVersion cloud/config.json)"
ig=$(jq -r .igUserId cloud/config.json)
out=$(mktemp -d)

# get <path> [curl -G data args...]; prints the JSON body (API errors included)
get() {
  local path=$1; shift
  local body status=ok
  body=$(curl -sS -G -H "Authorization: Bearer $IG_PAGE_TOKEN" "$api/$path" "$@" 2>&1) || true
  if ! jq -e . >/dev/null 2>&1 <<<"$body"; then body=$(jq -n --arg raw "$body" '{error:{message:$raw}}'); fi
  if jq -e '.error' >/dev/null <<<"$body"; then status=error; fi
  # runs inside $(...) too, so keep the tally in a file rather than a variable
  local args="$*"
  printf '%s\t%s\t%s\n' "$status" "$path" "${args//$IG_PAGE_TOKEN/[token]}" >> "$out/calls.log"
  printf '%s' "$body"
}

get "$ig" --data-urlencode 'fields=username,name,biography,website,followers_count,follows_count,media_count' > "$out/account.json"

# which permissions the token carries and when it expires (a token can inspect itself)
get "debug_token" --data-urlencode "input_token=$IG_PAGE_TOKEN" | jq 'if .data then .data | del(.user_id, .profile_id) else . end' > "$out/token.json"
# the app ID is public (it appears in every login URL); printing it tells apart apps that share a name
echo "token app: $(jq -r '.app_id // "?"' "$out/token.json") ($(jq -r '.application // "?"' "$out/token.json"))"

# every post on the account, not only the ones autopost made
echo '{"data":[]}' > "$out/media.json"; cursor=""
for page in 1 2 3 4 5 6 7 8 9 10; do
  r=$(get "$ig/media" --data-urlencode 'fields=id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count,thumbnail_url' --data-urlencode 'limit=100' ${cursor:+--data-urlencode "after=$cursor"})
  jq --argjson r "$r" '.data += ($r.data // []) | if $r.error then .error = $r.error else . end' "$out/media.json" > "$out/t" && mv "$out/t" "$out/media.json"
  cursor=$(jq -r '.paging.cursors.after // empty' <<<"$r")
  [ -n "$(jq -r '.paging.next // empty' <<<"$r")" ] && [ -n "$cursor" ] || break
done

reel_metrics="views reach saved shares likes comments total_interactions ig_reels_avg_watch_time ig_reels_video_view_total_time reels_skip_rate"
feed_metrics="views reach saved shares likes comments total_interactions follows profile_visits profile_activity"
# one call per post with every metric; if the API rejects the set, fall back to one metric at a time
pick='def val: .values[0].value // .total_value.value; reduce (.data // [])[] as $d ({}; . + {($d.name): ($d | val)})'
echo '{}' > "$out/media_insights.json"
echo '{}' > "$out/comments.json"
for row in $(jq -r '.data[]? | "\(.id)|\(.media_product_type)"' "$out/media.json"); do
  id=${row%%|*}; kind=${row#*|}
  metrics=$feed_metrics; [ "$kind" = "REELS" ] && metrics=$reel_metrics
  r=$(get "$id/insights" --data-urlencode "metric=${metrics// /,}")
  if jq -e '.error' >/dev/null <<<"$r"; then
    one='{}'
    for m in $metrics; do
      r=$(get "$id/insights" --data-urlencode "metric=$m")
      one=$(jq --arg m "$m" --argjson r "$r" '. + {($m): ($r.data[0].values[0].value // $r.data[0].total_value.value // {error: ($r.error.message // "no value")})}' <<<"$one")
    done
  else
    one=$(jq "$pick" <<<"$r")
  fi
  jq --arg id "$id" --argjson v "$one" '. + {($id): $v}' "$out/media_insights.json" > "$out/t" && mv "$out/t" "$out/media_insights.json"
  c=$(get "$id/comments" --data-urlencode 'fields=id,text,timestamp,username,like_count,replies{text,username,timestamp}' --data-urlencode 'limit=100')
  jq --arg id "$id" --argjson v "$c" '. + {($id): $v}' "$out/comments.json" > "$out/t" && mv "$out/t" "$out/comments.json"
done

# account level: daily totals for the last 14 days (older days are in earlier snapshots)
echo '{}' > "$out/account_daily.json"
acct_metrics="views reach accounts_engaged total_interactions likes comments saves shares profile_links_taps follows_and_unfollows"
end=$(date -u +%s); d=$(( (end / 86400 - 14) * 86400 ))
while [ "$d" -lt "$end" ]; do
  day=$(date -u -d "@$d" +%F); next=$((d + 86400))
  one='{}'
  for m in $acct_metrics; do
    extra=(); [ "$m" = follows_and_unfollows ] && extra=(--data-urlencode 'breakdown=follow_type')
    r=$(get "$ig/insights" --data-urlencode "metric=$m" --data-urlencode 'period=day' --data-urlencode 'metric_type=total_value' --data-urlencode "since=$d" --data-urlencode "until=$next" "${extra[@]}")
    one=$(jq --arg m "$m" --argjson r "$r" '. + {($m): ($r.data[0].total_value // {error: ($r.error.message // "no value")})}' <<<"$one")
  done
  jq --arg k "$day" --argjson v "$one" '. + {($k): $v}' "$out/account_daily.json" > "$out/t" && mv "$out/t" "$out/account_daily.json"
  d=$next
done

# account level: whole period with breakdowns, plus audience (needs 100+ followers)
since=$(( end - 28 * 86400 ))
{
  echo '{'
  echo '"reach_by_type":';   get "$ig/insights" --data-urlencode 'metric=reach' --data-urlencode 'period=day' --data-urlencode 'metric_type=total_value' --data-urlencode "since=$since" --data-urlencode "until=$end" --data-urlencode 'breakdown=media_product_type,follow_type'; echo ','
  echo '"views_by_type":';   get "$ig/insights" --data-urlencode 'metric=views' --data-urlencode 'period=day' --data-urlencode 'metric_type=total_value' --data-urlencode "since=$since" --data-urlencode "until=$end" --data-urlencode 'breakdown=media_product_type,follow_type'; echo ','
  echo '"reach_series":';    get "$ig/insights" --data-urlencode 'metric=reach' --data-urlencode 'period=day' --data-urlencode "since=$since" --data-urlencode "until=$end"; echo ','
  echo '"follower_count":';  get "$ig/insights" --data-urlencode 'metric=follower_count' --data-urlencode 'period=day' --data-urlencode "since=$since" --data-urlencode "until=$end"; echo ','
  echo '"online_followers":'; get "$ig/insights" --data-urlencode 'metric=online_followers' --data-urlencode 'period=lifetime'; echo ','
  echo '"demo_follower":';   get "$ig/insights" --data-urlencode 'metric=follower_demographics' --data-urlencode 'period=lifetime' --data-urlencode 'metric_type=total_value' --data-urlencode 'breakdown=age,gender,city'; echo ','
  echo '"demo_engaged":';    get "$ig/insights" --data-urlencode 'metric=engaged_audience_demographics' --data-urlencode 'period=lifetime' --data-urlencode 'timeframe=this_month' --data-urlencode 'metric_type=total_value' --data-urlencode 'breakdown=age,gender,city'
  echo '}'
} > "$out/account_range.json"

calls=$(wc -l < "$out/calls.log"); errors=$(grep -c '^error' "$out/calls.log")
jq -n --arg at "$(date -u +%FT%TZ)" --arg src "${TOKEN_SOURCE:-IG_PAGE_TOKEN}" --argjson calls "$calls" --argjson errors "$errors" '{fetchedAt:$at, token:$src, calls:$calls, errors:$errors}' > "$out/meta.json"
echo "token=${TOKEN_SOURCE:-IG_PAGE_TOKEN} calls=$calls errors=$errors (details are inside the encrypted bundle)"

# encrypt: random AES key, sealed with the RSA public key; the workflow commits the result
tar czf "$out.tgz" -C "$out" .
key=$(openssl rand -hex 32)
mkdir -p insights
openssl enc -aes-256-cbc -pbkdf2 -salt -in "$out.tgz" -out insights/latest.enc -pass "pass:$key"
printf '%s' "$key" | openssl pkeyutl -encrypt -pubin -inkey cloud/insights.pub.pem -pkeyopt rsa_padding_mode:oaep > insights/latest.key
# error messages only (no numbers), to make failed calls easy to spot in the public log
grep '^error' "$out/calls.log" | cut -f2- | sed -E 's/[0-9]{15,}/ID/g; s/(since|until)=[0-9]+/\1=T/g' | sort | uniq -c | sort -rn | head -40
