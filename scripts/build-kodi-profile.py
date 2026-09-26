"""Build the curated 'Kodi' channel profile.

Creates the ChannelProfile "Kodi" plus clean channel groups/numbers and limits
membership to the curated 123 channels, so the Kodi box gets a small, fast,
cable-like lineup while Jellyfin keeps the full 3,590-channel playlist.

DRY_RUN=True  -> resolve and print the picks only (safe, no writes)
DRY_RUN=False -> create profile/groups/memberships, renumber and rename

Run:  docker exec -i dispatcharr python manage.py shell < scripts/build-kodi-profile.py

Note: creating a ChannelProfile makes *every* channel a member, so the write
path also disables membership for everything outside the curated set - that is
what keeps the client playlist at 123 channels.
"""
from apps.channels.models import Channel, ChannelGroup, ChannelProfile, ChannelProfileMembership
from apps.epg.models import ProgramData

DRY_RUN = True
FORCE = False           # required to shrink the profile deliberately
PROFILE_NAME = 'Kodi'
# Channels with no guide data at all are moved to the end of the lineup so the
# leading groups in the guide are fully populated (A3, 2026-09-26).
NO_GUIDE_GROUP = 'No Guide'
NO_GUIDE_BASE = 9001

qs = Channel.objects.filter(hidden_from_output=False)
BAD = ['ppv', '24/7', '24-7', 'test', 'adult', 'xxx', 'backup', 'dummy']


def resolve(aliases, prefer=None, exclude_extra=()):
    hits = Channel.objects.none()
    for a in aliases:
        hits = hits | qs.filter(name__icontains=a)
    scored = []
    for c in hits.distinct():
        low = c.name.lower()
        if any(b in low for b in BAD) or any(x in low for x in exclude_extra):
            continue
        score = 0
        if low.startswith('us:'):
            score += 40
        for bad in ('mx:', 'la:', 'rd:', 'ar:', 'es:', 'fr:', 'uk:', 'ca:', 'br:', 'lv:', 'it:'):
            if low.startswith(bad):
                score -= 25
        if prefer:
            for i, p in enumerate(prefer):
                if p in low:
                    score += 100 - i * 10
        if 'hd' in low or '4k' in low:
            score += 5
        if 'raw' in low:
            score += 2
        score -= len(c.name) / 100.0
        scored.append((score, c))
    scored.sort(key=lambda t: -t[0])
    return scored[0][1] if scored else None


# (number, group, aliases, prefer)
LINEUP = [
    # --- Austin / local ---
    (101, 'Austin Local', ['kxan'], ['us:']),
    (102, 'Austin Local', ['ktbc', 'fox 7 hd [austin]'], []),
    (103, 'Austin Local', ['keye'], []),
    (104, 'Austin Local', ['abc 13 (ktrk)'], []),
    (105, 'Austin Local', ['pbs hd'], []),
    (106, 'Austin Local', ['spectrum news austin'], []),
    # --- Entertainment (YouTube-TV-style bundle) ---
    (201, 'Entertainment', ['usa network'], ['us:']),
    (202, 'Entertainment', ['tnt hd'], ['us:']),
    (203, 'Entertainment', ['tbs hd'], ['us:']),
    (204, 'Entertainment', ['fx hd'], ['us:']),
    (205, 'Entertainment', ['fxx hd'], ['us:']),
    (206, 'Entertainment', ['amc hd'], ['us:']),
    (207, 'Entertainment', ['bbc america'], ['us:']),
    (208, 'Entertainment', ['comedy central'], ['us:']),
    (209, 'Entertainment', ['syfy hd'], ['us:']),
    (210, 'Entertainment', ['bravo hd'], ['us:']),
    (211, 'Entertainment', ['e! entertainment'], ['us:']),
    (212, 'Entertainment', ['tlc hd'], ['us:']),
    (213, 'Entertainment', ['hgtv'], ['us:']),
    (214, 'Entertainment', ['food network'], ['us:']),
    (215, 'Entertainment', ['discovery hd'], ['us:']),
    (216, 'Entertainment', ['history hd'], ['us:']),
    (217, 'Entertainment', ['a&e hd'], ['us:']),
    (218, 'Entertainment', ['lifetime hd'], ['us:']),
    (219, 'Entertainment', ['hallmark hd'], ['us:']),
    (220, 'Entertainment', ['trutv'], ['us:']),
    (221, 'Entertainment', ['tv land'], ['us:']),
    (222, 'Entertainment', ['investigation discovery'], ['us:']),
    (223, 'Entertainment', ['national geographic'], ['us:']),
    (224, 'Entertainment', ['animal planet'], ['us:']),
    (225, 'Entertainment', ['travel channel'], ['us:']),
    (226, 'Entertainment', ['freeform east'], ['us:']),
    (227, 'Entertainment', ['oxygen hd'], ['us:']),
    (228, 'Entertainment', ['we tv'], ['us:']),
    (229, 'Entertainment', ['ifc hd'], ['us:']),
    (230, 'Entertainment', ['sundance hd'], ['us:']),
    (231, 'Entertainment', ['bet hd'], ['us:']),
    (232, 'Entertainment', ['cmt hd'], ['us:']),
    (233, 'Entertainment', ['mtv live'], ['us:']),
    (234, 'Entertainment', ['cooking channel'], ['us:']),
    (235, 'Entertainment', ['destination america'], ['us:']),
    (236, 'Entertainment', ['magnolia'], ['us:']),
    (237, 'Entertainment', ['reelz'], ['us:']),
    (238, 'Entertainment', ['motortrend'], ['us:']),
    (239, 'Entertainment', ['outdoor channel'], ['us:']),
    # --- Sports (general) ---
    (301, 'Sports', ['espn hd'], ['us:']),
    (302, 'Sports', ['espn 2'], ['us:']),
    (303, 'Sports', ['espn news'], ['us:']),
    (304, 'Sports', ['espn usa'], ['us:']),
    (305, 'Sports', ['cbs sports network'], ['us:']),
    (306, 'Sports', ['fox sports 1 hd'], ['us:']),
    (307, 'Sports', ['fox sports 2 hd'], ['us:']),
    (308, 'Sports', ['bein sports hd'], ['us:']),
    (309, 'Sports', ['spectrum sports 1'], ['us:']),
    (310, 'Sports', ['yes network'], ['us:']),
    (311, 'Sports', ['sportsnet new york'], ['us:']),
    (312, 'Sports', ['msg hd'], ['us:']),
    (313, 'Sports', ['bally sports ohio'], ['us:']),
    (314, 'Sports', ['premier league'], ['us:']),
    (315, 'Sports', ['willow cricket hd'], ['us:']),
    (316, 'Sports', ['ufc hd'], ['us:']),
    (317, 'Sports', ['wwe hd'], ['us:']),
    (318, 'Sports', ['fight sports'], []),
    (319, 'Sports', ['sky sports f1'], []),
    # --- Sports by league ---
    (321, 'Sports: NFL', ['nfl network'], ['us:']),
    (322, 'Sports: NBA', ['nba tv'], []),
    (323, 'Sports: MLB', ['mlb network'], ['us:']),
    (324, 'Sports: NHL', ['nhl network'], ['us:']),
    (326, 'Sports: College', ['sec network'], ['us:']),
    (327, 'Sports: College', ['acc network'], ['us:']),
    (328, 'Sports: College', ['big ten network'], ['us:']),
    (331, 'Sports: Golf & Tennis', ['golf channel'], ['us:']),
    (332, 'Sports: Golf & Tennis', ['tennis channel'], ['us:']),
    # --- News ---
    (401, 'News', ['cnn hd'], ['us:']),
    (402, 'News', ['fox news hd'], ['us:']),
    (403, 'News', ['msnbc hd'], ['us:']),
    (404, 'News', ['cnbc hd'], ['us:']),
    (405, 'News', ['bloomberg hd'], ['us:']),
    (406, 'News', ['newsmax'], ['us:']),
    (407, 'News', ['hln hd'], ['us:']),
    (408, 'News', ['weather channel'], ['us:']),
    (409, 'News', ['bbc world news'], []),
    # --- Kids ---
    (501, 'Kids', ['nickelodeon'], ['us:']),
    (502, 'Kids', ['nick jr'], ['us:']),
    (503, 'Kids', ['disney channel'], ['us:']),
    (504, 'Kids', ['disney jr'], ['us:']),
    (505, 'Kids', ['cartoon network'], ['us:']),
    (506, 'Kids', ['boomerang hd'], ['us:']),
    (507, 'Kids', ['pbs kids'], ['us:']),
    # --- Movies ---
    (601, 'Movies', ['starz hd'], ['us:']),
    (602, 'Movies', ['showtime hd'], ['us:']),
    (603, 'Movies', ['movieplex hd'], ['us:']),
    (604, 'Movies', ['tcm hd'], ['us:']),
    # --- Spanish ---
    (701, 'Spanish', ['univision23'], ['us:']),
    (702, 'Spanish', ['telemundo 51'], ['us:']),
    (703, 'Spanish', ['fox deportes'], ['us:']),
    (704, 'Spanish', ['tudn zona'], ['us:']),
]

# Provider "PPV slot" event feeds carry live games; they have cryptic names
# ("NBA 06 :", "NFL  | 02 -") so they get renamed. Verified streaming.
# (number, group, exact provider name, clean name)
EVENTS = [
    (341, 'Sports: NBA', 'NBA 06 :', 'NBA Live 1'),
    (342, 'Sports: NBA', 'NBA 07 :', 'NBA Live 2'),
    (343, 'Sports: NBA', 'NBA 08 :', 'NBA Live 3'),
    (344, 'Sports: NBA', 'NBA 09 :', 'NBA Live 4'),
    (345, 'Sports: NBA', 'NBA 11 :', 'NBA Live 5'),
    (346, 'Sports: NBA', 'NBA 12 :', 'NBA Live 6'),
    (347, 'Sports: NBA', 'NBA 13 :', 'NBA Live 7'),
    (348, 'Sports: NBA', 'NBA 14 :', 'NBA Live 8'),
    (349, 'Sports: NBA', 'NBA 15 :', 'NBA Live 9'),
    (351, 'Sports: NFL', 'NFL  | 01 -', 'NFL Live 1'),
    (352, 'Sports: NFL', 'NFL  | 02 -', 'NFL Live 2'),
    (353, 'Sports: NFL', 'NFL  | 03 -', 'NFL Live 3'),
    (354, 'Sports: NFL', 'NFL  | 04 -', 'NFL Live 4'),
    (355, 'Sports: NFL', 'NFL  | 05 -', 'NFL Live 5'),
    (356, 'Sports: NFL', 'NFL  | 06 -', 'NFL Live 6'),
    (357, 'Sports: NFL', 'NFL  | 07 -', 'NFL Live 7'),
    (358, 'Sports: NFL', 'NFL  | 08 -', 'NFL Live 8'),
    (359, 'Sports: NFL', 'NFL  | 09 -', 'NFL Live 9'),
    (360, 'Sports: NFL', 'NFL  | 10 -', 'NFL Live 10'),
    (361, 'Sports: NFL', 'NFL  | 11 -', 'NFL Live 11'),
    (362, 'Sports: NFL', 'NFL  | 12 -', 'NFL Live 12'),
    (363, 'Sports: NFL', 'NFL  | 13 -', 'NFL Live 13'),
    (364, 'Sports: NFL', 'NFL  | 14 -', 'NFL Live 14'),
    (365, 'Sports: NFL', 'NFL  | 15 -', 'NFL Live 15'),
    (366, 'Sports: NFL', 'NFL  | 16 -', 'NFL Live 16'),
    (367, 'Sports: MLB', 'MLB 18:', 'MLB Live 1'),
]

resolved, missing, seen = [], [], set()
renames = {}
for number, group, aliases, prefer in LINEUP:
    ch = resolve(aliases, prefer)
    if not ch:
        missing.append((number, group, aliases))
        continue
    if ch.id in seen:
        missing.append((number, group, aliases + ['DUPLICATE-of-already-picked']))
        continue
    seen.add(ch.id)
    resolved.append((number, group, ch))

for number, group, exact, clean in EVENTS:
    # idempotent: prefer the already-renamed channel, else the provider name
    ch = (Channel.objects.filter(name=clean, hidden_from_output=False).first()
          or Channel.objects.filter(name=exact, hidden_from_output=False).first())
    if not ch or ch.id in seen:
        missing.append((number, group, [exact]))
        continue
    seen.add(ch.id)
    renames[ch.id] = clean
    resolved.append((number, group, ch))

print(f'resolved {len(resolved)} curated channels, {len(missing)} unresolved')

# ---------------------------------------------------------------------------
# Bulk imports: take every visible channel from the provider groups below and
# re-home it into a clean Kodi group with its own number range. Mexican
# channels only for the Latin side (LA|/AR|/RD| groups are deliberately left
# out), plus the full sports set.
# ---------------------------------------------------------------------------
SPORTS_IMPORTS = [
    (['SPORT ON AIR'],                            'Sports: International', 2701),
    (['US| SPORT', 'BALLY'],                      'Sports: Networks',      2001),
    (['NBA'],                                     'Sports: NBA',           2201),
    (['NFL'],                                     'Sports: NFL',           2251),
    (['MLB'],                                     'Sports: MLB',           2301),
    (['NHL'],                                     'Sports: NHL',           2351),
    (['NCAAF', 'NCAAB', 'BTN'],                   'Sports: College',       2401),
    (['UEFA', 'SOCCER', 'FLO SPORTS'],            'Sports: Soccer',        2451),
    (['TENNIS', 'GOLF'],                          'Sports: Golf & Tennis', 2501),
    (['RACING', 'MOTOR', 'NASCAR'],               'Sports: Motorsport',    2551),
    (['UFC', 'WWE', 'BOXING', 'FIGHT'],           'Sports: Combat',        2601),
    (['PARAMOUNT+ PPV', 'ESPN+ PPV', 'PPV EVENT',
      'B/R MAX'],                                 'Sports: Events',        3301),
]

# VIP must be matched before plain 'MX| MEXICO', which is a substring of it
MX_IMPORTS = [
    (['MX| MEXICO ⱽᴵᴾ'],   'Mexico VIP',    1201),
    (['MX| MEXICO'],       'Mexico',        801),
    (['MX| VIX'],          'Mexico: VIX',   841),
]

imported = []
used_numbers = {n for n, _, _ in resolved}


def import_group(matchers, kodi_group, base, pools):
    """Pull all visible channels from matching provider groups / name prefix."""
    picked = []
    for ch in pools:
        if ch.id in seen:
            continue
        gname = (ch.effective_channel_group_obj.name if ch.effective_channel_group_obj else '')
        up = gname.upper()
        if any(m.upper() in up for m in matchers):
            picked.append(ch)
    if not picked:
        return
    number = base
    for ch in sorted(picked, key=lambda c: (c.name or '').lower()):
        while number in used_numbers:
            number += 1
        used_numbers.add(number)
        seen.add(ch.id)
        imported.append((number, kodi_group, ch))
        number += 1


vis_all = list(qs.order_by('name'))
for matchers, kodi_group, base in SPORTS_IMPORTS:
    import_group(matchers, kodi_group, base, vis_all)

# Mexican channels that sit outside the MX| groups (named 'MX: ...')
mx_prefixed = [c for c in vis_all
               if c.id not in seen and (c.name or '').upper().startswith('MX:')]
number = 801
for ch in sorted(mx_prefixed, key=lambda c: (c.name or '').lower()):
    while number in used_numbers:
        number += 1
    used_numbers.add(number)
    seen.add(ch.id)
    imported.append((number, 'Mexico', ch))
    number += 1

for matchers, kodi_group, base in MX_IMPORTS:
    import_group(matchers, kodi_group, base, vis_all)

# Every group this script is allowed to own. Used both to adopt channels from a
# previous run and to keep the sweep honest - do not add provider group names here.
KODI_GROUPS = {
    'Austin Local', 'Entertainment', 'Sports', 'Sports: NFL', 'Sports: NBA', 'Sports: MLB',
    'Sports: NHL', 'Sports: College', 'Sports: Golf & Tennis', 'Sports: Soccer',
    'Sports: Motorsport', 'Sports: Combat', 'Sports: Networks', 'Sports: International',
    'Sports: Events', 'News', 'Kids', 'Movies', 'Spanish', 'Mexico', 'Mexico VIP',
    'Mexico: VIX', NO_GUIDE_GROUP,
}

allrows = resolved + imported
print(f'imported {len(imported)} extra channels; total {len(allrows)}\n')

# --- Idempotency: a previous run already moved channels into the Kodi groups, so the
# --- provider-group matchers above no longer see them. Adopt them back (keeping their
# --- existing group/number) instead of dropping them from the profile.
already = [ch.id for _, _, ch in allrows]
adopted = []
for ch in Channel.objects.filter(channel_group__name__in=KODI_GROUPS).exclude(id__in=already):
    adopted.append((ch.channel_number or NO_GUIDE_BASE, ch.channel_group.name, ch))
allrows = allrows + adopted
print(f'adopted {len(adopted)} channels already in Kodi groups (idempotent re-run)\n')
print('--- explicit picks (curated) ---')
last_group = None
for number, group, ch in resolved:
    if group != last_group:
        print(f'  == {group}')
        last_group = group
    old_g = ch.effective_channel_group_obj
    tag = f' -> rename "{renames[ch.id]}"' if ch.id in renames else ''
    print(f'   {number:>5}  {ch.name[:44]:<44} (was #{ch.channel_number}{tag})')

print('--- bulk imports (count + samples) ---')
by_group = {}
for number, group, ch in imported:
    by_group.setdefault(group, []).append((number, ch))
for group in sorted(by_group):
    rows = sorted(by_group[group])
    print(f'  == {group}: {len(rows)} channels, numbers {rows[0][0]}..{rows[-1][0]}')
    for number, ch in rows[:3]:
        print(f'         e.g. {number} {ch.name[:46]}')
for number, group, aliases in missing:
    print(f'  MISSING {number} {group} {aliases}')

# --- A3: channels without any *upcoming* guide data are swept to a trailing group,
# --- so every group above them in the guide is fully populated. Using end_time here
# --- matches what the client actually renders (stale past programmes do not show).
from django.utils import timezone as _tz
epg_with_programs = set(
    ProgramData.objects.filter(end_time__gte=_tz.now()).values_list('epg_id', flat=True).distinct())
swept = []
renumbered = []
next_no_guide = NO_GUIDE_BASE
for row in allrows:
    number, group, ch = row
    if getattr(ch, 'epg_data_id', None) not in epg_with_programs:
        renumbered.append((next_no_guide, NO_GUIDE_GROUP, ch))
        swept.append(ch)
        next_no_guide += 1
    else:
        renumbered.append(row)
allrows = renumbered
if swept:
    print(f'\nno-guide sweep: {len(swept)} channels -> "{NO_GUIDE_GROUP}" '
          f'(numbers {NO_GUIDE_BASE}+)')
    for ch in swept[:6]:
        print(f'         e.g. {ch.name[:50]}')
else:
    print('\nno-guide sweep: nothing to move')

if DRY_RUN:
    print('\nDRY RUN - nothing written')
else:
    # --- Safety guard: a bad resolve must never gut the live profile. ---
    existing_profile = ChannelProfile.objects.filter(name=PROFILE_NAME).first()
    current_enabled = 0
    if existing_profile:
        current_enabled = ChannelProfileMembership.objects.filter(
            channel_profile=existing_profile, enabled=True).count()
    print(f'\nresolved {len(allrows)} channels; profile currently has {current_enabled} enabled')
    if current_enabled and len(allrows) < 0.9 * current_enabled and not FORCE:
        print('ABORT: this would shrink the profile by more than 10%.')
        print('  - the provider-group matchers only see the original group names; channels already')
        print('    moved into Kodi groups are adopted above, so a short count means stale matchers')
        print('  - set FORCE = True if the reduction is intentional')
        raise SystemExit(1)
    profile, _ = ChannelProfile.objects.get_or_create(name=PROFILE_NAME)
    groups = {}
    for number, group, ch in allrows:
        if group not in groups:
            groups[group], _ = ChannelGroup.objects.get_or_create(name=group)
        ch.channel_number = number
        ch.channel_group = groups[group]
        if ch.id in renames:
            ch.name = renames[ch.id]
        ch.save()
        ChannelProfileMembership.objects.update_or_create(
            channel_profile=profile, channel=ch, defaults={'enabled': True})
    keep_ids = [ch.id for _, _, ch in allrows]
    disabled = (ChannelProfileMembership.objects.filter(channel_profile=profile)
                .exclude(channel_id__in=keep_ids).update(enabled=False))
    print(f'\nprofile {profile.id} "{profile.name}"')
    print('members disabled:', disabled)
    print('members enabled:', ChannelProfileMembership.objects.filter(
        channel_profile=profile, enabled=True).count())
