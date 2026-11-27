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
        record(self.data, "example", "paid", "stripe:test", "kailoop_consult", 49800, True)
        self.assertEqual(report(self.data)["recordedGrossJPY"], 0)
        with self.assertRaises(ValueError):
            record(self.data, "example", "refund", "refund:bad", "kailoop_consult", 49800)
        record(self.data, "example", "paid", "note:real", "note_delegation", 1980)
        self.assertTrue(record(self.data, "example", "paid", "note:real", "note_delegation", 1980)["duplicate"])
        with self.assertRaises(ValueError):
            record(self.data, "example", "paid", "note:real", "note_delegation", 2000)
        record(self.data, "example", "refund", "note:refund", "note_delegation", 1980)
        with self.assertRaises(ValueError):
            record(self.data, "example", "refund", "note:again", "note_delegation", 1)
        self.assertEqual(report(self.data)["recordedGrossJPY"], 1980)
        self.assertEqual(report(self.data)["recordedRefundJPY"], 1980)

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
