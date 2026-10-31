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
exec cline \
    --config "$CONFIG" \
    --data-dir "$CONFIG/data" \
    connect telegram \
    -k "$TELEGRAM_BOT_TOKEN" \
    --allowed-user-id "$TELEGRAM_USER_ID" \
    --mode act \
    --cwd /workspace
