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

## Verifying on Windows

`docs/WINDOWS_VERIFICATION.md` covers running the suite on a real Windows machine rather than a CI
runner — how to reach it, and the two traps that make a run look valid when it is not (SSH lands
in session 0 with no desktop; an SSH session authorised by `administrators_authorized_keys` runs
elevated, which a developer's shell does not).

Worth reading before trusting any Windows result: the runners are elevated, have long paths
enabled, and until `T-066` installed without a virtualenv. Every one of those differences was a
test that passed on CI and failed on a desk.

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
python -m tracks_and_trails --version    # prints the version, exits 0, needs no display
python -m tracks_and_trails              # opens the application window
```

The window is the Phase 0 shell (`T-007`): a title, the app icon, and File → Quit plus
Help → About. It remembers its size and position, and nothing downloads yet.

On a machine with no display, use `QT_QPA_PLATFORM=offscreen` — `--version` and `--help` work
without one either way, because they are handled before Qt is imported.

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

Building the frozen artifact, which CI does on both platforms every run (`T-020`):

```bash
python -m pip install -e ".[dev,build]"
cd packaging && pyinstaller --noconfirm --clean \
    --distpath ../dist --workpath ../build tracks-and-trails.spec && cd ..
python packaging/frozen_smoke.py dist/tracks-and-trails
```

The smoke test asserts the frozen build spawns a child without relaunching itself. It is a
Phase 0 build for that check only — not the release build, which is Phase 5.

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
  _freeze_probe.py  T-020's frozen-build self-test; not a layer
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
packaging/        PyInstaller spec and the frozen smoke test (T-020)
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
| `ModuleNotFoundError: tracks_and_trails` | The editable install did not run, **or it ran from a different directory** — see below. |
| `.venv/bin/tracks-and-trails: bad interpreter` | Same cause. The console script hard-codes the interpreter path it was installed with. |
| ffmpeg missing and a download refuses before starting | Expected: `REQ-024` refuses a *merge* it cannot perform, before spending bandwidth. A download needing no merge proceeds (`T-061`). |
| mypy passes locally but fails in CI | Run bare `mypy` — it reads paths from `pyproject.toml`. Passing a path overrides them. |
| ffmpeg-related runtime errors | Install ffmpeg. It is not a build dependency, and the suite passes without it. |

### An editable install remembers where it was run

**Both faults above have one cause and one fix** (`T-063`). An editable install records absolute
paths in two places — a `.pth` under `site-packages` naming the source tree, and a shebang in each
console script naming the interpreter — and neither follows the venv if the checkout moves, is
cloned to a second path, or was installed from a parent directory by mistake.

The symptom is a venv that looks healthy and cannot run the thing it installed:

```
$ .venv/bin/tracks-and-trails --version
bad interpreter: .../tracks-and-trails/.venv/bin/python: No such file or directory

$ .venv/bin/python -m tracks_and_trails --version
No module named tracks_and_trails
```

**Fix: recreate the venv from the checkout you actually work in** (`T-064`).

```bash
cd /path/to/your/tracks-and-trails      # the directory containing pyproject.toml
python3 -m venv --clear .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"      # add ,build for PyInstaller
```

**Reinstalling this project alone is not enough, and that is the trap.** It rewrites *our*
`.pth` and *our* console script, so the application starts and the fault looks fixed — while
every launcher installed by a dependency still names the old interpreter. After a move this
checkout had **45 of 46** launchers stale, `mypy` and `pytest` among them, with
`tracks-and-trails` the only healthy one. The documented bare commands keep failing for a reason
the application's own success actively hides. `--clear` is what rewrites all of them.

Then check the entry points and the tools, because they fail independently:

```bash
.venv/bin/tracks-and-trails --version           # exercises the shebang
.venv/bin/python -m tracks_and_trails --version # exercises the .pth
.venv/bin/python -c "import tracks_and_trails; print(tracks_and_trails.__file__)"
.venv/bin/mypy --version                        # a dependency-owned launcher
.venv/bin/pytest --version                      # the other one you will reach for first
```

The third command is the one worth keeping: it prints which tree is actually imported, and a venv
pointing at the *wrong* checkout will happily import someone else's code and pass tests against it.

`PYTHONPATH=$PWD/src` makes the symptom go away without fixing it, which is worth knowing and
worth not settling for — under that workaround the console script stays broken and the imported
tree is still whatever the `.pth` says.

**`.venv/` is git-ignored and does not survive a clone.** `ai/STATUS.md` records it being missing
twice already, so this is a recurring first-five-minutes problem rather than a one-off.

## Windows

Windows is verified on **`STARBASE`**, the maintainer's own machine, which is both an interactive
verification target and a self-hosted runner for the `windows desktop` job (2026-07-28). Setup
there is the same apart from venv activation. `docs/WINDOWS_VERIFICATION.md` is the procedure.
Several things still need a human — see `ai/TESTING.md` §9; that list blocks the first public
release.

*(This section said "there is currently no Windows machine available, so Windows is verified
through CI only" while the same file's "Verifying on Windows" section above described running the
suite on exactly such a machine. Corrected under `T-064`.)*
