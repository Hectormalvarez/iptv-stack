# Active Context (2026-11-07)

## 2026-11-07 (Sat ~15:05 CST): live-stream census — "what's available live right now"
- **Request:** "check what's available live right now on the streams". Read-only census + short
  ffmpeg probes; nothing wired, nothing tuned.
- **CORRECTED after viewing the frames (byte-size verdicts were wrong):** ESPN #301 = Texas A&M @
  South Carolina pre-game/kickoff graphic — genuinely live. RedZone #325 = NFL RedZone standby
  card (no NFL today; the whole slate incl. London CIN@ATL is Sunday Nov 8). ZQAVO NFL slot twins
  = "NO LIVE EVENT FOR THE MOMENT" placeholder, not live games; STRONG8K slots = black trickle.
  Genuinely live ball: FA Cup **Peterborough 0-3 Reading** (45+4', Stan feed on `AU (STAN 22)`),
  rugby **France 19-3 Fiji** (~35') on `AU (STAN 23)`, NCAAM season-openers on `:NCAAB` slots.
- **Hidden-slot inventory tonight (all `hidden_from_output=True`, no EPG):** Peacock Miami vs Notre
  Dame 5:30 CT (ch 7801), Michigan State vs Michigan 5:30 CT (7802), Maryland vs Georgetown 6:00 CT
  (7803); NBA slate 4:00–9:00 CT (`:NBA 01–07` slots); UFC Fight Night Paris prelims 5:55 CT / main
  Cortes Acosta–Walker 8:55 CT (ch 6445/6449); NHL 7:00–9:30 CT slate (ch 7209–7219); ATP Paris
  Ruud v Alcaraz 4:00 CT (`:Tennis 10`). None are wired/enabled — wiring is per decision #30/#31.
- **EAGLE4K** (account id 4) exists with **0 streams** — created, not synced.
- EPG on-air-now sweep of 450 bound channels ran clean (745 rows). RedZone's EPG row
  ("Every Sunday Afternoon 13:00–21:00") was closer to the truth than my byte-size read — with
  zero NFL games on Saturday the feed only shows its standby card. Neither EPG text nor JPEG size
  decides "live"; the decoded, *viewed* frame does.
- ~15:00 CT follow-up sweep (all groups incl. Mexico/VIP): **frame-verified live** = ESPN #301
  (A&M–SC), Telemundo #702 (Serie A Roma 2-0 Sassuolo 57'), Golf Channel #331 (WWTC Los Cabos R3,
  Ben James -18 thru 11 — also seen on the Canal+ Sport PL feed), FA Cup + France–Fiji slots.
  EPG-vs-frame lies caught: beIN #308 (padel, not Ligue 1), #2706 (golf, not LaLiga), #845 (ViX
  promo, not LaLiga) — Valencia–Real Madrid unconfirmed everywhere probed.

## 2026-11-07 (Sat ~10:45 CST): "Put ESPN on" — the movie was a dead guide binding, not the feed
- **Request:** "put espn thats going to show the texas game on". Slate (EPG description search, not
  team names): **No. 7 Texas Longhorns at No. 18 Missouri, 11:00 AM–2:00 PM CT, ESPN** — plus
  Texas A&M at South Carolina 2:00 PM and Texas Tech v West Virginia 8:30 PM, also ESPN.
- **Two ESPN feeds, one working guide:** #301 `US: ESPN HD` (Dispatcharr id 2087, Kodi
  **channelid 1595**, 3 sources) was bound to **dead `EPGData 1200`** (STRONG8K `US: ESPN USA HD`,
  40 rows, 0 upcoming) → the guide showed *nothing*, which reads exactly like "ESPN isn't carrying
  it". The live `EPGData 8716` (`ESPN HD`, EPGSHARE-US2, 5 rows in 8 h) was attached only to the
  VIP twin #1552 `VIP: ESPN` (id 14149, channelid **4001**).
- **Tuned #301** (`Player.Open {channelid:1595}`) → `speed:1 live:true`; content proved with a
  snapshot: **College GameDay**, ESPN bug + ticker, **1280x720** (ESPN's native format), 160 KB JPEG.
- **Fix:** `ChannelOverride.epg_data = EPGData 8716` on ch 2087 (decision #33, pattern #6/#14).
  Dispatcharr logged `EPG data changed (None -> 8716)` + `Triggering EPG program refresh for
  ESPN.HD.us2`; `/output/epg/Kodi` now carries `channel="301"` 17:00–20:00 UTC = *"Live: College
  Football — The No. 7 Texas Longhorns (6-2) visit the No. 18 Missouri Tigers"*. The TV guide picks
  it up on IPTV Simple's next refresh; playback never needed it.
- **Probe gotcha (new):** with the box holding the provider's single upstream connection, the
  stream-specific path timed out and `-frames:v 1` on the channel UUID produced
  `non-existing PPS/no frame!` → a 148-byte JPEG. `-t 12 -c copy` to a file, then decode, worked.

## 2026-11-07 (Sat ~10:00 CST): Arsenal v Hull City — from invisible Peacock slot to live TV
- **Request:** "play the arsenal game on the kodi client" — EPL MW10, Arsenal v Hull City
  (3:00 PM UK kickoff = 9:00 AM CT; live mid-match on request). US carriage is **Peacock-only**,
  so the guide has **zero PL programmes today** — neither team-name nor "premier league"
  programme searches find anything.
- **Discovery path was the stream list, not the EPG:**
  `US (Peacock 021) | Arsenal v. Hull City (2026-11-07 09:50:00)` (STRONG8K), the trailing
  timestamp being **ET** (9:50 ET pre-show = 8:50 CT). Feed verified through
  `/proxy/ts/stream/<hash>`: 1080p30, 12 s of frames.
- **Wiring (ch #7812, id 3935, group `US| PEACOCK PPV ⱽᴵᴾ`):** STRONG8K slot *channels* ship
  `hidden_from_output=True` + a **disabled** Kodi membership + a weeks-stale *channel* name
  ("Away Feed: NYY at SD") while order=0 already holds the current fixture. Fix per decision
  #30 pattern: enable membership → unhide → `ChannelOverride.name='EPL: Arsenal v Hull City -
  9:00 AM CT'`. Order=0 re-verified unchanged after tuning (fixture-identity check).
- **Box was OFF, not drifted:** full `/24` ARP inventory listed every live host and k5320 was
  absent; `ul5420` (.107/.142) answered 8080 as ever (documented decoy). Wi-Fi box → WoL out —
  **user powered it on**; it came back at **192.168.1.182**, boot-resumed on CNN (#3013),
  which was the "it's not playing anything" state.
- **Tuned minutes after boot:** the boot playlist load already included 7812 (M3U 1,680 ch) →
  `PVR.GetChannels` → **channelid 5261** → `Player.Open` → live edge verified: joined at
  `47:30/4:00:00`, `speed 1`, `live true`, then 47:54 → 48:04 over a 10 s wall clock.
- **Process note:** the Dispatcharr wiring ran before plan mode was registered mid-session;
  disclosed immediately, user approved continuing and switching off CNN consciously.
- **~10:20 AM CT: "its not playing" — hourly reset, not sub expiry.** The picture froze
  ~60–70 min into the stream while Kodi's player kept reporting `speed:1` on a dead session;
  STRONG8K's `M3UAccount.status=error` is sync-level only — fresh proxy probes pulled clean
  1080p30 frames from the Arsenal feed *and* an unrelated channel seconds later.
  **`Player.Stop` + fresh `Player.Open` re-tuned instantly** (live edge 54:05 → 54:31 rolling).
  Symptom of the same churn: ESPN #301's order-0 hash 404'd on the proxy at that moment.
- **Hardened the slot + ZQAVO reality check:** attached the same-fixture AU twin
  (`S 7694 AU (STAN 44) | Arsenal v Hull City`, probed healthy first) as `order=1` failover on
  #7812 — the standard anti-single-source fix. **ZQAVO has no Arsenal v Hull row today** (only
  `Everton v Coventry @ Nov 6 ... :Nbc Sports 01` + generic `US-P| Premier League TV FHD`,
  unattached) — "switch to the other sub" has no exact equivalent for this game; PLTV wired onto
  #314 is the nearest fallback if STRONG8K truly dies.
- **~10:50 AM resolution — it was never the box; it was BLACK VIDEO.** The user renewed STRONG8K
  (panel Active to 2026-12-08; **`max_connections: 1`** now, was 3). One sync (`success`, 2,444
  URLs updated, 15,828 streams) fixed normal channels instantly — a CNN JPEG snapshot showed real
  decoded video — but the fixture's old event rows were tombstones: `Peacock 021` served a
  **pure-black TS**, `STAN 44` was dead. **The sync renumbered the event slots**: new rows
  `S 6599 US (Peacock 006)` and `S 7625 AU (STAN 12)` appeared; frame snapshots proved both live
  at 64:54 (ARS 0-0). Wired 6599 as order 0, 7625 as order 1, pruned the two dead links →
  **match confirmed on the TV at ~65'**. Postscript to the 10:20 entry: that "re-tune recovery"
  only restored player *flags*; the feed had already gone black, and the app restart +
  `System.Reboot` were chasing a phantom (HARMLESS but unnecessary — a reboot wasn't needed).
- **Diagnostic that actually works:** pull one decoded JPEG frame through the proxy and *look* at
  it (+fetch via the Engine-API archive endpoint). `-c copy -f null` counters prove packets, not
  pictures; black slate ≈12 KB, real content 55-96 KB. **`VideoPlayer.HasVideo` is unreliable on
  this build** — it read `false` while the user confirmed CNN was playing fine.
- **EAGLE4K account created (id 4, 2026-11-07):** same line as ZQAVO on the live DNS
  (`vpn-esxtrapro.pro`, expiry 2026-11-24, `max_connections: 1`); `ZQAVO`'s own `line.zqavo.top`
  URL is connection-reset dead. Import stalls on the 33k-catalogue fetch (needs the
  `timeout=300` xtream patch + a patient retry) — finish it and use it to REPLACE ZQAVO as the
  failover account; `scripts/swap-provider.py` (census + strict matching, dry-run) is staged.


## 2026-10-31 (Sat): Telegram bridge live; Liga MX wired; Wisconsin-Iowa on
- **Kodi tuned** to #25 Wisconsin @ Iowa (FOX 7 HD Austin, channelid 1307) via the standard
  sequence — idle check, `Player.Open`, live-edge verification (`time 41:30`, `speed 1`).
- **Cline ↔ Telegram bridge**: `cline-telegram` container (compose service) running
  `cline connect telegram` as **@hectorsdevbot**, allowlisted to the user's Telegram id,
  act mode, tools on, cwd=/workspace. Provider auth done once via one-shot `cline auth cline`
  (device code) into the persisted `/state`. Six gotchas solved on the way — see
  `systemPatterns.md` *Cline ↔ Telegram bridge* and `docs/reference.md`.
- **Liga MX request from the phone exposed a stack blind spot**: ZQAVO event streams
  (`Liga MX: Chivas vs Atlante @ Oct 31 8:30 PM :Nbc Sports 16`) arrive unattached — no
  channel, no guide rows (TUDN epg only lists `Liga MX en 60`). Wired tonight's game onto
  VIX slot ch #3192: event stream order=0, `ChannelOverride.name`='Liga MX: Chivas vs
  Atlante - 7:30 PM CT', unhidden, membership enabled. Pre-game probe = 0 bytes (normal).
  Background watcher (`/tmp/watch-ligamx.sh`, log `/tmp/ligamx-watch.log`) polling Kodi for
  the channel to appear after playlist refresh.


## 2026-10-28 (Wed ~20:10 CDT): World Series Game 2 put on the Kodi box
- **Request:** "help me get the world series to play on the kodi client" — mid-game
  (Brewers at Rays, Tropicana Field, 7:00 PM CDT start on Fox).
- **Path:** EPG title search (`ProgramData.title__icontains='world series'`) → resolve back
  through `epg_id` → `Channel.epg_data_id` / `ChannelOverride.epg_data_id` intersected with the
  Kodi profile membership → **#102 `US: FOX 7 HD [AUSTIN]`** was the only Fox affiliate in the
  curated profile (3 sources). Verified the proxy feed first (2 consecutive 8 s probes, 12.5 MB
  and 4.6 MB — the bytes-not-status-codes rule). Kodi was up and idle (`Player.GetActivePlayers
  → []`, ping pong), so nothing was interrupted.
- **Tuned:** `PVR.GetChannels` → label `FOX 7 HD [AUSTIN]` = **channelid 1307** →
  `Player.Open {"item":{"channelid":1307}}` → OK. Verified: `live: true`, `speed: 1`,
  `time 1:06:52 / 3:00:00` — **playing at the live edge, not a restart** (game clock matched wall
  clock). Dispatcharr log: `Channel <uuid> ready, starting normal streaming`.
- **No config changes were needed** — the channel was already in the profile with EPG bound.
  Note the Austin Fox affiliate's EPG binding resolves to a *different* Fox station's guide entry
  (`US: FOX 29`), which is how `remap-epg.py` matches; national Fox programmes still line up, so
  guide shows the World Series correctly.
- Gotchas hit: `ProgramData` joins via `.select_related('epg')` (not `epg_data`); `Channel.override`
  raises `DoesNotExist` when absent — use the try/except helper; `Channel.channel_number` is
  **not unique** (a lookup by number alone can return a different channel than the profile member).

## 2026-10-25 (Sun 17:50 CDT): second subscription wired in as cross-provider failover
- **Request:** "i'm buying a sub to a new service" → "do it".
- **New service — ZQAVO, Dispatcharr M3U account id 3:** `line.zqavo.top`,
  `auth: 1 / status: Active`, **`max_connections: 1`**, panel timezone **Africa/Casablanca**,
  **33,614 live streams in 725 categories**. `player_api.php` works but **`get.php` and `xmltv.php`
  both return 502** — fine for our purpose, because Dispatcharr imports XC accounts through the API
  and a failover source does not need its own EPG (the channel keeps its existing binding). This
  matches the reference doc's own note that `get.php` returns nothing to plain curl.
- **Imported narrowly on purpose:** 13 `|US|` categories → **1,529 streams**, not all 725
  categories, per the API-abuse-block lesson. Gotcha found: the import only creates streams for
  **enabled** groups. With `auto_enable_new_groups_live=False` the first refresh returned
  `error: No streams returned from Xtream Codes provider` with 0 streams; 726
  `ChannelGroupM3UAccount` rows exist and **all default to disabled** — enabling the 13 and
  refreshing again imported everything in 5.7 s.
- **Failover wired:** `scripts/add-cross-provider-failover.py` (dry-run by default,
  `FAILOVER_APPLY=1`) attaches the new provider's feed at the **highest** `ChannelStream.order` on
  **22 channels** — the Austin locals (it even carries `|US| ABC 24 (KVUE) Austin`, the *real*
  Austin ABC that the old provider never had), ESPN/ESPN2/ESPN News/ESPN USA/CBSSN/FS1/FS2,
  NFL Network ×4, RedZone, SEC/ACC/BTN, and the `NCAAF 03/09/10` network feeds. Verified idempotent
  (second run: "to attach: 0").
- **Audit closed — the pending `order=1` fixture mismatch:** found and **removed 4 wrong-fixture
  links**. `NFL  | 4k - SNF 8:20pm Chiefs at Seahawks` was the `order=1` "backup" on **#321, #1680,
  #1681, #2251** (all NFL Network), so a failover would have silently shown a *different game*.
  Those channels then got the new provider's **correct** NFL Network feed, so none were left
  single-source. Re-audit: **0 remaining**. Four NBA candidates (#341/#342/#2201/#2202) were
  **false positives** — both sources carry the *identical* fixture name, so the duplicate is
  legitimate. One left for review: **#324 NHL Network's `order=1` is the empty slot `NHL  |  4K -`**.
- **Consequence to remember:** `max_connections: 1` means ZQAVO can never serve two channels at
  once, so it must stay failover-only. #325 carries it at `order=3` (deepest), which is correct.

## 2026-10-25 (Sun 16:47 CDT): "not playing" triage — provider outage, not the stack
- **Symptom:** the TV showed nothing. `Player.GetActivePlayers` → `[]` (idle) while `JSONRPC.Ping` →
  `pong`, so the box was **not wedged** — it just had nothing playing.
- **Two causes, in sequence:**
  1. **Expected:** the #352 slot feed ended at **12:06 CDT** (the game finished ~11:30). The stream
     manager logged `Stream was stable for 8935s` and then stopped. `autoplaynextprogramme=false`, so
     Kodi stopped rather than retuning — nothing played from 12:06 onward.
  2. **The actual fault:** when the box was next tuned to **RedZone (#325)** the stream never came up.
     Logs show the TV (`Broken pipe … (192.168.1.182)`) looping on dropped connections while
     Dispatcharr held the channel at `state: connecting`.
- **Verdict: provider-side outage.** **20× 502 in one hour** (after 1/4/2/1 per hour for the previous
  four), 58× `Invalid data found when processing input`, 57× `waiting for buffer to fill: 0/4 chunks`,
  and **every** channel stuck in `connecting` — KXAN #101, ESPN #301, RedZone #325, NFL slots
  #358/#361. Direct probes of a single stream URL returned **407 / 502 / timeout /
  200-with-53-bytes-of-HTML**, and `player_api.php` answered
  `{"error":"There is an Database Error","status":false}`.
- **Ruled out:** a wedge (ping answers), an IP ban (web root **401 on both families** — a ban is 403),
  the address-family flip (`getent ahosts` still A-first), the stack (`verify-stack.sh` healthy,
  EPG 97%, all three EPG sources `success`), and the channel/fixture/failover set (unrelated channels
  fail identically, so the diagnosis never needed to touch Dispatcharr's config).
- **Disclosure:** 3 of the 4 channels in `connecting` were **my own diagnostic probes** (KXAN, ESPN,
  #361); they cleared as those client connections timed out. They did not cause the outage (onset was
  ~17:00 UTC, before the probes) but with a 3-connection cap they briefly competed with the TV.
- **Next:** wait for recovery — signature is streams going 502/407/HTML → 302 → real TS data — then
  retune. SNF Chiefs at Seahawks (#363) was still ~3.5 h away when this was written.

### Follow-up (17:15 CDT): the outage was partly OURS — `gai.conf` pinned the blocked family
- The triage above correctly identified a failing provider, but missed a second, **self-inflicted**
  fault. Testing per family: **IPv4 stream → 403 / `000` on connect, IPv6 stream → 200 + 25 MB of
  `video/mp2t`**. So the ban had flipped a third time, and `config/gai.conf`
  (`precedence ::ffff:0:0/96 100`, added 2026-10-04) was forcing every container lookup to the
  **blocked** family. Proof:
  `docker exec dispatcharr sh -lc 'getent ahosts cf.vovu.top | head -1'` → `104.21.52.9` (IPv4)
  while IPv6 was serving perfectly. That also explains the *intermittent* 12–21 MB bursts seen
  through the proxy: sometimes the IPv4 attempt failed fast enough for the client to fall back to
  IPv6, sometimes it hung at `waiting for buffer to fill: 0/4 chunks`.
- **Fixed:** removed the override — glibc's RFC 3484 default prefers AAAA when the host holds a
  global IPv6 address — then `docker restart dispatcharr jellyfin`, because **glibc caches
  gai.conf per process, so a reload is not enough**. After the restart the container resolves to
  `2606:4700:3036::ac43:c0c8` (IPv6). See `decisions.md` #26.
- **Not sufficient yet:** the provider's origin then went down entirely — **502 on BOTH families** —
  so streams still fail. The `gai.conf` fix is correct and necessary; it just cannot fix an origin
  outage. Nothing further to do locally.
- **Bug fixed in my own watcher:** `scripts/watch-provider-recovery.sh`'s `kodi_idle()` used the
  inverse test (`grep -q '"result":\[\]'`, miss ⇒ busy), so a transient empty JSON-RPC answer was
  read as "already playing" and **silently cancelled the retune at the exact moment the provider
  recovered** (`recovered, but the box is already playing - not touching it` while
  `Player.GetActivePlayers` was `[]`). Replaced with a positive `box_playing()` test on
  `"result":[{`.

## 2026-10-25 (Sun 08:12 CDT): Steelers at Saints on #352 — and a wrong-game failover trap
- **Request:** "put on the nfl game that's on right now". The only game in the early window is the
  **NFL Paris game — Steelers at Saints, kickoff 08:30 CDT** (9:30am ET, at Saint-Denis, the first
  NFL game played in France). From 08:00 the NFL feeds carry *"NFL Gameday Kickoff"* pregame.
- **Done:** resolved pvrid **5242** = `NFL: 9:30am Steelers at Saints` (profile **#352**,
  `Sports: NFL`, channel uuid `74f8bce5-…`), `Player.Open` → `OK`. Verified: correct label,
  `live: true`, `speed: 1`, h264 1280×720, Dispatcharr
  `Channel 74f8bce5-… has 1 clients, state: active`, **0×403**, the old ABC session stopped cleanly,
  no stream-health warnings, box still responsive (**no wedge** — a plain zap remains safe).
- **⚠️ Wrong-game failover trap found:** `#321` and `#2251` both report **2 sources**, but their
  `order=1` is `NFL  | 4k - SNF 8:20pm Chiefs at Seahawks` — the **Sunday Night slot**, i.e. a
  *different fixture*. `add-backup-streams.py` matched on the network name (`NFL NETWORK`), not the
  game, so a failover rotation would silently switch the viewer to tonight's SNF game. For a
  per-fixture event feed, the **dedicated slot channel (#352) is the correct primary** — a network
  channel's slot "backup" is worse than no backup.
- **Also checked, not taken:** the **Chivas–Monterrey** Liga MX game (Jornada 14, Apertura 2026,
  Monterrey at home, Estadio Monterrey) *was* available on **#1876 `VIP: TUDN`** (2 sources:
  `VIP: TUDN` + `MX: TUDN`) and `#701 US: Univision23 (WLTV) Miami`, window 19:30–22:00 CDT on
  2026-10-24. Not on any PPV slot — the whole `US| SOCCER PPV` group read `NO EVENT STREAMING NOW`
  or other fixtures. Guide showed it only as generic *"Fútbol Mexicano Primera División"*.
- **Guide-time note:** Dispatcharr prints UTC, so 13:12 UTC = 08:12 CDT — confirmed against the host
  clock (`TZ=America/Chicago date`) before quoting any kickoff.

## 2026-10-24 (Sat evening): Ole Miss at Texas pulled up on ABC — plain zap, no wedge
- **Request:** "pull up the college football game" — the game is **not identifiable from the guide**.
- **Box IP drifted again: `k5320.lan` = `192.168.1.182`** (`.181` answers nothing; same Kodi, same
  `-u kodi:kodi`). Resolve the name every session instead of reusing a remembered number.
- **Why the guide cannot answer "which game":** the provider's EPG titles every national feed
  **"Live: College Football"**; the fixture is only in the programme **description**
  (#104: *"The No. 7 Ole Miss Rebels visit the No. 19 Texas Longhorns for an SEC game"*).
  So enumerate the slate from `ProgramData.description`, not `title` — see `systemPatterns.md`.
- **The provider's `US| NCAAF PPV` group (82 slots) is a decoy.** All ship
  `hidden_from_output=True`, so none are in the Kodi profile, and their **channel names are stale**
  (a previous week's fixtures) while their **stream names are current** — #7956's name reads
  "UT Rio Grande Valley at UTSA" but its stream reads "2pm Colgate at Richmond". Trust neither
  without cross-checking.
- **Done:** resolved **pvrid 2048** = `US: ABC 13 (KTRK) HOUSTON HD` (profile **#104**,
  `Austin Local`; `channelid` ≠ channel number), then `Player.Open` → `OK` on the first try while
  the box was already streaming ESPN (#301).
- **Verified:** `Player.GetItem` → correct label; `Player.GetProperties` → `live: true`, `speed: 1`,
  h264 1280×720 (ABC is 720p60 natively — not a degraded feed); Dispatcharr
  `Channel 5ebe13bf-… has 1 clients, state: active` (UUID confirmed = #104), **0×403**; the old ESPN
  session (`5cd98c12-…`) tore down cleanly, so **a plain zap still does not wedge the box**.
- **Watch:** #104 is **single-source** — exactly the hourly-reset death pattern. No failover attached.

## 2026-10-11 (later): NBC 5 Chicago added for the marathon — ON AIR (fixed by a power cycle)
- **Request:** switch to the Chicago Marathon on the NBC Chicago channel, "not listed in the guide".
- **Why it was missing:** the WMAQ feed was never a profile member. The right channel is
  **#1923 `US: NBC 5 CHICAGO IL (WMAQ) HD`** (channel id 4404), bound to EPG
  `EPGSHARE-US-LOCALS/WMAQ-DT`, whose current programme is literally *2026 Bank of America Chicago
  Marathon* (12:00–16:00 **UTC** = 07:00–11:00 CDT — note `timezone.localtime()` in the container
  prints **UTC**, so subtract 5 h for Austin). The three other WMAQ rows (`#5004`/`#5005`/`#5006`
  A/H/S and `#5376` D) are RAW feeds on the same EPG.
- **Done (durable):** moved it into the **`News` group at #410** with `ChannelOverride.name =
  'NBC 5 Chicago (WMAQ)'` and enabled the Kodi membership — the builder *adopts* anything already
  in a `KODI_GROUPS` group, so a future `build-kodi-profile.py` run keeps it (no script edit
  needed). Attached `#5005`'s stream as an order=1 failover: the feed was single-stream, which is
  the documented hourly-reset death. Profile M3U 1,677 → **1,678**; `verify-stack.sh` healthy,
  EPG coverage 98%. Both feeds verified through the proxy (primary ~10 Mbps, failover ~15 Mbps,
  h264 720p30 + AAC-LC — nothing exotic).
- **How it went wrong:** to make the box see #410 I toggled `pvr.iptvsimple` off/on (the only
  remote way to force a playlist reload). The box picked the channel up (1,678 channels, PVRID
  5215) but the toggle killed the running NFL stream **and wedged Kodi's app thread** — see
  `systemPatterns.md` for the full symptom pattern. The marathon never started, and the box can no
  longer be driven: `System.Reboot` is accepted but not executed, SSH auth is refused, so **only a
  power cycle at the box recovers it**.
- **RESOLVED by a power cycle:** with a clean boot, `Player.Open` on channel 410 returned `OK` on the
  first try and the marathon played — `label "NBC 5 Chicago (WMAQ)"`, title *2026 Bank of America
  Chicago Marathon*, `speed: 1`, position **2h32m** of the 4 h broadcast (the live edge), Dispatcharr
  showing 1 client `state: active`, 0×403. So the channel, the M3U entry and the feed were all fine;
  the two freezes were **stale IPTV Simple/PVR state from the mid-session addon toggle**, and only a
  reboot cleared it. PVR id stayed **5215** across the restart here, but resolve it fresh rather than
  assuming.
- **Then: RedZone was "laggy" → fixed by reordering its sources (same session).** `#325`'s primary
  (`US: NFL REDZONE ᴴᴰ`) was a **720p29.97** feed while `TV:`/`AT&T:` `ᴿᴬᵂ` are **1080p59.94** — the
  "HD" name was the worst of the three. Promoted `TV:` first, which turned out to be **corrupt**
  (`Packet corrupt`, reconnect attempts) and gave a *black screen while Kodi reported `speed: 1`,
  fullscreen video and 1080p* — my mistake; the burst-inflated 6 s bitrate sample I chose it on was
  misleading. Settled on **`AT&T:` (1080p59.94, ~9 Mbps steady)** with `US:` (720p30, ~4.8 Mbps) as the
  first fallback and the corrupt `TV:` last. Verified: box reports `VideoResolution 1080`,
  `speed: 1`, `Live: NFL RedZone`, no errors on the new session, 0×403.

- **Second freeze (same session):** the box un-wedged on its own (it answered
  `Player.GetActivePlayers` → `{"result":[]}`, so the app thread was alive), `Player.Open` on 5215 was
  issued, the proxy logged the box connecting and dropping twice within ~2 s, and the app thread
  wedged again — all `Player.*` / `GUI.*` calls now hang while `JSONRPC.Ping` still answers. Verdict:
  a PVR channel open re-triggers the wedge, and only a power cycle clears it. Server side was cleared
  in the same pass — the entry the box receives for `#410` is identical in shape to the working `#352`
  entry (fetched with the box's own Host, zero `localhost` URLs), catchup is off on channel and
  streams (`is_catchup=False`, and the profile M3U has no `catchup` attributes at all), and the feed
  streams at ~10 Mbps. (The clean-boot retry did work — see the RESOLVED bullet above.)

## 2026-10-11: "put the game on" — live TV switched via JSON-RPC (operational, no code change)
- **Request:** put on the early-window NFL game. It is provider slot **#352**
  `NFL: 9:30am Eagles at Jaguars` (`group-title="Sports: NFL"`), kickoff 09:30 ET = 08:30 CDT,
  still on the provider's slate. Guide/EPG healthy throughout (`verify-stack.sh` → healthy,
  98% coverage, 1,677 profile channels).
- **Played:** `Player.Open {"item":{"channelid":5198}}` → `speed: 1`, position **35m56s → 36m28s**
  (resumed at the live edge, so it is the real feed, not a restart). Dispatcharr logged
  `Channel 74f8bce5-… has 1 clients, state: active`, **0×403** over 5 min, and the previous
  channel (ESPN HD pregame, `5cd98c12-…`) released its slot cleanly. Proxy stream pre-checked
  at 11.2 MB / 12 s (~7.5 Mbps) before switching.
- **PVR `channelid` ≠ channel number.** The scripted NFL slate is `channelid` 5194–5213
  (5198 = 352 Eagles, 5208 = 360 Giants@Commanders, 5152 = 325 RedZone, 1791 = 321 NFL Network).
  Resolve ids with `PVR.GetChannelGroups` → `Sports: NFL` = **77**, then
  `PVR.GetChannels {"channelgroupid":77}` (omit `properties` to get `channelid`+`label`).
- **Box state:** back at **192.168.1.181** (`k5320.lan`); **port 22 is now open** but rejects key
  *and* password auth from `usrv-01`, so JSON-RPC on 8080 is still the only way in.
- **Lesson (now in systemPatterns):** an unauthenticated `/jsonrpc` POST answers `401` with an
  **empty body**, which reads exactly like a dead host. And `192.168.1.107`/`.142` also listens
  on 8080 but is a different machine (`ul5420`) — a port scan is not a box check.

## 2026-10-04 (later): guide restored — STRONG8K EPG refreshed + No-Guide sweep reapplied
- **Symptom:** `verify-stack.sh` FAILed — EPG coverage **10%** (692/777 blank), `STRONG8K` source
  `status=error`, both M3U accounts `error`. Live TV itself still worked.
- **Root cause (not corruption):** the provider's `xmltv.php` feed is **short-horizon** (only ~11–14 h
  of programmes for the mapped channels), so the 6-hourly `epg_source-refresh-1` is the lifeline.
  It had been failing since ~2026-10-03 12:03 with the pre-`gai.conf` **403** (IPv6-first egress), so
  no new programmes were inserted and the guide simply **aged out** — `ProgramData.max_end` was frozen
  at 2026-10-03 22:59 UTC. The 13:46 UTC container recreate (the `gai.conf` fix) also wiped the
  **ephemeral** `/app/media` EPG cache, but that is by design (`APP_DIRS`; `fetch_xmltv` recreates it).
- **Fix (first-party recovery, no code change):** dispatched Dispatcharr's **own** tasks —
  `refresh_epg_data.delay(1, force=True)` (the UI refresh icon / `POST /api/epg/import/`) and
  `refresh_single_m3u_account.delay(2)`. Egress was already healthy: `https://cf.vovu.top/` → 401 on
  both families, and the EPG URL fetched with the pinned `TiviMate/5.1.6` UA → 200.
- **Verified (first-party):** `STRONG8K` `status=success` ("Parsed 48,352 programs for 885 channels"),
  `ProgramData` future = **24,235**, `max_end` → 2026-10-06 02:40 UTC; programme index rebuilt (3,639
  channels); M3U refresh "Streams: 2419 updated", auto-sync ok; `verify-stack.sh` → **RESULT: healthy**,
  coverage **98%** (781 guide-expected, 13 blank); profile M3U = 1,677 channels; `/output/epg/Kodi` =
  35,315 programmes; proxy stream pulled **19 MB in 8 s**. Reapplied the No-Guide sweep (896 parked).
- **No-op:** `label-event-slots.py` dry run showed **0** changes (19 slots already labelled — the
  override names are durable and match this week's fixtures).
- **Known orphan:** M3U account 1 (`custom`, STD, **no URL**) stays `error`; it has nothing to fetch.
- **Not done:** Jellyfin's guide refresh — it pulls Dispatcharr's XC `xmltv.php` and refreshes on its
  own schedule (the Jellyfin admin password is held by the user, not stored).

## 2026-10-04: provider banned IPv6 (family flipped) + hourly Xtream sync disabled
- **Symptom:** Kodi couldn't play anything; the NFL slots showed the previous week's games.
- **Root cause — two parts:**
  1. The provider banned our **IPv6** (403 on `/`, `get.php`, `player_api`, `xmltv` and live)
     while **IPv4 served normally** (web root 401, live URLs 302) — the *reverse* of 2026-10-01.
     A third-party egress (r.jina.ai) got `401` on the web root, proving the provider was up and
     only *our* address was blocked. glibc sorts AAAA first, so the host-networked containers
     kept hitting the banned family and every stream died with `403 Forbidden`.
  2. The Jellyfin **Xtream sync was running hourly.** The plugin's `GetDefaultTriggers()` always
     returns a trigger — `Manual` falls through to an interval trigger of `SyncIntervalMinutes`,
     which defaults to **60**. Every run hammered `player_api.php` and re-tripped the ban; it
     also meant the playlist couldn't refresh, so the NFL fixture labels (read from
     `Stream.name`) were days stale → "not this week's game".
- **Fix:** mount `config/gai.conf` (`precedence ::ffff:0:0/96 100`) into dispatcharr + jellyfin
  (`6ff9530`); set `SyncIntervalMinutes=525600` so the sync no longer fires (`3c82c59`).
- **Verified:** NFL Network streamed 22 MB; Kodi opened the Commanders game (ch 5208, `NFL: 9:30am
  Colts at Commanders`) with Dispatcharr showing it `active`; **0** 403s; no Xtream sync since the fix.
- **Resolved (later 2026-10-04):** once IPv4 egress stayed clean, a forced M3U refresh + re-run of
  `label-event-slots.py` brought the playlist current — see the section at the top.

## Where things stand
The guide is healthy again — 98% coverage, `verify-stack.sh` RESULT: healthy (2026-10-04). Kodi boots
into the TV guide and zaps by number, the provider's VOD catalog is imported into Jellyfin, and
WNBA/NFL event slots are wired in. Live playback was re-verified end-to-end through the proxy
(19 MB in 8 s) this session.

## 2026-10-01: every channel 403'd (provider IPv4 block) — fixed
- **Symptom:** Kodi opened nothing; `dispatcharr` logged `HTTP error 403 Forbidden` on every
  provider stream URL; the `STRONG8K` EPG source went `status: error` (403).
- **Root cause:** the provider front `cf.vovu.top` returned **403 to our egress IPv4** on *every*
  endpoint (streams, `get.php`, `player_api`, `xmltv`) while **IPv6 worked** — same URL, same
  pinned `TiviMate` UA, same host; only the address family differed (`curl -4` → 403,
  `curl -6` → 302). A third-party IPv4 fetch of the web root returned 401, so it is a block on
  *this host's IPv4*, not IPv4 in general (403 body came from the provider's own CDN front).
- **Why only Dispatcharr broke:** the host has routable IPv6 and prefers it, so host `curl`
  worked; the bridged `dispatcharr` container had **no IPv6 route** and could only try the
  blocked IPv4.
- **Likely trigger:** the Xtream-Library VOD sync hammering `player_api.php` (first 403 burst
  2026-09-29 23:44). This ban outlived the documented ~15–45 min and escalated to live streams.
- **Fix (commit `ed272f9`):** `dispatcharr` → `network_mode: host`; Jellyfin keeps
  `http://dispatcharr:9191/...` via `extra_hosts: dispatcharr=172.18.0.1`; `media-net` subnet
  pinned so that gateway is deterministic.
- **Verified:** proxy stream 200 (21 MB), Kodi playing ch 1581 with `time` advancing at
  `speed: 1`, **0** 403s, and `STRONG8K` EPG refresh now `success` (45,033 programs).
- **Follow-ups done this session:** the Xtream VOD sync's daily trigger was removed
  (`SyncScheduleType=Manual` — no trigger is registered at startup) and is now run by hand via
  `scripts/sync-vod.sh`; Jellyfin also moved to host networking so that manual sync has IPv6;
  the STRONG8K profile's `max_streams` went 2 → 3 because with 2 a single zap already filled the
  cap and every extra zap 503'd.

## WNBA event slots (2026-09-29)
- 8 upcoming fixtures (Sep 29 – Oct 2) resolved from the provider's `US (WNBA NN) | <away> at
  <home> (<date>)` slots into group **`Sports: WNBA` at 368–375**, named via
  `ChannelOverride.name`, with a same-date failover feed attached where one exists.
- **Blockers found and fixed:** the provider's PPV slots are `hidden_from_output=True` (so
  membership alone did nothing — the profile M3U kept excluding them), and
  `build-kodi-profile.py` would have dropped the new group on its next run. `Sports: WNBA`
  is now in `KODI_GROUPS` + `CURATED_GROUPS`.
- Verified: profile M3U = 1,677 channels and contains both games with clean names.
- **Not verified:** the Kodi client never loaded them — the box was offline (no ARP, no SSH,
  full /24 scan clean). It also means the earlier playback attempt via a raw TS URL was cut
  short by the client, not by the provider (provider feed was healthy: 29 MB/6 s).
- To play the live game once the box is back: guide → `Sports: WNBA` → 368
  (`WNBA: Las Vegas Aces at Indiana Fever`), or JSON-RPC `Player.Open` on the channel id.

## Provider VOD → Jellyfin (2026-09-29)
- Xtream Library plugin v1.55.3.0 (STRM → native libraries, so `jellyfin-kodi` syncs it),
  `VOD Movies` + `VOD Series` libraries, STRM output at `/mnt/storage/vod-strm`.
- Category selection limited to an English "best of" (46 movie + 26 series categories) rather
  than the full 28.7k/8.7k catalog; picker lives in `scripts/pick-xtream-categories.py`.
- First sync was running at session end (batch 1/2: 4,060 movies, 1,998 series; ~6.9k STRM
  files already written). Check `/XtreamLibrary/Progress` next session and confirm the
  libraries populate in Jellyfin and Kodi.
- Lesson: the plugin's all-category defaults fire ~11k API calls and trip Cloudflare's
  403 block on the whole IP for ~1 h (live streams unaffected). Keep the selection tight and
  `RequestDelayMs=250`, `SyncParallelism=3`.
- Jellyfin `root` password was reset (user request; was never stored). New value given to the
  user, `MustUpdatePassword` set — not stored in the repo.

## 2026-09-29 provider outage (earlier, resolved)
- MNF night: Kodi couldn't play the game. Root cause was a **provider-wide outage** — every
  stream on `cf.vovu.top` returned Cloudflare `error code: 502` (origin down), including
  web-root HTTPS. Nothing local was broken; `verify-stack.sh` stayed healthy throughout.
- Diagnostic shortcut: before touching bindings/streams, curl 2+ unrelated channels' URLs.
  502 on all = provider outage, just wait. Recovery signs: web root goes 502 → 401
  "Restricted", stream URLs go 502 → 302 (redirect to data).
- Once the origin returned, played the dedicated **4K MNF event slot (ch 7038)** via
  JSON-RPC `Player.Open {"item":{"channelid":5171}}`; confirmed live playback. The 4K feed
  tested ~95 Mbps. Channel 2251 (NFL Network HD) carries the same 4K MNF stream as failover.

## Current lineup numbers
| Range | Group |
|---|---|
| 101–106 | Austin Local (KXAN/KTBC/KEYE/ABC-stand-in/PBS/Spectrum News) |
| 201–239 | Entertainment |
| 301–319 · 321–367 | Sports + per-league (incl. **325 = NFL RedZone**) |
| 401–409 · 501–507 · 601–604 · 701–704 | News / Kids / Movies / Spanish |
| 2001–3388 | Sports: Networks, NBA, NFL, MLB, NHL, College, Soccer, Golf & Tennis, Motorsport, Combat, International, Events |
| 801–849 · 1201–1933 | Mexico / Mexico VIP |
| 9001+ | No Guide (guide-less bulk channels) |

## Session work just completed
1. **NFL RedZone added** as #325 with **3 sources** (`US:` / `TV:` / `AT&T:`) — was hidden in the
   provider's `US| NFL PPV` group; renamed via `ChannelOverride.name` and added to `LINEUP`.
2. **`add-backup-streams.py`** — 475 of 1,668 channels gained a failover source. This fixed
   "channel 219 won't play": single-stream channels die at the provider's hourly reset
   (`Stream ends prematurely` → 3 × 4XX → `Found 0 alternatives`).
3. **`label-event-slots.py`** — 13 NFL fixtures restored into channel names
   (`NFL: 1pm Chargers at Bills`, `NFL: SNF 8:20pm Rams at Broncos`, …). The provider keeps the
   fixture in `Stream.name`; my earlier rename had discarded it.
4. **Playback continuity**: `pvrplayback.autoplaynextprogramme = false`, power timers off,
   screensaver unchanged (Kodi inhibits it during playback). LibreELEC's `idle_timeout` turned out
   to be Bluetooth-only — no shutdown timer exists.
5. **Playlist refresh 51 → 10 min** so fixture renames appear within 10 minutes.
   Verified there is no JSON-RPC way to force a reload in Kodi 21 (`Addons.SetAddonSetting`
   is absent); the timer or a GUI settings change are the options.

## Verified working
- RedZone playing, `state: active` on Dispatcharr, ~6.6 Mbps
- 0 Kodi log errors, no new segfaults (6 = pre-2026-09-26 VideoPlayer crashes)
- Guide aligned to America/Chicago, median depth ~14 h, all three EPG sources `success`
- `verify-stack.sh`: RESULT healthy (EPG coverage 98% of guide-expected channels)

## Known quirks, accepted for now
- NFL/PPV event slots carry **no EPG** — the game name lives on the channel name, not as a
  programme title. Provider XC EPG for those stream IDs returns empty.
- NBA/MLB event slots are empty (offseason); they will label themselves when fixtures appear.
- Arctic Fuse 3 is installed but needs a GUI first-load to build its includes; Mod V2 is active.
- 1,193 channels still have a single source (no duplicate exists on the provider).
