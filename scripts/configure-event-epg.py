#!/usr/bin/env python
"""Bind explicit-date sports event slots to a customized dummy EPG source.

Why
---
Rotating event slots normally have no useful guide data. When the provider
actually carries an explicit date in the stream name, Dispatcharr's custom dummy
EPG can turn that into real programme metadata. This script is deliberately
narrow:

* only leagues listed here are considered;
* only channels explicitly passed via ``EVENT_EPG_CHANNEL_IDS`` are touched;
* time-only names (e.g. ``SNF 8:20pm``) are never used, because they would
  repeat on the wrong day.

Safety
------
* Dry-run by default. Set ``EVENT_EPG_APPLY=1`` to write.
* Only the ``Kodi`` profile is inspected.
* Existing EPG bindings are shown, never silently overwritten.

Usage
-----
Dry run:

    docker exec -i dispatcharr python manage.py shell < scripts/configure-event-epg.py

Bind one explicit-date NBA slot:

    docker exec -e EVENT_EPG_CHANNEL_IDS=2201 -i dispatcharr python manage.py shell \
        < scripts/configure-event-epg.py
    docker exec -e EVENT_EPG_APPLY=1 EVENT_EPG_CHANNEL_IDS=2201 -i dispatcharr python manage.py shell \
        < scripts/configure-event-epg.py
"""

import os
import re

from django.db import transaction

from apps.channels.models import Channel, ChannelOverride, ChannelProfile, ChannelProfileMembership
from apps.epg.models import EPGData, EPGSource

PROFILE = 'Kodi'
APPLY = os.environ.get('EVENT_EPG_APPLY', '') == '1'
CHANNEL_IDS = {
    int(x) for x in os.environ.get('EVENT_EPG_CHANNEL_IDS', '').split(',') if x.strip().isdigit()
}

# One source per league, with stream-name parsing tuned to that provider's
# fixture format. Only explicit-date formats belong here.
LEAGUE_CONFIG = {
    'NBA': {
        'source_name': 'NBA EVENTS PILOT',
        'title_pattern': r'(?<team1>.*?)\s+vs\s+(?<team2>.*?)\s+@.*',
        'time_pattern': r'(?<hour>\d{1,2}):(?<minute>\d{2})\s*(?<ampm>AM|PM)',
        'date_pattern': r'(?<month>[A-Za-z]{3,9})\s+(?<day>\d{1,2})',
        'timezone': 'America/Chicago',
        'program_duration': 180,
        'title_template': 'NBA: {team1} vs {team2}',
        'description_template': 'Provider-listed start {starttime} on {date}. Event-slot feed; availability may vary.',
        'upcoming_title_template': 'NBA upcoming: {team1} vs {team2} at {starttime}',
        'upcoming_description_template': 'Scheduled provider event slot. Availability is not confirmed until the feed starts.',
        'ended_title_template': 'NBA event slot ended',
        'ended_description_template': 'The provider event feed is no longer active.',
        'category': 'Sports,Live',
    },
}


def league_of(stream_name):
    name = str(stream_name or '')
    for league, cfg in LEAGUE_CONFIG.items():
        if re.search(rf'\b{league}\b', name, re.I):
            return league, cfg
    return None, None


def ensure_source(league, cfg):
    source, created = EPGSource.objects.get_or_create(
        name=cfg['source_name'],
        defaults={
            'source_type': 'dummy',
            'is_active': False,
            'custom_properties': {
                'name_source': 'stream',
                'title_pattern': cfg['title_pattern'],
                'time_pattern': cfg['time_pattern'],
                'date_pattern': cfg['date_pattern'],
                'timezone': cfg['timezone'],
                'program_duration': cfg['program_duration'],
                'title_template': cfg['title_template'],
                'description_template': cfg['description_template'],
                'upcoming_title_template': cfg['upcoming_title_template'],
                'upcoming_description_template': cfg['upcoming_description_template'],
                'ended_title_template': cfg['ended_title_template'],
                'ended_description_template': cfg['ended_description_template'],
                'category': cfg['category'],
                'include_date': True,
                'include_live': True,
            },
        },
    )
    if not created and source.source_type != 'dummy':
        raise RuntimeError('%s exists but is not a dummy source' % cfg['source_name'])
    epg_data = EPGData.objects.filter(epg_source=source).first()
    if not epg_data:
        raise RuntimeError('dummy source %s has no EPGData row' % cfg['source_name'])
    return source, epg_data, created


def main():
    prof = ChannelProfile.objects.filter(name=PROFILE).first()
    if not prof:
        print('no %r profile' % PROFILE)
        return

    cids = list(ChannelProfileMembership.objects.filter(
        channel_profile=prof, enabled=True).values_list('channel_id', flat=True))
    qs = Channel.objects.filter(id__in=cids).select_related(
        'override', 'channel_group').prefetch_related('channelstream_set__stream')

    print('profile %r | requested ids=%s | apply=%s' % (PROFILE, sorted(CHANNEL_IDS), APPLY))
    for ch in qs:
        if CHANNEL_IDS and ch.id not in CHANNEL_IDS:
            continue
        link = sorted(ch.channelstream_set.all(), key=lambda x: x.order)
        if not link:
            continue
        primary = link[0].stream
        league, cfg = league_of(primary.name)
        current_epg = getattr(getattr(ch, 'override', None), 'epg_data', None) or ch.epg_data
        ov = getattr(ch, 'override', None)
        display_name = ov.name if ov and ov.name else ch.name
        print('#%-5s %-38s stream=%-46s league=%s current_epg=%s' % (
            int(ch.channel_number or 0), display_name[:38],
            primary.name[:46], league or '-', current_epg.tvg_id if current_epg else '-'))
        if not league:
            continue

        existing = EPGSource.objects.filter(name=cfg['source_name']).first()
        if APPLY:
            source, epg_data, created = ensure_source(league, cfg)
            print('   -> source=%s epg=%s created=%s' % (source.name, epg_data.tvg_id, created))
        else:
            print('   -> would create/use source=%s (apply to bind)' % cfg['source_name'])
            continue

        with transaction.atomic():
            ov, _ = ChannelOverride.objects.get_or_create(channel=ch)
            ov.epg_data = epg_data
            ov.save(update_fields=['epg_data', 'updated_at'])

    if not APPLY:
        print('\nDRY RUN - nothing written. Use EVENT_EPG_APPLY=1 to apply.')


main()

