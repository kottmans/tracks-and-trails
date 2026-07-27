"""The recorded fixtures, as contracts rather than samples (`T-018`, `ai/TESTING.md` §5).

A fixture earns its maintenance cost only if changing it breaks something. So this file asks
four questions of the committed files, and none of them is "does it parse":

1. **Can it be trusted?** Every fixture records the yt-dlp version and date it was taken, and
   whether it was *recorded* or *derived*. A file that cannot say where it came from cannot
   distinguish an upstream change from our own bug, which is most of what a fixture is for.
2. **Is it safe?** They are committed, so a leaked cookie or token is permanent (`REQ-026`,
   `NFR-007`). The scan below is the guarantee; sanitizing at capture time is only the
   mechanism, and review discipline is neither.
3. **Do they cover what `T-018` requires?** Asked of the *contents* — a normal video, an
   audio-only item, a playlist, DRM, an unsupported URL, an extractor error — not of filenames,
   which can be renamed into or out of compliance without anything changing.
4. **Does the projection still read them the same way?** Field by field, so a failure names the
   field that moved instead of reporting that two large objects differ.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import MediaInfo
from tracks_and_trails.downloader import ytdlp_adapter as adapter

FIXTURES = Path(__file__).parents[1] / "fixtures"
INFODICTS = FIXTURES / "infodicts"
ERRORS = FIXTURES / "errors"


def load(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def info_fixtures() -> list[Path]:
    return sorted(INFODICTS.glob("*.json"))


def error_fixtures() -> list[Path]:
    return sorted(ERRORS.glob("*.json"))


def all_fixtures() -> list[Path]:
    return info_fixtures() + error_fixtures()


def fixture_id(path: Path) -> str:
    return path.stem


def test_the_fixture_directories_are_not_empty() -> None:
    """Every parametrised test below would pass over nothing if a glob stopped matching."""
    assert len(info_fixtures()) >= 4, info_fixtures()
    assert len(error_fixtures()) >= 2, error_fixtures()


# --- 1. provenance ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_every_fixture_records_where_it_came_from(path: Path) -> None:
    """`ai/TESTING.md` §5: the yt-dlp version and the capture date, on every fixture.

    Machine-checked because it is checkable. *Why* a fixture changed is a review convention in
    §5 and deliberately not asserted here — a test cannot read an explanation, and pretending
    otherwise would put a human obligation behind a green tick.
    """
    meta = load(path).get("_fixture")
    assert meta is not None, f"{path.name} has no _fixture block"
    assert meta.get("yt_dlp_version"), "no yt-dlp version: an upstream change cannot be dated"
    assert meta.get("captured"), "no capture date"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta["captured"])), meta["captured"]


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_a_fixture_says_whether_it_was_recorded_or_constructed(path: Path) -> None:
    """The distinction that keeps the set honest.

    `derived_drm_protected` is not a recording and must not read like one: capturing a real
    DRM-protected item means probing a DRM service, which `REQ-EXCL-001` and `SEC-001` put out
    of scope. A derived fixture is legitimate — a constructed one that *claims* to be a capture
    is not, because the next person reads its shape as evidence of what a site really sends.
    """
    meta = load(path)["_fixture"]
    method = meta.get("capture_method")
    assert method in {"recorded", "derived"}, f"{path.name}: capture_method={method!r}"
    if method == "recorded":
        assert meta.get("source_url"), "a recording must say what it recorded"
    else:
        assert meta.get("what_is_synthetic"), "a derived fixture must say which parts are made up"
        assert meta.get("derived_from"), "a derived fixture must say what it was derived from"


# --- 2. sanitization (REQ-026, NFR-007) ------------------------------------------------------

#: What must never appear in a committed fixture. Each is a literal that shows up in real
#: yt-dlp output: session cookies, the browser identity yt-dlp sends, bearer tokens, and local
#: paths. Written out rather than derived from the sanitizer, so weakening the sanitizer does
#: not weaken the check on its results (`ai/TESTING.md` §13).
FORBIDDEN_SUBSTRINGS = (
    "Set-Cookie",
    "set-cookie",
    "Bearer ",
    "csrf",
    "session-id",
    "donation-identifier",
    "Mozilla/",
)

#: A path inside somebody's home directory, on **any** drive or share (`T018-R1`).
#:
#: The first version listed `C:\Users` and its JSON-escaped twin, so `D:\Users\...` produced no
#: finding at all — and a second drive or a redirected profile is entirely ordinary. Written as a
#: pattern over one or two backslashes, because the scan reads the file as *text* and JSON
#: escapes every backslash it contains.
_USER_DIRECTORY = re.compile(
    r"(?:[A-Za-z]:(?:\\{1,2}|/)+users(?:\\{1,2}|/))"
    r"|(?:\\{2,4}[^\\/\s\"']+(?:\\{1,2}|/)+[^\\/\s\"']+(?:\\{1,2}|/)+users(?:\\{1,2}|/))"
    r"|(?:/home/)"
    r"|(?:/Users/)",
    re.IGNORECASE,
)

#: Query parameters a committed fixture may carry. **None** (`T018-R1`).
#:
#: This is the gate's half of the same inversion the sanitizer made, arrived at independently:
#: the previous version listed the parameter names it considered dangerous, so an AWS-style
#: `X-Amz-Signature` was not merely missed — it was outside the question being asked. Since no
#: projection reads a query parameter, any parameter at all in a committed fixture is either a
#: credential or unnecessary, and both are reasons to fail.
#:
#: Deliberately **not** imported from `capture.py`. The sanitizer and this gate are supposed to
#: agree, and a shared constant would make disagreement invisible — which is the entire value of
#: having a second check at all.
ALLOWED_QUERY_PARAMETERS: frozenset[str] = frozenset()

#: A URL query **or fragment** parameter, as it appears inside JSON.
#:
#: `#` is included because a fragment is where an OAuth implicit flow puts an access token
#: (`T018-R1`), and a check that only knew about `?` reported a fixture carrying
#: `#access_token=…` as clean.
_QUERY_PARAMETER = re.compile(r"[?&#]([A-Za-z0-9_.\-%]+)=")

#: `scheme://user:password@host` — a credential in a position no parameter list covers.
_URL_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^/\s\"']*@")


def leaks_in(blob: str) -> list[str]:
    """Every credential-shaped thing in `blob`. The scanner both tests use.

    Fails closed on two of its three checks (`T018-R1`): any query parameter outside the
    allowlist counts, and so does any URL carrying userinfo. Only the literal list above
    enumerates, and it enumerates things that are *always* wrong rather than trying to be a
    complete catalogue of what a secret looks like.
    """
    found = [needle for needle in FORBIDDEN_SUBSTRINGS if needle in blob]
    found += [f"user directory in {match.group(0)!r}" for match in _USER_DIRECTORY.finditer(blob)]
    found += [
        f"query parameter {match.group(1)!r}"
        for match in _QUERY_PARAMETER.finditer(blob)
        if match.group(1).lower() not in ALLOWED_QUERY_PARAMETERS
    ]
    found += [f"url userinfo in {match.group(0)!r}" for match in _URL_USERINFO.finditer(blob)]
    return found


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_no_fixture_carries_credential_material(path: Path) -> None:
    """The acceptance criterion, asserted over the file as text.

    Over the raw text rather than the parsed object on purpose: a leak nested inside a
    playlist's entries' formats — which is exactly where the real one was — is invisible to a
    check that looks at top-level keys.
    """
    leaks = leaks_in(path.read_text(encoding="utf-8"))
    assert not leaks, f"{path.name} carries {leaks}. Fixtures are committed; a leak is permanent."


@pytest.mark.parametrize("path", info_fixtures(), ids=fixture_id)
def test_the_redacted_keys_are_actually_redacted(path: Path) -> None:
    """`cookies` and `http_headers` must hold the marker, not merely be absent.

    An absent key and a redacted one look the same to the scan above, and only one of them
    proves the sanitizer ran.
    """
    payload = load(path)
    redacted: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"cookies", "http_headers"}:
                    assert item == "<redacted>", f"{path.name}: {key} = {item!r}"
                    redacted.append(key)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload["info_dict"])
    assert redacted, f"{path.name} has no cookies or headers at all; the sanitizer is untested"


#: Leak shapes the gate must reject. Each is a real thing a capture can contain, and the last
#: four are `T018-R1`'s: the parameter names a blocklist had never heard of, a percent-encoded
#: spelling of one it had, and a credential in the URL's authority rather than its query.
LEAK_SHAPES = {
    "cookie value": '{"cookies": "ia-csrf=abc; Domain=.archive.org"}',
    "browser identity": '{"http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"}}',
    "bearer token": '{"authorization": "Bearer eyJhbGciOi"}',
    "linux path": '{"cookiefile": "/home/sean/.config/cookies.txt"}',
    "windows path": '{"path": "C:\\\\Users\\\\sean\\\\cookies.txt"}',
    "named signature": '{"url": "https://cdn.example/v.mp4?signature=deadbeef&expires=1"}',
    "aws signed url": (
        '{"url": "https://s3.example/v.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256'
        '&X-Amz-Credential=AKIA%2F20260727&X-Amz-Signature=abc123&X-Amz-Expires=3600"}'
    ),
    "cloudfront signed url": (
        '{"url": "https://d1.cloudfront.net/v.mp4?Policy=eyJTdGF0ZW1l&Key-Pair-Id=APKA"}'
    ),
    "percent-encoded name": '{"url": "https://cdn.example/v.mp4?%73ignature=deadbeef"}',
    "url userinfo": '{"url": "https://someone:hunter2@cdn.example/v.mp4"}',
    "unfamiliar provider name": '{"url": "https://cdn.example/v.mp4?hdnts=exp=1~hmac=9f"}',
    # `T018-R1`, second pass. Each of these produced no finding at all: a home directory is not
    # confined to `C:`, and a fragment is where an OAuth implicit flow leaves an access token.
    "second drive profile": '{"cookiefile": "D:\\\\Users\\\\Sean\\\\cookies.txt"}',
    "unc share profile": '{"cookiefile": "\\\\\\\\nas\\\\home\\\\Users\\\\Sean\\\\c.txt"}',
    "lowercase drive profile": '{"cookiefile": "d:/users/sean/cookies.txt"}',
    "fragment token": '{"url": "https://example.invalid/video#access_token=secret"}',
    "fragment token after query": '{"url": "https://example.invalid/v?a=1#id_token=secret"}',
}


@pytest.mark.parametrize("shape", sorted(LEAK_SHAPES))
def test_the_leak_scanner_can_actually_fail(shape: str) -> None:
    """`ai/TESTING.md` §13: a scan nobody has watched reject something is not evidence.

    Parametrized rather than looped so a shape that stops being caught names itself. The four
    `T018-R1` rows are the point: the previous scanner asked "is this one of the parameter names
    I know?", which no amount of adding names fixes. This one asks "is any parameter present?",
    and the answer for a fixture is always no.
    """
    assert leaks_in(LEAK_SHAPES[shape]), f"the scanner would have let a {shape} through"


@pytest.mark.parametrize(
    ("shape", "payload"),
    [
        ("tuple", ({"cookies": "SID=secret"},)),
        ("tuple inside a list", [({"cookies": "SID=secret"},)]),
        ("tuple inside a dict", {"formats": ({"cookies": "SID=secret"},)}),
        ("set of urls", {"seen": {"https://cdn.example/v.mp4?X-Amz-Signature=abc"}}),
        ("nested three deep", {"a": [{"b": ({"http_headers": {"Cookie": "SID=x"}},)}]}),
    ],
)
def test_the_sanitizer_walks_every_container_not_just_two(shape: str, payload: Any) -> None:
    """`T018-R1`'s core: `redact()` recursed through `dict` and `list` only.

    A single tuple anywhere in the graph carried everything beneath it through untouched, and
    yt-dlp's info dicts contain tuples — `_format_sort_fields` is one. This is asserted on
    Python objects rather than on JSON text because a tuple cannot be written in JSON: the
    committed-file scanner is structurally unable to see this class, which is exactly why the
    sanitizer has to fail closed rather than be checked afterwards.
    """
    from tests.fixtures import capture

    serialized = json.dumps(capture.redact(payload))

    assert "secret" not in serialized, f"a {shape} carried a cookie through: {serialized}"
    assert "SID=" not in serialized
    assert not leaks_in(serialized), f"a {shape} carried {leaks_in(serialized)}"


def test_what_a_capture_writes_is_sanitized_including_its_own_metadata(tmp_path: Path) -> None:
    """`T018-R1`, second pass: the provenance block is captured data too.

    `source_url` comes from whoever asked for the capture, and it was written into the metadata
    raw — so a URL carrying userinfo and a signature was recorded verbatim beside an
    `info_dict` that had been carefully cleaned. Asserted at `write()`, which every capture goes
    through, because sanitizing per-field is exactly the arrangement that forgot a field.
    """
    from tests.fixtures import capture

    hostile = "https://someone:hunter2@cdn.example/v.mp4?X-Amz-Signature=secret#access_token=t"
    payload = {
        "_fixture": {
            "captured": "2026-07-27",
            "yt_dlp_version": "0.0.0",
            "source_url": hostile,
            "capture_method": "recorded",
            "redaction": "irrelevant",
            "note": r"taken from D:\Users\Sean\downloads",
        },
        "info_dict": {"webpage_url": hostile, "cookies": "SID=secret"},
    }
    written = tmp_path / "hostile.json"

    capture.write(written, payload)
    blob = written.read_text(encoding="utf-8")

    assert not leaks_in(blob), f"the capture wrote {leaks_in(blob)}"
    assert "hunter2" not in blob and "secret" not in blob
    assert "cdn.example" in blob, "the URL should be cleaned, not deleted"


def test_the_redaction_record_survives_its_own_policy(tmp_path: Path) -> None:
    """The provenance note must still be readable after the sanitizer has been over it.

    `write()` now sanitizes everything, so a record that described the policy in keys named
    after credentials would redact itself and leave the fixture claiming nothing.
    """
    from tests.fixtures import capture

    written = tmp_path / "record.json"
    capture.write(
        written,
        {"_fixture": {"redaction": capture._redaction_record()}, "info_dict": {}},
    )

    record = json.loads(written.read_text(encoding="utf-8"))["_fixture"]["redaction"]
    assert "fail-closed" in record, f"the redaction record was itself redacted: {record!r}"


def test_the_scanner_and_the_sanitizer_agree_without_sharing_a_list() -> None:
    """The two halves are written separately on purpose; this is where they must meet.

    Every leak shape above is put through `capture.redact()` and then re-scanned. A sanitizer
    that misses what the gate catches would let a refresh write a fixture that cannot be
    committed; a gate that misses what the sanitizer strips would stop noticing regressions.
    """
    from tests.fixtures import capture

    for shape, blob in LEAK_SHAPES.items():
        sanitized = json.dumps(capture.redact(json.loads(blob)))
        assert not leaks_in(sanitized), (
            f"the sanitizer left a {shape} that the gate rejects: {sanitized}"
        )


# --- 3. coverage, asked of the contents ------------------------------------------------------
#
# `T-018`, transcribed: "Fixtures cover at minimum: a normal video, an audio-only case, a
# playlist, DRM_PROTECTED, UNSUPPORTED_URL, and EXTRACTOR_ERROR." Each case below is that
# sentence turned into a question about what a fixture *contains*.


def _is_normal_video(info: dict[str, Any]) -> bool:
    media = adapter.project_media(info)
    return (
        not media.is_playlist
        and not adapter.has_drm(info)
        and any(fmt.video_codec is not None or (fmt.height or 0) > 0 for fmt in media.formats)
    )


def _is_audio_only(info: dict[str, Any]) -> bool:
    media = adapter.project_media(info)
    if media.is_playlist or not media.formats:
        return False
    return all(fmt.video_codec is None and not fmt.height for fmt in media.formats)


def _is_playlist(info: dict[str, Any]) -> bool:
    return adapter.project_media(info).is_playlist


def _is_drm(info: dict[str, Any]) -> bool:
    return adapter.has_drm(info)


INFO_CASES = {
    "a normal video": _is_normal_video,
    "an audio-only item": _is_audio_only,
    "a playlist": _is_playlist,
    "DRM_PROTECTED": _is_drm,
}

ERROR_CASES = {
    "UNSUPPORTED_URL": ErrorKind.UNSUPPORTED_URL,
    "EXTRACTOR_ERROR": ErrorKind.EXTRACTOR_ERROR,
}


@pytest.mark.parametrize("case", sorted(INFO_CASES))
def test_the_required_info_dict_cases_are_covered(case: str) -> None:
    covered = [path.stem for path in info_fixtures() if INFO_CASES[case](load(path)["info_dict"])]
    assert covered, f"no committed fixture is {case}"


@pytest.mark.parametrize("case", sorted(ERROR_CASES))
def test_the_required_error_cases_are_covered(case: str) -> None:
    kinds = {load(path)["error"]["expected_kind"] for path in error_fixtures()}
    assert ERROR_CASES[case].value in kinds, f"no recorded failure classifies as {case}"


# --- 4. the projection contract --------------------------------------------------------------

#: `MediaInfo` field → the `info_dict` key it is projected from, and the value it must take when
#: that key is absent. Transcribed from `project_media`'s contract in `ARCHITECTURE.md` §5, by
#: hand: reading the mapping out of the adapter would make this a mirror (`ai/TESTING.md` §13).
#:
#: `title`, `url` and `formats` are absent from the table because each has a documented fallback
#: chain of its own, tested in `tests/unit/test_ytdlp_adapter.py`.
PROJECTED_FIELDS: dict[str, tuple[str, Any]] = {
    "uploader": ("uploader", None),
    "thumbnail_url": ("thumbnail", None),
    "is_live": ("is_live", False),
}


@pytest.mark.parametrize("path", info_fixtures(), ids=fixture_id)
@pytest.mark.parametrize("field_name", sorted(PROJECTED_FIELDS))
def test_each_projected_field_still_reads_the_key_it_is_supposed_to(
    path: Path, field_name: str
) -> None:
    """One field, one fixture, one assertion — so a failure names what moved.

    The criterion `T-018` states: when a fixture changes shape the test must say *which* field,
    not that two objects are unequal. Comparing whole `MediaInfo` objects would satisfy the
    letter of "the test fails" and be useless at three in the morning.
    """
    info = load(path)["info_dict"]
    key, absent_default = PROJECTED_FIELDS[field_name]
    media = adapter.project_media(info)
    projected = getattr(media, field_name)

    if key not in info or info[key] in (None, ""):
        assert projected == absent_default, (
            f"{path.stem}: {field_name} is {projected!r}, but the fixture has no {key!r} and the "
            f"documented default is {absent_default!r}"
        )
    elif field_name == "is_live":
        assert projected is bool(info[key])
    else:
        assert projected == info[key], (
            f"{path.stem}: {field_name} projected {projected!r} from {key}={info[key]!r}"
        )


@pytest.mark.parametrize("path", info_fixtures(), ids=fixture_id)
def test_every_fixture_projects_into_declared_types_all_the_way_down(path: Path) -> None:
    """`ARC-002` over the whole set, not just the one fixture `T-012` had."""
    media = adapter.project_media(load(path)["info_dict"])

    assert isinstance(media, MediaInfo)
    assert isinstance(media.formats, tuple)
    assert not any(isinstance(fmt, dict) for fmt in media.formats)


@pytest.mark.parametrize("key", ["title", "duration", "uploader", "formats", "thumbnail"])
@pytest.mark.parametrize("path", info_fixtures(), ids=fixture_id)
def test_removing_a_projected_key_changes_the_projection(path: Path, key: str) -> None:
    """The contract property, over every fixture: a lost key must not project the same.

    A fixture that does not carry the key is skipped rather than asserted, because "removing an
    absent key changes nothing" is true of every implementation and would be a passing test that
    checks nothing.
    """
    info = load(path)["info_dict"]
    if key not in info or info[key] in (None, "", []):
        pytest.skip(f"{path.stem} carries no {key}")

    baseline = adapter.project_media(info)
    reduced = {name: value for name, value in info.items() if name != key}
    assert adapter.project_media(reduced) != baseline, (
        f"{path.stem}: dropping {key!r} left the projection identical, so nothing reads it"
    )


# --- the playlist projection (T012-R6, REQ-002) ----------------------------------------------


def test_the_playlist_fixture_projects_as_a_playlist_with_its_count() -> None:
    """`REQ-002`: a probe must say whether the URL is a single item or a playlist.

    Read from `_type`, which is yt-dlp's structured answer, and counted from `playlist_count`,
    which is the site's. Both values come from the fixture rather than being written here, so
    this cannot pass against a projection that returns a constant.
    """
    info = load(INFODICTS / "archive_org_art_of_war_playlist.json")["info_dict"]
    media = adapter.project_media(info)

    assert media.is_playlist is True
    assert media.entry_count == info["playlist_count"]
    assert media.entry_count == len(info["entries"]), (
        "this fixture holds every entry, so the two counts must agree; if they stop agreeing "
        "the fixture was trimmed and the preference for playlist_count needs its own test"
    )
    assert media.title == info["title"]


@pytest.mark.parametrize(
    "path", [p for p in info_fixtures() if "playlist" not in p.stem], ids=fixture_id
)
def test_a_single_item_is_not_reported_as_a_playlist(path: Path) -> None:
    """The other half. A projection that answered "playlist" for everything would pass above."""
    media = adapter.project_media(load(path)["info_dict"])

    assert media.is_playlist is False
    assert media.entry_count is None, "a single item has no entries to count"


#: yt-dlp's declared multi-item result types, transcribed from its extractor documentation
#: rather than imported from the adapter (`ai/TESTING.md` §13). Asking the module which types it
#: handles and then checking it handles them is the `T010-R1` shape.
YT_DLP_MULTI_ITEM_TYPES = ("playlist", "multi_video")


@pytest.mark.parametrize("declared_type", YT_DLP_MULTI_ITEM_TYPES)
def test_every_multi_item_type_yt_dlp_declares_is_projected_as_one(declared_type: str) -> None:
    """`T018-R2`: `multi_video` is a multi-item result, and reading only `playlist` missed it.

    yt-dlp's own contract names both, and `playlist_result(multi_video=True)` produces the
    second for parts of one work — a film split across files. `REQ-002` asks a binary question,
    so both answer it the same way; the distinction between them is yt-dlp's business.
    """
    info = {
        "_type": declared_type,
        "title": "A work in parts",
        "webpage_url": "https://example.com/p",
        "entries": [{"id": "1"}, {"id": "2"}],
        "playlist_count": 2,
    }
    media = adapter.project_media(info)

    assert media.is_playlist is True, f"{declared_type!r} was projected as a single item"
    assert media.entry_count == 2


def test_a_single_video_type_is_still_a_single_item() -> None:
    """The other side: widening the set must not swallow the type it exists to distinguish."""
    info = {"_type": "video", "title": "One thing", "webpage_url": "https://example.com/v"}
    assert adapter.project_media(info).is_playlist is False


@pytest.mark.parametrize(
    "entries",
    ["two", b"two", iter([{"id": "1"}, {"id": "2"}])],
    ids=["str", "bytes", "generator"],
)
def test_an_entries_value_that_is_not_a_list_is_not_counted(entries: object) -> None:
    """`T018-R2`'s sibling: `str` and `bytes` are `Sequence`s.

    A malformed `entries` of `"two"` was counted as three — its number of characters — and
    reported as a playlist of three items. A generator, which a lazily paginated playlist
    supplies, has no length and must not be consumed here: doing so would fetch the whole
    playlist during a probe.
    """
    info = {
        "_type": "playlist",
        "title": "P",
        "webpage_url": "https://example.com/p",
        "entries": entries,
    }
    media = adapter.project_media(info)

    assert media.is_playlist is True
    assert media.entry_count is None, f"{type(entries).__name__} was counted as {media.entry_count}"


def test_the_count_prefers_what_the_site_reported_over_what_was_materialised() -> None:
    """`playlist_count` and `len(entries)` are different facts, and the difference matters.

    Flat extraction, a page limit or a lazy generator can all make `entries` shorter than the
    playlist. Reporting the short number as the total understates the playlist silently, which
    is the failure mode this project keeps finding: a value computed from the wrong source and
    then displayed as fact.
    """
    partial = {"_type": "playlist", "title": "Long", "webpage_url": "https://e.com/p"}
    assert (
        adapter.project_media({**partial, "playlist_count": 500, "entries": [{}, {}]}).entry_count
        == 500
    )
    assert adapter.project_media({**partial, "entries": [{}, {}, {}]}).entry_count == 3
    assert adapter.project_media(partial).entry_count is None, (
        "a playlist whose size nobody reported must say unknown, not zero"
    )


# --- recorded failures (ARCHITECTURE.md §7, NFR-008) -----------------------------------------


@pytest.mark.parametrize("path", error_fixtures(), ids=fixture_id)
def test_a_recorded_failure_still_classifies_the_way_the_taxonomy_says(path: Path) -> None:
    """The recorded exception type is rebuilt and put through `classify_exception`.

    Two things fail here, and both matter. The import fails if yt-dlp renames or moves the type,
    which is the `NFR-008` canary — upstream churn confined to two modules is only true if
    something notices when it happens. And the classification fails if the taxonomy mapping
    drifts from `ARCHITECTURE.md` §7, whose answer is recorded in the fixture by hand rather
    than read back from the adapter.
    """
    import importlib

    recorded = load(path)["error"]
    module = importlib.import_module(recorded["module"])
    exception_type = getattr(module, recorded["type"], None)
    assert exception_type is not None, (
        f"{recorded['module']}.{recorded['type']} no longer exists in this yt-dlp. The fixture "
        "recorded it at capture time, so this is upstream churn, not a test failure (NFR-008)."
    )

    if recorded["http_status"] is not None:
        error: BaseException = _http_error(int(recorded["http_status"]))
    else:
        error = exception_type(recorded["message"])

    assert adapter.classify_exception(error).kind.value == recorded["expected_kind"]


def _http_error(status: int) -> Any:
    """A real `HTTPError`, built the way yt-dlp builds one — from a `Response`, not by hand."""
    import io

    from yt_dlp.networking import Response
    from yt_dlp.networking.exceptions import HTTPError

    response = Response(fp=io.BytesIO(b""), url="https://example.com/x", headers={}, status=status)
    return HTTPError(response)


@pytest.mark.parametrize("path", error_fixtures(), ids=fixture_id)
def test_a_recorded_failure_keeps_the_extractor_s_own_words(path: Path) -> None:
    """`NFR-006`: the message is recorded verbatim, so a paraphrase upstream is visible here."""
    recorded = load(path)["error"]
    assert recorded["message"].strip()
    assert recorded["message"] == recorded["message"].strip()
