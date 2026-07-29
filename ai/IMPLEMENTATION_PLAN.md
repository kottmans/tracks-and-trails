# IMPLEMENTATION_PLAN.md — Tracks & Trails

**Purpose:** Define the high-level delivery sequence.
**Authority:** Canonical for phase order, boundaries, and exit criteria.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-26
**Last reviewed:** 2026-07-26
**Update when:** Phase scope, delivery order, dependencies, or exit criteria change.
**Does not contain:** Individual coding tasks (`TASKS.md`), progress (`STATUS.md`).

---

## Sequencing principle

Phase 1 deliberately builds a **thin vertical slice through every architectural layer** —
UI → manager → IPC → worker → yt-dlp → SQLite — for a single download, rather than building
one complete layer at a time. The riskiest assumption in this project is `ARC-002` (the
per-job process model with IPC progress and hard cancellation). If it is wrong, that must
surface in Phase 1, while the cost of changing it is a rewrite of a few hundred lines rather
than the whole application.

Everything after Phase 1 is breadth on a proven spine.

---

## Phase 0 — Foundation

**Goal:** A runnable, tested, lint-clean skeleton with the environment questions answered.

**Prerequisites:** None.

### Deliverables

- ~~Python baseline confirmed against PySide6 wheel availability~~ — **done** (`T-002`): Python 3.14, PySide6 6.11.1
- ~~`pyproject.toml`, virtual environment, dependency set~~ — **done** (`T-001`)
- ~~Package skeleton matching `ARCHITECTURE.md` §4~~ — **done** (`T-001`)
- ~~ruff + mypy configured and passing~~ — **done** (`T-001`)
- ~~pytest + pytest-qt running~~ — **done** (`T-001`); layering-enforcement test is `T-005`
- ~~Git repository with `.gitignore`; `LICENSE`~~ — **done** (`T-004`)
- ~~`docs/DEVELOPMENT.md` created~~ — **done** (`T-001`, `DOC-002` trigger discharged)
- Layering-enforcement test (`T-005`)
- CI running lint, types, and tests on Linux and Windows (`T-006`)
- Frozen-build smoke test in CI proving `spawn` works from a frozen binary (`T-020`)
- A window that opens, shows the app icon, and closes cleanly on both platforms (`T-007`)

### Exit criteria

- `ruff check`, `ruff format --check`, `mypy src`, and `pytest` all pass locally and in CI
- The layering test fails when a deliberate `PySide6` import is added to `core/`
- The window launches on Linux **and** Windows from a clean checkout following only
  `docs/DEVELOPMENT.md`
- A frozen artifact spawns a child process without relaunching itself, on both platforms
- `LIC-001` is Accepted and `LICENSE` exists

**Exited 2026-07-26.** All five criteria verified rather than asserted:

| Criterion | Evidence |
|---|---|
| Four checks pass locally and in CI | Green locally; CI run `30215160820`, all five jobs |
| Layering test fails on a deliberate `PySide6` import in `core/` | Mutation run 2026-07-26: `test_module_respects_the_layer_rules[core/models.py]` failed, 108 others passed; restored |
| Window launches on Linux **and** Windows from a clean checkout | Linux: `T-007`. Windows: `T-026`'s `windows desktop` job runs the real `app.run` entry point under the real `windows` platform plugin and asserts the native `HWND`, visibility and title through the Win32 API |
| Frozen artifact spawns a child without relaunching itself, both platforms | `T-020`; `frozen ubuntu-latest` and `frozen windows-latest` green |
| `LIC-001` Accepted and `LICENSE` exists | Accepted; `LICENSE` present, MIT |

**What the phase exits with, named rather than hidden:** the subjective half of Windows
verification (`OPS-004`) — whether rendering *looks* right, whether Narrator *sounds* coherent,
whether the installer *feels* normal — is unverified and blocks first release, not this phase.
Installer behavior (`T-039`) has no automated gate yet. **Widget tab order does**, as of
2026-07-28: `T-040` asserts it under the real Windows platform plugin, per widget state, and both
`T-026` mutation classes were run on a real Windows desktop and killed (`COORD-R5` — this
sentence outlived being true).

**Risk retired:** PySide6 wheel availability on Python 3.14 was the phase's headline risk.
`T-002` closed it — PySide6 ships stable-ABI (`abi3`) wheels covering every Python ≥3.10, so
the baseline is not tied to PySide6's release cadence at all. Baseline is Python 3.14.

**Why freezing appears in Phase 0.** `REL-001` ships artifacts with no Python prerequisite,
which means `ARC-002` must work under PyInstaller — where a `spawn`ed child re-executes the
application binary rather than a Python interpreter. That is a recursive launch, not a subtle
bug, and no unfrozen test can catch it. `T-020` makes it a Phase 0 CI failure rather than a
Phase 5 discovery on top of a finished application.

---

## Phase 1 — Vertical slice: one download, end to end

**Goal:** Paste a URL, probe it, pick a preset, download it with live progress, cancel it.
Prove `ARC-002`.

**Prerequisites:** Phase 0 complete. **Satisfied 2026-07-26.**

> The 2026-07-25 amendment that distinguished Phase 0's *deliverables* from its *exit criteria*
> is **withdrawn as moot**, exactly as it said it would be once the Windows criterion was met.
> Phase 0 has formally exited, so the plain reading is now the true one and no distinction is
> needed. The episode is preserved in `ai/REVIEWS.md` and in `OPS-004`/`T-026`: the amendment
> existed because the criterion was believed unreachable without hardware, and `OPS-004`
> disproved that premise rather than the criterion being waived.

### Deliverables

- `core/models.py`, `core/job_state.py`, `core/errors.py` — domain and state machine
- `downloader/protocol.py` — the IPC message contract
- `downloader/worker.py` + `ytdlp_adapter.py` — yt-dlp in a spawned child process
- `downloader/manager.py` + `result_pump.py` — pool of one, progress to Qt signals
- `persistence/` — SQLite schema, migration runner, `JobRepository`
- Built-in presets and preset → yt-dlp options translation (`REQ-006`, `REQ-009`)
- Add-URL dialog with probe results (`REQ-001`, `REQ-002`, `REQ-005`)
- Single-job progress view with cancel (`REQ-014`, `REQ-015`)
- Recorded `info_dict` fixtures for adapter tests

### Exit criteria

- A real URL downloads to disk with accurate live progress and correct final bytes
- Cancel stops the download within 2 seconds with no orphaned process (verified on both
  platforms, `ps` / Task Manager)
- `kill -9` of the worker is reported as `WORKER_CRASH` and the app stays responsive
- Job state survives an application restart mid-download
- An unsupported URL produces a failed job showing the extractor's own message
- Worker code runs with no display attached (headless test passes)
- Verified on Linux **and** Windows
- Reviewed and signed off in `REVIEWS.md`

> **What "Windows" means here is `STARBASE`** (`OPS-005`, 2026-07-29): the maintainer's Windows 10
> 22H2 machine, which is both an interactive verification target and the self-hosted runner for the
> `windows desktop` job. A finding that reproduces only on a GitHub-hosted image and not there does
> not block this exit — `T-056` and `T-068` are open on exactly that basis.
>
**Not exited. Standing as of 2026-07-29:**

| Criterion | Evidence |
|---|---|
| A real URL downloads to disk with accurate live progress and correct final bytes | `T-037`, `test_a_url_becomes_a_file_with_the_bytes_it_reported`. Real yt-dlp, its generic extractor and its HTTP downloader against a local `http.server` — the §6 exception recorded for exactly this. The assertion joins the halves: the file's size equals both what the last progress message reported *and* what the queue recorded |
| Cancel stops the download within 2 seconds with no orphaned process | `T-013` and `T-019`. `CANCEL_BUDGET_SECONDS = 2.0` is asserted by `test_cancel_stops_a_real_in_flight_download_within_the_budget`, and the escalation path — a worker that ignores both the event and `SIGTERM` — by `test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget`. Orphans are covered separately by `test_cancelling_a_download_kills_what_the_worker_spawned` and `test_a_worker_killed_from_outside_does_not_leave_its_grandchild_behind` |
| `kill -9` of the worker is reported as `WORKER_CRASH` and the app stays responsive | `test_a_killed_worker_becomes_worker_crash_with_its_exit_code` and `test_the_application_survives_a_worker_crash_and_can_start_another`. `test_a_worker_that_exits_zero_without_an_outcome_is_a_crash_not_a_success` covers the case `REQ-028` cares about most |
| Job state survives an application restart mid-download | `T-037`, `test_a_job_killed_mid_download_is_recovered_by_the_next_start` — a real `SIGKILL` to a separate interpreter with the row confirmed `RUNNING` first. `test_recovery_is_the_applications_own_and_not_the_tests` plants the row directly, so the claim is about startup rather than about what the previous test left behind |
| An unsupported URL produces a failed job showing the extractor's own message | `test_the_extractor_message_survives_verbatim` (`T-057`, `T-018`'s recorded fixtures). **Thinner than the rest**: the projection is proved against recorded `info_dict` fixtures, not by putting an unsupported URL through a live session |
| Worker code runs with no display attached | `tests/unit/test_layering.py` — `core/**` and `downloader/worker.py` may not import `PySide6` or `shiboken6`, mutation-verified. The whole suite runs under `QT_QPA_PLATFORM=offscreen` |
| **Verified on Linux and Windows** | **Not met.** See below |
| **Reviewed and signed off in `REVIEWS.md`** | **Not met.** The exit review has not been called |

> **The Windows half is measured** (`T-073`, 2026-07-29): run `30415333608` ran lint, format,
> Windows-platform types, the Qt baseline, the real-plugin desktop slice and the full suite on
> `STARBASE` — 1388 passed, 20 skipped, with ffmpeg present.
>
> **The Linux half is the maintainer's own machine** (`OPS-006`, 2026-07-29). A self-hosted runner
> on the development box would share its OS, packages and libraries, so it would record results
> without verifying anything the developer's own run does not already cover. What that gives up is
> named in the decision: a change that adds a **system-library** dependency would pass on a
> desktop and fail on a bare Linux install.
>
> **The criterion is still not met, and `T-074` is why.** The Windows suite exits with an access
> violation roughly one run in four; a gate that crashes intermittently does not verify anything
> reliably. That reading is the Implementer's, and the exit review is where it is settled.

---

## Phase 2 — Queue and concurrency

**Goal:** Turn one download into a managed queue.

**Prerequisites:** Phase 1 approved. `ARC-002` confirmed sound.

### Deliverables

- Bounded concurrent worker pool, configurable limit (`REQ-013`)
- Queue view: multi-job table, per-job status/progress, pause/resume/retry/remove (`REQ-015`)
- Reordering and clear-completed (`REQ-016`)
- Crash recovery — interrupted jobs detected at startup and offered for retry (`REQ-012`)
- Bounded retry with backoff for `NETWORK` failures only (`REQ-018`)
- History persistence and completed-download records (`REQ-020`)
- Open file / reveal in file manager (`REQ-021`)
- Per-job log capture and log view (`REQ-019`)
- Single-instance guard (`A-004`)

### Exit criteria

- Three concurrent downloads show independent accurate progress with the UI interactive
  throughout (`NFR-001`)
- Hard-killing the app mid-queue and restarting restores the queue with correct states
- Concurrency limit is respected exactly; lowering it while running drains cleanly
- A second launch attaches to or refuses in favor of the running instance
- No worker process outlives application exit, on both platforms
- Reviewed and signed off

---

## Phase 3 — Format and content depth

**Goal:** Expose yt-dlp's real capability. This is the phase that separates the app from a
one-button downloader.

**Prerequisites:** Phase 2 approved.

**Trigger:** `docs/UX_SPEC.md` is created at the start of this phase (`DOC-002`).

### Deliverables

- Full sortable format table with separate video/audio selection and merge (`REQ-003`, `REQ-008`)
- Playlist probing and per-entry selection (`REQ-004`)
- Output template editor with live path preview (`REQ-011`)
- Post-processing: audio extraction/conversion, remux/recode, embed thumbnail, embed
  metadata, embed chapters, subtitle download/embed with language selection (`REQ-010`)
- User-defined presets: create, edit, duplicate, delete, set default (`REQ-007`)
- Cross-restart resume of partial downloads (`REQ-017`)
- Duplicate-URL detection and warning (`REQ-022`)

### Exit criteria

- The format table matches `yt-dlp -F` output for a fixture set of URLs
- A separate video + audio selection merges correctly via ffmpeg on both platforms
- Output template preview matches the actual written path in every tested case, including
  titles containing characters illegal on Windows
- Path containment holds: no rendered template escapes the output directory
- A partial download resumes after restart, or clearly states it cannot
- Reviewed and signed off

---

## Phase 4 — Settings, polish, and accessibility

**Goal:** Make it pleasant, configurable, and usable without a mouse.

**Prerequisites:** Phase 3 approved.

### Deliverables

- Full settings dialog covering `REQ-023`
- Network options: rate limit, proxy, retry policy
- Cookie source configuration — browser profile or cookies file — with redaction verified
  (`REQ-026`, `REQ-EXCL-003`)
- In-app yt-dlp version display and update action (`REQ-025`, `OPS-002`)
- ffmpeg detection, capability reporting, and override path (`REQ-024`)
- Theme: brand palette, light and dark (`ARCHITECTURE.md` §8)
- Accessibility pass: keyboard navigation, focus order, screen-reader labels (`NFR-005`)
- Error-surface pass: every taxonomy class has a tested, actionable presentation (`NFR-006`)

### Exit criteria

- Every function is reachable by keyboard alone, verified end to end **on Linux**
- A screen reader announces every control meaningfully **on Linux (Orca)**. On Windows this
  splits per `OPS-004`: that the UI Automation tree exposes a correct name and role for every
  control is automated by `T-026`; whether Narrator's announcements are *coherent* is
  subjective, stays with the pre-release Windows session, and is recorded as unverified until
  then — this phase may exit with that gap named, but not hidden.
- No information is conveyed by color alone
- Logs contain no cookie contents, cookie paths, proxy credentials, or token-like query
  parameters — verified by an automated redaction test (`NFR-007`)
- Updating yt-dlp in-app changes the reported version and reverting restores the baseline
- Reviewed and signed off

---

## Phase 5 — Distribution

**Goal:** Installable artifacts for both platforms and a repeatable release process.

**Prerequisites:** Phase 4 approved.

**Trigger:** `docs/RELEASE.md`, `SECURITY.md`, and `CHANGELOG.md` are created here
(`DOC-002`). A `REL-` decision recording the Linux packaging format must be accepted before
the first build.

### Deliverables

- Windows: PyInstaller one-dir build + Inno Setup installer, ffmpeg bundled (`OPS-001`)
- Linux: packaging per the `REL-` decision
- Bundled yt-dlp baseline pinned and recorded (`OPS-002`)
- License texts for Qt, ffmpeg, and yt-dlp shipped with the distribution (`LIC-001`)
- Versioning policy, release gate, and rollback procedure documented
- First tagged release

### Exit criteria

- A clean Windows 10/11 machine with no Python installs and runs the app successfully
- A clean Linux machine installs and runs it successfully
- Installer behavior is verified on the runner by `T-039` — silent install, file and shortcut
  placement, launch, uninstall and removal (`OPS-004`)
- **The Windows manual verification session is complete** and recorded in `REVIEWS.md`
  (`ai/TESTING.md` §8 item 15). `OPS-004` shrank this to the subjective residue — whether the
  rendering *looks* right, whether Narrator *sounds* coherent, whether the installer *feels*
  normal, shell foreground and file-association behavior, and long-running stability. It still
  requires a real Windows desktop and is still the one Phase 5 item that cannot be satisfied
  from the current development environment — arrange it before the phase starts, not at its end.
- Qt is dynamically linked in every artifact (`NFR-009`)
- The full test suite and the release gate pass on both platforms
- Cold start under 3 seconds on the reference machine (`NFR-002`)
- All MVP acceptance criteria (`REQUIREMENTS.md` §11) pass on both platforms
- Release review completed and recorded

---

## Deferred beyond Phase 5

Not scheduled: scheduled/deferred downloads, per-site profiles, watch-folder import, browser
"send to" integration, SponsorBlock, music-library organization and tagging, bandwidth
scheduling, macOS support. See `REQUIREMENTS.md` §7. None may be started without a phase
being added here first.

## Phase-level risks

| Risk | Phase | Mitigation |
|---|---|---|
| ~~PySide6 has no wheel for Python 3.14~~ | 0 | **Closed** by `T-002` — `abi3` wheels serve all Python ≥3.10 |
| `ARC-002` process model proves unworkable | 1 | Vertical slice first; failure is cheap and early |
| Windows `spawn` behaves differently than Linux | 1 | `spawn` everywhere from the start; CI on both from Phase 0 |
| No Windows machine exists — CI is the only Windows environment | all | `OPS-004` narrowed this: the runner is a real desktop, so `T-026`/`T-039` automate the objective half. Name what CI cannot assert and discharge that subjective residue in one pre-release session |
| yt-dlp changes option or `info_dict` shape | ongoing | Churn confined to two modules (`NFR-008`); fixtures pin the contract |
| Format-selection UI becomes unusably complex | 3 | Presets are the default path; the table is progressive disclosure |
| Windows packaging of a Qt app proves painful | 5 | Prototype the build in Phase 0 CI (`T-020`), not first at Phase 5 |
| Frozen build breaks `spawn` (recursive launch) | 0 | `freeze_support()` + `T-020` CI assertion from Phase 0 |
| yt-dlp gains a compiled dependency, breaking the `OPS-002` updater | ongoing | Purity re-checked at every release gate (`TESTING.md` §8) |
| License choice blocks public release | 0 | `LIC-001` resolved as a Phase 0 exit criterion |
