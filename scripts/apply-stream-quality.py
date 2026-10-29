#!/usr/bin/env python
"""Apply reviewed stream-order changes from the quality audit.

Why
---
The audit report is deliberately read-only. This script is the separate, explicit
step that turns reviewed recommendations into ``ChannelStream.order`` changes.
It only reorders streams that are *already attached* to the channel, so a wrong
fixture or an unattached provider feed cannot be introduced by this script.

Safety
------
* Dry-run by default. Set ``QUALITY_APPLY=1`` to write.
* Only works from the audit report at ``/data/audit/latest.json``.
* Event slots are never reordered automatically.
* ZQAVO is never promoted: it stays the deepest failover.
* A per-run backup of the previous order is written to ``/data/audit/orders-<ts>.json``.

Usage
-----
Dry run:

    docker exec -i dispatcharr python manage.py shell < scripts/apply-stream-quality.py

Apply the pilot audit:

    docker exec -e QUALITY_APPLY=1 -i dispatcharr python manage.py shell \
        < scripts/apply-stream-quality.py
"""

import json
import os
import re
from datetime import datetime, timezone

from django.db import transaction

from apps.channels.models import Channel, ChannelStream

REPORT_PATH = os.environ.get('AUDIT_REPORT_PATH', '/data/audit/latest.json')
APPLY = os.environ.get('QUALITY_APPLY', '') == '1'
BACKUP_DIR = os.environ.get('AUDIT_BACKUP_DIR', '/data/audit')

TIER_SCORE = {'S': 4, 'A': 3, 'B': 2, 'C': 1, 'D': 0}

# Conservative identity guard: two names are treated as the same channel only
# after provider prefixes, quality tokens and filler words are stripped.
IDENTITY_PREFIX = re.compile(
    r'^\s*(us|usa|at&t|att|prime|tv|go|rk|mx|uk|ca|4k|8k|vip|spectrum|bally|dazn)'
    r'\s*(\([^)]*\))?\s*[:\-|]\s*', re.I)
IDENTITY_QUALITY = re.compile(r'\b(hd|fhd|uhd|4k|8k|sd|raw|hevc|h|plus)\b', re.I)
IDENTITY_FILLER = re.compile(r'\b(channel|network|television|tv|feed|stream)\b', re.I)


def identity_core(name):
    t = str(name or '').lower()
    t = IDENTITY_PREFIX.sub('', t)
    t = IDENTITY_FILLER.sub(' ', t)
    t = IDENTITY_QUALITY.sub(' ', t)
    return re.sub(r'[^a-z0-9]', '', t)


def identity_region(name):
    m = re.match(r'^\s*([A-Za-z]{2,4})\s*[:\-|]', str(name or ''))
    return m.group(1).upper() if m else None


def same_region(current_name, candidate_name):
    cur = identity_region(current_name)
    cand = identity_region(candidate_name)
    if cur and cand:
        return cur == cand
    return True


def same_identity(current_name, candidate_name):
    cur = identity_core(current_name)
    cand = identity_core(candidate_name)
    return bool(cur and cand and cur == cand)


def tier_score(value):
    return TIER_SCORE.get(value, -1)


def load_report():
    with open(REPORT_PATH) as fh:
        return json.load(fh)


def best_candidate(channel_report):
    """Pick the best healthy non-primary candidate, if any."""
    sources = channel_report.get('sources', [])
    if len(sources) < 2:
        return None
    current = sources[0]
    candidates = []
    for src in sources[1:]:
        if not src.get('tier') or src.get('warnings'):
            continue
        if src.get('provider') == 'ZQAVO':
            continue
        if not same_identity(current.get('name'), src.get('name')):
            continue
        if not same_region(current.get('name'), src.get('name')):
            continue
        candidates.append(src)
    if not candidates:
        return None
    best = max(candidates, key=lambda s: tier_score(s['tier']))
    if tier_score(best['tier']) <= tier_score(current.get('tier') or 'unknown'):
        return None
    return best


def plan_changes(report):
    planned = []
    skipped = []
    for ch_report in report.get('channels', []):
        if ch_report.get('event_slot'):
            skipped.append((ch_report, 'event_slot'))
            continue
        best = best_candidate(ch_report)
        if not best:
            continue

        links = list(ChannelStream.objects.filter(channel_id=ch_report['channel_id'])
                     .select_related('stream').order_by('order'))
        report_ids = [s['stream_id'] for s in ch_report.get('sources', [])]
        db_ids = [l.stream_id for l in links]
        if set(report_ids) != set(db_ids):
            skipped.append((ch_report, 'stale_report_source_set'))
            continue

        current_primary = links[0]
        if best['stream_id'] == current_primary.stream_id:
            continue

        desired = [best['stream_id'], current_primary.stream_id]
        desired += [l.stream_id for l in links
                    if l.stream_id not in desired]
        planned.append({
            'channel_id': ch_report['channel_id'],
            'channel_number': ch_report.get('channel_number'),
            'effective_name': ch_report.get('effective_name'),
            'old_orders': [{'stream_id': l.stream_id, 'order': l.order} for l in links],
            'new_orders': [{'stream_id': sid, 'order': i} for i, sid in enumerate(desired)],
            'promote_stream_id': best['stream_id'],
            'promote_name': best.get('name'),
            'promote_tier': best.get('tier'),
        })
    return planned, skipped


def write_backup(planned):
    if not planned:
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = os.path.join(BACKUP_DIR, 'orders-%s.json' % stamp)
    with open(path, 'w') as fh:
        json.dump({'generated_at': stamp, 'orders': planned}, fh, indent=2)
    return path


@transaction.atomic
def apply_changes(planned):
    changed = 0
    for item in planned:
        links = {l.stream_id: l for l in
                 ChannelStream.objects.filter(channel_id=item['channel_id'])}
        for row in item['new_orders']:
            link = links.get(row['stream_id'])
            if link and link.order != row['order']:
                link.order = row['order']
                link.save(update_fields=['order'])
                changed += 1
    return changed


def main():
    report = load_report()
    planned, skipped = plan_changes(report)
    print('loaded %s scope=%s generated=%s' % (
        REPORT_PATH, report.get('scope'), report.get('generated_at')))
    print('planned changes: %d | skipped: %d' % (len(planned), len(skipped)))
    for item in planned:
        print('  #%-5s %-32s promote=%s tier=%s' % (
            item['channel_number'], item['effective_name'][:32],
            item['promote_name'][:40], item['promote_tier']))
    for ch, reason in skipped:
        print('  SKIP #%-5s %s' % (ch.get('channel_number'), reason))

    if not APPLY:
        print('\nDRY RUN - nothing written. Use QUALITY_APPLY=1 to apply.')
        return

    backup_path = write_backup(planned)
    changed = apply_changes(planned)
    print('\nAPPLIED: %d order changes | backup: %s' % (changed, backup_path))


main()
