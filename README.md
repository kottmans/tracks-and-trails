<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-on-dark.png">
    <img src="docs/assets/logo-on-light.png" width="200" alt="Tracks &amp; Trails logo">
  </picture>
</p>

# Tracks & Trails

A desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp) on Linux and Windows.

Tracks & Trails gives yt-dlp a queue-based desktop interface — presets and one-click downloads when you want
simple, and the full format table, output templates, and post-processors when you don't.

---

## Status

**Working application, run from source. Not yet released.**

Phases 0–3 are complete and signed off: the process model, the persistent queue, concurrency,
and the format/content depth that separates this from a preset-only wrapper. Phase 4 —
settings, theming, and accessibility — is built, and its exit sign-off is pending. Phase 5 is
packaging: a Linux AppImage and a Windows installer are built and being tested, but no release
has been published.

Concretely, that means:

| | |
|---|---|
| **You can** | [install it from source](#installing) and download things with it today |
| **You cannot** | download a release — the first one has not been published |
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
- Tells you when a newer version is out: once a day (switch it off in Preferences) or from Help,
  Check for Updates. It asks GitHub for the latest release number and sends nothing about you
- No telemetry, no analytics

## Installing

**There is no release to download yet.** Until the first one is published, install from source
as below. It takes a few minutes, most of it downloading Qt. The install brings its own pinned
copy of yt-dlp, so you do not need yt-dlp installed separately.

You need:

- **Python 3.14 or newer.** Check with `python3 --version`, or `py -3.14 --version` on Windows.
- **git**
- **ffmpeg** is optional but recommended. Without it the app still runs, but it cannot merge
  separate video and audio streams or extract audio, and it tells you so.

### Linux

Install the prerequisites from your package manager:

```bash
# Fedora. ffmpeg-free is in Fedora's own repositories; RPM Fusion's ffmpeg package
# supports more formats.
sudo dnf install python3 git ffmpeg-free

# Debian and Ubuntu
sudo apt install python3 python3-venv git ffmpeg
```

If your distribution's `python3` is older than 3.14, install a newer Python first.

Then install Tracks & Trails into its own folder and start it:

```bash
git clone https://github.com/kottmans/tracks-and-trails.git
cd tracks-and-trails
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .

.venv/bin/tracks-and-trails
```

### Windows 10 and 11

In PowerShell, install the prerequisites with winget, then **open a new PowerShell window** so
they are on your `PATH`:

```powershell
winget install --id Python.Python.3.14
winget install --id Git.Git
winget install --id Gyan.FFmpeg
```

Then install Tracks & Trails into its own folder and start it:

```powershell
git clone https://github.com/kottmans/tracks-and-trails.git
cd tracks-and-trails
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install .

.venv\Scripts\tracks-and-trails
```

If the app says it cannot find ffmpeg, set its location in **Settings → Preferences…**.

### Starting it again, updating, and removing it

- **Start it again** by running the last line above from the `tracks-and-trails` folder.
- **Update** from the same folder with `git pull`, then repeat the `pip install .` line.
  yt-dlp can also be updated from inside the app, without updating Tracks & Trails.
- **Remove it** by deleting the `tracks-and-trails` folder. Your settings, queue and log are kept
  in your user profile, not in that folder; `--help` prints where the log is (see below).

### Command line

The options below go after the launcher from the install steps. The `tracks-and-trails` command
is inside the `.venv` folder and is not on your `PATH`, so run it from the `tracks-and-trails`
folder with its path:

```text
.venv/bin/tracks-and-trails --help            # Linux
.venv\Scripts\tracks-and-trails --help        # Windows
```

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

The tests need an editable development install instead; [DEVELOPMENT](docs/DEVELOPMENT.md#setup)
has the full setup.

```bash
pip install -e ".[dev]"
python -m pytest -q -n auto               # the suite, in parallel
python -m pytest -q tests/unit            # headless, fast, no Qt
ruff check . && ruff format --check .
mypy src tests
```

Dated test results and their verified revisions are recorded in
[STATUS](docs/project/STATUS.md#verification).
`tests/network/` is opt-in and excluded by default; everything else runs offline against recorded
yt-dlp `info_dict` fixtures.

CI skips the full suite for the enumerated prose paths in `ci.yml`'s
`paths-ignore`; TASKS.md and COMPLETED_TASKS.md changes trigger the placement
check in `prose.yml`. Gated documentation such as COMPLETED_TASKS.md and
`docs/YTDLP_OPTION_AUDIT.md` also triggers the full CI checks.
[TESTING](docs/project/TESTING.md) defines required gates and
[DEVELOPMENT](docs/DEVELOPMENT.md) covers contributor setup.

## A few engineering choices

The [decision index](docs/project/DECISIONS.md#effective-decision-index) links to
the choices below and their amendments.

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
  request. That is deliberately narrower than "the database holds no secrets", in two ways: a
  diagnostic yt-dlp emits is stored verbatim because `NFR-006` requires it intact, and yt-dlp
  sometimes names a cookie file in one; and the URL you queue is stored whole, so a credential
  inside one is stored with it. `DAT-003` is the first trade-off, taken explicitly after two
  attempts to scrub such prose failed. [SECURITY.md](SECURITY.md) states both boundaries in full. See [DAT-003 and its amendments](docs/project/DECISIONS.md#effective-decision-index)
  for the storage/logging boundary and retained diagnostic risk.
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
docs/project/            requirements, design, work state and review evidence
docs/                    developer and operator documentation
packaging/               PyInstaller spec and the frozen smoke test
tools/                   probes, screenshot generators, one-off diagnostics
```

## Documentation

| Reader purpose | Start here |
|---|---|
| Understand and run the product | This README, especially [Installing](#installing) |
| Develop and test | [DEVELOPMENT](docs/DEVELOPMENT.md) and [test policy](docs/project/TESTING.md) |
| Understand design and rationale | [ARCHITECTURE](docs/project/ARCHITECTURE.md) and [decision index](docs/project/DECISIONS.md#effective-decision-index) |
| Find active work and blockers | [STATUS](docs/project/STATUS.md) and [TASKS](docs/project/TASKS.md) |
| Find completed or cancelled work | [COMPLETED_TASKS](docs/project/COMPLETED_TASKS.md) |
| Inspect review evidence | [REVIEWS](docs/project/REVIEWS.md) |


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
| [docs/project/COMPLETED_TASKS.md](docs/project/COMPLETED_TASKS.md) | What work closed, and what evidence was recorded? |
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

Not currently open to outside code contributions; bug reports and feature requests are welcome.
[CONTRIBUTING](CONTRIBUTING.md) explains why and how to report, and everyone taking part follows
the [Code of Conduct](CODE_OF_CONDUCT.md). If contributions open, they will be under the MIT
License. [AGENTS.md](AGENTS.md) documents the rules the project is built under — roles, file ownership,
scope control, and the validation required before anything is called complete.

## License

[MIT](LICENSE) — Copyright (c) 2026 Sean Kottman. See `LIC-001` in
[docs/project/DECISIONS.md](docs/project/DECISIONS.md).

MIT covers this source. Distributed binaries will additionally carry third-party obligations:
Qt/PySide6 is **LGPLv3** and must stay dynamically linked, any bundled ffmpeg build must be
**LGPL**, and yt-dlp is **Unlicense**. Those license texts ship with every release artifact.
