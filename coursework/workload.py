# Copyright (C) 2026 Steven Vu
# SPDX-License-Identifier: GPL-2.0-only
"""Small deterministic filesystem journeys run natively or under parrot_run."""

import argparse
import errno
import hashlib
import json
import os
import re
import sys


PAYLOAD = b"owned distributed I/O fixture\n"
EXPECTED_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()
ENDPOINT = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def lifecycle(root):
    os.mkdir(root, 0o700)
    written = 0
    descriptor = os.open(os.path.join(root, "payload.bin"),
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        while written < len(PAYLOAD):
            count = os.write(descriptor, PAYLOAD[written:])
            if count <= 0:
                raise OSError(errno.EIO, "write made no progress")
            written += count
    finally:
        os.close(descriptor)

    previous = os.getcwd()
    os.chdir(root)
    try:
        chdir_result = 0
        details = os.stat("payload.bin")
        descriptor = os.open("payload.bin", os.O_RDONLY | getattr(os, "O_BINARY", 0))
        chunks = []
        try:
            while True:
                chunk = os.read(descriptor, 4096)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(descriptor)
        data = b"".join(chunks)
        try:
            os.stat("missing.bin")
        except OSError as exc:
            missing_errno = exc.errno
        else:
            raise AssertionError("missing.bin unexpectedly exists")
    finally:
        os.chdir(previous)

    result = {
        "mkdir_result": 0,
        "write_result": written,
        "write_close_result": 0,
        "chdir_result": chdir_result,
        "stat_size": details.st_size,
        "read_bytes": len(data),
        "read_sha256": hashlib.sha256(data).hexdigest(),
        "read_close_result": 0,
        "missing_errno": missing_errno,
    }
    if data != PAYLOAD or written != len(PAYLOAD) or details.st_size != len(PAYLOAD) or missing_errno != errno.ENOENT:
        raise AssertionError(f"filesystem result mismatch: {result}")
    return result


def read_alternates(endpoints, expected_sha256, request_id, trace_path):
    if not endpoints:
        raise ValueError("at least one endpoint is required")
    attempts = []
    for label, path in endpoints:
        try:
            with open(path, "rb") as source:
                data = source.read()
        except OSError as exc:
            attempts.append({"endpoint": label, "path": path, "outcome": "unavailable", "errno": exc.errno})
            continue

        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            attempts.append({"endpoint": label, "path": path, "outcome": "wrong-bytes", "sha256": actual})
            event = {
                "request_id": request_id, "attempts": attempts, "lineage": [],
                "result": "wrong-bytes", "expected_sha256": expected_sha256, "sha256": actual,
            }
            break
        attempts.append({"endpoint": label, "path": path, "outcome": "success", "sha256": actual})
        event = {
            "request_id": request_id, "attempts": attempts, "lineage": [label],
            "result": "success", "expected_sha256": expected_sha256, "sha256": actual,
        }
        break
    else:
        event = {
            "request_id": request_id, "attempts": attempts, "lineage": [],
            "result": "unavailable", "expected_sha256": expected_sha256,
            "sha256": None, "final_errno": attempts[-1]["errno"],
        }

    with open(trace_path, "a", encoding="utf-8") as trace:
        trace.write(json.dumps(event, sort_keys=True) + "\n")
        trace.flush()
        os.fsync(trace.fileno())
    return event


def parse_endpoint(value):
    label, separator, path = value.partition("=")
    if not separator or not ENDPOINT.fullmatch(label) or not path:
        raise argparse.ArgumentTypeError("endpoint must be NAME=PATH with a simple unique name")
    return label, path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    lifecycle_parser = subcommands.add_parser("lifecycle")
    lifecycle_parser.add_argument("--path", required=True)
    read_parser = subcommands.add_parser("read-alternates")
    read_parser.add_argument("--endpoint", action="append", type=parse_endpoint, required=True)
    read_parser.add_argument("--expected-sha256", required=True)
    read_parser.add_argument("--request-id", required=True)
    read_parser.add_argument("--trace", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "lifecycle":
            result = lifecycle(args.path)
            status = 0
        else:
            labels = [label for label, _ in args.endpoint]
            if len(labels) != len(set(labels)) or not SHA256.fullmatch(args.expected_sha256):
                raise ValueError("endpoint names must be unique and the expected digest must be SHA-256")
            result = read_alternates(args.endpoint, args.expected_sha256, args.request_id, args.trace)
            status = {"success": 0, "unavailable": 3, "wrong-bytes": 4}[result["result"]]
        print(json.dumps(result, sort_keys=True))
    except (OSError, AssertionError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "errno": getattr(exc, "errno", None)}, sort_keys=True), file=sys.stderr)
        return 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
