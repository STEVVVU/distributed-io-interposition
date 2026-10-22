# Parrot/Chirp benchmark evidence

[Native run 39728898971](https://github.com/STEVVVU/distributed-io-interposition/actions/runs/39728898971)
executed source `e497cbb6f570dfa526cafd6bf8ea3abef02a2357` on non-root Ubuntu
24.04, Linux 6.17 Azure, AMD EPYC 7763 VM (four logical CPUs on two reported
cores), GCC 13.3, Python 3.12. Normal receipt has passed/metrics_passed/
behavior_passed/cleanup/scratch_removed/reaped_owned_processes all true. The
separate injected failure has the exact intentional cause, passed false and
cleanup true. No host privilege, kernel policy or catalog settings changed.

[receipt.json](receipt.json) is a compact extraction of the observed terminal
receipt. [summary.json](summary.json) retains all nine complete median/range
groups; [raw-sha256.txt](raw-sha256.txt) identifies 100 original metric,
environment, profile and terminal files in artifact
`p23-native-39728898971-1`. Original full receipt, command argv, process groups,
raw phase timings, receiver checks, resources and trace remain in that artifact.
All 36 byte rows and 18 recovery rows, including warmups, were independently
checked for complete trial sets, byte counts, errors and expected outcomes.
Recomputed write medians matched the original summary. The original terminal
receipt is unchanged.

Frozen byte batches are 4 KiB x200, 1 MiB x64 and 16 MiB x16. Each mode receives
one warmup then five alternating measured pairs. Each performs 1000 exclusive
create/close/stat/unlink metadata cycles. All receiver files were independently
hashed and sized after timing before only owned payload directories were
removed. Reads follow writes with warm caches and include SHA256 work. No
fsync, cache eviction or disk-durability claim. Small 4 KiB native phases are
below 10 ms and remain overhead controls.

In the 256 MiB batch, Parrot median write/read bandwidth is 195.1/186.9 MB/s
versus native 3760.3/1411.4 MB/s (decimal MB). Interposed metadata median is
2.206 seconds versus native 0.0342 seconds, and whole commands 5.179 versus
0.369 seconds. The full ranges are retained without claiming superiority or
explaining the entire difference from the client alone. A representative
interposed whole process used 0.43 user, 1.07 system and 5.28 wall seconds,
20320 KiB peak RSS. These resources exclude the live Chirp server.

Five rotated trials plus one warmup per state measure both available,
primary-down fallback, and both-down failure. Read medians are 5.163 ms,
10.017405 seconds and 20.023529 seconds respectively. Per-attempt latency and
explicit success/unavailability are retained. Timing excludes trace fsync and
Python/Parrot launch. Existing `--timeout=5` and upstream bounded retry behavior
were preserved; no shorter timeout was substituted to manufacture recovery.

Campaign clients omit syscall logging and Chirp uses supported notice logging.
The separate unreported syscall trace confirms actual application operations
for a 4 MiB/100-cycle workload. Its timings are excluded. It does not identify
a complete system CPU/transport limiter, measure cache/NUMA behavior or certify
arbitrary distributed fault tolerance. Further cause-dependent optimization
needs appropriate server/client profiling first.

```sh
python3 coursework/verify.py --run fresh-metrics --metrics
```
