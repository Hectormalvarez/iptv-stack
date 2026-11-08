# Inventory & disposition

Measured on the `legacy/pre-rewrite-2026-11-07` tag (2026-11-07). Baseline for every parity
gate in `plan.md`.

## Why it is being replaced

| Symptom | Measurement |
|---|---|
| Scripts are pipes, not a system | 19 files, ~3,019 lines; **zero imports between them** |
| Duplicated logic | **6** name normalisers (`add-backup-streams.py:65`, `swap-provider.py:74`, `remap-epg.py:98`, `apply-stream-quality.py:55/63/76`, `add-wnba-events.py:61`); **2** copies of `tier_score` (`audit-stream-quality.py:320`, `apply-stream-quality.py:82`) |
| No uniform "apply" gate | 9 different switches: `BACKUP_APPLY`, `FAILOVER_APPLY`, `REMAP_APPLY`, `LABEL_APPLY`, `AUDIT_PROBE`+`AUDIT_SCOPE`, … plus a **hardcoded** `DRY_RUN = True` in `build-kodi-profile.py:19` that the README claims is an env var |
| Untestable | no `tests/`, no `pyproject.toml`, no `requirements.txt`, no `Makefile` |
| Prose instead of contracts | ~25–33 % of every Python script is a docstring; the one real invariant ("write to `ChannelOverride`") is documented in prose in four files |
| Coupled to container internals | run via `docker exec … manage.py shell < file.py`; two scripts depend on patched/undocumented app internals |

## Scripts

| File | Lines | Disposition |
|---|---|---|
| `build-kodi-profile.py` | 425 | **Rewrite** → `kodi-lineup` plugin + `lineup.yml` (`lineuparr` for the group/number mechanics) |
| `audit-stream-quality.py` | 434 | **Adopt** `iptv-checker`; keep probing knowledge in `invariants.md` |
| `remap-epg.py` | 280 | **Adopt** `epg-janitor`; the call-sign/region policy stays ours as `epg_rebind` |
| `apply-stream-quality.py` | 204 | **Adopt** `underfed` / `stream-mapparr` |
| `swap-provider.py` | 205 | **Stage** — only if store mapping proves insufficient for a provider swap |
| `add-cross-provider-failover.py` | 142 | **Adopt** `automap-channelarr` |
| `add-backup-streams.py` | 135 | **Adopt** `stream-mapparr` |
| `label-event-slots.py` | 118 | **Adopt** `epg-and-sports-editor` / `event-channel-managarr` |
| `configure-event-epg.py` | 159 | **Delete** — pilot, never applied |
| `add-wnba-events.py` | 146 | **Delete** — single-season one-off, superseded |
| `pick-xtream-categories.py` | 80 | **Delete** — one-time VOD setup, done |
| `write-xtream-library-config.sh` | 67 | **Delete** — same |
| `verify-stack.sh` | 132 | **Replace** with `dispatcharr-exporter` (+ alerting), or keep as a thin probe |
| `sync-vod.sh` | 58 | **Keep** in `ops/` — genuinely host-side |
| `watch-kodi-wnba.sh` | 42 | **Delete** — session helper |
| `watch-xtream-sync.sh` | 46 | **Delete** — session helper |
| `watch-provider-recovery.sh` | 137 | **Delete** — superseded by the `channel_error` event hook |
| `cec-vizio-bringup.sh` | 99 | **Delete** — CEC is a closed dead end (IR-only remote, LE 12.2 libCEC regression) |
| `install-arctic-fuse3.sh` | 79 | **Delete** — skin never activated |
| `doexec.js` | 38 | **Delete** — the host has a docker CLI; the workaround outlived its reason |
| `scripts/__pycache__/` | — | **Delete** — stale bytecode |

Net: ~3,019 lines → roughly 250 (plugin) + 60 (host ops).

## Services, config, docs

| Item | Lines | Disposition |
|---|---|---|
| `docker-compose.yml` (dispatcharr, jellyfin, watchstate, cline-telegram) | 133 | **Keep**, minus `watchstate` (running since Sept, never configured; 57 MB) |
| `config/gai.conf` | 39 | **Keep** — non-obvious provider-egress fix, see `invariants.md` |
| `kodi/advancedsettings.xml`, `kodi/keymaps/livetv.xml` | ~40 | **Keep** — verified tag set for Kodi 21 only |
| `kodi/deploy.sh` | ~20 | **Keep** — two-file push |
| `cline-telegram/` | ~100 | **Keep** (working feature); `state/` stays gitignored |
| `docs/reference.md` | 1,296 | **Legacy** — facts migrate to `invariants.md`, then delete |
| `memory-bank/` | ~1,900 | **Legacy** — retired in favour of `adr/` + `plan.md` |

## Host crontab (iptv entries)

| Entry | Disposition |
|---|---|
| 04:15 rsync + jellyfin `.backup` | **Delete** — backups removed by decision (ADR-0002); `verify-stack.sh:108-110` must lose its backup-freshness check with it |
| 08:30 `verify-stack.sh` | **Delete or replace** by exporter/alerting |
| Mon 07:00 `remap-epg.py` | **Delete** — becomes an `epg_rebind` action / event hook |
| Mon 07:20 `add-backup-streams.py` | **Delete** — becomes plugin-driven |
| 09:00 `label-event-slots.py` | **Delete** — becomes `epg-and-sports-editor` rule |

Target: **no crontab entries for policy.** Only `ops/` gets one, and it logs its own failure.

## Parity baseline (what "we did not break it" means)

- Kodi box (`k5320.lan` → 192.168.1.182, Kodi **21.3**): PVR **1,680 channels / 24 groups**
- Dispatcharr profile `Kodi`: 1,680 members, **896 parked** in `No Guide`
- EPG: 3 sources `success`; coverage **90 %** (72 of 784 guide-expected blank)
- ESPN `#301` → EPGSHARE `ESPN HD` (3 sources attached); `#2086`/`#4628` still on the dead
  provider entry (known gap, fix in Phase 2)
- 475 channels carry ≥2 sources (failover depth)
- Containers: `dispatcharr`, `jellyfin`, `watchstate` reporting healthy
