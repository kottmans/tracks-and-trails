# Verifying on Windows without a CI runner

**Purpose:** How this project runs its Windows evidence on a real machine, and the traps that
make a run look valid when it is not.
**Owner:** Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-28
**Related:** `docs/project/TESTING.md` §12, `T-040`, `T-056`, `T-066`…`T-070`, `OPS-003`, `OPS-004`

---

## Why this exists

`OPS-003` recorded that the maintainer has no Windows machine, which made the GitHub runner the
only Windows environment this project had. `docs/project/TESTING.md` and `.github/workflows/ci.yml` are both
written around that fact.

It stopped being true on 2026-07-28, and the first run on a machine that is not a runner produced
five findings in one afternoon — `T-066` through `T-070`. The lesson worth keeping is not any one
of them:

> **CI is one Windows configuration, and it is an unusual one.** The runners are elevated, have
> long paths enabled, and install without a virtualenv. A developer's machine is typically none of
> those things, and every difference showed up as a test that passed on CI and failed on a desk.

## The machine

`STARBASE`, on the maintainer's local network. Windows 10 22H2, Python 3.14.6 (MSC v.1944) and
PySide6 6.11.1 — the same versions the runners report, which is what makes a difference in results
attributable to configuration rather than to versions.

Two checkouts live on it, deliberately:

| Path | Installed | Stands for |
|---|---|---|
| `C:\dev\tracks-and-trails` | virtualenv | what `docs/DEVELOPMENT.md` tells a developer to do |
| `C:\dev\tt-ci` | no virtualenv | what CI did before `T-066` |

Keeping both is what turned "STARBASE differs from CI" into an A/B that says *which* differences
are the virtualenv's. It is worth the two minutes it costs.

## Getting in

```bash
xfreerdp /v:<address> /u:<user> +clipboard /dynamic-resolution /cert:ignore \
         /drive:linux,/home/<you>/starbase-share
```

**`<address>` is the mDNS name, not an address you remember.** The machine takes its address from
DHCP, so a reboot can move it — measured 2026-09-11, when it came back on a different one and the
address from the last session simply did not answer. `getent hosts <name>.local` resolves it, and
`<name>.local` in the command survives the next reassignment. The account and the address stay out
of this file for the reason `tools/windows/run-on-starbase.sh` records: a public repository should
carry neither.

`/drive:` maps a local folder to `\\tsclient\linux` inside the session. Copying a file beats
pasting a script into a PowerShell console — a long line that wraps becomes a syntax error, and a
mangled SSH key fails by silently falling back to password auth rather than by erroring.

`tools/windows/ssh-setup.ps1` enables OpenSSH and authorises a key. Run it once, elevated, from
the RDP session.

## The three traps

The first two produce a run that *looks* fine and is not evidence about the machine. The third
produces no run at all, and blames the network for it.

### 1. SSH lands in session 0, which has no desktop

A process started over SSH has no window station. Qt does not fail there; it **degrades**. The
`offscreen` platform falls back to a font database that needs a font directory, and the real
`windows` plugin cannot even set DPI awareness. Anything touching focus, window handles, or text
metrics is measuring a different thing.

`tools/windows/run-on-starbase.sh` exists for this. It writes the command to a file, triggers a
pre-registered scheduled task created with `/IT` — so it inherits the logged-on session — and
returns the output. It takes the machine from `STARBASE_HOST` and refuses to run without it —
there is no default account or address in the script:

```bash
export STARBASE_HOST=user@windows-host      # once per shell
tools/windows/run-on-starbase.sh 'cd C:\dev\tracks-and-trails && .venv\Scripts\python.exe -m pytest -q'
```

Register the task once, from the RDP session or over SSH:

```
schtasks /create /tn ttjob /tr "C:\dev\interactive\run.cmd" /sc once /st 23:59 /it /f
```

Confirm it worked by asking which session you are in. **It must not be 0.**

```bash
tools/windows/run-on-starbase.sh 'powershell -NoProfile -Command "(Get-Process -Id $PID).SessionId"'
```

The same reasoning applies to a self-hosted GitHub Actions runner, and more sharply: install it as
a Windows **service** and it runs in session 0, where the focus tests pass while proving nothing.
Start it with `run.cmd` from a logged-on session instead.

### 2. SSH with `administrators_authorized_keys` runs *elevated*

That is not what a developer's shell is. Elevation changes results:

- **Symlinks.** Creating one needs `SeCreateSymbolicLinkPrivilege` or Developer Mode. Four tests
  failed as an ordinary user and passed elevated (`T-070`). They now skip with a reason.
- **Temp directories.** An elevated run creates `pytest-of-<user>` with an ACL the unelevated
  session cannot use, and the next run fails with `PermissionError: [WinError 5]` on 499 tests.
  If that happens, delete `%LOCALAPPDATA%\Temp\pytest-of-<user>` and the `.pytest_cache`
  directories and re-run.

Prefer the scheduled-task route for anything you intend to record as evidence.

### 3. Killing the runner orphans its session, and every job then fails at ten minutes

**Measured 2026-09-11**, at the cost of an hour. The symptom is a self-hosted job that fails with

> *"The self-hosted runner lost communication with the server. Verify the machine is running and
> has a healthy network connection."*

and the message sends you to the network, which is fine. What is actually wrong is that GitHub
still holds a **session** for a runner process that no longer exists, so jobs are dispatched into
it and no worker ever starts.

**How to tell it apart from a real fault**, without guessing:

| Evidence | What a dead session looks like |
|---|---|
| Job duration | **Exactly 10:00**, repeatably. Two jobs failed at 10:01 and 10:00 |
| `steps` on the job record | Empty, and no logs — `gh run view --job <id> --log` answers *log not found* |
| Newest `C:\actions-runner\_diag\Worker_*.log` | Older than the job. **No worker launched at all** |
| `Runner_*.log` | `Cancel running worker right away` naming the *previous* job each time, and `renewjob … HTTP Status: NotFound` |

A real test failure has none of those: it has steps, logs, and a worker log written while the job
ran.

**Stop the runner with Ctrl-C in its own console.** `Stop-Process` does not release the session,
and the next `run.cmd` answers *"A session for this runner already exists"* with
`Runner connect error: Error: Conflict. Retrying until reconnected.` That is the right behaviour
and it clears itself — the orphan expired in **two and a half minutes** here. Do not kill it again
to hurry it along; each kill makes another orphan. A reboot has the same effect as a kill, which
is why this surfaces after one.

**It is not a service, deliberately** — see trap 1 — so nothing restarts it for you, and there is
no `Restart-Service` to reach for. `Get-Service actions.runner.*` returning nothing is the
expected state here, not a fault.

## Running the suites

```bash
# Full default suite, virtualenv checkout, interactive session
tools/windows/run-on-starbase.sh 'cd C:\dev\tracks-and-trails && .venv\Scripts\python.exe -m pytest -q'

# The desktop suite needs the real plugin and a desktop; the marker is load-bearing
tools/windows/run-on-starbase.sh 'cd C:\dev\tracks-and-trails && set "QT_QPA_PLATFORM=windows" && .venv\Scripts\python.exe -m pytest -q -m windows_desktop'
```

Note `set "VAR=value"` with the quotes **inside**. `set VAR=value && ...` in `cmd` includes the
trailing space in the value, and `QT_QPA_PLATFORM=offscreen ` (with a space) is not a plugin name.

## Running the T-026 mutations

`T-026` requires that reordering two widgets fails the focus tests, and that a focusable control
added without being declared fails them. `tools/windows/mutations/run_mutations.py` executes both
classes plus a control, from the repository root, in the desktop session:

```bash
tools/windows/run-on-starbase.sh 'cd C:\dev\tracks-and-trails && .venv\Scripts\python.exe C:\dev\mutations\run_mutations.py'
```

Each mutation is a **pytest plugin**, not a source edit, so a failed run cannot leave a
half-mutated checkout behind.

Two things it does that are easy to leave out, and that make the difference between a result and a
table of numbers:

- **Only pytest exit code 1 counts as a kill.** Any other non-zero code is reported as
  `NO RESULT`. The first version of this driver treated every non-zero exit as a kill and, having
  forgotten to pass its environment to the subprocess, reported three clean kills from runs that
  had executed no tests at all.
- **A positive control, run first.** `mutations/mut_control_chain.py` makes `focus_chain()` return
  nothing, which must fail the focus tests. Without one, "the mutation survived" and "the mutation
  never applied" look identical — which is how a real survival gets misread as a broken harness,
  and vice versa. It runs before the mutations for that reason: if the control does not fail, no
  verdict after it means anything.

  *(This named `mut_control_always_dead.py`, which is `T-056`'s control for `still_running` and
  has nothing to do with the `T-026` focus harness. Corrected under `WIN-R3`; keep the `T-056`
  control in the `T-056` procedure rather than presenting it as `T-026` evidence.)*

## The self-hosted runner

`STARBASE` runs the `windows desktop` CI job as of 2026-07-28. Self-hosted minutes are not
billed, so that job survives the Actions quota running out — which is what took it away in the
first place.

Setup, once:

```powershell
# in C:\actions-runner, from an elevated shell
config.cmd --unattended --replace --url https://github.com/<owner>/<repo> `
           --token <registration token> --name STARBASE --labels desktop --work _work
```

Get the token with `gh api -X POST /repos/<owner>/<repo>/actions/runners/registration-token -q .token`.
It expires in an hour.

**Start it with `run.cmd` from a logged-on session. Never install it as a Windows service.** A
service runs in session 0, and every focus test in that job would pass while proving nothing. A
scheduled task registered `/sc onlogon /it /rl highest` gives an interactive *and* elevated
session, which is the combination that matters:

```
schtasks /create /tn ghrunner /tr "C:\actions-runner\run.cmd" /sc onlogon /rl highest /it /f
schtasks /run /tn ghrunner
```

Elevation is deliberate — GitHub-hosted runners are elevated, so matching it keeps the symlink
tests `T-070` made conditional actually running here rather than skipping.

Verify both properties rather than assuming them:

```bash
# must report Session#2 (or any non-zero), not 0
ssh <host> 'tasklist /FI "IMAGENAME eq Runner.Listener.exe" /FO LIST'
# must report online
gh api /repos/<owner>/<repo>/actions/runners -q '.runners[] | "\(.name) \(.status)"'
```

A `.env` file in the runner root points `TEMP`/`TMP` at `C:\actions-runner\_temp`. Without it,
the elevated runner and an unelevated manual run share `%LOCALAPPDATA%\Temp\pytest-of-<user>`,
and whichever comes second fails with `PermissionError: [WinError 5]` on hundreds of tests.

### A self-hosted runner is a machine, not a container

This is the trap that cost the most, and it is not obvious from GitHub's documentation, because
their runners make it invisible: **a hosted runner is discarded after every job, so an action that
installs software is free. This one is a computer somebody uses.**

The first run of the `windows desktop` job on `STARBASE` included `actions/setup-python@v7`. On a
hosted runner that is silent and unattended. Here it downloaded `python-3.14.6-amd64.exe`, found
the machine's existing 3.14.6, and opened an **interactive Modify/Repair dialog** — then
deadlocked against `msiexec` in session 0. Three installer processes sat in session 2 with
unchanging memory for the full 15-minute timeout, with no window visible on the desktop, and left
`C:\Users\<user>\AppData\Local\Programs\Python\Python314` without its `python.exe` while
`Lib`, `Scripts` and `DLLs` remained. The virtualenv then could not start at all: its launcher
resolves the base interpreter by absolute path.

Recovery was `taskkill /F /IM msiexec.exe`, then
`winget install --id Python.Python.3.14 -e --force`, then confirming the venv resolved again.

**So the job installs nothing.** It uses the Python already on the machine and asserts the version
it needs, failing loudly if that is wrong. Provisioning is a setup step a human does once, not a
side effect of running a test. Before adding any action to a self-hosted job, ask what it writes
outside the workspace.

### Three things that had to be fixed before a job would run

Recorded because each looks like a broken machine and is not.

1. **`schtasks /run` is a silent no-op on a task already marked running.** Killing the runner's
   worker externally leaves the task in that state, and the runner then sits `offline busy=true`
   while jobs report zero steps until they time out. `schtasks /end /tn ghrunner` first, then
   `/run`.
2. **`bash` must be on `PATH`.** The workflow sets `shell: bash` for every step and hosted Windows
   runners ship Git Bash. A `winget install Git.Git` leaves `C:\Program Files\Git\bin` off
   `PATH`, and the job fails with `bash: command not found` before any step of yours runs. Add it
   to the user environment and restart the runner so it inherits the change.
3. **The runner inherits its environment at start.** Anything you change afterwards — `PATH`, a
   reinstalled interpreter — needs a listener restart to take effect.

**If the machine is off or logged out, the job queues rather than fails — for up to 24 hours.**
`timeout-minutes` does **not** bound this. It caps how long a job may *run* after a runner picks
it up; a self-hosted job that no runner ever matches stays queued for about a day before GitHub
discards it. See GitHub's
[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idtimeout-minutes)
and [self-hosted routing](https://docs.github.com/en/actions/reference/runners/self-hosted-runners#routing-precedence-for-self-hosted-runners).

It is a real trade: this job is now as available as one desktop machine is, and its failure mode
when that machine is unreachable is a day-long hang rather than a prompt red.

*(This said `timeout-minutes` bounded the queue wait. It does not, and the difference is 15
minutes against 24 hours. Corrected under `RUNNER-R1`.)*

## What CI does differently

Kept here because each row was a failing test before it was understood.

| | GitHub runner | An ordinary Windows desktop |
|---|---|---|
| Elevation | elevated | not elevated → symlink tests skip (`T-070`) |
| `LongPathsEnabled` | `1` | `0`, the default (`T-067`) |
| Install | virtualenv as of `T-066`; none before | virtualenv, per `docs/DEVELOPMENT.md` |
| Process depth | one extra generation under a venv, because `Scripts\python.exe` is a launcher that spawns the real interpreter (`T-066`) | same, now that CI matches |
| Fonts under `offscreen` | populated | **empty** without `QT_QPA_FONTDIR` (`T-068`) |

---

## Crash dump capture (`T-092`)

**Status: prepared, not armed.** Everything below is committed and ready; nobody has run it on
`STARBASE`, and until somebody does, `T-092`'s acceptance criteria are **unmet** — see its task
entry. The maintainer consented to this on 2026-08-01; what is missing is the machine, not the
permission.

### Why

`T-074`'s second acceptance criterion is that the faulting thread **and the object it touched** are
identified: *a stack is not a cause*. On the single recorded access violation, `faulthandler`
printed `[ResultPump]` and `Thread-50 (_monitor)` and named neither the faulting module nor the
address. `OPS-007` accepted that crash as residual risk on 361 attempts without a reproduction, and
`T-092` is the instrument that makes the *next* one answerable rather than another anecdote.

It buys nothing until then. That is the point of arming it in advance.

### Arming it

```powershell
# From the repository root, in a normal (non-elevated) PowerShell:
.\tools\windows\crash-dumps.ps1
```

`HKCU`, so it applies to the current user and needs no elevation, and it is scoped to `python.exe`
rather than to every process on the machine.

### Proving it — do not skip this

The registry keys are **not** the evidence. `T-092`'s first criterion is a deliberately crashed
process leaving a dump at a known path:

```powershell
python -c "import ctypes; ctypes.string_at(0)"
dir $env:LOCALAPPDATA\CrashDumps\tracks-and-trails
```

A `.dmp` file must appear. If none does, the configuration has failed at the thing it exists for,
and that must be recorded as a failure rather than the keys being reported as success.

Then open it (WinDbg, or Visual Studio) and confirm it names a **faulting module and address**. A
dump that cannot is `T-092` failing its second criterion.

### What it costs

| | |
|---|---|
| Dump type | **Full** (`DumpType 2`) |
| Size each | roughly 300–600 MB for a Python process with Qt loaded |
| Kept | 5 by default, so **up to ~3 GB** |
| Location | `%LOCALAPPDATA%\CrashDumps\tracks-and-trails` |

A *mini* dump is a few megabytes and routinely lacks the heap the faulting address points into,
which is exactly the question being asked — so the size is the price of an answer, not waste. Lower
`-DumpCount 2` if the disk is tight.

### Undoing it

```powershell
.\tools\windows\crash-dumps.ps1 -Remove
```

Dumps already written are left behind deliberately; delete them yourself when the investigation is
over.

### What CI does with them — metadata only

**No dump is ever uploaded** (`T092-R1`). Both `STARBASE` jobs write `reports/crashdumps.txt`
naming any dump written **during that run**, with its size and timestamp, and leave the dump on the
machine for you to fetch deliberately.

Three reasons, and the first version of this got all three wrong:

- **WER is keyed by executable *file name*.** `python.exe` is every Python process under your
  account, not this project. A dump here is *not by itself evidence of `T-074`* and the report says
  so in as many words.
- **Stale dumps destroy attribution.** The folder persists, so an upload with no time filter would
  re-upload the deliberate proof dump on every later run and announce a recurrence that never
  happened. The jobs stamp their start time and report only what was written after it.
- **A full memory dump can carry another program's heap**, and a CI artifact is a copy of it
  somewhere else. Metadata leaves the machine; the dump does not.

Both steps are `if: always()` and `continue-on-error: true`: **no dump is the normal case and must
never redden the gate.** A job that finds nothing says so and stays green.

If you want dumps narrowed to this project, copy the interpreter to a distinct file name and point
WER at that. Noted rather than done — it changes how the suite is launched.
