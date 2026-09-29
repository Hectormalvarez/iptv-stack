#!/usr/bin/env bash
# Waits for the provider player_api to unblock (403 rate limit), then triggers
# the Jellyfin Xtream Library sync and logs progress until it finishes.
# Run detached:  setsid nohup scripts/watch-xtream-sync.sh > /dev/null 2>&1 &
set -u
LOG=/tmp/poll.log

api_ok() {
  local out
  out=$(cat <<'EOF' | docker exec -i dispatcharr python manage.py shell 2>/dev/null | tail -1
import json, urllib.request
from apps.m3u.models import M3UAccount
a = M3UAccount.objects.get(pk=2)
base = a.server_url.split("get.php")[0]
req = urllib.request.Request(f"{base}player_api.php?username={a.username}&password={a.password}", headers={"User-Agent": "Mozilla/5.0"})
try:
    d = json.load(urllib.request.urlopen(req, timeout=15))
    print("OK" if d.get("user_info") else "BAD")
except Exception as e:
    print("ERR", str(e)[:40])
EOF
)
  [ "$out" = "OK" ]
}

echo "$(date +%H:%M:%S) watcher started" >> "$LOG"
while ! api_ok; do
  echo "$(date +%H:%M:%S) api still blocked" >> "$LOG"
  sleep 60
done
echo "$(date +%H:%M:%S) api unblocked, triggering sync" >> "$LOG"

TOKEN=$(cat /tmp/jf-token)
curl -s -X POST http://localhost:8096/XtreamLibrary/Sync \
  -H "Authorization: MediaBrowser Token=$TOKEN" \
  -H 'Content-Type: application/json' -d '{}' >> "$LOG" 2>&1
echo >> "$LOG"
echo "$(date +%H:%M:%S) sync triggered" >> "$LOG"

while true; do
  sleep 60
  P=$(curl -s --max-time 10 http://localhost:8096/XtreamLibrary/Progress -H "Authorization: MediaBrowser Token=$TOKEN")
  echo "$(date +%H:%M:%S) ${P:0:300}" >> "$LOG"
  echo "$P" | grep -q '"IsRunning":false' && break
done
echo "$(date +%H:%M:%S) SYNC-FINISHED" >> "$LOG"
