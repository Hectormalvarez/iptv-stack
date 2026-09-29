#!/usr/bin/env python
"""Add the provider's WNBA PPV event slots to the Kodi profile + TV guide.

Why
---
The provider exposes WNBA playoff games as PPV event channels in two groups:

  * 7536-7546  "####### WNBA PPV #######"      - slots with fixture + start/stop
  * 7547+      "####### WNBA PPV ⁽ᴮᴷ⁾ #######" - slots with clean fixture + date

Fixtures rotate through the same slot numbers as games are scheduled, so this
script re-resolves everything on each run (like label-event-slots.py).

What it does (dry-run by default):

  1. Finds every ``US (WNBA NN) | <away> at <home> (<date>)`` slot whose date is
     today or later.
  2. Renames it via ``ChannelOverride.name`` -> ``WNBA: <away> at <home>``
     (durable; survives provider syncs, same as label-event-slots.py).
  3. Re-homes it into the ``Sports: WNBA`` group at numbers 368+ (the curated
     event block after NFL 351-366 / MLB 367).
  4. Enables it in the Kodi profile.
  5. Attaches the matching feed from the 7536+ group as a failover stream
     (team sets matched between the two groups' names) - a single stream per
     channel dies at the provider's hourly reset.

Event slots carry no EPG (provider XC EPG for them is empty), so the guide
shows the channel name, exactly like the NFL event slots.

Run inside the Dispatcharr container (dry-run by default):

    docker exec -i dispatcharr python manage.py shell < scripts/add-wnba-events.py

Apply:

    docker exec -e WNBA_APPLY=1 -i dispatcharr python manage.py shell < scripts/add-wnba-events.py
"""

import os
import re
from datetime import datetime

from django.utils import timezone as tz

from apps.channels.models import (Channel, ChannelGroup, ChannelOverride,
                                  ChannelProfile, ChannelProfileMembership,
                                  ChannelStream, Stream)

APPLY = os.environ.get('WNBA_APPLY', '') == '1'
PROFILE = 'Kodi'
GROUP = 'Sports: WNBA'
BASE_NUMBER = 368          # NFL Live 351-366, MLB 367
FIRST_SLOT = 7548          # first slot of the fixture-labelled group
LAST_SLOT = 7580

DATE_RE = re.compile(r'\((\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\)\s*$')
TEAMS_RE = re.compile(r'^US \(WNBA \d+\) \| (.+?) \((\d{4}-\d{2}-\d{2})')
OLD_RE = re.compile(r'^US \((WNBA \d+)\) \|')


def team_tokens(text):
    """Lowercase word set of a fixture string, ignoring 'at'/'x' connectors."""
    words = re.split(r'[^A-Za-z]+', text.lower())
    return frozenset(w for w in words if w and w not in ('at', 'x', 'us', 'wnba'))


def main():
    profile = ChannelProfile.objects.filter(name=PROFILE).first()
    if not profile:
        raise SystemExit(f'no profile {PROFILE}')

    # --- 1. collect fixture slots (7548+) with a real date >= today ---
    today = tz.localdate()
    fixtures = []   # (channel, away_at_home, date)
    for num in range(FIRST_SLOT, LAST_SLOT + 1):
        ch = Channel.objects.filter(channel_number=num).first()
        if not ch:
            continue
        s = ch.streams.first()
        if not s:
            continue
        m = TEAMS_RE.match(s.name or '')
        if not m:
            continue  # empty slot (2098 placeholder date etc.)
        date = datetime.strptime(m.group(2), '%Y-%m-%d').date()
        if date < today:
            continue
        fixtures.append((ch, m.group(1).strip(), date))
    print(f'{len(fixtures)} upcoming WNBA fixtures found')

    # --- 2. pool of alternative feeds from the 7536+ group for failover ---
    alts = {}   # (date, team-token-frozenset) -> stream id
    for num in range(7537, 7547):
        ch = Channel.objects.filter(channel_number=num).first()
        if not ch:
            continue
        s = ch.streams.first()
        if not s:
            continue
        # "wnba: 1 name: Indiana Fever (IND) x Las Vegas Aces (LVA) start:..."
        core = re.match(r'^(?:wnba:?\s*\d+\s*(?:name:)?\s*|WNBA\s*\d+\s*:?\s*)(.*)', s.name or '', re.I)
        if not core:
            continue
        body = core.group(1)
        start = re.search(r'start:(\d{4}-\d{2}-\d{2})', body)
        body = re.sub(r'\s*(start|stop):.*$', '', body)
        body = re.sub(r'\([A-Z]{2,4}\)', '', body)   # drop team abbreviations
        tokens = team_tokens(body)
        if tokens and start:
            alts[(start.group(1), tokens)] = s.id

    group, _ = ChannelGroup.objects.get_or_create(name=GROUP)
    number = BASE_NUMBER
    for ch, fixture, date in fixtures:
        override, _ = ChannelOverride.objects.get_or_create(channel=ch)
        new_name = f'WNBA: {fixture}'
        backup = alts.get((date.isoformat(), team_tokens(fixture)))
        print(f'{number:>4}  {new_name}  ({date})'
              f'{"  +backup:" + str(backup) if backup else ""}')
        if not APPLY:
            number += 1
            continue
        if override.name != new_name:
            override.name = new_name
            override.save()
        ch.channel_number = number
        ch.channel_group = group
        ch.save()
        ChannelProfileMembership.objects.update_or_create(
            channel_profile=profile, channel=ch, defaults={'enabled': True})
        if backup:
            exists = ChannelStream.objects.filter(
                channel=ch, stream_id=backup).exists()
            if not exists:
                max_order = (ChannelStream.objects.filter(channel=ch)
                             .order_by('-order')
                             .values_list('order', flat=True).first())
                order = 0 if max_order is None else max_order + 1
                ChannelStream.objects.create(channel=ch, stream_id=backup, order=order)
        number += 1

    if APPLY:
        print(f'applied: {len(fixtures)} channels -> {GROUP} #{BASE_NUMBER}+')


main()
