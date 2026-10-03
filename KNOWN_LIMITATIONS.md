# KayiFamily TV — Known Limitations (v0.1.0)

This is a proof-of-concept release candidate, not a finished product.

## Content

- Exactly one episode is playable: Mehmed Fetihler Sultani, Episode 85
  (Season 4, Episode 2).
- No series catalog, no seasons view, no search, no recently-added,
  no favorites, no watch history, no recommendations.

## Sources

- The `OkRu` (OK.ru) player source is the working one and is preferred.
- The `moLy` (VidMoly) source is currently broken upstream: VidMoly's own
  player reports its video file cannot be played (JW Player Error 232011),
  reproducible in a desktop browser. The add-on detects this and reports it
  cleanly instead of hanging.

## Playback

- Signed media URLs are temporary (expire, IP-bound) and are re-resolved
  live on every Play. They cannot be bookmarked or shared.
- Playback startup can take approximately 10–20 seconds (live resolution
  plus HLS manifest/segment startup through inputstream.adaptive).
- English subtitles for the current test episode are burned into the video;
  no separate subtitle tracks exist to select.
- Requires Kodi 20+ with inputstream.adaptive (ships with standard Kodi
  installs, including Android).

## Site dependence

- If KayiFamily changes its player markup, or OK.ru changes its embed page
  scheme, resolution will fail with a readable error instead of playing.
  The resolver is deliberately small so it can be updated in one place
  (`plugin.video.kayifamily/resources/lib/resolver.py`).

## Platform

- Tested on Linux Kodi 20.5. Chromecast with Google TV not yet tested.
