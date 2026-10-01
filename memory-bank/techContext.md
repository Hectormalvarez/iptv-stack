# Tech Context

## Stack versions (as of 2026-09-27)
- LibreELEC **12.2.1**, Kodi **21.3 Omega**, Intel Tiger Lake iGPU (Iris Xe, VAAPI works)
- Dispatcharr / Jellyfin `:latest` images (pinning was deliberately deferred)
- Jellyfin **10.11.11**, Kodi Sync Queue plugin **15.0.0.0** (must match server ABI)
- Dispatcharr runs with **`network_mode: host`** (2026-10-01): the provider front 403s this
  host's IPv4 on every endpoint but serves IPv6, and a bridge container has no IPv6 route.
  Jellyfin stays on `media-net` and reaches it via `extra_hosts: dispatcharr=172.18.0.1`
  (media-net subnet pinned). See README *Provider egress*.

## The client
- Boots **straight into the TV guide** (`lookandfeel.startupwindow = 10702`)
- GUI runs at **3840x2160 @ 60 Hz** (`videoscreen.resolution = 26`); refresh switching *On start/stop*
- Display values are `17 + index into `modetest -c`` — see README *Display and playback tuning*
- `filecache.buffermode = 2` (HTTP finally cached), 64 MB, adaptive read factor
- Remote: **Kore** (HTTP event server). No physical remote yet — the Vizio V505-H9 remote is
  **IR-only** (manual-verified), so **FLIRC USB (~$25) is the recommended path**; HDMI-CEC only via
  Pulse-Eight/pico-cec and LibreELEC 12.2 has a known libCEC 7.1.1 regression
- Wi-Fi power save disabled (that was an early "finicky" root cause)

## Repo layout
```
docker-compose.yml          TZ=America/Chicago, DVR volume, /dev/dri, healthchecks
kodi/advancedsettings.xml   only tags verified to exist in Kodi 21 (many blog-post tags don't)
kodi/keymaps/livetv.xml     ←/→ = channel down/up (no catchup/timeshift, so step-back is useless)
kodi/deploy.sh              one command to push the two files above
scripts/build-kodi-profile.py   builds the curated "Kodi" channel profile (DRY_RUN default)
scripts/remap-epg.py            region-aware EPG fix via ChannelOverride (REMAP_APPLY=1)
scripts/label-event-slots.py    labels PPV slots with the provider fixture (LABEL_APPLY=1)
scripts/add-backup-streams.py   attaches failover sources (BACKUP_APPLY=1)
scripts/verify-stack.sh         read-only health check
scripts/cec-vizio-bringup.sh    Vizio CEC diagnostics / --apply-vizio
scripts/install-arctic-fuse3.sh AF3 skin side-by-side installer
```

## Cron (host, user crontab)
| When | What |
|---|---|
| 04:15 daily | Dispatcharr backups + Jellyfin SQLite snapshot → `/mnt/storage/backups/iptv-stack` |
| 08:30 daily | `verify-stack.sh` → `verify.log` |
| Mon 07:00 | `remap-epg.py` (REMAP_APPLY=1) → `remap.log` |
| Mon 07:20 | `add-backup-streams.py` (BACKUP_APPLY=1) → `backups.log` |
| 09:00 daily | `label-event-slots.py` (LABEL_APPLY=1) → `labels.log` |

## Kodi access
`ssh root@192.168.1.181` (password known to the user, not stored here).
JSON-RPC: `http://192.168.1.181:8080/jsonrpc`, user `kodi`/`kodi`.
