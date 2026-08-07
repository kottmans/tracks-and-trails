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

#: The `info_dict` keys whose **values** may be committed: exactly the ones
#: `downloader/ytdlp_adapter.py` reads (`T018-R1`, structural).
#:
#: Transcribed by hand from that module; `tests/unit/test_fixtures.py` derives the same set from
#: its AST and fails if the two disagree — transcribe one side, derive the other
#: (`ai/TESTING.md` §13).
#:
#: **This replaces four rounds of guessing what a secret looks like.** Marker lists failed by
#: enumeration every time: `cookies`, then tuple containers, then capture metadata and non-`C:`
#: profiles, then `auth`, then `passwd`, `passphrase`, `private_key`, `accessKey`. Each fix was
#: correct and the next spelling still walked through. An allowlist inverts the question — a
#: credential can only be committed if the projection reads a field by that name, and it does
#: not — so a new spelling is irrelevant by construction rather than by vigilance.
#:
#: It is the **only** control, deliberately. A fifth round found the secondary shape record
#: writing captured mapping *keys* verbatim, which is captured data; `SEC-002` was amended to
#: drop it rather than sanitize it, because "everything except the allowlist, but safely" is the
#: same bet that lost four times.
CONSUMED_TOP_LEVEL: Final = (
    "_has_drm",
    "_type",
    "duration",
    "entries",
    "formats",
    "is_live",
    "original_url",
    "playlist_count",
    "thumbnail",
    "title",
    "uploader",
    "url",
    "webpage_url",
)

#: A set view of the above, for callers that ask "may this key carry a value?".
CONSUMED_TOP_LEVEL_SET: Final = frozenset(CONSUMED_TOP_LEVEL)

#: The same, for each entry of `formats`.
CONSUMED_FORMAT: Final = (
    "acodec",
    "ext",
    "filesize",
    "filesize_approx",
    "format_id",
    "format_note",
    "fps",
    "has_drm",
    "height",
    "tbr",
    "vcodec",
    "width",
)

#: Provenance fields a fixture may carry, and nothing else. Reviewed one by one, because this
#: block is written here rather than captured — except `source_url`, which is supplied by
#: whoever asks for a capture and is therefore sanitized like any other captured value.
ALLOWED_FIXTURE_FIELDS: Final = (
    "captured",
    "capture_method",
    "capture_options",
    "content_licence",
    "derived_from",
    "extractor",
    "note",
    "policy",
    "source_url",
    "what_is_synthetic",
    "why_this_source",
    "yt_dlp_version",
)

#: Fields a recorded *failure* may carry.
ALLOWED_ERROR_FIELDS: Final = (
    "expected_kind",
    "http_status",
    "message",
    "module",
    "type",
)

#: The **only** query parameters allowed to survive into a committed fixture.
#:
#: Empty, and an allowlist rather than a blocklist: nothing downstream reads a query parameter,
#: so the safe default is to keep none. A consumed field can still be a URL — `webpage_url` and
#: `thumbnail` both are — so this still matters after the key allowlist above.
ALLOWED_QUERY_PARAMETERS: Final[tuple[str, ...]] = ()

REDACTED: Final = "<redacted>"

#: Anything that looks like somebody's home directory, on any drive or share.
#:
#: Still needed after the allowlist: a *consumed* field can carry one. `NFR-007` keeps personal
#: paths out of records that persist, and a fixture persists forever.
USER_DIRECTORY_PATTERN: Final = re.compile(
    r"(?:[a-z]:[\\/]+users[\\/])"
    r"|(?:\\\\(?:[^\\/]+[\\/]+)+users[\\/])"
    r"|(?:/home/)"
    r"|(?:/users/)",
    re.IGNORECASE,
)


def names_a_user_directory(value: str) -> bool:
    return USER_DIRECTORY_PATTERN.search(value) is not None


def clean_scalar(value: Any) -> Any:
    """Sanitize one value that *is* allowed through: URLs lose their credentials, paths go."""
    if isinstance(value, str):
        return REDACTED if names_a_user_directory(value) else redact_url(value)
    return value


def redact_url(value: str) -> str:
    """Strip every query parameter, any userinfo and any fragment from a URL.

    Deciding per-parameter meant deciding, in advance, every name a provider might use for a
    signature, and AWS's `X-Amz-*` family was already outside that list. Userinfo and fragments
    go for the same reason: both are credential positions no parameter list covers.
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
    return urlunsplit(parts._replace(netloc=netloc, query=urlencode(kept), fragment=""))


#: What a playlist entry carries (`T-137`). **This used to be `{}`**, on the recorded premise that
#: "the projection reads `len(entries)` and nothing else" — true until `T-137` made a playlist
#: expand into one job per entry, which needs each entry's address and name.
#:
#: **Ruled by the maintainer 2026-08-04, recorded as `SEC-002`'s amendment.** This records
#: more than it did, so it is
#: worth being exact about *what*: these are the same four facts the fixture already keeps about
#: the top-level item — where it is, what it is called, how long, and its picture. Nothing new in
#: kind is retained; what changed is that a playlist's items now get the same treatment as the
#: playlist. The rule the allowlist has always followed is unchanged: a field is kept if and only
#: if `ytdlp_adapter` reads it, and `test_the_allowlist_matches_what_the_adapter_actually_reads`
#: derives that from the source rather than trusting this list.
CONSUMED_ENTRY: Final[tuple[str, ...]] = (
    "url",
    "webpage_url",
    "original_url",
    "title",
    "duration",
    "thumbnail",
)


def keep_consumed(info: Mapping[str, Any]) -> dict[str, Any]:
    """The projection's own view of an info dict: allowed keys only, values cleaned.

    Everything else is **dropped, not redacted**. A dropped key cannot leak whatever it held,
    and cannot become a leak later when somebody adds a field to yt-dlp with a name nobody has
    thought of yet. Nothing is kept about it — see `SEC-002`, amended: the shape record that
    used to stand in for the discarded data was itself able to carry it, because a mapping *key*
    is captured data too.
    """
    kept: dict[str, Any] = {}
    for key in CONSUMED_TOP_LEVEL:
        if key not in info:
            continue
        value = info[key]
        if key == "formats" and isinstance(value, list | tuple):
            kept[key] = [_keep_format(entry) for entry in value]
        elif key == "entries" and isinstance(value, list | tuple):
            # **Content now, because there is a reader** (`T-137`). This kept cardinality only,
            # and said why: `T018-R1` found each entry's title and uploader retained for nothing.
            # The rule was never "entries are special" — it was "kept only if read" — and a
            # playlist that expands into jobs reads four fields per entry. Everything else about
            # an entry is still dropped, by the same allowlist mechanism as everywhere else.
            kept[key] = [_keep_entry(item) for item in value]
        else:
            kept[key] = clean_scalar(value)
    return kept


def _keep_format(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, Mapping):
        return {}
    return {key: clean_scalar(entry[key]) for key in CONSUMED_FORMAT if key in entry}


def _keep_entry(item: Any) -> dict[str, Any]:
    """One playlist entry, allowlisted (`T-137`). Same shape and rule as `_keep_format`."""
    if not isinstance(item, Mapping):
        return {}
    return {key: clean_scalar(item[key]) for key in CONSUMED_ENTRY if key in item}


def _policy_record() -> str:
    """What the fixture writer promised, recorded beside the fixture.

    A sentence rather than a structure: it describes a rule that no longer depends on
    recognising anything, so there is no marker list to reproduce here.
    """
    return (
        "allowlist: only fields ytdlp_adapter reads carry values, and playlist entries are "
        "counted rather than recorded; every other key is dropped and nothing about it is kept. "
        "URLs lose query, userinfo and fragment; user-directory paths are removed"
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
        name="archive_org_big_buck_bunny",
        url="https://archive.org/details/BigBuckBunny_124",
        why=(
            "The original fixture, captured by T-012 and re-captured here because T018-R1's "
            "allowlist changed what a fixture may contain. Refreshing is meant to be deliberate; "
            "this one was forced by the policy, which is recorded rather than quietly done."
        ),
        licence="Big Buck Bunny (c) Blender Foundation, CC BY 3.0. Media URLs are unsigned.",
    ),
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
        name="wikimedia_caminandes",
        url="https://commons.wikimedia.org/wiki/File:Caminandes-_Llama_Drama_-_Short_Movie.ogv",
        why=(
            "The only recorded source that populates the codec and bitrate columns REQ-003 names "
            "(T107-R1). archive.org's derivatives report `unknown` for both, which `yt-dlp -F` "
            "confirms, so the columns could only ever be exercised against synthetic values. "
            "Wikimedia reports vcodec, acodec and tbr per format, and its sizes are "
            "`filesize_approx` - which exercises T107-R7's estimate rendering from a real capture "
            "as well. It also has no fps for any format; no boring, freely licensed source found "
            "does, which is recorded in T-185 rather than worked around."
        ),
        licence=(
            "Caminandes: Llama Drama (c) Blender Foundation, CC BY 3.0. Hosted by Wikimedia "
            "Commons; media URLs are unsigned."
        ),
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
            "policy": _policy_record(),
            "note": (
                "A contract, not a sample (ai/TESTING.md §5). Changing a projected key must fail "
                "the projection test. Refreshing this file is a deliberate act with its own task."
            ),
        },
        "info_dict": keep_consumed(dict(info or {})),
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
    """Enforce the allowlists, then write.

    Every capture goes through here, so this is where "no field was forgotten" becomes true by
    construction rather than by review (`T018-R1`). Anything outside the allowlists is dropped
    — including from the provenance block, whose `source_url` is captured data like any other.

    **Nothing in `payload` is trusted, and nothing outside the three known blocks is carried.**
    The removed `_schema` was accepted from the caller when one was supplied, which meant the
    door had a hole in it beside the lock: whatever a caller had already computed went to disk
    unexamined. Every field written below is derived here, from this function.
    """
    fixture = {
        key: clean_scalar(value)
        for key, value in (payload.get("_fixture") or {}).items()
        if key in ALLOWED_FIXTURE_FIELDS
    }
    written: dict[str, Any] = {"_fixture": fixture}
    if "info_dict" in payload:
        written["info_dict"] = keep_consumed(payload["info_dict"])
    if "error" in payload:
        written["error"] = {
            key: clean_scalar(value)
            for key, value in payload["error"].items()
            if key in ALLOWED_ERROR_FIELDS
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(written, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
