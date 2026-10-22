# Copyright (C) 2026 Steven Vu
# SPDX-License-Identifier: GPL-2.0-only
import errno
import json
import tempfile
import unittest
from pathlib import Path

from workload import EXPECTED_SHA256, PAYLOAD, lifecycle, read_alternates
from verify import (check_catalog_registration_disabled, check_runtime_binaries,
                    finalize_state, persist_state, RUNTIME_BINARIES)


class WorkloadTests(unittest.TestCase):
    def test_catalog_check_ignores_owned_commands_and_checks_each_chirp_log(self):
        with tempfile.TemporaryDirectory() as directory:
            debug = Path(directory) / "chirp.debug.log"
            debug.write_text("server started\n", encoding="utf-8")
            checked = check_catalog_registration_disabled([
                {"name": "configure", "log": "configure.log"},
                {"name": "chirp-A-1", "debug_log": str(debug)},
            ])
        self.assertEqual(checked, [str(debug)])

    def test_catalog_check_rejects_registration_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            debug = Path(directory) / "chirp.debug.log"
            debug.write_text("catalog update\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "registration was not demonstrably disabled"):
                check_catalog_registration_disabled([{"name": "chirp-A-1", "debug_log": str(debug)}])

    def test_runtime_build_check_requires_chirp_and_parrot_executables(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            missing = check_runtime_binaries(checkout)
            self.assertFalse(missing["ready"])
            for relative_path in RUNTIME_BINARIES.values():
                binary = checkout / relative_path
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_bytes(b"fixture executable")
                binary.chmod(0o700)
            complete = check_runtime_binaries(checkout)
        self.assertTrue(complete["ready"], complete)
        self.assertTrue(all(item["exists"] and item["executable"]
                            for item in complete["checks"].values()))

    def test_state_is_atomically_persisted_without_live_process_handles(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            state = {
                "evidence_dir": str(evidence), "passed": False,
                "_active_processes": [(object(), {})],
            }
            persist_state(state)
            saved = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
            leftovers = list(evidence.glob(".result-*.tmp"))
        self.assertEqual(saved, {"evidence_dir": str(evidence), "passed": False})
        self.assertEqual(leftovers, [])

    def test_behavior_success_is_not_terminal_success_when_cleanup_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            state = {"evidence_dir": directory, "behavior_passed": True, "_active_processes": []}
            finalize_state(state, all_stopped=True, cleanup_errors=["fixture cleanup failure"],
                           scratch_removed=False)
            saved = json.loads((Path(directory) / "result.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["behavior_passed"])
        self.assertFalse(saved["cleanup"])
        self.assertFalse(saved["passed"])

    def test_cleanup_requires_every_owned_process_group_to_be_reaped(self):
        with tempfile.TemporaryDirectory() as directory:
            live_process = object()
            state = {
                "evidence_dir": directory, "behavior_passed": True,
                "owned_processes": [{"pid": 123, "status": "running"}],
                "_active_processes": [(live_process, {"pid": 123})],
            }
            finalize_state(state, all_stopped=True, cleanup_errors=[], scratch_removed=True)
            saved = json.loads((Path(directory) / "result.json").read_text(encoding="utf-8"))
        self.assertFalse(saved["reaped_owned_processes"])
        self.assertFalse(saved["cleanup"])
        self.assertFalse(saved["passed"])

    def test_native_lifecycle_uses_posix_file_operations_and_reports_missing_errno(self):
        with tempfile.TemporaryDirectory() as directory:
            output = lifecycle(str(Path(directory) / "lifecycle"))
            stored = (Path(directory) / "lifecycle" / "payload.bin").read_bytes()
        self.assertEqual(stored, PAYLOAD)
        self.assertEqual(output["write_result"], len(PAYLOAD))
        self.assertEqual(output["read_bytes"], len(PAYLOAD))
        self.assertEqual(output["missing_errno"], errno.ENOENT)

    def test_alternate_reader_records_good_wrong_and_unavailable_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "good"
            bad = root / "bad"
            trace = root / "events.jsonl"
            good.write_bytes(PAYLOAD)
            bad.write_bytes(b"corrupt fixture")

            success = read_alternates([("A", str(good))], EXPECTED_SHA256, "good", trace)
            wrong = read_alternates([("B", str(bad))], EXPECTED_SHA256, "wrong", trace)
            unavailable = read_alternates([("C", str(root / "missing"))], EXPECTED_SHA256, "down", trace)
            events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([success["result"], wrong["result"], unavailable["result"]],
                         ["success", "wrong-bytes", "unavailable"])
        self.assertEqual([event["result"] for event in events],
                         ["success", "wrong-bytes", "unavailable"])
        self.assertEqual([event["lineage"] for event in events], [["A"], [], []])


if __name__ == "__main__":
    unittest.main()
