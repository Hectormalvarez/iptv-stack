# Project Brief — iptv-stack

## What this is
A self-hosted IPTV + media stack that turns a single provider subscription into a
polished, cable-box-like experience on Kodi, with Jellyfin as the media layer.

## Components
| Piece | Where | Role |
|---|---|---|
| **Dispatcharr** | `usrv-01:9191` (container `dispatcharr`) | The brain. Holds provider streams, EPG, output profiles, proxy, DVR |
| **Jellyfin** | `usrv-01:8096` (container `jellyfin`) | Media library + Live TV for non-Kodi clients, recordings |
| **Watchstate** | `usrv-01:8081` (container `watchstate`) | Watch-state sync between backends (deployed, **not yet configured**) |
| **Kodi client** | `192.168.1.181` (Dell Latitude 5320, LibreELEC 12.2.1 / Kodi 21.3 Omega) | The TV front end |

## Provider
strong8k via `cf.vovu.top` (Xtream Codes). See the provider section in `README.md` for
URLs and credentials — **credentials live only there and in `.gitignore`d files, never in git**.
Key constraints: User-Agent is pinned to `TiviMate/5.1.6 (Android 12)`, and the
subscription is effectively a single connection, so *everything* must go through the
Dispatcharr proxy (never `direct=true`).

## Architecture in one line
Provider → Dispatcharr (1 shared upstream connection, correct UA, proxy + failover)
→ curated channel profiles → Kodi (IPTV Simple for live TV) and Jellyfin (everything else).

## Two non-negotiables
1. **Never bypass Dispatcharr.** Kodi and Jellyfin only ever see `/output/m3u/...` and
   `/proxy/ts/stream/...` URLs.
2. **User data is written to `ChannelOverride`, never to `Channel`.** Provider sync rewrites
   `Channel.*` on every refresh; overrides survive.
