# R5 — Developer Hermes non-root runtime repair

**Slice:** `R5_DEVELOPER_RUNTIME_NONROOT_REPAIR_XS`  
**Status:** implementation + focused runtime proof  
**Human merge gate:** required  
**R5 gate:** remains `CLOSED`. This is not a broad R5 reopening.

Discovered during the `TELEGRAM_DEVELOPER_SECOND_BOT_0C` human smoke.
This slice does **not** redesign Telegram and does **not** change PR #74.

## Runtime identity

```text
IMAGE_USER                 = hermes / 10000:10000
CONTAINER_RUNTIME_USER     = hermes / 10000:10000
HERMES_SERVE_USER          = hermes
TELEGRAM_GATEWAY_USER      = hermes
HERMES_HOME_RUNTIME_OWNER  = hermes:hermes
ROOT_GATEWAY_ALLOWED       = NO
HERMES_ALLOW_ROOT_GATEWAY  = ABSENT
HERMES_DOCKER_EXEC_AS_ROOT = ABSENT
FIX_ARCHITECTURE           = PURE_NONROOT
```

The previous image ended with `USER root` and the launcher forced `--user 0:0`
plus `HERMES_DOCKER_EXEC_AS_ROOT=1`. That was an intentional Windows bind-mount
Git workaround, not a forgotten privilege drop. The entrypoint comment claiming
the image `hermes` user was stale.

Root runtime wrote ordinary `HERMES_HOME` state as `root:root`. Upstream
correctly refuses `gateway run` as root. A non-root gateway then could not
write `/opt/data`.

## HERMES_HOME ownership

The entire persistent `HERMES_HOME` (`/opt/data`, volume
`r5-developer-hermes-home`) is intended to be owned by uid/gid 10000.
There is no deliberate root-owned exception inside that tree.

Workspace binds, `/opt/r5-egress-ca`, and the Docker socket are out of
scope for migration.

One-shot repair (volume only, `network=none`, unprivileged, no binds):

```text
python scripts/r5_developer_hermes/container/launch.py migrate-home
python scripts/r5_developer_hermes/container/launch.py migrate-home --apply
```

`up` applies the same migration automatically after the developer container
is stopped and before it is recreated. The tool is idempotent, preserves
modes (especially `600` / `700`), never prints secret contents, does not
follow escape symlinks, and fails closed on unexpected ownership.

A fresh volume initializes as `hermes` without a human `chown`.

The existing Developer Telegram token in
`/opt/data/profiles/telegram-ops/.env` is preserved. This slice does not
start live Telegram polling.

## Why root gateway stays forbidden

`HERMES_ALLOW_ROOT_GATEWAY=1` would hide the defect by letting the gateway
run as root and keep poisoning `HERMES_HOME`. Upstream's refusal is the
correct control. Developer Hermes must stay aligned with it.

## Relation to PR #74

`feat/developer-hermes-telegram-second-bot-0c` remains a separate open PR.
After this repair merges, that branch should rebase and finish the Telegram
`gateway run` + status fix. This slice does not change Telegram lifecycle.

## Remaining residual

Windows bind-mount working trees stay writable by uid 10000. Some
root-created `.git` metadata (`index`, existing object shards) may remain
unwritable without changing Windows-side repository ownership. That residual
does **not** justify returning to a root Hermes runtime. This slice does
not chown workspace binds.

## Hardlines unchanged

Host isolation, production-authority isolation, filesystem boundary, and
egress boundary stay in force. No privileged mode, no Docker socket, no
mount widening, no broker/topology change, no Railway/Operator/Vercel work.
