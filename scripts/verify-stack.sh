#!/usr/bin/env bash
# Read-only health check for the iptv-stack. It never writes to Dispatcharr, Jellyfin or Kodi.
#
#   ./scripts/verify-stack.sh
#   KODI_HOST=root@192.168.1.181 ./scripts/verify-stack.sh   # adds the client checks
#
# Why: the curated lineup and the EPG matching are the fragile parts of this stack. A provider
# re-sync can renumber channels or drop EPG bindings without anything visibly breaking, so this
# reports drift instead of letting it go unnoticed. Exit code is non-zero if anything FAILs.
#
# Kodi checks need key-based SSH (password auth is deliberately NOT baked in - SSH hardening on
# the box is still outstanding, see docs/reference.md). Without KODI_HOST they are skipped.
set -uo pipefail

FAIL=0
ok()   { printf '  OK    %s\n' "$1"; }
warn() { printf '  WARN  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; FAIL=1; }

echo "== containers"
for c in dispatcharr jellyfin watchstate; do
    if docker ps --format '{{.Names}}' | grep -qx "$c"; then ok "$c running"; else fail "$c not running"; fi
done

echo "== dispatcharr: curated profile"
stats=$(docker exec -i dispatcharr python manage.py shell 2>/dev/null <<'PY'
from apps.channels.models import Channel, ChannelProfile, ChannelProfileMembership, ChannelGroup
from apps.epg.models import EPGSource, EPGData, ProgramData
from django.utils import timezone

now = timezone.now()
have = set(ProgramData.objects.filter(end_time__gte=now).values_list('epg_id', flat=True).distinct())
# channels deliberately parked on the dummy source are "no guide by design", not gaps
dummy_ids = set(EPGData.objects.filter(epg_source__source_type='dummy').values_list('id', flat=True))

p = ChannelProfile.objects.filter(name='Kodi').first()
if not p:
    print('PROFILE=missing')
else:
    cids = list(ChannelProfileMembership.objects.filter(channel_profile=p, enabled=True)
                .values_list('channel_id', flat=True))
    noguide = ChannelGroup.objects.filter(name='No Guide').first()
    parked = 0
    expect = 0
    covered = 0
    for c in (Channel.objects.filter(id__in=cids)
              .select_related('epg_data', 'override__epg_data', 'channel_group')):
        e = c.effective_epg_data_obj
        eid = getattr(e, 'id', None)
        if eid in dummy_ids:
            parked += 1
            continue
        if noguide and c.channel_group_id == noguide.id:
            parked += 1
            continue
        expect += 1
        if eid in have:
            covered += 1
    print('PROFILE=%d' % len(cids))
    print('EXPECT=%d' % expect)
    print('COVERED=%d' % covered)
    print('NOGUIDE=%d' % parked)
# dummy sources are intentionally idle - never report them as failed
for s in EPGSource.objects.exclude(source_type='dummy').order_by('id'):
    print('SOURCE=%s:%s:%s' % (s.name, s.status, s.refresh_interval))
PY
)
profile=$(grep -m1 '^PROFILE=' <<<"$stats" | cut -d= -f2)
expect=$(grep -m1 '^EXPECT=' <<<"$stats" | cut -d= -f2)
covered=$(grep -m1 '^COVERED=' <<<"$stats" | cut -d= -f2)
noguide=$(grep -m1 '^NOGUIDE=' <<<"$stats" | cut -d= -f2)
for v in profile expect covered noguide; do
    eval "[[ \"\${$v}\" =~ ^[0-9]+$ ]] || $v=0"
done
if [ "$profile" -eq 0 ]; then
    fail "Kodi profile missing or empty"
elif [ "$profile" -lt 1500 ]; then
    fail "Kodi profile has only $profile channels (expected ~1668) - did the builder run unwatched?"
else
    ok "Kodi profile: $profile channels ($noguide parked in 'No Guide')"
fi
# Coverage is measured excluding the deliberately guide-less 'No Guide' group.
if [ "$expect" -gt 0 ]; then
    missing=$((expect - covered))
    pct=$((covered * 100 / expect))
    if [ "$pct" -lt 95 ]; then
        fail "EPG coverage ${pct}% - $missing of $expect guide-expected channels have no upcoming programmes"
    else
        ok "EPG coverage ${pct}% ($missing of $expect guide-expected channels blank)"
    fi
fi
while read -r line; do
    spec=${line#SOURCE=}
    interval=${spec##*:}
    rest=${spec%:*}
    status=${rest##*:}
    name=${rest%:*}
    if [ "$status" = "success" ]; then ok "EPG source $name: success (every ${interval}h)"
    else fail "EPG source $name: $status"; fi
done < <(grep '^SOURCE=' <<<"$stats")

echo "== storage"
avail=$(df -Pk /mnt/storage 2>/dev/null | awk 'NR==2{print int($4/1024/1024)}')
if [ -z "$avail" ]; then fail "/mnt/storage not mounted"
elif [ "$avail" -lt 20 ]; then fail "/mnt/storage only ${avail}G free"
else ok "/mnt/storage: ${avail}G free"; fi

newest=$(find /mnt/storage/backups/iptv-stack -type f -mtime -2 2>/dev/null | head -1)
if [ -n "$newest" ]; then ok "backups fresh (< 2 days)"
else warn "no backup file newer than 2 days in /mnt/storage/backups/iptv-stack"; fi

if [ -n "${KODI_HOST:-}" ]; then
    echo "== kodi client ($KODI_HOST)"
    if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "$KODI_HOST" true 2>/dev/null; then
        fail "cannot ssh to $KODI_HOST with keys"
    else
        ok "reachable"
        gui=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$KODI_HOST" \
              'grep -oE "Display [0-9x]+ @ [0-9.]+ Hz" /storage/.kodi/temp/kodi.log | tail -1' 2>/dev/null)
        if grep -q "@ 60" <<<"$gui"; then ok "display: $gui"; else warn "display: ${gui:-unknown}"; fi
        errs=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$KODI_HOST" 'grep -cE ERROR /storage/.kodi/temp/kodi.log' 2>/dev/null)
        segs=$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$KODI_HOST" 'dmesg | grep -ci segfault' 2>/dev/null)
        if [ "${errs:-1}" -eq 0 ]; then ok "kodi log errors: 0"; else warn "kodi log errors: $errs"; fi
        ok "segfaults since boot (5 are the known VideoPlayer crashes): ${segs:-?}"
    fi
else
    echo "== kodi client: skipped (set KODI_HOST=root@<ip> to include)"
fi

echo
if [ "$FAIL" -eq 0 ]; then echo "RESULT: healthy"; else echo "RESULT: problems found"; fi
exit "$FAIL"
