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
- **A 403 on *every* endpoint (including live streams) can be address-family-specific.**
  2026-10-01: `cf.vovu.top` 403'd our egress **IPv4** but served **IPv6** (`curl -4` → 403,
  `curl -6` → 302, same URL/UA/host). A bridge container has **no IPv6 route**, so it could
  only try IPv4 and *everything* failed while the host looked fine. Diagnose by comparing
  families on the host, then check what the container can actually reach:
  `docker exec dispatcharr sh -lc 'getent ahosts cf.vovu.top; ip -6 route'` (empty `ip -6
  route` = no IPv6 egress). Fix is `network_mode: host` for Dispatcharr, not a provider wait.
  The trigger was the Xtream-Library VOD sync hammering `player_api.php`; the resulting ban
  outlived the documented ~15–45 min and escalated to live streams.
  The Xtream Library plugin with "all categories" selected trips the 403 block — keep the
  category selection tight and `RequestDelayMs` ≥ 250 until proven stable.
- **The banned family flips — don't hard-code "IPv6 is the good one".** 2026-10-04: IPv4
  answered normally (web root 401, live 302) while **IPv6** was 403'd — the reverse of
  2026-10-01. A third-party egress (r.jina.ai) got `401` on the web root, proving the provider
  was up and only *our* address was blocked. glibc sorts AAAA first, so a host-networked
  container kept hitting the banned IPv6 and every stream died. Fix: mount
  `config/gai.conf` (`precedence ::ffff:0:0/96 100`) into both containers so getaddrinfo
  returns A records first. A restart picks the wrong family again unless the mount is present.
  Quick check: `docker exec dispatcharr sh -lc 'getent ahosts cf.vovu.top'` — the IPv4 (A)
  rows must come before the IPv6 (AAAA) rows.
- **Jellyfin 10.11 plugin loading**: flat DLLs in `plugins/` are ignored; plugins need a
  `Name_version/` subfolder with the DLL + a `meta.json`. "Failed to load assembly ...
  incompatible version" = shared-library mismatch; try the next-oldest release.
- **The Xtream-Library plugin cannot be switched off through its config.** Its
  `GetDefaultTriggers()` *always* returns a trigger: `SyncScheduleType=Daily` gives a daily
  one, and **every other value — including `Manual` — falls through to an interval trigger**
  of `SyncIntervalMinutes` minutes, which **defaults to 60** when it is 0 or negative. So
  setting `Manual` only removed the daily line while the sync kept firing **hourly**; each run
  hammers `player_api.php` and re-trips the provider ban. The only config-only stop is a huge
  interval (`SyncIntervalMinutes=525600`, 1 year). Diagnose via the `"Sync Xtream Library"
  Completed ...` lines in the Jellyfin log and the `.snapshots/` mtimes. 2026-10-04.
- **`hidden_from_output=True` beats profile membership.** A channel can be enabled in a
  profile and still never appear in that profile's M3U; the output builder filters hidden
  channels. The provider's PPV event slots ship hidden (2026-09-21 cleanup) — unhide them.
- **The profile rebuild owns the membership list.** `build-kodi-profile.py` disables every
  membership it does not recognise, and sweeps any row without upcoming EPG to `No Guide`
  unless it is curated. A new group needs entries in `KODI_GROUPS` (adoption) *and*
  `CURATED_GROUPS` (sweep exemption) or the next run silently removes it.
- **`channel_number` is not unique across Dispatcharr.** Curated numbers can collide with
  provider-assigned ones (e.g. 368–375 are both WNBA slots and a PRIME group); harmless while
  only one of them is a profile member, but check before renumbering.
- **Kodi box: no SSH, DHCP address, only JSON-RPC.** Port 22 is closed on the LibreELEC box,
  so nothing can force an IPTV Simple playlist reload from outside (Kodi 21 has no JSON-RPC
  method for it). If JSON-RPC stops answering, scan the subnet before assuming the box is up
  — the last outage was the box being off, not the stack.
- **⚠️ Do NOT `Addons.SetAddonEnabled` on `pvr.iptvsimple` to force a playlist reload (2026-10-11).**
  It *does* reload the playlist — the new channel appeared (1,677 → 1,678) within seconds — but it
  also tears down whatever is playing and leaves Kodi's **player/app thread wedged**. Symptom
  pattern: `Player.Open` never returns (no body, curl exit 28), a random client connects to the
  proxy and drops within ~2–5 s, the on-screen player stays idle, and then *every* `Player.*` /
  `GUI.GetProperties` call blocks **while `JSONRPC.Ping`, `Input.ExecuteAction` and `System.Reboot`
  still answer `OK`** (they run on the RPC thread, not the app thread). `System.Reboot` is accepted
  and then never executed, because the shutdown is actioned by the stuck app thread — the box stays
  up and wedged. There is no remote recovery: with SSH auth refused, only a **power cycle at the
  box** clears it. Reload the playlist the supported ways instead: let the 10-min IPTV Simple
  refresh timer fire, or restart Kodi (needs SSH — see `progress.md`).
  Reading the blockage: RPC-thread methods answering + app-thread methods hanging = wedged player
  or a modal dialog, **not** a dead box and **not** a bad stream.
- **A wedged Kodi re-triggers on the next PVR channel open** (2026-10-11, second freeze). After the
  first wedge cleared, the box answered `Player.GetActivePlayers` with `{"result":[]}` — proof the
  app thread was alive again — and then a single `Player.Open` on the new channel wedged it a second
  time. So "reads work" ≠ "the player works": test with a **known-good channel** before blaming the
  new one. Ruled out for the new channel (410, WMAQ): catchup/timeshift (`is_catchup=False`,
  `catchup_days=0`, and the profile M3U contains **zero** `catchup` attributes), a malformed playlist
  entry (fetched with the *box's* Host so the URLs match what it really sees — byte-for-byte the same
  shape as the working 352 entry, no `localhost` URLs), and the stream itself (healthy through the
  proxy at ~10 Mbps, h264 720p30 + AAC-LC). **Confirmed 2026-10-11:** after a clean power cycle the
  very same channel opened first try and played, so the wedge is stale IPTV Simple/PVR state from the
  mid-session toggle — *not* the channel and *not* the stream. Bottom line: never toggle the addon to
  force a reload; if a wedge happens, the only fix is a restart at the box.
- **`max_streams` is Dispatcharr's own cap**, not the provider's. 1 caused 503s on every zap
  (→ 2 on 2026-09-21). Raised to **3** on 2026-10-01: with 2 a single zap already holds
  old+new, so there is **zero headroom** and any lingering/failed init — or Jellyfin's tuner
  taking a slot — 503s the next zap. A direct test showed the provider serves 3 concurrent
  streams. Symptom to recognise: `Profile 2 at max connections: 2/2` then
  `No stream available ... All active M3U profiles have reached maximum connection limits`.
- **Retries are hardcoded in-container** (`apps/proxy/config.py`: `MAX_RETRIES=3`,
  `RETRY_WAIT_INTERVAL=0.5`) — no env/DB override, so tuning them is not persistent. Data-level
  fixes (backups) were chosen instead.
- **The provider `xmltv` feed is short-horizon, so a stalled EPG refresh empties the guide fast.**
  `cf.vovu.top/xmltv.php` only carries ~11–14 h of programmes for the *mapped* channels, so the
  6-hourly refresh is the lifeline: a couple of missed runs and the guide drains to 0 for those
  channels (2026-10-04: coverage 98% → 10% after refreshes 403'd since the prior day). The programmes
  are **not wiped** — they age out (`ProgramData.max_end` freezes at the last successful parse). Recover
  by dispatching Dispatcharr's **own** `refresh_epg_data.delay(<id>, force=True)` (the UI refresh icon /
  `POST /api/epg/import/`); it re-downloads, re-parses and rebuilds the index. Verify with
  `EPGSource.status == 'success'`, a future `max_end`, and `verify-stack.sh`.
- **`/app/media` (MEDIA_ROOT, incl. `cached_epg/<id>.xml`) is ephemeral by design.** The official
  compose mounts only `/data`; the image's `docker/init/03-init-dispatcharr.sh` lists `/app/media` and
  `/app/static` under `APP_DIRS` ("live on the image layer"). So a container recreate wipes the cached
  EPG XML and `build_programme_index` logs `File not found for source N` until the next successful
  refresh — expected, **not** a bug to fix by mounting a volume.
- **M3U accounts refresh via `refresh_single_m3u_account.delay(<id>)`** (the UI refresh button); the XC
  account processes the full live catalog (~15.8k streams) in 11 batches in ~15 s. A `custom`/STD
  account with **no URL** stays `error` forever — an orphan worth deleting.
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
- **JSON-RPC needs `-u kodi:kodi` on every call** (`http://192.168.1.181:8080/jsonrpc`).
  Unauthenticated it answers `401 Unauthorized` with a **zero-length body** — indistinguishable
  from an unreachable host, and it reads like "the box is off" (2026-10-11 detour). Related traps:
  - `PVR.GetChannels` only accepts real `Item.Fields.Base` properties; `label` / `channelname`
    are rejected with `Invalid params`. Omit `properties` and you get `channelid` + `label`.
  - Group ids come from `PVR.GetChannelGroups` — `"alltv"` works, and `Sports: NFL` is **77**
    (as an integer).
  - **PVR `channelid` ≠ channel number** (the NFL slate is 5194–5213); resolve it before
    `Player.Open`, which takes `{"item":{"channelid":<int>}}`.
  - The box's DHCP address drifts — `k5320.lan` is the stable handle. `ul5420` (`192.168.1.107`
    / `.142`) also listens on 8080, so a port scan alone will point you at the wrong machine.
  - Play the real feed, not a restart: check `Player.GetProperties` — the position must resume
    at the live edge (35m56s for a game that kicked off 36 min ago), not at 0.

## Curation model
`build-kodi-profile.py` is the single source of truth for the client lineup:
- explicit curated picks (`LINEUP` + `EVENTS`) — these are **exempt from the no-guide sweep**
- bulk imports from provider groups, re-homed into clean groups with number ranges
- idempotent: adopts channels already in its groups; aborts if a run would shrink >10%
- `SWEEP_NO_GUIDE` moves guide-less bulk channels to a trailing `No Guide` group (9001+)
