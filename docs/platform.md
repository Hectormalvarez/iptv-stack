# Platform: what Dispatcharr already provides

Verified against the running `dispatcharr` container, **version 0.30.0**
(`/app/version.py`), on 2026-11-07. Everything here is a native feature we should be using
instead of re-implementing.

## 1. REST API

DRF, OpenAPI 3 schema at `GET /api/schema/` (~355 KB of JSON — the authoritative list).
Auth: JWT **or API key** (`apps.accounts.authentication.ApiKeyAuthentication`), permission
`IsAdmin`. A script on any machine can therefore drive the stack with an API key — no
`docker exec`, no container internals, no image coupling.

Endpoints that duplicate what `scripts/` does by hand today:

| Need | Endpoint |
|---|---|
| Set a channel's EPG binding | `POST /api/channels/channels/{id}/set-epg/` |
| Auto-match EPG for one / all | `POST .../channels/{id}/match-epg/`, `POST .../channels/match-epg/` |
| Bind many channels at once | `POST .../channels/batch-set-epg/` |
| Copy names / logos / tvg-ids from EPG | `POST .../set-names-from-epg/`, `.../set-logos-from-epg/`, `.../set-tvg-ids-from-epg/` |
| Bulk field edit (incl. overrides) | `PATCH .../channels/edit/bulk/` |
| Bulk edit by regex | `POST .../channels/edit/bulk-regex/` |
| Reorder a channel's sources | `POST .../channels/{id}/reorder/` |
| Create/attach channels from streams | `POST .../channels/assign/`, `.../from-stream/`, `.../from-stream/bulk/` |
| Channel numbers in a range / next free | `GET .../channels/numbers-in-range/`, `.../channels/ids/`, `.../channels/summary/` |
| Stream search + regex preview | `StreamViewSet`, `GET .../streams/regex-preview/`, `.../streams/by-ids/` |
| Group cleanup | `POST /api/channels/groups/cleanup/` |
| Plugin admin | `GET /api/plugins/plugins/`, `POST /api/plugins/plugins/reload/` |

Paths above are abbreviated after the first use; all live under `/api/channels/`.

## 2. Plugin system

- **Location:** `/app/data/plugins/<slug>/` inside the container = host
  `dispatcharr/data/plugins/<slug>/`. Override with `DISPATCHARR_PLUGINS_DIR`.
- **Shape:** `plugin.json` manifest (safe metadata, read without executing code) plus
  `plugin.py` (or a package `__init__.py`) exporting a `Plugin` class.
- **Interface:** `name`, `version`, `description`, `author`, `help_url`, `fields`
  (settings schema rendered by the UI: `boolean|number|string|text|select|info`),
  `actions` (each becomes a UI button; supports a `confirm` modal), `run(action, params,
  context)`, optional `stop(context)`.
- **Capabilities:** full ORM (`from apps.channels.models import Channel`), Celery
  (`refresh_m3u_accounts.delay()`, `refresh_all_epg_data.delay()`), WebSocket updates
  (`send_websocket_update`), `transaction.atomic()`, and a `logger` from `context`.
- **Lifecycle:** discovered at startup and on `POST /api/plugins/plugins/reload/`; code is
  only imported when the plugin is **enabled**; settings persist in `PluginConfig.settings`.
- **Constraints** (from `/app/Plugins.md`): the DB pool is `MAX_CONNS=8` per uWSGI worker —
  keep `run()` short, defer heavy work to Celery, and any thread/greenlet you spawn must
  `close_old_connections()` in its own `finally`.
- **Event hooks:** an action may declare `"events": ["channel_error"]`; those are dispatched
  from `log_system_event()` on a separate gevent. This is the native way to react to a dying
  stream, instead of a cron that polls.

## 3. Event bus (`apps/connect`)

`trigger_event(name, payload)` → `EventSubscription` rows → handlers, with a `DeliveryLog`
audit trail (request, response and error per delivery).

- **Integration types:** `webhook`, `api`, `script`.
- **Events (17):** `channel_start`, `channel_stop`, `channel_reconnect`, `channel_error`,
  `channel_failover`, `stream_switch`, `recording_start`, `recording_end`, `epg_refresh`,
  `m3u_refresh`, `client_connect`, `client_disconnect`, `login_failed`, `epg_blocked`,
  `m3u_blocked`, `vod_start`, `vod_stop`.
- **Payload templates:** per-subscription Jinja/Django template (webhook integrations).

This replaces "poll and retune" scripts: subscribe to `channel_error` / `m3u_blocked` and get
a logged, auditable delivery.

## 4. Official plugin store

Repo manifest: `https://dispatcharr.github.io/Plugins/manifest.json` (registered by
migration `0003_update_official_repo_url`), **36 plugins** as of 2026-11-07.

Candidates that overlap our own code. Each must be read before enabling (they run with DB
access), and none declare 0.30.0 compatibility in the manifest — verify at install.

| Plugin | What it claims | Replaces |
|---|---|---|
| `stream-mapparr` | adds matching streams to channels by name similarity + quality precedence | `add-backup-streams.py`, `apply-stream-quality.py` |
| `automap-channelarr` | deterministic rule-based mapper, pools per-M3U-group names | `add-cross-provider-failover.py` |
| `underfed` | moves a channel off a starving/drifting/refusing source to the next one | quality failover |
| `iptv-checker` | ffprobe status + quality, then rename/move/restore/delete | `audit-stream-quality.py` |
| `epg-janitor` | finds channels with EPG assignments but no programme data, auto-matches | `remap-epg.py` |
| `epg-and-sports-editor` | regex transform of EPG data, virtual channel copies | `label-event-slots.py` |
| `event-channel-managarr` | hides channels without events, shows those with events | manual event-slot wiring |
| `lineuparr` | creates groups/channels and mirrors real lineups | `build-kodi-profile.py` (groups/numbers) |
| `channel-name-cleaner` | strips `\| HD \|`, `(1080p)`, `[VIP]` style tags | name normalisation in several scripts |
| `dustarr` | records which channels are actually watched | ad-hoc "what's live" censuses |
| `could-not-dispatch` | placeholder when every source on a channel failed | black-slate handling |
| `audio-buffer-tuner` | faster startup for low-bitrate streams | zapping-latency work |
| `dispatcharr-exporter` | Prometheus metrics | `verify-stack.sh` monitoring |
| `m3u-expiration-notifier` | warns before an M3U account expires | renewal surprises |
| `telegram-alerts` / `newsflasharr` | route events to Telegram/Discord | notification glue |
| `stream-dripper` | drops active streams once a day at a set time | manual stream resets |
| `vod-probe` / `vod-manager` / `vod2mlib` | VOD quality probing, catalogue curation, STRM export to Jellyfin | Xtream-Library STRM setup |

**Adoption rule:** a plugin is accepted only if it reproduces today's behaviour on a real
check (see the gates in `plan.md`). Where it does not, the residual policy goes into our own
plugin — never back into a cron script.

