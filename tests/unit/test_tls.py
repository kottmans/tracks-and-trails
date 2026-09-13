"""`downloader/tls.py`: Windows verifies certificates with its own chain builder (`REL-007`)."""

import ssl
import urllib.request
from collections.abc import Iterator

import pytest
import truststore

from tracks_and_trails.downloader.tls import verify_with_the_operating_system


@pytest.fixture
def unpatched_ssl() -> Iterator[None]:
    """Put `ssl.SSLContext` back however the test left it; the patch is process-wide."""
    original = ssl.SSLContext
    try:
        yield
    finally:
        truststore.extract_from_ssl()
        ssl.SSLContext = original  # type: ignore[misc]


@pytest.mark.usefixtures("unpatched_ssl")
def test_windows_hands_verification_to_the_operating_system() -> None:
    assert verify_with_the_operating_system(os_name="nt") is True
    assert ssl.SSLContext is truststore.SSLContext


@pytest.mark.usefixtures("unpatched_ssl")
@pytest.mark.parametrize("os_name", ["posix", "java"])
def test_other_platforms_keep_openssls_own_store(os_name: str) -> None:
    """Linux's store is files OpenSSL reads completely, so there is no gap to close there."""
    original = ssl.SSLContext

    assert verify_with_the_operating_system(os_name=os_name) is False
    assert ssl.SSLContext is original


@pytest.mark.usefixtures("unpatched_ssl")
def test_the_patch_reaches_the_contexts_yt_dlp_and_urllib_actually_build() -> None:
    """**The claim that matters is about the context a download uses**, not about a module name.

    yt-dlp's `make_ssl_context` and `urllib.request` both look `ssl.SSLContext` up when they
    are called, which is why patching after they were imported works. If either ever bound the
    class at import time, this is what would say so.
    """
    from yt_dlp.networking._helper import make_ssl_context

    verify_with_the_operating_system(os_name="nt")

    assert isinstance(make_ssl_context(), truststore.SSLContext)
    handler = urllib.request.HTTPSHandler()
    assert isinstance(handler._context, truststore.SSLContext)  # type: ignore[attr-defined]


@pytest.mark.usefixtures("unpatched_ssl")
def test_calling_it_twice_is_harmless() -> None:
    """`app.run` and the download probe's in-process `run_session` both call it."""
    verify_with_the_operating_system(os_name="nt")
    verify_with_the_operating_system(os_name="nt")

    assert ssl.SSLContext is truststore.SSLContext
