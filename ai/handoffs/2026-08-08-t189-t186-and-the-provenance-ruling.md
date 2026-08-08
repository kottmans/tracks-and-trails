# Review handoff — `T-189`, `T-186`, and two maintainer rulings, 2026-08-08

**From:** Implementer, and the maintainer for §1 and §4
**To:** Reviewer (Codex)
**Review base:** `4b430de` — *"Redraw the board: nine of nine, and it leaves the repository"*
**Review head:** `6a0d97f` — **committed this time**, five commits, clean tree
**Branch:** `main`. Serial mode, no wave.

```
git diff 4b430de..6a0d97f
```

**Two verdicts are wanted**, and two items are here for awareness rather than approval.

| § | What | Needs |
|---|---|---|
| 1 | `T-171` — refused, `DAT-008` accepted | **Awareness.** A maintainer ruling; the task is `## Complete` |
| 2 | `T-189` — a missing ffmpeg now fails the runs that prove `T-108` | **Review.** `## In Review` |
| 3 | `T-186` — the withdrawn-History prose sweep | **Review.** `## In Review` |
| 4 | `AGENTS.md` — one commit per task | **Awareness.** A maintainer instruction, now a standing rule |

**`T-188` is deliberately not in this boundary.** It is the last open Phase 3 item and the source
hunt is in progress; nothing has been produced for it, and this handoff does not claim otherwise.

---

## 1 · `T-171` — refused, and `DAT-008` records why

**A maintainer ruling, not an implementation.** The task asked whether output files should carry a
record of how they were produced; the answer is no, and the task closes as a rejection with its
reasons — which is what its seventh criterion asks for. No implementation task follows and no
dormant UI was added.

The reasoning is in `DAT-008` in full. The one fact worth surfacing here, because it changed
*after* the measurement `T-171` rests on: **`T-109` added `embed_metadata`**, configuring yt-dlp's
`FFmpegMetadata`. The legitimate "this file should say what it is" is already built, already
opt-in, and already the user's. `DAT-008` does not touch it, and does not foreclose Phase 4.5
exposing more of yt-dlp's metadata options under `ARC-010`.

**`T171-R1` is moot rather than resolved, and the entry says so.** Your finding — that criterion
1's matrix does not exist and the evidence is surrogate — **is still true**. The matrix was never
completed because the decision it was to inform came out no. `DAT-008` records the reopening
condition so the matrix is visibly the first thing owed if anyone returns.

*(The measurement file has one stale sentence, flagged in the task entry rather than edited: it
reports `--embed-metadata` as never configured, true on 2026-08-06 and capability-false since
`T-109` landed. The §3 container finding the decision rests on is unaffected.)*

## 2 · `T-189` — the gate that could evaporate

**What was wrong.** `test_a_chosen_video_and_audio_pair_produce_one_merged_file` is exit criterion
2's evidence on both platforms and it takes the ordinary `ffmpeg` fixture, which **skips**. The
self-hosted Windows runner *records* ffmpeg rather than installing it (`OPS-005` — it is the
maintainer's own machine). The day it loses the tool, a required proof becomes a `SKIPPED` line
inside a green job and the criterion is silently unevidenced.

**What was built.** `resolve_ffmpeg` keeps the developer's skip and adds one branch: with
`TRACKSANDTRAILS_REQUIRE_FFMPEG` set, an absent tool **fails**. The two jobs carrying the proof set
it — `check`'s *Tests* step and `windows-desktop`'s *Full suite*. **Nothing installs anything**,
which the task's scope requires.

Three decisions worth your attention:

- **An opt-in variable rather than a `CI` check or a hostname.** `CI` is set on runners that
  legitimately have no ffmpeg, and detecting the self-hosted machine by name would put the runner's
  identity in the test suite. The workflow declares which jobs carry the proof; the fixture reads
  that declaration.
- **`resolve_ffmpeg` is a function, not only a fixture body.** A fixture can only be exercised by
  tests that request it, and every one of those runs where ffmpeg is *present* — so the decision
  would have been unobservable. This is what makes criterion 4's probe assertable.
- **The probe empties `PATH` rather than mocking.** `ffmpeg_tools` asks `shutil.which`, so hiding
  the executable is the same question a runner that lost the tool will ask.

### The mistake this task made, and it is the part I most want checked

**The first version of the new test had the exact defect the task exists to close.** Written as
`pytest.raises(pytest.fail.Exception)`, a regression to skipping raises `Skipped` — which `raises`
does not catch, so it propagated and **turned the test into a skip**. Mutating the fail branch away
produced `18 passed, 1 skipped` and nothing red.

That is `T-189`'s own subject one level up: a required assertion silently becoming a non-assertion
inside a green run. It was caught by the mutation check and not by reading the test. The case now
uses an explicit `try` with a `skip` arm that calls `pytest.fail`, and re-mutating turns it red —
**please confirm that, since a second pair of eyes on this specific shape is worth more than on the
feature.**

`tests/unit/test_capabilities.py` is new, 19 cases.

## 3 · `T-186` — eight false claims, and two that were not

Both survivors the entry named by hand were among the eight; the full table is in the task entry
and the commit message.

**The sweep is semantic, and two findings are the evidence:**

- **`manager.py` keeps a `history` that is not History.** *"a second `READY` revision to every
  probed job's **history** … asserts that history as a sequence (`ARC-004`)"* is the job's **status
  sequence**. A word replacement would have corrupted a correct comment about a different thing.
- **Two of the eight were reasoning worth keeping, not text worth deleting.** `row_delegate.py`'s
  *"absent means no"* default and `queue_view.py`'s one-shared-rule argument were both *justified*
  by History and remain correct without it. Each now states the surviving reason rather than losing
  it with the sentence that carried it. **This is the judgement call in the task** — the criterion
  says preserve historical rationale that still explains a live invariant, and I read those two as
  live.
- **`_confirm_history_removal` could not be repaired by rewording.** The comment's whole content was
  a pointer to a departed function, so its justification was unreadable from the code. The reason is
  stated in place instead.

**Criterion 2, on what must stay byte-identical:** migrations, frozen fixtures, `ai/archive/` and
`ai/REVIEWS.md` are untouched. **`ai/DECISIONS.md` is not** — it gained `DAT-008` in §1's commit,
which is a different task in the same boundary and purely additive (no deleted lines).

Production behaviour is unchanged; this commit is comments, docstrings and assertion messages.

## 4 · `AGENTS.md` — one commit per task

Maintainer instruction after a session put four tasks in one commit and three in the next. Now a
standing rule in the Git section, with coordination files named as the exception. The same rule is
in the shared convention at `/mnt/projects/software_projects/AI_PROJECT_DOCUMENTATION_CONVENTION.md`
— **which is not a git repository**, so that edit is unversioned and is not in this boundary.

**The last commit here breaks the new rule on purpose and says so.** `6a0d97f` carries `TASKS.md`
bookkeeping for all three tasks, because their entries interleave in one file and the `## In Review`
intro changes for all of them. The code for each task is in its own commit; splitting the ledger
would have been reconstruction rather than separation.

`T-191` is newly filed there — the pre-download size `T143-R1`'s amendment deferred rather than
declined. Phase 4, Low. Its real content is the estimate question `REQ-003` already names.

---

## Checks, with their actual results

Run at `6a0d97f`, Linux:

| Check | Result |
|---|---|
| `git diff --check` | clean |
| `ruff check` | All checks passed |
| `ruff format --check` | 216 files already formatted |
| `mypy` (src + tests) | Success: no issues found in **125** source files |
| `mypy --platform win32` | Success: no issues found in **125** source files |
| `pytest tests/unit/test_task_placement.py` | 14 passed |
| `pytest tests/unit/test_capabilities.py` | 19 passed |
| `QT_QPA_PLATFORM=offscreen pytest` | **2787 passed, 14 skipped, 2 deselected** in 364 s |

2768 → 2787 is `T-189`'s 19 new cases. `T-186` added none, which is correct — it changed only prose.

**`.github/workflows/ci.yml` was not executed.** No `pyyaml` is available in the venv and I would
not install one into the maintainer's environment to lint a workflow, so both `env:` blocks were
verified structurally instead — correct indentation, siblings of `run:`, nested under their step.
**The requirement therefore has not run on a real runner**, and the first CI run at this head is its
first genuine exercise.

## What is not claimed

- **`ai/REVIEWS.md` untouched.** Yours.
- **No verdict claimed** for `T-189` or `T-186`.
- **Windows runtime and real sites remain unverified.** Nothing here is platform-specific, though
  `T-189`'s whole subject is a Windows runner's provisioning.
- **`T-188` is not in this boundary** and is still open.
