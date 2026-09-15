"""Certificates are verified against the operating system's own trust (`REL-007`).

**Windows only, and why it cannot be left to Python's default.** Python's `ssl` on Windows copies
the certificates already sitting in the `ROOT` and `CA` stores into OpenSSL, and yt-dlp does the
same (`load_default_certs`). Windows does not keep every trusted root there: it fetches one the
first time its own verifier needs it. A machine that has never met a site's root therefore cannot
verify that site from Python while Edge and `Invoke-WebRequest` reach it without complaint.

Found in `T-327`'s session: **every YouTube download failed in a fresh Windows Sandbox** with
`CERTIFICATE_VERIFY_FAILED`, the same videos downloaded on Linux, and `Invoke-WebRequest` to
`https://www.youtube.com` succeeded in that same Sandbox — while `GTS Root R1` was absent from
`Cert:\\LocalMachine\\Root` before and after it. `STARBASE`, where the network suite runs, has
browsed enough to hold the root, which is why no test saw it.

`truststore` makes an `ssl.SSLContext` verify by calling the platform's own chain builder —
`CertGetCertificateChain` on Windows — which fetches a missing root exactly as a browser would,
and honours a corporate or user-added root, the property `REL-007` refused `certifi` for losing.

**Linux: OpenSSL is pointed at the distribution's own bundle when it cannot find one** (`T-341`).
Its store is a set of files OpenSSL reads completely, so Windows' gap does not exist there. A
different one does: the AppImage bundles the OpenSSL it was built with on Debian, which looks only
in `/usr/lib/ssl`. Fedora has no such directory, so **every HTTPS request from the `0.1.0`
candidates failed on Fedora** with `CERTIFICATE_VERIFY_FAILED`, while the `ubuntu:24.04` clean
machine, which has that path, downloaded. Measured on Fedora 44: the draft AppImage's download
probe failed as it was, and passed with `SSL_CERT_FILE` naming Fedora's bundle.

So when neither built-in location exists (an empty directory counting as absent), `SSL_CERT_FILE`
is set to the first bundle in `LINUX_CA_BUNDLES` that exists. It is still **the machine's own
store**, as `REL-007` decided, and a user-added root the distribution installed is in it. Nothing is
changed when a built-in location exists (a distribution's own Python, or Debian and Ubuntu), when
the user already set
`SSL_CERT_FILE` or `SSL_CERT_DIR`, or when no bundle exists: `REL-007`'s bare container stays a
machine with no store.

OpenSSL reads the variable each time a context loads its default locations, so setting it in
this process reaches yt-dlp's contexts and `urllib`'s alike, and a spawned worker inherits it.

**Injected per process.** `inject_into_ssl` replaces `ssl.SSLContext` in the module, which reaches
yt-dlp's `make_ssl_context` and `urllib.request` alike because both look the name up at call time.
A spawned worker starts with an unpatched `ssl`, so it calls this itself; see `worker.run_session`
and `app.run`.
"""

import os
import ssl
from collections.abc import MutableMapping, Sequence
from pathlib import Path
from typing import Final

#: Where Linux distributions keep their combined CA bundle, in the order Go's `crypto/x509` reads
#: them. Several are symlinks to one another on a given distribution; the first that exists wins.
LINUX_CA_BUNDLES: Final = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu, Arch, Gentoo; Fedora links it too
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora and RHEL, older releases
    "/etc/ssl/ca-bundle.pem",  # openSUSE
    "/etc/pki/tls/cacert.pem",  # OpenELEC
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora, CentOS and RHEL 7 and later
    "/etc/ssl/cert.pem",  # Alpine
)


def verify_with_the_operating_system(
    *,
    os_name: str = os.name,
    environ: MutableMapping[str, str] = os.environ,
    default_paths: ssl.DefaultVerifyPaths | None = None,
    bundles: Sequence[str] = LINUX_CA_BUNDLES,
) -> bool:
    """Make this process verify against the operating system's trust; `True` when it changed.

    Idempotent, and called before any connection is opened. `os_name` rather than
    `sys.platform`, because mypy narrows the latter and would call the Windows half unreachable
    under the Linux run.
    """
    if os_name == "nt":
        import truststore

        truststore.inject_into_ssl()
        return True
    if os_name != "posix":
        return False
    return _find_the_system_bundle(
        environ, default_paths or ssl.get_default_verify_paths(), bundles
    )


def _find_the_system_bundle(
    environ: MutableMapping[str, str], paths: ssl.DefaultVerifyPaths, bundles: Sequence[str]
) -> bool:
    """Point OpenSSL at the distribution's bundle if it has no built-in location to read."""
    if "SSL_CERT_FILE" in environ or "SSL_CERT_DIR" in environ:
        return False
    if _has_a_default_location(paths):
        return False
    found = next((bundle for bundle in bundles if Path(bundle).is_file()), None)
    if found is None:
        return False
    environ["SSL_CERT_FILE"] = found
    return True


def _has_a_default_location(paths: ssl.DefaultVerifyPaths) -> bool:
    """Whether OpenSSL's compiled-in file exists or its directory has any entry (`T341-R1`).

    **Existence, not validity.** An empty file or a directory holding only a README counts, and
    the machine is left as it is. That is the conservative boundary: this recovers a location that
    is missing, and does not second-guess one that is there, malformed or not. Counting what a
    fresh context loads would not do instead, because OpenSSL reads a hashed directory only when a
    verification needs it.
    """
    if paths.cafile and Path(paths.cafile).is_file():
        return True
    if paths.capath and Path(paths.capath).is_dir():
        try:
            return any(Path(paths.capath).iterdir())
        except OSError:
            return False
    return False
