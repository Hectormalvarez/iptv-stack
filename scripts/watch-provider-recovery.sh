#!/usr/bin/env bash
# Watches for a provider outage to clear, then retunes the Kodi box to a target
# channel. Born from the 2026-10-25 outage, where every channel sat in
# "state: connecting" and the TV was left with no active player.
#
# It probes through Dispatcharr (never the provider directly) using the target
# channel's proxy URL from the HDHR lineup, so the test is the same path the box
# will use. It only retunes when NOTHING is playing, so it can never yank a
# channel someone is already watching.
#
# Recovery needs NEED_STREAK consecutive good probes: on 2026-10-25 the provider
# served a 12.8 MB burst and then 0 bytes nine seconds later, so one good probe
# proves nothing. (Status codes are useless here too - during the outage the URL
# answered 200 with 53 bytes of HTML.)
#
# Run detached:  setsid nohup scripts/watch-provider-recovery.sh > /dev/null 2>&1 &
#
#   TARGET_NUM=325 TARGET_NAME='NFL RedZone' scripts/watch-provider-recovery.sh
#   MAX_MIN=360 MIN_BYTES=1000000   # give up after 6h; require >=1 MB in 8s
set -u

LOG=${LOG:-/tmp/provider-recovery.log}
LINEUP=${LINEUP:-http://localhost:9191/hdhr/Kodi/lineup.json}
KODI=${KODI:-http://192.168.1.182:8080/jsonrpc}
TARGET_NUM=${TARGET_NUM:-325}
TARGET_NAME=${TARGET_NAME:-NFL RedZone}
MIN_BYTES=${MIN_BYTES:-1000000}
NEED_STREAK=${NEED_STREAK:-2}   # consecutive good probes before we trust recovery
MAX_MIN=${MAX_MIN:-360}
PROBE_SECS=${PROBE_SECS:-8}
PROBE_TMP=/tmp/provider-recovery-probe.bin

log() { echo "$(date +%H:%M:%S) $*" >> "$LOG"; }

# Resolve the target's proxy URL from the auth-free HDHR lineup.
target_url() {
  curl -s -m 10 "$LINEUP" | python3 -c "
import json, sys
num, name = '$TARGET_NUM', '$TARGET_NAME'.lower()
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for e in d:
    if str(e.get('GuideNumber')) == num or name in str(e.get('GuideName', '')).lower():
        print(e['URL'])
        break
"
}

# True once the provider is actually serving video for the target channel.
# Bytes, not status codes: during the outage the URL answered 200 with 53 bytes
# of HTML, which looks healthy to any status-code check.
provider_ok() {
  local url bytes
  url=$(target_url)
  if [ -z "$url" ]; then log "lineup lookup failed (is dispatcharr up?)"; return 1; fi
  bytes=$(curl -s -m "$PROBE_SECS" -o "$PROBE_TMP" -w '%{size_download}' "$url" 2>/dev/null)
  bytes=${bytes:-0}
  log "probe ${bytes} bytes in ${PROBE_SECS}s (need >= ${MIN_BYTES})"
  [ "$bytes" -ge "$MIN_BYTES" ]
}

# The box's PVR id for the target channel — never assume it equals the number.
kodi_pvrid() {
  curl -s -m 10 -u kodi:kodi -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"PVR.GetChannels","params":{"channelgroupid":"alltv","limits":{"start":0,"end":2000}}}' \
    "$KODI" | python3 -c "
import json, sys
name = '$TARGET_NAME'.lower()
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
for c in d['result']['channels']:
    if name in c['label'].lower():
        print(c['channelid'])
        break
"
}

# Only retune when nothing is playing, so we can never steal a channel the user
# already put on by hand.
kodi_idle() {
  curl -s -m 8 -u kodi:kodi -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":2,"method":"Player.GetActivePlayers"}' "$KODI" \
    | grep -q '"result":\[\]'
}

retune() {
  local cid
  cid=$(kodi_pvrid)
  if [ -z "$cid" ]; then log "ERROR: no Kodi channel matches '$TARGET_NAME'"; return 1; fi
  curl -s -m 10 -u kodi:kodi -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"Player.Open\",\"params\":{\"item\":{\"channelid\":$cid}}}" \
    "$KODI" >> "$LOG" 2>&1
  echo >> "$LOG"
  log "Player.Open sent (pvrid $cid)"
  sleep 8
  log "item:  $(curl -s -m 8 -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":4,"method":"Player.GetItem","params":{"playerid":1}}' "$KODI")"
  log "props: $(curl -s -m 8 -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":5,"method":"Player.GetProperties","params":{"playerid":1,"properties":["speed","live","percentage"]}}' "$KODI")"
}

# ---------------------------------------------------------------------------
log "watcher started: target #$TARGET_NUM '$TARGET_NAME', giving up after ${MAX_MIN}m"
if ! kodi_idle; then
  log "box is already playing something - leaving it alone, exiting"
  exit 0
fi

deadline=$(( $(date +%s) + MAX_MIN * 60 ))
streak=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  if provider_ok; then
    streak=$((streak + 1))
    log "probe ok (${streak}/${NEED_STREAK} consecutive)"
    if [ "$streak" -ge "$NEED_STREAK" ]; then
      log "PROVIDER RECOVERED (${NEED_STREAK} consecutive good probes)"
      if kodi_idle; then
        retune && log "DONE"
      else
        log "recovered, but the box is already playing - not touching it"
      fi
      exit 0
    fi
  else
    streak=0
  fi
  sleep 60
done

log "GIVE-UP: target still failing after ${MAX_MIN}m"
exit 1
