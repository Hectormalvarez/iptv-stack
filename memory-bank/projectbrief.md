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

## Providers
Two subscriptions, both consumed **only** through Dispatcharr:

| Name | Account | Host | Role | Concurrency |
|---|---|---|---|---|
| **STRONG8K** | id 2 | `cf.vovu.top` | primary — every curated channel's `order=0` source | 3 |
| **ZQAVO** | id 3 | `line.zqavo.top` | **failover only** — deepest source on 22 curated channels | **1** |

Credentials live in Dispatcharr's M3U accounts and in `.gitignore`d files — **never in git**,
never in the memory bank. ZQAVO was added 2026-10-25 after STRONG8K took the whole stack down
twice in one day (IPv4 403'd, then 502 on both families for hours). It is deliberately *not* a
primary because it permits only **one** concurrent connection. See `README.md` → *Provider*
and `decisions.md` #27.

Key constraints: everything must go through the Dispatcharr proxy (never `direct=true`), and
the provider front 403s **one address family at a time** — that preference lives in
`config/gai.conf` (see `decisions.md` #23 / #26).

> Discrepancy to re-verify: `M3UAccount.user_agent` is `None` on both accounts, so the
> long-standing "User-Agent pinned to `TiviMate/5.1.6`" claim is **not** visible in the account
> config. It may live in a Stream Profile, or the claim may be stale.

## Architecture in one line
Provider → Dispatcharr (1 shared upstream connection, correct UA, proxy + failover)
→ curated channel profiles → Kodi (IPTV Simple for live TV) and Jellyfin (everything else).

## Two non-negotiables
1. **Never bypass Dispatcharr.** Kodi and Jellyfin only ever see `/output/m3u/...` and
   `/proxy/ts/stream/...` URLs.
2. **User data is written to `ChannelOverride`, never to `Channel`.** Provider sync rewrites
   `Channel.*` on every refresh; overrides survive.
