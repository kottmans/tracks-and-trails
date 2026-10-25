"""What ffprobe is asked about a section, and what its answers mean (`T252-R1`).

**Driven with a stand-in for ffprobe**, so the arguments and the readings are pinned exactly; the
real ffprobe against real media is `tests/integration/test_download_sections.py`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.downloader.media_probe import (
    LOCAL_TIMEOUT_SECONDS,
    REMOTE_TIMEOUT_SECONDS,
    ffprobe_beside,
    holds_media,
    remote_length,
    run_with,
)

FFPROBE = Path("/opt/ffmpeg/ffprobe")


class Answers:
    """Stands in for ffprobe: each run is recorded and answered from a list."""

    def __init__(self, *answers: tuple[int, str]) -> None:
        self.answers = list(answers)
        self.runs: list[tuple[list[str], float]] = []

    def __call__(self, arguments: Sequence[str], timeout: float) -> tuple[int, str]:
        self.runs.append((list(arguments), timeout))
        return self.answers.pop(0) if self.answers else (1, "")


def _read(streams: list[str], duration: str | None) -> str:
    container: dict[str, Any] = {} if duration is None else {"duration": duration}
    return json.dumps({"streams": [{"codec_type": kind} for kind in streams], "format": container})


# --- a section on disk -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "holds"),
    [
        ((0, _read(["video", "audio"], "2.019")), True),
        ((0, _read(["audio"], "2.0")), True),
        # A container that reports no length is not held to one.
        ((0, _read(["video"], None)), True),
        # The 262-byte cut: a valid MP4 with no streams.
        ((0, _read([], None)), False),
        ((0, _read(["subtitle", "data"], "2.0")), False),
        ((0, _read(["video"], "0.000000")), False),
        ((0, _read(["video"], "N/A")), False),
        ((1, ""), False),
        ((0, "not json"), False),
        ((0, "[]"), False),
    ],
)
def test_a_section_holds_media_only_with_a_picture_or_a_sound(
    answer: tuple[int, str], holds: bool
) -> None:
    run = Answers(answer)

    assert holds_media(Path("/staging/Clip (section 1).mp4"), FFPROBE, run) is holds
    arguments, timeout = run.runs[0]
    assert arguments[0] == str(FFPROBE) and arguments[-1] == "/staging/Clip (section 1).mp4"
    assert timeout == LOCAL_TIMEOUT_SECONDS


# --- a link's length -------------------------------------------------------------------------


def test_the_length_is_read_from_the_chosen_link_with_its_headers_and_cookies() -> None:
    """The request's own headers, and its cookies as a `Cookie` header: yt-dlp keeps them in a
    format's `cookies` field as `Set-Cookie` text, attributes and all."""
    run = Answers((0, "6.000000\n"))
    info = {
        "url": "https://media.example/clip.mp4",
        "http_headers": {"User-Agent": "UA", "Referer": "https://page.example/"},
        "cookies": "session=abc; Domain=.example; Path=/; Secure; theme=dark; Path=/",
    }

    assert remote_length(info, FFPROBE, run, SimpleCookie) == 6.0

    ((arguments, timeout),) = run.runs
    assert timeout == REMOTE_TIMEOUT_SECONDS
    assert arguments[-1] == "https://media.example/clip.mp4"
    headers = arguments[arguments.index("-headers") + 1]
    assert headers.split("\r\n")[:-1] == [
        "User-Agent: UA",
        "Referer: https://page.example/",
        "Cookie: session=abc; theme=dark",
    ]


def test_the_first_merged_link_that_answers_gives_the_length() -> None:
    run = Answers((1, ""), (0, "6.02"))
    info = {
        "requested_formats": [
            {"url": "https://media.example/video.mp4"},
            {"url": "https://media.example/audio.m4a"},
        ]
    }

    assert remote_length(info, FFPROBE, run) == 6.02
    assert [arguments[-1] for arguments, _ in run.runs] == [
        "https://media.example/video.mp4",
        "https://media.example/audio.m4a",
    ]
    assert all("-headers" not in arguments for arguments, _ in run.runs), "no headers to send"


@pytest.mark.parametrize("answer", [(0, "N/A\n"), (0, ""), (0, "0"), (0, "inf"), (1, "6.0")])
def test_no_length_is_read_where_ffprobe_gives_none(answer: tuple[int, str]) -> None:
    assert (
        remote_length({"url": "https://media.example/clip.mp4"}, FFPROBE, Answers(answer)) is None
    )


def test_only_a_web_link_is_asked() -> None:
    run = Answers()

    assert remote_length({"url": "rtmp://media.example/live"}, FFPROBE, run) is None
    assert remote_length({}, FFPROBE, run) is None
    assert run.runs == []


# --- which ffprobe, and how it is run ---------------------------------------------------------


def test_the_ffprobe_is_the_one_beside_ffmpeg(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n")
    ffmpeg.chmod(0o755)
    assert ffprobe_beside(ffmpeg) is None

    ffprobe = tmp_path / "ffprobe"
    ffprobe.write_text("#!/bin/sh\n")
    ffprobe.chmod(0o755)
    assert ffprobe_beside(ffmpeg) == ffprobe


def test_a_run_that_cannot_start_answers_nothing(tmp_path: Path) -> None:
    run = run_with(None)

    assert run([str(tmp_path / "not-a-program")], 5) == (-1, "")


def test_a_run_goes_through_yt_dlp_s_popen_when_it_has_one() -> None:
    seen: dict[str, Any] = {}

    class Popen:
        @classmethod
        def run(cls, arguments: list[str], **options: Any) -> tuple[str, str, int]:
            seen.update(arguments=arguments, **options)
            return "6.0\n", "an error naming https://media.example/?token=secret", 0

    assert run_with(Popen)(["ffprobe", "x"], 7) == (0, "6.0\n")
    assert seen["arguments"] == ["ffprobe", "x"] and seen["timeout"] == 7 and seen["text"] is True
