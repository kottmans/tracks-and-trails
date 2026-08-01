# IMPLEMENTATION_PLAN.md — Tracks & Trails

**Purpose:** Define the high-level delivery sequence.
**Authority:** Canonical for phase order, boundaries, and exit criteria.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-31
**Last reviewed:** 2026-07-31
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
**Exited 2026-07-29.** The Phase 1 exit review is recorded in `ai/REVIEWS.md`.

*(The first version of this table cited the layering test and `QT_QPA_PLATFORM=offscreen` as
evidence for the headless criterion. Neither establishes it — a static import guard is a different
claim, and offscreen selects a plugin rather than removing a display, so every worker test was
inheriting `DISPLAY` including the one whose docstring said otherwise. `P1EXIT-R1`. It also cited
the wrong test for the unsupported-URL row and called an inline `ExtractorError` a recorded
`info_dict` fixture — `P1EXIT-R2`. Both rows are rebuilt below; building the table is what exposed
them, which is the argument for having built it.)*

| Criterion | Evidence |
|---|---|
| A real URL downloads to disk with accurate live progress and correct final bytes | `T-037`, `test_a_url_becomes_a_file_with_the_bytes_it_reported`. Real yt-dlp, its generic extractor and its HTTP downloader against a local `http.server` — the §6 exception recorded for exactly this. The assertion joins the halves: the file's size equals both what the last progress message reported *and* what the queue recorded |
| Cancel stops the download within 2 seconds with no orphaned process | `T-013` and `T-019`. `CANCEL_BUDGET_SECONDS = 2.0` is asserted by `test_cancel_stops_a_real_in_flight_download_within_the_budget`, and the escalation path — a worker that ignores both the event and `SIGTERM` — by `test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget`. Orphans are covered separately by `test_cancelling_a_download_kills_what_the_worker_spawned` and `test_a_worker_killed_from_outside_does_not_leave_its_grandchild_behind` |
| `kill -9` of the worker is reported as `WORKER_CRASH` and the app stays responsive | `test_a_killed_worker_becomes_worker_crash_with_its_exit_code` and `test_the_application_survives_a_worker_crash_and_can_start_another`. `test_a_worker_that_exits_zero_without_an_outcome_is_a_crash_not_a_success` covers the case `REQ-028` cares about most |
| Job state survives an application restart mid-download | `T-037`, `test_a_job_killed_mid_download_is_recovered_by_the_next_start` — a real `SIGKILL` to a separate interpreter with the row confirmed `RUNNING` first. `test_recovery_is_the_applications_own_and_not_the_tests` plants the row directly, so the claim is about startup rather than about what the previous test left behind |
| An unsupported URL produces a failed job showing the extractor's own message | `test_an_unsupported_url_fails_the_job_with_the_extractors_own_message` raises `UnsupportedError` through a real `run_session`, and asserts `UNSUPPORTED_URL` **and** the message by equality. `test_an_unsupported_url_shows_the_extractors_message_character_for_character` proves the UI shows that kind and message without paraphrase; `test_a_failed_probe_leaves_the_job_failed_and_recorded` proves the corresponding job is stored as `FAILED` with both values intact. Mutation-verified: removing the `UnsupportedError` row from the adapter's table makes it answer `EXTRACTOR_ERROR`, which the parent class would silently supply. **Limit, stated:** the error is injected at the `_extract` seam, so yt-dlp's own recognition of such a URL is not exercised |
| Worker code runs with no display attached | `test_the_worker_runs_in_a_real_spawned_process_with_no_display` — the scrub and the workload are now **one observation**: `monkeypatch.delenv` removes `DISPLAY` and `WAYLAND_DISPLAY` before `spawn` copies the environment, `_spawn_target` asserts their absence in the child, and that same child runs a real `run_session` whose message sequence is protocol-validated. Both halves mutation-verified: restoring the inherited environment fails, and injecting `os.environ["DISPLAY"]` into `run_session` fails. `test_the_worker_really_runs_with_no_display_attached` covers resolution separately |
| **Verified on Linux and Windows** | **Met with accepted residual risk.** Linux: the documented gate passed on the maintainer machine during the exit review — ruff and format clean, native and Windows-platform mypy clean, **1430 passed, 11 skipped, 2 deselected**. Windows: `T-073` run `30415333608` passed the full `STARBASE` gate — **1388 passed, 20 skipped** — with the unexplained one-time access violation retained as open Medium `T-074` and explicitly accepted by `OPS-007` |
| **Reviewed and signed off in `REVIEWS.md`** | **Met 2026-07-29.** The Phase 1 exit review approved all eight criteria, independently reran the Linux gate and criterion mutations, and recorded the `OPS-005` and `OPS-007` residuals rather than treating them as fixes |

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
> **The exit review calls the criterion met with `OPS-007`'s residual accepted, not resolved.**
> The Windows suite exited once with an access violation in ordinary `ResultPump` delivery — the
> `ARC-002` path this phase exists to prove. The faulting object and product-versus-harness
> classification remain unknown. Three deliberate full-suite batches then produced **0 crashes in
> 51 runs**: 12 at `ea53c71` (run `30429327464`), 24 pre-`T-090` (run `30454206697`), and 15
> post-`T-090` at `35fc7ec` (run `30478557533`). Along with 60 isolated-test runs and 250
> in-process iterations, that is **361 attempts with no reproduction**. The pre-fix sample was
> already clean, so this does **not** establish `T-090` as the cause. `T-074` remains open at
> Medium with its acceptance criteria unmet; `T-092` owns the crash-dump trap, and recurrence
> reopens the decision.
>
> *(This previously read "roughly one run in four", which was the anecdote's denominator rather
> than a measurement.)*

---

## Phase 2 — Queue and concurrency

**Goal:** Turn one download into a managed queue.

**Prerequisites:** Phase 1 approved. `ARC-002` confirmed sound. **Satisfied 2026-07-29.**

**Status: in progress** (2026-07-31). **Seven of thirteen deliverables are built** — three approved,
four awaiting a verdict. Five more are Ready and one is still Proposed. **The blocking risk is not
code:** exit criterion 5 says *on both platforms*, and no CI job of any kind has executed a step
since 2026-07-30 — see "What stands between here and the exit" below, and `STATUS.md` for the
measurement.

*(These counts are transcribed from the table below rather than written beside it. `COORD-R5`
through `COORD-R11` are seven rounds of a hand-written summary drifting from the thing it
summarises, and the first draft of this line said "five approved, four in review, three not
started" against a table holding three, four, four and two.)*

### The shape of what is left

```mermaid
flowchart LR
    classDef approved fill:#1a7f4b,stroke:#0d4f2d,stroke-width:2px,color:#fff
    classDef review   fill:#b8860b,stroke:#7a5808,stroke-width:2px,color:#fff
    classDef ready    fill:#1f5fa8,stroke:#123a68,stroke-width:2px,color:#fff
    classDef proposed fill:#4a4a4a,stroke:#2a2a2a,stroke-width:2px,color:#fff
    classDef exit     fill:#5b2d8e,stroke:#3a1c5c,stroke-width:3px,color:#fff

    T078["<b>T-078</b><br/>worker pool"]:::approved
    T079["<b>T-079</b><br/>queue view"]:::approved
    T085["<b>T-085</b><br/>history records"]:::approved

    T080["<b>T-080</b><br/>pause · resume<br/>cancel · retry · remove"]:::review
    T081["<b>T-081</b><br/>reorder<br/>clear finished"]:::review
    T046["<b>T-046</b><br/>path collision"]:::review
    T083["<b>T-083</b><br/>bounded retry"]:::review
    T053["<b>T-053</b><br/>log isolation proof"]:::review

    T082["<b>T-082</b><br/>crash recovery"]:::ready
    T084["<b>T-084</b><br/>log capture + view"]:::ready
    T100["<b>T-100</b><br/>history view"]:::ready
    T102["<b>T-102</b><br/>settings reports"]:::ready
    T087["<b>T-087</b><br/>single instance"]:::ready

    T086["<b>T-086</b><br/>open · reveal file"]:::proposed
    T088["<b>T-088</b><br/>prove the phase"]:::proposed
    EXIT(["<b>Phase 2 exit</b>"]):::exit

    T078 --> T079
    T078 --> T046
    T078 --> T083
    T078 --> T082
    T078 --> T084
    T078 --> T053
    T079 --> T080
    T079 --> T081
    T085 --> T100
    T100 --> T086
    T053 -. gates approval .-> T084

    T080 --> T088
    T081 --> T088
    T082 --> T088
    T084 --> T088
    T086 --> T088
    T087 --> T088
    T088 --> EXIT
```

**Green is approved, amber awaits a verdict, blue is startable now, grey has not started.**
`T-046`, `T-083` and `T-102` are deliverables that `T-088` does not gate — they are correctness and
diagnostics rather than queue behaviour the phase proof exercises — so they carry no edge into it.

### Decisions taken during this phase

Recorded here because each one changed what a deliverable *is*, not merely how it was built:

| Decision | What it settled |
|---|---|
| `ARC-007` (+ amendment) | The settings surface is `settings.toml` plus one main-window control, and `CONCURRENCY_MAXIMUM = 16` |
| `ARC-008` | A `settings.toml` that exists and cannot be used **reports** rather than reverting silently. `T-102` implements it |
| `UX-001` | Pause is a queue-level drain; remove never deletes a file |
| `ARC-006` (+ `T-094`) | The single-instance guard is a `QLocalServer` named from the resolved database path, with an atomic Windows ownership primitive |
| `OPS-008` | The environment ownership gate's three blind spots stay open |
| **The `PAUSED` edges** (maintainer, 2026-07-31) | `RUNNING → PAUSED` and `PAUSED → RUNNING` were unreachable under `UX-001`, so `T-080` removed them **and the `JobStatus.PAUSED` member**. `REQ-017` in Phase 3 is the named reopening condition |
| **`P2PLAN-R7`** (maintainer, 2026-07-31) | Manual retry re-enters the queue at the back. Confirmed as a decision in its own right, **not** as something `P2PLAN-R1` settled |

### Deliverables

| # | Deliverable | Owner | State |
|---|---|---|---|
| 1 | Bounded concurrent worker pool, configurable limit (`REQ-013`). **The configuration surface is `ARC-007`**: `settings.toml` via `core/settings.py`, plus one control in the existing main window. The full `REQ-023` settings dialog stays Phase 4 | `T-078`, `T-097` | **Approved** 2026-07-30 (`0f9986f`) |
| 2 | Queue view: multi-job table, per-job status/progress | `T-079` | **Approved** 2026-07-31 (`da49a51`) |
| 3 | **Pause and resume are queue-level** (`UX-001`); cancel, retry and remove are per job (`REQ-015` as amended 2026-07-29). *(This read "per-job status/progress, pause/resume/retry/remove", which contradicted the amendment — `P2PLAN-R1`.)* | `T-080` | **In review** 2026-07-31 |
| 4 | Reordering and clear-completed (`REQ-016`) | `T-081` | **In review** 2026-07-31 |
| 5 | Output-path collision policy against the filesystem (`DAT-002`, `REQ-011`) | `T-046` | **In review** 2026-07-31 |
| 6 | Bounded retry with backoff for `NETWORK` failures only (`REQ-018`) | `T-083` | **In review** 2026-07-31 — its bound and backoff ship **provisional**, awaiting a `DECISIONS.md` entry (`AGENTS.md` §4) |
| 7 | History persistence and completed-download records (`REQ-020`) | `T-085`, `T-050`, `T-093` | **Approved** 2026-07-30 |
| 8 | A corrupt `settings.toml` reports rather than reverting silently (`ARC-008`) | `T-102` | **Ready** — filed 2026-07-31 |
| 9 | Crash recovery — interrupted jobs detected at startup and offered for retry (`REQ-012`) | `T-082` | **Ready** |
| 10 | Per-job log capture and log view (`REQ-019`) | `T-084`, gated by `T-053` | **Ready**; `T-053` in review |
| 11 | History view over those records | `T-100` | **Ready** |
| 12 | Open file / reveal in file manager (`REQ-021`), from both views | `T-086` | **Proposed** — released once `T-100` lands |
| 13 | Single-instance guard (`A-004`, `ARC-006`) | `T-087` | **Ready** — promoted 2026-07-31; its `T-094` primitive is approved |

*(Deliverable 5 was **added 2026-07-31**. `DAT-002` filed `T-046` as a Phase 2 task and this list
never named it — the same class as `P2PLAN-R8`, where the history records were listed and the view
that makes them reachable was not. A deliverable nothing lists is one nothing can report as
outstanding.)*

*(Deliverable 11 was added 2026-07-30 after `P2PLAN-R8`: this list named the records and not the
view, Phase 3 and 4 named neither, and `REQ-021` presupposes one. Phase 2's own clear-completed
plus `UX-001`'s remove-never-deletes leave the user unable to find their files without it.)*

**Carried, blocking nothing:** `T-099`, `T-101` and `T-103` are review follow-ups filed against
Phase 2 work. None is a deliverable and none gates the exit; they are listed in `TASKS.md`.

### Exit criteria

| # | Criterion | State |
|---|---|---|
| 1 | Three concurrent downloads show independent accurate progress with the UI interactive throughout (`NFR-001`) | **Evidenced, not yet proven end to end.** `T-079`'s first acceptance criterion asserts it and was approved; `T-088` re-proves it against the whole phase |
| 2 | Hard-killing the app mid-queue and restarting restores the queue with correct states | **Not met** — `T-082` (Ready) and `T-088` (Proposed) |
| 3 | Concurrency limit is respected exactly; lowering it while running drains cleanly, and so does pausing the queue (`UX-001` — the same reasoning: no partial file to have a rule about) | **Half met.** The limit half is `T-078`, approved, including a lowered limit draining. The pause half is `T-080`, in review |
| 4 | A second launch attaches to or refuses in favor of the running instance | **Not met** — `T-087`, **Ready** and startable now |
| 5 | No worker process outlives application exit, on both platforms | **Not met, and currently unreachable.** Linux is covered for a pool of one (`T-019`, Phase 1) and has never been re-run against a pool of N. **Windows has never run against the pool at all** — see below |
| 6 | Reviewed and signed off | **Not met** — four tasks await a verdict |

> **What stands between here and the exit is a runner, not a feature.**
>
> Criterion 5 says *on both platforms*, and Phase 1's own note fixes what "Windows" means: it is
> `STARBASE` (`OPS-005`). **No CI job has executed a single step since 2026-07-30 04:08 UTC** —
> GitHub-hosted jobs fail in three to four seconds having run nothing, and the self-hosted
> `windows desktop` job is starved and then cancelled by the next push. The last fully green CI
> push run was 2026-07-28 (`11e1203`).
>
> Every Phase 2 task approved or delivered since then rests on the maintainer's Linux machine
> alone (`OPS-006`). That is sufficient for a *task* under `AGENTS.md` §8; it is **not** sufficient
> for criterion 5, which is a claim about Windows.
>
> `OPS-005` covers a criterion that waits on an unreachable environment and `OPS-006` states the
> general rule — *a criterion that waits on a payment is not a gate*. **Neither is invoked here**,
> and this note is not an application for a waiver: the phase is not ready to exit on other
> grounds, so nothing needs deciding yet. It is recorded now so the decision is made deliberately
> when criteria 2, 4 and 6 are met, rather than discovered at the exit review.

---

## Phase 3 — Format and content depth

**Goal:** Expose yt-dlp's real capability. This is the phase that separates the app from a
one-button downloader.

**Prerequisites:** Phase 2 approved.

**Trigger:** `docs/UX_SPEC.md` is created at the start of this phase (`DOC-002`). **Owned by
`T-105`** as of 2026-08-01 — it was a scheduled trigger with no task behind it, which is how a
phase starts without the document it is supposed to start with.

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
the first build. **That decision does not exist** — the only `REL-` entry is `REL-001`, which
decides artifacts are frozen and says nothing about format. **`T-106` owns taking it** (filed
2026-08-01), and it is worth taking early: AppImage, Flatpak and system packages differ in how the
application finds `ffmpeg` and where it may write, which reaches back into `REQ-024` and `NFR-004`
long before Phase 5.

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
| **CI stops executing entirely, so "a red run blocks" stops meaning anything** | 2 | **Live as of 2026-07-31**, not hypothetical: no job has run a step since 2026-07-30, hosted jobs fail before step one and the self-hosted job is starved. Measured in `STATUS.md`. The mitigation is that it is *visible* — a zero-step failure must never be read as a test failure, and no task may be reported as gated by CI until a run executes a step. It blocks Phase 2's exit criterion 5, not its tasks |
| License choice blocks public release | 0 | `LIC-001` resolved as a Phase 0 exit criterion |
