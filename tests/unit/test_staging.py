"""The staging list's state machine (`T-118`, `UX-003`).

No `QApplication` and no event loop: `ui/staging.py` is Qt-free precisely so these rules can be
asserted directly. What the widget does *with* them is `tests/ui/test_add_dialog.py`.
"""

import pytest

from tracks_and_trails.ui.staging import (
    DUPLICATE_TEXT,
    Duplicate,
    Row,
    RowState,
    Staging,
    placeholder_hue,
    summarise,
)


def a_staging(*urls: str) -> Staging:
    staging = Staging()
    staging.reconcile(urls)
    return staging


# --- reconciling the rows with what is entered -------------------------------------------------


def test_every_entered_line_becomes_a_row_in_entry_order() -> None:
    """`UX-003`: the paste is the batch, not just its first line.

    Order matters beyond tidiness — it is the order the jobs are written in, and therefore the
    `queue_position` order the pool will start them in (`T115-R1`).
    """
    staging = a_staging("https://a.invalid/1", "https://b.invalid/2", "https://c.invalid/3")

    assert [row.url for row in staging.visible] == [
        "https://a.invalid/1",
        "https://b.invalid/2",
        "https://c.invalid/3",
    ]
    assert all(row.state is RowState.PENDING for row in staging.visible)


def test_two_identical_lines_are_two_rows() -> None:
    """`REQ-001`, `T016-R1`: the user asked for both, so both resolve and both commit.

    The failure this guards is quiet: one row for two lines means one download, and the user gets
    what looks like a successful add with half the work missing.
    """
    staging = a_staging("https://same.invalid/x", "https://same.invalid/x")

    assert len(staging.visible) == 2
    first, second = staging.visible
    assert first is not second, "the two lines share one row"


def test_a_row_is_an_identity_rather_than_a_value() -> None:
    """`REQ-001`: two rows describing the same line are not the same row.

    Written because a mutation removing `eq=False` **survived the whole battery**. Nothing in
    `staging.py` currently depends on it — `reconcile` tracks what it creates rather than asking
    what it had — so the docstring was claiming a protection no test could see. This pins the
    semantics at the level the claim is actually made: anything reaching for `in`, `remove`,
    `index` or a `set` must be able to tell two identical lines apart.
    """
    one = Row(url="https://same.invalid/x", generation=1)
    other = Row(url="https://same.invalid/x", generation=1)

    assert one != other, "two rows for two identical lines compare as one"
    assert len({id(one), id(other)}) == 2
    assert [one, other].index(other) == 1, "the second row resolves to the first"
    assert len({one, other}) == 2, "a set collapses two identical lines into one download"


def test_editing_one_line_leaves_the_other_rows_alone() -> None:
    """Retyping must not restart twenty probes.

    Asserted on **identity**, not on the URL: a row rebuilt from scratch would carry the same URL
    and compare equal, while having lost its probe, its media and its job id. That is the whole
    difference between editing a batch and re-entering it.
    """
    staging = a_staging("https://a.invalid/1", "https://b.invalid/2")
    kept, replaced = staging.visible
    kept.state = RowState.READY
    replaced.state = RowState.READY

    fresh = staging.reconcile(["https://a.invalid/1", "https://c.invalid/3"])

    assert staging.visible[0] is kept, "an untouched line lost its row, and its probe with it"
    assert kept.state is RowState.READY
    assert [row.url for row in fresh] == ["https://c.invalid/3"]
    assert replaced.state is RowState.SUPERSEDED


def test_a_line_that_is_gone_is_superseded_rather_than_dropped() -> None:
    """`T016-R1`: a result already in flight still arrives, and has to be refused **by name**.

    Deleting the record would leave the refusal in `_on_media_probed` unreachable — a guard that
    reads as protection while protecting nothing, which `ai/TESTING.md` §13 exists to catch.
    """
    staging = a_staging("https://gone.invalid/x")
    row = staging.visible[0]
    row.job_id = "job-1"
    row.state = RowState.PROBING

    staging.reconcile([])

    assert staging.visible == ()
    assert row.state is RowState.SUPERSEDED
    assert staging.for_job("job-1") is row, "the late result has nothing to be refused against"


def test_reconciling_bumps_the_generation() -> None:
    """A line typed, cleared and retyped produces a row that cannot be confused with the first."""
    staging = Staging()
    first = staging.generation
    staging.reconcile(["https://a.invalid/1"])
    original = staging.visible[0]

    staging.reconcile([])
    staging.reconcile(["https://a.invalid/1"])

    assert staging.generation > first
    retyped = staging.visible[0]
    assert retyped is not original
    assert retyped.generation > original.generation


# --- what may be committed ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "allowed"),
    [
        (RowState.PENDING, False),
        (RowState.SAVING, False),
        (RowState.WAITING, False),
        (RowState.PROBING, False),
        (RowState.READY, True),
        (RowState.FAILED, False),
        (RowState.SUPERSEDED, False),
    ],
)
def test_only_a_resolved_row_may_be_committed(state: RowState, allowed: bool) -> None:
    """`UX-003` in one assertion, over **every** state rather than a sampled pair.

    Adding a state without deciding which side of this line it falls on fails here, which is the
    same shape `job_state.py`'s transition table is tested with.
    """
    row = Row(url="https://a.invalid/1", generation=1, state=state)
    assert row.committable is allowed


def test_a_failed_row_stays_visible_and_out_of_the_commit() -> None:
    """`UX-003`'s first rule: a URL that will not probe never becomes queued work.

    It stays on screen with its message so a timeout costs a button press rather than the paste —
    refusing the whole batch was the alternative, and it loses thirty URLs to eight bad ones.
    """
    staging = a_staging("https://good.invalid/1", "https://bad.invalid/2")
    good, bad = staging.visible
    good.state = RowState.READY
    bad.state = RowState.FAILED
    bad.message = "ERROR: [generic] Unable to download webpage: <urlopen error timed out>"

    assert staging.committable() == (good,)
    assert staging.failed() == (bad,)
    assert bad in staging.visible, "the failed row was hidden, so its message went with it"


def test_every_row_holding_a_staging_job_is_reported_for_unstaging() -> None:
    """What `done()` has to stop — **whatever state the row reached** (`T118-R1`).

    Resolved, failed and superseded rows all still own a transient probe until it is released, and
    a row that was never staged owns nothing: passing `None` to `unstage` would be an error rather
    than a no-op.

    *(This asked `unresolved_job_ids()`, which excluded `READY` rows on the reasoning that Add
    would commit them. Nothing is written before Add now, so a `READY` row nobody committed is a
    probe like any other and close must stop it too — `T118-R11`.)*
    """
    staging = a_staging("https://a.invalid/1", "https://b.invalid/2", "https://c.invalid/3")
    ready, failed, never_staged = staging.visible
    ready.state, ready.job_id = RowState.READY, "job-ready"
    failed.state, failed.job_id = RowState.FAILED, "job-failed"
    never_staged.state = RowState.PENDING

    assert staging.staged_job_ids() == ("job-ready", "job-failed")


def test_a_superseded_rows_job_is_reported_for_unstaging_too() -> None:
    """The row the user replaced still owns a probe, and nobody is waiting for its answer."""
    staging = a_staging("https://a.invalid/1")
    row = staging.visible[0]
    row.job_id = "job-1"
    row.state = RowState.PROBING

    staging.reconcile([])

    assert staging.staged_job_ids() == ("job-1",)


# --- when the batch is done ----------------------------------------------------------------------


def test_an_empty_batch_is_not_settled() -> None:
    """`all([])` is `True`, and `T088-R4` is what that costs.

    An observer that reported "everything is finished" for nothing at all turned a strict xfail
    into an `XPASS` and announced a repair that had not happened. Nothing pasted is not a batch
    that has resolved.
    """
    assert Staging().settled() is False


def test_a_batch_is_settled_only_when_every_visible_row_has_an_answer() -> None:
    staging = a_staging("https://a.invalid/1", "https://b.invalid/2")
    first, second = staging.visible
    first.state = RowState.READY

    assert staging.settled() is False

    second.state = RowState.FAILED
    assert staging.settled() is True, "a failure is an answer; the batch is as resolved as it gets"


def test_a_superseded_row_does_not_hold_the_batch_open() -> None:
    """Nobody is waiting on a line that is no longer entered."""
    staging = a_staging("https://a.invalid/1", "https://b.invalid/2")
    first, second = staging.visible
    first.state = RowState.READY
    second.state = RowState.PROBING

    staging.reconcile(["https://a.invalid/1"])

    assert staging.settled() is True


# --- the summary line ----------------------------------------------------------------------------


def test_a_urls_placeholder_tile_is_stable_and_process_independent() -> None:
    """`UX-003`: a row is filled the moment it appears, and keeps its tile.

    Stability is the whole property. `hash()` would satisfy "derived from the URL" and is salted
    per process, so every launch would repaint the queue in different colours — which is worse
    than no tile, because it looks like the rows changed.
    """
    first = placeholder_hue("https://example.invalid/a")
    assert first == placeholder_hue("https://example.invalid/a")
    assert 0 <= first < 360

    neighbours = {placeholder_hue(f"https://example.invalid/{n}") for n in range(8)}
    assert len(neighbours) > 1, "adjacent URLs all drew the same tile, so the column is one colour"


def test_the_summary_names_the_state_in_words() -> None:
    """`NFR-005`: never a colour alone. The counts come from the rows, not from a second tally."""
    # **An empty batch says nothing here** (`T-218`). This asserted "Paste one URL per line.",
    # which the paste box's placeholder already said; the instruction now lives inside the empty
    # list, where it explains the space it is in. A summary of no rows has nothing to summarise.
    assert summarise(()) == ""

    rows = [Row(url=f"https://a.invalid/{n}", generation=1) for n in range(3)]
    assert summarise(rows) == "Reading 3 URLs — 0 done"

    rows[0].state = RowState.READY
    assert summarise(rows) == "Reading 3 URLs — 1 done"

    rows[1].state = RowState.READY
    rows[2].state = RowState.FAILED
    assert summarise(rows) == "2 ready · 1 URL could not be read"

    rows[2].state = RowState.READY
    assert summarise(rows) == "3 ready"


def test_the_summary_pluralises_the_failures_it_reports() -> None:
    """One bad URL and two are different sentences, and a user reads the sentence."""
    rows = [
        Row(url=f"https://a.invalid/{n}", generation=1, state=RowState.FAILED) for n in range(2)
    ]
    assert summarise(rows) == "0 ready · 2 URLs could not be read"


# --- T-114: which rows repeat something (REQ-022, UX_SPEC §9.3) --------------------------------


def test_a_url_the_queue_already_holds_is_marked() -> None:
    """`REQ-022` as rescoped: the comparison is against **the live queue**, in memory.

    There is no record of past downloads to consult — `REQ-020` is withdrawn and migration `0009`
    dropped the table — so *downloaded before* is not a question this can ask.
    """
    staging = Staging()
    staging.reconcile(["https://a.invalid/one", "https://a.invalid/two"])

    staging.mark_duplicates(["https://a.invalid/two"])

    assert [row.duplicate for row in staging.visible] == [None, Duplicate.QUEUED]


def test_the_second_occurrence_in_a_paste_is_marked_and_not_the_first() -> None:
    """`T-114`'s own criterion, and the direction matters.

    Marking both would say the first line is a duplicate of the second, which is not a thing that
    happened: the user pasted one link and then repeated it.
    """
    staging = Staging()
    staging.reconcile(["https://a.invalid/one", "https://a.invalid/one", "https://a.invalid/one"])

    staging.mark_duplicates([])

    assert [row.duplicate for row in staging.visible] == [None, Duplicate.PASTED, Duplicate.PASTED]


def test_a_url_that_is_both_queued_and_repeated_says_it_is_queued() -> None:
    """The stronger statement wins: there is a row elsewhere to go and look at."""
    staging = Staging()
    staging.reconcile(["https://a.invalid/one", "https://a.invalid/one"])

    staging.mark_duplicates(["https://a.invalid/one"])

    assert [row.duplicate for row in staging.visible] == [Duplicate.QUEUED, Duplicate.QUEUED]


def test_a_url_matching_nothing_is_marked_nothing() -> None:
    """The silent case, which an over-eager implementation breaks."""
    staging = Staging()
    staging.reconcile(["https://a.invalid/one", "https://a.invalid/two"])

    staging.mark_duplicates(["https://a.invalid/three"])

    assert staging.duplicates() == ()
    assert all(row.duplicate is None for row in staging.visible)


def test_a_marking_is_recomputed_rather_than_accumulated() -> None:
    """The queue moves underneath an open dialog: a job finishes, a row is removed.

    A marking that was only ever *set* would go on saying *already in the queue* about a queue that
    no longer holds it — and the user would be told a fact that had stopped being true while they
    were looking at it.
    """
    staging = Staging()
    staging.reconcile(["https://a.invalid/one"])
    staging.mark_duplicates(["https://a.invalid/one"])
    assert staging.visible[0].duplicate is Duplicate.QUEUED

    staging.mark_duplicates([])

    assert staging.visible[0].duplicate is None, "the marking outlived the job it was about"


def test_a_superseded_row_is_never_a_duplicate() -> None:
    """A retyped line is not on screen, so it cannot be reported as repeating anything — and it
    must not make the line that replaced it look like a repeat of itself."""
    staging = Staging()
    staging.reconcile(["https://a.invalid/one"])
    staging.reconcile(["https://a.invalid/two"])

    staging.mark_duplicates(["https://a.invalid/one"])

    assert staging.duplicates() == ()
    assert all(row.duplicate is None for row in staging.rows)


def test_matching_is_exact_rather_than_clever() -> None:
    """`P-28`, ruled 2026-08-07: **no detection by content**.

    Two URLs for the same video are not detectable without a heuristic nobody has specified, and
    `REQ-022` says *URL*. A near-miss matcher that was wrong occasionally would be worse than one
    that is narrow always — this test is what stops one being added without the ruling changing.
    """
    staging = Staging()
    staging.reconcile(["https://a.invalid/one?t=30", "https://A.INVALID/one"])

    staging.mark_duplicates(["https://a.invalid/one"])

    assert staging.duplicates() == (), (
        "a URL that merely resembles a queued one was marked; P-28 refuses detection by content"
    )


def test_every_kind_of_duplicate_has_words() -> None:
    """`NFR-005`: the row says it. A kind with no sentence is a state carried by nothing."""
    for kind in Duplicate:
        assert DUPLICATE_TEXT.get(kind), f"{kind.value} has no words to say on the row"
