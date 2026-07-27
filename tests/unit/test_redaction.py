"""Structural redaction of credentials and cookie paths (`T014-R1`, `REQ-026`, `NFR-007`).

Two directions matter equally and the second is easy to forget. A leak violates `REQ-026`; a
diagnostic mangled into uselessness violates `NFR-006`, which requires the extractor's message be
preserved rather than replaced with something the user cannot act on.

The third section pins the **boundary** — what this deliberately does not catch. `T-044` cost six
review rounds by enumerating what a thing might look like and then claiming completeness, and
`T-045` restated the same defect. This module recognises two *structural* constructs and says so;
free-form secret content in arbitrary prose is not one of them.
"""

import pytest

from tracks_and_trails.core.redaction import REDACTED, redact, redact_optional

# --- credentials, the Critical path (T014-R1) ------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "must_keep"),
    [
        pytest.param("http://user:pass@proxy.invalid:8080", "proxy.invalid:8080", id="scheme"),
        # The form that defeated the previous implementation: `urlsplit` puts this entirely in
        # `path` and leaves `netloc` empty, so a netloc-only check returned it unchanged.
        pytest.param("user:pass@proxy.invalid:8080", "proxy.invalid:8080", id="scheme-less"),
        pytest.param("socks5://u:p@proxy.invalid:1080", "proxy.invalid:1080", id="socks"),
        pytest.param("HTTP://u:p@Proxy.Invalid:8080", "Proxy.Invalid:8080", id="uppercase"),
        pytest.param("https://u:p@localhost:3128", "localhost:3128", id="localhost"),
        pytest.param("http://u:p@[2001:db8::1]:8080", "[2001:db8::1]:8080", id="ipv6"),
        pytest.param("http://u:p%40x@proxy.invalid", "proxy.invalid", id="encoded-userinfo"),
    ],
)
def test_credentials_are_removed_and_the_host_survives(raw: str, must_keep: str) -> None:
    """`REQ-026`. The host must survive: a proxy without one is not a proxy setting at all."""
    cleaned = redact(raw)
    assert "pass" not in cleaned
    assert "hunter2" not in cleaned
    assert must_keep in cleaned
    assert REDACTED in cleaned


def test_credentials_are_removed_from_the_middle_of_prose() -> None:
    """The realistic sink is a diagnostic, not a bare URL (`T014-R1`)."""
    cleaned = redact("proxy failed: http://secretuser:hunter2@proxy.invalid:8080 refused")
    assert "hunter2" not in cleaned
    assert "secretuser" not in cleaned
    assert "proxy failed" in cleaned
    assert "refused" in cleaned


def test_redaction_is_idempotent() -> None:
    """A value may be redacted into the database and again into a log; twice must equal once."""
    once = redact("http://u:p@proxy.invalid:8080")
    assert redact(once) == once


def test_none_passes_through() -> None:
    assert redact_optional(None) is None


# --- cookie paths (REQ-026 names them explicitly) --------------------------------------------


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        pytest.param("Cookie file /home/someone/cookies.txt missing", "cookies.txt", id="posix"),
        pytest.param(r"could not read C:\Users\someone\cookies.txt", "cookies.txt", id="windows"),
        pytest.param("unable to open --cookies /var/data/jar", "/var/data/jar", id="flag"),
        pytest.param(
            "--cookies-from-browser /home/someone/.mozilla", ".mozilla", id="browser-flag"
        ),
    ],
)
def test_cookie_paths_are_removed(raw: str, secret: str) -> None:
    assert secret not in redact(raw)
    assert REDACTED in redact(raw)


# --- the other direction: NFR-006 (do not destroy the diagnostic) ----------------------------


@pytest.mark.parametrize(
    "message",
    [
        "Video unavailable: this video is private",
        "retry at 10:30@home",
        "HTTP Error 404: Not Found",
        "ffmpeg exited 1 while merging",
        "No space left on device: /downloads/film.mp4",
        "contact someone@example.invalid for access",
    ],
)
def test_ordinary_diagnostics_are_left_alone(message: str) -> None:
    """Over-eager redaction violates `NFR-006` as surely as a leak violates `REQ-026`.

    `retry at 10:30@home` is the shape that a naive `x:y@z` rule mangles, and
    `someone@example.invalid` is an ordinary address with no userinfo colon before the `@`.
    """
    assert redact(message) == message


# --- the boundary, pinned rather than claimed away -------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        pytest.param("session cookie value is abc123def456", id="bare-cookie-value"),
        pytest.param("Authorization: Bearer eyJhbGciOi", id="bearer-token"),
        pytest.param("password is hunter2", id="password-in-prose"),
    ],
)
def test_free_form_secret_content_is_not_recognised(message: str) -> None:
    """**A stated limit, not an oversight** (`T-044`'s lesson, applied deliberately).

    A cookie value, a bearer token or a password written as prose is not structurally
    distinguishable from ordinary text. Catching it would mean enumerating what secrets look
    like and then treating the enumeration as exhaustive — the defect that cost `T-044` six
    review rounds and `T-045` one.

    This is pinned so the limit stays visible. If a future change *does* catch these, this test
    fails and should be deleted along with the caveat in `core/redaction.py` — rather than the
    module quietly acquiring a guarantee nobody verified.
    """
    assert redact(message) == message
