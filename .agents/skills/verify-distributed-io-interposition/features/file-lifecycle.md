# Transparent remote file lifecycle

An ordinary process creates, writes, closes, changes into, stats, reads, and checks a missing file through a Chirp path presented by Parrot.

## Sub-features

- `remote-write-read`: perform file and directory operations on owned Chirp storage.
- `native-parity`: compare deterministic outputs and POSIX error numbers against native local I/O.
- `receiver-side-effect`: check the actual bytes stored under each Chirp server root.

## How to get to it (user POV)

- Run the verification driver on Linux; there is no interactive interface.

## Driving it with the Python verification driver

Preconditions:

- Use an Ubuntu 24.04 x86-64 session as a non-root user with the documented build tools.
- Use a fresh run name and the `coursework/verify.py` driver.

- Action: run `python3 coursework/verify.py --run lifecycle-check`.
- Result: inspect `.local/evidence/lifecycle-check/result.json`; it records native and `parrot_run` results and requires matching mkdir, write, close, chdir, stat, read bytes, and missing-path errno outcomes.
- Side effect: the evidence records bytes read directly from each owned Chirp storage root before the driver's scratch stores are removed.

## Gotchas

- Parrot relies on native Linux `ptrace`; Windows behavior is not evidence for this journey.
- Chirp catalog registration is disabled with `--no-advertise`; authentication and ACLs stay limited to the owned local user.
- Runtime return and error values must come from the actual run, not generated examples.
