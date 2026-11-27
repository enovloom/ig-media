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
from zoneinfo import ZoneInfo

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


def record(data, handle, kind, source_ref, offer=None, amount=None, test=False,
           *, order_ref=None, occurred_at=None, attribution_ref=None, fee_jpy=None):
    source_ref = source_ref.strip()
    attribution_ref = attribution_ref.strip() if attribution_ref else None
    if kind not in KINDS or not source_ref.strip():
        raise ValueError("known event kind and actual source reference required")
    financial = kind in ("paid", "refund")
    handle = normalize(handle) if handle else None
    lead = next((x for x in data["leads"] if x["handle"] == handle), None) if handle else None
    if (handle or not financial) and not lead:
        raise ValueError("lead missing")
    if financial and (not order_ref or not order_ref.strip() or not occurred_at):
        raise ValueError("payment/refund requires actual order reference and source timestamp")
    order_ref = order_ref.strip() if order_ref else None
    now = datetime.now(timezone.utc)
    at = datetime.fromisoformat(occurred_at) if occurred_at else now
    if at.tzinfo is None or at > now:
        raise ValueError("source timestamp must include timezone and cannot be in the future")
    if fee_jpy is not None and (not financial or type(fee_jpy) is not int or fee_jpy < 0):
        raise ValueError("fee must be a nonnegative integer yen amount on a financial event")
    order_events = [x for x in data["events"] if order_ref and x.get("orderRef") == order_ref and x["test"] == test]
    payment = next((x for x in order_events if x["kind"] == "paid"), None)
    if kind == "refund" and payment:
        if payment["offer"] != offer or at < datetime.fromisoformat(payment["occurredAt"]):
            raise ValueError("refund offer/timestamp does not match its payment")
        if lead and lead["id"] != payment["leadId"]:
            raise ValueError("refund lead does not match its payment")
        if attribution_ref and attribution_ref != payment.get("attributionRef"):
            raise ValueError("refund cannot change payment attribution")
        attribution_ref = payment.get("attributionRef")
    previous = next((x for x in data["events"] if x["sourceRef"] == source_ref), None)
    payload = {"leadId": payment["leadId"] if kind == "refund" and payment else (lead["id"] if lead else None), "kind": kind, "sourceRef": source_ref,
               "offer": offer, "amountJPY": amount, "test": test}
    if financial:
        payload.update(orderRef=order_ref.strip(), occurredAt=at.isoformat(),
                       attributionRef=attribution_ref or None, feeJPY=fee_jpy)
    elif occurred_at:
        payload["occurredAt"] = at.isoformat()
    if previous:
        if all(previous.get(k) == v for k, v in payload.items()):
            return {"duplicate": True, "event": previous}
        raise ValueError("source reference already used with different facts")
    if kind == "paid" and payment:
        raise ValueError("order already recorded; do not count email and dashboard twice")
    related = [x for x in data["events"] if lead and x["leadId"] == lead["id"]]
    if kind == "contacted" and any(x["kind"] in ("contacted", "declined", "unreachable") for x in related):
        raise ValueError("repeat outreach blocked; inspect the existing conversation")
    if kind == "offer" and any(x["kind"] == "declined" for x in related):
        raise ValueError("declined lead: do not send another offer")
    if kind in ("paid", "refund"):
        if not offer or type(amount) is not int or amount <= 0:
            raise ValueError("payment/refund requires offer and positive integer yen amount")
        balance = sum((1 if x["kind"] == "paid" else -1) * x["amountJPY"] for x in order_events
                      if x["offer"] == offer and x["test"] == test and x["kind"] in ("paid", "refund"))
        if kind == "refund" and amount > balance:
            raise ValueError("refund exceeds recorded payment for this order and offer")
    elif amount is not None:
        raise ValueError("only paid/refund events may contain money")
    event = {**payload, "occurredAt": at.isoformat(), "recordedAt": now.isoformat()}
    data["events"].append(event)
    return {"duplicate": False, "event": event}


def report(data, month=None):
    if month:
        datetime.strptime(month, "%Y-%m")
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError("month must be YYYY-MM")
    all_real = [x for x in data["events"] if not x["test"]]
    def in_month(event):
        if not month:
            return True
        stamp = event.get("occurredAt")
        return bool(stamp and datetime.fromisoformat(stamp).astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m") == month)
    events = [x for x in all_real if in_month(x)]
    paid = [x for x in events if x["kind"] == "paid"]
    refunds = [x for x in events if x["kind"] == "refund"]
    gross, returned = sum(x["amountJPY"] for x in paid), sum(x["amountJPY"] for x in refunds)
    attributed = [x for x in events if x.get("attributionRef") and x["kind"] in ("paid", "refund")]
    money = paid + refunds
    return {"coverage": "記録済みの証拠のみ。金額は顧客の支払額（税・手数料控除前）、会計売上や利益ではない。流入元の証拠がない購入はInstagramの成果に含めない",
            "monthJST": month,
            "leads": len(data["leads"]), "events": {k: sum(x["kind"] == k for x in events) for k in KINDS},
            "recordedGrossJPY": gross, "recordedRefundJPY": returned,
            "recordedNetBeforeFeesJPY": gross - returned,
            "instagramAttributedNetBeforeFeesJPY": sum((1 if x["kind"] == "paid" else -1) * x["amountJPY"] for x in attributed),
            "paidOrdersWithUnknownAttribution": sum(not x.get("attributionRef") for x in paid),
            "knownFeesJPY": sum(x.get("feeJPY") or 0 for x in money),
            "financialEventsWithUnknownFees": sum(x.get("feeJPY") is None for x in money),
            "eventsWithoutSourceTimestamp": sum(not x.get("occurredAt") for x in all_real),
            "testEventsExcluded": sum(x["test"] for x in data["events"])}


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
    rec.add_argument("--handle")
    rec.add_argument("--kind", choices=KINDS, required=True)
    rec.add_argument("--source-ref", required=True)
    rec.add_argument("--offer")
    rec.add_argument("--amount-jpy", type=int)
    rec.add_argument("--test", action="store_true")
    rec.add_argument("--order-ref", help="Actual order/payment ID; no customer name needed")
    rec.add_argument("--occurred-at", help="Actual source timestamp, ISO 8601 with timezone")
    rec.add_argument("--attribution-ref", help="Evidence that this purchase came from Instagram; omit if unknown")
    rec.add_argument("--fee-jpy", type=int, help="Verified fee only; omit if unknown")
    link = commands.add_parser("link")
    link.add_argument("--handle", required=True)
    link.add_argument("--offer", required=True)
    link.add_argument("--demo", action="store_true")
    exclude = commands.add_parser("exclude")
    exclude.add_argument("--org", required=True)
    exclude.add_argument("--source-ref", required=True)
    status = commands.add_parser("status")
    status.add_argument("--month", help="YYYY-MM, Japan time; omit for all recorded evidence")
    a = ap.parse_args()
    offers = json.loads((Path(__file__).resolve().parents[1] / "commerce.json").read_text())["offers"]
    if getattr(a, "offer", None) and a.offer not in offers:
        ap.error("unknown offer")
    try:
        with ledger(a.store) as data:
            if a.cmd == "add":
                result = add_lead(data, a.handle, a.org, a.reason, a.post_url)
            elif a.cmd == "record":
                result = record(data, a.handle, a.kind, a.source_ref, a.offer, a.amount_jpy, a.test,
                                order_ref=a.order_ref, occurred_at=a.occurred_at,
                                attribution_ref=a.attribution_ref, fee_jpy=a.fee_jpy)
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
                result = report(data, a.month)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        ap.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()

