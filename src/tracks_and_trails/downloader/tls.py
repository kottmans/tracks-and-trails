"""Certificates are verified by the operating system, not by OpenSSL reading a store (`REL-007`).

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

**Linux is left alone.** Its store is a set of files OpenSSL reads completely, so the gap does not
exist there, and `REL-007`'s bare-container finding is about an empty store, which no verifier can
fill.

**Injected per process.** `inject_into_ssl` replaces `ssl.SSLContext` in the module, which reaches
yt-dlp's `make_ssl_context` and `urllib.request` alike because both look the name up at call time.
A spawned worker starts with an unpatched `ssl`, so it calls this itself; see `worker.run_session`
and `app.run`.
"""

import os


def verify_with_the_operating_system(*, os_name: str = os.name) -> bool:
    """Make this process's TLS verification the operating system's; `True` when it was changed.

    Idempotent, and called before any connection is opened. `os_name` rather than
    `sys.platform`, because mypy narrows the latter and would call the Windows half unreachable
    under the Linux run.
    """
    if os_name != "nt":
        return False
    import truststore

    truststore.inject_into_ssl()
    return True
