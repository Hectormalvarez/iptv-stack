#!/usr/bin/env python
"""Remap curated Kodi-profile channels to better EPG sources.

Run inside the Dispatcharr container (dry-run by default):

    docker exec -i dispatcharr python manage.py shell < scripts/remap-epg.py

Add ``APPLY = True`` below (or pipe a modified copy) to actually write.

Why this exists
---------------
The provider's (STRONG8K) XMLTV only carries ~379 US channel ids out of ~4,423
(the rest are India/France/Spain/UK/Poland/Mexico...). Dispatcharr's fuzzy
matcher therefore bound US channels to whatever looked closest, e.g.

    US: NBC 36 (KXAN) AUSTIN   -> KTRK.us      (ABC Houston!)
    US: CBS 42 AUSTIN (KEYE)   -> KPIX.us      (CBS San Francisco!)
    US: FOX 7 HD [AUSTIN]      -> WUTV.us      (FOX Buffalo!)

Two epgshare01 feeds fix that:
  * EPGSHARE-US-LOCALS  ids like ``KXAN-DT.us_locals1``  (call-sign based)
  * EPGSHARE-US2        ids like ``CNN.HD.us2``          (national cable)

Matching is deliberately conservative: call-signs must match exactly, and
network names must normalise to the same string. Anything ambiguous is left
alone and reported.
"""

import re
from collections import Counter, defaultdict

from apps.channels.models import Channel, ChannelProfile, ChannelProfileMembership
from apps.epg.models import EPGData, EPGSource, ProgramData

APPLY = False
LOCALS_SOURCE = 'EPGSHARE-US-LOCALS'
NATIONAL_SOURCE = 'EPGSHARE-US2'
PROFILE = 'Kodi'

CALLSIGN_RE = re.compile(r'\(([KW][A-Z]{2,4})\)')
DROP_TOKENS = re.compile(r'\b(hd|fhd|uhd|4k|sd|hevc|raw|vip|backup|plus|h)\b', re.I)


def norm(text):
    t = text.lower()
    # strip the source tag that epgshare ids carry (CNN.HD.us2, KXAN-DT.us_locals1)
    t = re.sub(r'[.\-_](us_locals1|us2|us|uk|ca|mx|de|fr|es|in|pl|nl|pt)\s*$', '', t)
    t = re.sub(r'\(pacific\)|\(east\)|\(west\)|\(sat\)|\bpacific\b', ' ', t)
    t = re.sub(r'^(us|usa|mx|uk|ca|de|fr|es|al|spo|in)\s*[:\-|]\s*', '', t)
    t = DROP_TOKENS.sub(' ', t)
    return re.sub(r'[^a-z0-9]', '', t)


GROUP_REGION = {
    'US': 'us', 'MX': 'mx', 'DE': 'de', 'UK': 'uk', 'CA': 'ca',
    'FR': 'fr', 'ES': 'es', 'IN': 'in', 'PL': 'pl', 'NL': 'nl', 'PT': 'pt',
}


def region_hint(ch):
    """Best guess at which country's guide a channel should use."""
    group = str(getattr(ch.channel_group, 'name', '') or '')
    m = re.match(r'\s*([A-Za-z]{2,3})\s*\|', group)
    if m and m.group(1).upper() in GROUP_REGION:
        return GROUP_REGION[m.group(1).upper()]
    m = re.match(r'\s*([A-Za-z]{2,3})\s*[:\-|]', ch.name)
    if m and m.group(1).upper() in GROUP_REGION:
        return GROUP_REGION[m.group(1).upper()]
    if ch.name.upper().startswith('VIP:') or 'MEXICO' in group.upper():
        return 'mx'
    return None


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

    prof = ChannelProfile.objects.get(name=PROFILE)
    cids = ChannelProfileMembership.objects.filter(channel_profile=prof, enabled=True).values_list('channel_id', flat=True)
    channels = Channel.objects.filter(id__in=list(cids)).select_related('epg_data', 'channel_group')

    planned, stats, samples = [], Counter(), []
    for ch in channels.iterator():
        current = ch.epg_data
        cur_tvg = str(getattr(current, 'tvg_id', '') or '')
        cur_country = cur_tvg.rsplit('.', 1)[-1].lower() if cur_tvg else ''

        hint = region_hint(ch)
        target = None
        method = None

        m = CALLSIGN_RE.search(ch.name)
        if m and m.group(1).lower() in call_index:
            target, method = call_index[m.group(1).lower()], 'callsign'
        else:
            cands = index.get(norm(ch.name), {})
            # Prefer the channel's own region; for US-style content allow the US feeds.
            # Never fall back to an unrelated country's guide - wrong data is worse than none.
            order = [hint] if hint else []
            if hint in ('us', None):
                order += ['us_locals1', 'us2', 'us']
            else:
                order += ['us2', 'us']
            for c in order:
                if c and c in cands:
                    target, method = cands[c], 'region' if c == hint else 'fallback'
                    break

        if target is None:
            stats['no_exact_name_match'] += 1
            continue
        if cur_tvg.lower() == target.lower():
            stats['already_correct'] += 1
            continue

        stats['planned_%s' % method] += 1
        if cur_country:
            stats['was_%s' % cur_country] += 1
        planned.append((ch, target, method))
        if len(samples) < 16:
            samples.append((ch.name[:34], (cur_tvg or '-')[:22], target[:30], method, str(getattr(ch.channel_group, 'name', ''))[:14]))

    print('\n== plan ==')
    for k, v in sorted(stats.items()):
        print('   %-26s %d' % (k, v))
    print('\n== samples (channel | current | proposed | method | group) ==')
    for s in samples:
        print('   %-34s %-22s %-30s %-8s %s' % s)

    if not APPLY:
        print('\nDRY RUN - nothing written. Set APPLY = True to apply.')
        return

    cache, updated = {}, 0
    for ch, target, method in planned:
        country = target.rsplit('.', 1)[-1].lower()
        if target not in cache:
            cache[target] = EPGData.objects.filter(tvg_id=target).first()
        epg = cache[target]
        if epg is None:
            continue
        ch.epg_data = epg
        ch.save(update_fields=['epg_data'])
        updated += 1
    print('\nAPPLIED: %d channels remapped' % updated)


main()
