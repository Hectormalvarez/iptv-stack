# iptv-stack

IPTV → Jellyfin media server.

| Service | Port | Purpose |
|---|---|---|
| Dispatcharr | http://localhost:9191 | M3U/EPG management, stream proxying, DVR |
| Jellyfin | http://localhost:8096 | Media server & clients |

Both share the `media-net` Docker network and an Intel Iris Xe GPU (VAAPI) at `/dev/dri`.

## Provider (strong8k)

Xtream Codes portal: `http://cf.vovu.top` — credentials live in Dispatcharr's M3U account (UI: M3U & EPG Manager). Do **not** commit them here.

- The `get.php` M3U endpoint returns empty for plain curl; Dispatcharr imports via the XC API (`type=XC`), which works fine.
- The XMLTV EPG (`/xmltv.php`) contains 4,423 channels with IDs like `SkySportsNews.uk` — country-suffixed, and mostly **not** matching the XC stream `tvg-id`s. Bulk name matching is required (below).

## EPG setup (already done, documented for reference)

The provider's EPG channel IDs don't match the M3U `tvg-id`s, so the guide shows placeholders until you bulk-match:

1. **Channels page → toolbar menu (⋮) → Auto-Match EPG** → default settings → Start.
   Matches all channels without EPG by name. ~14k channels takes ~45 min (background celery task).
2. Fix leftovers manually: channel row EPG dropdown, or select rows → bulk EPG assign.
3. EPG source refreshes every 24h (M3U & EPG Manager → EPG row → edit).
4. If programs are shifted by hours, adjust the EPG timezone offset in the EPG source settings.

## Jellyfin Live TV hookup

Use the **container names** over `media-net` (traffic stays internal). Jellyfin's Live TV is configured as:

- **Tuner: "M3U Tuner"** → `http://dispatcharr:9191/get.php?username=<dispatcharr-user>&password=<xc-token>&type=m3u_plus&output=ts`
- **Guide: XMLTV provider** → `http://dispatcharr:9191/xmltv.php?username=<dispatcharr-user>&password=<xc-token>`

The `xc-token` is the per-user XC API password in Dispatcharr (Users → user → set/generate "xc_password"; it is separate from the login password). The plain `/hdhr` endpoint returns 401 without HDHR device auth — do not use it.

Then Jellyfin → Dashboard → Live TV → "Refresh Guide Data" (the 84 MB XMLTV with ~14k channels takes a few minutes).

## Hardware transcoding (VAAPI, Intel Iris Xe)

Both containers have `/dev/dri` mounted. In Dispatcharr create a Stream Profile:

- Command: `ffmpeg`
- Parameters: `-user_agent {userAgent} -hwaccel vaapi -hwaccel_output_format vaapi -hwaccel_device /dev/dri/renderD128 -i {streamUrl} -c:a aac -c:v h264_vaapi -f mpegts pipe:1`

In Jellyfin: Dashboard → Playback → Transcoding → enable VAAPI, device `/dev/dri/renderD128`.

Notes (2026-09-21):

- The agent must be told the provider's UA — Dispatcharr injects `{userAgent}` from the M3U account.
- The container's ffmpeg lists `vaapi`/`qsv` and sees `/dev/dri/renderD128`.
- A client-requested `output_profile` only takes effect when the channel is **not** already streaming on
  another profile — Dispatcharr multiplexes extra clients onto the existing branch. Don't judge a
  profile by requesting it for a channel that's already playing.
- For the LAN Kodi box, **no transcoding is wanted**: the Latitude hardware-decodes H.264/HEVC itself,
  so the default `-c copy` remux profile (id 1) is what's actually used.

## Channel cleanup (2026-09-21)

14,936 → **3,590 visible channels, all with EPG**. Junk is *hidden* (`hidden_from_output=True`), never deleted — auto-sync keeps them updated and never re-creates them, and they can be un-hidden from the Channels page (filter "Hidden Only"). Hidden so far:

1. Separator-name channels (`#####...#####`) — 147
2. Channels with no streams — 1,118
3. Dated one-shot PPV/event channels (name contains `(YYYY-MM-DD ...`) — 1,750
4. All remaining channels without EPG — 8,346

SQL equivalent (inside the container):

```python
from apps.channels.models import Channel
Channel.objects.filter(name__regex=r'^#+').update(hidden_from_output=True)
Channel.objects.filter(streams__isnull=True).update(hidden_from_output=True)
Channel.objects.filter(name__regex=r'\(20[0-9]{2}-[0-9]{2}-[0-9]{2}').update(hidden_from_output=True)
Channel.objects.filter(epg_data_id=None).update(hidden_from_output=True)
```

After cleanup: Jellyfin → Live TV → "Refresh Guide Data" (or Scheduled Tasks → Refresh Guide) so the tuner re-imports the shrunken playlist.



- Dispatcharr DVR output → `/data/recordings_host` → host `/mnt/storage/recordings` → Jellyfin sees it at `/recordings`.

## Operations

```bash
docker compose config -q     # validate
docker compose up -d         # apply changes
docker compose logs -f dispatcharr
```

Dispatcharr admin account: `hadev` (password reset via `manage.py set_password` if lost).
Nightly Dispatcharr backups: `./dispatcharr/data/backups/` — copy these off-box.

## Kodi client (LibreELEC on Dell Latitude 5320)

**Architecture:** Jellyfin-first for VOD (`jellyfin-kodi` addon syncs Movies/TV/Recordings/watch-state), `pvr.iptvsimple` for Live TV pointed at a **curated Dispatcharr channel profile**. Kodi 21 Omega / LibreELEC 12.2.1.

### Curated lineup for the client (the "Kodi" channel profile)

The box does **not** get all 3,590 channels. Dispatcharr serves it a curated
**Channel Profile** whose playlist is defined in
`scripts/build-kodi-profile.py` (dry-run by default; `DRY_RUN=False` applies it):

| Range | Group | Contents |
|---|---|---|
| 101–106 | Austin Local | KXAN (NBC), FOX 7 (KTBC), KEYE (CBS), ABC stand-in (KTRK Houston — no KVUE feed on this provider), PBS, Spectrum News Austin |
| 201–239 | Entertainment | YouTube-TV-style bundle: USA, TNT, TBS, FX/FXX, AMC, BBC America, Comedy Central, Syfy, Bravo, TBS-family, HGTV, Food, Discovery, History, A&E, Lifetime, Hallmark, TruTV, ID, Nat Geo, Animal Planet, Travel, Freeform, Oxygen, WE tv, IFC, Sundance, BET, CMT, MTV Live, Cooking, Destination America, Magnolia, Reelz, MotorTrend, Outdoor |
| 301–319 | Sports | ESPN, ESPN 2/News/USA, CBS Sports, FOX Sports 1/2, beIN, Spectrum Sports 1, YES, SNY, MSG, Bally Ohio, Premier League, Willow Cricket, UFC, WWE, Fight Sports, Sky Sports F1 |
| 321–367 | Sports: NFL / NBA / MLB / NHL / College / Golf & Tennis | league networks plus the provider's live game slots, renamed from `NBA 06 :`/`NFL  \| 02 -` to `NBA Live 1`/`NFL Live 2` etc. **These are event feeds: live during games, dark (and erroring) otherwise** — verified streaming during an active window and dead 15 min later. Reliable league networks come first, slots sit at the end of each group. Optional hardening: attach the duplicate slot streams to the same channel in Dispatcharr so failover has a second source. |
| 401–409 | News | CNN, Fox News, MSNBC, CNBC, Bloomberg, Newsmax, HLN, Weather Channel, BBC World |
| 501–507 | Kids | Nickelodeon, Nick Jr, Disney, Disney Jr, Cartoon Network, Boomerang, PBS Kids |
| 601–604 | Movies | Starz, Showtime, MoviePlex, TCM |
| 701–704 | Spanish | Univision (Miami), Telemundo 51, Fox Deportes, TUDN Zona |

Result on the box: **123 channels / ~3,000 EPG entries** instead of 3,590 / 84,000
— the guide loads instantly and number entry zaps directly ("1 0 1" → KXAN).

Client endpoints (these are what `pvr.iptvsimple` uses):

```
http://usrv-01:9191/output/m3u/Kodi
http://usrv-01:9191/output/epg/Kodi
```

Jellyfin keeps the full `/output/m3u` + `/output/epg` (no profile) — the two
clients are independent.

**Changing the lineup:** edit the `LINEUP` list (number, group, aliases, prefer)
or `EVENTS` (provider name → clean name) in `scripts/build-kodi-profile.py`, run
the dry run to review the picks, then set `DRY_RUN=False` and re-run. The script
is idempotent, so re-running is safe. Partial channels are fine — the resolver
scores candidates (US feeds preferred, `PPV`/`24-7`/`test` excluded).

**Watch out:** renaming/numbering here is global (Jellyfin's guide sees the same
names/numbers). Also, `channel_number` is only unique *per group* in Dispatcharr,
so always select the curated set **by group membership**, not by number range —
provider channels in other groups already use numbers 101–704.

### What's installed

| Component | Source | Notes |
|---|---|---|
| `jellyfin-kodi` 2.2.0 | repo.jellyfin.org (manual zip) | deps vendored: requests+urllib3 1.26.16, certifi, idna, charset_normalizer (PyPI), websocket, typing_extensions, unidecode, simplecache, simpleeval |
| `pvr.iptvsimple` | preinstalled | instance 1 → **curated profile** `http://usrv-01:9191/output/m3u/Kodi` + `/output/epg/Kodi`, refresh 51 min (never `direct=true` — see below) |
| `skin.estuary.modv2` 21.4 | b-jesch GitHub (Omega branch) | needs script.skinshortcuts 2.0.3 + pvr.artwork + image.resource.select |
| Wi-Fi power-save | off (runtime + systemd unit `wifi-powersave-off.service` in `/storage/.config/system.d/`) | fixes periodic drop-offs |
| `pvr.iptvsimple` config | userdata | `catchupEnabled=false`, `allChannelsCatchupMode=0`, `timeshiftEnabled=false` — deliberately off, see below. Backups: `/storage/backups/instance-settings-1.xml.pre-*` |
| `guisettings.xml` tweaks | userdata | `pvrmanager.usebackendchannelnumbers=true`, `pvrplayback.confirmchannelswitch=false` (instant zap) |

### Zapping / concurrent streams (root-caused and fixed 2026-09-21)

Symptom: channel switches often failed or took ~40 s, with Dispatcharr logging
`503 {"error": "All active M3U profiles have reached maximum connection limits"}`.

Root cause: **the M3U account profile capped Dispatcharr at one upstream
connection** (`M3UAccountProfile id=2 "STRONG8K Default".max_streams = 1`). A
channel switch then races — Kodi requests the new channel while the old stream
still holds the only slot — and Dispatcharr refuses until Kodi gives up and
releases the old stream.

The provider itself is **not** the constraint: raising the cap to 2 and pulling
two different channels at the same time streamed both (`150000` bytes each,
`Successfully obtained stream ... after 1 attempts`). So `max_streams` is now **2**:

- Zaps get the stream on the first attempt (~8 s including Dispatcharr's ~5 s
  buffer fill) instead of ~38 s of retry loops.
- Kodi and Jellyfin can watch different channels at the same time.

Supporting tuning in `CoreSettings` → `proxy_settings` (UI: System → proxy):

| Setting | Was | Now | Why |
|---|---|---|---|
| `channel_shutdown_delay` | 0 | 3 | at 0 the channel is torn down the instant Kodi drops a connection, so a retry hits `Channel ... unavailable. Teardown or pending shutdown` and Kodi gives up |
| `channel_client_wait_period` | 5 | 10 | keeps a ready channel alive while the client re-attaches |

**Do not** raise `retry_timeout` in `apps/proxy/live_proxy/views.py` (upstream
value: `3`, with `retry_interval = 0.1`). A longer budget was tested and made
things *worse* (zaps went from ~10 s to ~38 s): Kodi blocks on Dispatcharr's HTTP
response, so while Dispatcharr waits, Kodi never releases the old stream — the
fast-fail path is what lets Kodi drop the old channel and retry cleanly.

Caveat: the subscription is advertised as a single connection. Two concurrent
streams work in practice, but if the provider tightens enforcement, set
`max_streams` back to 1 (Channels → M3U account → profile) and expect slower
switching; a 2-connection plan would remove the trade-off entirely.

### Stream path: always proxy through Dispatcharr (fixed 2026-09-21)

The client previously fetched streams **direct** (`direct=true`), i.e. Kodi connected straight to
`cf.vovu.top` with Kodi's own User-Agent. That caused random 502s and crashes because of two
provider-side facts, both verified:

1. The STRONG8K account allows **one simultaneous connection** (`M3UAccount.max_streams = 1`).
   Kodi's playback plus its extra probe requests (`CCurlFile::Exists`) plus Jellyfin's tuner all
   competed for that single slot.
2. The provider pins the **User-Agent** (`TiviMate/5.1.6 (Android 12)`). Requests with any other
   UA return an empty 502 response.

Pointing the client at `/output/m3u` (proxied, **no** `direct=true`) fixes both: Dispatcharr holds
exactly one upstream connection with the correct UA, multiplexes all clients onto it, buffers ~5 s
server-side, and serves the stream over the LAN. Verified: the box pulled
`http://usrv-01:9191/proxy/ts/stream/<uuid>`, buffered (`buffer ready (86/4 chunks) -> active`),
and played with no new `VideoPlayer` segfaults and zero log errors.

### Why catchup and timeshift are OFF

Both were enabled during setup and both are **crash sources here**:

- **Catchup is impossible on this subscription.** The XC API reports `tv_archive=1` on **0 of
  15,830** streams, and Dispatcharr's derived `Channel.is_catchup` is 0 channels. With catchup
  enabled Kodi still builds timeshift URLs, gets 502s and freezes —
  [pvr.iptvsimple#499 *"Using Catchup on unsupported channels causes kodi to crash/hang"*](https://github.com/kodi-pvr/pvr.iptvsimple/issues/499).
- **Timeshift freezes Kodi Omega** —
  [pvr.iptvsimple#760 *"Kodi (Omega) freeze and/or crash when using Timeshift"*](https://github.com/kodi-pvr/pvr.iptvsimple/issues/760), still open.
  The crash backtrace we captured matched this path: `VideoPlayer` segfault with frames in
  `inputstream.ffmpegdirect → CURL::Parse` and `pvr.iptvsimple.so.21.11.0`.

The provider's *Xi* archive is re-checkable any time — if a future subscription advertises
archives, re-enable catchup (`catchupEnabled=true`, `allChannelsCatchupMode=4`) since the XC
catchup URL pattern then works.

Time-shifted viewing instead comes from **Dispatcharr's DVR** (schedule recordings server-side;
they appear in Jellyfin/Kodi through the jellyfin-kodi addon).

### Startup, buffering, sync and backups (2026-09-21)

**Startup — boots into the TV guide.** `lookandfeel.startupwindow = 10702` (TV Guide;
window IDs from Kodi's `WindowIDs.h`: TV Channels 10700, TV Recordings 10701, **TV Guide 10702**,
Timers 10703, Search 10704, Home 10000). `lookandfeel.startupaction = 0` (None) — set it to
*Play TV* in Settings → Interface → Startup if you'd rather it starts playing immediately.
Verified: after a Kodi restart, `XBMC.GetInfoLabels(["System.CurrentWindow"])` → `TV guide`.

**Buffering — Kodi was not caching HTTP streams at all.** Kodi's default
`filecache.buffermode = 4` is `CACHE_BUFFER_MODE_NETWORK`, and the decision in
`xbmc/filesystem/File.cpp` is:

```cpp
if ((mode == CACHE_BUFFER_MODE_INTERNET      && IsInternetStream(path, true)) ||
    (mode == CACHE_BUFFER_MODE_TRUE_INTERNET && IsInternetStream(path, false)) ||
    (mode == CACHE_BUFFER_MODE_NETWORK       && IsNetworkFilesystem(path)) ||   // SMB/NFS only!
    (mode == CACHE_BUFFER_MODE_ALL           && (IsNetworkFilesystem(path) || IsHD(path))))
  m_flags |= READ_CACHED;
```

`IsNetworkFilesystem()` is true only for streamed filesystems/SMB/NFS, so **plain `http://` IPTV
streams were never cached** with the default. The enum (from `filesystem/IFileTypes.h`) is
deliberately non-sequential, which is why the GUI order is misleading:

| GUI label | Value |
|---|---|
| Buffer all internet filesystems (FTP, WebDAV…) | 0 `INTERNET` |
| Buffer all filesystems (incl. local) | 1 `ALL` |
| **Only buffer true internet streams (HTTP, HTTPS)** | **2 `TRUE_INTERNET`** |
| No buffer | 3 `NONE` |
| Buffer all network filesystems (SMB, NFS) | 4 `NETWORK` ← Kodi default |

Applied via JSON-RPC `Settings.SetSettingValue`:

| Setting | Was | Now |
|---|---|---|
| `filecache.buffermode` | 4 (network filesystems — http uncached) | **2** (true internet → http/https cached) |
| `filecache.memorysize` | 20 MB | **64 MB** |
| `filecache.readfactor` | 400 (fixed 4x) | **0 = Adaptive** (aggressive while empty, ~1.5x when full) |
| `filecache.chunksize` | 131072 (128 KB) | unchanged (already the sensible default) |

Playback start is unchanged after this (measured 5 s from cold), zero new errors.

**Jellyfin → Kodi sync.** Installed **Kodi Sync Queue** on the server, which Jellyfin's docs
recommend with library mode so Kodi gets library changes without waiting for a periodic re-sync.
Use the version whose ABI matches the server — on Jellyfin 10.11.11 that is **15.0.0.0**; the
catalog's 7.0.0.0 (ABI 10.8) installs but reports `NotSupported` and does nothing:

```bash
TOKEN=$(curl -s -X POST http://localhost:8096/Users/AuthenticateByName \
  -H 'Content-Type: application/json' \
  -H 'Authorization: MediaBrowser Client="cli", Device="cli", DeviceId="cli", Version="1.0"' \
  -d '{"Username":"root","Pw":"<jellyfin-root-password>"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessToken"])')
curl -s -X POST 'http://localhost:8096/Packages/Installed/Kodi%20Sync%20Queue?version=15.0.0.0' \
  -H "Authorization: MediaBrowser Token=\"$TOKEN\""      # then restart Jellyfin
```

Verify with `GET /Plugins` → `"status": "Active"`, and remove a stale
`/config/plugins/Kodi Sync Queue_<oldversion>` folder if one is left behind.

**Kodi config backups (box side).** Daily systemd timer on the box:
- script `/storage/.config/kodi-config-backup.sh`
- units `/storage/.config/system.d/kodi-config-backup.{service,timer}` (`OnCalendar=daily`, `Persistent=true`)
- output `/storage/backups/kodi/kodi-config-<YYYYmmdd-HHMM>.tar.gz`, last 7 kept
- contains `userdata/` (settings, databases, `addon_data/`, keymaps) + `addons/`, excluding
  `Thumbnails`, `Textures*`, `temp` and addon `resources`

  Restore: extract into `/storage/.kodi/` with Kodi stopped.

**PVR artwork.** `script.module.pvr.artwork` is installed and powers guide/OSD/NextUp art. Channel
logos already come from Dispatcharr (`tvg-logo` → Kodi channel icons). Poster/fanart/metadata
enrichment additionally needs a **TMDB API key** (and optionally fanart.tv) entered in the module's
settings — not configured yet.

### Skin trial: Arctic Fuse 3 installed alongside Mod V2 (2026-09-21)

`skin.arctic.fuse.3` 3.3.1 (jurialmunkey — the skin family most "customised Kodi boxes" run) is
**installed but disabled**, so Mod V2 stays active until you switch at the TV. It has its own addon
ID, so both coexist and every Mod V2 setting is untouched; falling back is just picking Mod V2 again.

Installed into `/storage/.kodi/addons/`:

| Addon | Version | Source |
|---|---|---|
| `repository.jurialmunkey` | 3.4 | `jurialmunkey.github.io/repository.jurialmunkey/repository.jurialmunkey-3.4.zip` |
| `skin.arctic.fuse.3` | 3.3.1 | that repo → `omega/zips/skin.arctic.fuse.3/…-3.3.1.zip` |
| `script.skinvariables` | 2.2.4 | repo |
| `script.texturemaker` | 0.2.11 | repo |
| `plugin.video.themoviedb.helper` | 6.17.3 | repo (widget/metadata engine) |
| `script.module.jurialmunkey` | 0.2.35 | repo |
| `script.module.infotagger` | 0.0.9 | repo |
| `resource.font.robotocjksc` | 0.0.3 | repo — **its zip ships the folder misspelled** as `resource.font.robotcjksc`, renamed to match the declared ID or the skin's dependency is unmet |
| `script.module.addon.signals` | 0.0.6+matrix.1 | `mirrors.kodi.tv/addons/omega/` |
| `script.module.qrcode` | 6.1.0+matrix.3 | Kodi repo |
| `resource.images.weathericons.white` | 0.0.6 | Kodi repo |
| `resource.images.studios.coloured` | 0.0.24 | Kodi repo |

`script.skinvariables`, `script.texturemaker` and `plugin.video.themoviedb.helper` were enabled via
JSON-RPC (`Addons.SetAddonEnabled`). The skin was deliberately **not** enabled — switching skins
headlessly is what left Mod V2 half-configured earlier, so that step belongs at the TV. Verified:
`Addons.GetAddonDetails skin.arctic.fuse.3` → `broken: false` (all dependencies satisfied),
active skin still `skin.estuary.modv2`, 0 log errors, no new segfaults.

**To try it:** Settings → Interface → Skin → *Arctic Fuse 3*. First load runs its hub/shortcut
setup and regenerates artwork, so it is slow once. Use ←/→ on the top bar for its hubs — the
prebuilt **Live TV hub** is the natural home for the PVR side.
**To revert:** Settings → Interface → Skin → *Estuary Mod V2*, or
`Settings.SetSettingValue {"setting":"lookandfeel.skin","value":"skin.estuary.modv2"}`.

AF3 is alpha; extra ratings need a free OMDb/MDbList key in TMDb Helper settings. It matters long
term because **Estuary Mod V2 cannot run on Kodi 22 (Piers)** — it requires Skinshortcuts 2.x, which
Piers replaces — while AF3 is maintained for both.

### Verifying client changes headlessly

The box can be tested without the TV:

```bash
# list channels, play one, confirm it is playing
curl -s -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"PVR.GetChannels","params":{"channelgroupid":"alltv","limits":{"start":0,"end":6}}}' http://192.168.1.181:8080/jsonrpc
curl -s -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":2,"method":"Player.Open","params":{"item":{"channelid":1402}}}' http://192.168.1.181:8080/jsonrpc
curl -s -u kodi:kodi -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":3,"method":"Player.GetActivePlayers"}' http://192.168.1.181:8080/jsonrpc

# crash check: compare before/after (must not increase)
ssh root@192.168.1.181 'dmesg | grep -ci segfault; grep -cE ERROR /storage/.kodi/temp/kodi.log'

# which URL the client actually plays (should be the Dispatcharr proxy, never cf.vovu.top)
ssh root@192.168.1.181 'grep -oE "Live Stream URL: [^ ]*" /storage/.kodi/temp/kodi.log | tail -1'
```

Edit addon settings in `userdata/addon_data/pvr.iptvsimple/instance-settings-1.xml`, then
`systemctl stop kodi; <edit>; systemctl start kodi` — stop Kodi first, otherwise it rewrites the
file on exit.

### PVR behavior

- Backend channel numbers (provider `tvg-chno`) are used — number entry on remote/Kore zaps directly.
- Channel switch is instant (no confirm dialog).

### Remaining customizations (not yet done)

- Custom channel groups file, per-channel `tvg-shift` for region-mismatched EPG (only if observed), favourites widget row in Mod V2, Kore PVR remote mode check.
- Parental PIN: N/A — no adult groups in the lineup.
- Genre display: `useEpgGenreText=true` — guide shows provider EPG category text.
- Channel logos: served by Dispatcharr (`/api/channels/logos/<id>/cache/`), verified HTTP 200.

## Automation & sync (phase 2 proposal)

Deployed:
- **watchstate** (`:8081`) — watch-state sync between Jellyfin (and later other backends). Setup: open WebUI → create system user → add Jellyfin backend (two-way) → Dashboard → Webhooks → point at `http://watchstate:8081/ws/{key}`. Scheduled import runs hourly by default.
- **Backups**: host cron (04:15 daily) → Dispatcharr backup zips + Jellyfin SQLite snapshot → `/mnt/storage/backups/iptv-stack/`, 7 DB snapshots retained.

Not yet deployed (needs interactive setup + decisions):
- **Prowlarr + Sonarr + Radarr + Seerr** (`linuxserver` images): indexers → automation → requests. Seerr (formerly Jellyseerr, now "seerr") gives discovery/requests UI wired to Jellyfin auth; Sonarr/Radarr download into `/mnt/storage/tv` and `/mnt/storage/movies` which Jellyfin + jellyfin-kodi pick up automatically. Requires an indexer/usenet/torrent source decision.



### Known gotchas

- **Python module addons are not importable until Kodi restarts** after filesystem installation.
- **skinshortcuts builds its include file on first skin load** — first switch may fail once, then retry.
- Manual first-login in jellyfin-kodi 2.2.0 crashes with `KeyError: 'address'` (server_id unset); patched `connection_manager.get_server_info()` to fall back to the first saved server.
- Web/JSON-RPC credentials on the box: `kodi`/`kodi` (kodi.log reveals them if changed).

### Home screen curation (Mod V2)

Estuary Mod V2 ships looking similar to stock Estuary — the customization is in **skin settings → Home menu / widgets**: pin *PVR (Now Playing / Next Up)* and *Continue Watching* rows (Jellyfin), favourites. On first run the skin wizard offers menu setup; re-run any time via long-press on a home item.

### Live TV in Kodi

TV section → 3,590 channels in provider groups (US| PRIME, TUBI, PEACOCK...). Channel numbers come from Dispatcharr's `tvg-chno`. Kore (HTTP event server) works as the remote; FLIRC USB IR receiver is the recommended add for a real remote — it presents as a keyboard, map your buttons once in the Flirc GUI, works everywhere including pre-boot navigation.

