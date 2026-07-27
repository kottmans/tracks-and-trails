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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

FIXTURE_DIR: Final = Path(__file__).parent / "infodicts"
ERROR_DIR: Final = Path(__file__).parent / "errors"

#: Keys whose values never enter the repository, whatever they contain.
#:
#: `cookies` and `http_headers` are the two yt-dlp attaches to every format. They carry session
#: identifiers and a fingerprintable user agent, and neither is anything the projection reads.
REDACTED_KEYS: Final = ("cookies", "http_headers", "_cookies", "cookiefile")

#: Query parameters whose *name* suggests a credential. Matched case-insensitively on the name
#: alone: guessing from a value's shape is how a legitimate id gets mangled and a real token
#: gets missed.
TOKEN_PARAMETERS: Final = re.compile(
    r"^(token|access_token|auth|authorization|sig|signature|key|api_key|session|sid|password|"
    r"pwd|secret|expires|policy|credential)$",
    re.IGNORECASE,
)

REDACTED: Final = "<redacted>"


def redact(value: Any) -> Any:
    """Return `value` with credential material replaced, at any depth.

    Recursive because the material is: a playlist's entries each carry their own formats, and
    each format carries its own cookies. A single-level sweep over the top-level dict would
    leave every one of them in place — which is exactly what a committed playlist fixture would
    have shipped.
    """
    if isinstance(value, dict):
        return {
            key: REDACTED if key in REDACTED_KEYS else redact(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_url(value)
    return value


def redact_url(value: str) -> str:
    """Strip token-like query parameters from anything that looks like a URL.

    Left as-is when there is no query string, so ordinary text passes through untouched. The
    parameter is removed rather than blanked: a URL that still carries `?token=` with an empty
    value invites someone to conclude the fixture was captured without one.
    """
    if "?" not in value or "://" not in value:
        return value
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(value)
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not TOKEN_PARAMETERS.match(k)
    ]
    return urlunsplit(parts._replace(query=urlencode(kept)))


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
            "redacted_keys": list(REDACTED_KEYS),
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
                "redacted_keys": list(REDACTED_KEYS),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(Path(__file__).parents[2])} ({path.stat().st_size} bytes)")


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
