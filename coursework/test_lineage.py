# Copyright (C) 2026 Steven Vu
# SPDX-License-Identifier: GPL-2.0-only
import json
import tempfile
import unittest
from pathlib import Path

from lineage import minimal_cuts, read_events
from workload import EXPECTED_SHA256


def event(request_id, endpoint, result="success", digest=EXPECTED_SHA256):
    if result == "success":
        attempts = [{"endpoint": endpoint, "path": f"/chirp/127.0.0.1:9000/{endpoint}",
                     "outcome": "success", "sha256": digest}]
        lineage = [endpoint]
    elif result == "unavailable":
        attempts = [{"endpoint": endpoint, "path": f"/chirp/127.0.0.1:9000/{endpoint}",
                     "outcome": "unavailable", "errno": 111}]
        lineage = []
    else:
        attempts = [{"endpoint": endpoint, "path": f"/chirp/127.0.0.1:9000/{endpoint}",
                     "outcome": "wrong-bytes", "sha256": digest}]
        lineage = []
    return {
        "request_id": request_id, "attempts": attempts, "lineage": lineage, "result": result,
        "expected_sha256": EXPECTED_SHA256, "sha256": digest if result != "unavailable" else None,
        **({"final_errno": 111} if result == "unavailable" else {}),
    }


class LineageTests(unittest.TestCase):
    def test_alternate_observed_paths_infer_their_joint_minimal_cut(self):
        self.assertEqual(minimal_cuts([["A"], ["B"]]), [["A", "B"]])

    def test_all_minimal_hitting_sets_are_returned(self):
        self.assertEqual(minimal_cuts([["A", "B"], ["A", "C"]]), [["A"], ["B", "C"]])

    def test_failed_or_wrong_byte_runs_do_not_become_lineages(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "events.jsonl"
            rows = [event("a", "A"), event("bad", "B", "wrong-bytes", "0" * 64), event("down", "B", "unavailable")]
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            observed = read_events(trace)
        paths = [row["lineage"] for row in observed if row["result"] == "success"]
        self.assertEqual(paths, [["A"]])
        self.assertEqual(minimal_cuts(paths), [["A"]])

    def test_success_cannot_claim_wrong_bytes_as_a_good_path(self):
        bad = event("bad", "B", "success", "0" * 64)
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "events.jsonl"
            trace.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "oracle mismatch"):
                read_events(trace)

    def test_failure_cannot_smuggle_a_success_lineage(self):
        bad = event("bad", "A", "unavailable")
        bad["lineage"] = ["A"]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "events.jsonl"
            trace.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot carry lineage"):
                read_events(trace)

    def test_empty_paths_and_unbounded_endpoint_sets_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonempty"):
            minimal_cuts([[]])
        with self.assertRaisesRegex(ValueError, "at most"):
            minimal_cuts([[f"n{i}" for i in range(17)]])


if __name__ == "__main__":
    unittest.main()
