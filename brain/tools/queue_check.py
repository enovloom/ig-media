#!/usr/bin/env python3
"""Read-only check of future posting slots. No credentials or network access."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def read(path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else fallback


def check(repo, now):
    settings = read(repo / "brain/settings.json")
    offers = read(repo / "brain/commerce.json", {}).get("offers", {})
    state = read(repo / "queue/state.json", {})
    held = set(read(repo / "auto/hold.json", {"hold": []})["hold"])
    errors, active, scheduled, seen = [], [], [], set()
    jst = ZoneInfo("Asia/Tokyo")
    today = now.astimezone(jst).date()
    for root in ("queue", "auto/queue"):
        for path in sorted((repo / root).glob("*/post.json")):
            ident = path.parent.name
            try:
                post = read(path)
                at = datetime.fromisoformat(post["publishAt"])
                if at.tzinfo is None:
                    raise ValueError("publishAt requires timezone")
                status = state.get(ident, {}).get("status")
                if ident in held or at.astimezone(jst).date() < today or status == "failed":
                    continue
                if not (post.get("approved") or post.get("autoApprove")):
                    continue
                scheduled.append({"id": ident, "at": at, "sales": bool(post.get("brain", {}).get("offerId"))})
                if at <= now or status in ("published", "publishing"):
                    continue
                if ident in seen:
                    errors.append(f"duplicate ID across queue roots: {ident}")
                seen.add(ident)
                caption = (path.parent / post["captionFile"]).read_text(encoding="utf-8")
                if len(caption) > 2200:
                    errors.append(f"caption exceeds 2200 chars: {ident}")
                brain = post.get("brain", {})
                offer_id = brain.get("offerId")
                if offer_id:
                    if offer_id not in offers:
                        errors.append(f"unknown offer: {ident}: {offer_id}")
                    elif post.get("source") != offers[offer_id]["url"]:
                        errors.append(f"offer URL mismatch: {ident}")
                    if offer_id == "kailoop_consult" and "プロフィールのリンク" in caption:
                        errors.append(f"profile link is not KAILOOP: {ident}")
                active.append({"id": ident, "at": at, "sales": bool(offer_id)})
            except (KeyError, ValueError, OSError, TypeError) as exc:
                errors.append(f"invalid queue item {ident}: {exc}")
    days = Counter(p["at"].astimezone(jst).date().isoformat() for p in scheduled)
    slots = Counter(p["at"].astimezone(timezone.utc).isoformat() for p in active)
    sales = Counter(p["at"].astimezone(jst).date().isoformat() for p in scheduled if p["sales"])
    for day, count in days.items():
        if count > settings["postsPerDay"]:
            errors.append(f"daily cap exceeded: {day}: {count}")
    for slot, count in slots.items():
        if count > 1:
            errors.append(f"duplicate slot: {slot}: {count}")
    for day, count in sales.items():
        if count > 1:
            errors.append(f"sales CTA cap exceeded: {day}: {count}")
    return {"ok": not errors, "futurePosts": len(active), "days": dict(days), "errors": errors}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    a = ap.parse_args()
    result = check(a.repo, datetime.now(timezone.utc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()

