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

**Architecture:** Jellyfin-first for VOD (`jellyfin-kodi` addon syncs Movies/TV/Recordings/watch-state), `pvr.iptvsimple` for Live TV pointed at Dispatcharr's output endpoints. Kodi 21 Omega / LibreELEC 12.2.1.

### What's installed

| Component | Source | Notes |
|---|---|---|
| `jellyfin-kodi` 2.2.0 | repo.jellyfin.org (manual zip) | deps vendored: requests+urllib3 1.26.16, certifi, idna, charset_normalizer (PyPI), websocket, typing_extensions, unidecode, simplecache, simpleeval |
| `pvr.iptvsimple` | preinstalled | instance 1 → **proxied** `http://usrv-01:9191/output/m3u` + `/output/epg`, refresh 51 min (do **not** use `direct=true` — see below) |
| `skin.estuary.modv2` 21.4 | b-jesch GitHub (Omega branch) | needs script.skinshortcuts 2.0.3 + pvr.artwork + image.resource.select |
| Wi-Fi power-save | off (runtime + systemd unit `wifi-powersave-off.service` in `/storage/.config/system.d/`) | fixes periodic drop-offs |
| `pvr.iptvsimple` config | userdata | `catchupEnabled=false`, `allChannelsCatchupMode=0`, `timeshiftEnabled=false` — deliberately off, see below. Backups: `/storage/backups/instance-settings-1.xml.pre-proxy-fix-*` |
| `guisettings.xml` tweaks | userdata | `pvrmanager.usebackendchannelnumbers=true`, `pvrplayback.confirmchannelswitch=false` (instant zap) |

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

