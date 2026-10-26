"""yt-dlp writes the download pass's literal path as the worker built it (`T-365`).

The worker renders a name, contains it and shows it, then hands yt-dlp the absolute path inside
its staging folder as a literal. **yt-dlp changed that path twice more**: `_outtmpl_expandpath`
expanded `$` variables anywhere in it, on every platform, and on Windows `get_output_path` renamed
any folder of it that `sanitize_path` dislikes, such as one ending in U+00A0, which Windows allows.
`keep_the_literal_path` keeps both off the session's `YoutubeDL`.

**Windows' rename is reproduced here by `windowsfilenames`**, which makes `sanitize_path` act on
Linux as it always acts on Windows. Real sessions are in
`tests/integration/test_shaping_containment.py`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Final

import pytest
import yt_dlp
from yt_dlp import YoutubeDL

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.worker import as_literal_template
from tracks_and_trails.downloader.ytdlp_adapter import build_options, keep_the_literal_path

#: A variable set for each test, whose value holds a separator, as `HOME` and `PATH` do.
VARIABLE: Final = "TT_T365_ELSEWHERE"
ELSEWHERE: Final = f"x{os.sep}elsewhere"

ROOT: Final = Path("/home/someone")
STAGING_NAME: Final = ".tracks-and-trails-staging-0123456789abcdef0123456789abcdef0123"

#: `(folder, title, windows)`: the chosen folder and the item's title, and whether only Windows'
#: rename reaches it. Each was measured writing elsewhere, or under another name, at 2026.08.19.
CASES: Final = [
    pytest.param(f"Notes ${VARIABLE}", "Clip", False, id="a variable in the folder"),
    pytest.param(f"Notes ${{{VARIABLE}}}", "Clip", False, id="a braced variable in the folder"),
    # The template escapes the `%`, so the folder is recognised by its escaped spelling.
    pytest.param(f"100% ${VARIABLE}", "Clip", False, id="a percent and a variable in the folder"),
    pytest.param("Videos", f"Price ${VARIABLE}", False, id="a variable in the title"),
    pytest.param("Talks\u00a0", "Clip", True, id="a folder ending in U+00A0"),
    pytest.param("Talks\u3000", "Clip", True, id="a folder ending in U+3000"),
]


@pytest.fixture(autouse=True)
def _variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, ELSEWHERE)


def _session(staging: Path, contained: Path, *, kept: bool, windows: bool) -> YoutubeDL:
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(staging.parent),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    options: dict[str, Any] = {**build_options(request, as_literal_template(contained))}
    ydl = YoutubeDL({**options, "quiet": True, "windowsfilenames": windows})
    if kept:
        keep_the_literal_path(ydl, yt_dlp, staging)
    return ydl


def _written(folder: str, title: str, *, kept: bool, windows: bool) -> tuple[Path, str]:
    staging = ROOT / folder / STAGING_NAME
    contained = staging / f"{title}.mp4"
    with _session(staging, contained, kept=kept, windows=windows) as ydl:
        return contained, ydl.prepare_filename({"id": "clip", "title": title, "ext": "mp4"})


@pytest.mark.parametrize(("folder", "title", "windows"), CASES)
def test_yt_dlp_rewrites_each_case_unless_it_is_kept(
    folder: str, title: str, windows: bool
) -> None:
    """The positive control: without `keep_the_literal_path` each path is written elsewhere."""
    contained, written = _written(folder, title, kept=False, windows=windows)

    assert written != str(contained)


@pytest.mark.parametrize("windows", [False, True], ids=["as on Linux", "as on Windows"])
@pytest.mark.parametrize(("folder", "title", "_only_windows"), CASES)
def test_the_literal_path_is_written_as_the_worker_built_it(
    folder: str, title: str, _only_windows: bool, windows: bool
) -> None:
    contained, written = _written(folder, title, kept=True, windows=windows)

    assert written == str(contained)


@pytest.mark.parametrize("folder", ["Videos", f"Notes ${VARIABLE}", "Talks\u00a0"])
def test_each_section_is_written_inside_staging_too(folder: str) -> None:
    """The sections' own template begins with the same literal (`T-252`)."""
    staging = ROOT / folder / STAGING_NAME
    contained = staging / "Clip.mp4"
    info = {"id": "clip", "title": "Clip", "ext": "mp4", "section_number": 1}
    with _session(staging, contained, kept=True, windows=True) as ydl:
        written = Path(ydl.prepare_filename({**info, "section_title": "Intro"}, "chapter"))

    assert written.parent == staging, written


def test_yt_dlp_s_windows_pass_still_runs_below_staging() -> None:
    """Only the staging folder's own path is kept out of it: the folder exists as written because
    the worker made it. Below it, where a site's chapter title can land, yt-dlp's pass is kept."""
    staging = ROOT / "Videos" / STAGING_NAME
    contained = staging / "Clip.mp4"
    with _session(staging, contained, kept=True, windows=True) as ydl:
        below = ydl.get_output_path("", str(staging / "Inner\u00a0" / "Clip.mp4"))
        elsewhere = ydl.get_output_path("", str(ROOT / "Talks\u00a0" / "Clip.mp4"))

    assert below == str(staging / "Inner#" / "Clip.mp4")
    assert elsewhere == str(ROOT / "Talks#" / "Clip.mp4")


def test_a_template_outside_staging_is_still_expanded() -> None:
    staging = ROOT / "Videos" / STAGING_NAME
    with _session(staging, staging / "Clip.mp4", kept=True, windows=False) as ydl:
        expanded = ydl._outtmpl_expandpath(f"${VARIABLE}{os.sep}%(title)s.%(ext)s")

    assert expanded == f"{ELSEWHERE}{os.sep}%(title)s.%(ext)s"


def test_a_yt_dlp_without_the_two_methods_is_left_as_it_is() -> None:
    """The claim's source check (`T109-R8`) is then the only line, as before `T-365`."""

    class Bare:
        def __init__(self) -> None:
            self.params: dict[str, Any] = {}

    class Partial(Bare):
        @staticmethod
        def get_output_path(dir_type: str = "", filename: str | None = None) -> str:
            return f"{dir_type}:{filename}"

    bare, partial = Bare(), Partial()
    keep_the_literal_path(bare, yt_dlp, ROOT / STAGING_NAME)
    keep_the_literal_path(partial, object(), ROOT / STAGING_NAME)

    assert set(vars(bare)) == {"params"}
    assert set(vars(partial)) == {"params"}, "without yt-dlp's sanitize_path it is not replaced"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' rename is unconditional only there")
@pytest.mark.parametrize("folder", ["Talks\u00a0", "Talks\u3000"])
def test_on_windows_a_folder_it_allows_is_kept_without_asking(folder: str) -> None:
    contained, written = _written(folder, "Clip", kept=True, windows=False)

    assert written == str(contained)
