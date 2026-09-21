#!/usr/bin/env bash
# Raise Dispatcharr's live-proxy connection retry budget so channel zapping
# survives a single-connection IPTV subscription.
#
# Why: /app/apps/proxy/live_proxy/views.py hardcodes
#     retry_timeout = 3  # 3 seconds total timeout
# When the provider only allows one simultaneous connection (STRONG8K profile
# max_streams=1) a Kodi channel switch races: Kodi requests the new channel
# before releasing the old stream, so the upstream slot frees ~2s later - just
# after the 3s budget expires. The zap then fails with
#     HTTP 503 {"error": "All active M3U profiles have reached maximum connection limits"}
# and Kodi stops playback instead of retrying.
#
# Raising the budget makes the switch wait for the old stream to release, so the
# zap just takes a couple of seconds instead of failing.
#
# This file lives inside the image, so re-run this script after every
# Dispatcharr image update.
#
# Usage: ./scripts/patch-dispatcharr-zap-retry.sh [container-name]
set -euo pipefail

CONTAINER="${1:-dispatcharr}"
FILE=/app/apps/proxy/live_proxy/views.py
NEW_VALUE=15          # seconds to wait for the provider slot to free

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "container '$CONTAINER' is not running" >&2
  exit 1
fi

current="$(docker exec "$CONTAINER" grep -n 'retry_timeout = ' "$FILE" || true)"
echo "current: ${current:-<no match>}"

if docker exec "$CONTAINER" grep -q "retry_timeout = 3 " "$FILE"; then
  docker exec "$CONTAINER" sed -i \
    "s|retry_timeout = 3 |retry_timeout = ${NEW_VALUE} |" \
    "$FILE"
  echo "patched -> ${NEW_VALUE}"
  echo "restarting ${CONTAINER} to reload uwsgi..."
  docker restart "$CONTAINER" >/dev/null
  sleep 12
  docker exec "$CONTAINER" grep -n 'retry_timeout = ' "$FILE"
else
  echo "already patched or upstream code changed - nothing to do"
fi
