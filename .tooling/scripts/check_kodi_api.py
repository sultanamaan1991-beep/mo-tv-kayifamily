#!/usr/bin/env python3
"""Static/API check: import the add-on's Kodi code against Kodistubs.

Exercises list_root/list_series/list_episode/play with a stubbed resolver
so every xbmc*/xbmcgui/xbmcplugin/xbmcaddon call in main.py and
resources/lib/*.py runs against the real Kodi API surface. An
AttributeError means we called something that does not exist.

Usage: .tooling/venv/bin/python .tooling/scripts/check_kodi_api.py
"""

import sys
import types

PLUGIN_DIR = "/home/hatch/workspace/kayifamily-tv/plugin.video.kayifamily"
sys.path.insert(0, PLUGIN_DIR)
# main.py reads sys.argv at import time -> set a dummy first.
sys.argv = ["plugin://plugin.video.kayifamily/", "1", ""]

import main  # noqa: E402  (imports xbmc* stubs from Kodistubs)
from resources.lib import resolver as resolver_mod  # noqa: E402


def fake_resolve(episode_url, preferred_source="auto"):
    assert episode_url.startswith("https://kayifamilytv.com/")
    return {
        "video_url": "https://example.invalid/video.m3u8?sig=test",
        "stream_type": "hls",
        "headers": {
            "Referer": "https://ok.ru/videoembed/1",
            "User-Agent": "test-agent",
        },
        "subtitles": [],
        "source": "okru",
    }


def run(action, extra=None):
    argv = ["plugin://plugin.video.kayifamily/", "1", ""]
    if action:
        qs = "action=%s" % action
        if extra:
            qs += "&" + extra
        argv[2] = "?" + qs
    sys.argv = argv
    main.HANDLE = 1
    main.router()


resolver_mod.resolve_episode = fake_resolve

run(None)                                            # list_root
run("series")                                        # list_series
run("episode", "url=https%3A%2F%2Fkayifamilytv.com%2Fx&title=Ep")
run("play", "url=https%3A%2F%2Fkayifamilytv.com%2Fx&title=Ep")

# resolver failure path -> clean notification, no traceback
def boom(url, preferred_source="auto"):
    raise resolver_mod.ResolverError("nope")
resolver_mod.resolve_episode = boom
run("play", "url=https%3A%2F%2Fkayifamilytv.com%2Fx&title=Ep")

print("KODISTUBS API CHECK: PASS (no invented Kodi calls)")
