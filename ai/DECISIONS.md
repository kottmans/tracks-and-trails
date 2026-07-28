# DECISIONS.md — Tracks & Trails

**Purpose:** Record durable product and technical decisions and the reasoning behind them.
**Authority:** Canonical for decision *rationale and status*. **Not** canonical for current
requirements or design — those live in `REQUIREMENTS.md` and `ARCHITECTURE.md`.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-27
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

### Consequences

- `persistence/writer.py` is new and owns the thread. `ui/` depends on a narrow protocol, not on
  it, so the dialog still cannot see that SQLite exists (`ARCHITECTURE.md` §3).
- `persistence/db.configure()` now sets `busy_timeout`. In-process contention is gone by
  construction, but a *second process* — a second instance, `sqlite3` at a prompt — can still
  hold the lock, and waiting briefly beats raising at a user.
- Composition (`T-036`) owns constructing the writer and shutting it down. A writer thread that
  outlives the application is the same shape of orphan `T-019` spent a task on.
- **This decision reopens** if a write ever needs to be ordered against a read the GUI thread
  just made — a read-modify-write on a job. Nothing does that today: the manager owns job
  updates and runs its own transitions.
