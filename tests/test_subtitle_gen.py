"""Tests for subtitle generation helpers (tools/generate_subtitles.py).

FIX 3: long translated segments must NEVER lose words. They are split
into multiple chronological cues instead of being truncated.
"""

import re
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from generate_subtitles import (  # noqa: E402
    clean_subtitles,
    split_into_cues,
    subtitle_output_path,
    wrap_lines,
)


def _words(text):
    return re.findall(r"\w+", text)


LONG_SENTENCE = (
    "The Sultan, having received news of the enemy's advance toward the "
    "city walls, immediately summoned his commanders to discuss the "
    "strategy for the coming battle that would decide the fate of the empire."
)


def test_long_sentence_preserves_all_words():
    """Input words == output words (the core FIX 3 requirement)."""
    cues = split_into_cues(0.0, 12.0, LONG_SENTENCE)
    assert len(cues) > 1, "long text should split into multiple cues"
    out_text = " ".join(t for _, _, t in cues)
    assert _words(LONG_SENTENCE) == _words(out_text)


def test_cues_respect_line_limits():
    cues = split_into_cues(0.0, 12.0, LONG_SENTENCE)
    for _, _, text in cues:
        lines = text.split("\n")
        assert len(lines) <= 2, "max 2 lines per cue"
        for line in lines:
            assert len(line) <= 42, "max 42 chars per line: %r" % line


def test_cues_chronological_no_overlap():
    cues = split_into_cues(5.0, 17.0, LONG_SENTENCE)
    assert cues[0][0] >= 5.0
    assert cues[-1][1] <= 17.0 + 0.001
    for i in range(1, len(cues)):
        assert cues[i][0] >= cues[i - 1][1] - 0.001, "overlap or out of order"


def test_short_text_single_cue():
    cues = split_into_cues(1.0, 4.0, "Hello, my Sultan.")
    assert len(cues) == 1
    assert cues[0] == (1.0, 4.0, "Hello, my Sultan.")


def test_clean_subtitles_preserves_words_end_to_end():
    cleaned = clean_subtitles([(0.0, 12.0, LONG_SENTENCE)])
    out_text = " ".join(t for _, _, t in cleaned)
    assert _words(LONG_SENTENCE) == _words(out_text)


def test_wrap_lines_never_truncates():
    lines = wrap_lines(LONG_SENTENCE, max_chars=42)
    assert _words(LONG_SENTENCE) == _words(" ".join(lines))
    for line in lines:
        assert len(line) <= 42


def test_empty_text_no_cues():
    assert split_into_cues(0.0, 5.0, "") == []
    assert split_into_cues(0.0, 5.0, "   ") == []
    assert clean_subtitles([(0.0, 5.0, "")]) == []


def test_output_path_matches_addon_resources():
    """FIX 1: generator output must land where Kodi looks for bundled SRTs."""
    import os
    path = subtitle_output_path("mehmed", 1, 1)
    # Must be under the addon's resources/subtitles/ directory
    assert "plugin.video.kayifamily" in path
    assert os.path.join("resources", "subtitles", "mehmed") in path
    assert path.endswith(os.path.join("mehmed", "s01e01.en.srt"))
    # And it must match the catalog's subtitle_file convention
    rel = os.path.relpath(
        path,
        os.path.join(os.path.dirname(path).split("plugin.video.kayifamily")[0],
                     "plugin.video.kayifamily", "resources", "subtitles"))
    assert rel == os.path.join("mehmed", "s01e01.en.srt")


def test_adjacent_short_segments_preserve_all_words():
    """FIX 3 edge case: tightly-packed short cues must not lose dialogue."""
    segs = [
        (0.00, 0.30, "First sentence"),
        (0.31, 0.60, "Second sentence"),
        (0.61, 0.90, "Third sentence"),
    ]
    cleaned = clean_subtitles(segs)
    # ALL words from A+B+C must survive
    out_text = " ".join(t for _, _, t in cleaned)
    expected = "First sentence Second sentence Third sentence"
    assert _words(expected) == _words(out_text)
    # Chronological, no negative durations, no reversed timestamps
    assert len(cleaned) == 3
    for s, e, _ in cleaned:
        assert e > s, "non-positive duration"
    for i in range(1, len(cleaned)):
        assert cleaned[i][0] >= cleaned[i - 1][0], "out of order"
        assert cleaned[i][0] >= cleaned[i - 1][1] - 0.001, "overlap"


def test_extreme_overlap_never_drops_cue():
    """Even fully-overlapping cues are preserved (shortened, not deleted)."""
    segs = [
        (0.0, 5.0, "Long first cue with plenty of words here"),
        (1.0, 1.5, "Tiny overlapping cue"),
        (2.0, 6.0, "Another cue overlapping the first"),
    ]
    cleaned = clean_subtitles(segs)
    out_text = " ".join(t for _, _, t in cleaned)
    for word in ["Tiny", "overlapping", "Another"]:
        assert word in out_text, "cue dropped: %s" % word
    for s, e, _ in cleaned:
        assert e > s
