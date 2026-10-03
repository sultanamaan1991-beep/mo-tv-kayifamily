# KayiFamily TV — Proof of Concept

A minimal Kodi video add-on that plays **one** KayiFamily episode through
Kodi's native player. No catalogs, no accounts, no stored stream URLs.

> Status: proof of concept. One episode page, one resolver, one player.

## What it does

```
KayiFamily TV
    └── Test Series
          └── Test Episode
                └── Play  →  resolver  →  Kodi Player  →  VIDEO PLAYS
```

On Play, the add-on:

1. Loads the public episode page (`kayifamilytv.com/...`, HTTP 200)
2. Finds the player tabs and their `<iframe>` URLs (VidMoly, OK.ru)
3. Loads the OK.ru embed page and extracts the **signed, time-limited HLS
   manifest URL** from its flashVars JSON — regenerated on every Play,
   bound to the viewer's IP, never stored
4. Hands the manifest + `Referer`/`User-Agent` headers to Kodi's
   `inputstream.adaptive`, which handles segments, seeking, pause/resume

No DRM, paywalls, logins, CAPTCHAs, or geo-blocks are encountered or
bypassed anywhere in this chain.

## Requirements

- Kodi 20 (Nexus) or newer
- `inputstream.adaptive` (ships with most Kodi installs; required for HLS)

## Installation

1. Copy `plugin.video.kayifamily-0.1.0.zip` to the Kodi machine
   (USB stick, network share, `~/Downloads`, …).
2. In Kodi: **Add-ons → Install from zip file** → select the zip.
   (If "Unknown sources" needs enabling, Kodi will prompt you.)
3. Open **Add-ons → Video add-ons → KayiFamily TV**.
4. Navigate **Test Series → Test Episode → Play**.

Add-on settings (optional): preferred player source — Auto (default),
moLy, or OkRu.

## Test episode

- Series page: https://kayifamilytv.com/ (Mehmed Fetihler Sultani)
- Episode page: https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/
- Episode: **Mehmed Fetihler Sultani — Episode 85** (Season 4, Episode 2),
  duration 1:51:36, English subtitles burned in.

## Playback path (verified 2026-10-02)

| Step | Detail |
|---|---|
| Episode page | `kayifamilytv.com/mehmed-fetihler-sultani-episode-85/` → HTTP 200 |
| Player tabs | `moLy` → `https://vidmoly.org/embed-28rtaeym9d4g.html` · `OkRu` → `https://ok.ru/videoembed/17557429029406` |
| Player host | **ok.ru** (VidMoly's own player currently fails upstream with JW Error 232011) |
| Playback type | **HLS** (`.m3u8`), 6 variants; progressive MP4 renditions also available |
| Stream URL | `https://ok6-4.vkuser.net/video.m3u8?cmd=videoPlayerCdn&expires=…&sig=…` — signed per request, IP-bound, expires |
| Required headers | `Referer: https://ok.ru/videoembed/17557429029406`, desktop Chrome `User-Agent` |
| Media check | Master playlist 200 `application/x-mpegURL`; media playlist 1117 MPEG-TS segments covering 6697 s (111.6 min); first/middle/last segments all HTTP 200 `video/MP2T` |

## Subtitles

English subtitles are **burned into the video** (hardcoded). The OK.ru
flashVars/metadata contain no `.vtt`, `.srt`, or `<track>` references, and
no external subtitle files are served as part of normal playback. The
add-on therefore attaches no external subtitles — nothing is missing, there
is simply nothing separate to attach. If a future source provides external
tracks, `resources/lib/subtitles.py` attaches them with English preferred.

## Known limitations

- Proof of concept: exactly one hard-coded *episode page*; the *stream URL*
  is always resolved live.
- The `moLy` (VidMoly) tab is detected but currently unplayable — VidMoly's
  own player reports its video file cannot be played (upstream issue, also
  reproducible in a desktop browser). The add-on reports this cleanly and
  uses the `OkRu` source instead.
- Signed OK.ru URLs expire (typically within ~a day) and are IP-bound: they
  cannot be bookmarked or shared; the resolver regenerates them per Play.
- If KayiFamily changes its player markup or OK.ru changes its embed
  scheme, resolution fails with a readable error instead of playing.

## Debugging

Enable **Debug logging** in the add-on settings, reproduce, then check
`kodi.log` for lines tagged `[KayiFamily TV]`. The log shows the episode
URL, HTTP status codes, redirect destinations, player type, iframe domain,
stream type, HLS/MP4 detection, subtitle findings, and resolver
success/failure. Cookies and secrets are never printed.

The resolver has no Kodi dependencies: test it from a plain shell with

```
python3 -m resources.lib.resolver <episode_url>
```

## Project layout

```
plugin.video.kayifamily/
├── addon.xml
├── main.py                  # Kodi plugin entry: navigation + playback handoff
├── resources/
│   ├── lib/
│   │   ├── resolver.py      # episode page → playable stream (no Kodi deps)
│   │   ├── subtitles.py     # subtitle track selection/attach
│   │   └── logger.py        # Kodi-aware logging
│   └── settings.xml
└── README.md
```

## Test report

See `TEST_REPORT.md` for the full PASS/FAIL report.
