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
  person, and blocks **first release**, not this phase. `T-040` (tab order) and `T-039`
  (installer) have no automated gate yet either.
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

- **`T-013` — reviewed 2026-07-27: changes requested.** The download manager and result pump are
  implemented and merged to `main` at `0a19daf`; a job goes from `QUEUED` to a file on disk
  through a real spawned worker, and a cancelled or crashed one ends in a state the queue can
  explain. Three blocking findings (`T013-R1`, `T013-R2` High; `T013-R3` Medium) are open and
  the correction batch has not started. Four of the five judgement calls the implementer flagged
  were accepted; the fifth produced `T-051`.
- **`T-015` and `T-018` — implemented 2026-07-27, In Review**, on branch
  `phase1-presets-and-fixtures` (`AGENTS.md` §7: branched on maintainer instruction, to keep new
  work off `main` while `T-013`'s corrections land there). Presets and their translation; the
  recorded-fixture set, a playlist projection, and a committed capture tool. **Both came back
  Changes requested on 2026-07-27**, with one Critical (`T018-R1`: the fixture credential gate
  is a false negative for tuple-nested cookies and signed-URL parameters) and two High. **`T-016`
  is not unblocked**: `T018-R2` found the projection misses yt-dlp's `multi_video`, so `T012-R6`
  is still open. An earlier version of this line claimed the opposite.
- **`ai/TESTING.md` §7 stands at eight of ten mandatory areas**, up from six. `T-013` added
  Cancellation and Worker crash, both against real spawned processes. The two outstanding are
  Log redaction (`T-038`) and DRM. **DRM has no Phase 1 owner** — worth settling deliberately
  rather than discovering it at the exit review.
- **The lesson from `T-044`, `T-045` and `T-014`, now three for three:** each blocking finding
  came from filtering unbounded input instead of constraining what the input could be. `T-044`
  stopped parsing for exports and read the interpreter's namespace; `T-045` dropped a completeness
  claim it could not keep; `T-014` made a proxy credential *unrepresentable* in the model rather
  than strippable in persistence. **`T-038` is this problem again** and should start from that,
  not from a recogniser.

## Next

`ARC-002` is proven end to end. A spawned child imports yt-dlp, extracts and reports typed
messages back (`T-012`); a job survives a restart and an unclean kill (`T-014`); and `T-013` now
connects them — in a test, a URL becomes a file on disk, and cancelling it leaves neither an
orphan process nor a job that lies about its state. **No widget touches any of it yet**:
composition is `T-036` and the first *user-visible* download is `T-037`.

1. **Correct `T-013`'s three blockers**, on `main`. Two of them are one theme: the receiver acts
   on a message before deciding whether the message was legal. Nothing downstream should be
   built against a manager in that state.
2. **`T-038` — logging with handler-level redaction.** Ready, High priority, and now overdue
   rather than early: `T-013` generates the diagnostics most likely to carry a tokenised URL or a
   cookie path, and they are being produced today with no redacting handler under them.
   Retrofitting redaction around live diagnostics is how `T-014` lost four review rounds.
3. **Review `T-015` and `T-018`** on `phase1-presets-and-fixtures`. Both are independent of
   `T-013`'s corrections and touch no file it does — except `ytdlp_adapter.py`'s projection and
   `core/models.py`, neither of which the findings name.
4. **`T-050`** — new, and **Phase 2**, not Phase 1: the `history` table is still empty, and
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

**Something downloads now — in a test.** A window opens (`T-007`) and knows nothing about any
of this. What `T-013` connected is the *engine*: given a job in the repository, a real spawned
worker downloads a real URL to a real file and every transition is persisted. **No widget calls
it** — composition is `T-036`, and the first URL a *user* can download is `T-037`. Treat
`ARCHITECTURE.md` as the approved target rather than a description of what a user can do.

Precisely, recounted 2026-07-27 by parsing each module for anything beyond its docstring: of the
**31** modules under `src/`, **13 are still docstring-only stubs** and **18 have code**. Those
eighteen are `__init__.py`, `__main__.py`, `_freeze_probe.py`, `app.py`, `ui/main_window.py`,
`core/{models,job_state,errors,paths}.py`,
`downloader/{environment,protocol,worker,ytdlp_adapter}.py`, `persistence/{db,repositories}.py`,
`downloader/{manager,result_pump}.py` (`T-013`), and — new with `T-015` — `core/presets.py`.

*(Before `T-014` this said 23 stubs and eight coded, recomputed at `697e024`; it had gone stale
across four tasks. Each count since has been recounted rather than adjusted.)*

The `core/` modules remain **domain vocabulary plus pure functions** — what a job, a request and
a failure *are*, the rules for moving between states, and filename safety. `persistence/` is the
first module that keeps something across a restart.

Of `TESTING.md` §7's ten mandatory areas, **eight** are now covered: Layering (`T-005`), the
State machine (`T-010`), Path safety (`T-034`), Crash recovery, Migrations and the Settings
freeze (`T-014`), and — new with `T-013` — Cancellation and Worker crash. The two outstanding
are Log redaction (`T-038`) and DRM.
