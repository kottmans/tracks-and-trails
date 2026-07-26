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

**Start here:** `T-010` — the domain models, state machine and error taxonomy that every
other Phase 1 task imports. `T-011` and `T-012` are planned in full and become Ready as their
dependency merges; `T-013`–`T-019` and `T-034` are planned in full behind them.

Phase 0 is built and reviewed, but has **not formally exited**: one criterion needs a Windows
machine (`OPS-003`). That does not block Phase 1. `T-026` awaits a maintainer decision on
`OPS-004`; `T-033` becomes Ready once `T-012` merges.

---

## Ready

### T-010 — Domain models, job state machine, and error taxonomy

**Status:** Ready
**Owner:** Implementer
**Priority:** High — every other Phase 1 task imports this
**Phase:** Phase 1
**Depends on:** `T-001`
**Relevant context:** `ARCHITECTURE.md` §4 (layers), §5 (data ownership), §7 (error taxonomy),
§8 (settings propagation); `REQ-005`, `REQ-012`, `REQ-015`, `REQ-018`, `REQ-028`, `NFR-006`,
`REQ-EXCL-001`; `ai/TESTING.md` §7 (State machine)
**Affected surfaces:** `core/models.py`, `core/job_state.py`, `core/errors.py`,
`tests/unit/`
**Risk:** Medium — cheap to write, expensive to change once four other modules import it
**Review base:** `ce7cec4`

#### Scope

The pure-domain foundation of the vertical slice. No Qt, no yt-dlp, no I/O beyond the standard
library — `core/` is the layer that stays testable headless and gets reused by both the GUI
process and the spawned worker.

Three modules, deliberately together because they are one design and splitting them would
mean three reviews of the same decisions:

1. **`models.py`** — `Job`, `JobStatus`, `MediaInfo`, `FormatInfo`, `Preset`,
   `DownloadRequest`. Plain dataclasses.
2. **`job_state.py`** — the legal-transition table and the single function that applies a
   transition. `ai/TESTING.md` §7 requires that every illegal transition raises; this is where
   that guarantee lives.
3. **`errors.py`** — the `ARCHITECTURE.md` §7 taxonomy as an enum, plus a `classify()` seam.
   The module *defines* the taxonomy and how a classified failure is carried; `T-012` supplies
   the yt-dlp-specific mapping into it, because that is the only place that may import
   `yt_dlp` (§6).

`errors.py` is pulled forward into this task rather than left to `T-012` for two reasons: it
is pure `core/` code, and `T-012` needs to classify from its first line, so writing it there
would put a `core/` design decision inside a task reviewed for its yt-dlp handling.

Two properties are load-bearing and easy to lose:

- **Everything here crosses a process boundary** (`ARC-002`). Every type must be picklable:
  plain dataclasses and enums, no lambdas, no open handles, no `functools.partial`.
- **`DownloadRequest` is frozen at job-creation time** (`ARCHITECTURE.md` §8). A running job
  never observes a mid-flight settings change, which is what makes the worker's behavior
  reproducible from the request alone.

#### Acceptance criteria

- Every model round-trips through `pickle` unchanged, asserted per type — this is what makes
  `T-011`'s IPC possible, and it fails loudly the day someone adds an unpicklable field
- **Each model's required fields and invariants are pinned**, not merely its picklability: a
  `Job` without an id, url or status fails construction; `MediaInfo` and `FormatInfo` declare
  the fields `ARCHITECTURE.md` §5 names. Empty dataclasses would satisfy a pickle test alone,
  which is exactly the vacuous pass to avoid
- `DownloadRequest` is immutable; attempting to mutate a field raises
- The state machine accepts every transition in the legal table and **raises on every
  transition outside it** — asserted exhaustively over the full `JobStatus × JobStatus`
  product, not over a sampled list, so a newly added status cannot silently acquire
  permissive behavior
- Adding a `JobStatus` member without adding its transitions fails the suite
- `CANCELLED` is reachable from every non-terminal state; no state is reachable *from* a
  terminal state
- The taxonomy covers exactly the ten kinds in `ARCHITECTURE.md` §7 — asserted against that
  list, so the table and the code cannot drift apart
- A classified failure preserves the original message verbatim alongside the classification
  (`NFR-006`); the classification is additive and never replaces the text
- `DRM_PROTECTED` and `CANCELLED` are marked non-retryable, and `NETWORK` is the only kind
  marked auto-retryable (`REQ-018`, `REQ-EXCL-001`)
- The layering test still passes: no Qt, no `yt_dlp` anywhere in `core/`

#### Out of scope

- Any yt-dlp exception mapping — `T-012`, and it is the only place that may import `yt_dlp`
- Persistence of any of these types — `T-014` owns the schema
- Preset *content* and selector translation — `T-015`; this task defines the `Preset` shape
  only
- Retry scheduling and backoff policy — Phase 2, though the retryable flag is defined here

---

## Proposed — Phase 0

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

## Proposed — Phase 1

### T-011 — IPC message contract

**Status:** Proposed — Ready once `T-010` merges
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `ARCHITECTURE.md` §3 (process model), §6 (yt-dlp boundary), §7;
`ARC-002`, `NFR-008`, `REQ-014`, `REQ-028`
**Affected surfaces:** `downloader/protocol.py`, `tests/unit/`
**Risk:** Medium — this is the parent/child contract; a gap here shows up as a hang, not an
exception
**Review base:** the `T-010` merge commit

#### Scope

The typed messages that cross the `multiprocessing.Queue` between the GUI process and a
worker, and nothing else. One module, no behavior beyond construction and validation.

Cover the message kinds the vertical slice needs: a probe result, progress updates carrying
the stages `REQ-014` names (probing, downloading video, downloading audio, merging,
post-processing), a terminal success carrying the final path and byte count, and a terminal
failure carrying a `core.errors` classification plus the verbatim message.

The rule this module exists to enforce: **a raw yt-dlp `info_dict` never crosses the
boundary** (`ARCHITECTURE.md` §3). The dict's shape belongs to yt-dlp and changes without
notice (`NFR-008`); the parent must only ever see declared types projected by
`ytdlp_adapter.py`.

**Shutdown and identity are part of the contract, not details left to `T-013`.** The earlier
draft specified only the message payloads, which leaves three ways to hang or lie:

- **Every message carries a job ID.** Without it the parent cannot attribute a message, and
  "exactly one terminal message per job" is unenforceable.
- **A sentinel terminates the stream.** `ResultPump` does a blocking `Queue.get()`; with no
  sentinel, shutdown depends on a timeout or on killing a thread mid-read. The protocol
  defines the sentinel and the guarantee that it is the last thing sent.
- **Terminal-once is a receiver obligation, stated here.** Message classes alone cannot
  prevent a second terminal message being sent — an earlier draft claimed they could. The
  protocol therefore *specifies* that a job has exactly one terminal outcome and that the
  receiver must enforce it by job ID; `T-013` implements the enforcement.

**No protocol versioning.** Both ends ship in the same artifact and are always the same build,
even when the user updates yt-dlp underneath (`OPS-002`) — that changes the *engine*, not the
contract. Recording this now so nobody later adds negotiation machinery for a skew that cannot
occur.

#### Acceptance criteria

- Every message type round-trips through `pickle` unchanged
- **Every message carries a job ID**, and constructing one without it fails
- A declared `is_terminal` predicate identifies exactly the success and failure types, so the
  receiver's terminal-once rule can be written against the protocol rather than a hardcoded
  list that drifts as types are added
- A sentinel type exists, is picklable, and is documented as the last item on the queue
- Progress messages carry every stage named in `REQ-014`, asserted against that list
- A terminal failure carries both a `core.errors` kind **and** the original text; neither is
  optional, and a message with a classification but no text fails construction (`NFR-006`)
- A **validation helper** rejects anything that is not a declared message — including a bare
  `dict` — and it lives here so both ends share one definition of "valid". This task tests the
  helper directly; `T-013` applies it on receipt. The earlier draft promised rejection "at a
  seam" while declaring both seams out of scope, which was unimplementable
- `protocol.py` imports no Qt and no `yt_dlp`, enforced by the layering test
- Every message type is exercised by at least one test; an unexercised type fails the suite

#### Out of scope

- Sending or receiving anything — `T-012` (child side) and `T-013` (parent side). This task
  defines and tests the validator; it does not call it across a real queue
- Enforcing terminal-once — specified here, implemented and tested in `T-013`
- Queue lifetime, draining, and backpressure — `T-013`
- Any type that only Phase 2's queue needs

---

### T-035 — Resolve the yt-dlp and ffmpeg environment

**Status:** Proposed — Ready once `T-011` merges
**Owner:** Implementer
**Priority:** High — `T-012` cannot honour `OPS-002` without it, and `REQ-024` is owned by
nothing else
**Phase:** Phase 1
**Depends on:** `T-011`
**Relevant context:** `ARCHITECTURE.md` §6 (resolution order), §4; `OPS-002`, `OPS-001`,
`REQ-024`, `REQ-025`, `NFR-007`
**Affected surfaces:** `downloader/environment.py`, `tests/unit/`, `tests/integration/`
**Risk:** Medium — a wrong answer here is misattributed to yt-dlp or to the site
**Review base:** the `T-011` merge commit

#### Scope

**Filed during Phase 1 planning: `downloader/environment.py` was claimed by no task, and
`REQ-024` by nothing at all.** `ARCHITECTURE.md` §4 assigns this module "locating yt-dlp and
ffmpeg; version reporting; update", and `ARCHITECTURE.md` §6 puts yt-dlp resolution at *worker
start* — so `T-012` needs it from its first line, and without it the worker would import
whatever yt-dlp happens to be on `sys.path`, which is precisely what `OPS-002` rejects.

Two jobs:

1. **Locate yt-dlp candidates** per `OPS-002` — and *only* locate them. This module returns
   an ordered list of candidate paths: the user-managed copy in
   `user_data_dir/tracksandtrails/ytdlp/` first, then the bundled baseline. It reports what
   exists on disk and answers nothing about whether a candidate works.

   **It must not import yt-dlp**, and the earlier draft of this task required exactly that —
   "fail loudly if the user copy does not import cleanly" and "report the resolved version"
   are both unimplementable without importing it. `ARCHITECTURE.md` §6 permits that import in
   `worker.py` and `ytdlp_adapter.py` alone, and `T-005`'s layering guard enforces it after
   being deliberately mutation-tested. Reaching for `importlib` to slip past the guard would
   be worse than the violation, because it defeats a check the project spent two review
   rounds hardening.

   So the split is: **`environment.py` locates, `worker.py` imports.** `worker.py` walks the
   candidate list, prepends the first entry to `sys.path`, imports, and on `ImportError` falls
   back to the next candidate — reporting which one it used and why any earlier candidate was
   rejected (`ARCHITECTURE.md` §6: fail loudly, never silently ignore an override). The
   version comes from the imported module, so only the importer can report it (`REQ-025`).

   If a third module ever genuinely needs to import yt-dlp, that is an architecture change:
   amend `ARCHITECTURE.md` §6 and the layering rule deliberately, in a reviewed change.
2. **Detect ffmpeg** at startup and report which features are unavailable without it
   (`REQ-024`, `OPS-001`) — rather than failing at merge time, after a download has already
   consumed the user's bandwidth.

Resolution runs in the worker, so this module must not import Qt.

#### Acceptance criteria

- With no user copy present, the candidate list contains the baseline alone
- With a user copy present, it is ordered ahead of the baseline
- A candidate directory that exists but is empty, or contains no `yt_dlp` package, is still
  *listed* — deciding it is unusable requires importing it, which is `worker.py`'s job
- `environment.py` does not import `yt_dlp`, asserted by the layering test **and** by a test
  that the module can be imported with `yt_dlp` absent from `sys.modules` entirely
- **Ownership boundary asserted:** a test confirms `environment.py` exposes no version and no
  usability verdict, so the split cannot erode back into this module by accident
- ffmpeg presence and absence both yield a correct feature report; the absent case names what
  will not work (`REQ-024`)
- Detection never executes a shell (`ARCHITECTURE.md` §9) and never blocks the GUI thread
- No user path, cookie, or credential reaches a log line from this module (`NFR-007`)
- `environment.py` imports no Qt

#### Out of scope

- Downloading and extracting the yt-dlp wheel — Phase 4; this task resolves what is already
  present
- Bundling either dependency into the frozen artifact — `T-033` for yt-dlp, Phase 5 for ffmpeg
- Any UI for showing the version or the ffmpeg state — `T-016`/`T-017` consume the report

---

### T-012 — yt-dlp in a spawned worker

**Status:** Proposed — Ready once **all three** of `T-011`, `T-034` and `T-035` merge
**Owner:** Implementer
**Priority:** High — this is where `ARC-002` stops being a design
**Phase:** Phase 1
**Depends on:** `T-011`, `T-034` (no file write without a validated path), `T-035` (no
yt-dlp without a candidate list)
**Relevant context:** `ARCHITECTURE.md` §3, §6, §7; `ARC-002`, `OPS-002`, `NFR-008`,
`REQ-002`, `REQ-005`, `REQ-025`, `REQ-028`, `NFR-006`; `ai/TESTING.md` §5 (fixtures)
**Affected surfaces:** `downloader/worker.py`, `downloader/ytdlp_adapter.py`,
`tests/unit/`, `tests/integration/`, `tests/fixtures/infodicts/`
**Risk:** **High** — the first code to run in a spawned process, the only code that may import
`yt_dlp`, and the seam every future upstream change lands on
**Review base:** the last of the `T-011`, `T-034` and `T-035` merge commits — *not* `T-011`
alone, which an earlier draft said while already depending on the other two

#### Scope

Two modules, and they are the **only** two in the project permitted to `import yt_dlp`
(`ARCHITECTURE.md` §6, enforced by `T-005`'s layering test):

1. **`ytdlp_adapter.py`** — builds the yt-dlp options dict from a `DownloadRequest`, projects
   `info_dict` into `MediaInfo`/`FormatInfo`, and maps yt-dlp exceptions onto the `core.errors`
   taxonomy. Pure translation: no process handling, no I/O of its own.
2. **`worker.py`** — the child-process entry point. Import-safe under `spawn` (no side effects
   at import time), resolves yt-dlp per `OPS-002`, runs one probe or one download, converts
   `progress_hooks` and `postprocessor_hooks` into `T-011` messages, and exits.

Neither may import Qt: the worker runs with no display and must inherit no Qt (`ARC-002`).

**This task also owns yt-dlp's import and template rendering**, both moved here from
neighbouring tasks after review:

- **Importing yt-dlp and reporting its version.** `T-035` locates candidates; `worker.py`
  walks them, prepends to `sys.path`, imports, falls back on `ImportError`, and reports which
  candidate won and why any earlier one lost (`OPS-002`, `REQ-025`). Only the importer can
  read the version, and only these two modules may import at all (§6).
- **Output-template rendering and the `REQ-011` preview.** Rendering uses yt-dlp's own
  template mechanism (`ARCHITECTURE.md` §9), so it cannot live in `core/`. The rendered result
  is then passed through `T-034`'s sanitizing and containment check before anything is
  written.

**Fixtures.** `T-018` broadens fixture coverage, but this task cannot be tested without at
least one recorded `info_dict`, so it captures the first ones itself — recording the yt-dlp
version and capture date alongside each, per `ai/TESTING.md` §5. Adapter projection is tested
against recorded fixtures, never against the live network.

**`T-012` stays whole — settled, do not re-open.** Splitting the adapter from the worker was
considered twice and rejected by the maintainer on 2026-07-25. The argument for splitting is
that they fail differently: translation bugs versus process bugs. The argument against, which
won, is that the adapter has no meaningful test surface without a worker to run it in, so a
split would produce one task that cannot be verified and a second that carries all the risk
anyway. Review it as one unit and expect it to be the largest review in the phase.

**`T-033` stays separate, deliberately.** This task makes the worker import `yt_dlp` from
source; `T-033` makes the *frozen artifact* actually contain it. Folding them together would
mean one review covering both a domain seam and a packaging change, and would let a green
source-mode suite imply a working release. `T-012` therefore claims nothing about the frozen
build, and `T-033` becomes Ready the moment this merges.

#### Acceptance criteria

- A probe of a recorded fixture yields a `MediaInfo` with title, uploader, duration and
  format list, asserted field by field
- Every taxonomy kind in `ARCHITECTURE.md` §7 that yt-dlp can raise has a mapping, asserted
  against the §7 table; an unmapped exception classifies as the explicit unknown case rather
  than crashing the worker
- The extractor's own message survives classification verbatim (`REQ-005`, `NFR-006`) —
  asserted by string equality against the fixture, not by substring
- **`DRM_PROTECTED` is classified as non-retryable and no alternative extraction is
  attempted** (`REQ-EXCL-001`, `SEC-001`). Asserted at *this* level as a property of the
  classification and of the adapter's behavior — asserting "is never retried" here would be
  vacuous, because no retry mechanism exists until Phase 2, which is where that assertion
  belongs
- The worker runs headless: a test spawns it with no display and it completes (`ARC-002`)
- The worker module imports cleanly under `spawn` with no side effects — asserted by importing
  it in a fresh interpreter and observing no work performed
- yt-dlp's resolved version is reported through a message (`REQ-025`), read from the imported
  module rather than from a recorded string that could drift
- With a **broken** user copy present — a path that exists holding an unimportable package —
  the worker falls back to the baseline and **says so**; a test asserts both the fallback and
  that it was not silent (`ARCHITECTURE.md` §6)
- A rendered output template is passed through `T-034`'s containment check before use; a
  template that renders outside the target directory is rejected, not written
- The `REQ-011` preview equals the path actually used — asserted by rendering, previewing,
  downloading to a temporary directory, and comparing the real result
- Changing a projected `info_dict` key in a fixture fails the projection test — the fixture is
  a contract, not a sample
- The layering test still passes, and `yt_dlp` appears in exactly these two modules

#### Out of scope

- The process pool, scheduling, and Qt signals — `T-013`. In particular **`WORKER_CRASH`
  cannot be asserted here**: it is produced by the parent observing a child's exit, and there
  is no parent until `T-013`. An earlier draft claimed it as a criterion of this task
- Bundling yt-dlp into the frozen artifact — `T-033`
- Broadening fixture coverage across sites — `T-018`
- Cancellation and crash *integration* tests — `T-019`; this task covers the worker side, and
  the 2-second cancellation criterion is measured there
- The in-app yt-dlp updater — Phase 4; this task only *resolves* what `OPS-002` describes

---

Every Phase 1 task is now planned in full. `T-034` was filed during planning: output-path
rendering and filename safety belonged to no task, despite being a `ai/TESTING.md` §7
mandatory area that `T-012` depends on.

**Four requirements are cited in Phase 1 but only partly discharged here**, and are listed so
raw citation counts are not mistaken for coverage:

| REQ | Cited by | Discharged in Phase 1? |
|---|---|---|
| `REQ-008` (select format IDs from the table) | `T-015` out-of-scope | **No.** The format table is Phase 3. `T-015` only notes the boundary. |
| `REQ-021` (open / reveal a completed file) | `T-017` out-of-scope | **No.** Phase 2. |
| `REQ-025` (report the yt-dlp version, update it in-app) | `T-012`, `T-035` | **Partly.** Reporting the resolved version, yes. Updating it in-app is Phase 4 (`OPS-002`). |
| `REQ-026` (cookies for entitled content) | `T-014`, `T-038` | **Partly.** Only the promise that cookie material never reaches the database or a log. Cookie *input* is Phase 3. |

**Five tasks were filed during planning, not created as new work.** `T-034` (path safety),
`T-035` (environment resolution), `T-036` (application composition), `T-037` (end-to-end
download and restart proof) and `T-038` (logging and redaction) are all `ARCHITECTURE.md` or
`IMPLEMENTATION_PLAN.md` responsibilities that the original ten-row outline did not own. Two
were found while writing dependencies, three by review. Without `T-036` and `T-037` in
particular, every task could pass while the application still opened an empty window and no
download was ever proven to complete.

Dependency order: `T-010`; then `T-011`, `T-014`, `T-015`, `T-034` in parallel; then `T-035`
and `T-038`; then `T-012`; then `T-013`; then `T-016`, `T-017`, `T-018`, `T-019`; then `T-036`;
then `T-037`.

### T-034 — Filename safety and output-path containment

**Status:** Proposed — Ready once `T-010` merges
**Owner:** Implementer
**Priority:** **High** — a `ai/TESTING.md` §7 mandatory area, and `T-012` cannot write a file
without it
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `ARCHITECTURE.md` §8 (Filename safety), §9 (Security boundaries);
`REQ-011`, `NFR-004`; `ai/TESTING.md` §7 (Path safety)
**Affected surfaces:** `core/paths.py`, `tests/unit/`
**Risk:** **High** — the failure mode is writing a file outside the directory the user chose,
driven by a title an attacker controls
**Review base:** the `T-010` merge commit

#### Scope

**Filed during Phase 1 planning: this was assigned to no task.** `ARCHITECTURE.md` §8 requires
every output path to pass through `core/paths.py`, `ai/TESTING.md` §7 lists path safety as
mandatory coverage, and `T-012` writes files — so the slice cannot be built without it, and
nothing in the original outline owned it.

**Corrected after review: this task no longer renders output templates.** The earlier draft
put yt-dlp-compatible template rendering in `core/paths.py`, which cannot work —
`ARCHITECTURE.md` §9 says rendering uses *yt-dlp's own template mechanism*, and `core/` may not
import `yt_dlp` (§6). Reimplementing yt-dlp's template language in `core/` would be a second
implementation of someone else's syntax, guaranteed to drift.

The responsibility splits:

- **`core/paths.py` (this task)** — pure, yt-dlp-free: platform directory resolution, filename
  sanitizing, and the containment check. Given a candidate path and a target directory, it
  answers *is this safe and legal on both platforms*, and returns a sanitized path.
- **`ytdlp_adapter.py` (`T-012`)** — passes the output template to yt-dlp, which renders it,
  then runs the result through this module before it is used. Rendering stays with the only
  code allowed to know yt-dlp's syntax.

Sanitizing enforces the **intersection** of Linux and Windows rules: reserved device names
(`CON`, `NUL`, `LPT1`…), characters illegal on NTFS, trailing dots and spaces, and path-length
limits.

The security property, stated plainly: **a title-derived filename must never escape the
configured output directory.** Titles come from media sites and are attacker-influenced data.
After rendering, `..` and absolute components are rejected, and the result is verified to be
contained within the target directory.

#### Acceptance criteria

- A rendered path is always inside the configured output directory. Asserted against titles
  containing `../`, absolute paths, drive letters, UNC prefixes, NUL bytes, and separators for
  the *other* platform — each must be neutralized, not merely escaped
- Windows-illegal names are sanitized **on both platforms**, not only on Windows
  (`ai/TESTING.md` §7) — a name legal on Linux that becomes illegal when the file syncs to
  Windows is still a defect
- Reserved device names are handled including with extensions (`CON.mp4`), which is the case
  usually missed
- Over-long paths are shortened without losing the extension or colliding with a neighbouring
  file
- Sanitizing is deterministic and idempotent: sanitizing an already-sanitized path returns it
  unchanged, so passing a path through twice cannot corrupt it
- The `REQ-011` live preview is **not** this task's — it needs a rendered template and
  therefore belongs with `T-012`, which owns rendering. This task supplies the sanitizing step
  the preview must pass through, and `T-012` asserts preview-equals-actual
- `core/paths.py` imports no Qt and no `yt_dlp`

#### Out of scope

- **Output-template rendering** — `T-012`, because it uses yt-dlp's own mechanism
- The `REQ-011` live preview — `T-012`, for the same reason
- The settings UI for choosing a template — Phase 4
- Collision policy when the target file already exists — Phase 2 alongside resume
- Any actual file writing; this module computes and validates paths

---

### T-013 — Download manager and result pump

**Status:** Proposed — Ready once `T-012` merges
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 1
**Depends on:** `T-012`, `T-014`
**Relevant context:** `ARCHITECTURE.md` §3, §8 (threading); `ARC-002`, `REQ-014`, `REQ-015`,
`REQ-018`, `REQ-028`, `NFR-001`, `NFR-003`; `ai/TESTING.md` §7 (Cancellation, Worker crash)
**Affected surfaces:** `downloader/manager.py`, `downloader/result_pump.py`,
`tests/integration/`
**Risk:** **High** — owns process lifetime and the only thread in the application. Both of its
failure modes are silent: an orphaned worker, and a Qt object touched off the GUI thread.
**Review base:** the `T-012` merge commit

#### Scope

The GUI-process half of `ARC-002`. A pool of exactly one for Phase 1 — concurrency is Phase 2,
and building the pool for N now would mean designing scheduling policy with no queue to test
it against.

- **`manager.py`** — starts a worker per job, tracks its lifetime, cancels it, reaps it, and
  turns a worker that died without a terminal message into `WORKER_CRASH` with its exit code
  (`REQ-028`).
- **`result_pump.py`** — a `QThread` doing a blocking read on the result queue and re-emitting
  each `T-011` message as a Qt signal. It is the **only** bridge from worker to GUI, and it
  communicates *only* by signal emission (`ARCHITECTURE.md` §8).

`manager.py` is the one `downloader/` module allowed to import Qt, because it emits signals.
`worker.py` still may not.

**Persistence is injected, not imported.** `ARCHITECTURE.md` §3 shows `DownloadManager` owning
a repository, and Phase 1 promises durable transitions — so the dependency on `T-014` stays.
But the manager must not know SQLite exists: it takes a **repository protocol**, is unit-tested
against a fake implementation, and receives the concrete `JobRepository` from `app.py` at
composition time (`T-036`). One integration test exercises the real repository. A widget is the
wrong place to create this boundary; `T-017` consumes durable state, it does not construct the
persistence seam.

Cancellation is the sharp end (`REQ-015`): try the cooperative path first — `DownloadCancelled`
raised from a progress hook, so partial files are left in a known state — then `terminate()`,
then `kill()` on a timeout. The 2-second budget is measured against a **real in-flight
download**, not a sleeping worker; `T-002`'s probe only ever proved the sleeping case and said
so.

#### Acceptance criteria

- Cancel terminates a **real in-flight download** within 2 seconds and leaves no orphan
  process, asserted programmatically rather than by watching a process list
  (`REQ-015`, `ai/TESTING.md` §7)
- `SIGKILL`/`TerminateProcess` of a worker yields `WORKER_CRASH` with the exit code recorded,
  and the application stays responsive (`REQ-028`)
- A worker that exits 0 without sending a terminal message is also `WORKER_CRASH`, not a
  silent success — the case that looks like nothing went wrong
- No orphan survives application exit, including a job cancelled during shutdown
- The GUI thread is never blocked: an assertion that no manager or pump call performs a
  blocking wait on the GUI thread (`NFR-001`)
- **No Qt object is touched off the GUI thread.** The pump's only interaction with the GUI is
  signal emission; a test asserts messages arrive on the GUI thread, since this is the
  standing risk `ai/REVIEWS.md` names and it produces intermittent failures rather than
  errors
- Every `T-011` message type is routed to a signal; an unhandled type raises rather than being
  dropped
- The manager is constructed with a fake repository in unit tests and never imports
  `persistence` directly — asserted, so the injected boundary cannot quietly collapse
- Every state transition the manager performs is persisted before the corresponding signal is
  emitted, so a crash between the two cannot leave the UI ahead of the database
- **Shutdown is deterministic:** the pump exits on a protocol sentinel rather than on a
  timeout, and a test asserts no thread is left blocked in `Queue.get()` after shutdown
- **The terminal-message/exit race is handled:** a worker that sends a terminal message and
  then exits non-zero is reported by its message, not as `WORKER_CRASH`. A test forces that
  ordering, because the naive implementation checks the exit code first and manufactures a
  crash from a successful download
- Killing the parent does not leave the child running

#### Out of scope

- More than one concurrent job, scheduling, priority, pause/resume — Phase 2
- Retry policy and backoff — Phase 2; this task reports failures, it does not re-run them
- Any widget — `T-016`, `T-017`

---

### T-014 — Persistence: schema, migrations, and the job repository

**Status:** Proposed — Ready once `T-010` merges
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `ARCHITECTURE.md` §5 (core entities); `DAT-001`, `REQ-012`, `REQ-018`,
`NFR-003`, `NFR-004`; `ai/TESTING.md` §7 (Crash recovery, Migrations)
**Affected surfaces:** `persistence/schema.sql`, `persistence/migrations/`,
`persistence/db.py`, `persistence/repositories.py`, `tests/unit/`, `tests/integration/`
**Risk:** **High** — the one component whose failure mode is *lost user data*, and the only
one where a bug can persist across restarts
**Review base:** the `T-010` merge commit

#### Scope

SQLite in WAL mode at `user_data_dir/tracksandtrails/library.sqlite3` (`DAT-001`,
`ARCHITECTURE.md` §5). The schema for `Job` and `HistoryEntry` as §5 defines them, a forward-only
migration runner, and `JobRepository`.

Two properties are the entire point:

- **The queue survives an unclean kill** (`REQ-012`, `NFR-003`). WAL is chosen for exactly
  this; the test must actually kill the process, not close the connection politely.
- **Startup recovers jobs stranded in `RUNNING`.** A job cannot be running if the application
  just started, so it is recovered to a retryable state rather than left lying about its own
  status (`ai/TESTING.md` §7).

`DownloadRequest` is persisted *with* the job, so a retry after a settings change reproduces
the original request rather than current defaults (`ARCHITECTURE.md` §5, §8).

#### Acceptance criteria

- A hard kill (`SIGKILL`) mid-write leaves the database readable with no partial row, verified
  by killing a real process rather than simulating it
- Jobs found in `RUNNING` at startup are recovered to a retryable state, and the recovery is
  recorded so it is visible rather than silent
- **Every migration runs forward from every prior schema version with data intact**, asserted
  by building a database at each historical version and migrating it — not just from the
  latest (`ai/TESTING.md` §7). With one version today, the harness must still exist, because
  it is unwritable later once several versions exist
- A schema change without a migration fails the suite
- A persisted `DownloadRequest` round-trips exactly; a retry uses the stored request, proven
  by changing the defaults between store and retry (`ARCHITECTURE.md` §8)
- Queue order survives a restart (`REQ-012`)
- No cookie path, cookie content, proxy credential, or token-like query parameter is ever
  written to the database (`REQ-026`, `NFR-007`) — asserted against a request containing all
  four
- The database lives under `platformdirs`, never beside the installed application (`NFR-004`)

#### Out of scope

- History pruning, search, and export — Phase 3
- Concurrency beyond a single writer — Phase 2 brings the second
- Settings storage, which is TOML and not this store (`DAT-001`)

---

### T-015 — Built-in presets and selector translation

**Status:** Proposed — Ready once `T-010` merges
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-010`
**Relevant context:** `REQ-006`, `REQ-008`, `REQ-009`; `ARCHITECTURE.md` §4, §6
**Affected surfaces:** `core/presets.py`, `tests/unit/`
**Risk:** Low — pure translation, fully unit-testable
**Review base:** the `T-010` merge commit

#### Scope

The named presets `REQ-006` requires, at minimum: best video ≤1080p (MP4), best video
available, audio only (MP3), audio only (best/original), and video with embedded subtitles.
Plus the translation from a `Preset` to the fields of a `DownloadRequest`.

**This module produces data, not yt-dlp calls.** It emits format selector strings and option
values; `ytdlp_adapter.py` turns those into a yt-dlp options dict. That split is what keeps
`core/` free of `yt_dlp` (`ARCHITECTURE.md` §6) and is enforced by the layering test.

`REQ-009` requires the **effective selector to be visible for every preset**, so a user can
learn the syntax and then write their own. That means the selector string is a first-class
output of translation, not an internal detail.

#### Acceptance criteria

- Every preset named in `REQ-006` exists and translates to a `DownloadRequest`
- Each preset exposes its effective selector string, and the string is what translation
  actually uses — not a separately maintained label that could drift (`REQ-009`)
- A raw user-supplied selector passes through unchanged, including strings the project does
  not understand — the escape hatch is not validated into uselessness (`REQ-009`)
- **The validation boundary is explicit**, because "accept anything unknown" and "reject
  malformed" otherwise contradict each other. Only two structural conditions are rejected, and
  only for **built-in presets**: an empty selector, and one that is not a string. A
  user-supplied selector is never rejected for content — yt-dlp is the judge of whether it
  resolves, and a test asserts a deliberately nonsensical user selector survives untouched
- `core/presets.py` imports no `yt_dlp` and no Qt

#### Out of scope

- Custom user-defined presets and their TOML persistence — Phase 4
- The format table and per-format selection UI — `REQ-003`/`REQ-008`, Phase 3
- Whether a selector actually resolves against a real site — that is yt-dlp's judgment

---

### T-016 — Add-URL dialog with probe results

**Status:** Proposed — Ready once `T-013` and `T-015` merge
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-013`, `T-015`
**Relevant context:** `REQ-001`, `REQ-002`, `REQ-005`, `NFR-001`, `NFR-005`, `NFR-006`
**Affected surfaces:** `ui/add_dialog.py`, `ui/main_window.py`, `tests/ui/`
**Risk:** Medium — the first widget that talks to the manager, and the first place a blocking
call would freeze the application
**Review base:** the later of the `T-013` and `T-015` merge commits

#### Scope

Paste or type a URL, probe it, see what it is, choose a preset, and queue it. Probing runs in
a worker process — **never inline** — because probe latency is unbounded and blocking the GUI
thread on it is exactly what `NFR-001` forbids (`ARCHITECTURE.md` §8).

Show what `REQ-002` names: title, uploader, duration, thumbnail, and whether the URL is a
single item or a playlist. On failure, show the extractor's own message **verbatim**
(`REQ-005`, `NFR-006`) — not a paraphrase, and not a generic "could not fetch".

#### Acceptance criteria

- A probe of a fixture-backed URL populates **every field `REQ-002` names** — title,
  uploader, duration, a thumbnail decoded to a real pixmap rather than a URL, and whether the
  URL is a single item or a playlist — asserted field by field, since "populates the dialog"
  would pass with four of five missing
- The GUI thread is never blocked, and a test asserts the dialog stays responsive while a
  probe is outstanding (`NFR-001`)
- An unsupported URL shows the extractor's message character-for-character, asserted by
  equality against the fixture (`REQ-005`, `NFR-006`)
- A probe that never returns can be cancelled and leaves no worker behind
- Multi-line paste queues each URL as a separate job (`REQ-001`)
- Full keyboard operation: every control reachable and actuable by keyboard, with a
  deliberate tab order asserted, and an accessible name on every control (`NFR-005`)
- No information is conveyed by color alone (`NFR-005`)
- Queuing a job persists it before the dialog closes, so a crash immediately after does not
  lose it (`REQ-012`)

#### Out of scope

- The sortable format table and per-format selection — `REQ-003`, `REQ-008`, Phase 3
- Drag-and-drop — `REQ-001` allows it, but it is not needed to prove the slice; Phase 2
- Playlist expansion into individual jobs — Phase 3

---

### T-017 — Single-job progress view with cancel

**Status:** Proposed — Ready once `T-013` and `T-014` merge
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-013`, `T-014`
**Relevant context:** `REQ-014`, `REQ-015`, `REQ-018`, `NFR-001`, `NFR-005`
**Affected surfaces:** `ui/queue_view.py`, `ui/job_detail.py`, `tests/ui/`
**Risk:** Medium
**Review base:** the later of the `T-013` and `T-014` merge commits

#### Scope

One job, visible: percent, downloaded/total, speed, ETA, and the current stage — probing,
downloading video, downloading audio, merging, post-processing (`REQ-014`). A cancel control
that reaches `T-013`'s cancellation path. A failed job stays visible with its error and a
retry affordance (`REQ-018`); nothing fails silently.

#### Acceptance criteria

- Every stage in `REQ-014` is displayed, driven by real `T-011` messages rather than a
  simulated sequence
- Under a burst of progress messages the **event loop stays responsive by measurement**, not
  by eye: either event-loop latency stays under a stated bound, or updates are coalesced to a
  stated maximum repaint rate and a test asserts the coalescing. "Does not visibly stutter" is
  not testable, and a per-message repaint is the obvious naive implementation — it degrades
  exactly when a download is fastest
- Cancel is actuable by keyboard and produces a cancelled job within the `REQ-015` budget
- A failed job shows the extractor's verbatim message and remains in the view with a retry
  affordance (`REQ-018`, `NFR-006`)
- A cancelled job is presented as cancelled, not as an error (`ARCHITECTURE.md` §7:
  `CANCELLED` is not a failure)
- Accessible names on all controls; no state conveyed by color alone (`NFR-005`)

#### Out of scope

- Multi-job queue view, reordering, bulk actions — Phase 2
- Pause and resume — `REQ-015` includes them, but they need Phase 2's scheduler
- Open-file and reveal-in-file-manager — `REQ-021`, Phase 2

---

### T-036 — Application composition and wiring

**Status:** Proposed — Ready once `T-013` merges
**Owner:** Implementer
**Priority:** **High** — without it every component can pass while the product still opens an
empty window
**Phase:** Phase 1
**Depends on:** `T-013`, `T-014`, `T-015`, `T-016`, `T-017`
**Relevant context:** `ARCHITECTURE.md` §3, §4, §8; `NFR-001`, `NFR-002`, `REQ-024`
**Affected surfaces:** `app.py`, `ui/main_window.py`, `tests/ui/`, `tests/integration/`
**Risk:** **High** — the only task that can fail while every other task is green
**Review base:** the last of its dependencies' merge commits

#### Scope

**Filed after review: nothing owned this.** `app.py`'s own docstring says `T-013` adds the
download manager wiring, but `T-013` neither claims `app.py` nor proves the assembled path. So
every Phase 1 task could pass in isolation while the application still did nothing — which is
the failure the phase exists to prevent.

Compose the object graph in one place: construct the repository, the manager, the result pump
and the window; inject the concrete `JobRepository` into the manager through the protocol seam
`T-013` defines; connect the add-URL dialog and the progress view to manager signals; and
report the ffmpeg state `T-035` supplies at startup (`REQ-024`).

Also own orderly shutdown: closing the window stops the pump on its sentinel, cancels any
running job, reaps its process tree, and closes the database — in that order.

#### Acceptance criteria

- A test drives the **assembled application** — not components — from paste through to a queued
  job, using `T-016`'s dialog and asserting the job reaches the repository
- Wiring is asserted structurally too: the manager holds the concrete repository, and every
  manager signal the UI needs has exactly one connection. A signal connected twice, producing
  duplicate rows, must fail
- Startup reports the ffmpeg state and names what will not work without it (`REQ-024`)
- Closing the window with a job running exits with code 0, leaves no process in the tree, and
  leaves the database consistent
- Cold start stays inside `NFR-002`'s 3-second budget with the full graph constructed, and the
  measurement is recorded — `T-007` measured an empty window
- No component is constructed twice, asserted by identity, so a second manager cannot quietly
  service a second queue

#### Out of scope

- Any new behavior; this task connects what the others built
- The single-instance guard — `A-004`, Phase 2

---

### T-037 — End-to-end download and restart proof

**Status:** Proposed — Ready once `T-036` merges
**Owner:** Implementer
**Priority:** **High** — two Phase 1 exit criteria are unowned without it
**Phase:** Phase 1
**Depends on:** `T-036`
**Relevant context:** `IMPLEMENTATION_PLAN.md` Phase 1 exit criteria; `REQ-012`, `REQ-014`,
`NFR-003`; `ai/TESTING.md` §7 (Crash recovery)
**Affected surfaces:** `tests/integration/`
**Risk:** **High** — it is the evidence for the phase
**Review base:** the `T-036` merge commit

#### Scope

**Filed after review: the phase had no proof of success.** `T-012` tests probing and failure,
`T-019` tests cancellation and crashes — nobody proved a download *completing*. Phase 1's first
exit criterion is "a real URL downloads to disk with accurate live progress and correct final
bytes", and its fourth is "job state survives an application restart mid-download". Both were
unowned.

Two integration tests against the assembled application, with yt-dlp faked at the adapter seam
so they are deterministic and offline:

1. **Success.** A job runs to completion: the file exists at the expected path, its byte count
   matches what was reported, progress advanced monotonically through the `REQ-014` stages, and
   the job's terminal state is success in both the UI and the repository.
2. **Restart.** Kill the application mid-download, restart it, and assert the job is recovered
   to a retryable state, visible in the UI, with its `DownloadRequest` intact — the assembled
   equivalent of the database-level recovery `T-014` proves.

A network-marked variant downloads one real, stable, small URL end to end, so the offline fake
is checked against reality at least once. It stays excluded by default (`ai/TESTING.md` §2).

#### Acceptance criteria

- The completed file exists, and its size equals the total the final progress message reported
  — a mismatch is exactly the bug this criterion is for
- Progress is monotonic and reaches every `REQ-014` stage the job actually used
- Success is recorded identically in the UI and the repository; disagreement fails
- After a mid-download kill and restart, the job is recovered, visible, retryable, and its
  stored `DownloadRequest` is byte-identical to the original (`REQ-012`, `NFR-003`)
- Recovery is proven by killing a real process, not by closing the application cleanly
- The `-m network` variant completes one real download and is **not** part of the default run

#### Out of scope

- Multiple concurrent jobs — Phase 2
- Resume of a partial download — Phase 2

---

### T-038 — Logging with handler-level redaction

**Status:** Proposed — Ready once `T-011` merges
**Owner:** Implementer
**Priority:** High — `NFR-007` is a privacy promise and worker diagnostics are where it leaks
**Phase:** Phase 1
**Depends on:** `T-011`
**Relevant context:** `ARCHITECTURE.md` §8 (Logging); `REQ-026`, `NFR-007`, `NFR-004`
**Affected surfaces:** `core/` logging setup, `downloader/worker.py`, `tests/unit/`
**Risk:** **High** — a leak here is written to disk and survives
**Review base:** the `T-011` merge commit

#### Scope

**Filed after review: nothing owned logging.** `ARCHITECTURE.md` §8 promises an application log
in `user_cache_dir`, per-job logs, and redaction **at the handler level rather than at each
call site** — precisely so a forgotten call site cannot leak. No Phase 1 task owned any of it,
while `T-012` and `T-013` are about to generate the diagnostics most likely to carry a
tokenized URL or a cookie path.

Configure logging for both processes, add per-job log files, and implement the redacting
handler: cookie file paths, cookie contents, proxy credentials, and token-like URL query
parameters (`REQ-026`, `NFR-007`).

Handler-level is the whole design. A redaction helper that call sites must remember to use is
the thing this task exists to avoid.

#### Acceptance criteria

- A log record whose message contains a cookie path, cookie content, proxy credential, or a
  token-like query parameter is redacted **in the emitted output**, asserted by writing through
  a real handler rather than by calling a redaction function directly
- Redaction survives every formatting route: `%`-style args, f-strings pre-formatted by the
  caller, `extra=` fields, and an exception traceback carrying a URL in its message
- A deliberately careless call site — logging a full request object — still produces redacted
  output, which is the property that distinguishes handler-level from call-site redaction
- Worker logs reach the parent's log without the child needing Qt
- Logs are written under `platformdirs`, never beside the application (`NFR-004`)
- A test scans a generated log for a known token and fails if it appears in any form

#### Out of scope

- A log viewer in the UI — Phase 3
- Rotation and retention policy — Phase 4
- Crash reporting of any kind; there is none (`NFR-007`)

---

### T-018 — Recorded `info_dict` fixtures and projection tests

**Status:** Proposed — Ready once `T-012` merges
**Owner:** Implementer
**Priority:** Medium
**Phase:** Phase 1
**Depends on:** `T-012`
**Relevant context:** `ai/TESTING.md` §5 (fixtures), `NFR-008`, `C-002`, `REQ-026`, `NFR-007`
**Affected surfaces:** `tests/fixtures/infodicts/`, `tests/unit/`
**Risk:** Medium — a carelessly refreshed fixture hides the upstream breakage the fixture
exists to catch
**Review base:** the `T-012` merge commit

#### Scope

Broaden the fixture set `T-012` bootstrapped: several sites, a playlist, an audio-only case,
a DRM-protected case, an unsupported URL, and an extractor error. Each records the yt-dlp
version and capture date (`ai/TESTING.md` §5).

Fixtures are **sanitized**: no cookies, tokens, session or auth query parameters, and no
personal paths (`REQ-026`, `NFR-007`). They are committed, so a leak here is permanent.

#### Acceptance criteria

- Each fixture records the yt-dlp version and capture date alongside it
- A fixture containing a cookie, token, auth query parameter, or a path under `/home` or
  `C:\Users` fails a sanitization check — asserted by a test that scans the fixture directory,
  not by review discipline
- The projection test fails when a projected key changes shape, which is the whole purpose
- When a fixture changes shape the test **names the field that moved**, rather than reporting
  a generic mismatch, so the diff is diagnosable
- Fixture provenance is machine-checked: every fixture has a recorded yt-dlp version and
  capture date, and one lacking either fails. *(Requiring a human to explain why a fixture
  changed is a review convention from `ai/TESTING.md` §5, not an executable criterion — it is
  stated there and deliberately not restated here as if a test enforced it.)
- Fixtures cover at minimum: a normal video, an audio-only case, a playlist, `DRM_PROTECTED`,
  `UNSUPPORTED_URL`, and `EXTRACTOR_ERROR`
- No test in this task touches the network

#### Out of scope

- The `-m network` suite that hits real sites — it exists and stays opt-in
- Automatic fixture refresh; refreshing is deliberately manual

---

### T-019 — Cancellation and worker-crash integration tests

**Status:** Proposed — Ready once `T-013` merges
**Owner:** Implementer
**Priority:** **High** — two of `ai/TESTING.md` §7's mandatory areas, and Phase 1 cannot exit
without them
**Phase:** Phase 1
**Depends on:** `T-013`
**Relevant context:** `ai/TESTING.md` §7 (Cancellation, Worker crash), `REQ-015`, `REQ-028`,
`NFR-003`, `OPS-003`
**Affected surfaces:** `tests/integration/`, possibly `.github/workflows/ci.yml`
**Risk:** **High** — these tests are the evidence for `ARC-002`. A test that passes because
nothing was really running would retire the guarantee rather than establish it.
**Review base:** the `T-013` merge commit

#### Scope

Real child processes, real IPC, yt-dlp faked at the adapter seam (`ai/TESTING.md` §2) so a
download can be made to hang, crash, or run long on demand without the network.

**The fake must do observable work, or the whole task is vacuous.** A fake that returns
immediately would let every assertion below pass against an implementation that cancels
nothing. So the fake, running inside a **real spawned child**, must: signal that it has entered
the download call, emit progress messages carrying its own PID, and grow a partial file on
disk. Only once the test has observed all three may it cancel or kill. That sequencing is
itself an acceptance criterion.

**Descendants count.** Killing the Python worker does not necessarily kill the `ffmpeg` it
spawned. The fake therefore spawns a real grandchild, and cleanup is asserted over the whole
process tree — checking worker PIDs alone would report success while `ffmpeg` kept running and
kept writing.

Prove on **both platforms**: cancellation terminates genuinely in-flight work within 2 seconds
leaving no surviving descendant; a killed worker becomes `WORKER_CRASH` and the application
survives; and no orphan outlives the test session.

#### Acceptance criteria

- Before any cancel or kill, the test has observed **all three** signs of real work: the child
  reported entering the download, progress arrived stamped with the child's PID, and the
  partial file grew. A fake that skips any of them fails the test rather than passing it
- Cancellation of that genuinely in-flight work completes within 2 seconds (`REQ-015`) — the
  distinction `T-002` raised and never closed
- **Cleanup is asserted over the process tree**, including a deliberately spawned grandchild
  standing in for `ffmpeg`. Killing the worker while the grandchild survives must fail
- **The orphan detector is permanently self-tested**: a test creates a real leaked child *and*
  a leaked grandchild and asserts the detector finds both, then reaps them. This runs on every
  suite run — a one-time manual leak would repeat exactly the Phase 0 evidence problem, where
  a check nobody re-exercises looks identical to one that works
- Exactly **one** terminal outcome is recorded per job; a cancelled job is `CANCELLED`, never
  also a failure or a success
- A cancelled download leaves **no completed-file rename** — the partial file stays partial,
  so a cancel cannot be mistaken for a finished download
- The job's persisted state after cancellation matches what the UI was told
- The **GUI event loop is still running** after the kill, asserted by scheduling and observing
  a timer — "the application survives" is otherwise unfalsifiable (`REQ-028`)
- `SIGKILL` and `TerminateProcess` are both exercised on their own platform
- A worker exiting 0 with no terminal message is reported as `WORKER_CRASH`
- The tests run in CI on Linux **and** Windows, and are not skipped on either — a skip on one
  platform fails the job, because `OPS-003` makes CI the only Windows evidence there is
- Timings are recorded, not just asserted, so the 2-second budget can be seen trending

#### Out of scope

- Queue-level behavior with multiple workers — Phase 2
- Network-dependent tests — yt-dlp is faked at the adapter seam here

---

## Blocked

*(none)*

## In Review

*(none)*

## Complete

### T-027 — Reject unsafe stored window geometry

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
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

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
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

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
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

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
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

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
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

**Status:** Complete
**Completed:** 2026-07-25 — squash-merged via PR #7. `T005`-era findings and `P0-R2` … `P0-R5` were reviewer-verified; the corrections to `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **accepted by the maintainer without a final re-review**. Recorded rather than implied: those four are maintainer-accepted, not reviewer-verified.
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
