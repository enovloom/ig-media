"""Turns one decrypted insights bundle into a per-post table joined with the queue.

    python3 brain/tools/snapshot.py --data <decrypted dir> --repo <ig-media root> [--csv <history.csv>] [--json <out.json>]

Prints a readable table. --csv appends today's rows to a history file (one row per post per
fetch), --json writes the rows for further analysis.
"""
import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
FIELDS = ["fetched_at", "media_id", "queue_id", "posted_jst", "age_h", "kind", "template", "theme", "hook_type",
          "experiment", "variant", "hook", "duration_s", "views", "reach", "skip_rate", "avg_watch_s", "watch_ratio",
          "likes", "comments", "saved", "shares", "total_interactions", "follows", "profile_visits", "permalink"]


def load(path, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--csv")
    ap.add_argument("--json")
    a = ap.parse_args()

    meta = load(os.path.join(a.data, "meta.json"), {})
    fetched = datetime.strptime(meta.get("fetchedAt", "1970-01-01T00:00:00Z"), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    media = (load(os.path.join(a.data, "media.json"), {}) or {}).get("data", [])
    ins = load(os.path.join(a.data, "media_insights.json"), {}) or {}
    queue = os.path.join(a.repo, "queue")
    state = load(os.path.join(queue, "state.json"), {}) or {}
    by_media = {v.get("mediaId"): k for k, v in state.items() if v.get("mediaId")}

    rows = []
    for m in media:
        i = ins.get(m["id"], {})
        qid = by_media.get(m["id"], "")
        post = load(os.path.join(queue, qid, "post.json"), {}) if qid else {}
        scenes = load(os.path.join(queue, qid, "scenes.json"), None) if qid else None
        render = load(os.path.join(queue, qid, "render.json"), {}) if qid else {}
        brain = post.get("brain", {}) if post else {}
        posted = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        hook = " / ".join(x.replace("*", "") for x in scenes["hook"]) if scenes else (m.get("caption") or "").split("\n")[0][:40]
        duration = render.get("duration") or (26.0 if m.get("media_product_type") == "REELS" else None)
        avg_ms = num(i.get("ig_reels_avg_watch_time"))
        avg_s = round(avg_ms / 1000, 2) if avg_ms is not None else None
        rows.append({
            "fetched_at": fetched.astimezone(JST).strftime("%Y-%m-%d %H:%M"),
            "media_id": m["id"], "queue_id": qid or "(manual)",
            "posted_jst": posted.astimezone(JST).strftime("%Y-%m-%d %H:%M"),
            "age_h": round((fetched - posted).total_seconds() / 3600, 1),
            "kind": m.get("media_product_type"),
            "template": (post or {}).get("template") or ((post or {}).get("type") == "carousel" and "carousel") or ("reel_chat" if qid else "manual"),
            "theme": brain.get("theme", ""), "hook_type": brain.get("hookType", ""),
            "experiment": brain.get("experiment", ""), "variant": brain.get("variant", ""),
            "hook": hook, "duration_s": duration,
            "views": num(i.get("views")), "reach": num(i.get("reach")),
            "skip_rate": num(i.get("reels_skip_rate")), "avg_watch_s": avg_s,
            "watch_ratio": round(avg_s / duration, 3) if avg_s is not None and duration else None,
            "likes": num(i.get("likes")) if num(i.get("likes")) is not None else m.get("like_count"),
            "comments": num(i.get("comments")) if num(i.get("comments")) is not None else m.get("comments_count"),
            "saved": num(i.get("saved")), "shares": num(i.get("shares")),
            "total_interactions": num(i.get("total_interactions")),
            "follows": num(i.get("follows")), "profile_visits": num(i.get("profile_visits")),
            "permalink": m.get("permalink", ""),
        })
    rows.sort(key=lambda r: r["posted_jst"])

    acct = load(os.path.join(a.data, "account.json"), {}) or {}
    print(f"fetched {rows[0]['fetched_at'] if rows else meta.get('fetchedAt')} JST  followers={acct.get('followers_count')}  posts={acct.get('media_count')}")
    f = lambda v: "-" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))
    print(f"{'posted':<16} {'tmpl':<12} {'views':>5} {'reach':>5} {'skip%':>5} {'watch':>5} {'like':>4} {'save':>4} {'shr':>3} {'cmt':>3}  hook")
    for r in rows:
        print(f"{r['posted_jst']:<16} {r['template'][:12]:<12} {f(r['views']):>5} {f(r['reach']):>5} {f(r['skip_rate']):>5} {f(r['avg_watch_s']):>5} "
              f"{f(r['likes']):>4} {f(r['saved']):>4} {f(r['shares']):>3} {f(r['comments']):>3}  {r['hook']}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
    if a.csv:
        new = not os.path.exists(a.csv)
        os.makedirs(os.path.dirname(os.path.abspath(a.csv)), exist_ok=True)
        with open(a.csv, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
