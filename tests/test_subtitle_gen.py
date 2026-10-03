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
