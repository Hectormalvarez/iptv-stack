#!/usr/bin/env python
"""Read-only stream-quality audit for the curated Kodi profile.

Why
---
Dispatcharr picks a channel's stream from ``ChannelStream.order``. The provider's
names lie about quality, and a single 6-second sample can be wildly misleading
(the same 720p30 feed read 15 Mbps over 6 s but 4.8 Mbps over 15 s, and one
1080p60 "RAW" feed was outright corrupt). So quality choices need actual
measurements, not name tokens.

How it works
------------
The script builds an inventory of every source attached to the Kodi profile and
optionally probes each source through Dispatcharr's stream-specific proxy path
(``/proxy/ts/stream/<stream_hash>``). This is deliberate:

* it never bypasses Dispatcharr or exposes provider credentials;
* the URL is per-stream, so a channel-level failover cannot contaminate the
  measurement;
* one probe runs at a time, keeping two primary-provider connections free.

ZQAVO is deliberately never probed: it is the one-connection failover provider.

Usage
-----
Dry run inside the Dispatcharr container (safe, no probing):

    docker exec -i dispatcharr python manage.py shell < scripts/audit-stream-quality.py

Probe the pilot channels only:

    docker exec -e AUDIT_PROBE=1 -i dispatcharr python manage.py shell \
        < scripts/audit-stream-quality.py

Probe the full core scope:

    docker exec -e AUDIT_PROBE=1 AUDIT_SCOPE=core -i dispatcharr python manage.py shell \
        < scripts/audit-stream-quality.py

The JSON report is written to ``/data/audit/latest.json`` (inside the
Dispatcharr data volume) and a short human-readable summary is printed. No
provider URLs, credentials or stream hashes are emitted.
"""

import json
import os
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone

import requests

from apps.channels.models import Channel, ChannelProfile, ChannelProfileMembership, ChannelStream

PROFILE = 'Kodi'
REPORT_DIR = os.environ.get('AUDIT_REPORT_DIR', '/data/audit')
PROBE = os.environ.get('AUDIT_PROBE', '') == '1'
SCOPE = os.environ.get('AUDIT_SCOPE', 'pilot')
SAMPLE_SECONDS = int(os.environ.get('AUDIT_SAMPLE_SECONDS', '25'))
PAUSE_BETWEEN = float(os.environ.get('AUDIT_PAUSE_SECONDS', '5'))

# Rough scoping only. The audit never changes anything.
CORE_GROUPS = [
    'Austin Local', 'Entertainment', 'News', 'Kids', 'Movies', 'Spanish', 'Sports',
    'Sports: College', 'Sports: NFL', 'Sports: NBA', 'Sports: MLB',
    'Sports: NHL', 'Sports: Networks',
]

# Small pilot set: locals, the main sports networks, and the known tricky RedZone.
PILOT_CHANNELS = [
    (101, 'Austin Local'),
    (102, 'Austin Local'),
    (103, 'Austin Local'),
    (301, 'Sports'),
    (302, 'Sports'),
    (306, 'Sports'),
    (307, 'Sports'),
    (321, 'Sports: NFL'),
    (325, 'Sports: NFL'),
    (2201, 'Sports: NBA'),
    (2401, 'Sports: College'),
]

EVENT_GROUPS = {'Sports: Events', 'No Guide'}

# League prefixes used by the provider on rotating event slots. These channels
# need fixture identity checks before any order change, so the audit reports
# them but the apply step must never promote them automatically.
EVENT_SLOT_RE = re.compile(
    r'^\s*(NFL|NBA|MLB|NHL|NCAAF|NCAAB|SOCCER|UFC|WWE|BOXING|GOLF|TENNIS)\b', re.I)


def effective_name(ch):
    """The name clients see: override wins, else the channel's own name."""
    ov = getattr(ch, 'override', None)
    return (ov.name if ov and ov.name else ch.name)


def is_event_slot(ch, primary_stream_name):
    """Best-effort detection of rotating provider event slots."""
    if ch.channel_group and ch.channel_group.name in EVENT_GROUPS:
        return True
    return bool(EVENT_SLOT_RE.match(str(primary_stream_name or '')))


def fps_from_ffprobe(value):
    """Convert ffprobe's '60000/1001' style frame rate into a float."""
    if not value:
        return None
    try:
        num, den = str(value).split('/')
        num, den = float(num), float(den)
        return round(num / den, 3) if den else None
    except Exception:
        return None


def probe_metadata(url):
    """Return codec/resolution/fps metadata for one stream."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-analyzeduration', '3000000', '-probesize', '3000000',
        '-show_streams', '-show_format', '-of', 'json', url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return {'ok': False, 'error': 'ffprobe_failed'}
        data = json.loads(proc.stdout)
        video = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
        audio = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None)
        if not video:
            return {'ok': False, 'error': 'no_video_stream'}
        return {
            'ok': True,
            'video_codec': video.get('codec_name'),
            'width': video.get('width'),
            'height': video.get('height'),
            'fps': fps_from_ffprobe(video.get('avg_frame_rate') or video.get('r_frame_rate')),
            'pixel_format': video.get('pix_fmt'),
            'audio_codec': audio.get('codec_name') if audio else None,
            'audio_channels': audio.get('channels') if audio else None,
            'audio_sample_rate': audio.get('sample_rate') if audio else None,
        }
    except Exception:
        return {'ok': False, 'error': 'ffprobe_exception'}


def sample_stream(url):
    """Measure a short live sample without decoding video."""
    started = time.monotonic()
    first_byte = None
    total = 0
    status = None
    try:
        with requests.get(url, stream=True, timeout=(5, SAMPLE_SECONDS + 5)) as resp:
            status = resp.status_code
            if status != 200:
                return {
                    'ok': False, 'status': status, 'bytes': 0,
                    'elapsed': round(time.monotonic() - started, 2),
                    'throughput_mbps': None, 'error': 'http_error',
                }
            for chunk in resp.iter_content(chunk_size=65536):
                if first_byte is None:
                    first_byte = time.monotonic()
                total += len(chunk)
                if time.monotonic() - started >= SAMPLE_SECONDS:
                    break
        elapsed = time.monotonic() - started
        return {
            'ok': total > 0,
            'status': status,
            'bytes': total,
            'elapsed': round(elapsed, 2),
            'startup_seconds': round(first_byte - started, 2) if first_byte else None,
            'throughput_mbps': round((total * 8) / elapsed / 1_000_000, 2) if elapsed else None,
            'error': None if total > 0 else 'no_data',
        }
    except requests.exceptions.Timeout:
        return {'ok': False, 'status': status, 'bytes': total,
                'elapsed': round(time.monotonic() - started, 2),
                'throughput_mbps': None, 'error': 'timeout'}
    except Exception:
        return {'ok': False, 'status': status, 'bytes': total,
                'elapsed': round(time.monotonic() - started, 2),
                'throughput_mbps': None, 'error': 'request_exception'}


def probe_stream(stream):
    """Probe one stream through Dispatcharr's stream-specific proxy path."""
    if not stream.stream_hash:
        return {'ok': False, 'error': 'no_stream_hash'}
    # Never leak the URL into logs; it is only used in-process.
    url = f"http://localhost:9191/proxy/ts/stream/{stream.stream_hash}"
    meta = probe_metadata(url)
    sample = sample_stream(url)
    return {'metadata': meta, 'sample': sample}


def quality_tier(meta, sample, is_sports):
    """Rough, explainable tier. Identity and health still outrank this."""
    if not meta.get('ok') or not sample.get('ok'):
        return 'unknown'
    width = meta.get('width') or 0
    fps = meta.get('fps') or 0
    sports = is_sports
    if sports and fps >= 50:
        if width >= 3840:
            return 'S'
        if width >= 1920:
            return 'A'
        if width >= 1280:
            return 'B'
        return 'unknown'
    if not sports and width >= 3840 and fps >= 24:
        return 'S'
    if width >= 1920 and (fps >= 50 or fps >= 24):
        return 'A' if fps >= 50 else 'B'
    if width >= 1280 and fps >= 50:
        return 'B'
    if width >= 1920 and fps >= 25:
        return 'C'
    if width >= 1280 and fps >= 25:
        return 'D'
    return 'unknown'


def health_warnings(meta, sample):
    """Cheap, explainable health signals. Bitrate is a hint, not a score."""
    warnings = []
    if not meta.get('ok'):
        warnings.append('metadata_failed')
    if not sample.get('ok'):
        warnings.append('sample_failed')
    if sample.get('error') in ('timeout', 'no_data'):
        warnings.append('stalled')
    if sample.get('throughput_mbps') is not None and sample['throughput_mbps'] < 1.5:
        warnings.append('low_throughput')
    return warnings


def main():
    prof = ChannelProfile.objects.filter(name=PROFILE).first()
    if not prof:
        print('no %r profile' % PROFILE)
        return

    cids = list(ChannelProfileMembership.objects.filter(
        channel_profile=prof, enabled=True).values_list('channel_id', flat=True))
    qs = Channel.objects.filter(id__in=cids).select_related(
        'override', 'channel_group').prefetch_related('channelstream_set__stream__m3u_account')

    if SCOPE == 'pilot':
        wanted = {(num, grp) for num, grp in PILOT_CHANNELS}
        qs = [c for c in qs
              if (int(c.channel_number or 0), c.channel_group.name if c.channel_group else None) in wanted]
        scope_label = 'pilot'
    else:
        qs = [c for c in qs
              if c.channel_group and c.channel_group.name in CORE_GROUPS]
        scope_label = 'core'

    print('profile %r scope=%s channels=%d probe=%s' % (PROFILE, scope_label, len(qs), PROBE))

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'profile': PROFILE,
        'scope': scope_label,
        'probe': PROBE,
        'channels': [],
    }

    for ch in qs:
        links = sorted(ch.channelstream_set.all(), key=lambda x: x.order)
        if not links:
            continue
        primary_link = links[0]
        entry = {
            'channel_id': ch.id,
            'channel_number': int(ch.channel_number or 0),
            'group': ch.channel_group.name if ch.channel_group else None,
            'effective_name': effective_name(ch),
            'event_slot': is_event_slot(ch, primary_link.stream.name),
            'current_primary_stream_id': primary_link.stream.id,
            'current_primary_name': primary_link.stream.name,
            'sources': [],
        }
        sports = 'sports' in str(entry['group']).lower()
        for link in links:
            s = link.stream
            provider = s.m3u_account.name if s.m3u_account else None
            existing_stats = s.stream_stats or {}
            existing_fresh = bool(s.stream_stats_updated_at)
            probe_result = probe_stream(s) if PROBE and provider != 'ZQAVO' else None
            meta = probe_result['metadata'] if probe_result else {}
            sample = probe_result['sample'] if probe_result else {}
            measured = bool(meta) or bool(sample)
            tier = quality_tier(meta, sample, sports) if measured else None
            warnings = health_warnings(meta, sample) if measured else []
            entry['sources'].append({
                'stream_id': s.id,
                'order': link.order,
                'name': s.name,
                'provider': provider,
                'is_stale': s.is_stale,
                'existing_stats': existing_stats,
                'existing_stats_fresh': existing_fresh,
                'measured': measured,
                'tier': tier,
                'metadata': meta,
                'sample': sample,
                'warnings': warnings,
            })
        report['channels'].append(entry)
        if PROBE:
            time.sleep(PAUSE_BETWEEN)

    tiers = Counter()
    recommendations = 0
    for ch in report['channels']:
        for src in ch['sources']:
            if src['tier']:
                tiers[src['tier']] += 1
        candidates = [s for s in ch['sources'][1:]
                      if s['tier'] and not s['warnings'] and not ch['event_slot']]
        if candidates:
            current = ch['sources'][0]
            best = max(candidates,
                       key=lambda s: {'S': 4, 'A': 3, 'B': 2, 'C': 1, 'D': 0}.get(s['tier'], -1))
            current_score = {'S': 4, 'A': 3, 'B': 2, 'C': 1, 'D': 0}.get(
                current.get('tier') or 'unknown', -1)
            if best['tier'] > current.get('tier') or current_score < 0:
                recommendations += 1

    print('tiers:', dict(tiers))
    print('possible promotions:', recommendations)

    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, 'latest.json'), 'w') as fh:
        json.dump(report, fh, indent=2)
    print('report written to %s/latest.json' % REPORT_DIR)


main()



