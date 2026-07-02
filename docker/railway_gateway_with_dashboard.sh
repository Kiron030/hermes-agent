#!/usr/bin/env bash
# Railway public URL (502 fix): run Telegram gateway + bind dashboard to $PORT.
#
# Default Docker CMD is `gateway run` only — no HTTP server on PORT, so Railway's
# proxy returns 502. Use this script as the Railway **Start Command** when you
# need Stage-1 dashboard over the generated domain.
#
# IMPORTANT (2026-07-02 incident): Railway's own docs confirm that for
# Dockerfile/image deployments, a custom Start Command "overrides the image's
# ENTRYPOINT in exec form" — https://docs.railway.com/deployments/start-command.
# That means when this script is configured as the Start Command, `/init`
# (s6-overlay, our real ENTRYPOINT) and its cont-init.d bootstrap — including
# docker/stage2-hook.sh's UID remap, $HERMES_HOME chown of config.yaml/
# gateway.lock/etc., first-boot config seeding, and the Powerunits
# first_safe_v1 runtime-policy hook — NEVER RUN. An earlier version of this
# script (and docs/powerunits_railway_bootstrap_v1.md) incorrectly assumed
# "Start Command only replaces CMD, entrypoint still runs" — that assumption
# is wrong for this image's 2-element `ENTRYPOINT [ "/init", "main-wrapper.sh" ]`
# and caused a production PermissionError on /opt/data/config.yaml +
# /opt/data/gateway.lock (unreadable because they were never re-chowned to the
# runtime user). Fix: run the same stage2 bootstrap explicitly, here, before
# starting the gateway/dashboard. Idempotent — safe on every restart.
#
# Expects venv + PATH from the image (same container as `hermes`).
# Pair with HERMES_POWERUNITS_DASHBOARD_MODE=observe for read-only /api/ writes.
#
# Security: `--insecure` is required for 0.0.0.0 (see hermes_cli/web_server.py).
# Prefer IP allowlists / VPN; never treat the dashboard as a public product surface.
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

# No manual privilege drop needed here: /opt/hermes/bin (ahead of
# .venv/bin on PATH via the image's baked ENV) resolves `hermes` to
# docker/hermes-exec-shim.sh, which already auto-drops root -> hermes
# before exec'ing the real binary (see that file for details). That drop
# was never the missing piece — the missing piece was stage2-hook.sh (above)
# actually chowning config.yaml/gateway.lock to the hermes user it drops to.
hermes gateway run --replace &
exec hermes dashboard \
    --host 0.0.0.0 \
    --port "${_listen_port}" \
    --insecure \
    --no-open
