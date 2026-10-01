# Decisions Log

| # | Decision | Why | Date |
|---|---|---|---|
| 1 | **Everything goes through the Dispatcharr proxy** — never `direct=true` | Provider pins UA (`TiviMate/5.1.6`) and is effectively 1-connection; Kodi's extra probes were stealing the slot and causing 502s | 2026-09-21 |
| 2 | **`max_streams` 1 → 2** | The 1 was Dispatcharr's own cap, not the provider's; it made every zap fail | 2026-09-21 |
| 3 | **Catchup + timeshift OFF** | Provider has zero archive (`tv_archive=1` on 0/15,830) and both are documented Kodi-Omega crash bugs (#499, #760). Time-shifting = Dispatcharr DVR recordings instead | 2026-09-21 |
| 4 | **Curated "Kodi" profile for the box, full lineup for Jellyfin** | 3,590 channels / 71 messy groups was unusable; the client gets a clean 1,669 | 2026-09-21 |
| 5 | **Timezone America/Chicago on box + containers, host stays UTC** | Host runs production stacks; guide was displaying 5 h late because everything defaulted to UTC | 2026-09-26 |
| 6 | **EPG writes go to `ChannelOverride`** | Provider sync rewrites `Channel.*`; overrides are the designed persistence point | 2026-09-26 |
| 7 | **Wrong-region EPG is blanked, not left** | A French schedule on a Mexican channel is worse than a placeholder; needs the `NO GUIDE` dummy because an override of NULL falls back | 2026-09-26 |
| 8 | **No-guide sweep is one-way and skips curated picks** | The original group isn't recorded, so sweeping before the guide settles strands channels; curated picks (RedZone, PPV slots) must stay put | 2026-09-26/27 |
| 9 | **Backup streams over retry tuning** | `MAX_RETRIES`/`RETRY_WAIT_INTERVAL` are in-container constants with no override; data-level failover is persistent and uses Dispatcharr's own mechanism | 2026-09-27 |
| 10 | **Fixture labels from `Stream.name` → `ChannelOverride.name`** | The provider updates stream names as fixtures are assigned; daily cron keeps them fresh | 2026-09-27 |
| 11 | **FLIRC over HDMI-CEC for the remote** | V505-H9 remote is IR-only (manual-verified), FLIRC is cheaper, avoids the LE 12.2 libCEC 7.1.1 regression, and works pre-boot | 2026-09-27 |
| 12 | **Audio stays PCM (passthrough off)** | HDMI sink is `AE_DEVTYPE_PCM` on stereo TV speakers; bitstreaming would kill Kore's volume control for zero gain | 2026-09-26 |
| 13 | **Reflashing rejected as the fix for crashes** | Root causes were catchup+timeshift on an archive-less provider and a client bypassing the proxy — both fixed in place | 2026-09-26 |
| 14 | **User edits live in `ChannelOverride`; scripts are dry-run by default and idempotent** | Every "it silently reverted" incident traced back to writing `Channel.*` | 2026-09-26 |
| 15 | **Provider VOD goes to Jellyfin via the STRM-writing *Xtream Library* plugin, not Kevinjil's `Jellyfin.Xtream`** | Kevinjil's exposes VOD as Jellyfin *channels*, which `jellyfin-kodi` does not sync — Kodi would never see the content. STRM files become native libraries that do sync. Plugin pinned to v1.55.3.0 because v2.0.x failed to load on Jellyfin 10.11 despite claiming ABI 10.11 | 2026-09-29 |
| 16 | **VOD library is a curated English "best of", not the full catalog** | 28.7k movies is unusable to browse and heavy on the provider API; foreign-language/regional, multi-sub and niche shelves are dropped (`scripts/pick-xtream-categories.py`). Widening later is one config change | 2026-09-29 |
| 17 | **Provider PPV slots are wired per-sport into the Kodi profile, unhidden explicitly** | Slots ship `hidden_from_output=True` (silently excluded from the profile M3U) and their names rotate per fixture, so a per-sport resolver (`add-wnba-events.py`) plus `KODI_GROUPS`/`CURATED_GROUPS` entries are required or the next profile rebuild drops them | 2026-09-29 |
| 18 | **Provider API calls are rate-limited by us, not by the plugin defaults** | A first sync across all categories (~11k API calls) tripped a Cloudflare 403 block on the whole IP for ~56 min; live streams kept working. Selection is kept tight and `RequestDelayMs=250`, `SyncParallelism=3` | 2026-09-29 |
| 19 | **Dispatcharr runs on `network_mode: host`** (not `media-net`) | The provider front 403'd this host's IPv4 on *every* endpoint while IPv6 worked; a bridge container has no IPv6 route, so it could only fail. Host networking gives it the host's working IPv6 egress. Jellyfin keeps `http://dispatcharr:9191/...` via an `extra_hosts` alias to the pinned media-net gateway (172.18.0.1). Trade-off: Dispatcharr loses network isolation and 9191 binds directly on the host (it already did) | 2026-10-01 |
