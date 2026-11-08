# Rewrite plan

**Status:** Phase 1 (documentation) in review. Phase 2 not started.

| Phase | Goal | Exit criteria |
|---|---|---|
| **0** | Freeze the legacy tree | tag `legacy/pre-rewrite-2026-11-07`, branch `legacy/scripts-pre-rewrite`, both pushed, tarball off-repo — **done 2026-11-07** |
| **1** | Documentation first | this doc set + ADRs exist and are reviewed — **done 2026-11-07** |
| **2** | Strip | dead scripts, cron entries and the unconfigured service are gone; `verify-stack.sh` is still green apart from the known EPG gap; the box still plays a channel |
| **3** | Adopt store plugins | each candidate reproduces the script it replaces on the parity baseline, one commit per plugin |
| **4** | Build the `kodi-lineup` plugin | a preview action on the live line-up produces an **empty diff** — proof the declarative file reproduces today's 1,680-channel profile |
| **5** | Retire the legacy layer | `memory-bank/` + `docs/reference.md` deleted, README rewritten, crontab free of policy |

## Phase 2 — strip

Delete per `inventory.md`: `configure-event-epg.py`, `add-wnba-events.py`,
`pick-xtream-categories.py`, `write-xtream-library-config.sh`, the three `watch-*.sh`,
`cec-vizio-bringup.sh`, `install-arctic-fuse3.sh`, `doexec.js`, `scripts/__pycache__/`; the 04:15
crontab backup entry **together with** `verify-stack.sh:108-110`; the `watchstate` service.

While in there, fix the two known dead EPG bindings (`#2086 US: ESPN USA HD`,
`#4628 NCAAF 03: ESPNU`) — they are the same defect that made `#301` look broken.

**Gate:** `./scripts/verify-stack.sh` → only the known coverage `FAIL`; `Player.Open` on a live
channel returns `speed: 1`.

## Phase 3 — adopt, one at a time

Order chosen so each step is independently verifiable:

1. `epg-janitor` — covers `remap-epg.py`. Watch for: it must not unbind legitimate
   call-sign bindings, and must not undo the `NO GUIDE` parking.
2. `stream-mapparr` — covers `add-backup-streams.py`. Hard rule: **475 channels keep ≥2 sources**.
3. `underfed` — covers `apply-stream-quality.py`. Hard rule: an **event slot never becomes
   `order=0`**.
4. `event-channel-managarr` — covers the manual event-slot wiring.
5. `iptv-checker` — covers `audit-stream-quality.py`.
6. `lineuparr` — covers the group/number mechanics of `build-kodi-profile.py`.

Per plugin: read its source (it runs with DB access), install, configure, run in preview mode,
compare to the baseline, and delete the corresponding script **in the same commit**.

## Phase 4 — the `kodi-lineup` plugin

`plugin.json`, `plugin.py`, `lineup.yml`, `names.py`, `policy.py`, plus `tests/`.

First action is `lineup_preview`: a read-only diff of "what the YAML says" versus "what the
profile currently is". Until that diff is empty, nothing writes.

**Gate:** empty preview diff, plus `lineup_apply` on a rebuilt profile leaving the box with the same
24 groups and the same channel numbers it shows today.

## Phase 5 — retire

Delete `memory-bank/` and `docs/reference.md`, rewrite `README.md` around `docs/`, and update
`.clinerules` to the ADR + `plan.md` discipline instead of the session log.

## Verification commands that actually mean something

```bash
# containers
docker ps --filter name=dispatcharr --filter name=jellyfin

# profile + EPG (read-only)
./scripts/verify-stack.sh

# does the box actually play? (JSON-RPC)
curl -s -u kodi:kodi -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"Player.GetProperties",
       "params":{"playerid":1,"properties":["speed","live"]},"id":1}' \
  http://192.168.1.182:8080/jsonrpc

# is a feed really live? one decoded frame, then LOOK at it
ffmpeg -y -ss 5 -i http://localhost:9191/proxy/ts/stream/<hash> -frames:v 1 /tmp/f.jpg
```

## Rollback

`git checkout legacy/pre-rewrite-2026-11-07` restores every script, doc and config exactly as it
was. Store plugins are inert when disabled, so a bad adoption is a toggle, not a rebuild. The
off-repo tarball (`/mnt/storage/backups/iptv-stack/code/`) covers a lost repo.
