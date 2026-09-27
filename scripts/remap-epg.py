#!/usr/bin/env python
"""Remap channels to the correct EPG source (this is the "make the guide usable" fix).

Run inside the Dispatcharr container (dry-run by default):

    docker exec -i dispatcharr python manage.py shell < scripts/remap-epg.py

Add ``APPLY = True`` below (or pipe a modified copy) to actually write.

Why this exists
---------------
The provider's (STRONG8K) XMLTV only carries ~379 US channel ids out of ~4,423
(the rest are India/France/Spain/UK/Poland/Hungary...). Dispatcharr's fuzzy
matcher therefore bound channels to whatever looked closest, e.g.

    US: NBC 36 (KXAN) AUSTIN   -> KTRK.us      (ABC Houston!)
    US: CBS 42 AUSTIN (KEYE)   -> KPIX.us      (CBS San Francisco!)
    VIP: CANAL 13 (CAMPECHE)   -> canalplus.fr (Mexican channel, French guide!)
    US: DISNEY CHANNEL WEST    -> DisneyChannel.hu (Hungarian guide!)

Two epgshare01 feeds fix most of it:
  * EPGSHARE-US-LOCALS  4,456 entries, call-sign ids (``KXAN-DT.us_locals1``)
  * EPGSHARE-US2          769 entries, national cable (``CNN.HD.us2``)

What this script does, per channel
----------------------------------
 1. **call-sign match** - ``US: NBC 36 (KXAN) AUSTIN`` -> ``KXAN-DT.us_locals1``.
    This binds each station to *its own* schedule rather than a sibling affiliate.
 2. **region-aware name match** - normalised name must land in the channel's own
    region. A US channel will never be bound to a French entry.
 3. **unbind wrong-region bindings** - if a channel is bound to another country's
    guide and nothing correct is available, the binding is cleared. A blank guide
    is honest; a French schedule on a Mexican channel is not.
 4. Everything else is left untouched and reported.

Only visible channels are touched (``hidden_from_output=False``) - that is exactly
what Jellyfin imports and what the curated Kodi profile is drawn from.
"""

import os
import re
from collections import Counter, defaultdict

from apps.channels.models import Channel, ChannelOverride
from apps.epg.models import EPGData, EPGSource

# Dry run by default. To apply without editing the file (e.g. from cron):
#   docker exec -e REMAP_APPLY=1 -i dispatcharr python manage.py shell < scripts/remap-epg.py
APPLY = os.environ.get('REMAP_APPLY', '') == '1'
LOCALS_SOURCE = 'EPGSHARE-US-LOCALS'
NATIONAL_SOURCE = 'EPGSHARE-US2'

# Durable "no guide" target. Wrong-region bindings are pointed here instead of being
# nulled, because the output resolves EPG as
#     Coalesce(override__epg_data, channel.epg_data)
# so an override of NULL falls straight back to the (wrong) provider binding. A dummy
# EPG entry with no programmes makes Dispatcharr generate its own placeholder
# programmes for the channel - honest, and it survives provider syncs.
NOGUIDE_SOURCE = 'NO GUIDE'

# Why writes go to ChannelOverride and not Channel
# ------------------------------------------------
# From the model docstring: "Sync writes only to Channel.* fields and never to this
# table, so provider metadata keeps flowing while user customizations persist across
# refreshes." Every M3U refresh re-resolves each channel's EPG (see
# _resolve_epg_for_stream in m3u/tasks.py) and overwrites Channel.epg_data, which is
# why the previous version of this script kept partially reverting. Overrides stick.

CALLSIGN_RE = re.compile(r'\(([KW][A-Z]{2,4})\)')
DROP_TOKENS = re.compile(r'\b(hd|fhd|uhd|4k|sd|hevc|raw|vip|backup|plus|h)\b', re.I)

# Region of a channel is derived from its group name / name prefix, then mapped to
# the country tag that its EPG entries carry.
REGION_TAGS = {
    'US': 'us', 'MX': 'mx', 'DE': 'de', 'UK': 'uk', 'CA': 'ca', 'FR': 'fr',
    'ES': 'es', 'IN': 'in', 'PL': 'pl', 'NL': 'nl', 'PT': 'pt', 'BR': 'br',
    'AR': 'ar', 'IT': 'it', 'HU': 'hu',
}

# Which EPG country tags are acceptable for a channel in a given region. Anything
# outside this set counts as a wrong binding and is a candidate for unbinding.
ACCEPT = {
    'us': {'us', 'us2', 'us_locals1', 'espn', 'ca'},   # ca: CBC/CTV carried in US lists
    'mx': {'mx', 'us2', 'es'},                          # no real MX feed exists
    'ca': {'ca', 'us2'},
    'uk': {'uk'},
    'es': {'es'},
    'fr': {'fr'},
    'de': {'de'},
    'it': {'it'},
    'pt': {'pt'},
    'pl': {'pl'},
    'nl': {'nl'},
    'in': {'in'},
}


def norm(text):
    t = text.lower()
    # strip the source tag that epgshare ids carry (CNN.HD.us2, KXAN-DT.us_locals1)
    t = re.sub(r'[.\-_](us_locals1|us2|us|uk|ca|mx|de|fr|es|in|pl|nl|pt)\s*$', '', t)
    t = re.sub(r'\(pacific\)|\(east\)|\(west\)|\(sat\)|\bpacific\b', ' ', t)
    t = re.sub(r'^(us|usa|mx|uk|ca|de|fr|es|al|spo|in)\s*[:\-|]\s*', '', t)
    t = DROP_TOKENS.sub(' ', t)
    return re.sub(r'[^a-z0-9]', '', t)


def region_of(ch):
    """Best guess at which country's guide a channel should use.

    Group names win over channel names because providers are inconsistent with the
    name prefix (``US (ESPN+ 528) | ESPN+: Ottawa`` has no colon after ``US``).
    """
    group = str(getattr(ch.channel_group, 'name', '') or '')
    name = ch.name or ''

    for src in (group, name):
        m = re.match(r'\s*([A-Za-z]{2,3})\s*[:|\-(\s]', src)
        if m and m.group(1).upper() in REGION_TAGS:
            return REGION_TAGS[m.group(1).upper()]

    if name.upper().startswith('VIP:') or 'MEXICO' in group.upper():
        return 'mx'
    return None


def accepts(region, country):
    """Is ``country`` an acceptable guide for a channel in ``region``?"""
    if region is None:
        return True          # unknown region: never judge, never unbind
    return country in ACCEPT.get(region, {region})


def main():
    locals_src = EPGSource.objects.filter(name=LOCALS_SOURCE).first()
    nat_src = EPGSource.objects.filter(name=NATIONAL_SOURCE).first()
    if not locals_src and not nat_src:
        print('No supplemental sources found - run the refresh first.')
        return

    # --- index every EPG entry we have, keyed by normalised name then country tag ---
    def better(candidate, existing):
        if existing is None:
            return True
        if '(pacific)' in existing.lower() and '(pacific)' not in candidate.lower():
            return True
        return False

    index = defaultdict(dict)          # key -> {country: tvg_id}
    call_index = {}                    # callsign -> tvg_id (us_locals1)
    for epg in EPGData.objects.all().only('tvg_id', 'epg_source'):
        tvg = epg.tvg_id
        if not tvg:
            continue
        country = tvg.rsplit('.', 1)[-1].lower()
        key = norm(tvg)
        if better(tvg, index[key].get(country)):
            index[key][country] = tvg
        if epg.epg_source_id in (getattr(locals_src, 'id', None),):
            call = re.split(r'[-.]', tvg)[0].strip().lower()
            if re.fullmatch(r'[kw][a-z]{3,4}', call):
                cur = call_index.get(call)
                if cur is None or ('-dt.' in tvg.lower() and '-dt.' not in cur.lower()):
                    call_index[call] = tvg

    print('indexed keys: %d | call-sign entries: %d' % (len(index), len(call_index)))

    # Resolve the durable no-guide target up front so dry runs report already-blanked
    # channels instead of re-proposing them every time.
    noguid_src = EPGSource.objects.filter(name=NOGUIDE_SOURCE).first()
    noguid_epg = (EPGData.objects.filter(epg_source=noguid_src).first()
                  if noguid_src else None)
    noguid_tvg = str(getattr(noguid_epg, 'tvg_id', '') or '')

    # --- channel scope: everything Jellyfin sees (visible), not just the Kodi profile ---
    channels = (Channel.objects.filter(hidden_from_output=False)
                .select_related('epg_data', 'channel_group', 'override__epg_data'))
    print('scope: %d visible channels' % channels.count())

    planned, stats, samples, unbinds = [], Counter(), [], []
    for ch in channels.iterator():
        # effective value: an override wins over the provider-assigned binding
        current = ch.effective_epg_data_obj
        cur_tvg = str(getattr(current, 'tvg_id', '') or '')
        cur_country = cur_tvg.rsplit('.', 1)[-1].lower() if cur_tvg else ''
        region = region_of(ch)

        target, method = None, None

        # 1. call-sign match: each station gets its *own* schedule. Only attempted for
        #    US-ish channels so a stray "(ABCD)" in a foreign name cannot misfire.
        m = CALLSIGN_RE.search(ch.name or '')
        if m and region in ('us', None):
            cand = call_index.get(m.group(1).lower())
            if cand:
                target, method = cand, 'callsign'

        # 2. region-aware name match
        if target is None:
            cands = index.get(norm(ch.name or ''), {})
            order = [region] if region else []
            if region in ('us', None):
                order += ['us_locals1', 'us2', 'us']
            elif region == 'mx':
                order += ['mx', 'us2', 'es']
            else:
                order += ['us2', 'us']
            for c in order:
                if c and c in cands and accepts(region, c):
                    target, method = cands[c], 'region' if c == region else 'fallback'
                    break

        if target is not None:
            if cur_tvg.lower() == target.lower():
                stats['already_correct'] += 1
                continue
            stats['planned_%s' % method] += 1
            if cur_country:
                stats['was_%s' % cur_country] += 1
            planned.append((ch, target, method))
            if len(samples) < 18:
                samples.append((ch.name[:36], (cur_tvg or '-')[:24], target[:32], method))
            continue

        # 3. nothing correct available - is the existing binding from the wrong country?
        if cur_tvg and noguid_tvg and cur_tvg == noguid_tvg:
            stats['already_blank'] += 1
            continue
        if cur_tvg and not accepts(region, cur_country):
            stats['unbind_%s_%s' % (region or '?', cur_country)] += 1
            unbinds.append((ch, cur_tvg))
            if len(samples) < 18 + 8:
                samples.append((ch.name[:36], cur_tvg[:24], '(unbind)', 'wrong-region'))
            continue

        stats['left_alone'] += 1

    print('\n== plan ==')
    for k, v in sorted(stats.items(), key=lambda x: (-x[1], x[0])):
        print('   %-30s %d' % (k, v))
    print('\n   REBIND total : %d' % len(planned))
    print('   UNBIND total : %d' % len(unbinds))
    print('\n== samples (channel | current | proposed | method) ==')
    for s in samples:
        print('   %-36s %-24s %-32s %s' % s)

    if not APPLY:
        print('\nDRY RUN - nothing written. Set APPLY = True to apply.')
        return

    # --- durable "no guide" target (created once, then reused) ---
    if noguid_src is None:
        noguid_src = EPGSource.objects.create(
            name=NOGUIDE_SOURCE, source_type='dummy', is_active=False)
        print('created EPG source %r' % NOGUIDE_SOURCE)
    if noguid_epg is None:
        noguid_epg = EPGData.objects.create(
            epg_source=noguid_src, tvg_id='no-guide', name='No guide data')
    print('no-guide target: EPGData id=%s tvg_id=%r' % (noguid_epg.id, noguid_epg.tvg_id))

    cache, updated, cleared = {}, 0, 0
    for ch, target, method in planned:
        if target not in cache:
            cache[target] = EPGData.objects.filter(tvg_id=target).first()
        epg = cache[target]
        if epg is None:
            continue
        ChannelOverride.objects.update_or_create(
            channel=ch, defaults={'epg_data': epg})
        updated += 1
    for ch, _tvg in unbinds:
        ChannelOverride.objects.update_or_create(
            channel=ch, defaults={'epg_data': noguid_epg})
        cleared += 1
    print('\nAPPLIED: %d channels remapped, %d wrong-region bindings blanked (via overrides)'
          % (updated, cleared))


main()
