# STATUS.md — Tracks & Trails

**Purpose:** Concise snapshot of where the project stands right now.
**Authority:** Canonical for current project state.
**Owner:** Planner / Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-27
**Last verified against repository:** 2026-07-27
**Update when:** A meaningful work session ends, a phase changes, a blocker appears or clears, or the next task changes.
**Does not contain:** Task detail (`TASKS.md`), review history (`REVIEWS.md`), decision rationale (`DECISIONS.md`).

---

**Current phase:** **Phase 1 — Vertical slice.** Phase 0 **formally exited 2026-07-26**.
**Overall state:** Phase 0's five exit criteria were each verified rather than asserted, and the
evidence is recorded in `IMPLEMENTATION_PLAN.md` §Phase 0 — including a fresh mutation run
proving the layering test still fails on a deliberate `PySide6` import in `core/`.

`T-010`, `T-011` and `T-026` are complete. `ARC-003` settled the IPC versioning question.

**Two things the phase exits with, named rather than hidden:**

- The **subjective** half of Windows verification (`OPS-004`) — whether rendering *looks* right,
  whether Narrator *sounds* coherent, whether the installer *feels* normal. Unverified, needs a
  person, and blocks **first release**, not this phase. `T-039` (installer) has no automated gate
  yet either. `T-040` (tab order) is now **Ready** rather than blocked: `T-016` supplied the
  focusable controls and gates their order offscreen, leaving `T-040` the real-Windows half.
- **`T011-R8` is closed.** `T-041` was approved at `0268e13` and the finding is functionally
  resolved. The audit behind it found the hole was not one field but every field of every model
  in `core/models.py`.

## Completed

- Documentation system bootstrapped: `DOC-001`
- Requirements, architecture, phases, and Phase 0 tasks defined
- Foundational decisions accepted: `ARC-001`, `ARC-002`, `DAT-001`, `OPS-001`, `OPS-002`,
  `OPS-003`, `SEC-001`, `REL-001`, `LIC-001`
- **`T-004` complete** — licensed MIT; `LICENSE` written
- **`T-002` complete** — Python 3.14 baseline confirmed (PySide6 ships `abi3` wheels)
- **`T-001` complete** — `pyproject.toml`, 27-module skeleton per `ARCHITECTURE.md` §4,
  `tests/` tree, `docs/DEVELOPMENT.md`. All four checks green from a simulated clean checkout.
- **`T-003` + `T-022` complete and approved** — icon set derived from the maintainer's
  1024×1024 source; brand swatches fixed in `ARCHITECTURE.md` §8; resource invariant tests
  added. Codex requested changes, then approved the corrections on re-review; no open
  findings. Two standing caveats: no SVG exists (no vector source), and 16 px is legible only
  narrowly — `T-021` filed as an optional improvement that blocks nothing
- **First review completed** — the review process in `AGENTS.md` §3 has now been exercised
  end to end (implement → review → correct → focused re-review) and works
- **`T-006` + `T-023` complete** — CI runs on Linux and Windows for every push and pull
  request, squash-merged as `c8a72b8` and green on `main`. Reviewed twice; the final
  documentation correction was maintainer-accepted with the focused re-review waived.
- **`T-005` + `T-024` complete** — layering enforcement test, squash-merged as `d1f45e5`.
  The analyser is guarded against being weakened, verified by eight distinct weakenings. Two
  review rounds; the second re-review was waived by the maintainer.
- **`T-007` complete** — the application shell window, merged as `fa5a3c0`. Opens with the
  icon and title, File → Quit and Help → About, geometry across restarts, clean exit. Cold
  start 0.178 s median against `NFR-002`'s 3 s. **Merged without any independent review** at
  the maintainer's direction — not a waived re-review, no first pass; recorded in its task.
- **`T-020` + `T-025` complete** — frozen-build smoke test and the Phase 0 exit preparation,
  merged as `564aad0`. A frozen artifact spawns a child without relaunching itself on both
  platforms; the clean-checkout verification passes on Linux. The **negative** proof — that
  removing `freeze_support()` breaks it — has now been run on Windows too (`T-029`, run
  `30186080950`).
- **Phase 0 exit review complete, and its eight findings closed** — `T-027` … `T-032`,
  squash-merged as `7b7860d`. `P0-R2` … `P0-R5` were reviewer-verified; the corrections to
  `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **maintainer-accepted without a final
  re-review**, and each task records that.
- **Windows is no longer entirely unverified.** `T-006`'s runners confirmed, with downloadable
  artifact evidence: Python 3.14.6 (MSC v.1944, AMD64), PySide6/shiboken6/Qt 6.11.1, a
  `QWidget` visible offscreen, and the full 27-test suite passing. This discharges the Windows
  carries from `T-002` and `T-003`. The `OPS-003` interactive gaps (screen reader, native
  dialogs, keyboard, theming, installer) remain untouched. They no longer all need a person:
  `OPS-004` splits them into an objective half CI can assert (`T-026`) and a subjective
  residue — whether it *looks* right, whether Narrator *sounds* coherent, installer feel,
  shell foreground behavior, long-running stability — which is what still blocks first release.
- Verified 2026-07-25 that yt-dlp 2026.06.09 is pure Python (1046 `.py`, no compiled
  extensions), which is what makes the `OPS-002` pip-free updater viable
- **`T-045` complete — Approved with follow-ups**, 2026-07-26 after four rounds, with no
  production change at any point. `T-046` owns the filesystem-aware uniqueness guarantee.
- **`T-044` complete — Approved with follow-ups by maintainer direction**, 2026-07-26 after six
  rounds and three scope decisions. The gate now states only its tested runtime promise; three
  known blind spots are pinned and owned by `T-047`. No production code changed in any round.
- **The lesson from T-044 and T-045:** all six defects came from treating an enumerated set as
  exhaustive. The successful corrections were not longer enumerations: T-044 reads the
  interpreter's namespace and states its gaps, while T-045 dropped the completeness claim.
  `ai/TESTING.md` §13 records the general rule.

## In progress

- **`T-016` — merged to `main` at `33ebd11`, awaiting review.** The add-URL dialog, plus
  `ARC-004`'s `READY` entry point in `DownloadManager.start()`. CI green on all five jobs. Its
  branch existed only to stay clear of a review running on trunk and is gone. See `Next` item 4.
- **`T-019` and `T-038` are both Approved**, 2026-07-27 — `T-019` at `eaa5b50`, `T-038` at
  `098ba3f` after three focused corrections of High `T038-R2`. That finding was the one that
  "directly regresses High `T013-R2`": the per-job log handler closed when the *result* pump
  finished, without establishing that the *log* listener had drained, and listener shutdown
  blocked the GUI thread for a measured 2.001 s. Both halves are fixed — a same-job reopen returns
  the identical still-attached handler, and `idle` is withheld while the listener thread is alive,
  polled by the existing timer and never joined, with `gave_up_on_the_log` as the bounded escape
  if it wedges past `reap_seconds`. `T013-R2/R3/R4` were re-examined and remain resolved.
  **`ai/TESTING.md` §7 now covers nine of ten mandatory areas**; only DRM is uncovered, and it
  still has no Phase 1 owner.
- **`T-013` closed after three correction passes.** `T013-R1`, `T013-R2` and `T013-R4` were
  verified resolved; `T013-R3` came back twice more with a different sibling each time, so the
  maintainer authorized **restructuring** the startup transaction rather than patching it again:
  the session now records each start as it happens, and the unwind reads that record instead of
  inferring it. `T013-R5` remains non-blocking hardening owned by `T-052`.
- **`T-013` approved with follow-ups and `T-015` approved**, 2026-07-27. `T-018` reached its
  **fifth** correction of the same Critical (`T018-R1`). Three recogniser passes each closed the
  reported spellings and left another the rule had not been written to see; the fourth made an
  allowlist the control (`SEC-002`), and the reviewer verified that it works. The fifth removed
  what stood beside it: the schema fingerprint copied captured mapping **keys** verbatim, so a
  secret used as a key was written to disk while all three gates called the file clean. `SEC-002`
  is amended — the fingerprint is gone, `write()` derives everything it writes, and a playlist
  entry is a count rather than a record. **`T-018` is closed as Approved on that fifth pass.**
- **The lesson, a fourth time in one task:** every one of the five rounds ended the same way —
  something was being kept without a reader for it, and the argument for keeping it was always
  "it's only shape / only names / only the parts we recognise". The allowlist survived review
  because it starts from what is *read*. Anything else in a fixture is a liability with a story.
- **`ai/TESTING.md` §7 covers nine of ten mandatory areas, all in the default local run.**
  `T-013` added Cancellation and Worker crash against real spawned processes; both moved behind
  `-m process_tree` in `9010794`, because `T-019`'s live defect left descendants that wedged later
  runs. **`T019-R1` caught that the same marker removed them from CI**, which ran a bare `pytest`
  and inherited the exclusion — so for one day two mandatory areas gated nothing anywhere, while
  three records said CI still covered them. `T-019` removed the marker along with the defect.
  Log redaction closed with `T-038`'s approval. **DRM is the one uncovered area and still has no
  Phase 1 owner** — worth settling deliberately rather than discovering it at the exit review.
- **The lesson from `T-044`, `T-045` and `T-014`, now three for three:** each blocking finding
  came from filtering unbounded input instead of constraining what the input could be. `T-044`
  stopped parsing for exports and read the interpreter's namespace; `T-045` dropped a completeness
  claim it could not keep; `T-014` made a proxy credential *unrepresentable* in the model rather
  than strippable in persistence. **`T-038` is this problem again** and should start from that,
  not from a recogniser.

## Next

`ARC-002`'s ordinary end-to-end path is proven: a spawned child imports yt-dlp, extracts and
reports typed messages back (`T-012`); a job survives a restart and an unclean kill (`T-014`);
and, in a test, a URL becomes a file on disk through `T-013`. T-013 is now approved, so that path
is something to build on, and cancellation now reaps the worker's descendants too (`T-019`).
**No widget touches any of it yet**: composition is `T-036` and the first *user-visible* download
is `T-037`.

1. **`T-018` is approved and closed** (2026-07-27, `T018-R1` and `T019-R1` both Resolved). The
   fifth correction removed the schema fingerprint that could carry captured mapping keys;
   `SEC-002` records the amendment and what it gives up.
2. **`T-019`, `T-038` and `T-051` are all approved and on `main`.** `T-019` fixed the live defect
   — cancelling now reaps the worker's whole process group, and the `process_tree` marker is gone
   with the reason for it. `T-038` puts redaction in a formatter, so no call site can leak by
   forgetting, and its High `T038-R2` took three focused corrections. `T-051` is a decision,
   `ARC-004`. The `phase1-orphans-logging-lifecycle` branch that carried them is merged.
3. **Windows has runtime evidence, and it found a real bug.** `30293051118` first ran the
   process-tree suite on both platforms; `30302798113` then ran `T-019`'s new descendant tests
   there and **failed**, because `ctypes` had truncated the Job object's handle — invisible on
   Linux by construction. `30303348265` is green on every job, with all four grandchild tests
   and the containment check passing on `windows-latest` (1163 passed, 20 skipped). Phase 1's
   "verified on Linux *and* Windows" criterion has moved for the first time since it was written,
   and the move was worth more than the confirmation: pushing bought a defect nothing local
   could have found (`T019-R2`).
4. **`T-016` is merged to `main` at `33ebd11` and in review.** It is the first code that makes
   any of the engine visible to a person: paste URLs, probe one in a worker process, see title,
   uploader, duration, a decoded thumbnail and whether it is a playlist, pick a preset, queue them
   all. It also implements `ARC-004` — `DownloadManager.start()` now takes a `READY` job as well
   as a `QUEUED` one — which amends code `T-013` was approved with, and replaces the `T-013` test
   that asserted the older rule.

   Twelve deliberate weakenings were run against the new tests and all twelve were killed, but
   **three gates reported clean while covering nothing**, and that is the part worth keeping. The
   tab-order test derived its expected order from the same list the dialog hands to Qt, so it
   proved only that the list equalled itself and the mutation survived. The local type gate was
   the wrong *scope* — `mypy src` reads 33 files, the `windows desktop` job reads 69 including
   `tests/` — and CI found two real errors, one of which had silently stopped mypy analysing the
   rest of a test. The Windows UI Automation menu contract then caught a File-menu item this task
   added without declaring it. Each was corrected, and `ai/TESTING.md` §12 now states the scope
   difference that nothing had written down.

5. **`T-017` is the only substantive task startable now**, and the critical path to the phase
   exit is linear: **`T-017` → `T-036` → `T-037`**. `T-036` depends on `T-016` *and* `T-017`, so
   composition does not begin the moment `T-016` clears review. **DRM is the one uncovered
   mandatory area and still has no owner** — worth settling before `T-037` rather than at the
   exit review.
6. **`T-050`** — **Phase 2**, not Phase 1: the `history` table is still empty, and
   `IMPLEMENTATION_PLAN.md` puts `REQ-020`'s history persistence in Phase 2. This file's claim
   that `T-013` owned it was `STATUS.md` running ahead of both the plan and `T-013`'s own scope;
   the task entry records the two things still missing before it can be written honestly.

**What two review rounds cost, and what they bought.** Eight blocking findings across two
passes, every one real. The pattern worth remembering: **five of them were things that
computed the right answer and then failed to act on it** — the resolved yt-dlp version never
left the worker, the rendered path was validated and then re-rendered, ffmpeg was located and
never passed to the library, an audio codec was chosen and never requested, and the frozen
probe resolved an extractor name without loading the extractor. Each looked correct in the
code and produced no error.

The tests that missed them shared a shape too: they asserted on the *input* to a boundary
rather than on what came out the far side — a key present in an options dict, a local variable
on the worker's side of the queue. `ai/TESTING.md` §13 now has the general form of this.

## Known gaps not yet scheduled

- **`T-035` was missing from the plan.** `downloader/environment.py` was claimed by no task
  and `REQ-024` (ffmpeg detection) by nothing at all, though `ARCHITECTURE.md` §6 puts yt-dlp
  resolution at worker start and `T-012` therefore needs it immediately.
- **`T-034` was missing from the plan.** Filename safety and output-path containment
  (`core/paths.py`) belonged to no task, despite `ARCHITECTURE.md` §8 requiring every output
  path to pass through it and `ai/TESTING.md` §7 listing path safety as mandatory. Found while
  planning Phase 1; now filed and blocking `T-012`.

- **`T-033` — implemented, not closed** (`P1-R2`). The spec collects yt-dlp's submodules and
  data files; the probe resolves an extractor *by name* through the lazy machinery and asserts
  the bundled version against the pin (`T033-R1`). It stays **In Review** until the frozen jobs
  run on both platforms: the local probe is source-mode and proves nothing about the artifact,
  which is the entire subject of the task. An earlier version of this file called it "closed"
  here while listing it as pending above — the contradiction `P1-R2` reported.

## Open questions for the maintainer

- *(`ARC-003` was accepted on 2026-07-26, closing `T011-R5`. It narrows `ARC-002`'s "versioned
  internal contract" to version-controlled, and names its own expiry: any packaging in which
  parent and child become separately deployable re-opens the question.)*

- **Confirm the Phase 1 prerequisite amendment.** `IMPLEMENTATION_PLAN.md` said "Phase 0
  complete" while `TASKS.md` treated `T-010` as startable — and the plan outranks `TASKS.md`
  (`AGENTS.md` §5), so `T-010` was formally blocked. The prerequisite now reads "Phase 0's
  **deliverables** complete, merged and reviewed", separating those from the exit criteria,
  one of which needs a Windows machine. The Windows criterion is **not** waived; it still
  blocks Phase 0's formal exit and first release.

*(`OPS-004` was accepted on 2026-07-26 and is no longer open. Its installer half became
`T-039`, blocked until Phase 5 produces an installer.)*

## Blockers

- **`T-033` — blocked on CI evidence, not on code.** Its corrections are reviewed and verified,
  but approval needs the collection-removal negative run, Linux **and** Windows frozen results,
  and the recorded artifact-size delta. PyInstaller is in the `build` extra and absent from the
  working venv, so none of it can be produced here. Clears when the frozen jobs run against the
  pushed boundary.

*(the `T-003` logo blocker cleared on 2026-07-25 when the maintainer supplied the source
asset)*

## Repository

`github.com/kottmans/tracks-and-trails` — **private** for now, intended to go public later.

Commits are authored as `40611149+kottmans@users.noreply.github.com`, set in **repo-local**
git config so the maintainer's personal address never enters a history that will eventually be
public. This is per-repository, not global: a fresh clone, or a new repo, needs it set again.

To do when it goes public: state that contributions are accepted under MIT (`LIC-001`), and
re-check that no personal paths or local configuration reached the history.

## Environment baseline

Development machine, verified 2026-07-25:

| Item | State |
|---|---|
| Python | 3.14.6 (`/usr/bin/python3`) — the only interpreter; **confirmed sufficient** (`T-002`) |
| `pip` | 26.0.1, installed via `ensurepip --user` into `~/.local` (no sudo, no PEP 668 marker on F44) |
| Project venv | `.venv/` — recreated 2026-07-26 (this checkout had none, again: it is git-ignored and does not survive a fresh clone); editable install, PySide6 6.11.1, platformdirs 4.11.0. `comtypes` is a Windows-only dev dependency and is absent here by design |
| Dev tools | ruff 0.16.0, mypy 2.3.0, pytest 9.1.1, pytest-qt 4.5.0, PyInstaller 6.21.0, psutil — no longer packaging-only, the default suite needs it since `T-013` asserts on real processes |
| ffmpeg | present |
| git | branch `main` tracking `origin/main`; CI green on every push and PR (`T-006`) |
| Repository path | **Unsettled, and this row has now been wrong in both directions.** On 2026-07-27 the `T-013` session ran entirely in `/mnt/projects/software_projects/tracks-and-trails`, where `ls`, `readlink -f` (not a symlink) and every check and test agree, while `/mnt/storage` does not exist at all. The previous entry asserted the reverse. Rather than flip the value a third time: the working checkout is wherever the maintainer's shell says it is, and **this row should record a machine, not a truth** — one of the two paths is presumably a mount that is not always present. Needs a maintainer answer, not another edit |
| Windows environment | **CI runners only** — no local Windows machine or VM. The runner is a real desktop, not a bare headless box (`OPS-004`), and the dedicated `windows desktop` job uses it: the other jobs pin `QT_QPA_PLATFORM=offscreen`, that one does not |

## Current risks

| Risk | Impact | Standing |
|---|---|---|
| ~~PySide6 may lack Python 3.14 wheels~~ | — | **Closed** by `T-002`: PySide6 ships `abi3` wheels serving all Python ≥3.10 |
| No Windows machine — CI only | Interactive Windows behavior (screen reader, dialogs, keyboard, theming, installer) is **known-unverified**, not merely untested | Narrowed by `OPS-004`: the runner has a real desktop, so the objective half is automatable and `T-026` owns it. Only the subjective residue needs a person, and that still blocks first public release |
| `ARC-002` process model is unproven | It is the project's central architectural bet | **Mechanics validated on Linux** by a `T-002` probe (spawn under a live `QApplication`, structured progress over `mp.Queue`, instant terminate with no orphan). Phase 1 still proves it under a real download. |
| `ARC-002` may break once frozen — `spawn` from a frozen binary relaunches the app | Recursive launch; invisible until Phase 5 without a guard | `freeze_support()` + `T-020` frozen smoke test in Phase 0 CI |
| yt-dlp upstream churn | Ongoing maintenance cost | Confined to two modules (`NFR-008`); pinned fixtures |

## Notes

**Something downloads now — in a test.** What `T-013` connected is the *engine*: given a job in
the repository, a real spawned worker downloads a real URL to a real file and every transition is
persisted. `T-016` adds the first widget that calls it — the add-URL dialog probes, displays and
queues through `DownloadManager`, and its tests drive that path end to end.

**A user still cannot reach any of it.** `app.py` builds `MainWindow` with no manager, no job
store and no output directory, so File → Add URLs… is **disabled**, saying so in its status tip.
Supplying those three is composition (`T-036`); the first URL a *user* can download is `T-037`.
Treat `ARCHITECTURE.md` as the approved target rather than a description of what a user can do.

Precisely, recounted 2026-07-27 by parsing each module for anything beyond its docstring: of the
**33** modules under `src/`, **12 are still docstring-only stubs** and **21 have code**. Those
twenty-one are `__init__.py`, `__main__.py`, `_freeze_probe.py`, `app.py`, `ui/main_window.py`,
`core/{models,job_state,errors,paths}.py`,
`downloader/{environment,protocol,worker,ytdlp_adapter}.py`, `persistence/{db,repositories}.py`,
`downloader/{manager,result_pump}.py` (`T-013`), `core/presets.py` (`T-015`),
`core/logging.py` (`T-038`), `downloader/process_tree.py` (`T-019`), and — new with `T-016` —
`ui/add_dialog.py`, **the first widget beyond the shell window**.

*(Before `T-014` this said 23 stubs and eight coded, recomputed at `697e024`; it had gone stale
across four tasks. The previous count of 31/13/18 was itself two modules stale, missing
`core/logging.py` and `downloader/process_tree.py`, which landed with `T-038` and `T-019`. Each
count is recounted rather than adjusted, which is how that was caught.)*

The `core/` modules remain **domain vocabulary plus pure functions** — what a job, a request and
a failure *are*, the rules for moving between states, and filename safety. `persistence/` is the
first module that keeps something across a restart.

Of `TESTING.md` §7's ten mandatory areas, **nine** are now covered: Layering (`T-005`), the
State machine (`T-010`), Path safety (`T-034`), Crash recovery, Migrations and the Settings
freeze (`T-014`), Cancellation and Worker crash (`T-013`, with the process-tree half proved by
`T-019`), and Log redaction (`T-038`). **DRM is the one outstanding, and has no Phase 1 owner.**

*(This paragraph read "eight … the two outstanding are Log redaction and DRM" until 2026-07-27,
contradicting the count in `In progress` above after `T-038` was approved. Two statements of one
number in one file is the defect; this is now the only one.)*
