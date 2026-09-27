#!/usr/bin/env python
"""Attach backup provider streams to curated channels that only have one source.

Why
---
A channel with a single stream has nothing to fail over to. When the provider
resets that stream (these subs drop the connection roughly hourly), Dispatcharr
retries a few times, and if the provider refuses the immediate reconnect the
channel simply dies:

    Stream ends prematurely at 1187824068 ... Input/output error
    Stream was stable for 2532.9 seconds
    Reconnecting ... (attempt 1/3)   -> Server returned 4XX Client Error
    Reconnecting ... (attempt 2/3)   -> Server returned 4XX Client Error
    Maximum retry attempts (3) reached
    Trying to find alternative stream ... Found 0 alternatives   <-- dies here

Adding a second source (ChannelStream with order=1) is what `trying next stream`
needs, and it is persistent - unlike patching MAX_RETRIES/RETRY_WAIT_INTERVAL in
apps/proxy/config.py, which lives inside the container.

How a backup is chosen (deliberately strict)
-------------------------------------------
Two streams are treated as the same channel only when their names normalise to
the same core:

  * provider prefixes dropped   "US:", "AT&T:", "PRIME:", "TV:", "GO:", "RK:"
  * filler words dropped        "channel", "network", "tv", "feed", "television"
  * quality tokens dropped      "hd", "fhd", "uhd", "4k", "sd", "raw", "plus"
  * punctuation/spacing removed

So "US: HALLMARK HD" and "AT&T: HALLMARK CHANNEL" both reduce to ``hallmark`` and
match, while the different networks do not:

    "US: HALLMARK M & M HD"    -> hallmarkmm      (no match)
    "US: HALLMARK DRAMA HD"    -> hallmarkdrama   (no match)
    "AT&T: HALLMARK FAMILY"    -> hallmarkfamily  (no match)

Run inside the Dispatcharr container (dry-run by default):

    docker exec -i dispatcharr python manage.py shell < scripts/add-backup-streams.py

Apply:

    docker exec -e BACKUP_APPLY=1 -i dispatcharr python manage.py shell < scripts/add-backup-streams.py
"""

import os
import re
from collections import defaultdict

from apps.channels.models import Channel, ChannelProfile, ChannelProfileMembership, ChannelStream, Stream

APPLY = os.environ.get('BACKUP_APPLY', '') == '1'
PROFILE = 'Kodi'
MAX_BACKUPS = 2

PREFIX = re.compile(
    r'^\s*(us|usa|at&t|att|prime|tv|go|rk|mx|uk|ca|4k|8k|vip|spectrum|bally|dazn)'
    r'\s*(\([^)]*\))?\s*[:\-|]\s*', re.I)
QUALITY = re.compile(r'\b(hd|fhd|uhd|4k|8k|sd|raw|hevc|h|plus)\b', re.I)
FILLER = re.compile(r'\b(channel|network|television|tv|feed|stream)\b', re.I)


def core(name):
    """Reduce a stream/channel name to a comparable core token."""
    t = str(name or '').lower()
    t = PREFIX.sub('', t)
    t = FILLER.sub(' ', t)
    t = QUALITY.sub(' ', t)
    # unicode small-caps (ᴿᴬᵂ) and similar decorations fall out of this strip
    return re.sub(r'[^a-z0-9]', '', t)


def main():
    prof = ChannelProfile.objects.filter(name=PROFILE).first()
    if not prof:
        print('no %r profile' % PROFILE)
        return
    cids = list(ChannelProfileMembership.objects.filter(
        channel_profile=prof, enabled=True).values_list('channel_id', flat=True))
    channels = (Channel.objects.filter(id__in=cids).prefetch_related('streams'))
    print('profile %r: %d channels' % (PROFILE, len(channels)))

    # index every stream we know about by its normalised core
    by_core = defaultdict(list)
    for s in Stream.objects.all().only('id', 'name', 'url'):
        k = core(s.name)
        if k:
            by_core[k].append(s)

    planned, samples = [], []
    already_ok = 0
    for ch in channels:
        attached = list(ch.streams.all())
        if len(attached) > 1:
            already_ok += 1
            continue
        if not attached:
            continue
        k = core(attached[0].name)
        if not k:
            continue
        have_ids = {s.id for s in attached}
        cands = [s for s in by_core.get(k, []) if s.id not in have_ids]
        if not cands:
            continue
        for s in cands[:max(0, MAX_BACKUPS - len(attached))]:
            planned.append((ch, s))
            if len(samples) < 20:
                samples.append((ch.name[:38], str(attached[0].name)[:34], str(s.name)[:34]))

    print('\nchannels already having >1 stream : %d' % already_ok)
    print('backups to add                    : %d' % len(planned))
    print('\n== samples (channel | primary | proposed backup) ==')
    for a, b, c in samples:
        print('   %-38s %-34s %s' % (a, b, c))

    if not APPLY:
        print('\nDRY RUN - nothing written. Use BACKUP_APPLY=1 to apply.')
        return

    added = 0
    for ch, s in planned:
        next_order = (ChannelStream.objects.filter(channel=ch)
                      .order_by('-order').values_list('order', flat=True).first() or 0) + 1
        _, created = ChannelStream.objects.get_or_create(
            channel=ch, stream=s, defaults={'order': next_order})
        if created:
            added += 1
    print('\nAPPLIED: %d backup stream links added' % added)


main()
