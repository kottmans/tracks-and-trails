# DECISIONS.md — Tracks & Trails

**Purpose:** Record durable product and technical decisions and the reasoning behind them.
**Authority:** Canonical for decision *rationale and status*. **Not** canonical for current
requirements or design — those live in `REQUIREMENTS.md` and `ARCHITECTURE.md`.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-08-02
**Update when:** A durable choice is accepted, superseded, or deliberately rejected.
**Does not contain:** Completion notes for routine work. Routine fixes go to `TASKS.md` and `CHANGELOG.md`.

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

**Status:** **Accepted** (2026-07-29) — maintainer decision
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

## OPS-009 — Where each CI job runs, now that `STARBASE` is back and minutes are metered

**Status:** **Proposed** — awaiting the maintainer
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

### What I would propose, if asked

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
