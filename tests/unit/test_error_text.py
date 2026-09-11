"""`T-201`: every taxonomy class has a presentation, and three of them honestly offer nothing.

**One test per class**, as the criterion asks, so a thirteenth `ErrorKind` added later fails here
until somebody writes its words — rather than reaching a user as a bare identifier, which is what
the queue showed before this module existed.

The sweeps that follow are the ones worth more than the individual assertions: that no
unretryable kind is told to retry, that no message replaces the extractor's own, and that the two
classes with a ruling behind them suggest nothing.
"""

from typing import Final

import pytest

from tracks_and_trails.core.errors import ErrorKind, is_auto_retryable, is_retryable
from tracks_and_trails.ui.error_text import (
    ErrorPresentation,
    describe,
    describe_failure,
    headline_for,
    next_step_for,
)

#: The words that make a next step an offer to update yt-dlp (`T-290`).
#:
#: Matched as a substring rather than against a whole sentence, so the property keeps
#: holding if the wording is reworked — which `T-290` may yet do to the Settings half.
UPDATE_OFFER: Final = "Updating yt-dlp"

#: The three with no honest action (`T-201`'s scope). Named here so the assertions below read as
#: a rule rather than as three unrelated special cases.
NOTHING_TO_DO = frozenset({ErrorKind.GEO_RESTRICTED, ErrorKind.DRM_PROTECTED, ErrorKind.CANCELLED})


@pytest.mark.parametrize("kind", sorted(ErrorKind, key=str))
def test_every_error_kind_has_a_presentation(kind: ErrorKind) -> None:
    """The criterion: *each of the twelve classes has a tested presentation*.

    Parametrised over the enum rather than over a list written here, so adding a kind adds a case
    automatically instead of leaving one uncovered.
    """
    presentation = describe(kind)

    assert isinstance(presentation, ErrorPresentation)
    assert presentation.headline, f"{kind} has no plain-words statement of what failed"


@pytest.mark.parametrize("kind", sorted(ErrorKind, key=str))
def test_no_headline_leaks_the_taxonomy_identifier(kind: ErrorKind) -> None:
    """`geo_restricted` is a database value, not a sentence.

    This is what the failed row and the detail view actually showed: the identifier on one line
    and the extractor's message on the next, with nothing saying what had happened.

    **Only the multi-word identifiers are checked for verbatim appearance.** `cancelled`'s
    identifier is also an ordinary English word, and *"You cancelled this download"* is the right
    sentence — asserting the value's absence there would forbid the correct wording. The
    underscore check below is the part that holds for every kind.
    """
    if "_" in kind.value:
        assert kind.value not in headline_for(kind).lower()
    assert "_" not in headline_for(kind)


@pytest.mark.parametrize("kind", sorted(ErrorKind, key=str))
def test_a_headline_is_a_sentence_a_user_could_read_aloud(kind: ErrorKind) -> None:
    """`NFR-006` asks for *what failed*, and a fragment is not that."""
    headline = headline_for(kind)

    # `ffmpeg` and `yt-dlp` are spelled lower-case by their own projects, and a headline that
    # opens with one is correct rather than sloppy. Everything else starts as a sentence does.
    starts_with_a_proper_name = headline.startswith(("ffmpeg", "yt-dlp"))
    assert headline[0].isupper() or starts_with_a_proper_name, (
        f"{kind}'s headline does not start as a sentence"
    )
    assert len(headline.split()) >= 4, f"{kind}'s headline is too terse to say what failed"
    assert not headline.endswith("."), (
        f"{kind}'s headline ends in a full stop; it is a heading, and the step is the sentence"
    )


def test_the_three_with_no_honest_action_offer_none() -> None:
    """**The substance of this task, not an omission in it.**

    A message suggesting an action that cannot work is worse than one admitting there is none:
    it sends the user off to try things. `GEO_RESTRICTED` is here because the line between a
    user's own proxy and circumventing a restriction is a ruling nobody has taken
    (`SEC-003` against `REQ-EXCL-002`); `DRM_PROTECTED` because `REQ-EXCL-001` means there must
    never be a way; `CANCELLED` because nothing went wrong.
    """
    for kind in NOTHING_TO_DO:
        assert next_step_for(kind) == "", f"{kind} was given a next step it cannot honestly offer"
        assert describe(kind).has_next_step is False


def test_every_other_kind_does_offer_a_next_step() -> None:
    """The mirror, and it is what stops the rule above from being satisfied by an empty table."""
    for kind in ErrorKind:
        if kind in NOTHING_TO_DO:
            continue
        assert next_step_for(kind), f"{kind} tells the user nothing they can do"


def test_geo_restricted_suggests_no_circumvention() -> None:
    """`REQ-EXCL-002` forbids bypass, and `T-201` says this task must not invent the line.

    Asserted as *no workaround vocabulary at all* rather than as an exact sentence: the criterion
    is about what the text may not push the user toward, and pinning the wording would let a
    rephrasing introduce exactly what this forbids while the test went on passing (`T214-R1`).
    """
    text = f"{headline_for(ErrorKind.GEO_RESTRICTED)} {next_step_for(ErrorKind.GEO_RESTRICTED)}"
    lowered = text.lower()

    for forbidden in ("proxy", "vpn", "bypass", "get around", "work around", "another country"):
        assert forbidden not in lowered, f"the geo-restriction text suggests {forbidden!r}"


def test_drm_says_plainly_that_the_application_does_not_do_it() -> None:
    """`REQ-EXCL-001` is a promise about the product, and this is where a user meets it."""
    assert "drm" in headline_for(ErrorKind.DRM_PROTECTED).lower()
    assert next_step_for(ErrorKind.DRM_PROTECTED) == ""


def test_cancelled_is_not_presented_as_a_failure() -> None:
    """`ARCHITECTURE.md` §7: a cancellation is shown as one and never as an error."""
    headline = headline_for(ErrorKind.CANCELLED).lower()

    assert "cancel" in headline
    for blame in ("failed", "error", "could not", "problem"):
        assert blame not in headline, f"a cancellation is described with {blame!r}"


def test_no_unretryable_kind_is_told_to_retry() -> None:
    """The two tables must agree, and this is what keeps them agreeing.

    `core/errors.is_retryable` decides whether the button is drawn at all — `job_detail` and
    `queue_view` both ask it. Text telling a user to retry where no button exists is `T-075`'s
    defect: a screen describing a capability the application does not offer.
    """
    for kind in ErrorKind:
        if is_retryable(kind):
            continue
        assert "retry" not in next_step_for(kind).lower(), (
            f"{kind} may not be retried, and its text tells the user to"
        )


def test_the_one_auto_retrying_kind_says_so() -> None:
    """`NETWORK` retries by itself (`REQ-018`), and a user who is not told that reads *"check
    your connection"* while a retry they never asked for is already in flight."""
    assert is_auto_retryable(ErrorKind.NETWORK)

    assert "itself" in next_step_for(ErrorKind.NETWORK)


def test_no_next_step_names_a_setting_the_application_does_not_have() -> None:
    """A suggestion the user cannot act on is the reassuring-but-useless shape.

    Network options are `T-196` and are not built, so nothing here may send a user to look for
    them. This is also the check that catches the tempting `GEO_RESTRICTED` wording sneaking in
    through another class's text.
    """
    absent = ("rate limit", "proxy", "socket timeout", "source address")
    for kind in ErrorKind:
        lowered = next_step_for(kind).lower()
        for setting in absent:
            assert setting not in lowered, f"{kind} sends the user to {setting!r}, which is T-196"


def test_an_unknown_kind_raises_rather_than_reaching_a_user() -> None:
    """A generic fallback is the sentence `NFR-006` forbids, delivered silently."""

    class Impostor:
        pass

    with pytest.raises(KeyError):
        describe(Impostor())  # type: ignore[arg-type]


def test_the_extractor_message_is_carried_verbatim_and_last() -> None:
    """`NFR-006`: the message is surfaced, never swallowed or replaced.

    Last, because the frame is what orients the reader and the message is the evidence. Verbatim,
    because `core/errors.py` stores it unchanged for the reason this asserts — paraphrasing
    destroys the only information the user can act on.
    """
    message = "ERROR: [youtube] dQw4: Video unavailable. This video is private."

    rendered = describe_failure(ErrorKind.AUTH_REQUIRED, message)

    assert rendered.endswith(message), "the extractor's own words were edited or displaced"
    assert headline_for(ErrorKind.AUTH_REQUIRED) in rendered
    assert next_step_for(ErrorKind.AUTH_REQUIRED) in rendered


def test_a_class_with_nothing_to_suggest_contributes_no_hopeful_line() -> None:
    """Two lines rather than three, and no filler where the step would be."""
    rendered = describe_failure(ErrorKind.DRM_PROTECTED, "ERROR: DRM protected stream")

    assert rendered.splitlines() == [
        headline_for(ErrorKind.DRM_PROTECTED),
        "ERROR: DRM protected stream",
    ]


def test_a_failure_with_no_message_still_says_what_happened() -> None:
    """A worker that crashed before it could speak still has a class, and the user still asked."""
    rendered = describe_failure(ErrorKind.WORKER_CRASH, "")

    assert rendered.startswith(headline_for(ErrorKind.WORKER_CRASH))
    assert not rendered.endswith("\n")


def test_the_network_step_stops_promising_a_retry_once_they_are_spent() -> None:
    """**`T201-R2`.** The one kind that is retried automatically is the one that can run out.

    `DownloadManager` announces every failure *before* deciding whether to schedule another, and
    refuses once `attempts` reaches `AUTOMATIC_RETRY_LIMIT` — so the fourth and final failure
    rendered *"This one retries by itself"* at exactly the moment none remained. That is this
    task's own named risk: **reassuring text that is no longer true.**

    Both states are asserted, because a correction that made the *ordinary* text hedge would
    satisfy a one-sided test while telling a user mid-backoff that nothing is happening.
    """
    during = next_step_for(ErrorKind.NETWORK)
    after = next_step_for(ErrorKind.NETWORK, exhausted=True)

    assert "retries by itself" in during, (
        f"a network failure with retries left does not say they are running: {during!r}"
    )
    assert during != after, "the last failure says the same thing as the ones being retried"
    assert "retries by itself" not in after, (
        f"the final network failure still promises an automatic retry: {after!r}"
    )
    assert "retry" in after.lower(), (
        f"and it no longer says what the user can do instead: {after!r}"
    )


@pytest.mark.parametrize("kind", [kind for kind in ErrorKind if kind is not ErrorKind.NETWORK])
def test_every_other_kind_says_the_same_thing_either_way(kind: ErrorKind) -> None:
    """Eleven of the twelve have no exhausted state, because nothing else retries by itself.

    A second wording for a kind that is never automatically retried would be a state the product
    cannot reach — and an empty `exhausted_next_step` is how the table says so.
    """
    assert next_step_for(kind) == next_step_for(kind, exhausted=True)


def test_the_whole_composition_carries_the_exhausted_wording() -> None:
    """`describe_failure` is what a surface renders, so the flag has to reach it (`T201-R2`)."""
    spent = describe_failure(ErrorKind.NETWORK, "ERROR: timed out", exhausted=True)

    assert "retries by itself" not in spent
    assert "ERROR: timed out" in spent, "the extractor's message went with the wording change"


def test_only_a_failure_the_update_could_fix_offers_the_update() -> None:
    """`T-290`: *"the offer appears only where it could be true"* (`UX-005` §5).

    **`C-002` is why the offer exists at all**: site support *is* yt-dlp's site support, so when a
    site changes, a newer yt-dlp is the honest first move rather than a platitude. **`UX-005` §5 is
    why it is bounded**: an unwritable folder or a full disk has nothing to do with the extractor,
    and suggesting an update there sends a user to do something that cannot help.

    **Pinned as a property over the whole taxonomy, not as one string.** This table predates
    `T-290` and already had the shape the task asks for; what it did not have was anything stopping
    a later kind from picking the sentence up by copying a neighbour. Asserted both ways — the kind
    that must offer it, and every kind that must not — because half of it would pass on a table
    that offered the update everywhere or nowhere.
    """
    offering = {kind for kind in ErrorKind if UPDATE_OFFER in next_step_for(kind)}

    assert offering == {ErrorKind.EXTRACTOR_ERROR}, (
        f"the update is offered for {sorted(k.value for k in offering)}; it can only be true for a "
        "site that changed under yt-dlp"
    )
    # The two this most obviously must not reach, named rather than left to the set comparison so a
    # failure says which rule was broken.
    assert UPDATE_OFFER not in next_step_for(ErrorKind.DISK)
    assert UPDATE_OFFER not in next_step_for(ErrorKind.AUTH_REQUIRED)
    # **And the refusal `T-201` calls the substance of its own task** — a kind with no honest next
    # step keeps none, rather than being given an encouraging one.
    for hopeless in (ErrorKind.GEO_RESTRICTED, ErrorKind.DRM_PROTECTED):
        assert next_step_for(hopeless) == "", (
            f"{hopeless.value} grew a next step; it has no honest one"
        )
