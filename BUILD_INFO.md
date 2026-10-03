# KayiFamily TV — Build Info (v0.1.0)

Project: KayiFamily TV
Version: 0.1.0
Kodi minimum: 20 Nexus
Addon ID: plugin.video.kayifamily

Known working test: Mehmed Fetihler Sultani Episode 85
(Test episode page: https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/)

Playback chain:
KayiFamily
→ OK.ru embed
→ fresh signed HLS
→ Kodi native playback

Resolver: PASS
Linux Kodi: PASS
Google TV: NOT TESTED

Runtime dependencies:
- Python stdlib (urllib, http.cookiejar, re, sys)
- Kodi xbmc APIs (xbmc, xbmcaddon, xbmcgui, xbmcplugin)
- inputstream.adaptive (ships with Kodi, including Android)

No Playwright/Chromium/ffmpeg/yt-dlp/Streamlink runtime dependency.
Those were development/research tools only and are not in the release ZIP.

Release commit: PLACEHOLDER_COMMIT_SHA
(Updated by CI when the release artifact is built.)
