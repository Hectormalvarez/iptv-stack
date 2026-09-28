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
