# Verifying on Windows without a CI runner

**Purpose:** How this project runs its Windows evidence on a real machine, and the traps that
make a run look valid when it is not.
**Owner:** Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-28
**Related:** `ai/TESTING.md` §12, `T-040`, `T-056`, `T-066`…`T-070`, `OPS-003`, `OPS-004`

---

## Why this exists

`OPS-003` recorded that the maintainer has no Windows machine, which made the GitHub runner the
only Windows environment this project had. `ai/TESTING.md` and `.github/workflows/ci.yml` are both
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

`/drive:` maps a local folder to `\\tsclient\linux` inside the session. Copying a file beats
pasting a script into a PowerShell console — a long line that wraps becomes a syntax error, and a
mangled SSH key fails by silently falling back to password auth rather than by erroring.

`tools/windows/ssh-setup.ps1` enables OpenSSH and authorises a key. Run it once, elevated, from
the RDP session.

## The two traps

Both of these produce a run that *looks* fine and is not evidence about the machine.

### 1. SSH lands in session 0, which has no desktop

A process started over SSH has no window station. Qt does not fail there; it **degrades**. The
`offscreen` platform falls back to a font database that needs a font directory, and the real
`windows` plugin cannot even set DPI awareness. Anything touching focus, window handles, or text
metrics is measuring a different thing.

`tools/windows/run-on-starbase.sh` exists for this. It writes the command to a file, triggers a
pre-registered scheduled task created with `/IT` — so it inherits the logged-on session — and
returns the output:

```bash
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
- **A positive control.** `mutations/mut_control_always_dead.py` breaks the helper outright and
  must fail. Without one, "the mutation survived" and "the mutation never applied" look identical
  — which is how a real survival gets misread as a broken harness, and vice versa.

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

**If the machine is off or logged out, the job queues rather than fails.** `timeout-minutes`
bounds that. It is a real trade: this job is now as available as one desktop machine is.

## What CI does differently

Kept here because each row was a failing test before it was understood.

| | GitHub runner | An ordinary Windows desktop |
|---|---|---|
| Elevation | elevated | not elevated → symlink tests skip (`T-070`) |
| `LongPathsEnabled` | `1` | `0`, the default (`T-067`) |
| Install | virtualenv as of `T-066`; none before | virtualenv, per `docs/DEVELOPMENT.md` |
| Process depth | one extra generation under a venv, because `Scripts\python.exe` is a launcher that spawns the real interpreter (`T-066`) | same, now that CI matches |
| Fonts under `offscreen` | populated | **empty** without `QT_QPA_FONTDIR` (`T-068`) |
