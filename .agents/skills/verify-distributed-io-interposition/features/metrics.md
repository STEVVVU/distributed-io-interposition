# Native/interposed metrics

Run `python3 coursework/verify.py --run <fresh-name> --metrics` on the existing
non-root Ubuntu runtime path, or dispatch the maintained workflow with
`metrics=true`. The same driver owns all services, paths, command deadlines,
failure receipts and cleanup. The existing correctness/fault journeys still run.

The frozen byte workloads are 200 files of 4 KiB, 64 files of 1 MiB and 16 files
of 16 MiB. Each creates/writes/closes/reads/checks hashes, then performs 1000
exclusive create/close/stat/unlink cycles. Each native/interposed pair follows
one warmup per side; five measured pairs alternate order. The receiver's file
sizes and hashes are independently checked outside the timer. Payload fixtures
are deleted only under owned scratch after validation to bound disk use.

Kernel timers record write, read-with-SHA256, and metadata phases. Driver wall
time includes Python/Parrot launch, receipt persistence and process wait; it
excludes process-group cleanup. `/usr/bin/time -v` resources include the client
and Parrot process tree, not the live Chirp server's CPU. Source SHA, environment,
commands, raw samples, call/byte/operation counts, zero-error proof and resources
are retained with median/range summaries. No disk-durability claim is made;
files are closed without fsync, reads follow writes and use warm filesystem
caches. Parrot over loopback TCP is compared with native local filesystem I/O.
Phases below 10ms are flagged as short overhead controls in the summary.

Servers use notice logging during metrics and clients omit syscall tracing.
A separate unreported Parrot syscall trace follows the measurements. Counters
and hashing remain part of the application workload. No security policy changes
or nested ptrace profiler is used.

Five rotated trials plus warmups separately measure both endpoints available,
primary down with successful B fallback, and both down with explicit failure.
They retain per-attempt and whole-read elapsed time, excluding trace fsync and
process startup. Unavailability is an expected error outcome, not throughput.
Fallback latency is recovery of a read via an alternate; it does not establish
automatic server restart or broad distributed fault tolerance.
