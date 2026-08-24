#!/bin/sh
# Developer-Hermes runtime entry. Runs as the image hermes user.
# Seeds isolated HERMES_HOME, then execs the requested command.
set -eu

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
