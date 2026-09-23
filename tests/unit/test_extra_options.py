"""Which options the escape hatch admits, and why it refuses the rest (`T-184`, `REQ-031`).

The maintainer ruled **default-deny** on 2026-09-18: an option is usable only when the audit puts
it in a class the hatch may reach. These tests are about that decision and about the *timing* of
it — `T184-R3` established that `parse_options` exits the process on `--help` and loads an explicit
`--config-locations` file, so a refusal that ran after parsing would come too late to be one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tracks_and_trails.downloader.extra_options import (
    HAS_A_CONTROL,
    NO_EFFECT,
    NOT_AN_OPTION,
    NOT_RULED,
    TOGETHER,
    UNKNOWN_EFFECT,
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
    """A user may write either, and a boundary that only understood one would be porous."""
    admission = admit("--fragment-retries=10")

    assert admission.usable
    assert admission.accepted == ("--fragment-retries=10",)


def test_a_value_that_looks_like_an_option_is_still_a_value() -> None:
    """**Arity, not appearance**, decides what a word is.

    `--playlist-items -3` is an option and its value. A scanner that called every `-`-leading word
    an option would refuse the value as an unknown option, and the user would be told their own
    argument does not exist. The parser's own table says how many values each option takes, and
    building that table parses nothing.
    """
    admission = admit("--playlist-items -3")

    assert admission.usable, [
        (refusal.option, refusal.reason) for refusal in admit("--playlist-items -3").refusals
    ]
    assert admission.accepted == ("--playlist-items", "-3")


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

    An option whose control has not been built is reachable by no other route. `--limit-rate` has
    a field, so it is refused above; `--concurrent-fragments` does not, so it is usable here.
    """
    admission = admit("--concurrent-fragments 4")

    assert admission.usable, [(r.option, r.reason) for r in admission.refusals]


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


def test_options_that_contradict_each_other_are_refused_together() -> None:
    """`T184-R8`: each is valid alone, so asking one at a time accepted a field yt-dlp refuses.

    `--dateafter 20260920 --datebefore 20260901` asks for a window that ends before it starts.
    The seam said usable and the worker then refused it, which is the failure arriving after the
    user has left the dialog.
    """
    admission, argv = options_for("--dateafter 20260920 --datebefore 20260901")

    assert not admission.usable
    assert argv == ()
    assert [refusal.reason for refusal in admission.refusals] == [TOGETHER]


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
