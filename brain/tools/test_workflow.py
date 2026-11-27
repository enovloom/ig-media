import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from outreach import add_lead, empty, record, report
from queue_check import check


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = empty()
        add_lead(self.data, "Example", "same-org", "observed reason", "https://www.instagram.com/p/example/")

    def test_cross_account_duplicate_and_repeat_contact(self):
        with self.assertRaises(ValueError):
            add_lead(self.data, "another", "same-org", "reason", "https://www.instagram.com/p/other/")
        record(self.data, "@EXAMPLE", "contacted", "instagram:real1")
        self.assertTrue(record(self.data, "example", "contacted", "instagram:real1")["duplicate"])
        with self.assertRaises(ValueError):
            record(self.data, "example", "contacted", "instagram:real2")

    def test_real_money_separate_from_tests_and_refunds(self):
        facts = {"order_ref": "order:1", "occurred_at": "2026-11-01T00:00:00+00:00"}
        record(self.data, "example", "paid", "stripe:test", "kailoop_consult", 49800, True, **facts)
        self.assertEqual(report(self.data)["recordedGrossJPY"], 0)
        with self.assertRaises(ValueError):
            record(self.data, "example", "refund", "refund:bad", "kailoop_consult", 49800, **facts)
        record(self.data, "example", "paid", "note:real", "note_delegation", 1980, **facts)
        self.assertTrue(record(self.data, "example", "paid", "note:real", "note_delegation", 1980, **facts)["duplicate"])
        with self.assertRaises(ValueError):
            record(self.data, "example", "paid", "note:real", "note_delegation", 2000, **facts)
        record(self.data, "example", "refund", "note:refund", "note_delegation", 1980, **facts)
        with self.assertRaises(ValueError):
            record(self.data, "example", "refund", "note:again", "note_delegation", 1, **facts)
        self.assertEqual(report(self.data)["recordedGrossJPY"], 1980)
        self.assertEqual(report(self.data)["recordedRefundJPY"], 1980)

    def test_purchase_without_instagram_identity_is_not_attributed(self):
        facts = {"order_ref": "note:order-a", "occurred_at": "2026-10-31T15:01:00+00:00"}
        record(self.data, None, "paid", "note:receipt", "note_delegation", 1980, **facts)
        summary = report(self.data, "2026-11")
        self.assertEqual(summary["recordedGrossJPY"], 1980)
        self.assertEqual(summary["instagramAttributedNetBeforeFeesJPY"], 0)
        self.assertEqual(summary["paidOrdersWithUnknownAttribution"], 1)
        self.assertEqual(summary["financialEventsWithUnknownFees"], 1)
        self.assertEqual(report(self.data, "2026-10")["recordedGrossJPY"], 0)
        with self.assertRaises(ValueError):
            record(self.data, None, "paid", "note:dashboard-same-order", "note_delegation", 1980, **facts)

    def test_refund_uses_order_balance_and_original_attribution(self):
        facts = {"order_ref": "order:attributed", "occurred_at": "2026-11-01T00:00:00+00:00"}
        record(self.data, None, "paid", "receipt:a", "note_delegation", 1980,
               attribution_ref="customer-reply:instagram-source", fee_jpy=0, **facts)
        with self.assertRaises(ValueError):
            record(self.data, None, "refund", "refund:too-early", "note_delegation", 100,
                   order_ref=facts["order_ref"], occurred_at="2026-10-01T00:00:00+00:00")
        record(self.data, None, "refund", "refund:a", "note_delegation", 500, **facts)
        summary = report(self.data)
        self.assertEqual(summary["instagramAttributedNetBeforeFeesJPY"], 1480)
        self.assertEqual(summary["recordedNetBeforeFeesJPY"], 1480)
        with self.assertRaises(ValueError):
            record(self.data, None, "refund", "refund:wrong-order", "note_delegation", 1,
                   order_ref="other-order", occurred_at=facts["occurred_at"])

    def test_payment_needs_real_date_and_order(self):
        with self.assertRaises(ValueError):
            record(self.data, None, "paid", "receipt:missing", "note_delegation", 1980)
        with self.assertRaises(ValueError):
            record(self.data, None, "paid", "receipt:future", "note_delegation", 1980,
                   order_ref="future-order", occurred_at="9999-01-01T00:00:00+00:00")

    def test_queue_collision_and_hold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def put(path, value):
                p = root / path; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(value))
            put("brain/settings.json", {"postsPerDay": 1})
            for name in ("one", "two"):
                put(f"auto/queue/{name}/post.json", {"publishAt": "2026-11-29T12:00:00+09:00", "approved": True, "captionFile": "caption.txt"})
                (root / f"auto/queue/{name}/caption.txt").write_text("example")
            now = datetime(2026, 11, 27, tzinfo=timezone.utc)
            result = check(root, now)
            self.assertFalse(result["ok"])
            self.assertTrue(any("duplicate slot" in x for x in result["errors"]))
            put("auto/hold.json", {"hold": ["two"]})
            self.assertTrue(check(root, now)["ok"])
            put("queue/state.json", {"one": {"status": "publishing"}})
            self.assertEqual(check(root, now)["futurePosts"], 0)

            # Today's already-published post still consumes the daily cap.
            put("auto/hold.json", {"hold": []})
            put("queue/state.json", {"one": {"status": "published"}})
            put("auto/queue/two/post.json", {"publishAt": "2026-11-29T18:00:00+09:00", "approved": True, "captionFile": "caption.txt"})
            result = check(root, datetime(2026, 11, 29, 4, tzinfo=timezone.utc))
            self.assertTrue(any("daily cap" in x for x in result["errors"]))


if __name__ == "__main__":
    unittest.main()
