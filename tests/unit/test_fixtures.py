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


def test_a_recorded_fixture_names_the_extractor_its_own_source_declares() -> None:
    """`T107-R8`: the committed extractor is the source's, not whichever one was hardcoded.

    `capture_info` wrote the literal `"archive.org"` into every fixture it produced. Three sources
    are archive.org and the fourth is Wikimedia Commons, so `wikimedia_caminandes.json` recorded an
    extractor that had never touched it — provenance that reads exactly like the checked kind.

    **The declaration is the transcribed side and the committed file is the derived one**
    (`ai/TESTING.md` §13). `capture.py` is where a human states where a source comes from; this
    reads what was actually written. A capture additionally refuses to write when yt-dlp's own
    `extractor` disagrees with the declaration, which is the half of the check that needs the
    network and therefore cannot live here.
    """
    from tests.fixtures.capture import SOURCES

    declared = {source.name: source.extractor for source in SOURCES}
    checked = 0
    for path in info_fixtures():
        meta = load(path)["_fixture"]
        if meta.get("capture_method") != "recorded":
            continue
        expected = declared.get(path.stem)
        assert expected is not None, f"{path.name} is recorded but no Source declares it"
        assert meta.get("extractor") == expected, (
            f"{path.name} records extractor {meta.get('extractor')!r}, but its source declares "
            f"{expected!r}"
        )
        checked += 1
    assert checked >= 4, f"only {checked} recorded fixtures were checked"


def test_the_writer_records_each_source_s_own_extractor() -> None:
    """The **writer**, not the files it wrote (`T107-R8`, `ai/TESTING.md` §13).

    **The committed-fixture test above cannot catch this defect coming back.** It compares files on
    disk against the declarations, and a writer that went back to a hardcoded `"archive.org"` does
    not change a file until somebody re-captures — so the assertion that caught the original bug
    would sit green while the bug was live again. That mutation was run and it survived, which is
    why `provenance` was separated out of `capture_info`: the decision is now reachable without the
    network.

    Every source is checked, not one, because a hardcode is invisible against whichever source
    happens to share its value.
    """
    from tests.fixtures.capture import SOURCES, provenance

    for source in SOURCES:
        block = provenance(source, "2026.07.04", {"extractor": source.extractor})
        assert block["extractor"] == source.extractor, (
            f"the writer recorded {block['extractor']!r} for {source.name}, which declares "
            f"{source.extractor!r}"
        )


def test_the_writer_refuses_to_record_an_extractor_yt_dlp_contradicts() -> None:
    """A declaration is only worth something if the capture checks it (`T107-R8`).

    Declaring the extractor by hand makes a wrong value less likely; it does not make it
    impossible. The capture compares against yt-dlp's own answer and **stops**, so the committed
    value is hand-written — `SEC-002`'s line intact — and cannot disagree with the site it came
    from. Refusing rather than picking a winner: an extractor rename is `NFR-008` churn, and
    absorbing it silently is what a fixture exists to prevent.
    """
    from tests.fixtures.capture import SOURCES, provenance

    source = SOURCES[0]
    with pytest.raises(SystemExit, match="declared extractor"):
        provenance(source, "2026.07.04", {"extractor": "somewhere.else"})

    # Silence is not a contradiction: an extractor that reports nothing leaves the declaration
    # standing rather than failing a capture for a field yt-dlp did not fill.
    assert provenance(source, "2026.07.04", {})["extractor"] == source.extractor


def test_the_recorded_policy_names_every_entry_field_that_is_actually_kept() -> None:
    """`T185-R2`: the provenance must not understate what is permanently committed.

    It said playlist entries were **"counted rather than recorded"**. That was true until
    `SEC-002`'s 2026-08-04 amendment for `T-137`, after which an entry keeps its address, title,
    duration and thumbnail — and `archive_org_art_of_war_playlist.json` contains them. Every
    fixture carried the old sentence, so the record of a **data boundary** was wrong in the one
    direction that matters: it claimed less was kept than is.

    **Derived from `CONSUMED_ENTRY`, not transcribed** (`ai/TESTING.md` §13). A sentence written
    beside a machine-read allowlist is two statements of one fact, and they had already drifted
    once. Each field is asserted by name, so adding one to the allowlist and not to the sentence
    fails here.
    """
    from tests.fixtures.capture import CONSUMED_ENTRY, _policy_record

    policy = _policy_record()
    for field in CONSUMED_ENTRY:
        assert field in policy, f"the recorded policy does not mention the retained entry {field!r}"
    assert "counted rather than recorded" not in policy, (
        "the policy still claims playlist entries are only counted, which SEC-002's amendment "
        "and the committed playlist fixture both contradict"
    )


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_the_committed_policy_matches_the_writer(path: Path) -> None:
    """Every committed fixture states the policy the writer currently promises (`T185-R2`).

    **The half that catches a stale file rather than a stale sentence.** Correcting
    `_policy_record` alone would leave seven fixtures on disk still describing the superseded rule,
    and they are what a reader actually opens. Equality rather than a keyword, so a future
    amendment cannot land in the writer and quietly not reach the committed provenance.

    Error fixtures carry no `policy` — they record an exception, not an allowlisted extraction —
    and are skipped rather than asserted into having one.
    """
    from tests.fixtures.capture import _policy_record

    meta = load(path)["_fixture"]
    if "policy" not in meta:
        pytest.skip(f"{path.name} records a failure and carries no policy")
    assert meta["policy"] == _policy_record(), (
        f"{path.name}'s recorded policy is not the one the writer promises today"
    )


def test_a_playlist_fixture_actually_contains_the_entry_fields_the_policy_names() -> None:
    """The claim is checked against the data, not only against the writer (`T185-R2`).

    A policy sentence and an allowlist that agree with each other can still both be wrong about
    what is on disk. This is the third side of that triangle: the committed playlist is opened and
    its first entry read.
    """
    from tests.fixtures.capture import CONSUMED_ENTRY

    playlists = [path for path in info_fixtures() if load(path)["info_dict"].get("entries")]
    assert playlists, "no committed fixture has playlist entries, so this asserts nothing"
    for path in playlists:
        for entry in load(path)["info_dict"]["entries"]:
            unexpected = set(entry) - set(CONSUMED_ENTRY)
            assert not unexpected, f"{path.name} keeps {sorted(unexpected)} on a playlist entry"
        first = load(path)["info_dict"]["entries"][0]
        assert first, f"{path.name}'s entries are empty, so the policy's claim is untested here"


def test_the_recorded_sources_do_not_all_come_from_one_extractor() -> None:
    """The property that makes the test above able to fail (`T107-R8`).

    A hardcoded extractor is invisible while every source shares it: the assertion passes, and it
    passes for the wrong reason. This is why the hardcode survived three fixtures and was caught by
    the fourth — so the fourth is what is asserted, rather than left as a happy accident of the
    current set.

    Stated as *more than one*, not as *Wikimedia specifically*: the point is that some fixture
    contradicts any single literal, and naming one source here would make replacing it a test
    failure rather than a capture decision.
    """
    from tests.fixtures.capture import SOURCES

    assert len({source.extractor for source in SOURCES}) > 1, (
        "every recorded source shares one extractor, so a hardcoded value cannot be detected"
    )


def test_a_source_cannot_inherit_another_source_s_extractor_by_omission() -> None:
    """`T107-R8`'s gate: declaring the extractor is not optional (`ai/TESTING.md` §13).

    The correction would be worth little if the next source could simply leave the field out and
    pick up a default. `Source` takes it keyword-only and required, so omission is a `TypeError` at
    the point the source is written rather than a wrong value in a committed file months later.

    Asserted rather than described, because "it is required" is exactly the kind of claim a later
    refactor makes false while every other test stays green.
    """
    from tests.fixtures.capture import Source

    with pytest.raises(TypeError):
        Source(  # type: ignore[call-arg]
            name="no_extractor",
            url="https://example.com/",
            why="a source that forgot to say where it comes from",
            licence="none",
        )


# --- 2. what a fixture may contain (REQ-026, NFR-007) ---------------------------------------
#
# `T018-R1` was Critical four times, and every correction was a better *recogniser*: cookies,
# then tuple containers, then capture metadata and non-`C:` profiles, then `auth`, then `passwd`
# and `accessKey`. Each fix was right and the next spelling still walked through, because the
# question — "does this look like a secret?" — has no closed answer.
#
# The question is now "is this a field the projection reads?", which does. A value can only be
# committed if `ytdlp_adapter` reads a field by that name, and it reads none that carry
# credentials.
#
# A fifth round found the exception that proved the rule. Everything dropped used to leave a
# value-free `_schema` fingerprint behind, for `NFR-008` churn evidence — and a fingerprint
# copies mapping *keys* verbatim, so `{"unknown_map": {"<a secret>": "ignored"}}` wrote the
# secret to disk while all three gates reported the file clean. A key is captured data. `SEC-002`
# was amended to remove the fingerprint rather than sanitize it, and this file no longer has a
# second thing that may contain something.

#: Transcribed from `capture.py`'s allowlists **by hand**, as the second of two statements that
#: must agree. Importing them would make the gate a mirror of the thing it checks.
ALLOWED_INFO_KEYS = frozenset(
    {
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
    }
)
#: What a playlist entry may carry (`T-137`). Kept in step with `capture.CONSUMED_ENTRY` by
#: `test_the_allowlist_matches_what_the_adapter_actually_reads`, which derives the truth from the
#: adapter's own source rather than trusting either list.
ALLOWED_ENTRY_KEYS = frozenset(
    {"url", "webpage_url", "original_url", "title", "duration", "thumbnail", "thumbnails"}
)

ALLOWED_FORMAT_KEYS = frozenset(
    {
        "acodec",
        "ext",
        "filesize",
        "filesize_approx",
        "format_id",
        "format_note",
        # `fps` and `tbr` joined when `T-107` gave `FormatInfo` the two columns `REQ-003` had
        # always named and nothing carried. **The recorded captures predate them and do not hold
        # them** — this list says what a fixture *may* carry, not what one does — so the columns
        # they feed are asserted against a derived fixture until a re-capture lands (`T-185`).
        "fps",
        "has_drm",
        "height",
        "tbr",
        "vcodec",
        "width",
    }
)
ALLOWED_FIXTURE_KEYS = frozenset(
    {
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
    }
)
ALLOWED_ERROR_KEYS = frozenset({"expected_kind", "http_status", "message", "module", "type"})

#: The only top-level blocks a fixture may have. `_schema` is deliberately **not** one of them
#: any more (`SEC-002`, amended): removing the writer's ability to emit one is half the fix, and
#: refusing to accept one at the gate is the half that stays true if somebody restores it.
ALLOWED_TOP_LEVEL_KEYS = frozenset({"_fixture", "error", "info_dict"})

#: Literal strings that must never appear anywhere in a committed fixture. Kept as a second,
#: independent check — the allowlist should make every one of them unreachable, and a hit here
#: means it did not.
FORBIDDEN_SUBSTRINGS = (
    "Set-Cookie",
    "set-cookie",
    "Bearer ",
    "csrf",
    "session-id",
    "donation-identifier",
    "Mozilla/",
)

_QUERY_PARAMETER = re.compile(r"[?&#]([A-Za-z0-9_.\-%]+)=")
_URL_USERINFO = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^/\s\"']*@")
_USER_DIRECTORY = re.compile(
    r"(?:[A-Za-z]:(?:\\{1,2}|/)+users(?:\\{1,2}|/))"
    r"|(?:\\{2,4}(?:[^\\/\s\"']+(?:\\{1,2}|/)+)+users(?:\\{1,2}|/))"
    r"|(?:/home/)"
    r"|(?:/Users/)",
    re.IGNORECASE,
)


def leaks_in(blob: str) -> list[str]:
    """Credential-shaped text anywhere in `blob` — the belt, not the braces.

    The allowlist is what actually keeps secrets out. This stays because a second check that
    shares no logic with the first is how the two are known to agree, and because a *consumed*
    field can still be a URL carrying a signature.
    """
    found = [needle for needle in FORBIDDEN_SUBSTRINGS if needle in blob]
    found += [f"user directory in {m.group(0)!r}" for m in _USER_DIRECTORY.finditer(blob)]
    found += [f"query parameter {m.group(1)!r}" for m in _QUERY_PARAMETER.finditer(blob)]
    found += [f"url userinfo in {m.group(0)!r}" for m in _URL_USERINFO.finditer(blob)]
    return found


def unexpected_keys(payload: dict[str, Any]) -> list[str]:
    """Every key in a fixture that is not on an allowlist — the gate that closes the class.

    Reported by path so a failure names what got in, and checked on the parsed object because a
    key is not visible in text. This is the check `T018-R1` needed from the start: it does not
    care what the key is *called*.
    """
    found: list[str] = []

    def walk_info(info: Any, path: str) -> None:
        if not isinstance(info, dict):
            return
        for key, value in info.items():
            if key not in ALLOWED_INFO_KEYS:
                found.append(f"{path}.{key}")
                continue
            if key == "formats" and isinstance(value, list):
                for index, entry in enumerate(value):
                    if not isinstance(entry, dict):
                        continue
                    found.extend(
                        f"{path}.formats[{index}].{name}"
                        for name in entry
                        if name not in ALLOWED_FORMAT_KEYS
                    )
            elif key == "entries" and isinstance(value, list):
                # **An entry is now a record, and an allowlisted one** (`T-137`). This read
                # "every key is unexpected rather than every unlisted key", because the projection
                # took `len(entries)` and never looked inside one (`T018-R1`). A playlist that
                # expands into one job per entry reads four fields off each, so entries are held
                # to the same rule as formats — unlisted keys are leaks, listed ones are not.
                for index, entry in enumerate(value):
                    if isinstance(entry, dict):
                        found.extend(
                            f"{path}.entries[{index}].{name}"
                            for name in entry
                            if name not in ALLOWED_ENTRY_KEYS
                        )
                    elif entry is not None:
                        found.append(f"{path}.entries[{index}] = {type(entry).__name__}")

    found.extend(
        f"_fixture.{k}" for k in payload.get("_fixture", {}) if k not in ALLOWED_FIXTURE_KEYS
    )
    found.extend(f"error.{k}" for k in payload.get("error", {}) if k not in ALLOWED_ERROR_KEYS)
    walk_info(payload.get("info_dict"), "info_dict")
    found.extend(k for k in payload if k not in ALLOWED_TOP_LEVEL_KEYS)
    return found


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_a_fixture_carries_only_the_keys_the_projection_reads(path: Path) -> None:
    """The gate that ends the marker-list rounds (`T018-R1`).

    Four corrections tried to recognise a credential and four were outrun by the next spelling.
    This asks the closed question instead: a value may be committed only under a field
    `ytdlp_adapter` reads, and none of those carry credentials.
    """
    found = unexpected_keys(load(path))
    assert not found, (
        f"{path.name} carries fields the projection never reads: {found}. Values belong only "
        "under consumed keys; everything else is dropped and nothing about it is kept."
    )


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_no_fixture_carries_a_shape_record(path: Path) -> None:
    """`SEC-002`, amended: there is no second block, because the second block could carry data.

    A fingerprint of the discarded keys was `NFR-008` churn evidence until a probe put a secret
    in a nested mapping *key* and watched every gate call the file clean. A key is captured data.
    What remains of `NFR-008` here is narrower and honest: a rename of a field the adapter
    **reads** fails the projection tests, and one it never reads is not this project's canary.
    """
    payload = load(path)
    assert "_schema" not in payload, (
        f"{path.name} carries a _schema block. It was removed because a fingerprint copies "
        "mapping keys verbatim, and a key is data (SEC-002, amended)."
    )
    assert set(payload) <= ALLOWED_TOP_LEVEL_KEYS, sorted(set(payload) - ALLOWED_TOP_LEVEL_KEYS)


@pytest.mark.parametrize("path", all_fixtures(), ids=fixture_id)
def test_no_fixture_carries_credential_material(path: Path) -> None:
    """The second, independent check. The allowlist should make every hit here impossible."""
    leaks = leaks_in(path.read_text(encoding="utf-8"))
    assert not leaks, f"{path.name} carries {leaks}. Fixtures are committed; a leak is permanent."


def test_the_allowlist_matches_what_the_adapter_actually_reads() -> None:
    """The two statements that must agree, one transcribed and one **derived** (§13).

    The allowlist above is written by hand; this walks `ytdlp_adapter`'s AST for the keys it
    reads off an info dict or a format entry. A field the adapter starts reading fails here
    until the fixtures can carry it — which is the failure you want, because until then the
    fixtures cannot test it.
    """
    import ast

    source = (
        Path(__file__).resolve().parents[2] / "src/tracks_and_trails/downloader/ytdlp_adapter.py"
    ).read_text(encoding="utf-8")

    reads: dict[str, set[str]] = {"info": set(), "entry": set(), "item": set()}
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "get" or not isinstance(node.func.value, ast.Name):
            continue
        receiver = node.func.value.id
        first = node.args[0] if node.args else None
        if receiver in reads and isinstance(first, ast.Constant) and isinstance(first.value, str):
            reads[receiver].add(first.value)

    assert reads["info"], "no info-dict reads found; the derivation broke, not the allowlist"
    assert reads["info"] <= ALLOWED_INFO_KEYS, (
        f"the adapter reads {sorted(reads['info'] - ALLOWED_INFO_KEYS)}, which fixtures drop"
    )
    assert reads["entry"] <= ALLOWED_FORMAT_KEYS, (
        f"the adapter reads {sorted(reads['entry'] - ALLOWED_FORMAT_KEYS)} off a format"
    )
    # `item` is the adapter's name for a playlist entry, kept distinct from `entry` — a format —
    # precisely so this derivation can tell the two allowlists apart (`T-137`).
    assert reads["item"] <= ALLOWED_ENTRY_KEYS, (
        f"the adapter reads {sorted(reads['item'] - ALLOWED_ENTRY_KEYS)} off a playlist entry, "
        "which fixtures drop"
    )


#: A payload holding every spelling that has ever beaten a marker list, plus a few nobody has
#: proposed yet. None of them is recognised by name any more — they are dropped because nothing
#: reads a field called that.
HOSTILE_INFO = {
    "title": "kept",
    "webpage_url": "https://archive.org/details/x",
    "cookies": "SID=secret",
    "auth": "fixture-secret-7c6c",
    "passwd": "hunter2",
    "passphrase": "open sesame",
    "private_key": "-----BEGIN",
    "accessKey": "AKIA",
    "cookiejar": "jar.txt",
    "clientsecret": "shh",
    "somethingNobodyHasNamedYet": "still a secret",
    "formats": [
        {"format_id": "1", "ext": "mp4", "http_headers": {"Cookie": "SID=x"}, "nonce": "abc"}
    ],
}


def test_the_writer_keeps_only_what_the_projection_reads() -> None:
    """`T018-R1`, structurally: the *writer* is where the class is closed.

    The committed files are clean, so weakening the writer changes nothing until somebody
    re-captures — which is a network act the suite never performs. Every guarantee below is
    therefore asserted against `capture` directly, or it is asserted against nothing.
    """
    from tests.fixtures import capture

    kept = capture.keep_consumed(HOSTILE_INFO)

    assert kept["title"] == "kept"
    assert set(kept) <= capture.CONSUMED_TOP_LEVEL_SET, f"unread fields survived: {sorted(kept)}"
    assert set(kept["formats"][0]) <= set(capture.CONSUMED_FORMAT)
    blob = json.dumps(kept)
    for secret in ("secret", "hunter2", "sesame", "BEGIN", "AKIA", "shh", "SID="):
        assert secret not in blob, f"{secret!r} survived into the committed values"


def test_a_secret_used_as_a_mapping_key_is_not_written(tmp_path: Path) -> None:
    """The probe that reopened `T018-R1` a fifth time, now a permanent assertion.

    `capture.write()` used to emit a shape fingerprint of everything it dropped, and a
    fingerprint copies mapping keys verbatim. Nested maps are commonly keyed by data — a header
    name, an identifier, a token — so the claim that the record "cannot carry data" was simply
    false, and all three gates reported the file clean.
    """
    from tests.fixtures import capture

    written = tmp_path / "keys.json"
    capture.write(
        written,
        {
            "_fixture": {"captured": "2026-07-27"},
            "info_dict": {"unknown_map": {"credential-value-as-key-7c6c": "ignored"}},
        },
    )
    text = written.read_text(encoding="utf-8")

    assert "credential-value-as-key-7c6c" not in text, "a mapping key reached the file"
    assert "unknown_map" not in text, "the dropped key's own name reached the file"
    assert not unexpected_keys(load(written))
    assert not leaks_in(text)


def test_the_writer_ignores_anything_the_caller_supplies_beside_the_known_blocks(
    tmp_path: Path,
) -> None:
    """`write()` derives what it writes; it does not accept a caller's version of it.

    The removed `_schema` was taken from the payload when one was there, so a value that had
    never been through the allowlist went to disk. Nothing outside `_fixture`, `info_dict` and
    `error` is carried now, and those three are rebuilt rather than copied.
    """
    from tests.fixtures import capture

    written = tmp_path / "supplied.json"
    capture.write(
        written,
        {
            "_fixture": {"captured": "2026-07-27"},
            "info_dict": {"title": "kept"},
            "_schema": {"smuggled": "SID=secret"},
            "extra_block": {"also": "SID=secret"},
        },
    )
    payload = load(written)

    assert set(payload) <= ALLOWED_TOP_LEVEL_KEYS, sorted(payload)
    assert "SID=secret" not in written.read_text(encoding="utf-8")
    assert payload["info_dict"]["title"] == "kept"


def test_a_playlist_entry_keeps_only_what_the_adapter_reads(tmp_path: Path) -> None:
    """`T-137` changed what this asserts, and the rule it asserts *under* did not change.

    This used to require every entry to be `{}`, and said why: the projection read `len(entries)`
    and each entry was a whole info dict, so recursing into them was the largest single body of
    retained data in the fixture set. A playlist that expands into one job per entry now reads
    four fields off each one, so the same rule — **kept if and only if the adapter reads it** —
    now keeps four fields and drops the rest.

    The hostile values below are the point: `uploader` and `cookies` are exactly the shape
    `T018-R1` found being retained for nobody, and they must still not survive.
    """
    from tests.fixtures import capture

    written = tmp_path / "playlist.json"
    capture.write(
        written,
        {
            "_fixture": {"captured": "2026-07-27"},
            "info_dict": {
                "_type": "playlist",
                "title": "kept",
                "entries": [
                    {
                        "title": "chapter one",
                        "url": "https://example.invalid/one",
                        "duration": 61,
                        "uploader": "a person",
                        "cookies": "SID=secret",
                    },
                    {"title": "chapter two", "uploader": "a person"},
                ],
            },
        },
    )
    payload = load(written)

    entries = payload["info_dict"]["entries"]
    assert entries[0] == {
        "title": "chapter one",
        "url": "https://example.invalid/one",
        "duration": 61,
    }, (
        "an entry kept something outside the allowlist, or dropped something inside it: "
        f"{entries[0]}"
    )
    assert entries[1] == {"title": "chapter two"}, (
        "an entry that named fewer fields gained ones it never had"
    )

    text = written.read_text(encoding="utf-8")
    for value in ("a person", "SID=secret"):
        assert value not in text, f"{value!r} survived inside an entry"
    assert not unexpected_keys(payload)


def test_the_gate_refuses_a_shape_record_and_a_populated_entry(tmp_path: Path) -> None:
    """`ai/TESTING.md` §13: the gate has to be watched refusing what the writer stopped emitting.

    Removing the writer's ability to emit a `_schema` is half the fix. This is the half that
    survives somebody restoring it, or hand-editing a fixture.
    """
    hostile = {
        "_fixture": {"captured": "2026-07-27"},
        "info_dict": {
            "title": "fine",
            # `title` is allowlisted for an entry since `T-137`; `uploader` never was, and it is
            # the field `T018-R1` actually found being retained for no reader.
            "entries": [{"title": "chapter one", "uploader": "a person"}, {}],
        },
        "_schema": {"unknown_map": {"credential-value-as-key-7c6c": "str"}},
    }
    written = tmp_path / "restored.json"
    written.write_text(json.dumps(hostile), encoding="utf-8")

    found = unexpected_keys(load(written))

    assert "_schema" in found, "a restored fingerprint was accepted"
    assert "info_dict.entries[0].uploader" in found, (
        "an unlisted field inside an entry was accepted; entries are allowlisted now, not empty"
    )
    assert "info_dict.entries[0].title" not in found, (
        "an entry's title was refused, though the adapter reads one for every queued entry"
    )
    assert not any(item.endswith(".title") and "entries" not in item for item in found), (
        "a consumed field was refused"
    )


def test_the_writer_enforces_the_provenance_and_error_allowlists(tmp_path: Path) -> None:
    """`source_url` is captured data, and so is an error message.

    A previous round wrote the provenance block raw while cleaning the `info_dict` beside it.
    Both blocks are now allowlisted at the same door every capture passes through.
    """
    from tests.fixtures import capture

    written = tmp_path / "written.json"
    capture.write(
        written,
        {
            "_fixture": {
                "captured": "2026-07-27",
                "source_url": "https://u:p@example.com/x?X-Amz-Signature=s#access_token=t",
                "smuggled": "value",
            },
            "error": {"message": "fine", "stack": "leak"},
            "info_dict": HOSTILE_INFO,
        },
    )
    payload = load(written)

    assert "smuggled" not in payload["_fixture"]
    assert "stack" not in payload["error"]
    assert payload["_fixture"]["source_url"] == "https://example.com/x"
    assert not unexpected_keys(payload)
    assert not leaks_in(written.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "path_value",
    [
        r"C:\Users\Sean\Videos\out.mp4",
        r"D:/Users/Sean/out.mp4",
        r"\\server\Users\sean\out.mp4",
        "/home/sean/out.mp4",
        "/Users/sean/out.mp4",
    ],
)
def test_a_consumed_field_still_loses_a_user_directory(tmp_path: Path, path_value: str) -> None:
    """The allowlist does not cover this, and a mutation battery proved it (`NFR-007`).

    A key allowlist answers "may this field carry a value?" — it says nothing about *what* the
    value is. `title` is consumed, and a title can be a local path; so can a `url`. Removing
    `clean_scalar`'s user-directory branch left every test green, which is the definition of an
    unasserted guard (`ai/TESTING.md` §13). Asserted at `write()` rather than against
    `clean_scalar`, because the door is what a future capture goes through.
    """
    from tests.fixtures import capture

    written = tmp_path / "paths.json"
    capture.write(
        written,
        {
            "_fixture": {"captured": "2026-07-27", "note": path_value},
            "info_dict": {
                "title": path_value,
                "url": path_value,
                "formats": [{"format_id": "1", "ext": "mp4", "format_note": path_value}],
            },
        },
    )
    payload = load(written)

    assert payload["info_dict"]["title"] == capture.REDACTED
    assert payload["info_dict"]["url"] == capture.REDACTED
    assert payload["info_dict"]["formats"][0]["format_note"] == capture.REDACTED
    assert payload["_fixture"]["note"] == capture.REDACTED
    assert not leaks_in(written.read_text(encoding="utf-8"))


def test_the_gate_rejects_a_fixture_carrying_anything_else(tmp_path: Path) -> None:
    """`ai/TESTING.md` §13: the gate has to be watched refusing something.

    Every spelling that beat a marker list is here — and none of them is recognised by name now.
    They are refused because nothing reads a field called that.
    """
    hostile = {
        "_fixture": {"captured": "2026-07-27", "smuggled": "value"},
        "info_dict": {
            "title": "fine",
            "cookies": "SID=secret",
            "auth": "fixture-secret-7c6c",
            "passwd": "hunter2",
            "passphrase": "open sesame",
            "private_key": "-----BEGIN",
            "accessKey": "AKIA",
            "cookiejar": "jar.txt",
            "clientsecret": "shh",
            "formats": [{"format_id": "1", "ext": "mp4", "http_headers": {"Cookie": "SID=x"}}],
        },
        "error": {"message": "fine", "stack": "leak"},
    }
    written = tmp_path / "hostile.json"
    written.write_text(json.dumps(hostile), encoding="utf-8")

    found = unexpected_keys(load(written))

    for smuggled in (
        "cookies",
        "auth",
        "passwd",
        "passphrase",
        "private_key",
        "accessKey",
        "cookiejar",
        "clientsecret",
    ):
        assert any(item.endswith(f".{smuggled}") for item in found), f"{smuggled} was allowed"
    assert "info_dict.formats[0].http_headers" in found
    assert "_fixture.smuggled" in found
    assert "error.stack" in found
    assert not any(item.endswith(".title") or item.endswith(".format_id") for item in found), (
        "a consumed field was refused"
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
