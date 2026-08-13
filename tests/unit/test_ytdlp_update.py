"""`T-198`: installing a newer yt-dlp, and every way that can fail without costing the user one.

**The criterion these are mostly about is the fifth**: *a failed update — no network, a refused
index, a corrupt download — leaves the working version in place and reports.* So nearly every
test here installs a **sentinel copy first** and asserts it is still there afterwards. A test
that only checks the exception would pass against an implementation that deletes the live
directory and then fails, which is the outcome the criterion exists to forbid.

No network is touched. `UrlOpener` is injected, so the refused index, the truncated body and the
wrong checksum are driven as data rather than waited for.
"""

import hashlib
import io
import json
import urllib.error
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

import pytest

from tracks_and_trails.downloader.ytdlp_update import (
    MAXIMUM_WHEEL_BYTES,
    PYPI_INDEX,
    Release,
    UpdateError,
    install_latest,
    latest_release,
    revert_to_baseline,
)


#: What a real index document looks like, reduced to the fields the code reads.
def _index(version: str = "2026.9.1", digest: str = "", *, wheel: bool = True) -> dict[str, Any]:
    urls: list[dict[str, Any]] = [
        {
            "packagetype": "sdist",
            "filename": f"yt_dlp-{version}.tar.gz",
            "url": f"https://files.pythonhosted.org/yt_dlp-{version}.tar.gz",
            "digests": {"sha256": "0" * 64},
        }
    ]
    if wheel:
        urls.append(
            {
                "packagetype": "bdist_wheel",
                "filename": f"yt_dlp-{version}-py3-none-any.whl",
                "url": f"https://files.pythonhosted.org/yt_dlp-{version}-py3-none-any.whl",
                "digests": {"sha256": digest},
            }
        )
    return {"info": {"version": version}, "urls": urls}


def _wheel_bytes(version: str = "2026.9.1", *, contents: bool = True) -> bytes:
    """A minimal but structurally real wheel: a zip whose top level is what site-packages gets."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if contents:
            archive.writestr("yt_dlp/__init__.py", "")
            archive.writestr("yt_dlp/version.py", f"__version__ = {version!r}\n")
        archive.writestr(f"yt_dlp-{version}.dist-info/METADATA", f"Version: {version}\n")
    return buffer.getvalue()


class _Opener:
    """A fake `UrlOpener` serving prepared bytes, or raising the transport failure asked for."""

    def __init__(self, responses: dict[str, bytes | Exception]) -> None:
        self.responses = responses
        self.asked: list[str] = []

    @contextmanager
    def __call__(self, url: str) -> Iterator[IO[bytes]]:
        self.asked.append(url)
        answer = self.responses.get(url)
        if answer is None:
            raise urllib.error.URLError(f"no route to {url}")
        if isinstance(answer, Exception):
            raise answer
        yield io.BytesIO(answer)


def _serving(version: str = "2026.9.1", *, body: bytes | None = None) -> _Opener:
    """An opener whose index and wheel agree, which is the case where an install should work."""
    payload = _wheel_bytes(version) if body is None else body
    digest = hashlib.sha256(payload).hexdigest()
    document = _index(version, digest)
    wheel_url = document["urls"][-1]["url"]
    return _Opener({PYPI_INDEX: json.dumps(document).encode(), wheel_url: payload})


@pytest.fixture
def installed(tmp_path: Path) -> Path:
    """A user-managed copy that is already in place, with a file nothing else would write.

    The sentinel is what every failure test looks for afterwards. A directory that merely still
    *exists* proves nothing — `mkdir` after an `rmtree` would satisfy that.
    """
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    (directory / "yt_dlp" / "__init__.py").write_text("")
    (directory / "yt_dlp" / "sentinel.txt").write_text("the copy that was already here")
    return directory


def _still_intact(directory: Path) -> bool:
    marker = directory / "yt_dlp" / "sentinel.txt"
    return marker.is_file() and marker.read_text() == "the copy that was already here"


# --- reading the index ------------------------------------------------------------------------


def test_the_wheel_is_chosen_and_the_sdist_is_not() -> None:
    """`OPS-002` rests on yt-dlp being pure Python; a wheel extracts, a source archive does not."""
    release = latest_release(_serving("2026.9.1"))

    assert release.version == "2026.9.1"
    assert release.filename.endswith(".whl")


def test_the_package_type_decides_and_not_only_the_file_extension() -> None:
    """**Written because the test above passed for the wrong reason.**

    Dropping the `packagetype` check entirely left the suite green: the ordinary sdist fixture is
    named `.tar.gz`, so the *filename* check rejected it and the assertion above was satisfied by
    a rule it was not testing. That is the vacuous-assertion shape this project keeps finding, so
    the check is given an input only it can reject — an entry PyPI declares a source
    distribution while naming it like a wheel.

    A real index does not publish that. **This is untrusted input from a supply-chain surface**
    (`OPS-002`), and the declared type is the field that means what it says; the extension is a
    convention. Both are checked, and this is what makes the first one load-bearing.
    """
    document = _index("2026.9.1", "e" * 64)
    document["urls"] = [
        {
            "packagetype": "sdist",
            "filename": "yt_dlp-2026.9.1-py3-none-any.whl",
            "url": "https://files.pythonhosted.org/yt_dlp-2026.9.1.tar.gz",
            "digests": {"sha256": "e" * 64},
        }
    ]

    with pytest.raises(UpdateError, match="no installable wheel"):
        latest_release(_Opener({PYPI_INDEX: json.dumps(document).encode()}))


def test_an_entry_whose_declared_type_and_name_disagree_is_skipped() -> None:
    """The mirror of the test above, and it exists for the same mutation-found reason.

    Dropping the `.whl` extension check also left the suite green, because no fixture declared
    `bdist_wheel` while naming something else. Both fields are read and **both are now
    load-bearing**: an index entry where the declared type and the filename disagree is malformed,
    and on a supply-chain surface (`OPS-002`) malformed is the interesting case rather than the
    negligible one.

    *(The filename is no longer used to build any path — the download is staged under a fixed
    name — so this is an integrity check on metadata, not the thing standing between the index
    and a directory traversal. That was the other half of what this mutant exposed.)*
    """
    document = _index("2026.9.1", "f" * 64)
    document["urls"] = [
        {
            "packagetype": "bdist_wheel",
            "filename": "yt_dlp-2026.9.1.tar.gz",
            "url": "https://files.pythonhosted.org/yt_dlp-2026.9.1.tar.gz",
            "digests": {"sha256": "f" * 64},
        }
    ]

    with pytest.raises(UpdateError, match="no installable wheel"):
        latest_release(_Opener({PYPI_INDEX: json.dumps(document).encode()}))


def test_a_release_filename_cannot_reach_outside_the_staging_directory(tmp_path: Path) -> None:
    """The metadata names the file; the metadata does not choose where it lands.

    **The reachable path is `release=`, not the index.** A hostile name coming *through the index*
    is already rejected at selection — `latest_release` requires the name to start with the
    distribution — so the first version of this test asserted a traversal that could not happen
    and failed for that reason. `install_latest` accepts a caller-supplied `Release`, which is the
    entry point where an unvetted filename can still arrive, and that is what is driven here.

    Nothing opens the wheel by its published name, so it is staged under a fixed one.
    """
    payload = _wheel_bytes("2026.9.1")
    hostile = Release(
        version="2026.9.1",
        url="https://files.pythonhosted.org/yt_dlp-2026.9.1-py3-none-any.whl",
        digest=hashlib.sha256(payload).hexdigest(),
        filename="../../../escaped.whl",
    )
    opener = _Opener({hostile.url: payload})

    directory = tmp_path / "nested" / "ytdlp"
    install_latest(directory, opener, release=hostile)

    assert (directory / "yt_dlp" / "version.py").is_file()
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["nested"]
    assert not (tmp_path.parent / "escaped.whl").exists()


def test_a_yanked_wheel_is_skipped() -> None:
    """A yanked release is one PyPI is telling installers not to take."""
    document = _index("2026.9.1", "a" * 64)
    document["urls"][-1]["yanked"] = True
    opener = _Opener({PYPI_INDEX: json.dumps(document).encode()})

    with pytest.raises(UpdateError, match="no installable wheel"):
        latest_release(opener)


def test_a_release_with_no_wheel_reports_rather_than_improvising() -> None:
    """`OPS-002`'s reopening condition, surfaced instead of worked around."""
    opener = _Opener({PYPI_INDEX: json.dumps(_index(wheel=False)).encode()})

    with pytest.raises(UpdateError, match="no installable wheel"):
        latest_release(opener)


@pytest.mark.parametrize(
    ("name", "answer"),
    [
        ("unreachable", urllib.error.URLError("network is unreachable")),
        ("refused", urllib.error.HTTPError(PYPI_INDEX, 403, "Forbidden", {}, None)),  # type: ignore[arg-type]
        ("timeout", TimeoutError("timed out")),
    ],
)
def test_an_index_that_does_not_answer_is_reported_in_words(name: str, answer: Exception) -> None:
    with pytest.raises(UpdateError) as raised:
        latest_release(_Opener({PYPI_INDEX: answer}))

    assert "untouched" in str(raised.value), f"{name} should say the version in use is unaffected"


def test_an_index_returning_junk_is_not_parsed_into_a_release() -> None:
    with pytest.raises(UpdateError, match="not a package listing"):
        latest_release(_Opener({PYPI_INDEX: b"<html>maintenance</html>"}))


# --- installing -------------------------------------------------------------------------------


def test_installing_puts_yt_dlp_where_the_worker_resolves_it(tmp_path: Path) -> None:
    """The whole mechanism in one assertion: the package lands in the resolved directory.

    `environment.ytdlp_candidates` offers this directory ahead of the baseline and
    `worker._import_ytdlp` prepends it to `sys.path`, so landing here *is* the install.
    """
    directory = tmp_path / "ytdlp"

    release = install_latest(directory, _serving("2026.9.1"))

    assert release.version == "2026.9.1"
    assert (directory / "yt_dlp" / "version.py").is_file()


def test_installing_over_an_existing_copy_removes_what_was_there(installed: Path) -> None:
    """An update replaces; it does not merge. A file left from the old copy could shadow a new
    module and produce a version that reports one thing and behaves as another."""
    install_latest(installed, _serving("2026.9.1"))

    assert (installed / "yt_dlp" / "version.py").is_file()
    assert not (installed / "yt_dlp" / "sentinel.txt").exists()


def test_the_named_release_is_the_one_installed(tmp_path: Path) -> None:
    """A caller that showed the user a version installs *that* version.

    Looking the index up twice — once to name it, once to fetch it — can install something the
    user was never shown, because the index moves.
    """
    opener = _serving("2026.9.1")
    named = latest_release(opener)

    installed_release = install_latest(tmp_path / "ytdlp", opener, release=named)

    assert installed_release == named
    assert opener.asked.count(PYPI_INDEX) == 1, "the index was consulted a second time"


# --- the fifth criterion: a failure costs the user nothing ------------------------------------


def test_a_checksum_mismatch_discards_the_download_and_keeps_the_copy(installed: Path) -> None:
    """The corrupt-download case, named in the criterion.

    The index publishes one digest and the bytes hash to another, which is what a truncated or
    tampered transfer looks like.
    """
    document = _index("2026.9.1", "b" * 64)
    opener = _Opener(
        {
            PYPI_INDEX: json.dumps(document).encode(),
            document["urls"][-1]["url"]: _wheel_bytes("2026.9.1"),
        }
    )

    with pytest.raises(UpdateError, match="checksum"):
        install_latest(installed, opener)

    assert _still_intact(installed)


def test_an_unreachable_download_keeps_the_copy(installed: Path) -> None:
    document = _index("2026.9.1", "c" * 64)
    opener = _Opener(
        {
            PYPI_INDEX: json.dumps(document).encode(),
            document["urls"][-1]["url"]: urllib.error.URLError("connection reset"),
        }
    )

    with pytest.raises(UpdateError):
        install_latest(installed, opener)

    assert _still_intact(installed)


def test_a_download_that_is_not_a_package_keeps_the_copy(installed: Path) -> None:
    """A zip that is not a wheel, and a wheel with no `yt_dlp` in it, are both refused."""
    body = b"this is not a zip file"
    with pytest.raises(UpdateError):
        install_latest(installed, _serving(body=body))

    assert _still_intact(installed)


def test_a_wheel_without_yt_dlp_in_it_keeps_the_copy(installed: Path) -> None:
    with pytest.raises(UpdateError, match="did not contain yt-dlp"):
        install_latest(installed, _serving(body=_wheel_bytes(contents=False)))

    assert _still_intact(installed)


def test_an_oversized_download_is_cut_off_and_keeps_the_copy(installed: Path) -> None:
    """A redirect to something enormous must not fill the disk while the user waits."""
    with pytest.raises(UpdateError, match="larger than any yt-dlp release"):
        install_latest(installed, _serving(body=b"\0" * (MAXIMUM_WHEEL_BYTES + 1)))

    assert _still_intact(installed)


def test_a_failure_at_the_final_placement_puts_the_previous_copy_back(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The reason the install is two renames rather than a delete and a move.**

    Written because a mutant replacing the swap with `rmtree(directory); move(staged, directory)`
    survived every other test here: every failure they drive happens *before* the swap, so the
    destructive step was never reached and the two implementations were indistinguishable. The
    difference only shows when the final placement itself fails — which on Windows means a worker
    still holds the directory open, the case the docstring names.

    So the final rename is made to fail, and what is asserted is that the user still has the copy
    they started with. An install that cannot complete is recoverable; one that destroys the
    working version first is not.
    """
    real_rename = Path.rename
    refused: list[Path] = []

    def refuse_the_first_placement(self: Path, target: Any) -> Path:
        # Only the *first* move into the live directory fails. The restore that follows is a
        # second move to the same target, and it is allowed to work — otherwise this would be
        # driving the double-failure path instead of the one being asserted, which has its own
        # message and its own recovery.
        if Path(target) == installed and not refused:
            refused.append(Path(target))
            raise OSError("the directory is in use")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", refuse_the_first_placement)

    with pytest.raises(UpdateError, match="previous one was kept"):
        install_latest(installed, _serving("2026.9.1"))

    monkeypatch.undo()
    assert _still_intact(installed), "the copy that was in use was destroyed by a failed install"


def test_nothing_is_staged_beside_the_directory_after_a_failure(installed: Path) -> None:
    """A failed install leaves no half-tree for the next one to trip over."""
    with pytest.raises(UpdateError):
        install_latest(installed, _serving(body=b"not a zip"))

    siblings = {entry.name for entry in installed.parent.iterdir()}
    assert siblings == {installed.name}, f"a staging directory was left behind: {siblings}"


# --- reverting --------------------------------------------------------------------------------


def test_reverting_removes_the_user_copy_so_the_baseline_resolves(installed: Path) -> None:
    """The exit criterion's second half. With the directory gone, `ytdlp_candidates` offers the
    baseline alone — which is what "reverting restores the baseline" means mechanically."""
    assert revert_to_baseline(installed) is True
    assert not installed.exists()


def test_reverting_with_no_user_copy_says_there_was_nothing_to_remove(tmp_path: Path) -> None:
    assert revert_to_baseline(tmp_path / "absent") is False


def test_reverting_leaves_no_discarded_tree_behind(installed: Path) -> None:
    revert_to_baseline(installed)

    assert list(installed.parent.iterdir()) == []


# --- NFR-007: what a message may carry --------------------------------------------------------


def test_no_failure_message_carries_a_path_or_a_url(installed: Path) -> None:
    """`NFR-007` and `T-197`'s gate, applied to the surface that talks to the network.

    Every failure this module can raise is collected and swept together, rather than one
    assertion per test: the rule is about the class of message, and a rule proved against one
    spelling is a guard against one spelling (`T214-R1`).
    """
    document = _index("2026.9.1", "d" * 64)
    wheel_url = document["urls"][-1]["url"]
    listing = json.dumps(document).encode()
    failures = [
        _Opener({PYPI_INDEX: urllib.error.URLError("connection reset")}),
        _Opener({PYPI_INDEX: urllib.error.HTTPError(PYPI_INDEX, 403, "no", {}, None)}),  # type: ignore[arg-type]
        _Opener({PYPI_INDEX: b"<html/>"}),
        _Opener({PYPI_INDEX: listing, wheel_url: _wheel_bytes()}),
        _Opener({PYPI_INDEX: listing, wheel_url: urllib.error.URLError("reset")}),
        _serving(body=b"not a zip"),
        _serving(body=_wheel_bytes(contents=False)),
    ]

    messages = []
    for opener in failures:
        with pytest.raises(UpdateError) as raised:
            install_latest(installed, opener)
        messages.append(str(raised.value))

    assert len(messages) == len(failures)
    for message in messages:
        assert "http" not in message.lower(), f"a URL reached the user: {message}"
        assert str(installed) not in message, f"a filesystem path reached the user: {message}"
        assert "pythonhosted" not in message, f"a host reached the user: {message}"


def test_every_release_field_survives_the_round_trip() -> None:
    """`Release` is what the screen shows before the user commits to an install."""
    release = latest_release(_serving("2026.9.1"))

    assert isinstance(release, Release)
    assert release.version and release.url and release.digest and release.filename
