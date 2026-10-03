"""Catalog loader for KayiFamily TV.

The episode catalog is built outside Kodi (tools/build_catalog.py) from
the public KayiFamily WordPress API and published as a single JSON file
on GitHub Pages. Kodi makes ONE lightweight request for it and caches
the result in the add-on profile directory, so browsing stays fast and
keeps working (from cache) when the network or the site is down.

catalog.json never contains video stream URLs -- only public episode
PAGE urls. Streams are resolved fresh at Play time by resolver.py.
"""

import json
import urllib.request

import xbmc
import xbmcaddon
import xbmcvfs

from .logger import log, debug

CATALOG_URL = (
    "https://sultanamaan1991-beep.github.io/mo-tv-kayifamily/catalog.json"
)
TIMEOUT = 15


def _cache_path():
    profile = xbmcaddon.Addon().getAddonInfo("profile")
    xbmcvfs.mkdirs(profile)
    return profile + "catalog.json"


def _read_cache(path):
    try:
        f = xbmcvfs.File(path, "r")
        data = f.read()
        f.close()
        catalog = json.loads(data)
        if isinstance(catalog, dict) and "shows" in catalog:
            return catalog
    except Exception as exc:  # corrupt/missing cache -> refetch
        debug("Catalog cache unreadable: %r" % exc)
    return None


def _write_cache(path, catalog):
    try:
        f = xbmcvfs.File(path, "w")
        f.write(json.dumps(catalog))
        f.close()
    except Exception as exc:
        debug("Catalog cache write failed: %r" % exc)


def _download():
    req = urllib.request.Request(
        CATALOG_URL, headers={"User-Agent": "KayiFamilyTV-kodi/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        catalog = json.load(resp)
    if not isinstance(catalog, dict) or "shows" not in catalog:
        raise ValueError("catalog.json has unexpected shape")
    return catalog


def load_catalog():
    """Return (catalog_dict, from_cache). Never raises.

    Strategy: read the local cache first (instant UI), then try to
    refresh it in the background of this call. If the refresh fails,
    keep serving the cache. Only when there is no cache at all does a
    network failure surface as an empty catalog.
    """
    path = _cache_path()
    cached = _read_cache(path)
    try:
        fresh = _download()
        _write_cache(path, fresh)
        debug("Catalog refreshed from %s" % CATALOG_URL)
        return fresh, False
    except Exception as exc:
        log("Catalog refresh failed (%r); using cache: %s"
            % (exc, bool(cached)))
        if cached is not None:
            return cached, True
        return {"shows": [], "documentaries": [], "latest": []}, True


def get_shows(catalog):
    return catalog.get("shows") or []


def get_show(catalog, show_id):
    for show in get_shows(catalog):
        if show.get("id") == show_id:
            return show
    return None


def get_season(show, season_number):
    for season in show.get("seasons") or []:
        if season.get("number") == season_number:
            return season
    return None


def get_latest(catalog, limit=30):
    return (catalog.get("latest") or [])[:limit]


def get_documentaries(catalog):
    return catalog.get("documentaries") or []


def search(catalog, query):
    """Match show titles and episode titles (case-insensitive)."""
    q = (query or "").strip().lower()
    if not q:
        return []
    results = []
    for show in get_shows(catalog):
        if q in (show.get("title") or "").lower():
            results.append({"type": "show", "show": show})
        for season in show.get("seasons") or []:
            for ep in season.get("episodes") or []:
                if q in (ep.get("title") or "").lower():
                    results.append({"type": "episode", "show": show,
                                    "season": season.get("number"),
                                    "episode": ep})
    return results
