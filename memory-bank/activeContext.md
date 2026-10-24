# Active Context (2026-10-24)

## 2026-10-24 (Sat evening): Ole Miss at Texas pulled up on ABC — plain zap, no wedge
- **Request:** "pull up the college football game" — the game is **not identifiable from the guide**.
- **Box IP drifted again: `k5320.lan` = `192.168.1.182`** (`.181` answers nothing; same Kodi, same
  `-u kodi:kodi`). Resolve the name every session instead of reusing a remembered number.
- **Why the guide cannot answer "which game":** the provider's EPG titles every national feed
  **"Live: College Football"**; the fixture is only in the programme **description**
  (#104: *"The No. 7 Ole Miss Rebels visit the No. 19 Texas Longhorns for an SEC game"*).
  So enumerate the slate from `ProgramData.description`, not `title` — see `systemPatterns.md`.
- **The provider's `US| NCAAF PPV` group (82 slots) is a decoy.** All ship
  `hidden_from_output=True`, so none are in the Kodi profile, and their **channel names are stale**
  (a previous week's fixtures) while their **stream names are current** — #7956's name reads
  "UT Rio Grande Valley at UTSA" but its stream reads "2pm Colgate at Richmond". Trust neither
  without cross-checking.
- **Done:** resolved **pvrid 2048** = `US: ABC 13 (KTRK) HOUSTON HD` (profile **#104**,
  `Austin Local`; `channelid` ≠ channel number), then `Player.Open` → `OK` on the first try while
  the box was already streaming ESPN (#301).
- **Verified:** `Player.GetItem` → correct label; `Player.GetProperties` → `live: true`, `speed: 1`,
  h264 1280×720 (ABC is 720p60 natively — not a degraded feed); Dispatcharr
  `Channel 5ebe13bf-… has 1 clients, state: active` (UUID confirmed = #104), **0×403**; the old ESPN
  session (`5cd98c12-…`) tore down cleanly, so **a plain zap still does not wedge the box**.
- **Watch:** #104 is **single-source** — exactly the hourly-reset death pattern. No failover attached.

## 2026-10-11 (later): NBC 5 Chicago added for the marathon — ON AIR (fixed by a power cycle)
- **Request:** switch to the Chicago Marathon on the NBC Chicago channel, "not listed in the guide".
- **Why it was missing:** the WMAQ feed was never a profile member. The right channel is
  **#1923 `US: NBC 5 CHICAGO IL (WMAQ) HD`** (channel id 4404), bound to EPG
  `EPGSHARE-US-LOCALS/WMAQ-DT`, whose current programme is literally *2026 Bank of America Chicago
  Marathon* (12:00–16:00 **UTC** = 07:00–11:00 CDT — note `timezone.localtime()` in the container
  prints **UTC**, so subtract 5 h for Austin). The three other WMAQ rows (`#5004`/`#5005`/`#5006`
  A/H/S and `#5376` D) are RAW feeds on the same EPG.
- **Done (durable):** moved it into the **`News` group at #410** with `ChannelOverride.name =
  'NBC 5 Chicago (WMAQ)'` and enabled the Kodi membership — the builder *adopts* anything already
  in a `KODI_GROUPS` group, so a future `build-kodi-profile.py` run keeps it (no script edit
  needed). Attached `#5005`'s stream as an order=1 failover: the feed was single-stream, which is
  the documented hourly-reset death. Profile M3U 1,677 → **1,678**; `verify-stack.sh` healthy,
  EPG coverage 98%. Both feeds verified through the proxy (primary ~10 Mbps, failover ~15 Mbps,
  h264 720p30 + AAC-LC — nothing exotic).
- **How it went wrong:** to make the box see #410 I toggled `pvr.iptvsimple` off/on (the only
  remote way to force a playlist reload). The box picked the channel up (1,678 channels, PVRID
  5215) but the toggle killed the running NFL stream **and wedged Kodi's app thread** — see
  `systemPatterns.md` for the full symptom pattern. The marathon never started, and the box can no
  longer be driven: `System.Reboot` is accepted but not executed, SSH auth is refused, so **only a
  power cycle at the box recovers it**.
- **RESOLVED by a power cycle:** with a clean boot, `Player.Open` on channel 410 returned `OK` on the
  first try and the marathon played — `label "NBC 5 Chicago (WMAQ)"`, title *2026 Bank of America
  Chicago Marathon*, `speed: 1`, position **2h32m** of the 4 h broadcast (the live edge), Dispatcharr
  showing 1 client `state: active`, 0×403. So the channel, the M3U entry and the feed were all fine;
  the two freezes were **stale IPTV Simple/PVR state from the mid-session addon toggle**, and only a
  reboot cleared it. PVR id stayed **5215** across the restart here, but resolve it fresh rather than
  assuming.
- **Then: RedZone was "laggy" → fixed by reordering its sources (same session).** `#325`'s primary
  (`US: NFL REDZONE ᴴᴰ`) was a **720p29.97** feed while `TV:`/`AT&T:` `ᴿᴬᵂ` are **1080p59.94** — the
  "HD" name was the worst of the three. Promoted `TV:` first, which turned out to be **corrupt**
  (`Packet corrupt`, reconnect attempts) and gave a *black screen while Kodi reported `speed: 1`,
  fullscreen video and 1080p* — my mistake; the burst-inflated 6 s bitrate sample I chose it on was
  misleading. Settled on **`AT&T:` (1080p59.94, ~9 Mbps steady)** with `US:` (720p30, ~4.8 Mbps) as the
  first fallback and the corrupt `TV:` last. Verified: box reports `VideoResolution 1080`,
  `speed: 1`, `Live: NFL RedZone`, no errors on the new session, 0×403.

- **Second freeze (same session):** the box un-wedged on its own (it answered
  `Player.GetActivePlayers` → `{"result":[]}`, so the app thread was alive), `Player.Open` on 5215 was
  issued, the proxy logged the box connecting and dropping twice within ~2 s, and the app thread
  wedged again — all `Player.*` / `GUI.*` calls now hang while `JSONRPC.Ping` still answers. Verdict:
  a PVR channel open re-triggers the wedge, and only a power cycle clears it. Server side was cleared
  in the same pass — the entry the box receives for `#410` is identical in shape to the working `#352`
  entry (fetched with the box's own Host, zero `localhost` URLs), catchup is off on channel and
  streams (`is_catchup=False`, and the profile M3U has no `catchup` attributes at all), and the feed
  streams at ~10 Mbps. (The clean-boot retry did work — see the RESOLVED bullet above.)

## 2026-10-11: "put the game on" — live TV switched via JSON-RPC (operational, no code change)
- **Request:** put on the early-window NFL game. It is provider slot **#352**
  `NFL: 9:30am Eagles at Jaguars` (`group-title="Sports: NFL"`), kickoff 09:30 ET = 08:30 CDT,
  still on the provider's slate. Guide/EPG healthy throughout (`verify-stack.sh` → healthy,
  98% coverage, 1,677 profile channels).
- **Played:** `Player.Open {"item":{"channelid":5198}}` → `speed: 1`, position **35m56s → 36m28s**
  (resumed at the live edge, so it is the real feed, not a restart). Dispatcharr logged
  `Channel 74f8bce5-… has 1 clients, state: active`, **0×403** over 5 min, and the previous
  channel (ESPN HD pregame, `5cd98c12-…`) released its slot cleanly. Proxy stream pre-checked
  at 11.2 MB / 12 s (~7.5 Mbps) before switching.
- **PVR `channelid` ≠ channel number.** The scripted NFL slate is `channelid` 5194–5213
  (5198 = 352 Eagles, 5208 = 360 Giants@Commanders, 5152 = 325 RedZone, 1791 = 321 NFL Network).
  Resolve ids with `PVR.GetChannelGroups` → `Sports: NFL` = **77**, then
  `PVR.GetChannels {"channelgroupid":77}` (omit `properties` to get `channelid`+`label`).
- **Box state:** back at **192.168.1.181** (`k5320.lan`); **port 22 is now open** but rejects key
  *and* password auth from `usrv-01`, so JSON-RPC on 8080 is still the only way in.
- **Lesson (now in systemPatterns):** an unauthenticated `/jsonrpc` POST answers `401` with an
  **empty body**, which reads exactly like a dead host. And `192.168.1.107`/`.142` also listens
  on 8080 but is a different machine (`ul5420`) — a port scan is not a box check.

## 2026-10-04 (later): guide restored — STRONG8K EPG refreshed + No-Guide sweep reapplied
- **Symptom:** `verify-stack.sh` FAILed — EPG coverage **10%** (692/777 blank), `STRONG8K` source
  `status=error`, both M3U accounts `error`. Live TV itself still worked.
- **Root cause (not corruption):** the provider's `xmltv.php` feed is **short-horizon** (only ~11–14 h
  of programmes for the mapped channels), so the 6-hourly `epg_source-refresh-1` is the lifeline.
  It had been failing since ~2026-10-03 12:03 with the pre-`gai.conf` **403** (IPv6-first egress), so
  no new programmes were inserted and the guide simply **aged out** — `ProgramData.max_end` was frozen
  at 2026-10-03 22:59 UTC. The 13:46 UTC container recreate (the `gai.conf` fix) also wiped the
  **ephemeral** `/app/media` EPG cache, but that is by design (`APP_DIRS`; `fetch_xmltv` recreates it).
- **Fix (first-party recovery, no code change):** dispatched Dispatcharr's **own** tasks —
  `refresh_epg_data.delay(1, force=True)` (the UI refresh icon / `POST /api/epg/import/`) and
  `refresh_single_m3u_account.delay(2)`. Egress was already healthy: `https://cf.vovu.top/` → 401 on
  both families, and the EPG URL fetched with the pinned `TiviMate/5.1.6` UA → 200.
- **Verified (first-party):** `STRONG8K` `status=success` ("Parsed 48,352 programs for 885 channels"),
  `ProgramData` future = **24,235**, `max_end` → 2026-10-06 02:40 UTC; programme index rebuilt (3,639
  channels); M3U refresh "Streams: 2419 updated", auto-sync ok; `verify-stack.sh` → **RESULT: healthy**,
  coverage **98%** (781 guide-expected, 13 blank); profile M3U = 1,677 channels; `/output/epg/Kodi` =
  35,315 programmes; proxy stream pulled **19 MB in 8 s**. Reapplied the No-Guide sweep (896 parked).
- **No-op:** `label-event-slots.py` dry run showed **0** changes (19 slots already labelled — the
  override names are durable and match this week's fixtures).
- **Known orphan:** M3U account 1 (`custom`, STD, **no URL**) stays `error`; it has nothing to fetch.
- **Not done:** Jellyfin's guide refresh — it pulls Dispatcharr's XC `xmltv.php` and refreshes on its
  own schedule (the Jellyfin admin password is held by the user, not stored).

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
- **Resolved (later 2026-10-04):** once IPv4 egress stayed clean, a forced M3U refresh + re-run of
  `label-event-slots.py` brought the playlist current — see the section at the top.

## Where things stand
The guide is healthy again — 98% coverage, `verify-stack.sh` RESULT: healthy (2026-10-04). Kodi boots
into the TV guide and zaps by number, the provider's VOD catalog is imported into Jellyfin, and
WNBA/NFL event slots are wired in. Live playback was re-verified end-to-end through the proxy
(19 MB in 8 s) this session.

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
