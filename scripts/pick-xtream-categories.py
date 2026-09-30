#!/usr/bin/env python3
"""Pick the English/Western VOD + series categories from the provider's catalog.

Rules (deliberately conservative, "no foreign content"):

* a category must name a known Western/English brand or carry an EN marker
  (NETFLIX, DISNEY+, APPLE+, AMAZON, HBO MAX, PARAMOUNT, UNIVERSAL, DREAMWORKS,
   MARVEL, DISCOVERY+, SHOWTIME, PEACOCK, NICKELODEON, SKY, TOP MOVIES, IMDB, EN -
   / ENGLISH)
* anything mentioning a non-English region/language is dropped even if a brand
  matches (ASIA, TURKISH, ITALIAN SUB ENG, MULTI-SUBS, MX/ES/FR/DE/IN ...)
* "adult" categories are never included

Prints the chosen ids per content type as JSON on stdout, e.g.

    {"vod": [1923, 219, ...], "series": [427, ...]}

Usage:  scripts/pick-xtream-categories.py /tmp/xtl-categories.json
"""

import json
import re
import sys

BRANDS = re.compile(
    r'(netflix|disney\+|apple\+|amazon|hbo max|paramount|universal|dreamworks|'
    r'marvel|discovery\+|showtime|peacock|nickelodeon|sky\b|top movies|imdb|'
    r"james bond|007|en - |english)", re.I)

# Kept only in these flavours - premium presentations of a brand, or an
# explicitly-English content set. The rest (music, podcasts, reality, stand-up,
# docu-, niche variants) is dropped so the library stays a "best of" rather
# than a mirror of the provider's whole VOD shelf.
PREMIUM = re.compile(r'(⁴ᴷ|3840p|ᴰᵒˡᵇʸ|ᴰᴼᴸᴮʸ|4k|dolby)', re.I)
ENGLISH_SET = re.compile(r'(^en\s*-|english|imdb top 250|marvel|james bond|007|'
                         r'paramount|universal|dreamworks|top movies)', re.I)
MAIN_BRAND_SET = re.compile(r'^(netflix|disney\+|apple\+|amazon|hbo max)\s+(movies|series|kids)\b', re.I)

FOREIGN = re.compile(
    r'(asia|asian|turkish|turksih|italian|spanish|latino|mexic|india|indian|french|'
    r'german|deutsch|arabic|multi-subs|multi sub|\bmx\b|\bes\b|\bfr\b|\bde\b|\bin\b|'
    r'\bar\b|\bbr\b|\bpl\b|\bnl\b|\bpt\b|\btr\b|korea|japan|china|philip|vietnam|'
    r'thai|african|nollywood)', re.I)

ADULT = re.compile(r'\badult\b|\bxxx\b|porn', re.I)

# Niche shelves stay out even when they are 4K/Dolby: they bloat the library
# without adding anything a family would browse for.
NICHE = re.compile(r'(docu|music|podcast|reality|stand-?up|animi|anime|hevc|'
                   r'workout|wwe|as\u2011?mr|adult-?swim)', re.I)


def pick(cats):
    chosen = []
    for c in cats:
        name = c.get('category_name') or ''
        if ADULT.search(name) or FOREIGN.search(name) or NICHE.search(name):
            continue
        if not BRANDS.search(name):
            continue
        if PREMIUM.search(name) or ENGLISH_SET.search(name) or MAIN_BRAND_SET.search(name):
            chosen.append((int(c['category_id']), name))
    return chosen


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/xtl-categories.json'
    data = json.load(open(path))
    out = {}
    for key in ('vod', 'series'):
        chosen = pick(data[key])
        out[key] = [cid for cid, _ in chosen]
        print(f'--- {key}: {len(chosen)} of {len(data[key])} categories', file=sys.stderr)
        for cid, name in chosen:
            print(f'    {cid:>5}  {name}', file=sys.stderr)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
