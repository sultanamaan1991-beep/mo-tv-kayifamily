"""KayiFamily Videa.hu adapter (placeholder for future authorized use).

Videa.hu embeds appear on some KayiFamily episode posts (notably Kurulus
Orhan). This adapter is a placeholder: Videa stream resolution is NOT
implemented in the add-on. If Videa becomes an approved source, implement
`resolve()` here following the same contract as kayi_okru.

Do NOT manually recreate Videa's token algorithm or bundle yt-dlp.
"""


class VideaAdapterError(Exception):
    """Raised when the Videa adapter cannot resolve a stream."""


def matches(iframe_url):
    """True if this adapter would handle the given iframe URL."""
    url = (iframe_url or "").lower()
    return "videa.hu" in url


def resolve(iframe_url, session):
    """Not implemented -- Videa is an optional future source only."""
    raise VideaAdapterError(
        "Videa.hu is not yet a supported playback source in this add-on.")
