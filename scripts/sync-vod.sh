#!/usr/bin/env bash
# Manually run the Jellyfin "Xtream Library" VOD sync.
#
# Why manual: the scheduled sync is deliberately OFF (the plugin config uses
# SyncScheduleType=Manual). The sync fires thousands of player_api.php calls, and the
# provider answers with an abuse block that 403s this host's IPv4 on *every* endpoint --
# which also takes live TV down (see docs/reference.md *Provider egress*). Run it by hand, off-peak,
# and keep an eye on how many calls it makes.
#
# Auth (credentials are never stored or committed) -- one of:
#   export JELLYFIN_TOKEN=<api key or access token>       # preferred; Dashboard -> API Keys
#   export JELLYFIN_USER=<admin> JELLYFIN_PASS=<password> # authenticated transiently
#
# Usage:
#   ./scripts/sync-vod.sh            # trigger a sync, then poll progress until Ctrl-C
#   ./scripts/sync-vod.sh --status   # print current progress and exit
set -euo pipefail

BASE="${JELLYFIN_URL:-http://localhost:8096}"
INTERVAL="${SYNC_POLL_SECONDS:-15}"

auth_header() {
    if [ -n "${JELLYFIN_TOKEN:-}" ]; then
        printf 'X-Emby-Token: %s' "$JELLYFIN_TOKEN"
        return
    fi
    if [ -n "${JELLYFIN_USER:-}" ] && [ -n "${JELLYFIN_PASS:-}" ]; then
        local tok
        tok=$(curl -fsS -X POST "$BASE/Users/AuthenticateByName" \
            -H 'Content-Type: application/json' \
            -H 'Authorization: MediaBrowser Client="sync-vod", Device="cli", DeviceId="sync-vod", Version="1.0"' \
            -d "{\"Username\":\"$JELLYFIN_USER\",\"Pw\":\"$JELLYFIN_PASS\"}" \
            | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessToken"])')
        printf 'X-Emby-Token: %s' "$tok"
        return
    fi
    echo 'Set JELLYFIN_TOKEN, or JELLYFIN_USER + JELLYFIN_PASS.' >&2
    exit 2
}

AUTH=$(auth_header)

progress() {
    curl -fsS "$BASE/XtreamLibrary/Progress" -H "$AUTH"
    echo
}

if [ "${1:-}" = "--status" ]; then
    progress
    exit 0
fi

echo "Triggering sync on $BASE ..."
curl -fsS -X POST "$BASE/XtreamLibrary/Sync" -H "$AUTH" -o /dev/null
echo 'Triggered. Progress every '"$INTERVAL"'s (Ctrl-C to stop watching; the sync keeps running):'
while :; do
    progress
    sleep "$INTERVAL"
done