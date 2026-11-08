# 0002 — Drop the AI-added backup, watchstate and cron scaffolding

- **Status:** accepted
- **Date:** 2026-11-07

## Context

The backup machinery was not a requirement of this stack; it was added while the stack was being
set up, and it has never been reviewed. Its current state:

- The 04:15 crontab entry runs `rsync … && sqlite3 … ".backup …" && ls -t | tail -n +8 | xargs rm`.
  The `.backup` step has produced **0-byte files since 2026-11-03** (and on 10-29) — 5 consecutive
  nights. A manual run of the identical command succeeds, so it fails only inside cron.
- Nothing records the failure: the entry redirects no stderr, there is no mail spool, and
  `journalctl -t CRON` logs only the command line.
- Because the chain is `&&`, the rotation step never ran either, so snapshots have been
  accumulating. The 7-newest rotation would have deleted the last two *valid* snapshots
  (Nov 1, Nov 2) within two nights.
- `watchstate` has been running since September and was never configured — 57 MB of an unused
  service.

`verify-stack.sh:108-110` asserts that backups are fresh, so it warns forever as soon as the cron
entry goes away.

## Decision

Remove the backup cron entry **and** the backup-freshness check in `verify-stack.sh` in the same
commit. Remove the `watchstate` service. Stop adding policy crontab entries as each script is
replaced. Do not build a replacement backup mechanism now; if one comes back, it comes back as a
decided feature with a test that fails when it produces an empty artefact.

The one thing that *is* kept is a source archive: the pre-rewrite code is frozen as the git tag
`legacy/pre-rewrite-2026-11-07` (plus a branch and an off-repo tarball). That is source history, not
data backup, and it costs nothing.

## Consequences

- Accepted risk: no off-box copy of Dispatcharr or Jellyfin state. Losing the volumes means
  re-importing both M3U accounts, re-running the EPG sources, and rebuilding the curated profile —
  a couple of hours, and watch history / DVR metadata are gone. Credentials live only in
  Dispatcharr's database, so they would have to be re-entered.
- `verify-stack.sh` (or its successor) stops reporting a signal nobody was acting on — it will only
  assert things we intend to fix.
- One service and one storage claim disappear from the host.
