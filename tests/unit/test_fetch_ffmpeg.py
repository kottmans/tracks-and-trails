"""The Windows ffmpeg's fetcher, when upstream no longer has the pinned build (`T-360`, `OPS-001`).

`OPS-001`, amended 2026-10-11: every pinned archive is kept beside the release that bundled it,
and the fetcher takes it from there **by the same digest** when upstream fails. BtbN deleted
`0.1.0`'s pin within a month (`T-357`). Nothing here touches the network: `download` is replaced,
and the archive is a small one built to the real one's shape.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
import zipfile
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Final
from urllib.error import HTTPError

import pytest

REPOSITORY: Final = Path(__file__).resolve().parents[2]
SCRIPT: Final = REPOSITORY / "packaging" / "fetch_ffmpeg.py"


def load() -> ModuleType:
    """Load the fetcher by path: `packaging/` is not a package, as `test_option_table` says."""
    specification = importlib.util.spec_from_file_location("fetch_ffmpeg", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


fetch = load()


def an_archive(*, executable: bytes = b"MZ ffmpeg") -> bytes:
    """An archive shaped like BtbN's: one root, its `LICENSE.txt`, and the executables in `bin/`."""
    buffer = io.BytesIO()
    root = "ffmpeg-n0-win64-lgpl-shared"
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(f"{root}/LICENSE.txt", fetch.LICENCE.read_bytes())
        bundle.writestr(f"{root}/bin/ffmpeg.exe", executable)
        bundle.writestr(f"{root}/bin/ffprobe.exe", b"MZ ffprobe")
        bundle.writestr(f"{root}/bin/avutil-61.dll", b"MZ avutil")
    return buffer.getvalue()


def gone(url: str) -> HTTPError:
    return HTTPError(url, 404, "Not Found", Message(), None)


@pytest.fixture
def pinned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> bytes:
    """A vendor directory of its own, and a pin naming the test archive's digest."""
    archive = an_archive()
    monkeypatch.setattr(fetch, "VENDOR", tmp_path / "vendor")
    monkeypatch.setattr(fetch, "FFMPEG_SHA256", hashlib.sha256(archive).hexdigest())
    return archive


def serving(monkeypatch: pytest.MonkeyPatch, answers: dict[str, bytes | None]) -> list[str]:
    """Replace `download`: each URL answers its bytes, or 404 when mapped to `None`."""
    asked: list[str] = []

    def download(url: str) -> bytes:
        asked.append(url)
        answer = answers[url]
        if answer is None:
            raise gone(url)
        return answer

    monkeypatch.setattr(fetch, "download", download)
    return asked


def test_the_kept_copy_stands_in_when_upstream_has_deleted_the_build(
    pinned: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What happened to `0.1.0`'s pin, met by the copy `OPS-001` now keeps."""
    asked = serving(monkeypatch, {fetch.FFMPEG_URL: None, fetch.kept_url(): pinned})

    assert fetch.main() == 0

    assert asked == [fetch.FFMPEG_URL, fetch.kept_url()]
    assert (fetch.VENDOR / "ffmpeg.exe").read_bytes() == b"MZ ffmpeg"
    assert (fetch.VENDOR / "ffprobe.exe").is_file()


def test_a_kept_copy_that_is_not_the_pinned_build_is_refused(
    pinned: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The copy is held to the same digest**, so it can only ever supply the pinned bytes.

    A different archive, one byte of one executable apart, is refused before anything is
    extracted or kept: this binary is about to ship under this project's name.
    """
    other = an_archive(executable=b"MZ ffmpef")
    serving(monkeypatch, {fetch.FFMPEG_URL: None, fetch.kept_url(): other})

    assert fetch.main() == 1

    assert not (fetch.VENDOR / "ffmpeg.exe").exists(), "a refused archive was extracted"
    assert not (fetch.VENDOR / fetch.FFMPEG_ARCHIVE).exists(), "a refused archive was kept"


def test_upstream_is_asked_first_and_the_copy_not_at_all_while_it_answers(
    pinned: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = serving(monkeypatch, {fetch.FFMPEG_URL: pinned})

    assert fetch.main() == 0

    assert asked == [fetch.FFMPEG_URL]


def test_the_copy_is_looked_for_beside_this_tree_s_release() -> None:
    """A checkout of `v0.2.0` asks its own assets; a `.dev` version names the release ahead."""
    version_line = next(
        line
        for line in fetch.VERSION_FILE.read_text("utf-8").splitlines()
        if line.startswith("__version__")
    )
    version = version_line.split('"')[1].split(".dev")[0]

    assert fetch.release_tag() == f"v{version}"
    assert fetch.kept_url() == (
        "https://github.com/kottmans/tracks-and-trails/releases/download/"
        f"v{version}/{fetch.FFMPEG_ARCHIVE}"
    )
