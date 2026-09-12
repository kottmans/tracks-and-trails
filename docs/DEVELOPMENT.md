# DEVELOPMENT.md — Tracks & Trails

**Purpose:** Practical developer setup and local workflow.
**Authority:** Canonical for setup steps. **Not** authoritative for validation policy — see `docs/project/TESTING.md`.
**Owner:** Implementer / Documentation Maintainer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-09-08
**Update when:** Setup, dependencies, or the local workflow change.
**Does not contain:** What must be tested or which gates are required (`docs/project/TESTING.md`).

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
runner — how to reach it, and the three traps between you and a trustworthy result. Two make a run
look valid when it is not: SSH lands in session 0 with no desktop, and an SSH session authorised by
`administrators_authorized_keys` runs elevated, which a developer's shell does not. The third
produces no run at all — killing the self-hosted runner orphans its session, and every job then
fails at exactly ten minutes with a message blaming the network.

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

Install the hooks, which is a per-clone step for the same reason (`T-240`):

```bash
tools/install-hooks.sh
```

This points `core.hooksPath` at the version-controlled `.githooks/`, so the hook that runs is the
hook that was reviewed rather than a copy in `.git/hooks` that goes stale. It installs
`commit-msg`, which refuses a message that names an AI tool as an author or omits its `Task:`
trailer — `AGENTS.md` §7 and §13, and the two rules nothing checked until `T-240`.

**It can be skipped with `git commit --no-verify`, and it does not exist until you run the line
above.** That is why the `Commit messages` workflow checks the same two rules over what was pushed:
the hook catches the defect while amending is still free, and CI catches the defect the hook was
never installed to see. Neither is sufficient alone.

Then:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`-e` installs the package in editable mode, so `src/` changes take effect without reinstalling.
`[dev]` adds ruff, mypy, pytest, pytest-qt and pytest-xdist. Add `[build]` when you need
PyInstaller.

**Ruff and mypy are pinned exactly, and re-running the install is how you stay on them**
(`T-269`). They are gates rather than libraries: a different formatter version fails CI on code
your own `ruff format --check` called clean, and that has cost this project a whole Windows
measurement round. Everything else in `[dev]` is a floor, so this line is cheap to repeat — run it
again after a pull that touches `pyproject.toml`, and `pytest tests/unit/test_toolchain_versions.py`
tells you in a second whether your environment matches what the repository declares.

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
pytest                       # default suite, serial
pytest tests/unit            # fast headless loop
pytest -m network            # opt-in; hits real sites
pytest --cov --cov-report=term-missing
```

**The full sweep is two commands, and the split is the point** (`T-123`). This is what CI runs on
Linux and the only parallel shape that has been measured green:

```bash
pytest -n auto tests/unit tests/ui   # 2711 tests — 23 s, against 186 s serial
pytest tests/integration             # 403 tests — 297 s, and serial on purpose
```

**Do not reach for bare `pytest -n auto`.** It runs the whole suite in 78 s and **fails about one
run in six** — measured, not feared. Two hazards live in `tests/integration`: one is fixed (a
stray-reaper that killed other workers' processes) and one is open (`T-228`, a retry deadline that
stops firing under load). Until `T-228` is answered, integration runs serially.

**What makes the parallel half safe is two properties, and both are now enforced rather than
argued.**

**Nothing shared is written.** Every per-user directory — config, data, cache, downloads — is
redirected into the test's own `tmp_path` by an autouse fixture in `tests/conftest.py`, which is
what `docs/project/TESTING.md` §5 has always required. *Before it existed, one `-n auto tests/unit tests/ui`
run left 241 job logs in the developer's real cache*; it is 0 now, and
`tests/unit/test_user_directories.py` re-derives the list of consuming modules from `src/` with
`ast` so a new consumer cannot be missed silently.

**Nothing reaps what it did not start.** `psutil.process_iter` appears nowhere under `tests/unit`
or `tests/ui` — checked, and the narrow claim rather than a count of files that merely mention
`subprocess`. That is the property parallelism actually breaks, and
`tests/integration/test_manager.py` is where it was broken: its reaper must scan the machine,
because a reparented stray is findable no other way, so its marker now carries
`PYTEST_XDIST_WORKER` and a worker can only reap its own.

**The limit worth knowing:** a monkeypatch lives in one interpreter, so a test that *spawns* a
process gives the child the real directories unless it passes explicit paths.
`tests/ui/test_app_launch.py` does exactly that for the application it launches. The fixture is the
in-process half and does not replace it.

Serial and parallel collect the identical 3130 tests, checked by diffing `--collect-only`.
**The Windows jobs stay serial**: `T-056` is an open Windows defect about whether a process is
alive, which is precisely the question parallel load perturbs.

**`-n auto` is not in `addopts`, and that is a choice.** The runs where you want it — the sweep
before calling a change done — are not the runs where you want `-x`, `--pdb` or a readable
traceback, and xdist makes all three worse. Reach for it on the sweep, leave it off in the loop.

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

**These are convenience shortcuts, not policy.** `docs/project/TESTING.md` §3 defines which checks are
*required* for which kind of change, and §8 defines the release gate. When they disagree with
this file, `docs/project/TESTING.md` wins.

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
docs/project/     coordination documents -- start with docs/project/TASKS.md
docs/             developer and operator documentation
packaging/        PyInstaller spec and the frozen smoke test (T-020)
```

## Which `REQ-023` settings the screen actually holds

<!-- req023:table -->
*(The `<!-- req023:… -->` comments in the table below are **read by a test** and are why this
section cannot go stale: `tests/ui/test_settings_records.py` compares them against
`ui/settings_dialog.REQ_023_SETTINGS`, which is what the screen itself is built from. Every word
around them is free prose — the gate reads the markers and nothing else, so rewriting a sentence
cannot break it and cannot fool it either. `T-227`.)*

`REQ-023` names eight settings. **Settings → Settings… holds all eight** — three from `T-146`, the
ffmpeg location from `T-199`, the cookie source from `T-197`, the default preset and output
template from `T-195`, and the network options from `T-196`, which was the last. The screen's own
*"still to come"* sentence is therefore empty and its label is not built; adding a ninth setting to
`REQ-023` without building it puts both back, which is the whole of what that mechanism promises.

**A cookie path is the one setting with a decision attached.** `DAT-003` (amended 2026-08-10) puts
it in `settings.toml` and in a worker's arguments and **nowhere else** — never on
`DownloadRequest`, so it cannot reach the queue database. That is why the file is *late-bound*: a
queued job cannot carry it, so it authenticates with whatever is set when its worker starts.
`cookies_from_browser` is the other half and binds when the job is queued, because it is a preset
field.

**The network options bind at queue time, like everything that is not the cookie file.**
`ARCHITECTURE.md` §8 freezes settings into the `DownloadRequest` when a job is created, and the
proxy, rate limit and retry count all have fields there — so a change reaches downloads added from
then on, and anything already in the queue keeps what it was added with. The screen says so, and
`T-196`'s exceptions to a plain read are worth knowing:

- **Zero retries is a real answer** — *do not retry inside the attempt* — while an absent key means
  yt-dlp's own count. The retry this sets is `--retries`, the **file transfer's** own;
  `--fragment-retries`, which covers the pieces of a segmented stream, is a separate option nothing
  here sets and belongs to `T-183` (`T196-R5`).
- **A stored rate limit outside `RATE_LIMIT_MINIMUM_BYTES..RATE_LIMIT_MAXIMUM_BYTES` is reported**,
  and `0` or a negative is reported and dropped rather than read as *no limit* — it would otherwise
  silently remove a limit somebody asked for. The floor exists because the screen counts whole
  KiB/s: 500 B/s displayed as *No limit* while downloads were capped at it (`T196-R3`).
- **A proxy is never quoted back.** The `ARC-008` reason names the rule, not the value, and the
  literal is registered for redaction only when it is usable or carries userinfo — registering a
  fragment like `http://` makes every URL in the log unreadable (`T196-R2`).
- **The proxy field commits when the edit is finished, never per keystroke.** Typing a credentialed
  proxy passes through prefixes that are valid addresses — `http://alice:12345` is a legal
  `host:port` — and committing those wrote a password to `settings.toml` (`T196-R1`, Critical).

| Setting | Where it is | Stored as |
|---|---|---|
| Default download directory <!-- req023:download-directory built --> | Settings screen | `[downloads] directory` |
| Theme (light/dark) <!-- req023:theme built --> | Settings screen | `[appearance] theme` |
| Concurrency limit <!-- req023:concurrency built --> | Settings screen — the toolbar's copy went with `UX-013` (`T-234`) | `[queue] concurrency` |
| Default preset <!-- req023:default-preset built --> | Settings screen **and** the preset manager — two controls, **one writer** | `default_preset` (bare key, above the first table) |
| Output template <!-- req023:output-template built --> | Settings screen | `output_template` (bare key, above the first table); absent means the shipped template |
| ffmpeg location <!-- req023:ffmpeg-location built --> | Settings screen | `[ffmpeg] location` |
| Network options (rate limit, proxy, retries) <!-- req023:network-options built --> | Settings screen | `[network] proxy`, `rate_limit_bytes` (bytes per second), `retries` |
| Cookie source <!-- req023:cookie-source built --> | Settings screen | `[cookies] file`, plus `cookies_from_browser` per preset |

**The concurrency control is in one place** (`UX-013`, built by `T-234`). Its home is one value in
`settings.toml`, and the Settings screen is the only view of it: composition applies and saves
once, then tells the window, which holds the number so the screen opens on what is running.

*(This paragraph said the control was **deliberately in both places** — `T-146`'s recorded choice,
which kept the toolbar's copy and left removing it to `T-220`'s open ruling. `UX-013` took that
ruling on 2026-08-12 and `T-234` carried it out, so the stopgap and the pending ruling are both
finished. The two-control mechanism it described — composition as the single writer, controls as
views — is unchanged; there is simply one view now.)*

**The default preset is in two places for the same reason, and answered the same way** (`T-195`'s
recorded choice). *Set as default* in the preset manager and the combo on the settings screen both
call `settings.set_default_preset`; **neither keeps a copy**. The screen reads the catalogue and the
current default *when it opens* rather than caching at startup, so a preset made default in the
manager is what the screen shows next. Two controls writing one key is how the two records in
`P3EXIT-R1` came to disagree, so the crossing is proved from the file in both directions rather than
from either screen's state.

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

**`.venv/` is git-ignored and does not survive a clone.** Create it during clone
setup and rebuild it after moving the checkout. The [historical environment record](project/COMPLETED_TASKS.md#t001-environment)
preserves the earlier launcher and import-path repair.

## Windows

Windows is verified on **`STARBASE`**, the maintainer's own machine, which is both an interactive
verification target and a self-hosted runner for the `windows desktop` job (2026-07-28). Setup
there is the same apart from venv activation. `docs/WINDOWS_VERIFICATION.md` is the procedure.
Several things still need a human — see `docs/project/TESTING.md` §9; that list blocks the first public
release.

*(This section said "there is currently no Windows machine available, so Windows is verified
through CI only" while the same file's "Verifying on Windows" section above described running the
suite on exactly such a machine. Corrected under `T-064`.)*

---

## Documentation workflow

Start with README for the product, this guide for local work, ARCHITECTURE and
DECISIONS for design/rationale, TASKS/STATUS for active work, COMPLETED_TASKS for
closed task history, and REVIEWS to find the canonical review records. Those files live in
`docs/project/`. Review policy lives
in [TESTING §14](project/TESTING.md#14-review-policy); launch wording lives in
[TESTING §14](project/TESTING.md#14-review-policy), whose entry template moved there when
`PROMPTS.md` was removed on 2026-09-11. Required ownership and permissions remain in AGENTS.
Use the [review-storage rule](project/TESTING.md#review-records-and-storage) to
choose a new task file or an existing indexed record before starting a review.

When a task becomes Complete or Cancelled, the task/status owner moves its full
record from TASKS to the running [COMPLETED_TASKS](project/COMPLETED_TASKS.md) in
the same update. Preserve its evidence and follow-up links, leave no stub in the
active queue, and run the placement check over both files. Do not create dated
batches. Follow [AGENTS §6](../AGENTS.md#tt-history) for reopening and ownership.
The decision owner updates the amendment index
in the same change. New records describe the problem, cause, correction, checks
and remaining risk; omit fields that add no information. Record review identity
in its provenance field rather than narrating tools in product explanations.

The [standard adoption record](project/DECISIONS.md#doc-007-review-migration) pins
the private shared repository, revision and full source commit. Its README and
release migration notes explain adoption in other projects. When upgrading this
project, compare that pinned revision with the proposed release, apply relevant
changes, verify them, and update the adoption decision. Routine work uses the
project's local rules and does not require access to the shared repository.

Follow [TESTING's captured-evidence controls](project/TESTING.md#captured-evidence-and-formatting)
before formatting a historical instrument. Maintained examples stay checked.

## Parallel work procedure

**Skip this section unless the maintainer has told you that you are in a parallel wave.** It
describes an option, not an expectation: most work on this project is serial (AGENTS.md §7), nothing here
requires a wave, and no task is worse for having been done one at a time.

A **parallel wave** is several agents implementing different tasks at the same time. Only the
maintainer opens one, per wave. An agent does not start one, create its branches, split a task
into workers, or propose a wave in place of doing the task in front of it. Two tasks merely
*being* independent is not a reason to run them concurrently — a wave adds base selection,
write-set assignment, serial integration, and combined verification, and that overhead only pays
off when the tasks are substantial as well as independent.

**A task may join a wave only if all of these hold.** Otherwise sequence it, or land the
shared piece first as its own task:

1. Its dependencies are already integrated at the wave's common base.
2. Its acceptance criteria can be checked without another worker's unfinished code.
3. Its write set does not overlap another active worker's.
4. The interfaces it depends on already exist — no two workers inventing the same seam.
5. `pyproject.toml`, migration sequence numbers, generated assets, and other single-owner
   surfaces are assigned to one worker or deferred to integration.
6. Its runtime resources are isolated (see below).

**Setup — coordinator.** Pick one stable `main` commit as the common base, assign a wave ID
`PW-###`, and per task: branch `task/T-0NN-slug`, its own worktree, exclusive write set,
read-only shared surfaces, runtime allocation, review-record path, integration order. Record
those as fields on the `docs/project/TASKS.md` entry. Do **not** record worktree paths there — they are
machine-specific; the branch and starting commit are the durable identifiers. Start a wave at
two or three workers, not more.

**One branch, one worktree, one writer.**

```bash
BASE="$(git rev-parse main)"
git worktree add -b task/T-042-<slug> ../tracks-and-trails-T-042 "$BASE"
```

Branches alone are not enough: two agents in one checkout share an index and working tree, and
switching a branch or editing the same file destroys the other's uncommitted work. That has
already happened here — a reviewer fell back to `git archive` mid-review because unrelated work
had entered the shared tree. The primary checkout stays on `main` for coordination.

**One worker per machine.** Separate worktrees are not enough either: **do not run concurrent
workers on one host**, even with disjoint write sets. A wave gets its parallelism by putting one
workstream on each machine, each with its own clone. Three reasons specific to this repository:

- **The integration tests that spawn and kill real worker processes contend** — the files are
  listed under *Runtime isolation* below. Two of those suites on one machine produce intermittent
  failures that look like defects in the code under test.
- **`.venv` is an editable install pointing at the primary checkout's `src`**, so a second worktree
  silently tests the *other* agent's code unless every command overrides `PYTHONPATH`. One worker
  per machine removes the trap rather than relying on remembering it.
- **A machine running a measurement is fully committed.** The `T-128` soak (`tools/soak.sh`) runs
  the whole suite sixty times and measures timing; any second workload invalidates it. So does a CI
  job — **a machine registered as a self-hosted runner is not idle**, and its runner service must be
  stopped for the duration or the contention recorded.

**Record which machine produced a measurement** in `docs/project/STATUS.md` or the evidence artifact:
reproducing a timing-dependent result requires knowing the host, and a baseline taken on one
machine does not transfer to another. Host names do not belong in a task entry's durable fields,
for the same reason worktree paths do not.

**Runtime isolation, specific to this repository.**

- `.venv` holds an **editable** install pointing at the primary checkout's `src`, so a second
  worktree silently tests the *other* agent's code. Override it:
  `PYTHONPATH=$PWD/src /path/to/primary/.venv/bin/python -m pytest` (and the same for `mypy`),
  then verify once with
  `python -c "import tracks_and_trails; print(tracks_and_trails.__file__)"`.
- **The integration tests that spawn and kill real worker processes** contend with each other:
  run them in one worktree at a time. They live in `tests/integration/` — `test_manager.py`,
  `test_crash_kill.py`, `test_single_instance.py`, `test_phase_2_exit.py`, `test_composition.py`
  and `test_worker.py`.
  *(This said "`-m process_tree` tests", and **no test carries that marker**: it was retired when
  `T-019` made cancellation reap the whole process group. So the instruction selected nothing and
  could not be followed. Naming the files is worse than a marker and better than a marker that
  does not exist; `T-123` owns identifying them properly, because parallelising the suite needs
  exactly that list.)*
- Qt tests need `QT_QPA_PLATFORM=offscreen`. Every worker's tests must use their own temp,
  database, and config paths — never a shared per-user application directory.

**Write sets are permissions, not predictions.** Needing an unassigned file — a shared module,
`pyproject.toml`, a migration, a generated asset — is a coordination event. Stop that part of
the change and report the scope expansion; do not edit it quietly.

**Shared coordination files are frozen for workers.** During a wave the coordinator is the only
writer of `docs/project/TASKS.md`, `docs/project/STATUS.md`, and the wave-level parts of `docs/project/REVIEWS.md`. Workers
propose those updates in the end-of-task report (AGENTS.md §11).

**Review storage follows TESTING §14 in serial and wave work.** The assigned
reviewer writes the assigned canonical record on the task branch. The
coordinator updates `docs/project/REVIEWS.md` navigation and records combined
verification in its assigned integration record. Follow the
[storage rule](project/TESTING.md#review-records-and-storage), including the
historical migration; severity, blocking, independence and the pass budget apply.

**Approval freezes one exact head.** Approval reads `Approved at <sha>` and covers that
implementation head only. A later commit may advance the branch if its diff is review-only
(the review record, review metadata). Any change to source, tests, build files, dependencies,
generated artifacts, or evidence creates a new implementation head and needs focused re-review
of the changed part before integration.

**Integration is serial.** The coordinator merges approved branches one at a time in dependency
order, resolves conflicts centrally, and runs the relevant checks after each step. A conflict
resolution that changes behavior is new implementation: keep it as a distinct diff and have it
reviewed, rather than burying it in a merge. Workers never merge or rebase a moving `main` into
themselves — that silently moves the review boundary.

**Verify the combined tree, not just the branches.** After the wave, run what `docs/project/TESTING.md`
§3 requires for the *union* of the layers touched. Branch-local green does not prove the merged
result works.

**Clean up last.** Remove worktrees and delete branches only after the integrated commit and
its evidence are secure, and never for a branch holding unique unintegrated work.


## Roadmap maintenance

**The maintainer keeps one roadmap, as a published artifact, for their own reference.** It is
**never committed** — no `roadmap*.html`, no `roadmap*.md`, nothing under `docs/`. Two
were removed from this repository on 2026-08-08 for that reason.

**It is derived, not authoritative.** `docs/project/IMPLEMENTATION_PLAN.md` §Phase *N* and `docs/project/TASKS.md`
§`## Proposed — Phase N` remain canonical; the roadmap is a rendering of them. **Where they
disagree, they are right and it is stale.** Nothing in the repository may cite it, for the reason
handoffs may not be cited: it is not a home.

**Update it — the same artifact, keeping its URL — when:**

- a phase exits or begins,
- a task's disposition changes in a way the phase's shape depends on (approved, blocked, re-phased,
  or newly filed),
- a ruling opens or closes.

**One artifact, updated in place.** Not one per phase: a bookmark that keeps working is the point,
and a graveyard of superseded roadmaps is the thing this rule replaces.

**What it contains**, in this order:

1. **A dependency graph** of the phase's tasks — real edges, not a decorative sequence. Label an
   edge where the *reason* for the dependency is not obvious from the two node names.
2. **The stages**, expanded: each task's one-line substance and the trap in it.
3. **Every plan deliverable mapped to an owning task**, and **every exit criterion mapped** too. A
   deliverable with no owner is the thing this section exists to surface.
4. **Which entries are *not* plan deliverables** — carried-in polish and defects. They must not be
   counted as satisfying one.
5. **Open rulings**, listed separately, each named as the maintainer's to take.

**Diagram legibility is part of the deliverable.** Mermaid in a rendered artifact does not honour
HTML in labels — `<br/>` and `<b>` are stripped, so `T-200<br/>Accessibility` renders as
`T-200Accessibility`. **Use single-line plain-text labels with a visible separator.** Mermaid also
scales an SVG down to its container by default, which shrinks text as the graph grows; set
`useMaxWidth: false` and let the container scroll.


## Commit message format

A commit message is read twice: once as a one-line subject while scanning history, and once in
full while investigating something that broke. The two readings want different things, and the
format below serves each separately rather than compromising between them.

### Shape

```
<subject, imperative, ≤50 chars, no trailing period>
<blank>
<why-paragraph: 1–3 sentences of reasoning that is not recoverable from the diff>
<blank>
- <one discrete change, wrapped at 72>
- <another>
<blank>
Task: T-0NN
```

### Subject — the only line most tools show

- **≤50 characters.** Hard cap 60. This is not stylistic: VSCode's Source Control pane, GitHub's
  commit list and `git log --oneline` in a split terminal all clip around 50, which is why
  history has looked "cut off" despite nothing being truncated in git itself.
- **Imperative mood** — "Add", "Close", "Record", "Fix". It completes the sentence *"Applied,
  this commit will…"*.
- **No trailing period.** No task ID, no `(T-0NN)` suffix, no `feat:`/`fix:` prefix.
- Say what changed in the product's own vocabulary, not the file's. "Bound stored geometry to
  Qt's maximum" beats "Update paths.py".

### Why-paragraph — the part that only you know

One to three sentences on **why**, or what the change means, or what it cost. The diff already
records what changed; it cannot record that a previous fix was itself wrong, or that a test was
passing vacuously, or that a design was chosen over a specific alternative. That is the content
worth keeping.

Skip it only when the subject is genuinely self-explanatory — a typo fix, a status-file pointer
update. A body that merely restates the subject in longer words is worse than no body.

### Bullets — one per discrete change

Bullets, not paragraphs, once there is more than one thing to report. Wrap at 72 columns so the
message stays readable under `git log`'s four-space indent.

**Budget: about 150 words, and at most ~8 bullets.** Past that, the commit is doing too much and
should have been split, or the detail belongs in `docs/project/TASKS.md` where it is indexed and editable.
A commit message is an immutable record, so it is the worst place to put anything that will need
revising.

### Trailers

Machine-readable, last, after a blank line:

| Trailer | Use |
|---|---|
| `Task:` | `T-0NN`, or `T-027..T-032` for a range. Omit only for work no task covers. |
| `Refs:` | Decision or requirement IDs the commit turns on — `ARC-002`, `REQ-011`. |
| `Review:` | Finding IDs closed by this commit — `T034-R5`, `T035-R3`. |

Look-ups stay easy: `git log --grep='Task:.*T-034'`.

**No AI tools as authors or co-authors** — AGENTS.md §7 already governs this, and it applies to trailers
specifically. No `Co-Authored-By:` for an AI tool, no "generated with" footer. The commit history
names the human maintainer only.

### Worked example

Rewriting this repository's longest message (516 words, 8 unstructured paragraphs):

```
Close the Phase 0 exit review findings

Eight findings plus the four that survived the first re-review. The
theme running through them: stored window geometry was treated as
trusted input when it is not, and the first fix was itself incomplete
in a way its own test concealed.

- Bound coordinates to Qt's QWIDGETSIZE_MAX. Validating the four
  numbers individually missed that QRect derives right() as
  x + width - 1, so at y = 2**31 - 1 the bottom edge wrapped negative
  and off-screen recovery never fired.
- Reject bools, inf and nan in load_geometry, whose contract is that
  it never raises.
- Run T-020's frozen negative proof on Windows, not Linux alone.
- Schedule quit from showEvent so the harness never touches Qt from a
  foreign thread.

Task: T-027..T-032
Review: T027-R1..T032-R4
```

Same facts, a third of the words, and a reader looking for one finding can find it.

### Mechanics

`.gitmessage` at the repository root is the template; `git config commit.template .gitmessage`
activates it per clone (it is not set automatically by cloning).

Write the message in an editor or a file, not as a chain of `-m` flags — `-m` encourages
single-line messages and makes wrapping accidental.

## Historical rationale for handoff retention

The following rationale is retained from `f465688`. Current instructions are in
[AGENTS §6](../AGENTS.md#tt-history); this passage is historical context.

### Handoffs are messages, not records — and are never committed

**A handoff is one agent talking to another.** It asks for a review, or carries a correction back.

**It is never committed.** `docs/project/handoffs/` is in `.gitignore`. A handoff may exist as a local
untracked file so a reviewer working in this checkout can read it, and it may equally be delivered
to the maintainer as text to paste — **both are fine; a commit is not.** Once its verdict is in
`docs/project/REVIEWS.md` the message has done its job, and what is durable is the verdict and the task entry.

*(This first read "transient, deleted once its verdict is recorded", which still put 64 of them in
the history. The maintainer's rule is narrower and simpler: **not in the repository at all.**)*

**Durable records cite commits, never handoffs.** A commit SHA identifies a tree that still exists;
a handoff filename identifies a message that is supposed to stop existing. If a record needs a fact
that appeared in a handoff — what was claimed, what a Planner recommended, what a submission got
wrong — **it states the fact.** Writing *"see `docs/project/handoffs/…`"* means the record has not recorded
the thing.

**This was a real defect, found 2026-08-09.** Sixty-four handoffs had accumulated in nine days, and
nine were cited from durable records. **Not one citation carried content** — every one was
provenance a SHA already supplied, a bare pointer, or a description of a past event. One cited a
handoff in order to say it was *not* part of the reviewed boundary. A durable record that delegates
its content to a file scheduled for deletion is a document whose truth lives somewhere it does not
control, which is the same failure as a stale current-truth claim.

**Historical records keep their references, and that is not an exception to the rule.** This section
binds **current-truth** files, which are rewritten to reflect reality. `REVIEWS.md` and
`DECISIONS.md` are append-only above, and *"a review was requested in `docs/project/handoffs/X`"* stays true
after `X` is deleted — it is a statement about the past, not a live pointer. **Rewriting them to
remove a reference would be the larger error.** So a deleted handoff may leave a name behind in
history; what it must not leave behind is a current-truth file that cannot answer its own question.
