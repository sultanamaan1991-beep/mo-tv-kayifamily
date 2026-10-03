"""Subtitle handling for KayiFamily TV.

The resolver reports external subtitle tracks as:
    [{"lang": "en", "url": "...", "format": "vtt"|"srt"}, ...]

Kodi plays external subtitle files natively when they are attached to the
ListItem via setSubtitles(). English is preferred automatically: the
resolver orders tracks so English comes first, and this helper keeps that
order (Kodi shows the first track by default).
"""

from .logger import log, debug


def pick_tracks(tracks, preferred_lang="en"):
    """Order subtitle tracks so the preferred language comes first."""
    tracks = list(tracks or [])
    preferred = [t for t in tracks if t.get("lang") == preferred_lang]
    rest = [t for t in tracks if t.get("lang") != preferred_lang]
    return preferred + rest


def attach(listitem, tracks):
    """Attach external subtitle URLs to a Kodi ListItem. No-op when empty."""
    ordered = pick_tracks(tracks)
    urls = [t["url"] for t in ordered if t.get("url")]
    if not urls:
        debug("No external subtitles to attach (may be burned in).")
        return
    debug("Attaching subtitles: %s" % urls)
    listitem.setSubtitles(urls)
    log("Attached %d subtitle track(s), English preferred." % len(urls))
