# Progress

## Done and verified ✅
- **Stack**: Dispatcharr + Jellyfin + Watchstate on compose, TZ=America/Chicago, healthchecks,
  GPU passthrough, DVR volume → `/mnt/storage/recordings`, nightly off-box backups
- **Provider integration**: proxied output only (UA pinned), `max_streams=2`, EPG matched
  region-correctly (673 mis-bound call-sign channels fixed, 865 rebinding, 981 wrong-region blanks)
- **Guide**: 3 EPG sources at 6–12 h cadence, median depth 3.8 h → ~14 h, timezone aligned
- **Curated client lineup**: 1,669 channels in 22 clean groups, all numbers/zapping working,
  every NFL/PPV slot labelled with its fixture
- **Failover**: 475 channels have ≥2 sources
- **Kodi client**: 4K60 GUI, refresh switching, boot-to-guide, 10-min playlist refresh,
  Live TV keymap, VAAPI, Kore remote, daily config backups to `/storage/backups/kodi`
- **Sports event slots**: NFL/NBA/MLB slots 341–367 + WNBA fixtures 368–375 (`Sports: WNBA`)
  with durable fixture names, added to the guide on 2026-09-29
- **Jellyfin**: tuner + guide from Dispatcharr, VAAPI, Kodi Sync Queue active, root password
  reset (2026-09-29; new password held by the user, not in git)
- **Provider VOD → Jellyfin**: Xtream Library plugin v1.55.3.0, `VOD Movies` + `VOD Series`
  libraries over STRM files in `/mnt/storage/vod-strm`; category selection limited to the
  English "best of" (46 movie + 26 series categories); on-demand sync (no schedule)
- **Ops**: `verify-stack.sh` healthy, 5 cron jobs, drift guards (idempotent + safety-abort scripts)
- **Live TV outage fixed (2026-10-01)**: the provider 403'd this host's IPv4 on every endpoint
  while IPv6 worked; **both** Dispatcharr and Jellyfin moved to `network_mode: host`
  (`ed272f9`, `58ff0f3`). Verified: proxy stream 200 (21 MB), Kodi playing at `speed: 1`,
  0 403s, `STRONG8K` EPG back to `success`, Jellyfin egress now IPv6
- **Xtream VOD sync is now manual (2026-10-01)**: daily 04:30 trigger removed
  (`SyncScheduleType=Manual`), run on demand via `scripts/sync-vod.sh` (`3e60497`)
- **Zapping fixed (2026-10-01)**: provider profile `max_streams` 2 → 3 — with 2 a single zap
  already filled the cap, so extra zaps 503'd
- **IPv4-first provider egress (2026-10-04)**: the provider's ban flipped to IPv6 while IPv4
  served normally; mounted `config/gai.conf` into both containers so glibc resolves IPv4 first
  (`6ff9530`). Verified: NFL Network + the Commanders game stream, 0×403
- **Xtream sync stopped firing hourly (2026-10-04)**: the plugin's `Manual` schedule type still
  left an *interval* trigger, so it ran ~every 60 min and re-tripped the ban; set
  `SyncIntervalMinutes=525600` (1 year) as the only config-only stop (`3c82c59`)
- **Guide outage recovered (2026-10-04)**: the provider's short-horizon `xmltv` feed had aged out
  while the 6-hourly EPG refresh 403'd (pre-`gai.conf`); re-ran Dispatcharr's own `refresh_epg_data`
  + `refresh_single_m3u_account` tasks → coverage 10% → **98%**, all three sources `success`, index
  rebuilt, profile M3U 1,677 channels, `/output/epg/Kodi` 35,315 programmes, proxy stream 19 MB/8 s;
  No-Guide sweep reapplied. Event labels were already current (0 changes)
- **Repo**: conventional commits throughout, credentials kept out of git (no commit count here —
  it went stale on every docs commit, and the last one existed only to bump it)
- **Stream-quality audit + ordered apply (2026-10-29)**: read-only audit script uses Dispatcharr's
  stream-specific proxy path with a single ffmpeg pass; core report generated from fresh Dispatcharr
  stats. Conservative apply promoted 4 clearly better sources (Eleven Sports, Tennis, MoviePlex,
  Big Ten Network), leaving event slots and ZQAVO untouched.
- **Repo published to GitHub (2026-10-30)**: pushed `main` only to the public repo
  `Hectormalvarez/iptv-stack` via `gh`. The `refs/cline/checkpoints/*` refs (Watchstate DB, redis
  dumps, logs) were kept local on purpose — never push with `--all`/`--mirror`. Full pre-publish
  audit found no credentials in `main`'s tree or history.
- **README restructured (2026-10-30)**: the 1,239-line log-style README split into a 97-line
  overview + `docs/reference.md` (verbatim deep dive); ~15 cross-references re-pointed.
- **Cline ↔ Telegram bridge live (2026-10-31)**: `cline-telegram` compose service runs
  `cline connect telegram` (bot @hectorsdevbot, allowlisted to one Telegram user id) with
  cwd=/workspace — the stack is now drivable/debuggable from a phone. Hard-won gotchas are in
  docs/reference.md *Cline ↔ Telegram bridge* (jq in image, HOME at state volume, hub port
  25464, foreground `-i`, stale-record cleanup, one-shot device auth).
- **Liga MX event wiring (2026-10-31)**: ZQAVO's `:Nbc Sports NN` / `:Peacock Event NN` event
  streams arrive UNATTACHED (raw `Stream` rows, no channel) — invisible to profile, Kodi and
  guide searches. Tonight's Chivas vs Atlante (7:30 PM CT) wired onto VIX slot ch #3192
  (event stream order=0, filler demoted, override name, unhidden, membership enabled).
- **Tijuana found + playing (2026-10-31)**: Monterrey vs Tijuana (8:05 PM CT, Canal 5/TUDN/ViX)
  located via the generic guide title `Live: Fútbol Mexicano Primera División`; tuned to
  VIP: TUDN. Mid-tune the provider's hourly stream reset killed both sources — recovered with
  Stop+Open re-tune + ZQAVO TUDN attached as order=2 safety net (see systemPatterns).
- **Arsenal event-slot wired + playing (2026-11-07)**: STRONG8K `US (Peacock 021)` slot
  ch #7812 (id 3935) unhidden, Kodi membership enabled, fixture override name set; feed
  probed 1080p30 through the proxy; tuned **channelid 5261** at the live edge (`47:30/4:00`,
  `speed 1`) minutes after the user powered the (previously off) box on. Full entry in
  activeContext.

## Pending ⚠️
- **Post-match cleanup of the EPL slot channel (2026-11-07):** after today's matches, re-hide
  #7812 (id 3935), disable its Kodi membership, clear the `ChannelOverride.name`, **and remove
  the `ChannelStream` links to the MW10 feeds (`S 6599` Peacock 006, `S 7625` STAN 12)** — the
  next provider sync may re-hide it on its own, but the override name and links linger.
- **Finish the EAGLE4K account (id 4, 2026-11-07):** its first import stalls on the 33k-catalogue
  XC fetch; retry the refresh (timeout patch applied) and, once ~1.5k streams land, decide its
  role — likely REPLACE ZQAVO as the failover account (`line.zqavo.top` is connection-reset dead,
  EAGLE4K points at the live `vpn-esxtrapro.pro` DNS) and disable the ZQAVO M3U account; re-point
  or prune the 41 ZQAVO-wired `ChannelStream` links via `scripts/swap-provider.py` once its
  apply/prune stage exists.
- **Reapply the in-container XC timeout patch after any image update:**
  `/app/core/xtream_codes.py:77` `timeout=60 → 300` (sed; survives restarts, not recreates).
- **Re-probe the Liga MX Chivas vs Atlante stream near 7:30 PM CT kickoff** (2026-10-31) and
  verify Kodi picked up channel #3192 (watcher log: `/tmp/ligamx-watch.log`); the pre-game
  0-byte probe was normal.
- **Generic `scripts/wire-event-stream.py`** (2026-10-31): the ZQAVO `:Nbc Sports NN`/
  `:Peacock Event NN` wiring is a manual one-off; make it a dry-run-first script taking a
  stream id/regex + slot channel (pattern recorded in docs/reference.md).
- **Kodi SSH key still needs installing at the box** (2026-10-29): `root@k5320.lan` answers but
  rejects key auth. Remote recovery, skin activation and log-based checks remain blocked on this.
- **Arctic Fuse 3 activation is still manual at the TV** (2026-10-29): installer now targets 3.4.13
  + current deps, but the installed skin is still 3.3.1 and stock Estuary remains active.
- **Event-slot EPG pilot is prepared but not applied** (2026-10-29): only explicit-date fixtures are
  eligible; time-only NFL names must not be turned into recurring dummy guide rows.
- _(done 2026-10-11)_ box power-cycled; **#410 NBC 5 Chicago (WMAQ) is playing the Chicago Marathon**.
- _(done 2026-10-25)_ **`order=1` fixture-mismatch audit complete.** 4 wrong-game links removed —
  #321/#1680/#1681/#2251 (all NFL Network) were falling over to `NFL  | 4k - SNF 8:20pm Chiefs at
  Seahawks`, a *different* broadcast — and those channels were then re-pointed at the second
  subscription's correct NFL Network feed, so none are single-source. Re-audit: **0 remaining**.
  Left for review: **#324 NHL Network's `order=1` is the empty slot `NHL  |  4K -`**.
- **The new subscription (ZQAVO) has `get.php` and `xmltv.php` returning 502** — `player_api.php`
  works, which is all the import needs. Harmless while it is failover-only, but promoting it to a
  primary would need a working EPG path, and `max_connections: 1` means it can never serve two
  channels at once.
- **#104 ABC 13 (KTRK Houston) is single-source.** It carried Ole Miss at Texas on 2026-10-24 and is
  the only usable ABC feed in the profile, so any ABC game still dies at the provider's hourly reset
  (`add-backup-streams.py` hardened 475 channels but not this one). Duplicate candidates spotted:
  `VIP: ABC AEREO (MEXICALI / TIJUANA / CIUDAD JUAREZ)`, currently parked in the `No Guide` group.
- **The box is on `192.168.1.182` now** (`k5320.lan`; `.181` is dead). The DHCP drift is routine
  rather than an incident — resolve the hostname first, every session.
- **Install an SSH key on the box — now the top priority.** Remote recovery is impossible without
  it (this session needed a power cycle at the box, twice), and so is every docs/reference.md workflow that
  greps `/storage/.kodi/temp/kodi.log`.
- **Do not use the `pvr.iptvsimple` addon toggle to force a playlist reload** — it wedges the player
  (see `systemPatterns.md`). Wait for the 10-min refresh timer instead.
- **Audit the *primary* source (order 0) of the sports/event channels.** RedZone proved the trap:
  Dispatcharr defaults to whatever was linked first, which was the 720p**30** `ᴴᴰ` variant while
  1080p**60** `ᴿᴬᵂ` variants sat unused — and one RAW variant was outright corrupt. A one-pass script
  could ffprobe each channel's order-0 feed and report fps/corruption, the way `add-backup-streams.py`
  reports missing backups.
- **Confirm #410 survives the next `build-kodi-profile.py` run** — it should (adopted via its `News`
  group membership), but it is the first channel added by hand rather than by the script.
- **Confirm Jellyfin's guide repopulated.** It pulls Dispatcharr's XC `xmltv.php` and refreshes on
  its own schedule; the admin password is held by the user, so this was not forced. Check Live TV →
  guide next session.
- **Delete the orphan M3U account 1** (`custom`, STD, **no URL**) — it only ever reports `error` and
  feeds nothing.
- _(done 2026-10-04)_ provider fixtures refreshed; `label-event-slots.py` re-run (0 changes);
  No-Guide sweep reapplied (896 parked). _(resolved 2026-10-01)_ VOD sync is manual — `scripts/sync-vod.sh`.

## Open items from 2026-09-29
- **Kodi box is back online** (2026-10-01): reachable at 192.168.1.181 (Kodi 21.3), PVR loaded
  with 1,677 channels / 23 groups including `Sports: WNBA`. It streams again after the
  2026-10-01 networking fix (verified playing ch 1581). Earlier it had been offline (no ARP,
  full /24 scan clean) — the WNBA channels were in the profile M3U but unloaded at the time.
- **Kodi box SSH is listening but unusable** (inaccurate note fixed 2026-10-11): port 22 is now
  **open**, but `root@192.168.1.181` rejects both key and password auth from `usrv-01`, so
  JSON-RPC on 8080 (`-u kodi:kodi`) is still the only channel in. Forcing a playlist reload from
  outside remains impossible; a restart on the box (or the 10-min timer) is the only way. Still
  worth installing an SSH key from LibreELEC settings — that would also make the reference doc's
  log-based checks (`/storage/.kodi/temp/kodi.log`) usable from here.
- **Kodi client IP drifts** (DHCP). If JSON-RPC stops answering, scan for the box rather than
  assuming it is down.
- Confirm whether the client's IPTV Simple refresh interval is really 10 min: reference doc's
  component table still says 51 min, `activeContext` says it was changed to 10.
- **First VOD sync was still running at session end** (batch 1/2: 4,060 movies, 1,998 series);
  check `/XtreamLibrary/Progress` and that `VOD Movies`/`VOD Series` populate, then confirm
  Kodi sees them through `jellyfin-kodi`.

## Not yet decided / optional
- **`*arr` suite** (Prowlarr + Sonarr + Radarr + Seerr) — libraries are empty; needs a
  torrents-vs-usenet decision. This is what makes "Jellyfin stuff" finally appear in Kodi.
- **Watchstate first-run** (browser: system user → Jellyfin backend two-way → webhook)
- **Jellyfin user profiles** (kids/guest) — needs the current Jellyfin admin password
- **FLIRC USB** for a real remote (Vizio V505-H9 remote is IR-only; CEC needs hardware and
  LibreELEC 12.2 has a libCEC regression — see docs/reference.md *HDMI-CEC*)
- **USB-C→Ethernet adapter** for the Latitude (removes Wi-Fi as a variable)
- **Pin image versions** or add Watchtower (currently `:latest`)
- **Extend the EPG remap** coverage further / consider a second curated profile for Jellyfin
- Home-screen curation in Mod V2 (widgets/favourites) — needs the TV
