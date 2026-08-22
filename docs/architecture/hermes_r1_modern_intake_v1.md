# R1 — Modern Hermes immutable intake

**Slice:** R1  
**Audit date:** 2026-08-22  
**Base:** `origin/powerunits-internal-setup` @ `7eafef21053e42705553ac19916fdcf9dc998691`  
**Status:** intake record only — no production mutation

Execution references use immutable identities. The official image is
referenced by **digest**, not by a mutable tag.

```text
UPSTREAM_RELEASE          = v2026.8.19
UPSTREAM_PROJECT_VERSION  = 0.20.5
UPSTREAM_RELEASE_SHA      = fcbd1076a93841fa88855acce810e342a5b78101
UPSTREAM_TAG_OBJECT       = b05e680e63d39d5a8e3ec0f5842a41d1c4209c03
UPSTREAM_IMAGE_DIGEST     = sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
UPSTREAM_IMAGE_REF        = nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
UPSTREAM_IMAGE_REVISION   = not read (requires image-config pull; digest verified)
```

## Verification performed 2026-08-22

| Identity | Source | Observed | Match |
|---|---|---|---|
| Release tag | GitHub Release `v2026.8.19` | name `Hermes Agent v0.20.5 (v2026.8.19)` | YES |
| Tag object | `git/refs/tags/v2026.8.19` (annotated) | `b05e680e63d39d5a8e3ec0f5842a41d1c4209c03` | YES |
| Release commit | peeled annotated tag | `fcbd1076a93841fa88855acce810e342a5b78101` | YES |
| Project version | `pyproject.toml` at release SHA | `0.20.5` | YES |
| OCI index digest | Docker Hub tag API `v2026.8.19` | `sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09` | YES |

Platform image digests under that index (informational, not substitutes):

| Arch | Digest |
|---|---|
| linux/amd64 | `sha256:f3cba6abf5ed80d47a271498d663ace5dda87f45000552afb8be8370a35df1b5` |
| linux/arm64 | `sha256:d9e1cc25f91627a88791adb9d6eba26765bc3d22a908e775bba09eaf7108753f` |

Machine-readable copy: `scripts/r1_modern_hermes_proof/pin.json`.

## Reconstructability

Source proof:

```text
git fetch upstream fcbd1076a93841fa88855acce810e342a5b78101
python scripts/r1_modern_hermes_proof/harness.py prepare-source
python scripts/r1_modern_hermes_proof/harness.py frozen-install
```

Image proof (optional; Docker not required for R1 source evidence):

```text
docker pull nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09
```

Do not substitute a newer release, tag, or digest.

## Explicitly not built

Internal registry mirror, signing ceremony, SBOM gate, SLSA infrastructure.
Those remain deferred past GATE_3.
