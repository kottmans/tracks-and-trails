"""Capture and sanitize a recorded fixture (`T-018`, `ai/TESTING.md` §5).

**Run by hand, never by a test.** It touches the network; the committed JSON is what the suite
reads. Refreshing a fixture is a deliberate act with its own task, and this script exists so
that act is reproducible rather than remembered — the metadata it writes records the yt-dlp
version, the date, the options used, and what was redacted.

    python -m tests.fixtures.capture --list
    python -m tests.fixtures.capture archive_org_art_of_war_playlist

## Why sanitizing happens here rather than at read time

Fixtures are committed, so a leak is permanent (`REQ-026`, `NFR-007`). Redacting on the way in
means the secret never enters the repository; redacting on the way out would mean it was there
all along and merely hidden from one reader. `tests/unit/test_fixtures.py` scans the committed
files and fails on anything that got through, so this script is the mechanism and that test is
the guarantee.

## Sources are chosen to be boring

Every source below is public domain or freely licensed, is served without signed URLs, and has
no reason to change. A fixture that churns teaches nothing about our code when it breaks
(`ai/TESTING.md` §1).
"""

import argparse
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

FIXTURE_DIR: Final = Path(__file__).parent / "infodicts"
ERROR_DIR: Final = Path(__file__).parent / "errors"

#: Keys whose values never enter the repository, whatever they contain.
#:
#: Matched **case-insensitively and by substring** (`T018-R1`): the first version compared four
#: exact spellings, so `Cookie`, `set-cookie` and `authorization` all walked past it. A key whose
#: name mentions a credential is redacted, and a legitimate field that happens to contain one of
#: these words costs nothing to lose — no projection reads any of them.
CREDENTIAL_KEY_MARKERS: Final = (
    "cookie",
    "header",
    "authorization",
    "oauth",
    "bearer",
    "token",
    "secret",
    "password",
    "credential",
    "signature",
    "session",
    "api_key",
    "apikey",
)

#: Markers too short to match as substrings without swallowing innocent words, matched as whole
#: **tokens** instead (`T018-R1`, third pass).
#:
#: `auth` was dropped from the list above because it is a prefix of `author`, and a key named
#: exactly `auth` was then written out intact — the collision was real, and the answer to it was
#: wrong. Splitting a key into tokens distinguishes them properly: `auth`, `X-Auth` and
#: `authToken` match, `author` does not.
CREDENTIAL_KEY_TOKENS: Final = ("auth", "sig", "sid", "pwd")

#: `key` is deliberately absent. It is a whole word in `extractor_key`, which yt-dlp puts on
#: every info dict, so including it redacted real projected data — and a field named exactly
#: `key` carrying a secret is not a shape yt-dlp produces, while `extractor_key` is. `api_key`
#: and `apikey` are covered as substrings above.

_TOKEN_SPLIT: Final = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])")

#: The **only** query parameters allowed to survive into a committed fixture (`T018-R1`).
#:
#: An allowlist, not a blocklist, and that inversion is the finding. The blocklist enumerated
#: parameter names it had thought of, so `X-Amz-Signature`, `X-Amz-Credential` and `X-Amz-Expires`
#: — the standard fields on every signed S3 or CloudFront URL — walked straight through it, as
#: would the next provider's spelling. Nothing in the projection reads a query parameter at all,
#: so the safe default is to keep none: an empty tuple, and a reviewed entry if that ever changes.
#:
#: This is the same move `T-044`, `T-045` and `T-014` each ended at: stop trying to recognise
#: what a secret looks like, and constrain what can be present instead.
ALLOWED_QUERY_PARAMETERS: Final[tuple[str, ...]] = ()

REDACTED: Final = "<redacted>"


def key_tokens(key: object) -> list[str]:
    """A key split into lowercase words, across delimiters and camelCase humps.

    Split first, lowercase second: lowercasing up front erases the hump that separates
    `authToken` into two words, and the token match then misses it.
    """
    return [part.lower() for part in _TOKEN_SPLIT.split(str(key)) if part]


def is_credential_key(key: object) -> bool:
    """Whether a mapping key names something that must never be committed.

    Substring match for the long markers, whole-token match for the short ones — see
    `CREDENTIAL_KEY_TOKENS` for why the distinction has to exist rather than being tidied away.
    """
    if any(marker in str(key).lower() for marker in CREDENTIAL_KEY_MARKERS):
        return True
    return any(token in CREDENTIAL_KEY_TOKENS for token in key_tokens(key))


def redact(value: Any) -> Any:
    """Return `value` with credential material removed, at any depth and in any container.

    **Fails closed** (`T018-R1`). The first version recursed through `dict` and `list` only, so a
    single `tuple` anywhere in the graph carried everything below it through untouched — and
    yt-dlp's info dicts contain tuples. Every container Python's JSON encoder can serialise is
    walked here, and anything this function does not recognise is returned unchanged only if it
    is a scalar, which cannot hide a nested cookie.
    """
    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_credential_key(key) else redact(item) for key, item in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return REDACTED if names_a_user_directory(value) else redact_url(value)
    return value


#: Anything that looks like somebody's home directory, on any drive or share (`T018-R1`).
#:
#: `NFR-007` keeps personal paths out of records that persist, and a fixture persists forever.
#: The first version listed `c:\users` literally, so `D:\Users\...` — an ordinary second drive,
#: or a redirected profile — walked past it. Matched as a *pattern* rather than a prefix list:
#: any drive letter, either slash, and UNC shares, case-insensitively.
USER_DIRECTORY_PATTERN: Final = re.compile(
    r"(?:[a-z]:[\\/]+users[\\/])"  # C:\Users\, d:/users/
    r"|(?:\\\\(?:[^\\/]+[\\/]+)+users[\\/])"  # \\server\Users\ and \\server\share\Users\
    r"|(?:/home/)"
    r"|(?:/users/)",
    re.IGNORECASE,
)


def names_a_user_directory(value: str) -> bool:
    return USER_DIRECTORY_PATTERN.search(value) is not None


def redact_url(value: str) -> str:
    """Strip every query parameter and any userinfo from anything that looks like a URL.

    **Everything goes unless `ALLOWED_QUERY_PARAMETERS` says otherwise** (`T018-R1`). Deciding
    per-parameter meant deciding, in advance, every name a provider might use for a signature —
    and AWS's `X-Amz-*` family was already outside that list. Userinfo (`https://user:pass@host`)
    is dropped for the same reason: it is a credential in a position no allowlist covers.

    Nothing downstream reads a query parameter, so this costs the fixtures nothing.
    """
    if "://" not in value:
        return value
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(value)
    kept = [
        (name, item)
        for name, item in parse_qsl(parts.query, keep_blank_values=True)
        if name.lower() in ALLOWED_QUERY_PARAMETERS
    ]
    netloc = parts.netloc
    if "@" in netloc:
        netloc = netloc.rsplit("@", 1)[1]
    # The fragment goes with the query, and for the same reason (`T018-R1`). OAuth implicit
    # flows put access tokens there — `#access_token=…` — and it is invisible to a check that
    # only knows about `?`. Nothing downstream reads a fragment either.
    return urlunsplit(parts._replace(netloc=netloc, query=urlencode(kept), fragment=""))


def _redaction_record() -> str:
    """What the sanitizer promised this fixture, recorded with it.

    A single sentence, not a nested object: `write()` sanitizes the whole payload, and a
    metadata key called `credential_key_markers` would be redacted by its own policy. Values
    are never key-redacted, so a sentence survives and a structure does not.
    """
    return (
        "fail-closed: values under credential-named keys, every URL query parameter, URL "
        "userinfo, URL fragments and user-directory paths are removed at capture time"
    )


class Source:
    """One fixture: where it came from, how it was extracted, and why it was chosen."""

    def __init__(
        self,
        name: str,
        url: str,
        why: str,
        licence: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.url = url
        self.why = why
        self.licence = licence
        self.options = options or {}


#: The recorded `info_dict` fixtures, and the reason each one exists.
SOURCES: Final[tuple[Source, ...]] = (
    Source(
        name="archive_org_test_mp3",
        url="https://archive.org/details/testmp3testfile",
        why=(
            "An audio-only item: no video stream anywhere in the format list, which is the case "
            "REQ-006's two audio presets are for and the one the video fixture cannot exercise."
        ),
        licence="Public domain test file hosted by the Internet Archive.",
    ),
    Source(
        name="archive_org_art_of_war_playlist",
        url="https://archive.org/details/art_of_war_librivox",
        why=(
            "A real multi-item playlist: `_type: playlist` with seven entries. REQ-002 requires "
            "a probe to say whether a URL is a single item or a playlist, and nothing could "
            "test that against a single-item fixture (T012-R6)."
        ),
        licence="LibriVox recording of a public-domain text; the recordings are public domain.",
        options={"noplaylist": False},
    ),
)

#: Failures worth recording, and the taxonomy kind `ARCHITECTURE.md` §7 says each must become.
#:
#: The expected kind is transcribed from §7 by hand and stored with the capture. It is the
#: specification's answer, not the adapter's — asking the adapter what it does and then checking
#: it does that is the `T010-R1` shape (`ai/TESTING.md` §13).
ERROR_SOURCES: Final[tuple[tuple[str, str, str, str], ...]] = (
    (
        "unsupported_url",
        "https://example.com/",
        "unsupported_url",
        "A URL no extractor claims. yt-dlp raises UnsupportedError, which §7 maps to "
        "UNSUPPORTED_URL — 'no extractor matched' in the taxonomy's own words.",
    ),
    (
        "archive_org_missing_item",
        "https://archive.org/details/definitely-not-a-real-item-xyzzy-9999",
        "extractor_error",
        "An extractor that matched and then failed: HTTP 404 from a real site. §7 maps a "
        "non-retryable HTTP status to EXTRACTOR_ERROR, and the 404 is what makes it one — a "
        "503 from the same site would be NETWORK.",
    ),
)


def capture_info(source: Source, version: str) -> dict[str, Any]:
    from yt_dlp import YoutubeDL

    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noprogress": True,
        **source.options,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(source.url, download=False)

    return {
        "_fixture": {
            "captured": datetime.now(UTC).date().isoformat(),
            "yt_dlp_version": version,
            "source_url": source.url,
            "extractor": "archive.org",
            "capture_method": "recorded",
            # Recorded as text: `YoutubeDL` fills the dict it is handed with its own defaults,
            # including sets, and the point of the record is that a human can reproduce the
            # capture — not that a machine can replay it.
            "capture_options": sorted(f"{key}={value!r}" for key, value in source.options.items()),
            "content_licence": source.licence,
            "why_this_source": source.why,
            "redaction": _redaction_record(),
            "note": (
                "A contract, not a sample (ai/TESTING.md §5). Changing a projected key must fail "
                "the projection test. Refreshing this file is a deliberate act with its own task."
            ),
        },
        "info_dict": redact(dict(info or {})),
    }


def capture_error(
    name: str, url: str, expected_kind: str, why: str, version: str
) -> dict[str, Any]:
    """Record a real failure: its type, where that type lives, and its verbatim message."""
    from yt_dlp import YoutubeDL

    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            ydl.extract_info(url, download=False)
    except BaseException as error:  # the capture is the exception
        cause = adapter.unwrap(error)
        status = getattr(cause, "status", None)
        return {
            "_fixture": {
                "captured": datetime.now(UTC).date().isoformat(),
                "yt_dlp_version": version,
                "source_url": url,
                "capture_method": "recorded",
                "why_this_source": why,
                "redaction": _redaction_record(),
                "note": (
                    "expected_kind is transcribed from ARCHITECTURE.md §7, not read from the "
                    "adapter. The type path is an NFR-008 canary: an upstream rename fails the "
                    "test that imports it."
                ),
            },
            "error": {
                "module": type(cause).__module__,
                "type": type(cause).__name__,
                "http_status": int(status) if isinstance(status, int) else None,
                "message": redact_url(adapter.extractor_message(error)),
                "expected_kind": expected_kind,
            },
        }
    raise SystemExit(f"{url} did not fail; there is nothing to record")


def write(path: Path, payload: dict[str, Any]) -> None:
    """Sanitize the **whole** payload, then write it.

    Every capture goes through here, so sanitizing at this point is what makes "no field was
    forgotten" true by construction rather than by review (`T018-R1`). The first version
    sanitized `info_dict` and left the metadata alone, and `source_url` is captured data: a
    hostile URL was written into the provenance block verbatim, complete with its userinfo and
    its signature.

    The redaction record is a single sentence rather than a nested object precisely because this
    runs over it too — a metadata key named `credential_key_markers` would redact *itself*.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    root = Path(__file__).parents[2]
    shown = path.relative_to(root) if path.is_relative_to(root) else path
    print(f"wrote {shown} ({path.stat().st_size} bytes)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", help="fixtures to capture; default all")
    parser.add_argument("--list", action="store_true", help="list what can be captured")
    args = parser.parse_args(argv)

    known = [source.name for source in SOURCES] + [name for name, *_ in ERROR_SOURCES]
    if args.list:
        print("\n".join(known))
        return 0

    import yt_dlp

    version = str(yt_dlp.version.__version__)
    wanted = set(args.names or known)

    for source in SOURCES:
        if source.name in wanted:
            write(FIXTURE_DIR / f"{source.name}.json", capture_info(source, version))
    for name, url, kind, why in ERROR_SOURCES:
        if name in wanted:
            write(ERROR_DIR / f"{name}.json", capture_error(name, url, kind, why, version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
