# KayiFamily TV — Proof-of-Concept Test Report

Date: 2026-10-02
Tester: automated verification on Ubuntu 24.04 + real Kodi 20.5 (Nexus),
headless via Xvfb, driven over JSON-RPC.

## Final status

```
KAYIFAMILY TV — PROOF OF CONCEPT

Episode page: https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/
Player host: ok.ru (via https://ok.ru/videoembed/17557429029406)
Playback type: HLS (.m3u8)
English subtitles: PASS (burned in — no external files exist to attach)
Resolver: PASS
Kodi playback: PASS (Kodi 20.5, real playback at 1x for 5+ minutes)
Restart test: PASS (fresh Kodi instance re-resolved and played)
Installable ZIP: plugin.video.kayifamily-0.1.0.zip

OVERALL: WORKING
```

## Chain verification

```
KayiFamily episode page  →  resolver  →  playable source  →  Kodi Player
        PASS                     PASS           PASS               PASS
```

1. **Episode page loads** — `GET kayifamilytv.com/mehmed-fetihler-sultani-episode-85/`
   → HTTP 200, 323 KB. **PASS**
2. **Player tabs found** — `moLy` → `vidmoly.org/embed-28rtaeym9d4g.html`,
   `OkRu` → `ok.ru/videoembed/17557429029406`. **PASS**
3. **Embed page loads** — `GET ok.ru/videoembed/17557429029406` → HTTP 200,
   flashVars JSON present. **PASS**
4. **HLS manifest extracted** — signed `video.m3u8` URL (252 chars), fresh
   `expires`/`sig` per run. **PASS**
5. **Manifest reachable** — HTTP 200, `Content-Type: application/x-mpegURL`,
   6 variants. **PASS**
6. **Media playlist** — HTTP 200, 1117 MPEG-TS segments covering 6697 s
   (111.6 min = the full 1:51:36 episode). **PASS**
7. **Segments downloadable** — first, middle, and last segments all
   HTTP 200, `video/MP2T`, valid TS sync bytes. Playback of several minutes
   is therefore servable end-to-end. **PASS**
8. **Restart/regeneration** — two consecutive runs minted different
   `expires`/`sig` tokens; no URL is stored anywhere. **PASS**
9. **Headers** — `Referer: https://ok.ru/videoembed/17557429029406` and a
   desktop Chrome `User-Agent` are the only requirements; both are passed to
   Kodi via `inputstream.adaptive` `manifest_headers`/`stream_headers`. **PASS**
10. **Subtitles** — no `.vtt`/`.srt`/`<track>`/HLS subtitle references exist
    in the embed page or metadata; English subtitles are burned into the
    video. The add-on attaches nothing (correct behavior). **PASS**
11. **Protections** — no DRM, paywall, login, CAPTCHA, or geo-block
    encountered; none bypassed. **PASS**
12. **Failure behavior** — the `moLy` (VidMoly) tab raises a clean
    `ResolverError` ("video file cannot be played", upstream JW Error 232011,
    reproducible in a desktop browser); the UI shows a notification instead
    of crashing. **PASS**

## Known issue (upstream, not a resolver bug)

VidMoly's own player fails with **JW Player Error 232011** on both Episode 84
and 85 embeds — the media is broken on VidMoly's side, verified in a normal
desktop browser. The add-on detects the tab, reports it cleanly, and plays
via the working `OkRu` source.

## Real Kodi playback test (2026-10-02, Kodi 20.5 Nexus on Ubuntu 24.04)

Method: Kodi installed via apt (user-approved), run headless under Xvfb,
add-on installed from the ZIP and enabled, playback driven over JSON-RPC
with `Player.Open` on the add-on's real play URL
(`plugin://plugin.video.kayifamily/?action=play&url=<episode>&title=...`).

Results:

1. **Selecting the episode works** — Player.Open invoked the add-on's
   `play()`; kodi.log shows the full resolver chain inside Kodi's Python
   runtime. **PASS**
2. **Resolver finds the source dynamically** — fresh signed HLS manifest
   minted per play (`expires`/`sig` differ every run). **PASS**
3. **Kodi opens the stream** — `inputstream.adaptive 20.3.18`:
   "Successfully parsed manifest file", video player active. **PASS**
4. **Playback lasts several minutes** — time advanced at 1x for 5+ minutes
   (00:00:46 → 00:24:20 across samples), no errors, no stalls. **PASS**
5. **Pause/resume** — speed 1 → 0 → 1, time froze and resumed. **PASS**
6. **Seek** — jumped to 20:00, playback continued from 00:24:20. **PASS**
7. **Restart test** — Kodi killed and relaunched; resolver re-ran live,
   manifest re-parsed, playback resumed at 1x
   (00:01:24 → 00:01:49 → 00:02:14). **PASS**
8. **Temporary URLs regenerated** — confirmed across runs; nothing stored.
   **PASS**

Note: the sandbox has no audio device (`CActiveAESink` errors in the log);
video playback was unaffected. Software rendering (llvmpipe) was used;
on real hardware with GPU decoding this will be smoother.

## Independent verification (tooling pass, 2026-10-02)

Three independent tools confirmed the resolver's HLS output:

- **yt-dlp** (generic HLS path): 6 formats, 256x144 → 1920x1080 @ 25 fps,
  ~1.76 GiB for the 1080p rendition. No subtitle tracks offered.
- **Streamlink**: resolved the manifest to the best (1080p) stream URL.
- **ffprobe**: streams are **h264 video + aac audio**; no subtitle streams
  in the manifest.

**Discovered requirement**: the OK.ru CDN returns HTTP 400 on the manifest
unless a browser-like `User-Agent` is sent. The resolver and the Kodi
handoff already send the Chrome UA on every request, so this is covered —
recorded here for future debugging.

## Remaining work (out of PoC scope by design)

- **Catalog expansion** (Recently Added, series/season/episode browsing,
  search): deliberately not built until one episode played. That milestone
  is now met, so expansion can begin.
- **Kodi repository** (`repository.example` is cloned under
  `.tooling/references/` for later): not started, per instructions.

## Reproduce

```
cd plugin.video.kayifamily
python3 -m resources.lib.resolver https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/
```
