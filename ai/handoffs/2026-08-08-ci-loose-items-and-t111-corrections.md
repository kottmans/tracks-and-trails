# Session handoff — CI, the loose Phase 3 items, and `T-111`'s corrections, 2026-08-08

**From:** Implementer
**To:** Reviewer (Codex), and the maintainer for the ruling in §2
**Review base:** `bf30d82` — the head at the start of this session, and the head Codex's `T-111`
review was written against
**Review head:** **uncommitted working tree.** Nothing committed or pushed (`AGENTS.md` §7)
**Branch:** `main`. Serial mode, no wave.

**Four things happened and they are separable.** Only §5 answers an existing review; §1 answers a
question and changed nothing; §2 is a maintainer ruling; §3 and §4 are two new task
implementations that share the tree with §5 and touch none of the same files.

| § | What | Needs |
|---|---|---|
| 1 | CI investigation — three failed runs | Nothing. Already fixed before this session |
| 2 | The six loose Phase 3 items ruled into the phase | Recorded; the ruling was the maintainer's |
| 3 | `T-143` implemented | Review. `## In Review` |
| 4 | `T-180` implemented | Review. `## In Review` |
| 5 | `T-111`'s three findings corrected | **Re-review.** Own handoff: `2026-08-08-T-111-r2.md` |

---

## 1 · CI — three failures, two causes, both already fixed

Asked and answered; **no work came out of it**, and it is here so the answer is on the record.

| Run | Commit | Failed | Cause |
|---|---|---|---|
| `31240478847` | `4cb549d7` | linux, windows desktop | mypy |
| `31245177017` | `4cb549d7` (nightly) | linux, windows desktop | the same mypy, re-run on schedule |
| `31268442524` | `ff50b4f` | windows desktop | a path-separator assertion |

- **mypy, three errors** in test files, failing `Types, tests included` and `Types under the Windows
  platform` alike: `tests/ui/test_options_dialog.py:39` (a generator fixture with no `Generator`
  return type) and two on `tests/integration/test_end_to_end.py:720` (a `dict.get` overload). Fixed
  by `da7f97b`.
- **A Windows-only assertion**: `test_the_preview_follows_every_keystroke` asserted
  `preview.endswith("clips/A video with formats.ext")` against a **native** path, so it held on
  Linux and failed on Windows against the equally correct `clips\...`. Fixed by `c5997fd`, which
  compares `Path(preview).parts[-2:]`.

Both fixes were verified here rather than taken from the green run: `mypy` and
`mypy --platform win32` clean, and the preview test passes.

**One thing worth knowing rather than fixing:** `bf30d82` has **no CI run at all**, and that is
correct. It touches only `ai/roadmap-phase-3.html`, which `ci.yml`'s `paths-ignore` exempts and
`prose.yml`'s `paths` (`ai/TASKS.md` only) does not match. The newest commit on `main` is unverified
by construction, which is the design working rather than a gap.

## 2 · The six loose Phase 3 items are in Phase 3 — maintainer ruling

Six tasks sat under `## Proposed — Phase 3`, filed as findings and maintainer reports **during** the
phase, never ruled in or out. That is the position both prior exit reviews found wrong rows in.

**Ruling (maintainer, 2026-08-08): all six are in Phase 3's scope**, so Phase 4 opens without Phase
3 questions attached to it. `IMPLEMENTATION_PLAN.md` §Phase 3 now names them with dispositions and
states that the exit is not clear while any is unresolved — **including by explicit refusal**.

| Task | Disposition |
|---|---|
| `T-143` | **Implemented**, §3 below |
| `T-180` | **Implemented**, §4 below |
| `T-189` | **Open.** Guards exit criterion 2's *evidence* — see the note below |
| `T-171` | **Open, and the maintainer's.** Measurement done, decision outstanding. Moved from *"Phase 4 or later"* by this ruling |
| `T-186` | **Open.** Comments and docstrings; no runtime behaviour |
| `T-188` | **Open, held open by `OPS-013`** — it needs a licensed public source to exist |

`T-146` and `T-190` also sit under that heading and are **not** in the set; both are named in the
plan so their absence reads as a decision.

**`T-189` is the one I would not leave until after the exit.** Criterion 2 is marked *Met* and its
proof — `test_a_chosen_video_and_audio_pair_produce_one_merged_file` — takes the ordinary `ffmpeg`
fixture, which *skips* when the tool is absent, on a self-hosted Windows runner that **records
rather than installs** it. The evidence is real today (ffmpeg 8.1.2 at run `31233348009`); what is
missing is anything forcing it to stay real. A criterion already signed is the worst place for that.

## 3 · `T-143` — the premise was stale, and the defect underneath it was not the one in the title

**The title has been false since `T137-R2` was resolved**, and the entry asserted it in the present
tense for four days. Both admission routes admit an unprobed row as `PROBE` — `ui/add_dialog.py`
live, `app.py` at startup so a crash between the durable write and the admit cannot bypass it — and
`_probe_settled` carries the probe into its download (`ARC-009`).

**This is the reusable part, and it is the second time**: `T105-R1` was the same shape. *A finding
resolved against one task can close another task's premise, and nothing walks the entries to say
so.* The entry now carries the correction with the original struck rather than deleted.

**What was actually left** is a real defect the title does not describe. `_claim_outcome`'s `Probed`
branch persisted `title`, `thumbnail_url` and `is_live` and **dropped `uploader` and
`duration_seconds`**, while `add_dialog._durable_job` carried the whole set across for a *pasted*
URL. So a playlist entry probed, got a title and a picture, and still showed no uploader and no
duration beside a pasted row showing both — *"their rows stay bare"*, exactly as reported, for a
different reason than the title gives. `T124-R4` had already corrected this in the add dialog and
its docstring says *"adding the next one is a schema change and not a second omission."* **This was
the second omission.**

Three new cases in `tests/integration/test_manager.py`: the stored fields, per-entry failure
isolation, and a probe cancelled by removing its row (`T118-R1`'s lesson at the durable seam). The
fields case is mutation-checked.

**One criterion word was never satisfiable and is flagged rather than claimed: "size".** It lives
per-format in `FormatInfo.filesize`; `Job` carries `bytes_total`, which a *download* reports. A
pasted URL's row has no size before it runs either, so an entry is now **consistent with one** —
which is the bar `UX-005` §3 sets. Showing a size on an unstarted row means storing the chosen
format's `filesize` on the job: a schema change and a separate decision.

## 4 · `T-180` — the cache is partitioned per database, and the old one is adopted

`core/paths.cache_root_for` derives a root from the **resolved database path** via
`derived_component` — the two primitives `lock_path_for` and `T113-R1` already use, so the guard and
the cache cannot disagree about what "the same database" means. Composition derives it; `ui/` is
handed a root and never learns what a database is.

**Both halves of `T179-R1` close, and only one was destructive.** *Deletion*: `_SweepTask` now
iterates a directory this instance owns alone, so there is nothing foreign to unlink. *Blindness*:
`cache_generation` is keyed by directory, so a process-local publication count is now complete — it
inherited the fix rather than needing one. The docstring that recorded the problem as unsolved is
rewritten rather than deleted.

**The existing cache is adopted, not stranded**, and that is the task's own risk line answered
rather than accepted: *"a careless version strands every existing thumbnail — regenerable, but a
wholesale refetch is not a quiet event on a large queue."* One rename on first run. First database
to launch adopts it, which is defensible rather than derived — the shared directory is the mixture
the collision produced, so no partition has a better claim, and the adopter's own sweep then
collects what it does not name. Every failure mode leaves the legacy alone and costs one refetch.

**The partition wanted no migration** — a directory rename touches no schema — so the entry's
*"unless the partition turns out to want a migration"* condition did not fire and `T-180` stays in
Phase 3.

Nine new cases across `tests/unit/test_paths.py` and `tests/ui/test_queue_view.py`. The
cross-database sweep case is **mutation-checked**: with the partition removed it fails on the
foreign picture being deleted.

## 5 · `T-111` — Codex's three findings, all corrected

Codex reviewed at `bf30d82` during this session: **Changes requested**, two High and one Medium.
All three corrected; **none claimed closed**. Full detail in
`ai/handoffs/2026-08-08-T-111-r2.md` — the short version:

- **`T111-R1` (High)** — `_build_form` said the seven options have an editor already and that a
  second set of controls would be two screens answering one question. Right, and only half-built:
  nothing ever opened the other screen. An `Options…` button now opens the same `OptionsDialog` on
  the selected saved preset and writes through `update_preset`.
- **`T111-R2` (High)** — the collision policy was enforced everywhere except where a file enters.
  `_presets_from` checked shape and not names, so a hand-edited `Audio only (MP3)` loaded clean and
  every name-addressed operation became ambiguous. Now refused and reported per `ARC-008`, which
  **applies the stated policy rather than inventing one**: `add_preset` refuses a name the user
  typed, and a hand-edited file is a typed name.
- **`T111-R3` (Medium)** — the manager opened synchronously from `StagingModel.setData`, inside
  Qt's `commitData`. Deferred one turn, as `open_options` already is. **The shipped test encoded
  the defect** — it asserted the callback fired synchronously — so it was inverted, and a new case
  drives the real combo through `commitData`.

---

## Checks, with their actual results

Run on the working tree, Linux:

| Check | Result |
|---|---|
| `ruff check` | All checks passed |
| `ruff format --check` | 213 files already formatted |
| `mypy` (src + tests) | Success: no issues found in 124 source files |
| `mypy --platform win32` | Success: no issues found in 124 source files |
| `pytest tests/unit/test_task_placement.py` | 14 passed — the prose gate, and it **caught a real mistake** |
| `QT_QPA_PLATFORM=offscreen pytest` | **2766 passed, 14 skipped, 2 deselected** in 368 s |

CI at `54e24ab` was **2743 passed, 14 skipped**. The 23 additions are 12 for `T-143`/`T-180` and 11
for the `T-111` corrections. Linux only; nothing here is POSIX-specific and CI covers Windows.

**The placement gate earned its keep.** Moving `T-143` and `T-180` to `In Review` status while their
entries still sat under `## Proposed — Phase 3` failed `test_every_entry_sits_under_the_section_its_status_names`
immediately. That is `T-096` doing exactly the job it exists for, on the exact class of drift this
session's §3 is about.

## What is not claimed

- **Nothing committed or pushed.** `AGENTS.md` §7.
- **`ai/REVIEWS.md` was not edited.** It is the reviewer's append-only record; the status of
  `T111-R1`/`R2`/`R3` is Codex's to change. It shows as modified in `git status` because Codex's
  own review landed in it during this session.
- **No verdict is claimed for `T-143`, `T-180` or `T-111`.** All three sit in `## In Review`.
- **Windows runtime and real sites remain unverified**, as in every handoff this phase. Nothing here
  is platform-specific.
- **`T-189`, `T-171`, `T-186` and `T-188` are untouched.** They are in scope per §2 and open.
