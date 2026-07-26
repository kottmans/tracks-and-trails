# STATUS.md — Tracks & Trails

**Purpose:** Concise snapshot of where the project stands right now.
**Authority:** Canonical for current project state.
**Owner:** Planner / Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-26
**Last verified against repository:** 2026-07-26
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
- **`T011-R8` is closed.** `T-041` was approved at `c693ec6` and the finding is functionally
  resolved. The audit behind it found the hole was not one field but every field of every model
  in `core/models.py`.

## Completed

- Documentation system bootstrapped: `DOC-001` (convention rev 2026-07-18.1, Standard profile)
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
  request, squash-merged as `e36525e` and green on `main`. Reviewed twice; the final
  documentation correction was maintainer-accepted with the focused re-review waived.
- **`T-005` + `T-024` complete** — layering enforcement test, squash-merged as `88b810f`.
  The analyser is guarded against being weakened, verified by eight distinct weakenings. Two
  review rounds; the second re-review was waived by the maintainer.
- **`T-007` complete** — the application shell window, merged as `ef12f02`. Opens with the
  icon and title, File → Quit and Help → About, geometry across restarts, clean exit. Cold
  start 0.178 s median against `NFR-002`'s 3 s. **Merged without any independent review** at
  the maintainer's direction — not a waived re-review, no first pass; recorded in its task.
- **`T-020` + `T-025` complete** — frozen-build smoke test and the Phase 0 exit preparation,
  merged as `4d6ad3c`. A frozen artifact spawns a child without relaunching itself on both
  platforms; the clean-checkout verification passes on Linux. The **negative** proof — that
  removing `freeze_support()` breaks it — has now been run on Windows too (`T-029`, run
  `30186080950`).
- **Phase 0 exit review complete, and its eight findings closed** — `T-027` … `T-032`,
  squash-merged as `6f2fec9`. `P0-R2` … `P0-R5` were reviewer-verified; the corrections to
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

## In progress

- **`T-034`** — filename safety and output-path containment. Closes `TESTING.md` §7's **Path
  safety** mandatory area.
- **`T-035`** — yt-dlp and ffmpeg environment resolution. **`T-012`'s last prerequisite**: with
  `T-011`, `T-034` and `T-035` all implemented, the Phase 1 chokepoint is unblocked once the
  review clears.
- **`T-042`** and **`T-043`** — test-strength fixes for guards that were correct but
  unprotected, so a regression would have been silent.

All three await review.

## Next

Six tasks are Ready. Recommended order:

1. **`T-041`** — nested payload validation in `core/models.py`. Small, **High** severity, and it
   restores a guarantee `downloader/protocol.py` already advertises. Carried from `T011-R8`.
2. **`T-034`** — filename safety and output-path containment. A `TESTING.md` §7 mandatory area
   still uncovered, with a security failure mode: a title-derived filename escaping the output
   directory, driven by attacker-influenced data.
3. **`T-035`** — yt-dlp and ffmpeg environment resolution. Newly unblocked, and the third of
   `T-012`'s three prerequisites alongside `T-034`.
4. **`T-038`**, **`T-014`**, **`T-015`** — Ready, off the critical path.

`T-012` needs `T-011` (done), `T-034` and `T-035`; six tasks depend on it.

Phase 0's formal exit is **recorded**, and the Phase 1 prerequisite amendment is **withdrawn as
moot** — exactly as the amendment itself predicted once the Windows criterion was met.

## Known gaps not yet scheduled

- **`T-035` was missing from the plan.** `downloader/environment.py` was claimed by no task
  and `REQ-024` (ffmpeg detection) by nothing at all, though `ARCHITECTURE.md` §6 puts yt-dlp
  resolution at worker start and `T-012` therefore needs it immediately.
- **`T-034` was missing from the plan.** Filename safety and output-path containment
  (`core/paths.py`) belonged to no task, despite `ARCHITECTURE.md` §8 requiring every output
  path to pass through it and `ai/TESTING.md` §7 listing path safety as mandatory. Found while
  planning Phase 1; now filed and blocking `T-012`.

- **`T-033` — the frozen artifact contains no yt-dlp.** Verified against the built artifact:
  zero `yt_dlp` files. Correct today (nothing imports it yet) but it will not self-correct
  when `T-012` lands, because 972 of yt-dlp's 1046 modules are extractors resolved
  dynamically and PyInstaller follows static imports. The artifact would build, launch, and
  fail every URL in a way that looks like ordinary site breakage.

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

*(none — the `T-003` logo blocker cleared on 2026-07-25 when the maintainer supplied the
source asset)*

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
| Project venv | `.venv/` — recreated 2026-07-26 (this checkout had none); editable install, PySide6 6.11.1, platformdirs 4.11.0. `comtypes` is a Windows-only dev dependency and is absent here by design |
| Dev tools | ruff 0.16.0, mypy 2.3.0, pytest 9.1.1, pytest-qt 4.5.0, PyInstaller 6.21.0 |
| ffmpeg | present |
| git | branch `main` tracking `origin/main`; CI green on every push and PR (`T-006`) |
| Repository path | `/mnt/projects/software_projects/tracks-and-trails` (corrected 2026-07-26; the recorded `/mnt/storage/...` path does not exist) |
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

**Almost no application behavior exists yet.** Nothing downloads, probes, or persists a
job. There is now a window (`T-007`, merged) — titled, icon-bearing, with File → Quit and
Help → About — and it remembers its size and position. That is the whole of it. `ARCHITECTURE.md` describes the approved target, not
reality — treat any claim of implemented *behavior* as false until this section says
otherwise.

Precisely, recomputed at `4172fd0`: of the **31** modules under `src/`, **23 are
docstring-only stubs**. The eight with code are `__init__.py` (the version string),
`__main__.py` (`freeze_support()` and `main()`), `_freeze_probe.py` (`T-020`'s frozen-build
diagnostics), `app.py` (argument handling and `QApplication` setup), `ui/main_window.py`
(the shell window), and — new with `T-010` — `core/models.py`, `core/job_state.py` and
`core/errors.py`.

The three `core/` modules are **domain vocabulary, not behavior**. They define what a job,
a request and a failure *are*, and the rules for moving between states. Nothing calls them yet:
no job is created, persisted, or run. The statement above still holds — nothing downloads.

What *has* been built is the scaffolding that guards that behavior when it arrives, and those
parts of `TESTING.md` are real: CI on both platforms (`T-006`), the shipped-asset invariants
(`T-022`), the layering enforcement test (`T-005`), and the Windows desktop and accessibility
gates (`T-026`). Of `TESTING.md` §7's ten mandatory areas, **two** are now covered — Layering,
and the State machine (`T-010`, asserted over every ordered pair of statuses).
