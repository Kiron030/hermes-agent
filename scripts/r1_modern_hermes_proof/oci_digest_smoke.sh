#!/usr/bin/env bash
# Official OCI digest smoke for R1. Pulls IMAGE@DIGEST only. No tag.
set -euo pipefail

PIN="${1:-sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09}"
IMAGE="nousresearch/hermes-agent@${PIN}"
AMD64="sha256:f3cba6abf5ed80d47a271498d663ace5dda87f45000552afb8be8370a35df1b5"
ARM64="sha256:d9e1cc25f91627a88791adb9d6eba26765bc3d22a908e775bba09eaf7108753f"

AUTHORITY_NAMES=(
  DATABASE_URL_TIMESCALE
  DATABASE_URL
  POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET
  RAILWAY_TOKEN
  RAILWAY_API_TOKEN
  RAILWAY_SERVICE_ID
  RAILWAY_PROJECT_ID
  RAILWAY_ENVIRONMENT_ID
  RAILWAY_PUBLIC_DOMAIN
  RAILWAY_STATIC_URL
  VERCEL_TOKEN
  VERCEL_ORG_ID
  VERCEL_PROJECT_ID
  VERCEL_DEPLOY_HOOK
)

echo "Pulling ${IMAGE}"
docker pull "${IMAGE}"

DIGESTS="$(docker image inspect "${IMAGE}" --format '{{range .RepoDigests}}{{.}}{{"\n"}}{{end}}')"
echo "RepoDigests:"
echo "${DIGESTS}"

if echo "${DIGESTS}" | grep -q "${PIN}"; then
  echo "PINNED_INDEX_DIGEST_PRESENT=yes"
elif echo "${DIGESTS}" | grep -Eq "${AMD64}|${ARM64}"; then
  echo "PINNED_INDEX_DIGEST_PRESENT=platform-resolved"
  echo "Platform digest is one of the audited v2026.8.19 arch digests."
else
  echo "PINNED_INDEX_DIGEST_PRESENT=no"
  echo "RepoDigests did not contain the pinned index or known arch digest"
  exit 1
fi

REVISION="$(docker image inspect "${IMAGE}" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' || true)"
echo "OCI_REVISION_LABEL=${REVISION:-}"

NAME="r1-oci-smoke-$$"
cleanup() {
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run --name "${NAME}" --network none --rm \
  --entrypoint /bin/sh \
  -e HERMES_HOME=/tmp/r1-home \
  "${IMAGE}" \
  -c '
    set -eu
    mkdir -p "$HERMES_HOME"
    names="DATABASE_URL_TIMESCALE DATABASE_URL POWERUNITS_HERMES_INTERNAL_EXECUTE_SECRET RAILWAY_TOKEN RAILWAY_API_TOKEN RAILWAY_SERVICE_ID RAILWAY_PROJECT_ID RAILWAY_ENVIRONMENT_ID RAILWAY_PUBLIC_DOMAIN RAILWAY_STATIC_URL VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID VERCEL_DEPLOY_HOOK"
    for n in $names; do
      eval "v=\${$n-}"
      if [ -n "${v}" ]; then
        echo "AUTHORITY_PRESENT=$n"
        exit 1
      fi
    done
    echo AUTHORITY_ABSENT=yes
    echo LISTEN_ADDRESS=none
    if command -v hermes >/dev/null 2>&1; then
      hermes --help >/dev/null
      echo HERMES_HELP=ok
    else
      python -c "import hermes_cli, model_tools; print(\"boot-ok\")"
    fi
  '

echo "OCI_RUNTIME_EVIDENCE=PASS"
echo "CONTAINER_REMOVED=yes"
