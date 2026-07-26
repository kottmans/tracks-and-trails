# TASKS.md — Tracks & Trails

**Purpose:** Track concrete, actionable work.
**Authority:** Canonical for current actionable work and its state.
**Owner:** Planner (creates/prioritizes) · Implementer and Reviewer (update status)
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
**Update when:** A task starts, blocks, changes scope, completes, or is cancelled.
**Does not contain:** Phase planning (`IMPLEMENTATION_PLAN.md`), progress narrative (`STATUS.md`).

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
IDs are never reused. Completed tasks move to `ai/archive/` once they bury the live queue.

**Start here:** `T-023` to close the `T-006` review findings, then `T-005` or `T-007` —
both Ready and independent. `T-001`, `T-002`, `T-003`, `T-004`, `T-022` are complete.
Nothing is blocked.

---

## Ready

### T-007 — Application shell window

**Status:** Ready — `T-003` delivered the icon set, so this is no longer blocked
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 0
**Depends on:** `T-001`, `T-003`
**Relevant context:** `ARCHITECTURE.md` §4, `NFR-002`, `NFR-005`
**Affected surfaces:** `app.py`, `ui/main_window.py`, `resources/`
**Risk:** Low
**Required checks:** default suite; manual launch on both platforms

#### Scope

A `QApplication` and `MainWindow` that opens with the app icon and title, has a menu bar with
File → Quit and Help → About, restores window geometry, and shuts down cleanly with no
warnings on stderr. No download functionality.

#### Acceptance criteria

- Launches and exits cleanly on Linux and Windows with a zero exit code and no Qt warnings
- App icon appears in the title bar, taskbar, and About dialog on both platforms
- Geometry persists across restarts
- Cold start under 3 seconds on the reference machine (`NFR-002`, measured and recorded)
- A `pytest-qt` test constructs and closes the window offscreen

#### Out of scope

- Queue view, settings, theming (Phase 4), any yt-dlp interaction

---

### T-005 — Layering enforcement test

**Status:** Ready
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-001`
**Relevant context:** `ARCHITECTURE.md` §4, `AGENTS.md` §7 (Layering), `ai/TESTING.md` §7
**Affected surfaces:** `tests/unit/test_layering.py`
**Risk:** Low — but its absence lets the central architectural rule erode invisibly

#### Scope

Statically analyze the import graph (via `ast`, not by importing) and assert:
`core/**` and `downloader/worker.py` never import `PySide6`/`shiboken6`;
`ui/**` never imports `yt_dlp`; only `downloader/worker.py` and
`downloader/ytdlp_adapter.py` import `yt_dlp` at all.

#### Acceptance criteria

- The test passes on the current tree
- Adding `import PySide6` to any `core/` module fails it, with a message naming the file and
  the rule
- Adding `import yt_dlp` to a `ui/` module fails it
- Uses static analysis — importing modules to check would defeat the purpose and could
  execute side effects

#### Out of scope

- Enforcing anything beyond the two rules in `ARCHITECTURE.md` §4

---

## Proposed — Phase 0

### T-021 — Simplified small-size icon glyph

**Status:** Proposed
**Owner:** Implementer (needs a design decision from the maintainer first)
**Priority:** Low
**Phase:** Phase 4 (theming) — not a Phase 0 exit condition
**Depends on:** `T-003`
**Relevant context:** `T-003` completion note, `ARCHITECTURE.md` §8
**Affected surfaces:** `src/tracks_and_trails/resources/icons/`
**Risk:** Low — cosmetic only

#### Scope

**This is an enhancement, not a defect fix.** `T-003`'s 16 px asset meets its acceptance
criterion — the note and gold trail stay recognizable (`T003-R2`). What it loses is the
landscape: the trees and mountain collapse into the green mass. That is a property of the
artwork's detail level, not of the scaling method, so no better downscale recovers it.

Draw a reduced glyph for 16 px and 24 px that keeps only the elements that still read at that
size — the note head and stem plus the gold trail sweep — dropping the trees and mountain.
Ship it as a separate size-specific asset so Qt picks it for small requests.

#### Acceptance criteria

- At 16 px and 24 px the glyph is **more legible than the current downscale**, judged
  side by side — not merely legible, which the current asset already is
- The glyph is recognizably the same mark as the full logo, not a different one
- The Windows `.ico` embeds the simplified glyph at 16/24 and the full logo at 32 and above
- The `T-022` resource tests still pass, with their expected frame set updated if it changes

#### Out of scope

- Redesigning the logo itself
- Any change to the brand hex values fixed by `T-003`

**Note:** this is a judgment call about brand appearance, so it needs the maintainer's
agreement on the reduced form before implementation.

---

### T-020 — Frozen-build smoke test in CI

**Status:** Proposed
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-006`, `T-007`
**Relevant context:** `REL-001`, `REQ-029`, `ARC-002`, `ARCHITECTURE.md` §3 and §12, `ai/TESTING.md` §8
**Affected surfaces:** `__main__.py`, PyInstaller spec, CI workflow
**Risk:** **High** — the failure this guards against does not exist until the app is frozen, and
it is a recursive application launch, not a subtle misbehavior

#### Scope

Prove during Phase 0 that the `ARC-002` process model survives freezing, rather than
discovering otherwise at Phase 5 with the whole app built on top of it.

Add `multiprocessing.freeze_support()` as the first statement of `__main__.py`. Add a minimal
PyInstaller build producing a one-dir artifact of the Phase 0 shell window plus a trivial
worker that spawns a child process, exchanges one protocol message, and exits. Run that build
and its launch in CI on Linux and Windows.

This does **not** attempt real packaging — no installer, no ffmpeg bundling, no icons, no
signing. It answers one question: does spawning a child process from a frozen binary work, or
does it relaunch the application?

#### Acceptance criteria

- `multiprocessing.freeze_support()` is the first statement in `__main__.py`, with a comment
  citing `REL-001` so it is not "cleaned up" later
- CI builds a frozen artifact on Linux and Windows
- The frozen artifact launches, spawns a worker, receives one message, and exits zero
- **Exactly one** top-level application process exists during the run — asserted, not
  eyeballed. Removing `freeze_support()` must fail this test on Windows.
- No orphaned process survives exit on either platform
- Build and run complete inside the `T-006` ~10 minute CI budget, or the frozen job runs
  separately and its runtime is recorded

#### Out of scope

- Installers, ffmpeg bundling, icons, signing, size optimization — all Phase 5
- Qt dynamic-linking verification (Phase 5 release gate)
- The `OPS-002` wheel-extraction updater — Phase 4, though it shares this constraint

---

## Proposed — Phase 1 (outline; to be expanded when Phase 0 exits)

These are placeholders so the vertical slice is visible. Each gets full scope, acceptance
criteria, and a review base before it moves to Ready.

| ID | Title | Depends on |
|---|---|---|
| T-010 | `core/models.py` + `core/job_state.py` — domain models and state machine | T-001 |
| T-011 | `downloader/protocol.py` — IPC message contract | T-010 |
| T-012 | `downloader/worker.py` + `ytdlp_adapter.py` — yt-dlp in a spawned worker | T-011 |
| T-013 | `downloader/manager.py` + `result_pump.py` — pool of one, progress to Qt signals | T-012 |
| T-014 | `persistence/` — schema, migration runner, `JobRepository` | T-010 |
| T-015 | Built-in presets and preset → yt-dlp options translation | T-010 |
| T-016 | Add-URL dialog with probe results | T-013, T-015 |
| T-017 | Single-job progress view with cancel | T-013, T-014 |
| T-018 | Recorded `info_dict` fixtures + adapter projection tests | T-012 |
| T-019 | Cancellation and worker-crash integration tests | T-013 |

---

## Blocked

*(none)*

## In Review

*(none)*

## Complete

### T-006 — CI on Linux and Windows

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged as `e36525e` via PR #1; CI green on `main`
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-001`
**Relevant context:** `ai/TESTING.md` §10, `REQUIREMENTS.md` §3, `C-003`, **`OPS-003`**
**Affected surfaces:** CI workflow config
**Risk:** **High** — per `OPS-003` this is the *only* Windows environment that exists. Anything
it does not check is genuinely unverified on Windows, not merely unautomated.

#### Scope

A matrix workflow on Linux and Windows running lint, format check, mypy, and the default
pytest suite on the `T-002` baseline. UI tests run with `QT_QPA_PLATFORM=offscreen`. Network
tests excluded.

This is deliberately **larger than a standard lint-and-test pipeline**. Because there is no
Windows machine (`OPS-003`), CI carries verification load that manual testing would normally
carry, so treat the automatable list in `OPS-003` as this task's real target and extend the
workflow toward it as those features arrive in later phases.

#### Acceptance criteria

- Both platforms run green on push and pull request
- A deliberate lint error and a deliberate test failure each turn CI red (verified once, then reverted)
- UI tests pass headless on both runners
- **Carried from `T-002`:** on the Windows runner, PySide6 installs, `import PySide6` works,
  and a `QApplication` + `QWidget` constructs offscreen on the pinned baseline. `T-002`
  verified this on Linux only; CI is the only place it can be confirmed for Windows
  (`OPS-003`).
- **Carried from `T-003`:** `tests/ui/test_resources.py` passes on the Windows runner — every
  asset non-null through `QIcon`, and `icon.ico` reporting all seven embedded sizes. The test
  exists (added by `T-022`) and passes on Linux; CI is the only place it can be confirmed for
  Windows (`OPS-003`).
- Windows runner artifacts (logs, failure output, screenshots when added) are retained and
  downloadable — with no local Windows machine, CI output is the only debugging evidence
  available for Windows failures
- Total run under ~10 minutes

#### Out of scope

- Release/packaging pipelines (Phase 5), coverage gates, network tests
- The frozen build — that is `T-020`

#### Implementation record — 2026-07-25

**Delivered:** `.github/workflows/ci.yml` and `.github/scripts/qt_baseline.py`; `reports/`
added to `.gitignore`.

The workflow encodes two `OPS-003` consequences rather than leaving them to convention.
`fail-fast: false`, so a Linux failure can never cancel the Windows job — Windows evidence is
the scarce resource. Evidence uploads `if: always()`, so a failed Windows job still yields a
downloadable record of this project's own gates. That artifact is not the whole record:
checkout, `setup-python`, apt, and pip all run before `reports/` exists, and a failure in
those is available only through the Actions job log. `ai/TESTING.md` §10 tabulates which
source covers what. Concurrency cancels superseded runs, since Windows minutes bill at 2×
against a private repository's allowance.

`qt_baseline.py` is deliberately **not** a pytest test. It answers whether the Qt stack works
at all on the runner, which is the question worth asking before trusting a suite that imports
Qt: if it fails, every downstream UI failure is that same failure reported less clearly. It
asserts rather than reports — a wrong platform plugin or an invisible widget exits non-zero.

**Every acceptance criterion, with the run that evidences it.** All runs on `t-006-ci`:

| Criterion | Evidence |
|---|---|
| Both platforms green on push | `30179359072` |
| Both platforms green on pull request | `30179407050` (PR #1) |
| Deliberate lint error turns CI red | `30179263484` — both runners failed at `Lint` |
| Deliberate test failure turns CI red | `30179308976` — both runners failed at `Tests` |
| Both reverted after verification | `30179359072` is the reverted tree, green |
| UI tests pass headless on both | 27 passed on each runner under `QT_QPA_PLATFORM=offscreen` |
| **Carried from `T-002`:** PySide6 + `QApplication` on Windows | Python 3.14.6 (MSC v.1944, AMD64), PySide6 6.11.1, shiboken6 6.11.1, Qt 6.11.1, `QWidget` `visible=True` offscreen |
| **Carried from `T-003`:** `QIcon` reads all seven `.ico` frames on Windows | `test_ico_exposes_every_frame_to_qt` PASSED on `windows-latest` |
| Windows artifacts retained and downloadable | 30-day retention. Corrected after review — see below |
| Total run under ~10 minutes | Linux 37–54 s, Windows 1 m 3 s – 1 m 16 s |

**Both Windows carries are now discharged**, with artifact evidence rather than a green tick.
`T-002` and `T-003` should no longer be read as carrying unverified Windows claims.

**Two defects were caught before CI ever ran**, by executing each step's command locally
first: `QT_VERSION_STR` does not exist in PySide6 (the baseline script would have crashed on
both runners), and the actions were on the deprecated Node 20 runtime — bumped to v7.

**Assumption recorded:** the Linux job installs `libegl1 libgl1 libxkbcommon0 libdbus-1-3
libfontconfig1`. This list was derived from what the offscreen plugin links, not from a
minimality experiment; it may be broader than strictly needed. It is correct, not necessarily
minimal.

#### Review corrections — 2026-07-25

**`T006-R1`, evidence retention.** The artifact retention claim was only ever true for the
steps that happened to be piped. Lint, format, and mypy wrote to the Actions job log and
nothing else, so the artifact from the failed lint run contained `environment.txt` alone —
directly contradicting the claim that these artifacts carry failure output and are the only
Windows debugging material available under `OPS-003`. All four checks now tee into
`reports/`. The Qt baseline and pytest steps additionally gained `2>&1`: both write failure
detail to stderr, which the original pipe silently dropped, so they carried the same defect
in a less visible form.

Re-verified rather than assumed. Run `30180163074` reintroduced the lint error; the
`windows-latest` artifact now contains `lint.txt` with the full `F401` diagnostic, including
the Windows path separator in `tests\unit\test_ci_gate_check.py`, confirming it is the
runner's own output and not a replayed local result. Reverted in `30180215713`, whose passing
artifact carries all seven evidence files.

**`T006-R2`, coordination truth.** The `T-002` and `T-003` completion notes still described
their Windows checks as unverified and carried into `T-006`, while `T-006`'s own record in the
same file said those carries were discharged. `TASKS.md` is current truth (`AGENTS.md` §6), so
both notes now state the discharge and cite the evidence. `T-002`'s "explicitly still
unverified" list was also audited item by item: one item was genuinely resolved by `T-001` and
had never been marked so; the cancellation-timing item remains open and is now labeled as
such rather than sitting in an undifferentiated list.

**Not yet extended toward the rest of `OPS-003`'s automatable list** — orphaned-process
assertions, path-safety checks, artifact-install-and-launch, screenshot capture. Those depend
on behavior that does not exist yet; the task says to extend the workflow as those features
arrive, which is future-phase work rather than a gap in this one.

---

### T-023 — Close T-006 review findings

**Status:** Complete
**Completed:** 2026-07-25 — `T006-R2` closed in the first pass, `T006-R1` across two.
**The focused re-review was waived by the maintainer**, who judged three review rounds
sufficient and authorized the merge. Recorded rather than implied: the acceptance criterion
"`T006-R1` and `T006-R2` receive a focused re-review" was **not** met for the second-pass
documentation correction. That correction is therefore maintainer-accepted, not
reviewer-verified.
**Owner:** Implementer (workflow evidence) + Planner (coordination correction)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-006`
**Relevant context:** `ai/REVIEWS.md` findings `T006-R1`, `T006-R2`; `OPS-003`
**Affected surfaces:** `.github/workflows/ci.yml`, `ai/TESTING.md`, `ai/TASKS.md`, `ai/STATUS.md`
**Risk:** Low — evidence completeness and current-truth accuracy

#### Scope

Ensure a failed lint, format, or type-check command leaves its diagnostic in the uploaded
Windows evidence rather than only in the GitHub Actions job log. Make the documentation
distinguish retained artifacts from Actions-owned logs instead of calling the artifact the
only debugging material. Update the completed `T-002` and `T-003` notes to record that their
Windows carries were discharged by `T-006`.

#### Acceptance criteria

- The controllable project gates write stdout and stderr to `reports/` while preserving their
  non-zero exit status; a locally injected lint failure proves both properties
- `if: always()` still uploads the reports on both runners, and the evidence model states
  honestly which early action/setup failures remain available only through Actions job logs
- The `T-002` and `T-003` completion notes no longer say their Windows checks are unverified
  or still carried to `T-006`; they link to the verified `T-006` evidence
- `T-006` and `STATUS.md` reflect the review outcome and subsequent correction state
- The final Linux and Windows matrix remains green
- `T006-R1` and `T006-R2` receive a focused re-review

#### Out of scope

- Re-running the already-proven lint and pytest gate experiments unless needed to validate
  the evidence-capture correction
- Adding behavior-dependent `OPS-003` checks assigned to later phases

#### Work completed — 2026-07-25

**Pass 1 — mechanism.** All four project gates now tee stdout *and* stderr into `reports/`
while preserving exit status. The Qt baseline and pytest steps also gained `2>&1`; both write
failure detail to stderr, so they carried the same defect in a less visible form than the
three steps the finding named. Proven by run `30180163074` (lint failure, both platforms red,
Windows `lint.txt` carrying the native `tests\unit\...` `F401` diagnostic) and reverted in
`30180215713` (green, all seven evidence files per artifact).

**Pass 1 — `T006-R2`.** The `T-002` and `T-003` notes now record their discharge and cite the
`T-006` evidence. `T-002`'s "explicitly still unverified" list was audited item by item rather
than only the flagged entry; a third item had been resolved by `T-001` and never marked.

**Pass 2 — the documentation half of `T006-R1`, missed in pass 1.** Fixing the mechanism while
leaving the description intact meant the docs still called the artifact the only Windows
debugging material. It is not: checkout, `setup-python`, apt, and pip all run before
`reports/` exists, and a failure in any of them is recorded only in the Actions job log.

Corrected in all four places — `.github/workflows/ci.yml` (header and the tee comment),
`ai/TESTING.md` §10, and the `T-006` implementation record. `ai/TESTING.md` §10 now carries a
table stating which source covers what and with what retention, since that is the policy home
and the other three should point at it rather than restate it. `ai/REVIEWS.md` was left
untouched: it is a historical record (`AGENTS.md` §6), and its finding text quoting the old
wording is evidence of what was found, not a claim to be corrected.

**Standing distinction, recorded so it is not re-flattened:** the Actions job log is the
complete record and the only source covering the setup steps; the `reports/` artifact covers
this project's own gates and is the part that can be analyzed offline. Neither replaces the
other, and only the second is ours to control.

---

### T-022 — Close T-003 review findings

**Status:** Complete
**Completed:** 2026-07-25 — focused re-review approved; `T003-R1`, `T003-R2`, `T003-R3` all
Resolved, no new findings
**Owner:** Planner (documentation correction) + Implementer (resource test)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-003`
**Relevant context:** `ai/REVIEWS.md` findings `T003-R1` through `T003-R3`
**Affected surfaces:** `ai/ARCHITECTURE.md` §8, the `T-003` completion note, resource tests
**Risk:** Low — documentation accuracy and regression coverage for a fixed asset set

#### Scope

Make the palette evidence reproducible or describe the three hex values honestly as adopted
brand swatches rather than uniquely derived measurements. Correct the `T-003` completion note
so its status agrees with the review's judgment that the 16 px criterion is met narrowly, with
`T-021` retained as an optional visual improvement. Add a default-suite resource test for the
delivered PNG and ICO invariants.

#### Acceptance criteria

- The palette table either links to a deterministic algorithm whose radius-40 output matches
  every published hex and share, or drops the measurement-dependent shares and labels the
  hexes as the canonical swatches selected from the source artwork
- The `T-003` completion note no longer says a completed task left its 16 px acceptance
  criterion unmet; it preserves the marginal visual result and the rationale for `T-021`
- A default-suite test fails when a required PNG is missing or has the wrong dimensions, and
  fails when `icon.ico` is null or does not report 16/24/32/48/64/128/256 through `QIcon`
- The test passes on Linux offscreen; `T-006` runs the same assertion on Windows
- `T003-R1`, `T003-R2`, and `T003-R3` receive a focused re-review

#### Out of scope

- Changing the artwork, choosing new brand colors, implementing `T-021`, or consuming the
  icon in the application shell (`T-007`)

#### Work completed — 2026-07-25

**`T003-R1` — palette evidence.** Took the second option: the shares are gone and the hexes
are labeled adopted canonical swatches in `ARCHITECTURE.md` §8. No deterministic algorithm was
supplied because none exists to supply — the artwork has no flat fills, every colored region
is a cloud spanning roughly ±2 per channel, so the modal color is as unstable as the cluster
center (the gold's two most frequent exact values, `#D8A14C` and `#D8A24C`, are within 1.07%
and 0.94% of opaque pixels of each other). §8 now says so explicitly and forbids re-deriving
the values. **The three hex values are unchanged** — only the claim about them. The source
master's SHA-256 is recorded there as the provenance anchor (`T003-R5`).

**`T003-R2` — task truth.** The review's reading is adopted: the criterion is narrowly met.
The `T-003` note now says so, keeps the marginal 16 px assessment verbatim, and states that
`T-021` blocks nothing. `T-021` was itself reworded — it had inherited the overstated premise
that the trail collapses, and its acceptance criterion "distinguishable from a generic green
square" was already satisfied by the current asset, making it unfalsifiable. It now requires a
side-by-side improvement over the existing downscale.

**`T003-R3` — test coverage.** `tests/unit/test_resources.py` (11 assertions, stdlib only —
PNG `IHDR` and `.ico` directory parsing, since the project has no image library and adding one
for a test is not worth it) and `tests/ui/test_resources.py` (12 assertions through `QIcon`,
using pytest-qt's `qapp`). `tests/ui/conftest.py` sets `QT_QPA_PLATFORM=offscreen` by default
so a plain `pytest` reproduces CI.

Negative-tested rather than assumed — each failure mode was injected, confirmed to fail the
suite, and reverted, with the asset directory hashed before and after to prove restoration:

| Injected failure | Caught by |
|---|---|
| `icon-48.png` deleted | `test_no_unexpected_files_in_the_icon_directory` |
| `icon-32.png` resized to 31×31 | `test_derived_png_exists_at_its_declared_size[32]` |
| `icon.ico` truncated to 200 bytes | `test_ico_exposes_every_frame_to_qt` |
| `icon.ico` rebuilt with only 16/32/48 | `test_ico_declares_every_required_frame` + the Qt test |
| stray `icon-99.png` added | `test_no_unexpected_files_in_the_icon_directory` |

Suite: 27 passed, 1 deselected (was 4 passed). `ruff`, `ruff format --check`, `mypy src` green.

---

### T-003 — Add the application icon asset

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Implementer (source asset supplied by Sean Kottman)
**Phase:** Phase 0
**Relevant context:** `T-007`, `ARCHITECTURE.md` §8

**Source asset:** `icon.png`, 1024×1024 RGBA, placed by the maintainer. No vector source
exists, so **no SVG was produced** — that half of the scope is not deferred, it is
unavailable. If a vector original surfaces later, regenerating from it would be an
improvement, not a correction.

**Brand swatches, adopted from the asset.** Recorded canonically in `ARCHITECTURE.md` §8:
`#1E5E47` forest green, `#D9A24C` trail gold, `#083122` deep green.

Originally published here as measurements — hexes plus a share of the logo, said to be
"exact", from clustering opaque pixels at a Euclidean radius of 40. `T003-R1` showed that was
wrong: the artwork has no flat fills, so different reasonable clusterings give different
centers and shares. Corrected by `T-022` to adopted canonical swatches with no share claims.
The values themselves did not change; the claim made about them did.

**Framing decision.** The source artwork occupies only ~9% of its canvas: a 498×743 opaque
box inside 1024×1024, padded 260 left / 192 top / 266 right / 89 bottom — horizontally
centered but sitting low. Scaled as-is, a 16 px icon would carry roughly 8×12 px of actual
artwork. On the maintainer's instruction the derived sizes are **trimmed to the content box
and recentered in a square canvas with a 6% margin**, so the derived assets do not reproduce
the source's framing. `icon.png` is kept unmodified as the master.

**Delivered:** `icon-{16,24,32,48,64,128,256,512}.png` and `icon.ico` (embedding
16/24/32/48/64/128/256), all derived by Lanczos downsampling from an 844×844 master.
The directory's `.gitkeep` was removed, its purpose discharged.

**Checks run:**

| Check | Result |
|---|---|
| `.ico` embedded sizes | `[16, 24, 32, 48, 64, 128, 256]` — exceeds the required 16/32/48/256 |
| `QIcon` load, Linux offscreen | all assets non-null; `icon.ico` reports all 7 sizes to Qt |
| Visual inspection, 16–128 px | see below |
| Resource invariant tests | added by `T-022`; 23 assertions, negative-tested against five failure modes |
| `ruff`, `ruff format`, `mypy`, `pytest` | green |

**All acceptance criteria met.** The 16 px criterion — "renders correctly at 16 px without
becoming unreadable mush" — is met **narrowly**. Judged by eye at 8× nearest-neighbour zoom:

- **128/64/48 px** — fully legible; trees, mountain, trail, and note all distinct
- **32 px** — good; the note and trail read clearly, the trees begin to merge
- **24 px** — acceptable; note and gold trail read, the trees are one blob
- **16 px** — **marginal but legible.** The note and gold trail stay recognizable; only the
  landscape detail collapses. It reads as this mark, not as a green blob

The implementer first recorded 16 px as failing the criterion while still marking the task
Complete, which is a contradictory state (`T003-R2`). Independent review judged the criterion
narrowly met and that reading is adopted here. The marginal result stands as recorded — the
cause is the artwork's detail density, not the scaling — and the simplified small-size glyph
remains worth doing as an **optional enhancement, `T-021`**, which does not block this task,
`T-007`, or Phase 0 exit.

**Windows verified 2026-07-25 — carry discharged.** At completion this criterion, "loads via
Qt resources on both platforms", was confirmed on Linux only and carried into `T-006` as the
only place `OPS-003` allows it to be confirmed. `T-006` has since run it:
`test_ico_exposes_every_frame_to_qt` passed on `windows-latest`, so `QIcon` reads all seven
embedded frames there. This note is no longer an open carry.

---

### T-001 — Establish the project skeleton and toolchain

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Implementer
**Phase:** Phase 0
**Relevant context:** `ARCHITECTURE.md` §4, `ai/TESTING.md` §4, `DOC-002`

**Checks run** (Linux, from a simulated clean checkout containing only git-tracked files):

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 49 files already formatted |
| `mypy` (strict) | Success: no issues found in 37 source files |
| `pytest` | 4 passed, 1 deselected |
| `pytest -m network` | 1 passed, 4 deselected |
| `python -m tracks_and_trails` | exit 0 |
| `tracks-and-trails` (console script) | exit 0 |

**Acceptance criteria — all met.** The clean-checkout criterion was verified by extracting a
copy with no `.venv`, `.git`, caches, or egg-info, then following `docs/DEVELOPMENT.md`
verbatim; all four checks passed there.

**Delivered:** `pyproject.toml` (hatchling, src layout, `requires-python = ">=3.14"`, console
script, ruff/mypy/pytest/coverage config); the 27-module package skeleton matching
`ARCHITECTURE.md` §4, each module carrying a docstring stating its responsibility; the
four-package `tests/` tree; `docs/DEVELOPMENT.md` (`DOC-002` trigger discharged).

**Two deliberate deviations from "no behavior", both reported rather than made silently:**

1. **`__main__.py` contains `multiprocessing.freeze_support()`.** `ARCHITECTURE.md` §3 requires
   it as the first executable statement ahead of any Qt import. Creating the entry point
   without it would have committed a known-wrong file for `T-020` to discover later. `app.py`
   holds a placeholder `run()` returning 0 so the entry point resolves; `T-007` replaces it.
2. **`tests/unit/test_skeleton.py` and `tests/network/test_marker.py` exist.** A tree with no
   tests makes `pytest` exit 5 (no tests collected), so "pytest passes" would have been
   unverifiable. These test T-001's own acceptance criteria — importability, entry-point exit
   code, layer presence, marker exclusion — plus one guard that importing `__main__` pulls in
   no Qt, which is what makes the `freeze_support()` ordering meaningful.

**One mypy ignore exists**, contrary to a literal reading of the "no ignores" criterion:
`ignore_missing_imports` scoped to `yt_dlp.*`. yt-dlp ships no `py.typed` (verified), so this
is required the moment `T-012` imports it — confirmed with a throwaway probe module, since
nothing imports yt-dlp yet. It is confined to the two modules permitted to touch yt-dlp
(`ARCHITECTURE.md` §6), so the untyped surface stays small. Recorded here rather than passed
off as a clean strict run.

**Follow-ups:** `requires-python = ">=3.14"` is now recorded, closing `T-002`'s last open
item. `pyproject.toml` carries the MIT license metadata, closing `T-004`'s carried item.

---

### T-002 — Confirm the Python baseline against PySide6 wheel availability

**Status:** Complete — Linux at completion; Windows discharged by `T-006` on 2026-07-25
**Completed:** 2026-07-25
**Owner:** Implementer
**Phase:** Phase 0
**Relevant context:** `ARC-001`, `REL-001`

**Outcome: Python 3.14 is fully supported. No fallback interpreter is needed.**

Verified on Fedora 44 / x86-64, 2026-07-25, in a clean `.venv`:

| Component | Version | Note |
|---|---|---|
| Python | 3.14.6 | the machine's only interpreter |
| PySide6 | 6.11.1 | wheel is `cp310-abi3` |
| Qt runtime | 6.11.1 | `QApplication` + `QWidget` + `QTableView` construct and show offscreen |
| shiboken6 | 6.11.1 | |
| yt-dlp | 2026.7.4 | imports and extracts cleanly |
| PyInstaller | 6.21.0 | installs and imports on 3.14 — de-risks `T-020` |

**Key finding — PySide6 ships stable-ABI (`abi3`) wheels.** One `cp310-abi3` wheel serves
every Python ≥3.10, so PySide6 does *not* require a per-version wheel and the Python baseline
is not constrained by PySide6 release cadence. This removes the risk that motivated this task
and makes future interpreter upgrades cheap.

**Baseline recommendation for `T-001`: `requires-python = ">=3.14"`.** Not because older
versions would fail, but because `REL-001` freezes an interpreter into every artifact — users
never supply their own — so there is no value in claiming support for a range we do not test.
Pin to the one version actually verified.

**Bonus: `ARC-002` mechanics validated on Linux** with a throwaway probe (not committed):
spawn worked with a live `QApplication` in the parent; the child imported yt-dlp with no Qt
inherited and returned structured info (title, extractor, 33 formats) over an `mp.Queue` in
1.62 s; `terminate()` on a hung worker returned in 0.001 s with exit code -15, no orphan, and
the parent healthy. The central architectural bet behaves as designed.

**Unverified at completion, and their current standing:**

- **Resolved 2026-07-25.** Everything above was **Linux only**, with the Windows half
  transferred to `T-006` as the only Windows environment available (`OPS-003`). `T-006` has
  since run it: on `windows-latest`, Python 3.14.6 (MSC v.1944, AMD64), PySide6 6.11.1,
  shiboken6 6.11.1, Qt 6.11.1, and a `QWidget` visible offscreen. The Windows baseline is
  confirmed and this is no longer a carry.
- **Still open.** The 2-second cancellation criterion (`REQUIREMENTS.md` §11) was probed
  against a *sleeping* worker, not a real in-flight download. Real cancellation is Phase 1
  (`T-019`).
- **Resolved by `T-001`.** No `pyproject.toml` existed yet, so `requires-python` was a
  recommendation; `T-001` recorded `>=3.14`.

---

### T-004 — Decide and record the project license

**Status:** Complete
**Completed:** 2026-07-25
**Owner:** Sean Kottman (maintainer decision)
**Phase:** Phase 0
**Relevant context:** `LIC-001`, `NFR-009`, `C-004`

**Outcome:** MIT. `LIC-001` moved to Accepted with rationale; `LICENSE` written at the
repository root with the 2026 Sean Kottman copyright line; `README.md` updated.

**Remaining:** the `pyproject.toml` license field is set by `T-001`, since no
`pyproject.toml` exists yet. Shipping third-party license texts (Qt, ffmpeg, yt-dlp) with
the distribution is a Phase 5 release-gate item, not part of this task.
