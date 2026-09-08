# DECISIONS.md — Tracks & Trails

**Purpose:** Record durable product and technical decisions and the reasoning behind them.
**Authority:** Canonical for decision *rationale and status*. **Not** canonical for current
requirements or design — those live in `REQUIREMENTS.md` and `ARCHITECTURE.md`.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-09-08
**Update when:** A durable choice is accepted, superseded, or deliberately rejected.
**Does not contain:** Completion notes for routine work. Routine fixes go to `TASKS.md` and `CHANGELOG.md`.


> **Paths below are as they were written.** The coordination documents moved from `ai/` to
> `docs/project/` on 2026-09-08 (`DOC-006`). Entries here are statements about a past head —
> a command that was run, a review's write set, a `FILE.md:NNN` citation — so their paths are
> left alone rather than rewritten. `ai/TESTING.md` below means what is now
> `docs/project/TESTING.md`.

Statuses: Proposed · Accepted · Rejected · Deprecated · Superseded.
Prefixes: `DOC-` documentation system · `ARC-` architecture · `DAT-` data · `SEC-` security ·
`OPS-` operations · `REL-` release · `LIC-` licensing · `UX-` user experience.

---

## DOC-001 — Adopt the AI project documentation convention, Standard profile

**Status:** Accepted
**Date:** 2026-07-25
**Supersedes:** None

### Context

Tracks & Trails is a greenfield project intended to be built largely with AI assistance
across multiple sessions and more than one tool. Without a shared source of truth, scope
drifts and rationale is lost in chat history.

### Decision

Adopt the *AI-Assisted Project Documentation Convention*, **revision 2026-07-18.1**, using
the **Standard** adoption profile: root `AGENTS.md` and `README.md`, plus the full `ai/`
starter set.

Tool-to-role assignment is named explicitly: **Claude Code** as Planner, Implementer,
Documentation Maintainer, and Release Manager; **Codex** as Reviewer. Both are mapped to
capability roles in `AGENTS.md` so the workflow survives a change of tools.

### Rationale

The project is a distributed cross-platform desktop application with real dependency,
licensing, and safety constraints — heavier than the Lean profile supports. Splitting
implementation from review across two independent agents catches more than self-review,
because the reviewer does not inherit the implementer's assumptions.

### Alternatives considered

- **Lean profile** (`PROJECT.md` only) — rejected. This is intended as a released application
  with a release gate, licensing constraints, and both-platform verification requirements.
  The combined document would need splitting almost immediately.
- **Standard + UI-heavy + Operational immediately** — deferred, not rejected. See `DOC-002`.
- **Generic capability roles with no tool names** — rejected. The concrete assignment is the
  useful part; portability is preserved by the role mapping.

### Consequences

- Every task must identify its relevant context, acceptance criteria, and required checks.
- Review evidence goes in `REVIEWS.md`; unresolved findings become `TASKS.md` entries.
- No deliberate deviations from the convention are in force at adoption.
- The convention document is **not** in this repository. `AGENTS.md` is self-contained; a
  later convention revision does not silently change this project's rules.

### Affected files

`AGENTS.md`, all of `ai/`, `README.md`.

---

## DOC-002 — Defer the UI-heavy and Operational documentation profiles

**Status:** Accepted
**Date:** 2026-07-25

### Context

Two additional adoption profiles plainly apply to this project eventually: **UI-heavy** (a
download manager has real screen/flow/state complexity) and **Operational** (a distributed
desktop app needs a documented release and signing process).

### Decision

Do not create `docs/UX_SPEC.md`, `docs/OPERATIONS.md`, `docs/RELEASE.md`, `SECURITY.md`, or
`docs/DEVELOPMENT.md` at bootstrap. Create each when its documented trigger fires:

| File | Create when |
|---|---|
| `docs/UX_SPEC.md` | Phase 3 begins, or empty/loading/error states need specifying beyond a requirement line |
| `docs/DEVELOPMENT.md` | `T-001` establishes a real setup workflow (expected almost immediately) |
| `docs/RELEASE.md` + `SECURITY.md` | Phase 5 begins, or a release is first prepared |
| `docs/OPERATIONS.md` | Only if the project gains a service, updater backend, or hosted component |
| `docs/RISKS.md` | The "Current risks" section of `STATUS.md` outgrows a short list |
| `CHANGELOG.md` | The first tagged release |

### Rationale

The convention warns against speculative empty documents that gain no owner and rot. Each
file above has a concrete trigger, so deferral is scheduled rather than forgotten.

### Consequences

Until `SECURITY.md` exists, the security boundaries in `ARCHITECTURE.md` §9 and the
exclusions in `REQUIREMENTS.md` §8 are the authoritative security statements.
`docs/OPERATIONS.md` may never be needed — that is an acceptable outcome.

---

## DOC-003 — Parallel work is available, opt-in, and maintainer-opened

**Status:** Accepted
**Date:** 2026-07-27
**Supersedes:** None (extends `DOC-001`)

### Context

`DOC-001` adopted the documentation convention at revision **2026-07-18.1**, which assumed one
agent working serially on `main`. Two agents have since run on this project at the same time,
and the shared checkout is where that goes wrong: an uncommitted change in the working tree
belongs to whichever agent last touched it, and a reviewer already had to fall back to
`git archive` mid-review because unrelated work entered the tree under it. Convention revision
**2026-07-27.2** adds a repository-collaboration mode with rules for exactly this.

### Decision

Adopt revision 2026-07-27.2's **repository-collaboration-mode, parallel-work, and
review-partitioning rules**, recorded in `AGENTS.md` §9 with §3, §4, §7, §11 and §12 updated to
match. Serial work on `main` remains the default. A parallel wave is opened by the maintainer
per wave; an agent never starts one, creates its branches, or splits a task into workers on its
own. During a wave: one branch and one worktree per task, one writer each, an exclusive write
set, coordinator-only writes to `ai/TASKS.md` and `ai/STATUS.md`, reviewer-written
`ai/reviews/T-0NN.md` records, approval frozen to one implementation head, and serial
integration followed by verification of the combined tree.

Only those deltas were applied deliberately. The rest of the gap between 2026-07-18.1 and
2026-07-27.2 was not audited, so `DOC-001`'s recorded revision stands except where this entry
supersedes it.

### Rationale

Waiting out a serial queue is the cost this is meant to remove, but the failure mode is not
"slower" — it is losing another agent's uncommitted work, or approving a head that has since
moved. Worktrees, exclusive write sets, and head-frozen approval are the three rules that make
concurrency safe here; the rest is coordination overhead that only pays off when tasks are
genuinely independent, which is why the qualification test is explicit and the wave is opt-in.

The editable `.venv` install is a project-specific trap worth naming: a second worktree runs the
*primary* checkout's `src` unless `PYTHONPATH` overrides it, so a worker can otherwise test the
other agent's code and believe its own passed.

### Alternatives considered

- **Stay serial only** — rejected as the standing rule, but it remains the default. Serial work
  needs no coordination and produces the same reviewable base/head pairs.
- **Branches without separate worktrees** — rejected. This is the exact configuration that has
  already destroyed work here; one checkout cannot hold two writers.
- **Keep the monolithic `ai/REVIEWS.md` during waves** — rejected. Parallel reviewers appending
  to one file on separate branches conflict on every merge.
- **Let an agent open a wave when it judges the work parallelizable** — rejected. The
  qualification test needs knowledge of what else is in flight, and the cost of a wrong call is
  paid in lost work.

### Consequences

- `ai/reviews/` is created on first use, not now.
- A wave adds coordinator overhead: qualification, base selection, write-set assignment,
  serial integration, combined verification, and cleanup.
- `-m process_tree` tests stay single-slot across worktrees; they cannot be parallelized.
- Approval semantics tighten in wave mode: a post-approval commit that touches anything but the
  review record needs focused re-review before integration.

### Affected files

`AGENTS.md`, `ai/REVIEWS.md`, `ai/PROMPTS.md`.

---

## DOC-004 — Review findings do not map one-for-one to tasks

**Status:** Accepted
**Date:** 2026-08-26
**Supersedes:** `DOC-001`'s consequence that every unresolved finding becomes a `TASKS.md` entry;
otherwise extends `DOC-001`

### Context

T-279's final review correctly approved the behavior but turned two Low residuals — an
unnecessary helper read and two evidence-wording corrections — into a new `T-280` task solely
because the standing review rule required every non-blocking finding to have an owner and target
task. The maintainer rejected that outcome: *“dont keep creating endless follow up tasks.”*

The review record and execution queue answer different questions. Preserving a meaningful
observation is cheap and useful; scheduling every observation makes incidental cleanup compete
with product work, inflates the queue without a prioritization decision, and makes review itself
an unbounded task generator.

### Decision

Adopt the finding-disposition and task-creation-threshold rules from *AI-Assisted Project
Documentation Convention* revision **2026-08-26.1**, recorded locally in `AGENTS.md` §10.

Every meaningful finding remains in the review record. A **new task** is created only when the
work is independently actionable, materially worth scheduling, has clear acceptance criteria and
priority, and is actually intended to compete for execution time. Otherwise the finding is:

- corrected in the current task when tightly coupled and in scope;
- handled in that task's ordinary completion synchronization when it is mechanical current-truth
  or status cleanup;
- routed to an existing open task that naturally owns the behavior, or — for very minor
  mechanical cleanup — rolled into the next existing task's normal completion/coordination pass
  without changing that task's behavioral scope, risk or acceptance criteria; or
- closed honestly as a Note, Accepted Risk, Won't Fix or Superseded, with rationale where needed.

An owner/target field is not itself authority to create a task. **Approved with follow-ups** means
real scheduled work survived this threshold; it is not the default verdict whenever a Low finding
exists.

### Rationale

`REVIEWS.md` should be exhaustive enough to preserve evidence. `TASKS.md` should be selective
enough to express priority. Conflating them makes both worse: reviewers either suppress small but
useful observations to protect the queue, or record them and manufacture work nobody chose.
Explicit disposition preserves the observation without pretending it was prioritized.

### Alternatives considered

- **Keep task-per-finding, then periodically prune** — rejected. The queue is misleading between
  pruning passes, and deletion later cannot recover the missing prioritization decision.
- **Stop recording Low findings** — rejected. A Low observation can explain a future regression or
  reveal a recurring defect class even when no present work is justified.
- **Always fold Low findings into the reviewed task** — rejected. That silently broadens scope and
  can create endless correction/re-review loops by another route.

### Consequences

- `T-280` is not a task; T-279 remains approved with its harmless eager-read residual recorded and
  its evidence wording handled during ordinary completion synchronization.
- Reviewers must disposition non-blocking findings, but do not automatically create queue entries.
- Existing follow-up tasks are not cancelled by this decision; each remains until deliberately
  reprioritized under its own facts.
- `AGENTS.md` §7 and §10 carry the self-contained project rule. Later convention revisions still
  do not silently change this repository.

### Affected files

`AGENTS.md`, `ai/REVIEWS.md`, `ai/TASKS.md`.

---

## DOC-005 — Minor actionable findings ride existing work; Notes request no change

**Status:** Accepted
**Date:** 2026-08-26
**Supersedes:** `DOC-004` only where it allowed a reviewer to close an actionable minor finding as
a Note or other no-action disposition without the maintainer's decision

### Context

`DOC-004` correctly stopped review findings from mapping one-for-one to new tasks, but its phrase
*“closed honestly as a Note, Accepted Risk, Won't Fix or Superseded”* left two different things in
one bucket: a genuinely informational Note and a small change the reviewer decided was not worth
scheduling. The maintainer clarified that a very minor finding should roll into the next existing
task if necessary, not disappear merely because its consequence is harmless.

### Decision

Adopt the clarification in convention revision **2026-08-26.2**:

- A **Note** records useful context and requests no change. A small requested change remains a Low
  finding; a reviewer must not relabel it as a Note.
- A very minor actionable finding is handled in the current task's completion synchronization or
  rolled into the next existing task's normal completion/coordination pass when necessary, without
  changing that task's behavioral scope, risk or acceptance criteria.
- A valid actionable finding closes as **Accepted Risk** or **Won't Fix** only on an explicit
  maintainer no-action decision. **Superseded** requires a later fact that genuinely makes the work
  moot. These are dispositions, not reviewer shortcuts around routing the work.
- The new-task threshold from `DOC-004` is unchanged.

### Rationale

The queue should not grow for every tiny correction, but neither should avoiding queue growth erase
real work. Rolling minor mechanical work into an existing completion pass preserves the correction
without pretending it needs independent priority. Restricting Notes to non-actionable context keeps
severity and disposition honest.

### Consequences

- Reviewers distinguish *“no change requested”* from *“a change is requested but small.”*
- Minor actionable cleanup follows existing work rather than creating a new task.
- Choosing not to perform valid actionable work is the maintainer's decision and is recorded as
  such.

### Affected files

`AGENTS.md`, `ai/REVIEWS.md`, `ai/TASKS.md`.

---

## DOC-006 — Adopt convention revision 2026-09-08.1 and the neutral coordination layout

**Status:** Accepted
**Date:** 2026-09-08
**Supersedes:** the layout half of `DOC-001`. `DOC-001`'s profile choice and role mapping stand.

### Context

Two things arrived together. The maintainer decided this repository should become public so the
work can be shown to employers, and the *AI-Assisted Project Documentation Convention* was revised
to **2026-09-08.1**, which adds a **public-ready by default** baseline and moves the coordination
root from `ai/` to `docs/project/`.

The convention's retrofit section asks for that move to be made as **one bounded migration** rather
than drifting into place, and asks the adoption itself to be recorded here.

### Decision

Adopt convention revision **2026-09-08.1**, keeping the **Standard** profile, adding **UI-heavy**
(`docs/UX_SPEC.md` already exists and `DOC-002` deferred the label, not the file), and recording
the delivery target as an **installed desktop application**.

Concretely, in one change:

- `ai/` moved to `docs/project/`, with path references updated in the **current-truth** documents,
  the workflows, the tests, the source comments, `pyproject.toml`'s per-file ignores, `.gitignore`,
  `.gitattributes` and `.gitmessage`. The historical records keep the paths they were written with;
  see consequence 2.
- `SECURITY.md` added at the repository root. The application handles cookie material and proxy
  credentials, runs on a network, and is intended for public distribution; the convention's own
  criteria for that file are met several times over.
- `README.md` rewritten product-first. The old one said *"pre-alpha, planning only. No code exists
  yet"* while 58 source modules and a working application sat beside it.
- Document `Owner:` fields made capability roles. Three named a tool: `AGENTS.md`,
  `ai/TESTING.md`, and `ai/REVIEWS.md`.

### Rationale

`Owner` is an update-responsibility field, not a byline, and the convention is explicit that
named-tool assignment belongs in one operational mapping rather than in every document's header.
That mapping already exists in `AGENTS.md` §3 and is unchanged, so nothing about how work is
actually routed changed here — the roles were never carried by the metadata.

The layout move is the larger half, and its value is that shared engineering knowledge sits in a
neutral location. Requirements, architecture, decisions, tasks, and reviews belong to the project,
not to the tooling that happened to write them.

### Alternatives considered

- **Keep `ai/` and change only the framing** — rejected. The convention names the migration
  specifically, and a directory called `ai/` beside `docs/` invites exactly the misreading that
  the coordination documents are a tooling artifact rather than the project's record.
- **Remove the coordination documents from the public repository** — rejected. The review record is
  the most honest evidence this project has of how it was built, including the parts where the
  reviewer found the implementation wrong. Hiding it would trade the strongest artifact for a
  cosmetic gain.
- **Rewrite history to remove tool names from commit subjects** — rejected. Eighteen subjects name
  the reviewer. The convention forbids cosmetic rewriting of development history, and independently
  it would not work: the coordination documents cite several hundred short SHAs, and re-writing
  1306 commits invalidates every one of those citations.

### Consequences

Four deliberate deviations are in force, each recorded rather than silently taken:

1. **`AGENTS.md` is 628 lines**, against the convention's soft review trigger of roughly 200–300.
   It is **not** restructured here. Its section numbers are cited from 359 places — source
   comments, `pyproject.toml`, `tools/commit_message_check.py`, and the coordination documents —
   and renumbering them in the same change that moves every path would make one large mechanical
   migration into two. Filed as `T-300`.
2. **Only current-truth documents had their path references updated.** `REQUIREMENTS.md`,
   `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `TESTING.md`, `PROMPTS.md`, `TASKS.md` and
   `STATUS.md` name the new locations, because those files are rewritten to reflect reality
   (`AGENTS.md` §6). **`REVIEWS.md` and every decision entry above keep the paths they were written
   with**, because there a path is frequently a *fact* rather than a link: a command that was
   actually run, the write set a review actually excluded, a `FILE.md:NNN` citation taken at a head
   where the file was at that path, and handoff filenames that only ever existed under `ai/`.
   Rewriting those would change the record. A navigation note at the top of each says where the
   documents live now.

   *(This deviation first claimed a path reference is a link rather than a fact **everywhere**,
   and on that basis 513 references in `REVIEWS.md` and 48 here were rewritten. `T299-R2` gave the
   three categories that disprove it, and both files were restored. The claim was convenient and I
   did not test it against a single example before acting on it.)*
3. **Evidence lives at `docs/project/evidence/`.** The convention names no evidence directory; this
   keeps it beside the records that cite it.
4. **`REVIEWS.md` stays monolithic.** Partitioned mode is recommended for parallel work, and this
   project is serial with one writer.

`CHANGELOG.md` is still absent, correctly: there are no releases. It becomes required at the first
tagged one, with `docs/RELEASE.md`, under Phase 5.

### Affected files

`README.md`, `SECURITY.md`, `AGENTS.md`, the current-truth documents under `docs/project/`,
`docs/DEVELOPMENT.md`, `docs/WINDOWS_VERIFICATION.md`, `.github/workflows/`, `pyproject.toml`,
`.gitignore`, `.gitattributes`, `.gitmessage`, `tools/windows/run-on-starbase.sh`, and every test
and source file that named a coordination document.

---

## ARC-001 — Python + PySide6 (Qt 6) as the implementation stack

**Status:** Accepted
**Date:** 2026-07-25

### Context

The application needs a native-feeling desktop GUI on Linux and Windows, wrapping yt-dlp,
which is itself a Python library.

### Decision

Build in Python with **PySide6** (Qt 6) for the GUI.

### Rationale

- yt-dlp *is* Python. Sharing the runtime makes `ARC-002` — using it as a library rather
  than parsing CLI text — possible at all. Any other stack forces subprocess text parsing.
- Qt's model/view framework fits the two hardest views (a live-updating job queue and a
  sortable multi-column format table) without hand-rolling them.
- PySide6 is **LGPLv3**, which permits distribution under a permissive project license as
  long as Qt stays dynamically linked.

### Alternatives considered

- **PyQt6** — equivalent capability, but **GPLv3 or commercial**. GPL would force the whole
  application under GPLv3. Rejected on licensing, not on technical grounds.
- **Flutter desktop** — already installed locally and produces a polished UI, but Dart cannot
  import yt-dlp. It would require bundling the yt-dlp binary per platform and parsing
  stdout, losing structured `info_dict` access. Rejected.
- **Tauri (Rust + web UI)** — smallest binaries and good installers, but the same
  subprocess-parsing tradeoff plus two toolchains (Rust + Node), neither installed.
- **Electron** — same parsing tradeoff, largest footprint. Rejected.
- **Tkinter** — in the stdlib and available, but no usable table/model-view story and a
  dated look on both targets. Rejected.

### Consequences

- Runtime dependencies must stay LGPL-compatible; Qt must never be statically linked
  (`NFR-009`, `LIC-001`). This is a rule in `AGENTS.md`.
- Packaging a Python GUI app for Windows is more work than a compiled binary — Phase 5 cost.
- **Baseline: Python 3.14**, verified by `T-002` on 2026-07-25 (PySide6 6.11.1, Qt 6.11.1).
  PySide6 ships **stable-ABI (`abi3`) wheels** — one `cp310-abi3` build serves every Python
  ≥3.10 — so the baseline is *not* constrained by PySide6's release cadence, and interpreter
  upgrades are cheap. The originally feared wheel-availability risk does not exist.
  Verified on Linux only; the Windows half is carried by `T-006` (`OPS-003`).

---

## ARC-002 — Consume yt-dlp as a library inside one isolated child process per job

**Status:** Accepted — the "versioned internal contract" phrase in its consequences is
**narrowed by `ARC-003`** (2026-07-26). The decision itself is unchanged.
**Date:** 2026-07-25

### Context

There are three plausible ways to drive yt-dlp: shell out to the CLI and parse stdout; import
it and run in a GUI-process thread; or import it and run in a separate process. This choice
determines progress fidelity, cancellation behavior, and crash blast radius.

### Decision

Import `yt_dlp` as a library and execute each job in a **dedicated child process**, using the
`spawn` start method on all platforms. Progress flows back over a `multiprocessing.Queue` as
typed messages defined in `downloader/protocol.py`. Probing also runs in a worker process.

### Rationale

- **Structured data over scraped text.** `progress_hooks` give numeric bytes/speed/ETA and
  `extract_info` gives a real format list. Parsing `[download]  34.2% of 12.3MiB` is fragile
  and breaks silently on yt-dlp output changes.
- **Fault isolation** (`REQ-028`). yt-dlp runs a large surface of third-party extractors.
  In-process, a crash or unkillable hang takes the whole GUI with it. Per-process, one job
  fails and the app observes an exit code.
- **Real cancellation** (`REQ-015`). Threads cannot be reliably killed in Python; a hung
  socket read in an extractor leaks a thread forever. A process can be terminated.
- **Concurrency without the GIL.** Genuinely parallel jobs (`REQ-013`).

`spawn` on Linux as well as Windows is deliberate: forking a process with a Qt event loop is
unsafe, and using one start method everywhere means both platforms exercise the same path
instead of Windows-only bugs surfacing late.

### Alternatives considered

- **Subprocess the yt-dlp CLI** — best possible isolation and lets users swap the binary
  freely, but forfeits structured info and requires stdout parsing. Rejected; `OPS-002`
  recovers most of the "user can update it" benefit without the parsing cost.
- **QThread per job, yt-dlp in-process** — much simpler, no IPC, no pickling constraints.
  Rejected: cannot satisfy `REQ-028` or the 2-second cancellation criterion, and a
  C-extension crash would kill the application.
- **asyncio in-process** — yt-dlp is synchronous and blocking. Not applicable.

### Consequences

- Everything crossing the boundary must be picklable, and only declared message types may
  cross. Raw `info_dict` objects are projected first.
- Worker modules must not import Qt and must be import-safe under `spawn`. Enforced by
  `tests/unit/test_layering.py`.
- Per-process startup cost (interpreter + yt-dlp import) is real; acceptable against
  multi-second download times, and it is why the pool is bounded rather than per-click.
- The IPC protocol is now a versioned internal contract with its own tests.
- Distinguishing "worker died" from "job failed" requires exit-code handling
  (`WORKER_CRASH` in the `ARCHITECTURE.md` §7 taxonomy).

---

## DAT-001 — SQLite for queue and history; TOML for settings

### Amended 2026-08-06 (second, and current) — there is no history to store

**Status:** **Accepted**, on the maintainer's withdrawal ruling of the same day.

**This supersedes the amendment below it, which is only hours older.** That one said the word
*history* had narrowed to a private ledger and that SQLite still held completion records. Both
halves are now wrong: `REQ-020` is withdrawn, `DAT-006` is Withdrawn, and migration `0009` dropped
the table. **SQLite holds jobs and queue order. That is the whole of it.**

**The storage choice is still unaffected**, which is the only reason this entry survives at all.
`DAT-001` chose SQLite for WAL-mode crash safety on frequent transactional row updates during
downloads (`NFR-003`), and the queue alone justifies every word of that argument. The title says
*history* and is left as written, because renaming an accepted decision's title erases the trail a
reader follows from `REQ-020` to here.

### Amended 2026-08-06 (first, superseded) — "history" is a private ledger, and the storage choice is unchanged

**Status:** **Accepted**, on maintainer direction of 2026-08-06 recorded at `T-169`.

**The word *history* in this entry's title and body now means the completion ledger `DAT-006`
describes**, not a browseable list. **Nothing about the storage choice changes**: SQLite in WAL mode
still holds jobs, queue order and completion records, and TOML still holds settings. This note
exists because the title says *history* and a reader arriving from `REQ-020` would otherwise take
it as evidence that the browseable feature is still current truth.

The original entry follows unaltered.

**Status:** Accepted
**Date:** 2026-07-25

### Context

The queue must survive restarts and unclean kills (`REQ-012`, `NFR-003`), and settings must
be user-inspectable. These are different problems.

### Decision

**SQLite** (WAL mode, in `platformdirs.user_data_dir`) for jobs, queue order, and history.
**TOML** (in `user_config_dir`) for settings and user presets. Locations resolved via
`platformdirs` on both platforms.

### Rationale

The queue takes frequent transactional row updates during downloads and must not corrupt on
a hard kill — SQLite's WAL journaling is exactly that guarantee, and a JSON file rewritten
on every progress tick is a corruption bug waiting to happen. Settings are the opposite:
written rarely, read at startup, and worth hand-editing and diffing — a binary-ish store
would be user-hostile. Python 3.11+ reads TOML from the stdlib (`tomllib`).

### Alternatives considered

- **Everything in SQLite** — one store, but settings become opaque and un-diffable.
- **Everything in JSON** — no transactional safety for the queue. Rejected on `NFR-003`.
- **A file per job** — simple, but no ordering, querying, or atomic multi-row updates.

### Consequences

- Schema migrations must be maintained (`ARCHITECTURE.md` §10) and are a release-gate item.
- Two stores mean two load paths and two backup concerns.
- Concurrent instances against one database are unsafe; a single-instance guard is required
  (`A-004`, Phase 2).

---

## OPS-001 — ffmpeg is an external dependency: detected on Linux, bundled on Windows

**Status:** Accepted
**Date:** 2026-07-25

### Context

ffmpeg is required to merge separate video/audio streams and for all audio extraction and
recoding (`REQ-010`). Linux users typically have it; Windows users typically do not, and
telling them to install it manually would fail most first runs.

### Decision

Do not vendor ffmpeg on Linux — detect it at startup, report its absence clearly, and
disable the features that need it (`REQ-024`). **Bundle an LGPL-licensed ffmpeg build in the
Windows installer.** Allow an explicit override path in settings on both platforms.

### Rationale

Bundling on Linux fights the distro package manager and ships a second copy of a library the
user already has. On Windows there is no package manager to rely on, and "best quality"
downloads *require* a merge — an unbundled Windows build would fail the very first download
for most users.

Detect-and-degrade rather than fail-at-merge-time matters: discovering the problem after a
600 MB download completes is the worst possible time to report it.

### Alternatives considered

- **Bundle everywhere** — consistent, but poor Linux citizenship and larger packages.
- **Require manual install everywhere** — unacceptable Windows first-run experience.
- **Download ffmpeg on first run** — no bundle size cost, but adds an unexpected outbound
  download, a supply-chain trust question, and a failure mode behind corporate proxies.
  Rejected against `NFR-007`.

### Consequences

- The Windows installer grows by roughly the size of an ffmpeg build.
- Licensing: only an **LGPL** ffmpeg build may be bundled, and its license text must ship
  with it (`LIC-001`). A GPL build would relicense the distributed application.
- Startup does an ffmpeg capability probe, and features gate on the result.

---

## OPS-002 — Ship a pinned yt-dlp baseline that the user can update in place

**Status:** Accepted
**Date:** 2026-07-25

### Amended 2026-08-27 — the override is recovery, not a standing choice

**Status:** **Accepted, on the maintainer's ruling of 2026-08-27**, taken during `T-212`'s
checklist run. Asked whether users should simply be kept on the packaged baseline — *"we're
keeping track of two different versions, and if users update yt-dlp and there are issues they
would have to wait to get it to work again"* — and offered three answers, the maintainer chose the
middle one: **"lets go with the middle option. I think that makes the most sense."**

**The mechanism is unchanged and nothing below is withdrawn.** The pinned baseline, the
user-managed copy resolved ahead of it, the visible resolved version and the one-action revert all
stand exactly as decided. **What changes is where the update is offered and how it is worded.**

**The update stops being a standing button of equal weight on the Settings screen** — which reads
as something a user is supposed to do — and becomes what it was always for: **the way out of a
site that has broken.** Surfaced against a failure rather than presented as a routine choice, so
the baseline is what everybody runs and the override is the exception it was designed to be.

**The concern this answers, and the one it does not.** The maintainer's stated worry — a user
stranded on a version that does not work — was already answered by revert being one action, and
that has not changed. The worry the amendment actually addresses is the one underneath it: an
update offered as a peer of every other setting *invites* a population onto versions this project
has never tested, which is a support surface rather than a user risk.

**Removing the override outright was rejected, and the reason is stronger than when this entry was
written.** *"Pin only"* is already in *Alternatives considered* below, refused because a broken
site would block users until the next release. **There are no release tags in this repository**;
until a release pipeline exists, "until the next release" means indefinitely. The rejection is
re-affirmed, not re-argued.

**This is worth revisiting if app updates ever become automatic.** The slower and more manual the
application's own updates are, the more the in-app yt-dlp update earns its place, because it is the
only fast path a user has. On a platform that updates the application itself without being asked —
Flathub, say — the argument for the override genuinely weakens and this entry should be reopened.
`REL-001` defers the Linux packaging choice, so that is not yet decidable.

`T-290` builds it.

### Context

yt-dlp breaks constantly, because sites change constantly (`C-002`). A pinned dependency
means a broken site stays broken until the next Tracks & Trails release. An unpinned one
means behavior is irreproducible and an upstream regression becomes our bug report.

### Decision

Bundle a **pinned, tested baseline** yt-dlp version with each release. Additionally, resolve
a user-managed copy in `user_data_dir/tracksandtrails/ytdlp/` ahead of the baseline at worker
startup, and provide an in-app action to install the latest yt-dlp there (`REQ-025`). The
resolved version is always shown in the UI, and reverting to the baseline is one action.

**Update mechanism: wheel extraction, not pip.** The shipped artifact is a frozen application
(`REL-001`) with no pip and no writable `site-packages`, so the update action downloads the
yt-dlp wheel from PyPI, verifies it, and extracts it into `user_data_dir/tracksandtrails/ytdlp/`.
The worker prepends that directory to `sys.path`. This is viable only because **yt-dlp is pure
Python** — verified 2026-07-25 against 2026.06.09: 1046 `.py` files, zero `.so`/`.pyd`
extensions — so there is no compilation step and no ABI or interpreter-version matching. A
dependency on a compiled extension would invalidate this approach and reopen the decision.

### Rationale

This gets reproducibility and freshness at once. The baseline is what tests and support
assume; the override is what unblocks a user the day a site changes, without waiting for us.
Showing the resolved version means bug reports state which yt-dlp actually ran — otherwise
every report is unactionable.

### Alternatives considered

- **Pin only** — a broken site blocks users until we ship. Rejected against `C-002`.
- **Always fetch latest** — irreproducible; an upstream regression looks like our bug.
- **Use the system yt-dlp** — reasonable on Linux, absent on Windows; and version skew
  becomes unbounded.

### Consequences

- Worker startup resolves yt-dlp explicitly rather than relying on ambient `sys.path`.
- The user can put the app into an untested state. Acceptable, provided the version is
  visible and revert is trivial.
- The update action performs an outbound package download — it must be explicit, never
  automatic, and never silent (`NFR-007`), and the wheel must be integrity-checked before
  extraction. It executes code the user did not write; treat it as a supply-chain surface.
- Bumping the baseline is a release-gate step.
- A future yt-dlp release that adds a **required** compiled dependency breaks this mechanism.
  The release gate re-checks purity (`ai/TESTING.md` §8).

---

## REL-002 — `collect_submodules("yt_dlp")` stays, as insurance against a pin we do not have yet

**Status:** **Accepted** (2026-08-04) — maintainer decision, answering `T033-R4`
**Date:** 2026-08-04
**Extends:** `REL-001`, which chose frozen self-contained artifacts. This is one line inside that
choice. **Unblocks:** `T-033`.

### Context

`T033-R4` asked for two collection lines to be decided **separately**, because the evidence for
them is not the same and treating them together produced a wrong conclusion once already.

- **`collect_data_files("yt_dlp")` is not in question.** Removing it produced a *passing* probe
  while deleting all three yt-dlp YouTube solver assets — `yt.solver.core.js`,
  `yt.solver.deno.lib.js`, `yt.solver.bun.lib.js`. That survival proved **the frozen gate is blind
  to package-data loss**, not that the line is dead. It stays, and extending the probe to load the
  built-in solver through yt-dlp's real `vendor.load_script` path is `T-033`'s remaining work.
- **`collect_submodules("yt_dlp")` is genuinely redundant *for this pin*.** A build with it
  returning `[]` passed, and the pinned `_extractors.py` contains 928 static relative imports, so
  PyInstaller's analysis finds the extractors without help.

### Decision

**It stays.** The evidence establishes that it is unnecessary for the *current* pin, which is a
fact about this version of yt-dlp rather than about yt-dlp. Extractor discovery is exactly the kind
of thing an upstream refactor moves to dynamic imports, and the failure mode if that happens is
**silent**: a frozen build that has quietly lost extractors, passing a probe that only instantiates
`YoutubeIE` and checks a URL predicate.

The trade is one line, some build time and some artifact size, against a class of failure the gate
cannot currently see. That is not a close call while the probe is blind.

### Consequences

- **This is re-evaluated whenever the yt-dlp pin changes**, which `T033-R4` asked for. A pin bump
  is the moment the redundancy evidence expires, and the evidence is a *negative build* — cheap to
  repeat, so repeat it rather than assuming.
- **It is not a substitute for the probe extension.** Keeping this line does nothing about the data
  blindness `T033-R4` found; the two were separated precisely so that one could not be read as
  covering the other.
- **The reason is written here rather than in the spec file.** A comment saying "belt and braces"
  is what gets deleted by the next person who measures the artifact and finds the line does
  nothing.

---

## REL-001 — Ship frozen, self-contained artifacts: no Python required on the user's machine

**Status:** Accepted
**Date:** 2026-07-25

### Context

The target users (`REQUIREMENTS.md` §2) are desktop users, not developers. Requiring a Python
installation, a virtual environment, and a `pip install` would exclude most of them — and on
Windows, where there is often no Python at all, it would exclude nearly all of them. The
implementation language must not become a user-facing prerequisite.

### Decision

Every released artifact **bundles its own Python interpreter, Qt, and yt-dlp baseline**. A
user installs and runs Tracks & Trails with nothing preinstalled.

- **Windows** — PyInstaller one-dir build + Inno Setup installer, ffmpeg bundled (`OPS-001`).
- **Linux** — a self-contained format (AppImage or Flatpak; the choice is deferred to a
  follow-up `REL-` decision in Phase 5). ffmpeg remains a system dependency (`OPS-001`).
- `pipx install` may be offered as a **secondary** convenience for developers. It must never
  be the only Linux option, because it reintroduces the Python prerequisite.

### Rationale

"Works on a clean machine" is already a Phase 5 exit criterion; this makes it an architectural
commitment rather than a packaging afterthought. Freezing is the standard answer for
distributing a Python desktop application and the only one that meets the requirement.

### Alternatives considered

- **Require Python + pip/pipx** — rejected. Unacceptable on Windows, and it turns an
  implementation detail into a user prerequisite.
- **System packages (`.deb`/`.rpm`) depending on distro Python** — good Linux citizenship, but
  no Windows story, and it couples the app to whatever interpreter and PySide6 version the
  distro ships (`ARC-001` pins a baseline for a reason). May be added later; not the primary.
- **Rewrite in a compiled language** — would give small binaries, but forfeits `ARC-002`
  entirely, which is the design.

### Consequences

- **`multiprocessing.freeze_support()` must be the first statement in the entry point**,
  before any other import-time work. In a frozen app `sys.executable` is the application
  binary, so a `spawn`ed child re-executes the full application — a recursive launch loop, not
  a subtle bug. This interacts directly with `ARC-002` and is the single highest-risk
  packaging defect in the project. Covered by `T-020`.
- Artifact size is large (Qt is ~150 MB before ffmpeg). Accepted.
- `OPS-002`'s update path cannot use pip — see the update-mechanism note in that entry.
- Qt must be dynamically linked **inside the frozen bundle**; verified on the built artifact,
  not merely in project metadata (`NFR-009`, `LIC-001`).
- Freezing must be exercised in CI from Phase 0 (`T-020`), not first attempted at Phase 5.

---

## OPS-004 — Windows CI runners provide a real desktop; verify against it

**Status:** **Accepted** (2026-07-26) — accepted as proposed, without amendment
**Date:** 2026-07-25
**Supersedes:** the automatable / not-automatable classification in `OPS-003`

### Context

`OPS-003` accepted that CI is the only Windows environment available, then split Windows
verification into what CI could automate and what it could not. That split was reasoning, not
measurement, and it assumed a CI runner has no desktop session — so anything involving real
rendering, focus, or assistive technology was written off as human-only work blocking the
first public release.

A spike on `windows-latest` disproved the assumption:

```
platformName        'windows'          (the real platform plugin, not offscreen)
screens             [('HyperVMonitor', 1024, 768)]
native HWND         328186
GetWindowTextW      'Tracks & Trails'  (the Windows API sees the window)
IsWindowVisible     True
screenshot          captured, with native Windows font rendering
```

### Decision

Treat the Windows runner as a **real, if headless-in-practice, Windows desktop**, and move
everything it can genuinely check out of the manual list and into CI. Specifically, these are
now **automatable and therefore required**, not optional:

- Rendering under the real `windows` platform plugin, with screenshots retained as evidence
- Keyboard navigation and focus order, asserted through synthetic key events
- Accessibility: every control's name and role as exposed to the UI Automation tree — the
  data a screen reader actually reads (`NFR-005`)
- Installer behavior: silent install, file and shortcut placement, uninstall and removal

**Native dialogs and shell integration are split, not dropped.** `OPS-003` listed "native file
dialogs, reveal in file manager, open file behavior" as human-only. An earlier draft of this
decision omitted them from both lists, which would have retired a tracked gap by accident
(`T031-R1`). They divide:

- **Automatable:** that the application *requests* the native dialog rather than Qt's
  fallback; that a chosen path is handled correctly; that "reveal" and "open" invoke the
  right shell verb with the right argument, asserted at the call boundary rather than by
  watching Explorer.
- **Human:** whether Explorer actually comes to the foreground, whether the dialog starts in
  a sensible directory, and whether the association Windows picks is the one the user expects.

These remain **genuinely human** and continue to block first release:

- Whether the rendering *looks* right, as opposed to matching a baseline
- Whether Narrator's announcements are *coherent*, as opposed to the tree being correct
- Whether the installer *feels* normal
- The foreground and shell-association half of native dialogs, reveal, and open
- Long-running stability under real use

**Nothing leaves the manual list until its replacement automation has landed and is green.**
Moving an item here on the strength of a plan, rather than a passing check, would reduce the
recorded gap without reducing the actual one.

### Rationale

The distinction that matters is not "GUI versus not". It is **objective versus subjective**.
Almost everything `OPS-003` labelled human was objective and merely assumed unreachable:
focus order is a sequence, an accessibility name is a string, an installed file either exists
or does not. What genuinely needs a person is aesthetic and experiential judgment, and that is
a far shorter list.

Getting this wrong was expensive in the direction that matters: it inflated the release-blocking
manual list and understated how much confidence CI could already provide on the platform with
no other coverage.

### Alternatives considered

- **Leave `OPS-003` as written** — rejected. Its core decision is sound but its factual claim
  is disproven, and `AGENTS.md` §7 forbids letting a known-wrong claim stand as project truth.
- **Rewrite `OPS-003` in place** — rejected. It is a historical record (`AGENTS.md` §6);
  superseding preserves what was believed and when.
- **Buy a cloud Windows desktop instead** — not rejected, and still wanted for the subjective
  residue. It is a complement, not a substitute: a rented desktop does not run on every push.

### Consequences

- `T-026` implements the expanded verification, less the installer half. On acceptance that
  half was split into `T-039`, because an installer only exists in Phase 5 and `T-026` is what
  closes Phase 0's remaining exit criterion — it has to be completable now.
- The pre-release manual Windows session (`ai/TESTING.md` §9) shrinks to the subjective list
  above, and should be rewritten when `T-026` lands.
- `REQUIREMENTS.md` §3's "known-unverified" wording for Windows becomes too broad once the
  objective half is automated.

---

## SEC-001 — No circumvention: DRM, paywalls, auth walls, and rate limits are out of scope

**Status:** Accepted
**Date:** 2026-07-25

### Context

A download GUI attracts feature requests for DRM stripping, paywall bypass, and
anti-detection. The line needs to be recorded once, up front, so it is not relitigated per
request or eroded incrementally.

### Decision

Adopt the exclusions `REQ-EXCL-001` … `REQ-EXCL-005` in `REQUIREMENTS.md` §8 as
non-negotiable product boundaries. `DRM_PROTECTED` is a **permanent** failure class that is
never retried and never worked around. Cookie support (`REQ-026`) exists solely to let a user
reach content they are already entitled to.

Per `AGENTS.md` §5, a direct user instruction does not silently override this. An agent asked
to implement circumvention says so and asks rather than complying.

### Rationale

These features change the tool's character from "access what you can already access, more
conveniently" to "defeat access controls" — a legal and ethical posture the project does not
take. Recording it as an accepted decision means the boundary is a documented project
constraint rather than a per-request judgment call.

### Alternatives considered

- **Say nothing and decide per request** — rejected; guarantees inconsistency and slow
  erosion.
- **Exclude DRM only** — rejected; paywall bypass and anti-detection raise the same issues.

### Consequences

- Certain feature requests are declined by policy, with this entry as the citation.
- `REQ-026` must be implemented narrowly: explicit user action naming a profile or file, no
  ambient credential discovery.
- The README states that download rights are the user's responsibility (`A-001`).

---

## LIC-001 — Project license: MIT

**Status:** Accepted
**Date:** 2026-07-25

### Context

Three licenses constrain the outcome: PySide6 is **LGPLv3** (`ARC-001`); the bundled Windows
ffmpeg build must be **LGPL** (`OPS-001`); yt-dlp is **Unlicense** (public domain, imposes
nothing).

### Decision

License the project source under the **MIT License**. Copyright holder: Sean Kottman.

The binding constraint, which MIT does not alter: **Qt and ffmpeg must be dynamically linked
and replaceable**, and their license texts must ship with every distributed artifact.

### Rationale

MIT imposes the least on anyone using the code, and nothing about this project argues for
more. Apache-2.0's patent grant addresses a risk that does not apply to a desktop wrapper
around an existing open-source tool. GPLv3's copyleft would restrict downstream reuse in
exchange for a benefit the project does not seek.

MIT is fully compatible with dynamically linked LGPLv3 dependencies. Permissive source
licensing does not conflict with LGPL linkage — the LGPL obligations attach to the
distributed binary, not to our source.

### Alternatives considered

- **Apache-2.0** — MIT plus an explicit patent grant and a change-notice requirement.
  Rejected: meaningfully longer for a benefit this project has no use for.
- **GPLv3** — the simplest story for LGPL dependencies, since copyleft subsumes them.
  Rejected: restricts downstream reuse with no offsetting gain here.

### Consequences

- **The source license and the artifact's obligations are different things.** MIT covers this
  repository. The distributed Windows installer bundles LGPLv3 Qt and LGPL ffmpeg, so the
  *artifact* still carries LGPL duties: ship the license texts, and keep those libraries
  dynamically linked so a user could substitute their own build. Both are true at once, and
  the release gate checks the second (`ai/TESTING.md` §8).
- Static linking of Qt is prohibited (`NFR-009`). Unchanged by this decision.
- Contributions are accepted under MIT; this should be stated when the repository goes public.
- `T-004` is complete. `LICENSE` exists at the repository root.

---

## OPS-003 — Windows verification is CI-only until a real Windows machine exists

**Status:** Accepted — **classification lists superseded by `OPS-004`** (2026-07-25)
**Date:** 2026-07-25

> **Correction, 2026-07-25.** The decision below stands: CI remains the only Windows
> verification mechanism. Its *classification* of what CI can verify does not. The
> "not automatable" list was written on the assumption that a CI runner offers no desktop
> session; a spike proved otherwise. See `OPS-004`. The original text is left intact as the
> historical record.

### Context

`C-003` requires Linux and Windows parity at every release, and `REQUIREMENTS.md` §3 makes
Windows a primary platform. The maintainer has **no Windows machine and no way to run a
Windows VM**. The only available Windows environment is a hosted CI runner.

This is a constraint to be worked around honestly, not a preference.

### Decision

Treat **CI as the primary and only Windows verification mechanism** for Phases 0–4.
Consequently, push as much verification as possible into automation rather than accepting it
as unverified, and track what genuinely cannot be automated as a known gap.

Automatable on a Windows runner, and therefore **required** rather than optional:

- Install, import, and construct a `QApplication` (offscreen) — `T-002`
- Full lint, type, and test suite — `T-006`
- Frozen build, launch, spawn a child, exit — `T-020`
- Orphaned-process assertions after cancel and after exit, checked programmatically
- Path handling: reserved device names, illegal characters, length limits, traversal attempts
- Installing the built artifact on a fresh runner and launching it — a CI runner **is** a
  clean machine, which covers `REL-001` more genuinely than it first appears
- Screenshot capture of key windows, as weak but non-zero visual evidence

Not automatable, and therefore **known-unverified on Windows**:

- Screen-reader announcement quality under Narrator (`NFR-005`)
- Native file dialogs, "reveal in file manager", "open file" behavior (`REQ-021`)
- Real interactive keyboard navigation and focus order
- Visual correctness of light and dark themes on a real desktop
- Installer UX and upgrade/uninstall flows
- Long-running stability under real use

### Rationale

The alternative — declaring Windows verified because tests passed — would be false. Naming
the gap keeps `REQUIREMENTS.md` §11 honest and turns "we have no Windows box" from an
invisible risk into a tracked one with a defined discharge point.

Pushing the automatable set into CI is not a consolation prize: process-orphan and
path-safety checks are more reliable as assertions than as a human watching Task Manager.

### Alternatives considered

- **Drop Windows to secondary support** — rejected. Windows is half the intended audience,
  and `OPS-001` (bundled ffmpeg) exists specifically for Windows users.
- **Declare Windows verified from CI alone** — rejected as dishonest reporting.
- **Cloud Windows desktop for manual passes** — viable and not rejected, just not currently
  available. Revisit before first public release.

### Consequences

- **Blocking before the first public release:** the "not automatable" list above must be
  discharged by a real Windows session — the maintainer's, a tester's, or a rented cloud
  desktop. Recorded as a Phase 5 release-gate item (`ai/TESTING.md` §8, §9).
- `T-006` is a bigger task than a typical CI setup, because CI is carrying verification load
  that manual testing would otherwise carry.
- Phase 4's accessibility exit criteria can be fully met on Linux only; the Windows half is
  deferred to that pre-release session.
- Any Windows-only defect will be found late. Accepted knowingly; `T-020` exists to catch the
  worst-known instance of that class in Phase 0.

---

## ARC-003 — "Versioned" in `ARC-002` means version-controlled, not version-negotiated

**Status:** **Accepted** (2026-07-26) — accepted as proposed, without amendment
**Date:** 2026-07-26
**Narrows:** one phrase in `ARC-002`'s consequences. The decision itself stands unchanged.

### Context

`ARC-002`'s consequences include:

> The IPC protocol is now a versioned internal contract with its own tests.

`T011-R5` found that this does not say what it requires. Read one way it is an obligation to
carry an explicit protocol version across the boundary; read another it says the protocol is
now a real API surface, maintained deliberately in version control and covered by tests.

The ambiguity is not academic. `T-011` implements no version field and no negotiation, and
`DECISIONS.md` outranks `TASKS.md` (`AGENTS.md` §5) — so under the first reading `T-011` is
non-compliant and cannot be approved, and under the second it complies as written. The
reviewer correctly declined to resolve it, and so did the Implementer: reading an accepted
decision's intent is a maintainer act.

### Decision

**Version-controlled.** `ARC-002` requires that the IPC protocol be a deliberate, tested
internal contract — one module, declared types, changed only alongside its tests. It does
**not** require a protocol version field, a handshake, compatibility ranges, or any runtime
negotiation between parent and child.

`downloader/protocol.py` as implemented in `T-011` satisfies `ARC-002`.

### Rationale

- **The phrase sits among obligations, not features.** Its neighbours in the same list are
  "everything crossing the boundary must be picklable", "worker modules must not import Qt",
  and "per-process startup cost is real". Every one is a cost the decision imposes. "With its
  own tests" is the operative clause, and it is satisfied.
- **`ARC-002` never discusses version skew.** Not in its context, rationale, or alternatives.
  When this project means version skew it says so at length — see `OPS-002`, which is entirely
  about a yt-dlp version the user can change underneath the application.
- **Skew is architecturally impossible.** `REL-001` ships one self-contained artifact, and
  `ARC-002` spawns the child from that same binary. There is no supported configuration in
  which a parent and child of different builds meet. `OPS-002`'s in-place update replaces
  yt-dlp — the *engine* — not this protocol, which is the application's own code.
- **A check that can never fail is a check nobody maintains.** Version machinery guarding an
  unreachable state is dead weight that later readers must still reason about.

### Alternatives considered

- **Leave the phrase ambiguous** — rejected. It blocks `T-011`'s approval indefinitely, and
  `AGENTS.md` §7 forbids leaving a known conflict standing as project truth.
- **Rewrite `ARC-002` in place** — rejected. It is historical record (`AGENTS.md` §6);
  narrowing by a separate entry preserves what was believed and when.
- **Add a `PROTOCOL_VERSION` constant asserted at worker startup** — *not unreasonable*, and
  rejected only on balance. It would cost about five lines, add no negotiation, and make the
  original wording literally true. It also catches one case that genuinely occurs: a developer
  running a worker from source against a stale installed build. Rejected because that is a
  development-workflow problem rather than a shipped-artifact one, and because a permanently
  passing assertion invites exactly the machinery this entry declines. **If the trigger below
  fires, this is the first thing to add.**
- **Implement real version negotiation** — rejected. Substantial machinery for a failure mode
  the architecture forbids.

### Consequences

- `T011-R5` closes on acceptance, and `T-011` becomes approvable on its current implementation.
- `downloader/protocol.py` keeps its narrow claim — no runtime negotiation — and may drop the
  note recording this conflict as unresolved.
- **This decision expires if parent and child ever become separately deployable.** A standalone
  worker binary, an external helper process, a plugin model, or any packaging in which the
  child is not spawned from the parent's own artifact makes skew reachable and re-opens the
  question. Whoever proposes such a change must revisit this entry rather than discovering the
  gap at runtime.

## DAT-002 — Filename sanitizing promises idempotence, not uniqueness

**Status:** **Accepted** (2026-07-26) — maintainer decision on a blocking review finding
**Date:** 2026-07-26
**Narrows:** one acceptance criterion of `T-045`. `ARCHITECTURE.md` §8 stands unchanged.

### Context

`T-045` replaced the bare `_` used to defuse a Windows reserved name with the same digest the
truncation differentiator uses, so `COM1` became `COM1-<16 hex>` and stopped colliding with a
legal file named `COM1_`. Its first acceptance criterion read:

> Defusing a reserved name cannot produce a path that a legal filename also produces

`T045-R1` established that this cannot be satisfied while `sanitize_component` stays idempotent,
and the argument is not about hashing. For any reserved `x`, let `y = sanitize_component(x)`.
`y` is legal input in its own right, and idempotence requires `sanitize_component(y) == y`.
Therefore `x` and `y` map to the same path, whatever the renaming strategy. The digest changes
*which* legal name collides — from the plausible `COM1_` to the 16-hex-digit
`CON-1bc43d851d28ada0` — but cannot eliminate the collision.

The two criteria are individually reasonable and jointly unreachable. Choosing between them is a
product decision, not an implementation one, so the reviewer returned **Blocked** rather than
Changes requested.

### Decision

**Keep idempotence. Narrow the uniqueness promise to the plausible neighbour class.**

`sanitize_component` guarantees that a defused reserved name does not collide with the name a
user would realistically also hold — `COM1` versus `COM1_`. It does **not** guarantee collision
with nothing.

**Amended 2026-07-26 (`T045-R3`).** This entry first said the residual colliding set was "pinned
by test". That was an overclaim, and the test making it checked six hand-picked candidates and
called the result exact — `defused + " "`, `defused + "."` and control-character forms such as
`"CON\t"` all collide too. Normalization is many-to-one *by design*: control-character
stripping, trailing dot and space removal, and reserved-name defusing each merge inputs
deliberately, and every merge widens the class. What the test pins is what holds — the defused
output is a fixed point, the plausible neighbour stays distinct, and the class is demonstrably
wider than the reserved name alone. The colliding set is **not** enumerated, and this decision
does not claim it is.

**Absolute uniqueness moves to `T-046`** (Phase 2, alongside resume), where collision policy has
the filesystem context the guarantee actually requires.

### Rationale

- **Idempotence is load-bearing and uniqueness is not, at this layer.** `T-012` renders a path
  preview under `REQ-011` and writes later. If sanitizing were not a fixed point, the preview and
  the write could disagree — the user is shown one filename and gets another. That is a silent
  wrong result in what this product exists to do, which `AGENTS.md` §9 rates Critical. The
  residual collision, by contrast, requires a user to name a file `CON-1bc43d851d28ada0`.
- **Uniqueness is unanswerable without state.** "Does this path collide with something?" is a
  question about the filesystem. A pure function of one string cannot answer it, and pretending
  otherwise is what produced an unreachable criterion in the first place.
- **What can be asserted is asserted; what cannot is said plainly.** `T-045`'s tests pin the
  fixed point and the plausible-neighbour distinction, and demonstrate that the colliding class
  is wider than the reserved name alone. They do not enumerate it, and neither does this entry.

### Alternatives considered

- **Drop idempotence, keep absolute uniqueness** — rejected. It buys a guarantee no user
  realistically needs at the cost of the preview/write agreement `T-012` depends on: applying a
  non-idempotent sanitizer twice returns a different path, so the previewed filename and the
  written one diverge. *(An earlier draft said this would make sanitizing "non-deterministic
  across processes". That was wrong — a non-idempotent function can be perfectly deterministic,
  and determinism is not what the rejection turns on. Corrected under `T045-R3`.)*
- **Leave both criteria and mark `T-045` permanently Blocked** — rejected. `AGENTS.md` §7
  forbids leaving a known contradiction standing as project truth, and the implementation under
  review is a real improvement over the bare `_` regardless of how the criterion is worded.
- **Rewrite the criterion silently in `TASKS.md`** — rejected. This is a durable choice with a
  real trade-off between two safety properties, which is what `AGENTS.md` §11 says belongs here
  rather than in a task edit nobody can find later.
- **Reject reserved names outright instead of renaming them** — rejected. `REQ-011` requires a
  download to succeed from a title the user did not choose; failing on `CON` would turn a
  cosmetic problem into a lost download.

### Consequences

- `T045-R1` closes on acceptance; `T-045` becomes approvable on its current implementation with
  its narrowed criterion, and needs one focused re-review.
- `T-046` is filed and owns the real uniqueness guarantee. **This decision assumes it lands
  before first release** — until it does, two downloads whose titles sanitize identically still
  contend for one path, which is the ordinary collision case and not specific to reserved names.
- `core/paths.py` keeps its narrow claim: legal on both platforms, deterministic, idempotent.
  Any future change making it stateful or filesystem-aware re-opens this entry.

## DAT-003 — A stored diagnostic is verbatim; cookie paths inside one are accepted

**Status:** **Accepted** (2026-07-26) — maintainer decision on a Critical review finding
**Date:** 2026-07-26
**Narrows:** one clause of `REQ-026`, and one acceptance criterion of `T-014`.

### Context

`T-014` stores a failed job's `error_message`. Two requirements pull against each other there:

- `NFR-006`, `ARCHITECTURE.md` §5 and §7, `core/models.py` and `downloader/protocol.py` all
  require the extractor's original message, preserved rather than paraphrased.
- `REQ-026` says credentials and cookie paths are never written to logs **or to history**.

An attempt to satisfy the second by replacing the message with project-authored text violated the
first in four places (`T014-R7`). Two earlier attempts to scrub the prose with a recogniser both
failed — one also corrupted legitimate output paths, which was independently Critical.

**Credentials are no longer the issue.** `DownloadRequest` now rejects a proxy carrying userinfo,
so a job cannot hold one; that half of `REQ-026` is structurally guaranteed rather than filtered.
What remains is narrower: yt-dlp may name a browser cookie database in a diagnostic — for example
when a profile cannot be read — and that path is stored verbatim with the message.

### Decision

**The database stores the extractor's message verbatim, and a cookie *path* appearing inside one
is accepted.** `REQ-026`'s exclusion is read as binding on values this application *supplies* —
credentials and cookie file paths it holds, passes, or logs deliberately — not on text a third
party emits and `NFR-006` requires be preserved intact.

Scope, precisely:

- **Credentials** — never in the database. Structural: unrepresentable in the model.
- **Cookie contents** — never in the database. Nothing reads a cookie jar into a job.
- **Cookie paths supplied by this application** — none exist. `DownloadRequest` carries
  `cookies_from_browser`, a browser *name*, not a path.
- **Cookie paths echoed by yt-dlp inside a diagnostic** — **accepted**, and the only residue.

### Rationale

- **The alternative was worse and was tried twice.** Scrubbing prose neither excluded every
  secret nor left the message intact, and the second attempt turned a user's output directory
  into a relative path — a write outside the directory they chose.
- **A path is not a credential.** It names a file on the user's own machine. Its disclosure value
  is low, the database is local and user-owned, and the user can already see the path.
- **Losing the message costs more.** `NFR-006` exists because a paraphrased error destroys the
  only information a user can act on, and `REQ-019` shows that message back to them.
- **Silence was the real defect.** This trade-off was made when the diagnostic was restored and
  simply never written down, which is what `T014-R1`'s final round reported.

### Alternatives considered

- **Keep the generic stored message** — rejected as `T014-R7`: it contradicts four approved
  sources at once.
- **Scrub prose before storing** — rejected on evidence. Two implementations, three credential
  escapes, one Critical regression.
- **Drop `error_message` from the schema this phase** — rejected: `REQ-018` requires the error be
  recorded, and the per-job log that would hold it does not exist until `T-038`.

### Consequences

- `REQ-026` gains a note scoping its exclusion; `T-014`'s criterion is amended to match. Neither
  is weakened silently.
- **`T-038` still owns log redaction**, and its scope is unchanged — logs are written by this
  application, so the supplied-value rule binds there in full.
- **This decision reopens** if the database stops being local and user-owned — sync, export,
  cloud backup, or a bug report attaching it — because the disclosure calculus above depends on
  it. Whoever proposes such a feature revisits this entry.

### Amended 2026-07-30 — the boundary is provenance, and the table above overstated it (`T-049`)

**Status:** **Accepted** (2026-07-30) — maintainer decision
**Amends:** the *Decision* section's scope table and its "only residue" claim. The decision itself —
verbatim storage, with `REQ-026` read as binding on values this application supplies — is unchanged
and is what everything below rests on.

**Amended rather than rewritten in place.** `T-049` asked for the table to be rewritten; `AGENTS.md`
§6 makes `ai/DECISIONS.md` a historical record that is appended to and never silently rewritten. The
superseded rows stay above so the overstatement is visible, which is the point of finding it.

#### Three things the table got wrong

**1. "Credentials — never in the database. Structural: unrepresentable in the model" is false.**
`DownloadRequest` rejects userinfo in `proxy` and **not** in `url`. Measured 2026-07-30:
`DownloadRequest(url="https://alice:s3cret@example.com/v", …)` is accepted, and
`persistence/repositories.py` stores the job URL **verbatim on purpose** — *"because it **is** the
job; `REQ-012`'s queue and `REQ-020`'s history are both unusable without it, and a retry cannot
reconstruct it."* So a credential the **user typed into a URL** can be in the database. It is not
one this application supplies, which is why the decision still holds — but the guarantee was stated
one level too strongly.

**2. `cookies_from_browser` is a browser *name* by intent, not by construction.** The table says
"a browser *name*, not a path". The model requires only non-empty text: measured,
`cookies_from_browser="/home/u/.mozilla/cookies.sqlite"` is accepted. Nothing supplies a path today,
so no path reaches the database — but "none exist" describes current callers, not an invariant.

**3. "the only residue" cannot be established.** It is an exhaustive claim about the contents of
arbitrary third-party prose. yt-dlp can name anything in a diagnostic, and no reading of its source
at one version bounds what a later one says. This is the enumeration failure `T-044`, `T-045` and
`T-014` each produced and `ai/TESTING.md` §13 records — an enumerated set treated as complete.

#### The boundary, stated as provenance

`REQ-026`'s exclusion binds on **who put the value there**, not on what the value looks like:

| Provenance | In the database? | How that is guaranteed |
|---|---|---|
| **Values this application supplies** — a proxy's credentials, a cookie path it holds or passes, cookie contents | **Never** | Structural for proxy userinfo (unrepresentable). By construction for cookies: nothing reads a jar, and nothing supplies a path |
| **Values the user typed** — a source URL, which may carry userinfo | **Yes, verbatim** | Deliberate. The URL *is* the job; a retry cannot reconstruct it. Not this application's secret to withhold from the user's own local database |
| **Prose a third party emitted** — any yt-dlp diagnostic | **Yes, verbatim** | `NFR-006` requires it intact. **No claim is made about what it may contain** |

**What replaced the exhaustive claim:** nothing enumerates. The guarantee is about the first row and
is silent about the third by design, which is the only form of it that two failed recognisers did not
already disprove.

#### `T-038` is unchanged and origin-agnostic

Every log this application **emits** is redacted, whatever the provenance of the text inside it.
That is not in tension with the table: storage and emission are different sinks with different
rules, and the supplied-value rule binds emission in full. A yt-dlp diagnostic stored verbatim in
the database is still redacted on its way into a log file.

#### Reopening conditions, extended

The original condition stands — sync, export, cloud backup, or a bug report attaching the database.
Added:

- **Cookie-file support.** `REQ-026` already promises it. The moment the application holds a cookie
  *file path*, row one of the table above acquires a member it does not have today, and this decision
  must be revisited **before** that lands, not after.
- **Any other secret-bearing persisted field**, by the same reasoning.
- **Constraining `url` or `cookies_from_browser` at construction.** If either gains a validator, the
  "by intent, not by construction" caveats above become real invariants and this entry should say so.
  That is a `T-049`-adjacent change, not part of it — `T-049` is explicitly barred from touching
  `T-014`'s approved persistence code or the model.


### Amended 2026-08-10 — cookie files land, and the path never enters the model (`T-197`)

**Status:** **Accepted** (2026-08-10) — maintainer ruling, taken **before** cookie-file support
lands, which is what the condition above requires. Asked as four explicit questions with the
alternatives stated; the answers are recorded here as the maintainer's.
**Amends:** the provenance table's first row, and the two reopening conditions this ruling takes.
**Does not amend** the decision itself — verbatim storage, with `REQ-026` read as binding on values
this application supplies. That is unchanged and is still what everything rests on.

#### Why this was needed before any code

`T-197`'s entry says re-opening this decision is out of its scope. **That line is wrong**, and
`AGENTS.md` §5 is why: this file outranks `ai/TASKS.md`, and the condition above says the decision
*"must be revisited **before** [cookie-file support] lands, not after"*. Two of `T-197`'s central
criteria trip conditions — a cookie file path is row one acquiring its first member, and a
validator on `cookies_from_browser` is the second trigger by name. The task entry is corrected
rather than this one bent to fit it.

#### The ruling

1. **Cookie-file support lands in Phase 4**, as `T-197` is filed. `REQ-026` already promises *"a
   browser profile or a cookies file"*, so deferring would leave an approved requirement half
   built with nothing recording why.
2. **The path is settings-only and never enters `DownloadRequest`.** It lives in `settings.toml`
   and the adapter reads it when a session is spawned. The model does not carry it, so it cannot
   reach the database through a job at all.
3. **`cookies_from_browser` gains a validator** and must be a browser name.

#### What row one now says, and how

| Provenance | In the database? | How that is guaranteed |
|---|---|---|
| **A cookie file path this application holds** | **Never** | **Structural.** `DownloadRequest` has no field for it; a job cannot carry one. The value exists in `settings.toml` and in the arguments handed to a worker process, neither of which is the queue database |
| **A browser name this application supplies** | Yes, as a name | **By construction now, not by intent** — the validator above closes the caveat `T-049` recorded. A path typed into that field is refused rather than travelling through a field the redaction reasoning assumes is a name |

**Chosen against the two alternatives, both stated when the ruling was taken.** Letting the path
into `DownloadRequest` and relying on the redaction gate would make row one a *filtered* promise
rather than a structural one — the shape this entry twice records failing, at the cost of two
recognisers, three credential escapes and one Critical. Holding it in the request and stripping it
before storage would keep it out of the database while making the guarantee *"someone remembered to
strip it"* at every persistence path, which is a field that must be forgotten.

**What this costs, stated:** the adapter reads the cookie path from settings rather than from the
request, so a worker's arguments are no longer derivable from the job row alone. That is a real
loss of one property — a queued job no longer fully describes its own invocation — and it is
accepted deliberately, because the alternative is the guarantee above stopping being structural.

#### When each half of the credential is decided (maintainer ruling, 2026-08-10)

**Reading the path at spawn means a queued job authenticates with whatever cookie file is set when
it *starts*, not when it was queued.** That follows from the ruling rather than being chosen
separately, and it was not stated in the first drafting — the review asked for it explicitly, and
an entailed consequence nobody wrote down is the silence this decision exists to have stopped.

The two halves of `REQ-026` therefore bind at different moments, and the ruling is that **this is
correct and deliberate**:

| Half | Where it lives | When it is decided |
|---|---|---|
| **A browser profile** (`cookies_from_browser`) | `DownloadRequest`, and `Preset` | **When the job is queued.** It is a per-download choice a preset can carry (`T159-R1`) |
| **A cookie file** | `settings.toml` | **When the worker starts.** It is machine configuration, and row one forbids the job carrying it |

**What that means for a user, stated plainly because it is a surprise otherwise:** changing or
clearing the cookie file changes authentication for **everything already queued and not yet
started**. Clearing it is the case that reads best — the user said *stop using my cookies*, and
every job that has not run yet obeys. Switching from one file to another is the case that reads
worst, and it is the price of the guarantee.

**The alternatives, and why each loses.** Moving the browser name into settings as well would make
the two halves consistent, and would remove a per-preset capability `T159-R1` records as
deliberate — a change to approved behaviour far beyond `T-197`. Snapshotting the file path into
each job would fix authentication at queue time, and requires the path in `DownloadRequest`, which
is the thing this ruling exists to prevent.

#### Reopening conditions, as they now stand

The original three stand — sync, export, cloud backup, or a bug report attaching the database —
and *"any other secret-bearing persisted field"* stands. Two are **taken** by this ruling and are
no longer pending: cookie-file support, and constraining `cookies_from_browser`. Added:

- **A cookie path reaching any sink in the table below.** The condition is the table, not a
  property — twice now a property has contradicted the ruling it was written beside. The first
  drafting said *"any durable record"*, and `settings.toml` is durable and is where the path is
  meant to live. The second said *"a sink other than `settings.toml`"*, which still forbade the
  worker arguments the very next sentence authorises. **There are two authorised sinks — that file
  and the arguments handed to a worker process — and everything else is named here rather than
  implied:**

  | Sink | Why it is forbidden |
  |---|---|
  | `DownloadRequest`, and so the `jobs` row | Row one of the table above is structural only while the model cannot carry the value |
  | `error_message`, or any stored diagnostic this application composes | The verbatim-storage rule protects *third-party* prose; a path we wrote into a message is a value we supplied |
  | Any log this application emits | `T-038` binds emission in full, whatever the provenance of the text |
  | Any future export, sync, backup, or bug-report bundle | The original reopening conditions already cover these; this row is the reminder that a cookie path makes them sharper |

  Reaching any of those is what puts this decision back to being a filtered promise, and it must
  then say so.
- **Constraining `url`.** Still untaken, and still the remaining half of `T-049`'s caveat: a
  credential the user typed into a URL is in the database today, deliberately.


---

## SEC-002 — A fixture commits values only for the fields the projection reads

**Status:** **Accepted** (2026-07-27), **amended the same day** — maintainer decisions on a
Critical review finding
**Date:** 2026-07-27
**Narrows:** the scope of what `tests/fixtures/capture.py` writes, and one acceptance criterion
of `T-018`.

> **Amendment, 2026-07-27 — the schema fingerprint is removed, not sanitized.**
>
> The original decision below kept a value-free fingerprint of the discarded data as `NFR-008`
> churn evidence. That record was not value-free. **A mapping key is captured data**, and
> `schema_fingerprint()` copied every key verbatim: `{"unknown_map": {"<a secret>": "ignored"}}`
> wrote the secret to disk while the key gate, the schema-leaf check and the text scanner all
> reported the file clean. Nested maps are routinely keyed by data — a header name, an
> identifier, a token — so "names are schema, values are data" was simply the wrong line.
>
> The fingerprint is **deleted** rather than made name-free. A record that can say only
> "a mapping of nine things, one of them a list" identifies nothing that changed, and counts
> churn on every yt-dlp release, so it would have been a noisy test somebody eventually removed
> — while remaining a second place data could appear. Hashing was rejected too: the material at
> risk is low-entropy personal data, which a hash does not protect.
>
> Two consequences of the same amendment, from the same review:
>
> - **`write()` derives everything it writes.** It used to accept a caller-supplied `_schema`,
>   so a value that had never been through the allowlist reached disk. Nothing outside
>   `_fixture`, `info_dict` and `error` is carried, and those three are rebuilt, not copied.
> - **A playlist entry is a count.** `ytdlp_adapter` reads `len(entries)` and never looks inside
>   one, but capture recursed into each entry and kept its consumed fields — the largest body of
>   retained data in the fixture set, held for no reader. Entries are now placeholders.
>
> **What this gives up, deliberately:** detection of an upstream rename in a field the adapter
> never reads. That was the fingerprint's only unique job. A rename of a field the adapter *does*
> read still fails the projection tests, and the AST-derived allowlist test still fails when the
> adapter starts reading something the fixtures cannot carry. `NFR-008`'s canary is narrower now
> and honest about its range.

### Context

`T-018` records real yt-dlp `info_dict`s as fixtures. The original design committed the **whole
raw dict** and protected it with a recogniser: a list of credential-ish key markers, plus an
independent scanner over the committed file.

`T018-R1` reported that recogniser false-negative four times, and each correction closed the
reported spellings and left another the rule had not been written to see:

1. tuples, which `redact()` never walked, and which cannot appear in JSON at all;
2. capture-owned metadata written raw, non-`C:` Windows profiles, URL fragments;
3. a key named exactly `auth`, and a UNC share that is itself the profile root;
4. `passwd`, `passphrase`, `private_key`, `accessKey` — and five names the *sanitizer*
   recognised that the independent gate did not.

The reviewer declined to return it for a fifth marker list, on the grounds that three batches had
already established the defect class: **an open-ended namespace protected by a recogniser whose
accepted complement is treated as safe.** Under `AGENTS.md` §9 an agent may not close a Critical
as accepted risk, and continuing with the raw dict required exactly that. The decision was
escalated.

### Decision

**A fixture commits values only for fields `downloader/ytdlp_adapter.py` demonstrably reads**,
plus the reviewed provenance and error fields. Every other key is dropped before serialization.

- The allowlist is derived from the adapter's real reads, and a test re-derives it from the
  adapter's AST — so a field the adapter starts reading fails the suite until it is listed.
- URL-valued allowed fields still lose query, userinfo and fragment. The path and key patterns
  stay as defence in depth, not as the primary control.
- ~~**Upstream churn evidence is preserved without preserving unknown values**: alongside the
  allowlisted projection input, each fixture records a value-free recursive schema fingerprint
  of the discarded raw data — key names, container shape, scalar *type*, no scalar values. A
  yt-dlp shape change is still visible; an unfamiliar key cannot carry its value into git.~~
  **Struck by the amendment above**: key names are captured data, so this was never true. The
  fingerprint is removed; nothing about a dropped key is kept.

### Rationale

- **It makes the next leak spelling irrelevant by construction.** The question stops being "did
  we think of this key?" and becomes "does the adapter read it?", which has a checkable answer.
- **It is the same lesson three times over.** `T-014` made a proxy credential unrepresentable
  rather than strippable; `T-044` read the interpreter's namespace instead of parsing for it;
  `T-045` dropped a completeness claim it could not keep. Constrain the input, do not filter it.
- **The cost is small and was measured.** The fixture is a pinned contract for the projection,
  and the projection reads a small, known set of fields. The playlist fixture fell from 45 KB to
  12 KB; no projection test lost its subject.
- **A committed leak is permanent.** The consequence is irreversible in a way that justifies
  discarding data of unproven value.

### Alternatives considered

- **A fifth marker list** — rejected on the reviewer's evidence. Four passes, four escapes.
- **Keep the raw dict and accept the risk** — rejected, and not available to an agent anyway:
  `AGENTS.md` §9 reserves that to the maintainer, and the maintainer declined it here.
- **Encrypt or externalise the fixtures** — rejected: it keeps the secret material in the
  project's custody and adds a key to manage, without making any single fixture safer to read.

### Consequences

- **A fixture no longer proves what yt-dlp returned, only what this project consumes of it.**
  A field the adapter never reads changing shape — or name, after the amendment — is
  deliberately not a test failure. What still fails is a rename of a field the adapter *does*
  read (the projection tests) and the adapter reading something the fixtures cannot carry (the
  AST-derived allowlist test).
- **Adding an adapter read is a two-step change**: extend the allowlist, then re-capture. The
  AST test makes forgetting the first step fail loudly rather than silently drop data.
- **`T-012`'s `archive_org_big_buck_bunny` was force-refreshed** by this policy, because its
  committed provenance described a redaction policy that no longer holds. Two of its assertions
  moved from "the value is `<redacted>`" to "the key is absent".
- **This decision reopens** if a fixture is ever needed to prove something the adapter does not
  read — a reproduction case for an upstream bug, say. That fixture needs its own handling, not
  a widening of this rule.

---


### Amended 2026-08-04 — a playlist entry is a record, not a count

**Ruled by the maintainer.** A fixture may now keep, **per playlist entry**, the four facts the
adapter reads off one: its address, its title, its duration and its thumbnail. Everything else
about an entry is still dropped by the same mechanism as everywhere else.

**The rule did not change; what the projection reads did.** This decision has always said "values
only for the fields the projection reads", and `capture.py` blanked entries to `{}` because
`ytdlp_adapter` took `len(entries)` and never looked inside one — `T018-R1` found each entry's
title and uploader being retained for no reader, and removing them was correct at the time.
`T-137` makes a playlist expand into one job per entry, so there is now a reader for four of those
fields and none for the rest.

**The gate is what forced the question rather than letting it drift.**
`test_the_allowlist_matches_what_the_adapter_actually_reads` walks the adapter's AST and refuses a
field it reads that fixtures drop, so `T-137` could not be finished without answering this. That
is the gate working: the coupling between "what the code consumes" and "what the fixtures retain"
is machine-checked, and a task cannot quietly widen one without the other.

**What is knowingly accepted.** A committed fixture for a playlist now carries every entry's URL
and title, permanently and in the repository. That is more than a count, and it is the same class
of data the fixture already keeps about the top-level item — where it is and what it is called. The
alternative was considered and declined: with entries blank, **no recorded fixture can exercise
playlist expansion at all**, so `T-137`'s projection tests would be built from literal info dicts
indefinitely, and the feature with the widest blast radius in Phase 3 would have no recording
behind it.

**Unchanged:** `uploader`, `description`, cookies and every other key are still dropped from an
entry, and `test_a_playlist_entry_keeps_only_what_the_adapter_reads` watches the hostile ones fail
to survive.

## ARC-004 — A probed job downloads from `READY`; the download re-extracts, it does not re-probe

**Status:** **Accepted**
**Date:** 2026-07-27
**Decides:** `T-051`. **Blocks were:** `T-016`.
**Supersedes:** nothing. **Amends:** `ARCHITECTURE.md` §5's prose, not its diagram.

### Context

`T-016` probes a URL, shows the user what it is, lets them pick a preset, and then downloads it.
That flow needs a job to go from a finished probe to a running download, and `T-013`'s review
found it could not:

- `DownloadManager.start()` accepts only a `QUEUED` job, and unconditionally advances it to
  `PROBING`;
- a probe session leaves the job in `READY`;
- `READY → PROBING` is not an edge, and `_advance()` refuses to walk backwards.

So the probed job cannot be started, and creating a second job for the download would either
strand the probed record or duplicate it. The T-013 reviewer was right to refuse to invent the
edge in the manager: source code silently creating architecture is how the executable state
machine and the approved design come to disagree.

Two designs were available: allow a probed job to be probed again (a new `READY → PROBING`
edge), or start the download from `READY` and let its own extraction stand in for the probe.

### Decision

**A download starts from `READY` as well as from `QUEUED`, and never re-enters `PROBING`.**

- `DownloadManager.start(job_id, kind=DOWNLOAD)` accepts a job in `QUEUED` **or** `READY`, and
  sets the status that says a worker holds it: `PROBING` from `QUEUED`, `RUNNING` from `READY`.
  Both edges already exist; no new edge is added.
- **The download session always extracts again.** This is not a choice — `YoutubeDL.download()`
  resolves the URL itself, and there is no way to hand it a previous extraction. So the *bytes*
  are never fetched against stale metadata, whatever the age of the probe.
- **The probe's metadata is what the user was shown, and it stands** until something contradicts
  it. A download session reports no `Probed` outcome, so the recorded title does not change
  mid-download.
- **Stale metadata surfaces as an ordinary failure, in the extractor's own words.** If the site
  changed so that the chosen format no longer resolves, yt-dlp says so and `REQ-005`/`NFR-006`
  carry that message through verbatim. There is no freshness timer, no re-probe prompt, and no
  expiry on `READY`.

### Rationale

- **The honest reading of `PROBING` is "probing on the user's behalf".** A download's internal
  extraction is not that; it is the first step of downloading. Modelling it as a state would mean
  the status line said "probing" for a job the user had already told to download.
- **A `READY → PROBING` edge would make `READY` meaningless.** It is the state that says "this
  job is resolved and waiting"; an edge back out of it says nothing is ever resolved.
- **The staleness question mostly dissolves.** The only thing that can be stale is what is
  *displayed*, because the download re-resolves regardless. Guarding displayed text with a
  freshness timer would add a mechanism whose failure mode (a spurious re-probe, a dialog the
  user did not ask for) is worse than the one it prevents (a title that changed since Tuesday).
- **It keeps one invariant worth having:** a job with a live session is `PROBING` or `RUNNING`.
  The manager's active set and the persisted status cannot disagree about work in flight.

### Alternatives considered

- **Add `READY → PROBING`** — rejected above. It also reopens `T-013`'s "one terminal outcome per
  session" reasoning, because a job could then accumulate probe outcomes without downloading.
- **Discard the probed job and create a fresh one at download time** — rejected: the probed row
  is what `REQ-012` persisted, and abandoning it loses the queue position and the created time,
  or duplicates the job in the user's list.
- **Probe results live only in the dialog, never as a job** — rejected: `REQ-012` requires a
  queued job to survive a crash immediately after queuing, and a probe that is not persisted
  cannot be resumed or retried.
- **Expire `READY` after some interval** — rejected as a mechanism with no reader. Nothing acts
  on the age of a probe, and the download re-resolves anyway.

### Consequences

- **`T-016` owns the code change**, not this decision (`T-051` is a Planner task and changes no
  source). Concretely: `DownloadManager.start()` accepts `READY`, chooses the session-start
  status from the current one, and its docstring — which currently says the flow "needs the state
  machine amended first" — is replaced by a pointer here.
- **`T-013`'s manager contract is amended, not corrected.** Refusing a `READY` job was right at
  the time and is recorded as such; the refusal narrows rather than disappears.
- **A second probe of the same job is still impossible**, and stays impossible. Re-probing means
  a new job.
- **This decision reopens** if a probe ever becomes expensive enough to be worth reusing inside
  the download — a paid API, a rate-limited extractor, an interactive auth step. Then the
  question becomes how to hand an extraction to the worker, which is a protocol change and not
  this one.

---

## ARC-005 — The GUI thread never waits on SQLite; one writer thread owns every queue write

**Status:** **Accepted**
**Date:** 2026-07-27
**Decides:** `T-055`. **Blocks were:** `T-016` (`T016-R3`).
**Supersedes:** nothing. **Amends:** `ARCHITECTURE.md` §3 and §8, which said persistence is
injected but never said on which thread it runs.

### Context

`T-016`'s review found the first widget to touch persistence doing it synchronously on the GUI
thread. `JobRepository.next_queue_position()` and `add()` were called straight from button slots,
once per URL. With another connection holding SQLite's writer lock, the reviewer measured
**0.302 s** of blocked GUI thread followed by an `OperationalError` that reached no user.

`NFR-001` is unqualified — "UI thread is never blocked on network, **disk**, or subprocess
work" — and `ARCHITECTURE.md` §8 repeats it. So the widget was wrong. But *how* the application
writes without blocking was never decided: §3 says `DownloadManager` is given a repository, and
says nothing about threads. `persistence/db.connect()` uses `sqlite3.connect()` with the default
`check_same_thread=True`, so a repository built on the GUI thread **cannot be called from another
thread at all**. Fixing this inside a widget would have set application-wide policy from the
narrowest possible place, which is what `AGENTS.md` §5 forbids and what `T-051`/`ARC-004` exists
as the precedent against.

### The decision

**Queue writes happen on one dedicated writer thread that owns its own connection. The GUI
thread submits and is told the answer later; it never waits.**

Three parts, and each is load-bearing:

- **One writer, not a connection per caller.** SQLite permits exactly one writer at a time
  regardless, so serialising in-process removes self-contention entirely rather than converting
  it into `SQLITE_BUSY` retries. It also gives queue positions a single ordering authority —
  two threads racing `MAX(queue_position) + 1` would otherwise hand out the same position.
- **The connection is opened inside that thread**, from an injected factory rather than handed
  over. `check_same_thread=True` stays on, so a connection used from the wrong thread raises
  instead of corrupting quietly. Nothing about this decision weakens that check.
- **A batch is one transaction.** `JobRepository.append()` takes every job of one interaction,
  reads the next position, and inserts them with a single `executemany`. The previous shape —
  a `SELECT` and an `INSERT` with its own commit per URL — made a pasted batch's cost unbounded
  in the number of round trips.

**Submission is asynchronous and its result is reported back on the GUI thread.** The caller
passes a completion callback; success and failure both arrive there, so a write that fails is
surfaced rather than swallowed. `REQ-012`'s persist-before-close ordering is *preserved and
strengthened*: a dialog now closes **in** the success callback, so it cannot close before the
rows exist, and on failure it stays open with the user's input intact.

### Considered and rejected

- **A connection per thread.** Simpler to write, and WAL supports it. Rejected because it turns
  our own concurrency into lock contention we then have to tune a `busy_timeout` against, and
  because it leaves `queue_position` allocation racy between threads.
- **Keeping writes synchronous and carving `NFR-001` down** to exclude "fast local disk". The
  measurement is the answer: 0.302 s is not fast, contention is not exotic — a second
  application instance, a backup, or an antivirus scan produces it — and the failure mode was an
  unhandled exception, not a slow success. A carve-out would have been documenting a known
  freeze.
- **Making the whole repository asynchronous.** Reads on the GUI thread are indexed
  single-row lookups against a local file and are not what blocked. Making every read a callback
  would spread asynchrony through every widget to fix a problem only writes have.

### Amended 2026-07-27 — "every queue write" means the manager's too

The first implementation moved only `append` to the writer thread. `DownloadManager` kept calling
a synchronous `JobRepository.update()` for every start, cancel, stage change, success and failure,
so `T016-R3` remained open: the GUI thread blocked for a measured **5.017 s** under a held writer
lock and then raised an uncaught `OperationalError`, and `close()` itself waited 4.921 s.

Three clarifications, all now implemented:

- **`revise()` joins `submit()` on the same thread.** One writer means every queue write, not the
  new ones. Ordering between an append and a later revision is guaranteed by their sharing one
  receiver.
- **`JobStore.get` must reflect a queued `update` immediately.** `PersistentJobStore` keeps a
  write-through view for exactly this. Without it, asynchronous updates would have meant
  restructuring ten call sites of approved `T-013` code, because the manager reads a job back
  before advancing it. With it, only the announcement moved into a callback — `T-013`'s
  persist-then-signal ordering is preserved, and a failed write emits `persistence_failed`
  rather than raising into a slot.
- **Shutdown is a lifecycle, not a call.** `close()` returns immediately and reports completion
  through `closed`. `QThread.wait()` on the GUI thread is the defect `T013-R2` already ruled on
  for the manager; reintroducing it one layer down was the same mistake with a new owner.

### Amended 2026-07-28 — "only the announcement moved" was not true, and "callers unchanged" cost the most

The amendment above is corrected rather than removed, because what it got wrong is the useful
part. It claimed that a write-through view let asynchrony land without touching the manager's
call sites — *"only the announcement moved into a callback"*, *"ten call sites of approved
`T-013` code"* left alone. The third `T016-R3` review established that the equivalence does not
hold, and the correction this amendment describes is the one that rejects it.

**A synchronous write sequenced every following effect for free. An asynchronous one sequences
nothing.** Leaving the callers unchanged therefore did not preserve their behaviour; it preserved
their *text* while removing the ordering underneath it. Three consequences, each measured:

- **A queued value is not a durable one.** The view exists so a caller can read its own pending
  write, and the manager began treating that read as completion: a second progress message saw
  the `RUNNING` its predecessor had only queued, concluded there was nothing to persist, and
  announced while the row still said `PROBING`.
- **A queued write can still fail**, so a value read back from the view may describe a state
  nothing ever reached. Holding the newest value and rolling back to the one it displaced is
  correct for one failure and wrong for two — the reviewer measured SQLite at `QUEUED` while the
  store answered `PROBING`. `PersistentJobStore` now holds the revisions that are **in flight**
  and forgets each the moment it settles, so once nothing is queued the database is the only
  answer. That is a smaller claim than a cache, and it is one the disk can keep.
- **A start is not a session.** `start()` returns once its transition is queued, so cancellation,
  shutdown and `is_idle` all have to know about a start that exists but has no worker. The first
  version knew about it only as a lock against a second start; a cancel therefore wrote
  `CANCELLED` and the pending start still spawned.

So the decision gains a fourth load-bearing part:

- **Per job, writes and the effects that depend on them happen in the order they were asked
  for**, and a transition is computed when its turn comes rather than when it was requested. The
  manager owns this (`_Chain`), because it is the only place that knows which effects assert a
  durable state. A transition that no longer applies by the time it runs is skipped, which is a
  normal outcome and not an error — a job that a cancellation has already finished is the case
  that produced it.

What survives unchanged: one writer thread, one transaction per batch, `check_same_thread=True`,
reads staying synchronous, and persist-then-announce. What does not is the claim that those
could be had without the callers changing shape.

### Consequences

- `persistence/writer.py` owns the thread and `persistence/store.py` is the single owner the rest
  of the process holds. `ui/` depends on a narrow protocol, not on either, so the dialog still
  cannot see that SQLite exists (`ARCHITECTURE.md` §3).
- **Asynchrony is not free at the call site.** Every caller that has an effect depending on a
  write now says so, by putting that effect where the write reports its outcome. The four
  `T016-R1`/`T016-R3` defects were each an effect that had quietly kept running on the old
  synchronous schedule.
- `persistence/db.configure()` now sets `busy_timeout`. In-process contention is gone by
  construction, but a *second process* — a second instance, `sqlite3` at a prompt — can still
  hold the lock, and waiting briefly beats raising at a user.
- Composition (`T-036`) owns constructing the writer and shutting it down. A writer thread that
  outlives the application is the same shape of orphan `T-019` spent a task on.
- **This decision reopens** if a write ever needs to be ordered against a read the GUI thread
  just made — a read-modify-write on a job. Nothing does that today: the manager owns job
  updates and runs its own transitions.

---

## OPS-005 — `STARBASE` is the Windows verification platform; hosted-only findings do not gate the phase

**Status:** **Accepted** (2026-07-29) — maintainer decision
**Date:** 2026-07-29
**Supersedes:** nothing. **Narrows** `OPS-003`'s "CI is the only Windows environment" premise,
which `OPS-004` had already amended once

### Context

`T-056` and `T-068` were both blocking Phase 1 on evidence only a GitHub-hosted runner can
supply, and hosted jobs have not started since the Actions quota ran out. Neither is a defect a
user would meet, and the reasons differ:

- **`T-056` is test-only code.** `still_running()` lives in `tests/integration/test_manager.py`
  and never ships. Its documented sole error direction is a false **alive**, which fails an
  assertion in the open — it can redden CI spuriously, but it cannot make broken reaping look
  correct. It was observed once, on `windows-latest`, in run `30323328299`, and does not
  reproduce on `STARBASE`: the pre-correction form passes **20/20** there with a positive control
  proving the mutation applied. The correction is in and was reviewed as correct.
- **`T-068` runs the other way.** Its defect appeared **on** the real machine — Qt with zero font
  families under `offscreen`, so the whole offscreen UI suite ran with no fonts — while the
  hosted runners are the ones that look clean. The fix landed and is validated on `STARBASE`.
  What stays open is the diagnostic question of why the runners never showed it.

**One thing this decision does not get to assume.** `still_running`'s mechanism is
Windows-*general*, not Server-specific: Windows has no zombie state, and a terminated process
stays visible while any handle to it is open — including the `Popen` handle the killing test
still holds. Handle semantics are the same on Windows 10 and Windows Server. So `STARBASE`
passing 20/20 is **absence of a trigger, not evidence of correctness**. What justifies accepting
the risk is the error direction, not the clean run.

### Decision

`STARBASE` — the maintainer's Windows 10 22H2 machine, an interactive verification target and a
self-hosted runner — is the platform Phase 1's *verified on Windows* criterion is measured
against.

A finding that reproduces **only** on a GitHub-hosted image and not on `STARBASE` does not block
a phase exit. It stays open as a follow-up, with its non-reproduction recorded.

`T-056` and `T-068` are downgraded accordingly: still open, no longer phase blockers.

### Rationale

- **Windows Server is not a supported platform.** `REQUIREMENTS.md` lists Windows 10/11 x86-64 as
  primary. `windows-latest` is Windows Server, so a finding seen only there is outside the surface
  the product ships to. It is a CI-reliability concern, not a user-facing one.
- **Blocking on an environment nobody can reach is not a gate, it is a stall.** The hosted quota
  is an external billing state. A criterion that cannot be attempted teaches nothing about the
  software.
- **The risk is bounded and named.** `T-056` can only produce false failures. `T-068`'s fix is
  already in and validated on the platform that showed the defect.

### Alternatives considered

- **Keep both as blockers until billing clears.** Rejected: it makes the phase exit depend on a
  payment, and neither task would change the product when it resolved.
- **Move all CI to self-hosted and close both as unreproducible.** Rejected: it would delete the
  only environment where `T-056` has ever been observed and make `T-068`'s question permanently
  unanswerable, in exchange for a green checkmark.
- **Close both as Cancelled.** Rejected: `T-056` was really observed once, and an undiagnosed
  intermittent deserves to stay on the books.

### Consequences

- `T-056` and `T-068` remain **open and Blocked**, but are explicitly **not** Phase 1 exit
  dependencies. Their blockers are recorded as external.
- **This does not by itself satisfy exit criterion 7.** The `check (windows-latest)` job — lint,
  format, types, Qt baseline, and the full suite on Windows — has still not run anywhere since the
  quota ran out. `STARBASE` currently runs the desktop slice and the process-tree modules only.
  Meeting the criterion needs that full suite executed somewhere, which `STARBASE` **could** do.
- Windows verification now rests on **one machine the maintainer owns**. Its availability is the
  gate's availability, and `RUNNER-R1` records the failure mode: an unmatched self-hosted job
  queues for up to 24 hours rather than failing fast.
- **This decision reopens** if hosted CI returns and `T-056` reproduces again, or if a
  hosted-only finding is ever traced to a defect reachable on Windows 10/11.

### Amended 2026-07-29 — the rule covers evidence obtainable only on a hosted image, not only findings that reproduce there

**Status:** **Accepted** (2026-07-29) — maintainer decision
**Occasioned by:** `T-066`, and by a reviewer disposition that read this entry the other way

**What needed extending, stated precisely.** The **Decision** above speaks of *a finding that
reproduces **only** on a GitHub-hosted image*. `T-066` is not that shape. Nothing about it
reproduces anywhere: what it owes is **evidence obtainable only** on a hosted runner, because both
`frozen` jobs run there. Reproduction and obtainability are different things, and the decision as
drafted named only the first. It is extended to the second.

**The rationale already covered it.** *"Blocking on an environment nobody can reach is not a gate,
it is a stall. The hosted quota is an external billing state. A criterion that cannot be attempted
teaches nothing about the software."* That argument turns on the environment being unreachable,
not on which direction the evidence runs. `OPS-006` then stated it generally — *"a criterion that
waits on a payment is not a gate"* — and rejected *"wait for hosted CI"* on the ground that *"an
external billing state is not a measurement."*

**`T-066` is downgraded accordingly: still open and Blocked, no longer a Phase 1 exit dependency.**

### Why the frozen shape is not Phase 1's to answer

- **Every frozen criterion in the plan belongs to Phase 0, and is met.** `IMPLEMENTATION_PLAN.md`
  mentions a frozen artifact **five** times and every one belongs to Phase 0 — including the
  Phase-level risk-register row, which attributes itself to Phase 0 — among them its exit row:
  *"Frozen artifact spawns a child without relaunching itself, both platforms — `T-020`; `frozen
  ubuntu-latest` and `frozen windows-latest` green."* Phase 0 formally exited 2026-07-26.
- **Phase 1's section names no frozen, install, virtualenv or packaging concern at all.** Its eight
  exit criteria are claims about product behaviour — a download, a cancel, a crash, a restart, an
  unsupported URL, a headless worker, two platforms, a sign-off. `T-066` is a claim about the
  environment a gate measures, which is a different kind of thing.
- **The remaining frozen work is already assigned to Phase 5.** `T-033` owns the Windows frozen
  build and gates Phase 5. Holding Phase 1 for evidence that Phase 5 will produce anyway inverts
  the sequencing principle.

### What this gives up, precisely

The frozen process-tree shape stays **reasoned rather than measured**. `T-066` records the
reasoning — under PyInstaller `sys.executable` is the frozen executable and `multiprocessing`
re-launches it through `freeze_support()`, so there is no launcher generation and no virtualenv —
and explicitly records it as an assumption. If that assumption is wrong, `T-019`'s process-tree
reaping evidence may not describe the application a user actually runs. **That risk is real and it
lands in Phase 5**, next to `T-033`, which is where a Windows frozen build gets made.

### On the enumeration

`OPS-005`'s Context named `T-056` and `T-068`; this amendment names a third task, and the title's
rule was always the general statement. Reading the two examples as exhaustive is the failure class
`T-044`, `T-045` and `T-014` each produced and `ai/TESTING.md` §13 records — an enumerated set
treated as complete. The condition is *hosted-only and unreachable*, not *one of two named tasks*.

**This amendment reopens** if the frozen shape is ever measured and differs from the assumption
above, or if hosted CI returns and the `frozen` jobs contradict it. Either would make the residue
a real finding rather than an unobtainable one.

*(A reviewer's final disposition on 2026-07-29 recorded "the explicit `T-066` frozen-artifact
evidence blocker remains" — written before this amendment and without reference to `OPS-005` or
`OPS-006`. It stands in `ai/REVIEWS.md` as what was said on the evidence then; this supersedes it
rather than erasing it.)*

---

### Amended 2026-08-01 — hosted Windows carries the Windows gate while `STARBASE` is unreachable

**Status:** **Accepted** (2026-08-01) — maintainer decision
**Raised by:** `STARBASE` going offline while the maintainer is away from it

**This entry's own reasoning now points the other way.** It was written when the hosted Actions
quota had run out and `STARBASE` was the only Windows available, and it argued: *"Blocking on an
environment nobody can reach is not a gate, it is a stall."* On 2026-08-01 the positions reversed.
The hosted runners returned and began executing full 15–18 step jobs; `STARBASE` is registered and
**offline**, and the maintainer cannot reach it.

### Decision, revised while this holds

**`check (windows-latest)` is the Windows verification platform for everything it can run.** That
is the whole suite, lint, format, both `mypy` platforms and the Qt baseline — measured, not
asserted: the corrected single-instance lock passed **first acquisition, simultaneous refusal and
killed-holder recovery** there on 2026-08-01, which are `T-087`'s three required Windows cases and
the exact ones `P2PLAN-R5` withdrew the previous design over.

**Two things stay with `STARBASE`, because a hosted image genuinely cannot supply them:**

- **The desktop slice** (`-m windows_desktop`, `T-026`, `T-040`). It asserts a native `HWND`, the
  UI Automation tree and per-state tab order under the **real** `windows` platform plugin. A hosted
  runner has no interactive desktop session.
- **The subjective residue** `OPS-004` already names — whether rendering *looks* right, whether
  Narrator *sounds* coherent, whether the installer *feels* normal — plus `T-074`'s segfault
  environment and `T-092`'s crash-dump capture, which are configuration of that machine.

**The `windows desktop` job is skipped unless `STARBASE_AVAILABLE` is set.** An offline self-hosted
runner does not fail its job, it queues — holding the entire run in `queued` so nothing ever reaches
a conclusion. Skipping is what lets a run finish; setting the variable brings it back.

### What this gives up, stated

A defect that appears only on a real Windows desktop — a platform-plugin difference, a focus or
window-manager behaviour — is not caught while this holds. That is the same class of gap
`OPS-004` already tracks, and it is narrower than the alternative, which is no Windows evidence at
all.

**This amendment reopens** the moment `STARBASE` is reachable again: it is *while unreachable*, not
instead of. The desktop slice and the pre-release verification session are unchanged and still
required before first release.

---

## OPS-006 — Linux verification is the maintainer's own machine

**Status:** **Accepted** (2026-07-29) — maintainer decision
**Date:** 2026-07-29
**Supersedes:** nothing. **Completes** `OPS-005`, which named the Windows platform and left the
Linux half of the same criterion undefined

### Context

`OPS-005` made `STARBASE` the platform Phase 1's *verified on Windows* criterion is measured
against, because the hosted Windows jobs could not start. The Linux jobs cannot start either — the
billing block is per account, not per platform — so `check (ubuntu-latest)` has been dead for
exactly as long, and the criterion's other half had no defined home.

The obvious symmetry, a self-hosted Linux runner, does not hold up. **Every development platform
on this project is Linux.** The argument that justified `STARBASE` — that nobody exercises Windows
day to day, so it can rot unnoticed — has no Linux equivalent: the suite runs on Linux constantly,
before every commit, by the person who wrote the change.

Worse, a self-hosted runner **on the development machine would not be an independent environment**.
It would share the OS install, the system packages, the Qt libraries and the ffmpeg the developer
already has. It would add a clean checkout and a recorded result, and nothing else. That is
ceremony priced as infrastructure.

### Decision

Linux verification for Phase 1 is the **maintainer's own machine**: a full run of the documented
gate — `ruff check`, `ruff format --check`, `mypy`, `mypy --platform win32`, and `pytest` — from
the checkout under review.

The hosted `check (ubuntu-latest)` job stays in `ci.yml`. It is not retired, and it resumes being
the Linux gate whenever it can start.

### Rationale

- **Linux is the platform with the least verification risk here**, not the most. It is exercised
  by every development session.
- **A runner on the dev box buys the wrong property.** The valuable thing a second environment
  provides is independence, and same-machine self-hosting provides none of it.
- **A criterion that waits on a payment is not a gate.** This is `OPS-005`'s reasoning applied to
  the other platform, and it would be inconsistent to accept it there and not here.

### What this gives up, precisely

**Bare-environment dependency regressions.** `check (ubuntu-latest)` installs `libegl1`, `libgl1`,
`libxkbcommon0`, `libdbus-1-3` and `libfontconfig1` before it runs, because the offscreen platform
plugin still links EGL/GL and xkbcommon. A developer desktop has all of them already. So a change
that introduces a dependency on a system library would **pass here and fail for anyone starting
from a bare Linux install**, and nothing in this arrangement would notice.

That is not hypothetical for this project. `T-062` is the same shape one platform over: *"`T-037`
was written, reviewed and approved on a machine that had what the runners did not, and had never
passed on either."* The risk is accepted with its name written down, not waved away.

### Alternatives considered

- **A self-hosted Linux runner on the development machine.** Rejected: same OS install, same
  packages, same libraries. It would record results without verifying anything the developer's own
  run does not already cover.
- **A container-based runner on the same machine.** Rejected *for now*, not on principle — a bare
  image is a genuinely independent environment and would close the gap above. It is the right fix
  if the gap ever bites, and this decision reopens rather than being argued again.
- **Wait for hosted CI.** Rejected for `OPS-005`'s reason: an external billing state is not a
  measurement.

### Consequences

- Phase 1's seventh criterion now has a defined platform on both halves: `STARBASE` for Windows,
  the maintainer's machine for Linux.
- **It is still not met, and `T-074` is why.** The Windows suite exits with an access violation
  roughly one run in four. A gate that crashes intermittently does not verify anything reliably,
  so the criterion should not be called met while that is open. This is the Implementer's reading;
  the exit review is where it is settled.
- Linux results are developer runs. They must be **recorded in the task** that claims them, with
  their real numbers, because nothing else will hold them.
- **This decision reopens** if a system-library regression ever reaches a user, or when hosted CI
  returns — at which point `check (ubuntu-latest)` simply resumes and this becomes moot.

---

## OPS-007 — `T-074`'s unreproduced access violation is accepted as residual risk

**Status:** **Accepted** (2026-07-29) — maintainer decision — and **amended 2026-08-04**, when its
premise turned out to be gone. This entry accepts a residual *because* 361 attempts produced zero
events; `T-128` records something in the same subsystem reproducing at roughly 2 in 39 on Linux.
That is a candidate and not an identity — see `T-128` for why the two are filed separately — but
the reopening clause turns on recurrence rather than on identity. **The amendment at the end of
this entry is what is now in force for the phase exit**: the risk stands as risk, and `T-128` must
diagnose before Phase 2 exits. The original reasoning below is kept as written rather than edited,
because what changed is the evidence under it.
**Date:** 2026-07-29
**Supersedes:** `OPS-006`'s Consequences sentence *"The Windows suite exits with an access
violation roughly one run in four."* That figure was the anecdote's denominator, not a
measurement, and `T074-R1` rejected it. `OPS-006` is otherwise unchanged.

### Context

**The event, once.** The full suite on `STARBASE` died with exit **139**, *Windows fatal
exception: access violation*, in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget`, with the `ResultPump` thread
in the traceback. Run `30416495270` at `454b80e` — a **documentation-only** commit, byte-identical
in code to `38650dd`, which had passed the same suite minutes earlier.

**Everything tried since, with numbers, kept separate by head** — `T074-R1`'s rule is that samples
from materially different heads are not one population:

| Attempt | Head | Result |
|---|---|---|
| 12 deliberate full-suite runs, run `30429327464` | `ea53c71` (pre-`T-090`) | **0 crashes** |
| 24 deliberate full-suite runs, run `30454206697` | recent, pre-`T-090` | **0 crashes** |
| *(the two batches above are the "0 in 36" the task records — one population of 36, not two of 12 and 36)* | | |
| 15 deliberate full-suite runs, run `30478557533` | `35fc7ec` (post-`T-090`) | **0 crashes, 0 failures** |
| 60 runs of the crashing test alone, on Windows | current | 60 passed, 0 crashed |
| 250 in-process iterations of its shape | current | clean |
| A direct stress of the logging-teardown race | Linux | **unusable** — hung in its own setup before the first iteration |

That is **51 deliberate full-suite runs**, plus 60 single-test runs and 250 in-process iterations —
**361 attempts with zero events**, across three shapes and two heads. The failed stress harness is
counted as neither a positive nor a negative, which is how the task records it.

**`T-090` is not established as the cause, and this decision does not claim it.** `T-090` fixed a
real, deterministic race on the same thread the fatal dump named — a listener left in an overlapped
`ReadFile` on a finalised queue. But the access violation was **already not reproducing before that
fix** (0/12), so a clean run after it carries no causal weight. `T074-R4` made exactly this point
and it stands.

**The obvious candidate is already defended against.** The classic PySide6 fault of this shape is a
`QThread` destroyed while `run()` executes; `manager.py`'s `_release()` refuses to drop a session
while its pump is live. The first hypothesis anyone would reach for is not it.

### Decision

`T-074`'s access violation is **accepted as residual risk**. It does **not** hold Phase 1's seventh
exit criterion.

`T-074` stays **open**, downgraded **High → Medium**, with its four acceptance criteria recorded as
**unmet** — not rewritten to match what turned out to be achievable. Whether criterion 7 is called
met is the **exit review's** to record; this decision removes `T-074` as the reason it cannot be.

### Rationale

- **Reproduction is the only entry to the criteria, and it is exhausted.** All four criteria
  presuppose a deliberate reproduction: criteria 1–3 cannot be attempted without one, and 4 is a
  conditional needing a diagnosis either way. Every method available has been run.
- **Continuing costs the gate it protects.** At ~4.1 minutes per Windows suite run, a rate low
  enough to survive 51 deliberate full-suite runs would need days of continuous `STARBASE` time —
  the one machine Windows verification depends on, and a computer somebody uses.
- **This is not hiding it.** `T-069`'s rule, restated in `T-074`'s own out-of-scope list, forbids
  retry, `xfail` and rerun plugins: an intermittent gets its trigger found, not its symptom hidden.
  Accepting a named unknown with a trap set is a different act from suppressing a signal.
- **The failure mode is loud, not silent.** It reddens the gate and takes the interpreter with it.
  It is not the class this project treats as Critical — a silent wrong result, downloading the
  wrong thing, or writing outside the chosen directory.

### What this gives up, precisely

**An intermittent access violation in or adjacent to `ARC-002`'s result-delivery path is
unexplained, in a module under `src/`.** If it recurs, every green Windows run before it is worth
slightly less than it appeared. Product-versus-harness is unresolved, so if it is the product, the
user-facing consequence is **unknown** — that is the actual concession, and it should not be
softened.

### The trap, so a recurrence is not another anecdote

`T-092` arms `STARBASE` to capture a crash dump on an access violation. `faulthandler` gives a
thread list, and `T-074`'s second criterion is explicit that *a stack is not a cause*; a minidump
names the faulting module and address, which is what that criterion actually asks for. This turns
an unbounded hunt into a bounded one: the next occurrence is diagnostic rather than anecdotal.

### Alternatives considered

- **Push for a reproduction.** Rejected on cost above, not on principle. It reopens the moment
  there is a cheaper instrument than repetition.
- **Close `T-074` as fixed by `T-090`.** Rejected: that is precisely the causal claim `T074-R4`
  refused, and the pre-fix clean sample means the evidence cannot support it.
- **Cancel `T-074`.** Rejected for `OPS-005`'s reason on `T-056`: it was really observed once, and
  an undiagnosed intermittent deserves to stay on the books.
- **Retry, `xfail`, or a rerun plugin.** Out of scope by `T-069`'s rule, and it would convert a
  known unknown into an invisible one.

### Consequences

- `T-074` remains **open at Medium**, its criteria **unmet**, and blocks no phase exit.
- **`T-092`** owns the dump trap and is the instrument this decision leans on.
- The exit review records criterion 7 against `T-073`'s measured Windows run, with this decision
  named as the disposition of the residual.
- **This decision reopens** if the access violation recurs anywhere — at which point `T-092`'s dump
  should supply criterion 2 — or if any user-reachable defect is ever traced to `result_pump.py`.

### Amendment, 2026-08-04 — the reopening clause fired, and the residual no longer clears the exit

**Status of the amendment:** **Accepted** (2026-08-04) — maintainer ruling on `P2EXIT-R9`.
**Raised by:** the Phase 2 exit re-review, which refused to re-use the original premise silently.

**What changed.** The acceptance above is bought with one number — *361 attempts with zero events*
— and the entry's own last bullet says it reopens if the fault recurs anywhere. `T-128` records **2
Linux `SIGSEGV`s in 39 serial full-suite runs**, both at the same completed-test position with a
live `ResultPump`. `T-128` is careful, and correctly so, that this is a **candidate and not an
identity**: it is a different platform and a different signal, and product-versus-harness is as
unresolved for it as it was for `T-074`. But the clause does not turn on identity. It turns on a
recurrence in this subsystem, and the zero-event premise is gone whether or not the two are one bug.

**Ruled: `T-128` must diagnose before Phase 2 exits.** The residual stands as *risk*, and it stops
being something a phase exits over. Three options were on the table — re-accept at the measured
rate, require the diagnosis, or file the Linux reproduction as its own separate risk — and the
maintainer took the second.

**Why this one.** The original acceptance was not a judgement that the fault is tolerable; it was a
judgement that **reproduction was exhausted**, argued explicitly on cost — *"a rate low enough to
survive 51 deliberate full-suite runs would need days of continuous `STARBASE` time"*. That
argument is now false. A fault reproducing at roughly 1 in 20 on Linux is reachable in an afternoon
on hardware that is not the one machine Windows verification depends on. The cheaper instrument the
*Alternatives considered* section named as the condition for reopening — *"it reopens the moment
there is a cheaper instrument than repetition"* — has arrived, and it is a reproduction rather than
a tool. Accepting the risk a second time would be re-using an argument whose premise the evidence
has removed, which is the specific thing `P2EXIT-R9` says the reviewer may not do silently and
which the maintainer may not do accidentally.

**What this does not decide.** It does not merge `T-074` and `T-128`, and it does not assert the
crash is in the product. `T-128` owns identity and product-versus-harness, and it should answer
`T-074`'s second criterion — *a stack is not a cause* — on whichever platform it can.

**Consequences of the amendment.**

- **Phase 2 exit criterion 6 now also waits on `T-128`.** It was already unmet for want of the
  independent exit review; this adds a second, separately-tracked reason.
- **`T-074` is unchanged**: still open at Medium, criteria still unmet, still not established as
  the same fault. Nothing here re-raises it on the strength of a Linux crash.
- **`T-092`'s dump trap is no longer the only instrument.** It stays armed for the Windows
  occurrence, but a Linux reproduction at 2-in-39 is a faster route to a faulting frame.
- **Phase 1's exit is not disturbed.** It exited on this decision's original form, and re-reading a
  closed phase against evidence gathered a week later is not what the reopening clause is for.

### What `T-128` found, 2026-08-04 — and why this amendment needs the maintainer again

**`T-128` is diagnosed, and it is a defect in the test harness, not in the product.** A fixture
teardown polled `DownloadManager.is_idle` — which answers a question about *work* — and then
dropped the manager while its own poll timer was still registered with the event dispatcher.
Python freed the object; a later tick followed the pointer into freed memory. Two `systemd`-kept
core dumps show the receiver's vtable slot holding a value that is not even 8-aligned. A
sub-second reproduction of the mechanism exists, against a ~6-minute soak at 5%.

**Nothing in `src/` is implicated.** No production code reads `is_idle`; `app.py` waits for the
`idle` **signal**, emitted only after `_timer.stop()`. The application holds one manager for the
life of the process and never drops one.

**This bears directly on the ruling above, and the implementer is not the one to re-take it.**
The amendment made `T-128` a Phase 2 exit prerequisite because a reproducible crash in the
result-pump subsystem removed this entry's zero-recurrence premise. On the evidence, those two
crashes were **not** recurrences of `T-074`'s fault at all — they were the harness dropping a Qt
object incorrectly — so the premise this decision was originally made on (*361 attempts, zero
events* against the **product**) is arguably intact rather than broken.

Three things follow, and the maintainer should choose among them rather than have an agent assume:

1. **The prerequisite is satisfied** — `T-128` diagnosed, corrected, and shown to be harness-only —
   so the Phase 2 exit stops waiting on it.
2. **The prerequisite is satisfied but a new one replaces it**: confirm on Windows that the
   corrected teardown ends `T-074`'s recurrences too, which `OPS-010` makes nearly free since
   `STARBASE` runs the full suite on every push.
3. **The prerequisite stands** — on the view that until `T-074`'s faulting object is named on
   Windows, a Linux harness diagnosis says nothing about it.

**The implementer's recommendation is (2)**, because the strongest new fact is that `T-074`'s
recorded crash happened in *the same file and the same fixture* `T-128` found at fault. That is a
lead worth spending free evidence on, and it is the only route that can retire `T-074` rather than
keep accepting it.

### Ruled 2026-08-04: (2), with the confirmation made measurable

**Maintainer decision.** The `T-128` prerequisite is **satisfied**; a new and narrower one replaces
it. The Phase 2 exit no longer waits on diagnosing the segfault — it waits on evidence that the
correction actually removed it.

**The confirmation is on Linux, and the recommendation as first written was imprecise about that.**
It said *"confirm on Windows that the corrected teardown ends `T-074`'s recurrences"* — but this
entry records **361 attempts with zero events** on Windows, so there are no recurrences there to
end, and green Windows runs would only re-accumulate the evidence that produced this decision in
the first place. The measurable claim is the one with a measured baseline:

- **`T-128` reproduced at 2 in 39 full-suite runs on Linux** (≈5.1%). Re-running that soak against
  the corrected teardown is a real before-and-after, and it is the gate.
- **Sizing, so the number is not arbitrary.** If the rate were unchanged, the chance of a clean
  soak is 0.128 at 39 runs, **0.042 at 60**, and 0.009 at 90. **Sixty is the bar** — a clean run of
  sixty puts the "nothing changed" reading below 5%, and it fits one overnight window at ~5
  minutes a run.
- **Windows becomes a passive watch, not a gate.** `OPS-010` already runs the full suite on
  `STARBASE` on every push, so it costs nothing. Its value is asymmetric and worth stating: a
  recurrence of the access violation *after* the harness fix would **rule the fix out** as
  `T-074`'s cause, which is informative; continued silence adds nothing to 361 clean attempts and
  must not be reported as though it did.

**What this does not do.** It does not close `T-074`, whose four acceptance criteria stay unmet and
whose faulting object is still unknown. It does not assert the two are one defect. A clean soak
establishes that the *reproducible* crash is gone — nothing more.

*(What is **not** claimed: that `T-074` is this defect. Its faulting object was never determined,
its platform and signal differ, and `a stack is not a cause` — this entry's own standard.)*

---

## UX-001 — Pause is a queue-level drain; remove never deletes a file

**Status:** **Accepted** (2026-07-29) — maintainer decision, taken from the Implementer's
recommendation
**Date:** 2026-07-29
**Supersedes:** nothing. **Amends** `REQ-015`, which read *"Per job, support cancel, pause, resume,
retry, and remove"*. The amendment landed in `ai/REQUIREMENTS.md` on 2026-07-29; this entry is its
rationale, which `P2PLAN-R2` found had no durable home.

### Context

`REQ-015` requires cancel, retry and remove per job, and originally required pause and resume there
too. `core/job_state.py`'s `_TRANSITIONS` already carries `RUNNING → PAUSED`, `PAUSED → RUNNING` and
`FAILED → QUEUED`, with comments explaining why resume returns to `RUNNING` rather than `READY`. The
state machine modelled per-job pause; the machinery to reach it was never built, and `T-080` is
where it would be.

**The question pause actually raises is what happens to a half-written file.** `REQ-017` — resuming
a partial download — is **Phase 3**. So in Phase 2 a paused download's partial file has no defined
meaning: nothing can resume from it and nothing is specified to clean it up.

### Decision

**Pause and resume are queue-level, not per-job.** Pausing lets every in-flight download finish and
starts nothing new. Resuming takes work again. **No job ever enters `PAUSED`.**

**Remove takes a job out of the queue and never deletes a file from disk.** Removing a running job
cancels it first, within the same 2-second budget `REQ-015` sets for cancel.

### Rationale

- **Draining means there are no partial files to have a rule about.** Every alternative produces a
  half-written file and then needs a policy for it — keep it for a resume that does not exist yet,
  or delete data the user's download produced. Draining buys neither problem.
- **It matches what a user pausing a queue wants.** The intent is "stop starting things", not
  "abandon the download that is 90% done".
- **Remove is not delete, and conflating them is unrecoverable.** `AGENTS.md` §10 puts data loss in
  the Critical band. A queue action that silently removed a completed file would be exactly that,
  and no undo exists.

### Consequences

- `REQ-015` is amended and its superseded wording preserved in place.
- **`_TRANSITIONS`' `PAUSED` edges are now unreachable, and that is a defect to resolve rather than
  a curiosity.** `T-080` owns either removing them or recording why a state nothing reaches is kept.
  An unreachable state reads as capability and is not — the same shape as a guard nobody watches
  fail (`ai/TESTING.md` §13).
- `T-080` must be retitled and rewritten from this decision; `P2PLAN-R1` reports that its Scope
  still quotes the pre-amendment requirement while its acceptance criteria describe queue-level
  behaviour, so an implementer currently receives contradictory instructions.
- Pausing creates no partial file, which is an assertable property rather than a happy consequence,
  and `T-080` asserts it.

### Alternatives considered

- **Stop the in-flight session and keep the partial file.** Rejected: it buys a file nothing can
  resume until Phase 3, and a rule about its lifetime that would then change.
- **Stop the session and discard the partial.** Rejected: it throws away work the user asked for,
  to implement "pause".
- **Per-job pause, as `REQ-015` originally read.** Rejected on the same partial-file grounds, and
  because a per-job pause whose only effect is "this job will not be picked next" is a queue
  operation wearing a job's name.

**This decision reopens when `REQ-017` lands in Phase 3.** Once a partial download can be resumed,
a partial file has a defined meaning and per-job pause becomes coherent — at which point the
`PAUSED` edges may be wanted back, and this entry is the record of why they were idle.

> **Amended 2026-08-07 by `UX-006`.** The **default** changes; the **semantics** do not. The queue
> no longer runs unless it has been started, so the gate this entry describes is closed at launch
> rather than open. Everything above about *what closing it does* — drain the in-flight sessions,
> start nothing new, create no partial file, never put a job in `PAUSED` — is carried forward
> unchanged, which is why `UX-006` needed no new mechanism. Read `UX-006` for the default and this
> entry for the drain.

---

## ARC-006 — The single-instance guard is a `QLocalServer` named from the resolved database path

**Status:** **Accepted** (2026-07-29) — maintainer decision, taken from the Implementer's
recommendation
**Date:** 2026-07-29
**Supersedes:** nothing. **Addresses** `A-004`'s self-recorded *unverified* assumption of no
concurrent instances against one database, which named enforcement as a Phase 2 task. It does **not
discharge** it: `A-004` stays unverified until `T-087` lands and is tested. *(The header said
"Discharges" while this entry's own Consequences said `A-004` stops being unverified only once
`T-087` lands — `P2PLAN-R5` reported the contradiction.)*

> **Amended 2026-07-29 — `QLocalServer` is not an exclusive lock, and the mechanism below is
> withdrawn** (`P2PLAN-R5`). See the amendment at the end of this entry before implementing
> anything from it. The **attach channel** reasoning survives; the **ownership** reasoning does not.

### Context

`A-004` assumes a single local user and **no concurrent instances against the same database**.
`ARC-005` puts every write on one writer thread *within a process* — two processes have two writer
threads and no shared lock discipline, so the assumption is load-bearing for data integrity rather
than tidiness. `T-087` is the enforcement task, and it recorded this reasoning in task text;
`P2PLAN-R2` found that an architectural cross-platform choice was living somewhere mutable.

### Decision

**`QLocalServer` / `QLocalSocket`, with the server name derived from the resolved database path.**

The startup protocol is **connect first; if the connection fails the owner is gone, remove the
stale name and become the server.**

### Rationale

- **Already Qt.** No new dependency, and one code path compiles to a named pipe on Windows and a
  Unix domain socket on Linux — two correct platform implementations rather than two guesses.
- **It is a channel, not a flag.** That is what makes *attach* possible rather than only *refuse*:
  a second launch can hand its URL to the running instance and raise its window. A lock file can
  only say no.
- **Crash behaviour decided it**, because a crash is the case the guard exists for. Windows destroys
  a named pipe when its owning process dies. On Linux a killed process leaves the socket file
  behind, which is why the protocol connects before it claims: a refused connection proves the
  owner is gone, and only then is the stale name removed.
- **Named from the database path, because `A-004` is about the database, not the application.** Two
  instances against *different* databases harm nothing and must not be blocked.

### Consequences

- `T-087` implements this and its acceptance criteria bind the hard part: **the stale-socket path is
  tested by killing an instance, not by deleting a file by hand** — the recovery has to work against
  the failure it was chosen for. Verified on both platforms, `STARBASE` included.
- A second launch must say which thing it did, attach or refuse. Silence is indistinguishable from
  a hang.
- The derivation from database path to server name must be stable across launches and must not leak
  a filesystem path into a namespace with different legal characters. `T-087` owns stating it.
- `A-004` stops being an unverified assumption once `T-087` lands.

### Alternatives considered

- **PID lock file.** Rejected: it needs a liveness check, and it is wrong under PID reuse — a
  recycled PID makes a dead owner look alive and blocks startup permanently.
- **`flock`.** Rejected: robust, and the kernel releases it on process death, but it offers no
  channel, so *attach* is impossible and a second launch can only refuse.
- **Named mutex (Windows) plus something else (Linux).** Rejected: two mechanisms, two failure
  modes, and the platform-specific half is the part least exercised by the maintainer's own use.
- **A TCP socket on a fixed localhost port.** Rejected: it is visible to every other process and
  every other user on the machine, needs a port allocation policy, and can be firewalled — a
  networked answer to a local question.

### Amended 2026-07-29 — the ownership primitive is withdrawn; `QLocalServer` stays only as the channel

**Status:** **Accepted** (2026-07-29) — maintainer decision
**Raised by:** `P2PLAN-R5`, on the Qt documentation rather than on a measurement

**The decision above is wrong about the property it depends on.** It reasons that a failed connect
proves the owner is gone, and therefore that becoming the server is safe. Qt 6's own
`QLocalServer::listen` documentation states the opposite for the platform that matters most here:
on Windows **two local servers can listen on the same pipe name simultaneously**, and an incoming
connection may go to either of them.

So the protocol *connect first, then claim* is not mutually exclusive. Two launches racing at
startup can both fail their initial connect — neither is listening yet — and both then succeed at
`listen()`. The result is two live instances against one database, which is precisely the
two-writer state this entry opens by calling a data-integrity threat. `ARC-005` puts every write on
one writer thread **within a process**; two processes have two writer threads and no shared lock.

**What was actually established and what was assumed.** The crash-recovery reasoning is sound and
survives: Windows destroys a named pipe when its owning process dies, and a killed process on Linux
leaves the socket file behind, which is why any implementation must handle a stale name. What was
assumed without checking is that *creating* the server is an atomic claim. It is not, and no amount
of connect-first ordering makes it one.

### Decision, revised

**Ownership and messaging are two mechanisms, not one.**

- **Ownership** is an atomic, kernel-backed exclusive lock on a file derived from the resolved
  database path — `fcntl.flock` with `LOCK_EX | LOCK_NB` on POSIX, an exclusive-access open on
  Windows. Both are released by the kernel when the holder dies, which is the property a PID file
  cannot offer and the reason the original entry rejected PID files.
- **`QLocalServer` / `QLocalSocket` remains the attach channel**, and only that. Everything the
  original entry says about it being a channel rather than a flag still holds: it is what lets a
  second launch hand over its URL and raise the first window instead of merely refusing. It is
  started *after* ownership is won, and it is never the thing that decides who owns the database.

Whoever wins the lock starts the channel. Whoever loses it connects to the channel and hands over.

### What this changes for `T-087`

- Its acceptance criteria must add **simultaneous** starts, not only stale-owner recovery. The
  defect this amendment fixes is invisible to a sequential test: launch A, then launch B, and B's
  connect succeeds, so the broken mechanism looks correct. Two launches racing is the case.
- Tested on Linux **and** `STARBASE`, because the two halves are different system calls and the
  Windows half is the one the withdrawn design got wrong.
- `A-004` stays **unverified** until that lands.

**This amendment reopens** if a Qt release documents `listen()` as exclusive on Windows, or if the
exclusive-open approach proves unable to distinguish a live holder from a stale file — in which case
the answer is a better ownership primitive, not a return to using the channel as one.

---

### `ARC-007` amended 2026-07-30 — the concurrency limit gets a ceiling `REQ-013` does not name

**Status:** **Accepted** (2026-07-30) — maintainer decision
**Raised by:** the `T-078` settings layer, which flagged the gap rather than filling it

**`REQ-013` says *bounded, minimum 1* and names no maximum.** The first implementation was therefore
literally compliant and deliberately unbounded: any positive integer in `settings.toml` was honoured
verbatim, and the module said so rather than inventing a limit. That was the right call while nothing
consumed the value. It stops being the right call the moment the pool is real, because the integer
becomes that many spawned worker processes — `ARC-002` makes each one a full interpreter with yt-dlp
imported.

### Decision

**`CONCURRENCY_MAXIMUM = 16`.** A file asking for more is **clamped** to it; a caller passing more
**raises**, the same asymmetry the minimum already has and for the same reason — code is written once
and reviewed, a config file is typed by hand.

### Rationale, and what it is *not*

**It exists to catch a typo, not to model the hardware.** The realistic failure is `30` where `3` was
meant, or an extra zero. 16 is comfortably above any deliberate choice for a desktop downloader whose
default is 3, and low enough that a slipped digit does not survive.

**`os.cpu_count()` was considered and rejected.** It is the defensible-sounding answer and it is
wrong here: downloads are I/O-bound, so cores are not the constraint, and a two-core laptop can
usefully run more than two. Deriving the ceiling from cores would under-bound exactly the machines
least able to absorb the mistake.

**Memory was measured and is not the binding constraint either.** A worker's baseline is **~34 MiB**
(measured 2026-07-30: interpreter 12 MiB, 34 MiB after importing yt-dlp), so 16 is roughly 0.5 GiB
and even 64 would be about 2 GiB. The ceiling is not a memory bound and should not be justified as
one — saying so here prevents the number being "corrected" later against the wrong metric.

**So 16 is a judgement, not a measurement**, and it is recorded as such. What makes it defensible is
the class of error it stops and the cost of being wrong in either direction: too high and a typo
still bites, too low and a legitimate power user is obstructed.

### Consequences

- `_concurrency_from` clamps both ends; `with_concurrency` does the same, because the bound belongs
  wherever the value changes rather than only where it is read.
- `Settings.__post_init__` raises above the ceiling, so a programming error is loud.
- `settings.toml`'s comment header states the maximum **and** that each download is a separate worker
  process — the only place a hand-editor is told what the number costs.
- `T-078`'s pool inherits a value that is already in range, so it needs no bound of its own.

**This reopens** if the pool ever stops being process-per-job — `ARC-002` is what makes the number
expensive — or if a user reports 16 obstructing real work, which is the direction this is most likely
to be wrong in.

---

## ARC-007 — Phase 2's settings surface is `settings.toml` plus one main-window control, not a dialog

**Status:** **Accepted** (2026-07-30) — maintainer decision
**Date:** 2026-07-30
**Supersedes:** nothing. **Implements** `DAT-001`'s "TOML for settings" and `ARCHITECTURE.md` §5's
assignment of `settings.toml` to `core/settings.py`, both of which predate any settings code.
**Raised by:** `P2PLAN-R3`

### Context

`REQ-013` requires a **user-configurable** concurrent download limit, default 3, minimum 1. Phase 2's
deliverable is "bounded concurrent worker pool, configurable limit"; Phase 4 owns the **full**
`REQ-023` settings dialog, which covers eight settings including this one. So Phase 2 needs a real
way for a person to change the limit, without building the thing Phase 4 is going to build.

**`P2PLAN-R3` found the gap that silence left.** `T-078` called the limit "the first setting with
runtime effect" and left where it lives to the implementer. Its acceptance criteria proved that
different values of N work — which a constructor argument or a test seam satisfies completely, while
missing the requirement at the centre of the phase.

**Two things were already settled and are not re-decided here.** `DAT-001` chose TOML for settings;
`ARCHITECTURE.md` §5 places them at `user_config_dir/tracksandtrails/settings.toml` and assigns them
to `core/settings.py`, which exists as a stub from `T-001`'s skeleton and has never been written.
Window geometry deliberately does **not** use this layer (`ui/main_window.py`, `window.toml`), and
that stays true.

**And one thing was already required.** Phase 2's own exit criteria say *"Concurrency limit is
respected exactly; lowering it while running drains cleanly."* Live effect was never optional; it
had simply never been connected to a user-facing path.

### Decision

**1. `core/settings.py` lands in Phase 2**, owning `settings.toml` at §5's location. It is the
foundation of the whole settings layer rather than a special case for one key: Phase 4 adds keys and
a dialog on top of it, and migrates nothing.

**2. The limit is exposed as a control in the existing main window** (`T-007`'s window), **not a
settings dialog.** A one-control dialog built now is a layout Phase 4 replaces; a TOML layer plus a
control is purely additive.

**3. Changes take effect live, and lowering drains.** Lowering the limit while downloads run lets
in-flight work finish and governs what starts next — the same semantics `UX-001` chose for pause, for
the same reason: there is no partial file to have a rule about. Raising it starts waiting jobs
without waiting for a tick to fire.

**4. The persistence boundary: `downloader/manager.py` receives the value and never reads the
file.** Composition and the UI read and write `core/settings.py`; the manager takes an integer and a
way to be told it changed. This is `JobStore`'s shape again — the manager depends on a value, not on
a config format — and it is what keeps the pool testable without a TOML file on disk.

### Rationale

- **Phase 4 rewrites a dialog; it does not rewrite a file format.** The expensive, throwaway part of
  option "dialog now" is the layout and its keyboard-order gate, both of which change when seven more
  settings arrive.
- **A file-only surface leans on a reading of "user-configurable" that this project should not lean
  on.** A TOML file is technically configurable by a user, and `P2PLAN-R3`'s whole point is that a
  criterion satisfiable without a reachable path is not a criterion. One control removes the argument.
- **The live requirement already existed**, so connecting the surface to it costs nothing extra and
  omitting it would have contradicted a phase exit criterion.
- **Keeping the manager ignorant of TOML** means `T-078`'s tests stay unit-shaped, and a settings
  format change in Phase 4 cannot reach the pool.

### What this gives up, precisely

**There is no settings *screen* until Phase 4.** A user who wants to change several things at once
edits `settings.toml` by hand or waits. **Discoverability is lower** than a Settings menu item would
be: one control in a window is easy to miss, and nothing advertises that the file exists or what else
it will eventually hold. That is accepted for one phase, on the grounds that the alternative is
building a dialog twice.

### Alternatives considered

- **A minimal settings dialog now, grown in Phase 4.** Rejected on rework: its layout, its tests and
  its `T-060`-style keyboard-order gate all change when `REQ-023`'s other seven settings land.
- **`settings.toml` with no in-app control until Phase 4.** Rejected as the smallest thing that still
  invites `P2PLAN-R3`'s objection — a criterion met by editing a file and restarting is close enough
  to a seam to be argued about, and the argument is not worth having.
- **A constructor argument only, with configuration deferred entirely to Phase 4.** Rejected: this is
  the finding, not an option.
- **Putting the control in the queue view (`T-079`).** Rejected on sequencing: `T-078` lands before
  `T-079`, so the limit would be unreachable in the phase's own centre task. The main window exists
  already.

### Consequences

- `T-078` gains acceptance criteria for the user-facing path and for live application; see the task.
- `core/settings.py` stops being a stub, and its read/write contract is Phase 2's to establish —
  including what happens to an unparseable or hand-corrupted `settings.toml`, which `T-078` must
  state rather than discover. *(`T-078` stated it: a silent fallback to defaults, with the silence
  named as the cost. **`ARC-008` decided the other half on 2026-07-31** — a file that exists and
  cannot be used now reports; a missing or value-omitting one still does not.)*
- Phase 4's dialog is additive over this layer. **This decision reopens** when it lands: the
  main-window control may move into the dialog, and this entry is the record of why it was there.
- `REQ-013`'s "minimum 1" is a constraint the settings layer enforces, not the spinbox — a
  hand-edited `0` must not produce a pool that never starts anything.

---

## OPS-008 — The environment ownership gate's three blind spots stay open

**Status:** **Accepted** (2026-07-30) — maintainer decision
**Date:** 2026-07-30
**Supersedes:** nothing. **Closes** `T044-R1`'s residue, carried by `T-047` through six review
rounds without a disposition.

### Context

`T-044`'s gate reports any public attribute of `downloader/environment.py` that no `import`
statement accounts for. It reads the interpreter's namespace via `vars()` rather than parsing for
bindings, which is what makes it hold for *any* binding syntax — including syntax that does not
exist yet. That property was reached only after five parsing attempts failed, each defeated by
syntax its author had not enumerated.

Three gaps survive, pinned by test rather than left to memory:

1. **An export behind a guard that is false at run time** — OS, architecture, dependency presence,
   feature probe, environment state.
2. **A name imported and then rebound** — `try: from x import Y / except ImportError: Y = ...`, the
   ordinary shape of an optional dependency, where the import parse subtracts a name the fallback
   genuinely bound.
3. **Dynamic rebinding of an imported name** — `globals()["Path"] = ...`.

`T-047` existed to decide whether any is worth closing. Its first deliverable was deliberately a
decision rather than a patch, because the history says the next clever fix will also be wrong.

### Decision

**None of the three is closed. The gate stands as it is, and `ai/TESTING.md`'s statement of its
promise remains the durable description of what it does not cover.**

### Rationale

**All three are structurally unreachable in the module the gate protects.** Measured 2026-07-30 by
parsing `downloader/environment.py`, not by reading it:

| Gap | Construct it requires to become reachable | Present in the module |
|---|---|---|
| 1 | a module-scope `if` | **0** |
| 2 | a module-scope `try`/`except` | **0** |
| 3 | a call to `globals`, `locals`, `setattr`, `vars`, `exec` or `eval` anywhere | **0** |

Module scope is one docstring, seven plain imports, three annotated assignments, five functions and
two classes. There is no construct any of the three gaps needs.

That is a stronger argument than the one `T-047` was filed with, which was that gaps 1 and 3 "need a
determined author to trigger". True, but weaker: today they need a determined author **and** a change
to the module's structure, and the second is the part a reviewer can check.

- **Five attempts died to enumeration.** `T044-R1` was found six times. Every fix that recognised
  more syntax was beaten by syntax the author had not named, and three attempts to state the
  coverage overclaimed and were disproved. This is the `T-044`/`T-045`/`T-014` failure class, and
  `ai/TESTING.md` §13 records it.
- **The gate catches what it exists to catch.** An accidental `get_ytdlp_version()` appears in
  `vars()` under any binding syntax. That is the defect `ARCHITECTURE.md` §6 cares about.
- **§6's boundary has two other guards.** The layering test and review both bind it independently, so
  this gate is not the only thing standing between the module and a violation.

### What this gives up, precisely

**A determined author can defeat the gate**, three ways, and the project has written down how. That
is accepted: the gate is a check against accident, not an adversary, and treating it as the latter is
what produced five failed fixes.

**More usefully: the measurement above is a premise, and nothing enforces it.** Adding a platform
branch to a module that resolves paths across two operating systems is an ordinary thing to do. It
would make gap 1 live, nothing would fail, and this decision would be silently obsolete. **`T-098`
guards that premise** — and does so by parsing for the three constructs the gaps *require*, a closed
set that follows from the gaps' own definitions, rather than for bindings.

### Alternatives considered

- **Close gap 2** (the plausible one — an optional-dependency fallback is ordinary code). Rejected:
  the module has no optional dependency and no `try`/`except`, so there is nothing to close, and the
  fix would be a sixth parse of binding syntax.
- **Close gaps 1 and 3.** Rejected on the same grounds, with less motive: both need deliberate
  authorship.
- **Replace the gate.** Rejected: `vars()` is the property five rounds failed to achieve, and no
  proposal on the table improves on reading the interpreter's own namespace.
- **Record nothing and leave `T-047` open.** Rejected — that is what six rounds already did.

### Consequences

- `T-047` closes. Nothing in `src/` or `tests/` changed for it.
- **`T-098`** owns the premise guard and `ai/TESTING.md`'s reopening conditions.
- **This decision reopens** if `downloader/environment.py` gains a module-scope guard, an
  import-with-fallback, or any dynamic namespace manipulation — each of which makes one specific gap
  reachable — or if the gate is ever proposed to bind a second module with a different shape.

---

## ARC-009 — A durable probe continues into its download; a staging probe does not

**Status:** **Accepted** (2026-08-05) — maintainer ruling on `T137-R2`
**Date:** 2026-08-05
**Extends:** `admit()`'s contract from `T-115`. **Does not amend** `UX-003`, which this exists to
honour rather than to weaken, nor `UX-001`'s pause semantics.

### Context

`admit(job_id, kind)` schedules **one** session and has never chained. That was complete while the
only probe in the system was a *staging* probe, whose entire purpose is to stop and let the user
look at what they pasted before anything is committed.

`T-137` then introduced a second kind of probe subject. A playlist is expanded in the add dialog
into one durable job per entry, built from a **flat** extraction — an address and a name, with no
duration, no size and no format list, because resolving sixteen entries during an add is the cost
`project_media` has refused since `T-016`. Those rows are honestly created `QUEUED` rather than
`READY`, and the code says so.

**They were then admitted straight to `DOWNLOAD`.** So every entry of every playlist downloaded
without ever being probed, and `UX-003`'s rule — a queued job is a probed one — was broken for the
majority of rows a real playlist produces. `T137-R2` found it, and correctly refused to let filing
`T-143` defer a violation already in shipped behaviour.

**Admitting them as probes alone would have traded one broken promise for another**, because
nothing carries a finished probe into a download. Every entry would be probed and then parked for
ever.

### Decision

1. **When a probe settles for a job the manager is not staging, that job is admitted for
   download.** The continuation lives in `DownloadManager`, beside the outcome it follows.
2. **A staged row is excluded**, and that is the whole discriminator. Continuing a staging probe
   would start the very download the dialog is still asking the user about.
3. **The add dialog admits by status, not by shape.** An unprobed row — `QUEUED` — is admitted as
   a `PROBE`; anything already resolved is admitted as a `DOWNLOAD`. The rule is *unprobed things
   get probed*, so the dialog does not become a second place that has to know what a playlist is.

### Why the manager rather than composition

The alternative was for `app.py` to listen to `media_probed` and admit the download. It was
rejected: pause semantics, per-entry failure reporting and lane accounting are the manager's, and
`T036-R1` is what it cost the last time queue policy was written outside the object that owns the
queue — a retry that announced nothing and was attempted exactly once.

The add dialog could not host it either. It closes on `accept()`, so the object that admitted the
probes is gone before the first one lands.

### Consequences

- **Pause is preserved without special handling** (`UX-001`, `T080-R1`). The probe half runs while
  paused because probes are exempt; the continuation is an ordinary `DOWNLOAD` admission, so
  `_start_when_free` parks it and `resume()` drains it. A paused queue probes a playlist's entries
  and starts none of them.
- **A failed probe is not carried anywhere.** `Failed` is a different outcome branch, so an entry
  that cannot be resolved is reported per entry rather than downloaded blind.
- **The staged guard is load-bearing and its failure mode is deferred.** Without it the
  continuation admits a staged id; `admit()` does not refuse outright, it *parks*, and `start()`'s
  `ValueError` then arrives on drain from a timer's thread of control. A test that expected an
  immediate raise would pass against the broken version, so the regression asserts the queue state
  instead.
- Entries now cost one extraction each, at a moment nobody is waiting. `T-143` keeps what remains:
  what those probes should populate on the row.

---

## ARC-008 — A settings file that exists and cannot be used says so; a missing one does not

**Status:** **Accepted** (2026-07-31) — maintainer decision
**Date:** 2026-07-31
**Supersedes:** nothing. **Extends** `ARC-007`, whose Consequences delegated the read contract for
"an unparseable or hand-corrupted `settings.toml`" to Phase 2. `T-078` established that contract as
a silent fallback and **named the silence as what it gave up**, in `core/settings.py`'s own module
docstring. This decides the half `T-078` deferred.

### Context

`core/settings.py.load()` never raises. A missing file, an unreadable one, a malformed one and one
whose shape is wrong all produce `Settings()`. The module docstring states the cost plainly:

> **What that gives up, stated:** a corrupt file is silently replaced by defaults rather than
> reported. Nothing in `REQ-023` or `ARC-007` asks for a settings-parse diagnostic, and there is
> nowhere to show one until Phase 4's dialog exists.

Both halves of that justification have weakened. `T-078` shipped a main-window concurrency control,
so there **is** somewhere to show one; and `save()` writes the file the control edits, so a user
whose hand-edit is discarded now sees their number silently revert in the UI with no cause offered.
`settings.toml` is one of only two ways to change the value until Phase 4, and `DAT-001` chose a
human-editable format precisely so people would edit it by hand — which is the act that produces
the malformed file.

### Decision

**A `settings.toml` that exists and cannot be used is reported to the user, naming the file and
saying that defaults are in use.** The fallback itself does not change: `load()` still never raises
and still answers with `Settings()`. What changes is that the fallback stops being silent.

**The line is whether something was discarded, not whether the read was perfect.**

| The file | `load()` returns | Reported |
|---|---|---|
| Does not exist | `Settings()` | **No** — the normal first run |
| Exists, cannot be opened or read (`OSError`) | `Settings()` | **Yes** |
| Exists, is not valid TOML (`TOMLDecodeError`) | `Settings()` | **Yes** |
| Parses, but `[queue]` is not a table | `Settings()` | **Yes** |
| Parses, `[queue]` is a table, `concurrency` is not an `int` | `Settings()` | **Yes** |
| Parses and simply omits `concurrency` | `Settings()` | **No** — see below |
| Parses, `concurrency` is an `int` out of range | clamped | **No** — see below |

**Omission is silent because `save()` promises it is.** The file this application writes carries the
header *"Safe to delete: every value falls back to its default."* A user who takes that at its word
and deletes the line must not then be told their file is broken. The same reasoning covers an empty
file and one with no `[queue]` table at all.

**Clamping is silent because nothing was discarded.** `ARC-007`'s amendment decided that `0` means
"as few as possible" and `30` means "a lot", and that both intents are honoured up to the bound.
A report would contradict the decision to honour them. *(This is the weakest edge of the three and
is named as such: a user who writes `30` and gets 16 is not told. It is a reopening condition below
rather than a settled question.)*

**The report is a returned value, not a dialog raised from `core/`.** `AGENTS.md` §7's layering rule
forbids `core/**` from importing Qt, and `load()` is called from composition in `app.py` before the
main window exists. So `core/settings.py` answers with the diagnostic alongside the settings, and
the presentation belongs to `ui/`. This keeps `load()` testable without a display, which is the
property the layering rule exists to protect.

**Presentation is a modal warning at startup**, before the main window is usable, naming the path
and the underlying reason where one exists. Modal is justified by rarity rather than by severity:
this fires only when a file that exists cannot be used, which is never during normal operation.

### Alternatives considered

- **A status-bar message.** Rejected: transient and easy to miss, and the user this exists for is
  one who already missed something — they will notice the reverted value later, when the message
  is gone.
- **A dismissible banner above the queue.** Rejected on `ARC-007`'s reasoning: it is a new
  persistent UI element in a phase that deliberately shipped one control rather than a surface.
  Phase 4's dialog is where a settings surface belongs.
- **Logging it and nothing else.** Rejected as the status quo wearing diligence: `T-038`'s log is
  not a channel a user reads, and the whole finding is that the user is not told.
- **Raising from `load()`.** Rejected — "never raises" is the property that makes a broken config
  file a non-fatal state, and `save_geometry` follows the same rule for `window.toml`.

### Consequences

- **`T-102`** implements it. `core/settings.py`'s module docstring loses the "what that gives up"
  paragraph, because it will no longer be given up — and the paragraph must not outlive the
  behaviour it describes.
- `load()`'s signature changes, which reaches its callers in `app.py` and `ui/main_window.py`.
  The shape is `T-102`'s to choose; the constraint is that the diagnostic travels as data.
- **This decision reopens** if Phase 4's settings dialog lands (`REQ-023`), which gives the report a
  natural home other than a startup modal — and separately if clamping proves to surprise anyone,
  which is the edge deliberately left silent above.

---

## UX-002 — Automatic retry is three attempts at 2s, 4s and 8s, on `NETWORK` failures only

**Status:** **Accepted** (2026-08-01) — maintainer decision
**Date:** 2026-08-01
**Supersedes:** nothing. **Closes** the provisional marking `T-083` shipped with on 2026-07-31.

### Context

`REQ-018` requires that a failed job stays in the queue and offers retry, and never fails silently.
It says nothing about *automatic* retry, and `T-083` added it for the one class where a retry can
plausibly succeed unchanged: `NETWORK`. The narrowness is the point — an `UNSUPPORTED_URL` retried
on a timer is a request the site will refuse identically, forever, and `DRM_PROTECTED` never
reaches retry at all (`SEC-001`, `REQ-EXCL-001`).

`T-083` built the mechanism and **deliberately did not choose the numbers**, because its own scope
said they "need stating in `DECISIONS.md`, not choosing in code" and `AGENTS.md` §4 makes that file
the Architect's. It shipped them marked provisional with a draft entry. This is that entry.

### Decision

**Three automatic attempts follow the first, waiting 2, 4 and 8 seconds.** Only `NETWORK` failures
retry automatically.

```
attempt 1 fails → wait 2s
attempt 2 fails → wait 4s
attempt 3 fails → wait 8s
attempt 4 fails → FAILED, and manual retry only
```

**The bound is derived from the table, not declared beside it.** `AUTOMATIC_RETRY_LIMIT` is
`len(RETRY_BACKOFF_SECONDS)`. Two constants written separately can disagree, and the thing that
would notice is an `IndexError` inside a Qt slot. Changing the policy means changing one tuple.

**Doubling, and starting small.** The failure this exists for is transient — a dropped connection,
a moment of packet loss — and something that recovers in seconds should be retried in seconds. A
fourth attempt is evidence the problem is not transient, at which point a person should decide.

**An automatic retry spends an attempt; a manual one does not.** `Job.attempts` counts what the
queue did unattended, so `with_another_attempt` is called only on the automatic path. A user who
presses Retry four times is not throttled by a budget that exists to stop a machine looping.

**A retry never jumps the queue.** Automatic retries sort behind jobs that have never run, and
manual retry re-enters at the tail (`P2PLAN-R7`). Both are `T-080`'s and `T-083`'s to enforce; the
policy here is about *when*, not *where*.

### Alternatives considered

- **Longer backoff — 5s, 30s, 120s.** Kinder to a site that is genuinely down rather than briefly
  unreachable. Rejected on what it costs the common case: a job sits visibly idle for over two
  minutes before its last attempt, against roughly fourteen seconds here, and a user watching a
  queue cannot tell a long backoff from a hang. Reconsider if real-world failures turn out to
  cluster on sites that are down rather than connections that blip — that is the reopening
  condition below, and it wants evidence rather than a preference.
- **Unbounded retry with a growing delay.** Rejected: `REQ-018` requires the failure be *recorded*
  and the user offered a retry, which presumes retrying eventually stops.
- **Retrying every retryable class rather than `NETWORK` alone.** Rejected as `T-083`'s scope
  already had it: `is_retryable` governs whether a person may retry, which is a different question
  from whether a machine should.

### Consequences

- `manager.py`'s `RETRY_BACKOFF_SECONDS` loses its provisional marking and cites this entry.
- **This decision reopens** if failure data shows transient network faults are not the dominant
  automatic-retry case, or if `REQ-017`'s resume lands in Phase 3 — a retry that resumes a partial
  download is a different cost from one that starts over, and the backoff was chosen against the
  cost of starting over.
- Changing the policy is one tuple. Anything that adds a second constant beside it should be
  treated as reintroducing the disagreement this entry exists to prevent.

---

## DAT-005 — Removing a history entry removes a record, never a file

### Amended 2026-08-06 — one action, renamed, and the boundary this entry exists for is untouched

**Status:** **Accepted**, on maintainer direction of 2026-08-06 recorded at `T-169`.

**The boundary is the part that does not move.** A record is not a file, and emptying records never
deletes downloads — that is why this entry exists and `T-169` does not touch it.

**What changes is that there is nothing left to clear.** *(This said the two actions became one,
`Clear download records`, in a Settings data section. Later the same day `REQ-020` was withdrawn
outright — there are no records — so that action is gone too, and this entry now governs nothing
that exists.)*

**The boundary this entry exists for outlives the feature it was written about.** A record is not a
file, and nothing in this application deletes a user's downloads — that is `UX-001`'s promise and it
is untouched by there being no records. Anything later that stores what was downloaded inherits this
entry's rule rather than getting to decide it again.

The 2026-08-05 amendment and the original entry follow unaltered; both are historically true of the
feature as it stood.

### Amended 2026-08-05 — clearing the whole list, on the foundation §1 named

**Status:** **Accepted.** **Proposed by the Implementer** and **ratified by the maintainer on
2026-08-05**: §1 is reopened on the condition it set for itself, and the semantics below are
accepted as written.

*(`T144-R1`, and this case was the stricter of the two: `DAT-005` is Accepted and outranks `T-144`,
which has no criterion authorising an amendment. §1 naming its own reopening condition made an
amendment eligible for a decision; it did not make it self-accepting, and the Implementer wrote and
self-headed it anyway. The ruling that was missing has now been made.)*

**Raised by:** `T-144`, found by the maintainer with a history large enough for it to matter.

**§1 refused *Clear all* and said exactly what would lift the refusal**: *"both can be added on this
foundation once removal itself is proven, and neither is what a person reaches for first."* `T-125`
built removal and it has been through review, so the condition this entry set for itself is met.
What follows is the amendment, not an exception to it.

**1. The verb is `Clear history`, and the wording is the ruling.** §1's other objection stands
untouched: *"Clear all is also the phrasing most likely to be read as deleting downloads."* It is —
*all* has no object, so the user supplies one, and the one they have in mind is their files.
**`Clear history` names the thing it empties**, which is the same distinction this entry exists to
draw: a record, not your downloads.

**2. It is its own operation, not removal with the ids left out.** `HistoryRepository.remove`'s
empty-sequence guard exists so that an empty selection cannot become an accidental
`DELETE FROM history` — *"the failure this signature exists to make impossible"*. Widening that
method to mean "everything when given nothing" would delete the guard and the reasoning together.
So a wholesale clear is a **separate, explicitly named method**, and the narrow signature stays
narrow.

**3. The confirmation names its count and repeats the file guarantee**, per §4 and §3. *"Clear all
1,284 downloads from history? The files stay on your disk."* The count is what tells a user how much
they are about to lose; the guarantee is what tells them what they are not. This is the moment §3's
promise matters most, because it is the moment the list becomes empty.

**4. One transaction** (`NFR-003`). There is no half-emptied history, and nothing that survives only
until the process exits — `T125-R1`'s lesson, which was a delete that looked durable through the
connection that made it and was not.

**5. Still no automatic pruning by age or size.** §1 refused two things and this lifts one of them.
An age cutoff is a *policy* nobody has decided, and deciding it inside a task about a button would
be `UX-005` §5's shape in the data layer.

### Consequences

- **A history past SQLite's parameter ceiling can be emptied at all.** `remove` builds one
  placeholder per id, and `SQLITE_LIMIT_VARIABLE_NUMBER` is 32766 on this build — measured, in
  `T-144` — so "select everything and remove it" failed outright with a database error on a history
  that large. That is unreachable for most users and certain for the one who has used the
  application longest.
- **`UX-005`'s toolbar gains a verb that acts on History**, and the rule recorded in
  `_build_queue_actions` — *"what is on this toolbar acts on the queue"* — is rewritten to the
  principle underneath it rather than left standing as a comment that used to be true: **nothing on
  the toolbar acts on a selection, and every verb on it names the list it empties.** That is what
  made the original rule right; the tab a verb belongs to was never what made it unambiguous.

**Status:** **Accepted** (2026-08-04) — maintainer decision, answering `UX-005` §9's deferral
**Date:** 2026-08-04
**Amends:** `REQ-020`, which said *maintain* a history and did not admit removal.
**Unblocks:** `T-125`. **Does not amend** `DAT-001`'s storage choices or `UX-001`'s promise, which
this entry is an application of rather than an exception to.

### Context

`UX-005` §9 describes a removal control and then **refuses to specify it**: *"What is removable,
and whether a file is ever touched, is a `DAT-` entry, not a button."* That refusal was right.
`HistoryRepository`'s own docstring says *"Append-mostly and read-only to the rest of the
application: nothing here deletes"*, and no requirement asks for removal — `REQ-020` says maintain,
`REQ-021` says open and reveal. So this is a gap rather than an unimplemented requirement, and
adding a delete path to a deliberately append-only store is a data decision before it is a widget.

The risk is specific and it is not abstract: **a history entry names a file on disk.** "Clear
history" is ambiguous in exactly the way that loses somebody's downloads, and the obvious
implementation deletes the wrong thing.

### Decision

1. **Selected entries only.** Removal is scoped to what the user selected, and the verb names its
   own count — *Remove 3 downloads from history*, not *Remove*. No *Clear all* and no
   older-than-a-date: both can be added on this foundation once removal itself is proven, and
   neither is what a person reaches for first. *Clear all* is also the phrasing most likely to be
   read as deleting downloads.
2. **No file is ever touched.** Not as an option, not behind a second checkbox. `UX-001` already
   promises that nothing in this application deletes the user's files, and an "also delete the
   file" affordance would make that promise conditional — which is the same as not having it. A
   user who wants the file gone has a file manager.
3. **The guarantee is carried permanently, not only at the moment of asking.** *"Files are never
   deleted"* sits in the status bar while the History tab is showing, as well as in the
   confirmation. A promise that appears only in a dialog is a promise only the people who read
   dialogs have.
4. **Removal is irreversible, and confirmed with its count.** *"Remove 3 downloads from history?
   The files stay on your disk."* — the count and the file guarantee in one breath. No soft delete:
   a `deleted_at` column would change every history query and amend `DAT-001` to protect a record
   whose loss costs a user very little, given the files are untouched.
5. **`REQ-020` is amended** to admit removal, rather than a new requirement being added. One
   requirement describes one surface; the data reasoning lives here.

### Consequences

- **`HistoryRepository` gains its first delete path**, and its docstring's "nothing here deletes"
  becomes false and must be rewritten rather than left as a comment that used to be true. The
  method takes ids, never a predicate, so the scoping decision above cannot be widened at a call
  site.
- **`UX-005` §9 is now implementable**; `T-125` is unblocked.
- **`REQ-026`** (whatever a user can erase about themselves) is *not* settled here. This is one
  list. A user asking to remove their traces would also mean logs and the queue, and that is a
  larger question this entry deliberately does not answer.
- **The confirmation is not optional**, even though the loss is small. It is what carries the file
  guarantee to the one person who is about to act on it.

---

## DAT-004 — Log redaction is provenance-aware: exact values always, shape rules only on our own lines

**Status:** **WITHDRAWN** (2026-08-01) — see the withdrawal at the end of this entry. It was
**Proposed** (2026-08-01) — implements `DAT-003` as amended by `T-049` in the logging
layer. **Not a new boundary**; it is the first place the amended boundary had to be built, and it
changes observable behaviour, so it is recorded rather than left in a commit message.
**Date:** 2026-08-01
**Implements:** `DAT-003` (2026-07-26) and its `T-049` amendment (2026-07-30).
**Touches:** one sentence of `DAT-003`'s original *Consequences*; see below.

### Context

`T-084` has an acceptance criterion that names both directions of the boundary and says why:

> a value this application supplied does not reach the log, **and** a cookie path yt-dlp emitted
> inside a diagnostic is still there, character for character. One test each. A gate that only
> proves the first would pass an implementation that scrubs everything, which is the failure
> `DAT-003` records twice.

`T-038` redacted every log line by **shape** — patterns for URLs, proxy userinfo, cookie headers and
cookie paths. That satisfies the first direction and fails the second: a path yt-dlp itself named
matches `_COOKIE_PATH` and is removed, which is exactly the "scrubs everything" implementation
`DAT-003` records two failed attempts at.

### Decision

**Redaction asks who wrote the line.**

| The line was written by | Registered exact secrets | Pattern rules |
|---|---|---|
| This application | Removed | **Applied** |
| A third party (yt-dlp) | Removed | **Not applied** |

Mechanically: a `logging` filter stamps `THIRD_PARTY_FIELD` on records from the bridge yt-dlp writes
through, and `RedactingFormatter` reads it. Nothing infers provenance from the text.

### Rationale

- **It is `DAT-003`'s own boundary, applied where it had not been.** The amendment states the rule
  as *"binds on **who put the value there**, not on what the value looks like"*. A shape-based
  formatter is the thing that sentence rules out.
- **The guarantee that survives is one-directional, and deliberately so.** What this application
  supplies never reaches a log; **nothing is claimed about what a diagnostic may contain**. That is
  the only form two failed recognisers did not already disprove.
- **Exact values still bind everywhere**, including inside third-party prose, because there is
  nothing to be wrong about in an exact string this application is holding.

### The sentence this touches

`DAT-003`'s original *Consequences* says *"`T-038` still owns log redaction, and its scope is
unchanged — logs are written by this application, so the supplied-value rule binds there in full."*

Read precisely, that says the **supplied-value rule** binds fully in logs — which is exactly the
first row above and is preserved. It does not say every value is removed regardless of provenance,
and reading it that way contradicts the amendment written four days later. **This entry adopts the
narrow reading and says so, rather than relying on it silently.**

### Consequences

- Text yt-dlp emits now reaches a job log intact where it previously did not. That is the point, and
  it is a widening of what a log can contain.
- **`DAT-003`'s reopening clause is now live and is not settled here.** It names *"a bug report
  attaching it"* as a trigger, and `T-084` ships a Copy-diagnostics button whose whole purpose is
  that. The copied text is the file verbatim; no second, more-scrubbed rendering was invented,
  because that would be writing a specification rather than implementing one. **A maintainer ruling
  is owed on whether the clipboard path should differ from the file.**
- If the answer is that it should, the seam already exists: `redact(text, third_party=...)` is one
  call, and the view is the only caller that would pass a different flag.

### Alternatives considered

- **Keep shape-based redaction everywhere** — rejected: fails `T-084`'s second direction, and is the
  implementation `DAT-003` records failing twice.
- **Drop redaction for third-party lines entirely** — rejected: a supplied secret quoted back inside
  a diagnostic would survive. A mutation doing exactly this is in the battery and is killed.
- **Infer provenance from the logger name at format time** — rejected: the same string then means
  different things depending on a name a future refactor may change. A record attribute set at the
  source is the fact, not a proxy for it.

### Withdrawn 2026-08-01 — it contradicted an accepted decision, and shipped a Critical

**Status:** **Withdrawn** by the implementer on `T084-R1`. Nothing in this entry is in force.

`DAT-003`'s `T-049` amendment has a section headed **"`T-038` is unchanged and origin-agnostic"**:

> Every log this application **emits** is redacted, whatever the provenance of the text inside it.
> That is not in tension with the table: storage and emission are different sinks with different
> rules, and the supplied-value rule binds emission in full.

I read the amendment's provenance **table** — which governs the *database* — and applied it to logs,
without reading the section directly beneath it that says logs are not provenance-scoped. This entry
then argued for a change to an accepted decision from inside a task, which is not a route that
exists: a `Proposed` entry cannot supersede an `Accepted` one.

**Why it was Critical rather than merely wrong.** The scheme had two tiers: exact
`remember_a_secret()` values, always removed; and the pattern rules, dropped for third-party
records. **No production caller registers anything**, so the first tier is empty in the running
application — and "provenance-aware" collapsed to *no redaction at all* for every line yt-dlp emits.
A diagnostic echoing the source URL wrote its userinfo password and signed query to the job log
verbatim, onto a surface `T-084` had just given a Copy button.

**What replaces it:** nothing. `core/logging.py` is back to origin-agnostic redaction and the
`third_party` parameter is gone, so there is no flag for a caller to pass.

### The question this leaves open, which is the maintainer's

`T-084`'s second acceptance criterion asks that **a cookie path yt-dlp emitted survive character for
character** in the job log. Accepted `DAT-003` forbids that at this sink. The criterion and the
decision cannot both hold, and the cost is real in both directions:

- **As it now stands**, a user reading their own log cannot see which cookie database yt-dlp failed
  to open — `NFR-006`'s "preserved intact" is lost for exactly the diagnostics it was written for.
- **Loosening it** puts credentials a user typed into a URL onto a surface built for pasting into
  bug reports, which is `DAT-003`'s own named reopening condition.

#### Ruled 2026-08-01 — accepted `DAT-003` wins, and the criterion is amended

**Maintainer ruling.** Log emission stays origin-agnostic; `T-084`'s contradictory acceptance
criterion is **amended** rather than left unmet, because a criterion that contradicts an accepted
decision is the thing that is wrong.

What that costs is stated rather than absorbed: a user reading a job log will not see which cookie
database yt-dlp could not open. `NFR-006`'s promise is kept at the **other** sink — the database
stores the extractor's message verbatim — and `T-084`'s amended criterion now asserts the two sinks
against each other on one value, so neither rule can quietly drift into the other.

---

## UX-003 — Nothing enters the queue unprobed

**Status:** **Accepted** (2026-08-02) — maintainer decision
**Date:** 2026-08-02
**Supersedes:** nothing. **Changes** the add flow `T-016` shipped, which `REQ-001` and `REQ-012`
leave open.

### Context

Probing is optional today, and covers the **first URL only**: `ui/add_dialog.py` offers a
`&Probe first URL` button, and every other pasted line is persisted `QUEUED` having never been
looked at. Nothing decided that. `REQ-002` names title, uploader, duration and thumbnail as things
the application shows about a URL; `REQ-001` says a queue accepts many; neither says when the two
meet. The manual button is what fell out of Phase 1 running a pool of exactly one, where probing a
batch would have been a queue of probes with no scheduler to run it.

The consequence reaches the queue. A row for an unprobed job has **no title, no duration and no
thumbnail** — nothing but its URL — so a queue of twenty pasted links is twenty rows that cannot be
told apart until each one reaches the front. Filling those rows was raised as a display question
and turned out not to be one: a thumbnail exists only after a probe, and `_has_capacity()` counts
every session, so probes queue *behind downloads*. With a limit of three and twenty URLs added, the
last is probed only after the nineteenth has finished downloading.

**The add-time probe is not load-bearing, which is what makes this affordable.** A download session
already probes first — `downloader/worker.py`: *"A download session probes first, so DRM and ffmpeg
are caught before any bytes move."* Nothing downstream reads the earlier probe's result, so probing
at the door costs one round trip and cannot go stale.

### Decision

**A job enters the queue only once it has been probed.** The add dialog resolves the whole paste
before anything is queued: it becomes a staging list where each pasted line resolves in place into
a row carrying its title, uploader, duration and thumbnail, and *Add to queue* commits what
resolved.

Three rules follow, and they are the decision as much as the sentence above:

1. **A URL that will not probe never becomes a job.** It stays in the dialog with the extractor's
   message verbatim (`NFR-006`) and its own retry, and the commit button counts only what resolved.
2. **Probe state is shown in the dialog and nowhere else.** It answers "why is the button not
   ready"; in the queue it describes something already finished.
3. **`PROBING` stays in the state machine.** A retry re-enters `QUEUED → PROBING` (`REQ-018`), and
   a download session reports a probing stage of its own. What changes is that it stops being a
   status a user *reads*, not a state the machine has.

### Consequences

- **`REQ-018`'s retry splits by cause.** A job that fails *downloading* still sits in the queue
  offering retry, unchanged. A URL that never probed has no job to carry that offer, so its retry
  lives in the dialog. Both paths exist; neither is silent.
- **A long resolve is not durable.** Nothing is persisted until Add is pressed, so closing the
  window mid-paste loses the reading. That is the ordinary behaviour of an uncommitted dialog, and
  it is stated rather than discovered.
- **The metadata lane becomes a precondition, not an optimisation.** Mandatory probing through the
  shared pool means pasting twenty URLs takes the download slots and **stalls downloads already
  running** — a worse symptom than the ragged rows this started from, and one that appears only
  once probing is required. `T-116` owns it and precedes the rest.
- **Phase 3's playlist picker gets its prerequisite for free.** A playlist expands into entries only
  after a probe, which this guarantees has happened by the time a row exists (`T-110`).

### Alternatives considered

**Fill the unprobed rows with a generated placeholder and leave probing where it is.** A gradient
derived from the URL fills every tile the moment a row appears, costs nothing, and needs no
network. Rejected as *sufficient*: it stops the column looking broken but the row is still
title-less, and the title is the part a user actually reads. Kept as a **component** — a row still
needs something to draw between appearing and resolving, and `T-118` uses exactly this.

**Probe lazily, for visible rows only.** Cheapest at scale, and it is the right rule for *fetching
thumbnail bytes* (`T-119`). Rejected for metadata: it makes what a row says depend on where the
user has scrolled, and a queue that fills in as you look at it is harder to trust than one that
was complete when it was made.

**Refuse the whole paste when any URL fails.** Simple, and wrong on a flaky connection: paste
thirty, lose eight to timeouts, and the user loses all thirty. Rule 1 above costs a button press
instead.

---

## UX-004 — The staging row's controls: a visible preset, a menu for the rest

**Status:** **Accepted** (2026-08-02) — maintainer decision
**Date:** 2026-08-02
**Amends:** the row anatomy the maintainer approved from the `T-118` mockups. **Does not amend**
`UX-003`, whose rules are unchanged.

### Context

`T-118` shipped per-row Retry and Remove as a context menu rather than as the visible buttons the
approved mock drew, and shipped **no** per-row preset override at all. `T118-R5` refused both: a
keyboard-reachable menu is useful evidence about accessibility but is not authority to change an
approved interaction, and `T-118`'s own acceptance criterion requires the paste preset to be
overridable per row. The task also names `T-105`'s `docs/UX_SPEC.md` as a dependency, and that
file does not exist.

The reviewer stated the two ways out: complete `T-105` and build the approved anatomy, or take a
maintainer amendment that chooses the divergence and says where the per-row override lives. This
is the second.

### Decision

**The per-row format choice is a visible control on the row. Retry and Remove are a context menu.**

1. **Every row carries a visible "Download as" control** showing what that row will be downloaded
   with. A row that has not been overridden shows the batch preset explicitly as inherited — not as
   a blank, which reads as "none" rather than "the one above". *(Amended below: the control is a
   real combo on each row, after the alternative was measured.)*
2. **Retry and Remove stay in a context menu**, reachable by the menu key and Shift+F10 as well as
   by pointer.
3. **`T-105` is not a prerequisite for this.** It remains filed and owns `docs/UX_SPEC.md`, which
   should absorb this anatomy when it is written.

### Amended 2026-08-02 — the control is on the row, and the cost was measured

**Maintainer decision, after measurement.** The first version of this entry put the format control
in the footer acting on the *selected* row, on the reasoning that a widget per row would not scale.
That reasoning was asserted rather than measured, and the measurement does not support it.

Building the list, median of five warm runs, offscreen Qt, one developer machine, against
`NFR-001`'s ~100 ms interaction budget:

| Rows | A: a control on every row | B: text only |
|---:|---:|---:|
| 10 | 3.1 ms | 0.8 ms |
| 20 | 5.2 ms | 1.6 ms |
| 50 | 29.4 ms | 2.2 ms |
| 100 | 57.0 ms | 2.7 ms |
| **150** | **85.7 ms** | 3.7 ms |
| 200 | 116.2 ms | 5.3 ms |
| 500 | 296.2 ms | 10.4 ms |

**A crosses the budget between 150 and 200 rows**, and costs three to five milliseconds at any
paste a person types by hand. It is also a *build* cost, paid once when the paste resolves, so a
200-row paste is one visible hitch rather than a sluggish dialog.

So the control is on the row, as the approved mock drew it. Two consequences are recorded rather
than absorbed:

- **The threshold is machine-dependent.** These numbers are one machine; a slower one moves the
  crossing point down. No cap is imposed, because a silent switch to a different interaction at an
  invisible row count is worse than a hitch — if a guard is ever wanted it should be a stated limit
  with a message.
- **`T-119` should turn this into C.** Its delegate can draw the control only on the row under the
  pointer or holding focus: one widget reused, identical interaction, no threshold. That is a
  sequencing note, not a second decision — nothing about the interaction changes, so nobody has to
  relearn it.

### Rationale

The two row actions are not equivalent to the format choice and do not deserve equal weight.
Retry applies only to a row that failed, and Remove is destructive and rarely wanted — putting
both on every row spends the row's width on controls that are usually inapplicable, and a paste of
five hundred pays for them five hundred times. The format choice is different: it is the decision
the dialog exists to take, it applies to every row, and hiding it behind a right-click means a
user who wants one MP3 among twenty videos has no way of discovering they can have it.

`T118-R5` is right that the missing override is what made the divergence substantive. Restoring it
as a *visible* control answers the finding at the point where it bites, rather than by restoring
buttons whose absence nobody would have noticed.

### Consequences

- **`T-118` gains a per-row request model.** The final request for each row is built from that
  row's effective choice at Add, which is `T-075`'s rule applied per row rather than per batch.
- **The mock is now wrong in one respect** and should be treated as superseded here rather than as
  the specification. `T-105` inherits the discrepancy.
- **Discoverability of Retry is reduced**, and that is the cost of this decision. The batch-level
  "Retry the ones that failed" control remains visible, so the *capability* is discoverable even
  where the per-row route is not.

### Alternatives considered

**Build the approved mock exactly.** Three visible controls per row. Rejected on the scale
property `UX-003` was chosen for: a widget per control per row makes a paste of five hundred a
fifteen-hundred-widget layout pass on the GUI thread, which needs a virtualised delegate — pulling
`T-119`'s work into a task that is already the largest in the rework.

**Write `T-105` first.** The most faithful reading of the plan, and rejected only on sequencing:
`T-118` carries three Critical findings whose fixes do not depend on the spec, and holding them
behind a document would leave known-broken behaviour on `main` for longer.

---

## UX-005 — The main window: two tabs, no detail pane, and the verbs on the row

### Amended 2026-08-14 — a failed row is one line taller, when it has something to suggest

**Status:** **Accepted** — **maintainer ruling of 2026-08-14**, taken on `T201-R3`. The Reviewer
recommended option C and said in its own record that a recommendation is not a ruling; this entry
exists because the maintainer then made it one. *(The distinction is `T145-R1`'s, four amendments
up: an entry headed "maintainer ruling" when none had been made. It is not repeated here.)*

**Raised by:** `T201-R3` (High). `NFR-006` asks each failure to state **what failed, why, and what
the user can do**. §2 of this entry removed the detail pane, and the widget that composed all three
— `JobProgressView` — is constructed by nothing in the product. So the row carried the first two
and the third reached nobody. The text existed and was tested throughout; what it had was no
surface.

**The ruling: a third text line, on failed rows only.** Where the row has an honest next step it is
drawn on its own line, below the reason and above the format line, and the row is one line taller.
Where there is none — `DRM_PROTECTED`, `GEO_RESTRICTED`, and every row that has not failed — the
row keeps §3's anatomy exactly.

**The two options this rejects, and why the cheaper one was not taken:**

- **Appending it to the reason's line** (`headline · next step · message`) was refused **on a
  measurement, not a preference**: at 1180 px the step consumes the width that was carrying
  `--ffmpeg-location`, and the extractor's message elides to `--ff…`. That is `NFR-006`'s
  *surfaced, never swallowed* clause paying for `NFR-006`'s *what the user can do* clause, which is
  not a trade this entry will make. `ai/evidence/2026-08-14-T201-next-step-option-a.png` is the
  rendering.
- **Replacing the format line on a failed row** was refused because §6 makes plain format text the
  row's only statement of what a download ran as, and a failed row offers Retry — so it is
  precisely the row where knowing what will be attempted again is worth most.

**What this costs, stated rather than glossed: §3's anatomy is no longer one shape.** That is a
real loss and it is the second time this entry has spent it. Row 9c already made a playlist entry
shorter than its group, and `RowDelegate.sizeHint` already adds a line only where an entry has a
format of its own to state. **This follows that established rule** — height goes where the row has
an additional fact — rather than opening a new one. Uniform item sizing was given up at `T-140`
and is not given up again here.

**Conditions of the ruling, all of which the correction meets:** the paint and the height derive
from one role (`ACTION_ROLE`), the selector, progress bar and verbs move down with the line rather
than being drawn over, and the same text reaches the row's accessible description — `NFR-005` does
not let a fact be added for the eye alone. `ai/evidence/2026-08-14-T201-next-step-option-c.png` is
the ruled layout at the head that built it; `tools/failed_row_screenshot.py` regenerates it.

**Everything else in this entry stands**, §2's ban on a detail pane included. The line is the row
carrying more, not a pane returning.

### Amended 2026-08-06 — one tab, because the second one's contents are no longer a product

**Status:** **Accepted**, on maintainer direction of 2026-08-06 recorded at `T-169`.

**The main window shows one surface: the Queue.** There is no History tab, no History count, no
history rows, no history groups and no history-row verbs. `REQ-020` now keeps a private ledger
(`DAT-006`) with nothing to browse, so the tab has no contents rather than a smaller version of the
old ones.

**What survives is everything this entry decided that was never about *which* tab.** The row anatomy
of §3, the verbs-on-the-row ruling of §4 and §5, the state chip, the playlist group with its
segmented bar, and the rejection of a detail pane all stand — they describe **a row**, and the
Queue still has rows. The 2026-08-05 group amendment stays historically true of History and remains
current truth for the queue's own groups.

**Two tabs becomes no tab widget at all**, not one tab in a tab bar. A tab strip with a single tab
is a control that offers a choice the user does not have, which is the same objection §5 makes to
drawing a verb that would be refused.

**`Clear history` leaves the toolbar** with the list it emptied, and nothing replaces it: `REQ-020`
was withdrawn later the same day, so there are no records to clear from anywhere. `Clear finished`
stays — it clears completed **queue rows**, and with no ledger beside it there is nothing left for
it to be confused with.

The original entry and its 2026-08-05 amendment follow unaltered.

### Amended 2026-08-05 — a finished playlist is one History row

**Status:** **Accepted.** **Proposed by the Implementer** and **ratified by the maintainer on
2026-08-05**, all three decisions as written.

*(`T145-R1`: this entry was first headed "Maintainer ruling" when none had been made — the
Implementer chose the three answers and attributed them, which `T-145`'s "record before you
implement" criterion does not authorise. The attribution is corrected rather than quietly fixed:
the content below is unchanged, and what changed is that it is now true that a maintainer ruled on
it. The reviewer's disposition was that the content was internally coherent and worth ratifying,
which is a recommendation and was not the ruling.)*

**Raised by:** `T-145`, found by the maintainer after a sixteen-item playlist finished and landed in
History as sixteen unrelated rows.

§3 gives both tabs the same row anatomy, and a playlist is the largest place they differ: the queue
took trouble to show that sixteen tracks arrived together, and History dropped it at exactly the
point it became the only record. **A finished playlist is one History row that opens**, matching row
9's anatomy. Three things follow, and `T-145` is required to have them ruled on rather than decided
in an implementation.

**1. A History group's chip is a count of its members — `16 items`.** The 2026-08-04 amendment
excluded History from the **state** chip, because *"every history row is finished, so a chip reading
Done on all of them is noise"*. That reasoning is about a state, and it stands: an ordinary History
row still carries no chip. A group's count is not a state — it is the one fact about a group that is
not visible until it is opened — so this is a **different** chip rather than a reversal.

**2. A History group has no segmented bar.** Row 9b's bar exists to show a failed entry among
running ones. Every member of a History group succeeded, by `DAT-005`'s definition of what reaches
the list, so the bar would be sixteen identical blocks — the furniture the chip ruling above
rejects, drawn wider.

**3. A partly-failed playlist is a group of what History holds — `14 items`, never `14 of 16`.**
Two reasons, and the second is the one that decides it:

- History is a record of **completed** downloads (`REQ-020`, `DAT-005`). A denominator of 16 is a
  claim about two downloads History does not hold and cannot describe.
- **A stored original count goes stale on the first removal.** `DAT-005` makes records removable
  one at a time; a user who removes one member of a fourteen-member group would be shown
  `13 of 16`, which is now wrong about both numbers. A count derived from the members present
  cannot drift from them, which is `T-137`'s reason for having no `playlists` table.

This also settles the column question `T-145` raises: **no original-count column**, because nothing
would keep it true.

**Membership is carried at completion, not reconstructed.** The three columns `0004` put on `jobs`
are copied onto the history record by the completion transaction. A record written before that
migration has no membership, renders **ungrouped**, and is not re-grouped by guessing from titles or
paths — inventing it would be presenting a guess as a record.

**Recorded before implementation**, per `T126-R4` and the amendment above it.

### Amended 2026-08-05 — a divergent playlist says which row got which

**Raised by:** `T-157`, found by running the built window. **Maintainer ruling, 2026-08-05.**

**Rows 9c and 13 contradict each other, and neither is wrong about its own half.** Row 9c gives a
child no format line because *"an entry inherits its group's format, so its third and fourth lines
have nothing to say."* Row 13 puts retargeting on the group — and `T140-R3` correctly made it move
only the members that can still move, because a finished track cannot be un-downloaded.

So **retargeting a part-done playlist guarantees divergence**, and row 9c's premise becomes false
for exactly the playlists a user has touched. They were written apart and met in the built window.

**1. A child draws its format line only when its format differs from the group's**, and stays
silent when it agrees. Row 9c's economy is kept for the common case — a uniform playlist still
draws no format lines — and a line is spent only where there is something to say. It is the only
option that answers *which row got which*, and it scales: three formats, and each divergent child
names its own. The variable child height this costs is one `T-140` already spends deliberately.

**2. The group's format control shows explicit `Mixed` text and is never blank.** A blank combo
reads as *unset* or *broken* rather than *they differ*. The placeholder names the count —
`Mixed — 2 formats` — with the real choices below it; choosing one still retargets every member
that can move, which is `T140-R3`'s behaviour unchanged.

**The header's format line is unchanged.** `mixed across 2 formats` is already honest, and once the
children speak it stops being the only thing said.

### Rejected, and why

- **The header names both counts** — *"12 as MP3, 4 as original"*. Cheaper, and it does not say
  *which row* is which, which is the question a user has. It also stops scaling at three formats.
- **The control shows the majority value.** Actively misleading: an editable control reading `MP3`
  implies choosing `MP3` is a no-op, when it would retarget the twelve that are not.

**Recorded before implementation**, per `T126-R4` — the finding about one role meaning two things
on two surfaces, which is this shape exactly.

### Amended 2026-08-05 — `Pause all` is deferred to `REQ-017`

**Raised by:** `T140-R5`, on the reviewer's recommendation. **Maintainer ruling, 2026-08-05.**

Row 9 names four verbs for a playlist header, and `T-140`'s acceptance criteria transcribe them.
Three are built. **`Pause all` cannot be**, and the reason is another accepted decision rather than
an implementation difficulty: `UX-001` made pause a queue-level drain, and `T-080` deleted
`JobStatus.PAUSED` outright once its edges were unreachable. There is no mechanism for holding one
group without touching the rest of the queue, and inventing one is reopening `UX-001`.

**The verb is therefore deferred, not dropped.** `REQ-017` — cross-restart resume, Phase 3 — is
already the named condition under which the `PAUSED` edges may be wanted back, and a group hold is
the same question. Whoever answers `REQ-017` answers this.

Until then **the header offers three verbs**, and `row_verbs.group_verbs()` records the absence in
source so it cannot read as an oversight. A button with nothing behind it would be `T-016`'s
failure — an action that appears to work and quietly does not — which is a worse outcome than a
verb the mockup names and the window does not yet have.

**`T-140`'s criterion is amended to match**, so the task can be complete without the window and the
mockup disagreeing about it. That is the whole point of amending rather than leaving the criterion
unmet: an accepted criterion that cannot be built without reopening a decision is a criterion that
needs a ruling, not an implementer's silence.


**Status:** **Accepted** (2026-08-03) — maintainer decision
**Date:** 2026-08-03
**Amends:** nothing. **Records for the first time** what no document ever held: the shape of the
main window. **Does not amend** `UX-003`, `UX-004` or `T-119`'s row anatomy, all unchanged.

### Context

**The original mockup is gone, and the repository never recorded what it showed.** Three documents
refer to "mockups the maintainer reviewed and chose between" — `TASKS.md`, `STATUS.md` and
`UX-004` itself — and none of them is in the repository. `DECISIONS.md` had no layout entry at all.
`docs/UX_SPEC.md`, which `T-105` owns and which `UX-004` said "should absorb the chosen design",
has never been written.

So what actually shipped was decided **in a source comment**. `main_window._build_body` puts the
history table below the queue in a vertical splitter and argues, in a code comment, that "a tab
would hide it" — reasoning from `P2PLAN-R8`, which is about *which task owns the history view* and
says nothing about where it goes. That comment is the only record, it was never ratified, and it
contradicts the approved design.

The divergence surfaced the first time the application was opened on a screen, on 2026-08-03 —
after `T-118`, `T-119` and four rounds of review had all interrogated the row's *correctness*
without anyone checking the window against the mock.

### Decision

**The main window is two tabs over one list, with no detail pane. Every row carries everything.**

1. **`Queue` and `History` are tabs.** Not a splitter, not one above the other. Each shows a count.
2. **There is no detail pane.** No docked panel, no side panel, no separate window. A row shows
   what a user needs to know about that job, and selecting one does not open anything.
3. **Rows are the `T-119` anatomy** — thumbnail, title, uploader and duration, progress and state —
   in both tabs. History changes what the fields *say*, not what they are: where the queue shows
   progress and speed, history shows the saved path, size and when.
4. **Every verb the row's state permits is visible on its last line**, right-aligned, sharing that
   line with the format control. Running — *Cancel*. Queued — *↑*, *↓*, *Cancel*, **and *Remove***.
   Failed — *Retry*, *Remove*. Done — *Open*, *Show in folder*. Plus `⋯` for the rest, which is also
   the keyboard route.
   - **Amended 2026-08-28: a queued row offers *Remove*** (`T-293`). The maintainer, looking at an
     expanded playlist in the queue, expected to remove one entry without removing the playlist —
     and the row offered *Cancel* instead, which for a job that has never started promises to stop
     something that is not running, leaves a terminal cancelled row behind, and needs a second verb
     to clear it. **§5's own rule is what decides this**: nothing is drawn that would be refused,
     and removing a queued job is never refused. The two-step spelling was an accident of the
     table, not a policy. *Cancel* stays on queued rows, because a job that is queued may start
     between reading the row and pressing anything.
   - **On the existing line, not in a gutter.** The third line already exists to say *as Best
     video*; the buttons sit at its right end. This costs no row height and leaves the title and a
     verbatim extractor message the **full** width, which `NFR-006` needs and a reserved gutter
     narrows. The accepted cost is that the buttons shift position as the verbs change.
5. **Nothing is drawn disabled and nothing is drawn that would be refused.** A row offers only what
   its state permits — the rule `T081-R3` produced, applied to the row instead of the toolbar.
6. **The per-row format control appears only while `retarget()` would accept it** (`T-075`):
   a control on queued and waiting rows, plain text once a download starts.
7. **There is no per-job pause.** `pause()` is queue-wide, in-flight sessions finish, and `T-080`
   removed `JobStatus.PAUSED` outright. So *Pause queue* is a toolbar verb that says *queue*; the
   status bar says what pausing actually does — *"1 download is finishing; nothing new will
   start"* — and a waiting row reads **Held**, never *Paused*.
8. **A finished download stays in the Queue tab** with *Open* and *Show in folder* until *Clear
   finished* moves it on, so the tab in front of you answers "did it work".
9. **History removal is selection-scoped**, its verb names its own count, and *"files are never
   deleted"* is carried in the status bar rather than only in a confirmation.

### Rationale

**Tabs, because the splitter's argument was for a different problem.** The code comment worried
that history would be hard to find. A tab with a count is not hard to find; three panes competing
for vertical space in a window that is wider than it is tall is a real cost, and it is worse since
`T-119` made rows ~66 px.

**No detail pane, because the row already answers the question.** Once a row carries progress,
speed, size and what it will be downloaded as, a second surface repeating that is a second place
for it to disagree — which is the failure `T-059` and `T017-R2` both record in other forms.

**The verbs on the row rather than a toolbar acting on a selection**, because a toolbar verb has
to guess which of two tables it means, and `T-086` already had to solve that by attaching file
actions to each table separately. Putting them on the row removes the question.

**Visible rather than on hover**, because `T118-R12` is exactly that mistake: the per-row format
control was drawn as an empty slot and reachable only by someone who already knew it was there.
A control that appears when you find it is not a control.

### Consequences

- **`HistoryView` is wrong as built.** It is a six-column `QTableView` (`T-100`) and its tests
  assert those columns by name. It becomes a third model behind `ui/row_delegate.py`.
- **`main_window._build_body` loses the splitter**, and the source comment that decided this is
  deleted rather than corrected — it was never the right place for the decision.
- **The job detail view has no home in this layout.** `T-017`'s `JobProgressView` and `REQ-011`'s
  progress bar need a ruling of their own: retire it, or keep it for a route this window no longer
  offers. **Not decided here.**
- **Removing history needs its own decision.** `HistoryRepository` says in its docstring that
  nothing deletes, and no requirement covers removal — `REQ-020` says maintain, `REQ-021` says open
  and reveal. What is removable, and whether a file is ever touched, is a `DAT-` entry, not a
  button.
- **`T-105` writes `docs/UX_SPEC.md` from this entry**, and this entry is the authority until it
  does.

### Amendment, 2026-08-04 — the toolbar, the state badge, and the selection (`T-130`)

**Status:** **Accepted** (2026-08-04) — maintainer ruling on `T-130`.

**Why this amendment exists at all.** `T-130` compared the shipped window against the **B1-b**
mockup and found five differences. None was a violation of this entry, because this entry never
named the toolbar's contents or the row's state chip — which is the *same* gap that produced
`UX-005` in the first place, when the window's layout lived only in a source comment. So the
differences were gaps between a mockup and a decision, and the fix is to make the decision say
what the mockup showed.

**The mockup is now in the repository**, at `docs/mockups/2026-08-03-main-window-b1.html`. This
entry opens by recording that the previous mockup was lost and that three documents referred to
one nobody could produce; `T-130` was only findable because that page still existed as a published
artifact. It will not depend on that again.

| # | Mockup | Ruling |
|---|---|---|
| 1 | **`+ Add URLs` first on the toolbar**, as the primary action | **Adopted.** It is the application's primary action and it was reachable only through the File menu. |
| 2 | *(absent)* — the shipped toolbar also carries `Concurrent downloads:` | **Kept, and recorded here** rather than treated as drift. `ARC-007` put it there deliberately and says Phase 4's settings dialog replaces it; the mockup simply predates that question. |
| 3 | A **state chip** on the title line — `Done`, `Queued`, `62%`, `Failed` | **Adopted for the Queue tab only.** History is excluded on purpose: every history row is finished, so a chip reading *Done* on all of them is noise rather than information. The chip carries **words**, never colour alone (`NFR-005`). |
| 4 | Selection as a **light tint plus an inset bar** | **Adopted.** The shipped full-saturation fill passes contrast at 7.64:1, so this is weight rather than legibility — but on a list of finished downloads it dominates every row it touches. |
| 5 | A status bar carrying **counts and the download folder** | **Declined.** The status bar already has three claimants: `REQ-024`'s environment summary, `NFR-006`'s transient messages, and §9's permanent *"files are never deleted"* promise while History is showing. A fourth, permanent, would crowd the one that is about somebody's files. |

**What this does not change.** Everything in §1–§9 above stands. The row anatomy, the verbs, the
format control's window, the absence of a per-job pause and of a detail pane are all untouched —
this amendment adds the toolbar's contents and the state chip to what is recorded, and settles the
selection's weight.

## Amended 2026-08-04, third — a playlist is many rows, in one folder

> **Row 9 was ruled twice on 2026-08-04 and this is the second ruling.** The first was *one job
> per entry*; the maintainer then asked for a third shape, it was mocked up as
> `docs/mockups/2026-08-04-playlist-rows.html`, and **that is what was chosen** — P1/P2, with the
> segmented bar and the count. The first ruling is kept below the table rather than deleted,
> because a decision record that loses the option it argued against is the failure `UX-005` exists
> to prevent.

Not a mockup question, but a `UX-005` one: it decides what a queue row *is*. Ruled by the
maintainer after a real 16-item playlist downloaded a single file and said nothing about it
(`T-137`).

| # | What | Ruling |
|---|---|---|
| 9 | **One pasted playlist becomes one queue row that opens into its entries** | **Adopted**, to the mockup exactly. Closed it costs one row, so a sixteen-item paste survives beside ordinary downloads; open, the entries sit under it and each carries its own state and its own verbs. It is the only shape where the connection between the files is *visible* rather than remembered, and the only one where a failed entry has somewhere to be reported |
| 9a | **The group's chip counts, it does not measure** — `4 of 16` | **Adopted.** Sixteen files whose sizes arrive one at a time give a denominator that changes as it runs, so a percentage goes *backwards* when a later entry reports a total above its estimate. `Job.progress` already refuses to invent a percentage from an unknown total; this refuses to reintroduce one a level up. A count only goes up |
| 9b | **The group's bar is segmented — one block per entry** | **Adopted.** It draws what the group actually knows, and it gives a **failed** entry somewhere to be seen. Under one continuous bar a playlist that quietly skipped a track looks identical to one that got everything, which is the specific way this feature would lie |
| 9b-i | **Below a stated width the blocks merge to a fixed count, and each takes the worst state inside it** | **Adopted 2026-08-05** by the maintainer, ruling `T-164`. Sixteen blocks in a narrow bar are twelve pixels each and read as noise. The obvious repair — one continuous *done of total* bar — was **rejected**, because it removes precisely what 9b exists for: the failure would have to move into the text, and a bar that can no longer answer the question is not a smaller version of 9b but the shape 9b was adopted against. Merging keeps one guarantee at the cost of a weaker one: **a block no longer means an entry**, but a failure is still visible, and the count is already carried exactly by the chip (`9a`) and the second line. *Constraint:* the merge must read as deliberate — uniform gaps, a fixed block count — because `T-155` was blocks merging **by accident**, and a fix that merges on purpose must not look like that defect returning |
| 9c | **A child row is shorter, not merely indented** | **Adopted.** It drops the format line — every entry inherits the group's — and its thumbnail shrinks, so the indent buys back the width it costs. `UX-005` §3's anatomy is not forked: it is the same row with two lines instead of four |
| 9d | **`Clear finished` clears a group as a unit, when all of it is done** | **Adopted.** A part-done group stays. An entry vanishing from underneath a list the user opened specifically to watch is the opposite of what opening it was for |
| 10 | **Playlist items are written to `<download directory>/<playlist title>/`**, as a fixed rule | **Adopted.** Items that arrived together stay together. *Deliberately not a setting yet:* `T-112`'s output-template editor is where a user-shaped version belongs, and a rule that editor must later be able to express is a smaller commitment than a setting shipped before its editor |

**The rejected shapes, kept because the argument is the record.** *One job per entry* — ruled first
and then reopened — is honest and unreadable: sixteen rows from one paste, with nothing saying they
belong together. *One row reporting `item 4 of 16` and nothing else* is readable and hides fifteen
downloads the user cannot act on; per-item retry and cancel have nowhere to live in it.

**What this costs, ruled with the cost known rather than discovered.** `setUniformItemSizes(True)`
comes off the queue list — it is a promise every row is the same height, and a two-line child beside
a four-line group breaks it. `T118-R10` is the record of what per-row cost buys, so **a paste of 150
with groups open must be measured**, not assumed; that number is the first thing owed, and the one
result that would justify reopening this. The tree is **flattened in the model** rather than the
view becoming a `QTreeView`, which would replace the list, the delegate and the geometry four
findings have already been spent on.

**What this does not decide.** The tab's count. `Queue (2)` for a playlist and one download is
proposed — rows as shown, with the group's own `4 of 16` carrying the detail — because counting
entries makes the number jump when a group is opened. Proposed, not ruled.

## Amended 2026-08-04, again — the toolbar's *appearance*, and what the `⋯` carries

The window was opened a second time, on the build that carried the amendment above. **Adopting
where a control goes is not the same as adopting how it looks**, and the first amendment only did
the former. Four things came out of that sitting; two were defects with a right answer and are
tasks rather than decisions (`T-133`, the spin box with no arrows; `T-134`, painted verbs that do
not react to the pointer). The two below are choices, so they are recorded here.

| # | What | Ruling |
|---|---|---|
| 6 | **`+ Add URLs` is drawn as the mockup's filled brand button** — `primary` fill, `on_primary` text, weight 600 | **Adopted** (`T-132`). The mockup's markup is `<span class="btn primary">`, and the shipped button was a flat toolbar label indistinguishable from `Clear finished`. Amendment 1 put the primary action first and left it looking like one of four equals, which is half a decision. Its **disabled** state is part of the ruling: `T-016` disables it when composition supplied no manager, and a brand fill that stays vivid while inert is worse than the flat label it replaces |
| 7 | **`Pause queue` and `Clear finished` sit at the right edge**, separated from the left group by an expanding spacer | **Adopted** (`T-132`). The mockup's `.spacer{flex:1 1 auto}`. What adds work and what acts on work already queued are different kinds of verb, and packing them together put `Clear finished` next to the concurrency spinner with nothing between them. **`Concurrent downloads:` stays in the left group** — the mockup never had to place it (row 2 above), so the spacer's position against it is this ruling's own choice, not a transcription |
| 8 | **The row's `⋯` carries only the verbs the row could not show**, and is absent when it showed them all | **Adopted** (`T-135`). It listed every verb regardless, so a wide row offered the same three actions twice. The layout already drops verbs that will not fit and already places `⋯` first so it survives — only the menu was never told. *Declined in the same breath:* giving `⋯` menu-only actions (*Copy URL*, *Open details*) to justify its permanent presence. None are built, and inventing actions to keep a button is the wrong order |

| 11 | **The concurrency control steps with labelled `−` and `+` buttons**, not native spin arrows | **Adopted** (`T-141`). The arrows were reported missing twice and were, both times, a rendering question rather than a wiring one: first drawn as solid blocks by the CSS border-triangle trick, then drawn correctly as ~10px native wedges in a 23px control and still unreadable. Measured on the maintainer's own session at the real size: up `4,6,8,10`, down `8,6,4`. **Text cannot be silently un-drawn by a style sheet**, which is the failure mode `T-129`, `T-133` and `T-139` all share, and a label can be asserted by content rather than by wedge geometry |

| 12 | **The tab's count is of downloads, not of lines** | **Adopted 2026-08-04** (`T-140`). This was left *proposed* by the first amendment — "count rows as shown" — and running it settled it: a sixteen-item playlist beside one download read `Queue (17)` open and `Queue (2)` closed, so **the number moved when a user opened a group without the queue changing**. It counts jobs now, so a paste of sixteen reads sixteen at either state |

| 13 | **A playlist has one format, and it lives on the group** | **Adopted 2026-08-04** (`T140-R3`). The mock puts `Download as` on the header *because* the short child rows drop their format line — and the implementation answered no format role on the header at all, so a **collapsed playlist showed its format nowhere**, while each child still offered an editor that could make members differ. The premise and the controls contradicted each other. Entries **inherit**: the header shows the value, retargeting happens on the group, and the per-entry editors go. *Declined:* independent per-entry formats, which would need an honest control on a two-line child and so would reintroduce the clipping `T-136` had just fixed |

**Row 8 corrects a stated reason, not just a behaviour.** `_verb_rects` says the overflow "is the
keyboard route, and a route that relocates is not a route" — which was true when it was written and
stopped being true at `T124-R1`, when both lists took `CustomContextMenu`. Qt raises
`customContextMenuRequested` for the Menu key and Shift+F10, so **the keyboard route is the context
menu** and does not depend on the `⋯` existing. Had that comment still been accurate, row 8 would
have been declined: removing the only keyboard route to a verb is not a presentation change.

### What this does not decide

- Whether there is a whole-queue progress bar. There is none in the accepted design.
- Whether `T-084`'s log view becomes a third tab.
- The row's divergences from `UX-004`'s approved mock — the format control's fixed right slot, the
  fourth line carrying the literal selector, and state as words rather than a badge. Those are
  `UX-004`'s to answer and are filed separately.

---

## OPS-012 — Linux runs on the maintainer's Fedora machines, because it is faster as well as free

**Status:** **Accepted** (2026-08-05) — maintainer ruling
**Date:** 2026-08-05
**Extends:** `OPS-009`'s runner-selection mechanism to Linux. **Does not amend** `OPS-010`, which
governs Windows placement, nor `OPS-005`, which defines what "Windows" means for verification.

### Context

Hosted Actions consumption reached **~90% of the monthly allowance in the first four days** of
August. `OPS-010` had already moved Windows to `STARBASE`, so what remained on the meter was
Linux: roughly 9 billed minutes per push across `check (ubuntu-latest)`, `frozen ubuntu-latest`
and the coverage notice.

The obvious reading is that this is a cost decision. **It is not, and the measurement is why.**
Taken 2026-08-05:

| Environment | Full suite | Note |
|---|---|---|
| Hosted `ubuntu-latest` | **7m36s** | the whole `check` job, install included |
| Maintainer's desktop, i7-14700K | **4m29s** | serial, 2132 passed / 11 skipped |
| Maintainer's laptop, `-n auto` | **58s** | `T-123`, 7x — adoption not done |

The self-hosted machines are **faster than the hosted image**, so this buys development speed and
stops the metering as a side effect rather than the other way round.

### A `STARBASE` Linux VM was considered and rejected

The maintainer proposed hosting Linux in a VM on `STARBASE`, making one machine the testing point
for both platforms. `STARBASE` has the hardware for it — 2x Xeon E5-2650, 16 cores / 32 threads,
32 GB, Windows 10 Pro. It was rejected on three grounds, the first of which is specific to this
project and decisive:

1. **It would invalidate the Windows baseline.** `OPS-007` accepted `T-074`'s unreproduced access
   violation as residual risk on the strength of **361 attempts, zero events** — collected on bare
   metal. Enabling Hyper-V converts the Windows host into a root partition running *on* the
   hypervisor, with different scheduling and different timing. Putting a hypervisor underneath the
   one machine that carries Windows verification, while an intermittent Windows crash is open and
   a Linux segfault was diagnosed the previous day, is a confounder that would have to be chosen
   deliberately and then re-baselined.
2. **It would make the fast half slow.** The E5-2650 is 2012 silicon at 2.0 GHz; the suite there
   is an estimated 13–16 minutes serial against 7m36s hosted and 4m29s on the desktop. `OPS-010`
   explicitly relies on Linux answering in ~7 minutes while Windows runs long.
3. **It would be a single point of failure.** `STARBASE` was offline on 2026-08-03 and `OPS-005`
   needed an amendment to move the Windows gate. With Linux there too, one machine offline is no
   CI at all, on either platform.

The measured soak cost decided the margin: 60 runs for criterion 6(b) is **~4.5 hours** on the
desktop against an estimated 13–16 hours on a contended VM — and an intermittent timing fault is
badly served by a host contending with Windows CI.

### Decision

1. **`vars.LINUX_RUNNER` selects where Linux runs**, exactly as `WINDOWS_RUNNER` does for Windows.
   Unset means `ubuntu-latest`, so a fresh clone and any fork still run hosted and this file's
   default behaviour is unchanged. It governs `check`, `frozen`, and `prose.yml`.
2. **Both the desktop and the laptop register with the same labels**, so a job lands on whichever
   is free. Two runners also mean one machine being asleep does not stop CI.
3. **System packages are installed on hosted images and verified on self-hosted ones.** `apt-get`
   does not exist on Fedora, and a job must not provision a machine somebody uses — run
   `30823595744` is what that costs. The Qt-library step now checks each `.so` with `ldconfig` and
   **fails with the `dnf` command to fix it** rather than skipping silently. Verification, not
   omission: a missing library otherwise surfaces as a puzzling `QApplication` failure hundreds of
   lines later, or as a PyInstaller build failure.
4. **`STARBASE coverage` stays hosted, and is now the only job that is.** It reports when
   self-hosted work did not happen; running it self-hosted would delete the report in precisely
   the case it exists to announce. One billed minute per run is the price of the guarantee, and it
   now reports on Linux placement as well as Windows.

### What is surrendered, in writing

Stated because `OPS-010` stating its own surrenders is what let this entry weigh them.

- **Ubuntu, as a tested platform.** Linux verification becomes Fedora 44. The project's README
  claims "Linux (x86-64)" generally, and `apt`-based installation is no longer exercised anywhere.
  **This is the surrender most likely to produce a user-visible defect**, and the cheapest way to
  reopen it is to leave the nightly hosted.
- **Clean-machine evidence, now on both platforms.** `OPS-010` gave it up for Windows; this gives
  it up for Linux. Nothing in CI now runs on a machine nobody uses. `T-066` — CI installing the
  project differently from how the documentation says to — is exactly the class this used to
  catch.
- **The frozen Linux artifact is now built against Fedora's glibc.** Symbol versioning means a
  Fedora-built binary may not run on an older distro, so `frozen linux` stops being
  evidence that the artifact runs anywhere but here. **`REL-001`'s release build is Phase 5 and
  must revisit where Linux artifacts are produced** — a release built on a developer's desktop is
  a different question from a smoke test run there, and this entry does not settle it.
- **Availability becomes two more machines' availability.** A self-hosted job with no matching
  online runner **queues for up to 24 hours** before GitHub discards it; `timeout-minutes` does not
  bound that, as the `windows desktop` job's comment already records.

### Amended 2026-08-05 — the Linux jobs are named `linux`, not after a distribution

**Raised by:** the maintainer, on first reading a green board after the routing landed.

`check`'s Linux leg was named `ubuntu-latest` and `frozen`'s was `frozen ubuntu-latest`, taken
from the runner image. The moment `LINUX_RUNNER` pointed them at Fedora those names stopped being
true, and **a green check naming a platform nothing ran on is a claim rather than a label** — the
same shape as a test that passes with its subject removed.

`fedora-latest` was considered and rejected: it is wrong in the other direction. Unsetting
`LINUX_RUNNER` restores the hosted Ubuntu image, which is the documented fallback and what a fork
gets, so a distribution in the name is guaranteed to be false under one of the two routings. The
job is therefore named for the **cell it covers** — `linux` and `frozen linux` — while *which
machine took it* is recorded per-run by the runner name, where it is always accurate.

The Windows leg keeps `windows-latest`, which stays true: it is dropped entirely rather than
rerouted when `WINDOWS_RUNNER` is set.

**Older citations of `check (ubuntu-latest)` and `frozen ubuntu-latest` stay as written.** Those
runs did happen on Ubuntu; rewriting them would falsify the historical record to tidy a name
(`AGENTS.md` §6). Only forward-looking references were changed.

### Consequences

- `ai/TESTING.md` §10 is canonical for what runs where and follows this entry.
- `docs/DEVELOPMENT.md` gains the runner-registration procedure; the labels are part of the
  contract, since `LINUX_RUNNER` names them.
- Unsetting `LINUX_RUNNER` restores hosted Linux with no other change — the same one-variable
  reversal `OPS-009` built for Windows.

---

## OPS-011 — A prose-only push runs no CI, and the one gate that read prose moved rather than died

**Status:** **Accepted** (2026-08-05) — maintainer ruling
**Date:** 2026-08-05
**Widens:** `OPS-009`'s `paths-ignore`. **Does not amend** `OPS-010` — Windows still runs on
`STARBASE`, on every push that touches anything a test reads, and still answers asynchronously.

### Context

`OPS-009` exempted four prose paths from CI. The list was too narrow, and the cost is measured
rather than argued. On 2026-08-05, four consecutive pushes to `main` produced **three
cancellations and no Windows evidence**:

| Run | Head | What it carried | Outcome |
|---|---|---|---|
| `30971854157` | `1d87929` | roadmap prose | success, 17m50s |
| `30973364969` | `a884035` | **the only source change** | cancelled at 8m56s |
| `30973765745` | `6b354f0` | roadmap prose | cancelled at 14m46s — `windows desktop` had passed |
| `30974489596` | `a89ace2` | `ai/TASKS.md` — `T-144` filed | cancelled at 2m27s |
| `30974585294` | `d6f50a9` | `ai/TASKS.md` — `T-145` filed | superseded in turn |

**Not one of the cancelled runs carried a source change.** `a884035`'s tree stayed byte-identical
to `main` across `src/`, `tests/`, `packaging/`, `tools/` and `.github/` throughout — every one of
those runs was rebuilding the same code, and each was killed by a commit that only added text.

The arithmetic is the whole argument. `OPS-010` puts three Windows jobs on the one `STARBASE`
slot, so Windows needs **~19 uninterrupted minutes**; task filings were landing every **~2
minutes**. Under `cancel-in-progress`, Windows evidence for the source could not complete at all,
and criterion 8 stayed unevidenced for reasons that had nothing to do with the code.

Two of the offending paths — `ai/roadmap-phase-2.html` and `ai/TASKS.md` — were outside
`OPS-009`'s list. The roadmap by oversight. **`ai/TASKS.md` deliberately**, because
`tests/unit/test_task_placement.py` (`T-096`) reads it.

### Decision

1. **Every prose file in the repository is exempt from `ci.yml`**, enumerated in its
   `paths-ignore` anchor: the eight `ai/*.md` documents, `ai/*.html`, `ai/evidence/**`,
   `ai/handoffs/**`, `docs/**`, `AGENTS.md`, `README.md` and `LICENSE`. Enumerated rather than
   globbed as `ai/**`, so that adding a file is a deliberate act.
2. **`ai/TASKS.md` is exempt too, and its gate moved to `.github/workflows/prose.yml`** — a job
   that runs `tests/unit/test_task_placement.py` and nothing else. **The coverage is unchanged;
   only its cost is.** The test imports `re`, `pathlib` and `pytest` — verified, not assumed — so
   it needs no package install, no Qt and no Windows, and it completes in seconds against ~19
   minutes.
3. **The exemption is symmetric across platforms**, per the ruling: a prose push runs neither the
   Linux gate nor the Windows one. There is no argument for Linux that does not also hold for
   Windows, and an asymmetric rule would be one more thing to remember wrongly.
4. **`prose.yml` takes its own concurrency group.** Sharing `ci.yml`'s would reintroduce exactly
   the collision this entry exists to remove.

### Why this is not the coverage loss `P2EXIT-R4` reversed

That finding was a durable coverage change made for wall-clock and then defended with an argument
about money that did not apply. The distinction here is that **nothing stops being checked.**
Every test that ran before still runs, on both platforms, on every commit that changes anything a
test reads. What changes is that a commit which cannot affect any test no longer pretends to be
evidence — and no longer destroys somebody else's.

The `T-096` placement gate is the case that proves it: the cheap move was to add `ai/TASKS.md` to
`paths-ignore` and stop, which would have silently deleted a gate as a side effect of a speed
change. That is the `P2EXIT-R4` shape, and it was refused.

### What is surrendered, in writing

- **A prose commit is no longer a green tick.** A documentation-only head will show no CI run at
  all, and *"the last green run"* now means the last run over source. Anyone reading the board for
  a phase gate must cite a run against a head that changed code — which is what the citation was
  always supposed to mean, and `P2EXIT-R8` is the finding where it did not.
- **A malformed workflow file in a prose-only push is caught by `prose.yml` only if it touches
  that file.** `.github/**` is not exempt, so `ci.yml` changes still run the matrix.

### Consequences

- `ai/TESTING.md` §10 is canonical for what runs when and follows this entry.
- The three cancelled runs above need no re-run *as such*: the next push that touches source will
  carry the evidence, and until then `a884035`'s source is unchanged from `main`.

---

## OPS-010 — Windows runs on `STARBASE`, on every push, and asynchronously

**Status:** **Accepted** (2026-08-03) — maintainer ruling on `P2EXIT-R4`
**Date:** 2026-08-03
**Supersedes:** `OPS-009`'s runner placement. **Does not amend** `OPS-005`'s definition of what
"Windows" means for verification, which is unchanged.

### Context

Hosted Actions minutes are nearly exhausted, so `WINDOWS_RUNNER` was set to `STARBASE` — which
`OPS-009` explicitly anticipates as the fallback when the allowance runs out. Two consequences
followed, and **only one of them was authorised by that reasoning**:

1. The Windows leg of `check` and the `windows desktop` job then ran the **identical suite on the
   same machine** — 1972 passed, 21 skipped, 32 deselected in both, four seconds apart, serialised
   on one runner slot (run `30861672178`).
2. The full Windows desktop suite was then also removed from ordinary pushes, behind a `[win]`
   commit-message opt-in.

`P2EXIT-R4` found the second to be a durable coverage change made below the authority of an
accepted decision, and it was right. **The quota argument justifies the routing; it never justified
the removal** — the desktop job runs on hardware the maintainer owns and costs nothing. It was
removed for wall-clock and then defended with an argument about money that did not apply to it.

The review also found that the "nightly backstop" offered in its place **was not guaranteed**: a
global `cancel-in-progress: true` let any ordinary push cancel a scheduled run, and the replacing
push could skip Windows entirely.

### Decision

1. **Windows work runs on `STARBASE`** while `vars.WINDOWS_RUNNER` names it. This part of `OPS-009`
   stands, and its fallback condition — the hosted allowance running out — has been met.
2. **The Windows leg of `check` is dropped while that variable is set.** It duplicates the
   `windows desktop` job on the same machine, and the *clean-machine* evidence that justified it
   is precisely what routing to a desktop destroys. Unset the variable and the leg returns.
3. **The full Windows desktop suite runs on every push**, restored. Not nightly-only, not
   `[win]`-gated.
4. **Windows evidence is asynchronous.** It runs in parallel with the hosted Linux gate, which
   lands in ~7 minutes; the Windows result arrives when it arrives. **Work continues while it
   runs.** It is required before a task or phase is reviewed — not a barrier to carrying on.
5. **A scheduled run cannot be cancelled by a push.** Scheduled runs take their own concurrency
   group and set `cancel-in-progress: false`.

### What is surrendered, in writing

Both of these go with the routing and would return if `WINDOWS_RUNNER` were unset:

- **Clean-machine Windows evidence.** A fresh hosted image proves the application works somewhere
  nobody has been. `STARBASE` is a machine somebody uses, with a history.
- **The offscreen platform plugin on Windows.** The real `windows` plugin on Windows and
  `offscreen` on Linux both remain, and they bracket it — but the cell itself is not covered.

**Neither is a hidden cost.** They are stated here so that the next person to read a green board
knows what green does and does not mean, which is what `OPS-009` was for and what a workflow
comment could not carry.

### Consequences

- `ai/TESTING.md` §10 is the canonical statement of what runs when, and follows this entry.
- The `STARBASE coverage` job says when the hosted Windows leg did not run, so the surrender is
  visible in the run rather than only here.
- **Three Windows jobs serialise on one runner slot**, so a push takes roughly 19 minutes to
  produce Windows evidence against ~7 for Linux. If that becomes the constraint, `T-123` — running
  the suite in parallel — is the lever, **not** removing coverage. That is the trade this decision
  exists to refuse a second time.

---

## OPS-009 — Where each CI job runs, now that `STARBASE` is back and minutes are metered

**Status:** **Superseded by `OPS-010`** (2026-08-03) for runner placement; **Accepted** (2026-08-03) — maintainer decision
**Date:** 2026-08-03
**Raised by:** the maintainer, on 2026-08-03: *"we should use STARBASE as much as possible going
forward because github has limited use and we've burned most of it already"*

### Context

Two things changed on 2026-08-03. `STARBASE` came back online after being unreachable since
2026-08-01, and the maintainer reported the repository's hosted Actions allowance is nearly spent.

**`OPS-005`'s amendment has already expired by its own terms.** It says in as many words:
*"This amendment reopens the moment `STARBASE` is reachable again: it is while unreachable, not
instead of."* So the desktop slice returning to `STARBASE` needs no decision — that is the
amendment ending, not a reversal of it. What needs deciding is everything else.

**The repository is private, so minutes meter, and Windows meters at 2×.** Measured from run
`30786142921`:

| Job | Platform | Wall time | Billed multiple |
|---|---|---:|---:|
| `windows-latest` | hosted | 11m 04s | **2×** |
| `ubuntu-latest` | hosted | 6m 32s | 1× |
| `frozen windows-latest` | hosted | 2m 20s | **2×** |
| `frozen ubuntu-latest` | hosted | 1m 28s | 1× |
| `windows desktop` | `STARBASE` | — | **0** |

The two Windows jobs bill roughly 27 minutes against the two Linux jobs' 8. **Windows is where the
allowance goes**, and it is exactly what `STARBASE` can run natively.

### The decision this asks for

Move `windows-latest` and `frozen windows-latest` onto `STARBASE`, keep the Linux jobs hosted, or
some other split. Three considerations, stated so the choice is informed rather than obvious:

1. **`STARBASE` becomes a single point of failure for all Windows evidence.** Today, if it is
   offline the desktop slice skips and hosted Windows still gates. If it carries everything, an
   offline machine means *no* Windows evidence at all — and `OPS-005`'s amendment exists precisely
   because that happened for two days.

2. **A skipped job is silent, and that silence has already cost something.** The
   `STARBASE_AVAILABLE` guard makes an absent runner skip rather than queue, which is right — but
   it means config for that machine keeps merging unverified. `dd9c238` added two `shell: pwsh`
   steps while `STARBASE` was unreachable; the machine has no PowerShell 7, and the whole desktop
   slice failed at its first step the moment it came back. **Two days of green CI, and nothing
   could see it.** Whatever this decides, more work on `STARBASE` means more surface that goes
   unverified whenever it sleeps.

3. **Hosted runners are the only clean-machine evidence there is.** `STARBASE` has a developer's
   Python, PATH and installed tooling. A hosted image proves the project builds somewhere that has
   never seen it — which has caught real defects, including 38 Windows-only failures in one push.

### Decision

**Ruled by the maintainer, 2026-08-03**, on all four points, with one addition of theirs:

1. **Documentation commits no longer trigger CI.** `paths-ignore` covers `ai/REVIEWS.md`,
   `ai/handoffs/**` and `docs/**` — deliberately *not* all of `ai/`, because
   `tests/unit/test_task_placement.py` reads `ai/TASKS.md` and a filter written against "docs" as
   a category would skip a gate.
2. **A skipped self-hosted job says so.** The `STARBASE coverage` job always runs, costs seconds
   on Linux, and emits a warning naming what did *not* execute.
3. **`frozen windows` moves to `STARBASE`; `windows-latest` stays hosted.**
4. **PowerShell 7 is not required.** Those steps run on 5.1 (`bff9713`).

**And the maintainer's addition:** *"if I run out of tokens to use on GitHub Actions, we'll have
to use STARBASE for both."* So the hosted Windows leg reads its runner from a **variable**:
`WINDOWS_RUNNER`, unset meaning `windows-latest`. Exhausting the allowance is then

    gh variable set WINDOWS_RUNNER --body '["self-hosted","windows","desktop"]'

rather than a code change under time pressure — and setting it back is the same command. The
default encodes the ruling; the variable encodes the fallback.

### The reasoning behind point 3

**Move `frozen windows-latest` to `STARBASE` and leave `windows-latest` hosted.** The frozen job is
a packaging check whose value is mostly "does the artifact run at all", which a real machine answers
as well as a clean one; the full-suite Windows job is where clean-machine evidence actually pays.
That is roughly a third of the Windows spend for the smallest loss of independence.

**And make skipping loud.** If `STARBASE_AVAILABLE` is unset, the run should still *say* which jobs
did not execute, so the gap is visible in the run rather than only in this file.

### Two cheaper savings, found while writing this

Both are larger or safer than moving a job, and neither costs any coverage.

**Documentation commits spend Windows minutes.** `ci.yml` triggers on every push with no path
filter, so editing a file under `ai/` runs the full matrix — including two Windows jobs at 2×. A
`paths-ignore` for `ai/**` and `docs/**` removes a whole category of spend and weakens no gate,
because no test reads those files. *(The one caveat: `tests/unit/test_task_placement.py` and the
schema-drift tests do read `ai/TASKS.md` and `persistence/schema.sql`, so the filter has to be
written against paths nothing asserts on, not against "docs" as a vibe.)*

**`cancel-in-progress: true` discards evidence as readily as it saves minutes.** It is the right
default for superseded work, but it means any later push — however trivial — throws away a run
somebody is waiting on. **Demonstrated the same night this was written:** a docs-only push
cancelled four in-flight jobs on `bff9713`, including the first desktop-slice run since 07/29, and
the two Windows jobs among them were the expensive kind. Batching pushes when a run's result
matters is a habit rather than a setting, but it is worth writing down because the failure is
silent — the run simply reports `cancelled`, which reads as nothing having happened.

### Not decided here

Whether to install PowerShell 7 on `STARBASE`. The two steps that needed it now run on Windows
PowerShell 5.1 (`bff9713`), so it is no longer a prerequisite for anything.

---

## DAT-006 — The completion ledger: what it stores, and what it deliberately does not

### Withdrawn 2026-08-06 — there is no ledger, so there is nothing to decide

**Status:** **Withdrawn**, by maintainer decision the same day it was written. **It was never
accepted**: `T169-R1` found it self-headed as *Accepted "on maintainer direction"* when the
direction had established the product boundary — a lightweight downloader with no browseable
History — and not the detailed choices in §§1–6. That finding is correct and is the same authority
distinction as `T145-R1` and `T144-R1`: satisfying a decision's trigger makes it eligible for a
ruling, not self-ratifying.

**The ruling, when it came, was that the ledger should not exist.** `REQ-020` is withdrawn: Tracks &
Trails keeps no record of what has been downloaded, not even a private one. `REQ-022` is scoped to
the live queue, where a duplicate is confirmed rather than refused and no storage is involved.

**What the two review rounds actually showed.** Five findings, two of them High — an unratified
decision, retained credentials, a non-atomic backfill, credential-lowercasing, and duplicate rows
that broke the one-row invariant. **Not one was about the warning being wrong or unwanted; every one
was about keeping the data.** A feature whose entire cost is in its storage, and whose storage is
the only durable index of a user's viewing this application holds, is a feature a lightweight
downloader can decline.

**What survives, for whoever reads this next:**

- **The failure-direction argument** was sound and is worth reusing: a missed duplicate costs a
  warning that does not appear; a false one warns about the wrong file. Only the second lies.
- **§5's reasoning against dropping columns** — SQLite makes a column drop a table rewrite, on a
  table holding a user's own records — still governs migration `0008`'s now-unused
  `normalised_url`, which stays where it is. — **Superseded 2026-08-06 by the legacy-data ruling
  below: the whole table is dropped, so there is no column left to keep.** The reasoning itself is
  still sound and still applies to the next author who wants to tidy a *live* table; it simply has
  no subject here any more.
- **`T170-R1`'s lesson outlives its migration**: a Python step that runs after its version bump has
  committed leaves a database that is durably "migrated" with the data half missing, and no later
  run will revisit it. If a data-transforming migration is ever written here, it belongs inside the
  transaction.

### Legacy-data ruling 2026-08-06 — the rows already written are purged on upgrade

**Status:** **Accepted**, by explicit maintainer ruling.
**Raised by:** `T169-R3`, which found the gap.
**Implemented by:** migration `0009_drop_history.sql`.

**The question.** Withdrawing the ledger stopped new writes and deleted every reader, but it left
the table where it was. `T169-R3` measured the consequence for an upgraded installation rather than
a fresh one: opening the frozen v7 database on the withdrawal head kept all three rows, source URLs
and output paths included, with no route in the application to see or clear them. So `REQ-020` said
the application keeps no record of what has been downloaded while the database on disk kept one —
and of the two, the database was telling the truth.

**Why this needed a ruling and not a judgement.** Deleting a user's own rows is destructive and
irreversible, and nothing in "remove the History screen" implies it. `T169-R1` had just established
the same distinction one level up: satisfying a decision's trigger makes it eligible for a ruling,
not self-ratifying. An implementer who inferred the purge would have been making the larger version
of that mistake, on data instead of on design.

**The ruling: purge them.** Migration `0009` drops the table. Two alternatives were put alongside it
and both were declined:

| Considered | Why not |
|---|---|
| Keep a bounded clearing route until the rows are gone | Non-destructive, and it puts the choice in the user's hands — but it restores the Settings screen the withdrawal had just removed for having nothing in it, and leaves the contract false until somebody clicks the button. A control whose only purpose is to finish a removal is a removal that has not finished. |
| Preserve the rows, amend `REQ-020` to admit them | No data loss and no migration risk — but the application would then durably hold download URLs it promises not to keep, unreachable and unclearable. That is the shape of `T169-R2`, which is the finding this whole arc began with. |

**What the purge is, exactly, and what it is not.** The rows become unreachable by every query and
the table stops existing, which is what makes `REQ-020` true. **The bytes in the database file are
overwritten as well**, because `0009` sets `PRAGMA secure_delete = ON` before the drop — without it
SQLite frees the pages without zeroing them and every purged URL stays legible in the file. The
pragma is set explicitly rather than relied on: it is a compile option, on by default in the build
this was written against and quite possibly off in a bundled or Windows SQLite, and an erasure that
depends on who compiled the library is not an erasure the application can claim.

**What it still is not is a guarantee about the whole of a user's disk.** In WAL mode the old
content also lives in the `-wal` sidecar until a checkpoint retires it, and a hard exit before that
leaves it there; `secure_delete` does not reach it, and neither can a migration, since `VACUUM`
cannot run inside the transaction carrying the version bump. **A user who wants no trace must
delete the database together with its `-wal` and `-shm` siblings** — deleting `library.sqlite3`
alone can leave a `library.sqlite3-wal` holding exactly what they meant to remove.

*(Corrected 2026-08-06 after `T169-R6`. This first said the purge was "not a secure erase" and that
nothing could be done from inside a migration, which was wrong twice: `secure_delete` is settable
in the migration script and does zero the freed pages, and the advice to "delete the database file"
omitted the sidecars that are the actual residue. The mistake was assuming a limit instead of
measuring one.)*

**One consequence worth naming.** `0009` is the only destructive migration in the project, and it
inverted a test that had been correct since `T-014`: `ai/TESTING.md` §7's rule that every seeded row
survives every migration. That rule now covers `jobs` only, and the purge carries its own regression
proving the opposite for `history` — including that the plaintext is absent from *every* table
afterwards, so a future migration that "preserved" the record by relocating it fails rather than
passes. A destructive migration must also be a narrow one: a second test holds v8's job rows and
their queue positions across the same run.

---

The original entry follows unaltered, as the record of a design that was built, reviewed and
withdrawn inside one day.

**Status:** ~~Accepted~~ **Withdrawn** — see above
**Date:** 2026-08-06
**Raised by:** `T-169`, on maintainer direction of the same day.
**Amends:** `DAT-001`, `DAT-005`, `UX-005` — see the three amendment notes below, appended to those
entries rather than written over them.
**Unblocks:** `T-170` (the implementation) and `T-114` (duplicate warning).

### Context

Tracks & Trails is a lightweight downloader, not a media-library tracker. `REQ-020` promised the
opposite product — a browseable history of completed downloads with title, path, format, size and
per-record removal — and Phase 2 built it. Removing the tab alone would leave an accepted contract
requiring its return, or break `REQ-022`'s duplicate warning, which is the one durable behaviour
that still earns its cost. `T-169` reconciles the contract; this entry decides the data.

### Decision

**1. The identity is the URL the user entered, normalised, and nothing else is the key.**

Not the resolved media URL. That distinction is the whole of this entry's privacy story: what
yt-dlp resolves is a signed, expiring CDN address, and storing one would make transient
authorisation material durable to answer a question the entered URL already answers. The user
pastes the entered URL again — that is the thing a duplicate check must recognise.

**2. Normalisation is minimal, and the reason is false positives, not purity.**

Lower-case the scheme and host; drop the fragment. **Nothing else** — in particular no
query-parameter stripping, because the identity of a video lives in the query on the largest site
this application serves (`?v=…`), and a rule clever enough to strip tracking parameters per site is
a rule that will one day treat two different downloads as one. A missed duplicate costs a warning
that does not appear; a false one costs a warning about the wrong file, and only the second is a
lie.

**3. Three fields, and each answers a question the warning asks.**

| Field | Why it is kept |
|---|---|
| the normalised key | what `REQ-022` looks up, and what the index is on |
| the URL as entered | what the warning shows the user, since a normalised key is not what they typed |
| the completion time | `docs/UX_SPEC.md` `P-11`: the warning names **when** |

**Title, output path, format used, size, thumbnail URL and playlist membership are not kept.** Each
existed to draw a history row. No row remains to draw, and a path in particular is a claim about
where a file is that this application has just stopped making (`REQ-021`).

**4. One row per identity, updated in place.**

A repeat download after an override updates the completion time rather than appending a second row.
The question is *"have I downloaded this, and when last"*; a list of every attempt answers a
question nobody asked and grows without a retention policy to bound it.

**5. Obsolete columns stop being written. They are not dropped.**

The existing `history` table becomes the ledger. New completions write the three fields above and
leave the rest `NULL`; no migration rewrites or drops a column.

Two reasons, and the first is the operative one. **A destructive schema rewrite is the one change
in this task that can lose a user's data**, and SQLite's column drop is a table rebuild — the
riskiest possible way to end a task whose whole purpose is to remove a feature. Second, the old
rows are the upgrade data `T-114` needs: an installation that has been downloading for months
already knows what it has fetched, and dropping the table to tidy it would throw that away to save
bytes nobody is short of.

The rows that already exist keep the fields they were written with. Clearing the ledger removes
them, which is the user's control over data this decision no longer collects.

**6. The ledger never becomes a second home for credentials.**

Cookies, authorization material and proxy credentials are request fields and are not part of the
identity; `REQ-026` already forbids a cookie path reaching a durable record, and this entry does not
widen what is stored. The entered URL may itself contain a token a user pasted — that is the user's
own input, retained because they will paste it again, and removed when they clear their records.

### Alternatives considered

**Drop the obsolete columns in a migration.** Rejected under §5. The tidiness is real and the risk
is a table rebuild on every user's database to reclaim space that costs nothing.

**Keep a row per download rather than per identity.** Rejected: it needs a retention policy, and
`REQ-020` now promises no automatic expiry.

**Hash the URL rather than storing it.** Rejected. The warning has to show the user *which* URL,
and a hash cannot; it also buys nothing, since the plaintext URL is what the user typed and will
type again.

### Consequences

- `T-170` deletes the History view, its thumbnails, grouping, refresh subscriptions and filesystem
  probes, and narrows `HistoryRepository` to the ledger's three fields plus the clear.
- The duplicate lookup needs an index on the normalised key. Without one it is a table scan on
  every paste, which is `NFR-001`'s budget spent on a warning.
- Old rows have no normalised key. The upgrade computes it for existing rows once, which is the
  only migration this decision authorises, and it is additive.

### Not decided here

Whether a downloaded **file** should carry provenance — `T-171` owns that and it is not a
prerequisite for any of the above.

---

## UX-006 — The queue does not run until it is started, and it is stopped at every launch

**Status:** **Accepted** (2026-08-07) — maintainer decision, taken from the Implementer's
recommendation
**Date:** 2026-08-07
**Supersedes:** nothing. **Amends** `UX-001` — its *default*, not its semantics — and `REQ-015`.
Also amends `REQUIREMENTS.md` §11 criterion 1, whose casual-saver flow now has a `Start` in it.

### Context

A job starts the moment it is added, unless the user pressed `Pause queue` first. So the only way
to review a batch before it runs is to have anticipated wanting to — and the cost of not
anticipating scales with the batch: a playlist staged against the wrong preset is not one wrong
download but sixteen, already spending bandwidth by the time the mistake is legible.

**The mechanism for the alternative is already built.** `DownloadManager` holds a queue-level gate,
and `T080-R1` established the two properties that make it usable as more than a panic button: a
download added while the gate is closed is **parked and stays durably `QUEUED`** rather than
refused, and a **probe is admitted anyway**, because reading is not the work pause exists to stop.
What was missing was never machinery. It was the default.

### Decision

**The queue runs only after the user starts it.**

1. **The gate is a mode with two states — running and stopped — and it is stopped at launch.**
   `Start` opens it, `Stop` closes it.
2. **A started queue stays started.** It runs what it holds and everything added afterwards, until
   it is stopped or the application exits. Draining does not re-arm it: a queue that empties and
   then receives a URL starts that URL.
3. **Stopped is not refused.** Adding to a stopped queue enqueues durably and starts nothing; the
   row reads **Held**, the word `UX-005` already gives a waiting row.
4. **`Stop` drains, exactly as `UX-001` says.** In-flight sessions finish, nothing new starts, no
   partial file is created by stopping, and no job ever enters `PAUSED`.
5. **Probes are never gated** (`T080-R1`, unchanged). A stopped queue still resolves a paste — a
   staging list that could show nothing would defeat the review this decision exists to enable.
6. **The gate is queue-level and stays there.** No per-row `Start now`, no per-job hold. `P-10` and
   `T-113` decide per-job control on resume's terms, later and separately.
7. **Everything that starts work observes the gate**, including automatic retry (`UX-002`) and a
   user's `Retry` on a failed row. A retry is a *new* session, not the continuation of a draining
   one, so a stopped queue parks it.
8. **The gate is not persisted, because it does not need to be.** It is stopped at every launch, so
   there is no state to carry across one.

### Rationale

- **It is the review the user asked for, and nothing else changes.** Every alternative that
  produces a checkable batch either invents a second queue state or a per-job hold; this one
  changes which side of an existing gate the application starts on.
- **A relaunch that downloads on its own is a defect this fixes in passing.** Today, restoring a
  queue restores work in progress with no user action — including after a crash, and including
  when the user's reason for relaunching is to remove something.
- **Draining keeps `UX-001`'s best property.** Nothing the user presses produces a half-written
  file, so Phase 3's resume work inherits no partial-file policy it did not choose.
- **Mode rather than batch-commit, because the alternative is unexplainable.** If `Start` released
  only what was queued at that instant, a URL added to a running queue would sit `Held` beside jobs
  that are running, with the difference visible nowhere.

### Consequences

- `REQ-015` is amended and its superseded wording preserved in place; `REQUIREMENTS.md` §11
  criterion 1 gains the `Start` press.
- `docs/UX_SPEC.md` §2.1's `Pause queue` becomes a `Start`/`Stop` control, and §2 item 7's "there is
  no per-job pause" is unchanged and now load-bearing for a second reason.
- **The empty-queue and first-run states carry a new burden.** A user who pastes a URL, presses
  *Add to queue* and waits will wait forever if `Start` is not obvious. `T-181` owns making the
  stopped state legible — this is the risk the decision creates, not a detail of it.
- **Automatic retry must be asserted against the gate**, not assumed to follow it. `UX-002`'s
  backoff schedules work up to eight seconds out; the assertion is that a queue stopped in between
  parks the attempt rather than running it.
- `T-181` implements. Nothing else in Phase 3 depends on it.

### Alternatives considered

- **Batch commit, re-arming when the queue drains.** Rejected per the rationale: it is closest to
  the literal request and produces a held row nobody can explain.
- **A setting restoring start-on-add.** Rejected *for now* rather than on principle. It is the
  compatibility escape, and it costs a second behaviour in every spec clause, test and support
  answer for a preference nobody has yet expressed. It reopens if the stopped default proves
  unwanted in use.
- **A per-row `Start now`.** Rejected: it reopens `UX-001` and `P-10` ahead of `T-113`, and needs a
  rule for what it means against the concurrency limit that neither this decision nor that task has
  yet had to take.

---

## ARC-010 — Option coverage is typed fields plus one validated escape hatch

**Status:** **Accepted** (2026-08-07) — maintainer decision, taken from the Implementer's
recommendation
**Date:** 2026-08-07
**Supersedes:** nothing. **Extends** `REQ-009`'s escape-hatch pattern from format selectors to the
rest of yt-dlp's option surface. **Constrains** `P-12` and `P-18` in `docs/UX_SPEC.md` §10, which
asked the same question one option group at a time.

### Context

The product exists to be the GUI for yt-dlp (`REQUIREMENTS.md` §1), and yt-dlp exposes roughly 250
options across sixteen groups. `DownloadRequest` can express eleven things; Phase 3 and Phase 4
between them add perhaps fifteen more. Whole groups — video selection filters, download tuning,
most of the filesystem group, thumbnails, extractor arguments, workarounds — have no representation
at any layer, and no task proposes one.

**Total flag parity is the wrong target and cannot be met honestly.** A large part of that surface
*is* the command line rather than a capability: `--simulate`, `-O/--print`, `-j/--dump-json`,
`-a/--batch-file`, the progress and quiet flags, `--config-locations`, `--alias`, `--newline`. This
application is the caller — `ytdlp_adapter.build_options` already sets several of them for the
worker to function at all — and exposing them would be exposing its own plumbing.

### Decision

**The target is capability parity: no download reachable from the command line is unreachable from
this GUI.** It is met two ways, and both are required.

1. **Typed fields for what users reach for.** Per option group, with a declared field on the model,
   validation, and a test — the shape everything in `DownloadRequest` already has. The
   option-coverage phase in `IMPLEMENTATION_PLAN.md` schedules them.
2. **One escape hatch: *Additional yt-dlp options*,** per preset and overridable per job, taking
   command-line syntax. This is what makes the parity claim true before every widget exists, and it
   is the same trade `REQ-009` already took for format selectors — with the same justification,
   that an expert reaching for syntax they already know is better served than blocked.
3. **The hatch is parsed and validated, never passed through.** Three invariants bind it and none
   is negotiable:
   - **Containment** (`T-034`). Options that redirect where files land — `-P/--paths`, `-o` — are
     subject to the same containment check as the output template, or the escape hatch becomes the
     way to write outside the directory the user chose.
     > **Corrected 2026-08-07 by `SEC-003`.** This listed `--exec` among them, and containment
     > cannot reach it: `T-034` contains the paths *yt-dlp writes*, and a shell command writes
     > wherever it likes. `--exec` and `--exec-before-download` are **forbidden** and sit on the
     > refusal list instead. Left standing, an implementer building the hatch to this decision
     > would have believed a check was guarding something it cannot see — which is the shape of
     > defect this project keeps finding, committed inside a decision rather than a commit.
   - **Redaction** (`DAT-003`, `DAT-004`). An option value can carry a secret. What the user types
     here is *our* text under `DAT-004`'s provenance rule, and is redacted as such.
   - **Typing** (`ARC-002`, `ARCHITECTURE.md` §8). It is one declared, validated member of
     `DownloadRequest` — parsed into a checked structure at job-creation time, not an untyped dict
     handed to `build_options`. A frozen, picklable, persisted request stays exactly that.
4. **A refusal list exists, and refusals are stated at edit time with the reason** — never accepted
   and silently dropped. The application owns `outtmpl`, `format`, `progress_hooks`, `logger`,
   `quiet`, `paths` and the simulation flags; an option that would fight the GUI for control of its
   own process is rejected where the user typed it (`UX-005` §5).
5. **The hatch does not widen `REQ-EXCL`.** Options excluded on scope grounds are excluded here
   too, by the same refusal list. `T-182` rules on which families those are.

### Rationale

- **A wrapper that cannot express what it wraps has a ceiling**, and the ceiling is where the user
  goes back to the terminal — which is the outcome the product exists to prevent.
- **Widgets alone never finish.** Two hundred options at one task each is not a backlog anybody
  drains, and the options nobody built are exactly the long tail an expert needs.
- **The hatch alone is not a GUI.** It would make every capability reachable and none discoverable,
  which fails `REQUIREMENTS.md` §1's *approachable by default* half as completely as the current
  state fails *complete when you dig*.
- **Validation is what separates this from `--` passthrough.** Passthrough would make the security
  and containment boundaries this project has already paid for optional at the user's typing.

### Consequences

- `REQ-030` and `REQ-031` state the coverage target and the hatch in the requirements.
- **`P-12` is effectively answered and `P-18` is narrowed.** The five undedicated post-processing
  options get typed fields (`P-12`: typed, not strings in `post_processors`), and the free-text
  field `P-18` proposed refusing is granted at the *request* level with the validation above rather
  than as a raw post-processor list. Both stay listed in §10 until `T-109`'s screen is specified
  against them; this decision is what they are now specified against.
- **`build_options` becomes the merge point of two sources**, and its precedence needs a rule:
  typed fields are the request, the hatch may not override an application-owned key, and where both
  name a user-owned key the typed field wins because it is the one with a visible control.
- **The risk this creates is that the hatch becomes the roadmap.** An option typed into the free
  field often enough is evidence for promoting it to a control; the phase's exit criteria name
  promotion so it is work rather than good intentions.
- **`requires_ffmpeg` widens.** It derives from the post-processor class hierarchy today, which is
  the right mechanism and now has to run over processors the hatch installed.

### Alternatives considered

- **Typed widgets only.** Rejected: safest and most discoverable, and it leaves parity permanently
  a phase away — the long tail is never worth one task each, so it never gets built.
- **Escape hatch first, widgets later.** Rejected as a *sequence* while being adopted as a
  capability: shipping the text field before the common options have controls makes the CLI the
  real interface and the GUI a launcher for it.
- **Raw `--` passthrough, unvalidated.** Rejected: it makes containment and redaction opt-in, and
  those are the two boundaries whose breach `AGENTS.md` §10 puts in the Critical band.

### Not decided here

Which option families `REQ-EXCL` forbids, permits, or permits in a narrowed form — credentials,
`--impersonate`, `--xff`, `--exec`, `--download-archive`. **`T-182` owns that ruling**, and no
typed field or refusal-list entry for those families may be written until it is taken.

---

## UX-007 — The Phase 3 surfaces, ruled: all 25 open `[P]` clauses

**Status:** **Accepted** (2026-08-07) — maintainer decision, taken question by question from the
Planner's recommendations in `ai/handoffs/2026-08-07-ux-spec-ruling-pack.md`
**Date:** 2026-08-07
**Supersedes:** nothing. **Ratifies** every `[P]` clause in `docs/UX_SPEC.md` §10, which §1 barred
any task from building until it was ruled on. **Three are ratified against what the file
proposed** — see below, because that is the part a reader will otherwise get wrong.

### Context

`docs/UX_SPEC.md` §1: *"no task may build a `[P]` clause until it is ratified."* Twenty-five were
open, and every remaining Phase 3 deliverable's **surface** was decided by at least one — `T-107` by
`P-1` and `P-14`, `T-108` by `P-2`, `P-13`, `P-15`, `T-109` by `P-16`, `P-3`, `P-4`, `P-17`, `P-18`,
`T-110` by `P-19`, `P-5`, `P-25`, `T-111` by `P-6`, `P-7`, `P-20`, `P-21`, `T-112` by `P-9`, `P-22`,
`P-23`, `T-113` by `P-10`, `P-24`, `T-114` by `P-26`, `P-27`, `P-28`.

So eight deliverables were *startable* — nothing preceded them — and none was *finishable*, because
finishing meant drawing a surface nobody had settled. That distinction was not on the roadmap board
until 2026-08-07, and it was the phase's real blocker rather than any dependency.

### Decision

**Three were ruled against the proposal in the file**, and those clauses are rewritten rather than
re-marked:

- **`P-1` — the format table is an expanding row, not a modal.** §4 proposed a modal dialog. A modal
  opened from the add dialog is a modal over a modal, and the staging list is already a list of rows
  that open; `P-19` takes the same shape for the playlist picker, so the two surfaces are **one
  mechanism** rather than two.
- **`P-10` — per-job pause is `T-113`'s to decide, not this file's.** §9.2 proposed that resume
  keeps the queue-level drain. The ruling is that the answer depends on what resume turns out to
  cost per site and format, and `T-113` is scheduled early to find that out. **`T-113` must record
  the answer either way**, including whether `JobStatus.PAUSED` returns and whether a playlist
  header gets `Pause all` (`T140-R5`). `UX-001` named `REQ-017` as its reopening *condition*, not
  its answer.
- **`P-22` — the template preview is a focusable read-only field.** §9.1 proposed unfocusable
  read-only text, and stated the argument against itself: a user who cannot `Tab` to the preview
  cannot review it at their own pace. That argument won. It costs one stop in the tab order.

**The remaining twenty-two are ratified as written**, and the summary is:

| # | Ruled |
|---|---|
| `P-2` | Video+audio is a **mode** on one table, not two pickers |
| `P-3` | The post-processing editor is reachable as a per-download *Options…* **and** from the preset manager |
| `P-4` | A one-off change offers *Save as preset…* **explicitly**; it never becomes one silently |
| `P-5` | Playlist entries carry **checkboxes**, the group header a tri-state |
| `P-6` | **One** preset list, built-ins included and marked |
| `P-7` | **Always exactly one** default preset; deleting it promotes another |
| `P-9` | The template editor lists supported fields **inline** |
| `P-13` | With ffmpeg absent the merge mode is **hidden, with the reason in its place** |
| `P-14` | The format table refuses re-probe, download-from-table and filtering |
| `P-15` | Merging refuses three-way, external audio and automatic pairing |
| `P-16` | `T-109` and `T-111` **share one screen**, reached two ways |
| `P-17` | Subtitle languages are a **multi-select, populated from the probe's own languages** |
| `P-18` | The free post-processor list stays refused (`ARC-010`); **per-entry post-processing is refused too** |
| `P-19` | The playlist picker is the **staging row, opened** |
| `P-20` | The preset manager is a **list beside a form, with buttons** |
| `P-21` | Presets refuse import/export and per-site rules |
| `P-23` | A containment failure is shown **at edit time, with the reason** |
| `P-24` | A non-resumable job **says so on its row** and offers *start again* as its own verb |
| `P-25` | The playlist picker refuses filtering |
| `P-26` | The duplicate warning is a **staging-row state** |
| `P-27` | **Ordinary *Add to queue* is the override**, and the count includes duplicates |
| `P-28` | Duplicate detection refuses content matching and automatic skipping |

**`P-17` answers a second question the clause did not ask.** `SUBTITLE_LANGUAGES` is `("all",)`
today, so *what the user picks from* was unspecified. The list comes from **the probe's own
languages for that URL**, which is why the control belongs beside a probed row rather than in a
preset — and a preset carrying languages a given video does not have is the case `T-109` must
handle rather than assume away.

### Rationale

- **Six of these are scope refusals and were ruled as one line** (`P-14`, `P-15`, `P-18`, `P-21`,
  `P-25`, `P-28`). Each is recorded as *the boundary of Phase 3's UI* rather than a judgement that
  the feature is bad, which is what keeps it cheap to revisit as its own task.
- **The shape questions went the way that reuses a mechanism** rather than adding one: an expanding
  row twice (`P-1`, `P-19`), one table with a mode (`P-2`), one preset list (`P-6`), one editor
  reached two ways (`P-16`, `P-3`).
- **The accessibility questions went to the reader's control** (`P-22` focusable, `P-9` inline
  fields, `P-24` say it on the row): in each the alternative was cheaper to build and left the user
  with less.
- **`P-23` also settles `T-112`'s acceptance criterion**, which carried the same proposal. One
  ruling, two documents — they must not be answered separately.

### Consequences

- **`docs/UX_SPEC.md` §10 is closed.** Every clause is `[T]`, the table records what was ruled, and
  the file's §1 bar no longer stops anything.
- **Eight task entries lose their "unruled" caveats** — `T-107` through `T-114`. Leaving them is the
  `T105-R4` defect exactly: a task entry stating a settled thing as open is as wrong as one stating
  an open thing as settled.
- **`T-113` gains an acceptance criterion**: record the `P-10` answer as a decision, either way.
- **`T-109` gains one too**: the subtitle list's source, per `P-17`.
- Nothing here is built. The phase is now specified, not delivered.

### Alternatives considered

- **Ruling in groups without reading each clause.** Rejected in practice as well as in principle:
  three of the twenty-five were ruled *against* the file's own proposal, and a group ruling would
  have ratified the opposite of the decision in each.
- **Deferring the shape questions to a mockup.** Offered and declined; the six were ruled directly.
  A mockup is still worth building before `T-107` starts, but as a check on the ruling rather than
  as the thing that produces it.

---

## SEC-004 — The fifteen options `SEC-003` did not see are all forbidden

**Status:** **Accepted** (2026-08-16) — maintainer decision, taken on the Planner's material for
`T-256` after `T-183`'s audit surfaced them
**Date:** 2026-08-16
**Supersedes:** nothing. **Extends** `SEC-003` to option families it did not consider, on
`SEC-003`'s own reasoning. **Does not amend it** — the three corrections `T-183` proposed against
`SEC-003` itself are **still unruled**, and are listed at the end so they are not mistaken for
part of this.

### Context

`T-183`'s audit classified all 250 documented options of yt-dlp 2026.07.04 and **refused to
classify fifteen**, because each reaches something a written constraint forbids and no decision
covered it. `SEC-003` ruled six families on 2026-08-07 and did not see these; they were found by
reading the option parser rather than the README.

**Filing them unclassified was the point.** `T-183`'s fifth criterion asks the audit to state what
it could not classify rather than force a class, and `T-184`'s refusal list cannot be built while
any option's disposition is unknown.

### Decision

**All fifteen are forbidden.** One rule, in the user's terms: *an option that runs code, fetches
code, weakens transport security, or carries a secret is refused where it is typed, with the
reason.*

| Family | Options | Why |
|---|---|---|
| **Executes code or a binary** | `--plugin-dirs`, `--no-plugin-dirs`, `--use-postprocessor`, `--downloader`, `--downloader-args`, `--postprocessor-args`, `--js-runtimes`, `--no-js-runtimes` | `SEC-003` forbade `--exec` because *"the alternative cannot be built"* — `T-034` contains the paths yt-dlp **writes**, and a command writes wherever it likes. That reasoning reaches all eight without modification |
| **Fetches code at runtime** | `--remote-components`, `--no-remote-components` | A network destination `NFR-007` does not permit, delivering code this project did not ship. yt-dlp's own help says it is not currently needed |
| **Weakens TLS** | `--no-check-certificates`, `--prefer-insecure` | Through the hatch there is no control and therefore nothing that could show the downgrade. A security posture the user cannot see they changed is the shape `DAT-004` and `NFR-007` exist to prevent |
| **Carries a secret** | `-2/--twofactor`, `--ap-username`, `--ap-password` | `REQ-EXCL-003` and the `-u`/`-p` ruling, applied verbatim: a secret inside a frozen request that is persisted and crosses a process boundary |

### Rationale

- **This is `SEC-003` applied, not extended.** Every one of the fifteen was already answered by
  reasoning that decision wrote down; what was missing was somebody having looked at the option.
- **Consistency is the cheap part and the valuable part.** A refusal list with `--exec` on it and
  `--postprocessor-args` off it is not a boundary, it is a list of the things somebody happened to
  think of.
- **Nothing new has to be built.** Fifteen entries join a refusal list `T-184` is already building;
  permitting any of them would have meant new validation at a boundary whose breach is
  Critical-band.

**The cost is real and is accepted knowingly**, in `SEC-003`'s own manner:

- **`--downloader` is the one with genuine demand.** `aria2c` is materially faster on fragmented
  downloads, and it is **more constrained than `--exec`** — yt-dlp accepts a fixed set of names as
  well as a path, so an allowlist is buildable. It is refused anyway, and this is the option most
  likely to be reopened.
- **`--no-check-certificates` costs the corporate-MITM user.** They can still reach the site
  through `--proxy`, or fix their trust store, which is the honest fix.

**Every one of these is reopenable, and that is deliberate.** `SEC-003` permitted
`--download-archive` *"as a user-named file only"*, and `DAT-005` §1 refused *Clear all* while
naming its own lifting condition. **A refusal that names what would change it is not a wall.** The
condition here is the same for all fifteen: *a user asks for it, and the permitted form can be
stated narrowly enough to be validated* — for `--downloader`, an allowlist of yt-dlp's own
downloader names with no path form and `--downloader-args` still refused.

### Consequences

- **`T-184` is unblocked.** Its refusal list is the audit's `app:sets` + `app:contained` +
  `app:plumbing` + `excluded` classes, now **79 documented options** rather than 64.
- **`docs/YTDLP_OPTION_AUDIT.md` has no `unruled` rows.** The fifteen move to `excluded` and the
  class table is recounted rather than adjusted by hand.
- **`REQ-030`'s parity promise gains fifteen named exclusions**, and Phase 4.5's exit criteria
  already require the README to state what is refused rather than let it be silently absent.
- **The refusal is keyed on `dest`, not on the option string** — `T-183` Finding 4. Four suppressed
  spellings of `geo_bypass` reach what `SEC-003` forbids as `--xff`, and the same trap applies to
  anything ruled here.
- Nothing here is built.

### Still unruled — **not** decided by this entry

`T-183` raised three corrections **to `SEC-003` itself**. They were not part of the question this
decision answers and **remain open**:

1. **`SEC-003` permits `--netrc-cmd`, which executes a command** — on a rationale (*"the secret
   lives in the user's own file"*) that does not reach it. The same table forbids `--exec` four
   rows down for exactly that property.
2. **`SEC-003` permits `--client-certificate-password`, which is a secret** rather than a path to
   one — the shape `_require_credential_free_proxy` makes unrepresentable.
3. **`SEC-003`'s consequences say the refusal list gains *five* entries and then list *seven*.**

The audit classifies the first two `hatch` **because that is what the accepted decision says**, and
will keep doing so until it is amended. `T-256` carries them.

### Alternatives considered

- **Permit `--downloader` from an allowlist.** Rejected *for now*, not on principle: it is the
  first permitted option that starts a subprocess, and that is a boundary worth crossing on a
  user's request rather than on a guess. Named above as the most likely reopening.
- **Permit the two TLS options with a stated warning.** Rejected: there is no surface to state it
  on. The hatch is a text field, and a warning nobody sees is the silent downgrade with extra steps.
- **A separate decision per family.** Rejected: four entries would say the same sentence four times
  and leave `T-184` blocked until the last one landed.

---

## SEC-005 — `--legacy-server-connect` is forbidden, on `SEC-004`'s own TLS reasoning

**Status:** **Accepted** (2026-08-21) — maintainer decision, taken on the Planner's material for
`T-256` after `T183-R3` surfaced a sixteenth option
**Date:** 2026-08-21
**Supersedes:** nothing. **Extends** `SEC-004` to one option it did not see, exactly as `SEC-004`
extended `SEC-003`. **Does not amend it.**

### Context

`SEC-004` ruled the fifteen options `T-183`'s audit had refused to classify. **`T183-R3` then found a
sixteenth** — `--legacy-server-connect` — which the audit had missed, so it was **not** among the
fifteen the maintainer was asked about.

**It was left `unruled` rather than swept in, and that was the right call.** `SEC-004`'s scope is
bounded to the options it names; extending a ruling by inference is the maintainer's to do or not
do, and an audit that quietly widened a refusal would be the same defect as one that quietly
narrowed it. It has been the single `unruled` row since 2026-08-16 and the only thing blocking
`T-184`.

### Decision

**Forbidden.**

| Family | Options | Why |
|---|---|---|
| **Weakens TLS** | `--legacy-server-connect` | Enables `SSL_OP_LEGACY_SERVER_CONNECT` and a compatibility cipher policy — a transport-security downgrade. **`SEC-004`'s own sentence reaches it without modification**: *"through the hatch there is no control and therefore nothing that could show the downgrade. A security posture the user cannot see they changed is the shape `DAT-004` and `NFR-007` exist to prevent"* |

### Rationale

- **This is `SEC-004` applied, not extended in substance.** `--no-check-certificates` and
  `--prefer-insecure` are already forbidden for being TLS downgrades reachable through a text field
  with no surface to warn on. Nothing about this option is different in the way the rule cares
  about.
- **A refusal list with two of the three TLS downgrades on it is not a boundary.** It is a list of
  the ones somebody happened to look at — which is `SEC-004`'s own argument for consistency, and the
  reason `T-183` was told to state what it could not classify rather than force a class.
- **The cost is named and accepted, in `SEC-003`'s manner.** A user talking to an old or misconfigured
  server that needs legacy renegotiation cannot reach it through this application. The honest fixes
  are the server's configuration or a proxy — the same answer `SEC-004` gave the corporate-MITM user
  it costs.

**Reopenable, like every entry in this family.** If a real user meets a real server that needs it,
that is new evidence and this decision is where it gets revisited.

### Consequences

- **`docs/YTDLP_OPTION_AUDIT.md`'s `unruled` class reaches zero.** The class stays defined: a
  heading that disappears when it empties is one nobody notices coming back, and the audit's own
  rule is that it must be able to say *"no decision covers this"* when that is true.
- **`T-184` unblocks.** Its dependency read *"one unruled option, `--legacy-server-connect`"*, and
  the refusal list it enforces can now be built with every documented option classified.
- Nothing here is built.

### Alternatives considered

- **Permit it, with a warning.** Rejected on `SEC-004`'s own ground: the hatch is a text field and
  there is no surface to state a warning on. A warning nobody sees is the silent downgrade with
  extra steps.
- **Fold it into `SEC-004` by editing that entry.** Rejected: this file is appended to, and a ruling
  the maintainer took on 2026-08-21 must not be backdated into one taken on 2026-08-16.
- **Leave it `unruled` and let `T-184` refuse it as unclassified.** Rejected: that is a refusal
  nobody decided, arriving at the user as a refusal somebody did.

## SEC-003 — The six yt-dlp option families that meet an exclusion, ruled

**Status:** **Accepted** (2026-08-07) — maintainer decision, taken from the Planner's material for
`T-182`
**Date:** 2026-08-07
**Supersedes:** nothing. **Amends** `NFR-007` (a third permitted destination) and **corrects**
`ARC-010` §3, which claimed `--exec` is bound by containment. **Interprets** `REQ-EXCL-002`,
`-003` and `-005` without widening any of them.

### Context

`ARC-010` set the target as capability parity with yt-dlp and explicitly did **not** decide which
option families `REQ-EXCL` forbids. Six point in the opposite direction from a written constraint,
and an implementer meeting one mid-task would settle it in a commit rather than a decision. `T-182`
exists so that cannot happen.

**Three facts were measured against yt-dlp 2026.07.04 as installed, not recalled:**

1. **SponsorBlock sends a hash *prefix*, not a video id.** `postprocessor/sponsorblock.py` computes
   `sha256(video_id)` and requests `/api/skipSegments/<first 4 hex chars>`, filtering the response
   locally. The endpoint learns one bucket in 65,536, not which video was watched.
2. **`--impersonate` is inert here.** `curl_cffi` is not installed and
   `_get_available_impersonate_targets()` returns none, so permitting it means **adding a runtime
   dependency** — an `AGENTS.md` §7 decision, a `LIC-001` check, and both frozen artifacts.
3. **`--xff` is unambiguous.** yt-dlp's own option help reads *"Bypass geographic restriction via
   faking X-Forwarded-For"*, and it maps to `geo_bypass`.

### Decision

| Family | Ruled |
|---|---|
| **Site credentials** | **`--netrc`, `--netrc-cmd`, `--netrc-location` and the client-certificate options are permitted. `-u`/`-p`/`--video-password` are forbidden.** |
| **`--impersonate`** | **Forbidden.** |
| **Geo** | **`--xff` forbidden; `--geo-verification-proxy` permitted.** |
| **`--exec`, `--exec-before-download`** | **Forbidden**, and `ARC-010` §3 corrected. |
| **`--download-archive`** | **Permitted as a user-named file only.** |
| **SponsorBlock** | **Permitted, opt-in**, with `NFR-007` amended to name it. |

### Rationale

**Credentials: the application must never hold one, and `--netrc` is how it doesn't.**
`REQ-EXCL-003` forbids asking for a site username and password *to store*. A `--netrc` flag asks for
nothing: the secret lives in the user's own file, which this application neither reads nor writes.
A client certificate is the same shape — a path to something the user already has.

**The rejected half has a precedent in this codebase, and it is strict.** `DownloadRequest` cannot
carry proxy credentials *at all*: `_require_credential_free_proxy` makes them unrepresentable rather
than scrubbing them, because three credential forms reached the database before that and one attempt
to strip them corrupted output paths instead. A site password is the identical shape — a secret
inside a frozen request that is persisted and crosses a process boundary. Session-only fields would
mean reopening that, and the thing that was hard was never the field; it was everything downstream.

**`--impersonate` is the flag `REQ-EXCL-005` most looks like**, and it is not free either: it needs
a runtime dependency this project does not have. Sites fronted by TLS-fingerprint checks will simply
fail. **That cost is real and is accepted knowingly** — the refusal names itself, so a user meets an
explanation rather than a mystery.

**Geo splits on whether the user owns the thing being used.** `--xff` spoofs a header describing
someone else's location; `--geo-verification-proxy` routes a request through a proxy the user has.
The first is what `REQ-EXCL-002` names. The second is proxy configuration, which `REQ-023` already
covers.

**`--exec` is forbidden because the alternative cannot be built.** `ARC-010` §3 listed it among the
options "subject to the same containment check as the output template". **That is not achievable:**
`T-034` contains the paths *yt-dlp writes*, and a shell command writes wherever it likes. There is
no middle position where the hatch validates `--exec` — only refusal reaches it. A confirmation
dialog was considered and rejected: people click through confirmations, and this one would carry
arbitrary code.

**`--download-archive` is the user's record, not the application's.** `REQ-020` withdrew *this
application's* record of what has been downloaded. A path the user types, to a file the application
never creates, never defaults and never reads unasked, is not that record coming back. The
distinction is only real if the defaults hold, which is why "no default path" is part of the ruling
rather than a detail of it.

**SponsorBlock is permitted because the measured cost is small and the promise is amendable.**
`NFR-007` is a promise about outbound traffic, and a promise is kept by amending it in the open
rather than by reading it loosely. Opt-in per preset, and the request carries a 4-character hash
prefix. **A self-hosted `--sponsorblock-api` was declined**: it adds a field whose typo is a new
network destination, which is a poor trade against a lookup that already reveals almost nothing.

### Consequences

- **`NFR-007` is amended** to name SponsorBlock as a third permitted destination, conditional on the
  user enabling it. The amendment is in `REQUIREMENTS.md` §5 with its reasoning here.
- **`ARC-010` §3 is corrected**: containment binds paths, not commands, and `--exec` is on the
  refusal list rather than in the validated set. *The original line was wrong in a way that would
  have shipped: an implementer building the hatch to `ARC-010` as written would have believed
  `--exec` was contained by a check that cannot see it.*
- **`T-183`'s audit gains its excluded class**, and `T-184`'s refusal list gains five entries:
  `-u`, `-p`, `--video-password`, `--impersonate`, `--xff`, `--exec`, `--exec-before-download`.
- **`REQ-030`'s parity promise gains named exclusions.** The README must carry them, per Phase 4.5's
  exit criteria: what is refused is stated, not silently absent.
- Nothing here is built.

### Alternatives considered

- **Session-only username and password.** Rejected on the `_require_credential_free_proxy`
  precedent: the field is easy and the boundary it breaches is not.
- **`--exec` behind a confirmation.** Rejected: the guard is a dialog, and the payload is arbitrary
  code.
- **Forbidding `--geo-verification-proxy` with `--xff`.** Rejected: it reads `REQ-EXCL-002` at its
  widest and costs a user their own proxy for no gain in the thing the exclusion protects.
- **A default `--download-archive` path.** Rejected: that is the application keeping records again
  under a different filename.
- **A configurable SponsorBlock endpoint.** Rejected, as above.

### Amended 2026-08-21 — two options this entry permitted are forbidden, and the count corrected (`T-256`)

**Status:** **Accepted** (2026-08-21) — maintainer decision, taken on the Planner's material for
`T-256`
**Amends:** the *Decision* section's verdict table (the **Site credentials** row) and the
*Consequences* section's count. The decision itself — the six families, and the reasoning that
a secret living in a user's own file asks this application for nothing — is unchanged and is what
the rest of this entry still rests on.

**Amended rather than rewritten in place**, on the `DAT-002` precedent and `AGENTS.md` §6: this file
is appended to, never silently corrected. The original table stays legible above so the change is
readable as a change.

**`T-183`'s Finding 3 was right, and it was right for two different reasons.** This entry permitted
four site-credential options on one sentence — *"a `--netrc` flag asks for nothing: the secret lives
in the user's own file, which this application neither reads nor writes"* — and that sentence
reaches `--netrc` and `--netrc-location` and does not reach the other two.

| Family | Ruled |
|---|---|
| **Site credentials** *(amended)* | **`--netrc` and `--netrc-location` are permitted. `--netrc-cmd` and `--client-certificate-password` are forbidden.** `--client-certificate` and `--client-certificate-key` remain permitted. `-u`/`-p`/`--video-password` remain forbidden. |

- **`--netrc-cmd` executes a command.** yt-dlp's own help reads *"Command to execute to get the
  credentials for an extractor"*. That is the property `--exec` is forbidden for **four rows above**,
  and the property `SEC-004`'s whole *executes code or a binary* family turns on. The honest
  argument for permitting it — that it runs the **user's own** command to fetch the **user's own**
  credentials, the way a password-manager hook does — **does not survive the delivery mechanism**:
  `REQ-031`'s hatch is a free-text field, and *"the user's own command"* and *"an arbitrary
  command"* are the same string there.
- **`--client-certificate-password` carries a secret**, rather than naming a file that holds one. It
  is the shape `_require_credential_free_proxy` makes unrepresentable and the shape `-u`/`-p` were
  forbidden for, and `SEC-004` then forbade `-2/--twofactor`, `--ap-username` and `--ap-password` on
  exactly that wording — *a secret inside a frozen request that is persisted and crosses a process
  boundary*. **The counter-argument is real and is recorded rather than dismissed**: this passphrase
  unlocks a **local file** and is not a site credential, so a reader may think it belongs with
  `--client-certificate` itself. It is forbidden anyway, because persistence and the process
  boundary are what the rule names, and neither is changed by what the secret unlocks.
- **`--client-certificate` and `--client-certificate-key` are untouched.** They name files, which is
  what the original reasoning actually covers. Forbidding the family wholesale would have been the
  over-broad reading, and this entry does not take it.

**The `Consequences` count is corrected: the refusal list gains *seven* entries, not five.** The
list beside it already names seven — `-u`, `-p`, `--video-password`, `--impersonate`, `--xff`,
`--exec`, `--exec-before-download` — and every one is forbidden elsewhere in this entry. **The list
is the operative half and the number was the error**, which is why the number moved.

**Consequences of this amendment.** `docs/YTDLP_OPTION_AUDIT.md` moves `--netrc-cmd` and
`--client-certificate-password` from `hatch` to `excluded` — it had classified them `hatch` **because
that is what this decision said**, and said so in its own text rather than overruling a decision.
`T-184`'s refusal list gains two entries. Nothing is built by this.

## OPS-013 — A recorded-evidence criterion binds where the source reports it, and nowhere else

**Status:** **Accepted** (2026-08-07) — maintainer ratification, requested by the Reviewer in
`T107-R1` and given explicitly
**Date:** 2026-08-07
**Supersedes:** nothing. **Amends** `T-107`'s acceptance criterion and, through it, the standard
Phase 3 exit criterion 1 is read against.

### Context

Phase 3's first exit criterion is *"the format table matches `yt-dlp -F` output for a fixture set of
URLs"*, and `T-107` refined that to every column `REQ-003` names being **populated from a recorded
fixture**. The comparison run against that wording found two real defects, so the wording was doing
its job. Then it hit a column no source supplies.

**`fps` is reported by none of the seven acceptable sources probed** on 2026-08-07: four Wikimedia
Commons files (Caminandes, Big Buck Bunny, Sintel, Tears of Steel) and three archive.org items.
Commons supplies codecs and bitrate — which is why `wikimedia_caminandes` was captured — and carries
`fps` on no format. The constraint is `ai/TESTING.md` §5: sources must be freely licensed, unsigned
and unlikely to change. A site that reported `fps` and churned weekly would satisfy the criterion's
letter and break the property §5 chose these sources for.

So the criterion as written cannot be met by any source the project is willing to depend on.

### Decision

**The ratified wording:**

> Every column `REQ-003` names is present, and populated from a recorded fixture by value **where
> the source reports it**; `fps` may remain covered by the derived fixture until `T-185` finds an
> acceptable source.

`T107-R1` is Resolved at `09c57c3`. `T-107` is approved. `T-185` stays open as the record of the
search, and closing it as *"no acceptable source exists"* remains a legitimate outcome.

### Why

**A criterion that no permitted source can satisfy is not a high standard, it is a stuck one.** The
alternative was to hold `T-107` — and the whole `T-108` chain behind it — against a source that
seven probes say does not exist. That trades a real, working, independently-verified table for a
column's provenance.

**The gap is recorded rather than papered over.** `derived_format_columns.json` says what is
synthetic in its own `what_is_synthetic` field; the evidence artifact names the seven sources and
the answer each gave; `T-185` owns the search. The criterion is weakened in the open, with the
weakening visible from the fixture, the evidence and the task list independently.

**Ratification is recorded here because authority was the actual issue.** The Reviewer offered this
amendment as one resolution path and correctly refused to treat its own offer as the ruling —
`T-107`'s correction had recorded the amendment as the maintainer's while the handoff called it the
Reviewer's. Neither document was where a ruling belongs. *An accepted entry here is the only thing
that makes a criterion change checkable after the conversation that produced it is gone.*

### Consequences

- **`T-107`'s criterion is amended** to the wording above; the task record and
  `ai/evidence/2026-08-07-format-table-vs-yt-dlp-f.md` cite this entry rather than an unattributed
  "the maintainer".
- **Phase 3 exit criterion 1 is read against the amended wording**, and the board says so.
- **The general rule, for the criteria still ahead:** a recorded-evidence requirement binds a column
  only where an acceptable source reports it. Covering the remainder synthetically is permitted
  *only* when the fixture declares it synthetic and an open task owns the gap. Absent either, the
  criterion binds as written.
- Nothing here changes any code.

### Alternatives considered

- **Reject, and block `T-107` until a source supplies `fps`.** Rejected: seven acceptable sources
  report none, so this blocks the deliverable and its dependents on a search that has already
  failed.
- **Relax `ai/TESTING.md` §5 to admit a churning source that reports `fps`.** Rejected: it satisfies
  the criterion's letter by breaking the property the fixture set exists to have.
- **Time-box it — require `T-185` resolved before Phase 3 exits.** Considered and not taken: the
  criterion would gain a deadline without gaining a source, and `T-185` closing as *"none exists"*
  is already an outcome the phase can exit on.
- **Synthesize an `fps`-bearing "recorded" fixture by hand.** Rejected outright: that is a synthetic
  fixture claiming provenance it does not have, which is the failure `SEC-002` exists to prevent.

---

## UX-008 — Per-job pause stays out; resume is what `.part` files do, not a state

**Status:** **Accepted** (2026-08-08) — taken by `T-113`, which `P-10` named as the decision's
owner. Recorded because `UX-007` required an answer *"either way"*. **Amended the same day** by
`T113-R1`, `T113-R2` and `T113-R3`: the lifetime table gains a row for an orderly close, and names
who ends a partial's life and when.
**Date:** 2026-08-08
**Supersedes:** nothing. **Answers** `UX-001`'s named reopening condition and closes `P-10`.
**Does not amend** `UX-006`: the queue-level gate and its stopped-at-launch default are untouched.

### Context

`UX-001` removed per-job pause on the reasoning that pause could only mean *drain* — there was
nothing to pause *to*, because an interrupted download started again from the beginning. It named
`REQ-017` as the condition under which that would be worth revisiting: *"once a partial file can be
resumed, per-job pause becomes coherent — pause would stop having to mean drain."* `T-080` deleted
`JobStatus.PAUSED` on the matching reasoning that nothing could enter it.

`UX-007` (2026-08-07) ruled `P-10` by declining to rule it: the answer *"depends on what resume
actually costs per site and format, which is what `T-113` exists to find out"*, and it must be
recorded either way.

### What `T-113` found

**Resume costs nothing, and it was never a feature this application had to build.** yt-dlp's
`continuedl` is on by default: it finds the `.part` file at the path it is told to write to and
continues from it. The only reason downloads restarted was that the staging directory was
`tempfile.mkdtemp` — unique per *call* — so the next attempt looked in a directory that had never
been written to. Keying it by job id was the whole change.

**Measured, against a local server with and without `Accept-Ranges`** (`tools/`-free probe, run
2026-08-08 on the development machine):

| Server | Requests on the second attempt | Outcome |
|---|---|---|
| Sends `Accept-Ranges: bytes` | **one range request** | resumed, correct bytes |
| Ignores `Range` | **four full requests** | restarted from zero, correct bytes |

Both produced a byte-exact file. So resumability is not a capability that can fail — it is a *head
start that is sometimes lost*, decided by the server at the moment the request is made, and yt-dlp
handles the loss by starting over silently.

### Decision

**1. Per-job pause is not reintroduced. `JobStatus.PAUSED` stays deleted.**

`UX-001`'s condition is met in the letter and not in the spirit. Pause-to-a-state would mean
holding a worker process, its socket and its file handle open indefinitely, or stopping the worker
and calling the result *paused* — and the second is what **cancel plus retry already is**, now that
the partial survives a failure. Resume made the *mechanism* coherent and simultaneously made the
*state* redundant: there is nothing a paused job could offer that a stopped one with its bytes on
disk does not.

**2. There is no `Pause all` on a playlist header** (`T140-R5`, closed the same way). It would be a
group-level spelling of a per-job control that does not exist.

**3. The queue-level gate stays the only pause.** `UX-006` is unchanged.

**4. What the user gets instead is that stopping is cheap.** Cancel a download, and its partial is
discarded because a cancel is somebody saying they do not want it. Let one fail, or kill the
application mid-download, and the partial is **kept** — the next attempt continues from it.

### The partial file's lifetime, stated once

| What happens | The partial | The row |
|---|---|---|
| The download succeeds | discarded with the staging directory | `COMPLETED` |
| The download fails | **kept**, so the retry has a head start | `FAILED`, retryable |
| The application is killed | **kept** — nothing runs to delete it | left in flight; recovered at the next launch |
| **The application is closed** | **kept** | left in flight; recovered at the next launch |
| The user cancels | discarded | `CANCELLED`, terminal |
| The user removes the job | discarded, and no row would be left to explain it | deleted |
| The server refuses the resume | replaced: yt-dlp restarts from zero and writes the correct file | unchanged |

**An orderly close is an interruption, not a cancellation** (amended 2026-08-08, `T113-R2`). The
first version of this table had no row for closing the window, and the implementation treated it as
a cancel — `shutdown()` cancels every occupant, so the partial was deleted and the row was written
terminal. A terminal row is not recovered at the next launch, so an application closed mid-download
reopened with neither bytes to continue from nor anything offering to try again. `REQ-017` promises
resumption **across restarts**, and closing the window is how a restart usually begins.

So the intent is recorded when work is stopped, and the two intents differ: the user's Cancel is a
statement that the download is unwanted, and shutdown's is a statement that the application is
going away. **The user's outranks shutdown's** — cancelling a download and then closing the window
is an ordinary sequence, and the cancellation must survive it.

**Who ends the partial's life, and when** (amended 2026-08-08, `T113-R3`). The parent, once the
process is gone. The worker's cooperative cancellation branch used to do it, which was wrong twice:
that branch cannot tell a user's Cancel from a shutdown, and an escalation to `terminate()` or
`kill()` never reaches it at all. `remove()` deleting the directory as the removal was *asked for*
had the same shape from the other side — a worker that had not noticed yet simply recreated it.

**Nothing of the user's is ever in that directory**, and two things make that true rather than
assumed. Its name is a digest of the job id (`T113-R1`, **Critical**): `Job.id` is validated as
non-empty text and nothing more, it comes off a row a user can edit, and joining it into a path made
`../../../../outside` a real directory that this application created, wrote into and recursively
deleted. And every path the download *reports* is resolved and contained before it is moved
(`T109-R8`), because a source outside the staging directory is a file the session never created.

### Consequences

- `REQ-017` is met without a new job state, a new verb for stopping, or a change to `UX-001`'s
  semantics.
- A **live stream** is the one case where a probe can say in advance that resumption is impossible,
  and `Job.is_live` carries it so the row can say so (`P-24`). Everything else says nothing, because
  a promise that resumption *will* happen is one this application cannot keep.
- A job that fails and is never retried holds its partial until the row is removed. That is a
  deliberate trade — the bytes are recoverable value, and the row is the thing that explains them.

### Alternatives considered

- **Reintroduce `PAUSED` as "cancelled, but the row says paused".** Rejected: it is a second
  vocabulary for a state the queue already has, and `T-080` deleted the member for exactly the
  reason that nothing could honestly enter it. A status whose only content is a nicer word is what
  `ARCHITECTURE.md` §7's taxonomy exists to keep out.
- **Hold the worker open on pause.** Rejected: an idle worker holds a process, a socket and an open
  file for an unbounded time, and `ARC-002`'s pool is sized in processes. A user pausing eight
  downloads would hold eight processes hostage to a decision they may never come back to.
- **Discard the partial on failure too, as the old `finally` did.** Rejected: a network failure is
  precisely the case resume exists for, and `UX-002` already retries those automatically. Keeping it
  is what makes the automatic retry cheap instead of a second full download.

---

## UX-009 — Library-wide actions live in the dialog footer, not on a row

**Status:** **Accepted** (2026-08-09) — maintainer ruling, taken while reviewing `T-203`'s mockups
**Date:** 2026-08-09
**Amends:** `docs/UX_SPEC.md` §8's `[T]` clause binding the preset manager to *"the format control's
`Manage presets…`"*. **Narrows** `UX-004`, which put "the rest" of the row's controls in a menu on
the row. **Does not amend** `UX-004`'s core ruling — the per-row format choice stays a visible
control on the row, which is the part `T118-R5` fought for.

### Context

`UX-004` ruled that the row carries a visible format control and that other actions live in a menu.
What it did not anticipate is *which* actions would end up in that menu. By Phase 3's end the format
combo held four commands beside its presets — `Choose specific formats…`, `Options…`,
`Where it goes…` and `Manage presets…` — and the maintainer's review of the built dialog on
2026-08-08 was that **the control looks like a value picker while containing commands**, and appears
to accept a choice it discards.

**One of the four is not like the others.** `Choose specific formats…`, `Options…` and
`Where it goes…` all act on **the row they are on**. `Manage presets…` opens the shared preset
library — it does the same thing from every row, and the row it was invoked from is irrelevant to
it. It was offered once per row, on every row, because the combo was the only place it could go.

### Decision

**An action whose effect does not depend on the row it was invoked from belongs in the dialog's
footer, not on a row.**

1. **`Manage presets…` moves to the Add URLs footer.** `docs/UX_SPEC.md` §8's `[T]` clause is
   amended to say so. The five operations `REQ-007` names are unchanged — this moves the door, not
   the room.
2. **The rule generalises**, which is why this is a decision rather than a line in `T-203`: the next
   library-wide action will ask the same question, and the answer should not be re-argued.
3. **Per-row actions stay per-row.** This decision says nothing about how they are drawn — that is
   `T-203`'s, and the maintainer ruled its layout separately on the same day.

### Rationale

A per-row control implies per-row effect. Offering a library-wide command from a row teaches the
opposite, and it costs the row width on something that is identical everywhere. The footer already
holds the actions that apply to the dialog rather than to any row.

**`UX-005` §5's rule is the same instinct one step further on** — nothing is drawn that would be
refused. A command that is drawn N times and means one thing is not refused, but it is drawn N−1
times more than it means anything.

### What this does not decide

- **How the remaining per-row verbs are drawn.** `T-203` owns that.
- **Whether a per-item output template survives at all.** Still open, still the maintainer's, and
  it is the one ruling `T-203` is waiting on.
- **Anything about the queue's rows.** This is the add dialog's footer; the main window has its own
  anatomy in `UX-005`.

---

## DAT-007 — The thumbnail cache partitions by database, and the shared one is adopted once

**Status:** **Accepted** (2026-08-08) — maintainer ratification, required by the Reviewer in
`T180-R1` and given explicitly
**Date:** 2026-08-08
**Supersedes:** nothing. **Extends** `ARC-006`'s boundary to a second directory, and settles the
choice `T-180` reserved for the maintainer.

### Context

`ARC-006` decided the single-instance guard is named from the **resolved database path**, precisely
so two instances against different databases are not blocked: *"two instances against different
databases harm nothing and must not be blocked."*

Everything else under the cache root inherited that permission without inheriting the distinction.
`thumbnail_cache_directory()` was `cache_directory() / "thumbnails"` — one directory for the
machine — and `_SweepTask.run` unlinks every entry the sweeping instance's queue does not name. So
the second instance `ARC-006` deliberately permits had its live pictures deleted by the first, and
returned the favour on its next sweep. `T179-R1` found the harmless half of this (a publication
count that cannot see another process) and was dispositioned rather than fixed, because the
destructive half needed this decision.

**`ARC-006` permits the second instance; it does not say where that instance's cache lives.** That
is the gap `T180-R1` names, and treating the boundary as derived from `ARC-006` was the error — it
is a choice `ARC-006` makes possible, not one it makes.

### Decision

**The thumbnail cache is per database.** `core/paths.cache_root_for` derives the root from the
resolved database path through `derived_component`, and the derivation is stated once so it cannot
drift from `lock_path_for`'s. Composition derives it; `ui/` is handed a root and never learns what a
database is.

**The pre-existing shared cache is adopted, once, by the first database to launch.** On first run,
if the legacy shared `thumbnails/` directory exists and this database's partition does not, it is
renamed into place. Later databases start empty and refetch. Every failure — a cross-device rename,
a directory in use, a permission — leaves the legacy directory alone and costs one refetch.

### Why

- **It is the boundary the project already draws.** A user's mental model of "a separate library" is
  a separate database, and the instance guard already says so. A second, different boundary for the
  cache is two rules that must agree and will eventually not.
- **It makes the sweep correct rather than cautious.** The alternative below leaves the sweep unable
  to reclaim what it cannot account for; this one gives it a directory it owns alone, so
  `T-119`'s "a picture goes with its job" holds without qualification.
- **`cache_generation` inherited the fix.** It is keyed by directory, so a process-local publication
  count is now complete — `T179-R1` closes without its own mechanism.
- **Adoption is the difference between an upgrade and a refetch.** `T-180`'s risk line says a
  careless version *"strands every existing thumbnail — regenerable, but a wholesale refetch is not a
  quiet event on a large queue."* One rename spends nothing and keeps every picture for the
  single-database user, who is nearly everyone.

### Rejected

- **A machine-wide cache with a safely coordinated sweep.** The honest version of this is
  cross-process coordination — a lock, or a keep-set assembled from every live database — so a sweep
  can prove a file is unwanted before unlinking it. **Rejected for cost against benefit**: it is
  materially more machinery than the defect justifies, and the fallback available without it is a
  sweep that may not unlink what it cannot account for, which means the cache grows and stops being
  reclaimable. A cache that never shrinks is a worse answer than one that is partitioned.
- **Per database, with no adoption.** Simpler, and it removes a rename path that must be certain
  what it owns. **Rejected** because it is exactly the stranding `T-180`'s risk line warns about,
  paid by every existing user on one launch, to save a single `rename` guarded by an existence check.
- **Keying the cache by something other than the database** — a machine id, a profile, a config
  value. **Rejected**: none of them is the thing the user is actually separating, and each would be
  a third identity to keep in step with the lock and the database.

### Consequences

- **Existing thumbnails move once, for one database.** A machine with two databases gives the
  legacy cache to whichever launches first; the other refetches. Both are correct, and the adopter's
  own sweep then collects the mixture it inherited.
- **First-to-launch is a choice, not a derivation**, and it is recorded here so a later reader does
  not mistake it for a consequence of `ARC-006`. The shared directory holds pictures from every
  database that ever ran on the machine, so no partition has a better claim to it.
- **The cache root joins the object graph.** `Composition.cache_root` exposes it, because a
  partition nothing can reach is a partition nothing can check (`T180-R2`).
- **`ARC-006` is unchanged.** This decides where a permitted second instance's cache lives; it does
  not revisit which instances are permitted.

---

## DAT-008 — The application writes no provenance of its own into output files

**Status:** **Accepted** (2026-08-08) — maintainer ruling on `T-171`, which reserved this question
for the maintainer and took the measurement first
**Date:** 2026-08-08
**Supersedes:** nothing. **Closes** `T-171` as a rejection, and **narrows** the 2026-08-06 maintainer
direction that opened it.

### Context

`T-171` was opened on maintainer direction: *"file details are a better candidate for answering what
settings produced this file than a permanent in-app library, but this is not yet permission to write
private download context into every output."* It required a measurement before a choice, and
`ai/evidence/2026-08-06-provenance-survival.md` is that measurement.

The question is narrow and worth stating exactly, because a wider reading of this decision would be
wrong: **should this application write its own record of how a file was produced into the file?**

### Decision

**No.** The application embeds no provenance of its own — no preset name, no completion time, no
download context — in any output file or sidecar. No control is added, and no dormant UI.

### Why

- **The legitimate version already exists and is already the user's.** `T-109` added
  `embed_metadata`, which configures yt-dlp's `FFmpegMetadata`. It embeds *the source's* title,
  artist and date — what a user means by "this file should say what it is" — opt-in, per download or
  saved in a preset, using the tags those fields are for. No built-in preset enables it, and that is
  the right default. **This decision does not touch it.**
- **The non-intrusive mechanism does not work where it matters, and fails silently.** §3 of the
  measurement: a custom key is **dropped by MP4 and M4A** with no error and no warning at the
  default log level. Two of the five built-in presets produce exactly those containers. A feature
  whose whole purpose is to be findable later, that is invisibly absent for a large share of
  downloads, is worse than no feature.
- **The mechanism that does survive is one that belongs to the user.** Standard tags —
  `comment`, `description` — survived every measured path, at the cost of writing application text
  into fields a user may already be using. A downloader is not a tagger.
- **The file already answers the question.** Container, codec, resolution and bitrate *are* what the
  settings produced, and any tool can read them. A preset name adds a label, not information.
- **It cannot honestly promise what it is for.** `T-171`'s sixth criterion forbids claiming survival
  through untested tools, and nothing outside ffmpeg was tested — no player re-tag, no library
  import, no phone sync. The feature's value is conditional on exactly the thing the task forbids
  asserting.
- **It re-opens what this project twice closed.** `T-169` withdrew the completion record, `T-170`
  removed the History tab and the ledger behind it, and migration `0009` removed it from upgraded
  databases. **The application deliberately keeps no record of what has been downloaded.**
  Provenance in a file is that record relocated into an artifact the user *shares* — `T-171`'s own
  risk line is that embedded metadata travels. That is more exposure, not less.

### Rejected

- **A small opt-in set of embedded tags.** The measured options are a custom key (silently dead on
  MP4/M4A) or standard tags (writing into fields the user owns). Rejected on both counts above.
- **An explicit sidecar.** Rejected for two reasons. It survives nothing the feature exists to
  survive — a sidecar is lost the moment the media is moved, shared or imported, which is the
  workflow being served. And it is the easiest possible thing to read back as a list of downloads,
  which `T-171`'s own out-of-scope forbids: *"provenance in a file is a property of that file, and
  must not be read back to reconstruct a list of downloads."*
- **Filesystem extended attributes.** Named in `T-171`'s scope as not equivalent and not to be
  treated as such; they often disappear on copy. Not measured, and not adopted.

### Consequences

- **No implementation task follows.** `T-171` closes as a rejection with its reasons, which is what
  its seventh criterion asks for.
- **`embed_metadata` is untouched**, and so is any future work exposing more of yt-dlp's own
  metadata options under `ARC-010` in Phase 4.5. This decision is about *whose* metadata the
  application writes, not about how much of yt-dlp it exposes.
- **The measurement stays**, and is now the record of why. One sentence in it is stale and says so
  in `T-171`: it reports `--embed-metadata` as never configured, which was true on 2026-08-06 and
  became capability-false when `T-109` landed on 2026-08-08. The §3 container finding — the one this
  decision rests on — is unaffected.
- **The reopening condition**, stated so a later reader does not have to guess: a container-portable
  key that MP4 and M4A model natively, plus a measured survival path through tools this application
  does not run. Both are missing today.

## UX-010 — A queue group's chip is progress: done of total

**Status:** **Accepted** (2026-08-09) — maintainer ruling: *"For #3, go with option B"*, choosing
between the two options the UI review presented side by side
**Date:** 2026-08-09
**Amends:** `docs/UX_SPEC.md` §2.2's sentence extending the History count rule to queue groups.
**Does not amend** the History-group ruling itself (`T-145`'s *"14 items, never 14 of 16"*) — its
reasons were History's, and they stay recorded with it.

### Context

The two documents that describe the group chip disagreed, and by `UX_SPEC` §1's own rule that is a
defect in one of them. The spec said a group chip is a **count of the members present** —
*"`16 items` … Never `14 of 16`"* — and that the rule, written for History's groups, *"holds for
the queue's, which are the ones that remain."* The built queue chip reads `0 of 3`
(`ui/queue_view.py`, `STATE_CHIP_ROLE`), and `T-162`'s out-of-scope note had already called the
queue's `0 of 16` chip *"correct — nothing has downloaded yet."* The disagreement was found
2026-08-09 by a maintainer-requested UI review that put a screenshot of the built window beside the
spec.

### Decision

1. **A queue group's chip reads done-of-total** — `0 of 3` — because the one glanceable question
   about a live group is how far along it is, and every member is present, so the denominator is
   honest.
2. **Never a percentage.** The entries' totals arrive one at a time, so a fraction across them has
   a denominator that grows while it runs. This was the build's own recorded reasoning and it
   stands.
3. **The History rule is not reversed.** Its two reasons — a denominator claiming records the list
   did not hold, and a stored original count drifting on removal — are about History, which is
   withdrawn. Neither applies to a live queue group, which is why extending the rule to the queue
   was a transcription error rather than a ruling.

### Rejected

- **Option A — `3 items` on the queue group**, the spec as written. A member count on a live group
  is nearly furniture: the header's detail line already carries `3 items · 3 failed`, and "how
  many" matters less at a glance than "how far".

## UX-011 — The row picks a preset; the per-row verbs are the row's own menu

**Status:** **Accepted** (2026-08-09) — maintainer ruling on round 8: *"I'm leaning towards
option E. I wasn't a fan of how A looked at all. I liked option B's look, but it sounds like there
are too many downsides."*
**Date:** 2026-08-09 *(recorded the same day for `T203-R2`, which found the shape ruling lived in
a task entry's status line and nowhere durable — and found the previous ruling's trail stopped one
step before the conversation did: **option A was built, reviewed, and rejected on sight**, and
neither the rejection nor round 7's candidates had reached this repository)*
**Amends:** `docs/UX_SPEC.md` §3's row anatomy, §4's *Where it lives* and its keyboard route, §6's
`P-3` route, and adds §9.1's route clause. **Completes** `UX-009`, which moved `Manage presets…`
to the footer and explicitly left the remaining layout to `T-203`. **Does not amend** `UX-004`'s
core ruling — the per-row format choice stays a visible control on the row — and it **extends**
`UX-004`'s context-menu clause: the menu is now the verbs' home too, one menu rather than two.

### Context

By Phase 3's end the row's format combo held four commands beside its presets, and the maintainer's
review found the control *"looks like a value picker while containing commands"* — it appeared to
accept a choice it discarded. `UX-009` took the one library-wide command to the footer and left the
three genuinely per-row verbs — `Choose specific formats…`, `Options…`, and the template editor —
without a ruled home. **Eight mockup rounds looked for one.** The icon shapes fell to
accessibility; option A — a labelled verb bar above the list — was ruled, built and reviewed, and
the maintainer rejected it on sight: it spent a row of vertical space and clipped its own labels.
Round 8 rendered A as built beside E and G, and the maintainer chose E.

### Decision

**The combo holds presets, full stop** — every entry is a value that sticks. **The three per-row
verbs live in the row's menu** (*option E, "one menu, two doors"*):

- `Choose specific formats…`, `Options…` and `Naming and folders…` sit under a *Just this item*
  heading, above the Retry/Remove entries the row's context menu already holds — **one menu**, so
  the row ends with fewer distinct places to poke, not more.
- The menu opens **two ways**: a narrow `⋮` zone on the trailing edge of the row's format control,
  and the context-menu routes that already exist — right-click, the Menu key, Shift+F10.
- **The target is structural, not announced.** A menu opened from a row acts on that row.
  `T203-R1` — the bar telling a screen-reader user a row would change but never which one — is a
  problem class this shape does not have, which is a load-bearing part of why it won.
- **The painted `⋮` is an affordance, not the only door.** It has no accessibility node, and that
  is acceptable for the reason the painted disclosure triangle already is: the function has a
  fully accessible sibling route, and the menu's items are real widgets a screen reader announces.
- The template verb is renamed **`Naming and folders…`** — `Where it goes…` promised a folder
  picker and opened a template editor. *(Built already; survives from the A build, as do the
  presets-only combo and the footer's `Manage presets…`.)*

### Rejected

- **Icon buttons on the row** (the *"V2 + G2"* shape, and the maintainer's preferred look, *B*) —
  **ruled out by accessibility, not taste.** The row is delegate-painted; painted verbs have no
  accessibility node and no sibling route was on offer, so they would vanish from the tree
  `NFR-005` requires and `T-200` audits. The maintainer weighed the look against the downsides and
  let it go.
- **Option A — the verb bar** — ruled first, built, and **rejected on sight**: a full row of
  vertical space spent whether or not any verb is wanted, labels that clip at the widths the
  narrowing contract protects, and action-at-a-distance that needed `T203-R1`'s announcement
  machinery just to say which row it targets.
- **Option D** — a separator splitting the combo's values from its commands. Built to be looked
  at; went with the verbs.
- **Option F** — the verbs in the dialog footer. Traded A's clipping for footer crowding and kept
  A's distance-from-the-row problem.
- **Option G — not rejected but not chosen**: E minus the `⋮`. Same menu, zero new delegate
  geometry, weakest discoverability. It remains the recorded fallback if the `⋮` hit zone proves
  expensive — E degrades to G by removing the zone, with no other rework.

### Deliberately not decided

**Whether a per-item output template survives** (`REQ-011`'s *"for the current item"* reading).
The menu keeps `Naming and folders…` and removes no capability, so this ruling moves an entrance
and takes nothing by implication. Removing the capability later still requires the maintainer
ruling `T-203` records as open.

## UX-013 — The concurrency control leaves the toolbar for Settings

**Status:** **Accepted** (2026-08-12) — maintainer decision
**Date:** 2026-08-12
**Amends:** `ARC-007`, which put a single concurrency control in the main window *"until Phase 4's
settings dialog replaces it"*. That dialog exists (`T-146`), so the condition `ARC-007` named has
been met. **Unblocks:** the question `T-146` and `T-220` had each deferred to the other.
**Raised by:** the maintainer, asking directly — *"should the concurrent downloads stay on the tool
bar? or should that just be in settings/preferances?"* — and ruled in the same exchange: *"i think
we will move it."*

### Context

**Neither task could take this decision, and each said so.** `T-146` recorded *"kept in both
places"* and that removing the toolbar copy was **"not this task's to take"**, deferring to
`T-220`. `T-220`'s out-of-scope says the control *"stays until `T-146` decides its fate"* and
excludes membership changes outright. `T-146` has since decided — it stays, *pending `T-220`'s
ruling* — which leaves `T-220` unable to act on a clause that is already spent. **A decision with
no owner is how a stopgap becomes permanent**, which is what this ruling ends.

The evidence weighed, all of it already in the records:

- **`docs/UX_SPEC.md` §2.1 anticipates the move in its own wording** — the control is there *"until
  Phase 4's settings dialog replaces it"*.
- **`ARC-007` was explicit that it was a trade**, and named what it conceded: *one control in a
  toolbar is easier to miss than a Settings menu item*. The reason for the trade was that no dialog
  existed.
- **It is the only non-verb on the toolbar.** That bar's own rule is that *nothing on it acts on a
  selection, and every verb on it names the list it empties*; `+ Add URLs`, the run control and
  `Clear finished` are verbs, and a spinner is a setting.
- **It has already cost a defect.** During `T203-R3` the toolbar spin box was the window's **first
  focusable widget**, so `Shift+F10` raised the spin box's own edit menu and the row menu could not
  open at all. The fallback was corrected by other means; the window still declares no tab order.

### Decision

**The concurrency control is removed from the toolbar. `Settings → Settings…` is the only place it
is set.** `settings.toml` and `core/settings.py` are unchanged — this removes a *view* of the
value, not the value.

### What is given up, in writing

- **Adjusting the limit without leaving the queue.** Changing it mid-run now costs a dialog. This
  is the one argument for keeping it that `ARC-007`'s reasoning does not already answer, and it is
  accepted rather than dismissed: if watching-and-throttling turns out to matter, the honest answer
  is a control on the queue surface, not a setting parked on the toolbar.
- **Discoverability.** `ARC-007` put it in the window because a toolbar control is found sooner
  than a menu item. That cost is now paid deliberately, with a Settings screen that names it.

### Consequences

- `T-234` builds it. `T-220`'s three options collapse: with the spinner gone the toolbar is four
  verbs, and most of what §2.1 and the build disagreed about was where the spinner sat.
- `docs/UX_SPEC.md` §2.1 is amended by a Planner pass under this ruling, as `UX-012`'s was.
- `T-146`'s *"kept in both places"* becomes history rather than current truth, and its entry says
  so rather than being rewritten.

---

## UX-012 — The row's menu says what it removes, and the ⋮ reads as a button

**Status:** **Accepted** (2026-08-10) — maintainer ruling on three reports from live use of the
built option *E*, each quoted below with its decision.
**Date:** 2026-08-10
**Amends:** `UX-011`'s menu contents and the `⋮` zone's rendering, and `docs/UX_SPEC.md` §3's
menu clauses. **Does not amend** `UX-011`'s shape — one menu, two doors, the structural target —
or its accessibility stance: the `⋮` stays painted with no accessibility node, and the
context-menu routes stay the accessible sibling. The open `REQ-011` per-item-template ruling is
untouched.

### Context

The maintainer used the built menu on a real playlist row (screenshots, 2026-08-10) and reported
three things. `Choose a format for this URL…` *"seems pointless. The dropdown for the preset only
gets highlighted"* — the entry is `T118-R9`'s discoverability alias for the keyboard editor
route, added when the format control materialized only on demand; under option *E* the combo is
visibly on the row, so the entry focuses a control the user can already see, and on a playlist
row the highlight reads as a no-op. `Remove this URL` on a playlist row removes the whole
playlist — semantically right, the staging list stages pasted lines — but *"a user might assume
they are removing an individual video from the playlist."* And the `⋮`: *"The 3 dots are also not
a very pronounced button, people might even miss that they are there."*

### Decision

- **The editor alias leaves the menu** — *"Remove the 'choose a format for this url' option
  entirely. It doesn't really add anything here."* The keyboard route to the combo is separate
  machinery (`EditKeyPressed` through `edit_row`) and survives; `T118-R9`'s discoverability duty
  is discharged by the control being visibly on the row. `T-223` builds it.
- **Remove names the row's kind and blast radius** — *"Go with your recommendation."* On a
  playlist row the entry reads `Remove this playlist (19 items)`, with the row's real entry
  count; a single item keeps `Remove this URL`. The label is built from the row the menu opened
  from — per-row content, not a current-row announcement, so `T203-R1`'s problem class stays
  structurally absent. `T-223` builds it.
- **The `⋮` zone is drawn as a visible button** — *"Make the ⋮ more visable as a button."* The
  zone gains a drawn affordance (a border, and a hover/pressed state), keeping its one-definition
  geometry for paint and hit test. It remains a painted affordance with no accessibility node;
  the menu routes remain the accessible sibling, exactly as `UX-011` ruled. `T-224` builds it.

### Rejected

- **Option G — removing the `⋮` zone** — `UX-011`'s recorded fallback was on the table for the
  duplication report; the maintainer chose to strengthen the zone rather than remove it. G
  remains the recorded fallback if the strengthened zone still fails discoverability.
- **Renaming a single item's Remove to `Remove this video`** — a single row can be audio-only,
  so the honest generic stays `Remove this URL`.

### Deliberately not decided

**A per-entry gesture on playlist rows** (*"Choose which entries download…"* pointing at the
`T-110` picker) was offered alongside the rename and not taken. Adding one later is its own
ruling; nothing here forecloses it.
