"""Official broadcaster YouTube adapter for KayiFamily TV.

Input: a VERIFIED official YouTube video ID (from catalog episode metadata).
Output: a Kodi plugin URL that opens the broadcaster's official YouTube
copy through plugin.video.youtube.

We do NOT:
  - download YouTube videos
  - rehost them
  - extract raw YouTube CDN links
  - bundle yt-dlp into production
  - bypass YouTube restrictions or authentication

We are simply opening the broadcaster's official YouTube copy through Kodi.
The video ID must be explicitly verified (official channel, correct show,
correct episode number, full episode) before it enters the catalog.
"""

import re

from ..logger import log, debug

# plugin.video.youtube play URL. The add-on must be installed; Kodi can
# install it from the official repository.
YOUTUBE_PLAY_URL = "plugin://plugin.video.youtube/play/?video_id=%s"

# YouTube video IDs are 11 chars: [A-Za-z0-9_-]
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class YouTubeAdapterError(Exception):
    """Raised when the YouTube adapter cannot produce a playback URL."""


def is_valid_video_id(video_id):
    """True if the string looks like a real YouTube video ID."""
    return bool(video_id) and bool(_VIDEO_ID_RE.match(video_id))


def build_play_url(video_id):
    """Return the plugin.video.youtube playback URL for a video ID.

    Raises YouTubeAdapterError if the ID is not a valid YouTube video ID.
    No network access, no stream extraction -- just the plugin URL.
    """
    if not is_valid_video_id(video_id):
        raise YouTubeAdapterError(
            "Invalid YouTube video ID: %r" % (video_id,))
    url = YOUTUBE_PLAY_URL % video_id
    debug("YouTube official play URL: %s" % url)
    return url


def resolve_episode_source(video_id, episode_label=""):
    """Resolve a verified official YouTube video ID to a playback dict.

    Returns a dict matching the resolver contract:
        {
            "video_url":  "<plugin://... URL>",
            "stream_type": "youtube",
            "headers":    {},
            "subtitles":  [],
            "source":     "youtube_official",
        }
    Subtitles are attached separately by the caller if a local SRT exists.
    """
    url = build_play_url(video_id)
    log("YouTube official source: %s -> %s" % (episode_label, video_id))
    return {
        "video_url": url,
        "stream_type": "youtube",
        "headers": {},
        "subtitles": [],
        "source": "youtube_official",
    }
