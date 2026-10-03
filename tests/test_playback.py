"""Tests for main.py playback behavior (FIX 2, FIX 4).

Kodi modules (xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs) are mocked
so these run without Kodi.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin.video.kayifamily"


def _install_kodi_mocks(youtube_available=True, srt_exists=False):
    """Install mock xbmc* modules. Returns dict of mocks for assertions."""
    mods = {}

    xbmc = types.ModuleType("xbmc")
    xbmc.getCondVisibility = MagicMock(
        return_value=youtube_available)
    xbmc.LOGERROR = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGINFO = 0
    xbmc.LOGDEBUG = 3
    xbmc.log = MagicMock()
    xbmc.executebuiltin = MagicMock()
    mods["xbmc"] = xbmc

    xbmcaddon = types.ModuleType("xbmcaddon")
    addon = MagicMock()
    addon.getAddonInfo.return_value = "/fake/addon/path"
    addon.getSettingString.return_value = "Auto"
    xbmcaddon.Addon = MagicMock(return_value=addon)
    mods["xbmcaddon"] = xbmcaddon

    xbmcgui = types.ModuleType("xbmcgui")
    dialog = MagicMock()
    dialog.yesno.return_value = False
    xbmcgui.Dialog = MagicMock(return_value=dialog)
    listitem_instances = []

    class FakeListItem:
        def __init__(self, *a, **k):
            self.props = {}
            self.subtitles = None
            self.path = None
            listitem_instances.append(self)

        def setLabel(self, v): self.label = v
        def setPath(self, v): self.path = v
        def setInfo(self, *a, **k): pass
        def setArt(self, v): pass
        def setProperty(self, k, v): self.props[k] = v
        def setMimeType(self, v): pass
        def setContentLookup(self, v): pass
        def setSubtitles(self, urls): self.subtitles = urls

    xbmcgui.ListItem = FakeListItem
    xbmcgui.NOTIFICATION_ERROR = 1
    mods["xbmcgui"] = xbmcgui
    mods["listitems"] = listitem_instances
    mods["dialog"] = dialog

    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.setResolvedUrl = MagicMock()
    xbmcplugin.addDirectoryItem = MagicMock()
    xbmcplugin.endOfDirectory = MagicMock()
    xbmcplugin.setPluginCategory = MagicMock()
    xbmcplugin.setContent = MagicMock()
    mods["xbmcplugin"] = xbmcplugin

    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.exists = MagicMock(return_value=srt_exists)
    xbmcvfs.mkdirs = MagicMock()
    mods["xbmcvfs"] = xbmcvfs

    for name, mod in mods.items():
        if not name.startswith("listitems") and name != "dialog":
            sys.modules[name] = mod
    return mods


def _clear_kodi_mocks():
    for name in ("xbmc", "xbmcaddon", "xbmcgui", "xbmcplugin", "xbmcvfs"):
        sys.modules.pop(name, None)
    sys.modules.pop("main", None)


@pytest.fixture
def kodi_no_youtube():
    mods = _install_kodi_mocks(youtube_available=False)
    yield mods
    _clear_kodi_mocks()


@pytest.fixture
def kodi_with_youtube_srt():
    mods = _install_kodi_mocks(youtube_available=True, srt_exists=True)
    yield mods
    _clear_kodi_mocks()


@pytest.fixture
def kodi_with_youtube_no_srt():
    mods = _install_kodi_mocks(youtube_available=True, srt_exists=False)
    yield mods
    _clear_kodi_mocks()


def _load_main():
    sys.path.insert(0, str(PLUGIN_DIR))
    # main.py reads sys.argv[1] at import time
    with patch.object(sys, "argv", ["main.py", "1"]):
        if "main" in sys.modules:
            del sys.modules["main"]
        import main
    return main


def _fake_youtube_result():
    return {
        "video_url": "plugin://plugin.video.youtube/play/?video_id=KEWP2dELhrY",
        "stream_type": "youtube",
        "headers": {},
        "subtitles": [],
        "source": "youtube_official",
    }


def test_missing_youtube_addon_clear_failure(kodi_no_youtube):
    """FIX 4: YouTube needed but addon missing -> clear dialog, no blind handoff."""
    main = _load_main()
    with patch.object(main, "resolve_episode",
                      return_value=_fake_youtube_result()):
        main.HANDLE = 1
        main.play("https://kayifamilytv.com/ep", "EP1",
                  youtube_video_id="KEWP2dELhrY")
    # Dialog shown explaining the missing addon
    assert kodi_no_youtube["dialog"].yesno.called
    args = kodi_no_youtube["dialog"].yesno.call_args[0]
    assert "YouTube" in args[1]
    # Playback NOT resolved (no blind plugin:// handoff)
    resolve_calls = kodi_no_youtube["xbmcplugin"].setResolvedUrl.call_args_list
    assert resolve_calls
    assert resolve_calls[0][0][1] is False


def test_existing_srt_attached(kodi_with_youtube_srt):
    """FIX 2: bundled SRT exists -> attached to the ListItem."""
    main = _load_main()
    with patch.object(main, "resolve_episode",
                      return_value=_fake_youtube_result()):
        main.HANDLE = 1
        main.play("https://kayifamilytv.com/ep", "EP1",
                  youtube_video_id="KEWP2dELhrY",
                  subtitle_file="orhan/s01e01.en.srt")
    items = kodi_with_youtube_srt["listitems"]
    # Last ListItem is the resolved playback item
    played = items[-1]
    assert played.subtitles is not None
    assert played.subtitles[0].endswith("orhan/s01e01.en.srt")
    # And playback was allowed
    resolve_calls = kodi_with_youtube_srt["xbmcplugin"].setResolvedUrl.call_args_list
    assert resolve_calls[0][0][1] is True


def test_missing_srt_does_not_block_video(kodi_with_youtube_no_srt):
    """FIX 2: no SRT file -> video still plays, no subtitles attached."""
    main = _load_main()
    with patch.object(main, "resolve_episode",
                      return_value=_fake_youtube_result()):
        main.HANDLE = 1
        main.play("https://kayifamilytv.com/ep", "EP1",
                  youtube_video_id="KEWP2dELhrY",
                  subtitle_file="orhan/s01e01.en.srt")
    items = kodi_with_youtube_no_srt["listitems"]
    played = items[-1]
    assert played.subtitles is None  # no SRT attached
    resolve_calls = kodi_with_youtube_no_srt["xbmcplugin"].setResolvedUrl.call_args_list
    assert resolve_calls[0][0][1] is True  # but video plays


def test_youtube_present_no_dialog(kodi_with_youtube_no_srt):
    """FIX 4: YouTube addon installed -> no missing-addon dialog."""
    main = _load_main()
    with patch.object(main, "resolve_episode",
                      return_value=_fake_youtube_result()):
        main.HANDLE = 1
        main.play("https://kayifamilytv.com/ep", "EP1",
                  youtube_video_id="KEWP2dELhrY")
    assert not kodi_with_youtube_no_srt["dialog"].yesno.called
