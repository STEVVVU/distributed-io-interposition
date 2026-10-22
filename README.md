# Distributed I/O Interposition

This project preserves the full Cooperative Computing Tools source and history, including its Parrot syscall interposer and Chirp storage service. The local extension records successful endpoint lineages from an owned read workflow, derives minimal endpoint cuts from those observed paths, and replays the workload while stopping only its loopback fixture servers.

The native runtime is Linux-only because Parrot uses `ptrace`; Windows does not emulate it. The mapped native journeys and cleanup-failure path passed on non-root Ubuntu 24.04 at commit `7c5ef0d510bb4f4c12a8999429c49081ba353805`. See the [curated run evidence](evidence/linux-39716596917/) and [hosted CI run](https://github.com/STEVVVU/distributed-io-interposition/actions/runs/39716596917). This proves those mapped journeys on that runner, not other Linux versions or arbitrary workloads. To reproduce on a compatible host:

```sh
python3 -m unittest discover -s coursework -p 'test_*.py' -v
python3 coursework/verify.py --doctor
python3 coursework/verify.py --run local-linux
```

The driver builds only `dttools`, `chirp`, and `parrot` in disposable scratch, runs native and interposed filesystem workflows against two owned loopback Chirp servers, and saves proof under `.local/evidence/<run>/`. It uses real `parrot_run` and `chirp_server`, disables external catalog interaction, writes only within fresh run roots, and retains evidence after cleanup. Its scope is file-system calls routed to Chirp over loopback TCP; it does not virtualize arbitrary socket calls such as `sendto`/`recvfrom` or provide HTTP GET virtualization. The project-local [verification skill](.agents/skills/verify-distributed-io-interposition/SKILL.md) and [feature map](.agents/skills/verify-distributed-io-interposition/features/README.md) record the proved journeys and limits.

The fault explorer is intentionally bounded to at most 16 distinct endpoints. Its minimal hitting sets describe cuts over observed successful paths only; they are hypotheses for this run, not a proof of general fault tolerance. See [coursework/PROVENANCE.md](coursework/PROVENANCE.md) for source and research attribution, and [README.upstream.md](README.upstream.md) for the preserved CCTools README.

This project is distributed under GNU GPL version 2 as a whole, consistent with the preserved upstream application. See [COPYING](COPYING) and the original per-file notices.
