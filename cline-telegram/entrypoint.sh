#!/bin/sh
# cline-telegram entrypoint.
#
# The host's ~/.cline is mounted read-only at /cline-config (provider auth,
# model settings, custom CA bundle). Cline needs to WRITE its config dir
# (sessions, db, locks), so we seed a minimal writable copy into /state on
# first run and point cline at that. -n (no-clobber) means container state is
# never overwritten by an older host copy on restart.
set -eu

CONFIG=/state/.cline

# The background connector child does not reliably inherit --config/--data-dir;
# it resolves ~/.cline from $HOME. Point HOME at the writable state volume so
# parent AND child see the same authenticated config.
export HOME=/state

# Host networking shares the host netns, where the host's own Cline Hub binds
# 127.0.0.1:25463. Without an override the bridge child tries to start (or
# worse, "retire") the HOST's hub. The --rpc-address flag does not reach the
# spawned child, but env vars do — pin the bridge hub to its own port.
export CLINE_HUB_HOST=127.0.0.1
export CLINE_HUB_PORT=25464

# Stale instance cleanup: connector/hub records in the state volume reference
# pids from previous container boots — impossible to be alive in this fresh
# PID namespace, yet the parent trusts them ("connector already running")
# and exits. Clear them on every boot so each container start is clean.
rm -f "$CONFIG/data/connectors/telegram/"*.json 2>/dev/null || true
rm -rf "$CONFIG/data/locks/hub" 2>/dev/null || true

if [ ! -d "$CONFIG/data/settings" ]; then
    echo "[entrypoint] seeding cline config from read-only host mount..."
    mkdir -p "$CONFIG/data/settings"
    # CA bundle (proxy/custom certs), global state, provider secrets, settings.
    [ -f /cline-config/cli-node-extra-ca-certs.pem ] && \
        cp -n /cline-config/cli-node-extra-ca-certs.pem "$CONFIG/"
    for f in globalState.json secrets.json; do
        [ -f "/cline-config/data/$f" ] && cp -n "/cline-config/data/$f" "$CONFIG/data/"
    done
    cp -rn /cline-config/data/settings/. "$CONFIG/data/settings/"
    echo "[entrypoint] seed complete"
fi

# Global options (--config/--data-dir) must precede the subcommand.
# --rpc-address: host networking shares the host netns, where the host's own
# Cline Hub already binds 127.0.0.1:25463. Without this override the bridge
# tries to "retire" the HOST's hub — never let it. Dedicated port 25464.
exec cline \
    --config "$CONFIG" \
    --data-dir "$CONFIG/data" \
    connect telegram \
    -i \
    -k "$TELEGRAM_BOT_TOKEN" \
    --allowed-user-id "$TELEGRAM_USER_ID" \
    --mode act \
    --rpc-address 127.0.0.1:25464 \
    --cwd /workspace
