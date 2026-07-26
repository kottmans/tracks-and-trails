# STATUS.md — Tracks & Trails

**Purpose:** Concise snapshot of where the project stands right now.
**Authority:** Canonical for current project state.
**Owner:** Planner / Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
**Last verified against repository:** 2026-07-25
**Update when:** A meaningful work session ends, a phase changes, a blocker appears or clears, or the next task changes.
**Does not contain:** Task detail (`TASKS.md`), review history (`REVIEWS.md`), decision rationale (`DECISIONS.md`).

---

**Current phase:** Phase 0 — Foundation, **exit blocked**
**Overall state:** Every deliverable is built and green on both platforms, but the exit review
requested changes (`T-027` … `T-032`), and the documented Windows launch criterion remains
unmet and unmeetable here (`OPS-003`).

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
  platforms; the clean-checkout verification passes on Linux. The **negative** proof, that
  removing `freeze_support()` breaks it, was run on Linux only — `T-029` carries the Windows
  half.
- **Phase 0 exit review complete — changes requested.** Seven findings, three Medium; tracked
  as `T-027` … `T-032`. `T005-R1` and `T005-R3` are now formally Resolved.
- **Windows is no longer entirely unverified.** `T-006`'s runners confirmed, with downloadable
  artifact evidence: Python 3.14.6 (MSC v.1944, AMD64), PySide6/shiboken6/Qt 6.11.1, a
  `QWidget` visible offscreen, and the full 27-test suite passing. This discharges the Windows
  carries from `T-002` and `T-003`. The `OPS-003` interactive gaps (screen reader, native
  dialogs, keyboard, theming, installer) remain untouched and still block first release.
- Verified 2026-07-25 that yt-dlp 2026.06.09 is pure Python (1046 `.py`, no compiled
  extensions), which is what makes the `OPS-002` pip-free updater viable

## In progress

*(nothing active — all branches merged and deleted; `main` is the only branch)*

## Next

Phase 0's build work is merged. The exit review happened and **requested changes**, so the
phase has not exited.

1. **`T-027` … `T-032`** — the exit-review follow-ups. `T-027` (unsafe stored geometry),
   `T-029` (the frozen negative proof was never run on Windows) and `T-031` (correct `OPS-004`
   before deciding it) are High.
2. **Re-review**, then a second Phase 0 exit verdict.
3. **The Windows launch criterion** stays unmet regardless — it needs a real Windows session
   (`OPS-003`), and `OPS-004`/`T-026` decide how much of the surrounding gap CI can close.
4. **Phase 1** — `T-010` … `T-019` are outlines needing full scope, acceptance criteria and
   review bases before any moves to Ready. Planner work, and not started.

## Open questions for the maintainer

- **`OPS-004` needs accepting or rejecting.** A spike showed `OPS-003`'s "not automatable on
  Windows" list was written on a false assumption: the CI runner has a real desktop
  (`platformName == 'windows'`, a native `HWND`, working screenshots). `OPS-003`'s core
  decision stands; its classification does not. `T-026` implements the correction and is
  blocked until this is decided.

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
| Project venv | `.venv/` — editable install; PySide6 6.11.1, yt-dlp 2026.7.4, platformdirs 4.11.0 |
| Dev tools | ruff 0.16.0, mypy 2.3.0, pytest 9.1.1, pytest-qt 4.5.0, PyInstaller 6.21.0 |
| ffmpeg | present |
| git | branch `main` tracking `origin/main`; CI green on every push and PR (`T-006`) |
| Repository path | `/mnt/storage/software_projects/tracks-and-trails` |
| Windows environment | **CI runners only** — no Windows machine or VM is available (`OPS-003`) |

## Current risks

| Risk | Impact | Standing |
|---|---|---|
| ~~PySide6 may lack Python 3.14 wheels~~ | — | **Closed** by `T-002`: PySide6 ships `abi3` wheels serving all Python ≥3.10 |
| No Windows machine — CI only | Interactive Windows behavior (screen reader, dialogs, keyboard, theming, installer) is **known-unverified**, not merely untested | `OPS-003`: push everything automatable into `T-006`/`T-020`; one real Windows session blocks first public release |
| `ARC-002` process model is unproven | It is the project's central architectural bet | **Mechanics validated on Linux** by a `T-002` probe (spawn under a live `QApplication`, structured progress over `mp.Queue`, instant terminate with no orphan). Phase 1 still proves it under a real download. |
| `ARC-002` may break once frozen — `spawn` from a frozen binary relaunches the app | Recursive launch; invisible until Phase 5 without a guard | `freeze_support()` + `T-020` frozen smoke test in Phase 0 CI |
| yt-dlp upstream churn | Ongoing maintenance cost | Confined to two modules (`NFR-008`); pinned fixtures |

## Notes

**Almost no application behavior exists yet.** Nothing downloads, probes, or persists a
job. There is now a window (`T-007`, in review) — titled, icon-bearing, with File → Quit and
Help → About — and it remembers its size and position. That is the whole of it. `ARCHITECTURE.md` describes the approved target, not
reality — treat any claim of implemented *behavior* as false until this section says
otherwise.

Precisely, recomputed at `2d06153`: of the **31** modules under `src/`, **26 are
docstring-only stubs**. The five with code are `__init__.py` (the version string),
`__main__.py` (`freeze_support()` and `main()`), `_freeze_probe.py` (`T-020`'s frozen-build
diagnostics), `app.py` (argument handling and `QApplication` setup), and `ui/main_window.py`
(the shell window). `app.run` is no longer a placeholder — it builds and runs the real
application.

What *has* been built is the scaffolding that guards that behavior when it arrives, and those
parts of `TESTING.md` are real: CI on both platforms (`T-006`), the shipped-asset invariants
(`T-022`), and the layering enforcement test (`T-005`, in review). Of `TESTING.md` §7's ten
mandatory areas, exactly one — Layering — is covered.
