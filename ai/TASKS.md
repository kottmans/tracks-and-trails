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

**Start here:** the Phase 0 exit review found corrections. `T-027` through `T-032` are Ready;
`T-026` remains blocked on the `OPS-004` correction in `T-031`. Phase 0 cannot exit until the
review findings and the real Windows launch criterion are discharged.

---

## Ready

### T-033 — Bundle the pinned yt-dlp baseline into the frozen artifact

**Status:** Proposed
**Owner:** Implementer
**Priority:** High — blocks any usable release, and fails in a way that looks like a site bug
**Phase:** lands with `T-012`; verified by `T-020`'s CI job; gates Phase 5
**Depends on:** `T-012` (the worker is the first thing to import `yt_dlp`)
**Relevant context:** `OPS-002`, `REL-001`, `ARCHITECTURE.md` §6 and §12, `NFR-008`, `C-002`
**Affected surfaces:** `packaging/tracks-and-trails.spec`, `packaging/frozen_smoke.py`,
`.github/workflows/ci.yml`
**Risk:** **High** — the failure mode is silent at build time and total at run time

#### Scope

`OPS-002` says every release bundles a pinned yt-dlp baseline. The frozen artifact currently
contains **none of it**: a search of the built `dist/tracks-and-trails` for `yt_dlp` returns
zero files. That is correct today — nothing imports it, because `worker.py` and
`ytdlp_adapter.py` are still stubs — but it will not self-correct when `T-012` lands.

PyInstaller's analysis follows *static* imports. yt-dlp resolves its extractors dynamically:
1046 package files, **972 of them extractor modules**, reached through `lazy_extractors`
rather than by direct import. Static analysis will therefore collect the yt-dlp core and miss
essentially every extractor.

The resulting failure is the dangerous kind: the artifact **builds and launches normally**,
`import yt_dlp` succeeds, and then every real URL fails to find an extractor — which reads
exactly like the site-breakage `C-002` teaches everyone to expect, so it will be misdiagnosed.

Collect the package explicitly in the spec, and prove it from inside the artifact.

#### Acceptance criteria

- The frozen artifact contains the yt-dlp package, and the bundled version **equals the pin in
  `pyproject.toml`** — asserted, not eyeballed, so a stale build cannot pass
- A probe **inside the frozen artifact** imports `yt_dlp` and resolves a named extractor for a
  stable URL pattern, without network access
- Removing the collection from the spec makes that probe fail — the mutation is exercised once
  and reverted, as `T-020`'s negative proof was
- The `OPS-002` resolution order is honoured: with a directory present at
  `user_data_dir/tracksandtrails/ytdlp/`, the worker reports **that** version; with it absent
  or unimportable, it reports the baseline and says why
- Both the Linux and Windows frozen jobs stay green, and the artifact-size change is recorded

#### Out of scope

- The in-app update action itself (`OPS-002`, Phase 4) — this task bundles the baseline and
  proves the resolution order; downloading and extracting a wheel is separate
- Trimming the bundle. 972 extractor modules is a size cost worth measuring, but excluding
  extractors to save space would re-create this defect deliberately
- Any change to the pin

**Note:** `ai/TESTING.md` §8's release gate re-checks that yt-dlp is still pure Python. This
task is the other half — that the pure-Python package actually *ships*. Purity without
inclusion still yields an application that cannot download anything.

---

## Proposed — Phase 0

### T-026 — Verify Windows behavior against the runner's real desktop

**Status:** Proposed — blocked on `OPS-004` being accepted
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0 follow-up; must land before the first public release
**Depends on:** `T-006`, `T-007`, `OPS-004`
**Relevant context:** `OPS-004`, `OPS-003` (superseded classification), `NFR-005`,
`ai/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `tests/ui/`, `ai/TESTING.md`,
`REQUIREMENTS.md` §3
**Risk:** Medium — it converts release-blocking manual work into automation, so a weak
implementation would retire a gate without replacing it

#### Scope

`OPS-003` assumed a CI runner has no desktop and wrote off most Windows verification as
human-only. A spike disproved that: `windows-latest` reports `platformName == 'windows'`,
a 1024×768 display, a native `HWND` whose title the Win32 API reads back, and captures
screenshots with native font rendering.

Move the objective half of Windows verification into CI:

1. **Real-plugin rendering.** Run the UI suite on Windows without `QT_QPA_PLATFORM=offscreen`
   as well as with it, and retain screenshots of each key window as artifacts.
2. **Focus and keyboard.** Assert tab order and focus chain through synthetic key events on a
   real window, not an offscreen one.
3. **Accessibility tree.** Assert every control's name and role as exposed to UI Automation —
   what a screen reader reads (`NFR-005`). Needs a dev-only dependency such as `comtypes`.
4. **Installer**, once one exists (Phase 5): silent install, files, shortcuts, uninstall,
   removal — on a runner, which is a genuinely clean machine.

#### Acceptance criteria

- The Windows job runs the UI suite under the real `windows` platform plugin and uploads a
  screenshot of every key window. **A screenshot is retained evidence, not a gate**: it is
  uploaded for a human to look at and does not turn the build red on its own. Any claim that
  a broken layout "fails" must be backed by a separate objective assertion — a widget's
  geometry, visibility, or size — not by the image (`T031-R2`).
- Tab order and focus chain are asserted on Windows, and reordering two widgets fails the test
- Every interactive control exposes a non-empty accessible name and a correct role through UI
  Automation; removing a label fails the test
- `ai/TESTING.md` §9's manual Windows list is rewritten to only what remains subjective, and
  `REQUIREMENTS.md` §3's "known-unverified" wording is narrowed to match — **each item moved
  only once its replacement automation has landed and is green**, never on the strength of
  this task's intent
- Native file dialogs, reveal-in-file-manager and open-file behavior are handled per
  `OPS-004`'s split: the request, path handling and shell verb are asserted; foreground and
  file-association behavior stay on the manual list
- Both the offscreen and real-plugin runs stay green, and the added time is recorded against
  `T-006`'s budget

#### Out of scope

- Pixel-perfect screenshot diffing — retain screenshots as evidence first; baselines are a
  separate decision, and a brittle image gate is worse than none
- The subjective residue in `OPS-004`: whether rendering looks right, whether Narrator sounds
  coherent, installer feel, long-running stability. Those still need a person and still block
  first release
- Buying or renting a cloud Windows desktop — complementary, not part of this

**Note:** this is the rare task that *reduces* release-blocking manual work. The risk is doing
it shallowly: a screenshot nobody looks at and an accessibility assertion that passes on an
empty tree would retire a real gate and replace it with theatre.

The criteria are therefore of two kinds, and conflating them is exactly the failure mode
(`P0-R7`). **Gates** — focus order, accessibility names and roles, installer placement — are
each stated as a mutation that must turn the suite red, and only those may retire a manual
item. **Retained evidence** — the screenshots — is uploaded for a human to look at and fails
nothing on its own; it supports a judgement rather than replacing one.

---

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

### T-027 — Reject unsafe stored window geometry

**Status:** In Review — addressed 2026-07-25; awaiting re-review
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** `T-007`
**Relevant context:** Phase 0 finding `P0-R1`, `NFR-004`
**Affected surfaces:** `ui/main_window.py`, `tests/ui/test_main_window.py`
**Risk:** Medium — one damaged state file can prevent every subsequent application launch

#### Scope

Make window restoration honor its "never raises" contract for every TOML value and keep a
previous monitor layout from restoring the only window entirely off-screen.

#### Acceptance criteria

- TOML `inf`, values outside Qt's signed 32-bit geometry range, booleans, and huge integers
  fall back without an exception or Qt overflow warning
- Stored geometry that intersects no available screen is moved onto an available screen
- The existing round-trip remains green for ordinary negative coordinates and positive sizes
- Each new adversarial case fails against `2d06153` before the production fix is applied

---

### T-028 — Remove undocumented cross-thread Qt access from the launch test

**Status:** In Review — addressed 2026-07-25; awaiting re-review
**Owner:** Reviewer / Implementer
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-007`
**Relevant context:** Phase 0 finding `P0-R2`, `ai/REVIEWS.md` standing Qt-threading risk
**Affected surfaces:** `tests/ui/test_app_launch.py`
**Risk:** Low — this is test reliability, but it guards the phase's real startup path

#### Acceptance criteria

- The watcher uses only Qt APIs documented thread-safe from a foreign thread; it does not
  poll `QApplication.instance()` during construction
- A failed quit request cannot silently turn into a subprocess timeout
- The launch/quit test passes repeatedly on Linux and in the Windows matrix
- The ordering proof still establishes that `window.show()` runs before the queued quit

---

### T-029 — Complete the frozen-probe negative and evidence gates

**Status:** In Review — addressed 2026-07-25; awaiting re-review
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** `T-020`
**Relevant context:** Phase 0 findings `P0-R3`, `P0-R4`, `P0-R5`, `REL-001`, `ARC-002`
**Affected surfaces:** `_freeze_probe.py`, `packaging/frozen_smoke.py`, CI workflow
**Risk:** High — the probe guards recursive application launch in the distributed artifact

#### Acceptance criteria

- A temporary Windows CI mutation removes `freeze_support()`, the frozen smoke step goes red,
  and retained evidence records more than one top-level start including multiprocessing argv
- The mutation is reverted and the final Linux and Windows frozen jobs are green
- The smoke gate fails if either the parent or spawned child does not report `frozen=True`
- The raw probe log is uploaded from its actual `dist/frozen-probe.log` location, or the
  redundant raw-log upload claim is removed and `frozen-smoke.txt` is made canonical
- No temporary mutation remains in the final tree


#### Work completed — 2026-07-25

**The Windows negative proof, which had never been run.** `T-020`'s criterion required that
removing `freeze_support()` fails the frozen smoke test *on Windows*; it was only ever
exercised on Linux. Run `30186080950` removed it and pushed:

```
frozen windows-latest = failure
--spawn-probe exited 1 in 120.2s     (the child never sent its message)
top-level application starts recorded: 2
  app-start pid=3344 frozen=True argv=['--spawn-probe']
  app-start pid=1700 frozen=True argv=['--multiprocessing-fork', 'parent_pid=3344', 'pipe_handle=608']
```

That second argv is **Windows-specific** — `parent_pid`/`pipe_handle`, where Linux produced
`tracker_fd`/`pipe_handle` — so this is genuinely the Windows relaunch path and not a Linux
result restated. All four jobs went red, not just the frozen ones. Reverted in the following
commit; run `30186222977` is green on all four, and no mutation remains in the tree.

**`frozen=True` is now asserted, not printed.** The smoke test previously printed the parent's
and child's frozen state and asserted nothing about it, so it would have passed against a
source run — which proves nothing about freezing, the entire point of `T-020`.

**The raw probe log upload was silently broken.** CI requested `frozen-probe.log` at the
repository root; `frozen_smoke.py` writes it beside the artifact at `dist/frozen-probe.log`,
so the upload had been contributing nothing. Corrected, and confirmed by the negative run's
artifact, which now contains the log.
---

### T-030 — Ratify the two Phase 0 architecture additions

**Status:** In Review — addressed 2026-07-25; awaiting re-review
**Owner:** Planner
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-007`, `T-020`
**Relevant context:** Phase 0 finding `P0-R6`, `ARCHITECTURE.md` §4 and §5
**Affected surfaces:** `ai/ARCHITECTURE.md`
**Risk:** Low — the implementations are reasonable; the canonical ownership map is incomplete

#### Acceptance criteria

- §5 assigns ephemeral window geometry to the UI and records
  `user_config_dir/tracksandtrails/window.toml`
- §4 or §12 records `_freeze_probe.py` as frozen-build diagnostic infrastructure outside the
  product layers and explains why it must share the real entry point
- The changes ratify current behavior without broadening product scope or creating a routine
  `DECISIONS.md` completion entry

---

### T-031 — Correct OPS-004 before deciding it

**Status:** In Review — addressed 2026-07-25; awaiting re-review
**Owner:** Planner / Maintainer + Reviewer (`ai/TESTING.md`)
**Priority:** High
**Phase:** Phase 0 review correction
**Depends on:** none
**Relevant context:** Phase 0 finding `P0-R7`, `OPS-003`, proposed `OPS-004`, `T-026`
**Affected surfaces:** `ai/DECISIONS.md`, `ai/TASKS.md` (`T-026`), `ai/TESTING.md`
**Risk:** Medium — an omitted verification category could disappear when the manual gate shrinks

#### Acceptance criteria

- Native file dialogs, reveal-in-file-manager, and open-file behavior are explicitly assigned
  to automation or retained manual verification; they do not disappear between `OPS-003` and
  `OPS-004`
- `T-026` distinguishes a retained screenshot from a red/green layout assertion and does not
  claim that a visible mutation fails the suite unless an objective assertion actually does
- The manual list shrinks only after each replacement automation has landed
- After those corrections, the maintainer accepts or rejects `OPS-004` explicitly

---

### T-032 — Reconcile Phase 0 current-truth documents

**Status:** In Review — addressed 2026-07-25; awaiting re-review
**Owner:** Planner + Reviewer (`ai/TESTING.md`)
**Priority:** Medium
**Phase:** Phase 0 review correction
**Depends on:** `T-027` through `T-031`
**Relevant context:** Phase 0 finding `P0-R8`, `AGENTS.md` §6
**Affected surfaces:** `ai/STATUS.md`, `ai/TASKS.md`, `ai/TESTING.md`
**Risk:** Low — stale navigation and exact counts misstate what is implemented and reviewed

#### Acceptance criteria

- `STATUS.md` no longer asks to merge completed work, call completed tasks "in review", or
  describe the replaced placeholder `app.run`
- Exact source counts are recomputed rather than copied; at `2d06153` there are 31 Python
  modules, 26 docstring-only stubs, and 5 modules with code
- `TASKS.md` headings agree with task statuses, and the exit-review next step is current
- `TESTING.md`'s status note acknowledges resource, layering, and shell-window tests while
  retaining the honest boundary that only one of §7's ten mandatory areas is covered

---

## Complete

### T-007 — Application shell window

**Status:** Complete
**Completed:** 2026-07-25. **The Codex review was waived by the maintainer**, who authorized
the merge to unblock `T-020`. Recorded rather than implied: unlike `T-003`, `T-006` and
`T-005`, this task received **no independent review at all** — not a waived re-review after
findings, but no first pass. `AGENTS.md` §3 requires review by a different agent; that did not
happen here. The Windows config-directory bug below was caught by CI, not by review, and a
reviewer would plausibly have found more.
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

#### Implementation record — 2026-07-25

**Delivered:** `ui/main_window.py` (menu bar, About box, geometry), `app.py` (`QApplication`
setup, argument handling, event loop), `tests/ui/test_main_window.py` (17 cases),
`tests/ui/test_app_launch.py` (4 cases, subprocess). Suite 154 passed, 1 deselected.

**Two consequences this task forced that its text did not mention.**

1. **`ARCHITECTURE.md` §5's data-ownership table has no row for window geometry.** §5 assigns
   `settings.toml` to `core/settings.py`, which does not exist and is not this task's to
   build. Geometry is not a user setting — nobody edits it deliberately and losing it costs
   nothing — so it went to its own `user_config_dir/tracksandtrails/window.toml`, consistent
   with `DAT-001` (TOML, `platformdirs`, inspectable) and leaving the real settings layer
   free to arrive without a migration. **Reported, not decided:** §5 needs a row for window
   state, which is a Planner call.
2. **`test_module_entry_point_runs_and_exits_zero` could not survive a real window.** It ran
   `python -m tracks_and_trails` and expected exit 0; with a GUI it blocked until the 60 s
   timeout. `app.py`'s placeholder anticipated this ("unused until `T-007` parses
   arguments"), so `run` now handles `--version` and `--help` **before** constructing a
   `QApplication` — they must work with no display — and the test uses `--version`.

**Acceptance criteria:**

| Criterion | Evidence |
|---|---|
| Launches and exits cleanly, zero exit code, no Qt warnings | Verified under a **real Wayland session**: exit 0, stderr exactly 0 bytes |
| App icon in title bar and About dialog | `QIcon` from `icon.ico`, all seven frames asserted; About box screenshotted |
| Geometry persists across restarts | Round-trip test, plus a subprocess launch/quit confirming the file is written |
| Cold start under 3 s (`NFR-002`), measured and recorded | **median 0.178 s**, min 0.146, max 0.181, 10/10 runs on the reference machine |
| `pytest-qt` test constructs and closes offscreen | `test_window_constructs_and_closes_offscreen` |

**The "no Qt warnings" criterion needed care.** Headless runs emit `This plugin does not
support propagateSizeHints()`. Rather than relax the assertion, this was traced: it comes from
the `offscreen` and `minimal` plugins, reproduces with a bare `QMainWindow` plus a menu bar
and no project code, and does **not** occur under a real platform plugin, where stderr is
empty. It is allowlisted by exact string so the check still fails on anything else.

**A Qt threading defect in the test harness, found and fixed.** The first launch harness
polled `topLevelWidgets()` and `isVisible()` from a watcher thread — the "Qt object touched
off the GUI thread" violation in `ai/REVIEWS.md`'s standing risk list. It was intermittently
unreliable: 2 of 8 runs never saw the window and one took 18 s. The harness now touches only
`QApplication.instance()` and the thread-safe `QMetaObject.invokeMethod(..., QueuedConnection)`,
relying on `run` calling `show()` before `exec()` for ordering. 10/10 clean afterwards. The
instability was the harness, never the application.

**A Windows-only production bug, caught by CI on the first run.** `user_config_dir(APP_SLUG)`
inserts an author segment on Windows, defaulting it to the app name, so the real config path
would have been `%APPDATA%\tracksandtrails\tracksandtrails\` — a doubled directory that does
not match `ARCHITECTURE.md` §5. Invisible on Linux, where the call is identical either way.
Fixed with `appauthor=False` and pinned by `test_config_directory_is_not_doubled`, which
asserts the shape rather than the platform-specific string.

The same CI run also exposed a defect in the test that found it: `run_headless` redirected
platformdirs by setting `XDG_CONFIG_HOME`, `APPDATA` and `LOCALAPPDATA`, but platformdirs
resolves Windows folders through `SHGetKnownFolderPath` via ctypes and ignores `APPDATA`
entirely. The Windows job was therefore writing to the runner's real profile. It now uses
platformdirs' documented `WIN_PD_OVERRIDE_*` variables. **This is precisely the `OPS-003`
case for CI**: neither fault was observable on the development machine.

**Known-unverified.** Whether the icon appears correctly in the **Windows** taskbar and title
bar, and how the About box renders there, are not automatable and remain `OPS-003` gaps —
CI proves the assets load and the window constructs, not that they look right. Cold start was
measured on Linux only; `NFR-002` names the reference Linux machine, so this is complete as
specified, but Windows startup time is unmeasured.


#### Re-review corrections — 2026-07-25

**`P0-R1`, the fix was incomplete and its test enshrined the gap.** Validating each of the
four numbers against int32 was not enough: `QRect` computes `right()` and `bottom()` as
`x + width - 1`, and Qt's `intersects()` normalises internally. At `y = 2**31 - 1`, `bottom()`
wrapped to **-2147483170**, so an off-screen rectangle was reported as touching a screen, the
recovery never fired, and the window was restored where it could never be clicked. At
`x = -2**31` the same thing happened through a different overflow, even with both edges
representable.

`test_int32_boundary_values_are_accepted` asserted precisely those values were acceptable —
and only exercised `load_geometry`, so it could not see damage that happened *after* loading
succeeded. It has been replaced by `test_extreme_coordinates_never_strand_the_window`, which
asserts on the **restored** geometry across six extreme inputs.

Rather than chase which Qt operation overflows where, stored coordinates are now bounded to
`_MAX_COORD` (`2**24 - 1`), matching Qt's own `QWIDGETSIZE_MAX`. No real display arrangement
approaches 16.7 million pixels, and inside that range none of Qt's geometry arithmetic can
wrap. `test_the_largest_usable_coordinate_still_round_trips` guards against the bound being
tightened so far that legitimate multi-monitor offsets are discarded.

**`P0-R6`** — the contradiction was introduced by the previous fix. §4 listed the module while
§12 and its docstring both said it was outside §4. Corrected everywhere to the accurate
statement: it is listed in §4's structure and belongs to none of the four **layers**.

**`P0-R7`** — `T-026`'s closing note claimed every criterion was a failing mutation, while the
criteria themselves had just been corrected to make screenshots evidence-only. The note now
separates **gates** (focus order, accessibility names and roles, installer placement — each a
mutation that must turn the suite red, and only these may retire a manual item) from
**retained evidence** (screenshots, which fail nothing on their own). `OPS-004` remains
formally **Proposed**; accepting it is the maintainer's call and is surfaced in `STATUS.md`.

**`P0-R8`** — eight heading/status mismatches, now zero, verified by a script rather than by
reading. `STATUS.md` said seven findings where there were eight, claimed `main` was the only
branch while PR #7 was open, and still called `T-005` and `T-007` "in review" after both had
merged.
---

### T-020 — Frozen-build smoke test in CI

**Status:** Complete
**Completed:** 2026-07-25 — merged to `main` as part of `4d6ad3c`; **no independent review**, pending the Phase 0 exit review
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

#### Implementation record — 2026-07-25

**Delivered:** `_freeze_probe.py` (spawn probe and start marker), `packaging/tracks-and-trails.spec`
(minimal one-dir PyInstaller build), `packaging/frozen_smoke.py` (runs the artifact and
asserts), a `--spawn-probe` argument, and a separate `frozen` CI job on both platforms.
`psutil` added as a dev-only dependency for the orphan check (`AGENTS.md` §7: no `DECISIONS`
entry needed).

**`freeze_support()` was already correct.** `T-001` placed it as the first executable statement
of `__main__.py` with a comment citing `REL-001`, ahead of any Qt import. This task verified
that placement rather than making it.

**A separate CI job, not extra steps on `check`.** The build dominates the test suite, and
folding it in would hide that cost inside `T-006`'s ~10 minute budget. The task permits this
provided the runtime is recorded, which the job does explicitly.

**The detection method was wrong on the first attempt, and the negative test is what found
it.** `run_probe` originally wrote the "application started" marker itself, on the reasoning
that a relaunched child would re-enter the same path. It does not: a relaunched child inherits
*multiprocessing's* argument vector, not the parent's, so it never reaches `--spawn-probe`.
Removing `freeze_support()` and rebuilding produced a genuine recursion while the marker count
stayed at 1 — the assertion would have passed through exactly the failure it exists to catch.
The marker now lives in `main()`, which every top-level start reaches.

**Negative test, on Linux.** With `freeze_support()` commented out and the artifact rebuilt,
the probe exits **1** and the log records **three** top-level application starts instead of
one. The `argv` column names the mechanism outright:

```
app-start pid=110766 frozen=True argv=['--spawn-probe']
app-start pid=110768 frozen=True argv=['--multiprocessing-fork', 'tracker_fd=7', 'pipe_handle=9']
app-start pid=110767 frozen=True argv=['-B','-S','-I','-c','from multiprocessing.resource_tracker import main;main(6)']
```

Those second and third lines are multiprocessing's internal invocations being executed as the
whole application. `T-020` predicted this would fail "on Windows"; it fails on **Linux too**,
which is a better outcome than the task assumed — the guard is not Windows-specific.

**Positive result, Linux:** frozen artifact 284 MB, `--version` in 0.1 s, `--spawn-probe`
exits 0 in 0.3 s, exactly one top-level start, both parent and child report `frozen=True`, no
orphan. Build 15 s locally.

**Deliberate deviation, reported.** `_freeze_probe.py` belongs to none of
`ARCHITECTURE.md` §4's four layers (it is listed in §4's structure and described in §12 as
frozen-build infrastructure). It is underscore-prefixed to mark it as infrastructure rather than a layer, imports
no Qt so a spawned child inherits none, and is reachable only through an explicit argument.
The alternative — a separate frozen entry point — would not have tested `__main__.py`'s
ordering, which is the only thing that matters here. `--spawn-probe` is listed in `--help`
rather than hidden.

**Windows is unverified until this runs in CI**, which is the whole point of the job
(`OPS-003`).

---

### T-025 — Phase 0 exit preparation

**Status:** Complete
**Completed:** 2026-07-25 — merged to `main` as part of `4d6ad3c`; **no independent review**, pending the Phase 0 exit review
**Owner:** Implementer + Documentation Maintainer
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-007`, `T-020`
**Relevant context:** `IMPLEMENTATION_PLAN.md` Phase 0 exit criteria, `OPS-003`
**Affected surfaces:** `docs/DEVELOPMENT.md`
**Risk:** Low

#### Scope

Discharge the Phase 0 exit criteria that are not any single task's responsibility: bring
`docs/DEVELOPMENT.md` back in line with what the code now does, and re-run the clean-checkout
verification the exit criteria require, which has not been done since `T-001` — before the
window existed.

#### Acceptance criteria

- `docs/DEVELOPMENT.md` describes the application as it is, and every command in it is
  verified to work verbatim from a clean checkout
- The four gates pass from a checkout containing only git-tracked files
- The window launches and exits cleanly from that checkout on Linux
- Windows remains explicitly unverified (`OPS-003`), not quietly assumed

#### Out of scope

- The Windows interactive launch, which needs a real Windows session and blocks first release
- The Phase 0 exit review itself, which is Codex's

#### Implementation record — 2026-07-25

**Stale documentation corrected.** `docs/DEVELOPMENT.md` still said "It prints a version
banner and exits 0. There is no window yet — that is `T-007`." `T-007` had shipped, so the one
file the exit criteria name as the thing to follow was describing an application that no
longer existed. It now documents `--version` and the real window, the frozen build (`T-020`),
and `packaging/` and `_freeze_probe.py` in the layout.

**Clean-checkout verification, from 73 git-tracked files only** — no `.venv`, no `.git`, no
caches, no egg-info. Following the document verbatim:

| Step | Result |
|---|---|
| `python3 -m venv .venv`, `pip install -e ".[dev]"` | installed cleanly |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 58 files already formatted |
| `mypy` | Success: no issues in 44 source files |
| `pytest` | 158 passed, 1 deselected |
| `python -m tracks_and_trails --version` | `0.1.0.dev0`, exit 0 |
| `python -m tracks_and_trails` | window opened and exited 0, **stderr 0 bytes**, geometry written at the 960×640 default |
| `pip install -e ".[dev,build]"` + the documented PyInstaller invocation | built |
| `python packaging/frozen_smoke.py dist/tracks-and-trails` | OK: one top-level start, no orphan |

Every command in the document was executed as written rather than read for plausibility.

**Phase 0 exit criteria standing after this:**

| Criterion | Standing |
|---|---|
| Gates pass locally and in CI | **Met** |
| Layering test fails on a deliberate `core/` Qt import | **Met** (`T-005`, five real injections) |
| Window launches from a clean checkout on **Linux** | **Met** — above |
| Window launches from a clean checkout on **Windows** | **NOT met.** Blocked by `OPS-003`; needs a real Windows session. CI proves it constructs offscreen and that the frozen artifact runs, which is not the same claim. |
| Frozen artifact spawns without relaunching, both platforms | **Met** (`T-020`) |
| `LIC-001` Accepted and `LICENSE` exists | **Met** (`T-004`) |

Phase 0 cannot be declared fully exited on the letter of its own criteria until someone
launches the window on Windows. That is the same gap `OPS-003` records and `ai/TESTING.md` §9
lists as blocking first release; it is not newly discovered here, and everything automatable
around it is done.

---

### T-005 — Layering enforcement test

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged as `88b810f` via PR #2
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

#### Implementation record — 2026-07-25

**Delivered:** `tests/unit/test_layering.py`, 45 tests. Static `ast` analysis, no imports
executed — importing to inspect `sys.modules` would run module-level code, and a module
importing Qt lazily inside a function would pass while still breaking the frozen worker.

**Four rules, not two.** This task's Scope enumerates four checks while its Out of scope line
says "the two rules in `ARCHITECTURE.md` §4". Read as: implement the enumerated four, and do
not invent a fifth. All four are stated in the linked context — §4's diagram gives the two
headline rules, §4's bullets add "`worker.py` … never Qt", and §6 with `NFR-008` confines
`yt_dlp` to two modules. Flagged rather than silently resolved.

**A documentation imprecision, not a conflict.** §4's structure block calls `worker.py` "the
ONLY module that calls `yt_dlp`", while §6 permits both `worker.py` and `ytdlp_adapter.py` to
import it. These are consistent if "calls" is read as §6's "the only place `YoutubeDL` is
instantiated". The test follows §6, which is explicit. Not worth a task; noted so the next
reader does not have to re-derive it.

**Verification — five real violations injected into the actual tree**, each confirmed to fail
with a message naming both the file and the rule, then reverted with `src/` hashed before and
after to prove restoration:

| Injected | Caught by |
|---|---|
| `import PySide6` in `core/models.py` | core/ must not import Qt |
| `from PySide6.QtCore import QObject` in `core/job_state.py` | core/ must not import Qt |
| `import yt_dlp` in `ui/main_window.py` | both the `ui/` rule and the two-owner rule |
| `import PySide6` in `downloader/worker.py` | worker.py must not import Qt |
| `import yt_dlp` in `persistence/db.py` | only `worker.py` and `ytdlp_adapter.py` may import yt-dlp |

**The guard is itself guarded.** `ai/REVIEWS.md` names layering as an area where "the
enforcement test can be weakened as easily as bypassed" — narrowing a rule's `applies_to` or
dropping a package from `forbidden` leaves the tree passing and nothing else notices. Thirteen
synthetic cases assert the analyzer still catches what it must and still permits what the
architecture allows; a `test_source_tree_is_not_empty` guard catches the glob silently
matching nothing.

**Known limit, stated in the module docstring rather than left implicit:** only `import`
statements are analyzed. `importlib.import_module("PySide6")` and `__import__` are not
detected. Accepted, not overlooked — a dynamic import of Qt is conspicuous in review in a way
a plain one is not.

**Checks:** `ruff check`, `ruff format --check`, `mypy src`, and `pytest` all green.

#### Review corrections — 2026-07-25

**`T005-R1`, High — the analyzer's self-protection was routed around.** The finding is
correct and it is the exact failure the original design claimed to prevent. The synthetic
cases asserted the analyzer's behavior at a handful of *hardcoded paths*, so narrowing the
`core/` predicate to those same paths left all 45 tests green, as did adding
`downloader/environment.py` as a third yt-dlp owner. The guard was checking itself against its
own examples rather than against the architecture.

Fixed by stating the architecture a second time, independently. `architecture_forbids()`
derives what a file may not import straight from its path, sharing no constant or predicate
with `RULES`, and `test_every_module_is_actually_guarded` sweeps **every real module** in the
tree asserting the analyzer would catch every package the architecture forbids there. A
literal `ARCH_YTDLP_OWNERS` is compared against `YTDLP_OWNERS`, so widening the allowlist
fails rather than silently permitting a third importer. Two statements that must agree cannot
be routed around by editing one.

Verified by reproducing the reviewer's two bypasses and two more:

| Weakening | Result |
|---|---|
| Narrow the `core/` predicate to `core/models.py` + `core/paths.py` | **fails** — every other `core/` module reported as an enforcement hole |
| Add `downloader/environment.py` as a third yt-dlp owner | **fails** twice — allowlist mismatch, and `environment.py` unguarded |
| Drop `shiboken6` from `QT` | **fails** — `shiboken6` uncaught across `core/` |
| Make `check()` return `[]` unconditionally | **fails** — 36 of 76 |

**`T005-R2`, Low — the static test imported the package under test.** Correct and
self-contradictory: locating `SRC` via `import tracks_and_trails` executed its `__init__` and
bound the analysis to whichever copy was installed rather than this checkout. `SRC` is now
derived from `Path(__file__)`, so the module imports nothing from the package it analyzes.

**`T005-R3`, Low — stale current truth.** `STATUS.md` still said nothing in `TESTING.md` was
implemented. Rewritten to separate the two claims that had been conflated: no application
*behavior* exists, which remains true and is the warning worth keeping, while the *scaffolding*
that guards it does — CI, asset invariants, and this test.

**Suite:** 103 passed, 1 deselected (was 27 before `T-005`, 72 at first review).

---

### T-024 — Close T-005 review findings

**Status:** Complete
**Completed:** 2026-07-25. **The focused re-review was waived by the maintainer**, who
authorized the merge after two review rounds on `T-005`. Recorded rather than implied: the
acceptance criterion "`T005-R1` through `T005-R3` receive focused re-review" was **not** met
for this second pass. The set-equality fix and the `STATUS.md` module count are therefore
maintainer-accepted, not reviewer-verified.
**Owner:** Implementer (test correction) + Planner (coordination correction)
**Priority:** High
**Phase:** Phase 0
**Depends on:** `T-005`
**Relevant context:** `ai/REVIEWS.md` findings `T005-R1` through `T005-R3`;
`ARCHITECTURE.md` §4 and §6
**Affected surfaces:** `tests/unit/test_layering.py`, `ai/STATUS.md`
**Risk:** **High** — a green layering guard can be weakened around its sampled fixtures

#### Scope

Make the analyzer's self-tests pin the complete architectural rule definitions rather than
sample paths. Keep source discovery static and rooted in the repository without importing the
package under test. Correct the stale blanket statement in `STATUS.md` that nothing in
`TESTING.md` is implemented.

#### Acceptance criteria

- Narrowing the core rule to the currently sampled `core/models.py` and `core/paths.py` makes
  the suite red
- Adding any third existing module to `YTDLP_OWNERS` makes the suite red
- Dropping `shiboken6`, emptying `YTDLP_OWNERS`, or making `check()` return `[]` makes the
  suite red
- Adding an architecture-allowed package such as `typing` to a forbidden set, or widening a
  rule onto a layer where that package is allowed, makes the suite red
- The five real-tree violation probes from `T-005` still fail with the offending file and
  rule in the message, and the source tree is restored byte-for-byte
- The test locates and parses the repository source tree without importing
  `tracks_and_trails`; every Python module under that tree is swept
- `STATUS.md` accurately distinguishes the implemented `T-001` entry-point scaffold,
  implemented test infrastructure, and approved future application behavior
- The default suite and Linux/Windows matrix are green
- `T005-R1` through `T005-R3` receive focused re-review

#### Out of scope

- Detecting dynamic `importlib.import_module()` or `__import__()` calls
- Changing the layer boundaries or adding a fifth rule

#### Work completed — 2026-07-25

**Pass 1** closed the false-negative half of `T005-R1` (an independent
`architecture_forbids()` plus a real-tree sweep), `T005-R2` (source discovery via
`Path(__file__)`, importing nothing), and the blanket half of `T005-R3`.

**Pass 2 — the one-way comparison.** Re-review found the fix proved only that *required*
prohibitions exist, never that no *surplus* ones had been added: putting `typing` into `QT`
left all 76 tests green. Required-only agreement is not agreement.

`test_every_module_is_guarded_no_more_than_the_architecture_requires` now asserts set
**equality** between what `RULES` reject and what `ARCHITECTURE.md` forbids, per module, in
both directions. Surplus prohibitions matter as much as missing ones: a rule that rejects
legitimate code gets loosened or deleted by whoever it blocks, taking the real protection
with it.

**Pass 2 — `T005-R3`.** The claim "not one module in §4's structure has an implementation"
was still false: `__main__.py` and `app.py` carry `T-001`'s entry-point scaffold. Counted
rather than estimated — of 30 modules under `src/`, **27 are docstring-only stubs** and three
hold code (`__init__.py`, `__main__.py`, `app.py`, all `T-001`). `STATUS.md` now says exactly
that.

**Every weakening in `T-024`'s acceptance criteria, probed and reverted:**

| Weakening | Suite |
|---|---|
| Add `typing` to `QT` | 8 failed |
| Add `typing` to `YTDLP` | 28 failed |
| Widen the Qt rule onto `downloader/`, where Qt is allowed | 7 failed |
| Widen the Qt rule onto `ui/`, where Qt is allowed | 10 failed |
| Narrow `core/` to the two sampled files | 10 failed |
| Add a third `YTDLP_OWNERS` entry | 3 failed |
| Empty `YTDLP_OWNERS` | 5 failed |
| Drop `shiboken6` | 17 failed |

The five real-tree violation probes still fail with the file and rule named, and `src/` was
hashed before and after: byte-identical. Suite 133 passed, 1 deselected.

---

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
