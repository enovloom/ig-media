#!/usr/bin/env python3
"""Private contact/evidence ledger. NEVER sends messages or initiates payments."""
import argparse
import fcntl
import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

KINDS = ("contacted", "replied", "consultation", "demo", "offer", "paid", "refund", "used", "declined", "unreachable")


def normalize(value):
    return value.strip().lstrip("@").casefold()


def empty():
    return {"schemaVersion": 1, "leads": [], "events": [], "exclusions": []}


def add_lead(data, handle, org, reason, post_url):
    handle, org = normalize(handle), normalize(org)
    if not re.fullmatch(r"[a-z0-9._]{1,30}", handle) or not org or not reason:
        raise ValueError("valid handle, organization key and evidence-based reason required")
    if not post_url.startswith("https://www.instagram.com/"):
        raise ValueError("use the observed Instagram post URL")
    if any(x["org"] == org for x in data["exclusions"]):
        raise ValueError("organization excluded; check existing outreach")
    if any(x["handle"] == handle or x["org"] == org for x in data["leads"]):
        raise ValueError("same handle or organization already recorded; reuse its existing lead")
    lead = {"id": uuid.uuid4().hex[:16], "handle": handle, "org": org,
            "reason": reason, "postUrl": post_url, "dmReachability": "unknown"}
    data["leads"].append(lead)
    return lead


def record(data, handle, kind, source_ref, offer=None, amount=None, test=False):
    if kind not in KINDS or not source_ref.strip():
        raise ValueError("known event kind and actual source reference required")
    handle = normalize(handle)
    lead = next((x for x in data["leads"] if x["handle"] == handle), None)
    if not lead:
        raise ValueError("lead missing")
    previous = next((x for x in data["events"] if x["sourceRef"] == source_ref), None)
    payload = {"leadId": lead["id"], "kind": kind, "sourceRef": source_ref,
               "offer": offer, "amountJPY": amount, "test": test}
    if previous:
        if all(previous.get(k) == v for k, v in payload.items()):
            return {"duplicate": True, "event": previous}
        raise ValueError("source reference already used with different facts")
    related = [x for x in data["events"] if x["leadId"] == lead["id"]]
    if kind == "contacted" and any(x["kind"] in ("contacted", "declined", "unreachable") for x in related):
        raise ValueError("repeat outreach blocked; inspect the existing conversation")
    if kind == "offer" and any(x["kind"] == "declined" for x in related):
        raise ValueError("declined lead: do not send another offer")
    if kind in ("paid", "refund"):
        if not offer or type(amount) is not int or amount <= 0:
            raise ValueError("payment/refund requires offer and positive integer yen amount")
        balance = sum((1 if x["kind"] == "paid" else -1) * x["amountJPY"] for x in related
                      if x["offer"] == offer and x["test"] == test and x["kind"] in ("paid", "refund"))
        if kind == "refund" and amount > balance:
            raise ValueError("refund exceeds recorded payment for this lead and offer")
    elif amount is not None:
        raise ValueError("only paid/refund events may contain money")
    event = {**payload, "recordedAt": datetime.now(timezone.utc).isoformat()}
    data["events"].append(event)
    return {"duplicate": False, "event": event}


def report(data):
    events = [x for x in data["events"] if not x["test"]]
    paid = [x for x in events if x["kind"] == "paid"]
    refunds = [x for x in events if x["kind"] == "refund"]
    return {"coverage": "記録済みの証拠のみ。全体の購入件数・売上、Instagramへの帰属は別途確認が必要",
            "leads": len(data["leads"]), "events": {k: sum(x["kind"] == k for x in events) for k in KINDS},
            "recordedGrossJPY": sum(x["amountJPY"] for x in paid),
            "recordedRefundJPY": sum(x["amountJPY"] for x in refunds),
            "testEventsExcluded": len(data["events"]) - len(events)}


@contextmanager
def ledger(store):
    store = store.resolve()
    existing = store
    while not existing.exists():
        existing = existing.parent
    origin = subprocess.check_output(["git", "-C", str(existing), "remote", "get-url", "origin"], text=True).strip()
    if not re.search(r"(?:github\.com[:/])enovloom/notes(?:\.git)?$", origin):
        raise ValueError("store must be inside the private enovloom/notes checkout")
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (store / ".ledger.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = store / "ledger.json"
        data = json.loads(path.read_text()) if path.exists() else empty()
        before = json.dumps(data, ensure_ascii=False, sort_keys=True)
        yield data
        if before != json.dumps(data, ensure_ascii=False, sort_keys=True):
            fd, temp = tempfile.mkstemp(prefix=".ledger-", dir=store)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.write("\n"); f.flush(); os.fsync(f.fileno())
                os.replace(temp, path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", type=Path, required=True)
    commands = ap.add_subparsers(dest="cmd", required=True)
    add = commands.add_parser("add")
    for key in ("handle", "org", "reason", "post-url"):
        add.add_argument("--" + key, required=True)
    rec = commands.add_parser("record")
    rec.add_argument("--handle", required=True)
    rec.add_argument("--kind", choices=KINDS, required=True)
    rec.add_argument("--source-ref", required=True)
    rec.add_argument("--offer")
    rec.add_argument("--amount-jpy", type=int)
    rec.add_argument("--test", action="store_true")
    link = commands.add_parser("link")
    link.add_argument("--handle", required=True)
    link.add_argument("--offer", required=True)
    link.add_argument("--demo", action="store_true")
    exclude = commands.add_parser("exclude")
    exclude.add_argument("--org", required=True)
    exclude.add_argument("--source-ref", required=True)
    commands.add_parser("status")
    a = ap.parse_args()
    offers = json.loads((Path(__file__).resolve().parents[1] / "commerce.json").read_text())["offers"]
    if getattr(a, "offer", None) and a.offer not in offers:
        ap.error("unknown offer")
    try:
        with ledger(a.store) as data:
            if a.cmd == "add":
                result = add_lead(data, a.handle, a.org, a.reason, a.post_url)
            elif a.cmd == "record":
                result = record(data, a.handle, a.kind, a.source_ref, a.offer, a.amount_jpy, a.test)
            elif a.cmd == "link":
                lead = next((x for x in data["leads"] if x["handle"] == normalize(a.handle)), None)
                if not lead:
                    raise ValueError("lead missing")
                base = offers[a.offer].get("demoUrl") if a.demo else offers[a.offer]["url"]
                if not base:
                    raise ValueError("offer has no public demo")
                parts = urlsplit(base)
                query = dict(parse_qsl(parts.query))
                query.update(utm_source="instagram", utm_medium="dm", utm_campaign=a.offer, utm_content=lead["id"])
                result = {"url": urlunsplit(parts._replace(query=urlencode(query))), "note": "識別用URLのみ。割引・クリック計測・購入帰属の機能はない"}
            elif a.cmd == "exclude":
                org = normalize(a.org)
                if not org or not a.source_ref.strip():
                    raise ValueError("organization and evidence required")
                if not any(x["org"] == org for x in data["exclusions"]):
                    data["exclusions"].append({"org": org, "sourceRef": a.source_ref})
                result = {"excluded": org}
            else:
                result = report(data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        ap.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()

