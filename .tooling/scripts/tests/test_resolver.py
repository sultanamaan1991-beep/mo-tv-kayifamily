"""Kodi-independent unit tests for the KayiFamily resolver + subtitles.

Uses small hand-written fixtures (no live site dependency). A separate
LIVE test is opt-in via --live.
"""

import sys

import pytest

sys.path.insert(0, "/home/hatch/workspace/kayifamily-tv/plugin.video.kayifamily")

from resources.lib import resolver, subtitles  # noqa: E402

EPISODE_HTML_FIXTURE = """
<div class="sp-tab" data-sptab>
<span class="sp-tab__nav-link sp-tab__active" data-sptoggle="tab" for="#tab-1">
<span class="tab_title_area"><h4 class="sp-tab__tab_title">moLy</h4></span></span>
<span class="sp-tab__nav-link" data-sptoggle="tab" for="#tab-2">
<span class="tab_title_area"><h4 class="sp-tab__tab_title">OkRu</h4></span></span>
<div id="tab-1"><iframe src="https://vidmoly.org/embed-abc123.html"></iframe></div>
<div id="tab-2"><iframe src="//ok.ru/videoembed/999?nochat=1"></iframe></div>
</div>
"""

OKRU_EMBED_FIXTURE = (
    '{"flashvars":{"referer":"https://kayifamilytv.com/",'
    '"metadata":{"videos":[{"name":"hd","url":"https:\\/\\/cdn.example\\/x?type=3&sig=aa"},'
    '{"name":"full","url":"https:\\/\\/cdn.example\\/x?type=5&sig=bb"}]},'
    '"hlsManifestUrl":"https:\\/\\/cdn.example\\/video.m3u8?cmd=x&expires=1&sig=zz"}}'
)


class FakeSession:
    def __init__(self, pages):
        self.pages = pages

    def get_text(self, url, referer=None, timeout=25):
        return url, self.pages[url]

    def head_ok(self, url, referer=None, timeout=20):
        return True


def test_find_player_sources_extracts_tabs(monkeypatch):
    monkeypatch.setattr(
        resolver, "_Session",
        lambda: FakeSession({"https://kayifamilytv.com/ep": EPISODE_HTML_FIXTURE}),
    )
    sources = resolver.find_player_sources("https://kayifamilytv.com/ep")
    assert ("moly", "https://vidmoly.org/embed-abc123.html") in sources
    assert ("okru", "https://ok.ru/videoembed/999") in sources


def test_unescape_url():
    assert resolver._unescape_url("https:\\/\\/x\\/y?a\\u0026b=1") == \
        "https://x/y?a&b=1"


def test_resolve_okru_prefers_hls(monkeypatch):
    session = FakeSession({"https://ok.ru/videoembed/999": OKRU_EMBED_FIXTURE})
    url, stype, headers, subs = resolver._resolve_okru(
        session, "https://ok.ru/videoembed/999")
    assert stype == "hls"
    assert url == "https://cdn.example/video.m3u8?cmd=x&expires=1&sig=zz"
    assert headers["Referer"] == "https://ok.ru/videoembed/999"
    assert "User-Agent" in headers
    assert subs == []


def test_resolve_okru_falls_back_to_best_mp4(monkeypatch):
    import re
    html = re.sub(r'"hlsManifestUrl":"[^"]*",?', "", OKRU_EMBED_FIXTURE)
    session = FakeSession({"https://ok.ru/videoembed/999": html})
    url, stype, _, _ = resolver._resolve_okru(session, "https://ok.ru/videoembed/999")
    assert stype == "mp4"
    assert "type=5" in url  # 'full' beats 'hd'


def test_resolve_episode_contract(monkeypatch):
    monkeypatch.setattr(
        resolver, "find_player_sources",
        lambda url: [("okru", "https://ok.ru/videoembed/999")],
    )
    monkeypatch.setattr(
        resolver, "resolve_player_source",
        lambda label, surl: ("https://cdn.example/v.m3u8", "hls",
                             {"Referer": surl}, []),
    )
    result = resolver.resolve_episode("https://kayifamilytv.com/ep")
    assert set(result) == {"video_url", "stream_type", "headers",
                           "subtitles", "source"}
    assert result["source"] == "okru"


def test_resolve_episode_auto_prefers_okru(monkeypatch):
    calls = []
    monkeypatch.setattr(
        resolver, "find_player_sources",
        lambda url: [("moly", "https://vidmoly.org/e.html"),
                     ("okru", "https://ok.ru/videoembed/999")],
    )

    def fake_source(label, surl):
        calls.append(label)
        if label == "moly":
            raise resolver.ResolverError("broken upstream")
        return ("https://cdn.example/v.m3u8", "hls", {}, [])

    monkeypatch.setattr(resolver, "resolve_player_source", fake_source)
    result = resolver.resolve_episode("https://kayifamilytv.com/ep")
    assert result["source"] == "okru"
    assert calls[0] == "okru"  # okru tried first in auto mode


def test_subtitles_english_first():
    tracks = [{"lang": "tr", "url": "http://x/tr.vtt"},
              {"lang": "en", "url": "http://x/en.vtt"}]
    assert subtitles.pick_tracks(tracks)[0]["lang"] == "en"


def test_subtitles_attach_empty_is_noop():
    class FakeItem:
        def __init__(self):
            self.subs = None

        def setSubtitles(self, urls):
            self.subs = urls

    item = FakeItem()
    subtitles.attach(item, [])
    assert item.subs is None


@pytest.mark.live
def test_live_episode_resolves():
    result = resolver.resolve_episode(
        "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/")
    assert result["stream_type"] == "hls"
    assert result["video_url"].startswith("https://")
    assert "m3u8" in result["video_url"]
