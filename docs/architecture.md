# Target architecture

## One rule

**If Dispatcharr can do it, we configure Dispatcharr. If it cannot, we write a plugin — never a
script.** Every layer below exists because the layer above genuinely cannot do the job.

| Layer | Runs | Owns | Must never |
|---|---|---|---|
| Dispatcharr config (UI / API) | platform | M3U accounts, EPG sources, channel profiles, stream profiles, DVR | — |
| Store plugins (`dispatcharr/data/plugins/`) | inside Dispatcharr | generic mechanics: name matching, EPG janitor, quality probing | house policy |
| **Our plugin** `kodi-lineup` | inside Dispatcharr | the policy that is actually ours: curated lineup, EPG binding rules, event-slot rules | generic mechanics already sold by the store |
| Host shell `ops/` | host | things that physically cannot run in the container (VOD sync trigger, container health) | writing Dispatcharr data |
| `docs/` + `adr/` | — | decisions and invariants | narrative session logs |

## Why the boundary sits there

Code inside the container gets the ORM, Celery, the event bus, settings, UI buttons, the app
logger — and survives `:latest` image updates. The old design lost on all four counts: it
patched `/app/core/xtream_codes.py` (timeout) and leaned on `apps/proxy/config.py` constants
that are wiped on recreate, it could not be tested, its cron failures were invisible, and it
accumulated six copies of one name normaliser.

## Repository layout (target)

```
dispatcharr-plugins/
  kodi-lineup/                 the only hand-written policy plugin
    plugin.json                manifest: settings fields + actions (+ event hooks)
    plugin.py                  Plugin.run(): lineup_apply, epg_rebind, event_slot_wire
    lineup.yml                 declarative curated lineup — the part that is genuinely ours
    names.py                   core(), region(), same_identity(), tier_score()
    policy.py                  pure functions: resolve(), pick_primary(), should_rebind()
tests/
  test_names.py                host-runnable, no Django, no container
  test_policy.py
scripts/
  deploy-plugins.sh            copy plugin dirs into dispatcharr/data/plugins + POST reload
ops/
  sync-vod.sh                  host-only, unchanged in spirit
docs/  adr/
```

`lineup.yml` exists because the curated lineup is a *policy statement*, not code: one entry per
channel (`number`, `group`, `match` rules, `exclude` rules). `build-kodi-profile.py` currently
expresses it as ~300 lines of Python tuple literals spread over a 425-line file.

## Data ownership (unchanged, now enforced in one place)

- Writes go to **`ChannelOverride`**; `Channel.*` is provider-owned and rewritten on every M3U
  refresh. Enforced by a single helper — nothing else in the codebase writes overrides.
- Effective EPG is `Coalesce(override.epg_data, channel.epg_data)`, so an override of `NULL`
  falls back to the provider binding. "No guide on purpose" must point at the dummy source.
  Mirror the platform's semantics; never re-derive them.

## Scheduling and events

- **No crontab entries for policy.** Recurring work is a plugin action triggered from the UI, a
  Celery beat task, or an **event hook** (`events: ["channel_error", "m3u_blocked"]`).
- The only host cron left is whatever `ops/` genuinely needs, and it must log its own failure.

## Testing strategy

`names.py` and `policy.py` are pure functions — pytest on the host, no Django bootstrap. That is
the first testable code this repo has ever had. Everything that touches the ORM is an action with
a `dry_run` setting and a `confirm` modal, and its first real run is checked against a read-only
query before it is allowed to write.

## Non-goals

- Re-implementing platform features: EPG matching mechanics, stream proxying, retry/failover
  internals, DVR.
- A custom HTTP client where a plugin can use the ORM directly (`Plugins.md` is explicit about
  this).
- Mirroring more of the Kodi box than the two files it actually needs
  (`advancedsettings.xml`, `keymaps/livetv.xml`).
- Backups. Removed by decision — see `adr/0002-drop-ai-backup-scaffolding.md`.
