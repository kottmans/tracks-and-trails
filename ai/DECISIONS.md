# DECISIONS.md — Tracks & Trails

**Purpose:** Record durable product and technical decisions and the reasoning behind them.
**Authority:** Canonical for decision *rationale and status*. **Not** canonical for current
requirements or design — those live in `REQUIREMENTS.md` and `ARCHITECTURE.md`.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-26
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

**Status:** Proposed — needs maintainer acceptance
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
