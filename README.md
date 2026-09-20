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

## DVR / Recordings

- Dispatcharr DVR output → `/data/recordings_host` → host `/mnt/storage/recordings` → Jellyfin sees it at `/recordings`.

## Operations

```bash
docker compose config -q     # validate
docker compose up -d         # apply changes
docker compose logs -f dispatcharr
```

Dispatcharr admin account: `hadev` (password reset via `manage.py set_password` if lost).
Nightly Dispatcharr backups: `./dispatcharr/data/backups/` — copy these off-box.
