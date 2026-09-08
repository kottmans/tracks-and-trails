# Tracks & Trails

A desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) on Linux and Windows.

yt-dlp is the best media downloader available, and it is command-line only. Tracks & Trails
puts a real queue-based interface on it — presets and one-click downloads when you want
simple, and the full format table, output templates, and post-processors when you don't.

Video and audio are equally first-class.

---

## Status

**Working application, run from source. Not yet released.**

Phases 0–3 are complete and signed off: the process model, the persistent queue, concurrency,
and the format/content depth that separates this from a preset-only wrapper. Phase 4 —
settings, theming, and accessibility — is in progress. Phase 5 is packaging, and none of it is
built yet.

Concretely, that means:

| | |
|---|---|
| **You can** | clone it, install it, and download things with it today |
| **You cannot** | install it from a release — there are no installers or packages yet |
| **Targets** | Linux (Fedora, x86-64) and Windows 10/11 (x86-64), both exercised by CI |
| **Not supported** | macOS |

[docs/project/STATUS.md](docs/project/STATUS.md) is the only document authoritative for what is
actually built, including what is known-broken and what is unexplained.

## What works today

- Paste, drag, or batch-paste URLs, and probe them without downloading
- Presets for the common cases, with the effective yt-dlp format selector always visible
- Full sortable format table — pick exact video and audio streams to merge
- Persistent download queue with configurable concurrency, live progress, and cancel/retry
- Queue survives restart and survives an unclean kill — proven by killing a real process,
  not by closing a connection politely
- Playlist handling, with per-entry rows and unavailable entries reported rather than hidden
- Audio extraction, container remux, embedded thumbnails, metadata, chapters, and subtitles
- Configurable output templates with live path preview
- Settings: network options, cookie source, ffmpeg detection and override, light and dark themes
- In-app yt-dlp version display and update, so a broken site is fixable without waiting for a release
- No telemetry, no analytics, no phone-home

## Running it

You need **Python 3.14+**, **git**, and **ffmpeg** (for merging and audio extraction — the
application runs without it, and tells you what it cannot do).

```bash
git clone https://github.com/kottmans/tracks-and-trails
cd tracks-and-trails

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .

python -m tracks_and_trails
```

That last line opens the application window. The install pulls in PySide6 and a pinned yt-dlp,
so no separate yt-dlp is needed.

ffmpeg comes from your package manager — `dnf install ffmpeg` or `apt install ffmpeg` on Linux;
on Windows, put it on `PATH` or set its location in Settings.

### Command line

```
usage: tracks-and-trails [--version] [--help] [--log-level=LEVEL] [--spawn-probe]
                         [--ytdlp-probe]

  --version      print the version and exit
  --help, -h     print this message and exit
  --log-level=LEVEL
                 how much the application log records, one of
                 DEBUG, INFO, WARNING, ERROR, CRITICAL (default INFO).
  --spawn-probe  self-test the process model and exit
  --ytdlp-probe  self-test the bundled yt-dlp and exit
```

The log is redacted at every level, and `--log-level=DEBUG` does not turn on yt-dlp's own
verbose output. Redaction is a pattern set rather than a blanket guarantee — it strips proxy
credentials, URL query strings and cookie stores named as such, and it does **not** hide your
output paths. [SECURITY.md](SECURITY.md) has the exact table. `--help` prints the log's actual
path on your machine.

### Running the tests

```bash
pip install -e ".[dev]"
python -m pytest -q -n auto               # the suite, in parallel
python -m pytest -q tests/unit            # headless, fast, no Qt
ruff check . && ruff format --check .
mypy src tests
```

That is **3925 passing tests and 21 skipped**, measured on Linux at the current head.
`tests/network/` is opt-in and excluded by default; everything else runs offline against recorded
yt-dlp `info_dict` fixtures.

CI runs the full suite on Linux and Windows for pushes that touch code, plus a nightly run.
Documentation-only pushes are excluded deliberately (`OPS-011`) — nothing they change is something
a test reads. The Windows machine is the only Windows environment this project has, so anything it
does not check is genuinely unverified there rather than merely unautomated. [docs/project/TESTING.md](docs/project/TESTING.md) is
authoritative for what must be tested and which gates are required, and
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) covers local setup in detail.

## A few engineering choices

These are the ones that shaped everything else. Each links to its recorded decision.

- **yt-dlp runs in a spawned child process, never in the GUI process** (`ARC-002`). yt-dlp is a
  large library that can hang, crash, or call `sys.exit`; a worker that takes the window with it
  is not acceptable. Workers inherit no Qt, which is also what makes the frozen build possible.
- **yt-dlp is pinned exactly, not floated** (`OPS-002`). A tested baseline makes behavior
  reproducible. Users update their own copy in-app instead, and a weekly canary runs the suite
  against the newer yt-dlp so upstream drift is found here rather than by a user.
- **The queue is SQLite with one committed statement per write** (`DAT-001`). There is no state
  in which half a job is stored, and the crash test proves it by killing a real process.
- **Proxy credentials and cookie paths are refused at the model boundary** (`REQ-026`,
  `DAT-003`) rather than filtered on the way out, so the application cannot put one into a stored
  request. That is deliberately narrower than "the database holds no secrets": a diagnostic
  yt-dlp emits is stored verbatim because `NFR-006` requires it intact, and yt-dlp sometimes names
  a cookie file in one. `DAT-003` is that trade-off, taken explicitly after two attempts to scrub
  such prose failed — one of them corrupting a user's output directory. The four review rounds
  behind it are in [docs/project/REVIEWS.md](docs/project/REVIEWS.md), and are a fair sample of
  what the process here catches.
- **No pull-request trigger exists in any workflow, and a test enforces it** (`T-262`, `T-264`).
  Every runner is self-hosted, so a fork's pull request would be arbitrary code execution on a
  personal machine.

## What this is not

Tracks & Trails does **not** circumvent access controls. No DRM stripping, no paywall or
geo-restriction bypass, no authentication bypass, no rate-limit evasion, no bulk scraping.
Cookie support exists so you can reach content you already have an account for — nothing
more. See [docs/project/REQUIREMENTS.md](docs/project/REQUIREMENTS.md) §8 and decision `SEC-001`.

**You are responsible for having the right to download what you queue.** The application
cannot and does not verify this.

## Repository layout

```
src/tracks_and_trails/   the application
  core/                  domain models, settings, logging, paths
  downloader/            yt-dlp adapter, worker processes, the manager
  persistence/           SQLite schema, migrations, repositories
  ui/                    Qt widgets
tests/                   unit · ui · integration · network (opt-in)
docs/project/            coordination documents — start with TASKS.md
docs/                    developer and operator documentation
packaging/               PyInstaller spec and the frozen smoke test
tools/                   probes, screenshot generators, one-off diagnostics
```

## Documentation

The project keeps a structured record so that current truth, historical record, and rationale
are separable rather than tangled in one file.

| Document | Answers |
|---|---|
| [docs/project/STATUS.md](docs/project/STATUS.md) | Where does the project stand right now? |
| [docs/project/REQUIREMENTS.md](docs/project/REQUIREMENTS.md) | What must the product do? |
| [docs/project/ARCHITECTURE.md](docs/project/ARCHITECTURE.md) | How is the system designed? |
| [docs/project/DECISIONS.md](docs/project/DECISIONS.md) | Why was it designed that way? |
| [docs/project/IMPLEMENTATION_PLAN.md](docs/project/IMPLEMENTATION_PLAN.md) | In what order is it being built? |
| [docs/project/TASKS.md](docs/project/TASKS.md) | What work is ready, active, or blocked? |
| [docs/project/REVIEWS.md](docs/project/REVIEWS.md) | What was reviewed, and what did it find? |
| [docs/project/TESTING.md](docs/project/TESTING.md) | What must be tested, and how? |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | How do I set up and work on it? |
| [AGENTS.md](AGENTS.md) | The rules any contributor works under |

`REQUIREMENTS.md` and `ARCHITECTURE.md` describe the **approved design**, not what is built.
`STATUS.md` is the only document authoritative for implementation reality.

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability reporting process, what the application
treats as sensitive, and the CI trust boundary.

## Contributing

Not currently open to outside contributions. If that changes it will be under the MIT License.
[AGENTS.md](AGENTS.md) documents the rules the project is built under — roles, file ownership,
scope control, and the validation required before anything is called complete.

## License

[MIT](LICENSE) — Copyright (c) 2026 Sean Kottman. See `LIC-001` in
[docs/project/DECISIONS.md](docs/project/DECISIONS.md).

MIT covers this source. Distributed binaries will additionally carry third-party obligations:
Qt/PySide6 is **LGPLv3** and must stay dynamically linked, any bundled ffmpeg build must be
**LGPL**, and yt-dlp is **Unlicense**. Those license texts ship with every release artifact.
