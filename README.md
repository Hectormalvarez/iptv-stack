# iptv-stack

IPTV → Jellyfin media server.

| Service | Port | Purpose |
|---|---|---|
| Dispatcharr | http://localhost:9191 | M3U/EPG management, stream proxying, DVR |
| Jellyfin | http://localhost:8096 | Media server & clients |

Both share the `media-net` Docker network and an Intel Iris Xe GPU (VAAPI) at `/dev/dri`.

## Provider (strong8k)

Xtream Codes portal: `http://cf.vovu.top` — credentials live in Dispatcharr's M3U account (UI: M3U & EPG Manager). Do **not** commit them here.

- The `get.php` M3U endpoint returns empty for plain curl; Dispatcharr imports via the XC API (`type=XC`), which works fine.
- The XMLTV EPG (`/xmltv.php`) contains 4,423 channels with IDs like `SkySportsNews.uk` — country-suffixed, and mostly **not** matching the XC stream `tvg-id`s. Bulk name matching is required (below).

## EPG pipeline (reworked 2026-09-26)

Three EPG sources feed Dispatcharr:

| Source | URL | Cadence | Purpose |
|---|---|---|---|
| `STRONG8K` | provider `/xmltv.php` | **6 h** | Mexico + international + the little US data it really carries |
| `EPGSHARE-US-LOCALS` | `https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz` | 12 h | **US local stations**, call-sign IDs (`KXAN-DT.us_locals1`) |
| `EPGSHARE-US2` | `https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz` | 12 h | US national cable (`CNN.HD.us2`, `NFL.Network.HD.us2`) |

**Why the two extra sources:** the provider's XMLTV carries only **~379 US channel IDs out of 4,423** (the rest
are India/France/Spain/UK/Poland/Mexico…). The bulk fuzzy auto-match below therefore bound US channels to
whatever looked closest — `US: NBC 36 (KXAN) AUSTIN` → `KTRK.us` (ABC Houston), `CBS 42 (KEYE)` → `KPIX.us`
(CBS San Francisco), `VIP: NFL NETWORK` → `infosportplus.fr`, `MX: NICK JR` → `NickJr.hu`. **673 of 865
call-sign channels were mis-bound**, which is what made the guide look "wrong" even after the clock was fixed.

**Matching rules** — `scripts/remap-epg.py` (dry-run by default; pipe a copy with `APPLY = True` to write):

```bash
docker exec -i dispatcharr python manage.py shell < scripts/remap-epg.py
```

1. Call-sign in the channel name (`(KXAN)`) → `KXAN-DT.us_locals1` — exact match only, and only for US-ish
   channels so a stray `(ABCD)` in a foreign name cannot misfire.
2. Otherwise normalise the name and prefer the channel's own country (derived from its provider group or name
   prefix: `MX| …` → `.mx`, `US| …` → `.us`, `VIP:` / `MEXICO` → `.mx`), then the US feeds for US content.
   `ACCEPT` encodes which country tags are legitimate per region.
3. **Never** fall back to a third country. If nothing correct exists and the current binding is from the wrong
   country, the binding is **blanked** — a French schedule on a Mexican channel is worse than no schedule.
4. Channels with no region clue are never judged and never touched.

Scope is **all visible channels** (`hidden_from_output=False` = 3,590), i.e. everything Jellyfin imports and
the pool the Kodi profile is drawn from — not just the curated profile.

### Writes go to `ChannelOverride`, not `Channel` (this is what makes it stick)

The first version wrote `channel.epg_data` and kept partially reverting. From the `ChannelOverride`
model docstring:

> *"Sync writes only to `Channel.*` fields and never to this table, so provider metadata keeps flowing
> while user customizations persist across refreshes."*

Every M3U refresh re-resolves each channel (see `_resolve_epg_for_stream` in `m3u/tasks.py`) and overwrites
`Channel.epg_data`. The output path resolves EPG as:

```python
effective_epg_data = Coalesce(override__epg_data, epg_data)
```

So the script writes the override, which wins and survives syncs. **Blanking also needs the override** — an
override of `NULL` would fall straight back to the wrong provider binding, so wrong-region channels are
pointed at a dummy EPG entry (source `NO GUIDE`, `source_type='dummy'`, zero programmes). Dispatcharr then
generates its own placeholder programmes for those channels, which is honest and durable.

Applied 2026-09-26 (v2): **865 channels remapped, 981 wrong-region bindings blanked.**

| Effective source (visible channels) | Channels |
|---|---|
| `STRONG8K` | 1,674 |
| `NO GUIDE` (blanked) | 981 |
| `EPGSHARE-US-LOCALS` | 821 |
| `EPGSHARE-US2` | 114 |

The blanked 981 are dominated by groups that are systematically wrong because no suitable feed exists:
`Mexico VIP` (599 wrong of 650), `US\| PRIME` (73), `AR\| BOX OFFICE 4K` (67/67), `US\| ROKU` (45),
`US\| TUBI` (7/7) — i.e. Mexican, Arabic and FAST-service channels that the fuzzy matcher had bound to
French/Portuguese/Turkish/Hungarian guides.

### The ordering trap: bind first, *then* refresh

Dispatcharr deliberately only stores programmes for EPG entries **already mapped to a channel**
(`parse_programs_for_source`: *"Skips programmes for unmapped channels entirely during parsing"*). The source
log makes the scale of this obvious:

```
EPGSHARE-US-LOCALS: Parsed 553 programs for 5 channels
                    (skipped 551,362 programs for 4451 unmapped channels)
```

So a fresh source with 4,456 entries can look almost empty until channels are mapped to it. **Bind, then
refresh** — after the remap the refresh harvests those 551k programmes for the newly-mapped stations:

```bash
docker exec dispatcharr python manage.py shell -c "
from apps.epg.tasks import refresh_epg_data
refresh_epg_data.delay(3, force=True)"     # id 3 = EPGSHARE-US-LOCALS
```

Progress appears in `docker logs dispatcharr` as `Refreshing program data for tvg_id: KABC-DT.us_locals1`,
one mapped entry at a time. Budget ~10–30 min for ~800 stations.

Gotchas worth knowing:

- Refresh interval per source: M3U & EPG Manager → EPG row → edit, or set `EPGSource.refresh_interval`
  (hours) via `manage.py shell` and `save()` (saving is what reschedules the celery-beat task).
- `pvr.iptvsimple` reads the guide at Kodi start. To force a full rebuild after big EPG changes: stop Kodi,
  delete `/storage/.kodi/userdata/Database/Epg16.db`, start Kodi.
- Bulk matching still lives at **Channels → ⋮ → Auto-Match EPG**, but treat its output as a draft: verify
  call-sign channels afterwards with `scripts/remap-epg.py`.
- The provider stamps programmes with a `+0200` offset; Dispatcharr converts correctly (verified against
  CNN's real schedule) — do not add a timezone workaround.

## Jellyfin Live TV hookup

Use the **container names** over `media-net` (traffic stays internal). Jellyfin's Live TV is configured as:

- **Tuner: "M3U Tuner"** → `http://dispatcharr:9191/get.php?username=<dispatcharr-user>&password=<xc-token>&type=m3u_plus&output=ts`
- **Guide: XMLTV provider** → `http://dispatcharr:9191/xmltv.php?username=<dispatcharr-user>&password=<xc-token>`

The `xc-token` is the per-user XC API password in Dispatcharr (Users → user → set/generate "xc_password"; it is separate from the login password). The plain `/hdhr` endpoint returns 401 without HDHR device auth — do not use it.

Then Jellyfin → Dashboard → Live TV → "Refresh Guide Data" (the 84 MB XMLTV with ~14k channels takes a few minutes).

## Hardware transcoding (VAAPI, Intel Iris Xe)

Both containers have `/dev/dri` mounted. In Dispatcharr create a Stream Profile:

- Command: `ffmpeg`
- Parameters: `-user_agent {userAgent} -hwaccel vaapi -hwaccel_output_format vaapi -hwaccel_device /dev/dri/renderD128 -i {streamUrl} -c:a aac -c:v h264_vaapi -f mpegts pipe:1`

In Jellyfin: Dashboard → Playback → Transcoding → enable VAAPI, device `/dev/dri/renderD128`.

Notes (2026-09-21):

- The agent must be told the provider's UA — Dispatcharr injects `{userAgent}` from the M3U account.
- The container's ffmpeg lists `vaapi`/`qsv` and sees `/dev/dri/renderD128`.
- A client-requested `output_profile` only takes effect when the channel is **not** already streaming on
  another profile — Dispatcharr multiplexes extra clients onto the existing branch. Don't judge a
  profile by requesting it for a channel that's already playing.
- For the LAN Kodi box, **no transcoding is wanted**: the Latitude hardware-decodes H.264/HEVC itself,
  so the default `-c copy` remux profile (id 1) is what's actually used.

## Channel cleanup (2026-09-21)

14,936 → **3,590 visible channels, all with EPG**. Junk is *hidden* (`hidden_from_output=True`), never deleted — auto-sync keeps them updated and never re-creates them, and they can be un-hidden from the Channels page (filter "Hidden Only"). Hidden so far:

1. Separator-name channels (`#####...#####`) — 147
2. Channels with no streams — 1,118
3. Dated one-shot PPV/event channels (name contains `(YYYY-MM-DD ...`) — 1,750
4. All remaining channels without EPG — 8,346

SQL equivalent (inside the container):

```python
from apps.channels.models import Channel
Channel.objects.filter(name__regex=r'^#+').update(hidden_from_output=True)
Channel.objects.filter(streams__isnull=True).update(hidden_from_output=True)
Channel.objects.filter(name__regex=r'\(20[0-9]{2}-[0-9]{2}-[0-9]{2}').update(hidden_from_output=True)
Channel.objects.filter(epg_data_id=None).update(hidden_from_output=True)
```

After cleanup: Jellyfin → Live TV → "Refresh Guide Data" (or Scheduled Tasks → Refresh Guide) so the tuner re-imports the shrunken playlist.



- Dispatcharr DVR output → `/data/recordings_host` → host `/mnt/storage/recordings` → Jellyfin sees it at `/recordings`.

### Channels without a guide are swept to the end (2026-09-26)

`scripts/build-kodi-profile.py` moves any curated channel with **no upcoming programme data** into a
trailing group `No Guide` (numbers `9001+`), so every group above it in the guide is fully populated.
The test is `ProgramData.objects.filter(end_time__gte=now)` — that matches what the client renders
(stale backwards-looking programmes never appear).

Result: 266 of the 1,668 channels moved out of `Mexico VIP` (83), `Sports: International` (77),
`Sports: Networks` (75) and friends. The channels stay watchable at the end of the lineup; Jellyfin
still sees the full playlist. A handful of channels whose last programme expires minutes later can
land back in a normal group until the next run — re-run the script to tidy them.

Two things to know before re-running the script:

- **It is now idempotent**: provider-group matchers can only see the *original* provider groups, so on
  a second run the script *adopts* channels already sitting in Kodi groups (keeping their group and
  number). Without that, a re-run found only 207 channels and disabled 1,442 members — which actually
  happened during this session and had to be repaired.
- **Safety guard**: if the resolved set is less than 90% of the profile's current enabled members the
  script aborts instead of writing (`FORCE = True` overrides).

Sweep timing matters (learned the hard way):

- The sweep judges a channel by its **effective** EPG (`effective_epg_data_obj`), not `ch.epg_data_id`.
  When `remap-epg.py` writes a `ChannelOverride`, the raw `ch.epg_data_id` still points at the *old*
  wrong entry, so the original `epg_data_id` test read a stale binding for every remapped channel.
- The sweep is **one-way**: a channel moved to `No Guide` is not moved back later, because its original
  group is not recorded anywhere. So run it once the guide has settled — not while a large EPG harvest
  is still filling channels in. `SWEEP_NO_GUIDE = False` skips the sweep entirely.
- After the 2026-09-26 remap the sweep would have moved 910 channels, ~200 of which (the freshly
  remapped US stations) were about to receive programme data from the `EPGSHARE-US-LOCALS` harvest.
  Waiting for that harvest to drain first avoids stranding them.

Repair recipe if the profile is ever gutted: re-enable membership for channels whose
`channel_group.name` is one of the script's owned groups (see `KODI_GROUPS` in the script).

## Operations

```bash
docker compose config -q     # validate
docker compose up -d         # apply changes
docker compose logs -f dispatcharr
```

Dispatcharr admin account: `hadev` (password reset via `manage.py set_password` if lost).
Nightly Dispatcharr backups: `./dispatcharr/data/backups/` — copy these off-box.

### Health check (`scripts/verify-stack.sh`)

Read-only, never writes to Dispatcharr/Jellyfin/Kodi. Run it by hand, or read the daily log:

```bash
./scripts/verify-stack.sh                          # server checks
KODI_HOST=root@192.168.1.181 ./scripts/verify-stack.sh   # + client checks (needs SSH keys)
tail -40 /mnt/storage/backups/iptv-stack/verify.log      # cron output, 08:30 daily
```

It checks that all three containers are up, that the curated **Kodi profile still has ~1668 channels**
(a provider re-sync that renumbers or drops channels is otherwise silent), **EPG coverage excluding the
deliberately blank `No Guide` group** (must stay ≥95%), that all three EPG sources report `success`, that
`/mnt/storage` has room, and that a backup landed in the last 2 days. Exit code is non-zero when
something FAILs. The Kodi checks (display mode, log errors, segfault count) need key-based SSH; password
auth is deliberately not baked into the script.

### Timezones (fixed 2026-09-26)

Everything used to be UTC, which made the Kodi guide display every programme **5 hours late** in
Austin (CDT = UTC−5). Three layers, three fixes:

| Layer | Setting | Value |
|---|---|---|
| Kodi box (LibreELEC) | `/storage/.cache/timezone` → read by `tz-data.service` (`EnvironmentFile=-/storage/.cache/timezone`, default `TIMEZONE=UTC`, symlinks `/var/run/localtime`) | `TIMEZONE=America/Chicago` |
| `dispatcharr`, `jellyfin`, `watchstate` | `TZ` env in `docker-compose.yml` | `America/Chicago` |
| host `usrv-01` | left on **UTC** deliberately — it also runs other production stacks | `Etc/UTC` |

Details that matter:

- LibreELEC has no `timedatectl`; the file above **is** the supported mechanism (it is what the
  LibreELEC settings addon writes). After editing: `systemctl restart tz-data.service` **and** restart
  Kodi — Kodi caches the timezone at startup.
- The RTC stays UTC (correct); `America/Chicago` handles DST automatically.
- Clock sync comes from ConnMan (`connmanctl clock` → `TimeUpdates = auto`), not
  `systemd-timesyncd` (which is disabled) or chrony. The `ntpd` binary exists but no daemon runs.
- The provider's XMLTV stamps programmes with a **`+0200`** offset. That is valid XMLTV and Dispatcharr
  converts it correctly — verified against CNN's real schedule (The Lead 20:00 UTC, Erin Burnett
  23:00 UTC, AC360 00:00 UTC). Do **not** add any offset workaround for this.
- Verify: `ssh root@192.168.1.181 date` should print CDT, and
  `readlink -f /var/run/localtime` → `/usr/share/zoneinfo/America/Chicago`.
- Host cron still runs backups at **04:15 UTC = 23:15 CDT**. To move them to local time, add
  `CRON_TZ=America/Chicago` at the top of the crontab rather than changing the host timezone.

## Kodi client (LibreELEC on Dell Latitude 5320)

**Architecture:** Jellyfin-first for VOD (`jellyfin-kodi` addon syncs Movies/TV/Recordings/watch-state), `pvr.iptvsimple` for Live TV pointed at a **curated Dispatcharr channel profile**. Kodi 21 Omega / LibreELEC 12.2.1.

### Curated lineup for the client (the "Kodi" channel profile)

The box does **not** get all 3,590 channels. Dispatcharr serves it a curated
**Channel Profile** whose playlist is defined in
`scripts/build-kodi-profile.py` (dry-run by default; `DRY_RUN=False` applies it):

| Range | Group | Contents |
|---|---|---|
| 101–106 | Austin Local | KXAN (NBC), FOX 7 (KTBC), KEYE (CBS), ABC stand-in (KTRK Houston — no KVUE feed on this provider), PBS, Spectrum News Austin |
| 201–239 | Entertainment | YouTube-TV-style bundle: USA, TNT, TBS, FX/FXX, AMC, BBC America, Comedy Central, Syfy, Bravo, TBS-family, HGTV, Food, Discovery, History, A&E, Lifetime, Hallmark, TruTV, ID, Nat Geo, Animal Planet, Travel, Freeform, Oxygen, WE tv, IFC, Sundance, BET, CMT, MTV Live, Cooking, Destination America, Magnolia, Reelz, MotorTrend, Outdoor |
| 301–319 | Sports | ESPN, ESPN 2/News/USA, CBS Sports, FOX Sports 1/2, beIN, Spectrum Sports 1, YES, SNY, MSG, Bally Ohio, Premier League, Willow Cricket, UFC, WWE, Fight Sports, Sky Sports F1 |
| 321–367 | Sports: NFL / NBA / MLB / NHL / College / Golf & Tennis | league networks plus the provider's live game slots, renamed from `NBA 06 :`/`NFL  \| 02 -` to `NBA Live 1`/`NFL Live 2` etc. **These are event feeds: live during games, dark (and erroring) otherwise** — verified streaming during an active window and dead 15 min later. Reliable league networks come first, slots sit at the end of each group. Optional hardening: attach the duplicate slot streams to the same channel in Dispatcharr so failover has a second source. |
| 401–409 | News | CNN, Fox News, MSNBC, CNBC, Bloomberg, Newsmax, HLN, Weather Channel, BBC World |
| 501–507 | Kids | Nickelodeon, Nick Jr, Disney, Disney Jr, Cartoon Network, Boomerang, PBS Kids |
| 601–604 | Movies | Starz, Showtime, MoviePlex, TCM |
| 701–704 | Spanish | Univision (Miami), Telemundo 51, Fox Deportes, TUDN Zona |
| 801–849 | Mexico / Mexico: VIX | `MX:`-prefixed Mexican channels plus the provider's `MX| VIX` group |
| 1201–1933 | **Mexico VIP** | whole `MX| MEXICO ⱽᴵᴾ` group (733 channels) |
| 2001–2119 | **Sports: Networks** | `US| SPORT` + `BALLY` groups — RSNs (YES, SNY, MSG, Bally, Altitude, Monumental, AT&T SportsNet…), CBS Sports, etc. |
| 2201+ / 2251+ / 2301+ / 2351+ | Sports: NBA / NFL / MLB / NHL | league networks + event slots |
| 2401+ / 2451+ / 2501+ / 2551+ / 2601+ | Sports: College / Soccer / Golf & Tennis / Motorsport / Combat | |
| 2701–3189 | **Sports: International** | whole `8K\| SPORT ON AIR` group (489) — international sports feeds (M+, DAZN, Prima Sport, Sky…) |
| 3301–3388 | **Sports: Events** | `PARAMOUNT+ PPV`, `ESPN+ PPV`, `PPV EVENT`, `B/R MAX` event slots |

Expansion (2026-09-21, on request): **1,668 channels / 32,133 EPG entries** — the whole visible
sports estate plus Mexican channels. Deliberately excluded: the other Latin groups
(`LA|`, `AR|` — note `AR|` is Arabic, not Argentina — and `RD|`) because only Mexican channels were
wanted, and the ~2,780 hidden sports event feeds that have **no EPG at all** (they would appear as
blank guide rows; they can be added later by un-hiding them in Dispatcharr). Verified on the box:
1,668 channels in 22 groups, a Mexican channel (`MX: AMC`) played normally, 0 errors, no new
segfaults.

To extend: add entries to `SPORTS_IMPORTS` / `MX_IMPORTS` in `scripts/build-kodi-profile.py`
(matcher list, Kodi group, first channel number) — each import block must not overlap another
group's range, so give it its own slack.

Result on the box: the lineup started at **123 channels / ~3,000 EPG entries** (vs 3,590 / 84,000
unfiltered) and now sits at **1,668 channels / 32,133 EPG entries** after the sports + Mexico
expansion. Number entry zaps directly ("1 0 1" → KXAN).

Client endpoints (these are what `pvr.iptvsimple` uses):

```
http://usrv-01:9191/output/m3u/Kodi
http://usrv-01:9191/output/epg/Kodi
```

Jellyfin keeps the full `/output/m3u` + `/output/epg` (no profile) — the two
clients are independent.

**Changing the lineup:** edit the `LINEUP` list (number, group, aliases, prefer)
or `EVENTS` (provider name → clean name) in `scripts/build-kodi-profile.py`, run
the dry run to review the picks, then set `DRY_RUN=False` and re-run. The script
is idempotent, so re-running is safe. Partial channels are fine — the resolver
scores candidates (US feeds preferred, `PPV`/`24-7`/`test` excluded).

**Watch out:** renaming/numbering here is global (Jellyfin's guide sees the same
names/numbers). Also, `channel_number` is only unique *per group* in Dispatcharr,
so always select the curated set **by group membership**, not by number range —
provider channels in other groups already use numbers 101–704.

### What's installed

| Component | Source | Notes |
|---|---|---|
| `jellyfin-kodi` 2.2.0 | repo.jellyfin.org (manual zip) | deps vendored: requests+urllib3 1.26.16, certifi, idna, charset_normalizer (PyPI), websocket, typing_extensions, unidecode, simplecache, simpleeval |
| `pvr.iptvsimple` | preinstalled | instance 1 → **curated profile** `http://usrv-01:9191/output/m3u/Kodi` + `/output/epg/Kodi`, refresh 51 min (never `direct=true` — see below) |
| `skin.estuary.modv2` 21.4 | b-jesch GitHub (Omega branch) | needs script.skinshortcuts 2.0.3 + pvr.artwork + image.resource.select |
| Wi-Fi power-save | off (runtime + systemd unit `wifi-powersave-off.service` in `/storage/.config/system.d/`) | fixes periodic drop-offs |
| `pvr.iptvsimple` config | userdata | `catchupEnabled=false`, `allChannelsCatchupMode=0`, `timeshiftEnabled=false` — deliberately off, see below. Backups: `/storage/backups/instance-settings-1.xml.pre-*` |
| `guisettings.xml` tweaks | userdata | `pvrmanager.usebackendchannelnumbers=true`, `pvrplayback.confirmchannelswitch=false` (instant zap) |

### Zapping / concurrent streams (root-caused and fixed 2026-09-21)

Symptom: channel switches often failed or took ~40 s, with Dispatcharr logging
`503 {"error": "All active M3U profiles have reached maximum connection limits"}`.

Root cause: **the M3U account profile capped Dispatcharr at one upstream
connection** (`M3UAccountProfile id=2 "STRONG8K Default".max_streams = 1`). A
channel switch then races — Kodi requests the new channel while the old stream
still holds the only slot — and Dispatcharr refuses until Kodi gives up and
releases the old stream.

The provider itself is **not** the constraint: raising the cap to 2 and pulling
two different channels at the same time streamed both (`150000` bytes each,
`Successfully obtained stream ... after 1 attempts`). So `max_streams` is now **2**:

- Zaps get the stream on the first attempt (~8 s including Dispatcharr's ~5 s
  buffer fill) instead of ~38 s of retry loops.
- Kodi and Jellyfin can watch different channels at the same time.

Supporting tuning in `CoreSettings` → `proxy_settings` (UI: System → proxy):

| Setting | Was | Now | Why |
|---|---|---|---|
| `channel_shutdown_delay` | 0 | 3 | at 0 the channel is torn down the instant Kodi drops a connection, so a retry hits `Channel ... unavailable. Teardown or pending shutdown` and Kodi gives up |
| `channel_client_wait_period` | 5 | 10 | keeps a ready channel alive while the client re-attaches |

**Do not** raise `retry_timeout` in `apps/proxy/live_proxy/views.py` (upstream
value: `3`, with `retry_interval = 0.1`). A longer budget was tested and made
things *worse* (zaps went from ~10 s to ~38 s): Kodi blocks on Dispatcharr's HTTP
response, so while Dispatcharr waits, Kodi never releases the old stream — the
fast-fail path is what lets Kodi drop the old channel and retry cleanly.

Caveat: the subscription is advertised as a single connection. Two concurrent
streams work in practice, but if the provider tightens enforcement, set
`max_streams` back to 1 (Channels → M3U account → profile) and expect slower
switching; a 2-connection plan would remove the trade-off entirely.

### Stream path: always proxy through Dispatcharr (fixed 2026-09-21)

The client previously fetched streams **direct** (`direct=true`), i.e. Kodi connected straight to
`cf.vovu.top` with Kodi's own User-Agent. That caused random 502s and crashes because of two
provider-side facts, both verified:

1. The STRONG8K account allows **one simultaneous connection** (`M3UAccount.max_streams = 1`).
   Kodi's playback plus its extra probe requests (`CCurlFile::Exists`) plus Jellyfin's tuner all
   competed for that single slot.
2. The provider pins the **User-Agent** (`TiviMate/5.1.6 (Android 12)`). Requests with any other
   UA return an empty 502 response.

Pointing the client at `/output/m3u` (proxied, **no** `direct=true`) fixes both: Dispatcharr holds
exactly one upstream connection with the correct UA, multiplexes all clients onto it, buffers ~5 s
server-side, and serves the stream over the LAN. Verified: the box pulled
`http://usrv-01:9191/proxy/ts/stream/<uuid>`, buffered (`buffer ready (86/4 chunks) -> active`),
and played with no new `VideoPlayer` segfaults and zero log errors.

### Channels with a single stream get a backup (fixed 2026-09-27)

A channel with only one stream has **nothing to fail over to**, and this provider drops the connection
roughly hourly. That is what "channel 219 won't play" turned out to be — not an EPG or client problem:

```
Stream ends prematurely at 1187824068 ... Error during demuxing: Input/output error
Stream was stable for 2532.9 seconds                  <- played fine for 42 min
Reconnecting in 0.25 seconds... (attempt 1/3)         -> Server returned 4XX Client Error
Connection attempt 2/3 ...                            -> Server returned 4XX Client Error
Maximum retry attempts (3) reached
Trying to find alternative stream for channel ... current stream ID: 110
Found 0 connect subscription(s) for event 'channel_error'   <- nothing to switch to, channel dies
```

The upstream itself was healthy the whole time (verified directly: HTTP 200, 18 MB, ~10 Mbps). The
provider simply refuses the immediate reconnect while the old session is still closing, and with
`MAX_RETRIES = 3` / `RETRY_WAIT_INTERVAL = 0.5` the proxy only retries for ~1.75 s before giving up.

`scripts/add-backup-streams.py` attaches a second source (a `ChannelStream` with `order=1`) so the
built-in `trying next stream` failover has somewhere to go. It is deliberately strict — two streams
must normalise to the same core name, so a *different* network never gets attached:

| Primary | Backup | Core |
|---|---|---|
| `US: HALLMARK HD` | `TV: HALLMARK CHANNEL` | `hallmark` |
| `US: SHOWTIME HD` | `PRIME: SHOWTIME` | `showtime` |
| `US: WWE HD` | `US: WWE NETWORK` | `wwe` |
| `US: TENNIS HD` | `US: TENNIS CHANNEL` | `tennis` |

…while near-misses are correctly rejected: `US: HALLMARK M & M HD` → `hallmarkmm`,
`US: HALLMARK DRAMA HD` → `hallmarkdrama`, `AT&T: HALLMARK FAMILY` → `hallmarkfamily`.

```bash
docker exec -i dispatcharr python manage.py shell < scripts/add-backup-streams.py            # dry run
docker exec -e BACKUP_APPLY=1 -i dispatcharr python manage.py shell < scripts/add-backup-streams.py
```

Applied 2026-09-27: **475 of the 1,668 profile channels gained a backup**; the other 1,193 are the only
source the provider offers for that channel. Serving rate for #219 measured 1.06 MB/s (~8.5 Mbps)
afterwards, appropriate for its 1080p60 H.264 feed.

**Retry tuning was deliberately *not* applied.** `MAX_RETRIES` and `RETRY_WAIT_INTERVAL` are plain class
attributes in `apps/proxy/config.py` — inside the container, so any edit is lost on the next image
update or `--force-recreate`, and there is no env/DB override for them. A bind-mount would fight
upstream changes. The backup-stream route is persistent and uses Dispatcharr's own failover instead.

### Why catchup and timeshift are OFF

Both were enabled during setup and both are **crash sources here**:

- **Catchup is impossible on this subscription.** The XC API reports `tv_archive=1` on **0 of
  15,830** streams, and Dispatcharr's derived `Channel.is_catchup` is 0 channels. With catchup
  enabled Kodi still builds timeshift URLs, gets 502s and freezes —
  [pvr.iptvsimple#499 *"Using Catchup on unsupported channels causes kodi to crash/hang"*](https://github.com/kodi-pvr/pvr.iptvsimple/issues/499).
- **Timeshift freezes Kodi Omega** —
  [pvr.iptvsimple#760 *"Kodi (Omega) freeze and/or crash when using Timeshift"*](https://github.com/kodi-pvr/pvr.iptvsimple/issues/760), still open.
  The crash backtrace we captured matched this path: `VideoPlayer` segfault with frames in
  `inputstream.ffmpegdirect → CURL::Parse` and `pvr.iptvsimple.so.21.11.0`.

The provider's *Xi* archive is re-checkable any time — if a future subscription advertises
archives, re-enable catchup (`catchupEnabled=true`, `allChannelsCatchupMode=4`) since the XC
catchup URL pattern then works.

Time-shifted viewing instead comes from **Dispatcharr's DVR** (schedule recordings server-side;
they appear in Jellyfin/Kodi through the jellyfin-kodi addon).

### Startup, buffering, sync and backups (2026-09-21)

**Startup — boots into the TV guide.** `lookandfeel.startupwindow = 10702` (TV Guide;
window IDs from Kodi's `WindowIDs.h`: TV Channels 10700, TV Recordings 10701, **TV Guide 10702**,
Timers 10703, Search 10704, Home 10000). `lookandfeel.startupaction = 0` (None) — set it to
*Play TV* in Settings → Interface → Startup if you'd rather it starts playing immediately.
Verified: after a Kodi restart, `XBMC.GetInfoLabels(["System.CurrentWindow"])` → `TV guide`.

**Buffering — Kodi was not caching HTTP streams at all.** Kodi's default
`filecache.buffermode = 4` is `CACHE_BUFFER_MODE_NETWORK`, and the decision in
`xbmc/filesystem/File.cpp` is:

```cpp
if ((mode == CACHE_BUFFER_MODE_INTERNET      && IsInternetStream(path, true)) ||
    (mode == CACHE_BUFFER_MODE_TRUE_INTERNET && IsInternetStream(path, false)) ||
    (mode == CACHE_BUFFER_MODE_NETWORK       && IsNetworkFilesystem(path)) ||   // SMB/NFS only!
    (mode == CACHE_BUFFER_MODE_ALL           && (IsNetworkFilesystem(path) || IsHD(path))))
  m_flags |= READ_CACHED;
```

`IsNetworkFilesystem()` is true only for streamed filesystems/SMB/NFS, so **plain `http://` IPTV
streams were never cached** with the default. The enum (from `filesystem/IFileTypes.h`) is
deliberately non-sequential, which is why the GUI order is misleading:

| GUI label | Value |
|---|---|
| Buffer all internet filesystems (FTP, WebDAV…) | 0 `INTERNET` |
| Buffer all filesystems (incl. local) | 1 `ALL` |
| **Only buffer true internet streams (HTTP, HTTPS)** | **2 `TRUE_INTERNET`** |
| No buffer | 3 `NONE` |
| Buffer all network filesystems (SMB, NFS) | 4 `NETWORK` ← Kodi default |

Applied via JSON-RPC `Settings.SetSettingValue`:

| Setting | Was | Now |
|---|---|---|
| `filecache.buffermode` | 4 (network filesystems — http uncached) | **2** (true internet → http/https cached) |
| `filecache.memorysize` | 20 MB | **64 MB** |
| `filecache.readfactor` | 400 (fixed 4x) | **0 = Adaptive** (aggressive while empty, ~1.5x when full) |
| `filecache.chunksize` | 131072 (128 KB) | unchanged (already the sensible default) |

Playback start is unchanged after this (measured 5 s from cold), zero new errors.

**Jellyfin → Kodi sync.** Installed **Kodi Sync Queue** on the server, which Jellyfin's docs
recommend with library mode so Kodi gets library changes without waiting for a periodic re-sync.
Use the version whose ABI matches the server — on Jellyfin 10.11.11 that is **15.0.0.0**; the
catalog's 7.0.0.0 (ABI 10.8) installs but reports `NotSupported` and does nothing:

```bash
TOKEN=$(curl -s -X POST http://localhost:8096/Users/AuthenticateByName \
  -H 'Content-Type: application/json' \
  -H 'Authorization: MediaBrowser Client="cli", Device="cli", DeviceId="cli", Version="1.0"' \
  -d '{"Username":"root","Pw":"<jellyfin-root-password>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessToken"])')
curl -s -X POST 'http://localhost:8096/Packages/Installed/Kodi%20Sync%20Queue?version=15.0.0.0' \
  -H "Authorization: MediaBrowser Token=\"$TOKEN\""      # then restart Jellyfin
```

Verify with `GET /Plugins` → `"status": "Active"`, and remove a stale
`/config/plugins/Kodi Sync Queue_<oldversion>` folder if one is left behind.

**Kodi config backups (box side).** Daily systemd timer on the box:
- script `/storage/.config/kodi-config-backup.sh`
- units `/storage/.config/system.d/kodi-config-backup.{service,timer}` (`OnCalendar=daily`, `Persistent=true`)
- output `/storage/backups/kodi/kodi-config-<YYYYmmdd-HHMM>.tar.gz`, last 7 kept
- contains `userdata/` (settings, databases, `addon_data/`, keymaps) + `addons/`, excluding
  `Thumbnails`, `Textures*`, `temp` and addon `resources`

  Restore: extract into `/storage/.kodi/` with Kodi stopped.

**PVR artwork.** `script.module.pvr.artwork` is installed and powers guide/OSD/NextUp art. Channel
logos already come from Dispatcharr (`tvg-logo` → Kodi channel icons). Poster/fanart/metadata
enrichment additionally needs a **TMDB API key** (and optionally fanart.tv) entered in the module's
settings — not configured yet.

### Skin trial: Arctic Fuse 3 installed alongside Mod V2 (2026-09-21)

`skin.arctic.fuse.3` 3.3.1 (jurialmunkey — the skin family most "customised Kodi boxes" run) is
**installed but disabled**, so Mod V2 stays active until you switch at the TV. It has its own addon
ID, so both coexist and every Mod V2 setting is untouched; falling back is just picking Mod V2 again.

Installed into `/storage/.kodi/addons/`:

| Addon | Version | Source |
|---|---|---|
| `repository.jurialmunkey` | 3.4 | `jurialmunkey.github.io/repository.jurialmunkey/repository.jurialmunkey-3.4.zip` |
| `skin.arctic.fuse.3` | 3.3.1 | that repo → `omega/zips/skin.arctic.fuse.3/…-3.3.1.zip` |
| `script.skinvariables` | 2.2.4 | repo |
| `script.texturemaker` | 0.2.11 | repo |
| `plugin.video.themoviedb.helper` | 6.17.3 | repo (widget/metadata engine) |
| `script.module.jurialmunkey` | 0.2.35 | repo |
| `script.module.infotagger` | 0.0.9 | repo |
| `resource.font.robotocjksc` | 0.0.3 | repo — **its zip ships the folder misspelled** as `resource.font.robotcjksc`, renamed to match the declared ID or the skin's dependency is unmet |
| `script.module.addon.signals` | 0.0.6+matrix.1 | `mirrors.kodi.tv/addons/omega/` |
| `script.module.qrcode` | 6.1.0+matrix.3 | Kodi repo |
| `resource.images.weathericons.white` | 0.0.6 | Kodi repo |
| `resource.images.studios.coloured` | 0.0.24 | Kodi repo |

`script.skinvariables`, `script.texturemaker` and `plugin.video.themoviedb.helper` were enabled via
JSON-RPC (`Addons.SetAddonEnabled`). The skin was deliberately **not** enabled — switching skins
headlessly is what left Mod V2 half-configured earlier, so that step belongs at the TV. Verified:
`Addons.GetAddonDetails skin.arctic.fuse.3` → `broken: false` (all dependencies satisfied),
active skin still `skin.estuary.modv2`, 0 log errors, no new segfaults.

**To try it:** Settings → Interface → Skin → *Arctic Fuse 3*. First load runs its hub/shortcut
setup and regenerates artwork, so it is slow once. Use ←/→ on the top bar for its hubs — the
prebuilt **Live TV hub** is the natural home for the PVR side.
**To revert:** Settings → Interface → Skin → *Estuary Mod V2*, or
`Settings.SetSettingValue {"setting":"lookandfeel.skin","value":"skin.estuary.modv2"}`.

AF3 is alpha; extra ratings need a free OMDb/MDbList key in TMDb Helper settings. It matters long
term because **Estuary Mod V2 cannot run on Kodi 22 (Piers)** — it requires Skinshortcuts 2.x, which
Piers replaces — while AF3 is maintained for both.

### HDMI-CEC (investigated 2026-09-21 — hardware missing, software already complete)

**Verdict: this box cannot do CEC as-is. It needs the Pulse-Eight USB-CEC Adapter ($48.58, in
stock, SKU P8-USBCECv1). There is nothing to install — the whole software stack is present.**

Verified on the box:
- `cec-client -l` → **`Found devices: NONE`**; no `/dev/cec*`, no `/sys/class/cec`, no CEC module.
- libCEC **7.1.1** installed (`/usr/lib/libcec.so.7.1.1`) with `cec-client`, `cec-ctl`,
  `cec-compliance`, `cec-follower`, plus `/sys/module/cec` (kernel framework) — and `kodi.bin` is
  built with libCEC (89 CEC symbols).
- libCEC features compiled in: **`P8_USB, DRM, P8_detect`** → the Pulse-Eight USB adapter is
  supported out of the box. `cec-client -t rpi` / `-t tcp` are rejected as *invalid device types*,
  so the "Raspberry Pi as a network CEC bridge" trick is **not** available in this build.
- `card0-HDMI-A-1` is the connected TV output. Intel Tiger Lake / Iris Xe implements no CEC at all
  (Kodi wiki: "most HDMI ports on computers do not have integrated support for CEC"; Intel: "Intel
  Graphics doesn't support CEC commands").
- The DisplayPort/tunnelled path is also out: kernel 6.16.12 exposes `drm_dp_dpcd_*` but **no
  `drm_dp_cec*`** symbols, i.e. DP-CEC over AUX is not compiled in. A DP→HDMI adapter with CEC will
  not help without a custom kernel.

**⚠ Known regression on exactly this LibreELEC version.** LE 12.2.x ships libcec 7.1.1 (LE 12.0/12.1
had 4.0.7) and that broke CEC for Pulse-Eight users on x86-64 NUCs and even RPi4 — the tracking
thread [forum.libreelec.tv/thread/30065](https://forum.libreelec.tv/thread/30065-x86-64-cec-broke-after-updating-to-le-12-2-0/)
is unresolved. Symptoms: the adapter is detected and libCEC opens it, but the remote does nothing,
and settings reset on reboot (*Connected to HDMI device* → TV, physical address overwritten, Kodi
force-switching the TV to HDMI 1 during playback). Root-caused to libcec PR #706.

Workarounds that worked for users:
- Delete the settings file and let Kodi regenerate it:
  `systemctl stop kodi; rm /storage/.kodi/userdata/peripheral_data/cec_CEC_Adapter.xml; reboot`
- Set *Connected to HDMI device* to the real topology (e.g. AVR/amplifier) and the correct HDMI port.
- Some users only got it working with the adapter on the TV's HDMI 1 / eARC port.
- **LE 13 fixes it properly** (nightly 20260420 confirmed working; libcec reverted in PR #11599, then
  bumped to **8.1.1** in PR #11612, merged 2026-07-29, which also adds multi-CEC-adapter support).
  LE 13 ships when Kodi 22 (Piers) ships — not released yet, and Piers breaks Mod V2, so treat any
  LE 13 move as a full client rebuild, not a free upgrade.
- Do **not** pre-create a CEC settings file: a legacy/wrong one is itself a known failure mode.

Wiring (when the adapter arrives):
- USB → laptop, HDMI **in-line** between laptop and TV. It is passive (no repeater): total HDMI run
  ≤~2 m at UHD / ≤5 m at 1080p, and it does not pass more than 4K60 4:2:0 8-bit — for 4K, do not run
  it in-line; plug its HDMI into a spare TV input instead.
- Gives: TV remote controls Kodi (**including Bluetooth-only remotes** like LG Magic Remote, which
  FLIRC cannot learn), Kodi powers the TV/AVR on and off, input switching, AVR volume.
- Does not give: anything when the TV is off, and Kore stays the better remote for typing/search.

If $49 is not worth it: **FLIRC USB (~$25)** + any IR remote presents as a keyboard and needs no CEC,
but adds no TV power/input switching and cannot learn Bluetooth remotes.

### Vizio specifics (TV confirmed 2026-09-21)

Vizio ignores a Kodi box that registers as a **Recording** device (libCEC/Kodi's default). On several
Vizio models (P55-F1, PX65, P-Series Quantum, E-series) the fix is to register as **Playback** —
reported by multiple users on the Kodi and LibreELEC forums; without it the TV lists Kodi as a
discovered CEC device but the remote does nothing.

- Kodi 21 stores this enum as its **label id**: `36051` Recording (default) → **`36052` Playback**
  (`36053` Tuner). Kodi ≤19 stored the raw libCEC number (`1` → `4`) instead — verified against
  `PeripheralCecAdapter.cpp` and `strings.po` for Omega.
- Edit `/storage/.kodi/userdata/peripheral_data/usb_2548_1002_CEC_Adapter.xml` **with Kodi stopped**
  (`systemctl stop kodi`), or the change is discarded when Kodi exits; then start Kodi and power-cycle
  the TV / toggle CEC off-on so it re-reads the device.
- **`scripts/cec-vizio-bringup.sh`** does this for you: no argument = read-only diagnostics (safe with
  no adapter attached), `--apply-vizio` = back up the XML + patch the setting (stops/starts Kodi
  itself). The generic LE 12.2.x caveats above still apply.

**If a Vizio remote is Bluetooth, FLIRC cannot learn it** — Vizio SmartCast remotes pair over
Bluetooth and several models have no IR emitter at all, so CEC would be the *only* way to use the TV
remote. Test any remote by pointing it away from the TV (or covering its front) and pressing volume:
if it still works it is Bluetooth. Also note many BT remotes only emit IR for power/volume/input, so
FLIRC would learn those buttons and nothing else. **This model is the exception — see below.**

#### V505-H9 (this TV — manual-verified 2026-09-21)

Checked the official V5-Series 2020 manual PDF directly (`cdn.vizio.com`, V505-H9 is covered):

- **CEC menu path confirmed:** *Menu → System → CEC* ("Adjusting the CEC Settings", p.24).
- **The manual never mentions Bluetooth, pairing, voice or microphone anywhere** (~726 KB of
  extracted text, 0 hits) — so this set ships with the **IR-only remote**, and the observed
  "I have to point it for it to work" confirms IR rather than Bluetooth. Every button must therefore
  be IR, since the TV has no Bluetooth remote pairing at all.
- **Consequence: FLIRC *is* viable here** (the earlier concern about Bluetooth remotes does not
  apply to this model), and it is now the best effort/benefit option: ~$25, no soldering, no CEC
  involvement, immune to the LE 12.2.x libCEC regression, and it works in Kodi *and* pre-boot.
  Sanity check any remote with a phone's **front** camera (most rear cameras filter IR): an IR LED
  shows as a white/purple flash on the screen when you press a button.
- CEC still has one thing FLIRC cannot do: let **Kodi power the TV/AVR on and off and switch
  inputs**. On this TV that means enabling the CEC menu above *and* applying the Playback
  device-type fix. V-series CEC key pass-through is unverified (the reports above are P-series).

**Recommended order for this box (IR remote + willing to solder):**
1. **FLIRC (~$25, no soldering)** — learns the Vizio remote's IR codes, presents as HID keyboard.
2. **DIY IR → HID (~$8–10, solder)** — Pro Micro/RP2040 + VS1838B IR receiver + an IR-decode →
   HID-keyboard sketch does the same job for less money, with real firmware work. Same line-of-sight
   requirement as FLIRC, since the emitter must see the receiver.
3. **CEC (pico-cec DIY or Pulse-Eight)** — only worth it for Kodi→TV/AVR power and input switching,
   which is FLIRC's blind spot; otherwise it adds the LE 12.2.x libCEC risk for no extra control.

### DIY alternative: pico-cec (CEC → USB HID keyboard, ~$15–20 in parts)

[gkoh/pico-cec](https://github.com/gkoh/pico-cec) is the soldering project for exactly this problem: a
microcontroller listens to the CEC bus and emits **USB HID keystrokes**, so Kodi just sees a keyboard.
It needs **no driver, no libCEC and no kernel support — which sidesteps the LE 12.2.x libcec
regression entirely**, and it works before Kodi starts. LibreELEC recognises it natively.

BOM (prices as published Jan 2026):

| Part | Note |
|---|---|
| Seeed Studio XIAO RP2350 (~$10.60 AUD) | reference board since Jan 2026; XIAO RP2040 also supported |
| HDMI male/female passthrough test board, model **WP-905** (~$4.30 AUD) | the board the CEC pin is soldered to |
| 4 short wires + 2× M3×10 and 2× M3×20 bolts | |
| optional 3D-printed enclosure | STLs ship in the release zip (`pico-cec-{base,middle,pusher,top}.stl`) |

- **Wiring:** XIAO pad `D3` → HDMI **pin 13 (CEC)**, `GND` → HDMI GND (≈pin 17); optionally HDMI pin 18
  (5V) → `5V/VUSB`. Then PC HDMI → pico-cec → TV, plus USB to the PC.
- **Firmware:** drag-and-drop UF2, no toolchain. `pico-cec-v0.8.0.zip` contains
  `pico-cec-seeed_xiao_rp2350-v0.8.0.uf2` (and the RP2040 build).
- **Good:** v0.2.2+ passes the Linux `cec-compliance` suite (survived an hour of fuzz testing); basic
  user-control messages (arrows, select, …) map to Kodi shortcuts; **v0.4.0 added logical address +
  device type settings** (directly relevant to the Vizio quirk) and v0.8.0 made the OSD name
  configurable.
- **Limits:** it is a keyboard, so Kodi cannot use it to power the TV/AVR or switch inputs — you get
  remote→Kodi control only. It is passive in-line like the Pulse-Eight adapter, so the same ~2 m UHD /
  5 m 1080p cable limits apply (v0.8.0 added an explicit 4K caution).
- Boards the project supports: XIAO RP2350 (reference), XIAO RP2040, plain Pico (needs "RGB
  unhacking"), Waveshare RP2040-Zero / CEC-Enabler.

**Not viable on this box:** [impulse-cec](https://github.com/mkopec/impulse-cec) (ESP32-C6 / RP2350) is
attractive on paper — it speaks the open **P8 protocol**, the same one libCEC and Kodi's Pulse-Eight
path use — but integrating it needs either the kernel `pulse8-cec` driver + `inputattach` (neither
exists on LibreELEC x86_64: `modinfo pulse8-cec` → not found, `inputattach` → not installed) or libCEC
serial support with manual wiring. pico-cec is the low-risk DIY path here.

### Verifying client changes headlessly

The box can be tested without the TV:

```bash
# list channels, play one, confirm it is playing
curl -s -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"PVR.GetChannels","params":{"channelgroupid":"alltv","limits":{"start":0,"end":6}}}' http://192.168.1.181:8080/jsonrpc
curl -s -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":2,"method":"Player.Open","params":{"item":{"channelid":1402}}}' http://192.168.1.181:8080/jsonrpc
curl -s -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":3,"method":"Player.GetActivePlayers"}' http://192.168.1.181:8080/jsonrpc

# crash check: compare before/after (must not increase)
ssh root@192.168.1.181 'dmesg | grep -ci segfault; grep -cE ERROR /storage/.kodi/temp/kodi.log'

# which URL the client actually plays (should be the Dispatcharr proxy, never cf.vovu.top)
ssh root@192.168.1.181 'grep -oE "Live Stream URL: [^ ]*" /storage/.kodi/temp/kodi.log | tail -1'
```

Edit addon settings in `userdata/addon_data/pvr.iptvsimple/instance-settings-1.xml`, then
`systemctl stop kodi; <edit>; systemctl start kodi` — stop Kodi first, otherwise it rewrites the
file on exit.

### PVR behavior

- Backend channel numbers (provider `tvg-chno`) are used — number entry on remote/Kore zaps directly.
- Channel switch is instant (no confirm dialog).
- Channel-number entry timeout is **3000 ms** (`pvrplayback.channelentrytimeout`) so multi-digit numbers
  like `101` can be typed without zapping on the first digit (Kodi default 0 = wait for an explicit OK).
- "Play next programme" is left **on** (`pvrplayback.autoplaynextprogramme = true`).
- Screensaver dim delay raised 3 → **15 min** (`screensaver.time`).

### NFL RedZone and "won't stop playing on its own" (2026-09-27)

**NFL RedZone** is the provider's `US: NFL REDZONE ᴴᴰ`, which lives in the `US| NFL PPV` group and ships
**hidden**, so it never made it into the curated lineup. It is now #**325** in `Sports: NFL`, renamed to
`NFL RedZone` (via `ChannelOverride.name`, which — unlike a raw rename — survives provider sync), and added
to `LINEUP` in `scripts/build-kodi-profile.py` so rebuilds keep it.

It also has **three sources** (`US: NFL REDZONE ᴴᴰ`, `TV: NFL REDZONE ᴿᴬᵂ`, `AT&T: NFL REDZONE ᴿᴬᵂ`), which
is the main thing that stops it dying when the provider drops the connection.

Playback-continuity settings applied on the box:

| Setting | Value | Why |
|---|---|---|
| `pvrplayback.autoplaynextprogramme` | **false** | at each programme boundary Kodi otherwise re-tunes; leaving it off keeps one continuous stream |
| `powermanagement.shutdowntime` | 0 | no idle shutdown timer |
| `powermanagement.displaysoff` | 0 | never blank the display |
| `screensaver.time` | 15 (unchanged) | Kodi inhibits the screensaver during video playback, so it cannot interrupt TV |

LibreELEC's `idle_timeout` turned out to be a **Bluetooth** setting (`oe.read_setting('bluetooth', …)`), not
a shutdown timer, and no idle-shutdown service is active — so there was nothing to disable there.

**Hand-curated picks are now exempt from the No-Guide sweep.** RedZone carries no EPG, so the sweep would
have moved it to `No Guide` and renumbered it. The sweep now skips anything from `LINEUP`/`EVENTS`
(`curated_ids`) and only re-homes bulk imports — which also protects the PPV event slots. Effect on the
sweep: 910 → **874** channels.

The client was rendering its GUI at **3840x2160 @ 30 Hz**. The TV's EDID marks 4K30 as *preferred* and
Kodi took it, which is why the whole UI felt sluggish and why 60 Hz content could not be shown natively.
The TV does offer 4K60 (and 1080p60/50/24, 720p60/50) — the kernel mode list proves it, so no cable or
TV-side change was needed.

**Finding the right `videoscreen.resolution` value.** Kodi's Display setting exposes only *one*
representative mode per resolution, so the number you need is not obvious. The values are a stable index
into the DRM mode list, offset from the first (preferred) mode:

    value = 17 + (index in `modetest -c` output)

Verified against all nine options Kodi offered — every one matched:

| Kodi value | `modetest` # | Mode |
|---|---|---|
| 17 | #0 | 3840x2160 @ 30 (preferred — what it was stuck on) |
| 21 | #4 | 4096x2160 @ 30 |
| **26** | **#9** | **3840x2160 @ 60** ← now in use |
| 36 | #19 | 1920x1080 @ 30 |
| 41 | #24 | 1280x720 @ 60 |
| 55 | #38 | 720x400 @ 70 |

So: `modetest -c`, pick the mode you want, set `17 + index`. Values below 17 are ignored and Kodi
silently falls back (a `value=7` experiment reverted to 17 on the next start).

Applied:

| Setting | Value | Why |
|---|---|---|
| `videoscreen.resolution` | **26** (3840x2160 @ 60) | 60 Hz UI; was stuck at 30 Hz |
| `videoplayer.adjustrefreshrate` | **2** (On start/stop) | correct cadence per channel: 59.94 US, 50/25 EU, 24 film |
| `videoscreen.whitelist` | **empty** (Kodi default) | see *why the whitelist is empty* below |
| `videoscreen.whitelistdoublerefreshrate` | true | 25→50 / 30→60 during whitelist search (inert while the whitelist is empty) |
| `videoscreen.whitelistpulldown` | true | 24p handling (inert while the whitelist is empty) |
| `videoscreen.delayrefreshchange` | 2 (0.2 s) | brief settle before switching, less black flash |
| `videoscreen.blankdisplays` | false | don't blank outputs during a mode change |

Verified after the change: `GUI format 3840x2160, Display 3840x2160 @ 60.000000 Hz`, 0 errors, no new
segfaults, and channels still play — `Player.Open` on 101 (KXAN → *Live: College Football*), 808
(*How to Catch a Dirtbag*), 2701 (AF: CANAL+ SPORT → *Liga+*).

**Why the whitelist is empty.** A whitelist was set twice and both attempts were silently mangled by this
build, which is why it is back to Kodi's default (empty = all modes are candidates):

- First attempt, entries formatted as the GUI writes them (`3840x2160 @ 60.00Hz`, 17 entries): Kodi logged
  all **17 entries as the single mode `3840x2160 @ 30.000000 Hz`**, and every lookup answered
  `[WHITELIST] No match` / `No resolution matched` — so switching did nothing at all.
- Second attempt using the exact format Kodi itself prints (`3840x2160 @ 60.000000 Hz`, 24 entries):
  **24 well-formed entries collapsed to 8 distinct modes**, and inconsistently — `1280x720 @ 59.940063`
  was accepted but `1920x1080 @ 59.94` was not.

With an empty whitelist the standard, well-tested path applies. Debug evidence that refresh switching is
live and evaluating correctly (`advancedsettings.xml` `<loglevel>1</loglevel>`, then reverted):

    [WHITELIST] Searching the whitelist for: width: 1920, height: 1080, fps: 29.970, 3D: false
    CRenderManager::Configure - change configuration. 1920x1080. framerate: 29.97.

**Trade-off:** with switching *On start/stop*, zapping between channels of clearly different frame rates can
cause a short HDMI resync/black flash. Streams here report 29.97/25 fps, and 29.97 against a 60 Hz desktop
is close enough that Kodi leaves the mode alone (no flash observed in testing). If resyncs do show up on
European channels, set `videoplayer.adjustrefreshrate` to `3` (On start) or `0` (Off).

### `advancedsettings.xml` (deployed from `kodi/advancedsettings.xml`)

Tags commonly recommended for IPTV tuning — `minvideocachelevel`, `minaudiocachelevel`,
`readbufferfactor`, `maxchunksize`, `buffermode`, `memorysize`, `readfactor` — were **removed in the
videoplayer merge and do not exist in Kodi 21**; they are silently ignored. Verify a tag exists in this
build before using it:

    ssh root@192.168.1.181 "strings /usr/lib/kodi/kodi.bin | grep -xiE 'minvideocachelevel'"

The deployed file uses only tags confirmed present: `<loglevel>`, `<network>` (`curlclienttimeout` 15,
`curllowspeedtime` 15, `curlretries` 3) to ride out brief IPTV upstream stalls, plus
`<enablemultimediakeys>` and `<remotedelay>` for the future FLIRC remote. Cache tuning stays in
guisettings (mode 2 / 64 MB / adaptive — see *Startup, buffering, sync and backups*). Kodi only reads
this file at startup and logs both files it loaded:

    grep "Loaded settings file" /storage/.kodi/temp/kodi.log

### `keymaps/livetv.xml` (deployed from `kodi/keymaps/livetv.xml`)

With no catchup and timeshift disabled, Kodi's default left/right in fullscreen live TV
(StepBack/StepForward) do nothing useful, so they are remapped to **channel down/up**, set-top-box style.
Everything else stays at Kodi's defaults (`g` guide, `c` channel list OSD, page-up/down zapping, digit
entry). The FLIRC receiver presents as a keyboard, so these bindings will apply to a physical remote too.

### Jellyfin addon: live library updates

`plugin.video.jellyfin` had `kodiCompanion = false`, so the **Kodi Sync Queue** plugin installed on the
server was never being used and `LastIncrementalSync` was days stale. Now `true` in
`userdata/addon_data/plugin.video.jellyfin/settings.xml` — libraries update without a manual sync. Edit
that file only with Kodi **stopped**, otherwise Kodi rewrites it on exit.

### Favourites are deliberately not pre-seeded

Seeding favourite channels by hand would be nice, but `pvr://` paths are unsafe to hardcode here. Kodi's
own logged path is volatile (`.../All%20channels@-1/1@pvr.iptvsimple_<random>.pvr`), and the stable-looking
form `pvr://channels/tv/All channels/101.pvr` **resolved to the wrong channel** — it played
*US: MOTORTREND HD* instead of KXAN. A favourite that tunes the wrong channel is worse than no favourite,
so favouriting stays manual (Kore: context menu → *Add to favourites*); channel numbers and the
`Austin Local` group already cover fast access.

### LibreELEC system settings: not set headlessly

`service.libreelec.settings` keeps almost nothing in its own XML — `oe_settings.xml` holds only
`wizard_completed` flags; the real settings (update channel, idle shutdown, …) are written by its GUI
against system files. Not worth the risk of hand-editing, so set them at the TV (Settings → LibreELEC at
Advanced level): pick the update channel and turn off idle shutdown for a box that should act like a TV.
Wake-on-LAN is moot until the box is on Ethernet — WoL over Wi-Fi is unreliable.

### Remaining customizations (not yet done)

- Favourites widget row in Mod V2, home-screen curation, Kore PVR remote-mode check (all GUI work).
- LibreELEC update-channel + idle-shutdown toggles (GUI, see above).
- Custom channel groups file / per-channel `tvg-shift` — only if time offsets are actually observed.
- Parental PIN: N/A — no adult groups in the lineup.
- Genre display: `useEpgGenreText=true` — guide shows provider EPG category text.
- Channel logos: served by Dispatcharr (`/api/channels/logos/<id>/cache/`), verified HTTP 200.
- Audio: passthrough left **off** on purpose. The HDMI sink registers as `AE_DEVTYPE_PCM` and the TV's
  speakers are stereo, so bitstreaming buys nothing while it *would* bypass Kodi's volume control (Kore
  volume buttons would stop working on AC3 streams). Revisit if a soundbar/AVR is added.

## Automation & sync (phase 2 proposal)

Deployed:
- **watchstate** (`:8081`) — watch-state sync between Jellyfin (and later other backends). Setup: open WebUI → create system user → add Jellyfin backend (two-way) → Dashboard → Webhooks → point at `http://watchstate:8081/ws/{key}`. Scheduled import runs hourly by default.
- **Backups**: host cron (04:15 daily) → Dispatcharr backup zips + Jellyfin SQLite snapshot → `/mnt/storage/backups/iptv-stack/`, 7 DB snapshots retained.

Not yet deployed (needs interactive setup + decisions):
- **Prowlarr + Sonarr + Radarr + Seerr** (`linuxserver` images): indexers → automation → requests. Seerr (formerly Jellyseerr, now "seerr") gives discovery/requests UI wired to Jellyfin auth; Sonarr/Radarr download into `/mnt/storage/tv` and `/mnt/storage/movies` which Jellyfin + jellyfin-kodi pick up automatically. Requires an indexer/usenet/torrent source decision.



### Known gotchas

- **Python module addons are not importable until Kodi restarts** after filesystem installation.
- **skinshortcuts builds its include file on first skin load** — first switch may fail once, then retry.
- Manual first-login in jellyfin-kodi 2.2.0 crashes with `KeyError: 'address'` (server_id unset); patched `connection_manager.get_server_info()` to fall back to the first saved server.
- Web/JSON-RPC credentials on the box: `kodi`/`kodi` (kodi.log reveals them if changed).

### Home screen curation (Mod V2)

Estuary Mod V2 ships looking similar to stock Estuary — the customization is in **skin settings → Home menu / widgets**: pin *PVR (Now Playing / Next Up)* and *Continue Watching* rows (Jellyfin), favourites. On first run the skin wizard offers menu setup; re-run any time via long-press on a home item.

### Live TV in Kodi

TV section → **1,668 curated channels** (see *Curated lineup for the client* above) in 22 groups
(Austin Local, Entertainment, Sports + per-league sub-groups, Mexico VIP, …). Channel numbers come
from Dispatcharr's `tvg-chno`. Kore (HTTP event server) works as the remote; FLIRC USB IR receiver is
the cheap "real remote" add-on — it presents as a keyboard, map your buttons once in the Flirc GUI,
works everywhere including pre-boot navigation. See *HDMI-CEC* above for the TV-remote option.

