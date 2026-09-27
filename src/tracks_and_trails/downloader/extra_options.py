"""The escape hatch: additional yt-dlp options, admitted or refused (`T-184`, `REQ-031`).

**What this module decides.** A user types command-line options into one field. This says which of
them may be used and why each refused one is refused, in the audit's own words. What the admitted
ones *mean* — the option dictionary they produce — is the second half of the task and is not here
yet.

**Default-deny, ruled by the maintainer on 2026-09-18.** An option is admitted only when the audit
puts it in a class the hatch may reach. Everything else is refused, including the 34 suppressed
spellings nobody has ruled on, because the refusal list guards a security boundary and the surface
behind it grows on yt-dlp's schedule rather than this project's. A blacklist over a growing surface
fails open.

**The parser never sees a refused option, and that is the point** (`T184-R3`). `parse_options`
has side effects before it has a result: `--help` and `--version` raise `SystemExit`, and an
explicit `--config-locations FILE` is **loaded**, because `parseOpts` calls `load_configs()` on the
root config. A refusal that ran after parsing would be a refusal issued by a process that had
already exited or already read the user's file. So admission happens on the raw tokens, using only
the parser's table of what each option is called and how many values it takes — building that table
parses nothing.

**Layering, and a correction to what this module first did.** It read the parser's option table
by importing `yt_dlp.options` here. `tests/unit/test_layering.py` refused that: only `worker.py`
and `ytdlp_adapter.py` may import yt-dlp, so upstream churn stays absorbable (`NFR-008`). The rule
is the better design. The table is **generated** into `option_table.py` instead, so **admission
imports no yt-dlp at all** — the decision about what a user typed is pure data, the 25 MiB the
maintainer was asked to approve is not spent here, and a mismatch between the pin and the
installed release fails a test rather than shipping a wrong answer.

The *parse* half, which turns admitted options into the dictionary the worker receives, does need
`parse_options`. That is the half the 2026-09-20 ruling on edit-time validation is really about,
and it is not in this module.
"""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from tracks_and_trails.downloader.option_table import (
    EFFECT_UNKNOWN,
    NO_OBSERVABLE_EFFECT,
    OPTION_ARITY,
    OPTION_CLASSES,
    TYPED_WITH_A_FIELD,
)

#: The audit classes the hatch may reach.
#:
#: `hatch` is what the class exists for. `typed` is here because an option whose control has not
#: been built yet is unreachable by any other route, and `REQ-030`'s coverage claim is about today
#: rather than about the phase's end — but only while it *has* no control: `TYPED_WITH_A_FIELD`
#: takes the built ones back out, because `ARC-010` gives the visible control the win.
ADMITTED_CLASSES: Final = frozenset({"hatch", "typed"})

#: What a user is told when they type an option that has a control of its own.
HAS_A_CONTROL: Final = "There is a setting for this. Use it instead, so the value is shown to you."

#: What a user is told when the option is not one yt-dlp documents at this version.
NOT_AN_OPTION: Final = "yt-dlp has no option by this name at the version this application uses."

#: What a user is told when the parser knows the spelling but no ruling covers it.
#:
#: The suppressed spellings the audit does not reach (`T-184`'s own pinned set of 39). They are
#: deprecated aliases and command-line plumbing, every one reachable another way, and each can be
#: permitted later by a ruling of its own. Until then default-deny answers for them.
NOT_RULED: Final = (
    "This option has no ruling behind it yet, so this application does not pass it on."
)

#: What a user is told when the option does nothing this application can see.
#:
#: Measured rather than assumed: `tools/ytdlp_option_table.py` compares two values of the option
#: and finds no key that changes. Ten admitted options are in that position at this yt-dlp release
#: — several are negations that restore a default, and `--post-overwrites` is one the audit's
#: Finding 7 singled out. The maintainer ruled on 2026-09-20 that they are refused rather than
#: accepted as silent no-ops, because a user told nothing has no way to learn the option was idle.
NO_EFFECT: Final = "This option changes nothing in the version of yt-dlp this application uses."

#: What a user is told when the option is fine but its value is not.
#:
#: **Value-free on purpose** (`T184-R6`): the message names the option and stops there, because a
#: hatch value can be `Authorization: Bearer …` and a refusal may be repeated somewhere durable.
BAD_VALUE: Final = "yt-dlp will not accept the value given for this option."

#: What a user is told when each option is fine alone and they contradict one another.
#:
#: `--dateafter 20260920 --datebefore 20260901` asks for a window that ends before it starts.
#: Neither option is wrong; the pair is.
TOGETHER: Final = "These options are each valid, but yt-dlp will not accept them together."

#: What a refusal names when it is about the whole field rather than one option.
#:
#: **Never the text itself** (`T184-R6`). Two refusals used to name `text.strip()[:40]`: an
#: unclosed quote, and options that are each valid but contradict one another. Forty characters of
#: `--add-headers "Authorization: Bearer …"` is most of a credential.
WHOLE_FIELD: Final = "The whole field"

#: What a user is told when the effect cannot be measured at all.
UNKNOWN_EFFECT: Final = (
    "This application cannot tell what this option would change, so it does not pass it on."
)

#: What a user is told when a path option is given a relative path (`ARC-010`, amended 2026-09-27).
#:
#: yt-dlp resolves one against the process's working directory, which at a terminal is where the
#: user stands and here is wherever the application was started. Value-free, like `BAD_VALUE`.
NOT_A_FULL_PATH: Final = (
    "Give a full path. A relative one would be taken from wherever this application was started."
)

#: How yt-dlp expands a path option before it opens it; a spelling not listed is used as written.
#:
#: `expand_path`, which is `~` and then environment variables, for the archive and the cache;
#: `~` alone for the netrc location; nothing for the certificates. Read at 2026.08.19. `os.path`
#: rather than `Path`, because it is what yt-dlp calls and `Path.expanduser` can raise instead.
_AS_YT_DLP_EXPANDS: Final[dict[str, Callable[[str], str]]] = {
    "--download-archive": lambda path: os.path.expandvars(os.path.expanduser(path)),  # noqa: PTH111
    "--cache-dir": lambda path: os.path.expandvars(os.path.expanduser(path)),  # noqa: PTH111
    "--netrc-location": os.path.expanduser,
}


@dataclass(frozen=True, slots=True)
class Refusal:
    """One option the user typed that cannot be used, and why, in the words they need.

    `option` is **the spelling they typed**, not the canonical one: a user who wrote `-c` is told
    about `-c`. `REQ-031` requires the refusal to name the reason rather than say "not permitted".
    """

    option: str
    reason: str


@dataclass(frozen=True, slots=True)
class Admission:
    """What the hatch made of one field's worth of text.

    `accepted` is the argv of options that may go on to be parsed, in the order typed. `refusals`
    is every reason the user has to see.

    **They are never both non-empty**, and that is a safety property rather than a convenience. A
    field with one refused option in it yields no options at all, so a caller that forgets to ask
    `usable` cannot quietly run the subset that passed — which is the "accepted and silently
    dropped" outcome `REQ-031` forbids in as many words. The refusals still name every problem, so
    one trip through the dialog shows all of them.
    """

    accepted: tuple[str, ...]
    refusals: tuple[Refusal, ...]

    @property
    def usable(self) -> bool:
        """Whether the whole field may be used. One refusal refuses the field."""
        return not self.refusals


def option_arity() -> dict[str, int]:
    """Every spelling yt-dlp's parser knows, and how many values each one consumes.

    The generated table, behind a function so a caller reads it the same way whether it is pinned
    data or something asked of the parser. It is pinned: see this module's own docstring.
    """
    return OPTION_ARITY


def _reason_to_refuse(spelling: str) -> str | None:
    """Why `spelling` may not be used, or `None` when it may be.

    Called only for a spelling the parser knows, so "the audit has no row" means a **suppressed**
    option rather than an unknown one, and default-deny answers for it.
    """
    if spelling in TYPED_WITH_A_FIELD:
        return HAS_A_CONTROL
    ruling = OPTION_CLASSES.get(spelling)
    if ruling is None:
        return NOT_RULED
    group, reason = ruling
    if group not in ADMITTED_CLASSES:
        return reason
    # Admitted by class, and then asked whether it does anything. An option this application
    # cannot show reaching yt-dlp is refused rather than accepted and quietly ignored.
    if spelling in NO_OBSERVABLE_EFFECT:
        return NO_EFFECT
    if spelling in EFFECT_UNKNOWN:
        return UNKNOWN_EFFECT
    return None


def split_the_text(text: str) -> tuple[list[str], Refusal | None]:
    """The user's text as argv, or the refusal that it is not argv at all.

    Quoting is the user's to get right and `shlex` is the same reader a shell uses, so an unclosed
    quote is reported as what it is rather than silently dropping half the field.
    """
    try:
        return shlex.split(text), None
    except ValueError as unbalanced:
        # `shlex`'s own message ("No closing quotation") quotes nothing the user typed.
        return [], Refusal(WHOLE_FIELD, f"This is not a complete command line: {unbalanced}.")


def admit(text: str) -> Admission:
    """Decide every option in `text`, refusing the whole field if any one of them is refused.

    **The whole field, not the options it can salvage.** A user who typed five options and had the
    third silently dropped would be running something they did not write; `REQ-031` says an option
    is never "accepted and silently dropped". So the refusals are collected — all of them, so one
    pass through the dialog shows everything wrong — and nothing is used until there are none.
    """
    tokens, unreadable = split_the_text(text)
    if unreadable is not None:
        return Admission((), (unreadable,))

    arity = option_arity()
    accepted: list[str] = []
    refusals: list[Refusal] = []
    index = 0
    while index < len(tokens):
        word = tokens[index]
        index += 1
        if not word.startswith("-") or word == "-":
            # A bare word is a URL or a stray value. The field takes options; the URL has its own
            # box, and a value that arrived without its option is not something to guess about.
            refusals.append(
                Refusal(word, "This is not an option. Only options belong in this box.")
            )
            continue

        spelling, _, inline = word.partition("=")
        if spelling not in arity:
            refusals.append(Refusal(spelling, NOT_AN_OPTION))
            continue

        wanted = arity[spelling]
        values: list[str] = [inline] if inline else []
        while len(values) < wanted and index < len(tokens):
            values.append(tokens[index])
            index += 1

        # **The class decides before the value does.** Consuming the values is tokenizing — it is
        # how the scan finds the next option — but a user who types a forbidden option bare must
        # be told it is forbidden, not that it needs a value. The first version asked for the
        # value first and answered `--exec` with "this option needs a value", which is both
        # unhelpful and the wrong statement about it.
        refusal = _reason_to_refuse(spelling)
        if refusal is not None:
            refusals.append(Refusal(spelling, refusal))
            continue

        if len(values) < wanted:
            refusals.append(Refusal(spelling, "This option needs a value and none was given."))
            continue

        if spelling in PATH_VALUES and not all(_a_full_path(spelling, value) for value in values):
            refusals.append(Refusal(spelling, NOT_A_FULL_PATH))
            continue

        accepted.append(word if inline else spelling)
        if not inline:
            accepted.extend(values)

    if refusals:
        # Nothing is offered from a field that has a refusal in it. See `Admission`.
        return Admission((), tuple(refusals))
    return Admission(tuple(accepted), ())


def _a_full_path(spelling: str, path: str) -> bool:
    """Whether `path` is absolute as yt-dlp will open it, after its own expansion for `spelling`."""
    expand = _AS_YT_DLP_EXPANDS.get(spelling)
    return Path(expand(path) if expand is not None else path).is_absolute()


def grouped(accepted: Sequence[str]) -> list[list[str]]:
    """The admitted argv split into one chunk per option, each with its own values.

    Used to say **which** option a parser complaint is about without quoting the value, which a
    hatch token may not be safe to repeat (`T184-R6`).
    """
    arity = option_arity()
    chunks: list[list[str]] = []
    index = 0
    while index < len(accepted):
        word = accepted[index]
        index += 1
        spelling, _, inline = word.partition("=")
        wanted = 0 if inline else arity.get(spelling, 0)
        chunk = [word]
        while wanted and index < len(accepted):
            chunk.append(accepted[index])
            index += 1
            wanted -= 1
        chunks.append(chunk)
    return chunks


#: Admitted options whose values **cannot** carry a credential or name a file (`T184-R6`).
#:
#: Numbers, sizes, rates, dates, durations, ranges, enumerated words, format names, language codes,
#: extractor names and chapter or section patterns. The values describe the media, not the user.
#: **Everything else is registered**, including any option admitted after this list was written,
#: so the list fails safe: forgetting an entry over-redacts, and never leaks.
#:
#: The reason it exists. Registering every argument, which the first correction did, redacted the
#: ordinary vocabulary users type here: `--sub-format best` removed every `best` from the log,
#: `--retries 1000` every `1000` and `--fixup never` every `never`. `remember_a_secret`'s four-byte
#: floor stops none of them. A log nobody can read is `T197-R7`'s failure.
NOT_SECRET_VALUES: Final = frozenset(
    {
        "--age-limit",
        "--buffer-size",
        "--compat-options",
        "--concurrent-fragments",
        "-N",
        "--convert-sub",
        "--convert-subs",
        "--convert-subtitles",
        "--convert-thumbnails",
        "--date",
        "--dateafter",
        "--datebefore",
        "--default-search",
        "--download-sections",
        "--encoding",
        "--extractor-retries",
        "--file-access-retries",
        "--fixup",
        "--format-sort",
        "-S",
        "--fragment-retries",
        "--http-chunk-size",
        "--ies",
        "--use-extractors",
        "--limit-rate",
        "--rate-limit",
        "--max-downloads",
        "--max-filesize",
        "--merge-output-format",
        "--min-filesize",
        "--min-sleep-interval",
        "--sleep-interval",
        "--sleep-requests",
        "--sleep-subtitles",
        "--output-na-placeholder",
        "--playlist-items",
        "-I",
        "--remove-chapters",
        "--retries",
        "--retry-sleep",
        "--socket-timeout",
        "--sponsorblock-mark",
        "--sponsorblock-remove",
        "--srt-langs",
        "--sub-format",
        "--throttled-rate",
        "--trim-file-names",
        "--trim-filenames",
        "--wait-for-video",
    }
)

#: The options whose value is a match filter. yt-dlp compiles nothing when it parses one: a filter
#: is read part by part when an item arrives, so a part it cannot read is found then.
FILTER_OPTIONS: Final = frozenset({"--match-filters", "--break-match-filters"})

#: Admitted options whose value is a **path the user configured**, registered with
#: `remember_a_path`, which has no length floor (`T197-R1`).
PATH_VALUES: Final = frozenset(
    {
        "--cache-dir",
        "--client-certificate",
        "--client-certificate-key",
        "--download-archive",
        "--netrc-location",
    }
)


def remember_the_hatch(argv: Sequence[str]) -> None:
    """Register what `argv` could leak, so this process's log handlers redact it (`T184-R6`).

    **Called in the process that formats the logs, which is the parent.** A worker's records
    cross to the parent on a `QueueHandler` and are redacted by the parent's `RedactingFormatter`
    (`T-038`). The first correction registered the values inside the worker, where they redacted
    nothing, because no redacting formatter runs there. `DownloadManager` calls this before it
    starts a session.

    **Values, however they were spelled.** `--match-filters=title=X` is one token, and the first
    version skipped it because the token's spelling is an option's, so the `=` form was never
    registered at all. `grouped` pairs every option with its values in either form.

    **A header's value is registered on its own as well.** yt-dlp keeps `--add-headers` as a
    mapping, so anything that prints a header prints the value without the `Name:` in front of it.
    """
    from tracks_and_trails.core.logging import remember_a_path, remember_a_secret

    for chunk in grouped(argv):
        spelling, _, inline = chunk[0].partition("=")
        if spelling in NOT_SECRET_VALUES:
            continue
        for value in [inline] if inline else chunk[1:]:
            if spelling in PATH_VALUES:
                remember_a_path(value)
                continue
            for piece in _as_yt_dlp_may_print_it(spelling, value):
                remember_a_secret(piece)


def _as_yt_dlp_may_print_it(spelling: str, value: str) -> set[str]:
    """`value`, and each piece of it yt-dlp keeps apart and can print alone (`T184-R6`).

    Registering the whole value covers a line that quotes the whole value. yt-dlp splits three of
    these before it uses them, and each has a line, measured on 2026-09-26, that prints a piece:

    - **A header** is kept as a mapping, so its value is printed without `Name:`.
    - **An extractor argument** is split on `:`, `;`, `=` and unescaped commas, each value
      stripped, and a malformed `po_token` is echoed alone: *got "…"*. The split here is yt-dlp's.
    - **A match filter** is printed stripped (*does not pass filter (…)*), and a part yt-dlp cannot
      read is quoted alone with `repr` (*Invalid filter part '…'*), split on unescaped `&`.

    Pieces under `remember_a_secret`'s floor are ignored there, so `web` in `player_client=web`
    stays readable. A longer client name such as `android` is redacted, which is the safe direction.
    """
    pieces = {value, value.strip()}
    if spelling == "--add-headers":
        pieces.add(value.partition(":")[2].strip())
    elif spelling == "--extractor-args":
        for argument in value.partition(":")[2].split(";"):
            items = argument.partition("=")[2]
            pieces.update((argument.strip(), items.strip()))
            pieces.update(item.replace(r"\,", ",").strip() for item in re.split(r"(?<!\\),", items))
    elif spelling in FILTER_OPTIONS:
        for escaped in re.split(r"(?<!\\)&", value):
            part = escaped.replace(r"\&", "&")
            pieces.update((part, part.strip(), repr(part)[1:-1]))
    return pieces


def options_for(text: str) -> tuple[Admission, tuple[str, ...]]:
    """Admit `text` and, if every option in it may be used, say what it produces.

    **The one call the user interface makes**, and the reason it exists here rather than in `ui/`:
    the parse needs yt-dlp, `ui/` may not import it, and the maintainer ruled on 2026-09-20 that
    edit-time validation runs in the GUI process **lazily**. So the import happens on the line
    below, reached only when a field has usable options in it — a user who never opens the hatch,
    and one whose text is refused, both pay nothing.

    Returns the admission — which carries every refusal the user has to see — and the admitted
    tokens, which are empty whenever it is not usable. The tokens are what
    `DownloadRequest.extra_option_argv` takes.

    **The value is checked here too, and that is `T184-R8`.** Admission knows which options may
    be used; only the parser knows whether `--fragment-retries nope` is a number. Without this,
    that field reported *usable* with no refusal and no options — the user's intent silently
    discarded, and any valid option typed beside it discarded too.
    """
    admission = admit(text)
    if not admission.usable or not admission.accepted:
        # **`accepted` as well as `usable`**, or an empty field imports the parser to ask it
        # about nothing. Every user who never opens the hatch has an empty field, so that is the
        # common path, and it is the one the 25 MiB was approved on the understanding it avoids.
        return admission, ()

    from tracks_and_trails.downloader.ytdlp_adapter import unparseable

    chunks = grouped(admission.accepted)
    refused, culprit = unparseable(admission.accepted, chunks)
    if refused:
        # The whole field is refused. `culprit` only decides **what to call it**. When no single
        # option fails alone, they contradict one another, and the refusal names their spellings,
        # never the text around them (`T184-R6`, `WHOLE_FIELD`).
        if culprit is not None:
            return Admission((), (Refusal(culprit, BAD_VALUE),)), ()
        spellings = dict.fromkeys(chunk[0].partition("=")[0] for chunk in chunks)
        return Admission((), (Refusal(", ".join(spellings), TOGETHER),)), ()

    return admission, admission.accepted


def refusal_lines(admission: Admission) -> tuple[str, ...]:
    """Each refusal as one line of plain text, for a caller that shows them to a user."""
    return tuple(f"{refusal.option}: {refusal.reason}" for refusal in admission.refusals)
