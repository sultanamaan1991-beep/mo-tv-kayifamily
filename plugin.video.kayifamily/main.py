"""KayiFamily TV - Kodi video add-on.

Navigation:
    KayiFamily TV
        ├── Latest Episodes
        ├── All Shows
        │     └── Show
        │           └── Season
        │                 └── Episode -> Play
        ├── Search
        └── Documentaries

The episode catalog is a single JSON file built outside Kodi
(tools/build_catalog.py) and cached locally -- browsing never crawls
the website and never resolves video streams. Play calls the frozen
resolver.py flow exactly as the proven Episode 85 implementation does.
"""

import sys
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.logger import log, debug
from resources.lib.resolver import resolve_episode, ResolverError
from resources.lib import subtitles as subtitles_lib
from resources.lib import catalog as catalog_lib

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def _url(**params):
    return "%s?%s" % (BASE_URL, urllib.parse.urlencode(params))


def _add_dir(label, params, art=None, info=None, is_folder=True):
    item = xbmcgui.ListItem(label=label)
    if art:
        item.setArt({k: v for k, v in art.items() if v})
    if info:
        item.setInfo("video", info)
    xbmcplugin.addDirectoryItem(HANDLE, _url(**params), item, is_folder)


def _playable_episode(label, episode_url, art=None, info=None):
    """A single playable episode entry (IsPlayable -> action=play)."""
    item = xbmcgui.ListItem(label=label, offscreen=True)
    item.setProperty("IsPlayable", "true")
    if art:
        item.setArt({k: v for k, v in art.items() if v})
    info = dict(info or {})
    info.setdefault("mediatype", "episode")
    item.setInfo("video", info)
    xbmcplugin.addDirectoryItem(
        HANDLE,
        _url(action="play", url=episode_url, title=label),
        item,
        False,
    )


def _show_art(show):
    return {"poster": show.get("poster"), "fanart": show.get("fanart")}


def _episode_label(show_title, season_no, ep):
    return "%s - S%dE%d: %s" % (
        show_title, season_no, ep.get("number"), ep.get("title"))


def _episode_info(show, season_no, ep):
    return {
        "title": ep.get("title"),
        "tvshowtitle": show.get("title"),
        "season": season_no,
        "episode": ep.get("number"),
        "plot": show.get("description"),
        "date": ep.get("published"),
        "mediatype": "episode",
    }


def _episode_art(show, ep):
    return {
        "thumb": ep.get("thumb"),
        "poster": show.get("poster"),
        "fanart": show.get("fanart"),
    }


def list_root():
    xbmcplugin.setPluginCategory(HANDLE, "KayiFamily TV")
    xbmcplugin.setContent(HANDLE, "tvshows")
    _add_dir("Latest Episodes", {"action": "latest"})
    _add_dir("All Shows", {"action": "shows"})
    _add_dir("Search", {"action": "search"})
    _add_dir("Documentaries", {"action": "docs"})
    xbmcplugin.endOfDirectory(HANDLE)


def list_latest(catalog):
    xbmcplugin.setPluginCategory(HANDLE, "Latest Episodes")
    xbmcplugin.setContent(HANDLE, "episodes")
    for entry in catalog_lib.get_latest(catalog):
        show = catalog_lib.get_show(catalog, entry.get("show_id")) or {}
        label = "%s: %s" % (entry.get("show_title"), entry.get("title"))
        info = _episode_info(show, entry.get("season"), entry)
        info["title"] = label
        _playable_episode(label, entry.get("url"),
                          art=_episode_art(show, entry), info=info)
    xbmcplugin.endOfDirectory(HANDLE)


def list_shows(catalog):
    xbmcplugin.setPluginCategory(HANDLE, "All Shows")
    xbmcplugin.setContent(HANDLE, "tvshows")
    for show in catalog_lib.get_shows(catalog):
        n_eps = sum(len(s.get("episodes", [])) for s in show.get("seasons", []))
        label = "%s (%d episodes)" % (show.get("title"), n_eps)
        _add_dir(label, {"action": "show", "show_id": show.get("id")},
                 art=_show_art(show),
                 info={"title": show.get("title"), "plot": show.get("description"),
                       "mediatype": "tvshow"})
    xbmcplugin.endOfDirectory(HANDLE)


def list_seasons(catalog, show_id):
    show = catalog_lib.get_show(catalog, show_id)
    if not show:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    xbmcplugin.setPluginCategory(HANDLE, show.get("title"))
    xbmcplugin.setContent(HANDLE, "seasons")
    for season in show.get("seasons", []):
        label = "Season %d (%d episodes)" % (
            season.get("number"), len(season.get("episodes", [])))
        _add_dir(label,
                 {"action": "season", "show_id": show_id,
                  "season": season.get("number")},
                 art=_show_art(show),
                 info={"title": label, "tvshowtitle": show.get("title"),
                       "season": season.get("number"),
                       "plot": show.get("description"),
                       "mediatype": "season"})
    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes(catalog, show_id, season_no):
    show = catalog_lib.get_show(catalog, show_id)
    season = catalog_lib.get_season(show or {}, season_no)
    if not season:
        xbmcplugin.endOfDirectory(HANDLE)
        return
    xbmcplugin.setPluginCategory(
        HANDLE, "%s - Season %d" % (show.get("title"), season_no))
    xbmcplugin.setContent(HANDLE, "episodes")
    for ep in season.get("episodes", []):
        label = "Episode %d" % ep.get("number")
        _playable_episode(label, ep.get("url"),
                          art=_episode_art(show, ep),
                          info=_episode_info(show, season_no, ep))
    xbmcplugin.endOfDirectory(HANDLE)


def list_docs(catalog):
    xbmcplugin.setPluginCategory(HANDLE, "Documentaries")
    xbmcplugin.setContent(HANDLE, "episodes")
    docs = catalog_lib.get_documentaries(catalog)
    for ep in docs:
        _playable_episode(ep.get("title"), ep.get("url"),
                          art={"thumb": ep.get("thumb")},
                          info={"title": ep.get("title"),
                                "date": ep.get("published"),
                                "mediatype": "episode"})
    xbmcplugin.endOfDirectory(HANDLE)


def do_search(catalog):
    kb = xbmc.Keyboard("", "Search KayiFamily TV")
    kb.doModal()
    if not kb.isConfirmed():
        return
    query = kb.getText().strip()
    if not query:
        return
    xbmcplugin.setPluginCategory(HANDLE, "Search: %s" % query)
    xbmcplugin.setContent(HANDLE, "episodes")
    for hit in catalog_lib.search(catalog, query):
        show = hit["show"]
        if hit["type"] == "show":
            _add_dir(show.get("title"),
                     {"action": "show", "show_id": show.get("id")},
                     art=_show_art(show),
                     info={"title": show.get("title"),
                           "plot": show.get("description"),
                           "mediatype": "tvshow"})
        else:
            ep = hit["episode"]
            label = _episode_label(show.get("title"), hit["season"], ep)
            _playable_episode(label, ep.get("url"),
                              art=_episode_art(show, ep),
                              info=_episode_info(show, hit["season"], ep))
    xbmcplugin.endOfDirectory(HANDLE)


def play(episode_url, title):
    preferred = ADDON.getSettingString("preferred_source") or "Auto"
    preferred = preferred.lower()
    log("Play requested: %s (preferred source: %s)" % (episode_url, preferred))
    try:
        result = resolve_episode(episode_url, preferred_source=preferred)
    except ResolverError as exc:
        log("Resolver failed: %s" % exc, xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "KayiFamily TV", "Could not play: %s" % exc,
            xbmcgui.NOTIFICATION_ERROR, 6000,
        )
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    except Exception as exc:  # never crash Kodi with a traceback
        log("Unexpected resolver error: %r" % exc, xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "KayiFamily TV", "Unexpected error while resolving the video.",
            xbmcgui.NOTIFICATION_ERROR, 6000,
        )
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return

    # offscreen=True: this item only carries playback info to the player,
    # it is never shown in a listing (romanvm/plugin.video.example pattern).
    item = xbmcgui.ListItem(offscreen=True)
    item.setLabel(title)
    item.setPath(result["video_url"])
    item.setInfo("video", {"title": title, "mediatype": "episode"})

    stream_type = result.get("stream_type", "mp4")
    headers = result.get("headers") or {}
    if stream_type == "hls":
        # Route HLS through inputstream.adaptive so Kodi handles segments.
        item.setProperty("inputstream", "inputstream.adaptive")
        item.setProperty("inputstream.adaptive.manifest_type", "hls")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if headers:
            header_str = "&".join("%s=%s" % kv for kv in headers.items())
            # manifest_headers covers the playlist fetch, stream_headers covers
            # segments/sub-playlists (some hosts 403 without them on both).
            item.setProperty("inputstream.adaptive.manifest_headers", header_str)
            item.setProperty("inputstream.adaptive.stream_headers", header_str)
    elif headers:
        # Progressive MP4/DASH: Kodi appends "|Header=Value" itself.
        item.setPath(
            result["video_url"]
            + "|" + "&".join("%s=%s" % kv for kv in headers.items())
        )

    subtitles_lib.attach(item, result.get("subtitles") or [])

    log("Handing to Kodi player: %s [%s]" % (result["source"], stream_type))
    xbmcplugin.setResolvedUrl(HANDLE, True, item)


def router():
    params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    action = params.get("action")
    debug("Router action=%s" % action)
    if action == "play":
        play(params["url"], params.get("title", "Episode"))
        return
    catalog, from_cache = catalog_lib.load_catalog()
    debug("Catalog loaded (%d shows, from_cache=%s)"
          % (len(catalog_lib.get_shows(catalog)), from_cache))
    if action == "latest":
        list_latest(catalog)
    elif action == "shows":
        list_shows(catalog)
    elif action == "show":
        list_seasons(catalog, params.get("show_id"))
    elif action == "season":
        list_episodes(catalog, params.get("show_id"),
                      int(params.get("season", 0)))
    elif action == "docs":
        list_docs(catalog)
    elif action == "search":
        do_search(catalog)
    else:
        list_root()


if __name__ == "__main__":
    router()
