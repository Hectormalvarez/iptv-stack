# iptv-stack

> **Rewrite in progress.** The automation is being rebuilt plugin-first: configuration in
> Dispatcharr where the platform supports it, official store plugins for generic mechanics, and one
> small hand-written plugin for the policy that is ours. Start at [`docs/plan.md`](docs/plan.md)
> and [`adr/0001`](adr/0001-rewrite-plugin-first.md). Everything below that describes `scripts/` is
> the *current* (legacy) behaviour, frozen at tag `legacy/pre-rewrite-2026-11-07`.

A self-hosted live-TV stack: two IPTV subscriptions feed **Dispatcharr**, which normalizes
3,500+ raw channels into a curated lineup with a working guide, proxies every stream, and
serves it to **Jellyfin** and a dedicated **Kodi** box. This repo holds the compose file,
client configs, and the Python/shell automation that keeps it all curated and self-healing.

| Service | Port | Purpose |
|---|---|---|
| Dispatcharr | http://localhost:9191 | M3U/EPG management, stream proxying, DVR |
| Jellyfin | http://localhost:8096 | Media server, VOD libraries, Live TV tuner |
| cline-telegram | — | Telegram ↔ AI-agent bridge: message @bot, get a headless Cline session over this repo |

Both run with `network_mode: host` (provider blocks one address family; details in the
reference) and share an Intel Iris Xe GPU via VAAPI at `/dev/dri`. Only `watchstate` sits
on the `media-net` bridge.

## How it fits together

- **Two Xtream Codes providers.** The primary subscription feeds every channel; a second
  subscription is attached *only* as deep failover (`order=last`) on ~22 key channels, so a
  whole-provider outage no longer kills the lineup. Credentials live in Dispatcharr's
  database — never in this repo.
- **Curated channel profile.** Clients get a purpose-built Dispatcharr profile (~1,700
  channels in 22 clean groups, stable channel numbers), not the raw provider dump. Built
  idempotently by `scripts/build-kodi-profile.py`.
- **EPG pipeline.** Three XMLTV sources refreshed on 6–12 h cadence; a remap step matches
  guide entries to channels by normalized name (call-sign-aware, region-corrected) and
  writes bindings to `ChannelOverride` so they survive provider refreshes.
- **Streams always proxy through Dispatcharr.** Clients never talk to the provider directly:
  one pinned User-Agent, one connection budget, one place to audit.
- **Everything is dry-run by default.** Every mutation script prints its plan first and
  needs an explicit env var (`DRY_RUN=False`, `FAILOVER_APPLY=1`, …) to act.

## Repo layout

```
docker-compose.yml        Dispatcharr + Jellyfin + Watchstate, host networking, VAAPI
config/gai.conf           glibc address-selection policy (provider egress fix)
kodi/                     LibreELEC client: advancedsettings.xml, keymap, deploy.sh
scripts/                  automation (see index below)
docs/reference.md         deep dive: root causes, exact commands, gotchas per subsystem
memory-bank/              session log, decision log, progress tracking
```

## Scripts

Every script is idempotent and dry-run by default unless noted.

| Script | Purpose |
|---|---|
| `build-kodi-profile.py` | Builds the curated Dispatcharr channel profile + lineup numbers |
| `remap-epg.py` | Name-normalized EPG matching, writes `ChannelOverride` bindings |
| `add-backup-streams.py` | Attaches duplicate streams as failover sources (name-matched) |
| `add-cross-provider-failover.py` | Attaches the second subscription as deepest failover (explicit table, never fixture slots) |
| `label-event-slots.py` | Restores provider fixture names (`NFL: 1pm Chargers at Bills`) onto event channels |
| `add-wnba-events.py` | Creates dated WNBA event channels from the provider feed |
| `audit-stream-quality.py` | Read-only per-stream quality audit (fps/resolution/corruption, single ffmpeg pass) |
| `apply-stream-quality.py` | Reorders sources from the audit — conservative identity + region guards |
| `configure-event-epg.py` | Binds explicit-date event fixtures to dummy EPG entries (pilot) |
| `pick-xtream-categories.py` | Picks VOD categories for the Jellyfin Xtream library |
| `write-xtream-library-config.sh` | Writes the Xtream-Library plugin config (creds from Dispatcharr DB) |
| `sync-vod.sh` | On-demand VOD sync trigger (scheduled sync is off — provider rate limits) |
| `verify-stack.sh` | End-to-end health check: streams, EPG coverage, guide status |
| `watch-*.sh` | Live-tail helpers for provider recovery, Kodi playback, VOD sync |
| `cec-vizio-bringup.sh` | HDMI-CEC diagnostics for the Vizio TV |
| `install-arctic-fuse3.sh` | Installs/updates the Arctic Fuse 3 Kodi skin |

## Curated lineup (the "Kodi" profile)

| Range | Group |
|---|---|
| 101–106 | Austin Local (KXAN/FOX 7/KEYE/ABC/PBS/Spectrum News) |
| 201–239 | Entertainment |
| 301–319 · 321–367 | Sports + per-league (incl. 325 = NFL RedZone) |
| 401–409 · 501–507 · 601–604 · 701–704 | News / Kids / Movies / Spanish |
| 801–849 · 1201–1933 | Mexico / Mexico VIP |
| 2001–3388 | Sports: Networks, NBA, NFL, MLB, NHL, College, Soccer, Golf & Tennis, Motorsport, Combat, International, Events |
| 9001+ | No Guide (guide-less bulk channels) |

## Operations

```bash
docker compose config -q     # validate
docker compose up -d         # apply changes
docker compose logs -f dispatcharr
./scripts/verify-stack.sh    # full health check
```

Nightly Dispatcharr backups land in `./dispatcharr/data/backups/` — copy them off-box.

## Further reading

- **[`docs/README.md`](docs/README.md)** — the documentation index: platform capabilities,
  target architecture, inventory/disposition, invariants, plan, and ADRs.
- **[`docs/invariants.md`](docs/invariants.md)** — the provider/EPG/client facts that cost real
  outages to learn. Read this before touching anything.
- **[`docs/reference.md`](docs/reference.md)** — **legacy** (pre-rewrite) deep dive: root causes,
  exact commands, gotchas. Kept as the runbook until Phase 5.
- **[`memory-bank/`](memory-bank/)** — **legacy** session log from the pre-rewrite codebase.
