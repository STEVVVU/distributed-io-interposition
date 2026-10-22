# Repository guidance

This checkout preserves the complete GPL-2.0 CCTools upstream tree and history. Keep unrelated upstream applications, notices, tests, and existing user changes intact. New extension code belongs under `coursework/`; the Linux runtime proof is maintained by `.agents/skills/verify-distributed-io-interposition/` and its feature map.

## Checks

Run the deterministic checks from the repository root:

```sh
python3 -m unittest discover -s coursework -p 'test_*.py' -v
python3 -m compileall -q coursework
git diff --check
```

The real runtime proof is Linux-only. On non-root Ubuntu 24.04 with the documented compiler and build tools, run `python3 coursework/verify.py --doctor` followed by `python3 coursework/verify.py --run <fresh-name>`. The mapped Parrot/Chirp drive and controlled cleanup check passed at commit `7c5ef0d510bb4f4c12a8999429c49081ba353805`; see `evidence/linux-39716596917/`. Re-run after changes to mapped paths or the driver. The controlled cleanup check is `python3 coursework/verify.py --run <fresh-name> --fail-after-launch`; it should exit 1 while retaining `passed: false`, `cleanup: true`, and reaped-process evidence.

## Safety and environment

- The driver refuses non-Linux, root, and non-x86-64 hosts. Do not change ptrace/Yama policy, kernel settings, authentication, ACLs, or privilege boundaries to make a run pass.
- Runtime writes stay inside fresh `.local/verify/<run>/scratch` and `.local/evidence/<run>` paths. It owns only child process groups it starts, binds Chirp to `127.0.0.1`, disables catalog registration with `--no-advertise` and `CATALOG_HOST=""`, and disables Parrot catalog queries. Never redirect these fixtures to external services or user files.
- The driver deliberately supplies a minimal `PATH` and a clean environment (`HOME`, `TMPDIR`, locale, and catalog host are explicit). Do not broaden environment inheritance or place credentials in the fixture environment.
- Keep generated `.local/` data out of Git. CI permissions stay read-only; preserve publisher workflows under `.github/upstream-workflows/` rather than reactivating them. Do not commit, push, publish, or deploy unless the task owner explicitly authorizes it.
- Do not add global tools, WSL/containers, elevated privileges, or machine-wide changes for this project. Linux proof applies only to the recorded runner and mapped journeys; do not extend its claims to other platforms or workloads.
