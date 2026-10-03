"""Playback resolver for KayiFamily TV (proof of concept).

Public contract:

    resolve_episode(episode_url) -> dict

The dict always has this shape:

    {
        "video_url":  "<direct stream URL, regenerated on every call>",
        "stream_type": "hls" | "mp4" | "dash",
        "headers":    {"Referer": ..., "User-Agent": ...},   # only what playback needs
        "subtitles":  [{"lang": "en", "url": "...", "format": "vtt|srt"}, ...],
        "source":     "<which player tab was used, e.g. 'okru'|'moly'>",
    }

How it works (verified 2026-10-02 against
https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/):

1. Episode page -> player tabs are plain <iframe> embeds, e.g.
     https://vidmoly.org/embed-<id>.html        ("moLy" tab)
     https://ok.ru/videoembed/<id>?nochat=1     ("OkRu" tab)
2. The OK.ru embed page carries a flashVars JSON blob with signed,
   time-limited CDN URLs on hosts like ok6-4.vkuser.net:
     - HLS manifest:  .../video.m3u8?cmd=videoPlayerCdn&expires=...&sig=...
     - progressive MP4 renditions (mobile/lowest/low/sd/hd/full)
   The signed tokens are bound to the requesting IP and expire, so they
   are re-resolved live on every Play -- never stored.
3. English subtitles are burned into the video; no external subtitle
   files exist, so "subtitles" is [] (handled gracefully by the UI).

Raises ResolverError with a human-readable message on any failure so the
Kodi UI can fail cleanly. No DRM, paywalls, logins, CAPTCHAs or geo-blocks
are encountered or bypassed anywhere in this chain.
"""

import http.cookiejar
import re
import urllib.parse
import urllib.request

from .logger import log, debug

SITE_BASE = "https://kayifamilytv.com"

# A desktop Chrome User-Agent: the site serves its normal public player to it.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class ResolverError(Exception):
    """Raised when an episode cannot be resolved to a playable stream."""


class _Session(object):
    """One cookie jar + User-Agent for a whole resolution, like a browser tab."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def get_text(self, url, referer=None, timeout=25):
        headers = {"User-Agent": USER_AGENT}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        debug("GET %s (referer=%s)" % (url, referer))
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                final_url = resp.geturl()
                status = resp.status
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise ResolverError("HTTP %s while loading %s" % (exc.code, url))
        except urllib.error.URLError as exc:
            raise ResolverError("Could not reach %s: %s" % (url, exc.reason))
        debug("HTTP %s, %d bytes, final URL %s" % (status, len(body), final_url))
        return final_url, body

    def head_ok(self, url, referer=None, timeout=20):
        """True if the URL answers 200/206 to a ranged HEAD/GET."""
        headers = {"User-Agent": USER_AGENT, "Range": "bytes=0-1"}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                code = resp.status
                ctype = resp.headers.get("Content-Type", "")
            debug("probe %s -> HTTP %s (%s)" % (url[:100], code, ctype))
            return code in (200, 206)
        except Exception as exc:  # probe failure is not fatal by itself
            debug("probe %s failed: %s" % (url[:100], exc))
            return False


def _unescape_url(url):
    """Undo the JSON string escaping used inside the embed page source."""
    return (
        url.replace("\\/", "/")
        .replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\u003f", "?")
    )


# ---------------------------------------------------------------------------
# Step 1: episode page -> player iframe URL(s)
# ---------------------------------------------------------------------------

_IFRAME_RE = re.compile(
    r'<iframe[^>]+src="([^"]+)"', re.IGNORECASE
)

_OKRU_RE = re.compile(r"(?:https?:)?//ok\.ru/videoembed/(\d+)", re.IGNORECASE)
_MOLY_RE = re.compile(r"https?://vidmoly\.org/embed-[A-Za-z0-9]+\.html", re.IGNORECASE)


def find_player_sources(episode_url):
    """Return [(label, iframe_url), ...] for the episode page's player tabs."""
    session = _Session()
    final_url, html = session.get_text(episode_url)
    log("Episode page loaded: %s (HTTP 200)" % final_url)

    sources = []
    for match in _IFRAME_RE.finditer(html):
        src = match.group(1).strip()
        if _OKRU_RE.search(src):
            if src.startswith("//"):
                src = "https:" + src
            # strip the nochat query; the canonical embed URL is enough
            src = src.split("?")[0]
            sources.append(("okru", src))
            debug("iframe domain: ok.ru -> %s" % src)
        elif _MOLY_RE.search(src):
            sources.append(("moly", src))
            debug("iframe domain: vidmoly.org -> %s" % src)

    # de-duplicate, keep page order
    seen, unique = set(), []
    for label, src in sources:
        if (label, src) not in seen:
            seen.add((label, src))
            unique.append((label, src))
    return unique


# ---------------------------------------------------------------------------
# Step 2: player iframe URL -> direct stream URL
# ---------------------------------------------------------------------------


def _resolve_okru(session, iframe_url):
    """Resolve an OK.ru videoembed page to its signed stream URLs."""
    import html as html_module

    embed_url = iframe_url
    if embed_url.startswith("//"):
        embed_url = "https:" + embed_url
    final_url, raw_html = session.get_text(embed_url, referer=SITE_BASE + "/")
    log("Player host: ok.ru (embed %s)" % final_url)

    # The flashVars JSON is HTML-entity-encoded (&quot;) inside a JS string.
    # Unescape entities first so URL patterns terminate at real quotes.
    page = html_module.unescape(raw_html).replace("\\/", "/")

    headers = {"Referer": final_url, "User-Agent": USER_AGENT}

    # 1) Preferred: the explicit HLS manifest URL from flashVars.
    m = re.search(r'"hlsManifestUrl"\s*:\s*"(https?://[^"]+)"', page)
    if m:
        hls_url = _unescape_url(m.group(1))
        log("Stream type detected: HLS (.m3u8)")
        if session.head_ok(hls_url, referer=final_url):
            log("HLS manifest reachable (HTTP 200/206 on probe).")
        else:
            debug("HLS manifest probe failed; continuing anyway (Kodi will retry)")
        return hls_url, "hls", headers, []

    # 2) Fallback: progressive MP4 renditions, best quality first.
    #    OK.ru rendition ids: 4=mobile 0=lowest 1=low 2=sd 3=hd 5=full
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
            log("Stream type detected: progressive MP4 (rendition type=%s)" % quality)
            return mp4_by_type[quality], "mp4", headers, []

    raise ResolverError(
        "OK.ru embed page loaded but contained no playable stream URLs."
    )


def _resolve_moly(session, iframe_url):
    """VidMoly ('moLy' tab) resolver.

    Observed 2026-10-02: VidMoly's own player fails in a normal browser
    with JW Player Error 232011 ("This video file cannot be played") on
    both Episode 84 and 85 embeds -- the media is broken upstream, not a
    parsing problem. Nothing is bypassed here; the failure is reported.
    """
    raise ResolverError(
        "The 'moLy' (VidMoly) source is currently not playable: its own "
        "player reports the video file cannot be played (upstream media "
        "error). Try the 'OkRu' source instead."
    )


def resolve_player_source(label, iframe_url):
    """Resolve one player tab to (video_url, stream_type, headers, subtitles)."""
    session = _Session()
    if label == "okru":
        return _resolve_okru(session, iframe_url)
    if label == "moly":
        return _resolve_moly(session, iframe_url)
    raise ResolverError("Unknown player source '%s'." % label)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# In Auto mode the known-good source is tried first.
_SOURCE_PRIORITY = ("okru", "moly")


def resolve_episode(episode_url, preferred_source="auto"):
    """Resolve a public KayiFamily episode page to a playable stream dict."""
    log("Resolving episode: %s" % episode_url)
    sources = find_player_sources(episode_url)
    if not sources:
        raise ResolverError("No video player found on the episode page.")
    debug("Player tabs found: %s" % [label for label, _ in sources])

    if preferred_source and preferred_source != "auto":
        ordered = sorted(
            sources, key=lambda s: 0 if s[0] == preferred_source else 1
        )
    else:
        ordered = sorted(
            sources,
            key=lambda s: _SOURCE_PRIORITY.index(s[0])
            if s[0] in _SOURCE_PRIORITY
            else 99,
        )

    errors = []
    for label, iframe_url in ordered:
        try:
            video_url, stream_type, headers, subtitles = resolve_player_source(
                label, iframe_url
            )
            log("Resolved via '%s': %s" % (label, stream_type))
            debug("video_url: %s..." % video_url[:90])
            return {
                "video_url": video_url,
                "stream_type": stream_type,
                "headers": headers,
                "subtitles": subtitles,
                "source": label,
            }
        except ResolverError as exc:
            errors.append("%s: %s" % (label, exc))
            debug("Source '%s' failed: %s" % (label, exc))

    raise ResolverError(
        "Could not resolve a playable stream. Tried: %s" % "; ".join(errors)
    )


if __name__ == "__main__":
    import json
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if not target:
        print("usage: python3 -m resources.lib.resolver <episode_url>")
        sys.exit(2)
    try:
        print(json.dumps(resolve_episode(target), indent=2))
    except ResolverError as exc:
        print("RESOLVER FAILED: %s" % exc)
        sys.exit(1)
