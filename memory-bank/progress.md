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

## Pending ⚠️
- _(done 2026-10-11)_ box power-cycled; **#410 NBC 5 Chicago (WMAQ) is playing the Chicago Marathon**.
- **Install an SSH key on the box — now the top priority.** Remote recovery is impossible without
  it (this session needed a power cycle at the box, twice), and so is every README workflow that
  greps `/storage/.kodi/temp/kodi.log`.
- **Do not use the `pvr.iptvsimple` addon toggle to force a playlist reload** — it wedges the player
  (see `systemPatterns.md`). Wait for the 10-min refresh timer instead.
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
  worth installing an SSH key from LibreELEC settings — that would also make the README's
  log-based checks (`/storage/.kodi/temp/kodi.log`) usable from here.
- **Kodi client IP drifts** (DHCP). If JSON-RPC stops answering, scan for the box rather than
  assuming it is down.
- Confirm whether the client's IPTV Simple refresh interval is really 10 min: README's
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
  LibreELEC 12.2 has a libCEC regression — see README *HDMI-CEC*)
- **USB-C→Ethernet adapter** for the Latitude (removes Wi-Fi as a variable)
- **Pin image versions** or add Watchtower (currently `:latest`)
- **Extend the EPG remap** coverage further / consider a second curated profile for Jellyfin
- Home-screen curation in Mod V2 (widgets/favourites) — needs the TV
