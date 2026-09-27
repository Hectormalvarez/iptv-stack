#!/usr/bin/env python
"""Label provider "event slot" channels with the event the provider has assigned to them.

Why
---
The curated lineup renames the provider's PPV/event feeds to readable slot names
("NFL Live 1", "NBA Live 3") because the raw names are cryptic ("NFL  | 01 -",
"NBA 06 :"). But the provider *also* appends the actual event to the **stream**
name and updates it as fixtures are assigned:

    NFL  | 01 -                                  <- empty slot
    NFL  | 02 - 1pm Chargers at Bills            <- the game
    NFL  | 15 - SNF 8:20pm Rams at Broncos
    NFL  | 16 - MNF 8:15pm Eagles at Bears

Renaming the channel discarded that, leaving 16 identical-looking "NFL Live N"
channels with no way to tell which game is on which. This restores it by reading
the provider's stream name and writing it to `ChannelOverride.name` (durable
across provider syncs), leaving the channel's own name as the generic slot.

Empty slots have their override name cleared, so they fall back to the curated
generic name - that way a slot labelled last week does not keep a stale game.

Run inside the Dispatcharr container (dry-run by default):

    docker exec -i dispatcharr python manage.py shell < scripts/label-event-slots.py

Apply:

    docker exec -e LABEL_APPLY=1 -i dispatcharr python manage.py shell < scripts/label-event-slots.py
"""

import os
import re

from apps.channels.models import (Channel, ChannelOverride, ChannelProfile,
                                  ChannelProfileMembership, ChannelStream)

APPLY = os.environ.get('LABEL_APPLY', '') == '1'
PROFILE = 'Kodi'

# Provider slot naming: "NFL  | 02 - <event>", "NBA 06 : <event>", "MLB 18:<event>"
SLOT_RE = re.compile(r'^\s*(?P<league>[A-Za-z&]{2,8})\s*\|?\s*(?P<num>\d+)\s*[-:]\s*(?P<label>.*)$')
# Slot names this script manages, so a non-slot channel is never touched
LEAGUE_PREFIX = re.compile(r'^\s*(NFL|NBA|MLB|NHL|NCAAF|NCAAB|SOCCER|UFC|WWE|BOXING|GOLF|TENNIS)\b',
                           re.I)


def effective_name(ch):
    """The name clients see: an override wins, else the channel's own name."""
    try:
        ov = ch.override
    except ChannelOverride.DoesNotExist:
        ov = None
    return (ov.name if ov and ov.name else ch.name)


def main():
    prof = ChannelProfile.objects.filter(name=PROFILE).first()
    if not prof:
        print('no %r profile' % PROFILE)
        return
    cids = list(ChannelProfileMembership.objects.filter(
        channel_profile=prof, enabled=True).values_list('channel_id', flat=True))
    channels = Channel.objects.filter(id__in=cids).select_related('override')

    labelled, cleared, skipped = [], [], 0
    for ch in channels:
        # the ordered through-model gives the primary source (order=0)
        link = (ChannelStream.objects.filter(channel=ch)
                .order_by('order').select_related('stream').first())
        if not link:
            continue
        raw = str(link.stream.name or '')
        if not LEAGUE_PREFIX.match(raw):
            continue
        m = SLOT_RE.match(raw)
        if not m:
            skipped += 1
            continue
        league = m.group('league').upper()
        label = m.group('label').strip(' -:|')
        # collapse the ᴿᴬᵂ/ᴴᴰ small-caps decorations and stray spacing
        label = re.sub(r'\s+', ' ', label).strip()
        if label and re.fullmatch(r'[\u1d00-\u1d7f\u2070-\u209f\s]*', label):
            label = ''          # quality-token only, no real event name
        labelled.append((ch, league, label))

    print('slot channels found : %d' % (len(labelled) + skipped))
    print('with an event label : %d' % sum(1 for _, _, l in labelled if l))
    print('empty slots         : %d' % sum(1 for _, _, l in labelled if not l))
    print()
    for ch, league, label in labelled:
        cur = effective_name(ch) or ''
        want = '%s: %s' % (league, label) if label else str(ch.name or '')
        mark = '  ' if cur == want else '->'
        print('   %s #%-5s %-30s %s' % (mark, int(ch.channel_number or 0), cur[:30], want[:44]))

    if not APPLY:
        print('\nDRY RUN - nothing written. Use LABEL_APPLY=1 to apply.')
        return

    added, removed = 0, 0
    for ch, league, label in labelled:
        ov, _ = ChannelOverride.objects.get_or_create(channel=ch)
        if label:
            ov.name = '%s: %s' % (league, label)
            ov.save()
            added += 1
        elif ov.name:
            ov.name = None      # fall back to the curated generic slot name
            ov.save()
            removed += 1
    print('\nAPPLIED: %d labelled, %d cleared' % (added, removed))


main()
