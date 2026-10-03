"""KayiFamily TV - minimal proof-of-concept Kodi video add-on.

Navigation:
    KayiFamily TV
        └── Test Series
              └── Test Episode
                    └── Play

Play resolves the episode live (no hard-coded stream URLs) and hands the
result to Kodi's native player via xbmcplugin.setResolvedUrl.
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

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

# The single proof-of-concept episode. Only the *page* URL is fixed here;
# the actual video stream URL is resolved fresh on every Play.
TEST_SERIES_NAME = "Mehmed Fetihler Sultani (Test)"
TEST_EPISODE = {
    "title": "Episode 85 (Test)",
    "url": "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/",
}


def _url(**params):
    return "%s?%s" % (BASE_URL, urllib.parse.urlencode(params))


def _add_dir(label, params, is_folder=True):
    item = xbmcgui.ListItem(label=label)
    xbmcplugin.addDirectoryItem(HANDLE, _url(**params), item, is_folder)


def list_root():
    xbmcplugin.setPluginCategory(HANDLE, "KayiFamily TV")
    xbmcplugin.setContent(HANDLE, "tvshows")
    _add_dir(TEST_SERIES_NAME, {"action": "series"})
    xbmcplugin.endOfDirectory(HANDLE)


def list_series():
    xbmcplugin.setPluginCategory(HANDLE, TEST_SERIES_NAME)
    xbmcplugin.setContent(HANDLE, "episodes")
    _add_dir(TEST_EPISODE["title"], {
        "action": "episode",
        "url": TEST_EPISODE["url"],
        "title": TEST_EPISODE["title"],
    })
    xbmcplugin.endOfDirectory(HANDLE)


def list_episode(episode_url, title):
    item = xbmcgui.ListItem(label=title)
    item.setProperty("IsPlayable", "true")
    item.setInfo("video", {"title": title, "mediatype": "episode"})
    xbmcplugin.addDirectoryItem(
        HANDLE,
        _url(action="play", url=episode_url, title=title),
        item,
        False,
    )
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
    debug("Router action=%s params=%s" % (action, params))
    if action == "series":
        list_series()
    elif action == "episode":
        list_episode(params["url"], params.get("title", "Episode"))
    elif action == "play":
        play(params["url"], params.get("title", "Episode"))
    else:
        list_root()


if __name__ == "__main__":
    router()
