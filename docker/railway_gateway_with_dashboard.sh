#!/usr/bin/env bash
# Railway: Telegram gateway + optional dashboard on $PORT.
#
# Default (Telegram-first / Powerunits first_safe_v1): **gateway only** — no
# HTTP listener on $PORT. Upstream v0.18+ refuses 0.0.0.0 dashboard binds
# without a registered auth provider (--insecure no longer bypasses the gate).
#
# To expose the dashboard on the Railway domain, set **both**:
#   HERMES_DASHBOARD=1
#   and one auth provider, e.g.:
#     HERMES_DASHBOARD_BASIC_AUTH_USERNAME + _PASSWORD (or _PASSWORD_HASH)
#     HERMES_DASHBOARD_OAUTH_CLIENT_ID
#     HERMES_DASHBOARD_OIDC_ISSUER + HERMES_DASHBOARD_OIDC_CLIENT_ID
# Pair with HERMES_POWERUNITS_DASHBOARD_MODE=observe for read-only /api/ writes.
#
# IMPORTANT (2026-07-02 incident): Railway's own docs confirm that for
# Dockerfile/image deployments, a custom Start Command "overrides the image's
# ENTRYPOINT in exec form" — https://docs.railway.com/deployments/start-command.
# That means when this script is configured as the Start Command, `/init`
# (s6-overlay, our real ENTRYPOINT) and its cont-init.d bootstrap — including
# docker/stage2-hook.sh's UID remap, $HERMES_HOME chown of config.yaml/
# gateway.lock/etc., first-boot config seeding, and the Powerunits
# first_safe_v1 runtime-policy hook — NEVER RUN. This script runs stage2-hook.sh
# explicitly before starting services. Idempotent — safe on every restart.
#
# Expects venv + PATH from the image (same container as `hermes`).
set -euo pipefail

_install_dir="${HERMES_INSTALL_DIR:-/opt/hermes}"

# s6-overlay's own utilities (s6-setuidgid, s6-svc, ...) live under /command/
# and are normally only on PATH for processes /init launches itself (cont-init.d,
# with-contenv children). stage2-hook.sh calls them bare (unqualified) because it
# assumes that context. Since this script bypasses /init entirely (see note
# below), add /command to PATH ourselves so stage2-hook.sh's internal
# s6-setuidgid calls resolve instead of aborting the bootstrap partway through
# (docker/hermes-exec-shim.sh documents the same PATH gap).
export PATH="/command:${PATH}"

# Run the same UID-remap / $HERMES_HOME chown / first-boot-seed / runtime-policy
# bootstrap that /etc/cont-init.d/01-hermes-setup would normally run before s6
# starts services — required here because this script itself bypasses /init
# (see note above). Only meaningful (and only possible) as root; if the
# container is already running non-root, stage2-hook.sh's own job was either
# already done by the platform or is not achievable without root, so skip it
# rather than fail the whole boot on a permission it can't have anyway.
if [ "$(id -u)" = 0 ] && [ -x "${_install_dir}/docker/stage2-hook.sh" ]; then
    "${_install_dir}/docker/stage2-hook.sh"
fi

if ! command -v hermes >/dev/null 2>&1; then
    # shellcheck source=/dev/null
    source "${_install_dir}/.venv/bin/activate"
fi

_listen_port="${PORT:-9119}"

_has_dash_auth=false
if [ -n "${HERMES_DASHBOARD_BASIC_AUTH_USERNAME:-}" ] && \
   { [ -n "${HERMES_DASHBOARD_BASIC_AUTH_PASSWORD:-}" ] || \
     [ -n "${HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH:-}" ]; }; then
    _has_dash_auth=true
fi
if [ -n "${HERMES_DASHBOARD_OAUTH_CLIENT_ID:-}" ]; then
    _has_dash_auth=true
fi
if [ -n "${HERMES_DASHBOARD_OIDC_ISSUER:-}" ] && \
   [ -n "${HERMES_DASHBOARD_OIDC_CLIENT_ID:-}" ]; then
    _has_dash_auth=true
fi

_want_dashboard=false
case "${HERMES_DASHBOARD:-}" in
    1|true|TRUE|True|yes|YES|Yes|on|ON|On) _want_dashboard=true ;;
esac

if [ "$_want_dashboard" = true ] && [ "$_has_dash_auth" = true ]; then
    # Gateway in background; dashboard holds PID 1 on $PORT with auth gate satisfied.
    hermes gateway run --replace &
    exec hermes dashboard \
        --host 0.0.0.0 \
        --port "${_listen_port}" \
        --no-open
fi

if [ "$_want_dashboard" = true ] && [ "$_has_dash_auth" = false ]; then
    echo "[railway] HERMES_DASHBOARD is set but no dashboard auth provider is configured." >&2
    echo "[railway] v0.18+ requires basic_auth, OAuth, or OIDC for non-loopback binds." >&2
    echo "[railway] Starting gateway only so Telegram keeps working." >&2
fi

# Telegram-first default: foreground gateway, no public dashboard surface.
exec hermes gateway run --replace
