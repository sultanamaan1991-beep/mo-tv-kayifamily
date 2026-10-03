"""Episode identity regression tests (GitHub issue #3).

Bug: different Mehmed episodes resolved to the SAME video because
find_player_sources() scanned every <iframe> on the full page HTML,
including template-injected "latest videos" player widgets belonging to
other episodes. Episode 2, 3, ... all played Episode 85's video.

These tests prove that player identification is scoped to each
episode's OWN post content and that distinct episodes resolve to
distinct stable embed IDs. "A video started" is NOT sufficient --
identity is asserted on the OK.ru videoembed IDs.

Live tests (hit kayifamilytv.com + ok.ru); opt-in via --live.
"""

import re
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "plugin.video.kayifamily"
sys.path.insert(0, str(PLUGIN_DIR))

from resources.lib.resolver import find_player_sources, ResolverError  # noqa: E402

# (episode number, catalog page URL, expected OK.ru videoembed ID or None)
# None = the episode's own post has no OK.ru/VidMoly player, so the
# resolver must return no sources (fail closed) instead of grabbing
# another episode's video from a page widget.
CASES = [
    (1, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-1/", None),
    (2, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-2-english-subtitles/", None),
    (20, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-20/", None),
    (50, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-50/", "10142096230942"),
    (84, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-84/", "17462669609502"),
    (85, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-85/", "17557429029406"),
    (86, "https://kayifamilytv.com/mehmed-fetihler-sultani-episode-86/", None),
]

# Issue #4: identity-safe resolution must hold across ALL Phase 1 shows,
# not only Mehmed. Orhan EP 26 has its own OK.ru embed; Orhan 1/13 are
# vidmoly-only (their own player, not another episode's); Salahuddin is
# legacy-only (must never resolve to a modern player from a widget).
CROSS_SHOW_CASES = [
    ("orhan-1", "https://kayifamilytv.com/kurulus-orhan-episode-1/", None),
    ("orhan-13", "https://kayifamilytv.com/kurulus-orhan-episode-13/", None),
    ("orhan-26", "https://kayifamilytv.com/kurulus-orhan-episode-26/",
     "16075771808286"),
    ("salahuddin-1", "https://kayifamilytv.com/salahuddin-ayyubi-episode-1/",
     None),
    ("salahuddin-58", "https://kayifamilytv.com/salahuddin-ayyubi-episode-58/",
     None),
]

_EMBED_ID_RE = re.compile(r"videoembed/(\d+)")


def _okru_ids(sources):
    ids = []
    for label, src in sources:
        if label == "okru":
            m = _EMBED_ID_RE.search(src)
            assert m, "okru source without videoembed ID: %s" % src
            ids.append(m.group(1))
    return ids


@pytest.mark.live
@pytest.mark.parametrize("ep_num,url,expected_id", CASES,
                         ids=["ep%d" % c[0] for c in CASES])
def test_episode_resolves_to_own_player(ep_num, url, expected_id):
    """Each episode's player sources must come from its own post content."""
    try:
        sources = find_player_sources(url)
    except ResolverError:
        sources = []
    okru_ids = _okru_ids(sources)
    if expected_id is None:
        assert not okru_ids, (
            "EP %d must not resolve to another episode's player, got %s"
            % (ep_num, okru_ids))
    else:
        assert expected_id in okru_ids, (
            "EP %d must resolve to embed %s, got %s"
            % (ep_num, expected_id, okru_ids))


@pytest.mark.live
def test_distinct_episodes_have_distinct_embed_ids():
    """Two unrelated episode entries must never share an embed ID."""
    seen = {}
    for ep_num, url, expected_id in CASES:
        if expected_id is None:
            continue
        try:
            sources = find_player_sources(url)
        except ResolverError:
            sources = []
        for eid in _okru_ids(sources):
            assert eid not in seen, (
                "EP %d and EP %d resolved to the SAME embed %s "
                "(issue #3 regression)" % (seen[eid], ep_num, eid))
            seen[eid] = ep_num
    # the three playable samples must all be distinct videos
    assert len(seen) >= 3, "expected at least 3 distinct playable episodes"


@pytest.mark.live
@pytest.mark.parametrize("name,url,expected_id", CROSS_SHOW_CASES,
                         ids=[c[0] for c in CROSS_SHOW_CASES])
def test_cross_show_episode_identity(name, url, expected_id):
    """Issue #4: identity safety across shows (Orhan, Salahuddin)."""
    try:
        sources = find_player_sources(url)
    except ResolverError:
        sources = []
    okru_ids = _okru_ids(sources)
    if expected_id is None:
        assert not okru_ids, (
            "%s must not resolve to another episode's player, got %s"
            % (name, okru_ids))
    else:
        assert expected_id in okru_ids, (
            "%s must resolve to embed %s, got %s"
            % (name, expected_id, okru_ids))


@pytest.mark.live
def test_cross_show_distinct_embed_ids():
    """No two episodes across shows may share an OK.ru embed ID."""
    seen = {}
    for name, url, expected_id in CROSS_SHOW_CASES:
        if expected_id is None:
            continue
        try:
            sources = find_player_sources(url)
        except ResolverError:
            sources = []
        for eid in _okru_ids(sources):
            assert eid not in seen, (
                "%s and %s resolved to the SAME embed %s"
                % (seen[eid], name, eid))
            seen[eid] = name


@pytest.mark.live
def test_salahuddin_legacy_player_detected():
    """Salahuddin episodes use the legacy player: detected, not substituted."""
    from resources.lib.legacy import detect_legacy_players
    from resources.lib.resolver import _fetch_episode_post
    content, _ = _fetch_episode_post(
        "https://kayifamilytv.com/salahuddin-ayyubi-episode-1/")
    found = detect_legacy_players(content)
    assert found, "expected a legacy player in Salahuddin EP 1's own post"
    assert found[0][0] in ("wakeupummah", "vkvideo", "videa")
