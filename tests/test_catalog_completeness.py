"""Catalog completeness tests (issue #4).

The user-facing catalog must contain EVERY real episode with no gaps.
These tests fail the build if an expected episode number is missing,
e.g. 1,2,3,4,6,7... (Episode 5 missing) must FAIL.

Expected contiguous ranges (Phase 1):
    Mehmed:           1..86   (S1: 1-15, S2: 16-49, S3: 50-83, S4: 84-86)
    Kurulus Orhan:    1..26   (S1: 1-26)
    Salahuddin Ayyubi: 1..58  (S1: 1-28, S2: 29-58)
"""

import json
from pathlib import Path

import pytest

CATALOG = Path(__file__).resolve().parents[1] / "docs" / "catalog.json"

# show title -> {season_no: (first_ep, last_ep)}
EXPECTED = {
    "Mehmed Fetihler Sultani": {1: (1, 15), 2: (16, 49),
                                3: (50, 83), 4: (84, 86)},
    "Kurulus Orhan": {1: (1, 26)},
    "Salahuddin Ayyubi": {1: (1, 28), 2: (29, 58)},
}


def _load():
    return json.loads(CATALOG.read_text())


def test_catalog_exists():
    assert CATALOG.exists(), "docs/catalog.json not found"


def test_exactly_three_phase1_shows():
    catalog = _load()
    titles = sorted(s["title"] for s in catalog["shows"])
    assert titles == sorted(EXPECTED), \
        "Phase 1 must show exactly the 3 locked shows, got: %s" % titles


@pytest.mark.parametrize("show_title,seasons", list(EXPECTED.items()))
def test_season_boundaries(show_title, seasons):
    catalog = _load()
    show = next(s for s in catalog["shows"] if s["title"] == show_title)
    got = {se["number"] for se in show["seasons"]}
    assert got == set(seasons), \
        "%s: expected seasons %s, got %s" % (show_title,
                                             sorted(seasons), sorted(got))


@pytest.mark.parametrize("show_title,seasons", list(EXPECTED.items()))
def test_no_missing_episodes(show_title, seasons):
    """Every episode number in each season's range must be present."""
    catalog = _load()
    show = next(s for s in catalog["shows"] if s["title"] == show_title)
    for season_no, (lo, hi) in seasons.items():
        se = next(se for se in show["seasons"]
                  if se["number"] == season_no)
        nums = sorted(e["number"] for e in se["episodes"])
        expected = list(range(lo, hi + 1))
        missing = [n for n in expected if n not in nums]
        extra = [n for n in nums if n not in expected]
        assert not missing, \
            "%s S%d missing episodes: %s" % (show_title, season_no, missing)
        assert not extra, \
            "%s S%d unexpected episodes: %s" % (show_title, season_no, extra)


@pytest.mark.parametrize("show_title,seasons", list(EXPECTED.items()))
def test_no_duplicate_episodes(show_title, seasons):
    catalog = _load()
    show = next(s for s in catalog["shows"] if s["title"] == show_title)
    for se in show["seasons"]:
        nums = [e["number"] for e in se["episodes"]]
        assert len(nums) == len(set(nums)), \
            "%s S%d has duplicate episode numbers" % (show_title,
                                                      se["number"])


def test_episode_urls_present():
    catalog = _load()
    for show in catalog["shows"]:
        for se in show["seasons"]:
            for e in se["episodes"]:
                assert e.get("url", "").startswith("https://kayifamilytv.com/"), \
                    "%s S%d EP%s has no valid URL" % (
                        show["title"], se["number"], e.get("number"))


def test_total_episode_count():
    catalog = _load()
    total = sum(len(se["episodes"]) for s in catalog["shows"]
                for se in s["seasons"])
    assert total == 86 + 26 + 58, "expected 170 episodes, got %d" % total
