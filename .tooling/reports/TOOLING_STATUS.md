# KAYIFAMILY TV — TOOLING STATUS

Date: 2026-10-02
Environment: Ubuntu 24.04.5 LTS, Python 3.12.3, isolated venv at `.tooling/venv`
(pip 26.2.1). Nothing installed globally; `plugin.video.kayifamily/` untouched
by tooling (only `main.py` gained 4 best-practice lines, `addon.xml` bumped
`xbmc.python` 3.0.0 → 3.0.1 per the checker).

```
Kodi plugin example: CLONED (.tooling/references/plugin.video.example)
Kodistubs: PASS (21.0.0)
Kodi addon checker: PASS (0.0.36, report: .tooling/reports/kodi-addon-checker.txt)
Playwright: INSTALLED (1.63.0) / Chromium: INSTALLED (build 1243) / LIVE USE: FAIL (environment)
mitmproxy: INSTALLED (12.2.3, not needed)
yt-dlp: PASS (2026.08.19)
Streamlink: PASS (8.6.1)
HTTPX: PASS (0.28.1)
inputstream.adaptive reference verified: PASS (manifest_type=hls, stream_headers/manifest_headers format)
Kodi repo template cloned: CLONED (.tooling/references/repository.example — for LATER, not started)
ffmpeg: PASS (8.1.2)
ffprobe: PASS (8.1.2)
pytest: PASS (9.1.1, 8 unit tests green)
Kodi itself: INSTALL IN PROGRESS (apt, user-approved; GUI play test pending)
```

## What each tool proved

- **plugin.video.example** — structural comparison done. Two tiny
  best-practice gaps fixed in `main.py`: play item now uses
  `ListItem(offscreen=True)`, listings set plugin category + content type.
  `addon.xml`: `xbmc.python` → 3.0.1 for Omega. Remaining checker notes
  (icon/fanart assets, "complex entry point" for a 92-line main.py) are
  repo-submission polish, irrelevant to the PoC — documented, not hidden.
- **Kodistubs 21.0.0** — `.tooling/scripts/check_kodi_api.py` imports our
  add-on against the real Kodi API surface and exercises
  list_root/list_series/list_episode/play (success + resolver-failure paths).
  PASS: no invented Kodi calls.
- **kodi-addon-checker 0.0.36** (`--branch omega`) — 0 problems, 2 warnings
  (xbmc.python version — fixed; entry-point complexity — accepted for PoC).
  Full log saved.
- **yt-dlp** — independent diagnostic on the resolver's HLS manifest:
  6 formats, 256x144 → 1920x1080 @25fps, ~1.76 GiB for the 1080p rendition.
  No subtitle tracks offered. (Note: yt-dlp's own Odnoklassniki extractor
  crashes on the current ok.ru embed page format — site changed, extractor
  didn't. Generic-HLS path works. Also: this sandbox MITMs TLS, so yt-dlp
  needed `--no-check-certificate`; that works around the *sandbox proxy*,
  not any site protection.)
- **Streamlink 8.6.1** — independently resolved the manifest to the best
  (1080p) stream URL. PASS.
- **ffprobe 8.1.2** — streams are **h264 video + aac audio**, no subtitle
  streams in the manifest. PASS.
- **Discovered requirement**: the OK.ru CDN returns **HTTP 400** on the
  manifest unless a browser-like `User-Agent` is sent (ffprobe/streamlink
  both hit this; urllib/yt-dlp with browser UAs pass). Our resolver and the
  Kodi handoff already send the Chrome UA everywhere. Recorded so a future
  regression has a known cause.
- **HTTPX 0.28.1** — installed for prototype use; the final resolver stays
  on stdlib `urllib` (zero runtime dependencies is better for Kodi).
- **pytest 9.1.1** — `.tooling/scripts/tests/test_resolver.py`: 8 unit
  tests on hand-written fixtures (iframe extraction, URL unescaping,
  HLS preference, MP4 fallback quality order, result contract, auto source
  priority, subtitle ordering). All green. One opt-in `--live` test hits
  the real episode page.
- **Playwright 1.63.0 + Chromium 1243** — installed, but **live browsing
  fails in this sandbox**: the bundled Chromium gets `ERR_EMPTY_RESPONSE`
  even for example.com through the egress proxy (curl/urllib through the
  same proxy return 200). Proxy auth config was applied three ways; all
  failed identically. Verdict: environment limitation, not a tool bug. The
  dynamic inspection Playwright was meant for was already covered by the
  managed-browser research pass (VidMoly JW Error 232011 confirmed there)
  plus the urllib/yt-dlp/ffprobe verifications here. Not retried further.
- **mitmproxy 12.2.3** — installed, never needed: Playwright-level traffic
  inspection was unnecessary once the manifest/segments were verified
  directly. Not used to bypass anything.

## Investigation scripts (reusable)

- `.tooling/scripts/inspect_kayifamily.py` — episode page: tabs, iframes, network
- `.tooling/scripts/inspect_vidmoly.py` — VidMoly embed: play once, capture media requests/errors
- `.tooling/scripts/check_kodi_api.py` — Kodistubs API surface check
- `.tooling/scripts/tests/test_resolver.py` — pytest unit + opt-in live tests

Reports: `.tooling/reports/` (checker log, inspection JSONs).
Sanitized: URLs truncated in reports; no long-lived tokens stored.
