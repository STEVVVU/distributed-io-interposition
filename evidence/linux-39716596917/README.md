# Hosted Linux evidence: run 39716596917

Source commit: `7c5ef0d510bb4f4c12a8999429c49081ba353805`  
Platform: GitHub-hosted Ubuntu 24.04, Linux x86_64, non-root, Python 3.12.3.  
Workflow: [run 39716596917](https://github.com/STEVVVU/distributed-io-interposition/actions/runs/39716596917).

The successful run reports `behavior_passed=true`, `cleanup=true`, `scratch_removed=true`, and `reaped_owned_processes=true`; both `chirp_server` and `parrot_run` were present and executable. The native and interposed lifecycle results matched: 30-byte writes and reads, matching SHA-256, `ENOENT` for a missing file, successful `chdir` and `stat`, and successful closes. Both owned Chirp stores received the expected 30-byte payload with SHA-256 `0c54d8c26ac574d7162b5d2cb45b41ba8469dfe419939d0d52ca53f4f7a41c55`.

[`events.jsonl`](events.jsonl) contains actual observations: A succeeds; after A stops, B succeeds; with both unavailable, the result is `errno=104`; and wrong-byte B content yields a distinct `wrong-bytes` result. [`plans.json`](plans.json) records the resulting minimal cuts: `{A}` initially, then `{A,B}` after learning the B lineage. These cuts describe only successful paths observed in this bounded fixture.

The injected failure after launching the first owned server exited nonzero as intended. [`cleanup-failure.json`](cleanup-failure.json) records behavior failure with all owned groups reaped and scratch removed; this tests cleanup, not application behavior. The successful run checked three Chirp debug logs for disabled catalog registration; [`catalog-check.json`](catalog-check.json) names those logs. Full logs and raw result artifacts remain in the hosted run artifact; this directory is a compact extract.

Parrot logs warn that syscall 334 is unknown or unsupported for Python 3.12 and that kernel 6.17 was untested. All mapped assertions passed on this runner. The result does not establish behavior on other kernels, arbitrary workloads, `sendto`/`recvfrom` virtualization, or HTTP GET interception. The demonstrated path is filesystem syscall interposition to Chirp over owned loopback TCP.
