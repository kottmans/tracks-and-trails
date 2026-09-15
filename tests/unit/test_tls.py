"""`downloader/tls.py`: Windows verifies with its own chain builder; Linux finds its store.

`REL-007`, and `T-341` for the Linux half.
"""

import os
import ssl
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import truststore

from tracks_and_trails.downloader.tls import LINUX_CA_BUNDLES, verify_with_the_operating_system


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
def test_other_platforms_keep_openssls_own_verifier(os_name: str, tmp_path: Path) -> None:
    """Linux's store is files OpenSSL reads completely, so its context class is never replaced."""
    original = ssl.SSLContext

    verify_with_the_operating_system(
        os_name=os_name, environ={}, default_paths=_paths(), bundles=[str(_bundle(tmp_path))]
    )
    assert ssl.SSLContext is original


def _paths(cafile: str | None = None, capath: str | None = None) -> ssl.DefaultVerifyPaths:
    """What `ssl.get_default_verify_paths` answers; `None` for a location that does not exist.

    typeshed types both as `str`, but CPython answers `None` for a missing location, which is the
    case under test.
    """
    return ssl.DefaultVerifyPaths(
        cast("str", cafile),
        cast("str", capath),
        "SSL_CERT_FILE",
        "/usr/lib/ssl/cert.pem",
        "SSL_CERT_DIR",
        "/usr/lib/ssl/certs",
    )


def _bundle(directory: Path, name: str = "bundle.pem") -> Path:
    path = directory / name
    path.write_text("not read by these tests\n", encoding="utf-8")
    return path


def test_linux_with_no_built_in_store_is_pointed_at_the_distributions_bundle(
    tmp_path: Path,
) -> None:
    """`T-341`, the Fedora case: a Debian-built OpenSSL whose `/usr/lib/ssl` does not exist.

    The first bundle that exists wins, in the list's order.
    """
    environ: dict[str, str] = {}
    first = _bundle(tmp_path, "first.pem")
    second = _bundle(tmp_path, "second.pem")

    changed = verify_with_the_operating_system(
        os_name="posix",
        environ=environ,
        default_paths=_paths(),
        bundles=[str(tmp_path / "missing.pem"), str(first), str(second)],
    )

    assert changed is True
    assert environ == {"SSL_CERT_FILE": str(first)}


def test_an_empty_certificate_directory_is_no_store(tmp_path: Path) -> None:
    """`ubuntu:24.04` without `ca-certificates`: the directory exists and holds nothing."""
    empty = tmp_path / "certs"
    empty.mkdir()
    environ: dict[str, str] = {}

    changed = verify_with_the_operating_system(
        os_name="posix",
        environ=environ,
        default_paths=_paths(capath=str(empty)),
        bundles=[str(_bundle(tmp_path))],
    )

    assert changed is True
    assert "SSL_CERT_FILE" in environ


@pytest.mark.parametrize("built_in", ["file", "directory"])
def test_an_existing_default_location_is_left_alone(tmp_path: Path, built_in: str) -> None:
    """Debian, Ubuntu, and any distribution's own Python: a default location exists.

    **Existence is what is checked, not the certificates in it** (`T341-R1`); the entries here are
    not certificates, and the machine is still left as it is. The real-certificate test below is
    the proof that a pointed-at bundle loads.
    """
    certs = tmp_path / "certs"
    certs.mkdir()
    (certs / "002c0b4f.0").write_text("x", encoding="utf-8")
    cafile = _bundle(tmp_path, "cert.pem")
    paths = _paths(cafile=str(cafile)) if built_in == "file" else _paths(capath=str(certs))
    environ: dict[str, str] = {}

    changed = verify_with_the_operating_system(
        os_name="posix",
        environ=environ,
        default_paths=paths,
        bundles=[str(_bundle(tmp_path, "other.pem"))],
    )

    assert changed is False
    assert environ == {}


@pytest.mark.parametrize("variable", ["SSL_CERT_FILE", "SSL_CERT_DIR"])
def test_a_location_the_user_chose_wins(tmp_path: Path, variable: str) -> None:
    """A user who set either variable has said where their trust is; it is not second-guessed."""
    environ = {variable: "/somewhere/the/user/chose"}

    changed = verify_with_the_operating_system(
        os_name="posix", environ=environ, default_paths=_paths(), bundles=[str(_bundle(tmp_path))]
    )

    assert changed is False
    assert environ == {variable: "/somewhere/the/user/chose"}


def test_a_machine_with_no_bundle_anywhere_is_left_as_it_is(tmp_path: Path) -> None:
    """`REL-007`'s bare container: no store to find, and none is invented."""
    environ: dict[str, str] = {}

    changed = verify_with_the_operating_system(
        os_name="posix",
        environ=environ,
        default_paths=_paths(),
        bundles=[str(tmp_path / "missing.pem")],
    )

    assert changed is False
    assert environ == {}


@pytest.mark.skipif(sys.platform == "win32", reason="Windows contexts read the Windows store")
def test_openssl_reads_the_bundle_it_was_pointed_at_in_this_process(tmp_path: Path) -> None:
    """**The mechanism, with a real OpenSSL**: a variable set after `ssl` was imported still
    decides what the next context loads, which is what lets the parent set it at startup.

    The bundle holds exactly one certificate, copied from this machine's store, so the count
    proves which file was read: a default store loads many, or none.
    """
    source = next((Path(each) for each in LINUX_CA_BUNDLES if Path(each).is_file()), None)
    if source is None:
        pytest.skip("this machine has no CA bundle to copy a certificate from")
    text = source.read_text(encoding="utf-8")
    end = "-----END CERTIFICATE-----"
    one = text[text.index("-----BEGIN CERTIFICATE-----") : text.index(end) + len(end)] + "\n"
    bundle = tmp_path / "one.pem"
    bundle.write_text(one, encoding="ascii")

    saved = {
        name: os.environ.pop(name)
        for name in ("SSL_CERT_FILE", "SSL_CERT_DIR")
        if name in os.environ
    }
    try:
        changed = verify_with_the_operating_system(
            os_name="posix", default_paths=_paths(), bundles=[str(bundle)]
        )
        context = ssl.create_default_context()
    finally:
        os.environ.pop("SSL_CERT_FILE", None)
        os.environ.update(saved)

    assert changed is True
    assert context.cert_store_stats()["x509_ca"] == 1


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
