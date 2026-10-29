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


def probe_stream_ffmpeg(url):
    """Single-connection probe: remux a short sample and parse stream metadata.

    Using one ffmpeg pass avoids the provider's immediate-reconnect refusal: a
    separate ffprobe plus a separate sample often looks like a second connection
    and gets 503'd, which would otherwise be misread as a stream health problem.
    """
    cmd = [
        'ffmpeg', '-hide_banner', '-nostdin',
        '-i', url,
        '-t', str(SAMPLE_SECONDS),
        '-map', '0:v:0', '-map', '0:a:0?',
        '-c', 'copy', '-f', 'null', '-',
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=SAMPLE_SECONDS + 15)
        stderr = proc.stderr or ''
        if proc.returncode != 0 and 'time=' not in stderr:
            return {'ok': False, 'error': 'ffmpeg_failed', 'stderr_tail': stderr[-500:]}

        video = None
        audio = None
        for line in stderr.splitlines():
            if video is None and ': Video:' in line:
                video = line
            if audio is None and ': Audio:' in line:
                audio = line

        def parse_video(line):
            # Stream #0:0[0x1ff]: Video: h264 (High) ..., yuv420p(...), 1280x720 ..., 59.94 fps, ...
            codec = re.search(r'Video:\s*([A-Za-z0-9_]+)', line)
            dims = re.search(r'(\d{2,5})x(\d{2,5})', line)
            fps = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*fps', line)
            pix = re.search(r',\s*([a-zA-Z0-9_]+)\s*(?:\(|,)', line)
            return {
                'video_codec': codec.group(1) if codec else None,
                'width': int(dims.group(1)) if dims else None,
                'height': int(dims.group(2)) if dims else None,
                'fps': float(fps.group(1)) if fps else None,
                'pixel_format': pix.group(1) if pix else None,
            }

        def parse_audio(line):
            codec = re.search(r'Audio:\s*([A-Za-z0-9_]+)', line)
            rate = re.search(r'(\d{3,6})\s*Hz', line)
            channels = re.search(r'(\d+)\s*channels', line)
            if channels:
                channels = int(channels.group(1))
            elif re.search(r'\bstereo\b', line, re.I):
                channels = 2
            elif re.search(r'\bmono\b', line, re.I):
                channels = 1
            else:
                channels = None
            return {
                'audio_codec': codec.group(1) if codec else None,
                'audio_sample_rate': int(rate.group(1)) if rate else None,
                'audio_channels': channels,
            }

        meta = {'ok': video is not None}
        if video:
            meta.update(parse_video(video))
        if audio:
            meta.update(parse_audio(audio))

        bitrate = None
        elapsed = None
        total_kib = None
        for line in reversed(stderr.splitlines()):
            if total_kib is None and 'video:' in line and 'audio:' in line:
                sizes = re.findall(r'(\d+(?:\.\d+)?)\s*(KiB|MiB)', line)
                total_kib = sum(
                    float(num) * (1024 if unit.lower() == 'mib' else 1)
                    for num, unit in sizes)
            if bitrate is None:
                m = re.search(r'bitrate=\s*([0-9.]+)\s*kbits/s', line)
                if m:
                    bitrate = float(m.group(1))
            if elapsed is None:
                m = re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)', line)
                if m:
                    elapsed = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            if elapsed is not None and (bitrate is not None or total_kib is not None):
                break

        if bitrate is None and total_kib is not None and elapsed:
            bitrate = (total_kib * 1024 * 8) / elapsed / 1000

        if bitrate is not None:
            sample = {
                'ok': True,
                'status': 200,
                'bytes': int(total_kib * 1024) if total_kib is not None else None,
                'elapsed': round(elapsed, 2) if elapsed else SAMPLE_SECONDS,
                'throughput_mbps': round(bitrate / 1000, 2),
                'error': None,
            }
        else:
            sample = {'ok': False, 'status': None, 'bytes': None,
                      'elapsed': elapsed, 'throughput_mbps': None,
                      'error': 'no_bitrate'}

        return {'metadata': meta, 'sample': sample}
    except Exception:
        return {'ok': False, 'error': 'ffmpeg_exception'}


def probe_stream(stream):
    """Probe one stream through Dispatcharr's stream-specific proxy path."""
    if not stream.stream_hash:
        return {'ok': False, 'error': 'no_stream_hash'}
    # Never leak the URL into logs; it is only used in-process.
    url = f"http://localhost:9191/proxy/ts/stream/{stream.stream_hash}"
    result = probe_stream_ffmpeg(url)
    return {'metadata': result.get('metadata', {}), 'sample': result.get('sample', {})}


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



