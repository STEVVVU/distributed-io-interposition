# Distributed I/O Interposition

This project preserves the full Cooperative Computing Tools source and history, including its Parrot syscall interposer and Chirp storage service. The local extension records successful endpoint lineages from an owned read workflow, derives minimal endpoint cuts from those observed paths, and replays the workload while stopping only its loopback fixture servers.

The native runtime is Linux-only because Parrot uses `ptrace`; Windows does not emulate it. The mapped native journeys and cleanup-failure path passed on non-root Ubuntu 24.04 at commit `7c5ef0d510bb4f4c12a8999429c49081ba353805`. See the [curated run evidence](evidence/linux-39716596917/) and [hosted CI run](https://github.com/STEVVVU/distributed-io-interposition/actions/runs/39716596917). This proves those mapped journeys on that runner, not other Linux versions or arbitrary workloads. To reproduce on a compatible host:

```sh
python3 -m unittest discover -s coursework -p 'test_*.py' -v
python3 coursework/verify.py --doctor
python3 coursework/verify.py --run local-linux
```

The driver builds only `dttools`, `chirp`, and `parrot` in disposable scratch, runs native and interposed filesystem workflows against two owned loopback Chirp servers, and saves proof under `.local/evidence/<run>/`. It uses real `parrot_run` and `chirp_server`, disables external catalog interaction, writes only within fresh run roots, and retains evidence after cleanup. Its scope is file-system calls routed to Chirp over loopback TCP; it does not virtualize arbitrary socket calls such as `sendto`/`recvfrom` or provide HTTP GET virtualization. The project-local [verification skill](.agents/skills/verify-distributed-io-interposition/SKILL.md) and [feature map](.agents/skills/verify-distributed-io-interposition/features/README.md) record the proved journeys and limits.

## Native measurements

[Run 39728898971](https://github.com/STEVVVU/distributed-io-interposition/actions/runs/39728898971)
measured source `e497cbb6f570dfa526cafd6bf8ea3abef02a2357` on Ubuntu 24.04,
an AMD EPYC 7763 VM with four logical CPUs, GCC 13.3 and Python 3.12. Five
alternating native/Parrot pairs followed one warmup per side. All 30 measured
byte workloads and 15 measured availability states passed their expected
outcomes; receiver hashes and owned-process cleanup passed.

For sixteen 16 MiB files (256 MiB total), medians (full ranges) were:

| Measurement | Native local filesystem | Parrot over loopback Chirp |
| --- | ---: | ---: |
| Write and close, MB/s | 3760 (3730..3800) | 195 (173..206) |
| Read with SHA256, MB/s | 1411 (1401..1415) | 187 (165..206) |
| 1000 metadata cycles, seconds | 0.0342 (0.0340..0.0347) | 2.206 (1.827..2.324) |
| Whole command, seconds | 0.369 (0.368..0.369) | 5.179 (4.678..5.679) |

Each metadata cycle exclusively creates, closes, stats and unlinks one empty
file. Reads follow writes with warm filesystem caches. Files are closed without
fsync, so these are application I/O measurements with hashing, not durable disk
or network capacity. Whole-command time includes Python/Parrot launch and
verification receipt overhead. Interposition is slower than native local I/O
in this fixture; these values support no general performance advantage.

The sequential alternate reader, with the existing five-second Parrot timeout,
took 5.163 (4.905..5.517) ms with both endpoints available, 10017.405
(10016.618..10018.407) ms with A down and B succeeding, and 20023.529
(20023.429..20023.612) ms to return explicit failure with both down. These are
five-trial median/ranges for the read, excluding process startup and trace
fsync. Fallback is slow under the preserved transport retry behavior; it does
not provide automatic service recovery.

Reproduce all sizes, metadata and fault-state measurements with:

```sh
python3 coursework/verify.py --run fresh-metrics --metrics
```

[Complete compact results and raw hashes](evidence/linux-39728898971/) retain
all sizes and states, source identity, resource scope, separate trace and
limitations. Client/Parrot CPU and RSS exclude the live Chirp server, so a total
system bottleneck has not been established. No runtime retry limit was changed.

The fault explorer is intentionally bounded to at most 16 distinct endpoints. Its minimal hitting sets describe cuts over observed successful paths only; they are hypotheses for this run, not a proof of general fault tolerance. See [coursework/PROVENANCE.md](coursework/PROVENANCE.md) for source and research attribution, and [README.upstream.md](README.upstream.md) for the preserved CCTools README.

This project is distributed under GNU GPL version 2 as a whole, consistent with the preserved upstream application. See [COPYING](COPYING) and the original per-file notices.
