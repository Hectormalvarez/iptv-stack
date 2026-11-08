# 0001 — Rewrite plugin-first instead of script-first

- **Status:** accepted
- **Date:** 2026-11-07
- **Supersedes:** the entire `scripts/` approach in `docs/reference.md`

## Context

The stack works, but its automation is 19 standalone scripts (~3,019 lines) with **no imports
between them**, **six** implementations of name normalisation, **two** copies of the quality
tiering function, **nine** different "apply" switches, and **zero** tests. Every one of them runs
as a `docker exec … manage.py shell < file.py` heredoc, which:

- couples to container internals that are wiped on image update (`/app/core/xtream_codes.py`,
  `apps/proxy/config.py` constants),
- cannot be tested or type-checked outside a running container,
- fails invisibly when driven by cron (a nightly DB snapshot has produced 0-byte files for five
  days with no error anywhere to be found).

Meanwhile Dispatcharr 0.30.0 already ships the surface all of this was reaching for: an
OpenAPI-documented REST API with API-key auth, a plugin system that runs inside the app with ORM,
Celery, settings, UI actions and **event hooks**, an event bus with 17 events and delivery logs,
and an official store of 36 plugins — `epg-janitor`, `stream-mapparr`, `underfed`, `iptv-checker`,
`lineuparr` and others that overlap our scripts almost name for name (see `docs/platform.md`).

## Decision

Rebuild the automation **plugin-first**: configuration in Dispatcharr where the platform supports
it, store plugins for generic mechanics, and exactly one hand-written plugin (`kodi-lineup`) for
the policy that is genuinely ours — the curated line-up, the EPG binding rules, and the event-slot
rules. No policy code in crontab. No `docker exec` heredocs. Details in `docs/architecture.md`.

## Consequences

- The repo shrinks from ~3,000 lines to roughly 250 plus tests, and becomes testable for the first
  time (`names.py` and `policy.py` are pure functions).
- We inherit upstream maintenance for the mechanics and stop chasing image-update breakage.
- We take a dependency on third-party plugin code running with DB access: it must be read before
  it is enabled, and none of the store plugins declare 0.30.0 compatibility.
- Anything the store does *differently* from our policy becomes visible as a diff we have to
  decide about — which is the point, but it is real work in Phase 3.
- Existing behaviour is preserved only as far as the parity gates in `docs/plan.md` demand; drive-by
  features (WNBA event creation, CEC bring-up, skin installer) are dropped, not ported.
