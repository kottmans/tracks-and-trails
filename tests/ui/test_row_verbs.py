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
    history_group_verbs,
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


def test_a_terminal_history_group_offers_only_what_it_can_perform() -> None:
    """`T-142`, transcribed from `UX-005` §3 and row 9, `REQ-021` and `DAT-005`.

    **Written out by hand rather than derived from `group_verbs`**, which is this file's whole
    method: the queue's list and History's are independent readings of the same decisions, and a
    test that computed one from the other would pass while they said the same wrong thing.

    Every member of a History group is terminal, so `Cancel all` has nothing to stop and
    `Retry failed` has no job to retry — a record is not a download (`DAT-005`). `Open` is out
    because a group has no single file. What is left is the folder they share (`UX-005` row 10) and
    a removal that never touches one (`DAT-005` §2).
    """
    assert history_group_verbs([True, True]) == (Verb.REVEAL, Verb.REMOVE)
    assert history_group_verbs([False, True]) == (Verb.REVEAL, Verb.REMOVE), (
        "one member naming a file is enough: the entries share a folder, so any of them reveals it"
    )
    assert history_group_verbs([False, False]) == (Verb.REMOVE,), (
        "a group whose records name no file offered to show one, which FileActions would refuse "
        "for a reason the user cannot act on"
    )
    assert history_group_verbs([]) == (Verb.REMOVE,), (
        "a group the user no longer wants is always removable, so the header is never left with "
        "nothing at all"
    )


def test_a_history_group_never_offers_a_queue_verb() -> None:
    """The trap `T-142` names: assuming History's verbs are the queue's.

    Asserted over the whole of `Verb` rather than a list of the four that matter, so a verb added
    to the queue's vocabulary later cannot quietly appear on a terminal group.
    """
    for offer in ([True, True], [False, False]):
        assert set(history_group_verbs(offer)) <= {Verb.REVEAL, Verb.REMOVE}, (
            f"history_group_verbs({offer}) offers something outside what a record supports"
        )
