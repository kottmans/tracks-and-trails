"""Structural redaction of secrets from text that is about to be stored (`REQ-026`, `NFR-007`).

`REQ-026` says credentials and cookie paths are never written to logs **or to history**. This
module is the shared implementation of the second half; `T-038` owns the logging handler and
should call this rather than write a second copy, because two redactors are two chances to get
it subtly wrong.

**What this guarantees, stated narrowly on purpose.** Two things are recognised *structurally* —
by what they are, not by what they look like:

- **URL userinfo credentials**, `user:pass@host`, with or without a scheme. This is a defined
  construct in RFC 3986's authority, so recognising it is parsing rather than guessing. The
  scheme-less form matters: `urlsplit("user:pass@host:8080")` puts the whole string in `path`
  and leaves `netloc` empty, so a `netloc`-only check returns it unchanged — that was `T014-R1`.
- **Cookie file paths**, being an absolute path whose text names a cookie, or any path following
  an explicit `--cookies` flag.

**What it does not guarantee, and why that is said rather than papered over.** Free-form secret
*content* — a cookie value, a bearer token, a password — pasted into arbitrary prose is not
structurally distinguishable from ordinary text. Recognising it would mean a heuristic that
enumerates what secrets look like and then claims completeness, which is the failure mode that
cost `T-044` six review rounds and `T-045` one. `test_redaction.py` pins the boundary with
worked examples on both sides of it, so the limit stays visible rather than becoming folklore.

The caller's obligation is therefore to apply this at a **sink** — one choke point that every
value passes through — rather than at each site that happens to remember. `persistence` does
that in `_job_to_values`; `T-038` does it in a handler.
"""

import re
from typing import Final

#: Replacement for a redacted secret. Distinctive so it is obvious in a log or a database row
#: that redaction happened, rather than looking like the value was simply absent.
REDACTED: Final = "[redacted]"

#: `user:pass@host`, with or without a scheme.
#:
#: The host must look like one — a dotted name, `localhost`, or something carrying a port — so
#: ordinary prose containing a colon and an at-sign (`"retry at 10:30@home"`) is not mangled into
#: nonsense. A diagnostic destroyed by over-eager redaction violates `NFR-006` just as surely as
#: a leaked credential violates `REQ-026`.
_CREDENTIALS: Final = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)?"
    r"(?P<userinfo>[^\s/@:]+:[^\s/@]*)@"
    r"(?P<host>(?:localhost|\[[0-9A-Fa-f:]+\]|[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+)(?::\d+)?)"
)

#: An absolute path, POSIX or Windows, whose text names a cookie.
_COOKIE_PATH: Final = re.compile(
    r"(?:[A-Za-z]:[\\/]|/)[^\s\"'<>|]*cookie[^\s\"'<>|]*",
    re.IGNORECASE,
)

#: Whatever follows an explicit cookies flag, whether or not the filename says "cookie".
_COOKIE_FLAG: Final = re.compile(r"(--cookies(?:-from-browser)?[=\s]+)(\S+)", re.IGNORECASE)


def _mask_credentials(match: re.Match[str]) -> str:
    return f"{match.group('scheme') or ''}{REDACTED}@{match.group('host')}"


def redact(text: str) -> str:
    """Return `text` with URL credentials and cookie paths replaced by `REDACTED`.

    Idempotent: `REDACTED` contains no `@`, colon-separated userinfo, or path separator, so a
    second pass finds nothing further to mask. That matters because a value may be redacted on
    the way into the database and again on the way into a log.
    """
    text = _COOKIE_FLAG.sub(rf"\1{REDACTED}", text)
    text = _COOKIE_PATH.sub(REDACTED, text)
    return _CREDENTIALS.sub(_mask_credentials, text)


def redact_optional(text: str | None) -> str | None:
    """`redact`, passing `None` through. The form the persistence sink needs."""
    return None if text is None else redact(text)
