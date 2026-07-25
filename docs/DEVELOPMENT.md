# DEVELOPMENT.md — Tracks & Trails

**Purpose:** Practical developer setup and local workflow.
**Authority:** Canonical for setup steps. **Not** authoritative for validation policy — see `ai/TESTING.md`.
**Owner:** Implementer / Documentation Maintainer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
**Update when:** Setup, dependencies, or the local workflow change.
**Does not contain:** What must be tested or which gates are required (`ai/TESTING.md`).

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.14+** | The pinned baseline (`ARC-001`, verified by `T-002`). PySide6 ships stable-ABI wheels, so no exact patch version is required. |
| **pip** | If `python3 -m pip` is missing (Fedora ships it separately), `python3 -m ensurepip --user` installs it without root. |
| **ffmpeg** | Needed at *runtime* for merging and audio extraction, not to build or test. `dnf install ffmpeg` / `apt install ffmpeg`. |
| **git** | |

End users need none of this — released builds bundle their own interpreter (`REL-001`).

## Setup

```bash
git clone https://github.com/kottmans/tracks-and-trails.git
cd tracks-and-trails
```

Set your commit identity **for this repository**. The project keeps personal addresses out of
a history that will eventually be public — use a GitHub `noreply` address:

```bash
git config user.email "<id>+<username>@users.noreply.github.com"
```

Repo-local config does not survive a fresh clone, so this is a per-clone step.

Then:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`-e` installs the package in editable mode, so `src/` changes take effect without reinstalling.
`[dev]` adds ruff, mypy, pytest, and pytest-qt. Add `[build]` when you need PyInstaller.

Verify:

```bash
python -m tracks_and_trails
```

It prints a version banner and exits 0. There is no window yet — that is `T-007`.

## Everyday commands

```bash
ruff check .                 # lint
ruff check --fix .           # lint, fixing what is auto-fixable
ruff format .                # format
mypy                         # types (strict; paths come from pyproject.toml)
pytest                       # default suite
pytest tests/unit            # fast headless loop
pytest -m network            # opt-in; hits real sites
pytest --cov --cov-report=term-missing
```

Run all four before considering a source change done:

```bash
ruff check . && ruff format --check . && mypy && pytest
```

**These are convenience shortcuts, not policy.** `ai/TESTING.md` §3 defines which checks are
*required* for which kind of change, and §8 defines the release gate. When they disagree with
this file, `ai/TESTING.md` wins.

## Repository layout

```
src/tracks_and_trails/
  __main__.py     entry point -- read the freeze_support() comment before editing
  app.py          application wiring
  core/           pure domain logic; no Qt, no yt-dlp, no I/O
  downloader/     process pool, IPC, worker, yt-dlp adapter
  persistence/    SQLite repositories, schema, migrations
  ui/             Qt widgets
tests/
  unit/           headless, fast, no network
  ui/             pytest-qt widget tests
  integration/    real subprocesses, faked yt-dlp
  network/        opt-in, real network (excluded by default)
ai/               coordination documents -- start with ai/TASKS.md
docs/             developer and operator documentation
```

## Rules that will bite you

These are enforced by tests and CI, not by review. Read `ARCHITECTURE.md` §4 before moving code
between layers.

- **`core/` must not import Qt.** It runs in headless child processes.
- **`downloader/worker.py` must not import Qt** and must be import-safe under `spawn`.
- **`ui/` must not import `yt_dlp`.** Only `worker.py` and `ytdlp_adapter.py` may.
- **Do not reorder `__main__.py`.** `multiprocessing.freeze_support()` must stay the first
  executable statement, ahead of any Qt import. In a frozen build, removing it makes every
  spawned worker relaunch the entire application (`REL-001`, `T-020`).
- **No `shell=True`.** URLs and titles are attacker-influenced data (`ARCHITECTURE.md` §9).
- yt-dlp is pinned exactly in `pyproject.toml` on purpose (`OPS-002`). Do not float it.

## Qt on a headless machine

UI tests run offscreen. If a Qt test fails to start a display:

```bash
QT_QPA_PLATFORM=offscreen pytest tests/ui
```

CI sets this on both platforms.

## Common problems

| Symptom | Cause and fix |
|---|---|
| `No module named pip` | Fedora ships pip separately: `python3 -m ensurepip --user`. |
| `error: externally-managed-environment` | You are outside the venv. Activate `.venv` first. |
| `qt.qpa.plugin: could not load the Qt platform plugin` | No display. Set `QT_QPA_PLATFORM=offscreen`. |
| `ModuleNotFoundError: tracks_and_trails` | The editable install did not run: `pip install -e ".[dev]"`. |
| mypy passes locally but fails in CI | Run bare `mypy` — it reads paths from `pyproject.toml`. Passing a path overrides them. |
| ffmpeg-related runtime errors | Install ffmpeg. It is not a build dependency, so tests pass without it. |

## Windows

There is currently **no Windows machine available**, so Windows is verified through CI only
(`OPS-003`). Setup there is the same apart from venv activation. If you *do* have a Windows
machine, several things need a human — see `ai/TESTING.md` §9; that list blocks the first
public release.
