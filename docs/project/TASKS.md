# TASKS.md — Tracks & Trails

**Purpose:** Unfinished work: review, ready, proposed and blocked tasks.
**Owner:** Planner (priorities); Implementer (task/status); Reviewer (review disposition)
**Last updated:** 2026-09-08
**Update when:** Work starts, changes scope/status, closes or reopens.

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
Complete and Cancelled records live in [COMPLETED_TASKS](COMPLETED_TASKS.md).
Move each record there in the same update that closes it; keep no closed-task
stubs here. Preserve IDs, evidence, limitations and follow-up routes. Check both
files before allocating an ID; IDs are never reused. Task-reading tests and
the placement gate read both files. Current phase and blockers are in [STATUS](STATUS.md).

## In Review

### T-325 — Cold start, measured on the artifact that ships

**Status:** **In Review** — `T325-R1` corrected, and **`T325-R2` settled by the maintainer's ruling
of 2026-09-13**: `0.1.0` ships on the startup numbers already measured, recorded as
[`REL-008`'s amendment](DECISIONS.md#amended-2026-09-13--0-1-0-ships-on-the-startup-numbers-already-measured)
with the gaps it accepts — no Linux cold sample, and a Windows cold figure that names no artifact.
*(Was In Progress: neither requirement shown met, pending reboots.)* *(Said `NFR-002` "is met with
roughly 5× margin" and that every measurement clears `NFR-010` — claims about cold starts made from
warm and first-touch numbers, and one unidentified build.)* Filed 2026-09-11 with the Phase 5 plan.

#### 2026-09-12 — the numbers, and the one that is over the bound

Full captures in
[`evidence/2026-09-12-T325-startup-times.md`](evidence/2026-09-12-T325-startup-times.md).

| | cold (after reboot) | first run (fresh build) | warm median | `NFR-002` |
|---|---|---|---|---|
| Linux AppImage, reference machine | not taken | 1.077 s | **0.634 s** | within |
| Windows release build, `STARBASE` | **3.976 s** | **3.780** / **4.656 s** | **1.550 s** | **not met** |

**The cold number is the maintainer's own measurement**, taken seconds after `Restart-Computer`
and before anything else was launched — the one run neither the implementer nor CI can take, since
a reboot kills the runner and the session driving it. One run by construction: a second launch is
no longer cold.

**Instrumented, not timed by hand**, which the scope asks for in terms. `core.startup
.record_first_paint` writes one wall-clock line when the compositor confirms the surface is on
screen; `tools/startup_time.py` takes the other half of the clock before spawning. **`showEvent` is
deliberately not the hook** — it fires before the window exists on screen, and on Wayland the
widget is never told at all (`T287-R1`), so this rides the exposure watch that finding installed
rather than inventing a second notion of *visible*.

**The instrument was checked against a positive before it was trusted**: 0.318 s from source. Its
first run against an artifact reported *no window after 60s*, which was an AppImage built four
hours before the recorder existed — the harness reporting an absent instrument rather than a fast
start, which is the behaviour wanted.

**The finding: the first launch of a freshly written Windows artifact does not meet `NFR-002`, and
it reproduces.** Two independent builds, 3.780 s and 4.656 s, both over 3 s. A second pass over the
*same* files minutes later has no outlier at all — so this is a first-touch cost, not variance.
Defender scanning a newly written 155 MB tree and a cold page cache are the candidates and
**neither was isolated**; naming one would be a guess.

**That is the state a user's machine is in immediately after the installer writes the files**, which
is why it is reported as the headline rather than as an outlier next to a passing median. Linux
shows the same shape — 1.077 s against 0.634 s, a comparable ~1.7× — and stays well inside the
bound.

**Cold, as the scope defines it, was not measured.** *First launch after a reboot* needs a reboot,
which kills the `STARBASE` runner, and on Linux additionally `drop_caches`, which needs root.
Neither is the implementer's to do on a machine somebody is using.

**The freeze costs about 1.9×, against the 2–4× the Risk line anticipated** — 0.33 s from source
against 0.634 s frozen on Linux. Real in direction, immaterial in absolute terms.

**The harness mislabelled that run, and the fix is recorded because the label matters.** It
printed *"measuring warm launches"* unconditionally — over the cold number the task had been
waiting for. A tool cannot tell cold from warm; only the caller knows what state the machine is
in. `tools/startup_time.py` now takes `--cold` and says which it was told, rather than asserting
the one it cannot know.

#### 2026-09-12 (final) — the ruling, and a correction to this entry

**This entry said `NFR-002` was not met. That overstated it, and the overstatement is the finding.**
`NFR-002` reads *"under 3 seconds on the reference **Linux** machine"* — it has never covered
Windows. `TESTING.md` §8 item 14 said *"the reference machine"*, dropping the word, and a Windows
figure was duly reported against a Linux requirement as a failure. **Linux passes with about five
times the margin.** The defect was a gate item disagreeing with the requirement it cites, which is
the class this project keeps finding — and this time in a document rather than in code.

**Ruled by the maintainer 2026-09-12**, recorded as `REL-008`:

| | number | measured | verdict |
|---|---|---|---|
| Linux, `NFR-002` (unchanged) | 3 s | 0.634 s warm, 1.077 s first-touch | ~~met~~ **not shown** — no cold sample (`T325-R2`) |
| Windows, `NFR-010` (new) | **5 s** | **3.976 s cold**, 4.656 s worst first launch | ~~met~~ **not shown** — the cold run names no artifact (`T325-R2`) |

**Five seconds rather than four, from the measurements**: 4 s clears the cold figure by 24 ms,
which is a coin toss on a busy machine rather than a bound. §8 item 14 now names both platforms and
is executable — `tools/startup_time.py --cold`.

**One measurement is still missing and is not inferred away**: Linux cold, which needs a reboot of
the machine doing the work. The margin makes it unlikely to matter; that is an inference, written
as one.

**The rejected alternatives, for the record** — none of them the implementer's to pick:

| Option | What it costs |
|---|---|
| **Amend `NFR-002`** to a warm-start bound, stating the cold figure beside it | It is a change of requirement rather than a reading of one — the requirement says cold |
| **Raise the number** — 4 s covers every measurement taken, 5 s leaves margin on a slower machine | Honest, and the release gate then passes on a number somebody chose |
| **Attack the cost** | Mostly not ours: a Defender exclusion is not something an artifact can arrange for itself, and 155 MB is what bundling ffmpeg costs. **A one-file build would make it worse**, not better — it trades startup for extraction |

**§8 item 14 no longer reads as a pass on an untested claim**, which was the one outcome ruled out
from the start: it names the platform, the artifact and the launch, and points at the tool.
**Owner:** Implementer measures; Maintainer's machine is the reference
**Priority:** High — it is a release-gate item with a number in it
**Phase:** Phase 5
**Depends on:** `T-319`, `T-321`, `T-322` (an installed Windows build and an AppImage to time)
**Relevant context:** `NFR-002` (*"cold start to interactive window under 3 seconds on the
reference Linux machine"*); `TESTING.md` §8 item 14; `T-007`, which measured this **from source**
on 2026-07-25 and is the only recorded number
**Affected surfaces:** `docs/project/evidence/`, `docs/project/TESTING.md` §8
**Risk:** Low to measure; Medium if it fails — a frozen one-dir build pays for import-time
unpacking that a source checkout does not, and PyInstaller one-dir launches are commonly 2–4×
slower than the same code from a venv

#### Scope

`T-007`'s measurement predates freezing, `OPS-002`'s yt-dlp bundling, the thumbnail store, the
theme and the settings dialog. **It is not evidence about the artifact.** Measure again:

- **Cold**: first launch after a reboot (Linux: additionally `echo 3 > drop_caches` before the
  launch), timed from process start to the main window's first paint — instrumented by an
  environment-gated timestamp the application already has the shape for (`_freeze_probe`'s
  `record_app_start`), not by a stopwatch
- **Warm**: the second launch, recorded as a second number rather than averaged in
- Five runs each, on the reference Linux machine for the AppImage and on `STARBASE` for the
  installed Windows build; the median is the number, the five are retained

**If it fails, that is a task, not a re-measure** — `NFR-002` is a requirement, and the honest
outcomes are *meets*, *does not meet and here is the profile*, or a maintainer amendment of the
number with the reason.

#### 2026-09-13 — the review's two findings

**`T325-R1`: the cold gate averaged warm launches.** `--cold` still ran five launches and gated
their median, but only the first launch after a reboot is cold. The reviewer's counterexample —
`[6, 1, 1, 1, 1]` against a 5-second bound — printed *"cold median 1.000s"* and exited 0. Under
`--cold` the tool now gates **the first launch alone** and reports the rest as warm, ungated.
`test_the_cold_gate_judges_the_cold_launch_alone` runs the real CLI with substituted durations over
four cases, the reviewer's first; the previous tool fails two of them.

**`T325-R2`: the evidence does not support "met", so the claims are withdrawn rather than argued.**
The verdict column above and this entry's status are corrected in place, with the old wording
kept. What is owed, and needs the maintainer because each needs a reboot of a machine they use:

- **Linux cold**: reboot the reference Linux machine, then the AppImage by path and digest,
  `tools/startup_time.py <AppImage> --cold --runs 1`.
- **Windows cold on the installed artifact**, which `NFR-010` names: install a known installer
  (record its sha256), reboot `STARBASE`, then
  `tools/startup_time.py "%LOCALAPPDATA%\Programs\Tracks & Trails\tracks-and-trails.exe" --cold
  --runs 1 --bound 5`. The 2026-09-12 figure of 3.976 s stays as history; it names no build.

#### Acceptance criteria

- An evidence file per platform with machine, method and the numbers taken — **for `0.1.0`, the
  retained 2026-09-12 measurements, by the maintainer's second 2026-09-13 ruling** *(first amended
  that day to one identified cold launch per platform plus the warm median; originally "the ten raw
  numbers and the two medians")*
- `TESTING.md` §8 item 14 cites the file, and names *which* build and version were measured
- A failure produces a task with a profile attached, and this task closes as *measured* either way

#### Out of scope

- Optimising anything. Measure first

---

### T-332 — Bundle yt-dlp 2026.8.19: the pinned baseline cannot download from YouTube

**Status:** **In Review** — every acceptance criterion met 2026-09-13, the canary included. Filed
2026-09-12 from `T-327`'s session, on the maintainer's direction: *"the bundled version should be
updated before we make the first tagged release."*
**Owner:** Implementer
**Priority:** High — the first release's first YouTube download fails without it
**Phase:** Phase 5
**Depends on:** nothing; **blocks** `T-328`
**Relevant context:** `OPS-002` (*"bumping the baseline is a release-gate step"*); `TESTING.md` §8
item 10a; `REL-002` (re-evaluated whenever the pin changes); `docs/RELEASE.md` (a bump is at least
a minor release — moot before `0.1.0`, which has no previous release)
**Affected surfaces:** `pyproject.toml`; `environment.BASELINE_YTDLP_VERSION`;
`docs/YTDLP_OPTION_AUDIT.md`; `packaging/licenses/README.md`; the Windows installer

#### What was found

In Windows Sandbox, after `REL-007`'s 2026-09-12 amendment fixed certificate verification, a
YouTube download in the `Best video up to 1080p (MP4)` preset read the video and then failed with
`HTTP Error 403: Forbidden`. Reproduced on `STARBASE` against the same video and selector, whole
file, not a first-bytes test:

| yt-dlp | result |
|---|---|
| 2026.07.04, the pin | extraction succeeds, `403` partway into the video stream |
| 2026.08.19, current | `399+140` downloaded and merged, 104,454,162 bytes |

A first-10 KB test (`"test": True`) **passed on both**, which is why it is not the evidence here.
The maintainer's Linux install already ran a user-managed 2026.08.19, which is why the same videos
worked there; updating in the Sandbox's Settings fixed it there too.

#### Done 2026-09-12

- **The suite at 2026.8.19, pin unmoved**: 11 failed, 4,334 passed — **exactly** the eleven
  `ytdlp-canary.yml` lists in `EXPECTED_STALE`, and nothing else. That is item 10a's question
  answered locally; the canary workflow has not been dispatched.
- **The option audit re-run**: `create_parser()` compared between the versions — 292 parser
  entries in both, none added or removed, no help string changed. Recorded in the audit.
- **The licence text** is byte-identical between the two wheels.
- **The pin moved** in `pyproject.toml`, `BASELINE_YTDLP_VERSION` and the freeze-probe test.

#### Acceptance criteria

- [x] The pin, the constant and the audit name 2026.8.19, and the pin-bound tests pass against it
- [x] CI green on both platforms at the new pin — run `34739041125` at `4320859`, every job
- [x] The `yt-dlp canary` workflow dispatched at 2026.8.19 (`TESTING` §8 item 10a) — run
      [`34743729647`](https://github.com/kottmans/tracks-and-trails/actions/runs/34743729647) at
      `40b1dd8`, **green**: `pip install --upgrade yt-dlp` resolved **2026.8.19**, PyPI's latest and
      the pin, and the suite passed **4,350 / 42 skipped** with the expected-stale tests deselected.
      *(A first draft of this line called dispatching it a cost to hosted minutes; the repository is
      public, and `LINUX_RUNNER` is unset, so it runs on a free hosted runner.)* **`T-326` still needs
      it at the release candidate's commit.**
- [x] `REL-002`'s negative build repeated at the new pin, with the result recorded there — still redundant: the archives differ only by `yt_dlp.__main__` and `yt_dlp.__pyinstaller`, 1751 extractors either way
- [x] The rebuilt Windows installer downloads a YouTube video in a clean Sandbox in the
      `Best video up to 1080p (MP4)` preset — the case that failed, not the probe's selector.
      **Done 2026-09-13**: *Big Buck Bunny*, 134,886,020 bytes in 12.6 s from the bundled
      2026.08.19, in `docs/project/evidence/windows-0.1.0.dev0-sandbox-2026-09-13.md`

---

### T-335 — A cancelled download can be queued again

**Status:** **In Review** — ruled 2026-09-13 by the maintainer from `T-327`'s session (*Queue again*,
at the back, from scratch — the Implementer's recommendation), recorded as `UX-005` §4's 2026-09-13
amendment, and built the same day.
**Owner:** Implementer designs; Maintainer rules
**Priority:** Medium
**Phase:** Phase 5
**Relevant context:** `UX-005` §4–§5; `REQ-015` (cancel), `REQ-018` and `P2PLAN-R7` (manual retry
re-enters at the back); `ARCHITECTURE.md` §5's state machine; `UX-008` (a cancel discards the
partial)
**Affected surfaces:** `core/job_state.py`, `downloader/manager.py`'s `retry`, `ui/row_verbs.py`,
`ui/queue_view.py`

The maintainer, in the Sandbox: *"once a video in the queue is cancelled, you should be able to undo
it."* A cancelled row offered only *Remove*, and the state machine had no way out of `CANCELLED`.

#### Built 2026-09-13

- **`Verb.QUEUE_AGAIN`**, *Queue again*, on cancelled rows before *Remove*; routed through
  `retry_requested`, the same route as *Retry* and *Start again*.
- **`CANCELLED → QUEUED`** is the one new edge. `CANCELLED` stays in `TERMINAL`, so `_settled` still
  drops a late outcome for it and *Clear finished* still clears it; `ARCHITECTURE.md` §5 says so.
- **`DownloadManager.retry`** accepts a cancelled job and writes it through `requeue_at_end`, at the
  back. **If the cancelled job's session is still held** — a running job's row says `CANCELLED`
  when its stream ends, before `_release` has found the process gone — nothing is written until the
  tick finds it released (`_requeue_when_released`), because `_release` fills free slots before it
  discards the old attempt's partial, keyed by the same job id. The pending set counts as work for
  `is_idle`, the tick's keep-alive and the drain rule, and shutdown drops it.
- **Tests**: a worker that honours the cancel, ends its stream and lingers ignoring `SIGTERM` —
  *Queue again* pressed while the row says `CANCELLED` and the session is held writes nothing, then
  `QUEUED` at the back once released (**mutated**: writing immediately fails it); a job cancelled
  before starting re-queues at once; the verb table and its complement; the routing.

#### Acceptance criteria

- [x] A cancelled row offers *Queue again*, which puts the job at the back of the queue as `QUEUED`
- [x] No worker outcome can move a cancelled job; only the user's request can
- [x] Pressed while the cancelled worker is still being stopped, it waits for the release
- [ ] Seen on the Windows installed build

**Not done, and not asked for:** a playlist header whose members are all cancelled offers no group
*Queue again*; each entry offers its own.

---

### T-333 — The yt-dlp section says which version is newest at a glance

**Status:** **In Review** — ruled 2026-09-12 (a table with a Check button, the Implementer's
recommendation), recorded as `OPS-002`'s 2026-09-12 amendment, and built the same day. Filed from
`T-327`'s session.
**Owner:** Implementer designs; Maintainer rules
**Priority:** Medium
**Phase:** Phase 5
**Relevant context:** `OPS-002` and its 2026-08-27 amendment (`T-290`: updating is a recovery move,
not upkeep); `NFR-007` (*"explicit yt-dlp update checks"* — a check on opening Settings would not be
explicit); `REQ-025` (the version shown is the one a worker imported)
**Affected surfaces:** `ui/settings_dialog.py`'s yt-dlp group

The maintainer, in the Sandbox: *"it should be more obvious what version you have, what the bundled
version is and what the latest is … There's also a wall of text there that kind of hides it."*

Today the group is three paragraphs and one `Version in use` line. **The latest version is known to
nobody until a network request is made**, and `NFR-007` allows that only as an explicit check —
so a *Latest* row either waits for a button press or the requirement is amended.

#### Built 2026-09-12

- **`YtdlpService.check_latest_version`** asks PyPI through the existing `latest_release` and emits
  `checked`; it holds no workers and writes nothing, which its test asserts with holds refused and
  the directory absent. An install's `installed` also reports the newest release to the screen.
- **The section** is a grid: *In use* (from a worker, unchanged), *Bundled* (the pin, spelt the way
  yt-dlp prints versions), *Latest* (*Not checked* until **Check**). A **newest** tag sits beside
  every row holding the newest version, and only once Latest is known.
- **Update** is enabled only when Latest is newer than In use, compared by value, and reads
  *Update to 2026.09.02*. The three paragraphs became one line; *tested with this application* is
  the bundled row's detail, and *updating affects downloads only* is the button's tooltip and
  accessible description.
- **Tests**: the service check; the composed screen reaching the service through Check and Update
  (and not checking on opening); unchecked, same, in-use-newer and latest-newer; tags before and
  after a check. **Mutated**: Update enabled without anything newer (3 failures); tags shown before
  a check (1).

#### Acceptance criteria

- [x] In use, bundled and latest are shown together, and the newest is tagged
- [x] Latest is fetched only on an explicit Check (`NFR-007`)
- [x] Update is offered only when latest is newer than what runs
- [x] The wall of text is gone, and what it said is still somewhere true
- [ ] Seen on the Windows installed build

---

### T-039 — Verify Windows installer behavior on the runner

**Status:** **In Review** — all four gates implemented and passing in Windows Sandbox, `T039-R1`
resolved, and **`T039-R2` ruled by the maintainer 2026-09-13: per release candidate** (below).
**Owner:** Implementer
**Priority:** Medium now, High once Phase 5 starts — it must land before the first public release
**Phase:** Phase 5
**Depends on:** the Phase 5 installer, `T-026` (establishes the real-plugin Windows job)
**Relevant context:** `OPS-004`, `REL-001`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Risk:** Medium — same failure mode as `T-026`: a shallow check would retire a
release-blocking manual item without replacing it

#### 2026-09-13 — `T039-R1`: a failure contract, and gates that see what they missed

**The review's four gaps, each closed and each shown failing a real run.**

- **No failure contract.** The script wrote a Markdown verdict nothing read. It now ends with a
  machine-readable `<!-- VERDICT: PASS|FAIL n -->` line and a failing exit code, and
  **`tools/windows/sandbox_evidence.sh`** is the consumer: it stages the installer *and*
  `evidence.ps1`, launches Sandbox, waits for the report, closes it, and **exits non-zero unless the
  verdict is PASS**. It refuses to start while any Sandbox is open.
- **Placement checked a few named files.** Every `Dest filename:` in Inno's own install log must now
  lie under the install root or its Start Menu folder.
- **User data was counted, not fingerprinted.** Each file's SHA-256 before the uninstall must match
  after it, and **no user data at all is a failure**, not a warning.
- **Leftovers were "the install root is empty"**, which `T322-R1` shows is the wrong question: the
  user's files there must stay. Leftovers are now the installed files the log names; a sentinel
  placed before installing and a file saved into the directory before uninstalling must both
  survive byte-for-byte.

**Three negative controls, each an installer compiled from the same tree, each run through the
runner:**

| Installer mutation | Run's verdict | Runner exit | What it said |
|---|---|---|---|
| none (the fix) | **PASS** | 0 | 227 logged destinations, none outside; 226 installed files removed; both user files and all 5 data files unchanged |
| `filesandordirs` on `{app}` restored | **FAIL 2** | 1 | *pre-existing sentinel DELETED*, *user-saved file DELETED* |
| a stray `[Files]` entry to Documents, and an uninstall rule deleting the user data files | **FAIL 2** | 1 | *1 WRITTEN OUTSIDE the install root*, *4 removed or changed by the uninstaller … library.sqlite3* |

The earlier no-op-uninstaller mutation, above, covers leftovers. **`T039-R2` is not answered here**:
whether these per-candidate Sandbox runs replace the criterion's per-push `windows-latest` job is the
maintainer's to rule.

#### 2026-09-12 — the four gates, and why they do not run on `windows-latest`

**All four pass**, in `packaging/windows-sandbox/evidence.ps1`, against
`Tracks-and-Trails-0.1.0.dev0-setup.exe`. Evidence:
[`windows-0.1.0.dev0.md`](evidence/windows-0.1.0.dev0.md).

| Gate | Result |
|---|---|
| 1 · silent install, success exit, no prompt | **exit 0 in 18.6 s**, per-user, no elevation |
| 2 · file and shortcut placement | 225 files, `_internal\licenses\`, `_internal\ffmpeg.exe`, Start Menu shortcut; **desktop icon absent**, as the opt-in default asks |
| 3 · the installed application launches | window in **~2 s**, titled *Tracks & Trails*, **no orphans** after close |
| 4 · uninstall and removal | **exit 0**, install root removed, shortcut removed, **user data preserved** |

**Gate 4 makes the distinction the criteria ask for rather than tolerating a leftover.** Five
files under `%LOCALAPPDATA%\tracksandtrails` before the uninstall and five after: `DAT-001` says
settings and the job database survive by intent, so the check asserts they are **still there**,
and separately that the install root is **empty**. A single "nothing left behind" test would have
failed the requirement it was meant to protect.

**Each is a gate, proved by mutation** (`T031-R2`, and the acceptance criterion's own words).
Replacing the uninstaller with a no-op that exits 0:

```
install root      225 FILE(S) LEFT: tracks-and-trails.exe, unins000.dat, ...
start menu        SHORTCUT LEFT BEHIND
**FAIL** - 2 check(s) did not pass.
```

**The scope says *"assert, on `windows-latest`"* and this does not. That is deliberate.** When
this task was written, CI's Windows leg was a hosted runner — *"a CI runner is a genuinely clean
machine, which is what makes this worth automating at all"*. `OPS-010` has since routed Windows to
`STARBASE`, the maintainer's own desktop. Installing and uninstalling an application there on
every run would (a) not be clean-machine evidence, since the machine already has Python, a
toolchain and a developer's yt-dlp, and (b) make the machine's state a function of whoever pushed
— which is the concern `OPS-012` §3 exists for.

**Windows Sandbox is clean on every launch and discarded on close**, which is the property the
hosted runner used to supply, and `REL-006` already chose it for `T-318`. So these gates ride
`T-318`'s harness rather than a second one — which is also what the scope asked for in spirit:
*"reusing `T-026`'s harness rather than a second one"*.

**What that gives up, stated rather than implied:** these do not run on every push. They run when
the Sandbox evidence is taken, which is per release candidate. A regression in the installer
between candidates would not be caught the day it landed. Restoring per-push coverage would mean
un-routing Windows CI from `STARBASE`, which `OPS-010` decided against for reasons that have not
changed.

**Its gates are independent of signature** (`T-317`'s fourth criterion, recorded here where the
gates will be written). `REL-005` ships `0.1.0` unsigned and names a certificate as the `1.0`
condition — so these checks must hold in **both** states. A silent install must succeed whether or
not the installer is signed, and **no assertion here may pass only because a signed binary skipped
a prompt**: that is a test measuring SmartScreen rather than the installer, and it would go red
the day signing arrives, which is the one day nobody would suspect the test.

#### Scope

Split out of `T-026` when `OPS-004` was accepted on 2026-07-26. `OPS-004` reclassified four
things as automatable on the Windows runner; three of them `T-026` does now, but installer
verification cannot be written before an installer exists, and `T-026` had to stay completable
because it is what closes Phase 0's last exit criterion.

A CI runner is a genuinely clean machine, which is what makes this worth automating at all:
installing onto a box that has never held the application is exactly the case a developer
machine cannot reproduce.

Assert, on `windows-latest`:

1. **Silent install** completes with a success exit code and no interactive prompt.
2. **File and shortcut placement** — the installed tree, the Start Menu entry, and any
   registered association land where the installer claims.
3. **The installed application launches** under the real `windows` platform plugin, reusing
   `T-026`'s harness rather than a second one.
4. **Uninstall and removal** — the uninstaller exits clean and leaves nothing behind except
   what is deliberately preserved (user settings and the job database, per `DAT-001`).

#### 2026-09-13 — `T039-R2` ruled: per release candidate

**Asked with three options, the maintainer chose the recommendation**: keep the scripted Sandbox run
as the gate, once per release candidate, rather than a per-push job on a hosted `windows-latest`
runner or both. The criteria below are amended in place and keep what they said. `REQUIREMENTS.md`
§3 now says installer placement and removal are automated, on that cadence.

#### Acceptance criteria

- **Amended 2026-09-13 by the maintainer's ruling on `T039-R2`:** the gates run **once per
  release candidate** in a clean Windows Sandbox through `tools/windows/sandbox_evidence.sh`,
  whose non-zero exit is the failure — not on every push on `windows-latest`. Stated as given up:
  an installer regression is caught when a candidate is taken, not the day it lands.
- Each of the four is a **gate**, stated as a mutation that turns the run red: a missing
  shortcut, a file placed outside the install root, a non-zero silent-install exit code, and a
  leftover installed file after uninstall each fail it. Screenshots, if any, stay retained evidence
  and fail nothing on their own (`T031-R2`, `P0-R7`)
- Uninstall leaving user data behind is asserted as **intended** behavior, not tolerated as a
  leftover — the test distinguishes the two
- `docs/project/TESTING.md` §9's manual list drops installer placement and removal, and
  `REQUIREMENTS.md` §3 narrows to match — **only once this job is landed and green**
- ~~The added CI time is recorded against `T-006`'s budget~~ — **none added**: by the 2026-09-13
  ruling these run per candidate, outside CI

#### Out of scope

- Whether the installer *feels* normal — `OPS-004`'s subjective residue, still human, still
  blocks first release
- Upgrade-over-existing-install and downgrade paths — real, but a separate task once the
  versioning story exists
- Any non-Windows packaging

---


### T-324 — A release workflow that builds, gates and drafts — and never publishes

**Status:** **In Review** — written 2026-09-12. **Its first acceptance criterion needs a tag**, and
a tag is the one artifact in this project that cannot be quietly corrected, so that one is left to
the maintainer rather than taken. Filed 2026-09-11 with the Phase 5 plan.

#### 2026-09-12 — the workflow, and the criterion deliberately not met

`.github/workflows/release.yml`, four jobs: `verify` → (`build-linux`, `build-windows`) → `draft`.

**`push: tags` and nothing else.** No `workflow_dispatch`, because a release has exactly one
legitimate trigger and a dispatchable one invites a draft built from an untagged tree. No
`pull_request` ever — `SECURITY.md` §CI trust boundary makes the trigger set the control that
keeps a fork's code off the maintainer's machines, and `tests/unit/test_workflow_triggers.py`
already scans this file for it.

**The permission widens by exactly one scope, for one job.** `contents: read` at the top level as
`SECURITY.md` requires; `contents: write` re-declared on `draft` alone. A build job with write
access could replace a release and has no reason to be able to.

**It drafts, and the drafting is asserted three ways** — the flag is passed, the result is read
back with `gh release view --json isDraft`, and a test forbids every publishing verb anywhere in
the file. One of those alone would be easy to lose in an edit.

**Nothing is built before the tag is verified.** `verify` runs alone and checks three things: the
tag equals `__version__` (`tools/version_tag_check.py`), the commit is an ancestor of
`origin/main`, and **the changelog has a section for the version**. The last is checked *there*
rather than at the end, because discovering it after two builds wastes the builds — and because a
draft with an empty body is worse than a stop, since somebody then publishes it.

**`tools/changelog_section.py` is a function with a CLI**, which is `T240-R1`'s rule: a decision
buried in `sed` is a decision nobody reviews. **Its tests found two defects in it immediately** —
the first version matched up to the `]` and left `- 2026-09-12` as the first line of the release
body, and it required a separator before a pre-release suffix so `0.1.0rc1` was not a version at
all. Rewritten as a small parse: a body runs from the end of its heading *line* to the next
version heading, so the date stays out and a `### Added` inside stays in. 14 cases, including that
`0.1.10` does not satisfy a request for `0.1.0` and that a missing section is told apart from an
empty one.

**The release builds are gated and probed, not merely built.** `ci.yml`'s `frozen` job proves the
*smoke* build; the release build differs in the three places that matter — windowed on Windows,
ffmpeg bundled, built in the oldest-glibc container on Linux. So all four probes and all four
`T-323` gates run again against what actually ships, and the Windows probe step sets
`TT_PROBE_REPORT`, because `console=False` leaves a windowed build with no `stdout` and reading
the console would read nothing and pass.

**`OPS-012` §3 held in the one place it is tempting to break.** The Windows job **checks for Inno
Setup and fails**, naming the rule, rather than installing it. The pinned ffmpeg fetch *is* a
step here — and that is consistent rather than an exception: §3 is about a *build* changing the
machine, and `packaging/tracks-and-trails.spec` still refuses to fetch anything. A named,
reviewable step in a workflow a human reads is the opposite of a side effect.

**`cancel-in-progress: false`**, deliberately. A half-built draft is the one artifact nobody can
tell apart from a finished one — and `cancel-in-progress` has already destroyed a Windows evidence
run twice in this project, most recently on 2026-09-12.

**21 tests.** What is *not* done is the first acceptance criterion: *"a tag on a test branch
produces a draft release with two artifacts and a checksums file"*. Pushing a tag is an outward
act `REL-003` governs and `docs/RELEASE.md`'s own review prompt forbids without instruction, and
the Windows half needs `STARBASE`. **That is left to the maintainer**, and until it is run this
workflow is reviewed rather than proven.
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 5
**Depends on:** `T-319`, `T-321`, `T-322`, `T-323`, `T-320`
**Relevant context:** `.github/workflows/ci.yml`'s `frozen` job (builds both artifacts every push
and uploads **evidence only**, 30-day retention — nothing today produces a downloadable release);
`OPS-009`/`OPS-010`/`OPS-012` (where each platform builds); `SECURITY.md` §CI trust boundary
(read-only default token, no secrets); `docs/RELEASE.md`'s release review (*"do not tag, commit, push,
or publish unless explicitly instructed"*); `NFR-007`
**Affected surfaces:** `.github/workflows/release.yml` (new), `docs/RELEASE.md`
**Risk:** Medium — a workflow with permission to create releases is the one place the CI trust
boundary widens, and it must widen by exactly one scope

#### Scope

Triggered by a `v*` tag. On the same runners `ci.yml` uses — Windows on `STARBASE`, Linux on the
oldest-glibc container `T-321` names — it:

1. Asserts the tag matches `__version__` (`T-320`'s rule) and the commit is on `main`
2. Builds `T-319`'s windowed artifact and `T-322`'s installer; builds `T-321`'s AppImage
3. Runs every frozen probe and every `T-323` gate against the **release** builds
4. Writes `SHA256SUMS` for both artifacts
5. Creates a **draft** GitHub Release with the artifacts, the checksums, and the `CHANGELOG.md`
   section for the version as its body

**It stops at draft, always.** Publishing is a human click after `T-328`'s review, which is the
release prompt's own rule and the only place a release can be inspected before it is public. The
workflow's token gets `contents: write` for that one job and nothing else keeps it (`SECURITY.md`).

#### 2026-09-13 — the review's two findings

**`T324-R1`: the installer would never have been uploaded.** The upload step looked in
`packaging/Output/*.exe`, Inno's default — but `tracks-and-trails.iss` sets `OutputDir=..\dist`,
and `T-322`'s own compile transcript names `dist\Tracks-and-Trails-0.1.0.dev0-setup.exe`. A real
tag would have built both platforms, failed `if-no-files-found: error`, and drafted nothing. The
path is `dist/*-setup.exe` now, and
`test_the_installer_is_uploaded_from_where_the_script_writes_it` resolves the script's `OutputDir`
and `OutputBaseFilename` the way ISCC does and matches a representative compiled name against the
upload glob. **Mutation:** restoring `packaging/Output/*.exe` fails it.

**`T324-R2`: the ffmpeg probe was missing from the Windows release build**, though it exists for a
release-only defect. The loop is replaced by `packaging/windowed_checks.py probes`, which runs all
five probes — spawn, yt-dlp, database, update, **ffmpeg** — each with its own report file and its
console discarded, and fails any whose report lacks its success line. The same script is what
`ci.yml`'s `frozen windows` job now runs for `T-319`. **Missing and unusable helper failures** are
measured in `T-319`'s 2026-09-13 section: with `ffmpeg.exe` and `ffprobe.exe` deleted the probe
exits 1 naming `OPS-001`.

**Criterion 1's wording is corrected**, as the review asked: it said *"a tag on a test branch"*,
and `verify` deliberately refuses a commit that is not on `main`. The criterion now says what the
workflow can do. **`ci.yml`'s `frozen` job is no longer unchanged**: `T-319`'s own criterion adds
the windowed build to it; this workflow still does not run on push.

#### Acceptance criteria

- A `v*` tag **on a commit on `main`** produces a draft release with two artifacts and a checksums
  file, and `gh release view` shows `draft: true` *(said "a tag on a test branch", which `verify`'s
  main-ancestry check refuses by design)*
- A tag whose version disagrees with `__version__` fails at step 1 with the disagreement named
- The `permissions:` block grants `contents: write` to the release job only; the workflow file is
  reviewed against `SECURITY.md` §CI trust boundary and the review recorded
- `docs/RELEASE.md` describes the tag → draft → review → publish sequence, and the rollback of
  each step
- This workflow does not run on push. *(Also said the `frozen` job in `ci.yml` stays unchanged in
  scope; `T-319`'s criterion adds the windowed release build to its Windows leg.)*

#### Out of scope

- Publishing. Deliberately
- Signing (`T-317` decides; if signed, the signing step lives here and the key does not)

## Ready

### T-327 — The Windows manual verification session

**Status:** **In Progress** — the maintainer's session began 2026-09-12 in Windows Sandbox. Item 1
is under way and **has already found one defect**, below. Filed 2026-09-11 with the Phase 5 plan.
**Human, and blocking**: `TESTING.md` §8 item 15 says *"CI green is not a substitute"*

#### 2026-09-12 — the session so far

**Item 1, install.** The maintainer reports the installer *"works fine"* and, after the wizard
artwork changes, *"everything looks good"*. **One finding**: an *"Install for me only / Install for
all users"* question appeared before the wizard — invisible to every automated run, since they are
all `/VERYSILENT`. Fixed under `T-322` by ruling (`commandline`: no question, `/ALLUSERS` kept for
administrators). **To confirm on the rebuilt installer.** Also from this session: the wizard pages
now carry the logo rather than Inno's stock artwork, at the maintainer's request — a polish change,
not a defect.

**Items 2–6 not yet done.** The review record is written when the session is, in the maintainer's
own words.

#### 2026-09-12 (later) — what the session found, and where each went

**Item 1 is confirmed** on the rebuilt installer: no install-mode question, and the wizard artwork
sharp at Inno 6.7's real slot sizes. Then, using the installed application in Sandbox, the
maintainer found **six defects**, none visible to an automated run, and more on 2026-09-13. The first two were confirmed fixed by the maintainer on the rebuilt installer (`4324e21c…`) the same day; the rest await the next build. **Vertical bars** the maintainer saw across the empty queue in dark are not drawn by the application — measured on `STARBASE`, the queue paints one colour, `#0a1712`, everywhere but its text — and are most likely the Sandbox's remote display compressing a near-black area. Each is fixed, pushed and
tested; the review record will cite them.

| Found | Cause | Commit |
|---|---|---|
| a short grey line after each status-bar message | Qt's Windows item frame | `3294cfd` |
| a closing full stop on the ffmpeg summary | sentence punctuation beside a caption | `c7ef559` |
| dark-mode menu titles unreadable under the pointer | no `QMenuBar` rule, so the native pale highlight | `b060966` |
| **every YouTube download failed**, `CERTIFICATE_VERIFY_FAILED` | Python trusts only roots already in the Windows store; `REL-007` amended to verify through the OS (`truststore`) | `1f377db`, `4e20c70` |
| the chosen entry of a drop-down invisible | `QListView::item:selected` reaching the popup under the Windows style | `5461053` |
| **YouTube downloads then failed with 403** | the bundled yt-dlp 2026.7.4; `T-332` bumps it | `663838e` |
| dark mode: `Start` and `Clear finished` highlighted only at the border under the pointer | the hover fill was `sunken`, 1.05:1 against the resting fill; a `hover` role lifts it | `fcff105` |
| tooltips white on white | no `QToolTip` rule, so the theme's text on the Windows style's white panel | `fcff105` |
| a disabled option's label still drawn in full ink | the `QWidget` rule's colour beat the palette's disabled text for every widget without its own `:disabled` rule | `f91ea9d` |
| a band behind each label and tick box inside a group | every widget painted the `window` ground on the group's `surface` | `a5cd14f` |
| row buttons with no face, no hover and no press; the status chip read as a button | verbs drawn through the list's style, which no button rule matches; the chip outlined like a button (ruled: a filled label) | `3f576e1` |
| tick boxes a white square in every theme and state | the Windows style's own indicator (ruled: drawn from the theme) | `9511238` |
| no way back from a cancel | `CANCELLED` had no exit (ruled: *Queue again*, `T-335`) | `e9549fd` |

Two changes of behaviour came out of the same sitting, each ruled by the maintainer: the yt-dlp
section shows in-use, bundled and latest side by side (`T-333`), and a started queue stops itself
once its work is done (`T-334`).
**Owner:** Maintainer performs; Implementer prepares the list and records the result
**Priority:** High — the one exit criterion the plan says cannot be met from the development
environment
**Phase:** Phase 5
**Depends on:** `T-322` (an installer to install) and `T-318` (a clean Windows machine to install
it on — Windows Sandbox if that is what it chose)
**Relevant context:** `TESTING.md` §9's manual list and its `OPS-004` residue: *whether the
rendering looks right, whether Narrator sounds coherent, whether the installer feels normal, shell
foreground and file-association behaviour, long-running stability*; `IMPLEMENTATION_PLAN.md`
§Phase 4's screen-reader amendment (coherence *"belongs to the pre-release session"* — this is
that session, for Windows); `REQUIREMENTS.md` §3
**Affected surfaces:** a review record under `docs/project/reviews/`, indexed by `REVIEWS.md`;
`REQUIREMENTS.md` §3's *known-unverified* paragraph, which this discharges
**Risk:** Low to run; the risk is the schedule — it needs the maintainer, a Windows desktop and an
installer on the same afternoon

#### Scope

`OPS-004` shrank this to the subjective residue and named each item. The session performs exactly
that list — no more, because everything else is gated; no less, because each item is there for
a reason `OPS-003` and `OPS-004` recorded:

1. Install from `T-322`'s installer on the clean machine, watching the prompts (`T-317`'s
   SmartScreen screenshot is taken here if unsigned)
2. Rendering under light and dark themes — does it *look* right, beyond matching a baseline
3. **Narrator**: open the add dialog, stage a URL, open its format table, choose a format, add it,
   start the queue — is what Narrator says *coherent*, as distinct from the tree being correct
4. Native file dialogs, *Show in folder*, *Open*: does Explorer come to the foreground, does the
   dialog start somewhere sensible, is the association the expected one
5. A long real download with the window in use throughout — stability under real use
6. Uninstall, watching what it says about user data

*(Said `T-212`'s recorded checklist run was the same sitting. `T-212` was cancelled 2026-09-13 by the
maintainer; this session is the manual check the release relies on.)*

#### Acceptance criteria

- A dated review record with each of the six items marked and described in the maintainer's own
  words, indexed by `REVIEWS.md` — the form `TESTING.md` §8 item 15 names
- `REQUIREMENTS.md` §3's *known-unverified on Windows* paragraph is rewritten to what was
  actually observed, no further
- Anything found becomes a task, and a task found here blocks the release only if it is a
  Critical or High defect (`TESTING.md` §14's severities)

#### Out of scope

- Anything CI already gates. Recording a gated item as *passed by hand* is the drift `TESTING.md`
  §9 warns against

---

### T-326 — The release-candidate suite: everything the gate asks a machine for, on both platforms

**Status:** **In Progress** — the items that do not need a release candidate were run 2026-09-12;
the rest wait on a `v*` tag, which is `T-324`'s trigger and the maintainer's act. **The
enumeration found a gap in §7's own coverage**, below. Filed 2026-09-11 with the Phase 5 plan.

#### 2026-09-12 — what a machine could do without a candidate

Evidence:
[`2026-09-12-T326-release-candidate-suite.md`](evidence/2026-09-12-T326-release-candidate-suite.md).

**Item 3 — `pytest -m network`, both platforms, and its first run found a defect.** This suite
runs nowhere automatically (`addopts` excludes it), so CI has never executed it.

| Platform | Result |
|---|---|
| Linux | **2 passed, 2 skipped** in 9.88 s |
| Windows, `STARBASE`, logged-on session | **2 passed** in 31.73 s |

**It failed the first time in 3.35 s, and not because of the network.**
`test_one_real_url_downloads_end_to_end` raised *"already has a download session"*: it pressed
Start on the queue **and** called `manager.start(job_id)`, but with the queue running
`add_to_queue` admits the job and admission starts it. It had drifted from the offline sibling its
own docstring calls *"deliberately the same shape"* — that one presses Start once and then waits,
which is what a user does. **Its docstring also says it had never been executed**, which is
exactly why the drift could not show. Corrected; both platforms pass.

**Item 4 — every §7 mandatory test enumerated by name**, so the next release diffs the list rather
than re-reading the table. Ten of eleven areas map to named tests; the widget-destruction rule maps
to `tests/qt_lifecycle.py` enforcing it at every `tests/ui` boundary, which is how §7 itself
describes it.

**The eleventh is a gap, and finding it is what the item is for.** §7 requires *"a settings change
mid-flight does not alter a running job's `DownloadRequest`"* and **no test asserts it**. What
exists is the structural half — `test_every_model_is_frozen` proves the dataclass is frozen, and
`ARC-008` has composition read settings once. Frozen means it cannot be *mutated*; it does not
prove a running job keeps the request it started with, and the failure mode is a **new** request
being built and handed to something in flight. **Reported rather than resolved**: writing it is a
test, and whose task it is is the maintainer's call — it is §7 coverage, so arguably a phase-exit
obligation rather than this task's, whose job is to check the list rather than fill it.

**Item 5 — `N/A` for `0.1.0`, and that is only true once.** There is no previous release to
migrate from. The `0.2` obligation is now written into `docs/RELEASE.md`'s release-commit steps:
**keep a `0.1.0` database fixture at the `0.1.0` tag**, because it cannot be reconstructed
afterwards — what it has to prove is that *real rows* survive, not that a schema loads.

**Item 10a — owed after all.** This read *"not applicable: `OPS-002`'s baseline is not bumped in
`0.1.0`"*, which was true when written. **`T-332` moved the pin to 2026.8.19 the same evening**,
because 2026.7.4 cannot download from YouTube, so the canary at 2026.8.19 is part of this release's
evidence. `T-332` ran the suite locally at that version before moving the pin — eleven failures,
exactly the canary's expected-stale list — but the workflow itself has not been dispatched.

**Items 1, 2, 8 and 10 wait on a candidate.** 8 and 10 *have* been run by hand on the release
artifacts — 5 of 5 probes on Windows, 4 of 4 on the AppImage — but the gate asks for them **at the
candidate, through the workflow**, and that needs the tag.
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 5
**Depends on:** `T-324` (a release candidate to run against)
**Relevant context:** `TESTING.md` §8 items 1–5, 8, 10, 10a; §7's mandatory-coverage table;
`pyproject.toml`'s `addopts = "-m 'not network …'"` — **the network suite is not in CI**;
`ytdlp-canary.yml` (`workflow_dispatch`); `OPS-002`; `DAT-001`
**Affected surfaces:** `docs/project/evidence/`, possibly a `release-candidate` job in `T-324`'s
workflow
**Risk:** Low — these are runs, not builds; the risk is claiming one that did not happen

#### 2026-09-13 — the review's two findings

**`T326-R1`: the missing §7 test is written.** *Settings freeze* —
`tests/integration/test_composition.py::test_a_settings_change_mid_flight_does_not_alter_a_running_jobs_request`.
A real download runs in the composed application; the proxy and rate limit are changed on the
Settings screen while it runs. It asserts the change is live (a request built afterwards carries
it), that the running job's stored request is unchanged, and that the worker was handed the request
it was queued with. **Mutation:** making the network handler rewrite running jobs' stored requests
fails it. §7's eleven areas now all map to named tests.

**`T326-R2`: the routing is corrected** — item 10a is owed after `T-332`, and item 8's cancellation
and normal-exit clause is a sitting rather than a probe. The retained evidence gets an appended,
dated superseding note rather than an edit. `docs/RELEASE.md`'s fixture step said *"from `0.2`
onward"*, contradicting its own next sentence; it now says from `0.1.0` on.

#### Scope

The release gate's machine half, run **against the candidate** rather than against `main`:

- Items 1–2: static gates and the full default suite, both platforms — `ci.yml` already does this
  per push; the record here is the run ids at the RC commit
- Item 3: **`pytest -m network`** against the pinned baseline, both platforms — this suite runs
  nowhere automatically today, so it is a deliberate manual run with its output retained
- Item 4: every §7 mandatory test present — enumerated by name against the table, once, with the
  test ids recorded so the next release diffs the list rather than re-reading it
- Item 5: **the migration check is `N/A` for a first release and says so** — there is no previous
  release's database. The obligation is written into `docs/RELEASE.md` for `0.2`: keep a `0.1.0`
  database fixture and open it
- Item 8: the frozen smoke, on the **release** builds — `T-324`'s probe steps cover launch and no
  recursive launch, and the record is the run id; **the real download is the clean-machine
  transfer** of `T-318`'s evidence for that candidate (`--download-probe`, which `T-324` does not
  run); **"cancel another" and a normal exit are a sitting**, which no probe performs (`T326-R2`,
  `T326-R3` — this credited `T-324`'s offline probes with the download)
- Item 10: the in-app yt-dlp update from the release artifact — `T-324` runs the probe; the record
  is the run id
- Item 10a: only if the baseline is bumped in this release — **and for `0.1.0` it is**: `T-332`
  moved it to 2026.8.19, so the canary at that version is owed *(said "for `0.1.0` it is not")*

#### Acceptance criteria

- One evidence file for the release candidate listing each item, the command or run id that
  satisfied it, and the platform — no item marked passed without its artifact
- The network-suite output is retained for both platforms
- `docs/RELEASE.md` gains the `0.2` migration-fixture obligation

#### Out of scope

- Items 6, 7, 11–15: `T-328`'s release review, `T-318`, `T-323`, `T-325`, `T-327` respectively
  *(item 6 was `T-212`'s until its cancellation on 2026-09-13)*

---

### T-322 — The Windows installer

**Status:** **In Progress** — **compiled on `STARBASE`** 2026-09-12, installed and uninstalled in
Windows Sandbox by `T-039`'s gates, and polished in the maintainer's session (below). Open: built by
`T-324`'s workflow, which needs a tag, and `T-317`'s SmartScreen screenshot. *(This said it could not
be built without Inno Setup; the maintainer installed it.)*
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 5
**Depends on:** `T-319` (what it installs), `T-320` (the version), `T-317` (whether it is signed)

#### 2026-09-13 — `T322-R1`, Critical: the uninstaller deleted its whole directory

**The reviewer was right, and the Sandbox shows it.** `[UninstallDelete]` held
`Type: filesandordirs; Name: "{app}"` under a comment saying *only what the installer created* —
and `filesandordirs` is recursive deletion of **everything** there, including a user's own files
and anything that was in the directory before this installed into it. Inno's own documentation
warns against exactly that, and every automated run installed into an empty directory, so none
could see it.

**Removed, not narrowed.** Inno removes every file its log installed and the directory once it is
empty; the application writes nothing beside itself (`NFR-004`), so there is nothing else of ours
to name. `test_the_uninstaller_deletes_nothing_wholesale_under_the_install_directory` refuses a
recursive or wildcard entry under `{app}`, with the shipped line as its positive control. The
uninstall prompt also stopped promising a *download history*, which the application no longer
keeps (`T-186`).

**Verified in Windows Sandbox with both installers built from the same tree**, by `T-039`'s
reworked run, which installs into a directory already holding a sentinel file and plants a
user-saved file inside it before uninstalling:

| Installer | Sentinel | User-saved file | Verdict |
|---|---|---|---|
| fixed, sha256 `5c5c3ec3…` | kept, unchanged | kept, unchanged | **PASS** |
| the old rule restored, `91bd51cb…` | **DELETED** | **DELETED** | **FAIL 2** |

The passing report is `docs/project/evidence/windows-0.1.0.dev0-sandbox-2026-09-13.md`.

#### 2026-09-12 — the script, with every default the scope named

`packaging/tracks-and-trails.iss`. **Per-user with no administrator prompt**, because the
application writes nothing beside itself (`NFR-004`) and a per-machine install would add an admin
prompt on top of the SmartScreen warning `REL-005` already accepts — two warnings before the first
launch. Start Menu shortcut always, desktop shortcut **opt-in and unchecked**. The whole one-dir
tree including `licenses\`. `SignTool` is present but commented, so adding a certificate is an
edit to a line that exists rather than a new one.

**The uninstaller says what survives it** on its own final page: settings, download history and
downloaded files stay (`DAT-001`). `T-039` asserts the two halves separately — leftovers under the
install root are a failure, leftovers under the user directories are the intent.

**The version is passed in** (`/DAppVersion=`) and the script **refuses to compile without it**,
so it cannot acquire a second opinion about the version `REL-003` fixes in `__init__.py`.

**Nothing here is verified.** An Inno Setup script is not executable on Linux, so this is authored
rather than tested: the structure and directives are checked, and **silent install, placement,
launch, uninstall and removal are all `T-039`'s, on a machine that has Inno Setup**. Installing it
is a deliberate manual act on `STARBASE` per `OPS-012` §3.

#### 2026-09-12 (later) — the half a Windows machine would not have caught either

**Compiling it still needs Inno Setup, and that bound stands.** What does not need it is the other
half: **every declaration in this script repeats something declared elsewhere, and nothing fails
when a copy drifts.** The installer would compile, install, and leave a Start Menu shortcut
pointing at a filename the spec stopped producing — a defect a successful compile cannot see. Same
class as `test_appdir_metadata.py` for the Linux AppDir, and it is in
`tests/unit/test_windows_packaging.py` beside `T-319`'s.

What is now pinned, each against its other declaration or its requirement:

| Claim | Checked against |
|---|---|
| `AppExe` is the executable the build produces | the PyInstaller spec's own `name=` |
| the script refuses to compile without `/DAppVersion=` **and defines no default** | `REL-003`, which fixes the version in `__init__.py` |
| no administrator prompt, per-user location | `NFR-004`; a second warning on top of `REL-005`'s SmartScreen click-through is how an install gets abandoned |
| Start Menu shortcut always, desktop icon **unchecked** | the scope's named defaults |
| the whole one-dir tree, `recursesubdirs` included | `LIC-001` — `licenses\` has to reach the user, and `_internal\` has to reach them at all |
| `SignTool` present but **commented** | `REL-005` ships `0.1.0` unsigned, so enabling it is an edit to a line that exists |

**Four mutations, four caught**: a pre-ticked desktop shortcut, `PrivilegesRequired=admin`, an
`AppVersion` default that would give the installer a second opinion about the version, and
dropping `recursesubdirs` so only the executable ships.

#### 2026-09-12 — no install-mode question, found by the manual session

**The installer asked "Install for me only / Install for all users" before anything else.** Found
in the maintainer's first interactive install (`T-327` item 1). Every automated run — `T-039`'s
gates included — uses `/VERYSILENT`, which skips every dialog, so **no gate could have seen it**.

`PrivilegesRequiredOverridesAllowed=dialog` caused it, directly beneath a comment arguing for
fewer prompts before first launch; *"for all users"* is also an admin prompt. **Maintainer ruling:
no dialog, but keep the escape hatch** — now `commandline`, so a double-click installs per-user
without asking, and an administrator can still pass `/ALLUSERS`. A test asserts the value; setting
it back to `dialog` fails it. **`/ALLUSERS` itself is not exercised** — it needs elevation, and
nothing here runs elevated.

#### 2026-09-12 — no "pin to taskbar" option, by ruling

**Maintainer ruling, 2026-09-12: the installer does not pin to the taskbar**; the user pins it
themselves. Recorded so the checkbox is not proposed again.

**Windows does not let installers pin apps, deliberately.** Microsoft withdrew the pin action in
Windows 10 because installers abused it, and on Windows 11 the taskbar belongs to the user. The
only supported route (`TaskbarManager.RequestPinCurrentAppAsync`) asks the user to confirm and is
limited to apps with package identity (MSIX), which this is not. The remaining routes work around
that restriction and break between Windows builds. For an **unsigned** installer (`REL-005`),
reaching into the taskbar's private settings is also the kind of behaviour that makes antivirus
suspicious, on the screen where a stranger is deciding whether to trust the download.

**What the installer does instead** is what a well-behaved one is allowed to do: a Start Menu entry
always, a desktop icon if ticked, and *Launch* on the last page — from which pinning is one
right-click. A last-page hint about pinning was offered and not chosen. **Reopening condition:** the
application ships as an MSIX package, which would make the supported in-app prompt available.

#### 2026-09-12 (later) — compiled, and the first compile found two defects

**The maintainer installed Inno Setup 6.7.3 on `STARBASE`** — the deliberate manual act `OPS-012`
§3 requires, and which this task declined to do for itself. It then compiled:

```
Successful compile (85.516 sec).
C:\dev\tracks-and-trails\dist\Tracks-and-Trails-0.1.0.dev0-setup.exe
91,776,949 bytes
sha256 7528e12f3547a8b904b9247de745c24502e4d881c2e5a5b9ab9fb9552b56514b
FileVersion     0.1.0.0
ProductVersion  0.1.0.dev0
CompanyName     Sean Kottman
FileDescription Tracks & Trails Setup
```

**1. `VersionInfoVersion` will not take a PEP 440 version.** `AppVersion` comes straight from
`__init__.py` via `REL-003`, which between releases is `0.1.0.dev0` — and Inno rejects it
outright: *"Value of [Setup] section directive VersionInfoVersion is invalid"*, compile aborted at
line 32. The file's own numeric resource has to be numeric.

**Derived in the script rather than passed in**, so there is still exactly one version input: a
second `/D` define would be a second opinion about the version, which is what `REL-003` and this
script's `#error` exist to prevent. `.dev0` becomes a fourth numeric component, and the compiled
installer shows the result — `FileVersion 0.1.0.0` beside `ProductVersion 0.1.0.dev0`, the
numeric resource numeric and the human-readable one true. A suffix the mapping cannot handle
**fails the compile** rather than being guessed at.

**2. `ISCC.exe` is not where the release workflow looked.** `winget install
JRSoftware.InnoSetup` installs **per-user**, at `%LOCALAPPDATA%\Programs\Inno Setup 6\` — not
`C:\Program Files (x86)\`. `release.yml` checked only the latter and would have reported Inno
Setup missing on a machine that had it. It now searches three locations plus `PATH` and **exports
what it found**, so the compile step uses a located path rather than guessing again.

**That is the same defect class as `T-319`'s ffmpeg destination**, one task apart: a location
asserted from a comment instead of from a build. Both were found by running the thing.

**One of the new tests caught me in a third instance of it.** A test forbade the string
`winget install` anywhere in the workflow, to enforce `OPS-012` §3 — and then failed when the
error message started telling the human how to install Inno Setup. Naming a remedy is not
performing it; the test now looks at whether a line is *executed* rather than whether a string
appears, and the workflow's message is split so each line carries its own `echo`.

**Still not verified, and it is `T-039`'s by scope:** silent install, placement, launch,
uninstall and what survives it. Those need the installer *run*, and running it on `STARBASE`
would neither be clean-machine evidence nor leave the machine as it was — `T-318`'s Windows
Sandbox evidence is where that belongs.
**Relevant context:** `REL-001` (*"PyInstaller one-dir build + Inno Setup installer"*); `OPS-004`
(silent install, placement, uninstall are automatable — `T-039` does that; whether it *feels*
normal stays human); `DAT-001` (user data survives an uninstall); `NFR-004` (nothing written
beside the installed application); `OPS-012` §3 (a self-hosted runner must not provision itself)
**Affected surfaces:** `packaging/tracks-and-trails.iss` (new), `.github/workflows/`,
`docs/RELEASE.md`
**Risk:** Medium — an installer is the first thing a user judges, and every default it picks is a
decision

#### Scope

An Inno Setup script producing `Tracks-and-Trails-X.Y.Z-setup.exe`. **The defaults, proposed and
each one reversible by ruling:**

- **Per-user install, no administrator prompt.** The application writes nothing beside itself
  (`NFR-004`), so it needs no elevation; a per-machine install would need an admin prompt on top
  of whatever `T-317` decided about SmartScreen, which is two warnings before the first launch.
- **Start Menu shortcut always; desktop shortcut opt-in**, unchecked by default.
- **Silent install** honours `/VERYSILENT /NORESTART` — `T-039` asserts this.
- **Uninstall removes the files the installer installed, and its shortcuts, and leaves user data,
  settings, the job database and anything the user put in the install directory in place**, and
  says so on the uninstaller's final page — `DAT-001`, `T322-R1`. `T-039` asserts the halves
  separately: an installed file left behind is a failure; user-owned files — under the user
  directories *or* inside the install directory — surviving byte-for-byte is the intended
  behaviour. *(Said "leftovers under the install root are a failure", which demanded an empty
  directory and so the recursive deletion `T322-R1` removed; `T322-R2`.)*
- **No file associations and no protocol handler** in `0.1.0`. `T-104` (a second launch handing
  its URL to the running instance) is not built, so an association would open a message box
  rather than a download. Recorded here so it is a known omission rather than a surprise.
- **Licence texts installed** alongside the application — `LIC-001`'s artifact obligation, gated
  by `T-323`.

**Inno Setup on `STARBASE`** is a prerequisite, installed by hand once and recorded — a self-hosted
runner must not provision itself as a side effect of a build (`OPS-012` §3, and the `setup-python`
incident it cites).

#### Acceptance criteria

- The installer is built by `T-324`'s workflow from `T-319`'s windowed artifact, and its version
  string matches `__version__`
- A silent install on a clean machine (`T-318`) completes, the Start Menu entry launches the
  application under the real platform plugin, and an uninstall removes every installed file while
  leaving user data **and user-owned files in the install directory** unchanged *(said "leaves
  nothing under the install root"; `T322-R2`)*
- `T-039` is unblocked and its four gates are green on the runner
- The installer's own strings name the application, version and publisher; nothing in them names
  a developer path (`T-323`'s scan covers the tree; this covers the installer)
- If `T-317` chose unsigned: the SmartScreen prompt is screenshot once on the clean machine and
  filed as evidence, so the README's description of it is of the real thing

#### Out of scope

- Upgrade-over-existing and downgrade paths — real, and their own task once `T-320`'s policy
  exists to say what a downgrade even means
- Auto-update

---

### T-301 — Four UI tests break when the application font grows by one point

**Status:** In Progress — **three of the four repaired 2026-09-10**; the fourth is diagnosed and
not fixed, and what was tried is recorded below. *(Found 2026-09-08 while repairing the two that
`ubuntu-latest` broke.)*
**Owner:** Implementer
**Priority:** Low — contained test debt with no user-facing evidence behind it. It is recorded so
the measurement is not lost, not because it blocks anything.
**Phase:** Phase 4 (test infrastructure; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012`'s 2026-09-08 amendment, `tools/bigger_font_plugin.py`,
`tools/dialog_width_floor_probe.py`
**Affected surfaces:** `tests/ui/test_row_verb_wiring.py`, `tests/ui/test_add_dialog.py`
**Risk:** Low
**Required checks:** `ruff check .` · `ruff format --check .` · `pytest tests/ui` at the default
font **and** under `tools/bigger_font_plugin.py`

#### Scope

Four tests fail at one point larger than the default font:

```
tests/ui/test_row_verb_wiring.py::test_the_drawn_verbs_are_where_the_click_is_tested
tests/ui/test_row_verb_wiring.py::test_the_overflow_keeps_its_place_as_the_state_changes
tests/ui/test_row_verb_wiring.py::test_the_verbs_leave_the_message_its_width
tests/ui/test_add_dialog.py::test_the_menu_key_reaches_the_current_rows_menu
```

Three are one cluster — where verbs and the overflow land as a row narrows — and probably share a
cause. Reproduce with `PYTHONPATH=tools python -m pytest -q -p bigger_font_plugin tests/ui`.

#### 2026-09-10 — the cluster of three, and what a larger font actually does

**All three were test debt, and the product was never wrong.** Each invented a row —
`QRect(0, 0, 700, 66)`, sometimes with 100 px carved off the left — which is a row *at one font*.
A point larger and nothing fitted inside it, so `_verb_rects` answered empty and the test failed
for having guessed the geometry rather than for anything the delegate did.

**Re-expressed against the seam the paint itself uses:** `visualRect` for the row and `_verb_area`
for the region reserved in it. The claims are unchanged — verbs inside the row, right to left, not
overlapping, off the first two lines — and now hold at both fonts.

**One of the three also had a literal the comment beside it rejected.** It searched for the width
where two rows both overflow *"rather than writing it down, because a literal here would be a
number that passed on this machine"* — and then bounded the search at `range(24, 200, 2)`. The band
moves with the font, a point larger put it past 200, and the search ran off the end. The ceiling is
now the row's own width.

**So: a larger font does nothing to verb placement**, which is this task's fourth criterion
answered. `tests/ui/test_row_verb_wiring.py` passes in full — 62 tests — at both fonts.

#### The fourth is not fixed, and these are the measurements

`test_the_menu_key_reaches_the_current_rows_menu` still fails its second half at one point larger:
*"with no current row and no row under the point, a menu opened anyway."* Established by probe:

- The current index **is** invalid when the event is sent (`row: -1`).
- The probe point **is** off every row, and still is with a twenty-pixel margin.
- Exactly **one** `QMenu` exists; `_close_menu` hides it and `WA_DeleteOnClose` does **not** destroy
  it. The same object becomes visible again when the next context event reaches the viewport.

So the menu is not built a second time — a hidden popup is re-shown. `AddUrlDialog._show_row_menu`
cannot be the route, since with no valid index it returns before building anything.

**Two fixes were tried and both rejected**, recorded so the next reader does not repeat them:

- **Widening the probe point's margin** from 2 px to 20. The original margin was exactly two pixels
  at the larger font, which looked like a coordinate-space bug between `customContextMenuRequested`
  (list coordinates) and `indexAt` (viewport coordinates). **It is not that** — the failure survives
  the wider margin. The margin is kept anyway: a probe whose correctness depends on a frame width
  being zero is measuring the frame.
- **Forcing the menu's destruction** in `_close_menu` with `setParent(None)` plus `deleteLater`.
  This made the test fail at the **default** font too, so it trades a font-specific failure for an
  unconditional one. Reverted.

**Ruled 2026-09-11: leave it failing and documented.** The font lever is deliberately not wired
into CI — this task's own *Out of scope* says why — so nothing is red anywhere, and the diagnosis
plus both rejected fixes are the record a later reader inherits. **An `xfail` scoped to the lever
was offered and declined**: this task's own criteria forbid loosening an assertion to reach green,
and a marker saying a known failure is expected is that with extra steps.

#### Acceptance criteria

- For each, establish **product or test** by measurement, the way
  `tools/dialog_width_floor_probe.py` established the add-dialog floor. A pixel that moved is not
  by itself a defect, and an assertion that was only ever true at one font is not by itself sound.
- Repair whichever is wrong. **Do not loosen an assertion to reach green** — the two repaired on
  2026-09-08 were re-expressed as the property each was actually protecting.
- Record what a larger font does to verb placement, whichever way it goes.

#### Out of scope

- **Wiring the font lever into CI.** Gating on a standard nobody has established the product meets
  would leave the board red for a known reason, which is what removed the `STARBASE orphans` job.
- The other UI tests. **A 45-failure figure recorded earlier that day was wrong** — the lever that
  produced it did not restore the font between tests, so it compounded a point per test. At a true
  one point the count is four, and every accessibility-sounding test named in that figure passes.

<a id="t-302"></a>

### T-304 — Should a focus ring appear when the control was clicked?

**Status:** Ready — **ruled by the maintainer on 2026-09-09: option (2), the keyboard-only
ring.** The options and their costs are kept below as the reasoning the ruling was made on. The
decision entry recording it is part of this task, since the rule it supersedes has a review
finding and a test for authority and no numbered decision.

**Sequenced by the maintainer on 2026-09-11: not started until Phase 4's exit is approved.** The
build touches every `:focus` selector in `ui/theme.py`, the generated `BORDERED_CONTROLS` ones
included — and a type-and-attribute selector out-specifying a universal pseudo-class one is the
defect behind both `T-303` and `P4EXIT-R1`'s collapse triangle. It would also rewrite the rule
that `test_focus_is_visible_on_every_control_the_application_shows` enforces, which is the test
carrying `P4EXIT-R1`'s evidence while that finding is under verification. The ruling on *what* to
build is unchanged; only *when* is settled here.
**Owner:** Maintainer to rule; Implementer to build
**Priority:** Low — it is a comfort question, not a defect. Raised 2026-09-09: *"I don't
necessarily think that mode should be enabled by default — if you are clicking around with a
mouse all of the highlighted boxes are distracting."*
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** `T-303` should land first, so the ring is correct before its trigger is argued
**Relevant context:** `T202-R1`; `STATE_RULES` in `ui/theme.py`;
`tests/ui/test_colour_is_never_alone.py`; `NFR-005`
**Affected surfaces:** `ui/theme.py`, the application's input handling, and the accessibility tests
**Risk:** Medium — it changes a rule that currently has a test and a recorded rationale

#### The question

Qt shows the focus ring wherever focus lands, including a mouse click, because `QCheckBox` and
friends take `StrongFocus`. The web solved this with `:focus-visible`: ring for keyboard, none for
pointer. **Qt has no native equivalent**, so it would be built — track the last input device and
carry it as a dynamic property the style sheet selects on.

#### What makes it a decision rather than a tweak

The ring is not decoration here. `STATE_RULES` records it as the **geometry** channel for focus,
adopted so that focus reads without colour — *"ink against background, which needs no colour to
read"* — and `tests/ui/test_colour_is_never_alone.py` enforces that every state has a non-colour
channel. **No numbered decision governs it**: its authority is review finding `T202-R1` and the
test. So a ruling here would be the first time this is written down as a decision rather than as
code.

#### Options

1. **Leave it.** Every focus is drawn. Costs nothing, and the maintainer finds it distracting.
2. **Keyboard-only ring (`:focus-visible`).** Mouse focus draws no ring; keyboard focus does.
   Standard on the web and in modern toolkits. **It does not weaken the keyboard case**, which is
   what `NFR-005` and the accessibility pass are about. It does mean a control can hold focus with
   nothing showing it, which matters to a mouse user who then reaches for the keyboard — the
   handover is the case to check, not the steady state.
3. **Keep the ring, reduce it** — thinner, or a lower-contrast hue — for every focus. Keeps one
   code path and one rule; likely fails the contrast floor that made it 2px.

**Recommendation: (2), after `T-303`.** It is what the maintainer asked for, it leaves the
keyboard route untouched, and the objection it must answer — focus invisible until the user
reaches for the keyboard — is testable rather than theoretical.

#### Acceptance criteria

- Whatever is ruled is **recorded as a decision with the maintainer's authority**, since the
  current rule's authority is a review finding and this would supersede it in one direction.
- If (2): pressing a key after clicking reveals the ring on the already-focused control, and that
  handover is asserted by a test rather than described.
- `tests/ui/test_colour_is_never_alone.py` still passes, or is amended deliberately with the
  ruling cited — not adjusted to fit.

## Proposed — Phase 0

## Proposed — Phase 1

## Proposed — Phase 2

### T-121 — The phase-exit clip server aborts connections on hosted Windows

**Status:** **Proposed — narrowed 2026-08-03, and still open.** Two of its three parts are struck
off: the misleading assertion and the missing `ConnectionAbortedError`. What remains is the part
nothing here can reproduce — **why the loopback connection aborts under load on hosted Windows.**
Filed rather than fixed inline (`AGENTS.md` §7): it is not `T-118`'s.

**It is now latent for two independent reasons, and only one of them is about the defect.** It did
not recur in run `30859578131` — which is not the same as resolved (`COORD-R21`) — **and the
configuration it appeared in is no longer exercised at all.** It only ever failed on hosted
`windows-latest`, and that job does not run while `WINDOWS_RUNNER` points at `STARBASE`
(`docs/project/TESTING.md` §10). *Not running the job that found a defect is not evidence about the defect*,
and in six weeks the silence will read as resolution unless this paragraph is here.

The current red on `main` belongs to nothing: `T-122`'s ratio oracle is corrected.
*(This read "it is the only thing red on `main`" until 2026-08-03, which stopped being true the
moment `T-118`'s own scaling gate failed and this test passed.)*
**Owner:** Implementer
**Priority:** Medium — a gate that fails for its own fixture's reasons is a gate that will be
dismissed, which is `T118-R10`'s lesson in a different costume
**Phase:** Phase 2 (its gate), though the defect is in test infrastructure
**Relevant context:** `tests/integration/test_phase_2_exit.py`, its `media_url` fixture,
`tests/network/conftest.py`
**Affected surfaces:** `tests/**`
**Risk:** Low to fix, and it is *not* a production defect

**`test_every_queued_job_eventually_starts_as_slots_free` failed on hosted `windows-latest` while
passing on `STARBASE`.** The assertion reads:

```
0 of 5 jobs were still QUEUED after Add with nothing else done
Final: {'af90cb': 'completed', '660db5': 'completed', '83cc82': 'failed',
        'bdd939': 'completed', '7cbf8e': 'completed'}
```

**Read the numbers before the message.** Zero jobs were still `QUEUED`, so the behaviour the test
exists to prove — that a queue drains with no user action after Add — *held*. Four of five
completed. The fifth **failed**, and the captured stderr says why:

```
ConnectionAbortedError: [WinError 10053] An established connection was aborted
by the software in your host machine
```

That is the test's own `ThreadingHTTPServer` losing a connection to its own client, twice, on the
loopback interface. The predicate demands all five `COMPLETED`, so one aborted download reddens a
test whose subject is admission.

**The message is now misleading, which is the part worth fixing.** It reports the `QUEUED` count
and concludes "nothing admits durable queued intent" — a sentence that is false whenever the count
it prints is zero. A reader who trusts the prose over the dict diagnoses the scheduler.

#### Scope

- Make the fixture server survive an aborted client connection rather than propagating it.
- Distinguish the two failures in the message: *jobs did not start* is the defect this gate exists
  for; *a job started and its download failed* is a different sentence and should say so.
- Neither reproduces on Linux, and it is hosted-Windows-only so far — `STARBASE` ran the same test
  in the same run and passed. Codex separately reported 16 localhost-server tests denied outright
  by its sandbox, so this fixture is fragile in more than one constrained environment.

#### Out of scope

- The download path itself. Nothing here suggests a production defect: the worker did what a
  worker does when a server drops the connection.

#### Corrected 2026-08-03 — the two parts that could be fixed without reproducing it

**The assertion named the wrong defect.** It printed the `QUEUED` count and then concluded
"nothing admits durable queued intent" *whatever that count was*, so a run where every job started
and one download failed reported "0 of 5 still QUEUED" and blamed admission — the one part that was
working. It now branches: a stalled queue says so, and a queue that drained with a failed download
says **that**, and points at the clip server.

**`ConnectionAbortedError` was missing from the handler.** `media_handler` already caught
`BrokenPipeError` and `ConnectionResetError` with the comment *"the expected end of a killed
download: the worker went away mid-stream"* — and `ConnectionAbortedError` is that same condition
on Windows. Its absence is why the abort escaped to `socketserver`, which printed a traceback for a
state two lines of the fixture already called expected. Added in **both** copies: the shared
`media_handler` in `test_end_to_end.py` that `test_phase_2_exit.py` imports, and `test_manager.py`'s
own.

**Neither makes the download succeed**, and neither is claimed to. Swallowing the abort stops the
noise; the connection still died mid-stream and that is what failed the job. Both changes are
improvements a reader can verify without Windows, which is exactly why they were worth doing
separately from the part that needs it.

---

### T-104 — Hand a second launch's URL to the running instance

**Status:** Proposed — **filed 2026-08-01 by `T-087`**, which built the ownership half of `ARC-006`
and deliberately not the attach half.
**Owner:** Implementer
**Priority:** Low — `T-087` satisfies exit criterion 4 and `A-004` by refusing; this is the nicer
half of "attaches **or** refuses"
**Phase:** Phase 2
**Depends on:** `T-087`
**Relevant context:** **`ARC-006`** and its 2026-07-29 amendment, `A-004`, `REQ-001`
**Affected surfaces:** `app.py`, a new channel module
**Risk:** Low — the ownership guard already prevents the harm; this only improves the outcome

#### Scope

`ARC-006` keeps `QLocalServer`/`QLocalSocket` as an **attach channel**, and is explicit that this is
what makes *attach* possible rather than only *refuse*: "a second launch can hand its URL to the
running instance and raise its window. A lock file can only say no."

`T-087` built the ownership lock and stopped there, because the criterion it owns is satisfied by
refusing. Today a user who double-clicks the application a second time — or opens a link with it
while it is running — gets a message box naming the running instance and nothing happens to the URL.

**The channel is started by whoever wins the lock, and never decides who owns the database.** That
separation is the whole point of the amendment and must survive this task: the loser connects to the
channel and hands over; it does not attempt to become a server.

#### Acceptance criteria

- A second launch with a URL passes it to the running instance, which enqueues it, and the second
  process exits reporting that it did so
- The running instance's window is raised and focused
- **A second launch with no URL still raises the window** rather than doing nothing visible
- The channel is started **after** the lock is won, asserted — a channel started first would
  reintroduce the design `P2PLAN-R5` withdrew
- A second launch when the channel is unreachable — the owner is alive but wedged — still refuses
  rather than hanging, within a stated timeout
- Verified on both platforms. **`OPS-005` amended 2026-08-01:** hosted Windows carries the Windows
  gate while `STARBASE` is unreachable, so `check (windows-latest)` satisfies this and the desktop
  slice stays with `STARBASE` for first release
  *(This read "`STARBASE` included" without qualification, which after the amendment demanded a
  machine nobody could reach for a criterion hosted Windows had already met — `T087-R4`.)*: the named-pipe and Unix-socket halves are
  different system calls

#### Out of scope

- Anything that makes the channel decide ownership (`ARC-006` amendment)
- Multi-user or networked access (`A-004`)

---

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data.
*(Premise re-checked 2026-08-06 after `T169-R5`. Still true, and narrower than it was: `0009`
**destroys** data rather than transforming it. That is a different problem with a different answer
— it needs a test proving the rows are gone, which it has, not an allowance for values that
legitimately changed, which is what this task is for. What did move is the strict per-column rule
below: it now covers `jobs` only, because `history` no longer exists to compare.)*
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** unassigned
**Depends on:** the first migration that changes stored values
**Relevant context:** `T014-R4`; `docs/project/TESTING.md` §7 (Migrations)
**Affected surfaces:** `tests/unit/test_persistence.py`

#### Scope

`T-014`'s migration test asserts strict per-column equality **for the tables in
`_MIGRATED_TABLES`**, which since 2026-08-06 means `jobs` alone. That is correct while every
migration either leaves a table's values alone or removes the table outright, and any unasked-for
change is loss. It will be **wrong** the day a migration legitimately transforms values.

**A destructive migration is not the case this task covers**, and `0009` is the reason to say so:
it removes rows on an explicit ruling and proves it with its own regression. This task is about the
opposite situation — values that change and are still correct — where equality has no way to tell a
good transformation from a corrupt one.

A `TRANSFORMED_BY_MIGRATION` allowance was written and then removed: `T014-R4` established that
an allowance can conceal a corrupt-but-readable migration, and an empty allowance protects
nothing while adding a mechanism nobody has exercised. Designing it against a real migration
beats designing it against an imagined one.

#### Acceptance criteria

- The first data migration ships with a test asserting the transformed values are **correct**,
  not merely different — a readable row holding wrong data is the failure mode `T014-R4` named
- Untransformed columns stay under strict equality
- The v1 fixture remains untouched; a new version freezes its own

#### Out of scope

- Any change to `T-014`'s current strict comparison, which is right until then

## Proposed — Phase 3

### T-190 — `docs/UX_SPEC.md` §6 still says its screen is unspecified

**Status:** Proposed — filed by `T-109`, 2026-08-07.
**Owner:** Planner / Documentation Maintainer
**Priority:** Low — no runtime behaviour depends on it; the defect is a current-truth document
stating a solved problem in the present tense, which is `T185-R1` exactly.
**Phase:** Phase 3 cleanup
**Depends on:** `T-109`'s verdict, so the correction describes what was approved rather than what
was submitted.

#### Scope

`docs/UX_SPEC.md` §6 carries a `[T]` clause reading *"This clause stays because `T-109`'s screen has
not been specified against the ruling yet"*, and a `P-16` paragraph asking whether `T-109` and
`T-111` share a screen as though it were open. `UX-007` ruled `P-16`, and the screen now exists:
`ui/options_dialog.py`, reached as `Options…` on the row's format control.

`AGENTS.md` §4 does not put `docs/UX_SPEC.md` in the Implementer's write set, which is why `T-109`
filed this rather than editing it.

#### Acceptance criteria

- §6's open questions read as ruled and built, in the past tense, with the built surface named.
- The `Save as preset…` clause describes the control **as built by `T-109`** (`T109-R5`), rather
  than saying it arrives with `T-111`. `T-111` still owns the other four operations.
- Nothing else in §6 changes: the ruled clauses are the contract the implementation was built
  against.

---

### T-191 — A queued row shows no size until it downloads

**Status:** Proposed — **filed 2026-08-08 by the `T143-R1` amendment**, which deferred pre-download
size here rather than declining it. A criterion cannot be narrowed into nowhere, so this is where it
went.
**Owner:** Implementer
**Priority:** Low — no defect, and no user has reported it. `UX-005` §3 does not promise a size
before a download starts, which is why `T-143` was amended rather than expanded
**Phase:** Phase 4 — polish, and it is a schema change, so it does not belong in a phase that is
exiting
**Depends on:** nothing
**Relevant context:** `T-143`, `T143-R1`, `UX-005` §3, `DAT-001`, `core/models.py` (`Job`,
`FormatInfo.filesize`, `FormatInfo.filesize_is_estimate`), `persistence/` migrations
**Affected surfaces:** `core/models.py`, `persistence/`, `ui/queue_view.py`, a migration
**Risk:** Low in mechanism, **Medium in honesty.** A size shown before a download is a *prediction*,
and `FormatInfo.filesize_is_estimate` exists because yt-dlp's own number is sometimes
`filesize_approx`. A row that states an estimate as a fact is the class of confident lie
`Job.progress` already refuses to tell

#### What is wrong

Nothing, today — and that is why this is Low. **No row of any kind shows a size before it runs.**
A pasted URL and a playlist entry are equally bare, so there is no inconsistency for a user to
notice; there is a field the application could show and does not.

`T-143`'s first acceptance criterion asked for it and could not have delivered it: a size lives
per-format in `FormatInfo.filesize`, and `Job` carries only `bytes_total`, which a *download*
reports. `T143-R1` found the criterion unmet, the maintainer amended it to the `UX-005` §3 anatomy,
and the deferred half is this entry.

#### Scope

Decide whether a queued row shows a predicted size, and if so store it. That means a field on `Job`
populated from the chosen format, a migration for it, and a decision on what the row says when the
number is `filesize_approx` rather than `filesize`.

**The estimate question is the real work.** Storing a number is a morning; deciding what a row says
when the number is a guess is the part that needs a ruling, because `REQ-003` already names the
column *"filesize/estimate"* and `T107-R7` made the two distinguishable for exactly this reason.

#### Acceptance criteria

- A queued row shows the size of the format it will actually download, before it downloads
- An estimated size is **shown as an estimate**, distinguishable from a size the site stated
- A format with no size at all leaves the row saying nothing rather than zero
- The stored size survives a restart, and a re-probe that changes the chosen format updates it
- Changing the format on a row changes the size it shows

#### Out of scope

- Predicting a size for a format the user has not chosen. The row shows what it will download

## Proposed — Phase 4

### T-302 — Nothing detects orphaned workers automatically on either platform

**Status:** Proposed — the gap opened 2026-09-08 and is recorded rather than accepted silently.
**Owner:** Implementer, with the maintainer for where a scan is allowed to run
**Priority:** Medium — process lifecycle and orphaned workers are the first item in
`TESTING.md` §14's standing risk focus, and there is now no automatic signal for either.
**Phase:** Phase 4 (operations; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012` as amended 2026-09-08, `OPS-010`, `docs/RUNNER_ORPHANS.md`,
`tools/orphan_scan.py`, `T-268`, `T-272`
**Affected surfaces:** `tools/orphan_scan.py`, possibly a local hook or schedule; **not**
`.github/workflows/` unless the maintainer rules otherwise
**Risk:** Medium — a detector that runs where orphans do not accumulate is worse than none,
because it reports a clean zero
**Required checks:** whatever the design needs; a **known positive** before any clean result is
trusted (`2026-08-29-orphan-scan-known-positive-soak.md` is the precedent)

#### Scope

`STARBASE orphans` was removed 2026-09-03 because it found `T-268`'s seven preserved specimens
every night and correctly failed, leaving the board permanently red. `Linux orphans` stopped on
2026-09-08 when `LINUX_RUNNER` was deleted and `kirk` and `Spock` were unregistered.

**Restoring either is not the answer, and this task exists because the obvious fix is unavailable.**
A hosted runner's VM is destroyed after every job, so a scan there finds nothing by construction.
Putting a self-hosted Linux runner back would undo the exposure reduction the maintainer chose the
same day.

#### First measurement, 2026-09-09 — not from clean suite runs on this machine

`tools/t302_orphan_accumulation_sampler.sh` ran nine rounds on `Spock` over two hours: a full
`tests/integration` + `tests/ui` pass each round, then two scans, at age 0 and again 90 seconds
later. **Nine suite exits of `0`, nineteen scans, no orphan reported**, with the known positive
passing first so that zero can be read. Rounds 5 to 9 ran alongside a live application session,
which the record treats as a property of the evidence rather than noise.

[The record](evidence/2026-09-09-T302-orphan-accumulation-sampling.md) states its own limits: a
run that exits cleanly is not the route that orphaned `T-268`'s specimens, two hours is not a
distribution, and the scanner only sees a process whose parent died. **So the first criterion is
answered by elimination rather than satisfied**, and the remaining candidate is a session that
ends badly — the shape `2026-08-27-T212-ytdlp-update-double-free.md` recorded.

#### Acceptance criteria

- Establish **where orphans actually accumulate now** that Linux CI is ephemeral. The working
  assumption was a developer's own machine; the 2026-09-09 sampling rules out clean suite runs on
  one, and the next measurement belongs on a session that ends badly rather than on more rounds of
  the same.
- Propose a detector that runs there — a pre-push hook, a periodic local run, or a documented
  manual step — and say plainly what it does **not** cover.
- **Prove it sees a known positive before any clean result is reported.** A blind scan prints the
  zero the author wanted.
- Do not reintroduce a nightly job that fails on known specimens; that is the shape `2026-09-03`
  removed.

#### Out of scope

- Reversing the runner move.
- `T-268`'s seven preserved specimens, which remain its own.

## Proposed — Phase 4.5

### T-184 — The escape hatch: additional yt-dlp options, parsed and bounded

**Status:** Proposed — filed 2026-08-07 with the phase. **Unblocked 2026-08-21**: `SEC-005` ruled
`--legacy-server-connect`, the one disposition this waited on (`T183-R3`, the sixteenth option the
audit surfaced), and **`unruled` is now 0** — every documented option has a class, which is the
condition a final refusal list needs. The three `SEC-003` corrections `T-256` also carried were
non-blocking and were ruled the same day; two of them **add** to this list. `T-183` delivered the
classification and `SEC-004` ruled the original fifteen forbidden, so the refusal list is the
audit's `app:sets` + `app:contained` + `app:plumbing` + **`app:policy`** + `excluded` classes —
**92 documented options**, up from 89 by `--legacy-server-connect`, `--netrc-cmd` and
`--client-certificate-password`. **Nothing in this phase starts before Phase 4 exits**, so this is
unblocked rather than startable.

**`Depends on:` is satisfied rather than removed.** `T-256` is still In Review; what it owed this
task is taken, and a reviewer disposing `T-256` differently would reach this line.

**The refusal list is 92 and this entry gave two numbers** (`T256-R2`). Its `Depends on:` line still
carried the pre-ruling **89**, so an implementer could read both the three newly refused options and
the old list that omits them — from the same entry. **92 is the live figure**, and 89 survives below
only inside the struck dependency, as what it was.

*(**This entry said "both blockers are cleared", "nothing outstanding" and "79 documented options",
and required a destination-keyed refusal, after `T183-R1`…`R5` had changed all four.** The
re-review found it: correcting the audit and leaving the task that consumes it is how an
implementer follows a specification the audit no longer holds — and it would have refused a safe
normalized value as though it were the `SEC-003` bypass.)*
**Owner:** Implementer
**Priority:** High within the phase — it is what makes `REQ-030` true before the typed fields exist
**Phase:** Phase 4.5
**Depends on:** ~~**`T-256`** — **one** unruled option, `--legacy-server-connect`~~ — **satisfied
2026-08-21 by `SEC-005`**. *(This said "sixteen unruled options and three `SEC-003` corrections"; fifteen were ruled by `SEC-004` and the three corrections are explicitly non-blocking — `T183-F1`.)* `T-183` delivered the classification, `SEC-004` ruled the original fifteen and `SEC-005` the sixteenth, with `SEC-003`'s amendment withdrawing two permissions; the refusal list is **92 documented options** across five refused classes, in `docs/YTDLP_OPTION_AUDIT.md`. *(This line said **89** while the status above said 92, so one entry gave both the pre-ruling and post-ruling list to whoever builds it — `T256-R2`.)* *(It also waited on `T-182`, which ruled on 2026-08-07: the refusal list starts with `-u`, `-p`, `--video-password`, `--impersonate`, `--xff`, `--exec` and `--exec-before-download` — `SEC-003`.)*

> **Four of `T-183`'s findings land here, and the first changes the design.**
>
>
> - **Finding 4 — the refusal list keys on the normalized value `parse_options` produces**, not on
>   the option string and **not on the `dest`**. Three suppressed spellings — `--geo-bypass`,
>   `--geo-bypass-country`, `--geo-bypass-ip-block` — reach the value `SEC-003` forbids under the
>   name `--xff`, so a list of strings enforces `REQ-EXCL-002` against one spelling in four. **But
>   `--no-geo-bypass` shares that same `dest` and normalizes to the value that *disables* the
>   bypass**, so keying on `dest` refuses a safe input. Run the candidate through `parse_options`
>   and refuse on what comes out. The refusal still names the string the user typed, because that
>   is where it is stated.
>
>   *(This bullet required destination-keying until `T183-R1`'s re-review. It was the audit's
>   original conclusion and it was wrong in the direction that looks safe.)*
> - **Finding 4, second half — decide the whole parser, not the documented part.** 36 suppressed
>   options have a `dest` no documented option has, so keying on `dest` does not reach them either.
>   Two are the forbidden family outright (`--exec-before-download`, `--no-exec-before-download`).
> - **Finding 6 — `--write-thumbnail` shares `writethumbnail` with the application.** It is the one
>   place a typed control has to share a key rather than own it; `T-249` owns the tri-state and the
>   merge rule is this task's.
> - **Finding 7 — five hatch options touch `T-046`'s reservation, unmeasured.** `--continue`,
>   `--no-continue`, `--part`, `--no-part` and `--post-overwrites` all change how yt-dlp treats a
>   file already at the target path, and the download session leaves a zero-byte reservation there.
**Relevant context:** `REQ-031`, `ARC-010`, `REQ-009` (the pattern), `T-034` (path containment),
`DAT-003` and `DAT-004` (redaction, and whose text this is), `ARCHITECTURE.md` §8 (a request is
frozen at job-creation time), `ARC-002` (it crosses a process boundary and must pickle),
`core/models.DownloadRequest`, `downloader/ytdlp_adapter.build_options`
**Affected surfaces:** `core/models.py`, `core/presets.py`, `downloader/ytdlp_adapter.py`,
`persistence/` (the request gains a field, so a migration), the preset/options UI, and their tests
**Risk:** **High.** It is a new route to two boundaries whose breach is Critical-band: writing
outside the chosen directory, and a secret in a log

#### Scope

An *Additional yt-dlp options* field, per preset and overridable per job, taking command-line
syntax, **parsed into a validated structure at job-creation time** and merged into `build_options`
under a stated precedence.

- **Parsed, not passed through.** The stored field is declared, typed, frozen and picklable like
  every other member of `DownloadRequest`; an unparsed string handed to yt-dlp is not acceptable
  even as an intermediate step
- **Containment.** Options that redirect where files land go through `T-034`'s check, not beside it
- **Redaction.** Values are this application's text under `DAT-004` and are redacted as such
- **Refusal.** An application-owned or excluded option is refused **where the user typed it, with
  the reason** — never accepted and dropped
- **Precedence.** A typed field wins over the hatch for the same user-owned key, because it is the
  one with a visible control; an application-owned key is never overridable at all

#### Acceptance criteria

- A valid option typed into the field reaches yt-dlp, proved by the option dictionary the worker
  receives rather than by the download succeeding
- **The same intent expressed as a typed field and as a hatch option produces the same option
  dictionary** — the assertion that keeps two routes from meaning two things
- An option that would write outside the output directory is **refused or contained**, with a test
  that fails when the containment call is removed
- **No hatch value appears unredacted in any log**, under the existing redaction test extended over
  the parsed values — including the case where the option name is innocuous and the value is not
- An application-owned option and an excluded option are each refused at edit time with a stated
  reason, and a test asserts they never reach `build_options`
- A malformed field fails **at edit time**, not after the bytes are spent — the same rule
  `audio_quality` already follows and for the same reason
- The migration adding the field round-trips an existing queue, and an old row without it loads
- `requires_ffmpeg` still answers correctly for a post-processor the hatch installed
- Both mypy platforms, `ruff`, the model, adapter, persistence and UI tests are clean
- **The refusal list is keyed on the value `parse_options` produces**, and a test asserts that
  `--geo-bypass` is refused for the same reason `--xff` is **while `--no-geo-bypass` is not refused
  as a bypass** — it fails if the list is rebuilt on option strings *or* on destinations (Finding 4,
  as corrected by `T183-R1`)
- **All five refused classes are enforced**, `app:policy` included. It is 10 rows the application
  owns by behaviour rather than by setting a key, and a refusal list built from the other four
  omits every one of them
- **`--break-on-existing` and `--break-per-input` are measured, not assumed inert.** At the pin
  `_match_entry` can raise on the current item and this worker calls `extract_info` directly rather
  than through `YoutubeDL.download`, so the option can turn the current job into a failure. Keep
  them hatch-reachable only if that effect is visible to the user
- **Every option the parser accepts is dispositioned, suppressed ones included.** A test walks
  `create_parser()` and fails on an option that is neither refused, nor typed, nor hatch-reachable
  — the documented 250 are not the parser's whole surface
- **`--continue`, `--no-continue`, `--part`, `--no-part` and `--post-overwrites` are measured
  against `T-046`'s reservation**, not reasoned about: a test shows what each does to a job whose
  target path already holds the zero-byte exclusive-create file (Finding 7)
- **The `writethumbnail` merge is stated and tested** — the application sets it to embed and delete,
  `T-249`'s control sets it to keep, and one of them has to win by a written rule (Finding 6)

#### Out of scope

- Typed fields for individual options — those are `T-183`'s tasks
- yt-dlp **configuration files** as an input route. A config file is a second, invisible source of
  options and would defeat every check above; if it is ever wanted it needs its own decision
- Per-entry hatch options within a playlist — `T-110` owns per-entry anything

---

*(**The nine typed-field tasks, `T-247` … `T-255`**, filed 2026-08-16 by `T-183`, which is where
the option lists come from: `docs/YTDLP_OPTION_AUDIT.md`. **44 options over nine tasks** — the
typed class minus the 21 that already have a `DownloadRequest` field. Counted, and
`tests/unit/test_option_audit.py` asserts the partition, so a task that quietly grows or drops an
option fails a gate.)*

**The following is true of all nine.** Each still states its own `**Status:**`, because `T-096`'s
gate reads that line per entry and a shared one would exempt nine tasks from the check that six
review rounds exist to enforce:

- **Owner:** Implementer · **Phase:** Phase 4.5, filed 2026-08-16
- **Depends on:** `T-183` approved. **Not on `T-184`** — a typed field is a declared member of
  `DownloadRequest` and needs nothing from the hatch. Nine independent tasks, in any order
- **Relevant context:** `ARC-010` §1, `REQ-030`, `docs/YTDLP_OPTION_AUDIT.md`,
  `core/models.DownloadRequest`, `core/presets.py`, `downloader/ytdlp_adapter.build_options`
- **Affected surfaces:** `core/models.py`, `downloader/ytdlp_adapter.py`, `persistence/` (each new
  field is a migration), the preset and options UI, and their tests
- **Acceptance criteria, common to all nine.** Each option below becomes a declared, typed,
  validated, frozen and picklable member of `DownloadRequest` (`ARC-002`, `ARCHITECTURE.md` §8);
  **the value is proved to arrive by asserting on the option dictionary the worker receives**, not
  by the download succeeding — `T-012` produced five defects that were values computed correctly
  and then not acted on, and `T012-R5` two more where yt-dlp accepted a key and ignored it; a
  malformed value fails **at edit time**; the migration round-trips an existing queue and an old
  row without the field loads; every control is keyboard-reachable and screen-reader-labelled
  (`NFR-005`); `ruff`, both mypy platforms and the touched suites are clean
- **Risk:** Medium for all nine — breadth rather than depth, and `NFR-008`'s churn lands on each

### T-247 — Video selection: which items, how big, how old

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** High among the nine — playlist item selection is the most-asked-for of the 44
**Options (7):** `-I/--playlist-items`, `--min-filesize`, `--max-filesize`, `--date`,
`--datebefore`, `--dateafter`, `--max-downloads`
**Specific criteria:** `-I`'s range grammar is parsed and refused at edit time, not handed to
yt-dlp as a string; the three date options accept yt-dlp's own relative forms (`today-2weeks`) or
refuse them with the reason; `--max-downloads` interacts with the queue's own counting and the
interaction is asserted rather than assumed.

### T-248 — Filename shaping and the modification time

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--restrict-filenames`, `--no-restrict-filenames`, `--windows-filenames`,
`--no-windows-filenames`, `--trim-filenames`, `--mtime`, `--no-mtime`
**Specific criteria:** **`T-034`'s containment check runs after these, not before.** All three
filename options change what yt-dlp writes, and `--trim-filenames` can shorten a name into a
collision; the containment and collision tests are extended over each, and a test fails when the
check is removed. `--windows-filenames` is asserted on **both** platforms — its whole purpose is a
platform difference, and a Linux-only assertion proves nothing about it.

### T-249 — The sidecar writers: description, info JSON and thumbnail files

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--write-description`, `--no-write-description`, `--write-info-json`,
`--no-write-info-json`, `--write-thumbnail`, `--no-write-thumbnail`, `--write-all-thumbnails`
**Specific criteria:** every file these write lands inside the chosen directory, through `T-034`
rather than beside it. **`--write-thumbnail` shares `writethumbnail` with the application**
(`T-183` Finding 6): `build_options` sets it to embed and then delete, this control sets it to
keep, and the resolution is one written rule with a test — the control is tri-state (off, one,
all). **`--write-info-json` writes a file yt-dlp's own help calls personal information**, so
`DAT-003`'s redaction question is asked of it before it ships, not after.

### T-250 — Format depth: sorting, checking and the merge container

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-S/--format-sort`, `--check-formats`, `--no-check-formats`,
`--merge-output-format`
**Specific criteria:** `--format-sort`'s field grammar is validated against yt-dlp's own accepted
fields rather than passed through; `--check-formats` costs a request per format and the format
table's probe budget is stated (`T-161`'s per-entry lesson); `--merge-output-format` and
`remux_container` are two ways to name a container and the precedence between them is written down.

### T-251 — Subtitle depth: automatic captions, format and conversion

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `--write-auto-subs`, `--no-write-auto-subs`, `--sub-format`, `--convert-subs`
**Specific criteria:** `--convert-subs` installs an ffmpeg post-processor, so `requires_ffmpeg`
answers true for it and the user is told **before** the bytes are spent (`REQ-024`); automatic
captions and real subtitles are distinguishable in the UI, because "no subtitles" and "no *human*
subtitles" are different answers.

### T-252 — Download tuning and the retry policy the settings screen shows

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `-N/--concurrent-fragments`, `--fragment-retries`, `--extractor-retries`,
`--socket-timeout`, `--download-sections`, `--live-from-start`, `--no-live-from-start`
**Specific criteria:** **the three retry knobs this task owns are presented as one policy**, not
three integers — and the entry no longer calls them *the whole* retry policy, because
`--file-access-retries` and `--retry-sleep` stay in the hatch (`T183-R4`'s wording point) —
`--retries` already exists and `ytdlp_adapter` carries a comment deferring `--fragment-retries`
here by name, so this task is where the difference between them stops needing a comment to explain.
`--download-sections` takes a time-range grammar that is parsed and refused at edit time.
`-N` interacts with the pool's own concurrency (`ARC-007`, `CONCURRENCY_MAXIMUM = 16`) and the
interaction is measured rather than assumed.

### T-253 — Network reachability: address family and politeness delays

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-4/--force-ipv4`, `-6/--force-ipv6`, `--sleep-interval`, `--max-sleep-interval`
**Specific criteria:** `-4` and `-6` share yt-dlp's `source_address` and are mutually exclusive —
`DownloadRequest` makes that unrepresentable rather than validating it; `--max-sleep-interval` is
refused without `--sleep-interval`, which is yt-dlp's own rule, and it is refused at edit time.

### T-254 — SponsorBlock, opt-in per preset

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (3):** `--sponsorblock-mark`, `--sponsorblock-remove`, `--no-sponsorblock`
**Specific criteria:** **off by default, and the control says what enabling it sends.** `SEC-003`
permitted this and `NFR-007` was amended to name SponsorBlock as a third permitted destination
*conditional on the user enabling it*; a test asserts no SponsorBlock request leaves the process
while the option is off. The category lists are validated against yt-dlp's own. `--sponsorblock-api`
is **excluded** — `SEC-003` declined a configurable endpoint — and this task does not reopen it.

### T-255 — Per-extractor arguments

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** Lowest among the nine — one option, and the most expert-facing of the 44
**Options (1):** `--extractor-args`
**Specific criteria:** the `IE_KEY:ARGS` grammar is parsed into a validated structure, never stored
as the string the user typed; an unknown extractor key is refused **with the reason** rather than
accepted and ignored, which is `T012-R5`'s defect exactly; values are redacted under `DAT-004` like
any other text this application supplies, because an extractor argument can carry a token.

## Proposed — Phase 5

*Created 2026-09-10, when Phase 4.5 was resequenced to follow the first release and this
phase became the next one to run. `T-039` also carries `**Phase:** Phase 5` and stays under
`## Blocked`, because that section is about status rather than phase.*

### T-328 — The first release

**Status:** Proposed — filed 2026-09-11 with the Phase 5 plan. **This is the phase exit.**
**Owner:** Reviewer runs the release review; Maintainer tags and publishes
**Priority:** High
**Phase:** Phase 5
**Depends on:** every task above, `T-039` *(and `T-212`, cancelled 2026-09-13)*
**Relevant context:** `docs/RELEASE.md`'s release review; `TESTING.md` §8 in full; §14
(one initial review plus one focused pass, and *"a red canary is not a reason to skip the bump"*);
`DOC-002` (`CHANGELOG.md` at the first tag); `IMPLEMENTATION_PLAN.md` §Phase 5 exit criteria;
§Phase 4.5's resequencing note (**no parity claim**)
**Affected surfaces:** a release review record; `CHANGELOG.md`; `SECURITY.md` §Supported
versions; the tag `v0.1.0`; the GitHub Release
**Risk:** Medium — the first release is the one with no previous release to compare against, so
every gate is being exercised for the first time at once

#### Scope

1. **Freeze the candidate**: the release commit sets `__version__ = "0.1.0"`, creates
   `CHANGELOG.md` with a `0.1.0` section, fills `SECURITY.md` §Supported versions, and is tagged
   `v0.1.0`. `T-324` drafts the release.
2. **The release review**, per `docs/RELEASE.md`: `TESTING.md` §8 item by item, on both
   platforms, each with its evidence — `T-323`'s gates, `T-325`'s numbers, `T-326`'s runs,
   `T-318`'s clean-machine files, `T-327`'s session — and **§8 item 6, the `REQUIREMENTS.md` §11
   acceptance criteria verified by hand and recorded here**, since `T-212` was cancelled
   2026-09-13. Recorded in a review record
   indexed by `REVIEWS.md`. Its verdict is the phase's.
3. **Publish**: the draft becomes public by the maintainer's hand. The README's install section
   goes live in the same push — and, **by the maintainer's ruling of 2026-09-13**, it says the
   AppImage runs as it is, and that a menu entry comes from AppImageLauncher or Gear Lever or from
   the two lines it gives. The `.desktop` inside the bundle points inside the bundle, so it cannot
   serve as one (`T-321`).
4. **Reopen `main`**: `__version__` bumps to `0.1.1.dev0`; `IMPLEMENTATION_PLAN.md` marks Phase 5
   exited and Phase 4.5 as next; `STATUS.md` says there is a release.

**What the release notes must not say**: that this application reaches everything yt-dlp does.
`REQ-030` is unmet by design until Phase 4.5, and `REQ-031`'s escape hatch is the first thing
scheduled there. The notes say what *is* covered, and that the rest is coming as an update.

#### Acceptance criteria

- Every §8 item has evidence in the review record, or is marked `N/A` with the reason (item 5,
  item 10a) — none marked passed on a green CI run alone
- The published release carries both artifacts, `SHA256SUMS`, and notes that make no parity claim
- `IMPLEMENTATION_PLAN.md` §Phase 5 records the exit with the review's verdict and date
- `OPS-005`'s rule is applied to the four Windows-only diagnostic tasks reassigned here
  (`T-074`, `T-092`, `T-068`, `T-056`): each gets an explicit disposition — carried or closed —
  rather than silently outliving the release they were said to matter for

#### Out of scope

- Anything Phase 4.5 owns. The release ships without it, on the maintainer's 2026-09-10 ruling

## Blocked

### T-336 — The installed app crashed once with heap corruption opening *Naming and folders…*

**Status:** **Blocked — on a recurrence that carries a dump.** Seen once, 2026-09-13, in `T-327`'s
Sandbox session; not reproduced since by any route below. Filed the same day.
**Owner:** Implementer
**Priority:** High if it recurs; Medium while it does not — a crash is Critical by `TESTING.md` §14,
and one that cannot be reproduced cannot be ranked by its frequency
**Phase:** Phase 5
**Depends on:** a recurrence under crash capture
**Relevant context:** `T-289` (a Qt widget destroyed on the wrong thread — a double free); `T-074`
(an access violation never reproduced, and why repetition alone does not discriminate); `T-092`
(crash dumps on `STARBASE`)
**Affected surfaces:** unknown until a dump names them

#### What happened

The maintainer, in the installed build in Windows Sandbox: pasted
`https://www.youtube.com/watch?v=NnPvX-uMYWk` into Add URLs, waited for it to be read, opened the
row's ⋮ and chose *Naming and folders…*; the application closed. Windows recorded:

- `Application Error`: `tracks-and-trails.exe` 0.1.0.0, faulting module `ntdll.dll`
  10.0.19041.6456, **exception `0xc0000374` (heap corruption)**, offset `0xff489`, 16:30:01.
- The application log ends at 16:29:47, mid-probe of the same URL, which had also been probed at
  16:24:47 in the same session — so the dialog saw that URL twice. Nothing after: a native fault
  writes no Python record.

**Heap corruption is reported where the heap is next checked, not where it was damaged.** The menu
choice is where the process died; it is not established as the cause.

#### Not reproduced, by

- The same flow from source on `STARBASE` under the real Windows plugin — real probe, the ⋮ zone
  and the menu entry clicked through `QTest`, the maintainer's own URL, and with the dialog closed
  and reopened between two reads of it: **eight runs, no crash**.
- The output-path preview the panel opens with, under `pythonw.exe` (no console, as installed): clean.
- The 17 add-dialog tests touching the panel and the menu, under the real plugin: pass.
- The maintainer, in Sandbox: the installer built before that day's later changes (`d1e03e2`) and
  the current one (`e037c05`) — **no crash with either**; no dump was produced.

#### To capture it

Kept on `STARBASE`, not in the repository: `C:\dev\interactive-dumps.wsb` (the interactive Sandbox
plus a writable `C:\dev\sandbox-out`) and `sandbox-share\arm-crash-capture.ps1`, which turns on
full page heap for `tracks-and-trails.exe` — so a double free or overrun faults at the write that
does it — and WER full dumps into that folder. WinDbg is installed on `STARBASE` to read one.

#### Acceptance criteria

- [ ] A dump of a recurrence, with the faulting module and stack read
- [ ] The cause named, fixed, and a test that fails without the fix — or, if it never recurs, a
      recorded ruling on how long to wait (`T-074`'s repetition-budget lesson)

---

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Blocked — on `T-092`, 2026-08-20. Still undiagnosed, still not blocking Phase 1**
(`OPS-007`, maintainer risk decision 2026-07-29). Downgraded **High → Medium**.

**The dependency was always there; the entry just never said it.** This task's own text already
concluded that only a **recurrence carrying a dump** can supply criterion 2 — *a stack is not a
cause* — and arming `STARBASE` to capture that dump **is** `T-092`. Meanwhile `Depends on:` read
*"nothing"* and the entry sat under `## Ready`, which asserts somebody can pick it up and make
progress. **Nobody can.** Repetition is spent at **466 attempts** — this entry's 361 plus the 105
full-suite Windows runs counted on 2026-08-20, which are more of the same shape rather than a new
one — and the one plan that remained — accumulating clean Windows runs — was measured on 2026-08-20 and
**cannot discriminate**, because the pre-fix sample is equally clean.

**What this changes is the board, not the risk.** The residual `OPS-007` accepted is unchanged and
still accepted; the four criteria are still deliberately not rewritten; and **the detection is in
the code rather than in this entry** — a recurrence turns the `windows desktop` job red whether or
not anybody is holding this task open. What moves is the honest label: this is waiting on a
machine being armed, which is `T-092`, which is waiting on a person.

*(Filed as a correction rather than a re-triage: nothing about the defect changed on 2026-08-20.
What changed is that the last avenue this entry proposed was tried and recorded as insufficient,
which left `Ready` claiming work that does not exist.)* The faulting object of the access violation is
unknown, product-versus-harness is unresolved, and the crash has never been reproduced: the
recorded **0 in 36** deliberate full-suite runs, plus **0/15 at `35fc7ec`** (run `30478557533`,
post-`T-090`) — **51 full-suite runs** in total, with 60 clean runs of the crashing test and 250
clean in-process iterations beside them. **361 attempts, zero events**, across three shapes and two
heads.

**`T-128` is diagnosed as of 2026-08-04, and it was a *harness* defect** — a fixture teardown
dropping a `QObject` that still owned a running `QTimer`, so the dispatcher followed a pointer into
freed memory. Two core dumps and a sub-second reproduction establish it; `src/` is not implicated,
because nothing there reads `is_idle` and the application holds one manager for the life of the
process.

**The free-evidence strategy below was tried on 2026-08-20 and it does not work. The runs were
gathered; what they cannot do is discriminate.** Measured rather than assumed: **105 completed
full-suite Windows runs** on `STARBASE` between 2026-08-04 and 2026-08-20, **zero native crashes**.
Method, so it can be re-run: every `CI` run since the `T-128` teardown fix at `bd4dde8`, taking the
`windows desktop` job's **`Full suite` step conclusion** rather than the job's — 92 `success` plus
**13 `failure`**, and the 13 count because each one **ran to completion with an ordinary pytest
tally**, which a process death cannot produce. 22 `cancelled` and 14 `skipped` are excluded because
the suite did not finish; the 14 are `T-270`'s window, where the step never ran. **Four of the 145
runs are accounted for separately and were not in the first telling of this** (`T074-R5`): they have
no `windows desktop` job at all — `31080589319`, `31120246285`, `31956224066` cancelled, and
`32042191296` failed before it. 92 + 13 + 22 + 14 + 4 = **145**, and none of the four is a completed
run, so the 105 is unchanged.

**Why that settles nothing, and it is this task's own arithmetic that says so.** The pre-fix sample
was **0 events in 51 full-suite runs**. The post-fix sample is **0 events in 105**. *"If the crash
stops recurring"* cannot be observed as a change, **because it had already stopped recurring before
the fix landed** — there is no measured pre-fix rate to beat, so the comparison is undefined.

**What the 105 buys is a dated zero and nothing more, and the first version of this paragraph
claimed more** (`T074-R5`). It gave a rule-of-three **2.9% per-run ceiling**, which assumes
exchangeable trials sharing one underlying probability. **These runs do not share one.** They span
sixteen days and many heads: between `bd4dde8` and `06745fa` the manager and test-lifecycle
surfaces alone move by **2 886 insertions and 622 deletions**. **`T074-R1` had already ruled exactly
this** — samples from materially different heads are not one population, and it required exact-head
observations rather than a rate. *A rate quoted over a changing tree is the same error as a rate
quoted from four observations on different heads*, which is the sentence this entry has carried
since `T074-R1` and which I re-made from the other direction.

**The observation and the non-discrimination argument both stand**; only the ceiling is withdrawn.
Neither `OPS-007`'s accepted residual nor the Blocked-on-`T-092` disposition ever rested on it.

**This is `T238-R2`'s ruling arriving at a second task, and neither entry saw it coming.** That
finding replaced `T-238`'s criterion 6 because *"a larger clean sample cannot distinguish **the
guard worked** from **the crash was always this rare**"*. **The sentence transfers verbatim**: swap
*guard* for *corrected teardown* and it is the paragraph below. Two tasks proposed the same
instrument against the same class of defect, and one of them had already had it ruled out.

**So what would actually move this is `T-092`, and nothing cheaper.** Clean runs cannot supply
criterion 2; only a **recurrence with a dump** can, which is what `T-092` arms `STARBASE` to
capture. Until then the honest position is unchanged: the residual is accepted under `OPS-007`, and
**the accumulating-runs plan is recorded as tried and insufficient rather than left open as
available**.

*(The paragraph below proposed that plan and is kept, because it is what was tried. It was
reasonable when written — what it missed is that its own Status paragraph already recorded the
pre-fix sample as clean, which is the fact that makes it unable to discriminate.)*

**That is a lead here, and it is the strongest one this task has ever had.** The Windows crash
recorded above happened in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — **the same file and the
same `manager` fixture** whose teardown `T-128` found at fault, with the same `ResultPump` thread
alive in the traceback. The corrected teardown is now on both platforms.

**It is still not established as the same defect, and the bar has not moved.** Windows produced an
access violation and `T-128` a SIGSEGV; this task's faulting object was never determined, so there
is still nothing to compare against; and *a stack is not a cause* — this task's own words, which
apply to the resemblance as much as to the stack. What can be done now is cheap and was not before:
**`STARBASE` runs the full suite on every push (`OPS-010`), so repeated green Windows runs against
the corrected teardown are evidence that costs nothing extra to gather.** If the crash stops
recurring there over a meaningful number of runs, that is the first positive evidence this task has
had; if it recurs, the harness fix is ruled out as its cause and that is worth just as much.

*(This block read "A candidate reproduction exists … `T-128` owns finding out". `T-128` has now
found out, and what it found does not implicate the product.)*

**The four acceptance criteria below stay unmet, deliberately not rewritten.** All four presuppose
a deliberate reproduction, which is the one thing no instrument has produced, so `OPS-007` accepts
the residual rather than redefining the bar. `T-092` arms `STARBASE` to capture a crash dump so a
recurrence supplies criterion 2 — *a stack is not a cause* — instead of another anecdote.

*(This read "Ready — still undiagnosed and still blocking Phase 1" until `OPS-007`. Before that it
read "In Review — diagnosed and fixed", which `T074-R4` found unsupported; what was fixed is
`T-090`, and `T-090` is **not** established as this crash's cause — the pre-fix sample was equally
clean, so a clean post-fix run carries no causal weight.)*

**A separate defect was found on the way and is `T-090`.** The `T-038` log listener could be left
reading a queue that something else had closed — a real race on the same thread the crash
traceback names, now fixed with tests. **That is not this task.** Calling it "diagnosed and fixed"
claimed a causal link to the historical access violation that no evidence supports, which is what
`T074-R4` reports. This task's acceptance criteria remain unmet.

*(Superseded, and worth keeping: this block read "diagnosed and fixed" on 2026-07-29. Finding a
real defect near a crash is not the same as finding the crash's cause, and the wording did not
keep them apart.)*
`0/12 at ea53c71` (run `30429327464`). That is evidence against the original 25% anecdote and is
**not** a rate: the four original observations came from materially different heads, so they are
not one population, and a single event gives no bound worth quoting (`T074-R1`). The faulting
object is unknown, product-pump versus harness is unresolved, and there is no correction mutation.
**Phase 1's Windows criterion stays unverified.** *(This block claimed "1 in 16, not 1 in 4"; that
promoted samples from changed heads into a stable rate.)*
**Owner:** Implementer
**Priority:** **Medium** — downgraded from High by `OPS-007`. It is still an access violation in a
module under `src/`, in the suite `OPS-005` and `T-073` made Phase 1's only Windows gate; what
changed is that 361 attempts produced no reproduction, so there is no work left that repetition can
do. It returns to High the moment it recurs
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
**Depends on:** **`T-092`** — which is itself Blocked on somebody at `STARBASE`. The Windows
runner exists; what does not exist is a configured crash dump, and without one a recurrence
produces another anecdote rather than criterion 2
**Relevant context:** `T-073`, `OPS-005`, `ARC-002`, `src/tracks_and_trails/downloader/result_pump.py`
**Affected surfaces:** unknown — `downloader/result_pump.py` and/or
`tests/integration/test_manager.py`
**Risk:** **High to leave.** An intermittent crash makes every green Windows run mean less than it
appears to

#### Scope

The full suite on `STARBASE` died with exit **139**:

```
tests/integration/test_manager.py::test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Windows fatal exception: access violation
Thread 0x00000c88 [ResultPump] (most recent call first):
Thread 0x000024dc [Thread-50 (_monitor)] (most recent call first):
  File "...\tests\integration\test_manager.py", line 1028 in
    test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Segmentation fault
```

**It is intermittent, and the evidence for that is unusually clean.** The failing run was
`30416495270` at `454b80e` — a **documentation-only** commit whose code is byte-identical to
`38650dd`, which had passed the same suite minutes earlier.

| Run | Head | Full suite |
|---|---|---|
| `30415333608` | `c41e2ef` | pass |
| `30416156751` | `38650dd` | pass |
| `30416495270` | `454b80e` | **access violation** |
| `30416723791` | `32f9bd2` | pass |

**One in four**, with no code difference between a pass and the failure.

**Line 1028 is before the cancellation**, which narrows this usefully. It is
`assert spin(lambda: bool(recorder.progress), timeout=60)` — the wait for the *first progress
message*, three lines above `download.cancel()`. So the crash is not in the escalation path the
test is named for. It is in ordinary message delivery: `ResultPump` is a `QThread` emitting Qt
signals carrying Python objects from its `run()`, while the main thread sits in `spin()` calling
`app.processEvents()`.

#### What is not known

Everything about the cause. Recorded as a question rather than a hypothesis dressed as one:

- Whether the fault is in **product code** (`result_pump.py`, in `src/`, so `ARC-002`'s pump is a
  candidate) or in the **test harness** (fixture teardown ordering, a receiver outliving or
  predeceasing a queued emission).
- Whether it is specific to `child_ignoring_cancellation`, which is the one worker in the suite
  that deliberately refuses to stop, or reachable by any job.
- Whether it reproduces at all outside `STARBASE`. It has never been seen on Linux across many
  full-suite runs, but Linux has never been where this project's process faults show up.

#### Diagnostic progress, 2026-07-29 — two things narrowed, cause still unknown

**It does not reproduce on Linux.** Two attempts, both clean:

| Attempt | Result |
|---|---|
| The crashing test alone, 40 iterations | **40 passed, 0 non-zero exits** |
| `tests/integration/test_manager.py` entire, 5 runs | **5 × 71 passed**, no crash, no fatal exception |

That is a negative result and is worth exactly what a negative result is worth. It does **not**
clear Linux: `T-069` was ordering-dependent and failed only when one specific test ran first, and
the Windows crash happened inside a full-suite run, not a module run. What it does establish is
that the fault is not reachable by simple repetition of the failing test on this platform, so
whatever it is depends on the platform, on suite-wide ordering, or on both.

**The most obvious cause is already defended against, and this is the more useful half.** The
classic PySide6 access violation of this shape is a `QThread` object being destroyed while its
`run()` is still executing — and `ResultPump` emits `session_ended` from *inside* `run()`, so a
slot that dropped the last reference would do exactly that. It cannot: `_release()` in
`manager.py` refuses to drop a session while its pump is live —

```python
if session.pump_started and not (session.pump_finished or session.pump.isFinished()):
    return
```

— and `_sessions.pop()` is the only thing holding the pump. `_Session` even documents the two
moments as distinct: "the thread emits `session_ended` from inside `run()`." So the first
hypothesis anyone would reach for is not it, which is worth recording so nobody spends the
afternoon re-deriving it.

**Still open.** The crash traceback named two threads — `[ResultPump]` and
`Thread-50 (_monitor)`, which is `multiprocessing`'s — and the fault was at the wait for the first
progress message. Whether it is the pump, the queue read beneath it, the interaction between them,
or the harness remains unanswered. Nothing here should be read as narrowing it to product code.

#### The ordering hypothesis, tested — 2026-07-29

The earlier attempts ran the crashing test alone and its module. The Windows failure happened
inside a **full-suite** run, and `T-069`'s precedent is that suite ordering was the entire story,
so that was the remaining Linux hypothesis. Six deliberate full-suite runs:

| Attempt | Result |
|---|---|
| Crashing test alone, 40 iterations | 40 passed |
| `test_manager.py` entire, 5 runs | 5 × 71 passed |
| **Full suite, 6 runs** | **6 × 1401 passed, every exit code 0** |

**Linux is now exhausted as a route to this defect**, at least by repetition. Three shapes of
attempt, none of which reproduced it. That is not proof of a Windows-only fault — it is the
absence of a Linux reproduction after looking in the three places worth looking.

**So the measurement has to happen on the machine that shows it.** `.github/workflows/t074-repeat.yml`
runs the suite N times on `STARBASE` and reports a rate. Three things about it are deliberate:

- **Manual dispatch, in its own workflow.** `ci.yml` is a gate and runs on every push; this is an
  instrument. Folding it in would mean paying its cost on every push or making a gate
  conditional.
- **It does not stop on the first crash.** A rate needs every iteration attempted; stopping early
  turns it back into an anecdote.
- **It separates crashes from failures by exit code.** `pytest` exits 1 for a failing assertion.
  A crash takes the interpreter with it, so the code is a signal or an access violation — and
  `T-074` is not a failing assertion. Counting them together would let an ordinary red test
  inflate the crash rate.

"About one in four" came from four ordinary CI runs, where the denominator was however many times
the gate happened to run. This makes the denominator a choice, which is what the acceptance
criteria ask for.

#### The instrument ran — 2026-07-29, run `30429327464`

Twelve full-suite iterations on `STARBASE`, every one attempted:

| Iterations | Crashes | Failures |
|---|---|---|
| **12** | **0** | 0 — `1395 passed, 20 skipped, 32 deselected` each time, 209-217 s |

**"About one in four" was a denominator of four**, and this batch is not a replacement for it.
`0/12 at ea53c71` says the crash is not reliably reproducible at that head. It does **not**
establish a rate (`T074-R1`): the four earlier runs and these twelve are not one controlled
population — the manager and the full-suite composition changed materially between them, including
new integration tests — and after a single event an aggregate point estimate is not a bound. A
clean run is unremarkable under a 25% failure probability and under a 6% one alike.

The crash is real. It happened with a traceback naming `[ResultPump]` and `multiprocessing`'s
`_monitor`, on a documentation-only commit whose code was byte-identical to a passing run.

**It stays a Phase 1 blocker, and the reason is where it landed.** The only observed native crash
is in ordinary `ResultPump` delivery — the exact `ARC-002` path Phase 1 exists to prove — so the
uncertainty cannot be resolved in favour of product safety by counting clean runs. Downgrading it
or accepting the risk is the maintainer's explicit decision to record, not an inference this task
may draw.

**Still unknown: the cause.** Nothing here narrows it. A larger batch is running to either bound
the rate further or catch one with fresh diagnostics; the workflow keeps every iteration's output,
so a crash caught there arrives with its traceback rather than as a count.

*(Superseded: this section previously read "Not yet run. The job is authored and pushed;
executing it needs `STARBASE` and is the next step on this task." It has now run.)*

#### Diagnostic session, 2026-07-29 — narrowed, not diagnosed

**Both threads named in the crash are ours.** The traceback listed `[ResultPump]` and
`Thread-50 (_monitor)`, and `_monitor` was read as `multiprocessing`'s. It is not: `multiprocessing`
declares no such function, and `_monitor` is
`core/logging.py`'s `_ToWhicheverHandlersWeHaveNow._monitor` — the `T-038` log listener's thread
body. So the crash happened with the result pump and the **logging listener** both live, which
points somewhere the earlier notes did not.

**A mechanism worth testing, stated as a hypothesis.** `_monitor()`'s `finally` closes the worker
log queue — a `multiprocessing.Queue` — and `stop_listening_for_worker_logs()` **waits for
nothing**, deliberately (`T038-R2`, and it is right to: the GUI thread must not block on a slow
handler). So the close runs on the listener thread while parent threads may still be logging into
that queue and a spawned writer may still hold the other end. Closing a multiprocessing queue
under a concurrent user is the kind of thing that faults natively instead of raising, which is the
shape this crash took. The crashing test is also the one that **kills** a worker rather than
asking it to stop, so a writer dying mid-record is in scope there and almost nowhere else.

**Nothing here demonstrates that.** It is a mechanism that fits, and the file it implicates has a
recorded reason for the behaviour. It is written down so the next attempt starts from a candidate
rather than from the whole suite.

**What was attempted, and what it cost:**

| Attempt | Result |
|---|---|
| Repeat batch, 24 full-suite iterations on `STARBASE` | **0 crashes** (run `30454206697`) |
| Both batches together, recent heads | **0 in 36** |
| Repeat batch, 15 full-suite iterations at `35fc7ec`, **post-`T-090`** | **0 crashes, 0 failures** (run `30478557533`) |
| The crashing test alone, 60 iterations on Windows | **60 passed, 0 failed, 0 crashed** |
| A direct stress of the logging-teardown race | **unusable — it hung on Linux before its first iteration** |

The last row is the honest one. The harness drives a parent thread logging continuously while a
spawned writer is killed and the listener is torn down; it never reached a print, so it deadlocked
in its own setup rather than measuring anything. A failed instrument is not a negative result, and
it is recorded as neither.

**Classification is unchanged: product versus harness is still unresolved**, and `T-074` remains a
High Phase 1 blocker. What has changed is where to look — logging teardown alongside the pump,
rather than the pump alone.

#### What the diagnostic session produced — 2026-07-29

It found a **different** defect, now filed as `T-090`: the log listener could be left reading a
queue something else had closed. The evidence for that moved there with it.

**What it did not produce is anything about this crash.** The access violation has never been
reproduced — 0 in 36 full-suite runs, 60 clean runs of the crashing test alone, 250 clean
in-process iterations — so its faulting object is still unknown and it is still unclassified
between product and harness. `T074-R4`: a real race on the same thread is a candidate, not a
cause, and the crash's absence cannot distinguish them when it was already absent every time.

**What is genuinely narrowed** is that `_monitor` in the traceback is the `T-038` log listener
rather than anything in `multiprocessing`, so the next attempt has two of our own threads to
account for rather than one.

#### Acceptance criteria

- The failure is **reproduced deliberately**, with a rate, rather than waited for
- The faulting thread and the object it touched are identified — a stack is not a cause
- The fix is proven by a mutation that restores the crash, not only by runs that stop crashing
- If it turns out to be the harness rather than the pump, that is recorded explicitly, because
  the opposite conclusion is the one a reader would assume from the file it crashed in

#### Out of scope

- Retrying, `xfail`, or a rerun plugin. `T-069` established the rule: an intermittent failure gets
  its trigger found, not its symptom hidden. The one time this project reached for a retry the
  reviewer's instruction was explicit — *do not retry or xfail*
- `T-056`, which is a different intermittent on a different platform and is `OPS-005`-downgraded

---

### T-092 — Arm `STARBASE` so the next access violation leaves a cause, not a stack

**Status:** **Blocked — prepared 2026-08-01, on *somebody at* `STARBASE`.**

**Re-triaged 2026-08-04: still blocked, but it may no longer be the only route.** This task exists
because the faulting object of `T-074`'s access violation is unknown and a Windows crash dump was
the only way to get one. `T-128` records something in the same subsystem crashing on **Linux** at
roughly 2 in 39 — where a core dump needs `ulimit -c` and a pattern, not a person at a machine and
consent to write dumps on it. **That does not unblock this**, which is specifically about Windows,
and the two crashes are not established as one defect. It does mean the *cause* may become
obtainable without this task, which is worth knowing before anyone spends a trip to the desktop on
it.

Re-triaged 2026-08-03:
the machine came back that day and now runs every Windows job, so "blocked on `STARBASE`" no longer
says what it means. The three remaining criteria need a person to arm dumps, crash a process on
purpose and open the result — none of which a CI job does. **Availability was never the blocker.** The reviewer classified it
so on 2026-08-01: the safe correction is accepted (`T092-R1`) and the scope amendment is taken
(`T092-R2`), and **nothing further can be done from here.** Three criteria need somebody at the
machine.
*(This read "Ready — prepared 2026-08-01, and NOT complete", which put a task nobody could pick up
in the list of tasks to pick up.)* The maintainer's consent was given
2026-08-01 and the whole configurable half is committed: `tools/windows/crash-dumps.ps1` arms and
disarms it, `docs/WINDOWS_VERIFICATION.md` records the procedure and its disk cost, and both
`STARBASE` jobs collect a dump when one exists. **Three of the five acceptance criteria are
unmet and cannot be met from here** — they require running the script on `STARBASE`, crashing a
process on purpose, and opening the dump. See "Prepared, and what remains" below.
*(This read "Ready — the instrument `OPS-007` leans on".)*
**Owner:** Implementer
**Priority:** Medium — it buys nothing today and is the whole diagnostic plan if `T-074` recurs
**Phase:** Phase 1 origin; it is an instrument, not a deliverable, and gates no exit *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
**Depends on:** `STARBASE`, which exists. Needs the maintainer's consent to write dumps on a
machine they use
**Relevant context:** `OPS-007`, `T-074`, `T-073`, `docs/WINDOWS_VERIFICATION.md`
**Affected surfaces:** `docs/WINDOWS_VERIFICATION.md`, `.github/workflows/ci.yml` and
`t074-repeat.yml` (a metadata report, never a dump artifact), `STARBASE` machine configuration
**Risk:** Low to the product — it touches no source. The real risk is on the machine: dumps are
written unattended and a full-memory dump of a Python process with Qt loaded is not small

#### Scope

`T-074`'s second acceptance criterion is that **the faulting thread and the object it touched are
identified — a stack is not a cause.** `faulthandler` cannot supply that: it printed
`[ResultPump]` and `Thread-50 (_monitor)` and named neither the faulting module nor the address.
A minidump does.

So: configure Windows Error Reporting local dumps on `STARBASE` for the interpreter that runs the
suite, and have the `t074-repeat.yml` and `windows desktop` jobs **report** any dump written during
that run — name, size and timestamp into `reports/crashdumps.txt` — leaving the dump on the machine
for deliberate retrieval. Then a recurrence, in CI or in an ordinary run, produces something a
debugger can read instead of another anecdote.

*(**Superseded, and the wording matters because this is the live instruction.** This said "upload any
dump they find as an artifact", which `T092-R1` found unsafe on three counts: WER is keyed by
executable *file name* so the folder collects any `python.exe` under that account, nothing filtered
stale dumps so the deliberate proof dump would be re-uploaded on every later run and announced as a
recurrence, and a full memory dump can carry an unrelated program's heap into a CI artifact. The
metadata-only scope is the maintainer's decision of 2026-08-01 — `T092-R2`, which stayed open once
because the criterion was corrected and this sentence was not.)*

**Consent first, and this is not a formality.** `STARBASE` is the maintainer's own desktop.
`OPS-005` and `T-073` both carry the rule that a workflow must never provision it, and
`docs/WINDOWS_VERIFICATION.md` records what installing Python there already cost. Dump capture is
machine configuration and belongs in that document as a manual, reversible step — not in a
workflow.

#### Acceptance criteria

- A **deliberately crashed** Python process on `STARBASE` leaves a dump at a known path — proven by
  causing an access violation on purpose, not by trusting the registry keys
- That dump, opened, names a faulting module and address. If it cannot, this task has failed at the
  thing it exists for and says so rather than reporting the keys as success
- Dump size and retention are bounded and stated; the disk cost on a real machine is named
- **The jobs report a dump's existence and never upload it** — name, size and timestamp into
  `reports/crashdumps.txt`, with the dump left on `STARBASE` for deliberate retrieval. Both the
  "a dump was written" and "no dump" paths stay green: a missing dump is the normal case and must
  not redden the gate
  *(**Scope amended 2026-08-01, maintainer decision** — `T092-R2`. This read "upload a dump when
  one exists". WER is keyed by executable *file name*, so the folder collects any `python.exe`
  under that account and a full memory dump can carry an unrelated program's heap into a CI
  artifact; the old wording could not be met without reintroducing `T092-R1`. The narrower
  alternative — copy the interpreter to a distinct name and key WER to that — is recorded in
  `docs/WINDOWS_VERIFICATION.md` rather than taken, because it changes how the suite is
  launched.)*
- `docs/WINDOWS_VERIFICATION.md` records the configuration, how to undo it, and the disk cost

#### Out of scope

- Diagnosing `T-074` — this task cannot, and pretending otherwise is what `T074-R4` caught
- Any change to `src/`
- Dump capture on Linux, or on hosted runners, which are discarded anyway
- Making `T-074`'s recurrence more likely; this is passive capture, not a stress test

#### Prepared, and what remains, 2026-08-01

**Done, and committed:**

- `tools/windows/crash-dumps.ps1` — arms WER local dumps for `python.exe` under `HKCU` (no
  elevation, scoped to one executable rather than the whole machine), and `-Remove` undoes it.
- `docs/WINDOWS_VERIFICATION.md` — why, how to arm it, **how to prove it**, the disk cost, and how
  to undo it.
- `ci.yml`'s `windows desktop` job and `t074-repeat.yml` each stamp their start time and write
  `reports/crashdumps.txt` naming any dump written **during that run** — and upload no dump at all.
  `if: always()` and `continue-on-error: true`, because **no dump is the normal case and must not
  redden the gate**.
  *(This described copying the dump into `reports/`, which is what `T092-R1` found unsafe. The
  scope amendment above is the maintainer's, taken 2026-08-01.)*
- Full dumps (`DumpType 2`) rather than mini, stated with the cost: ~300–600 MB each for a Python
  process with Qt loaded, five kept, so up to ~3 GB. A mini dump routinely lacks the heap the
  faulting address points into, which is the entire question `T-074` is asking.

**Unmet, and honestly so** — each needs the machine:

| Criterion | State |
|---|---|
| A deliberately crashed process leaves a dump at a known path | **Unmet.** Nobody has run the script or the crash |
| The dump names a faulting module and address | **Unmet**, and it is the one that decides whether this task succeeded at all |
| Dump size and retention bounded and stated | **Met** — in `docs/WINDOWS_VERIFICATION.md` |
| The jobs **report** a dump and never upload one | **Half met.** The steps exist and both YAML files parse; no CI job has executed a step since 2026-07-30, so neither branch has run |
| `docs/WINDOWS_VERIFICATION.md` records config, undo and cost | **Met** |

**Why this is filed as prepared rather than done.** `T074-R4` caught this task's predecessor
reporting registry keys as evidence. The keys are not the evidence; a dump that names a faulting
module is. Until somebody runs the two commands in the document on `STARBASE`, the correct status
is that the instrument is *ready to arm* and has never fired.


#### Correction, 2026-08-01 — `T092-R1`

**The prepared upload was unsafe before it had ever run.** Three problems, all real:

- **WER is keyed by the executable's file name**, so `python.exe` collects *any* Python process
  under that account, not this project. There is no narrower WER key. A dump in the folder is
  therefore not by itself evidence of `T-074`, and the report now says exactly that.
- **Nothing cleared or time-filtered the folder**, so the deliberate proof dump — or a months-old
  one — would be re-uploaded on every later run and announced as a recurrence that never happened.
  Both jobs now stamp their start time and report only what was written after it.
- **A full memory dump can carry an unrelated process's heap**, and a CI artifact is a copy of it
  somewhere else. **Nothing is uploaded now.** The jobs write `reports/crashdumps.txt` with the
  dump's name, size and timestamp and leave the dump on `STARBASE` for deliberate retrieval.

`docs/WINDOWS_VERIFICATION.md` gains the provenance and disclosure reasoning beside the disk cost,
which is what it was missing. The narrower alternative — copy the interpreter to a distinct file
name and key WER to that — is recorded rather than done, because it changes how the suite is
launched.

**Three acceptance criteria remain unmet and still need the machine.** Nothing here changes that.

---

### T-068 — Qt writes a font warning to stderr on a real Windows machine

**Status:** **Blocked — on the runner question, which just got harder**, 2026-07-28; re-triaged
2026-08-03 and **again 2026-08-04, unchanged and verified**. `OPS-010` restored the Windows suite
to every push, which sounds like it would help and does not: it restored the **`STARBASE` desktop**
job, while `check`'s hosted Windows leg stays dropped. `vars.WINDOWS_RUNNER` is set, so hosted
Windows still does not run at all. The cost of answering this is now explicit — unsetting that
variable for one run spends hosted Windows minutes at a 2x multiplier, against a nearly exhausted
quota. The frozen half is now obtainable: `frozen windows` runs on `STARBASE`. The other half
asks *why the hosted runners never showed the fault*, and hosted Windows **no longer runs at all**
while `WINDOWS_RUNNER` points at the desktop (`docs/project/TESTING.md` §10). Answering it now needs that
variable unset deliberately for a run. A consequence of the gate rebuild, recorded rather than
discovered later. The
environment fix itself was not contested: the warning was the symptom, and the defect is that Qt
had **zero font families** under `offscreen` on that machine, so the whole offscreen UI suite ran
with no fonts. `QT_QPA_FONTDIR` is set before PySide6 is imported, is Windows-only, and honours an
explicit caller value. The task's own acceptance criteria still require the runner difference to
be explained and a Windows frozen artifact to be checked; both need a hosted runner. See
**Evidence**.

**No longer a Phase 1 exit dependency** (`OPS-005`, 2026-07-29). Still open, still Blocked. This
one runs the *other* way from `T-056`: the defect appeared **on** the real machine and the hosted
runners are the ones that look clean, so the fix is already validated where the fault was. What
remains is the diagnostic question of why the runners never showed it — worth answering, not worth
holding a phase for.
**Owner:** Implementer
**Priority:** Medium — an assertion about a *clean* run is failing, and the cause is not understood
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
**Depends on:** nothing
**Relevant context:** `T-007`, `tests/ui/test_app_launch.py`, `OPS-004`
**Affected surfaces:** `tests/ui/test_app_launch.py`, possibly packaging
**Risk:** Medium — unknown cause; it may be cosmetic, and it may be a deployment gap

#### Scope

`test_application_launches_and_exits_cleanly` asserts the application writes nothing to stderr on
a clean run. On `STARBASE` it writes:

```
QFontDatabase: Cannot find font directory <prefix>/PySide6/lib/fonts.
Note that Qt no longer ships fonts. Deploy some ... or switch to fontconfig.
```

**It fails in both the venv and the CI-style install**, so it is not the virtualenv — an
A/B that also corrects the implementer's first guess, which was that the venv caused it. The
cause is genuinely unknown and this task exists to find it rather than to silence it.

Two reasons not to treat it as noise. It only appears on a machine that is not a CI runner, which
is exactly the population `OPS-004` was written to stop assuming about. And a Qt that cannot find
a font directory under the offscreen platform raises an unanswered question about the **frozen**
artifact, which is what a user runs.

#### Acceptance criteria

- The cause is identified — not "PySide6 does that", but why this machine and not the runner
- Whether the frozen build (`T-020`, `T-033`) shows the same warning is answered on Windows
- If the warning is benign, the test says so deliberately rather than being loosened to pass
- If it is not benign, the fix is in packaging or startup, not in the assertion

#### Evidence, 2026-07-28

**The warning was the symptom. The defect is an empty font database.** Measured under
`QT_QPA_PLATFORM=offscreen` on `STARBASE`, in the interactive desktop session:

```
FAMILIES 0
SAMPLE  []
DEFAULT Sans Serif
```

Zero families. So the **entire offscreen UI suite** runs there against no fonts: every assertion
about a widget's size, about elision, or about anything else derived from font metrics is measured
against nothing — and passes. A suite that agrees with itself while measuring an empty font set is
the shape `docs/project/TESTING.md` §13 exists to catch, which is why this was not allowlisted into
`PLUGIN_NOISE` alongside `propagateSizeHints`. That allowlist is for artifacts that change no
measurement; this one changes every measurement.

**Not our code.** A bare `QApplication` produces nothing; a bare `QLabel` reproduces it in full,
with no project code involved. Same result in the venv and the no-venv checkout, which also
corrects the first guess recorded against this task — it is not the virtualenv.

**Not the session either.** It reproduces identically in session 2, so it is not an artifact of
running over SSH, which was the other plausible explanation and had to be ruled out because
several other results were.

**Fix:** `tests/conftest.py` sets `QT_QPA_FONTDIR` to `%WINDIR%\Fonts` on Windows, with
`setdefault` so an explicit value wins. Verified: `families()` goes from 0 to a populated list and
`test_application_launches_and_exits_cleanly` passes.

**Open, and it needs a runner:** *why the runners do not show this.* Their offscreen Qt evidently
finds fonts by some route this machine lacks, and until CI runs it is unknown whether
`QT_QPA_FONTDIR` changes anything there. If their database is already populated the variable is
ignored, which is the expected case — expected, not verified.

#### Out of scope

- Weakening the empty-stderr assertion to make the run green; that assertion caught this

---

### T-056 — `still_running` reports a reaped Windows process as alive, intermittently

**Status:** **Blocked — on a reproduction, not on a machine**, 2026-07-28 at `9c92c32`.

**Re-triaged 2026-08-04, and a candidate reproduction was checked and rejected.** The overnight
`-n auto` run failed exactly this task's subject —
`test_the_survival_check_can_tell_a_live_process_from_a_dead_one`, `still_running`'s own test — on
Linux, which looked like the reproduction this task has waited for since July. **It is not.** The
assertion was *"a running process was reported dead"*: `still_running([alive.pid])` returned `[]`
for a live process. This task is the **opposite** symptom — a *reaped* process reported **alive**.
Same helper, inverted direction, and a false negative under parallel load is a different defect
from a false positive on Windows.

Recorded rather than left for somebody else to find and re-check. What it does say is that
`still_running` has a second failure mode nobody had seen, which `T-123` carries.

Re-triaged 2026-08-03: `STARBASE`'s return does **not** help. This task already had its Windows
evidence and that is the finding — reverting the fix passes 20/20 there, so the defect does not
reproduce on the machine we have. More runs of the same machine cannot close it. The reviewer
found the implementation correct and could not verify it: the changed branch does not execute on
Linux, so neither the runtime behaviour nor the mutation that proves it can be observed here. The
helper decides by exit status on Windows and the third acceptance criterion is answered in its own
docstring.

**A Windows machine was not enough** (2026-07-28, `STARBASE`, Windows 10 22H2). The corrected
helper passes 3/3. Reverting it to the presence-based form it replaced passes **20/20** — the
defect does not reproduce here at all. A positive control (`still_running` always answering
"nothing alive") **fails** on the test's first assertion, so the patching mechanism is proven and
the survival is a real measurement rather than a mutation that never applied.

So the next step narrows rather than clears: this wants **`windows-latest`'s image**, Windows
Server, not Windows as such. `30323328299` remains the only observation of the defect anywhere.

**No longer a Phase 1 exit dependency** (`OPS-005`, 2026-07-29). Still open, still Blocked, but it
does not gate the phase: `still_running()` is test-only code that never ships, and its documented
sole error direction is a false **alive** — it can redden CI, it cannot make broken reaping look
correct. Windows Server is not a supported platform (`REQUIREMENTS.md`), so a finding seen only
there is a CI-reliability concern rather than a user-facing one.

**What that decision explicitly does not claim.** The mechanism is Windows-*general*: Windows has
no zombie state and a terminated process stays visible while any handle to it is open, which is
identical on Windows 10 and on Server. `STARBASE`'s 20/20 is therefore **absence of a trigger, not
evidence of correctness**. The risk is accepted on the error direction, not on the clean run.
**Owner:** Implementer
**Priority:** Medium — an intermittent failure in the helper every `T-019` assertion rests on
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
**Depends on:** nothing
**Relevant context:** `T-019`, `docs/project/TESTING.md` §7 (Cancellation, Worker crash)
**Affected surfaces:** `tests/integration/test_manager.py`
**Risk:** Medium — it decides whether the process-tree suite is telling the truth

#### Scope

`test_the_survival_check_can_tell_a_live_process_from_a_dead_one` failed once on `windows-latest`
in run `30323328299`: `still_running([dead_pid])` returned `[7208]` for a process the test had
already reaped. It passed on the runs either side, so it is **intermittent, not a regression** —
nothing in the `T-016` batch touches `process_tree.py` or that helper.

The likely cause is that `still_running` treats "psutil can still see the pid" as alive, excluding
only `NoSuchProcess` and `STATUS_ZOMBIE`. Windows has no zombie state, and a terminated process
stays visible while a handle to it remains open, so there is a window in which a dead process
reports as running.

**This matters more than a flaky test usually would.** `still_running` is the helper the whole
`T-019` descendant-reaping suite decides on, and its own docstring says a guard nobody watches
fail is the shape `docs/project/TESTING.md` §13 exists to catch. A false *alive* fails loudly, as here; the
concern is whether the same imprecision can produce a false *dead* and make a reaping assertion
pass without anything having been reaped.

#### Acceptance criteria

- The helper distinguishes a running process from a terminated-but-visible one on Windows, by
  exit status rather than by presence
- The claim is demonstrated on Windows CI, not reasoned about from Linux
- Whether the previous form could report a live process as dead is answered explicitly, and the
  answer is recorded rather than assumed benign

#### Out of scope

- Changing `downloader/process_tree.py`, which is `T-019`-approved and not implicated

#### Evidence, 2026-07-28

**The fix is Windows-only, because the imprecision is.** On POSIX the terminated-but-visible state
*is* the zombie state, so `status()` was already asking the right question. On Windows there is no
zombie and a corpse stays visible while any handle to it is open, so the helper now uses
`wait(timeout=0)` there — `WaitForSingleObject` on psutil's own handle, which neither disturbs
anyone else's handle nor depends on visibility.

**The first attempt used `wait(timeout=0)` on both platforms and broke the suite**, which is worth
keeping: on POSIX that call is `waitpid`, so inspecting a worker *reaped* it and stole the exit
status `multiprocessing` was waiting for. `is_alive()` then never reported the process gone and
the manager never went idle —
`test_cancelling_a_download_kills_what_the_worker_spawned` failed exactly that way. A survival
check that changes what it observes is worse than an imprecise one.

**The third criterion is answered, not assumed benign.** The previous form could **not** report a
live process as dead: it answered "dead" only on `NoSuchProcess` (and `ZombieProcess`, its
subclass) or on a `STATUS_ZOMBIE` a live process never has, and `AccessDenied` was uncaught and so
would have failed loudly. Its one error direction was **false alive**, which fails an assertion in
the open rather than letting a reaping assertion pass over nothing. The answer is recorded in the
helper's docstring, where the next reader of the helper will find it.

**The test now drives the failing shape**: a third process is killed and deliberately *not* waited
on. On Linux that is a zombie, which the old form already handled; on Windows it is exactly run
`30323328299`'s failure.

**Mutations run:** answering by presence alone everywhere — killed. Reporting nothing as alive —
killed. **Disabling the `win32` branch so it falls back to the POSIX question — survived, and
cannot do otherwise here**: the branch is unreachable on Linux by construction. That is
`AGENTS.md` §8's "a host-only check is not the whole gate" in its exact form, and it is why this
task is not claiming to be done.

**Checks:** `ruff check .`, `ruff format --check .`, configured `mypy` and `mypy --platform win32`
(72 files each — the win32 scope is what analyses the new branch at all) all pass. Bare `pytest`
green.

**Blocker:** the Windows demonstration. This machine has no Windows and the branch cannot execute
here, so approval needs the `windows desktop` job to run the corrected helper and the third
mutation against it. Same shape as `T-033`'s blocker: the code is done, the evidence is not
producible locally.

---

