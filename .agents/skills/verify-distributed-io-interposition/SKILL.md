---
name: verify-distributed-io-interposition
description: Build and drive the real Linux Parrot and Chirp runtime against owned loopback storage to verify transparent file I/O and lineage-driven endpoint failure exploration.
---

# Draft status

This driver is unproven on Linux. The current development host is Windows without WSL or a Linux container, and Parrot requires native Linux `ptrace`. Do not represent the native runtime journey as verified until a non-root Ubuntu 24.04 run finishes Launch, Doctor, Drive, Evidence, and Cleanup.

## Launch

From a fresh checkout on non-root Ubuntu 24.04 with Python 3, GCC, G++, Make, Perl, and the normal C build tools, run:

```sh
python3 -m unittest discover -s coursework -p 'test_*.py' -v
python3 coursework/verify.py --run fresh-linux-run
```

The driver snapshots the checkout without `.git` into `.local/verify/<run>/scratch/checkout`, configures only that copy, builds `dttools`, `chirp`, and `parrot`, then starts each fixture server in its own owned process group on `127.0.0.1` with a fresh port. Chirp receives `--no-advertise`, an empty `CATALOG_HOST` defense-in-depth setting, `--auth=unix`, a run-private default ACL, and a run-private storage root. Parrot uses direct `/chirp/127.0.0.1:<port>/...` paths and `--no-chirp-catalog`; no external catalog or HTTP endpoint is used. Readiness is the server-created random port file plus a successful direct Chirp operation.

After `make`, the driver explicitly checks that both `chirp/src/chirp_server` and `parrot/src/parrot_run` exist and are executable. A successful make exit alone does not establish that the configure package set included Parrot.

## Doctor

Run `python3 coursework/verify.py --doctor`. It performs read-only checks for Linux x86-64, a non-root effective UID, Python 3, and the required compiler/build commands. A missing check exits nonzero with a JSON report. This check does not launch services or modify the checkout.

## Drive

`python3 coursework/verify.py --run fresh-linux-run` drives the mapped journeys. The run name must be new and contain only letters, digits, underscores, or hyphens. The driver refuses root and non-Linux hosts, copies the source into its fresh disposable scratch tree, compares native local filesystem behavior with `parrot_run` over Chirp, and drives the trace-derived endpoint cut sequence against two owned loopback servers. It never runs a scenario against a pre-existing server.

CI also runs `python3 coursework/verify.py --run fresh-cleanup-run --fail-after-launch`. This deliberately exits nonzero after launching its first owned Chirp process. The expected retained evidence has `passed: false`, `cleanup: true`, all owned process records stopped/reaped, and the scratch tree removed. CI explicitly checks the exit status and these state assertions; the injected run does not substitute for the successful behavior run.

## Evidence

Proof is saved in `.local/evidence/<run>/` and survives cleanup: `result.json`, build and server logs, native/interposed workflow outputs, runtime trace logs, observed request lineage events, and the minimal-cut plans computed from those events. Passing requires the driver result to say `passed: true` and `cleanup: true`, lifecycle outputs and receiver-side bytes to match, a learned alternate endpoint path, a cut that makes both paths unavailable, and distinct unavailable versus wrong-byte outcomes. Captured endpoint paths and errors come from actual application reads under Parrot. The cut result only covers observed paths and this bounded fixture; it is not a general certification. The terminal `passed` value is set only after cleanup also succeeds; `behavior_passed` records the separate runtime journey result.

## Cleanup

The driver atomically writes `result.json` before launching work and after each owned-process registration/removal or failure. It terminates only process groups it created, confirms their exit, and deletes only the fresh `.local/verify/<run>/scratch` tree after all owned processes are reaped. It retains evidence under `.local/evidence/<run>/`. On an interrupted driver, inspect `result.json` and the recorded process IDs and command lines before manually stopping any survivor; never kill by process name or remove an unrelated scratch directory.

## Helpers

The maintained driver is `coursework/verify.py`, which builds the relevant upstream dependency closure and drives the runtime using only Python's standard library and the checked-out CCTools commands. The deterministic planner tests run with `python3 -m unittest discover -s coursework -p 'test_*.py' -v`.

See the [feature map](features/README.md). Use `/maintain-verification-skill` when the mapped user journeys change.
