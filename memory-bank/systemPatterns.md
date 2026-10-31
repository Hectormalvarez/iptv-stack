# System Patterns (the non-obvious things that cost real time to learn)

## 2026-10-31 additions
- **ZQAVO `max_connections: 1` cuts both ways.** Promoting a ZQAVO source to order-0 primary
  (2026-10-31: `US-P| FOX Deportes HD` 1080p promoted onto #703 Fox Deportes over STRONG8K's
  720p) consumes the provider's only connection while watched — ZQAVO failover is unavailable
  elsewhere at that moment. Fine as a one-off quality upgrade; revert or accept it.
- **Host shell has no docker CLI and no python3** — see `techContext.md` → *This workspace's
  host*; use `scripts/doexec.js` (docker Engine API v1.52 over the unix socket).
- Verified again: provider stream **names lie**; the only honest comparison is a short ffmpeg
  probe through `/proxy/ts/stream/<hash>` (bytes, not status codes). ZQAVO `FOX Deportes HD`
  was 1080p/8.5 Mbps while the identically-named STRONG8K primary was 720p/4.2 Mbps.

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
- **A "backup" source can carry the WRONG FIXTURE — a multi-source count is not proof of a mirror.**
  `add-backup-streams.py` matches duplicates by stream *name*, and provider **network** feeds
  (`US: NFL NETWORK HD`, `US: NFL NETWORK ᴴᴰ`) are also duplicated by **event slots**
  (`NFL  | 4k - SNF 8:20pm Chiefs at Seahawks`). So #321/#2251 report 2 sources whose `order=1` is a
  *different game*: on a failover rotation the viewer silently gets tonight's SNF match instead of
  the one they tuned to. For anything with a per-fixture slot feed, the **slot channel is the correct
  primary**, and a network channel's slot "backup" is worse than no backup. Compare
  `ChannelStream(order=1).stream.name` against `order=0`'s fixture before trusting a source count.
- **Provider-wide stream/API failures are usually the provider, not the stack.** Before
  touching bindings, curl 2+ unrelated channels' URLs: 502-on-all = origin outage (wait);
  403-on-player_api-only = rate limit from too many API calls (live streams keep working).
- **An outage can present as "connecting forever", not as 502-on-everything.** 2026-10-25: every
  channel sat in `state: connecting` (KXAN #101, ESPN #301, RedZone #325, NFL slots #358/#361) with
  `Invalid data found when processing input` and `waiting for buffer to fill: 0/4 chunks` repeating,
  while the box dropped its client (`Broken pipe … (192.168.1.182)`) and ended with **no active
  player at all**. The tells that it was upstream, in the order that worked:
  1. **Is there an active player?** `Player.GetActivePlayers` → `[]` while `JSONRPC.Ping` → `pong`
     means "idle, not wedged" (a wedge hangs `Player.*` but still answers ping).
  2. **Are *unrelated* channels stuck too?** KXAN and ESPN failing alongside RedZone rules out the
     channel, the fixture and the failover set in a single step.
  3. **Probe the provider URL directly with the pinned UA, several times.** The *same* URL returned
     **407, then 502, then a connection timeout, then `200` with 53 bytes of HTML** — inconsistent
     non-video responses. A one-shot probe can succeed by luck and mislead you: mid-outage the same
     URL delivered a **12.8 MB burst and then 0 bytes nine seconds later**. So recovery needs
     *consecutive* good probes — `scripts/watch-provider-recovery.sh` requires `NEED_STREAK=2` and
     measures **bytes, not status codes** (the URL answered `200` with 53 bytes of HTML throughout).
  4. **Hit `player_api.php`** — it answered `{"error":"There is an Database Error","status":false}`,
     an origin-side error that no local change can fix.
  Confirmed *not* the problem: the web root answered **401 on both address families** (a ban is 403)
  and `getent ahosts cf.vovu.top` was still A-first (so not the family flip). Then wait — do not touch
  bindings. Watch the escalation shape: 502s ran 1/4/2/1 per hour for four hours, then **20 in one
  hour** at the peak.
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
- **A channel's feed is chosen by `ChannelStream.order` (0 = primary), and the provider's *naming*
  lies about quality (2026-10-11).** RedZone (`#325`) shipped with three sources whose names suggested
  the opposite of the truth:
  `US: NFL REDZONE ᴴᴰ` = **1280x720 @ 29.97 fps**, `TV: … ᴿᴬᵂ` and `AT&T: … ῧᴬᵂ` = **1920x1080 @
  59.94 fps**. Dispatcharr picks the lowest `order`, so the box was playing the 720p**30** feed and
  the user reported it "laggy" — 30 fps on fast sport motion. **For live sport, fps beats resolution:
  check with ffprobe (see below), never the name.** Fix is a data-level reorder of `ChannelStream.order`
  (decision #9 style). Durability is good: `build-kodi-profile.py` never touches `ChannelStream`, and
  `add-backup-streams.py` only *appends* links at the next free order — so a manual order survives both.
- **Changing `order` does NOT affect a live session.** The source is resolved when the channel session
  starts, and a client reconnect inside the **3 s grace window** reuses the old session
  (`Cancelled pending shutdown … reconnected`). To force the new source: `Player.Stop`, wait ~10 s until
  the log shows `Stopping channel <uuid>` + `Removed stream buffer`, then `Player.Open`. Confirm with
  the `assigned stream <id>` line.
- **A broken feed looks like "playing" on the box — check the proxy, not the player.** The promoted
  `TV:` RAW feed threw `Reconnecting in 0.25 seconds... (attempt 1/3)` then
  `ERROR … Packet corrupt (stream = 1, dts = …)`, and the result was a **black screen while Kodi
  happily reported `speed: 1`, `Fullscreen video`, a live `time` counter and a 1080p resolution**.
  So: player state `speed: 1` does **not** mean a picture is on screen. Grep the Dispatcharr log for
  `Reconnect|corrupt|Stream process error` on that channel UUID first. Corollary — **RAW variants
  (`ᴿᴬᵂ`) are not automatically better; they can be flat-out corrupt.** Order known-bad feeds last so
  failover lands on a working one.
- **Measure bitrate over ≥15 s, never 6 s** (2026-10-11): the provider bursts at connection start, so a
  short sample is wildly inflated — the same 720p30 feed read **15 Mbps over 6 s but 4.8 Mbps over 15 s**,
  and the *corrupt* `TV:` feed's 5.6 Mbps "lightest" reading was really a **stall** (1.75 Mbps). A low or
  erratic reading is a health alarm, not a bargain. Useful live-stream ffprobe invocation (plain `-t`
  is rejected): `-analyzeduration 3000000 -probesize 3000000 -select_streams v:0
  -show_entries stream=codec_name,width,height,avg_frame_rate`. Direct provider URLs answer **302** —
  curl needs `-L` and the pinned `TiviMate/5.1.6 (Android 12)` UA. After the
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
  **Ordinary channel switching is unaffected** — after the clean boot a plain
  `Player.Open` to `#410` and then to `#325` (RedZone) both returned `OK` immediately and the
  previous channel was torn down normally (`Marked channel <uuid> stopping`). So do not avoid
  `Player.Open` out of caution: it is only the addon toggle that breaks the box.
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
- **"Which game is on?" is answered by `ProgramData.description`, never by `title`.** The provider
  titles every national sports feed generically (`Live: College Football`, `NFL Football`) while the
  actual fixture sits in the description (*"The No. 7 Ole Miss Rebels visit the No. 19 Texas
  Longhorns for an SEC game"*). Enumerate a slate with
  `ProgramData.objects.filter(start_time__lte=now, end_time__gte=now, description__icontains=...)`
  and map it back through `ProgramData.epg_id` → `Channel.effective_epg_data_obj` (the join field is
  `epg`, not `epg_data`). A `title`-based search returns dozens of rows that all read the same and
  tells you nothing.
- **`US| NCAAF PPV`-style slot groups are stale on the *channel* name and current on the *stream*
  name.** The 82 slots all ship `hidden_from_output=True`, so none are ever in the Kodi profile, and
  `Channel.name` holds a *previous* week's fixture while `ChannelStream.stream.name` holds the
  current one — #7956's channel name says "UT Rio Grande Valley at UTSA" but its stream says
  "2pm Colgate at Richmond". `label-event-slots.py` only rewrites profile members, which is exactly
  why the two drift apart. Never quote a game from that group's channel name.
- **The container reports UTC, not America/Chicago**, from `timezone.get_current_timezone()`, even
  though `TZ=America/Chicago` is set in compose. Subtract 5 h for Austin before quoting a kickoff —
  a "23:30" programme is 18:30 CDT, and guessing the other way puts you 5 h out.

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

## Provider event streams (ZQAVO `:Nbc Sports NN` / `:Peacock Event NN`)
- **These event streams arrive UNATTACHED — raw `Stream` rows with no channel.** They are
  invisible to the channel list, the Kodi profile and every guide search; an agent asked to
  "find live games" will find nothing even though the stream exists. Find them with
  `Stream.objects.filter(name__iregex=r'@ Oct 3[12]|@ Nov ..')` — names carry the fixture and
  start time (`Liga MX: Chivas vs Atlante @ Oct 31 8:30 PM :Nbc Sports  16`), and unlike the
  NCAAF slots there is no stale channel name to mislead you.
- **Wiring pattern (2026-10-31)**: the disabled-but-in-profile VIX PREMIUM DEPORTES slot
  channels are the natural hosts — attach the event stream as `ChannelStream(order=0)`, demote
  the generic filler to order=1, set a `ChannelOverride.name` with the fixture, flip
  `hidden_from_output=False` and enable the profile membership. Done as a dry-run-first one-off;
  a generic `wire-event-stream` script is a pending item.
- **A pre-game probe returns 0 bytes — that is normal.** Event slots only serve video near the
  listed start time; re-probe then (bytes-not-status-codes applies as always).
- **EPG carries Liga MX under GENERIC titles — team-name searches find nothing.** Matches are
  listed as `Live: Fútbol Mexicano Primera División` (no teams, no league name in the title).
  Search by that phrase plus the time window instead. 2026-10-31 example: the 8:00–10:00 PM CT
  window (Monterrey vs Tijuana, 8:05 CT kickoff — note CDMX is UTC-6 year-round, so late-October
  CDMX times are Austin CT + 1 h) appears on ~17 epg ids (TUDN family, Univision, Canal 5
  locals); the TUDN `Liga MX en 60` rows are just the highlights loop.

## Cline ↔ Telegram bridge (`cline-telegram` container)
- **jq must be in the image.** `--allowed-user-id` is enforced by a shell hook
  (`jq -r .payload.actor.participantKey | grep -qx telegram:id:<id>`); without jq every message
  is denied "unauthorized", *including the allowed user*. Silent — nothing in docker logs.
- **`HOME` must point at the state volume.** The spawned connector child does not reliably
  inherit `--config`/`--data-dir` flags; it resolves `~/.cline` from `$HOME`.
- **Pin the hub port (`CLINE_HUB_PORT=25464`).** Host networking shares the host netns where
  the host's own Cline Hub binds 25463 — without the override the bridge tries to "retire" the
  HOST's hub. The `--rpc-address` flag does not reach the child; env vars do.
- **Run the connector foreground (`-i`).** In background mode the parent spawns a detached
  child and exits 0 — Docker kills the container (and child) and `restart: unless-stopped`
  loops it forever.
- **Clear stale connector/hub records at boot.** The state volume outlives the container, so
  pid-bearing records (`data/connectors/telegram/*.json`, `data/locks/hub`) from a previous
  boot make the parent exit with "connector already running".
- **Device-code auth needs a one-shot run.** The background launcher times out after 15 s,
  killing the device flow mid-handshake; run `cline auth cline` as a one-off container against
  the same `/state` volume, approve the code in a browser once, and the token persists.
- Read-only `~/.cline` can't be used directly (cline writes sessions/db/locks); the entrypoint
  seeds a minimal copy (secrets.json, providers.json, settings, CA bundle) into `/state`.
