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
  English "best of" (46 movie + 26 series categories); daily 04:30 sync
- **Ops**: `verify-stack.sh` healthy, 5 cron jobs, drift guards (idempotent + safety-abort scripts)
- **Live TV outage fixed (2026-10-01)**: the provider 403'd this host's IPv4 on every endpoint
  while IPv6 worked; Dispatcharr moved to `network_mode: host` (commit `ed272f9`). Verified:
  proxy stream 200 (21 MB), Kodi playing ch 1581 at `speed: 1`, 0 403s, `STRONG8K` EPG back to
  `success`
- **Repo**: 47 conventional commits, credentials kept out of git

## Pending — the one operational step left ⚠️
- **Re-run the No-Guide sweep.** It was deferred while the EPG harvest drained (the harvest is
  now finished). Dry run expects **889** channels → `No Guide`, with curated picks exempt
  (`Sports: WNBA` is now in `CURATED_GROUPS`, so the new event slots stay put).
  ```bash
  cd /home/hadev/Projects/Lab/iptv-stack && sed 's/^DRY_RUN = True$/DRY_RUN = False/' \
    scripts/build-kodi-profile.py | docker exec -i dispatcharr python manage.py shell
  ```
  Then refresh Jellyfin's guide. Until this runs, blank channels still sit inside
  `Mexico VIP` / `Sports: …` groups.
- **Jellyfin's VOD sync is still IPv4-only** (2026-10-01). It runs in the bridged Jellyfin
  container, so the daily 04:30 run keeps hitting the provider's blocked IPv4 — the same ban
  that took live TV down. Move Jellyfin to `network_mode: host` too (tuner → `127.0.0.1:9191`)
  or throttle/pause the sync, so the ban can cool. Live TV is unaffected by this.

## Open items from 2026-09-29
- **Kodi box is back online** (2026-10-01): reachable at 192.168.1.181 (Kodi 21.3), PVR loaded
  with 1,677 channels / 23 groups including `Sports: WNBA`. It streams again after the
  2026-10-01 networking fix (verified playing ch 1581). Earlier it had been offline (no ARP,
  full /24 scan clean) — the WNBA channels were in the profile M3U but unloaded at the time.
- **Kodi box has no SSH** (port 22 unreachable) — only JSON-RPC on 8080. Forcing a playlist
  reload from outside is therefore impossible; a reboot/restart on the box (or the 10-min
  timer) is the only way. Worth enabling SSH in LibreELEC settings.
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
