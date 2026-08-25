#!/bin/sh
# Developer-Hermes runtime entry. Must run as the image hermes user (uid 10000).
# Seeds isolated HERMES_HOME, then execs the requested command.
# Root is refused so HERMES_HOME cannot be re-poisoned as root-owned.
set -eu

if [ "$(id -u)" = "0" ]; then
  echo "r5-developer: refusing to start Hermes runtime as root" >&2
  echo "r5-developer: one-shot volume repair is migrate_home.py, not this entrypoint" >&2
  exit 78
fi

HERMES_HOME="${HERMES_HOME:-/opt/data}"
export HERMES_HOME
export HOME="${HOME:-$HERMES_HOME}"
export GIT_CONFIG_GLOBAL="${GIT_CONFIG_GLOBAL:-$HERMES_HOME/.gitconfig}"
export GIT_CONFIG_NOSYSTEM="${GIT_CONFIG_NOSYSTEM:-1}"

python3 /opt/r5-developer/seed_home.py

if [ "$#" -eq 0 ]; then
  set -- sleep infinity
fi

exec "$@"
