# Lineage-driven endpoint cuts

The read workflow first succeeds through one owned endpoint, then learns an alternate after the first endpoint is stopped, derives a minimal endpoint cut from both observed paths, and confirms that the derived cut removes availability.

## Sub-features

- `observed-lineage`: record which real endpoint returned the expected bytes for each request.
- `minimal-cut`: compute minimal endpoint sets that hit every observed successful lineage.
- `alternating-replay`: use a derived cut to trigger the next real execution and incorporate its newly observed path.
- `failure-oracle`: keep unavailable and wrong-byte outcomes distinct from successful lineage.

## How to get to it (user POV)

- Run the verification driver on Linux; the endpoints are private loopback Chirp servers.

## Driving it with the Python verification driver

Preconditions:

- Start with an unused run name on an Ubuntu 24.04 x86-64 non-root host.
- Allow the driver to start and stop only the two loopback Chirp servers it owns.

- Action: run `python3 coursework/verify.py --run lineage-check`.
- Result: inspect `.local/evidence/lineage-check/events.jsonl` and the numbered plan JSON files in the result directory. The initial candidate must be derived from the first successful trace; after that path is unavailable, the next plan must include the actual newly successful alternate.
- Action: let the driver test the final derived cut and the corrupted-byte oracle case.
- Result: `result.json` distinguishes unavailable reads from wrong bytes and confirms neither is recorded as a successful path.

## Gotchas

- At most 16 distinct endpoints are accepted; enumeration is deliberately bounded.
- A hitting set only cuts paths observed in these executions. No completeness, general fault tolerance, or full LDFI certification is claimed.
- The planner must consume captured execution events; a hard-coded endpoint failure matrix is not a substitute.
