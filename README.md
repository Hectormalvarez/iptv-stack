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
| `pvr.iptvsimple` | preinstalled | instance 1 → `http://usrv-01:9191/output/m3u?direct=true&output_profile=1` + `/output/epg`, refresh 51 min |
| `skin.estuary.modv2` 21.4 | b-jesch GitHub (Omega branch) | needs script.skinshortcuts 2.0.3 + pvr.artwork + image.resource.select |
| Wi-Fi power-save | off (runtime + systemd unit `wifi-powersave-off.service` in `/storage/.config/system.d/`) | fixes periodic drop-offs |
| `pvr.iptvsimple` config | userdata | `catchupEnabled`, `allChannelsCatchupMode=4` (XC), `catchupDays=5`, `timeshiftEnabled=true` (HTTP) |
| `guisettings.xml` tweaks | userdata | `pvrmanager.usebackendchannelnumbers=true`, `pvrplayback.confirmchannelswitch=false` (instant zap) |

### Catchup & timeshift

- **Catchup**: XC mode generates strong8k timeshift URLs from the guide — select any past program (≤5 days) in the guide and play it as if live. Works because stream URLs are direct XC (`cf.vovu.top/live/...ts`), not proxied.
- **Timeshift**: `inputstream.ffmpegdirect` (preinstalled) buffers HTTP streams — pause/rewind live TV, seeking only back to when you started watching.
- Edit these in `userdata/addon_data/pvr.iptvsimple/instance-settings-1.xml`, then `systemctl restart kodi`.

### PVR behavior

- Backend channel numbers (provider `tvg-chno`) are used — number entry on remote/Kore zaps directly.
- Channel switch is instant (no confirm dialog).

### Remaining customizations (not yet done)

- Genre mapping file (`genres/genreTextMappings/genres.xml`) to clean up EPG categories + skin genre colors.
- Custom channel groups file, per-channel `tvg-shift` for region-mismatched EPG, logo fallback for blank channels, parental PIN, favourites widget row in Mod V2, Kore PVR remote mode check.


### Known gotchas

- **Python module addons are not importable until Kodi restarts** after filesystem installation.
- **skinshortcuts builds its include file on first skin load** — first switch may fail once, then retry.
- Manual first-login in jellyfin-kodi 2.2.0 crashes with `KeyError: 'address'` (server_id unset); patched `connection_manager.get_server_info()` to fall back to the first saved server.
- Web/JSON-RPC credentials on the box: `kodi`/`kodi` (kodi.log reveals them if changed).

### Home screen curation (Mod V2)

Estuary Mod V2 ships looking similar to stock Estuary — the customization is in **skin settings → Home menu / widgets**: pin *PVR (Now Playing / Next Up)* and *Continue Watching* rows (Jellyfin), favourites. On first run the skin wizard offers menu setup; re-run any time via long-press on a home item.

### Live TV in Kodi

TV section → 3,590 channels in provider groups (US| PRIME, TUBI, PEACOCK...). Channel numbers come from Dispatcharr's `tvg-chno`. Kore (HTTP event server) works as the remote; FLIRC USB IR receiver is the recommended add for a real remote — it presents as a keyboard, map your buttons once in the Flirc GUI, works everywhere including pre-boot navigation.

