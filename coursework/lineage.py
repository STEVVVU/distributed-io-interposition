# Copyright (C) 2026 Steven Vu
# SPDX-License-Identifier: GPL-2.0-only
"""Validate observed read outcomes and enumerate their minimal endpoint cuts."""

import argparse
import itertools
import json
import re
import sys


MAX_ENDPOINTS = 16
ENDPOINT = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def read_events(path):
    events = []
    request_ids = set()
    with open(path, encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"line {line_number}: event must be an object")
            request_id = event.get("request_id")
            if not isinstance(request_id, str) or not request_id or request_id in request_ids:
                raise ValueError(f"line {line_number}: request_id must be nonempty and unique")
            request_ids.add(request_id)
            result = event.get("result")
            attempts = event.get("attempts")
            lineage = event.get("lineage")
            expected = event.get("expected_sha256")
            actual = event.get("sha256")
            if result not in ("success", "unavailable", "wrong-bytes"):
                raise ValueError(f"line {line_number}: unknown result")
            if not isinstance(attempts, list) or not attempts or not isinstance(lineage, list):
                raise ValueError(f"line {line_number}: attempts and lineage are required")
            if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                raise ValueError(f"line {line_number}: invalid expected SHA-256")

            labels = []
            outcomes = []
            for attempt in attempts:
                if not isinstance(attempt, dict):
                    raise ValueError(f"line {line_number}: attempt must be an object")
                label = attempt.get("endpoint")
                path = attempt.get("path")
                outcome = attempt.get("outcome")
                if (not isinstance(label, str) or not ENDPOINT.fullmatch(label) or label in labels
                        or not isinstance(path, str) or not path):
                    raise ValueError(f"line {line_number}: invalid or repeated endpoint")
                if outcome not in ("success", "unavailable", "wrong-bytes"):
                    raise ValueError(f"line {line_number}: unknown attempt outcome")
                if outcome == "unavailable" and not isinstance(attempt.get("errno"), int):
                    raise ValueError(f"line {line_number}: unavailable attempt needs errno")
                labels.append(label)
                outcomes.append(outcome)

            if result == "success":
                if (not isinstance(actual, str) or not SHA256.fullmatch(actual) or actual != expected
                        or outcomes.count("success") != 1 or outcomes[-1] != "success"
                        or any(outcome != "unavailable" for outcome in outcomes[:-1])
                        or attempts[-1].get("sha256") != expected or lineage != [labels[-1]]):
                    raise ValueError(f"line {line_number}: successful lineage/oracle mismatch")
            elif lineage:
                raise ValueError(f"line {line_number}: failed outcome cannot carry lineage")
            elif result == "unavailable":
                if any(outcome != "unavailable" for outcome in outcomes):
                    raise ValueError(f"line {line_number}: unavailable result has a non-unavailable attempt")
                if not isinstance(event.get("final_errno"), int):
                    raise ValueError(f"line {line_number}: unavailable result needs final_errno")
            elif (outcomes[-1] != "wrong-bytes" or any(outcome != "unavailable" for outcome in outcomes[:-1])
                  or not isinstance(actual, str) or not SHA256.fullmatch(actual) or actual == expected
                  or attempts[-1].get("sha256") != actual):
                raise ValueError(f"line {line_number}: wrong-byte oracle mismatch")
            events.append(event)
    return events


def minimal_cuts(lineages):
    paths = [set(path) for path in lineages]
    if any(not path for path in paths):
        raise ValueError("successful lineages must be nonempty")
    endpoints = sorted(set().union(*paths)) if paths else []
    if len(endpoints) > MAX_ENDPOINTS:
        raise ValueError(f"at most {MAX_ENDPOINTS} endpoints can be enumerated")

    cuts = []
    for width in range(1, len(endpoints) + 1):
        for candidate in itertools.combinations(endpoints, width):
            cut = set(candidate)
            if any(set(known) <= cut for known in cuts):
                continue
            if all(cut & path for path in paths):
                cuts.append(candidate)
    return [list(cut) for cut in cuts]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", help="JSONL events recorded by the owned read workload")
    args = parser.parse_args(argv)
    try:
        events = read_events(args.events)
        paths = [event["lineage"] for event in events if event["result"] == "success"]
        print(json.dumps({"successful_lineages": paths, "minimal_cuts": minimal_cuts(paths)}, sort_keys=True))
    except (OSError, ValueError) as exc:
        print(f"lineage: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
