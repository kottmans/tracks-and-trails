# TESTING.md — Tracks & Trails

**Purpose:** Define how the project is verified.
**Authority:** Canonical for validation policy, required checks, gates, and coverage expectations.
**Owner:** Reviewer (Codex) — policy; Implementer may add checks a change introduces.
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-28
**Last reviewed:** 2026-07-26
**Update when:** A test type, CI requirement, mandatory command, coverage rule, or gate changes.
**Does not contain:** Local setup instructions (`docs/DEVELOPMENT.md`, once created).

> **Status note:** The toolchain and commands below are live as of `T-001` (2026-07-25) and
> pass. The suite is still mostly structural — the domain layer (`T-010`) is the first
> behavior it covers, and nothing downloads yet. Sections
> §7 (mandatory high-risk coverage) and §8 (release gate) describe the approved target, not
> current coverage. `ai/STATUS.md` is authoritative for what actually runs today.

---

## 1. Philosophy

Three things drive the test strategy, and they come straight from the architecture:

1. **The logic lives in `core/`, so most tests are fast, headless, and Qt-free.** If a rule is
   hard to test, it is probably in the wrong layer.
2. **yt-dlp and the network are not under our control.** They are mocked or replayed from
   recorded fixtures in every default-run test. Real-network tests exist, are marked, and
   are opt-in — a test that fails because a site changed teaches us nothing about our code.
3. **The dangerous parts are the boundaries.** Process lifecycle, cancellation, crash
   recovery, filename safety, and log redaction get disproportionate attention, because
   those are where failures are silent, destructive, or both.

## 2. Test types

| Type | Location | Runs by default | What it covers |
|---|---|---|---|
| Unit | `tests/unit/` | yes | `core/` domain logic, state machine, presets, path rendering, error classification, `ytdlp_adapter` projection against recorded fixtures, persistence repositories against a temp DB |
| Layering | `tests/unit/test_layering.py` | yes | The import rules in `ARCHITECTURE.md` §4 **and** §6, by static `ast` analysis: no Qt in `core/` or `downloader/worker.py`, no `yt_dlp` in `ui/`, and no `yt_dlp` anywhere but `worker.py` and `ytdlp_adapter.py` (`T-005`) |
| Resources | `tests/unit/test_resources.py`, `tests/ui/test_resources.py` | yes | Shipped asset invariants: the icon PNGs exist at their declared dimensions, `icon.ico` declares and exposes its full frame set, and every asset loads through `QIcon` (`T-022`) |
| UI | `tests/ui/` | yes (offscreen) | Widget behavior, signal wiring, keyboard navigation, accessible names — via `pytest-qt` with `QT_QPA_PLATFORM=offscreen` |
| Integration | `tests/integration/` | yes | Real child processes and real IPC, with yt-dlp faked at the adapter seam: progress delivery, cancellation, worker-crash handling, migrations, crash recovery |
| Process tree | `tests/integration/` — `test_manager.py`, `test_crash_kill.py`, `test_single_instance.py`, `test_phase_2_exit.py`, `test_composition.py`, `test_worker.py` | **yes**, since `T-019` | Real workers spawned and killed. This row said "**no** — `-m process_tree`" and promised the marker was "opt-in only until `T-019` lands". `T-019` landed, cancelling now reaps the worker's whole process group, and **the marker was retired with it** — so these have run in the default suite ever since, and a reader following that row would have selected nothing. The hazard the marker managed is not gone: these tests contend for real processes, which is why `T-123` has to identify them before anything runs the suite in parallel |
| Network | `tests/network/` | **no** — `-m network` | A small set of real URLs against real yt-dlp. Run before a release and when diagnosing extractor issues |

## 3. Required checks by change type

| Change | Required before "complete" |
|---|---|
| Documentation only — `ai/`, `docs/`, `README.md`, comments | **None.** No behavior changed. |
| Source change | `ruff check`, `ruff format --check`, `mypy src`, plus the tests relevant to the change |
| Change that adds or edits a **test** file | The above, plus **bare** `mypy` and `mypy --platform win32`. `mypy src` does not read `tests/`, so a test file's type errors reach no gate before the `windows desktop` CI job — see §12 |
| Change in `core/`, `downloader/`, or `persistence/` | The above, plus the **full** `tests/unit` and `tests/integration` suites — these layers have cross-cutting effects |
| Dependency add/remove/major bump | Full default suite on **both** platforms, plus a recorded `DECISIONS.md` entry (`AGENTS.md` §7) |
| Anything toward a tagged release or distributed build | The full suite **and** §8's release gate, regardless of how small the change looks |

Never report a check as passing without running it. Report the real result, including
failures (`AGENTS.md` §8).

## 4. Commands

Established by `T-001`; kept in sync here as the authoritative list.
`docs/DEVELOPMENT.md` may repeat them as convenience shortcuts but must not redefine policy.

```bash
ruff check .                 # lint
ruff format --check .        # formatting
mypy src                     # static types, what the `check` CI job runs
mypy                         # src *and* tests — the only gate that reads tests/ (§12)
mypy --platform win32        # the same scope, with Windows-guarded bodies analysed
pytest                       # default suite (excludes network)
pytest tests/unit            # fast headless loop
pytest -m network            # opt-in, real network
pytest --cov=tracks_and_trails --cov-report=term-missing
```

## 5. Fixtures and test data

- **Recorded `info_dict` fixtures** in `tests/fixtures/infodicts/` are the pinned contract
  between yt-dlp and `ytdlp_adapter.py`. Each records the yt-dlp version and capture date.
  Refreshing one is a deliberate act with its own task — a silently refreshed fixture hides
  exactly the breakage it exists to catch.
- **`tests/fixtures/capture.py` is how a fixture is taken or refreshed** (`T-018`). Run by hand,
  never by a test: it touches the network, sanitizes on the way in, and writes the provenance
  block. Its existence is what makes "refreshing is deliberate" a reproducible act rather than a
  remembered one.
- **Every fixture declares `capture_method`: `recorded` or `derived`** (`T-018`). A derived one
  must also say what it was derived from and which fields are synthetic. The distinction is not
  bookkeeping: the next reader treats a fixture's shape as evidence of what a site really sends,
  and one case — `DRM_PROTECTED` — cannot honestly be recorded at all, because capturing it
  would mean probing a DRM service that `REQ-EXCL-001` and `SEC-001` put out of scope.
- **Recorded failures** in `tests/fixtures/errors/` pin the other half of the boundary: the
  exception type yt-dlp raised, where that type lives, its verbatim message, and the taxonomy
  kind `ARCHITECTURE.md` §7 says it must become. The import of the recorded type is an
  `NFR-008` canary — an upstream rename fails a test instead of a download.
- **Filename fixtures** must include titles with characters illegal on NTFS, Windows
  reserved device names (`CON`, `NUL`, `LPT1`), trailing dots and spaces, emoji, RTL text,
  and path-traversal attempts (`../`, absolute paths).
- No test may write outside `tmp_path`. No test may download real media into the repository.
- Tests must not read or write the developer's real config, data, or cache directories —
  `platformdirs` paths are redirected to `tmp_path` by an autouse fixture.

## 6. Mocking policy

- **Never mock `core/`.** It is pure; test it directly. A mock in a `core/` unit test means
  the code has a dependency it should not have.
- **Always fake yt-dlp** in default-run tests, at the `ytdlp_adapter` seam — not by patching
  yt-dlp internals, which would couple tests to yt-dlp's private structure.
- **Never mock the process boundary in integration tests.** The entire point of
  `tests/integration/` is that real processes are spawned, real messages cross a real queue,
  and real terminations are issued. A mocked subprocess cannot fail the way a real one does.
- **One exception to "always fake yt-dlp", introduced by `T-013` and bounded here.** Two tests —
  a download that completes and `REQ-015`'s cancellation — run the **real** yt-dlp against a
  local `http.server` serving throttled `video/mp4` from `127.0.0.1`. What is faked is the
  *site*, not the library: no packet leaves the machine, so §1's "a site changed" flakiness does
  not apply, and these do not belong behind `-m network`. The reason is that the acceptance
  criterion is specifically about a download with **bytes actually moving** — `T-002` proved
  cancellation against a sleeping worker and recorded that as insufficient, and a faked
  `_extract` cannot be cancelled from a progress hook because it never calls one. Any further
  use of this pattern needs the same justification: faking yt-dlp remains the default.
- Do not mock SQLite. Use a real database in `tmp_path`; it is fast and catches actual SQL
  and migration errors.

## 7. Mandatory test coverage for high-risk behavior

These require an explicit test before the owning phase can exit. Each exists because the
failure mode is silent, destructive, or both.

| Area | Must be proven |
|---|---|
| Layering | `core/` importing Qt fails the suite; `ui/` importing `yt_dlp` fails the suite |
| Cancellation | Cancel terminates the worker within 2 s and leaves no orphan process |
| Worker crash | `SIGKILL`/`TerminateProcess` on a worker yields `WORKER_CRASH`, app survives (`REQ-028`) |
| Crash recovery | A DB with jobs stuck in `RUNNING` is recovered to a retryable state at startup |
| State machine | Every illegal transition raises; no silent state corruption |
| Path safety | No rendered output template escapes the output directory; Windows-illegal names are sanitized on both platforms |
| Log redaction | Cookie paths/contents, proxy credentials, and URL query parameters never reach any log — asserted on what a **handler emitted**, not on a redaction function (`NFR-007`, `T-038`) |
| DRM | `DRM_PROTECTED` is never auto-retried and has no bypass path (`REQ-EXCL-001`, `SEC-001`) |
| Migrations | Every migration runs forward from every prior schema version with data intact |
| Settings freeze | A settings change mid-flight does not alter a running job's `DownloadRequest` |

**Every mandatory area above is back in the default run as of `T-019`** (2026-07-27).
Cancellation and Worker
crash spent one day behind `-m process_tree`, because the defect `T-019` owned left descendants
that wedged later runs; that defect is fixed, so the reason is gone and the marker with it. The
episode is worth keeping in mind rather than in a marker: while the exclusion stood, `T019-R1`
found it had removed those two areas from **CI** as well — `addopts` is global and both check
jobs ran a bare `pytest` — so for a day two mandatory areas gated nothing anywhere while three
records said otherwise. A skip that is recorded is still a skip; check what actually runs.

**Each of these must be proven by mutation, not by a passing run** — remove the guard and watch
the suite fail. §13 explains why that is not pedantry: five tests in this project have passed
while the behavior they protected was deleted.

## 8. Release gate

All of the following, **on Linux and Windows**, before any tag or distributed build:

1. `ruff check`, `ruff format --check`, `mypy src` — clean
2. Full default suite — green
3. `pytest -m network` — green against the current pinned yt-dlp baseline
4. Every §7 mandatory test — present and passing
5. Migration check — the previous release's database opens, migrates, and retains data
6. `REQUIREMENTS.md` §11 MVP acceptance criteria — manually verified and recorded
7. Built artifact installs and runs on a **clean** machine with **no Python and no
   development toolchain** installed (`REQ-029`, `REL-001`)
8. Frozen-build smoke test passes: launch, run one real download to completion, cancel
   another, exit — confirming no recursive launch and no orphaned processes
   (`freeze_support()`, `REL-001`)
9. yt-dlp purity re-check: the pinned baseline still contains no compiled extensions, so the
   `OPS-002` wheel-extraction update path remains viable
10. In-app yt-dlp update works **from the frozen artifact** — download, extract, resolve the
    new version, and revert to baseline
11. Qt confirmed dynamically linked in the artifact (`NFR-009`, `LIC-001`)
12. License texts for Qt, ffmpeg, and yt-dlp present in the distribution
13. No secrets, cookies, or personal paths in the artifact or the repository
14. Cold start under 3 seconds on the reference machine (`NFR-002`)
15. **Windows manual verification session completed** — the §9 list performed on a real
    Windows desktop and recorded in `REVIEWS.md`. Blocking for the first public release;
    CI green is not a substitute (`OPS-003`).

## 9. Manual verification

Some things cannot be automated and are checked by hand, recorded in `REVIEWS.md` with the
date and platform:

- Screen-reader announcement *quality* — whether Orca and Narrator say something **coherent**.
  That the accessibility tree exposes a correct name and role for every control is no longer
  manual on Windows: `T-026`'s UI Automation gate gives that, and it is green
- Native file dialogs, "reveal in file manager", and "open file" on both desktops — the
  foreground and file-association half. Per `OPS-004` the request, path handling and shell verb
  are automatable, but none of that exists to test yet; revisit when the feature lands
- Visual correctness of light and dark themes
- Installer flow on a clean machine — until `T-039` automates placement and removal, at which
  point only whether it *feels* normal stays here
- Real-world download of a large file, watching memory and responsiveness

### What Windows CI does and does not cover (`OPS-004`)

`OPS-003` held that Windows manual verification was impossible and that everything above was
**known-unverified** there. Half of that is no longer true. The runner has a real desktop, and
since 2026-07-26 the `windows desktop` job asserts against it: the window launches under the
real platform plugin with a native `HWND` Windows reports by title, menus are keyboard
reachable, and the UI Automation tree exposes a correct name and role for every control.

What remains genuinely manual is the **subjective** residue listed above — whether it looks
right, sounds coherent, and feels normal. That still needs a person, still cannot be done from
the current development environment, and is still a **blocking item before the first public
release** (§8, item 15).

Two gaps in the automation are worth naming rather than discovering later:

- **Widget tab order is gated on both platforms as of 2026-07-28** (`T-040`, `COORD-R5`).
  Offscreen, `tests/ui/test_add_dialog.py` walks Qt's own focus chain against a hand-transcribed
  order. Under the **real** Windows platform plugin, `tests/ui/test_windows_desktop.py` walks Tab
  and Backtab per widget state, and both `T-026` mutation classes were executed on a real desktop
  and killed. §12 records what that gating does *not* cover. This entry read "not yet on Windows"
  after it had been done, which is the drift `COORD-R5` reported; until it landed, Windows
  keyboard use beyond the menu bar stayed
  unverified.
- **Installer behavior is not gated.** `T-039`, once Phase 5 produces an installer.

Do not record a manual item as passed because this job is green. It covers what it covers.

## 10. CI

Runs on every push and pull request. **Every test runs on every push, on both platforms** — what
changed on 2026-08-03 is *where* Windows runs and *when its answer arrives*, not what is covered.
`OPS-010` is the governing decision; the subsection below states it operationally.

### What runs on an ordinary push, since 2026-08-03 (`OPS-010`)

| Trigger | What runs |
|---|---|
| **push and pull request** | everything: Linux `check`, the full `windows desktop` suite, `frozen ubuntu-latest`, `frozen windows`, the coverage notice |
| **nightly (06:00 UTC) and `workflow_dispatch`** | the same, plus it cannot be cancelled by a push |

**Linux lands in ~7 minutes; Windows arrives later, and you do not wait for it.** Three Windows
jobs serialise on the one self-hosted slot — measured in run `30861672178`: `windows desktop`
12m56s, `frozen windows` ~6m, each starting two seconds after the previous finished. `OPS-010`
makes that explicit: **Windows evidence is required before a task is reviewed, not before work
continues.** Carry on against the Linux gate while it runs.

For a brief period the desktop suite was `[win]`-gated on pushes. `P2EXIT-R4` reversed that: it
was removed for wall-clock and defended with the hosted-minute constraint, which does not apply to
a job running on hardware the maintainer owns. **There is no opt-in marker any more** — a commit
message containing `[win]` means nothing.

One saving remains, and it is the one quota actually forces:

- **The Windows leg of `check` is dropped while `WINDOWS_RUNNER` points at `STARBASE`.** Both jobs
  ran the identical suite — 1972 passed, 21 skipped, 32 deselected, within four seconds of each
  other — because that variable put them on the same machine. What the leg contributed was
  *clean-machine* evidence on a fresh hosted image, which is precisely what it stops being when
  routed to the desktop. **What is surrendered with it is the offscreen platform plugin on
  Windows**, that cell existing nowhere else. Unset the variable and both return.

Plus one that costs nothing:

- **The desktop job's virtualenv persists between runs**, keyed by a hash of `pyproject.toml`.
  Building it was 111 s of the 13 minutes, on a machine whose disk survives. It lives under
  `RUNNER_TOOL_CACHE`, outside the workspace, because checkout cleans ignored files — and the
  directory name is truncated to 12 hash characters so PySide6's QML paths clear Windows'
  260-character `MAX_PATH`.

Platform-specific breakage in `spawn` behavior, path handling, and packaging is the expected
failure mode of this project; discovering it late is the thing CI exists to prevent. That is the
reason the coverage came back.

CI runs lint, format check, types, and the default suite. Network tests do not run in CI.
A red CI run blocks merge.

Implemented by `T-006` as `.github/workflows/ci.yml`. Two properties are load-bearing rather
than stylistic, both following from `OPS-003`: `fail-fast` is **off**, so a Linux failure
never cancels the Windows job, and every job uploads its `reports/` evidence **whether it
passed or failed**. Do not "tidy" either away.

### Where Windows failure evidence lives

With no Windows machine, CI output is the only Windows debugging evidence there is — but it
comes in two forms, and neither replaces the other:

| Source | Covers | Retention |
|---|---|---|
| **Actions job log** (GitHub-owned) | *Every* step, including checkout, `setup-python`, apt, and pip — all of which run before `reports/` exists. A failure there yields little or no artifact, so the log is the only record. | Repository log-retention setting |
| **`reports/` artifact** (ours) | This project's own gates: lint, format, mypy, the Qt baseline, pytest, plus the environment snapshot and junit XML. Downloadable, so it can be grepped and diffed offline. | 30 days, set in the workflow |

The distinction is worth keeping straight: the artifact is not the whole record, and the
project's own gates are the only part of it we control. That is why each one tees its stdout
*and stderr* into `reports/` — `T006-R1` found lint, format, and mypy reaching the log alone,
and the piped steps dropping stderr.

`.github/scripts/qt_baseline.py` runs before the suite and verifies the Qt stack itself —
PySide6 imports, and a `QApplication` + `QWidget` construct offscreen. It is not a pytest test
on purpose: if Qt is broken on a runner, every UI test failure is that same failure reported
less clearly.

### Type-checking Windows-only code (`T026-R4`)

`mypy` is configured for the host platform, so on Linux the bodies of
`tests/ui/test_windows_{desktop,accessibility}.py` sit behind a `sys.platform` guard mypy
proves unreachable — and are therefore never analysed at all. A module-scoped override in
`pyproject.toml` silences the resulting noise, which left those files with **no** effective
type gate anywhere: a deliberate `int = "not an int"` passed every check.

`mypy --platform win32` makes the guard true and analyses them. Run it whenever those files
change; the `windows desktop` job runs it on every push. It caught seven real errors the first
time it was used, including `QAction.menu()` being typed as `QObject` rather than `QMenu`.

**Run it bare — `mypy --platform win32`, not `mypy --platform win32 src`.** The two commands
differ in *scope*, not just in platform, and the difference is the whole point: the `check` job
runs `mypy src` (33 files) while the `windows desktop` job runs the unscoped command (**69
files**, `src` **and** `tests`). So a type error in a test file is invisible to every gate except
this one.

`T-016` proved that the expensive way. Its handoff recorded `mypy src` and
`mypy --platform win32 src` as passing, both true, and CI failed on two real errors in
`tests/ui/test_add_dialog.py` — neither of them Windows-specific. One was `nextInFocusChain()`
returning `QWidget | None`; the other was mypy narrowing a property to `str` at an earlier
`assert ... is not None`, which made the later `assert ... is None` statically impossible and
**silently stopped type-checking the rest of that test**. Adding `src` to this command narrows it
back to the scope that cannot see any of that.

### What the environment ownership gate actually promises (`T044-R1`)

`tests/unit/test_environment.py` pins `downloader/environment.py`'s reviewed public API, so a new
export that answers "what version?" or "does it work?" fails rather than quietly eroding the
locate/import split (`ARCHITECTURE.md` §6).

**How it decides what is exported changed after five review rounds, and the promise is now
deliberately narrow.** Every version that tried to recognise an export by parsing the source was
defeated by a shape its author had not enumerated — a conditional definition, tuple-
destructuring, a `match` capture, a walrus in a default argument. Each fix enumerated one layer
further out and was defeated by the next. The gate now reads `vars(module)` and subtracts only
what the parse shows was imported; the interpreter's namespace cannot be evaded by syntax.

**It guarantees exactly this:** under the interpreter, platform and configuration the suite runs
in, a public attribute not bound by an `import` statement is reported.

**It does not cover**, and three tests pin each rather than leaving it to memory:

- anything behind a guard false at run time — OS, architecture, dependency presence, feature
  probe, environment state;
- a name imported and then rebound, the ordinary `try: from x import Y / except ImportError:`
  shape of an optional dependency;
- dynamic rebinding of an imported name.

**A previous version of this section claimed the `[ubuntu-latest, windows-latest]` matrix
compensated for the first gap. It does not**, and the claim is recorded here because it was
wrong in a way worth not repeating: the matrix covers only guards true on Windows and false on
Linux. Every other guard is false on both runners. `T-047` carries whether the gaps are worth
closing; the gate remains useful for what it does catch, which is accidental erosion.

### The `windows desktop` job (`T-026`, `OPS-004`)

Every job above pins `QT_QPA_PLATFORM=offscreen`, which is correct for a headless suite and is
why none of them can satisfy Phase 0's "the window launches ... on Windows" exit criterion.
The `windows-desktop` job is the one place that override is absent, so Qt loads the real
`windows` platform plugin and the window reaches an actual desktop.

Windows only: the Linux runner has no display server, and Linux launch is verified on the
maintainer's own desktop — which Windows has never had.

**Since `T-073` this job also carries the whole Windows gate**, not just the desktop slice: lint,
format, the Qt baseline and the full suite, all offscreen, after the real-plugin tests have run.
That is not its original purpose. It happened because `check (windows-latest)` is hosted and has
not started since the Actions quota ran out, leaving Phase 1's *verified on Windows* criterion
with nowhere to be measured; `OPS-005` made `STARBASE` that place. The job keeps its name because
the desktop role above is still true and still why it exists.

Two things still differ from the hosted job, and neither is papered over:

- **ffmpeg is recorded, not installed.** `check` runs `choco install ffmpeg`; this job must never
  provision the machine it runs on, so it reports what is there. The default suite does not need
  ffmpeg — measured with it removed from `PATH`, the counts are identical — so the run states which
  configuration it measured rather than gating on it.
- **The interpreter is the machine's**, not `actions/setup-python`'s, for the reason recorded in
  the job itself: installing one deadlocked against `msiexec` and left the machine's Python
  half-removed.

Three rules keep this job from going green while proving nothing, which is its only real
failure mode:

1. Tests marked `windows_desktop` **fail rather than skip** when the platform plugin is not
   `windows`. A skip would be silent; a failure is not.
2. They are excluded from the default suite by `addopts`, and the job opts back in with
   `pytest -m windows_desktop`. Collecting none of them exits 5, so a marker typo or a
   swallowed module turns the job red rather than passing vacuously.
3. Screenshots in `reports/screenshots/` are **retained evidence, not a gate** (`T031-R2`).
   Nothing asserts on their content; they exist for a human to look at. Every claim that
   turns the build red is a separate objective assertion.

## 11. Coverage

Coverage is a signal, not a target — no build fails on a percentage. Expectations:

- `core/` — near-complete. It is pure logic with no excuse for untested branches.
- `persistence/`, `downloader/protocol.py`, `ytdlp_adapter.py` — high.
- `ui/` — behavior and wiring, not pixels. Low line coverage here is acceptable and expected.
- Anything in §7 — no gaps, ever.

## 12. Known gaps

Tracked honestly; each should become a task or be accepted deliberately.

- **The suite is structural, not behavioral.** It covers the toolchain (`T-001`), shipped
  asset invariants (`T-022`), the layering guard (`T-005`), and the shell window including
  hostile stored geometry (`T-007`, `T-027`) — real tests, and they have caught real defects.
  Of §7's ten mandatory areas **ten** are now covered, recounted row by row on 2026-07-28
  (`T-058`): Layering (`T-005`), the State machine (`T-010`, checked against a transition
  relation transcribed independently from `ARCHITECTURE.md` §5), Path safety (`T-034`), Crash
  recovery, Migrations and the Settings freeze (`T-014`), Cancellation and Worker crash
  (`T-013`, with the process-tree half proved by `T-019`), Log redaction (`T-038`), and DRM
  (`T-012`, `T-017`, `T-057` — see the next bullet). **Recomputed from §7's rows rather than
  adjusted**, which is the discipline that caught this bullet's own error: it said "eight … Log
  redaction and DRM remain uncovered" for weeks after `T-038` closed one and while three tests
  already gated the other.

- **DRM is covered, and what it cannot cover is named** (`T-058`, 2026-07-28). §7 asks that
  `DRM_PROTECTED` is never auto-retried and has no bypass path. Four layers answer, and each
  claim below was mutation-checked before being recorded here:
  - `tests/unit/test_errors.py` — non-retryable and non-auto-retryable, asserted across the
    whole taxonomy rather than for one kind. *Mutation: dropping `DRM_PROTECTED` from
    `_NON_RETRYABLE` — killed.*
  - `tests/unit/test_ytdlp_adapter.py` — detection is structural, prose claiming DRM is
    explicitly not DRM, and the adapter's rule is compared against **yt-dlp's own** across five
    format shapes (`T-057`). *Mutations: reading prose; the old `all`/`'maybe'` fallback —
    killed.*
  - `tests/integration/test_worker.py` — the bypass half, by counting extraction calls: a DRM
    item fails after exactly one, because a second would be an attempt to route around the
    protection. *Mutation: letting the download proceed past detection — killed.*
  - `tests/ui/test_job_detail.py` — the UI half (`T-017`): a `DRM_PROTECTED` job offers no retry
    **at all**, and the affordance is driven by `is_retryable` rather than by a kind named in a
    widget. *Mutation: a literal kind comparison — killed by the `CANCELLED` case.*

  Two limits stand, neither closable here. **No recorded fixture can exist**: capturing one
  means probing a DRM service, which `REQ-EXCL-001` and `SEC-001` put out of scope, so
  `derived_drm_protected` is constructed and says so (§5). And yt-dlp writes `_has_drm` as
  `True` or `None` and never `False`, so its absence does not distinguish "not DRM" from "never
  processed" — harmless on every path this application has, and recorded in `T-057` rather than
  papered over.
- **Windows has automated coverage only** (`OPS-004`, narrowing `OPS-003`). The runner is a
  real desktop, so the application launch, menu keyboard reachability, and the UI Automation
  name/role contract are now gated. Still unverified there: whether rendering *looks* right,
  whether Narrator *sounds* coherent, native dialog foreground and file-association behavior,
  theming, and installer UX. Discharged by the pre-release session in §8 item 15.
- **Widget tab order is gated on Windows by a recorded manual run, not by CI** (`T-040`,
  `T-060`). Both `T-026` mutation classes were executed on a real Windows desktop on 2026-07-28
  and killed — 6, 6 and 2 failing tests respectively, against a 28-passing baseline — so the
  criterion is met and the previous "ungated" entry is no longer true. What is still missing is
  **repetition**: it ran once, on one machine, and nothing re-runs it on a push. A regression
  between now and the first runner execution would not be caught.
- **Which Windows configurations are gated is narrower than "Windows"** — now measured, and
  mostly closed (`T-066`…`T-070`, `docs/WINDOWS_VERIFICATION.md`). The first run on a machine
  that is not a runner failed 8 tests as an ordinary user and 4 as an elevated one; it now passes
  **1384 with 24 skipped**. What each difference was:
  **elevation** — four symlink tests needed a privilege nothing named, and now skip saying which
  (`T-070`); **`LongPathsEnabled=0`**, the Windows default — a path test died in its own setup
  (`T-067`); **the virtualenv** — `Scripts\python.exe` is a launcher, so every spawn sits a
  generation deeper than CI tested, and CI now installs the same way (`T-066`); **fonts** — Qt's
  offscreen font database was *empty*, so the whole offscreen UI suite measured layout against no
  fonts and passed (`T-068`).
  The runners remain elevated and long-path-enabled, so those two axes are still gated on one
  configuration only. **CI is one Windows configuration, and it is an unusual one.**
- **A two-control focus chain has no order to gate** (`T060-R2`, measured offscreen 2026-07-28
  and **confirmed on Windows the same day** — the reversal mutation survives there too). No state of
  the progress view offers more than two reachable controls, and a two-element cycle is its own
  reverse: from either control, Tab and Backtab both deliver the other, from any start. So
  reversing those two is unkillable by any keyboard observation — not a weak assertion, an
  unobservable property. Order is gated on the add-URL dialog, whose states offer nine to twelve.
  Worth knowing before writing a tab-order test for any small widget.
- **macOS is untested and unsupported** (`REQUIREMENTS.md` §3).
- **Network tests are inherently flaky** — sites change. Failures are triaged as "our bug" vs
  "site changed" before being acted on.
- **Concurrent-instance behavior is unverified** until the Phase 2 single-instance guard
  (`A-004`).
- **Long-running stability** (multi-hour queues, hundreds of jobs) has no automated coverage;
  currently manual only.

## 13. Test validity: does the test actually test anything?

A passing test proves nothing until you know it can fail. This section exists because the
project has now produced **eight** tests that passed while the thing they protected was removed
— each written deliberately, each believed to be the strong version, each wrong in a different
way. The last two were the *named evidence for two phase exit criteria*, which is worth sitting
with: they were the most-read tests in the project and nobody had watched either one fail.

**The rule: derive the expectation from the specification, never from the code under test.**

`ARCHITECTURE.md`, `REQUIREMENTS.md`, a task's acceptance criteria, or an external authority
like Microsoft's file-naming rules — transcribe from those by hand. The moment a test asks
production what to expect, it stops being a test and becomes a mirror.

### The eight, and what each one teaches

| # | Test | What it did | Why it passed anyway |
|---|---|---|---|
| `T010-R1` | Exhaustive state transitions | Asked `can_transition()` which pairs were illegal, then checked `apply()` rejected them | Both read one table, so it compared production with itself. An undocumented edge was silently reclassified as legal and skipped. |
| `T041-R2` | "Every model is covered" | Compared `valid_kwargs()` with a hand-written `MODELS` list | Two views of one hand-maintained set. A sixth model appeared in neither. |
| `T041-R6` | Hostile-payload sweep including `None` | Asserted `not isinstance(stored, dict \| list)` | `None` is neither, so the case passed unconditionally. The sweep grew a column that could never fail. |
| `T034-R4` | Reserved device names | Asserted the sanitized stem was not in production's `_RESERVED_NAMES` | Shrinking the production set shrank the expectation with it. |
| `T035-R3` | Reviewed public API | Filtered runtime attributes by `value.__module__` | A constant has no `__module__`, so it was dropped before comparison. Inspected values where it needed definitions. |
| `P2EXIT-R1` | No worker outlives application exit, at N=3 | Handed the application's whole process **tree** to the kill, then asked whether the workers in that tree were alive | The kill had just killed them. Removing the worker's own parent watchdog left it green — it proved the test helper reaps a tree, which was never in question. **Kill only the thing whose loss the product must notice.** |
| `P2EXIT-R2` | The UI stays inside its budget while three downloads run | Recorded the worst `processEvents()` pass and asserted only the latency | Deleting all three `start()` calls left it green: an idle event loop is very fast. A latency gate needs a **positive control** — proof the load it names was present while it measured. |
| `T093-R1` | Completion/history crash atomicity | Exited after the completion callback, then claimed a split mutation was killed by adding a second exit inside the mutation | The mutation supplied the event that distinguished the two shapes; splitting the transaction alone left the committed test passing. |

### What to do instead

- **Transcribe the expectation.** If `ARCHITECTURE.md` §5 has a state diagram, write the
  transition relation out by hand in the test. If Microsoft documents thirteen reserved device
  names, write thirteen. Duplication between spec and test is the point: the test fails when
  they diverge, which is the whole job.
- **Never compare two things you maintain by hand.** Derive one side from the module — parse
  it, enumerate its annotations, walk its dataclass fields — and transcribe the other.
- **Check the assertion can fail for the case you added.** A new parametrize entry that no
  assertion can reject is decoration.
- **Inspect definitions, not values,** when asking what a module exposes. `ast` sees a `def`, a
  `class` and an assignment; `vars()` sees objects whose metadata varies by type.
- **Prefer equalities to subsets** where the specification is finite. A subset check stays green
  when something is deleted, duplicated, or mis-typed.
- **A "this did not happen" timeout must be shorter than how long the subject would live anyway**
  (`P2EXIT-R1`). Waiting sixty seconds for three orphaned workers to die let them **finish their
  eight-second download and exit**, and reported that as correctly reaped. `wait_procs` and
  friends return as soon as the condition holds, so a generous timeout costs nothing when the
  product works and is the entire defect when it does not. Size the wait against the *subject's*
  lifetime, not against how slow the runner might be.
- **Give a load measurement a positive control** (`P2EXIT-R2`). Any gate of the form "X stays under
  a budget while Y is happening" needs a separate assertion that Y was happening — and one taken
  *inside* the measured window, not before it. Prefer a control that fails **synchronously**: a
  reservation the API creates before its worker thread runs catches a missing start in
  milliseconds, where waiting for a state to appear catches it at a deadline.

### Mutation is the evidence, and it has a trap

Before claiming a guard is covered, remove the guard and watch the suite fail. Record the count
in the task. `AGENTS.md` §9 requires this of every correction batch.

Four things that have bitten here:

- **The mutation changes production; the test and its fault scenario stay fixed.** A mutation that
  also edits the test, adds a crash point, changes an input, or supplies another distinguishing
  event is not evidence that the committed test gates the guard. Apply the smallest production
  weakening named by the acceptance criterion, change nothing else, and run the unmodified test.
  `T093-R1` split one transaction into two, but the claimed mutation also inserted its own
  `os._exit` between them; that exit—not the test—did the discriminating.
- **Assert that your mutation applied.** A scripted `str.replace` that matches nothing edits
  nothing and the suite passes — reported as a survivor, indistinguishable from a real one. This
  happened in `T-126`: `ruff format` had reflowed the target expression onto one line, so two
  successive "survivors" were the same non-edit. `assert new != original` before writing the file,
  every time. The `T-013` note below is the same failure through a different mechanism.
- **A test can pass by coincidence rather than by checking.** Also `T-126`: matching a request to
  its preset on `format_selector` alone survived, because the test used `Audio only (MP3)` — and
  four of the five built-ins share a selector with another, so selector-only matching returns
  whichever is defined *first*. Using the second of a colliding pair killed the mutation
  immediately. **When a lookup can collide, test with the case that collides**; the first entry is
  the one value that cannot tell the two implementations apart.
- **A size-preserving mutation may not run at all** (`T-013`). Python validates a cached `.pyc`
  against the source's *size* and its mtime **in whole seconds**. Swapping two adjacent lines —
  the natural mutation for "is this written before that?" — changes neither, so a batch that
  mutates, runs, and restores within one second re-runs the *unmutated* bytecode and reports the
  guard as uncovered. Two real guards were nearly rewritten on that evidence. Clear
  `__pycache__` and set `PYTHONDONTWRITEBYTECODE=1` for any automated mutation run, and treat a
  "survivor" whose mutation changed neither size nor second as unmeasured rather than uncovered.
- **Mutate content, not just shape.** Adding a new `JobStatus` broke the transition table's
  lookups and failed loudly — which felt like proof, but adding an *undocumented edge* to the
  existing table changed nothing. The shape mutation was easy and uninformative; the content
  mutation was the real test.
- **A surviving mutation means one of two things, and choosing wrong causes bugs.** Either the
  code is genuinely redundant, or a test is missing. Assume redundancy and you delete a live
  guard: `sanitize_component` lost a `rstrip` that way, which let `"CON "` through as an
  unopenable Windows filename and broke idempotence. **Default to "a test is missing"** and
  prove redundancy before acting on it.

### Where this is enforced

Nowhere automatically — this is a discipline, not a gate. §7's mandatory areas are the places
it matters most, and their tests should carry a comment naming the specification they were
transcribed from.
