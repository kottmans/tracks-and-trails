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

import shlex
from dataclasses import dataclass
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

#: What a user is told when the effect cannot be measured at all.
UNKNOWN_EFFECT: Final = (
    "This application cannot tell what this option would change, so it does not pass it on."
)


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
        return [], Refusal(text.strip()[:40], f"This is not a complete command line: {unbalanced}.")


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

        accepted.append(word if inline else spelling)
        if not inline:
            accepted.extend(values)

    if refusals:
        # Nothing is offered from a field that has a refusal in it. See `Admission`.
        return Admission((), tuple(refusals))
    return Admission(tuple(accepted), ())


def refusal_lines(admission: Admission) -> tuple[str, ...]:
    """Each refusal as one line of plain text, for a caller that shows them to a user."""
    return tuple(f"{refusal.option}: {refusal.reason}" for refusal in admission.refusals)
