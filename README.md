# KayiFamily TV — Proof of Concept

A minimal Kodi video add-on that browses to **one** KayiFamily episode and
plays it through Kodi's native player.

> Status: proof of concept. One episode, one resolver, no catalogs.

## What it does

```
KayiFamily TV
    └── Test Series
          └── Test Episode
                └── Play  →  resolver  →  Kodi Player  →  VIDEO PLAYS
```

On Play, the add-on:

1. Loads the public episode page (`kayifamilytv.com/...`)
2. Finds the player tabs and their iframe URLs (e.g. VidMoly, OkRu)
3. Resolves the current direct stream URL (HLS `.m3u8`) — regenerated every time
4. Hands the stream + required headers + English subtitles to Kodi's player

No stream URLs are hard-coded. No accounts, no DRM bypass, no paywalls.

## Requirements

- Kodi 20 (Nexus) or newer (tested on: _TBD_)
- `inputstream.adaptive` (ships with most Kodi installs; needed for HLS)

## Installation

1. Download `plugin.video.kayifamily-0.1.0.zip` from this folder.
2. In Kodi: **Add-ons → Install from zip file** → select the zip.
3. Open **Add-ons → Video add-ons → KayiFamily TV**.
4. Navigate to Test Series → Test Episode → Play.

## Test episode

_TBD after Phase-1 research_

## Playback path

_TBD after Phase-1 research_

## Subtitles

_TBD after Phase-1 research_

## Known limitations

- Proof of concept: exactly one hard-coded *episode page*; the *stream* is resolved live.
- Only the sources found during research are supported.
- If KayiFamily changes its player markup or the video host changes its embed
  scheme, the resolver will fail cleanly with an error message instead of playing.

## Debugging

Enable **Debug logging** in the add-on settings, then reproduce and check
`kodi.log` for lines tagged `[KayiFamily TV]`. The log shows episode URL,
HTTP status codes, redirect destinations, player type, iframe domain, stream
type, and subtitle format — never cookies or secrets.

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

`resolver.py` has zero Kodi dependencies on purpose: it can be tested from a
plain shell with `python3 -m resources.lib.resolver <episode_url>`.
