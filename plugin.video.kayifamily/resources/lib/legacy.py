"""Legacy player adapter for KayiFamily TV.

Older KayiFamily episodes use legacy player embeds instead of the modern
OK.ru/VidMoly tabs:

    wakeupummah.com/fireplayer/...   (site's own legacy player)
    vkvideo.ru / vk.com video embeds  (VK Video)
    videa.hu player                   (Hungarian host)

These players are JavaScript-driven with no accessible HTTP API for
stream URLs (the fireplayer returns empty bodies to HTTP clients;
videa.hu is behind reCAPTCHA). They cannot currently be resolved to
playable streams without executing JavaScript or bypassing CAPTCHAs,
which we do not do.

This adapter DETECTS legacy players in an episode's own post content so
the UI can fail clearly ("legacy player, not yet supported") instead of
silently dropping the episode or -- worse -- playing another episode's
video (issue #3). If a legacy player later exposes a supported stream
method, resolution logic belongs here, behind this interface.
"""

import re

from .logger import log, debug
from .resolver import ResolverError


class LegacyPlayerError(ResolverError):
    """The episode has a player, but its type is not yet supported."""


# (player_type, regex) in detection priority order
_LEGACY_PATTERNS = [
    ("wakeupummah", re.compile(r"https?://wakeupummah\.com/fireplayer/[^\"]+", re.I)),
    ("vkvideo", re.compile(r"https?://(?:vkvideo\.ru|vk\.com)/video_ext\.php[^\"]+", re.I)),
    ("videa", re.compile(r"(?:https?:)?//videa\.hu/player[^\"]+", re.I)),
]

_IFRAME_RE = re.compile(r'<iframe[^>]+src="([^"]+)"', re.IGNORECASE)


def detect_legacy_players(post_content):
    """Return [(player_type, iframe_url)] for legacy players in the post.

    Only the episode's OWN post content is inspected (same scoping rule
    as the modern resolver -- issue #3).
    """
    found = []
    for match in _IFRAME_RE.finditer(post_content or ""):
        src = match.group(1).strip()
        for player_type, pattern in _LEGACY_PATTERNS:
            if pattern.search(src):
                # normalize HTML entities VK uses
                src = src.replace("&amp;", "&")
                found.append((player_type, src))
                debug("legacy player detected: %s -> %s" % (player_type, src[:80]))
                break
    # de-duplicate, keep order
    seen, unique = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def resolve_legacy(player_type, iframe_url, session):
    """Attempt to resolve a legacy player to a stream dict.

    Currently no legacy player exposes a supported stream method, so
    this always raises LegacyPlayerError with a clear message. The
    episode stays visible in the catalog and fails clearly instead of
    disappearing or playing the wrong video.
    """
    log("Legacy player '%s' is not yet supported (%s)"
        % (player_type, iframe_url[:80]))
    raise LegacyPlayerError(
        "This episode uses the legacy '%s' player, which is not "
        "supported yet. It will play automatically once supported."
        % player_type)
