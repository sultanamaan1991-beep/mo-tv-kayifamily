"""Playback resolver for KayiFamily TV (proof of concept).

Public contract:

    resolve_episode(episode_url, youtube_video_id=None) -> dict

The dict always has this shape:

    {
        "video_url":  "<direct stream URL, regenerated on every call>",
        "stream_type": "hls" | "mp4" | "dash" | "youtube",
        "headers":    {"Referer": ..., "User-Agent": ...},   # only what playback needs
        "subtitles":  [{"lang": "en", "url": "...", "format": "vtt|srt"}, ...],
        "source":     "<which adapter was used>",
    }

Source chain per episode (issue #4):
  1. every modern source (OK.ru / VidMoly) from the episode's OWN post
  2. every legacy source from THAT SAME post (wakeupummah/vk/videa)
  3. approved official fallback: verified broadcaster YouTube video ID
  4. fail clearly -- never substitute another episode's video

Identity scoping (issue #3) is preserved at every step: only the
episode's own post content is ever inspected. YouTube fallback uses an
explicit per-episode verified video ID from the catalog -- never a
search result or a guess.
"""

import http.cookiejar
import re
import urllib.parse
import urllib.request

from .logger import log, debug
from .adapters import kayi_okru, kayi_videa, youtube_official

SITE_BASE = "https://kayifamilytv.com"

# A desktop Chrome User-Agent: the site serves its normal public player to it.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class ResolverError(Exception):
    """Raised when an episode cannot be resolved to a playable stream."""


class KayiUnavailableError(ResolverError):
    """KayiFamily site/network is unreachable; identity could not be evaluated.

    Covers DNS failures, timeouts, connection refused, and HTTP errors
    where the episode page (or its WP API post) could not be loaded at
    all. When this happens, the resolver may fall back to the episode's
    already-verified official YouTube ID -- the identity of the YouTube
    video was verified independently at catalog build time.
    """


class EpisodeIdentityError(ResolverError):
    """Evidence that the loaded page is not the requested episode.

    Covers post-ID/canonical mismatches and pages where the episode
    cannot be identified. This MUST fail closed: the YouTube fallback
    is never used to hide an identity mismatch (Issue #3).
    """


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
            raise KayiUnavailableError(
                "HTTP %s while loading %s" % (exc.code, url))
        except urllib.error.URLError as exc:
            raise KayiUnavailableError(
                "Could not reach %s: %s" % (url, exc.reason))
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


# ---------------------------------------------------------------------------
# Step 1: episode page -> player iframe URL(s)
# ---------------------------------------------------------------------------

_IFRAME_RE = re.compile(
    r'<iframe[^>]+src="([^"]+)"', re.IGNORECASE
)

_OKRU_RE = re.compile(r"(?:https?:)?//ok\.ru/videoembed/(\d+)", re.IGNORECASE)
_MOLY_RE = re.compile(r"https?://vidmoly\.(?:org|biz|net)/embed-[A-Za-z0-9]+\.html", re.IGNORECASE)

# WordPress REST API for canonical post data. Player iframes are taken
# ONLY from the episode's own post content (content.rendered) -- never
# from the full page HTML, which also contains template-injected
# "latest videos" player widgets belonging to OTHER episodes.
WP_API = SITE_BASE + "/wp-json/wp/v2"

_POSTID_RE = re.compile(r"postid-(\d+)", re.IGNORECASE)


def _get_post_content(session, episode_url, final_url, html):
    """Return the episode's own post content via the WordPress API.

    Identity validation: the API post's canonical link must match the
    final page URL. Any mismatch fails closed -- we never want to play
    a video belonging to a different episode.
    """
    m = _POSTID_RE.search(html)
    if not m:
        raise EpisodeIdentityError(
            "Could not identify the episode on the page (no post ID).")
    post_id = m.group(1)
    debug("Episode post ID: %s" % post_id)

    api_url = "%s/posts/%s" % (WP_API, post_id)
    _, body = session.get_text(api_url, referer=SITE_BASE + "/")
    try:
        import json
        post = json.loads(body)
    except ValueError:
        # API returned something unparseable: identity could not be
        # evaluated (site issue), not evidence of a wrong episode.
        raise KayiUnavailableError(
            "Could not read episode data (post %s)." % post_id)

    canonical = (post.get("link") or "").rstrip("/")
    if canonical and canonical != final_url.rstrip("/"):
        raise EpisodeIdentityError(
            "Episode identity mismatch: page %s does not match post %s."
            % (final_url, canonical))
    debug("Episode identity confirmed: %s" % canonical)
    return post.get("content", {}).get("rendered", "")


def _fetch_episode_post(episode_url):
    """Fetch episode page, validate identity via WP API.

    Returns (post_content, final_url). Raises ResolverError on any
    identity problem -- fail closed, never resolve another episode.
    """
    session = _Session()
    final_url, html = session.get_text(episode_url)
    log("Episode page loaded: %s (HTTP 200)" % final_url)
    content = _get_post_content(session, episode_url, final_url, html)
    return content, final_url


def find_player_sources(episode_url):
    """Return [(label, iframe_url), ...] for the episode's OWN player.

    Only <iframe> embeds inside the episode's WordPress post content are
    considered. Template-injected widgets (e.g. "latest videos" players
    for other episodes) are ignored, so Episode N can never resolve to
    Episode M's video.
    """
    content, _ = _fetch_episode_post(episode_url)
    return _sources_from_content(content)


def _sources_from_content(content):
    """Extract [(label, iframe_url)] modern player sources from post HTML."""
    sources = []
    for match in _IFRAME_RE.finditer(content):
        src = match.group(1).strip()
        if _OKRU_RE.search(src):
            if src.startswith("//"):
                src = "https:" + src
            # strip the nochat query; the canonical embed URL is enough
            src = src.split("?")[0]
            sources.append(("okru", src))
            debug("episode player iframe: ok.ru -> %s" % src)
        elif _MOLY_RE.search(src):
            sources.append(("moly", src))
            debug("episode player iframe: vidmoly.org -> %s" % src)

    # de-duplicate, keep page order
    seen, unique = set(), []
    for label, src in sources:
        if (label, src) not in seen:
            seen.add((label, src))
            unique.append((label, src))
    if not unique:
        log("Episode's own player has no OK.ru/VidMoly embed.")
    return unique


# ---------------------------------------------------------------------------
# Step 2: player iframe URL -> direct stream URL
# (implemented in resources/lib/adapters/: kayi_okru, kayi_videa)
# ---------------------------------------------------------------------------


def resolve_player_source(label, iframe_url, session=None):
    """Resolve one player tab to (video_url, stream_type, headers, subtitles)."""
    session = session or _Session()
    if label == "okru":
        try:
            return kayi_okru.resolve(iframe_url, session)
        except kayi_okru.OkruAdapterError as exc:
            raise ResolverError(str(exc))
    if label == "moly":
        raise ResolverError(
            "The 'moLy' (VidMoly) source is currently not playable: its own "
            "player reports the video file cannot be played (upstream media "
            "error). Try the 'OkRu' source instead."
        )
    raise ResolverError("Unknown player source '%s'." % label)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# In Auto mode the known-good source is tried first.
_SOURCE_PRIORITY = ("okru", "moly")


def resolve_episode(episode_url, preferred_source="auto", youtube_video_id=None):
    """Resolve a public KayiFamily episode page to a playable stream dict.

    Source chain per episode (issue #4):
      1. every modern source (OK.ru / VidMoly) from the episode's OWN post
      2. every legacy source from THAT SAME post (wakeupummah/vk/videa)
      3. approved official fallback: verified broadcaster YouTube video ID
      4. fail clearly -- never substitute another episode's video

    Kayi outage vs identity mismatch (Issue #3 stays intact):
      - KayiUnavailableError (network/site down, identity could not be
        evaluated) -> may fall back to the verified official YouTube ID.
      - EpisodeIdentityError (page/post mismatch, wrong episode evidence)
        -> fails closed immediately; YouTube is never used to hide it.

    The YouTube fallback uses an explicit per-episode verified video ID
    from the catalog -- never a search or a guess.
    """
    # deferred to avoid a circular import (legacy imports ResolverError)
    from .legacy import detect_legacy_players, resolve_legacy

    log("Resolving episode: %s" % episode_url)
    session = _Session()
    try:
        content, _ = _fetch_episode_post(episode_url)
    except EpisodeIdentityError:
        # Fail closed: never paper over an identity problem with YouTube.
        raise
    except KayiUnavailableError as exc:
        # Site/network down before identity could be evaluated: the
        # per-episode YouTube ID was verified independently, so it is
        # safe to fall back to it.
        log("Kayi unavailable (%s); trying official YouTube fallback." % exc)
        content = None

    sources = []
    legacy = []
    if content is not None:
        sources = _sources_from_content(content)
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
                label, iframe_url, session
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

    # All modern sources failed (or there were none): try every legacy
    # source from the SAME post before giving up. Skipped entirely when
    # Kayi was unreachable (content is None) -- there is no post to
    # inspect, so go straight to the YouTube fallback.
    if content is not None:
        legacy = detect_legacy_players(content)
    for player_type, iframe_url in legacy:
        try:
            result = resolve_legacy(player_type, iframe_url, session)
            log("Resolved via legacy '%s'" % player_type)
            result["source"] = "legacy:" + player_type
            return result
        except ResolverError as exc:
            errors.append("legacy-%s: %s" % (player_type, exc))
            debug("Legacy '%s' failed: %s" % (player_type, exc))

    # Approved official fallback: verified broadcaster YouTube video.
    # The ID comes from the catalog (explicit per-episode mapping) --
    # never from a search or a guess.
    if youtube_video_id:
        try:
            result = youtube_official.resolve_episode_source(
                youtube_video_id, episode_label=episode_url)
            log("Resolved via YouTube official fallback: %s" % youtube_video_id)
            return result
        except youtube_official.YouTubeAdapterError as exc:
            errors.append("youtube: %s" % exc)
            debug("YouTube fallback failed: %s" % exc)

    if not sources and not legacy and not youtube_video_id:
        if content is None:
            raise KayiUnavailableError(
                "KayiFamily is unreachable and no official YouTube "
                "fallback is mapped for this episode.")
        raise ResolverError("No video player found on the episode page.")
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
