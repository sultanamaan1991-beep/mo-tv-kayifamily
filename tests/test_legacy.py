"""Unit tests for the legacy player adapter (issue #4).

Legacy players are detected in the episode's OWN post content and fail
clearly instead of dropping the episode or playing another episode's
video (issue #3).
"""

import pytest

import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin.video.kayifamily"
sys.path.insert(0, str(PLUGIN_DIR))

from resources.lib.legacy import (
    detect_legacy_players,
    resolve_legacy,
    LegacyPlayerError,
)

WAKEUP_IFRAME = (
    '<iframe src="https://wakeupummah.com/fireplayer/video/806fec5af7f5b48b8a3" '
    'width="640" height="360"></iframe>'
)
VK_IFRAME = (
    '<iframe src="https://vkvideo.ru/video_ext.php?oid=-230035790&amp;id=456239042" '
    'width="640" height="360"></iframe>'
)
VIDEA_IFRAME = '<iframe src="//videa.hu/player?v=lCmjRYrDalVHObGw"></iframe>'
OKRU_IFRAME = '<iframe src="https://ok.ru/videoembed/10142096230942"></iframe>'


def test_detects_wakeupummah():
    found = detect_legacy_players(WAKEUP_IFRAME)
    assert len(found) == 1
    assert found[0][0] == "wakeupummah"
    assert "wakeupummah.com/fireplayer" in found[0][1]


def test_detects_vkvideo():
    found = detect_legacy_players(VK_IFRAME)
    assert len(found) == 1
    assert found[0][0] == "vkvideo"


def test_detects_videa():
    found = detect_legacy_players(VIDEA_IFRAME)
    assert len(found) == 1
    assert found[0][0] == "videa"


def test_ignores_modern_players():
    assert detect_legacy_players(OKRU_IFRAME) == []


def test_ignores_template_widget_embeds():
    # issue #3: unrelated OK.ru widgets must not be treated as legacy
    widget = '<iframe src="https://ok.ru/videoembed/17557429029406"></iframe>'
    assert detect_legacy_players(widget) == []


def test_resolve_legacy_fails_clearly():
    with pytest.raises(LegacyPlayerError) as exc:
        resolve_legacy("wakeupummah",
                       "https://wakeupummah.com/fireplayer/video/abc", None)
    assert "wakeupummah" in str(exc.value)
    assert "not supported yet" in str(exc.value)


def test_legacy_error_is_resolver_error():
    from resources.lib.resolver import ResolverError
    assert issubclass(LegacyPlayerError, ResolverError)


def test_chain_tries_legacy_after_modern_fails(monkeypatch):
    """BLOCKER 2: legacy from the SAME post must be tried when modern fails."""
    import sys
    from pathlib import Path
    PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin.video.kayifamily"
    sys.path.insert(0, str(PLUGIN_DIR))
    from resources.lib import resolver

    post_html = (
        '<iframe src="https://vidmoly.org/embed-broken123.html"></iframe>'
        '<iframe src="https://wakeupummah.com/fireplayer/video/abc123"></iframe>'
    )
    monkeypatch.setattr(resolver, "_fetch_episode_post",
                        lambda url: (post_html, url))
    # modern source fails
    def fake_player_source(label, url):
        raise resolver.ResolverError("upstream broken")
    monkeypatch.setattr(resolver, "resolve_player_source", fake_player_source)

    # legacy adapter succeeds (simulating a future working adapter)
    from resources.lib import legacy
    def fake_legacy(ptype, url, session):
        return {"video_url": "https://cdn.example/legacy.mp4",
                "stream_type": "mp4", "headers": {}, "subtitles": []}
    monkeypatch.setattr(legacy, "resolve_legacy", fake_legacy)
    # re-import to pick up monkeypatched legacy.resolve_legacy
    import importlib
    importlib.reload(resolver)
    monkeypatch.setattr(resolver, "_fetch_episode_post",
                        lambda url: (post_html, url))
    monkeypatch.setattr(resolver, "resolve_player_source", fake_player_source)

    result = resolver.resolve_episode("https://kayifamilytv.com/ep")
    assert result["source"] == "legacy:wakeupummah"
    assert result["video_url"] == "https://cdn.example/legacy.mp4"
