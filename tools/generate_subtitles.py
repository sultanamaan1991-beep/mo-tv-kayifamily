#!/usr/bin/env python3
"""Generate English subtitles from official broadcaster YouTube episodes.

Workflow:
  1. Download episode audio from the official YouTube video (yt-dlp)
  2. Transcribe Turkish -> English using Faster-Whisper (translate task)
  3. Post-process: clean up formatting, enforce subtitle quality rules
  4. Save as .srt in subtitles/<show>/s<season>e<episode>.en.srt

Usage:
  python3 tools/generate_subtitles.py --show mehmed --season 1 --episode 1

Requirements:
  - faster-whisper (pip install faster-whisper)
  - yt-dlp (for audio download)
  - ffmpeg (for audio conversion)
  - GPU recommended: 2.5h episode takes ~30-60 min on GPU, 8-15 hours on CPU

IMPORTANT:
  - Generate subtitles from the SAME official video that Kodi will play.
    This guarantees timing matches.
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
    """Apply subtitle quality rules."""
    cleaned = []
    for start, end, text in subs:
        if not text:
            continue
        # Skip extremely short (< 0.5s) unless it has real content
        duration = end - start
        if duration < 0.5 and len(text) < 10:
            continue
        # Cap duration at 7s
        if duration > 7.0:
            end = start + 7.0
        # Split into max 2 lines, max 42 chars per line
        text = re.sub(r'\s+', ' ', text).strip()
        lines = wrap_text(text, max_chars=42, max_lines=2)
        if not lines:
            continue
        cleaned.append((start, end, "\n".join(lines)))

    # Ensure chronological order and no overlaps
    cleaned.sort(key=lambda s: s[0])
    result = []
    for start, end, text in cleaned:
        if result and start < result[-1][1]:
            # Overlap: push start to after previous end
            start = result[-1][1] + 0.04
            if start >= end:
                continue  # skip if this makes it invalid
        # Minimum display time 0.8s
        if end - start < 0.8:
            end = start + 0.8
        result.append((start, end, text))
    return result


def wrap_text(text, max_chars=42, max_lines=2):
    """Wrap text to max_chars per line, max_lines lines."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    # If still too long, truncate
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


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


def main():
    parser = argparse.ArgumentParser(
        description="Generate English SRT from official YouTube episode")
    parser.add_argument("--show", required=True,
                        choices=["mehmed", "orhan", "salahuddin"])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--model", default="large-v3",
                        choices=list(MODELS.keys()))
    parser.add_argument("--sample-seconds", type=int, default=None,
                        help="Only process first N seconds (for testing)")
    args = parser.parse_args()

    video_id = get_video_id(args.show, args.episode)
    if not video_id:
        print(f"ERROR: No YouTube mapping for {args.show} "
              f"S{args.season}E{args.episode}")
        sys.exit(1)

    print(f"Show: {args.show}, S{args.season}E{args.episode}")
    print(f"YouTube ID: {video_id}")
    print(f"Model: {args.model}")

    # Paths
    work_dir = "/tmp/subtitle_work"
    os.makedirs(work_dir, exist_ok=True)
    audio_path = os.path.join(
        work_dir, f"{args.show}_s{args.season}e{args.episode}.mp3")
    srt_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "subtitles", args.show,
        f"s{args.season:02d}e{args.episode:02d}.en.srt")

    # Step 1: Download audio
    if not os.path.exists(audio_path):
        print("Downloading audio from official YouTube video...")
        if not download_audio(video_id, audio_path, args.sample_seconds):
            print("ERROR: Audio download failed. YouTube may be blocking "
                  "this network. Try from a different network or manually "
                  "provide the audio file at: " + audio_path)
            sys.exit(1)
    else:
        print(f"Using existing audio: {audio_path}")

    # Step 2: Transcribe
    count = transcribe_to_srt(audio_path, srt_path, args.model)

    print(f"\nDone! {count} subtitles written to:")
    print(f"  {srt_path}")
    print("\nReview the SRT for quality before marking as verified.")


if __name__ == "__main__":
    main()
