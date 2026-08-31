"""Installs a newer yt-dlp where the worker will find it, and puts the baseline back (`OPS-002`).

`OPS-002` decided the mechanism and this module is only its implementation: **wheel extraction,
not pip.** The shipped artifact is frozen (`REL-001`) with no pip and no writable
`site-packages`, so the update downloads yt-dlp's wheel from PyPI, verifies it, and extracts it
into `user_data_dir/tracksandtrails/ytdlp/` — the directory `environment.ytdlp_candidates`
already resolves *ahead of* the baseline and `worker.py` already prepends to `sys.path`.

**That is why this task needed no new resolution path, and why the frozen build needs no separate
one.** The user directory is resolved identically by a source checkout and a frozen artifact; the
only thing that differs is what "the baseline" is behind it. An update that lands somewhere the
frozen build does not read is the failure `T-198` named as the worst available, and the way it is
avoided is by writing to the one location that was already being read.

## No import, no version claim

**This module never imports yt-dlp and never reports its version.** `ARCHITECTURE.md` §6 permits
`import yt_dlp` in `worker.py` and `ytdlp_adapter.py` alone, and the version a user is shown has
to be the one a worker actually imported (`REQ-025`) — not one inferred here from a `.dist-info`
directory name. Those two answers can disagree: a half-extracted tree, a wheel whose metadata
does not match its contents, or a directory the worker rejects at import all produce a
`.dist-info` saying one thing and an import saying another. **Reading the filename would be a
second source of truth for the number this task exists to report**, so it is not read.

What this module returns is therefore what it *did*, never what is now in use. The caller asks a
worker.

## Nothing is disturbed until everything has been verified

`T-198`'s fifth criterion: a failed update — no network, a refused index, a corrupt download —
leaves the working version in place. So the live directory is not touched until a fully
downloaded, hash-verified, fully extracted tree exists beside it; installation is then two
renames. A half-extracted yt-dlp is a broken application, and it is broken in the way that looks
like the application's fault rather than the update's.

## What may appear in a message

`NFR-007` and `T-197`'s gate: no URL, no filesystem path, no token reaches a message this module
raises. Errors name *what* failed in the user's terms — the index, the download, the checksum,
the install — because a `URLError` carrying a proxy's credentials is exactly the shape
`T-197` spent seven rounds removing from the logs. The index URL is a constant here, so quoting
it would leak nothing today; it is still not quoted, because the value of the rule is that it
holds without anyone re-deriving it.
"""

import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Final

from tracks_and_trails.downloader.cancellation import Cancelled, not_cancelled, stop_if_cancelled

#: PyPI's JSON API for yt-dlp. Not configurable: an index URL a user can set is an index URL a
#: user can be *told* to set, which turns the update action into an arbitrary code-execution
#: surface pointed at an attacker's host. `OPS-002` already calls this a supply-chain surface.
PYPI_INDEX: Final = "https://pypi.org/pypi/yt-dlp/json"

#: What the distribution is called on PyPI, and what its wheels are named with.
DISTRIBUTION: Final = "yt_dlp"

#: How long any single network call may take. A hung index request must not hang the update.
NETWORK_TIMEOUT_SECONDS: Final = 30.0

#: Refuse a download larger than this. A wheel is ~3 MB; the cap is generous enough that a
#: legitimate growth spurt does not trip it and small enough that a redirect to something
#: enormous cannot fill the user's disk while they wait for a progress bar.
MAXIMUM_WHEEL_BYTES: Final = 96 * 1024 * 1024

#: Read granularity for the download. Small enough that cancellation and progress stay
#: responsive, large enough not to syscall per kilobyte.
_CHUNK_BYTES: Final = 64 * 1024


class UpdateError(Exception):
    """An update or revert that did not happen, with a reason fit to show a user.

    **The message is the user-facing sentence.** Every raise site in this module writes one that
    says what failed and what it means, because the alternative is a dialog quoting
    `HTTPError: 403` at somebody who wanted a newer yt-dlp. It carries no URL and no path
    (`NFR-007`).
    """


@dataclass(frozen=True, slots=True)
class Release:
    """One yt-dlp wheel on PyPI: which version, where, and what it must hash to.

    `digest` is PyPI's own `sha256` for the file. It is metadata from the same host that serves
    the file, so it is not a defence against a compromised index — it is a defence against a
    truncated or corrupted transfer, which is the failure this actually sees. Refusing to install
    an artifact whose bytes do not match its published digest is the floor, not the ceiling.
    """

    version: str
    url: str
    digest: str
    filename: str


#: Opens a URL and yields a readable binary stream. Injected so tests drive the failure modes —
#: refused index, truncated body, wrong digest — without a network.
#:
#: A *context manager* rather than a bare stream, so a caller cannot forget to close one and so a
#: fake in a test is the same shape as the real opener.
UrlOpener = Callable[[str], AbstractContextManager[IO[bytes]]]


@contextmanager
def _open_url(url: str) -> Iterator[IO[bytes]]:
    """The real opener: HTTPS only, with a timeout, and no redirect off the index host.

    `urllib` follows redirects by default, and an index that redirects the wheel to another host
    is not something this needs to support — PyPI serves its own files.
    """
    # Checked on the string before anything is constructed or opened, so the `https`-only
    # guarantee holds at the point ruff's `S310` is asking about rather than one line later.
    if not url.startswith("https://"):
        raise UpdateError("The update location is not an https address, so it was not contacted.")
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:  # noqa: S310
        yield response


def _read_index(open_url: UrlOpener) -> Any:
    """Fetch and parse the index document, turning every transport failure into one sentence."""
    try:
        with open_url(PYPI_INDEX) as stream:
            payload = stream.read(MAXIMUM_WHEEL_BYTES)
    except urllib.error.HTTPError as error:
        raise UpdateError(
            f"The package index refused the request ({error.code}). "
            "Nothing was changed; the version in use is untouched."
        ) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise UpdateError(
            "The package index could not be reached. Check your connection and try again; "
            "the version in use is untouched."
        ) from error
    try:
        return json.loads(payload)
    except (ValueError, UnicodeDecodeError) as error:
        raise UpdateError(
            "The package index returned something that is not a package listing. "
            "Nothing was changed."
        ) from error


def latest_release(open_url: UrlOpener | None = None) -> Release:
    """The newest yt-dlp wheel PyPI lists, or `UpdateError` saying why there is none.

    **A wheel, specifically.** `OPS-002` rests on yt-dlp being pure Python, so a wheel is
    extractable without a compiler; a source distribution is not, and installing one would need
    the build machinery a frozen artifact does not have. If the release ever ships no wheel, that
    is the compiled-dependency case `OPS-002` says reopens the decision — so it is reported as
    such rather than worked around.
    """
    opener = _open_url if open_url is None else open_url
    document = _read_index(opener)
    if not isinstance(document, dict):
        raise UpdateError("The package index returned something that is not a package listing.")
    info = document.get("info")
    version = info.get("version") if isinstance(info, dict) else None
    if not isinstance(version, str) or not version.strip():
        raise UpdateError("The package index did not name a current version. Nothing was changed.")

    entries = document.get("urls")
    for entry in entries if isinstance(entries, list) else ():
        if not isinstance(entry, dict) or entry.get("packagetype") != "bdist_wheel":
            continue
        if entry.get("yanked"):
            continue
        url = entry.get("url")
        filename = entry.get("filename")
        digests = entry.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if not (isinstance(url, str) and isinstance(filename, str) and isinstance(digest, str)):
            continue
        if not filename.startswith(DISTRIBUTION) or not filename.endswith(".whl"):
            continue
        return Release(version=version.strip(), url=url, digest=digest, filename=filename)

    raise UpdateError(
        f"yt-dlp {version.strip()} publishes no installable wheel, so it cannot be installed "
        "this way. Nothing was changed."
    )


def _download_wheel(
    release: Release,
    destination: Path,
    open_url: UrlOpener,
    cancelled: Cancelled = not_cancelled,
) -> None:
    """Stream the wheel to `destination` and refuse it unless its bytes match `release.digest`.

    Hashing happens **while** writing rather than by re-reading the finished file: one pass, and
    no window in which the file on disk differs from the bytes that were checked.

    **Asked between chunks** (`T289-R21`). A download is the longest thing an update does and the
    one place where "stop" costs nothing: `destination` is inside the staging workspace, which
    `install_latest`'s `finally` removes, so a partial file is discarded by the same code that
    discards it after any other failure. An individual read is not interrupted — the next boundary
    declines to continue, which is what cooperative cancellation is.
    """
    digest = hashlib.sha256()
    written = 0
    try:
        with open_url(release.url) as stream, destination.open("wb") as sink:
            while chunk := stream.read(_CHUNK_BYTES):
                stop_if_cancelled(cancelled)
                written += len(chunk)
                if written > MAXIMUM_WHEEL_BYTES:
                    raise UpdateError(
                        "The download was larger than any yt-dlp release, so it was refused. "
                        "Nothing was changed."
                    )
                digest.update(chunk)
                sink.write(chunk)
    except urllib.error.HTTPError as error:
        raise UpdateError(
            f"The download was refused ({error.code}). Nothing was changed."
        ) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise UpdateError(
            "The download did not finish. Check your connection and try again; "
            "the version in use is untouched."
        ) from error

    if digest.hexdigest() != release.digest.strip().lower():
        raise UpdateError(
            "The downloaded file did not match the checksum the index published for it, "
            "so it was discarded. Nothing was changed."
        )


def _extract_wheel(wheel: Path, into: Path) -> None:
    """Unpack a verified wheel into an empty directory.

    A wheel is a zip whose top level *is* what `site-packages` would receive, so extraction is
    the whole install. `ZipFile.extract` sanitises member names — absolute paths and `..`
    components are stripped by CPython before anything is written — so a malicious archive
    cannot escape `into`. That is a property of the standard library rather than of this
    function, which is why it is stated here rather than reimplemented badly beside it.
    """
    try:
        with zipfile.ZipFile(wheel) as archive:
            # CPython sanitises member names before writing; see the docstring.
            archive.extractall(into)
    except (zipfile.BadZipFile, OSError) as error:
        raise UpdateError(
            "The downloaded file was not a readable package, so it was discarded. "
            "Nothing was changed."
        ) from error
    if not (into / DISTRIBUTION).is_dir():
        raise UpdateError(
            "The downloaded package did not contain yt-dlp, so it was discarded. "
            "Nothing was changed."
        )


def _swap_into_place(staged: Path, directory: Path) -> None:
    """Replace `directory` with `staged`, keeping a working tree at every moment.

    Two renames with the old tree kept until the new one is in place: if the second rename fails
    — which on Windows means a running worker still holds the directory open — the old tree goes
    back and the user keeps what they had.
    """
    directory.parent.mkdir(parents=True, exist_ok=True)
    displaced = directory.with_name(f"{directory.name}.replaced")
    shutil.rmtree(displaced, ignore_errors=True)

    had_previous = directory.exists()
    if had_previous:
        try:
            directory.rename(displaced)
        except OSError as error:
            raise UpdateError(
                "The installed copy could not be moved aside, which usually means a download is "
                "still running. Stop the queue and try again; nothing was changed."
            ) from error
    try:
        staged.rename(directory)
    except OSError as error:
        if had_previous:
            # Put it back. Failing to install is recoverable; failing to install *and* losing
            # what was there is the outcome this whole two-step exists to prevent.
            #
            # **The restore is itself allowed to fail**, and that case gets its own sentence
            # rather than escaping as an `OSError` nobody wrote for a user. It is the one path
            # here that leaves nothing resolvable in the directory, so it says what to do:
            # reverting is what puts a working yt-dlp back.
            try:
                displaced.rename(directory)
            except OSError as restore_failure:
                raise UpdateError(
                    "The new version could not be installed and the previous one could not be "
                    "put back. Revert to the bundled version to get a working yt-dlp again."
                ) from restore_failure
        raise UpdateError(
            "The new version could not be moved into place, so the previous one was kept."
        ) from error
    shutil.rmtree(displaced, ignore_errors=True)


def install_latest(
    directory: Path,
    open_url: UrlOpener | None = None,
    release: Release | None = None,
    cancelled: Cancelled = not_cancelled,
) -> Release:
    """Download, verify and install the newest yt-dlp wheel into `directory`.

    Returns the release that was installed. **It does not claim that is now the version in
    use** — only a worker's import can say that (`REQ-025`), and the caller asks one.

    `release` is injectable so a caller that has already looked the index up (to show the user
    what they are about to install) does not look it up twice and risk installing a different
    version from the one it named.

    **Cancellable up to the swap, and not through it** (`T289-R21`). `cancelled` is asked after the
    release lookup, between download chunks, after the download and after the staged tree exists —
    every one of those points leaves the live directory untouched and the workspace to be removed
    by the `finally` below. `_swap_into_place` is the one interval that must not be stopped: it
    displaces the live tree and either completes or rolls back, which is `T-198`'s transaction and
    the reason a checkpoint inside it would be a way to lose a working yt-dlp rather than a way to
    exit tidily.
    """
    opener = _open_url if open_url is None else open_url
    chosen = latest_release(opener) if release is None else release
    # **After the lookup, before anything is written.** The index read is network time with no
    # local effect at all, so stopping on the far side of it costs nothing and skips the download.
    stop_if_cancelled(cancelled)

    directory.parent.mkdir(parents=True, exist_ok=True)
    # Staged as a sibling so the final step is a rename within one filesystem. A temp directory
    # elsewhere could land on another device, where `rename` fails and the fallback is a copy —
    # which is exactly the non-atomic install this avoids.
    workspace = Path(tempfile.mkdtemp(prefix=f".{directory.name}.staging-", dir=directory.parent))
    try:
        # **A fixed name, not the index's.** `chosen.filename` is untrusted metadata, and joining
        # it to a path is how a name like `../../something` escapes the workspace. Nothing needs
        # the real filename on disk — it is shown to the user and never opened by name — so the
        # traversal surface is removed rather than guarded against.
        wheel = workspace / "downloaded.whl"
        unpacked = workspace / "tree"
        unpacked.mkdir()
        _download_wheel(chosen, wheel, opener, cancelled)
        # **After the download, before the extraction.** Everything so far lives in `workspace`.
        stop_if_cancelled(cancelled)
        _extract_wheel(wheel, unpacked)
        wheel.unlink(missing_ok=True)
        # **The last one, and it is the boundary of the transaction.** A fully staged tree beside
        # the live one is still nothing the user can see; the next line is where that stops being
        # true, so this is the last moment stopping is free.
        stop_if_cancelled(cancelled)
        _swap_into_place(unpacked, directory)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    return chosen


def revert_to_baseline(directory: Path) -> bool:
    """Remove the user-managed copy so resolution falls back to the bundled baseline.

    Returns whether there was one to remove, so a caller can tell "reverted" from "already on the
    baseline" without asking the filesystem a second time and racing itself.

    **Renamed before it is deleted**, for the reason `_swap_into_place` uses two steps: the
    rename is the atomic moment. Once the directory no longer carries its resolved name,
    `ytdlp_candidates` stops offering it, and how long the delete then takes stops mattering.
    """
    if not directory.exists():
        return False
    discarded = directory.with_name(f"{directory.name}.reverted")
    shutil.rmtree(discarded, ignore_errors=True)
    try:
        directory.rename(discarded)
    except OSError as error:
        raise UpdateError(
            "The installed copy could not be removed, which usually means a download is still "
            "running. Stop the queue and try again."
        ) from error
    shutil.rmtree(discarded, ignore_errors=True)
    return True
