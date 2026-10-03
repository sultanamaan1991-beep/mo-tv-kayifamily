#!/usr/bin/env python3
"""Playwright inspection: VidMoly embed behavior.

Loads a VidMoly embed page directly, presses the player's play control once
(the site's own control), and records:
  - network requests (looking for .m3u8 / .mp4 / media segments)
  - the player error state, if any (e.g. JW Error 232011)

Usage:
    .tooling/venv/bin/python .tooling/scripts/inspect_vidmoly.py [embed_url]

Output: .tooling/reports/vidmoly_inspect.json (sanitized)
"""

import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


def proxy_config():
    """Explicit egress proxy from the environment (never logged)."""
    raw = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
    parts = urllib.parse.urlparse(raw)
    if not parts.hostname:
        return None
    cfg = {"server": "%s://%s:%s" % (parts.scheme, parts.hostname, parts.port)}
    if parts.username:
        cfg["username"] = urllib.parse.unquote(parts.username)
    if parts.password:
        cfg["password"] = urllib.parse.unquote(parts.password)
    return cfg

EMBED_URL = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "https://vidmoly.org/embed-28rtaeym9d4g.html"
)

REPORT = "/home/hatch/workspace/kayifamily-tv/.tooling/reports/vidmoly_inspect.json"


def short(url, n=100):
    return url if len(url) <= n else url[:n] + "..."


def main():
    media_reqs = []
    findings = {
        "inspected_at": datetime.now(timezone.utc).isoformat(),
        "embed_url": EMBED_URL,
        "media_requests": [],
        "player_text": "",
        "error": None,
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(proxy=proxy_config())
        page = browser.new_page()
        page.on("response", lambda r: media_reqs.append(
            {"status": r.status, "url": short(r.url),
             "ctype": r.headers.get("content-type", "")})
            if any(k in r.url for k in (".m3u8", ".mp4", ".ts", ".m4s",
                                        "videoplayback", "master.txt"))
            or r.headers.get("content-type", "").startswith(
                ("application/vnd.apple.mpegurl", "video/"))
            else None)
        page.goto(EMBED_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        findings["title"] = page.title()

        # Press the player's own play control once, if present.
        for sel in (".jw-icon-display", "[aria-label='Play']",
                    "button.vjs-big-play-button", ".play-btn"):
            el = page.query_selector(sel)
            if el:
                try:
                    el.click(timeout=5000)
                    findings["notes"] = "pressed play via %s" % sel
                except Exception as exc:  # noqa: BLE001
                    findings["notes"] = "play click failed: %s" % exc
                break
        page.wait_for_timeout(8000)
        try:
            findings["player_text"] = (page.inner_text("body") or "")[:600]
        except Exception:  # noqa: BLE001
            pass
        findings["media_requests"] = media_reqs
        browser.close()

    with open(REPORT, "w") as fh:
        json.dump(findings, fh, indent=2)
    print("title:", findings.get("title"))
    print("media requests:", len(media_reqs))
    for m in media_reqs[:10]:
        print("  -", m["status"], m["ctype"], m["url"])
    print("player text excerpt:", findings["player_text"][:200].replace("\n", " "))
    print("report:", REPORT)


if __name__ == "__main__":
    main()
