"""`UX-005` §4 and §5, transcribed by hand (`T-124`).

**Every expectation below is written out from the decision entry, not read from the module.**
`ai/TESTING.md` §13 records six — now eight — tests in this project that passed while the thing
they protected was removed, and the common cause is a test that asked production what to expect.
`T034-R4` is the closest relative: shrinking production's reserved-name set shrank the expectation
with it, so the test could not fail. A table this small is exactly where that happens, because
`assert verbs_for(s) == _BY_STATUS[s]` looks like a test and is an identity.

So: the four rows `UX-005` names are typed out again below, and if somebody edits the module's
literal without the entry, this file fails.
"""

import pytest

from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.ui.row_verbs import (
    LABELS,
    MORE_LABEL,
    Verb,
    verbs_for,
)

#: `UX-005` §4, quoted: "Running — *Cancel*. Queued — *↑*, *↓*, *Cancel*. Failed — *Retry*,
#: *Remove*. Done — *Open*, *Show in folder*."
UX_005_TABLE = {
    "running": (Verb.CANCEL,),
    "queued": (Verb.MOVE_UP, Verb.MOVE_DOWN, Verb.CANCEL),
    "failed": (Verb.RETRY, Verb.REMOVE),
    "done": (Verb.OPEN, Verb.REVEAL),
}


@pytest.mark.parametrize(
    ("status", "row"),
    [
        (JobStatus.RUNNING, "running"),
        (JobStatus.QUEUED, "queued"),
        (JobStatus.FAILED, "failed"),
        (JobStatus.COMPLETED, "done"),
    ],
)
def test_each_state_offers_exactly_what_the_decision_says(status: JobStatus, row: str) -> None:
    """The four rows `UX-005` names, by value and in order.

    **Equality, not a subset** (`ai/TESTING.md` §13). A subset check stays green when a verb is
    deleted, and the failure mode this guards is a state quietly losing an action.
    """
    assert verbs_for(status) == UX_005_TABLE[row], (
        f"a {status.value} row offers {[v.value for v in verbs_for(status)]} where UX-005 says "
        f"{[v.value for v in UX_005_TABLE[row]]}"
    )


def test_no_state_offers_a_verb_another_state_owns() -> None:
    """`UX-005` §5: nothing is drawn that would be refused.

    This is the half `T081-R3` says is easy to lose, and it is the mutation the task's acceptance
    criteria name — **adding a verb a state forbids must fail**. Asserting only that each state
    has the verbs it should cannot catch that; this asserts the complement, which is why both
    exist.
    """
    forbidden = {
        # A download in flight cannot be reordered — it is not waiting for a slot — and there is
        # no per-job pause to offer (`UX-005` §7).
        JobStatus.RUNNING: {Verb.MOVE_UP, Verb.MOVE_DOWN, Verb.RETRY, Verb.OPEN, Verb.REVEAL},
        # Nothing has been written yet, so there is no file to open or reveal.
        JobStatus.QUEUED: {Verb.OPEN, Verb.REVEAL, Verb.RETRY},
        # A failure produced no file, and it is not running, so there is nothing to cancel.
        JobStatus.FAILED: {Verb.OPEN, Verb.REVEAL, Verb.CANCEL, Verb.MOVE_UP, Verb.MOVE_DOWN},
        # A finished download cannot be cancelled or retried — `test_end_to_end` asserted the
        # first of those through the detail pane until `UX-005` removed it, and this is where
        # that assertion now lives.
        JobStatus.COMPLETED: {Verb.CANCEL, Verb.RETRY, Verb.MOVE_UP, Verb.MOVE_DOWN},
        # Cancelled: no file, and re-running it is `Retry`'s job on a *failure*, not on a
        # deliberate stop.
        JobStatus.CANCELLED: {Verb.OPEN, Verb.REVEAL, Verb.CANCEL, Verb.RETRY},
    }
    for status, must_not in forbidden.items():
        offered = set(verbs_for(status))
        assert not (offered & must_not), (
            f"a {status.value} row offers {[v.value for v in sorted(offered & must_not)]}, which "
            f"its state forbids — UX-005 §5 says a row offers only what it permits, and a verb "
            f"that would be refused is worse than one that is absent"
        )


def test_every_status_is_mapped() -> None:
    """A status with no entry raises rather than silently offering nothing.

    An unmapped state that returned `()` would lose all its actions and look exactly like a state
    whose actions are legitimately empty. `JobStatus` is walked here so that adding a ninth member
    fails this test rather than shipping a row nobody can act on.
    """
    for status in JobStatus:
        assert verbs_for(status), f"a {status.value} row offers nothing at all"


def test_an_unretryable_failure_is_not_offered_a_retry() -> None:
    """`REQ-018` through `core/errors.py`, not through the status alone.

    Offering the button implies a workaround exists (`job_detail` states this); a retry that
    re-runs an unretryable failure spends a worker to produce the same error. The row must still
    offer *Remove*, so a user is never left with a failed row and nothing to do about it.
    """
    offered = verbs_for(JobStatus.FAILED, retryable=False)
    assert Verb.RETRY not in offered, (
        "a failure core/errors.py calls unretryable was offered a Retry, which promises the user "
        "a workaround that does not exist"
    )
    assert Verb.REMOVE in offered, "a failed row that offers nothing at all is a dead end"


def test_every_verb_has_a_label() -> None:
    """A verb with no label draws as an empty hit target — a control that is not a control."""
    for verb in Verb:
        assert LABELS.get(verb), f"{verb.value} has no label, so it would draw as a blank button"
    assert MORE_LABEL, "the overflow has no label, so the keyboard route has nothing to point at"


# --- T-113: a job that cannot resume says so, and its verb says what it will do ----------------


def test_a_job_that_cannot_resume_is_offered_start_again_rather_than_retry() -> None:
    """`P-24`, ruled 2026-08-07: *offers start again as its own verb*.

    **Renamed, not removed**, and the distinction is the point. A live stream can be run again;
    what it cannot do is continue, so a button reading *Retry* promises to pick up where it left
    off when it will start from zero. `UX-008` records why there is no separate action behind it —
    the difference is what the download does, not what the application asks for.
    """
    offered = verbs_for(JobStatus.FAILED, resumable=False)

    assert Verb.START_AGAIN in offered
    assert Verb.RETRY not in offered, "both verbs were offered, which is two buttons for one press"
    assert Verb.REMOVE in offered, "renaming the retry cost the row its other verb"
    assert len(offered) == len(verbs_for(JobStatus.FAILED)), "the row gained or lost a verb"


def test_a_resumable_job_keeps_the_verb_it_had() -> None:
    """The default, asserted so the rename cannot leak into every row."""
    assert verbs_for(JobStatus.FAILED) == verbs_for(JobStatus.FAILED, resumable=True)
    assert Verb.START_AGAIN not in verbs_for(JobStatus.FAILED)


def test_an_unretryable_failure_is_not_offered_start_again_either() -> None:
    """The two conditions compose, and the safety one wins.

    `SEC-001` says DRM is never retried. A live stream whose failure is unretryable must not be
    offered a differently-worded way to retry it — which is exactly what a rename applied after the
    retryability filter would have produced.
    """
    offered = verbs_for(JobStatus.FAILED, retryable=False, resumable=False)

    assert Verb.RETRY not in offered
    assert Verb.START_AGAIN not in offered, (
        "an unretryable failure was offered a retry under another name"
    )
    assert Verb.REMOVE in offered
