#!/usr/bin/env python
"""Swap the curated lineup's primary provider.

Why
---
The curated "Kodi" profile was built on one subscription (STRONG8K, account 2).
When that subscription expired (2026-11-04), the entire lineup went dark: 1,679
of 1,680 channels had STRONG8K as their order-0 source, and the provider served
an "expired account" placeholder slate on every URL - real packets, no content
(identical encode fingerprint across unrelated channels; byte-probes therefore
pass). A provider swap has to re-point every channel's primary, not one channel.

How it works
------------
Dispatcharr resolves a channel's source by walking `ChannelStream.order`
ascending, so a "swap" is: attach the new provider's matching stream at order 0
and clean out the dead provider's links. Channels are matched with the strict
`core()` normalisation borrowed from add-backup-streams.py, plus these rules:

  * per-fixture event slots (``NFL  | 02 - ...``) never match a network channel -
    a wrong feed is worse than no feed (2026-09-27 lesson);
  * ambiguous matches (2+ candidates sharing a core) are skipped and reported,
    never guessed;
  * the fallback account (ZQAVO, max_connections=1) is always pinned deepest,
    never promoted (decision #27);
  * the operator can extend MATCH_OVERRIDES for names normalisation cannot
    bridge (same mechanism as add-cross-provider-failover.py).

Kodi is untouched by design: the playlist's per-channel URLs
(``/proxy/ts/stream/<channel-uuid>``) are stream-agnostic, so an upstream swap
needs no client-side playlist refresh.

Usage
-----
Dry run inside the Dispatcharr container (default):

    docker exec -i dispatcharr python manage.py shell < scripts/swap-provider.py

Apply (re-order primaries, remove the old provider's links):

    docker exec -e SWAP_APPLY=1 -i dispatcharr python manage.py shell < scripts/swap-provider.py
"""

import os
from collections import Counter

from apps.channels.models import (Channel, ChannelProfile, ChannelProfileMembership,
                                  ChannelStream)
from apps.m3u.models import M3UAccount

PROFILE = 'Kodi'
NEW_PRIMARY = os.environ.get('NEW_PRIMARY', 'EAGLE4K')
FROM_ACCOUNT = os.environ.get('FROM_ACCOUNT', 'STRONG8K')
FALLBACK_ACCOUNT = os.environ.get('FALLBACK_ACCOUNT', 'ZQAVO')
APPLY = os.environ.get('SWAP_APPLY', '') == '1'
PRUNE_OLD = os.environ.get('PRUNE_OLD', '1') == '1'


def account_of(link):
    s = link.stream
    return s.m3u_account.name if s.m3u_account else None


def main():
    prof = ChannelProfile.objects.filter(name=PROFILE).first()
    if not prof:
        print('no %r profile' % PROFILE)
        return
    cids = set(ChannelProfileMembership.objects.filter(
        channel_profile=prof, enabled=True).values_list('channel_id', flat=True))
    channels = list(Channel.objects.filter(id__in=cids)
                    .prefetch_related('channelstream_set__stream__m3u_account'))
    print('profile %r: %d enabled channels' % (PROFILE, len(channels)))

    prim = Counter()
    for ch in channels:
        links = sorted(ch.channelstream_set.all(), key=lambda x: x.order)
        prim[account_of(links[0]) if links else '(none)'] += 1
    print('current primaries by account: %s' % dict(prim))
    print('fallback account (pinned deepest): %s' % FALLBACK_ACCOUNT)
    print('swap policy: %s -> %s, prune old links: %s, apply: %s'
          % (FROM_ACCOUNT, NEW_PRIMARY, PRUNE_OLD, APPLY))

    acct = M3UAccount.objects.filter(name=NEW_PRIMARY).first()
    if not acct:
        print('\nM3U account %r does not exist yet - add it in Dispatcharr first'
              % NEW_PRIMARY)
        return
    pool = list(acct.streams.all())
    print('\nnew primary %r (id=%s): %d streams available, max_streams=%s'
          % (acct.name, acct.id, len(pool), acct.max_streams))

    print('\nstage 1 (census + account check) only - matching/apply lands next.')


main()
