"""Tests for the official YouTube adapter and its fallback chain position."""

import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin.video.kayifamily"
sys.path.insert(0, str(PLUGIN_DIR))

from resources.lib.adapters import youtube_official  # noqa: E402
from resources.lib import resolver  # noqa: E402


def test_valid_video_id():
    assert youtube_official.is_valid_video_id("S76TuoUjZDg")
    assert youtube_official.is_valid_video_id("dQw4w9WgXcQ")


def test_invalid_video_id():
    assert not youtube_official.is_valid_video_id("")
    assert not youtube_official.is_valid_video_id(None)
    assert not youtube_official.is_valid_video_id("too-short")
    assert not youtube_official.is_valid_video_id("has spaces!!")
    assert not youtube_official.is_valid_video_id("waytoolongvideoid123")


def test_build_play_url():
    url = youtube_official.build_play_url("S76TuoUjZDg")
    assert url == "plugin://plugin.video.youtube/play/?video_id=S76TuoUjZDg"


def test_build_play_url_rejects_bad_id():
    with pytest.raises(youtube_official.YouTubeAdapterError):
        youtube_official.build_play_url("not-a-valid-id!!!")


def test_resolve_episode_source_contract():
    result = youtube_official.resolve_episode_source("S76TuoUjZDg", "Mehmed S1E1")
    assert set(result) == {"video_url", "stream_type", "headers",
                           "subtitles", "source"}
    assert result["video_url"] == \
        "plugin://plugin.video.youtube/play/?video_id=S76TuoUjZDg"
    assert result["stream_type"] == "youtube"
    assert result["source"] == "youtube_official"


def test_resolve_episode_falls_back_to_youtube(monkeypatch):
    """When Kayi sources fail, a verified YouTube ID is used -- never another episode."""
    monkeypatch.setattr(
        resolver, "_fetch_episode_post",
        lambda url: ("<html>no players here</html>", url),
    )
    monkeypatch.setattr(
        resolver, "_sources_from_content",
        lambda content: [],
    )
    import resources.lib.legacy as legacy_mod
    monkeypatch.setattr(legacy_mod, "detect_legacy_players", lambda c: [])

    result = resolver.resolve_episode(
        "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-1/",
        youtube_video_id="S76TuoUjZDg",
    )
    assert result["source"] == "youtube_official"
    assert result["video_url"].endswith("video_id=S76TuoUjZDg")


def test_resolve_episode_no_youtube_id_fails_clearly(monkeypatch):
    """Without any source and no YouTube ID, resolution fails clearly."""
    monkeypatch.setattr(
        resolver, "_fetch_episode_post",
        lambda url: ("<html>no players here</html>", url),
    )
    monkeypatch.setattr(
        resolver, "_sources_from_content",
        lambda content: [],
    )
    import resources.lib.legacy as legacy_mod
    monkeypatch.setattr(legacy_mod, "detect_legacy_players", lambda c: [])

    with pytest.raises(resolver.ResolverError) as exc_info:
        resolver.resolve_episode("https://kayifamilytv.com/ep")
    assert "No video player" in str(exc_info.value)
