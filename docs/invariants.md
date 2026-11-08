# Invariants

Facts that cost real outages to learn. They hold regardless of how the code is written, and each
one carries its proof. Anything not listed here is an implementation detail and is free to change.

## 1. Provider egress: one address family is banned at a time

The provider front 403s **this host's IPv4 or its IPv6**, and the two flip (IPv4 banned
2026-10-01, IPv6 banned by 2026-10-03). Both `dispatcharr` and `jellyfin` therefore run with
`network_mode: host`, and `config/gai.conf` is mounted into both to force the family that
currently works.

- A **bridge** container has only one family to try → it breaks alone while the host is fine.
  That is exactly why "the host curl works but Dispatcharr is dead" happened.
- Proof: `curl -4` vs `curl -6` against a channel URL return different codes; after the fix
  `curl -s -o /dev/null -w '%{http_code}' http://localhost:9191/proxy/ts/stream/<uuid>` → 200
  and `docker exec dispatcharr getent ahosts <provider-host>` shows the preferred family.
- When the ban flips: edit `config/gai.conf` (precedence), restart the containers.

## 2. Never bypass the proxy

Clients only ever see `/output/m3u/...` and `/proxy/ts/stream/...`. `direct=true` is forbidden:
the provider pins the **User-Agent** (any other UA → empty 502) and metres connections. The proxy
holds one upstream connection, applies the UA, buffers ~5 s, and multiplexes every client.

## 3. Connection budget is metered by the provider, not by us

`M3UAccount`/profile `max_streams` is *our* cap; the panel's `max_connections` is the real one.
After the 2026-11-07 renewal the panel reports **1** (it was 3), while the profile still allows 3.
Zapping needs ≥2 concurrently (the old stream is still closing when the new one opens); with a cap
of 1 the whole lineup stalls. Expect contention between the Kodi box and any Jellyfin
viewer/recording.

## 4. Every channel needs ≥2 sources

The provider drops the upstream roughly hourly and refuses the immediate reconnect. Dispatcharr's
retry budget is ~1.75 s (`MAX_RETRIES = 3`, `RETRY_WAIT_INTERVAL = 0.5` — in-container constants,
no override), after which it logs `Found 0 connect subscription(s) …` and the channel dies.
Failover must therefore be **data-level**: a second `ChannelStream` at a deeper `order`. Tuning
retry constants is not an option because they live inside the image.

## 5. User state goes to `ChannelOverride`, always

M3U refresh rewrites `Channel.*` on every sync; `ChannelOverride` is the documented persistence
point. Effective EPG is:

```
Coalesce(override.epg_data, channel.epg_data)
```

so an override of `NULL` **falls back** to the provider binding. "No guide on purpose" must point
at the dummy `NO GUIDE` source, not at null.

## 6. A blank guide on a healthy channel is a binding bug

The stream can be perfect while the guide is empty, because the channel is bound to a dead EPG
entry. Real case: `#301 US: ESPN HD` was bound to the provider's `US: ESPN USA HD`
(40 rows, **0 upcoming**) while the live schedule sat on the EPGSHARE `ESPN HD` entry that a VIP
twin already used. One re-bind fixed it; nothing was re-synced.

Diagnose before touching anything: **does a same-named sibling channel have upcoming
programmes?** If yes, it is a binding, not a provider fault.

## 7. Event slots are ephemeral and must never be promoted

- Provider event slots ship `hidden_from_output=True` and are therefore absent from the output
  profile until explicitly unhidden.
- Their names rotate per fixture; the stream behind a slot is only valid for that fixture.
- **Never** make an event slot a channel's `order=0` source. A dead event stream then becomes the
  primary and the channel goes black.
- After any provider renewal the slots are **renumbered** (e.g. dead `Peacock 021`/`STAN 44`
  became live `Peacock 006`/`STAN 12`). Always re-resolve a fixture by name, never by remembered
  slot id.

## 8. "Live" is decided by a decoded frame, never by bytes or EPG text

Byte counts and guide text both lie:

- A black slate is ≈12 KB; real content is 55–96 KB — but a provider **placeholder card** ("NO
  LIVE EVENT FOR THE MOMENT") is 3.9 MB / ~90 KB and looks "live" by size. It is not.
- EPG text lies as often: beIN listed Ligue 1 and showed padel; an `AF: CANAL+ SPORT` entry listed
  Valencia–Real Madrid and showed golf; a ViX entry listed LaLiga and showed a comedy promo.
  Named-matchup descriptions on real network channels did hold up (Telemundo "Roma vs Sassuolo" →
  frame confirmed ROM 2-0 SAS).
- `VideoPlayer.HasVideo` is **unreliable on Kodi 21.3** — it read `false` while the user confirmed
  playback was fine.
- Rule: extract one decoded JPEG through the proxy and *look at it* before calling anything live.
  `-c copy -f null` counters prove packets, not pictures.

## 9. Provider names lie about quality

`4K` can be 720p30, `ᴿᴬᵂ` can be corrupt, and a 6-second sample is misleading (the same 720p30 feed
measured 15 Mbps over 6 s and 4.8 Mbps over 15 s). Quality decisions come from measurement, on one
connection at a time, through the stream-specific proxy path.

## 10. Catchup and timeshift stay off

The provider has no archive (`tv_archive=1` on 0 of ~15,830 streams) and both options are
documented Kodi-Omega crash bugs. Time-shifting is Dispatcharr DVR instead.

## 11. Provider VOD sync is manual

Bulk `player_api.php` calls trip a Cloudflare ban that takes the whole IP out (documented: ~56 min
for a full-category sync; days when it hit live streams too). Scheduling is manual, and the plugin
still carries `SyncIntervalMinutes=525600` because `Manual` alone left an hourly trigger alive.

## 12. Timezones

Containers and the Kodi box run `America/Chicago`; the **host stays UTC** (it runs other production
stacks). Every DVR timer, guide timestamp and "7:30 PM CT" label depends on this split.

## 13. Two subscriptions, one primary

Primary feeds every channel at `order=0`. The second subscription exists **only** as deep failover,
because it allows one concurrent connection — it can never be a primary. The original failover
account's DNS is dead (`line.zqavo.top`, connection reset); its replacement points at the same line
under a live hostname and is staged, not yet synced.

## 14. Kodi client

- GUI **3840x2160 @ 60 Hz**, refresh switching *on start/stop*; display values are
  `17 + index into modetest -c`.
- Boots **straight into the guide** (`lookandfeel.startupwindow = 10702`).
- Playlist refresh every 10 min. **Do not** toggle `pvr.iptvsimple` to force a reload — it wedges
  the player; wait for the timer or restart the box.
- Keymap: `←`/`→` = channel down/up (there is no catchup, so step-back is useless).
- Audio stays **PCM** (HDMI sink is stereo `AE_DEVTYPE_PCM`; bitstreaming only breaks volume
  control).
- Only tags verified to exist in Kodi 21 belong in `advancedsettings.xml`; most blog-post tags do
  not.

## 15. Remote control is hardware, not software

The Vizio V505-H9 remote is **IR-only** (manual-verified), LibreELEC 12.2 has a libCEC 7.1.1
regression, and HDMI-CEC needs a Pulse-Eight/pico-cec adapter. Kore over the HTTP event server is
the only working input today.

