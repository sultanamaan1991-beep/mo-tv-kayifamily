#!/usr/bin/env python3
"""Unit tests for resources/lib/catalog.py using stubbed xbmc modules.

Tests: search matching, cache fallback when the network fails, and the
load path against the real published catalog.json.
"""

import json
import os
import sys
import tempfile
import types
import urllib.request

PLUGIN_DIR = "/home/hatch/workspace/kayifamily-tv/plugin.video.kayifamily"

# ---- stub Kodi modules ----
profile_dir = tempfile.mkdtemp(prefix="kftv-profile-") + "/"


class FakeAddon:
    def getAddonInfo(self, key):
        assert key == "profile"
        return profile_dir


xbmc = types.ModuleType("xbmc")
xbmcaddon = types.ModuleType("xbmcaddon")
xbmcvfs = types.ModuleType("xbmcvfs")
xbmcaddon.Addon = FakeAddon


class VFSFile:
    def __init__(self, path, mode):
        self._f = open(path, "r" if mode == "r" else "w")

    def read(self):
        return self._f.read()

    def write(self, data):
        return self._f.write(data)

    def close(self):
        self._f.close()


xbmcvfs.File = VFSFile
xbmcvfs.mkdirs = lambda p: os.makedirs(p, exist_ok=True)

logger_mod = types.ModuleType("resources.lib.logger")
logger_mod.log = lambda *a, **k: None
logger_mod.debug = lambda *a, **k: None
pkg = types.ModuleType("resources.lib")
pkg.__path__ = [os.path.join(PLUGIN_DIR, "resources", "lib")]

sys.modules["xbmc"] = xbmc
sys.modules["xbmcaddon"] = xbmcaddon
sys.modules["xbmcvfs"] = xbmcvfs
sys.modules["resources.lib.logger"] = logger_mod
sys.modules["resources"] = types.ModuleType("resources")
sys.modules["resources.lib"] = pkg
sys.path.insert(0, PLUGIN_DIR)

from resources.lib import catalog  # noqa: E402

CATALOG = json.load(open("/home/hatch/workspace/kayifamily-tv/docs/catalog.json"))

ok = True


def check(name, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))
    ok = ok and cond


# search
r = catalog.search(CATALOG, "kurulus")
check("search show title", any(h["type"] == "show" for h in r), "%d hits" % len(r))
r = catalog.search(CATALOG, "episode 85")
check("search episode title", any(h["type"] == "episode" for h in r), "%d hits" % len(r))
r = catalog.search(CATALOG, "mehmed")
check("search case-insensitive", len(r) > 0)
check("search empty query", catalog.search(CATALOG, "  ") == [])

# cache: first load populates from the real network
cat1, from_cache1 = catalog.load_catalog()
check("live load works", len(catalog.get_shows(cat1)) == 19 and not from_cache1)
cache_file = os.path.join(profile_dir, "catalog.json")
check("cache file written", os.path.exists(cache_file))

# now break the network -> must fall back to cache
real_urlopen = urllib.request.urlopen


def broken(*a, **k):
    raise IOError("simulated outage")


urllib.request.urlopen = broken
try:
    cat2, from_cache2 = catalog.load_catalog()
    check("cache fallback on outage",
          from_cache2 and len(catalog.get_shows(cat2)) == 19)
    check("fallback data matches",
          catalog.get_show(cat2, "kurulus-osman")["title"] == "Kurulus Osman")
finally:
    urllib.request.urlopen = real_urlopen

# no cache + no network -> empty catalog, no exception
os.remove(cache_file)
urllib.request.urlopen = broken
try:
    cat3, _ = catalog.load_catalog()
    check("empty catalog when no cache and no network",
          catalog.get_shows(cat3) == [])
finally:
    urllib.request.urlopen = real_urlopen

print("OVERALL:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
