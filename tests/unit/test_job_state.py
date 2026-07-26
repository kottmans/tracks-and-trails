"""The job state machine (`T-010`, `ai/TESTING.md` §7).

§7 requires that *every* illegal transition raises. These tests assert that over every ordered
pair of statuses rather than a sampled list, which is the difference between a guarantee and a
spot check: a sampled test passes forever while a newly added status quietly acquires
permissive behavior.
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


def test_every_status_has_an_entry_in_the_transition_table() -> None:
    """Adding a `JobStatus` without adding its transitions must fail the suite.

    Without this, a new member would raise `KeyError` from `allowed_from` at runtime — in the
    download manager, on a user's machine — rather than here.
    """
    for status in JobStatus:
        assert allowed_from(status) is not None, f"{status} is missing from the transition table"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (JobStatus.QUEUED, JobStatus.PROBING),
        (JobStatus.PROBING, JobStatus.READY),
        (JobStatus.READY, JobStatus.RUNNING),
        (JobStatus.RUNNING, JobStatus.POST_PROCESSING),
        (JobStatus.POST_PROCESSING, JobStatus.COMPLETED),
        (JobStatus.RUNNING, JobStatus.PAUSED),
        (JobStatus.PAUSED, JobStatus.RUNNING),
        (JobStatus.FAILED, JobStatus.QUEUED),
    ],
)
def test_the_documented_happy_paths_are_legal(source: JobStatus, target: JobStatus) -> None:
    """Transcribed from `ARCHITECTURE.md` §5's diagram, including retry and pause/resume."""
    assert apply(source, target) is target


def test_every_transition_outside_the_table_raises() -> None:
    """The exhaustive half: all 81 ordered pairs, not a chosen few."""
    illegal = 0
    for source, target in itertools.product(JobStatus, JobStatus):
        if can_transition(source, target):
            continue
        illegal += 1
        with pytest.raises(IllegalTransitionError):
            apply(source, target)

    assert illegal, "no illegal transitions found — the table cannot be permitting everything"


def test_no_status_transitions_to_itself() -> None:
    """A self-transition means a caller re-applied a state change it had already made.

    Allowing it would let a double-delivered message increment attempts twice or restart a
    download that was already running.
    """
    for status in JobStatus:
        assert not can_transition(status, status), f"{status} may transition to itself"


def test_cancelled_is_reachable_from_every_non_terminal_state() -> None:
    """`REQ-015`: cancel must work at any point, not only while running."""
    for status in JobStatus:
        if is_terminal(status) or status is JobStatus.FAILED:
            continue
        assert can_transition(status, JobStatus.CANCELLED), f"cannot cancel from {status}"


def test_nothing_is_reachable_from_a_terminal_state() -> None:
    """A completed or cancelled job is finished. Anything else is state corruption."""
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


def test_failed_can_only_go_back_to_the_queue() -> None:
    """Retry re-enters the queue; it does not resume in place or jump to running."""
    assert allowed_from(JobStatus.FAILED) == frozenset({JobStatus.QUEUED})


def test_every_non_terminal_state_can_fail() -> None:
    """`REQ-018` forbids failing silently, which presumes failure is always representable."""
    for status in JobStatus:
        if is_terminal(status) or status is JobStatus.FAILED:
            continue
        assert can_transition(status, JobStatus.FAILED), f"{status} has no path to FAILED"


def test_the_illegal_transition_message_names_both_states_and_the_alternatives() -> None:
    """The exception is a debugging aid; a bare `IllegalTransitionError` would waste the raise."""
    with pytest.raises(IllegalTransitionError) as caught:
        apply(JobStatus.COMPLETED, JobStatus.RUNNING)

    message = str(caught.value)
    assert "completed" in message
    assert "running" in message
    assert "terminal" in message
    assert caught.value.source is JobStatus.COMPLETED
    assert caught.value.target is JobStatus.RUNNING


def test_completed_is_reachable_only_from_post_processing() -> None:
    """Success has exactly one route in, so nothing can mark a job done by accident."""
    sources = [status for status in JobStatus if can_transition(status, JobStatus.COMPLETED)]
    assert sources == [JobStatus.POST_PROCESSING]
