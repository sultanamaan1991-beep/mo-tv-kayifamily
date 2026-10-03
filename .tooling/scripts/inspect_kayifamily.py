#!/usr/bin/env python3
"""Playwright inspection: KayiFamily episode page structure + player tabs.

Loads the episode page with JavaScript, dumps the player-tab DOM, lists
all iframes, and records the network requests made during a normal page
load (no play pressed here).

Usage:
    .tooling/venv/bin/python .tooling/scripts/inspect_kayifamily.py [episode_url]

Output: .tooling/reports/kayifamily_inspect.json (sanitized: URLs truncated)
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

EPISODE_URL = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/"
)

REPORT = "/home/hatch/workspace/kayifamily-tv/.tooling/reports/kayifamily_inspect.json"


def short(url, n=90):
    return url if len(url) <= n else url[:n] + "..."


def main():
    requests = []
    findings = {
        "inspected_at": datetime.now(timezone.utc).isoformat(),
        "episode_url": EPISODE_URL,
        "tabs": [],
        "iframes": [],
        "network": [],
        "notes": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(proxy=proxy_config())
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        )
        page.on("request", lambda r: requests.append(
            {"method": r.method, "url": short(r.url),
             "resource": r.resource_type}))
        page.goto(EPISODE_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)

        findings["title"] = page.title()
        findings["final_url"] = page.url

        # Player tabs: the sp-tab markup seen during research.
        for tab in page.query_selector_all("[data-sptoggle='tab']"):
            findings["tabs"].append({
                "text": (tab.inner_text() or "").strip(),
                "for": tab.get_attribute("for"),
                "active": "sp-tab__active" in (tab.get_attribute("class") or ""),
            })
        # All iframes on the page with their srcs.
        for f in page.query_selector_all("iframe"):
            findings["iframes"].append({
                "src": f.get_attribute("src") or "",
                "width": f.get_attribute("width"),
                "height": f.get_attribute("height"),
            })
        findings["network"] = requests
        browser.close()

    with open(REPORT, "w") as fh:
        json.dump(findings, fh, indent=2)
    print("tabs:", [(t["text"], t["active"]) for t in findings["tabs"]])
    print("iframes:", len(findings["iframes"]))
    for f in findings["iframes"]:
        print("  -", short(f["src"]))
    print("network requests:", len(findings["network"]))
    print("report:", REPORT)


if __name__ == "__main__":
    main()
