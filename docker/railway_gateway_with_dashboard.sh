#!/usr/bin/env bash
# Railway public URL (502 fix): run Telegram gateway + bind dashboard to $PORT.
#
# Default Docker CMD is `gateway run` only — no HTTP server on PORT, so Railway's
# proxy returns 502. Use this script as the Railway **Start Command** (args to
# entrypoint) when you need Stage-1 dashboard over the generated domain.
#
# Expects venv + PATH from docker/entrypoint.sh (same container as `hermes`).
# Pair with HERMES_POWERUNITS_DASHBOARD_MODE=observe for read-only /api/ writes.
#
# Security: `--insecure` is required for 0.0.0.0 (see hermes_cli/web_server.py).
# Prefer IP allowlists / VPN; never treat the dashboard as a public product surface.
set -euo pipefail

_install_dir="${HERMES_INSTALL_DIR:-/opt/hermes}"
if ! command -v hermes >/dev/null 2>&1; then
    # shellcheck source=/dev/null
    source "${_install_dir}/.venv/bin/activate"
fi

_listen_port="${PORT:-9119}"

hermes gateway run --replace &
exec hermes dashboard \
    --host 0.0.0.0 \
    --port "${_listen_port}" \
    --insecure \
    --no-open
