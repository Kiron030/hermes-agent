#!/usr/bin/env bash
# Railway Telegram-first: gateway only — no public HTTP dashboard on $PORT.
#
# Use this as the Railway **Start Command** when Telegram (long-polling or
# webhook) is the only channel and you do not need the Hermes web dashboard
# on the generated Railway domain. Avoids v0.18+ dashboard auth-gate crashes
# from binding 0.0.0.0 without an auth provider.
#
# Custom Start Commands replace the image ENTRYPOINT on Railway (see
# docs/powerunits_railway_bootstrap_v1.md). This script runs stage2-hook.sh
# explicitly before starting the gateway — same bootstrap contract as
# railway_gateway_with_dashboard.sh.
#
# Expects venv + PATH from the image (same container as `hermes`).
set -euo pipefail

_install_dir="${HERMES_INSTALL_DIR:-/opt/hermes}"

export PATH="/command:${PATH}"

if [ "$(id -u)" = 0 ] && [ -x "${_install_dir}/docker/stage2-hook.sh" ]; then
    "${_install_dir}/docker/stage2-hook.sh"
fi

if ! command -v hermes >/dev/null 2>&1; then
    # shellcheck source=/dev/null
    source "${_install_dir}/.venv/bin/activate"
fi

exec hermes gateway run --replace
