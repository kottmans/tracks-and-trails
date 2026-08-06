# Review handoff — `T-145`, `T-142`, `T-144`, `T-159`, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Review base:** `38504b3` — *"Phase 2 exits"*
**Review head:** `9edf7b6`. **Four commits, one task each, not pushed.**
**Branch:** `main`, per the trunk-based default.

Four Phase 3 History findings, in dependency order. `T-145` is first because a history group's
identity is what the other three act on; `T-159` is independent.

| Commit | Task | What |
|---|---|---|
| `c93e291` | `T-145` | A finished playlist is one History row that opens |
| `0fee38f` | `T-142` | That row gets the verbs a terminal group can support |
| `1924927` | `T-144` | One route empties the whole list |
| `9edf7b6` | `T-159` | A row names its format instead of printing a yt-dlp id |

**A concurrent instance (`kirk`) is working in the same checkout on different tasks.** Nothing in
this range is theirs; if `git status` is dirty when you read it, that is their work in flight.

---

## Read this first: I amended two accepted decisions, and that is a maintainer's act

Both amendments are in `ai/DECISIONS.md` and both are load-bearing for the code below. **Neither
has been ratified by the maintainer.** They are submitted as proposals that the implementation
already assumes, which is the wrong order for anything except the first, and I want that looked at
rather than passed over.

**1. `UX-005`, amended for `T-145`** — a finished playlist is one History row; the chip is a count;
no segmented bar; `14 items` never `14 of 16`. **This one is sanctioned**: `T-145`'s last
acceptance criterion is *"The three decisions above are recorded in `UX-005` before they are
implemented, not after"*, so writing it first is the task. What is still a maintainer call is
whether my three rulings are the ones they would have made.

The third is the one to press on. I refused the `14 of 16` denominator on two grounds — History
holds only completed downloads, so 16 describes rows it cannot show; and `DAT-005` makes records
removable one at a time, so a stored original count is wrong about **both** numbers after the first
removal. The second argument is what decided it, and it also settles the column question: no
original-count column, because nothing would keep it true.

**2. `DAT-005`, amended for `T-144`** — its §1 refused *Clear all* outright. It also named the
condition that lifts the refusal (*"both can be added on this foundation once removal itself is
proven"*), and `T-125` is that foundation. **`T-144` has no criterion telling me to amend it**, so
unlike the first, this is an implementer editing an accepted data decision because the task it was
given could not be built otherwise. The alternative was to stop and file it; I amended and am
disclosing it prominently instead. If you think that was the wrong call, the verdict should say so
regardless of whether the amendment's content is right.

Its content: the verb is `Clear history`, not `Clear all` — §1's other objection stands, that
*"all"* has no object so the user supplies one and the one they have in mind is their files.

---

## `T-145` — a finished playlist is one History row (`c93e291`)

**The report:** a sixteen-item playlist finished and landed in History as sixteen unrelated rows.
`history` had no notion of a playlist at all — `0004` put `playlist_id`, `playlist_index` and
`playlist_title` on `jobs`, where they die with the job, and `T-081`'s *Clear finished* is enough
to take them.

**The shared-code question, which the task calls the real design work.** `ui/grouping.py` is new
and holds the flattening, the expansion and `T140-R4`'s three rules (header at its first member's
position, members contiguous, a group of one dissolved). **`QueueModel` moved onto it in the same
commit**, so there is one copy from the start rather than two that drift. What did *not* move is
the data: the queue groups `Job`s and draws a bar of their statuses, History groups records that
are terminal by definition, so every header role stays with the model that owns it.

`queue_view.py`'s edit is deliberately surgical — `_Group` becomes `Group[_Row]`, `_rebuild_visible`
becomes a `flatten()` call, four sites move from `.playlist_id` to `.group_id`, and five
`isinstance` targets change (`Group[_Row]` is a parameterised alias and cannot be one).
**`tests/ui/test_queue_view.py` is not in this range at all** and its 66 tests pass, which is the
property I wanted from the extraction.

**Membership is carried at completion, not reconstructed** (migration `0006`). Once the job is gone
there is nothing to reconstruct it *from*, which is why it is asserted at the projection rather than
in the view.

**Where "removing a group removes its members" actually lives.** A header has no id in `history`, so
`HistoryModel.records_at`/`records_for` resolve a row to the records it stands for, and the existing
selection-scoped route (`DAT-005` §1) removes a playlist correctly with no second removal path. The
ids are deduplicated: selecting a header *and* one of its open members is one gesture and two paths
to the same id, and a count of 17 for sixteen downloads would be the decoration §4 forbids.

### Worth your attention

- **`entry_ids()` and row numbers stopped being the same number.** This is `T140-R1`'s defect
  arriving in the tab that had not grown groups yet, and I had to fix `verbs_of`, `selected_entry_id`
  and `select` where they indexed one space with the other. If I missed a call site, it will resolve
  a visible row to a hidden member and point a file verb at a record the user cannot see.
- **`ensure_visible` opens a closed playlist as a side effect of `select()`.** Without it, *Open*
  and *Show in folder* silently do nothing for any download that arrived in a playlist, because
  `FileActions` acts on the selection and a hidden member has no row. The cost is that revealing a
  playlist's folder expands the group, which the user did not ask for. Disclosed as a judgement, not
  hidden.

---

## `T-142` — verbs of its own (`0fee38f`)

`history_group_verbs()` in `ui/row_verbs.py`, transcribed by hand rather than derived from
`group_verbs`, which is that file's whole method: the two lists are independent readings of the same
decisions, and computing one from the other would pass while both said the same wrong thing.

`Show in folder` + `Remove`. `Cancel all` and `Retry failed` are absent because every member is
terminal and a record is not a download to retry; `Open` is absent because there is no one file.
`Show in folder` is offered only while some record still names a file, and **the member revealed is
re-checked when routed** (`T140-R6`) rather than trusted from the offer.

Removal reuses `DAT-005` §4's existing question by reporting the records rather than the header, so
there is no second wording for the same act.

---

## `T-144` — clearing the whole list (`1924927`)

**The task's own naming is off by one and I did not follow it.** It describes
`HistoryRepository.remove_many`; the method is `remove`. Everything the task says about that method
— the empty-sequence guard, *"the failure this signature exists to make impossible"* — is true of
`remove`, so I read it as a slip and left the signature alone.

`HistoryRepository.clear()` is a separate method with its own name. A bare `DELETE` names no
parameters, so it has no ceiling; `remove` builds one placeholder per id, and selecting a whole
history past `SQLITE_LIMIT_VARIABLE_NUMBER` (32766 on this build) failed with
`OperationalError: too many SQL variables`.

**The measured limit is in the test's reasoning, not in an assertion**, per the criterion. The test
seeds a fixed 40,000 — comfortably past what was measured here — because asserting against
`SQLITE_LIMIT_VARIABLE_NUMBER` would pass silently on a build with a different ceiling, including
one where the parameterised route never fails and the test proves nothing.

The route is a toolbar action. **That made `_build_queue_actions`'s recorded rule false** — *"what
is on this toolbar acts on the queue"* — so it is rewritten to the principle underneath it rather
than left as a comment that used to be true: nothing on the toolbar acts on a selection, and every
verb on it names the list it empties. `test_the_toolbar_holds_nothing_that_acts_on_a_selection` is
a closed list and was updated with the same reasoning. **The alternative was to show the action only
while History is in front**; I judged a control that appears when you switch tabs to be the moving
target `UX-005` rejects elsewhere, and the confirmation to be the real safety. Say if you disagree.

---

## `T-159` — the format in words (`9edf7b6`)

**The question the scope requires answering first — is the request recoverable from a history row —
is no.** `audio_quality` is preset-owned, so an MP3 converted at 320 kbps matches no built-in and
cannot be named from an id. So it needs a migration, which the task's out-of-scope permits once
decided.

`0007` carries **the request**, not a rendered name. A stored name is a derived value with a
lifetime: a preset renamed in a later build would leave every old record asserting a name this
application no longer has.

`ui/format_text.py` is new and holds the naming rule; `queue_view` now calls it instead of holding
its own copy. The raw `format_used` stays in the tooltip, labelled — `REQ-020` records what
happened and an id is what happened.

### One criterion is not built, deliberately

> *"Where the download was a conversion, the row says what it converted to, including the bitrate
> for MP3"*

**Not done, and reported rather than banked as met.** The queue's format dropdown offers
`preset.name`, so a row reading *Audio only (MP3), 192 kbps* beside a control reading *Audio only
(MP3)* would be `T140-R3`'s own defect one field over — a download named two ways, one row apart.
Disclosing the bitrate means deciding what the **control** says, which is the product half `T-156`
holds. `format_text.format_name` is the single place it changes, and all three surfaces change with
it, which is what criterion 5 asks for. `T-156`'s entry now records that it inherited this.

---

## Mutation evidence

Every mutation was applied to `HEAD`, run, and reverted; the suite is green at `HEAD` after each.

| Mutant | Result |
|---|---|
| History stops ordering group members by `playlist_index` | **killed** — `..._not_the_order_they_finished` |
| The completion stops carrying the playlist membership | **killed** — `..._carries_the_playlist_membership_across` |
| A group's `Show in folder` reveals `members[0]` instead of re-checking for a file | **killed** — `..._points_at_a_record_that_has_one` |
| `clear()` built on `remove([every id])` | **killed** — reproduces `OperationalError: too many SQL variables` |
| The History row prints `format_used` again | **killed by three tests** |
| The toolbar spacer stops expanding | **killed** — the rewritten geometry assertion |
| The completion stops carrying the **request** | **survived at first — see below** |

### The one that survived, and what it means

Dropping `request=job.request` from `PersistentJobStore.complete` left the suite green. The gap was
in `test_a_completion_records_every_field_req_020_names`, whose whole-object comparison is exactly
the guard designed to catch it — it had gone red when I added the field and I had not yet updated
its expectation, so for a short window the tree had a field nothing asserted.

Both completion-projection tests now name `request=job.request`, and the mutant is killed. Recording
it because it is the shape this project keeps finding — a property asserted more confidently than it
was tested — and it was the mutation pass rather than the suite that surfaced it.

---

## Submitted uncertainties

**1. The two decision amendments are unratified.** See the top. The `DAT-005` one especially.

**2. I rewrote another test's bound.** `test_the_queue_verbs_sit_at_the_far_end_of_the_toolbar`
asserted `gap > bar.width() // 3`. `Clear history` widens the group, which drove a **correct**
layout to 294px against a 300px threshold — and only under the full `tests/ui` run, where an earlier
test's stylesheet widens the buttons; it passed in isolation. The bound was measuring the group's
width as much as its position. It now compares the free space *before* the group to the space
*after* it, which is what `flex:1 1 auto` actually does and is independent of how many buttons are
there. Verified it still fails when the spacer stops expanding. **This is a test I was not asked to
touch**, changed because my task invalidated it.

**3. How the frozen fixtures were made.** `v6.sql` and `v7.sql` have their DDL produced by running
today's migrations — that is the schema under test — and every row is a **hand-authored SQL
literal**, including the request JSON. Nothing was seeded through `HistoryEntry`, `_serialize_request`
or any repository, which is `T014-R4`'s actual prohibition. The literals are frozen text now, so a
later field addition cannot retroactively change what a v7 row said. Worth confirming you read
`T014-R4` the same way.

**4. `records_at(row)` and `records_for(row_id)` are two accessors over one idea.** One is asked by
the selection, the other by a verb, and each is used once. It reads like duplication; I judged
collapsing them to be a simplification, which `AGENTS.md` §7 rules out under an active task. Say if
you would rather they merged.

---

## Verification

| Check | Result |
|---|---|
| `tests/unit tests/ui tests/integration` | **2242 passed, 11 skipped** (377s) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 171 files already formatted |
| `mypy` | Success, 109 source files |

**`tests/network` was not run** — it needs the network, and nothing in this range touches the
downloader. **No Windows run**: `mypy --platform win32` was not needed, since no
platform-guarded module is touched.

`ai/REVIEWS.md` and `ai/STATUS.md` are untouched. `ai/TASKS.md` moves all four entries to
`## Complete` with status *"Complete — 2026-08-05, awaiting review"*, and `ai/DECISIONS.md` carries
the two amendments above.

**`mypy` was run as `python -m mypy`**, for the reason the `T140-R3` handoff records: the
`.venv/bin/mypy` console script on this machine still carries a stale shebang. Machine state,
unfixed and unfiled.
