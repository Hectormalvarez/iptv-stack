# Active Context (2026-09-29)

## Where things stand
The stack works end to end and is being used. Kodi boots into the TV guide, zaps by channel
number, plays NFL RedZone continuously with 3 failover sources, and every NFL game slot is
labelled with its fixture.

## 2026-09-29 provider outage (resolved)
- MNF night: Kodi couldn't play the game. Root cause was a **provider-wide outage** — every
  stream on `cf.vovu.top` returned Cloudflare `error code: 502` (origin down), including
  web-root HTTPS. Nothing local was broken; `verify-stack.sh` stayed healthy throughout.
- Diagnostic shortcut: before touching bindings/streams, curl 2+ unrelated channels' URLs.
  502 on all = provider outage, just wait. Recovery signs: web root goes 502 → 401
  "Restricted", stream URLs go 502 → 302 (redirect to data).
- Once the origin returned, played the dedicated **4K MNF event slot (ch 7038,
  `NFL | 4k - MNF 8:15pm Eagles at Bears`)** via JSON-RPC
  `Player.Open {"item":{"channelid":5171}}`; confirmed `speed:1`, programme time advancing.
  The 4K feed tested ~95 Mbps. Channel 2251 (NFL Network HD) carries the same 4K MNF stream
  as its failover.

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
