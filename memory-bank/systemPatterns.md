# System Patterns (the non-obvious things that cost real time to learn)

## Dispatcharr internals
- **`ChannelOverride` is the only durable place for user edits.** Output resolves
  `Coalesce(override__epg_data, epg_data)` / `effective_name` / `effective_channel_group_obj`.
  Sync rewrites `Channel.*` every refresh.
- **Bind first, *then* refresh the EPG source.** `parse_programs_for_source` deliberately
  skips programmes for entries that no channel is mapped to — a fresh 4,456-entry feed looks
  empty until channels are bound. Binding auto-queues per-entry harvests via
  `dispatch_program_refresh_for_epg_ids`.
- **Blanking a binding needs a target, not NULL** — an override of NULL falls back to the
  provider binding. A `source_type='dummy'` source (`NO GUIDE`) is used for that; Dispatcharr
  then generates placeholder programmes named after the channel.
- **A single stream per channel is fragile.** Providers reset streams ~hourly and refuse the
  immediate reconnect (4XX). Failover only works if a `ChannelStream(order=1)` exists.
- **Provider-wide stream/API failures are usually the provider, not the stack.** Before
  touching bindings, curl 2+ unrelated channels' URLs: 502-on-all = origin outage (wait);
  403-on-player_api-only = rate limit from too many API calls (live streams keep working).
  The Xtream Library plugin with "all categories" selected trips the 403 block — keep the
  category selection tight and `RequestDelayMs` ≥ 250 until proven stable.
- **Jellyfin 10.11 plugin loading**: flat DLLs in `plugins/` are ignored; plugins need a
  `Name_version/` subfolder with the DLL + a `meta.json`. "Failed to load assembly ...
  incompatible version" = shared-library mismatch; try the next-oldest release.
- **jellyfin-kodi does not sync Jellyfin "channels"** — only native libraries. Any provider
  content that must reach Kodi has to land in Movies/TVShows libraries (STRM files work).
- **`max_streams` is Dispatcharr's own cap**, not the provider's. Was 1 (caused 503s on every
  zap), now 2.
- **Retries are hardcoded in-container** (`apps/proxy/config.py`: `MAX_RETRIES=3`,
  `RETRY_WAIT_INTERVAL=0.5`) — no env/DB override, so tuning them is not persistent. Data-level
  fixes (backups) were chosen instead.
- **Output M3U/EPG cache TTL is 2 s**, so changes appear immediately on re-fetch.
- Profile-scoped endpoints: `/output/m3u/<ProfileName>`, `/output/epg/<ProfileName>`.

## Kodi 21 (Omega) gotchas
- `inputstream.ffmpegdirect` **timeshift** and IPTV Simple **catchup** are known crash bugs
  ([#760](https://github.com/kodi-pvr/pvr.iptvsimple/issues/760), [#499](https://github.com/kodi-pvr/pvr.iptvsimple/issues/499)).
  Both are OFF here, and this subscription has no archive anyway.
- `advancedsettings` cache tags (`buffermode`, `readbufferfactor`, `maxchunksize`, …) **do not
  exist** in Kodi 21 — they were removed in the videoplayer merge. Cache tuning lives in
  guisettings (`filecache.*`).
- The **whitelist parsing is broken** in this build: 17 well-formed entries collapsed to one
  mode and every lookup answered "No match". Left empty (Kodi default = all modes).
- **jellyfin-kodi 2.x does NOT do Live TV.** Live TV always goes IPTV Simple → Dispatcharr;
  Jellyfin handles libraries/recordings. That is the intended architecture, not a workaround.
- Kodi Sync Queue needs matching ABI versions on server and client.

## Curation model
`build-kodi-profile.py` is the single source of truth for the client lineup:
- explicit curated picks (`LINEUP` + `EVENTS`) — these are **exempt from the no-guide sweep**
- bulk imports from provider groups, re-homed into clean groups with number ranges
- idempotent: adopts channels already in its groups; aborts if a run would shrink >10%
- `SWEEP_NO_GUIDE` moves guide-less bulk channels to a trailing `No Guide` group (9001+)
