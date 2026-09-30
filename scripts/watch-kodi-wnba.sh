#!/usr/bin/env bash
# Waits for Kodi's playlist refresh to pick up the WNBA channels, then plays
# the live game. Detached: setsid nohup ... < /dev/null > /dev/null 2>&1 &
set -u
LOG=/tmp/poll.log

check() {
  curl -s --max-time 8 -u kodi:kodi -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"PVR.GetChannels","params":{"channelgroupid":"alltv","properties":["channel"]}}' \
    http://192.168.1.181:8080/jsonrpc
}

for i in $(seq 1 40); do
  if check | grep -q WNBA; then
    echo "$(date +%H:%M:%S) kodi sees WNBA channels (poll $i)" >> "$LOG"
    break
  fi
  echo "$(date +%H:%M:%S) kodi playlist not refreshed yet (poll $i)" >> "$LOG"
  sleep 45
done

# Play the live game: WNBA: Las Vegas Aces at Indiana Fever
CID=$(check | python3 -c "
import json,sys
d = json.load(sys.stdin)
for c in d['result']['channels']:
    if 'Aces at Indiana Fever' in c['label']:
        print(c['channelid']); break
")
if [ -z "${CID:-}" ]; then
  echo "$(date +%H:%M:%S) ERROR: Aces at Fever channel not found on kodi" >> "$LOG"
  exit 1
fi
curl -s -u kodi:kodi -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"Player.Open\",\"params\":{\"item\":{\"channelid\":$CID}}}" >> "$LOG" 2>&1
echo >> "$LOG"
echo "$(date +%H:%M:%S) playback started (channelid $CID)" >> "$LOG"
sleep 10
curl -s -u kodi:kodi -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"Player.GetActivePlayers"}' http://192.168.1.181:8080/jsonrpc >> "$LOG"
echo >> "$LOG"
echo "$(date +%H:%M:%S) PLAYBACK-CHECK-DONE" >> "$LOG"
