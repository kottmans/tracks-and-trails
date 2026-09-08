"""`docs/YTDLP_OPTION_AUDIT.md` against the two things that can contradict it (`T-183`).

The audit classifies every documented yt-dlp option into exactly one class, and its whole value
rests on two claims that a document cannot keep true by itself:

- **the inventory is yt-dlp's**, not a list somebody transcribed, and
- **the application-owned class is `build_options`'**, not a list somebody remembered.

`T-183`'s second acceptance criterion asks for exactly this test, and `ARC-010`'s own history is
why: its §4 names `paths` as an application-owned key, and `build_options` has never set it. A
list written from memory drifts from the code silently, and the refusal list `T-184` builds on
top of it inherits the drift.

**Every expectation here is re-derived, never transcribed.** The option inventory comes from
`create_parser()`, the emitted keys come from calling `build_options` over every branch, and the
only hand-written thing is the audit itself — which is the artefact under test.
"""

import dataclasses
import re
from collections.abc import Callable
from optparse import SUPPRESS_HELP
from pathlib import Path
from typing import Any, Final

import pytest
import yt_dlp.version
from yt_dlp.options import create_parser

from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.downloader.ytdlp_adapter import build_options

YTDLP_VERSION: Final = yt_dlp.version.__version__

AUDIT = Path(__file__).resolve().parents[2] / "docs" / "YTDLP_OPTION_AUDIT.md"

#: Classes whose options the escape hatch must refuse (`ARC-010` §4, `SEC-003`, `SEC-004`).
REFUSED: Final = frozenset({"app:sets", "app:contained", "app:plumbing", "app:policy", "excluded"})
#: Classes that may legitimately name a key `build_options` sets — **everything that is not
#: hatch-reachable** (`T183-R1`).
#:
#: This was `{"app:sets", "typed"}` and it was too narrow. `--xff` is `excluded` by `SEC-003` *and*
#: names a key the application now sets: refusing the option and supplying the safe default are
#: **both** required, because `REQ-EXCL-002` names a behaviour that is on unless it is turned off.
#: The property this guards is hatch-reachability, so the honest membership is every refused class
#: plus `typed`, whose control wins by `ARC-010`'s precedence rule.
MAY_SET: Final = REFUSED | {"typed"}
KNOWN_CLASSES: Final = REFUSED | MAY_SET | {"hatch", "unruled"}


# --- what yt-dlp actually has ------------------------------------------------------------------


def _options() -> list[dict[str, Any]]:
    parser = create_parser()
    return [
        {
            "strings": tuple(opt._short_opts) + tuple(opt._long_opts),
            "dest": opt.dest,
            "documented": opt.help is not SUPPRESS_HELP and opt.help is not None,
        }
        for group in parser.option_groups
        for opt in group.option_list
    ]


ALL_OPTIONS: Final = _options()
DOCUMENTED: Final = [o for o in ALL_OPTIONS if o["documented"]]
SUPPRESSED: Final = [o for o in ALL_OPTIONS if not o["documented"]]


# --- what `build_options` actually sets --------------------------------------------------------

_BASE: Final[dict[str, Any]] = {
    "url": "https://example.invalid/watch?v=x",
    "output_directory": str(Path.home() / "downloads"),
    "format_selector": "bv*+ba/b",
    "output_template": "%(title)s.%(ext)s",
}
#: One value per `DownloadRequest` field that can turn a branch on inside `build_options`.
_FIELD_ON: Final = {
    "media_kind": MediaKind.AUDIO,
    "audio_codec": AudioCodec.MP3,
    "audio_quality": "192",
    "post_processors": ("FFmpegThumbnailsConvertor",),
    "subtitle_languages": ("en",),
    "embed_subtitles": True,
    "embed_thumbnail": True,
    "embed_metadata": True,
    "embed_chapters": True,
    "remux_container": "mkv",
    "recode_container": None,  # `DownloadRequest` refuses this alongside `remux_container`
    "proxy": "http://127.0.0.1:8080",
    "rate_limit_bytes": 1024,
    "retries": 0,
    "cookies_from_browser": "firefox",
}
_KEYWORD_ON: Final = {
    "probe_only": True,
    "ffmpeg_location": Path("/usr/bin/ffmpeg"),
    "cookie_file": Path.home() / "cookies.txt",
    "overwrites": True,
    "logger": object(),
}


def _emitted_keys() -> frozenset[str]:
    """Every key `build_options` can emit, by exercising it rather than by reading it.

    Each branch is turned on alone and then all together, which is what makes this a derivation:
    a new `if` in `build_options` that sets a new key shows up here without anyone editing a list.
    """
    fields = {f.name for f in dataclasses.fields(DownloadRequest)}
    unexercised = fields - set(_FIELD_ON) - set(_BASE)
    assert not unexercised, (
        f"{sorted(unexercised)} are DownloadRequest fields no case here turns on, so this "
        f"derivation cannot see the keys they set. Add them to _FIELD_ON."
    )

    on = {name: value for name, value in _FIELD_ON.items() if value is not None}
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = [({}, {})]
    cases += [({name: value}, {}) for name, value in on.items()]
    cases += [({}, {name: value}) for name, value in _KEYWORD_ON.items()]
    cases.append((on, dict(_KEYWORD_ON)))
    cases.append((on, {k: v for k, v in _KEYWORD_ON.items() if k != "probe_only"}))

    keys: set[str] = set()
    for overrides, keywords in cases:
        # `**` over `dict[str, Any]`: the point of this derivation is to drive `build_options`
        # through every branch, and the values are deliberately heterogeneous.
        request = DownloadRequest(**_BASE, **overrides)
        keys |= set(build_options(request, str(_BASE["output_template"]), **keywords))
    return frozenset(keys)


EMITTED: Final = _emitted_keys()


# --- the audit, parsed -------------------------------------------------------------------------

_ROW = re.compile(r"^\|((?:\s*`[^`]+`)+)\s*\|\s*`([a-z:]+)`\s*\|\s*(.+?)\s*\|$")


def _rows() -> list[tuple[tuple[str, ...], str, str]]:
    """The classification tables only — the findings above them have tables of their own."""
    text = AUDIT.read_text(encoding="utf-8")
    _, _, tables = text.partition("\n## The tables\n")
    assert tables, "the audit has no '## The tables' section to parse"
    parsed = []
    for line in tables.splitlines():
        match = _ROW.match(line.strip())
        if match:
            strings = tuple(re.findall(r"`([^`]+)`", match.group(1)))
            parsed.append((strings, match.group(2), match.group(3)))
    return parsed


ROWS: Final = _rows()


# --- the audit is about a named version --------------------------------------------------------


def test_the_audit_names_the_yt_dlp_version_it_was_taken_against() -> None:
    """`T-183`: an audit of an unnamed version cannot be re-run when upstream moves.

    This fails when the pin in `pyproject.toml` moves, which is the point — a bump is exactly
    when the classification has to be looked at again, and `NFR-008` owns that.
    """
    recorded = re.search(r"\*\*yt-dlp version:\*\* \*\*([0-9.]+)\*\*", AUDIT.read_text("utf-8"))
    assert recorded, "the audit does not state the yt-dlp version it was taken against"
    assert recorded.group(1) == YTDLP_VERSION, (
        f"the audit was taken against yt-dlp {recorded.group(1)} and {YTDLP_VERSION} is "
        f"installed. Re-run it (T-183) rather than editing the version line."
    )


# --- every documented option, exactly once -----------------------------------------------------


def test_every_documented_option_is_classified_exactly_once() -> None:
    classified: dict[str, int] = {}
    for strings, _, _ in ROWS:
        for string in strings:
            classified[string] = classified.get(string, 0) + 1

    documented = {s for option in DOCUMENTED for s in option["strings"]}
    twice = sorted(s for s, n in classified.items() if n > 1)
    assert not twice, f"classified in more than one row: {twice}"
    assert not documented - set(classified), (
        f"documented by yt-dlp and absent from the audit: {sorted(documented - set(classified))}"
    )
    assert not set(classified) - documented, (
        f"classified by the audit and not documented by yt-dlp: "
        f"{sorted(set(classified) - documented)}"
    )


def test_the_audit_states_the_row_count_it_has() -> None:
    """`T-212`'s row count said forty-one from an estimate and was forty-seven when counted."""
    stated = re.search(r"\*\*Rows:\*\* \*\*(\d+)\*\*", AUDIT.read_text("utf-8"))
    assert stated and int(stated.group(1)) == len(ROWS) == len(DOCUMENTED)


def test_the_audit_states_the_documented_and_suppressed_split() -> None:
    text = AUDIT.read_text("utf-8")
    assert f"**{len(ALL_OPTIONS)}** options" in text
    assert f"**{len(SUPPRESSED)}** have their help suppressed" in text


def test_every_class_used_is_one_the_audit_defines() -> None:
    used = {cls for _, cls, _ in ROWS}
    assert used <= KNOWN_CLASSES, f"undefined classes in use: {sorted(used - KNOWN_CLASSES)}"


def test_the_class_table_counts_what_the_tables_hold() -> None:
    """The audit's summary must not drift from the audit (`T-256`, `SEC-004`).

    `SEC-004` moved fifteen rows from `unruled` to `excluded`, and the summary at the top states a
    count per class. A hand-maintained count beside a machine-checked table is the `T-212` row-count
    shape — forty-one stated over a forty-seven row file — so it is derived here instead.
    """
    from collections import Counter

    counted = Counter(cls for _, cls, _ in ROWS)
    text = AUDIT.read_text("utf-8")
    stated = {
        match.group(1): int(match.group(2))
        for match in re.finditer(r"^\| `([a-z:]+)` \| \*{0,2}(\d+)\*{0,2} \|", text, re.M)
    }
    assert stated, "the audit states no class counts at all"
    wrong = {cls: (n, counted.get(cls, 0)) for cls, n in stated.items() if n != counted.get(cls, 0)}
    assert not wrong, f"class table says {{cls: (stated, actual)}} {wrong}"
    assert set(stated) == set(KNOWN_CLASSES), (
        f"the class table and the defined classes disagree: "
        f"{sorted(set(stated) ^ set(KNOWN_CLASSES))}"
    )


def test_the_refusal_list_size_is_stated_and_correct() -> None:
    """What `T-184` enforces, counted rather than asserted in prose.

    Whitespace is normalized before matching: the phrase is prose and wraps, and a gate that fails
    because a sentence was re-wrapped teaches people to re-wrap rather than to recount.
    """
    refused = sum(1 for _, cls, _ in ROWS if cls in REFUSED)
    flat = " ".join(AUDIT.read_text("utf-8").split())
    assert f"— {refused} rows**" in flat, (
        f"the audit does not state its refusal list as {refused} rows"
    )


def test_every_row_carries_a_reason() -> None:
    """`T-183`: "nobody asked for it" is a reason; silence is not."""
    silent = [strings for strings, _, note in ROWS if len(note.strip()) < 10]
    assert not silent, f"rows with no reason: {silent}"


# --- the application-owned class is derived, and cannot drift ----------------------------------


def test_no_key_build_options_sets_is_reachable_through_the_hatch() -> None:
    """The invariant the refusal list exists to hold, checked against the code that sets them.

    A key the application sets and the user can also type is a key two sources fight over. The
    audit's answer is that such an option is `app:sets` (refused) or `typed` (a control wins by
    `ARC-010`'s precedence rule) — never `hatch`, which would let the hatch win by silence.
    """
    class_of = {s: cls for strings, cls, _ in ROWS for s in strings}
    escapes = {}
    for option in DOCUMENTED:
        if option["dest"] in EMITTED:
            for string in option["strings"]:
                if class_of[string] not in MAY_SET:
                    escapes[string] = (option["dest"], class_of[string])
    assert not escapes, (
        f"these set a key build_options also sets, and the audit does not refuse them: {escapes}"
    )


def test_every_application_owned_row_names_a_key_build_options_really_sets() -> None:
    """The other direction: a refusal that refuses nothing is a refusal nobody maintains."""
    dest_of = {s: option["dest"] for option in DOCUMENTED for s in option["strings"]}
    stale = {
        strings: dest_of[strings[0]]
        for strings, cls, _ in ROWS
        if cls == "app:sets" and dest_of[strings[0]] not in EMITTED
    }
    assert not stale, f"classified app:sets and build_options never sets the key: {stale}"


def test_the_keys_with_no_command_line_route_are_the_ones_the_audit_names() -> None:
    """Five emitted keys are library parameters; refusing them would refuse nothing."""
    routable = {option["dest"] for option in ALL_OPTIONS}
    assert sorted(EMITTED - routable) == [
        "logger",
        "no_color",
        "postprocessor_hooks",
        "postprocessors",
        "progress_hooks",
    ]


# --- Finding 4: a string-keyed refusal list is routed around ------------------------------------


def test_suppressed_aliases_still_reach_a_refused_key() -> None:
    """Finding 4, kept true rather than kept written.

    `--geo-bypass` sets the same `geo_bypass` that `--xff` does, and `SEC-003` forbids `--xff` by
    name. If upstream ever stops sharing these dests the finding is obsolete and this test says
    so; while it holds, `T-184` cannot key its refusal list on option strings.
    """
    refused_dests = {
        option["dest"]
        for option in DOCUMENTED
        for strings, cls, _ in ROWS
        if cls in REFUSED and option["strings"][0] in strings
    }
    bypassing = {
        s for option in SUPPRESSED if option["dest"] in refused_dests for s in option["strings"]
    }
    assert bypassing == {
        "--all-formats",
        "--geo-bypass",
        "--geo-bypass-country",
        "--geo-bypass-ip-block",
        "--no-geo-bypass",
        "--no-colors",
        "--no-colours",
    }


@pytest.mark.parametrize("option", ["--exec-before-download", "--no-exec-before-download"])
def test_the_forbidden_exec_family_has_a_suppressed_member(option: str) -> None:
    """`SEC-003` names `--exec-before-download`, and the documented surface does not carry it."""
    suppressed = {s for o in SUPPRESSED for s in o["strings"]}
    assert option in suppressed


# --- the derivations the audit claims, actually performed (`T183-R4`) ---------------------------
#
# The audit said the test re-derived the excluded families and asserted the typed-task partition.
# It did neither: the class and count tests only compared the audit to itself, and the reviewer
# demonstrated it by moving `--no-check-certificates` from `excluded` to `hatch`, recounting the
# three totals, and watching all fourteen tests pass. These are the checks that make the claim true.

DECISIONS: Final = Path(__file__).resolve().parents[2] / "docs" / "project" / "DECISIONS.md"
TASKS: Final = Path(__file__).resolve().parents[2] / "docs" / "project" / "TASKS.md"
#: Option strings as they appear in prose — short forms (`-u`, `-2`) and the `-I/--long` shorthand
#: the task entries use, which is split on `/` by the callers.
_OPTION = re.compile(r"`(--?[A-Za-z0-9][A-Za-z0-9/-]*)`")


def _decision(name: str) -> str:
    text = DECISIONS.read_text(encoding="utf-8")
    start = text.index(f"## {name} —")
    return text[start : text.index("\n## ", start + 10)]


def _class_of() -> dict[str, str]:
    return {s: cls for strings, cls, _ in ROWS for s in strings}


def _ruled_options() -> tuple[set[str], set[str]]:
    """Every option the decisions forbid, and every one they permit — read from the tables.

    **The decisions are `SEC-003` (with its 2026-08-21 amendment), `SEC-004` and `SEC-005`**, and
    this docstring named only the first two for a day after `SEC-005` was added to the scan
    (`T256-R4`). The list below is the one that governs; this sentence is the one that goes stale,
    which is why the gate reads the tuple rather than the prose.

    **Both sides, because only reading the forbidden side is half a gate** (`T183-R4`): a mutation
    moving `SEC-003`-permitted `--netrc` *into* `excluded` passed, since the old check accepted any
    mention of an option in a decision — including a sentence permitting it — as authority to
    exclude it.

    `SEC-003`'s verdict column mixes both in one cell (*"`--xff` forbidden;
    `--geo-verification-proxy` permitted"*), so each cell is split into clauses and each clause is
    read for its own verdict.
    """
    return _read_verdicts(_decision)


class MixedVerdictClauseError(AssertionError):
    """One clause named both verdicts, so this gate refuses to guess which the decision meant.

    **`T256-R1`, and it is the defect this gate was built to make impossible.** The first version of
    the override below read `if "forbidden" … elif "permitted"`, which silently resolves a
    both-words clause **as forbidden** — and because the override *removes* the option from the
    opposite set, the intersection assertion that was supposed to catch exactly this could never
    fire. The Reviewer joined the amendment's permitted and forbidden phrases into one clause, moved
    permitted `--netrc` and `--netrc-location` to `excluded`, and re-derived every count to agree:
    **all 19 tests passed, and the gate had approved a refusal wider than the decision.**

    Refusing is the fail-closed reading. A decision may say both things in one *cell* — `SEC-003`'s
    Geo row does — but each **clause** must carry one verdict, which is a constraint on how a
    decision is written and is cheap to meet.
    """


def _read_verdicts(body_of: Callable[[str], str]) -> tuple[set[str], set[str]]:
    """The parse, taking its source as an argument so a regression can feed it a mixed clause."""
    forbidden: set[str] = set()
    permitted: set[str] = set()

    def rule(named: set[str], verdict: str) -> None:
        """Apply one clause, **overriding** whatever an earlier table said about the same option.

        The override is what lets an `### Amended` subsection mean something. `SEC-003`'s original
        table permits `--netrc-cmd`; its 2026-08-21 amendment forbids it, and both live in the file
        because `AGENTS.md` §6 makes this record append-only. Reading them in order and letting the
        later one win is the only reading under which the amendment is the decision and the original
        is history.

        **A clause naming both verdicts raises instead of resolving** (`T256-R1`). The override
        makes the later table win, which is right; it must not also make the *louder word* win
        inside one clause, because that silently widens or narrows a security decision and leaves
        every count free to agree with it.
        """
        says_forbidden = "forbidden" in verdict
        says_permitted = "permitted" in verdict
        if says_forbidden and says_permitted:
            raise MixedVerdictClauseError(
                "a verdict clause names both dispositions and cannot be read: "
                f"{verdict.strip()!r}. Split it so each clause carries one verdict; this gate "
                "will not guess which the decision meant, because guessing wrong changes a "
                "refusal list and nothing downstream would disagree."
            )
        if says_forbidden:
            forbidden.update(named)
            permitted.difference_update(named)
        elif says_permitted:
            permitted.update(named)
            forbidden.difference_update(named)

    for name, header in (
        ("SEC-003", "| Family | Ruled |"),
        ("SEC-004", "| Family | Options | Why |"),
        ("SEC-005", "| Family | Options | Why |"),
    ):
        body = body_of(name)
        # **Every** table with this header, in document order — not just the first. `SEC-003` has
        # two: the original verdict table and the amendment's.
        at = body.find(header)
        while at != -1:
            table = body[at : body.index("\n\n", at)]
            for line in table.split("\n")[2:]:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 2:
                    continue
                family, verdict = cells[0], cells[1]
                if name in ("SEC-004", "SEC-005"):
                    # Every option in these tables is forbidden; the third column is reasoning.
                    rule({s for e in _OPTION.findall(verdict) for s in e.split("/")}, "forbidden")
                    continue
                for clause in re.split(r"[.;]", verdict):
                    named = {s for e in _OPTION.findall(clause) for s in e.split("/")}
                    if not named:
                        named = {s for e in _OPTION.findall(family) for s in e.split("/")}
                    rule(named, clause.lower())
            at = body.find(header, at + len(header))
    assert not forbidden & permitted, (
        f"a decision both forbids and permits: {forbidden & permitted}"
    )
    return forbidden, permitted


#: Counterpart spellings refused alongside an option a decision names, listed one by one.
#:
#: `T183-R4` rejected a general "same `dest`" rule as authority: destination equality can widen a
#: refusal conservatively, but doing it by rule is a policy choice made silently. So the choices are
#: enumerated instead — short enough to read, and each one visible to a reviewer.
_REFUSED_COUNTERPARTS: Final = {"--no-exec": "--exec"}

#: Options a decision refuses in its **prose** rather than in its verdict table, quoted so the
#: reader can check the citation without opening the decision.
#:
#: **Enumerated rather than parsed, deliberately.** `SEC-003`'s *Alternatives considered* contains
#: sentences like *"Forbidding `--geo-verification-proxy` with `--xff`. Rejected"* — a rejected
#: *refusal*, which means the option is permitted. Any rule that scanned for "rejected" or
#: "declined" near an option name would read that backwards.
_REFUSED_IN_PROSE: Final = {
    "--sponsorblock-api": ("SEC-003", "A self-hosted `--sponsorblock-api` was declined"),
}


def test_a_clause_naming_both_verdicts_is_refused_rather_than_resolved() -> None:
    """`T256-R1`: the gate must not pick a winner inside one clause, however the audit is aligned.

    **The Reviewer's demonstration, as a test.** Joining the amendment's permitted and forbidden
    phrases into a single clause made the old parser read the whole clause as *forbidden*; moving
    permitted `--netrc` and `--netrc-location` into `excluded` and re-deriving the class and refusal
    counts to 91/28/94 then satisfied every other assertion. **All 19 tests passed while the gate
    approved a refusal wider than the accepted decision.**

    **This fails at parse time, which is what makes aligning the audit useless as a rescue.** The
    refusal happens before any row, count or total is consulted, so there is no arrangement of the
    audit that agrees with the wrong reading — every test that depends on `_ruled_options` errors
    out together. That is the property the finding asked for, and it is structural rather than
    dependent on this test predicting which counts a future mutation would choose.
    """
    mixed = {
        "SEC-003": (
            "## SEC-003 — stand-in\n\n"
            "| Family | Ruled |\n|---|---|\n"
            "| **Site credentials** | `--netrc` is permitted and `--netrc-cmd` is forbidden |\n\n"
        ),
        "SEC-004": "## SEC-004 — stand-in\n\n| Family | Options | Why |\n|---|---|---|\n\n",
        "SEC-005": "## SEC-005 — stand-in\n\n| Family | Options | Why |\n|---|---|---|\n\n",
    }
    with pytest.raises(MixedVerdictClauseError) as raised:
        _read_verdicts(lambda name: mixed[name])
    assert "--netrc" in str(raised.value), (
        "the refusal must quote the clause it could not read, or the next person has to find it"
    )

    # And the same shape split into two clauses is read normally — the override still works, so
    # this is a refusal to guess rather than a refusal to parse amendments.
    split = dict(mixed)
    split["SEC-003"] = mixed["SEC-003"].replace(
        "`--netrc` is permitted and `--netrc-cmd` is forbidden",
        "`--netrc` is permitted. `--netrc-cmd` is forbidden",
    )
    forbidden, permitted = _read_verdicts(lambda name: split[name])
    assert "--netrc-cmd" in forbidden and "--netrc" in permitted


def test_every_option_a_decision_forbids_is_excluded_in_the_audit() -> None:
    """The security disposition, derived from both decisions rather than the audit's own totals.

    Fails on `T183-R4`'s mutations: moving `SEC-004`'s `--no-check-certificates` or `SEC-003`'s
    `--exec` out of `excluded` breaks it however carefully the counts are re-derived.
    """
    forbidden, _ = _ruled_options()
    class_of = _class_of()
    # A decision may name an option the documented surface does not carry (`--exec-before-download`
    # is suppressed); those are `T-184`'s to refuse and cannot be asserted against these rows.
    wrong = {
        option: class_of[option]
        for option in forbidden
        if option in class_of and class_of[option] != "excluded"
    }
    assert not wrong, f"a decision forbids these and the audit does not exclude them: {wrong}"


def test_no_option_a_decision_permits_is_excluded() -> None:
    """The other side of the same gate (`T183-R4`).

    `SEC-003` permits `--netrc`, `--netrc-location`, the client certificates,
    `--geo-verification-proxy` and `--download-archive`. Excluding one of them would be the audit
    overruling a decision, which is the failure `T-183`'s own Finding 3 exists to avoid committing.
    """
    _, permitted = _ruled_options()
    class_of = _class_of()
    wrong = {o: class_of[o] for o in permitted if class_of.get(o) == "excluded"}
    assert not wrong, f"a decision permits these and the audit excludes them: {wrong}"


def test_every_excluded_row_is_named_by_the_decision_it_cites() -> None:
    """No option is excluded on the audit's own say-so, and no rule quietly widens a refusal."""
    forbidden, _ = _ruled_options()
    unsupported: dict[str, str] = {}
    for strings, cls, _reason in ROWS:
        if cls != "excluded":
            continue
        if set(strings) & forbidden:
            continue
        counterpart = next((s for s in strings if s in _REFUSED_COUNTERPARTS), None)
        if counterpart and _REFUSED_COUNTERPARTS[counterpart] in forbidden:
            continue
        prose = next((s for s in strings if s in _REFUSED_IN_PROSE), None)
        if prose:
            decision, quote = _REFUSED_IN_PROSE[prose]
            assert quote in _decision(decision), (
                f"{prose} is excluded on a quotation {decision} no longer contains: {quote!r}"
            )
            continue
        unsupported[strings[0]] = "no decision forbids it, and it is not a listed counterpart"
    assert not unsupported, f"excluded without a decision behind it: {unsupported}"


def _built_table() -> dict[str, str]:
    """The typed options that already have a `DownloadRequest` field, read from the audit."""
    text = AUDIT.read_text(encoding="utf-8")
    header = text.index("| Option | `DownloadRequest` field |")
    table = text[header : text.index("\n\n", header)]
    return {
        m.group(1): m.group(2)
        for line in table.split("\n")[2:]
        if (m := re.match(r"^\| `([^`]+)` \| `([^`]+)` \|$", line.strip()))
    }


def test_the_already_built_options_name_fields_the_model_really_has() -> None:
    """`built` is a claim about the code, so it is checked against the code (`T183-R4`).

    The partition previously defined `built` as *whatever the nine tasks did not claim*, which is
    circular: swapping an unbuilt option for an already-built one left the counts intact and passed.
    """
    built = _built_table()
    assert built, "the audit states no already-built table"
    fields = {f.name for f in dataclasses.fields(DownloadRequest)}
    missing = {option: field for option, field in built.items() if field not in fields}
    assert not missing, f"named a DownloadRequest field that does not exist: {missing}"


def test_the_typed_tasks_partition_the_typed_options_with_no_field_yet() -> None:
    """`T-247`…`T-255` plus the built table cover the typed class exactly once (criterion 3)."""
    text = TASKS.read_text(encoding="utf-8")
    assigned: list[str] = []
    for task in [f"T-{n}" for n in range(247, 256)]:
        start = text.index(f"### {task} —")
        block = text[start : text.index("\n**Specific criteria:**", start)]
        stated = re.search(r"\*\*Options \((\d+)\):\*\*(.+?)$", block, re.S)
        assert stated, f"{task} states no option list"
        entries = _OPTION.findall(stated.group(2))
        assert len(entries) == int(stated.group(1)), (
            f"{task} says {stated.group(1)} options and lists {len(entries)}"
        )
        assigned += [spelling for entry in entries for spelling in entry.split("/")]

    duplicated = sorted({o for o in assigned if assigned.count(o) > 1})
    assert not duplicated, f"claimed by more than one task: {duplicated}"

    class_of = _class_of()
    not_typed = {
        o: class_of.get(o, "<not classified>") for o in assigned if class_of.get(o) != "typed"
    }
    assert not not_typed, f"assigned to a typed-field task and not classified typed: {not_typed}"

    built = set(_built_table())
    overlap = sorted(built & set(assigned))
    assert not overlap, (
        f"claimed by a typed-field task and already built: {overlap}. Building it twice is the "
        f"swap T183-R4 found — the counts stay right and the work is wrong."
    )

    # Rows, not spellings: a row may read `-x` `--extract-audio` and either side may be named.
    typed_rows = [strings for strings, cls, _ in ROWS if cls == "typed"]
    unaccounted = [r for r in typed_rows if not (set(r) & set(assigned)) and not (set(r) & built)]
    assert not unaccounted, (
        f"typed rows that no task claims and the built table does not list: {unaccounted}"
    )
    claimed = [r for r in typed_rows if set(r) & set(assigned)]
    assert len(claimed) == 44, f"the nine tasks cover {len(claimed)} typed rows, the audit says 44"
    assert len(typed_rows) - len(claimed) == 21, (
        f"{len(typed_rows) - len(claimed)} typed rows are already built, and the audit says 21"
    )
