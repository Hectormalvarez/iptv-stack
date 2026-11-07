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
import re
from collections import Counter, defaultdict

from apps.channels.models import (Channel, ChannelProfile, ChannelProfileMembership,
                                  ChannelStream)
from apps.m3u.models import M3UAccount

PROFILE = 'Kodi'
NEW_PRIMARY = os.environ.get('NEW_PRIMARY', 'EAGLE4K')
FROM_ACCOUNT = os.environ.get('FROM_ACCOUNT', 'STRONG8K')
FALLBACK_ACCOUNT = os.environ.get('FALLBACK_ACCOUNT', 'ZQAVO')
APPLY = os.environ.get('SWAP_APPLY', '') == '1'
PRUNE_OLD = os.environ.get('PRUNE_OLD', '1') == '1'

# Same normalisation as add-backup-streams.py: two names are the same channel
# only when their cores agree after prefixes / filler / quality tokens drop out.
PREFIX = re.compile(
    r'^\s*(us|usa|at&t|att|prime|tv|go|rk|mx|uk|ca|4k|8k|vip|spectrum|bally|dazn)'
    r'\s*(\([^)]*\))?\s*[:\-|]\s*', re.I)
QUALITY = re.compile(r'\b(hd|fhd|uhd|4k|8k|sd|raw|hevc|h|plus)\b', re.I)
FILLER = re.compile(r'\b(channel|network|television|tv|feed|stream)\b', re.I)

# Rotating per-fixture slots ("NFL  | 02 - 1pm Steelers at Saints") must never
# be matched against a stable network channel - a wrong feed is worse than none.
EVENT_SLOT_RE = re.compile(
    r'^\s*(NFL|NBA|MLB|NHL|NCAAF|NCAAB|SOCCER|UFC|WWE|BOXING|GOLF|TENNIS)'
    r'\s*\|?\s*\d+\s*[-:]', re.I)


def core(name):
    """Reduce a stream/channel name to a comparable core token."""
    t = str(name or '').lower()
    t = PREFIX.sub('', t)
    t = FILLER.sub(' ', t)
    t = QUALITY.sub(' ', t)
    return re.sub(r'[^a-z0-9]', '', t)


def is_event_slot(name):
    return bool(EVENT_SLOT_RE.match(str(name or '')))


def effective_name(ch):
    """The name clients see: an override wins, else the channel's own name."""
    try:
        ov = ch.override
    except Exception:
        ov = None
    return (ov.name if ov and ov.name else ch.name)


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
    if not pool:
        print('\npool is empty - enable this account\'s M3U groups, then refresh')
        return
    print('\nnew primary %r (id=%s): %d streams available, max_streams=%s'
          % (acct.name, acct.id, len(pool), acct.max_streams))

    by_core = defaultdict(list)
    for s in pool:
        k = core(s.name)
        if k:
            by_core[k].append(s)

    already, slots_skipped = 0, 0
    planned, ambiguous, unmatched = [], [], []
    per_group = defaultdict(lambda: [0, 0])   # group -> [matched, to-swap]
    for ch in channels:
        links = sorted(ch.channelstream_set.all(), key=lambda x: x.order)
        if links and account_of(links[0]) == NEW_PRIMARY:
            already += 1
            continue
        g = ch.channel_group.name if ch.channel_group else '(none)'
        per_group[g][1] += 1
        src_name = links[0].stream.name if links else ch.name
        if is_event_slot(src_name):
            slots_skipped += 1
            continue
        cands = []
        for k in (core(ch.name), core(effective_name(ch))):
            if k and by_core.get(k):
                cands = by_core[k]
                break
        if not cands:
            unmatched.append(ch)
            continue
        uniq = {s.id: s for s in cands}
        if len(uniq) > 1:
            ambiguous.append((ch, list(uniq.values())[:3]))
            continue
        planned.append((ch, cands[0]))
        per_group[g][0] += 1

    print('\n== stage 2: matching (dry run only - apply lands in a later commit) ==')
    print('already on %-10s: %d' % (NEW_PRIMARY, already))
    print('event slots skipped : %d' % slots_skipped)
    print('matched             : %d' % len(planned))
    print('ambiguous (skipped) : %d' % len(ambiguous))
    print('unmatched           : %d' % len(unmatched))

    print('\n== samples (channel | current primary -> new primary) ==')
    for ch, s in planned[:15]:
        links = sorted(ch.channelstream_set.all(), key=lambda x: x.order)
        cur = links[0].stream.name if links else '(none)'
        print('   #%-6s %-26s %-24s -> %s'
              % (int(ch.channel_number or 0), (ch.name or '')[:26],
                 str(cur)[:24], str(s.name)[:32]))

    if ambiguous:
        print('\n== ambiguous (need MATCH_OVERRIDES or a rename) - first 8 ==')
        for ch, cands in ambiguous[:8]:
            print('   #%-6s %-32s cands: %s'
                  % (int(ch.channel_number or 0), (ch.name or '')[:32],
                     [str(c.name)[:24] for c in cands]))
    if unmatched:
        print('\n== unmatched (first 20 of %d) ==' % len(unmatched))
        for ch in unmatched[:20]:
            print('   #%-6s %-36s %s'
                  % (int(ch.channel_number or 0), (ch.name or '')[:36],
                     (ch.channel_group.name if ch.channel_group else '')))

    print('\n== per-group coverage (matched / to-swap) ==')
    for g in sorted(per_group):
        m, t = per_group[g]
        if t:
            print('   %-36s %4d / %4d' % (g, m, t))

    print('\nDRY RUN - nothing written. Apply/prune stage not implemented yet.')


main()
