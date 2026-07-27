# ARCHITECTURE.md — Tracks & Trails

**Purpose:** Define the current approved technical design.
**Authority:** Canonical for system structure, boundaries, data ownership, and cross-cutting patterns.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
**Last reviewed:** 2026-07-25
**Update when:** A boundary, data model, major dependency, or approved cross-cutting pattern changes.
**Does not contain:** Task status, review history, local setup commands, rationale (see `DECISIONS.md`).

> **Status note:** This describes the *approved design*, not implemented reality. As of
> 2026-07-25, of the 31 modules under `src/`, **26 are docstring-only stubs**; the five with
> code are `__init__.py`, `__main__.py`, `_freeze_probe.py`, `app.py` and `ui/main_window.py`
> — the entry point, the frozen-build probe, and the Phase 0 shell window. Nothing downloads,
> probes, or persists a job. `ai/STATUS.md` is authoritative for what is actually built.

---

## 1. Stack

| Concern | Choice | Decision |
|---|---|---|
| Language | Python 3.14 (`requires-python = ">=3.14"`, verified `T-002`) | `ARC-001` |
| GUI | PySide6 6.11 (Qt 6.11), dynamically linked, `abi3` wheels | `ARC-001` |
| Download engine | yt-dlp, imported **as a library** in isolated child processes | `ARC-002` |
| Media processing | ffmpeg, external binary invoked by yt-dlp | `OPS-001` |
| Persistence | SQLite (jobs/history) + TOML (settings) | `DAT-001` |
| Platform dirs | `platformdirs` | `DAT-001` |
| Test / lint / types | pytest + pytest-qt, ruff, mypy | `ai/TESTING.md` |

## 2. System boundary

Tracks & Trails is a single-process **desktop application** that spawns short-lived child
processes. It exposes no network service and accepts no inbound connections. Outbound
traffic is exclusively (a) downloads the user queued and (b) explicit yt-dlp update checks.

External things it depends on and does not own: the yt-dlp package, the ffmpeg binary, the
user's filesystem, and the media sites themselves.

## 3. Process model

This is the defining architectural choice (`ARC-002`).

```
┌──────────────────────────────────────────────────────────────┐
│ GUI process (Qt event loop)                                  │
│                                                              │
│   ui/  ──signals/slots──▶  DownloadManager                   │
│                                 │                            │
│                                 ├── JobQueue (core, pure)    │
│                                 ├── Repository ──▶ SQLite    │
│                                 └── ResultPump (QThread)     │
│                                          ▲                   │
│                                          │ mp.Queue          │
└──────────────────────────────────────────┼───────────────────┘
                                           │
        ┌──────────────────┬───────────────┴──────┐
        ▼                  ▼                      ▼
  ┌───────────┐      ┌───────────┐          ┌───────────┐
  │ worker P1 │      │ worker P2 │          │ worker P3 │
  │  yt_dlp   │      │  yt_dlp   │          │  yt_dlp   │
  │  ↳ ffmpeg │      │  ↳ ffmpeg │          │  ↳ ffmpeg │
  └───────────┘      └───────────┘          └───────────┘
     no Qt              no Qt                  no Qt
```

**One OS process per active job.** Each worker imports `yt_dlp` and calls
`YoutubeDL.extract_info()` directly — it does not shell out to the `yt-dlp` CLI and does not
parse human-readable stdout. Structured progress arrives via yt-dlp's `progress_hooks` and
`postprocessor_hooks`, is converted to typed messages, and is pushed onto a
`multiprocessing.Queue`.

This buys three things at once:

- **Structured data.** Real `info_dict` objects and numeric progress, not scraped text.
- **Fault isolation** (`REQ-028`, `NFR-003`). An extractor segfault, C-extension crash, memory
  blow-up, or unkillable hang takes down one worker. The GUI observes an exit code and fails
  that job.
- **Real cancellation** (`REQ-015`). Terminate the process. A cooperative
  `DownloadCancelled` raised from a progress hook is tried first for a clean partial-file
  state; `SIGTERM`/`TerminateProcess` then `SIGKILL` follow on a timeout. No thread leaks.

Constraints this imposes:

- `multiprocessing` **spawn** start method on every platform, including Linux. Do not rely
  on fork semantics: forking a Qt process is unsafe, and Windows only has spawn. Choosing
  spawn everywhere means Linux and Windows exercise the same code path.
- **`multiprocessing.freeze_support()` must be the first statement in `__main__.py`**, before
  any other import-time work. Released builds are frozen (`REL-001`), where `sys.executable`
  is the application binary rather than a Python interpreter — without this call a spawned
  child re-executes the entire application, opens another window, and spawns children of its
  own. It is harmless when running from source and mandatory when frozen, so it is
  unconditional. See `T-020`.
- Everything sent across the boundary must be picklable and must be an explicit message
  type from `downloader/protocol.py`. Never send a raw yt-dlp `info_dict`; project it into
  a declared dataclass first — the dict's shape is yt-dlp's to change (`NFR-008`).
- Worker code must not import Qt (enforced by `test_layering.py`).
- The child process entry point must be import-safe under spawn (no side effects at
  module import time).

**Queue draining.** A `ResultPump` QThread performs a blocking read on the result queue and
re-emits each message as a Qt signal on the GUI thread. Widgets never touch the
multiprocessing queue and never block (`NFR-001`).

## 4. Layers

Dependencies point downward only. The two rules below are enforced by an automated test,
not by convention.

```
ui/            Qt widgets, dialogs, view-models.  Knows about core/ and downloader/manager.
                 ── must not import yt_dlp ──
downloader/    Process pool, IPC protocol, worker entry point, yt-dlp adapter.
persistence/   SQLite repositories, schema, migrations.
core/          Domain models, job state machine, settings, presets, path logic.
                 ── must not import PySide6 ──
```

- `core/` is pure Python: no Qt, no yt-dlp, no I/O beyond the standard library. It is where
  the job state machine and preset→selector translation live, and it is fully unit-testable
  headless. This is what keeps the interesting logic out of widget classes.
- `downloader/worker.py` is the child-process entry point. It imports `yt_dlp` and `core/`,
  never Qt.
- `downloader/manager.py` runs in the GUI process, owns the process pool, and *is* allowed
  Qt (it emits signals).

### Project structure

```
src/tracks_and_trails/
  __main__.py            entry point
  _freeze_probe.py       frozen-build diagnostics (T-020); infrastructure, not a layer
  app.py                 QApplication setup, wiring, single-instance guard
  core/
    models.py            Job, JobStatus, MediaInfo, FormatInfo, Preset, DownloadRequest
    job_state.py         state machine + legal transitions
    presets.py           built-in presets; preset -> yt-dlp options translation
    settings.py          settings schema, load/save, defaults, validation
    paths.py             platform dirs, output-template rendering, filename sanitizing
    errors.py            error taxonomy and classification
  downloader/
    protocol.py          IPC message dataclasses (the parent/child contract)
    worker.py            child-process entry point; the ONLY module that calls yt_dlp
    ytdlp_adapter.py     options building + info_dict -> core model projection
    manager.py           process pool, scheduling, Qt signals
    result_pump.py       QThread draining the result queue
    environment.py       locating yt-dlp and ffmpeg; version reporting; update
  persistence/
    schema.sql
    migrations/
    db.py                connection, WAL, migration runner
    repositories.py      JobRepository, HistoryRepository
  ui/
    main_window.py
    queue_view.py
    add_dialog.py        URL entry, probe results, preset picker
    format_table.py
    job_detail.py        per-job log and progress detail
    settings_dialog.py
    theme.py             brand palette, light/dark
    widgets/
  resources/
    icons/               app icon (see T-003)
tests/
  unit/                  core/, persistence/, adapter projection — no Qt, no network
  ui/                    pytest-qt widget tests
  integration/           real subprocess, mocked yt-dlp
  network/               opt-in, real network, marked and excluded by default
```

## 5. Data ownership and model

| Data | Owner | Location |
|---|---|---|
| Jobs, queue state, history | `persistence/` (SQLite) | `user_data_dir/tracksandtrails/library.sqlite3` |
| User settings, presets | `core/settings.py` (TOML) | `user_config_dir/tracksandtrails/settings.toml` |
| Per-job logs | filesystem, one file per job | `user_cache_dir/tracksandtrails/logs/<job_id>.log` |
| Managed yt-dlp copy | `downloader/environment.py` | `user_data_dir/tracksandtrails/ytdlp/` |
| Window geometry | `ui/main_window.py` | `user_config_dir/tracksandtrails/window.toml` |
| Downloaded media | the user | user-configured directory |

Locations come from `platformdirs`. Nothing is written next to the installed application
(`NFR-004`). The `platformdirs` app slug is passed with `appauthor=False`; without it Windows
inserts an author segment defaulting to the app name, producing a doubled
`tracksandtrails\tracksandtrails\` directory that matches none of the paths above.

**Window geometry is ephemeral UI state, not a user setting**, which is why it belongs to
`ui/` rather than `core/settings.py`. Nobody edits it deliberately, nothing depends on it, and
losing it costs a window position. It is therefore read defensively: any value that is not a
32-bit integer, or a size below a usable minimum, is discarded in favour of the default rather
than repaired, and geometry that intersects no available screen is moved back onto one. A
separate file means the settings layer (`core/settings.py`, still unbuilt) arrives without a
migration.

**Why two stores:** the job queue needs transactional, crash-safe, concurrently-read
row updates during downloads — that is SQLite's job. Settings need to be hand-editable and
diffable by a user — that is TOML's job. Neither is a good substitute for the other.

### Core entities

- **Job** — `id` (UUID), `url`, `status`, `request` (serialized `DownloadRequest`), `title`,
  `output_path`, `bytes_done`, `bytes_total`, `error_kind`, `error_message`, `attempts`,
  `created_at`, `started_at`, `finished_at`, `queue_position`.
- **DownloadRequest** — the resolved intent: format selector, output template, target
  directory, post-processors, subtitle options, network options. Persisted with the job so a
  retry after a settings change reproduces the *original* request, not the current defaults.
- **MediaInfo / FormatInfo** — projections of yt-dlp's `info_dict`. Declared fields only.
- **Preset** — a named, user-facing bundle that translates to a `DownloadRequest`.
- **HistoryEntry** — a completed job's durable record, retained after the job row is cleared.

### Job state machine (`core/job_state.py`)

```
                  ┌──────────────────────────────┐
                  ▼                              │
QUEUED ──▶ PROBING ──▶ READY ──▶ RUNNING ──▶ POST_PROCESSING ──▶ COMPLETED
   │          │                     │  ▲             │
   │          │                     ▼  │             │
   │          │                   PAUSED             │
   │          ▼                     │                ▼
   └──────▶ FAILED ◀────────────────┴──────────── FAILED
   │                                                 │
   └──────▶ CANCELLED ◀──────────────────────────────┘

FAILED ──retry──▶ QUEUED        (attempts incremented)
```

Transitions are validated in one place. An illegal transition raises rather than silently
corrupting state — a persisted queue that lies about its state is worse than a crash.

**Starting a session sets the status that says a worker holds the job** (`T-051`, `ARC-004`).
There are two entry points into the machine and they use the two edges already drawn above:

| The job is | Starting a download session moves it to | Because |
|---|---|---|
| `QUEUED` | `PROBING` | nothing is resolved yet; the session's first act is to extract |
| `READY` | `RUNNING` | a probe already resolved it; this session downloads what was chosen |

`READY → PROBING` does not exist and is not added. A job that has been probed does not become
unprobed, and a download session's own extraction — yt-dlp cannot download without one — is an
implementation detail of downloading, not a return to an earlier state. The stage a worker
reports (`REQ-014`) is what tells a user it is extracting; the job's *status* says who holds it.

**The invariant this preserves:** a job with a live session is `PROBING` or `RUNNING`, never
`QUEUED` or `READY`. The manager's set of active jobs and the persisted statuses cannot disagree
about whether work is in flight.

**Crash recovery:** SQLite runs in WAL mode. Any job found in `PROBING`, `RUNNING`, or
`POST_PROCESSING` at startup was interrupted by an unclean exit; it is moved to an
`INTERRUPTED` presentation of `FAILED` and offered for retry (`REQ-012`, `NFR-003`).

## 6. yt-dlp integration boundary

Per `NFR-008`, yt-dlp churn is confined to exactly two modules:

- `downloader/ytdlp_adapter.py` — builds the yt-dlp options dict from a `DownloadRequest`;
  projects `info_dict` into `MediaInfo`/`FormatInfo`.
- `downloader/worker.py` — the only place `YoutubeDL` is instantiated.

Nothing else in the codebase may `import yt_dlp`. A change to yt-dlp's option names or dict
keys must be absorbable by editing those two files.

**yt-dlp resolution order** at worker start (`OPS-002`): the user-managed copy in
`user_data_dir/tracksandtrails/ytdlp/` (prepended to `sys.path` if present), then the bundled
baseline. The resolved version is reported in the UI (`REQ-025`). Pinning a bundled baseline
gives reproducible behavior; letting the user update out-of-band is what keeps a broken site
fixable without a release (`C-002`).

The user-managed copy is installed by **downloading and extracting the yt-dlp wheel**, not by
pip — released builds are frozen (`REL-001`) and have neither pip nor a writable
`site-packages`. This works only because yt-dlp is pure Python (no compiled extensions), so
there is no build step and no ABI matching. `environment.py` owns this and must fail loudly,
falling back to the baseline, if an extracted copy does not import cleanly.

## 7. Error handling

`core/errors.py` classifies every failure into a taxonomy, because the user-facing response
differs per class:

| Kind | Example | Response |
|---|---|---|
| `UNSUPPORTED_URL` | no extractor matches | Fail; suggest a yt-dlp update |
| `EXTRACTOR_ERROR` | site changed, video removed, private | Fail; show the extractor's message verbatim |
| `AUTH_REQUIRED` | login-walled | Fail; point to cookie settings (`REQ-026`) |
| `GEO_RESTRICTED` | region-blocked | Fail; state it plainly |
| `DRM_PROTECTED` | protected stream | Fail permanently; **never retried, never worked around** (`REQ-EXCL-001`) |
| `NETWORK` | timeout, connection reset | Retry with backoff, bounded |
| `FFMPEG_MISSING` / `FFMPEG_ERROR` | merge/convert failure | Fail; link to ffmpeg settings (`REQ-024`) |
| `DISK` | out of space, permission denied | Fail; pause the queue |
| `WORKER_CRASH` | non-zero exit, no result message | Fail; log exit code (`REQ-028`) |
| `INTERRUPTED` | the application died mid-flight | Fail; offer retry (`REQ-012`, `NFR-003`) |
| `CANCELLED` | user action | Not an error |

Only `NETWORK` auto-retries. Everything else waits for the user (`REQ-018`) — silently
retrying a permanent failure just hammers the site. That includes `INTERRUPTED`: an application
that crashed mid-download should not relaunch straight back into the download it crashed on.

`INTERRUPTED` is distinct from `WORKER_CRASH` and the difference is observability. A worker
crash was *watched* — the parent survived, saw a non-zero exit, and can log the code. An
interruption was watched by nobody: the whole process died, and all that is known at the next
startup is that a status which persisted before the crash cannot still be true. Collapsing the
two would make a failed job's history unable to say whether a retry has any prospect of working.

*(Added 2026-07-26 by `T-014`, on maintainer approval. §5 had required an "`INTERRUPTED`
presentation of `FAILED`" since the document was written, while this table never listed it —
so `core/errors.py` implemented §7 faithfully and §5's crash recovery had no kind to use.)*

The extractor's original message is always preserved verbatim (`NFR-006`) alongside the
classification. Classification is a hint, not a replacement.

## 8. Cross-cutting patterns

- **Threading.** Qt objects are touched only on the GUI thread. `ResultPump` is the single
  bridge from worker processes to the GUI, and it communicates only by signal emission.
- **Long operations.** Nothing on the GUI thread may block. Probing is a worker process too,
  not a "quick" inline call — probe latency is unbounded (`NFR-001`).
- **Settings propagation.** Settings are read at job-creation time into the `DownloadRequest`
  and frozen there. A running job never observes a mid-flight settings change.
- **Logging.** Python `logging`; app log to `user_cache_dir`, per-job logs separate. Cookie
  file paths, cookie contents, proxy credentials, and URL query parameters are redacted at the
  handler level, not at each call site (`REQ-026`, `NFR-007`).

  **Every** query parameter goes, not the ones that "look like tokens": deciding which names
  look like secrets is the recogniser problem that cost `T-018` four review rounds, and nothing
  downstream reads a query parameter out of a log.

  **One shape is deliberately out of scope**, authorized by the maintainer on 2026-07-27 after
  `T038-R1`: a bare `NAME=value` with no header, path or URL around it. It is indistinguishable
  from `height=1080`, and a rule wide enough to catch it redacts most of every line — which is
  the `T014-R6` failure in the opposite direction, a log that cannot describe what happened.
  This costs less than it appears: cookie *contents* are not a value this application ever
  holds, because `DownloadRequest` carries a browser name and yt-dlp reads the jar itself. When
  the application does hold a sensitive literal, `core/logging.remember_a_secret()` redacts that
  exact string, which needs no pattern at all.

  **The `REQ-026` boundary is narrower than this one, and both stand.** `REQ-026` and `DAT-003`
  preserve a cookie path that yt-dlp names inside a *stored diagnostic*, because `NFR-006`
  requires that message verbatim and the database is local and user-owned. A log is written by
  this application rather than quoted by it, so the supplied-value rule binds here in full and
  the path goes. The two sinks differ on purpose; neither weakens the other.
- **Filename safety.** All output paths pass through `core/paths.py`, which enforces the
  intersection of Linux and Windows rules — reserved device names (`CON`, `NUL`, `LPT1`…),
  characters illegal on NTFS, trailing dots/spaces, and path-length limits. A title-derived
  filename must never escape the configured output directory: reject `..` and absolute
  components after template rendering.
- **Theme.** Brand palette with light and dark variants; never color-only signaling
  (`NFR-005`). These three hexes are the project's **adopted canonical swatches**, selected
  from the source logo on 2026-07-25 (`T-003`; corrected by `T-022` after `T003-R1`):

  | Role | Hex |
  |---|---|
  | Forest green — primary | `#1E5E47` |
  | Trail gold — accent | `#D9A24C` |
  | Deep green — shading | `#083122` |

  **They are adopted, not measured.** The artwork contains no flat fills — each colored region
  is a cloud spanning roughly ±2 per channel — so clustering it recovers a different center for
  every reasonable algorithm and radius, and no percentage-of-the-logo figure is stable either
  (`T003-R1`). These values are the definition; the artwork is their origin, not their proof.
  Do not re-derive them from `icon.png`, and do not cite a measurement as evidence for them.

  Source of record: `resources/icons/icon.png`, SHA-256
  `f0e202c714ac316fdaa75b4cccbc0b46fee4686129ac09d0d276446abfe74b8d` (`T003-R5`). Changing a
  swatch is a deliberate brand decision, not a measurement update.

  Derived light/dark ramps are Phase 4 work; only these three are fixed.

## 9. Security boundaries

- The application executes exactly two external programs: the Python interpreter (for worker
  processes) and ffmpeg. Both paths are resolved explicitly, never through a shell.
- **No `shell=True`, anywhere.** URLs, titles, and template strings are attacker-influenced
  data and must never reach a shell.
- Output-template rendering is not `eval`; it uses yt-dlp's own template mechanism plus the
  containment check in §8.
- No inbound network surface (§2). No telemetry (`NFR-007`).
- Cookie material is passed to the worker by path, used, and never persisted into the
  database, history, or logs.

## 10. Persistence and migration strategy

- Schema version stored in SQLite `user_version`. Startup runs forward migrations in
  order from `persistence/migrations/`.
- Migrations are additive-first and never destructive without a pre-migration backup copy
  of the database file.
- The DB is user data (`REQ-012`) — a schema change that would lose queue or history without
  a migration is a defect, not an acceptable simplification.
- A database from a *newer* app version is refused with a clear message rather than opened.

## 11. Testing architecture

Detail lives in `ai/TESTING.md`. The architectural commitments that make it possible:

- `core/` is pure and headless-testable — the bulk of logic lives there deliberately.
- The parent/child contract is `downloader/protocol.py` dataclasses, so the manager can be
  tested against a fake worker and the worker against a fake queue.
- `ytdlp_adapter.py` projection is tested against **recorded** `info_dict` fixtures, so
  format-table behavior is verified without network access.
- Layering rules (§4) are enforced by an automated import test, not review vigilance.
- Real-network tests exist, are marked, and are excluded from the default run.

## 12. Deployment architecture

**Artifacts are frozen and self-contained: the user needs no Python installed** (`REL-001`,
`REQ-029`). Each artifact bundles its own interpreter, Qt, and the pinned yt-dlp baseline.

- **Windows** — PyInstaller one-dir build + Inno Setup installer, ffmpeg bundled (`OPS-001`).
- **Linux** — a self-contained format (AppImage or Flatpak); the specific choice is deferred
  to a follow-up `REL-` decision in Phase 5. ffmpeg stays a system dependency, not bundled.
- `pipx install` may exist as a secondary developer convenience only. It reintroduces the
  Python prerequisite and can never be the sole Linux option.

Freezing is **not** a Phase 5 concern only. It interacts with §3 in one dangerous way —
`freeze_support()` — so a smoke-level frozen build runs in CI from Phase 0 (`T-020`), where a
recursive-launch regression fails a pipeline instead of shipping.

That smoke test needs code **inside** the artifact, because the failure only exists there:
`src/tracks_and_trails/_freeze_probe.py` spawns one child, exchanges one message, and records
each top-level application start. It is listed in §4's structure so the tree is documented
completely, but it belongs to **none of the four layers** — it is frozen-build diagnostic
infrastructure, which is what the leading underscore marks. It imports
no Qt, so a spawned child inherits none (`ARC-002`), and is reachable only through an explicit
`--spawn-probe` argument.

It must share the real entry point rather than live in a separate frozen script. The property
under test is that `multiprocessing.freeze_support()` runs before anything else *in
`__main__.py`*; a second entry point would have its own ordering and would prove nothing about
the one users actually run.

Qt must remain dynamically linked *inside the bundle*, verified against the built artifact
rather than project metadata (`NFR-009`, `LIC-001`).
