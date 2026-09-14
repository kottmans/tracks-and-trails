"""Asking GitHub for the newest release, without GitHub (`T-338`)."""

import io
import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any

import pytest

import tracks_and_trails.downloader.app_release as app_release
from tracks_and_trails.core.app_updates import LATEST_RELEASE_API
from tracks_and_trails.downloader.app_release import (
    USER_AGENT,
    AppReleaseError,
    _open_url,
    latest_app_release,
)

REAL_OPEN_URL = _open_url


def answering(document: Any) -> app_release.UrlOpener:
    body = document if isinstance(document, bytes) else json.dumps(document).encode()

    @contextmanager
    def opener(url: str) -> Iterator[IO[bytes]]:
        assert url == LATEST_RELEASE_API
        yield io.BytesIO(body)

    return opener


def raising(error: BaseException) -> app_release.UrlOpener:
    @contextmanager
    def opener(url: str) -> Iterator[IO[bytes]]:
        if url:
            raise error
        yield io.BytesIO()

    return opener


def test_the_newest_release_is_its_tag_and_a_page_built_here() -> None:
    release = latest_app_release(answering({"tag_name": "v0.2.0"}))
    assert release.version == "0.2.0"
    assert release.page == "https://github.com/kottmans/tracks-and-trails/releases/tag/v0.2.0"


def test_an_address_in_the_answer_is_never_the_page() -> None:
    """Whatever wrote the response must not choose where a browser goes."""
    release = latest_app_release(
        answering({"tag_name": "v0.2.0", "html_url": "https://attacker.example/download"})
    )
    assert "attacker" not in release.page


@pytest.mark.parametrize(
    "document",
    [
        {"tag_name": "v0.2.0/../../evil"},
        {"tag_name": "nightly"},
        {"tag_name": 2},
        {},
        [],
        b"<html>rate limited</html>",
    ],
)
def test_an_answer_without_a_version_is_refused(document: Any) -> None:
    with pytest.raises(AppReleaseError):
        latest_app_release(answering(document))


def test_no_release_yet_says_so() -> None:
    missing = urllib.error.HTTPError(LATEST_RELEASE_API, 404, "Not Found", {}, None)  # type: ignore[arg-type]
    with pytest.raises(AppReleaseError, match="No version has been released yet"):
        latest_app_release(raising(missing))


def test_a_refusal_and_an_outage_are_sentences_without_the_address() -> None:
    refused = urllib.error.HTTPError(LATEST_RELEASE_API, 403, "Forbidden", {}, None)  # type: ignore[arg-type]
    for error in (refused, urllib.error.URLError("down"), TimeoutError()):
        with pytest.raises(AppReleaseError) as caught:
            latest_app_release(raising(error))
        assert "http" not in str(caught.value)


def test_the_request_names_the_application_and_not_its_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub requires a `User-Agent`. The version would say which release each user runs."""
    import tracks_and_trails

    seen: list[urllib.request.Request] = []

    @contextmanager
    def fake_urlopen(request: urllib.request.Request, timeout: float) -> Iterator[IO[bytes]]:
        seen.append(request)
        yield io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with REAL_OPEN_URL(LATEST_RELEASE_API) as stream:
        stream.read()
    [request] = seen
    assert request.get_header("User-agent") == USER_AGENT
    assert tracks_and_trails.__version__ not in USER_AGENT
    assert request.get_method() == "GET" and request.data is None


def test_only_https_is_contacted() -> None:
    with pytest.raises(AppReleaseError), REAL_OPEN_URL("http://api.github.com/"):
        pass
