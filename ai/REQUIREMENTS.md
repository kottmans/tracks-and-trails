# REQUIREMENTS.md — Tracks & Trails

**Purpose:** Define the product from the user and business perspective.
**Authority:** Canonical for goals, required behavior, scope, and user-facing constraints.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
**Last reviewed:** 2026-07-25
**Update when:** Product scope, a feature, a user-facing constraint, or acceptance criteria change.
**Does not contain:** Schema details, framework specifics, task lists, review history.

---

## 1. Product purpose

yt-dlp is the best media downloader available and it is command-line only. That excludes
everyone who will not memorize format selectors, output templates, and post-processor
flags — and it makes routine multi-download work tedious even for people who know them.

Tracks & Trails is a desktop GUI that exposes yt-dlp's real capability through a queue-based
interface, without hiding the power underneath. It is a **general-purpose downloader**:
video and audio are equally supported.

Design tension to hold: *approachable by default, complete when you dig.* A first-time user
picks a preset and presses Download. An expert reaches the same format selectors, output
templates, and post-processors they would have typed.

## 2. Target users

| User | Needs |
|---|---|
| **Casual saver** | Paste a link, pick "1080p video" or "MP3 audio", get a file in a sensible folder. Zero yt-dlp knowledge. |
| **Archivist / collector** | Queue dozens of URLs and playlists, control naming and folder layout, resume across restarts, see what failed and why. |
| **Power user** | Exact format IDs, raw format selector strings, subtitles, chapters, sponsor sections, cookies, rate limits, proxies. Would otherwise use the CLI. |

Assumed environment: a personal desktop machine, single local user, no multi-user server
deployment, no account system.

## 3. Supported platforms

| Platform | Support level |
|---|---|
| Linux (x86-64, glibc — Fedora/Ubuntu class) | **Primary.** Development and reference platform. |
| Windows 10/11 (x86-64) | **Primary.** Must reach feature parity; verified before any release. |
| macOS | **Not supported.** Not excluded architecturally, but untested and unreleased. |

A change is not complete if it works on only one primary platform. Where a behavior cannot
be verified on both, that must be stated as unverified rather than assumed.

**Current verification constraint** (`OPS-004`, narrowing `OPS-003`): there is no Windows
machine available, so Windows is verified by CI — but the runner provides a real desktop, and
the `windows desktop` job asserts against it: the application launches through its real entry
point under the real platform plugin, menus are keyboard reachable, and the UI Automation tree
matches an explicit name-and-role contract for the window, menu bar, every menu action, and the
About dialog.

*Rewritten 2026-07-26 after `T026-R2`.* An earlier version of this paragraph claimed the
name/role gap was closed while the tests required only that *some* menu items existed with
non-empty names — a claim that outran its evidence. Scope statements here must not exceed what
a gate actually fails on.

Still *known-unverified* on Windows, and to be reported as such: whether rendering **looks**
right, whether Narrator **sounds** coherent, whether the installer **feels** normal, shell
foreground and file-association behavior, and long-running stability. Not yet covered by
automation: installer placement and removal (`T-039`). **Widget tab order is covered** as of
2026-07-28 (`T-040`), on Windows as well as Linux; this said it was "blocked until focusable
controls exist", which stopped being true when `T-016` supplied them (`COORD-R5`). A single real Windows session discharges the subjective
residue and blocks the first public release.

## 4. Functional requirements

### Input and inspection

- **REQ-001** — Accept one or more URLs: typed, pasted, drag-and-dropped, or multi-line pasted as a batch.
- **REQ-002** — Probe a URL without downloading, and show title, uploader, duration, thumbnail, and whether it is a single item or a playlist.
- **REQ-003** — Show the available formats for a probed URL in a sortable table (format ID, extension, resolution, fps, codecs, bitrate, filesize/estimate, notes).
- **REQ-004** — For a playlist, let the user select which entries to enqueue, including select-all and range selection, before any download starts.
- **REQ-005** — Detect and warn when a URL is unsupported or the extractor reports an error, with the extractor's own message shown verbatim and not paraphrased.

### Selecting what to download

- **REQ-006** — Provide named **presets** covering the common cases, at minimum: best video ≤1080p (MP4), best video available, audio only (MP3), audio only (best/original), and video with embedded subtitles. Presets are the default path.
- **REQ-007** — Allow the user to create, edit, duplicate, and delete their own presets, and set one as the default.
- **REQ-008** — Allow selecting specific format IDs directly from the format table (`REQ-003`), including a separate video and audio stream to be merged.
- **REQ-009** — Allow entering a **raw yt-dlp format selector string** as an escape hatch, with the effective selector always visible for any preset so users can learn the syntax.
- **REQ-010** — Support post-processing options: extract/convert audio to a chosen codec and quality, remux/recode container, embed thumbnail, embed metadata, embed chapters, embed or write subtitle files (with language selection).
- **REQ-011** — Support output path and filename control via a configurable output template, with a live preview of the resulting path for the current item. **Where the final container is yt-dlp's to choose, the preview is labelled as the *intended* path rather than presented as the resulting one** (amended 2026-08-01, maintainer decision, `T046-R2`). Audio extraction to a **named** codec is previewed exactly, through yt-dlp's own `ACODECS` table — the codec is not the extension, since `aac` and `alac` both land in `m4a` and `vorbis` in `ogg` (`T046-R4`). **Audio only (original) is provisional**: `best` keeps the codec rather than the container, and yt-dlp decides by running `ffprobe` on the downloaded file and by checking the *downloaded* extension, neither of which exists before the write. a merge of separate video and audio streams is not derivable from the request, and `T-046` established that a predicted name is unsafe to rely on — showing that prediction as a promise is the same mistake one field over. *(This read only "a live preview of the resulting path", which `%(ext)s` cannot honestly deliver for a merge: it renders the container that arrives, not the one that is kept. `REQ-010`'s remux and recode make the choice explicit in the request, and `T-112` owns making preview equal write once they exist.)*

### Queue and execution

- **REQ-012** — Maintain a persistent download queue. Queue and history survive application restart and unexpected termination.
- **REQ-013** — Run a bounded, user-configurable number of downloads concurrently (default 3, minimum 1).
- **REQ-014** — Per job, show live progress: percent, downloaded/total size, speed, ETA, current stage (probing, downloading video, downloading audio, merging, post-processing).
- **REQ-015** — Per job, support cancel, retry, and remove. Cancelling must terminate the underlying work promptly and must not leave the UI unresponsive. Removing takes a job out of the queue and never deletes a file from disk. **Pause and resume are queue-level, not per-job** (`UX-001`, maintainer, 2026-07-29): pausing lets in-flight downloads finish and starts nothing new, so no partial file is ever created by pausing. Remove never deletes a file; removing a running job cancels it first. *(This read "Per job, support cancel, pause, resume, retry, and remove" until `T-080`'s decision; `core/job_state.py` still carries `RUNNING → PAUSED → RUNNING` edges that nothing now reaches, which `T-080` owns. `UX-001` holds the rationale and its reopening condition — per-job pause becomes coherent when `REQ-017` lands resume in Phase 3.)*
- **REQ-016** — Support reordering pending jobs and clearing completed ones.
- **REQ-017** — Resume partially completed downloads across restarts where the site and format allow it, and state clearly when resumption is not possible.
- **REQ-018** — On failure, record the error, keep the job in the queue in a failed state, and offer retry. Never fail silently.
- **REQ-019** — Provide a per-job log view containing the actual yt-dlp diagnostic output for that job, copyable for bug reports.
  - *Scoped 2026-08-01 by `T-084`, in two ways.* **Bounded:** a job's log is capped at 4 MiB
    (`MAX_JOB_LOG_BYTES` × two files), and the **newest** lines are the ones kept — a log is read
    to find out how something ended. **Redacted origin-agnostically** — `DAT-003`'s
    accepted rule for log *emission*, which `DAT-004` briefly and wrongly narrowed (`T084-R1`,
    Critical; that entry is withdrawn). Every line is redacted whoever wrote the text inside it, so
    a diagnostic can lose a path it named. **Ruled 2026-08-01:** `DAT-003` wins and `T-084`'s
    contradictory criterion was amended; `NFR-006`'s promise is kept at the database sink, which
    stores the extractor's message verbatim. **What is copied is the file exactly** — the
    view is capped for the GUI thread's sake and Copy re-reads the artifact (`T084-R2`).

### Library and results

- **REQ-020** — Maintain a history of completed downloads with source URL, title, resolved output path, format used, size, and completion time.
- **REQ-021** — Open a completed file, or reveal it in the system file manager, from the history and queue views.
- **REQ-022** — Detect that a URL has been downloaded before and warn before re-downloading, with an override.

### Configuration and environment

- **REQ-023** — Provide a settings screen covering: default download directory, default preset, concurrency limit, output template, ffmpeg location, network options (rate limit, proxy, retries), cookie source, and theme.
- **REQ-024** — Detect ffmpeg at startup and clearly report which features are unavailable without it, rather than failing at merge time.
- **REQ-025** — Report the yt-dlp version in use and let the user update yt-dlp from within the application without reinstalling Tracks & Trails.
- **REQ-026** — Support authenticated access **to content the user is already entitled to**, via cookies from a browser profile or a cookies file. Credentials and cookie paths **that this application supplies** are never written to logs or to history. A cookie path that yt-dlp itself names inside a diagnostic is preserved with that message, which `NFR-006` requires be kept verbatim — see `DAT-003` for the reasoning and the condition that reopens it.

- **REQ-029** — Installing and running Tracks & Trails must require **no Python installation, no virtual environment, and no developer toolchain** on the user's machine. The implementation language is not a user-facing prerequisite (`REL-001`).

### Cross-cutting behavior

- **REQ-027** — The interface must remain responsive during all downloading and probing work. No operation blocks the UI thread.
- **REQ-028** — A crash or hang inside yt-dlp or an extractor must not crash the application. Affected jobs fail; the app survives.

## 5. Non-functional requirements

- **NFR-001 — Responsiveness.** UI thread is never blocked on network, disk, or subprocess work. Interactions respond within ~100 ms.
- **NFR-002 — Startup.** Cold start to interactive window under 3 seconds on the reference Linux machine.
- **NFR-003 — Fault isolation.** Per `REQ-028`, extractor faults are contained. Job state is durable: an unclean kill must not corrupt the queue database.
- **NFR-004 — Portability.** One codebase, no platform forks beyond a documented platform-abstraction layer. All paths use platform-appropriate user config/data/cache directories; nothing is written beside the installed application.
- **NFR-005 — Accessibility.** Full keyboard navigation, visible focus, screen-reader labels on all controls, and no information conveyed by color alone.
- **NFR-006 — Honest errors.** Errors state what failed, why, and what the user can do. Extractor messages are surfaced, never swallowed or replaced with a generic message.
- **NFR-007 — Privacy.** No telemetry, no analytics, no phone-home, no crash reporting to a third party. The only outbound network traffic is downloads the user requested and explicit yt-dlp update checks.
- **NFR-008 — Resilience to yt-dlp churn.** yt-dlp changes frequently. The integration must isolate that churn behind an adapter so a yt-dlp update does not require changes spread across the codebase.
- **NFR-009 — Licensing.** All bundled and runtime dependencies must be license-compatible with distribution (see `LIC-001`). Qt/PySide6 stays dynamically linked.

## 6. MVP scope

The MVP is a working queue-based downloader on both primary platforms:

`REQ-001`, `REQ-002`, `REQ-003`, `REQ-005`, `REQ-006`, `REQ-008`, `REQ-009`, `REQ-011`,
`REQ-012`, `REQ-013`, `REQ-014`, `REQ-015`, `REQ-018`, `REQ-019`, `REQ-020`, `REQ-021`,
`REQ-023`, `REQ-024`, `REQ-027`, `REQ-028`, and all NFRs.

Plus, from `REQ-010`, the audio-extraction and remux subset only.

## 7. Post-MVP scope

Deferred but intended: `REQ-004` (playlist entry selection), `REQ-007` (user presets),
`REQ-010` in full (thumbnails, metadata, chapters, subtitles), `REQ-016` (reordering),
`REQ-017` (cross-restart resume), `REQ-022` (duplicate detection), `REQ-025` (in-app yt-dlp
update), `REQ-026` (cookies/auth).

Ideas not yet committed: scheduled/deferred downloads, per-site profiles, watch-folder or
URL-file import, browser extension "send to Tracks & Trails", SponsorBlock integration,
music-library organization and tagging, download bandwidth scheduling.

## 8. Explicit exclusions (`REQ-EXCL`)

These are **out of scope and will not be implemented**, including on request:

- **REQ-EXCL-001** — No DRM circumvention. Widevine/PlayReady/FairPlay-protected content is not supported, and no decryption, key extraction, or DRM workaround will be added.
- **REQ-EXCL-002** — No paywall, geo-restriction, or authentication bypass. `REQ-026` exists so a user can access content they *already have* an account for; it is not a circumvention feature.
- **REQ-EXCL-003** — No credential harvesting. The application never asks for a site username/password to store, and never reads a browser profile without an explicit user action naming that profile.
- **REQ-EXCL-004** — No bulk scraping or crawling. Downloads originate from URLs a user supplied. No site-wide enumeration, no automated discovery of new URLs.
- **REQ-EXCL-005** — No rate-limit evasion features: no automatic IP rotation, no CAPTCHA solving, no user-agent randomization presented as anti-detection.

Also out of scope for architectural reasons: macOS/mobile builds, any server or multi-user
mode, cloud sync, an account system, and a media player (playback is delegated to the
system default application).

## 9. Assumptions

- **A-001** — The user has the right to download the content they queue. The application does not and cannot verify this; it is the user's responsibility, and this is stated in the README.
- **A-002** — ffmpeg is available: from the system package manager on Linux, bundled on Windows (`OPS-001`).
- **A-003** — A desktop session is present. There is no headless or CLI mode in scope.
- **A-004** — Single local user; no concurrent instances against the same database. *Unverified* — enforcement of single-instance behavior is a Phase 2 task.

## 10. Constraints

- **C-001** — yt-dlp is the only download engine. Tracks & Trails does not reimplement extraction.
- **C-002** — Site support equals yt-dlp's site support. When a site breaks, the fix path is a yt-dlp update (`REQ-025`), not project code.
- **C-003** — Linux and Windows parity is required at every release (§3).
- **C-004** — Distribution license must be compatible with LGPLv3 (PySide6) and the GPL/LGPL terms of any bundled ffmpeg build (`LIC-001`).

## 11. Acceptance criteria — MVP

The MVP is accepted when, **on both Linux and Windows**:

1. A user with no yt-dlp knowledge can paste a URL, accept the default preset, and get a playable file in the configured directory.
2. The format table for a probed URL matches what `yt-dlp -F` reports for the same URL.
3. Three downloads run concurrently with independent, accurate live progress, and the UI stays interactive throughout.
4. Cancelling a running download stops it within 2 seconds, leaves no orphaned process, and leaves no partial file presented as complete.
5. Killing the application mid-download and restarting shows the queue intact with those jobs in a recoverable state.
6. A URL that yt-dlp cannot handle produces a failed job showing the extractor's own message and a copyable log — and no other job is affected.
7. Force-killing a download worker process does not crash or hang the application.
8. Every interactive control is reachable and operable by keyboard alone.
9. The full test suite, `ruff`, and `mypy` pass.

For criteria requiring interactive use, "on Windows" currently means *via CI automation
where possible, and explicitly recorded as unverified where not* (`OPS-003`). Criterion 8 in
particular is only partly automatable. The MVP may be accepted with those gaps named; the
**first public release may not** — see `ai/TESTING.md` §8 item 15.
