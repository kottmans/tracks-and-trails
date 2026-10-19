"""Which options the escape hatch admits, and why it refuses the rest (`T-184`, `REQ-031`).

The maintainer ruled **default-deny** on 2026-09-18: an option is usable only when the audit puts
it in a class the hatch may reach. These tests are about that decision and about the *timing* of
it — `T184-R3` established that `parse_options` exits the process on `--help` and loads an explicit
`--config-locations` file, so a refusal that ran after parsing would come too late to be one.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from tracks_and_trails.downloader.extra_options import (
    ABBREVIATED,
    BAD_VALUE,
    HAS_A_CONTROL,
    NO_EFFECT,
    NOT_AN_OPTION,
    NOT_RULED,
    TOGETHER,
    UNKNOWN_EFFECT,
    WHOLE_FIELD,
    admit,
    option_arity,
    options_for,
    refusal_lines,
)
from tracks_and_trails.downloader.option_table import OPTION_CLASSES


def only_refusal(text: str) -> tuple[str, str]:
    """The single refusal `text` produces, as (option, reason)."""
    admission = admit(text)
    assert not admission.usable, f"{text!r} was admitted"
    assert len(admission.refusals) == 1, f"{text!r} produced {len(admission.refusals)} refusals"
    return admission.refusals[0].option, admission.refusals[0].reason


# --- what may be used --------------------------------------------------------------------------


def test_an_option_the_audit_puts_in_the_hatch_is_usable() -> None:
    """`--continue` is a `hatch` row, and the hatch is what that class is for."""
    admission = admit("--continue")

    assert admission.usable
    assert admission.accepted == ("--continue",)


def test_an_option_that_takes_a_value_keeps_it() -> None:
    """The value is not a stray word. `T184-R1`'s trap lives on this option, in the next half."""
    admission = admit("--fragment-retries 10")

    assert admission.usable
    assert admission.accepted == ("--fragment-retries", "10")


def test_the_equals_form_is_the_same_option() -> None:
    """A user may write either, and a boundary that only understood one would be porous.

    **Stored canonically since the 2026-09-27 redesign**: the option in full and its values as
    separate tokens, which is what `--fragment-retries 10` means to yt-dlp as well. Every consumer
    after admission then reads one spelling.
    """
    admission = admit("--fragment-retries=10")

    assert admission.usable
    assert admission.accepted == ("--fragment-retries", "10")


def test_a_value_that_looks_like_an_option_is_still_a_value() -> None:
    """**Arity, not appearance**, decides what a word is.

    `--age-limit -3` is an option and its value. A scanner that called every `-`-leading word an
    option would refuse the value as an unknown option, and the user would be told their own
    argument does not exist. The parser's own table says how many values each option takes, and
    building that table parses nothing. *(`--playlist-items -3` until `T-247` gave it a control.)*
    """
    admission = admit("--age-limit -3")

    assert admission.usable, [
        (refusal.option, refusal.reason) for refusal in admit("--age-limit -3").refusals
    ]
    assert admission.accepted == ("--age-limit", "-3")


def test_several_usable_options_are_kept_in_the_order_typed() -> None:
    admission = admit("--continue --fragment-retries 3")

    assert admission.usable
    assert admission.accepted == ("--continue", "--fragment-retries", "3")


# --- what may not, and what the user is told ---------------------------------------------------


def test_a_forbidden_option_is_refused_in_the_audit_s_own_words() -> None:
    """`REQ-031`: refused **with the reason**, never a bare "not permitted".

    The message a user sees is the audit's own third column, so the reason they get is the reason
    that was ruled — not a paraphrase written at the boundary and left to drift from it.
    """
    option, reason = only_refusal("--exec")

    assert option == "--exec"
    assert reason == OPTION_CLASSES["--exec"][1]
    assert "SEC-003" in reason, (
        f"the ruling behind the refusal is not in what the user is told: {reason}"
    )


def test_an_option_the_application_owns_is_refused_with_its_own_reason() -> None:
    """`-o/--output`: `build_options` sets `outtmpl`, and `T-034` contains it."""
    option, reason = only_refusal("--output %(title)s.%(ext)s")

    assert option == "--output"
    assert reason == OPTION_CLASSES["--output"][1]


def test_an_option_that_has_a_control_points_at_the_control() -> None:
    """`ARC-010`: where both name a user-owned key, the one with a visible control wins.

    `--proxy` is `typed` **and built**, so the hatch is not its route. The user is sent to the
    setting rather than told the option is forbidden, because it is not.
    """
    option, reason = only_refusal("--proxy http://example.invalid:8080")

    assert option == "--proxy"
    assert reason == HAS_A_CONTROL


def test_a_typed_option_with_no_control_yet_is_usable() -> None:
    """The other half of the same rule, and the reason `typed` is an admitted class.

    An option whose control has not been built is reachable by no other route. `--proxy` has a
    field, so it is refused above; `--concurrent-fragments` does not, so it is usable here.
    """
    admission = admit("--concurrent-fragments 4")

    assert admission.usable, [(r.option, r.reason) for r in admission.refusals]


def _every_spelling_of_a_built_option() -> list[tuple[str, int]]:
    """Each spelling of each option the audit's built table names, with how many values it takes.

    Read from yt-dlp's parser and the audit's hand-listed table, **not** from `TYPED_WITH_A_FIELD`,
    which is what is being checked: a test reading the generated table would agree with it whatever
    it said.
    """
    import importlib.util

    from yt_dlp.options import create_parser

    tool = Path(__file__).resolve().parents[2] / "tools" / "ytdlp_option_table.py"
    specification = importlib.util.spec_from_file_location("ytdlp_option_table_t361", tool)
    assert specification is not None and specification.loader is not None
    generator = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = generator
    specification.loader.exec_module(generator)
    listed = set(generator.built_typed_options())
    found: list[tuple[str, int]] = []
    for group in create_parser().option_groups:
        for option in group.option_list:
            spellings = (*option._short_opts, *option._long_opts)
            if listed & set(spellings):
                takes = option.nargs if option.takes_value() else 0
                found.extend((spelling, takes or 0) for spelling in spellings)
    return sorted(found)


@pytest.mark.parametrize(("spelling", "takes"), _every_spelling_of_a_built_option())
def test_every_spelling_of_an_option_with_a_control_is_refused_for_it(
    spelling: str, takes: int
) -> None:
    """**`T-361`.** The hatch refused `-r` and admitted `--limit-rate`, the same parser option.

    The built table names one spelling per option and the hatch refuses by the spelling typed, so
    an alias was admitted; the generator skips a built option, so the hatch then produced nothing
    for it, which `REQ-031` forbids. Measured at `d2480fa`: `--limit-rate`, `--retries`,
    `--extract-audio`, `--add-metadata` and `--srt-langs` were all usable and all dropped.
    """
    text = shlex.join([spelling, *["1"] * takes])

    refusals = admit(text).refusals

    assert [(refusal.option, refusal.reason) for refusal in refusals] == [
        (spelling, HAS_A_CONTROL)
    ], f"{spelling} is not refused for its control"


def test_an_option_no_ruling_covers_is_refused_rather_than_allowed() -> None:
    """**Default-deny, which is the ruling of 2026-09-18.**

    `--all-subs` is one of the suppressed spellings the audit does not reach. Under default-allow
    it would be usable because no refusal list names it, and every future yt-dlp release would add
    more of them. A blacklist over a surface that grows on somebody else's schedule fails open.
    """
    option, reason = only_refusal("--all-subs")

    assert option == "--all-subs"
    assert reason == NOT_RULED


def test_an_option_that_changes_nothing_is_refused_rather_than_ignored() -> None:
    """Maintainer ruling of 2026-09-20, measured rather than assumed.

    `--post-overwrites` is a `hatch` row, so its class admits it — and comparing two values of it
    produces no key at all at this yt-dlp release. Accepting it would accept an option and then do
    nothing, which is `REQ-031`'s "accepted and silently dropped" with extra steps, and leaves the
    criterion "a valid option reaches yt-dlp, proved by the option dictionary" with nothing to
    prove. The user is told the fact instead.
    """
    option, reason = only_refusal("--post-overwrites")

    assert option == "--post-overwrites"
    assert reason == NO_EFFECT


def test_an_option_whose_effect_cannot_be_measured_is_refused() -> None:
    """The stronger case: not "it does nothing" but "this cannot say what it does".

    `--ap-mso` needs a real television provider id to validate, so no value the generator can
    supply exercises it, and its destinations were never measured. Refusing is the honest answer;
    admitting it would mean merging keys nobody has seen.
    """
    option, reason = only_refusal("--ap-mso x")

    assert option == "--ap-mso"
    assert reason == UNKNOWN_EFFECT


def test_an_option_with_a_measured_destination_is_still_usable() -> None:
    """The control for the two above: refusing the unprovable did not refuse everything."""
    assert admit("--continue").usable
    assert admit("--fragment-retries 10").usable


def test_a_word_that_is_not_an_option_is_refused() -> None:
    """A URL belongs in the URL box. A value with no option is not something to guess about."""
    option, _ = only_refusal("https://example.invalid/watch")

    assert option == "https://example.invalid/watch"


def test_an_option_yt_dlp_does_not_have_is_refused() -> None:
    option, reason = only_refusal("--invent-a-flag")

    assert option == "--invent-a-flag"
    assert reason == NOT_AN_OPTION


def test_an_option_missing_its_value_is_refused() -> None:
    """At edit time, which is the point: the bytes are not spent yet."""
    option, reason = only_refusal("--fragment-retries")

    assert option == "--fragment-retries"
    assert "value" in reason


def test_an_unclosed_quote_is_reported_as_what_it_is() -> None:
    """`shlex` is the reader a shell uses, so the user is told the quoting is wrong."""
    _, reason = only_refusal('--match-filter "still open')

    assert "complete command line" in reason


def test_an_unclosed_quote_does_not_repeat_what_was_typed() -> None:
    """`T184-R6`: the refusal named the first forty characters of the field.

    An unclosed quote is exactly where a header value is most likely to be, so forty characters of
    `--add-headers "Authorization: Bearer …` was most of a credential, in a refusal that
    `BAD_VALUE`'s own note says may be repeated somewhere durable.
    """
    option, reason = only_refusal('--add-headers "Authorization: Bearer T184_QUOTE_CANARY')

    assert option == WHOLE_FIELD
    assert "T184_QUOTE_CANARY" not in option + reason


def test_one_refusal_refuses_the_whole_field() -> None:
    """`REQ-031`: never "accepted and silently dropped".

    A user who typed three options and had the middle one quietly removed would be running
    something they did not write. Every refusal is collected, so one trip through the dialog shows
    everything that is wrong, and nothing is usable until none of it is.
    """
    admission = admit('--continue --exec "touch /tmp/x" --fragment-retries 3')

    assert not admission.usable
    assert admission.accepted == (), "a field with a refusal in it still offered options to run"
    assert [refusal.option for refusal in admission.refusals] == ["--exec"]


def test_the_refusal_names_the_spelling_the_user_typed() -> None:
    """A user who wrote `-c` is told about `-c`, and one who wrote `--continue` about that.

    Both are one audit row, so the *reason* is shared; the name in front of it is theirs.
    """
    short, short_reason = only_refusal("-a list.txt")
    long, long_reason = only_refusal("--batch-file list.txt")

    assert short == "-a"
    assert long == "--batch-file"
    assert short_reason == long_reason


# --- the timing, which is what `T184-R3` is about ----------------------------------------------


@pytest.mark.parametrize("text", ["-h", "--help", "--version"])
def test_an_option_that_would_exit_the_process_is_refused_without_running_it(text: str) -> None:
    """**It refuses rather than exits**, and that is a fact about when admission happens.

    `parse_options(['--help'])` raises `SystemExit`: the process would be gone before any refusal
    could be issued. Admission reads the raw tokens instead, so this returns an answer. If the
    order were ever reversed, this test would not fail — it would take the interpreter with it.
    """
    option, reason = only_refusal(text)

    assert option == text
    assert len(reason) > 10


def test_a_config_file_is_refused_without_being_read(tmp_path: Path) -> None:
    """`T184-R3`: an explicit `--config-locations FILE` **is** loaded by `parse_options`.

    Automatic discovery is suppressed when an argv is passed; an explicit path is not. So a
    refusal that ran after parsing would be issued by a process that had already read the user's
    file. This asserts the file is untouched, using a path that records being opened.
    """
    secret = tmp_path / "config.conf"
    secret.write_text("--fragment-retries 37\n", encoding="utf-8")
    before = secret.stat().st_atime_ns

    option, reason = only_refusal(f"--config-locations {secret}")

    assert option == "--config-locations"
    assert reason == OPTION_CLASSES["--config-locations"][1]
    assert secret.stat().st_atime_ns == before, "the config file was read before it was refused"


def test_asking_whether_a_preset_without_a_hatch_needs_ffmpeg_loads_no_parser() -> None:
    """`T184-R14`'s cost bound: the offer asks this of every preset, and most carry no hatch."""
    source = (
        "import sys;"
        "from tracks_and_trails.core.presets import BUILT_IN_PRESETS;"
        "from tracks_and_trails.downloader.extra_options import preset_needs_ffmpeg;"
        "[preset_needs_ffmpeg(preset) for preset in BUILT_IN_PRESETS];"
        "print('yt_dlp' in sys.modules)"
    )
    finished = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )

    assert finished.stdout.strip() == "False", (
        f"asking about an empty hatch loaded yt-dlp: {finished.stdout!r} {finished.stderr!r}"
    )


def test_the_option_table_is_pinned_data_rather_than_a_live_parser() -> None:
    """Admission imports **no** yt-dlp, which is an architecture rule and not a preference.

    `tests/unit/test_layering.py` confines `yt_dlp` imports to `worker.py` and `ytdlp_adapter.py`
    so upstream churn stays absorbable (`NFR-008`). This module read `create_parser()` at first and
    that test refused it. The table is generated instead, and
    `tests/unit/test_option_table.py` regenerates it against the real parser, so a pinned arity
    that disagrees with the installed release fails there rather than answering wrongly here.
    """
    arity = option_arity()

    assert arity["--continue"] == 0, "a flag was recorded as taking a value"
    assert arity["--fragment-retries"] == 1, "an option with a value was recorded as a flag"
    assert "--exec" in arity, "the table does not cover the options it has to refuse"


def test_admitting_options_pulls_in_no_yt_dlp() -> None:
    """The layering rule, asserted as the behaviour it exists to produce.

    `test_layering.py` reads the import statements; this runs the module. A lazy import inside a
    function would satisfy the reader and still cost a user 25 MiB the moment they typed an
    option, so the question is what a real admission actually loads.

    A subprocess, because this test session has imported yt-dlp for other reasons long before now.
    """
    source = (
        "import sys;"
        "from tracks_and_trails.downloader.extra_options import admit;"
        "admit('--continue --fragment-retries 5 --exec x');"
        "print('yt_dlp' in sys.modules)"
    )
    finished = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )

    assert finished.stdout.strip() == "False", (
        f"admission imported yt-dlp after all: {finished.stdout!r} {finished.stderr!r}"
    )


def test_the_one_call_the_interface_makes_gives_both_halves() -> None:
    """`options_for` is what the dialog calls: the refusals to show, and the tokens to store."""
    admission, argv = options_for("--continue --fragment-retries 10")

    assert admission.usable
    assert argv == ("--continue", "--fragment-retries", "10")


@pytest.mark.parametrize(
    ("text", "option"),
    [
        ("--fragment-retries nope", "--fragment-retries"),
        ("--concurrent-fragments 0", "--concurrent-fragments"),
        # **And the valid option beside it goes too** — the field is refused whole, so a user is
        # never left with half of what they typed running.
        ("--fragment-retries 7 --concurrent-fragments 0", "--concurrent-fragments"),
    ],
)
def test_a_value_the_parser_will_not_take_is_refused_at_the_seam(text: str, option: str) -> None:
    """`T184-R8`, the High finding: these reported **usable** with no refusal and no options.

    Admission knows which options may be used; only the parser knows whether `nope` is a number.
    Without asking it, the field said yes and produced nothing, which discards the user's intent
    in silence — and took any valid option typed beside it along.
    """
    admission, argv = options_for(text)

    assert not admission.usable, f"{text!r} was accepted with nothing to show for it"
    assert argv == ()
    assert [refusal.option for refusal in admission.refusals] == [option]


@pytest.mark.parametrize(
    ("text", "option"),
    [
        ('--match-filters "duration<5 & T184_PART ~~ x"', "--match-filters"),
        ('--break-match-filters "T184_PART >>"', "--break-match-filters"),
        ("--encoding T184-no-such-codec", "--encoding"),
    ],
)
def test_a_value_yt_dlp_reads_only_when_the_job_runs_is_checked_at_edit_time(
    text: str, option: str
) -> None:
    """`T184-R8`'s class: the parser takes these values as text and reads them later.

    A filter is read part by part as each item arrives, and an encoding is looked up when output is
    written. Measured 2026-09-26: each passed the whole-line parse and then failed the job, which is
    a malformed field failing after the user has left the dialog.
    """
    admission, argv = options_for(text)

    assert not admission.usable, f"{text!r} was accepted and would fail the job instead"
    assert argv == ()
    assert [refusal.option for refusal in admission.refusals] == [option]
    assert all("T184" not in line for line in refusal_lines(admission)), "the value was repeated"


@pytest.mark.parametrize(
    "text",
    [
        "--match-filters \"duration>100 & title~='(?i)talk' & !is_live\"",
        '--match-filters "like_count>?100" --break-match-filters "upload_date<20200101"',
        "--encoding utf-8",
    ],
)
def test_a_value_yt_dlp_can_read_is_still_accepted(text: str) -> None:
    """The check asks yt-dlp's own question with no item, so every field is merely missing."""
    admission, argv = options_for(text)

    assert admission.usable, refusal_lines(admission)
    assert argv


@pytest.mark.parametrize(
    "text",
    [
        "--download-archive archive.txt",
        "--cache-dir=cache",
        "--netrc-location .netrc",
        "--client-certificate certs/me.pem",
        # yt-dlp expands nothing for a certificate, so `~` stays a directory named `~`.
        "--client-certificate-key ~/me.key",
    ],
)
def test_a_relative_path_is_refused_where_it_was_typed(text: str) -> None:
    """`ARC-010`, amended 2026-09-27: yt-dlp resolves it against wherever this was started.

    Measured the day before: a relative `--download-archive` wrote its archive into the working
    directory of the process, which a user never chose. A probe left one in this repository.
    """
    admission = admit(text)

    assert not admission.usable, f"{text!r} would land wherever the application was started"
    [refusal] = admission.refusals
    assert refusal.option == text.split()[0].partition("=")[0]
    assert "full path" in refusal.reason
    assert text.split("=")[-1].split()[-1] not in refusal.reason, "the path was repeated back"


@pytest.mark.parametrize(
    "template",
    [
        "--download-archive {absolute}",
        "--client-certificate {absolute}",
        "--download-archive ~/archive.txt",
        "--cache-dir $T184_MEDIA/cache",
        "--netrc-location ~",
    ],
)
def test_a_path_absolute_once_yt_dlp_expands_it_is_accepted(
    template: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Judged as yt-dlp will use it: `~` and variables for the archive and cache, `~` for netrc.

    The absolute paths come from `tmp_path` so they are absolute on Windows too, where a path with
    no drive is not.
    """
    monkeypatch.setenv("T184_MEDIA", str(tmp_path))
    text = template.format(absolute=shlex.quote(str(tmp_path / "archive.txt")))

    admission = admit(text)

    assert admission.usable, refusal_lines(admission)


@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("-N4", ("-N", "4")),
        # *A value that is not a number, attached* was `-I1:3`, then `-Sres:720`; `T-247` and
        # `T-250` gave both a control, and no admitted short option takes text any more.
        ("-cN4", ("-c", "-N", "4")),
        ('--replace-in-metadata=title foo ""', ("--replace-in-metadata", "title", "foo", "")),
        ('"--add-headers=Referer: T184"', ("--add-headers", "Referer: T184")),
    ],
)
def test_the_seam_reads_a_command_line_the_way_yt_dlp_s_parser_does(
    text: str, canonical: tuple[str, ...]
) -> None:
    """`T184-R8`, redesigned 2026-09-27: one tokenizer, optparse's own rules, one canonical argv.

    Three hand-written splits disagreed with yt-dlp. Attached short values (`-N4`), clusters
    (`-cN4`) and an inline first value followed by the rest were refused or truncated; yt-dlp's
    parser accepts every one. The canonical form spells each option in full with its values as
    separate tokens, and means exactly what was typed. Abbreviated long options are refused
    instead (`ARC-010`, amended 2026-10-10), so none is here.
    """
    from yt_dlp import parse_options

    admission, argv = options_for(text)

    assert admission.usable, refusal_lines(admission)
    assert argv == canonical
    typed = repr(parse_options(shlex.split(text)).ydl_opts)
    assert repr(parse_options(list(argv)).ydl_opts) == typed, "the canonical form means otherwise"


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("--continue=yes", "--continue"),
        ("--no-", "--no-"),
        # An abbreviation of a forbidden option is refused, as every abbreviation is.
        ("--exec-b x", "--exec-b"),
        # A cluster is decided flag by flag, so a refused flag inside one is still refused.
        ("-ci", "-i"),
    ],
)
def test_the_seam_refuses_what_yt_dlp_s_parser_refuses_or_forbids(text: str, named: str) -> None:
    admission = admit(text)

    assert not admission.usable, f"{text!r} was admitted"
    assert named in [refusal.option for refusal in admission.refusals], admission.refusals


@pytest.mark.parametrize(
    ("text", "names"),
    [
        # The review's three (`T184-R8`, 2026-09-27). yt-dlp accepts the first two, because aliases
        # of one option are not ambiguous to its parser, and refuses the third as ambiguous; the
        # sixth round refused the first two and quietly turned the third into `--cache-dir`.
        ("--convert-s srt", ("--convert-sub", "--convert-subs", "--convert-subtitles")),
        ("--clean-info", ("--clean-info-json", "--clean-infojson")),
        ("--ca /tmp/t184-review-cache", ("--cache-dir",)),
        # A prefix of exactly one name, which the sixth round admitted as that option.
        ("--fragment-retr 5", ("--fragment-retries",)),
        ("--fragment-retr=5", ("--fragment-retries",)),
        ("--exec-b x", ("--exec-before-download",)),
    ],
)
def test_an_abbreviated_long_option_is_refused_naming_its_full_spellings(
    text: str, names: tuple[str, ...]
) -> None:
    """`ARC-010`, amended 2026-10-10: a long option is typed in full.

    Two designs that resolved prefixes disagreed with yt-dlp's parser, which bends optparse's rule.
    Refusing every abbreviation never admits what yt-dlp would refuse or read differently, and
    the refusal names what to type instead.
    """
    admission = admit(text)

    assert admission.accepted == (), f"{text!r} was admitted"
    [refusal] = admission.refusals
    assert refusal.option == text.split()[0].partition("=")[0]
    assert refusal.reason.startswith(ABBREVIATED)
    for name in names:
        assert name in refusal.reason, f"{name} is not offered: {refusal.reason!r}"


@pytest.mark.parametrize(
    "text",
    [
        "--video-pass T184_ABBREVIATED_CANARY",
        '--add-head "Authorization: Bearer T184_ABBREVIATED_CANARY"',
        "--video-pass=T184_ABBREVIATED_CANARY",
    ],
)
def test_an_abbreviation_does_not_repeat_the_value_typed_after_it(text: str) -> None:
    """`T184-R6`'s class, kept closed by the 2026-10-10 change.

    The sixth round read a unique prefix as its option, values included. Refused without reading
    them, the value would have been the next word, and a stray word is refused **by name**: the
    password would be shown back and could be repeated wherever a refusal is.
    """
    admission = admit(text)

    assert len(admission.refusals) == 1, admission.refusals
    for line in refusal_lines(admission):
        assert "CANARY" not in line, f"the value was repeated back: {line!r}"


def test_every_exact_long_name_is_still_read_as_itself() -> None:
    """The other direction: refusing abbreviations must not refuse a name typed in full.

    Every long spelling in the inventory, with as many values as it takes. Each may still be
    refused for its class or its value, but never as an abbreviation of something else, which a
    name that is also a prefix of a longer one (`--convert-sub`) would be under a careless rule.
    """
    arity = option_arity()
    abbreviated = [
        spelling
        for spelling in arity
        if spelling.startswith("--")
        and any(
            refusal.reason.startswith(ABBREVIATED)
            for refusal in admit(shlex.join([spelling, *["T184"] * arity[spelling]])).refusals
        )
    ]

    assert not abbreviated, f"refused as abbreviations though typed in full: {abbreviated}"


def test_an_empty_inline_value_is_a_value_and_this_one_fails_the_job() -> None:
    """`--match-filters=` is not a missing value. It is an empty filter, and yt-dlp's
    `match_str('')` raises *Invalid filter part ''* on the first item, so it is a bad value."""
    assert admit("--match-filters=").accepted == ("--match-filters", "")

    admission, argv = options_for("--match-filters=")

    assert argv == ()
    assert [(r.option, r.reason) for r in admission.refusals] == [("--match-filters", BAD_VALUE)]


@pytest.mark.parametrize(
    ("text", "usable"),
    [
        ("--encoding T184-nope --encoding utf-8", True),
        ("--encoding utf-8 --encoding T184-nope", False),
        ('--match-filters "duration>5" --match-filters "title ~~ x"', False),
    ],
)
def test_a_value_read_later_is_judged_by_what_yt_dlp_keeps(text: str, usable: bool) -> None:
    """`T184-R8`: the effective value after every repeat, not each occurrence.

    yt-dlp takes the last `--encoding`, so a bad one overwritten is harmless. Filters accumulate,
    so every one is kept and every one is checked.
    """
    admission, _ = options_for(text)

    assert admission.usable is usable, refusal_lines(admission)


#: An ordinary item, for evaluating a filter the way yt-dlp does as each one arrives.
_AN_ITEM: dict[str, object] = {
    "title": "T184 ordinary [title] a&b",
    "uploader": "someone",
    "duration": 120,
    "is_live": False,
}


@pytest.mark.parametrize(
    ("text", "option", "evaluated"),
    [
        ('--match-filters "title~=["', "--match-filters", "title~=["),
        ('--break-match-filters "title~=["', "--break-match-filters", "title~=["),
        # `match_str` stops at the first part that is false, so a comparison in front hides the
        # pattern from a check that only ever evaluates the whole filter.
        ('--match-filters "duration>5 & title~=["', "--match-filters", "duration>5 & title~=["),
        (
            '--match-filters "title~=T184" --match-filters "uploader~=(unclosed"',
            "--match-filters",
            "uploader~=(unclosed",
        ),
    ],
)
def test_a_filter_pattern_yt_dlp_cannot_compile_is_refused(
    text: str, option: str, evaluated: str
) -> None:
    """`T184-R8`, seventh round: parsing a filter part is not compiling its pattern.

    The sixth round asked `match_str` with every field missing, which answers before `re.search`
    is reached. `title~=[` passed the seam, the stored-options check and the editor, and raised
    `PatternError` on the first item with a title. The last line is that item, evaluated as yt-dlp
    evaluates it, so the refusal is shown to stand for a real failure.
    """
    from yt_dlp.utils import match_str

    admission, argv = options_for(text)

    assert argv == ()
    assert [(refusal.option, refusal.reason) for refusal in admission.refusals] == [
        (option, BAD_VALUE)
    ]
    with pytest.raises(re.error):
        match_str(evaluated, _AN_ITEM)


@pytest.mark.parametrize(
    "text",
    [
        '--match-filters "title~=(?i)^t184"',
        "--match-filters 'title~=\\[title\\]'",
        '--match-filters "title*=a\\&b"',
        '--match-filters "title~=T184" --match-filters "uploader~=some(one)?"',
        "--break-match-filters \"title~='(?P<word>ordinary)'\"",
    ],
)
def test_a_filter_pattern_yt_dlp_can_compile_is_still_accepted(text: str) -> None:
    """The other direction: valid patterns, escapes, quoting and repeats keep passing.

    Each admitted filter is then evaluated against an ordinary item, as yt-dlp will, and must
    not raise: agreement between the application's helpers is not the proof.
    """
    from yt_dlp.utils import match_str

    admission, argv = options_for(text)

    assert admission.usable, refusal_lines(admission)
    for value in argv[1::2]:
        match_str(value, _AN_ITEM)


#: Patterns `re.compile` cannot build, and not with `re.error` (`T184-R8`, eighth round).
_TOO_MANY: Final = "a{4294967296}"
_TOO_DEEP: Final = "(" * 500 + "a" + ")" * 500

#: Each spelling that carries a pattern, with each failure: the two filters, and the two options
#: whose patterns yt-dlp compiles while it parses, outside its own `re.error` handling.
UNCOMPILABLE: Final = [
    pytest.param(option, f"{prefix}{pattern}", pattern, raised, id=f"{option}-{raised.__name__}")
    for option, prefix in (
        ("--match-filters", "title~="),
        ("--break-match-filters", "title~="),
        ("--remove-chapters", ""),
        ("--download-sections", ""),
    )
    for pattern, raised in ((_TOO_MANY, OverflowError), (_TOO_DEEP, RecursionError))
]


@pytest.mark.parametrize(("option", "value", "pattern", "raised"), UNCOMPILABLE)
def test_a_pattern_re_cannot_compile_is_refused_where_it_is_typed(
    option: str, value: str, pattern: str, raised: type[Exception]
) -> None:
    """`T184-R8`, eighth round: refused by name and value-free, rather than raised.

    `re.compile` raises `OverflowError` and `RecursionError` for these, which are not `re.error`,
    and yt-dlp catches only that. They escaped `options_for`, so the editor's check raised instead
    of refusing. The first lines show each is a real compile failure, decided by the text alone.
    """
    with pytest.raises(raised):
        re.compile(pattern)

    admission, argv = options_for(shlex.join([option, value]))

    assert argv == ()
    assert [(refusal.option, refusal.reason) for refusal in admission.refusals] == [
        (option, BAD_VALUE)
    ]
    assert all("4294967296" not in line and "((((" not in line for line in refusal_lines(admission))


@pytest.mark.parametrize(
    "text",
    [
        "--video T184_R17_CANARY",
        '--add "Authorization: Bearer T184_R17_CANARY"',
        "--video=T184_R17_CANARY",
        "--typo T184_R17_CANARY",
        "--typo first T184_R17_CANARY",
    ],
)
def test_a_refused_option_of_unknown_arity_keeps_the_words_after_it(text: str) -> None:
    """`T184-R17`: a prefix whose candidates disagree read no values, so the value came next as a
    stray word and was refused **by name**. An option the inventory does not have did the same.
    Nobody can say how many words are its values, so the words up to the next option are."""
    admission = admit(text)

    [refusal] = admission.refusals
    assert refusal.option == text.split()[0].partition("=")[0]
    assert all("CANARY" not in line for line in refusal_lines(admission))


def test_the_next_option_is_still_decided_after_one_of_unknown_arity() -> None:
    """Keeping the words stops at the next word that begins with `-`, so nothing after is lost."""
    admission = admit("--video T184_R17_CANARY --exec x")

    assert [refusal.option for refusal in admission.refusals] == ["--video", "--exec"]


def test_yt_dlp_refuses_a_line_whose_options_are_each_valid_alone() -> None:
    """`T184-R8`: each is valid alone, so asking one at a time accepted a line yt-dlp refuses.

    `--dateafter 20260920 --datebefore 20260901` asks for a window that ends before it starts. The
    seam said usable and the worker then refused it, which is the failure arriving after the user
    has left the dialog. **Asked of the parser's check directly since `T-247`**, which refuses both
    dates in the hatch for their control, so the pair no longer reaches it through admission.
    """
    from tracks_and_trails.downloader.ytdlp_adapter import unparseable

    argv = ("--dateafter", "20260920", "--datebefore", "20260901")

    assert unparseable(argv, [argv[:2], argv[2:]]) == (True, None)


def _contradicting(monkeypatch: pytest.MonkeyPatch) -> None:
    """yt-dlp refusing every line as a whole and no option alone: a contradiction, stood in.

    **No admitted pair is known to contradict** since `T-247` refused the dates for their control,
    and the seam still has to say what one is called.
    """
    from tracks_and_trails.downloader import ytdlp_adapter

    monkeypatch.setattr(ytdlp_adapter, "unparseable", lambda _argv, _groups: (True, None))


def test_options_that_contradict_each_other_are_refused_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seam's half of `T184-R8`: a line refused with no option to blame is refused whole."""
    _contradicting(monkeypatch)

    admission, argv = options_for("--continue --fragment-retries 3")

    assert not admission.usable
    assert argv == ()
    assert [refusal.reason for refusal in admission.refusals] == [TOGETHER]


def test_contradicting_options_are_named_by_spelling_and_never_by_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T184-R6`: when no option fails alone, the refusal named forty raw characters of the field.

    With a header first, that was `--add-headers "Authorization: Bearer SEC`, a credential cut
    short. The spellings are what the user needs to find and the only part that is safe to repeat.
    """
    _contradicting(monkeypatch)

    admission, _ = options_for(
        '--add-headers "Authorization: Bearer T184_TOGETHER_CANARY" --fragment-retries 3'
    )

    [refusal] = admission.refusals
    assert refusal.reason == TOGETHER
    assert refusal.option == "--add-headers, --fragment-retries"
    assert "CANARY" not in refusal.option


def test_an_option_repeated_with_a_good_value_last_is_accepted() -> None:
    """The other direction of the same finding, and the reason the whole line has to decide.

    The real command line takes the last value, so `--fragment-retries nope --fragment-retries 7`
    is seven retries. Asking one option at a time refused it on the first, which would have
    rejected a field yt-dlp accepts.
    """
    admission, argv = options_for("--fragment-retries nope --fragment-retries 7")

    assert admission.usable, [(r.option, r.reason) for r in admission.refusals]
    assert argv == ("--fragment-retries", "nope", "--fragment-retries", "7")


def test_the_refusal_for_a_bad_value_does_not_repeat_the_value() -> None:
    """`T184-R6`: the parser's own complaint quotes the value, and a value can be a credential."""
    admission, _ = options_for("--add-headers @@@not-a-header@@@")

    if not admission.usable:
        assert all("@@@" not in refusal.reason for refusal in admission.refusals), (
            f"the value was repeated back: {[r.reason for r in admission.refusals]}"
        )


def test_a_refused_field_produces_nothing_to_store() -> None:
    """A caller cannot store options from a field the user has not got right yet."""
    admission, argv = options_for('--exec "touch /tmp/x"')

    assert not admission.usable
    assert argv == ()


def test_an_empty_field_parses_nothing_and_loads_nothing() -> None:
    """The common case. **Nothing is imported for a user who never opens the hatch.**

    The maintainer approved 0.13 s and 25 MiB for edit-time validation on the understanding that
    only a user who types an option pays it. This asserts the empty field costs nothing, in a
    subprocess because this session has long since imported yt-dlp for other reasons.
    """
    source = (
        "import sys;"
        "from tracks_and_trails.downloader.extra_options import options_for;"
        "options_for('');"
        "print('yt_dlp' in sys.modules)"
    )
    finished = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )

    assert finished.stdout.strip() == "False", (
        f"an empty hatch field loaded yt-dlp: {finished.stdout!r} {finished.stderr!r}"
    )


def test_a_refused_field_does_not_load_the_parser_either() -> None:
    """Refusal comes before the parser, so a refused field never reaches the import (`T184-R3`)."""
    source = (
        "import sys;"
        "from tracks_and_trails.downloader.extra_options import options_for;"
        "options_for('--exec x');"
        "print('yt_dlp' in sys.modules)"
    )
    finished = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )

    assert finished.stdout.strip() == "False", "a refused field still paid for the parser"


def test_the_refusals_read_as_lines_a_person_can_be_shown() -> None:
    lines = refusal_lines(admit('--exec "touch /tmp/x"'))

    assert len(lines) == 1
    assert lines[0].startswith("--exec: ")
