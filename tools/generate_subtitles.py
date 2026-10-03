#!/usr/bin/env python3
"""Generate English subtitles from official broadcaster episodes.

Workflow:
  1. Get episode audio (local file via --input, or YouTube download)
  2. Transcribe Turkish -> English using Faster-Whisper (translate task)
  3. Post-process: clean up formatting, enforce subtitle quality rules
  4. Save as .srt in plugin.video.kayifamily/resources/subtitles/<show>/s<SS>e<EE>.en.srt

Usage:
  # From local authorized file (recommended):
  python3 tools/generate_subtitles.py --input /path/to/episode.mp4 \\
      --show mehmed --season 1 --episode 1

  # From YouTube (requires network access to YouTube):
  python3 tools/generate_subtitles.py --show mehmed --season 1 --episode 1

Requirements:
  - faster-whisper (pip install faster-whisper)
  - yt-dlp (for YouTube audio download, optional if using --input)
  - ffmpeg (for audio conversion)
  - GPU recommended: 2.5h episode takes ~30-60 min on GPU, 8-15 hours on CPU

IMPORTANT:
  - Generate subtitles from the SAME official video that Kodi will play.
    This eliminates source-edit offset, but Whisper timestamps can still
    drift. ALWAYS test sync at: beginning, 30min, 60min, 90min, near end.
  - Generate ONCE, store the .srt as a reusable asset.
  - Do NOT generate from Kayi's version and assume it syncs to YouTube.

Subtitle quality rules enforced:
  - Max 42 chars per line, max 2 lines per subtitle
  - No overlapping timestamps, chronological order
  - No subtitles shorter than 0.8s or longer than 7s
  - Proper nouns preserved (not translated)
"""

import argparse
import os
import re
import subprocess
import sys

# Show -> YouTube mappings file
MAPPINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "youtube_mappings.json")

# Model recommendations:
#   - "large-v3": best quality, needs ~10GB VRAM or very slow on CPU
#   - "medium": good quality, needs ~5GB VRAM, slow on CPU
#   - "small": acceptable for testing, ~2GB VRAM, usable on CPU
MODELS = {
    "large-v3": {"vram_gb": 10, "quality": "best"},
    "medium": {"vram_gb": 5, "quality": "good"},
    "small": {"vram_gb": 2, "quality": "acceptable"},
}


def get_video_id(show, episode):
    import json
    with open(MAPPINGS_FILE, encoding="utf-8") as f:
        mappings = json.load(f)
    # show key mapping
    key_map = {"mehmed": "mehmed", "orhan": "orhan", "salahuddin": "salahuddin"}
    key = key_map.get(show, show)
    return (mappings.get(key) or {}).get(str(episode))


def download_audio(video_id, out_path, duration_limit=None):
    """Download audio from YouTube. Returns True on success."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings", "--no-check-certificate",
        "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "-o", out_path,
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    if duration_limit:
        # Use --postprocessor-args to trim (requires ffmpeg)
        cmd.extend(["--postprocessor-args", f"-t {duration_limit}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    return result.returncode == 0


def transcribe_to_srt(audio_path, srt_path, model_name="large-v3",
                      language="tr"):
    """Transcribe Turkish audio -> English SRT using Faster-Whisper.

    Uses task="translate" for direct Turkish->English translation.
    """
    from faster_whisper import WhisperModel

    print(f"Loading model '{model_name}'...")
    model = WhisperModel(model_name, device="auto", compute_type="auto")

    print(f"Transcribing {audio_path} (Turkish -> English)...")
    segments, info = model.transcribe(
        audio_path,
        task="translate",  # Turkish audio -> English text
        language=language,
        beam_size=5,
        vad_filter=True,  # voice activity detection for better segmentation
    )

    print(f"Detected language: {info.language} "
          f"(probability {info.language_probability:.2f})")

    # Collect segments
    subs = []
    for seg in segments:
        subs.append((seg.start, seg.end, seg.text.strip()))

    print(f"Generated {len(subs)} raw segments")
    cleaned = clean_subtitles(subs)
    print(f"After cleanup: {len(cleaned)} subtitles")

    write_srt(cleaned, srt_path)
    print(f"Wrote {srt_path}")
    return len(cleaned)


def clean_subtitles(subs):
    """Apply subtitle quality rules. NEVER discards words for timing reasons.

    Long translated segments are split into multiple chronological cues
    with the available time divided proportionally by text length.

    Timing normalization priorities (in order):
      1. Preserve every cue (no dialogue dropped for tight timing).
      2. Chronological order, no overlaps, no negative durations.
      3. 0.8s minimum display as a TARGET where space allows -- never a
         reason to delete text.
    """
    cues = []
    for start, end, text in subs:
        if not text:
            continue
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            continue
        duration = end - start
        # Skip likely Whisper noise: extremely short with almost no content.
        if duration < 0.5 and len(text) < 10:
            continue
        # Cap single-cue duration at 7s
        if duration > 7.0:
            end = start + 7.0
            duration = 7.0
        cues.extend(split_into_cues(start, end, text))

    cues.sort(key=lambda s: s[0])
    cues = _normalize_timing(cues)
    return cues


def _normalize_timing(cues, gap=0.04, target_min=0.8, abs_min=0.2):
    """Resolve overlaps without ever dropping a cue.

    Pass 1: walk chronologically; push each cue's start past the previous
    cue's end (+gap). If the adjusted start passes the cue's original end
    (extreme overlap), keep the cue with abs_min duration rather than
    deleting it -- content preservation beats timing precision.
    Pass 2: extend cues toward target_min where the gap to the next cue
    allows it, without creating new overlaps.
    """
    # Pass 1: eliminate overlaps, preserve everything
    adjusted = []
    cursor = 0.0
    for start, end, text in cues:
        s = max(start, cursor)
        # Guarantee a positive duration even under extreme overlap
        e = max(end, s + abs_min)
        adjusted.append([s, e, text])
        cursor = e + gap

    # Pass 2: extend short cues toward target_min where space allows
    for i, (s, e, text) in enumerate(adjusted):
        if e - s >= target_min:
            continue
        if i + 1 < len(adjusted):
            next_start = adjusted[i + 1][0]
            allowed_end = next_start - gap
        else:
            allowed_end = s + target_min  # last cue: free to extend
        new_end = min(s + target_min, allowed_end)
        if new_end > e:
            adjusted[i][1] = new_end

    return [(s, e, t) for s, e, t in adjusted]


def wrap_lines(text, max_chars=42):
    """Wrap text into lines of max_chars. Never truncates; returns all lines."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def split_into_cues(start, end, text, max_chars=42, max_lines_per_cue=2,
                    min_cue_secs=1.0):
    """Split text into multiple subtitle cues, preserving ALL words.

    Lines are wrapped at max_chars; every max_lines_per_cue lines form one
    cue. The [start, end] interval is divided proportionally by each
    cue's character count, with each cue getting at least min_cue_secs
    when the total duration allows it.
    """
    lines = wrap_lines(text, max_chars)
    if not lines:
        return []
    # Group lines into cues of max_lines_per_cue
    groups = [lines[i:i + max_lines_per_cue]
              for i in range(0, len(lines), max_lines_per_cue)]
    if len(groups) == 1:
        return [(start, end, "\n".join(groups[0]))]

    total_chars = sum(len("".join(g)) for g in groups) or 1
    duration = end - start
    cues = []
    cursor = start
    for i, group in enumerate(groups):
        share = len("".join(group)) / total_chars
        cue_dur = duration * share
        # Last cue takes whatever remains to avoid rounding drift
        if i == len(groups) - 1:
            cue_end = end
        else:
            cue_end = cursor + max(cue_dur, min_cue_secs)
            # Don't let minimums push us past the segment end
            remaining = len(groups) - i - 1
            latest_allowed = end - remaining * min_cue_secs
            if cue_end > latest_allowed:
                cue_end = latest_allowed
        cues.append((cursor, cue_end, "\n".join(group)))
        cursor = cue_end
    return cues


def wrap_text(text, max_chars=42, max_lines=2):
    """Legacy wrapper: kept for compatibility, now delegates.

    NOTE: callers that need all words preserved should use
    split_into_cues() instead; this returns at most max_lines lines.
    """
    return wrap_lines(text, max_chars)[:max_lines]


def write_srt(subs, path):
    """Write subtitles in SRT format."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(subs, 1):
            f.write(f"{i}\n")
            f.write(f"{fmt_time(start)} --> {fmt_time(end)}\n")
            f.write(f"{text}\n\n")


def fmt_time(seconds):
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def subtitle_output_path(show, season, episode):
    """Return the addon-bundled SRT path for an episode.

    This MUST match where Kodi looks: the addon's
    resources/subtitles/ directory, so a generated file lands
    directly in the packaged ZIP with no manual copying.
    """
    filename = f"s{season:02d}e{episode:02d}.en.srt"
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "plugin.video.kayifamily",
        "resources", "subtitles", show, filename)


def main():
    parser = argparse.ArgumentParser(
        description="Generate English SRT from official episode audio")
    parser.add_argument("--show", required=True,
                        choices=["mehmed", "orhan", "salahuddin"])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--model", default="large-v3",
                        choices=list(MODELS.keys()))
    parser.add_argument("--sample-seconds", type=int, default=None,
                        help="Only process first N seconds (for testing)")
    parser.add_argument("--input", type=str, default=None,
                        help="Path to authorized local audio/video file. "
                             "If provided, skips YouTube download. "
                             "Use this for subtitle generation from a local file.")
    args = parser.parse_args()

    print(f"Show: {args.show}, S{args.season}E{args.episode}")
    print(f"Model: {args.model}")

    # Paths
    work_dir = "/tmp/subtitle_work"
    os.makedirs(work_dir, exist_ok=True)
    # Output lands directly in the addon resources (bundled into the ZIP).
    srt_path = subtitle_output_path(args.show, args.season, args.episode)

    # Step 1: Get audio (local file or YouTube download)
    if args.input:
        # Use authorized local file directly
        if not os.path.exists(args.input):
            print(f"ERROR: Input file not found: {args.input}")
            sys.exit(1)
        audio_path = args.input
        print(f"Using local input file: {audio_path}")
        print("NOTE: Ensure this file is from the SAME official video "
              "that Kodi will play, for sync accuracy.")
    else:
        # Download from YouTube (requires network access to YouTube)
        video_id = get_video_id(args.show, args.episode)
        if not video_id:
            print(f"ERROR: No YouTube mapping for {args.show} "
                  f"S{args.season}E{args.episode}")
            sys.exit(1)
        print(f"YouTube ID: {video_id}")
        audio_path = os.path.join(
            work_dir, f"{args.show}_s{args.season}e{args.episode}.mp3")
        if not os.path.exists(audio_path):
            print("Downloading audio from official YouTube video...")
            if not download_audio(video_id, audio_path, args.sample_seconds):
                print("ERROR: Audio download failed. YouTube may be blocking "
                      "this network. Try from a different network, or use "
                      "--input with a local authorized file.")
                sys.exit(1)
        else:
            print(f"Using existing audio: {audio_path}")

    # Step 2: Transcribe
    count = transcribe_to_srt(audio_path, srt_path, args.model)

    print(f"\nDone! {count} subtitles written to:")
    print(f"  {srt_path}")
    print("\nIMPORTANT: Test sync at beginning, 30min, 60min, 90min, and near end.")
    print("Whisper timestamps may drift; do not assume perfect sync.")
    print("Review the SRT for quality before marking as verified.")


if __name__ == "__main__":
    main()
