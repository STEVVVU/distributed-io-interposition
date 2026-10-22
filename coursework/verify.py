# Copyright (C) 2026 Steven Vu
# SPDX-License-Identifier: GPL-2.0-only
"""Build and exercise Parrot and Chirp in an owned Linux-only fixture."""

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from workload import EXPECTED_SHA256, PAYLOAD


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
RUN_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}\Z")
BUILD_FLAGS = [
    "--without-system-prune", "--without-system-umbrella",
    "--without-system-weaver", "--with-fuse-path", "no", "--with-readline-path", "no",
    "--with-perl-path", "no",
]
RUNTIME_BINARIES = {
    "chirp_server": Path("chirp/src/chirp_server"),
    "parrot_run": Path("parrot/src/parrot_run"),
}


def doctor():
    tools = {name: shutil.which(name) for name in ("gcc", "g++", "make", "perl", "bash", "python3", "git")}
    checks = {
        "linux": sys.platform.startswith("linux"),
        "x86_64": platform.machine().lower() in ("x86_64", "amd64"),
        "non_root": hasattr(os, "geteuid") and os.geteuid() != 0,
        "python3": sys.version_info >= (3, 8),
        "build_tools": all(tools.values()),
    }
    return {"checks": checks, "tools": tools, "ready": all(checks.values())}


def is_within(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def clean_environment(home, temp):
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(home),
        "TMPDIR": str(temp),
        "CATALOG_HOST": "",
        "USER": getpass.getuser(),
        "LOGNAME": getpass.getuser(),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def copy_checkout(destination):
    ignored = shutil.ignore_patterns(".git", ".local", ".pixi", "__pycache__", "*.pyc", "*.o", "*.a", "*.dylib", "config.mk")
    shutil.copytree(ROOT, destination, ignore=ignored, symlinks=True)


def check_runtime_binaries(checkout):
    checks = {}
    for name, relative_path in RUNTIME_BINARIES.items():
        binary = Path(checkout) / relative_path
        exists = binary.is_file()
        executable = exists and os.access(binary, os.X_OK)
        checks[name] = {"path": str(binary), "exists": exists, "executable": executable}
    return {"checks": checks, "ready": all(item["exists"] and item["executable"]
                                           for item in checks.values())}


def persist_state(state):
    """Atomically retain serializable state; private keys are in-memory only."""
    destination = Path(state["evidence_dir"]) / "result.json"
    serializable = {key: value for key, value in state.items() if not key.startswith("_")}
    handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".result-", suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(serializable, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def register_process(state, process, record):
    state.setdefault("owned_processes", []).append(record)
    state.setdefault("_active_processes", []).append((process, record))
    persist_state(state)


def unregister_process(state, process):
    state["_active_processes"] = [entry for entry in state.get("_active_processes", [])
                                  if entry[0] is not process]
    persist_state(state)


def finalize_state(state, all_stopped, cleanup_errors, scratch_removed):
    state["cleanup_errors"] = cleanup_errors
    processes_reaped = not state.get("_active_processes") and all(
        process.get("status") == "stopped" for process in state.get("owned_processes", []))
    state["cleanup"] = all_stopped and processes_reaped and not cleanup_errors and scratch_removed
    state["scratch_removed"] = scratch_removed
    state["passed"] = bool(state["behavior_passed"] and state["cleanup"] and not state.get("error"))
    state["reaped_owned_processes"] = processes_reaped
    persist_state(state)


def run_command(state, name, argv, cwd, log, env, timeout=1200, expected=(0,)):
    record = {"name": name, "argv": [str(value) for value in argv], "cwd": str(cwd), "log": str(log)}
    state.setdefault("commands", []).append(record)
    with log.open("wb") as output:
        process = subprocess.Popen([str(value) for value in argv], cwd=cwd, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        record["pid"] = process.pid
        record["process_group"] = process.pid
        record["status"] = "running"
        register_process(state, process, record)
        try:
            record["returncode"] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            record["timed_out"] = True
            raise RuntimeError(f"command timed out: {name}; see {log}")
        finally:
            stop_process(process, state, f"command-{name}")
            record["status"] = "stopped"
            record["returncode"] = process.returncode
            unregister_process(state, process)
    if record["returncode"] not in expected:
        raise RuntimeError(f"command failed ({record['returncode']}): {name}; see {log}")
    return record


def stop_process(process, state, label):
    record = {"name": label, "pid": process.pid}
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
    record["returncode"] = process.returncode
    if process.poll() is None:
        raise RuntimeError(f"owned process did not stop: {label} ({process.pid})")
    record["process_reaped"] = True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            raise RuntimeError(f"owned process group did not stop: {label} ({process.pid})")
    record["process_group_absent"] = True
    state.setdefault("stopped_processes", []).append(record)


class ChirpEndpoint:
    def __init__(self, label, store, scratch, evidence, username, env, state):
        self.label = label
        self.store = store
        self.scratch = scratch
        self.evidence = evidence
        self.username = username
        self.env = env
        self.state = state
        self.process = None
        self.process_record = None
        self.port = None
        self.last_port = None
        self.starts = 0

    def start(self, server_binary):
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError(f"endpoint {self.label} is already running")
        self.starts += 1
        transient = self.scratch / f"transient-{self.label}-{self.starts}"
        transient.mkdir()
        acl = self.scratch / f"acl-{self.label}-{self.starts}.txt"
        acl.write_text(f"unix:{self.username} rwlda\n", encoding="utf-8")
        port_file = self.scratch / f"port-{self.label}-{self.starts}.txt"
        port_file.unlink(missing_ok=True)
        stdout_log = self.evidence / f"chirp-{self.label}-{self.starts}.stdout.log"
        debug_log = self.evidence / f"chirp-{self.label}-{self.starts}.debug.log"
        argv = [
            server_binary, "--no-advertise", "--auth=unix", "--debug=all",
            f"--debug-file={debug_log}", "--debug-rotate-max=0", f"--default-acl={acl}",
            "--inherit-default-acl", "--interface=127.0.0.1", "--no-core-dump", "--parent-death",
            "--port=0", f"--port-file={port_file}", f"--root={self.store}", f"--transient={transient}",
        ]
        with stdout_log.open("wb") as log_stream:
            self.process = subprocess.Popen(
                [str(value) for value in argv], cwd=self.scratch, env=self.env,
                stdout=log_stream, stderr=subprocess.STDOUT, start_new_session=True,
            )
        process_record = {
            "name": f"chirp-{self.label}-{self.starts}", "pid": self.process.pid,
            "process_group": self.process.pid, "status": "running",
            "argv": [str(value) for value in argv], "stdout_log": str(stdout_log), "debug_log": str(debug_log),
        }
        self.process_record = process_record
        register_process(self.state, self.process, process_record)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"Chirp endpoint {self.label} exited; see {stdout_log}")
            if port_file.exists() and port_file.stat().st_size:
                value = port_file.read_text(encoding="ascii").strip()
                if not value.isdecimal() or not 1 <= int(value) <= 65535:
                    raise RuntimeError(f"Chirp endpoint {self.label} wrote an invalid port")
                self.port = int(value)
                self.last_port = self.port
                process_record["port"] = self.port
                return
            time.sleep(0.05)
        raise RuntimeError(f"Chirp endpoint {self.label} did not publish its owned port; see {stdout_log}")

    def stop(self):
        if self.process is not None:
            process = self.process
            stop_process(process, self.state, f"chirp-{self.label}-{self.starts}")
            self.process_record["status"] = "stopped"
            self.process = None
            self.process_record = None
            self.last_port = self.port
            self.port = None
            unregister_process(self.state, process)

    def path(self, relative):
        port = self.port if self.port is not None else self.last_port
        if port is None:
            raise RuntimeError(f"endpoint {self.label} is not running")
        return f"/chirp/127.0.0.1:{port}/{relative.lstrip('/')}"


def read_json_log(log):
    lines = log.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError(f"command produced no JSON output: {log}")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command output is not JSON: {log}") from exc


def run_lifecycle(state, workload, path, name, evidence, env, cwd, parrot=None):
    log = evidence / f"{name}.log"
    argv = [sys.executable, workload, "lifecycle", "--path", path]
    if parrot:
        argv = [parrot, "--no-chirp-catalog", "--chirp-auth=unix", "--debug=syscall",
                f"--debug-file={evidence / (name + '.parrot.log')}", "--timeout=5", *argv]
    run_command(state, name, argv, cwd, log, env, timeout=60)
    result = read_json_log(log)
    if result.get("read_sha256") != EXPECTED_SHA256 or result.get("read_bytes") != len(PAYLOAD):
        raise RuntimeError(f"lifecycle returned unexpected bytes: {name}")
    return result


def run_alternate(state, workload, endpoint_paths, trace, request_id, name, evidence, env, cwd,
                  parrot=None, expected_status=0):
    log = evidence / f"{name}.log"
    argv = [sys.executable, workload, "read-alternates", "--expected-sha256", EXPECTED_SHA256,
            "--request-id", request_id, "--trace", trace]
    for label, path in endpoint_paths:
        argv.extend(("--endpoint", f"{label}={path}"))
    if parrot:
        argv = [parrot, "--no-chirp-catalog", "--chirp-auth=unix", "--debug=syscall",
                f"--debug-file={evidence / (name + '.parrot.log')}", "--timeout=5", *argv]
    run_command(state, name, argv, cwd, log, env, timeout=60, expected=(expected_status,))
    return read_json_log(log)


def load_plan(state, lineage, events, name, evidence, env, cwd):
    log = evidence / f"{name}.log"
    run_command(state, name, [sys.executable, lineage, str(events)], cwd, log, env, timeout=30)
    plan = read_json_log(log)
    (evidence / f"{name}.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def exercise(args):
    root = ROOT.resolve()
    local = LOCAL.resolve()
    if not is_within(local, root):
        raise RuntimeError(".local resolves outside the checkout")
    verify_root = local / "verify"
    evidence_root = local / "evidence"
    if not is_within(verify_root, local) or not is_within(evidence_root, local):
        raise RuntimeError("verification roots resolve outside .local")
    run_dir = verify_root / args.run
    evidence = evidence_root / args.run
    if run_dir.exists() or evidence.exists():
        raise RuntimeError("run and evidence names must be fresh")
    if not RUN_NAME.fullmatch(args.run):
        raise RuntimeError("run name must use 1-32 letters, digits, underscores, or hyphens")
    scratch = run_dir / "scratch"
    checkout = scratch / "checkout"
    if not is_within(scratch, verify_root) or not is_within(evidence, evidence_root):
        raise RuntimeError("run paths escape their owned roots")

    evidence.mkdir(parents=True)
    scratch.mkdir(parents=True)
    state = {
        "run": args.run,
        "platform": {"system": platform.system(), "machine": platform.machine(), "python": sys.version},
        "passed": False,
        "cleanup": False,
        "behavior_passed": False,
        "evidence_dir": str(evidence),
        "scratch_dir": str(scratch),
        "_active_processes": [],
    }
    persist_state(state)
    endpoints = []
    scratch_removed = False
    try:
        state["source_head"] = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                                              capture_output=True, text=True).stdout.strip()
        health = doctor()
        state["doctor"] = health
        if not health["ready"]:
            raise RuntimeError(f"doctor failed: {health}")
        home = scratch / "home"
        temp = scratch / "tmp"
        home.mkdir()
        temp.mkdir()
        env = clean_environment(home, temp)
        copy_checkout(checkout)
        state["checkout_copy"] = str(checkout)
        state["build_flags"] = BUILD_FLAGS
        run_command(state, "configure", ["./configure", f"--prefix={scratch / 'install'}", *BUILD_FLAGS],
                    checkout, evidence / "configure.log", env)
        run_command(state, "make-runtime", ["make", "-j2", "dttools", "chirp", "parrot"],
                    checkout, evidence / "make-runtime.log", env)
        binary_health = check_runtime_binaries(checkout)
        state["runtime_binaries"] = binary_health
        persist_state(state)
        if not binary_health["ready"]:
            missing = [name for name, item in binary_health["checks"].items()
                       if not item["exists"] or not item["executable"]]
            raise RuntimeError(f"runtime build completed without required executable(s): {missing}")

        chirp = checkout / "chirp" / "src" / "chirp_server"
        parrot = checkout / "parrot" / "src" / "parrot_run"
        workload = checkout / "coursework" / "workload.py"
        lineage = checkout / "coursework" / "lineage.py"
        native_root = scratch / "native-lifecycle"
        native = run_lifecycle(state, workload, str(native_root), "native-lifecycle",
                               evidence, env, checkout)
        native_read = run_alternate(state, workload, [("native", str(native_root / "payload.bin"))],
                                    evidence / "native-events.jsonl", f"{args.run}-native", "native-alternate-read",
                                    evidence, env, checkout)
        if native_read.get("result") != "success" or native_read.get("sha256") != native["read_sha256"]:
            raise RuntimeError(f"native alternate read differs from lifecycle bytes: {native_read}")

        username = getpass.getuser()
        for label in ("A", "B"):
            store = scratch / f"store-{label}"
            store.mkdir()
            endpoint = ChirpEndpoint(label, store, scratch, evidence, username, env, state)
            endpoints.append(endpoint)
            endpoint.start(chirp)
            if args.fail_after_launch:
                state["failure_injection"] = "after-first-owned-server-launch"
                persist_state(state)
                raise RuntimeError("intentional failure after launching the first owned Chirp server")
            remote = run_lifecycle(state, workload, endpoint.path(f"seed-{label}"),
                                   f"remote-lifecycle-{label}", evidence, env, checkout, parrot)
            if remote != native:
                raise RuntimeError(f"native and interposed lifecycle outputs differ for endpoint {label}")
            stored = store / f"seed-{label}" / "payload.bin"
            if not stored.is_file() or stored.read_bytes() != PAYLOAD:
                raise RuntimeError(f"receiver {label} did not store the expected bytes")
            state.setdefault("receiver_side_effects", []).append({"endpoint": label, "path": str(stored),
                                                                    "bytes": stored.stat().st_size,
                                                                    "sha256": hashlib.sha256(stored.read_bytes()).hexdigest()})

        events = evidence / "events.jsonl"
        first = run_alternate(state, workload,
                              [(endpoint.label, endpoint.path(f"seed-{endpoint.label}/payload.bin")) for endpoint in endpoints],
                              events, f"{args.run}-first", "alternate-first", evidence, env, checkout, parrot)
        if first.get("result") != "success" or first.get("lineage") != ["A"]:
            raise RuntimeError(f"first real read did not establish endpoint A lineage: {first}")
        first_plan = load_plan(state, lineage, events, "plan-first", evidence, env, checkout)
        if first_plan.get("minimal_cuts") != [["A"]]:
            raise RuntimeError(f"initial observed path did not produce its minimal cut: {first_plan}")
        endpoints[0].stop()

        fallback = run_alternate(state, workload,
                                 [(endpoint.label, endpoint.path(f"seed-{endpoint.label}/payload.bin"))
                                  for endpoint in endpoints],
                                 events, f"{args.run}-fallback", "alternate-fallback", evidence, env, checkout, parrot)
        if fallback.get("result") != "success" or fallback.get("lineage") != ["B"]:
            raise RuntimeError(f"fallback did not record endpoint B as a real lineage: {fallback}")
        learned_plan = load_plan(state, lineage, events, "plan-learned", evidence, env, checkout)
        if learned_plan.get("minimal_cuts") != [["A", "B"]]:
            raise RuntimeError(f"learned alternative did not enlarge the minimal cut: {learned_plan}")

        endpoints[1].stop()
        unavailable = run_alternate(state, workload,
                                   [(endpoint.label, endpoint.path(f"seed-{endpoint.label}/payload.bin"))
                                    for endpoint in endpoints],
                                   events, f"{args.run}-unavailable", "alternate-unavailable", evidence, env,
                                   checkout, parrot, 3)
        if unavailable.get("result") != "unavailable" or not isinstance(unavailable.get("final_errno"), int):
            raise RuntimeError(f"all-down run did not report explicit unavailability: {unavailable}")
        final_plan = load_plan(state, lineage, events, "plan-final", evidence, env, checkout)
        if final_plan.get("minimal_cuts") != [["A", "B"]]:
            raise RuntimeError(f"failed outcomes changed the observed successful cut: {final_plan}")

        bad_file = endpoints[1].store / "seed-B" / "payload.bin"
        bad_file.write_bytes(b"wrong bytes from the owned fixture\n")
        endpoints[1].start(chirp)
        wrong = run_alternate(state, workload,
                              [("A", endpoints[0].path("seed-A/payload.bin")),
                               ("B", endpoints[1].path("seed-B/payload.bin"))],
                              events, f"{args.run}-wrong", "alternate-wrong-bytes", evidence, env,
                              checkout, parrot, 4)
        if wrong.get("result") != "wrong-bytes" or wrong.get("lineage"):
            raise RuntimeError(f"wrong bytes were not distinguished from unavailability: {wrong}")
        final_plan = load_plan(state, lineage, events, "plan-after-wrong-bytes", evidence, env, checkout)
        if final_plan.get("minimal_cuts") != [["A", "B"]]:
            raise RuntimeError(f"wrong-byte outcome changed the successful-path cut: {final_plan}")
        endpoints[1].stop()
        for process_record in state.get("owned_processes", []):
            debug_log = Path(process_record["debug_log"])
            if not debug_log.is_file() or "catalog update" in debug_log.read_text(encoding="utf-8", errors="replace"):
                raise RuntimeError(f"Chirp catalog registration was not demonstrably disabled: {debug_log}")
        state["catalog_registration"] = {
            "disabled": True,
            "checked_debug_logs": [process["debug_log"] for process in state.get("owned_processes", [])],
        }
        state["behavior_passed"] = True
    except KeyboardInterrupt as exc:
        state["error"] = f"KeyboardInterrupt: {exc}"
        state["interrupted"] = True
        persist_state(state)
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
        persist_state(state)
    finally:
        cleanup_errors = []
        for endpoint in reversed(endpoints):
            try:
                endpoint.stop()
            except Exception as exc:
                cleanup_errors.append(str(exc))
        for process, record in reversed(state.get("_active_processes", [])):
            try:
                stop_process(process, state, f"cleanup-{record['name']}")
                record["status"] = "stopped"
                unregister_process(state, process)
            except Exception as exc:
                cleanup_errors.append(str(exc))
        state["cleanup_errors"] = cleanup_errors
        endpoints_stopped = all(endpoint.process is None for endpoint in endpoints)
        processes_reaped = not state.get("_active_processes") and all(
            process.get("status") == "stopped" for process in state.get("owned_processes", []))
        all_stopped = endpoints_stopped and processes_reaped
        if all_stopped and is_within(scratch, local / "verify"):
            try:
                shutil.rmtree(scratch)
                scratch_removed = not scratch.exists()
                if scratch_removed:
                    run_dir.rmdir()
            except OSError as exc:
                cleanup_errors.append(str(exc))
        finalize_state(state, all_stopped, cleanup_errors, scratch_removed)
    if state.get("interrupted"):
        raise KeyboardInterrupt
    return 0 if state["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doctor", action="store_true", help="check the native build environment without changing files")
    group.add_argument("--run", help="execute the native Parrot and Chirp proof with a fresh run name")
    parser.add_argument("--fail-after-launch", action="store_true",
                        help="inject a controlled failure after the first owned Chirp server starts")
    args = parser.parse_args(argv)
    if args.doctor and args.fail_after_launch:
        parser.error("--fail-after-launch requires --run")
    report = doctor()
    if args.doctor:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ready"] else 1
    if not report["ready"]:
        print(json.dumps({"passed": False, "cleanup": True, "doctor": report}, indent=2, sort_keys=True))
        return 1
    return exercise(args)


if __name__ == "__main__":
    raise SystemExit(main())
