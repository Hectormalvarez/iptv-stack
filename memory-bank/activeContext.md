# Active Context (2026-10-04)

## 2026-10-04: provider banned IPv6 (family flipped) + hourly Xtream sync disabled
- **Symptom:** Kodi couldn't play anything; the NFL slots showed the previous week's games.
- **Root cause — two parts:**
  1. The provider banned our **IPv6** (403 on `/`, `get.php`, `player_api`, `xmltv` and live)
     while **IPv4 served normally** (web root 401, live URLs 302) — the *reverse* of 2026-10-01.
     A third-party egress (r.jina.ai) got `401` on the web root, proving the provider was up and
     only *our* address was blocked. glibc sorts AAAA first, so the host-networked containers
     kept hitting the banned family and every stream died with `403 Forbidden`.
  2. The Jellyfin **Xtream sync was running hourly.** The plugin's `GetDefaultTriggers()` always
     returns a trigger — `Manual` falls through to an interval trigger of `SyncIntervalMinutes`,
     which defaults to **60**. Every run hammered `player_api.php` and re-tripped the ban; it
     also meant the playlist couldn't refresh, so the NFL fixture labels (read from
     `Stream.name`) were days stale → "not this week's game".
- **Fix:** mount `config/gai.conf` (`precedence ::ffff:0:0/96 100`) into dispatcharr + jellyfin
  (`6ff9530`); set `SyncIntervalMinutes=525600` so the sync no longer fires (`3c82c59`).
- **Verified:** NFL Network streamed 22 MB; Kodi opened the Commanders game (ch 5208, `NFL: 9:30am
  Colts at Commanders`) with Dispatcharr showing it `active`; **0** 403s; no Xtream sync since the fix.
- **Still open:** `get.php` was returning an odd Cloudflare `884` on IPv4, so the playlist hadn't
  refreshed — once the IPv4 path stays clean, force an M3U refresh + re-run `label-event-slots.py`
  to bring the fixtures current.

## Where things stand
Live TV is working again after a ~2-day provider-egress outage (see below). Everything else is
where it was on 2026-09-29: Kodi boots into the TV guide and zaps by number, the provider's VOD
catalog is imported into Jellyfin, and WNBA/NFL event slots are wired in.

## 2026-10-01: every channel 403'd (provider IPv4 block) — fixed
- **Symptom:** Kodi opened nothing; `dispatcharr` logged `HTTP error 403 Forbidden` on every
  provider stream URL; the `STRONG8K` EPG source went `status: error` (403).
- **Root cause:** the provider front `cf.vovu.top` returned **403 to our egress IPv4** on *every*
  endpoint (streams, `get.php`, `player_api`, `xmltv`) while **IPv6 worked** — same URL, same
  pinned `TiviMate` UA, same host; only the address family differed (`curl -4` → 403,
  `curl -6` → 302). A third-party IPv4 fetch of the web root returned 401, so it is a block on
  *this host's IPv4*, not IPv4 in general (403 body came from the provider's own CDN front).
- **Why only Dispatcharr broke:** the host has routable IPv6 and prefers it, so host `curl`
  worked; the bridged `dispatcharr` container had **no IPv6 route** and could only try the
  blocked IPv4.
- **Likely trigger:** the Xtream-Library VOD sync hammering `player_api.php` (first 403 burst
  2026-09-29 23:44). This ban outlived the documented ~15–45 min and escalated to live streams.
- **Fix (commit `ed272f9`):** `dispatcharr` → `network_mode: host`; Jellyfin keeps
  `http://dispatcharr:9191/...` via `extra_hosts: dispatcharr=172.18.0.1`; `media-net` subnet
  pinned so that gateway is deterministic.
- **Verified:** proxy stream 200 (21 MB), Kodi playing ch 1581 with `time` advancing at
  `speed: 1`, **0** 403s, and `STRONG8K` EPG refresh now `success` (45,033 programs).
- **Follow-ups done this session:** the Xtream VOD sync's daily trigger was removed
  (`SyncScheduleType=Manual` — no trigger is registered at startup) and is now run by hand via
  `scripts/sync-vod.sh`; Jellyfin also moved to host networking so that manual sync has IPv6;
  the STRONG8K profile's `max_streams` went 2 → 3 because with 2 a single zap already filled the
  cap and every extra zap 503'd.

## WNBA event slots (2026-09-29)
- 8 upcoming fixtures (Sep 29 – Oct 2) resolved from the provider's `US (WNBA NN) | <away> at
  <home> (<date>)` slots into group **`Sports: WNBA` at 368–375**, named via
  `ChannelOverride.name`, with a same-date failover feed attached where one exists.
- **Blockers found and fixed:** the provider's PPV slots are `hidden_from_output=True` (so
  membership alone did nothing — the profile M3U kept excluding them), and
  `build-kodi-profile.py` would have dropped the new group on its next run. `Sports: WNBA`
  is now in `KODI_GROUPS` + `CURATED_GROUPS`.
- Verified: profile M3U = 1,677 channels and contains both games with clean names.
- **Not verified:** the Kodi client never loaded them — the box was offline (no ARP, no SSH,
  full /24 scan clean). It also means the earlier playback attempt via a raw TS URL was cut
  short by the client, not by the provider (provider feed was healthy: 29 MB/6 s).
- To play the live game once the box is back: guide → `Sports: WNBA` → 368
  (`WNBA: Las Vegas Aces at Indiana Fever`), or JSON-RPC `Player.Open` on the channel id.

## Provider VOD → Jellyfin (2026-09-29)
- Xtream Library plugin v1.55.3.0 (STRM → native libraries, so `jellyfin-kodi` syncs it),
  `VOD Movies` + `VOD Series` libraries, STRM output at `/mnt/storage/vod-strm`.
- Category selection limited to an English "best of" (46 movie + 26 series categories) rather
  than the full 28.7k/8.7k catalog; picker lives in `scripts/pick-xtream-categories.py`.
- First sync was running at session end (batch 1/2: 4,060 movies, 1,998 series; ~6.9k STRM
  files already written). Check `/XtreamLibrary/Progress` next session and confirm the
  libraries populate in Jellyfin and Kodi.
- Lesson: the plugin's all-category defaults fire ~11k API calls and trip Cloudflare's
  403 block on the whole IP for ~1 h (live streams unaffected). Keep the selection tight and
  `RequestDelayMs=250`, `SyncParallelism=3`.
- Jellyfin `root` password was reset (user request; was never stored). New value given to the
  user, `MustUpdatePassword` set — not stored in the repo.

## 2026-09-29 provider outage (earlier, resolved)
- MNF night: Kodi couldn't play the game. Root cause was a **provider-wide outage** — every
  stream on `cf.vovu.top` returned Cloudflare `error code: 502` (origin down), including
  web-root HTTPS. Nothing local was broken; `verify-stack.sh` stayed healthy throughout.
- Diagnostic shortcut: before touching bindings/streams, curl 2+ unrelated channels' URLs.
  502 on all = provider outage, just wait. Recovery signs: web root goes 502 → 401
  "Restricted", stream URLs go 502 → 302 (redirect to data).
- Once the origin returned, played the dedicated **4K MNF event slot (ch 7038)** via
  JSON-RPC `Player.Open {"item":{"channelid":5171}}`; confirmed live playback. The 4K feed
  tested ~95 Mbps. Channel 2251 (NFL Network HD) carries the same 4K MNF stream as failover.

## Current lineup numbers
| Range | Group |
|---|---|
| 101–106 | Austin Local (KXAN/KTBC/KEYE/ABC-stand-in/PBS/Spectrum News) |
| 201–239 | Entertainment |
| 301–319 · 321–367 | Sports + per-league (incl. **325 = NFL RedZone**) |
| 401–409 · 501–507 · 601–604 · 701–704 | News / Kids / Movies / Spanish |
| 2001–3388 | Sports: Networks, NBA, NFL, MLB, NHL, College, Soccer, Golf & Tennis, Motorsport, Combat, International, Events |
| 801–849 · 1201–1933 | Mexico / Mexico VIP |
| 9001+ | No Guide (guide-less bulk channels) |

## Session work just completed
1. **NFL RedZone added** as #325 with **3 sources** (`US:` / `TV:` / `AT&T:`) — was hidden in the
   provider's `US| NFL PPV` group; renamed via `ChannelOverride.name` and added to `LINEUP`.
2. **`add-backup-streams.py`** — 475 of 1,668 channels gained a failover source. This fixed
   "channel 219 won't play": single-stream channels die at the provider's hourly reset
   (`Stream ends prematurely` → 3 × 4XX → `Found 0 alternatives`).
3. **`label-event-slots.py`** — 13 NFL fixtures restored into channel names
   (`NFL: 1pm Chargers at Bills`, `NFL: SNF 8:20pm Rams at Broncos`, …). The provider keeps the
   fixture in `Stream.name`; my earlier rename had discarded it.
4. **Playback continuity**: `pvrplayback.autoplaynextprogramme = false`, power timers off,
   screensaver unchanged (Kodi inhibits it during playback). LibreELEC's `idle_timeout` turned out
   to be Bluetooth-only — no shutdown timer exists.
5. **Playlist refresh 51 → 10 min** so fixture renames appear within 10 minutes.
   Verified there is no JSON-RPC way to force a reload in Kodi 21 (`Addons.SetAddonSetting`
   is absent); the timer or a GUI settings change are the options.

## Verified working
- RedZone playing, `state: active` on Dispatcharr, ~6.6 Mbps
- 0 Kodi log errors, no new segfaults (6 = pre-2026-09-26 VideoPlayer crashes)
- Guide aligned to America/Chicago, median depth ~14 h, all three EPG sources `success`
- `verify-stack.sh`: RESULT healthy (EPG coverage 98% of guide-expected channels)

## Known quirks, accepted for now
- NFL/PPV event slots carry **no EPG** — the game name lives on the channel name, not as a
  programme title. Provider XC EPG for those stream IDs returns empty.
- NBA/MLB event slots are empty (offseason); they will label themselves when fixtures appear.
- Arctic Fuse 3 is installed but needs a GUI first-load to build its includes; Mod V2 is active.
- 1,193 channels still have a single source (no duplicate exists on the provider).
