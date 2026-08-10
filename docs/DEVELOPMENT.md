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

## Registering a Linux CI runner (`OPS-012`)

Linux CI runs on the maintainer's Fedora machines rather than on hosted images — **faster** as
well as free: 4m29s for the full suite on the desktop against 7m36s for the whole hosted `check`
job. `vars.LINUX_RUNNER` selects it; unset the variable and everything returns to `ubuntu-latest`.

Do this once per machine. Both the desktop and the laptop get **the same labels**, so a job lands
on whichever is free and one machine being asleep does not stop CI.

Prerequisites, checked rather than assumed — on Fedora 44 these are typically already present:

```bash
python3 --version                       # must be 3.14.x
ffmpeg -version | head -1
for lib in libEGL.so.1 libGL.so.1 libxkbcommon.so.0 libdbus-1.so.3 libfontconfig.so.1; do
    ldconfig -p | grep -q "$lib" && echo "$lib ok" || echo "$lib MISSING"
done
# If any are missing:
# sudo dnf install -y mesa-libEGL mesa-libGL libxkbcommon dbus-libs fontconfig
```

Then register. The token comes from **Settings → Actions → Runners → New self-hosted runner** and
expires in an hour:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner

# The asset name carries the version — there is no version-less "latest/download" file, and
# requesting one returns a 9-byte "Not Found" page that tar then rejects as "not in gzip format".
# `-f` is what makes that a failed command rather than a corrupt download.
# No `${}` braces anywhere below, deliberately: a paste that percent-encodes them sends curl a
# literal `$%7BRUNNER_VERSION%7D` and it 404s, while the *next* line expands correctly and names
# a file that was never downloaded. Observed 2026-08-05 on one machine and not the other.
RUNNER_VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
                 | grep -oP '"tag_name": "v\K[^"]+')
echo "runner $RUNNER_VERSION"
curl -fLO https://github.com/actions/runner/releases/download/v$RUNNER_VERSION/actions-runner-linux-x64-$RUNNER_VERSION.tar.gz

# Verify before extracting. The expected digest is published in the release notes.
sha256sum actions-runner-linux-x64-$RUNNER_VERSION.tar.gz

tar xzf actions-runner-linux-x64-$RUNNER_VERSION.tar.gz
```

Then configure. **Mint the registration token inline rather than pasting one.** Registration
tokens expire in an hour and are single-use, so a copied one is usually dead by the second
machine; `gh` needs only the `repo` scope to issue a fresh one:

```bash
./config.sh --url https://github.com/kottmans/tracks-and-trails \
  --token "$(gh api -X POST repos/kottmans/tracks-and-trails/actions/runners/registration-token --jq .token)" \
  --labels self-hosted,linux,fedora \
  --name "$(hostname)" --unattended
sudo ./svc.sh install && sudo ./svc.sh start     # survives reboot
sudo ./svc.sh status
```

Expect `√ Runner successfully added` and `√ Runner connection is good`. The web route —
**Settings → Actions → Runners → New self-hosted runner** — shows the same token inside a
prefilled `./config.sh` line, but hand-copying it is where the expiry and placeholder mistakes
come from.

### Install it under `/opt`, not `/home` — SELinux will refuse otherwise

**Do this before configuring**, or redo it afterwards as below. On Fedora with SELinux enforcing,
a service started from `/home` fails instantly with `status=203/EXEC` and an audit denial:

```
avc: denied { execute } for comm="(runsvc.sh)" name="runsvc.sh"
scontext=system_u:system_r:init_t:s0  tcontext=unconfined_u:object_r:user_home_t:s0
```

The file is executable — `-rwxr-xr-x` — and that is the trap. The permission bits are fine; the
*label* is not. `/home` is `user_home_t`, which systemd is not permitted to execute, by design, so
that a compromised home directory cannot inject service binaries. Both machines hit this on
2026-08-05 and `config.sh` had succeeded on both, so the runners were registered and dead: they
appear in the API as `status=offline`, which reads like a network problem rather than a policy one.

Recovering an already-configured runner, without re-registering — the move does not touch
`.runner` or `.credentials`, so no new token is needed:

```bash
cd ~/actions-runner && sudo ./svc.sh uninstall
sudo mv ~/actions-runner /opt/actions-runner
sudo chown -R "$USER:$USER" /opt/actions-runner

sudo dnf install -y policycoreutils-python-utils            # provides semanage
sudo semanage fcontext -a -t bin_t "/opt/actions-runner(/.*)?"
sudo restorecon -Rv /opt/actions-runner

cd /opt/actions-runner
sudo ./svc.sh install "$USER" && sudo ./svc.sh start && sudo ./svc.sh status
```

**Use `semanage`, not `chcon`.** `chcon -R -t bin_t` fixes it now and is silently reverted by the
next filesystem relabel — CI that breaks months later for no visible reason. `semanage` records
the rule so `restorecon` reapplies it.

Confirm from the API rather than from the local service, since a running service that cannot reach
GitHub still reports `active`:

```bash
gh api repos/kottmans/tracks-and-trails/actions/runners \
  --jq '.runners[] | "\(.name) \(.status)"'
```

**`svc.sh` does not ship in the tarball** — the layout contains `config.sh`, `run.sh` and `env.sh`
only, and `svc.sh` is generated from `systemd.svc.sh.template` by `config.sh`. So `./svc.sh:
command not found` before configuring is expected, and after configuring means `config.sh` did not
complete. Do not go looking for it in the archive.

**The labels are part of the contract**, because `LINUX_RUNNER` names them — and **GitHub rewrites
what you asked for**. It adds `self-hosted`, `X64` and `Linux` itself, folding a requested `linux`
into its own capitalised `Linux`, so both machines above report
`self-hosted,X64,Linux,fedora`. Set the variable from what the API says the runner *has*, not from
what `--labels` requested:

```bash
gh api repos/kottmans/tracks-and-trails/actions/runners \
  --jq '.runners[] | "\(.name) \([.labels[].name]|join(","))"'
```

Finally, point CI at them:

```bash
gh variable set LINUX_RUNNER --body '["self-hosted","Linux","fedora"]'
```

**Do not install the runner into this checkout.** It keeps its own workspace under
`~/actions-runner/_work`; a runner sharing your working tree would check out over your edits.

**Stop the runner before running a soak or any timing measurement on that machine.** A CI job
landing mid-run changes the timing the measurement depends on, and the machine is a runner from the
moment this service starts:

```bash
sudo systemctl stop actions.runner.kottmans-tracks-and-trails.<host>.service
# ... measurement ...
sudo systemctl start actions.runner.kottmans-tracks-and-trails.<host>.service
```

On a laptop, wrap a long unattended run in `systemd-inhibit --what=sleep:idle:handle-lid-switch`
so a closed lid does not end it six hours in, and leave it on mains power — an inhibitor does not
stop a flat battery.

Two things to know once it is live. A self-hosted job with **no online runner queues for up to 24
hours** before GitHub discards it — `timeout-minutes` does not bound that, so both machines asleep
makes CI look hung rather than failed. And no CI job now runs on a machine nobody uses, on either
platform, so `T-066`'s class of finding — CI installing the project differently from the way this
file documents — no longer has anywhere to be caught. `OPS-012` records what that surrenders.

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

## Which `REQ-023` settings the screen actually holds

`REQ-023` names eight settings. **Settings → Settings… holds five** — three from `T-146`, the
ffmpeg location from `T-199`, and the cookie source from `T-197`; the rest are filed and not built,
and the screen says so itself rather than reading as complete.

**A cookie path is the one setting with a decision attached.** `DAT-003` (amended 2026-08-10) puts
it in `settings.toml` and in a worker's arguments and **nowhere else** — never on
`DownloadRequest`, so it cannot reach the queue database. That is why the file is *late-bound*: a
queued job cannot carry it, so it authenticates with whatever is set when its worker starts.
`cookies_from_browser` is the other half and binds when the job is queued, because it is a preset
field.

| Setting | Where it is | Stored as |
|---|---|---|
| Default download directory | Settings screen | `[downloads] directory` |
| Theme (light/dark) | Settings screen | `[appearance] theme` |
| Concurrency limit | Settings screen **and** the toolbar — one value, two controls | `[queue] concurrency` |
| Default preset | not built — `T-195` | `default_preset` (written already by the preset manager) |
| Output template | not built — `T-195` | — |
| ffmpeg location | Settings screen | `[ffmpeg] location` |
| Network options (rate limit, proxy, retries) | not built — `T-196` | — |
| Cookie source | Settings screen | `[cookies] file`, plus `cookies_from_browser` per preset |

**The concurrency control is deliberately in both places** (`T-146`'s recorded choice). Its home is
one value in `settings.toml` and both controls are views of it: composition applies and saves once,
then tells the window, which updates whichever controls exist. Removing the toolbar copy is a
change to the toolbar's composition, which is `T-220`'s open ruling and not this task's to take.

**A bad value reports rather than reverting silently** (`ARC-008`). A download folder that has been
deleted, is a file, or cannot be written to falls back to the platform's downloads folder *and*
says so on startup; a missing one is **not** recreated, because the picker only offers folders that
exist, so its absence means it was deleted or its drive is not mounted.

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
