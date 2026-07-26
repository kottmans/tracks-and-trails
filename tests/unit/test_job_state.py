"""The job state machine (`T-010`, `ai/TESTING.md` §7).

§7 requires that *every* illegal transition raises. That guarantee is only worth anything if
the test knows what "illegal" means **independently of the code under test**.

`T010-R1`: the first version of this file asked `can_transition()` which pairs were illegal and
then asserted `apply()` rejected them. Both read `_TRANSITIONS`, so the test proved that two
views of one table agreed — not that the table matched `ARCHITECTURE.md` §5. Adding an
undocumented `QUEUED → READY` edge left all 48 state and model tests green, because the test
simply reclassified the new edge as legal and skipped it.

`EXPECTED` below is therefore transcribed by hand from `ARCHITECTURE.md` §5's diagram and is
the authority here. Production is checked against it, never the other way round. If the two
disagree, one of them is wrong and this file says so.
"""

import itertools

import pytest

from tracks_and_trails.core.job_state import (
    TERMINAL,
    IllegalTransitionError,
    JobStatus,
    allowed_from,
    apply,
    can_transition,
    is_terminal,
)

#: Transcribed by hand from `ARCHITECTURE.md` §5's state diagram and its
#: `FAILED ──retry──▶ QUEUED` note. **Do not derive this from `_TRANSITIONS`** — that is
#: precisely the mistake `T010-R1` recorded. Changing production without changing this must
#: fail the suite; that is the entire point of the file.
EXPECTED: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.PROBING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.PROBING: {JobStatus.READY, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.READY: {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.RUNNING: {
        JobStatus.POST_PROCESSING,
        JobStatus.PAUSED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.PAUSED: {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.POST_PROCESSING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.FAILED: {JobStatus.QUEUED},
    JobStatus.COMPLETED: set(),
    JobStatus.CANCELLED: set(),
}

#: States with active work to stop. `CANCELLED` must be reachable from exactly these.
#:
#: `T010-R3`: the acceptance criterion says "every non-terminal state", which reads as though it
#: includes `FAILED`. It does not, and should not — cancelling stops in-flight work and a failed
#: job has none. Naming the set explicitly stops that exclusion from being a silent
#: `if status is FAILED: continue` that nobody can tell apart from an oversight.
CANCELLABLE: frozenset[JobStatus] = frozenset(
    {
        JobStatus.QUEUED,
        JobStatus.PROBING,
        JobStatus.READY,
        JobStatus.RUNNING,
        JobStatus.PAUSED,
        JobStatus.POST_PROCESSING,
    }
)


def test_the_expected_relation_covers_every_status() -> None:
    """Guards the guard: an incomplete `EXPECTED` would silently narrow every test below."""
    assert set(EXPECTED) == set(JobStatus)


def test_production_matches_the_architecture_relation_exactly() -> None:
    """The central assertion: `allowed_from()` equals §5, state by state.

    Both directions at once — an edge production has that §5 does not, and an edge §5 has that
    production does not — each fail here with the offending state named.
    """
    for status in JobStatus:
        assert allowed_from(status) == frozenset(EXPECTED[status]), (
            f"{status.value}: production allows "
            f"{sorted(s.value for s in allowed_from(status))}, "
            f"ARCHITECTURE.md §5 allows {sorted(s.value for s in EXPECTED[status])}"
        )


def test_every_ordered_pair_agrees_with_the_architecture() -> None:
    """All 81 pairs, through both public entry points, judged against `EXPECTED`.

    `can_transition()` and `apply()` are checked separately: they could disagree with each
    other, and a caller may reasonably use either.
    """
    for source, target in itertools.product(JobStatus, JobStatus):
        legal = target in EXPECTED[source]

        assert can_transition(source, target) is legal, (
            f"can_transition({source.value}, {target.value}) disagrees with ARCHITECTURE.md §5"
        )

        if legal:
            assert apply(source, target) is target
        else:
            with pytest.raises(IllegalTransitionError):
                apply(source, target)


def test_every_status_has_an_entry_in_the_transition_table() -> None:
    """Adding a `JobStatus` without wiring its transitions must fail the suite.

    Without this, a new member raises `KeyError` from `allowed_from` at runtime — in the
    download manager, on a user's machine — rather than here.
    """
    for status in JobStatus:
        allowed_from(status)


def test_no_status_transitions_to_itself() -> None:
    """A self-transition means a caller re-applied a change it had already made.

    Allowing it would let a double-delivered message increment attempts twice or restart a
    download that was already running.
    """
    for status in JobStatus:
        assert not can_transition(status, status), f"{status} may transition to itself"


def test_cancelled_is_reachable_from_exactly_the_cancellable_states() -> None:
    """`REQ-015`: cancel must work wherever there is work to stop, and nowhere else.

    An equality rather than a one-way check, so a state that quietly gains or loses
    cancellability fails here.
    """
    actual = {status for status in JobStatus if can_transition(status, JobStatus.CANCELLED)}
    assert actual == CANCELLABLE


def test_a_failed_job_is_retryable_but_not_cancellable() -> None:
    """`T010-R3`, pinned deliberately rather than left as a silent exclusion.

    A failed job has no active work to cancel, and `REQ-015`'s "remove" is deletion rather than
    a lifecycle transition. Retry is its only outgoing edge.
    """
    assert allowed_from(JobStatus.FAILED) == frozenset({JobStatus.QUEUED})
    assert not can_transition(JobStatus.FAILED, JobStatus.CANCELLED)


def test_nothing_is_reachable_from_a_terminal_state() -> None:
    """A completed or cancelled job is finished. Anything else is state corruption."""
    assert frozenset({JobStatus.COMPLETED, JobStatus.CANCELLED}) == TERMINAL
    for status in TERMINAL:
        assert allowed_from(status) == frozenset(), f"{status} is terminal but has transitions"
        for target in JobStatus:
            with pytest.raises(IllegalTransitionError):
                apply(status, target)


def test_failed_is_not_terminal_because_retry_exists() -> None:
    """`REQ-018` keeps a failed job in the queue and offers retry.

    Worth asserting explicitly: treating `FAILED` as terminal is the intuitive mistake, and it
    would silently remove retry from the product.
    """
    assert not is_terminal(JobStatus.FAILED)
    assert apply(JobStatus.FAILED, JobStatus.QUEUED) is JobStatus.QUEUED


def test_every_state_with_work_in_flight_can_fail() -> None:
    """`REQ-018` forbids failing silently, which presumes failure is always representable."""
    for status in CANCELLABLE:
        assert can_transition(status, JobStatus.FAILED), f"{status} has no path to FAILED"


def test_completed_is_reachable_only_from_post_processing() -> None:
    """Success has exactly one route in, so nothing can mark a job done by accident."""
    sources = [status for status in JobStatus if can_transition(status, JobStatus.COMPLETED)]
    assert sources == [JobStatus.POST_PROCESSING]


def test_the_illegal_transition_message_names_both_states_and_the_alternatives() -> None:
    """The exception is a debugging aid; a bare raise would waste it."""
    with pytest.raises(IllegalTransitionError) as caught:
        apply(JobStatus.COMPLETED, JobStatus.RUNNING)

    message = str(caught.value)
    assert "completed" in message
    assert "running" in message
    assert "terminal" in message
    assert caught.value.source is JobStatus.COMPLETED
    assert caught.value.target is JobStatus.RUNNING
