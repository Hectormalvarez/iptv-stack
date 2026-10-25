#!/usr/bin/env python
"""Attach the second provider's feeds as cross-provider failover sources.

Why
---
Every source on a channel currently comes from the SAME subscription (STRONG8K,
account 2). When that provider has a bad day - on 2026-10-25 it 403'd our IPv4,
then 502'd both address families for hours - every source fails together, because
they are all one provider. A second subscription (ZQAVO, account 3) only helps if
its feeds are actually ATTACHED to the channels you watch.

How it works
------------
Dispatcharr walks `ChannelStream.order` upward when the current source dies:

    Trying to find alternative stream for channel ... current stream ID: 59060
    Successfully switched to new URL ... (switch attempt 2/10)

so a source from another account just needs a higher order. This appends one per
channel and leaves the existing sources untouched.

Deliberately NOT fuzzy
----------------------
Matching is an explicit (channel number, stream-name substring) table, not name
normalisation. `add-backup-streams.py` learned this the hard way: matching on the
network name attached `NFL  | 4k - SNF 8:20pm Chiefs at Seahawks` as the "backup"
for NFL Network, so a failover would silently show a *different game*. A wrong
feed is worse than no feed.

Numbered fixture slots (`NFL  | 02 - 1pm Steelers at Saints`, `NCAAF 42: ...`) are
excluded for the same reason - their fixture must match, and the two providers
number their slots independently. Only stable network feeds are wired here.

Run inside the Dispatcharr container (dry-run by default):

    docker exec -i dispatcharr python manage.py shell < scripts/add-cross-provider-failover.py

Apply:

    docker exec -e FAILOVER_APPLY=1 -i dispatcharr python manage.py shell < scripts/add-cross-provider-failover.py
"""

import os

from apps.channels.models import (Channel, ChannelProfile, ChannelProfileMembership,
                                  ChannelStream)
from apps.m3u.models import M3UAccount

APPLY = os.environ.get('FAILOVER_APPLY', '') == '1'
PROFILE = 'Kodi'
NEW_ACCOUNT = 'ZQAVO'

# (channel number, channel group, substring of the NEW provider's stream name)
MAPPING = [
    # Austin locals - the new provider carries the real Austin affiliates
    (101, 'Austin Local', 'NBC 36 (KXAN) Austin'),
    (102, 'Austin Local', 'FOX 7 (KTBC)'),
    (103, 'Austin Local', 'CBS 42 (KEYE) Austin'),
    (104, 'Austin Local', 'ABC 13 (KTRK) Houston'),
    # general sports
    (301, 'Sports', 'US| ESPN 1 HD (S)'),
    (302, 'Sports', 'US| ESPN 2 HD (S)'),
    (303, 'Sports', 'ESPN NEWS'),
    (304, 'Sports', 'ESPN USA'),
    (305, 'Sports', 'CBS Sports Network'),
    (306, 'Sports', 'US| FOX SPORTS 1 HD (S)'),
    (307, 'Sports', 'US| FOX SPORTS 2 HD (S)'),
    # league networks
    (321, 'Sports: NFL', 'US| NFL NETWORK FHD (S)'),
    (1680, 'Mexico VIP', 'US| NFL NETWORK FHD (S)'),
    (1681, 'Mexico VIP', 'US| NFL NETWORK FHD (S)'),
    (2251, 'Sports: NFL', 'US| NFL NETWORK FHD (S)'),
    (325, 'Sports: NFL', 'US| NFL REDZONE FHD (S)'),
    (326, 'Sports: College', 'US| ESPN SEC NETWORK HD (S)'),
    (327, 'Sports: College', 'US| ESPN ACC NETWORK HD (S)'),
    (328, 'Sports: College', 'US| BIG TEN NETWORK HD (S)'),
    # college *network* feeds (stable channels, not per-fixture slots)
    (2401, 'Sports: College', 'NCAAF 03: ESPNU'),
    (2403, 'Sports: College', 'NCAAF 09: BIG TEN NETWORK'),
    (2404, 'Sports: College', 'NCAAF 10: BIG TEN NETWORK ALT'),
]


def main():
    prof = ChannelProfile.objects.filter(name=PROFILE).first()
    if not prof:
        print('no %r profile' % PROFILE)
        return
    cids = set(ChannelProfileMembership.objects.filter(
        channel_profile=prof, enabled=True).values_list('channel_id', flat=True))

    acct = M3UAccount.objects.filter(name=NEW_ACCOUNT).first()
    if not acct:
        print('no %r M3U account - add it first' % NEW_ACCOUNT)
        return
    pool = list(acct.streams.all())
    print('account %s (id=%s): %d streams available' % (acct.name, acct.id, len(pool)))

    planned, missing = [], []
    for num, grp, needle in MAPPING:
        ch = Channel.objects.filter(id__in=cids, channel_number=num,
                                    channel_group__name=grp).first()
        if not ch:
            missing.append('channel #%s in %r is not in the profile' % (num, grp))
            continue
        cands = [s for s in pool if needle.upper() in (s.name or '').upper()]
        if not cands:
            missing.append('#%s %s: no stream matching %r' % (num, ch.name, needle))
            continue
        src = cands[0]
        attached = list(ChannelStream.objects.filter(channel=ch))
        if any(l.stream_id == src.id for l in attached):
            print('  #%-5s already has %s' % (num, (src.name or '')[:44]))
            continue
        planned.append((ch, src, len(attached)))

    print()
    print('to attach: %d' % len(planned))
    for ch, src, n in planned:
        print('  #%-5s %-32s + %-32s (order=%d)'
              % (int(ch.channel_number), (ch.name or '')[:32], (src.name or '')[:32], n))
    for m in missing:
        print('  MISSING: %s' % m)

    if not APPLY:
        print('\nDRY RUN - nothing written. Use FAILOVER_APPLY=1 to apply.')
        return

    added = 0
    for ch, src, _ in planned:
        last = (ChannelStream.objects.filter(channel=ch)
                .order_by('-order').values_list('order', flat=True).first())
        next_order = (last if last is not None else -1) + 1
        _, created = ChannelStream.objects.get_or_create(
            channel=ch, stream=src, defaults={'order': next_order})
        if created:
            added += 1
    print('\nAPPLIED: %d cross-provider failover links added' % added)


main()
