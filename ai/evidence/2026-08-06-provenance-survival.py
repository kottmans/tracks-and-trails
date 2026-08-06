"""`T-171` evidence: what metadata survives this application's own processing.

Regenerates sections 2 and 3 of `2026-08-06-provenance-survival.md` from scratch, in a temporary
directory. Needs ffmpeg and ffprobe on `PATH` and nothing else.

**Synthetic media only — no network, no real download, no real URL.** The question is what the
*ffmpeg step this application runs* does to tags, and a generated file answers that exactly as well
as a fetched one, while keeping a measurement out of anybody's real library.
"""

import json
import subprocess
import tempfile
from pathlib import Path

TAGS = {
    "title": "A clip about trails",
    "comment": "downloaded by Tracks & Trails",
    "purl": "https://example.invalid/watch?v=abc123",
    "date": "2026-08-06",
    "description": "preset=Audio only (MP3), 192 kbps",
}


def probe(path: Path) -> dict[str, str]:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return {k.lower(): v for k, v in json.loads(out.stdout)["format"].get("tags", {}).items()}


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, capture_output=True)


with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    source = tmp / "source.mp4"
    metadata: list[str] = []
    for key, value in TAGS.items():
        metadata += ["-metadata", f"{key}={value}"]
    run(
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=128x96:rate=5",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-shortest",
        *metadata,
        str(source),
    )
    print(f"source mp4 carries: {sorted(probe(source))}\n")

    cases = {
        # What `FFmpegExtractAudio` does for the MP3 preset: transcode to mp3 at a bitrate.
        "MP3 preset (extract audio, transcode)": (
            ["-i", str(source), "-vn", "-c:a", "libmp3lame", "-b:a", "192k", str(tmp / "out.mp3")],
            tmp / "out.mp3",
        ),
        # What it does for `Audio only (original)`: extract the stream without re-encoding.
        "Original-audio preset (extract, copy)": (
            ["-i", str(source), "-vn", "-c:a", "copy", str(tmp / "out.m4a")],
            tmp / "out.m4a",
        ),
        # The merge path the video presets take when video and audio arrive separately.
        "Video preset (remux/merge, copy)": (
            ["-i", str(source), "-c", "copy", str(tmp / "out.mkv")],
            tmp / "out.mkv",
        ),
    }

    for label, (args, output) in cases.items():
        run(*args)
        survived = probe(output)
        kept = {k: v for k, v in survived.items() if k in TAGS}
        lost = sorted(set(TAGS) - set(kept))
        print(f"{label}")
        print(f"    kept : {sorted(kept)}")
        print(f"    lost : {lost}")
        print(f"    added by ffmpeg: {sorted(set(survived) - set(TAGS))}\n")


# --- section 3: which containers accept a key they do not model ---------------------------------

with tempfile.TemporaryDirectory() as raw:
    tmp = Path(raw)
    print("container support for a custom key:")
    for suffix in ("mkv", "mp3", "mp4", "m4a", "opus"):
        output = tmp / f"probe.{suffix}"
        run(
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-metadata",
            "purl=https://example.invalid/watch?v=abc",
            "-metadata",
            "title=T",
            str(output),
        )
        held = probe(output)
        print(
            f"    {suffix:<5} purl={'kept' if 'purl' in held else 'dropped':<7} "
            f"title={'kept' if 'title' in held else 'dropped'}"
        )
