# R1 modern Hermes proof harness

Isolated, reconstructable proof of pinned upstream `v2026.8.19` / `0.20.5`.

This is not production. It does not read `.env`, does not start a public
listener, and does not implement a core clamp patch.

## Immutable pin

See `pin.json` and `docs/architecture/hermes_r1_modern_intake_v1.md`.

Image identity is the OCI **digest**, not a mutable tag:

```text
nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

Docker is optional. The local proof uses the matching source SHA via a
git worktree under `.r1-proof/` (gitignored).

## Commands

From the Repo A root, with project `.venv` optional:

```bash
python scripts/r1_modern_hermes_proof/harness.py verify-pin
python scripts/r1_modern_hermes_proof/harness.py prepare-source
python scripts/r1_modern_hermes_proof/harness.py frozen-install
python scripts/r1_modern_hermes_proof/harness.py inspect-lazy-install
python scripts/r1_modern_hermes_proof/harness.py isolate-env
python scripts/r1_modern_hermes_proof/harness.py boot-smoke
python scripts/r1_modern_hermes_proof/harness.py enumerate-tools
python scripts/r1_modern_hermes_proof/harness.py clamp-operator
python scripts/r1_modern_hermes_proof/harness.py capability-inventory
python scripts/r1_modern_hermes_proof/harness.py capability-probes
python scripts/r1_modern_hermes_proof/harness.py model-smoke
```

Or:

```bash
python scripts/r1_modern_hermes_proof/harness.py all
```

## Isolation

Each proof process gets a dedicated `HERMES_HOME` under `.r1-proof/homes/`.
The process environment is constructed by **absence of authority**: production
DB, execute-secret, Railway, and Vercel names are not copied into the child.

Two contexts, never one shared toolset:

- `operator` — bounded allow/deny experiment
- `developer` — capability-uplift scratch workspace

## Model smoke

Do not read production `.env`. If a dedicated non-production key exists:

```bash
set HERMES_R1_MODEL_API_KEY=<non-production-ephemeral-key>
set HERMES_R1_MODEL_PROVIDER=openai
set HERMES_R1_MODEL=gpt-4.1-mini
python scripts/r1_modern_hermes_proof/harness.py model-smoke
```

DO NOT ATTACH RAW MODEL-SMOKE ARTIFACT TO PR WITHOUT REVIEW/REDACTION.

stdout/stderr tails may contain provider-error material. There is no
secret-redaction subsystem. A human must review before attaching output.

## OCI digest smoke

Official image only, by digest:

```bash
scripts/r1_modern_hermes_proof/oci_digest_smoke.sh sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

GitHub Actions: `.github/workflows/r1-oci-digest-smoke.yml` (`workflow_dispatch`).

## Tests

```bash
python -m pytest tests/r1_modern_proof -q
```
