"""Asks GitHub which Tracks & Trails release is newest (`T-338`, `NFR-007`).

One request, to one constant address, answered by one parsed version. What `core/app_updates.py`
says about what is sent and why the page is never taken from the answer applies here; this module
is the part that touches the network, which is why it is in `downloader/` beside yt-dlp's updater.

**Messages carry no URL**, for `ytdlp_update`'s reason: the rule holds without anyone re-deriving
whether a given address is safe to quote.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import IO, Final

from tracks_and_trails.core.app_updates import LATEST_RELEASE_API, parse_version, release_page

#: How long the request may take. An automatic check runs in the background, but a hung one would
#: still hold a pool thread that shutdown then waits for.
NETWORK_TIMEOUT_SECONDS: Final = 15.0

#: A release document is a few kilobytes; this refuses a redirect to something enormous.
MAXIMUM_RESPONSE_BYTES: Final = 1024 * 1024

#: GitHub's API refuses requests without a `User-Agent`. The name only, and no version: the
#: version would tell GitHub which release each user runs, which this check exists not to send.
USER_AGENT: Final = "Tracks-and-Trails"

UrlOpener = Callable[[str], AbstractContextManager[IO[bytes]]]


class AppReleaseError(Exception):
    """Why the newest release could not be learned, in the user's terms."""


@dataclass(frozen=True)
class AppRelease:
    """The newest published release: its version, and the page this application built for it."""

    version: str
    page: str


@contextmanager
def _open_url(url: str) -> Iterator[IO[bytes]]:
    """HTTPS only, with a timeout and the headers GitHub's API asks for."""
    if not url.startswith("https://"):
        raise AppReleaseError("The release address is not an https address, so it was not used.")
    request = urllib.request.Request(  # noqa: S310
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Accept-Encoding": "identity",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:  # noqa: S310
        yield response


def latest_app_release(open_url: UrlOpener | None = None) -> AppRelease:
    """The newest published release, or `AppReleaseError` saying why there is none."""
    opener = _open_url if open_url is None else open_url
    try:
        with opener(LATEST_RELEASE_API) as stream:
            payload = stream.read(MAXIMUM_RESPONSE_BYTES)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            # GitHub's answer when the repository has no published release yet.
            raise AppReleaseError("No version has been released yet.") from error
        raise AppReleaseError(
            f"GitHub refused the request ({error.code}). Try again later."
        ) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise AppReleaseError(
            "GitHub could not be reached. Check your connection and try again."
        ) from error
    try:
        document = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as error:
        raise AppReleaseError("GitHub's answer was not a release.") from error
    tag = document.get("tag_name") if isinstance(document, dict) else None
    version = parse_version(tag) if isinstance(tag, str) else None
    if version is None:
        raise AppReleaseError("GitHub's answer did not name a version.")
    return AppRelease(version=version.text, page=release_page(version))
