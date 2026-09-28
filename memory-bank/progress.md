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
- **Jellyfin**: tuner + guide from Dispatcharr, VAAPI, Kodi Sync Queue active, root password reset
- **Ops**: `verify-stack.sh` healthy, 5 cron jobs, drift guards (idempotent + safety-abort scripts)
- **Repo**: 41 conventional commits, clean tree, credentials kept out of git

## Pending — the one operational step left ⚠️
- **Re-run the No-Guide sweep.** It was deferred while the EPG harvest drained (the harvest is
  now finished). Dry run expects **874** channels → `No Guide`, with curated picks exempt.
  ```bash
  cd /home/hadev/Projects/Lab/iptv-stack && sed 's/^DRY_RUN = True$/DRY_RUN = False/' \
    scripts/build-kodi-profile.py | docker exec -i dispatcharr python manage.py shell
  ```
  Then refresh Jellyfin's guide. Until this runs, blank channels still sit inside
  `Mexico VIP` / `Sports: …` groups.

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
