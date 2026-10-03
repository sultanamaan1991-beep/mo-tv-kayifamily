"""KayiFamily OK.ru adapter.

Resolves an OK.ru videoembed iframe URL (from the episode's own
WordPress post) to signed stream URLs, regenerated at playback time.
"""

import html as html_module
import re

from ..logger import log, debug

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_OKRU_RE = re.compile(r"(?:https?:)?//ok\.ru/videoembed/(\d+)", re.IGNORECASE)


class OkruAdapterError(Exception):
    """Raised when the OK.ru adapter cannot resolve a stream."""


def matches(iframe_url):
    """True if this adapter handles the given iframe URL."""
    return bool(_OKRU_RE.search(iframe_url or ""))


def _unescape_url(url):
    return (
        url.replace("\\/", "/")
        .replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\u003f", "?")
    )


def resolve(iframe_url, session):
    """Resolve an OK.ru videoembed URL to (video_url, stream_type, headers).

    `session` is the resolver's _Session (cookie jar + User-Agent).
    Returns (video_url, stream_type, headers, subtitles).
    Raises OkruAdapterError on failure.
    """
    embed_url = iframe_url
    if embed_url.startswith("//"):
        embed_url = "https:" + embed_url
    final_url, raw_html = session.get_text(embed_url, referer="https://kayifamilytv.com/")
    log("Player host: ok.ru (embed %s)" % final_url)

    page = html_module.unescape(raw_html).replace("\\/", "/")
    headers = {"Referer": final_url, "User-Agent": USER_AGENT}

    # 1) Preferred: explicit HLS manifest from flashVars.
    m = re.search(r'"hlsManifestUrl"\s*:\s*"(https?://[^"]+)"', page)
    if m:
        hls_url = _unescape_url(m.group(1))
        log("Stream type detected: HLS (.m3u8)")
        if session.head_ok(hls_url, referer=final_url):
            log("HLS manifest reachable (HTTP 200/206 on probe).")
        return hls_url, "hls", headers, []

    # 2) Fallback: progressive MP4 renditions, best quality first.
    mp4_by_type = {}
    for m in re.finditer(
        r'"name"\s*:\s*"(?:mobile|lowest|low|sd|hd|full)"\s*,\s*'
        r'"url"\s*:\s*"(https?://[^"]+)"',
        page,
    ):
        url = _unescape_url(m.group(1))
        t = re.search(r"[?&]type=(\d)", url)
        if t:
            mp4_by_type.setdefault(t.group(1), url)
    for quality in ("5", "3", "2", "1", "0", "4"):
        if quality in mp4_by_type:
            log("Stream type detected: progressive MP4 (type=%s)" % quality)
            return mp4_by_type[quality], "mp4", headers, []

    raise OkruAdapterError(
        "OK.ru embed page loaded but contained no playable stream URLs.")
