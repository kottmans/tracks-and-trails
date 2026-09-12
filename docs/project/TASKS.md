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

**Status:** **In Review** — measured 2026-09-12 on both artifacts, cold included. **`NFR-002` is
not met on Windows and the task now needs a ruling rather than a re-measure**: cold start is
**3.976 s against a 3 s bound**. Warm is 1.55 s and was never the question. Filed 2026-09-11 with
the Phase 5 plan.

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

**What is left is a ruling, not a re-measure.** `NFR-002` says *"cold start"*, and cold start is
3.976 s. Three options, none of them the implementer's:

| Option | What it costs |
|---|---|
| **Amend `NFR-002`** to a warm-start bound, stating the cold figure beside it | It is a change of requirement rather than a reading of one — the requirement says cold |
| **Raise the number** — 4 s covers every measurement taken, 5 s leaves margin on a slower machine | Honest, and the release gate then passes on a number somebody chose |
| **Attack the cost** | Mostly not ours: a Defender exclusion is not something an artifact can arrange for itself, and 155 MB is what bundling ffmpeg costs. **A one-file build would make it worse**, not better — it trades startup for extraction |

**What is not an option is leaving `TESTING` §8 item 14 reading as a pass.** It is a release-gate
item with a number in it, and the number is not met.
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

#### Acceptance criteria

- An evidence file per platform with machine, method, the ten raw numbers and the two medians
- `TESTING.md` §8 item 14 cites the file, and names *which* build and version were measured
- A failure produces a task with a profile attached, and this task closes as *measured* either way

#### Out of scope

- Optimising anything. Measure first

---

### T-317 — Decide whether the first Windows installer is signed

**Status:** **In Review** — the ruling was taken 2026-09-11 and its documentation follow-through
landed 2026-09-12. One criterion is **sequenced rather than met**, and deliberately: the README's
install section lands with the release commit, because the line it replaces is still true. Filed
2026-09-11 with the Phase 5 plan. **Gated the start**: it changes what `T-322` builds and what
`T-039` may assert.

**The decision is taken.** The maintainer ruled on 2026-09-11 for option **A**, recorded as
[`REL-005`](DECISIONS.md#rel-005--the-first-windows-installer-ships-unsigned): `0.1.0` ships
unsigned, with B or C named as the `1.0` condition. **The follow-through landed 2026-09-12**,
below.

#### 2026-09-12 — the follow-through, and the one criterion that is sequenced rather than met

Checked against the acceptance criteria one at a time rather than declared done:

| Criterion | Where |
|---|---|
| a `REL-` entry naming the choice, the rejected alternatives and why | `REL-005`, which also carries the reopening condition and the deliberate omission of AppImage signing |
| if unsigned: `docs/RELEASE.md` states what SmartScreen shows and the exact click-through | §*What a Windows user will see* — the prompt quoted, **More info** → **Run anyway**, and why reputation never accrues without a certificate |
| `T-039`'s gates stated as **independent of signature** | stated in `T-039`'s own entry, where the gates will be written |
| names its reopening condition | `REL-005`: the `1.0` release, or evidence the prompt is costing installs |

**The README's install section is the one that is sequenced, not met, and that is `T-320`'s
judgement rather than a gap here.** The README says *"you cannot install it from a release — there
are no installers or packages yet"*, which is **true today**; replacing it now would claim
installers that do not exist. `docs/RELEASE.md` makes the replacement a release-commit step
alongside `CHANGELOG.md` and `SECURITY.md` §Supported versions, and that step now **requires the
SmartScreen click-through verbatim** plus the two system requirements — so the wording this task
asks for is pinned to the commit where a README section can exist without being false.

**`T-039`'s note is the half worth reading.** Its checks have to hold whether or not the installer
is signed, and **no assertion may pass only because a signed binary skipped a prompt** — that is a
test measuring SmartScreen rather than the installer, and it would go red the day signing arrives,
which is the one day nobody would suspect the test.

**Nothing was bought and nothing is signed.** The `.iss` carries a commented `SignTool` line so
`REL-005`'s condition is met by uncommenting rather than authoring, and
`tests/unit/test_windows_packaging.py` asserts it is still commented — a signing line that
switched itself on would be a silent change to what the artifact is.
**Owner:** Maintainer decision; Implementer records it as a `REL-` entry
**Priority:** High — every later Windows task is shaped by the answer, and a certificate is a
purchase with a lead time
**Phase:** Phase 5
**Depends on:** nothing
**Relevant context:** `REL-001`; `OPS-004` (the installer must *feel* normal — a human item);
`SECURITY.md` §CI trust boundary; `NFR-007`
**Affected surfaces:** `docs/project/DECISIONS.md`; later `T-322`'s build step and `T-324`'s
release workflow
**Risk:** Low to decide; Medium not to — an unsigned installer meets SmartScreen's *"Windows
protected your PC"* on every first install, which is the single largest reason a desktop user
abandons an install

#### Scope

Nothing in the record decides this. `DOC-002` names *"a documented release and signing process"* as
the reason `docs/RELEASE.md` exists, and no `REL-` entry has taken the question up. Three honest
answers:

| Option | What the user sees | What it costs |
|---|---|---|
| **A. Ship unsigned**, document the SmartScreen prompt in the README and release notes | *"Windows protected your PC"* → *More info* → *Run anyway*, on every first install | Nothing. Reputation never accrues, so the prompt never goes away |
| **B. OV code-signing certificate** | The same prompt until SmartScreen reputation accrues over downloads; then none | A yearly purchase, identity verification, a key to protect |
| **C. Azure Trusted Signing** (or an EV certificate) | No prompt from the first install | A subscription and an Azure identity; EV needs hardware-backed keys |

**Recommendation: A for `0.1.0`, with B or C named as the `1.0` condition.** The first release is the
one where the maintainer learns whether anyone installs it; buying identity infrastructure before
that is the cost inverted. But the choice is the maintainer's because it is their name on the
certificate, and this task exists so that *"unsigned"* is a decision with its consequences written
down rather than an omission discovered at the first SmartScreen screenshot.

#### Acceptance criteria

- A `REL-` entry naming the choice, the rejected alternatives and why, in the house style
- If unsigned: the README's install section and `docs/RELEASE.md` state what SmartScreen will show
  and the exact click-through, so support is a link rather than a conversation
- If signed: where the key lives, who can use it, and the rule that CI never holds it in a
  repository secret readable by a fork (`SECURITY.md` §CI trust boundary)
- `T-039`'s gates are stated as **independent of signature** — a silent install must succeed
  either way, and the test must not pass only because a signed binary skipped a prompt
- Names its reopening condition

#### Out of scope

- Signing the Linux artifact. AppImage signatures are optional and rarely checked; record that as
  a deliberate omission in the same entry
- Buying anything. The decision may be *A*; this task does not presume otherwise

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

#### Acceptance criteria

- A tag on a test branch produces a draft release with two artifacts and a checksums file, and
  `gh release view` shows `draft: true`
- A tag whose version disagrees with `__version__` fails at step 1 with the disagreement named
- The `permissions:` block grants `contents: write` to the release job only; the workflow file is
  reviewed against `SECURITY.md` §CI trust boundary and the review recorded
- `docs/RELEASE.md` describes the tag → draft → review → publish sequence, and the rollback of
  each step
- The `frozen` job in `ci.yml` is unchanged in scope — it remains the per-push smoke, and this
  workflow does not run on push

#### Out of scope

- Publishing. Deliberately
- Signing (`T-317` decides; if signed, the signing step lives here and the key does not)

---

### T-318 — Decide how "a clean machine" is evidenced for the first release

**Status:** **In Review** — the harness landed 2026-09-12 and has taken Linux evidence for
`0.1.0.dev0`. The Windows half waits on `T-319`/`T-322` for a candidate to install. **Gates the
exit** (criteria 1, 2 and release-gate item 7). Filed 2026-09-11 with the Phase 5 plan.

**The decision is taken.** The maintainer ruled on 2026-09-11 for option **B**, recorded as
[`REL-006`](DECISIONS.md#rel-006--a-clean-machine-is-a-disposable-vm-the-maintainer-owns):
disposable VMs the maintainer owns, with *A* as the fallback. **The harness landed 2026-09-12**,
below.

#### 2026-09-12 — the harness, and the VM that is not a VM

**The maintainer narrowed `REL-006` the same week it was taken**: *"I don't really want to use VMs
for testing the packages. I'd rather just test the app image on my own machine and test the windows
installer on starbase."* So the Linux clean machine is a **disposable container** and the Windows
one is **Windows Sandbox on `STARBASE`**. Both satisfy what B was chosen for — clean by
construction, owned by the maintainer, no hosted minutes — and the container costs a pull rather
than the afternoon B was priced at. `REL-006`'s *"written down well enough to recreate in a year"*
is then met by a committed script instead of a setup document, which is the stronger form.

| Platform | How | Evidence |
|---|---|---|
| Linux | `tools/clean_machine_linux.sh <artifact>`, which supplies `ubuntu:24.04` and runs `tools/clean_machine_evidence.sh` on it | `docs/project/evidence/linux-<version>.md` |
| Windows | By hand in Sandbox, against `docs/project/evidence/TEMPLATE-windows.md` | `windows-<version>.md` |

**`ubuntu:24.04` and not the build image.** `packaging/build_appimage.sh` builds on Debian 12 so
the artifact reaches as far back as possible; this runs it on the oldest LTS the README claims.
Testing on the machine that built it would prove nothing about either.

**The pre-install check is first and it can fail the run** — the first acceptance criterion, and
the reason it is first: evidence taken on a machine that turns out to have had Python on it is not
evidence, and finding that out afterwards is too late. Thirteen tools probed with `command -v`,
plus a count of system Qt libraries, **output retained in full** rather than reduced to a verdict.

**What it caught on its first run is recorded in `T-321`** — the artifact carries no CA bundle, so
the real download failed on a machine whose `/etc/ssl/certs` is empty. That is the harness earning
its place on the day it landed.

**Why the Windows half is a template and not a script.** Everything the Linux evidence needs can
be answered without a display; `--download-probe` exists for exactly that. The Windows half is
driven through the window, which is what lets it cover *cancel another* — the one `TESTING` §8
item 8 clause no probe can reach, because cancellation is a parent-side signal and a probe has no
parent.

#### 2026-09-12 (later) — the Windows half, taken in Sandbox, and scripted rather than by hand

**`docs/project/evidence/windows-0.1.0.dev0.md`.** Windows 10 Enterprise inside Windows Sandbox on
`STARBASE`, installing `Tracks-and-Trails-0.1.0.dev0-setup.exe` (sha256 `7528e12f…`):

| | |
|---|---|
| pre-install check | python, pip, ffmpeg, ffprobe, yt-dlp, cl, gcc, qmake6, git — **all absent**; no system Qt |
| install | **exit 0 in 18.6 s**, per-user, **no elevation prompt** |
| placed | 225 files, `_internal\licenses\`, `_internal\ffmpeg.exe`, Start Menu shortcut |
| desktop icon | **absent**, as the opt-in default asks |
| first launch | window in **~2 s**, titled *Tracks & Trails* |
| orphans after close | **none** |

**`REL-006`'s premise was unchecked until today.** It chose Windows Sandbox because it is *"clean
on every launch by design"* — true, and **Sandbox was `Disabled` on `STARBASE`**, with
`WindowsSandbox.exe` absent. One command and a reboot, but it could as easily have been a Home
edition, and the decision would have needed revisiting.

**Scripted, which the task did not expect.** `T-318` made this half a template a human fills in,
because the Linux probes have no Windows equivalent. Sandbox runs a **logon command** and a mapped
folder carries the result back, so the pre-install check, the silent install, placement, launch
and orphan check are all `packaging/windows-sandbox/evidence.ps1`. What stays human is `OPS-004`'s
judgement — whether the installer *feels* normal — which no script answers.

**Three defects in the harness, found by running it:**

1. **An XML comment containing `--`.** Sandbox refused the configuration with *"The configuration
   file was invalid. Error 0xc00cee2f"* — a double hyphen is illegal inside an XML comment, and
   my own prose put one there.
2. **A recursive `Get-ChildItem C:\` looking for `Qt6Core.dll`.** Not a check, a crawl: the run
   stopped there for twenty-five minutes. Narrowed to the places a system-wide Qt could actually
   be loaded from.
3. **The verdict said PASS while the report said `start menu MISSING`.** Two faults at once: the
   path omitted the `DefaultGroupName` subfolder the `.iss` creates, so it was looking in the
   wrong place — and **nothing incremented the failure count**, so a reported problem passed
   anyway. The shortcut was there all along. A check that reports a problem and does not fail is
   the defect this project keeps finding, and this one was mine.

**Still not covered, and it is `T-039`'s by scope:** uninstall and what survives it. `DAT-001` says
settings, history and downloaded files stay; that needs a second Sandbox pass driving the
uninstaller, which `T-039` owns.

**The Windows machine is settled** — maintainer, 2026-09-12: *"The windows half can run on
starbase."*

**One distinction the template makes and this entry repeats, because it decides whether the
evidence counts.** `STARBASE` is where the run is *driven from*; it is not the clean machine. It
carries Python, a toolchain, ffmpeg and a developer's yt-dlp, so the pre-install check run there
would report `PRESENT` on every line and fail — correctly. **Windows Sandbox on `STARBASE`** is
the clean machine: fresh on every launch, discarded on close, and `REL-006` chose it for exactly
that property. The ffmpeg line matters most there: `OPS-001` bundles ffmpeg on Windows, so a
machine with ffmpeg already on `PATH` cannot tell a bundled copy from a borrowed one.
**Owner:** Maintainer decision; Implementer records it and builds whichever harness it names
**Priority:** High — the two exit criteria it serves are the phase's definition of done
**Phase:** Phase 5
**Depends on:** nothing
**Relevant context:** `OPS-010` and `OPS-012`, which each record surrendering clean-machine CI
evidence on one platform; `TESTING.md` §8 item 7; `REQ-029`; `REL-001`; `T-066` (CI once installed
the project differently from the documentation, and the clean machine is what caught it)
**Affected surfaces:** `docs/project/DECISIONS.md`; possibly `.github/workflows/`; evidence under
`docs/project/evidence/`
**Risk:** Medium — the phase's own exit criteria say *"a clean … machine"* twice, and nothing in CI
runs on one any more

#### Scope

Both self-hosted routings were taken with eyes open: `OPS-010` gave up clean-machine evidence for
Windows and `OPS-012` for Linux, each saying so in writing. Phase 5's exit criteria were written
before either. So the phase now demands something CI no longer produces, and the honest options
are:

| Option | Clean? | Cost |
|---|---|---|
| **A. One hosted run per release candidate** — unset `WINDOWS_RUNNER`/`LINUX_RUNNER` for the RC | Yes, both platforms | Hosted minutes, which `OPS-010` says ran out; and it evidences `ubuntu-latest`, not an older distro |
| **B. Disposable VMs the maintainer owns** — Windows Sandbox on the desktop, and a throwaway Ubuntu LTS VM or container for Linux | Yes; Sandbox is clean on every launch by design | One afternoon to set up; the Linux VM doubles as `T-321`'s oldest-glibc target |
| **C. Accept developer-machine evidence** with the surrender recorded | No | Nothing now; the first user with a missing `.so` is the test |

**Recommendation: B.** It is genuinely clean, it costs no hosted minutes, and the Linux half is the
same machine `T-321` needs anyway. *A* is the fallback if *B* cannot be arranged, and *C* is
recorded here only so that choosing it is a choice.

#### Acceptance criteria

- A `REL-` (or `OPS-`) entry naming the option, and **what "clean" means operationally**: no
  Python, no Qt, no ffmpeg on Windows (it is bundled), no developer toolchain — checked by a
  command run before the install, whose output is retained
- For each platform, an evidence file under `docs/project/evidence/` per release candidate:
  machine identity, the pre-install check, the install, first launch, one real download, exit
- If *A*: the variable flip is written into `docs/RELEASE.md` as a step, with its reversal
- If *B*: the setup is documented well enough that the maintainer can recreate the VM in a year

#### Out of scope

- Restoring clean-machine CI permanently. `OPS-010`/`OPS-012` stand; this is per-release evidence

---

### T-330 — The Windows job runs the suite serially, and is at 97% of its bound

**Status:** **In Review** — implemented 2026-09-12; **the three consecutive green runs its own
criteria ask for are outstanding**, and until they exist this is a change that has not been
watched. Filed 2026-09-11 from three consecutive runs at **98%, 98% and 97%** of the 40-minute
bound. **Maintainer ruled the direction the same day**: parallelise, rather than raise the
number.
**Owner:** Implementer
**Priority:** Medium — nothing is failing, and the next test added tips it into timeouts
**Phase:** Phase 5 (CI capacity; found during Phase 4's exit evidence)
**Depends on:** nothing
**Relevant context:** `T-259` (*"a bound is crossed by growth, not by faults — re-measure before
raising it"*); `.github/workflows/ci.yml:794` the Windows invocation and `:430` the Linux one;
`OPS-010`; `T-074` (the intermittent Windows segfault, Blocked)
**Affected surfaces:** `.github/workflows/ci.yml`'s `windows-desktop` job
**Risk:** Medium — `xdist` on Windows is the one change that could surface `T-074`

#### The measurement

| Head | Elapsed | Of the 40-minute bound |
|---|---|---|
| `2ea1aa6` | 39.3 min | 98% |
| `88fc6b1` | 39.3 min | 98% |
| `59598de` | 38.9 min | **97%** |

The job's own reporter warns past 85%, citing `T-259`. **A timeout also reads as *cancelled*
rather than *slow***, which cost an hour of diagnosis on 2026-09-11 before the orphaned-session
trap was identified — so the failure mode is not merely a red job, it is a misleading one.

#### The cause, and why this is not a bound problem

**Windows runs the whole suite serially.** `ci.yml:794` is `pytest -v --junitxml=…` with no
`-n`. The Linux `check` job at `:430` runs its unit/UI slice with `$parallel` and only the
integration slice serially. Measured locally on Linux, the same suite is **184 s** with `-n auto`
against **1,045 s** serial — 5.7×. Windows need not match that, but 36:22 serial is the number to
attack rather than the 40 that contains it.

#### 2026-09-12 — implemented; the three runs are what remains

The `Full suite` step was one serial `pytest -v` over everything. It is now the **same two
invocations the Linux `check` job uses**, in the same order: `tests/unit tests/ui` with `-n auto`,
then `tests/integration` serial.

**The integration slice stays serial deliberately**, not by omission. `T-123` has two open defects
that appear only under parallel load there — `test_manager.py` scans every process on the machine
and kills other workers' children, and a retry deadline stops firing under load. Parallelising
that half would trade a slow job for a flaky one.

**The split collects the same tests as the bare invocation it replaces**, checked rather than
assumed: `pytest --collect-only tests` and
`pytest --collect-only tests/unit tests/ui tests/integration` both report **4,245**. `tests/network`
is deselected by `addopts` either way, and nothing else lives outside those three directories.

**`reports/pytest.{xml,txt}` becomes `reports/pytest-unit-ui.*` and `reports/pytest-integration.*`**,
matching the Linux job. Nothing reads those names — checked; the only references are three
historical review records describing runs that already happened.

#### 2026-09-12 (later) — driven on `STARBASE` directly, before spending another CI run

**The parallel slice runs clean on Windows in 4 minutes.** Run through
`tools/windows/run-on-starbase.sh` — the logged-on session, `QT_QPA_PLATFORM=offscreen`, exactly
what the job's own step invokes:

```
3848 passed, 40 skipped, 17 warnings in 240.43s (0:04:00)
```

**Against the serial baseline of 39.1–39.5 minutes** the maintainer's own runner console
corroborated for four consecutive jobs on 2026-09-11. The step is not the whole job, so the job
total will not fall by that ratio — but the number the bound was being crossed by is the one that
moved.

**Done here rather than by pushing**, because five CI attempts had already been spent on this: four
cancelled by pushes of mine and one failed on an `os.geteuid` call that Linux mypy cannot see. A
Windows CI run costs ~40 minutes of the one available slot; the same evidence cost four minutes
over SSH.

**Three failures on the first attempt, none of them parallelism** — and establishing that was the
point:

| Failure | Cause |
|---|---|
| `test_toolchain_versions` ×2 | `.venv\Scripts` was not on `PATH`; the tests shell out to `ruff`/`mypy` by name |
| `test_the_default_spawner_actually_runs_the_command` | runs `["true"]`, which on Windows exists **only under Git bash** |

**All three failed *serially* too**, which is what ruled parallelism out — the discriminator, run
before drawing a conclusion.

**The third is a real latent defect and is fixed.** That test's docstring said *"`true` is on
every Linux image"* and it carries **no platform guard**: it passes on the `windows desktop` job
only because that job's steps run under Git bash, which puts Git's `usr/bin` on `PATH`. A test
whose result depends on which shell invoked pytest will break for a reason unrelated to what it
asserts. It now runs `sys.executable -c ""`, which exists on any machine that can run the suite.

**`test_artifact_gates.py`'s `ldd` shim was Unix-only, which the earlier CI run found.** Six tests
failed on Windows and **two passed for the wrong reason** — they assert only *that problems are
reported*, and received the missing-linkage-evidence complaint rather than the one they were
written for. The shim now skips on Windows with the reason stated; nothing is given up, because
the loader half of §8 item 11 is Linux-only by construction and
`test_windows_keeps_the_presence_check_alone` covers the Windows path.

#### 2026-09-12 (later still) — run 1 of 3, green, and the number the bound asked for

**`windows desktop` in 16.3 minutes.** Run
[`34708223001`](https://github.com/kottmans/tracks-and-trails/actions/runs/34708223001) at
`66accdc`, every job green.

| | elapsed | of the 40-minute bound |
|---|---|---|
| serial, four consecutive jobs 2026-09-11 | 39.1–39.5 min | **97–98%** |
| parallel unit/UI slice | **16.3 min** | **41%** |

**That is `T-259`'s measurement, not a smaller percentage asserted.** The bound was being crossed
by growth; it now has 23 minutes of headroom rather than 40 seconds. The job total more than
halved even though only one of its steps changed, because that step was most of the job.

**Runs 2 and 3 are deliberately not dispatched yet.** `STARBASE` is about to be rebooted to bring
up Windows Sandbox for `T-318`, and a run cancelled or failed by a restart mid-job would cost a
slot and leave a red that means nothing. Three *consecutive* green runs is the criterion, and a
run killed by a reboot is not a data point about parallelism.

**Not yet closed.** The acceptance criteria ask for **three consecutive green runs**, and `T-056`
— an open Windows defect about whether a process is alive — is exactly the question parallel load
perturbs. That is also what the `check` job's comment means by *"the Windows legs stay serial
until someone can watch a parallel run there"*: this is the watching. **The new elapsed time is
recorded here once those runs exist**; until then this task is not done, and if it destabilises,
the finding is recorded and the job goes back to serial.

#### Acceptance criteria

- The Windows unit/UI slice runs parallel, the integration slice stays serial, **and the split is
  the same shape as the Linux job's** rather than a second arrangement
- **The new elapsed time is recorded here**, with the bound re-measured against it — `T-259` asks
  for the measurement, not a smaller percentage
- **A parallel run is green three times consecutively before this closes.** `T-074` records an
  intermittent segfault on this machine; `xdist` changes process counts, and one green run would
  not distinguish a fix from luck
- If parallelism destabilises it, **the finding is recorded and the job stays serial** — a flaky
  fast job is worse than a slow reliable one, and that outcome closes this task rather than
  reopening the bound question

#### Out of scope

- `T-074` itself, which stays Blocked on a person at `STARBASE`
- The Linux job, which is already split

---

### T-321 — The Linux release artifact, built where it will run

**Status:** **In Review** — the artifact is built, runs on a clean machine and on the maintainer's
desktop, and has downloaded a video. One bound is stated below and one question is left for the
maintainer. Started under the maintainer's
ruling relaxing §Phase 5's *Phase 4 approved* prerequisite.

#### 2026-09-11 (later) — built in a container, and it runs where nothing is installed

**`packaging/build_appimage.sh`**, run in `python:3.14-slim-bookworm`:

```
podman run --rm -v "$PWD":/src:ro,Z -v "$PWD/dist":/out:Z \
    docker.io/library/python:3.14-slim-bookworm /src/packaging/build_appimage.sh
```

**The base is not the Ubuntu LTS this task proposed, and the swap is an improvement.** It carries
Python 3.14 already and is **glibc 2.36** against Ubuntu 24.04's 2.39, so it covers more machines;
there is no 3.14 image on an older Debian. **The floor that buys is Debian 12 / Ubuntu 24.04 and
newer — Ubuntu 22.04 is glibc 2.35 and is out of reach.**

*(This said "and the README claims exactly that". **It did not** — `Debian 12` and `Ubuntu 24.04`
appear nowhere in `README.md`, checked 2026-09-12. The floor lived only in a build script's
comments. It is now in `docs/RELEASE.md` as a release-page requirement, and the README's Install
section takes it when `T-320` adds one. Corrected rather than deleted, because a false claim about
where a claim lives is the kind this project keeps finding.)*

**Why the container rather than this desk, measured rather than argued:**

| Built on | Bundled libraries require | Runs on Ubuntu 24.04 |
|---|---|---|
| the development machine, glibc 2.43 | **`GLIBC_2.43`** | **no** |
| the container, glibc 2.36 | **`GLIBC_2.36`** | yes |

**The executable itself needs only `GLIBC_2.14` in both**, which is what makes this silent: anyone
checking the binary would conclude the desktop build was fine. The requirement lives in the
bundled `.so` files.

**The first build of it could not open a window, and that is the finding.** The slim image has no
Qt runtime libraries, so PyInstaller's PySide6 hook could not import `QtCore` in the child process
it uses to ask Qt where its plugins live. It logged `failed to obtain Qt library info` as a
**warning** and carried on, producing an artifact with **no platform plugins at all**.

**It passed everything below.** `--version`, the spawn probe, the yt-dlp probe, the database probe,
all four artifact gates — because **none of them creates a `QApplication`**. It died on the
maintainer's real desktop with `SIGABRT` inside bundled `libQt6Core`, and the coredump showed it
resolving `libbrotlicommon`, `libharfbuzz`, `libfontconfig` and `libglib` from **Fedora RPMs**,
because those had not been bundled either. Qt's own message named it exactly: *"Could not find the
Qt platform plugin"*.

The build now installs Qt's runtime dependencies, and **asserts the platform plugins came across**
before going any further — the check that would have caught this on the first build. Nothing else
in this project asks whether a window can open from a frozen artifact.

**`Tracks_and_Trails-0.1.0.dev0-x86_64.AppImage`, 68.2 MB** (49.9 MB before Qt's libraries and
plugins were actually in it). On `ubuntu:24.04` with **no `python3`, no Qt, no ffmpeg and no
toolchain**:

| Check | Result |
|---|---|
| **The application itself**, `QT_QPA_PLATFORM=offscreen` | **still running at 20 s**, no crash markers |
| `--version` | `0.1.0.dev0`, exit 0 — **and this is not a launch test**: it exits before a `QApplication` exists, which is how the broken build passed |
| `--spawn-probe` (`T-020`) | *spawned a child from this build, exchanged one message, and reaped it* |
| `--ytdlp-probe` (`T-033`) | *the frozen artifact carries a usable yt-dlp with its extractors* |
| `--database-probe` | ok |
| `artifact_gates.py` over the payload | **all four pass** |

**This is the first evidence this project has that the bundle is self-contained.** Every previous
Linux run was on a machine that already had Python and Qt installed.

**Validated from inside the built AppImage**, not from the sources it was made from:
`desktop-file-validate` **clean** on the shipped `.desktop`, `appstreamcli validate`
**successful** on the shipped `metainfo.xml`, and the icon present both at the AppDir root and
under `usr/share/icons/hicolor/256x256/apps/` — the two places launchers look.

**On the maintainer's Fedora desktop, 2026-09-11:** it starts, **downloads a video to
completion**, and once its desktop entry is installed it **appears in the launcher with its
icon**. That is `TESTING` §8 item 8's real download, taken on the artifact that ships.

**`--ytdlp-update-probe` passes on the AppImage too**, which is §8 item 10: install a user-managed
copy, resolve it in a child, revert to the bundled baseline. Run with a substituted `HOME`, it
wrote **only** under that profile and nothing under the default one — `T-298`'s isolation, asked
of the artifact rather than the checkout.

**One gap this exposed, and it is a decision rather than a defect.** The `.desktop` inside the
AppImage says `Exec=tracks-and-trails`, which resolves only *within* the bundle. Installed as a
menu entry it has to be rewritten to the AppImage's own path — `AppImageLauncher` does that
automatically, and a user without it gets a menu entry that does nothing. **Three ways out and
none is taken yet**: recommend `AppImageLauncher` in the README, ship an `--install` step in the
artifact, or accept it and document the two-line manual integration. `T-322` meets the same
question on Windows, where the installer creates the shortcuts.

**`libGL.so.1` is deliberately not bundled**, and the clean-machine model accounts for it: an
AppImage must not ship the graphics stack, because it has to match the user's driver. A bare
`ubuntu:24.04` has none at all, which no real desktop lacks, so the test container installs
`libgl1`/`libegl1` and nothing else — still no Python, no Qt, no toolchain.

**It starts on the development desktop too** — Fedora, glibc 2.43, built against 2.36.

**One stated bound remains.** The clean-machine evidence is a launch, the four probes and the
gates — **not a real download**, which needs the GUI driven and has no headless route. The real
download was taken on the Fedora desktop instead, and the criterion asked for one *on each*.
`packaging/frozen_smoke.py` does not cover the last of those — it answers `ARC-002`'s process
question and downloads nothing — so `TESTING` §8 item 8's *"run one real download"* has no
automated route on this artifact and is a sitting, not a script.

#### 2026-09-12 — the review's two findings, and what the first one found

**`T321-R2`: the documented command did not produce an AppImage.** The header of
`build_appimage.sh` and the entry above both give one `podman run` line as the whole recipe. A
fresh `python:3.14-slim-bookworm` has no `appimagetool`, and the script packed only
`if [ -x /usr/local/bin/appimagetool ]` — otherwise it copied out an AppDir and printed `done`.
Nothing put the tool there. **The 68.2 MB AppImage above was packed with a binary installed by
hand in a container nobody else has**, which is a manual step masquerading as a recipe.

The script now fetches it: **version 1.9.1, pinned, and verified by SHA-256 before it is used**.
An unpinned `continuous` download would make the artifact depend on whatever was published that
morning, and a build tool fetched without a digest is a supply-chain hole in the one script whose
output gets signed and shipped. **The `else` branch is gone** — packing is the point, and a run
that quietly produced an AppDir instead looked like a success, which is how this survived.

Verified by running the documented line verbatim on a clean checkout:
`Tracks_and_Trails-0.1.0.dev0-x86_64.AppImage`, **66 MB**, no manual step.

**`T321-R1`: the clean-machine evidence had no real download**, which the entry above states as a
bound. A bound that never closes is a gap, and this one covered the single thing a clean machine
is uniquely able to disprove: that the bundle can reach a real site, over TLS, with its own
certificates, and write a file.

`--download-probe` closes it. It calls **`run_session`** — the same function the spawned worker
runs — so yt-dlp is resolved the way a job resolves it, the extractor runs, and the bytes land
through the real writer. Not the GUI, and deliberately not a parallel implementation. It takes the
same URL `tests/network/test_real_download.py` uses, so a disagreement between them is the
artifact rather than the site. **It reports failures**: handed a dead host it exits 1 as `network`,
handed a 404 it exits 1 as `extractor_error` — checked before it was trusted to pass.

**And on the first clean-machine run it failed.**

```
FAIL: the download failed as network: ERROR: [generic] big_buck_bunny_720p_surround:
Unable to download webpage: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
self-signed certificate in certificate chain (_ssl.c:1082)
```

**The AppImage carries no CA bundle of its own.** `ubuntu:24.04` ships with `/etc/ssl/certs`
**empty** — measured, zero files — and the bundle contains no `certifi`, so every HTTPS request
fails. Adding `ca-certificates` and *nothing else* (still no Python, no Qt, no ffmpeg, no
toolchain) makes the same probe download **61,878,609 bytes in 6.5 s from the bundled baseline
yt-dlp**.

**This is a decision, not a defect to quietly fix, and it is the maintainer's.** Every desktop
distribution ships `ca-certificates`, so no real user meets this. But bundling `certifi` is not
obviously right either: it would make the application ignore the *system* trust store, which is
where a corporate root or a user-added CA lives — so the fix that helps a bare container breaks
the user behind a TLS-inspecting proxy. Three ways out:

| Option | What it costs |
|---|---|
| **A. Leave it.** Record the dependency in the README's requirements | Nothing. A machine with no CA store cannot do HTTPS at all, and that is true of every application on it |
| **B. Bundle `certifi` as a fallback** — use it only when the system store is empty or unusable | A little code and a test; keeps corporate CAs working, which a plain bundle would not |
| **C. Bundle `certifi` outright** | Simplest, and **wrong for anyone behind a TLS-inspecting proxy** |

**Recommendation: A**, with the requirement written down. B is defensible if a user ever reports
it; C should not be taken.

**Ruled A by the maintainer on 2026-09-12**, recorded as
[`REL-007`](DECISIONS.md#rel-007--the-artifacts-use-the-system-certificate-store-and-bundle-none).
The requirement is written down in `docs/RELEASE.md` under *What the release page must state*,
with the glibc floor beside it, and `T-320`'s deferred README Install section is named as where
both go when it exists. The clean-machine harness installs the package with the reason in its own
output, so the boundary is stated rather than quietly satisfied.

**The evidence file is `docs/project/evidence/linux-0.1.0.dev0.md`** — pre-install check, all six
probes, and a launch held offscreen for 20 s. `--version` is still not a launch test; the launch
is.

#### 2026-09-11 — the AppDir's three files, and what is deliberately still missing

**Done, and validated by the tools that own the formats** rather than by a parser of mine:

- `packaging/appdir/io.github.kottmans.TracksAndTrails.desktop` — `desktop-file-validate` **clean,
  no hints.** One main category (`AudioVideo`), because two put the application in two menus and
  the validator says so.
- `packaging/appdir/io.github.kottmans.TracksAndTrails.metainfo.xml` — `appstreamcli validate`
  **successful**, informational messages cleared.
- `packaging/appdir/AppRun` — **prepends** to `PATH` rather than setting it. That is the whole of
  `REL-004`'s reasoning in one line: `OPS-001` makes ffmpeg a system dependency on Linux and
  `REQ-024` finds it on `PATH`, so an `AppRun` that shadowed the host's copy would break merging
  on every machine that has it — the failure Flatpak was rejected for.
- `tests/unit/test_appdir_metadata.py` — seven cross-reference checks. Each of these files repeats
  something declared elsewhere (the binary name from the spec, the licence from `pyproject.toml`,
  the component id from the desktop file's own name) and nothing fails when a copy drifts.
  **Both mutations the docstrings name were run**: renaming `Exec` and replacing `PATH` each fail
  exactly one test. Format validation is *not* reimplemented here — the two validators own that.

**What remains, and why none of it could be done now:**

- **The build host.** `REL-004` requires building against the oldest glibc the README claims, and
  `REL-006`'s Ubuntu LTS VM is that machine. It does not exist yet.
- **`appimagetool` is not installed** on the development machine, so no `.AppImage` has been
  produced — only the AppDir contents that go into one.
- **Every acceptance criterion about the built artifact** — launching on a clean machine, the three
  probes running against the AppImage rather than the one-dir tree, the icon appearing in a
  launcher — needs that artifact and `T-318`'s evidence harness.

*(Filed 2026-09-11 with the Phase 5 plan, written against **AppImage** as `T-106` recommended.
`REL-004` ruled that way on the same day, so the task starts as written rather than being bent to
fit a different format.)*

**Owner:** Implementer
**Priority:** High — it is the other artifact
**Phase:** Phase 5
**Depends on:** `T-106` (the format), `T-320` (the version); `T-318` if it chose a Linux VM, since
that is the build host this task wants
**Relevant context:** `REL-001`; `OPS-001` (ffmpeg stays a system dependency); `OPS-012`'s surrender
— *"a Fedora-built binary may not run on an older distro … `REL-001`'s release build is Phase 5
and must revisit where Linux artifacts are produced"*; `NFR-004`; `NFR-009`; `REQ-024`; `T-298`
**Affected surfaces:** `packaging/` (an AppDir recipe, `.desktop`, AppStream `metainfo.xml`),
`.github/workflows/`, `docs/DEVELOPMENT.md`
**Risk:** Medium — glibc symbol versioning is a silent failure: the artifact builds, runs on the
build host, and dies with `GLIBC_2.38 not found` on the user's machine

#### Scope

**Build against the oldest glibc the README will claim.** `OPS-012` moved the frozen Linux build
onto Fedora and recorded exactly this consequence. The release build therefore runs in a
**container of the oldest supported distribution** — proposed: the current Ubuntu LTS, which is
also the `apt` platform `OPS-012` says is *"no longer exercised anywhere"* — on the self-hosted
Linux runner. The README's platform line then says what was actually built and tested against.

**AppDir from the PyInstaller tree**: `AppRun` launching the frozen binary, a `.desktop` entry,
the icon set that already exists under `resources/icons/`, and an AppStream `metainfo.xml` so
desktop environments show a name and description rather than a filename. Built with `appimagetool`
into `Tracks_and_Trails-X.Y.Z-x86_64.AppImage`.

**ffmpeg is not inside** (`OPS-001`), and the existing `REQ-024` path already reports its absence
and degrades; this task adds nothing there beyond confirming the AppImage's `PATH` search sees the
host's ffmpeg.

**`NFR-004` holds**: `XDG_*` resolution from inside an AppImage is the same as from source, which
`T-298`'s isolation gate pins — assert it on the built AppImage, not by inference.

#### Acceptance criteria

- The artifact is produced by a documented command on the container image the README names, and
  the image's glibc version is recorded with the artifact
- It launches on a **clean** machine of that distribution (`T-318`'s evidence), and on the
  Fedora desktop, and runs one real download to completion on each
- `T-020`'s spawn probe, `T-033`'s yt-dlp probe and `T-298`'s isolation check all pass **against the
  AppImage**, not only against the one-dir tree it was made from
- The `.desktop` entry and `metainfo.xml` validate (`desktop-file-validate`, `appstreamcli
  validate`) and the icon appears in the launcher
- Qt inside the AppImage is dynamically linked (`T-323` gates it; this task keeps it true)

#### Out of scope

- Flatpak or system packages, unless `T-106` rules otherwise
- A Linux ffmpeg bundle — `OPS-001`'s reopening condition, not this task's

---

### T-329 — The focus-ring floor mismodels a header, and Windows is where it shows

**Status:** **In Review** — both findings answered 2026-09-11. `T329-R1` corrected; **`T329-R2`
executed on `STARBASE`**, below. The maintainer ruled option A the same day, it is implemented, and the normal
Windows job confirms it: run `34653977245` at `59598de` is green, with the full Windows suite at
**4,152 passed / 36 skipped**.

#### 2026-09-11 — the review's two findings

**`T329-R1` — corrected. The helper measured the wrong section in every state but the audited
one.** `_focused_section` read `header.currentIndex()`; `SortableHeader` paints its ring on
`current_section()`. The two agree at zero — which is the state every sweep opens in — and diverge
the moment a user sorts another column, where the ring is painted on a section of **64 to 77**
pixels while the model still reports section 0 and its **84**. The helper now asks whatever paints
the ring, falling back to the model index and then to section 0 for a plain `QHeaderView` that
paints none.

**Covered by a case driven off the shared inventory**, not a header built to suit it:
`test_a_header_is_measured_by_the_section_it_actually_paints` moves each header to a
differently-sized section and checks the floor follows. **Mutation run**: restoring the
`currentIndex()` reading fails that case and nothing else.

**`T329-R2` — the Windows mutation, prepared but not run.** The evidence asked for is the
focus-removal mutation on **both** platforms; only Linux was supplied. It now has a home rather
than a one-off command:

- `tools/windows/mutations/mut_header_no_extra_ring.py` replaces `SortableHeader.paintSection`
  with `QHeaderView.paintSection`, so the application's extra ring is never painted — **a rendered
  control mutation, not a changed measurement**, which is the distinction the review drew.
- `run_mutations.py` gained per-case *selection* and *platform*, because `T-026`'s classes drive
  `-m windows_desktop` on the real plugin and this one drives the rendered focus sweep
  **offscreen** — the configuration the `windows desktop` job's own full-suite step uses, and
  therefore the one where this gate actually guards the product.
- **Its own unmutated baseline runs beside it**, since a different selection and platform is a
  different run and a pass under mutation means nothing without one.

**Validated on Linux before it is trusted on Windows**, reproducing the reviewer's own numbers:
**0 changed pixels against the 134 floor**, all six headers, both palettes, with the unmutated
control at **2 passed**.

#### 2026-09-11 — `T329-R2`, executed on `STARBASE`

**Implementation:** `mut_header_no_extra_ring` replaces `SortableHeader.paintSection` with
`QHeaderView.paintSection`, so the application's extra focus ring is never painted. A rendered
control mutation, not a changed measurement.

**Platform:** Windows, `STARBASE`, offscreen — the configuration the `windows desktop` job's own
full-suite step runs, and therefore the one in which this gate guards the product. Tree at
`a4db6f8`, **clean**, venv rebuilt from `pyproject.toml` first.

**The runs, verbatim** (`T329-R3`: this was a summary table, and a table is a claim *about*
evidence rather than the evidence — the two are not interchangeable when the number is the point).

Baseline, unmutated:

```
PS C:\dev\tracks-and-trails> .venv\Scripts\python.exe -m pytest -q "tests/ui/test_colour_is_never_alone.py::test_focus_is_visible_on_every_control_the_application_shows"
..                                                                                                               [100%]
2 passed in 3.36s
```

With `mut_header_no_extra_ring` loaded, which replaces `SortableHeader.paintSection` with
`QHeaderView.paintSection` so the application's extra ring is never painted:

```
PS C:\dev\tracks-and-trails> $env:PYTHONPATH="tools\windows\mutations"
PS C:\dev\tracks-and-trails> .venv\Scripts\python.exe -m pytest -q -p mut_header_no_extra_ring "tests/ui/test_colour_is_never_alone.py::test_focus_is_visible_on_every_control_the_application_shows"
FF                                                                                                               [100%]
...
E       AssertionError: in light, focus is drawn by changing a colour rather than the edge on:
SortableHeader  on format panel: 0 pixels change in brightness on focus, under the 121 its size asks for;
SortableHeader  on format panel: 0 pixels change in brightness on focus, under the 121 its size asks for;
SortableHeader  on format table: 0 pixels change in brightness on focus, under the 121 its size asks for;
SortableHeader  on format table: 0 pixels change in brightness on focus, under the 121 its size asks for;
SortableHeader  on queue format dialog: 0 pixels change in brightness on focus, under the 121 its size asks for;
SortableHeader  on queue format dialog: 0 pixels change in brightness on focus, under the 121 its size asks for

tests\ui\test_colour_is_never_alone.py:1093: AssertionError
=============================================== short test summary info ===============================================
FAILED tests/ui/test_colour_is_never_alone.py::test_focus_is_visible_on_every_control_the_application_shows[light] - AssertionError: in light, focus is drawn by changing a colour rather than the edge on: SortableHeader  on format pa...
FAILED tests/ui/test_colour_is_never_alone.py::test_focus_is_visible_on_every_control_the_application_shows[dark] - AssertionError: in dark, focus is drawn by changing a colour rather than the edge on: SortableHeader  on format pan...
2 failed in 3.80s
```

**Both palettes, all six headers** — the `[light]` failure is quoted in full above and `[dark]`
reports the same six at the same floor. The ellipsis stands only for Qt's
`propagateSizeHints()`/`raise()` warnings from the offscreen plugin, which the run emits in
volume and which say nothing about this gate.

**The Windows floor is 121 where Linux is 134**, and that is the section-based model working
rather than a discrepancy: the floor is derived from the focused section's own geometry, so it
followed Windows drawing that section about twelve pixels narrower. A perimeter floor baked in
from Linux would not have. Both are far above the 0 the mutation produces.

**Getting there took five environment faults, none of them this correction**, recorded where the
next person meets them: `T-331` for the driver, and `docs/WINDOWS_VERIFICATION.md` for the
bundle-backed remote, the shallow runner clone, the stale checkout and the stale venv. Filed the same day from the first native Windows run of the corrected tree
(`P4EXIT-R2`'s evidence run, `34645329305` at `65f57e9`). **Blocks that evidence**: `windows
desktop` failed on it, so `R2` cannot be satisfied while it stands.

#### 2026-09-11 — implemented, and what it measures now

`one_more_ring` grows one branch: a `QHeaderView` is measured by the **section focus is drawn on**,
not by its own perimeter. `_focused_section` takes the current index's section — logical index 0 on
every header this sweep reaches, measured at **84×30** against widgets of 198 to 312 — and falls
back to the first section when there is no current index.

**The race is gone rather than widened.** The floor for those headers is now **134** and
*constant*, because it no longer scales with a width the indicator never used:

| | ink changed | old floor | new floor | old margin | new margin |
|---|---|---|---|---|---|
| Linux | 430 | 392–408 | **134** | +22 to +38 | **+296** |
| Windows | 386 | 389–404 | **134** | **−3 to −18** | **+252** (projected) |

**The mutation the criteria ask for was run, and it is a real one** rather than an arithmetic
stand-in: styling the sections flat (`QHeaderView::section { background: …; border: none; }`) makes
the native focus rect disappear, the measured change falls to **0**, and the sweep fails on that
header. A control that stops drawing its focus is still caught at the new floor.

**Nothing else moved.** Every control whose focus really is drawn around itself keeps the perimeter
model, and `MINIMUM_FOCUS_RING_SHARE` is untouched at `0.6` — `T202-R2` measured it at 0.82–1.94
across every bordered control, and option C would have blunted it for all of them to accommodate
one mismodelled class.
**Owner:** Implementer; the choice between the options below is the maintainer's
**Priority:** High — it is the only thing failing the Windows job, and Phase 4's exit waits on it
**Phase:** Phase 4 (accessibility gate), found during Phase 5
**Depends on:** nothing
**Relevant context:** `one_more_ring` and `MINIMUM_FOCUS_RING_SHARE` in
`tests/ui/test_colour_is_never_alone.py`; `T202-R2` which measured the constant; `T-200` which
made `SortableHeader`'s keyboard route real; `NFR-005`
**Affected surfaces:** `tests/ui/test_colour_is_never_alone.py`
**Risk:** Medium — it changes a gate that currently carries `P4EXIT-R1`'s evidence

#### What fails

`test_focus_is_visible_on_every_control_the_application_shows`, **both palettes**, on the three
surfaces carrying a `FormatTable`:

```
SortableHeader on format panel:        386 pixels change, under the 389 its size asks for
SortableHeader on format table:        386 pixels change, under the 404 its size asks for
SortableHeader on queue format dialog: 386 pixels change, under the 389 its size asks for
```

#### The cause, measured on both platforms rather than inferred

`one_more_ring(widget)` is `2 * (width + height) - 4` — **the perimeter of a one-pixel ring around
the whole control** — and the floor is `0.6` of it. That model fits a button, a line edit and a
list. **It does not fit a `QHeaderView`**, which draws focus on its *current section* rather than
around itself, so the ink it changes is **constant** while the floor rises with the header's width.

| Platform | Pixels changed | Floor at 299 px wide | at 312 px | Margin |
|---|---|---|---|---|
| Linux | **430**, constant | 392 | 408 | +38 / **+22** |
| Windows | **386**, constant | 389 | 404 | **−3** / **−18** |

**So this is a size race, and Linux is 22 pixels from losing it too.** Windows loses first only
because its section focus rect is smaller. Widen the table by about 30 pixels — one more column,
a longer codec name, a larger font — and Linux fails identically. `T-259`'s rule applies to a
different bound but says the same thing: a threshold crossed by growth is not a fault.

**The product is not at fault.** A focused header changes 386–430 pixels of geometry, which is
exactly what `NFR-005` asks for: focus that reads without colour. The metric, not the application,
is what mismodels this control.

#### Options

1. **Model a header's focus as its section, not its perimeter.** `one_more_ring` grows a
   `QHeaderView` case that uses the current section's rect. Keeps the floor scaling for everything
   else, and states in one place why a header is different. *Cost:* the sweep gains a control-class
   special case, which is the thing this file has resisted.
2. **Cap the floor.** Keep the perimeter model but stop the floor rising past what any focus
   indicator plausibly draws. *Cost:* an arbitrary constant, and it weakens the floor for large
   controls generally — a list that genuinely stopped drawing its ring could pass.
3. **Measure the change against the focused region rather than the whole widget.** The most
   faithful, and the largest change to a gate that is currently load-bearing evidence.

**Recommendation: (1).** It is the only one that keeps the rule exact for every other control, and
the special case is honest — a header really is a different shape of control, and the file already
skips `qt_` internals for a comparable reason. **Do not lower `MINIMUM_FOCUS_RING_SHARE`**: it was
measured at `0.82`–`1.94` across every bordered control (`T202-R2`), and moving it to accommodate
one mismodelled class would blunt it for the rest.

#### Acceptance criteria

- The Windows job passes without loosening the rule for any control the perimeter model does fit
- **A mutation proves it still catches the defect it exists for**: a header that recolours on focus
  without changing geometry fails, on both platforms
- The Linux margin is no longer a race — stated as a measurement, not an assertion
- Whatever is chosen is recorded where `MINIMUM_FOCUS_RING_SHARE`'s own measurement is recorded

#### Out of scope

- `MINIMUM_FOCUS_RING_SHARE` itself, unless the ruling says otherwise
- The Windows job's 40-minute bound, which the same run reported at **98%** — a separate matter

---

### T-323 — Executable gates over the built artifact

**Status:** **In Review** — implemented 2026-09-11 against the smoke build, as its own
dependency line allows. Filed the same day with the Phase 5 plan.

#### 2026-09-11 — the four checks, and the two things they found

`packaging/artifact_gates.py`, wired into the `frozen` job. **All four run in 1.2 s** over a real
PyInstaller build.

**It found its subject missing on the first run.** The artifact carried **no licence texts at
all** — `packaging/licenses/` did not exist and the spec bundled nothing — so `LIC-001`'s
*"their license texts must ship with every distributed artifact"* was unmet in every build to
date. The texts are now in `packaging/licenses/` with provenance in its `README.md`, and the spec
bundles them via `SPECPATH` rather than a relative path that resolves against the caller's cwd.

**And `T031-R2`'s rule earned its keep.** The Qt check originally globbed for the library files
and **passed with `libQt6Widgets.so.6` deleted** — the bundle carries Qt **twice**, at
`_internal/` and `_internal/PySide6/Qt/lib/`, so one copy satisfied it. It now also asks `ldd`
where each dependency resolves: a static build lists none, a build borrowing the host's Qt
resolves outside the tree, and a deleted library resolves to *not found*.

**The mutations, on a real build:**

| Item | Mutation | Result |
|---|---|---|
| 11 · Qt dynamic | remove **every** copy of a required module | **FAIL** |
| 12 · licences | delete any one of the four files | **FAIL** |
| 13 · no secrets | plant the home path in a data file | **FAIL** |
| 9 · yt-dlp purity | drop a `.so` or `.pyd` into the tree | **FAIL** |

**Scope's suggested mutation for item 11 — *"deleting one fails"* — is not a mutation of the
property**, and that is recorded rather than worked around: with two copies shipped, deleting one
leaves Qt dynamically linked and resolving inside the artifact, which is all the item claims.

**One false positive, kept as a test.** Searching for the bare user name reported
`libbrotlicommon.so.1` — brotli's built-in English dictionary contains those four letters inside
ordinary words — while the real home path appeared in **no file**. The name now counts only
bracketed by path separators; `core/logging`'s own four-byte floor has the same reasoning.

**Outstanding:** `ffmpeg-LGPL.txt`, which needs `T-319`'s binary choice; the check requires it only
where ffmpeg is bundled, so no artifact is failed for lacking a licence for something it does not
ship. `T-324` wires the same script into the release workflow when it exists.

#### 2026-09-12 — the review's four findings, and what the first one cost

**`T323-R1` found the item 11 gate passing with its subject deleted — again.** The entry above
records that defect being fixed by adding the loader check. It was not fixed. The reviewer's
mutation — delete the real `libQt6Widgets.so.6` — still passed **every** gate, three ways at once:

1. The glob accepted a **dangling symlink**. The note above says the bundle carries Qt at two
   paths; what it does not say, and what makes the difference, is that the second is a *symlink to
   the first*, not an independent copy. `rglob` returns a dangling link, so deleting the only real
   file left something that looked like a library.
2. The loader half then inspected `extensions[:4]` — an arbitrary cap. **QtWidgets sorts fifth**
   in a real build, so the one module the mutation removed was the one never asked about.
3. And an inspection that *could not run* — no `ldd`, a failed call — returned no problems, which
   is indistinguishable from no problem found.

Fixed: `is_file()` (which follows the link), no cap, every binding inspected, **positive
per-module linkage evidence** required rather than absence of complaints, and any failed
inspection reported. Reproduced the reviewer's exact topology — real library plus symlink, delete
the real one — and it now fails two ways: the dangling-symlink message, and the loader reporting
`resolves libQt6Widgets.so.6 to /lib64/libQt6Widgets.so.6, outside the artifact`.

**`T323-R2` — planted cookie material escaped the scan.** Patterns ran only over an allowlist of
text suffixes and skipped lines past column 2000, so a `Cookie:` header in a `.bin`, in an
extensionless file, or on a long line all survived. Nothing is decided by suffix or line length
now. What a file's content decides is only **which half of the vocabulary** runs, and that split
is by measured cost, over this artifact's 337 binary files (206 MB):

| Pattern | Over 206 MB of binaries | In the gate |
|---|---|---|
| `_COOKIE_WITH_A_VALUE` | 10.7 s, no false positives | every file |
| `_URL_CREDENTIALS` | 13.2 s, no false positives | every file |
| `_COOKIE_FILENAME` | **171 s on `libQt6Gui.so.6` alone** | text only |
| `_COOKIE_PATH` | same nested-quantifier shape | text only |

**Truncating does not rescue the costly two** — the same library capped to `MAX_SCANNED_BYTES`
still took 170.7 s, because the blow-up happens inside the first two megabytes. So the split is by
file kind, stated on the constants, not by a size bound pretending to be a cost control. All six
of the reviewer's counterexamples now fail the gate, including a NUL-leading binary, which the
first fix would still have skipped. **The gate now takes 23.4 s, not the 1.2 s recorded above** —
that is what covering the binaries costs, and it is affordable for something that runs per build.

**`T323-R3`** (the interpreter's own install prefix is provenance, not a leak) and **`T323-R4`**
(the release-review prompt invited prose where a tool now produces evidence) are both closed. R4's
first attempt cited *"item 1"* for the version check; §8 item 1 is lint and mypy, and version
consistency is not a §8 item at all. Corrected against the list rather than from memory.

#### 2026-09-12 (later) — `T323-R4`: the R3 fix did not work, and CI is where that showed

**The first `frozen linux` run to execute this gate failed it**, on the same 110 hits `T323-R3`
was supposed to have fixed:

```
FAIL  item 13 · no secrets or personal paths
        _internal/libpython3.14.so.1.0 contains the build machine's home directory
        _internal/libpython3.14.so.1.0 contains the build machine's user name, in a path
        _internal/python3.14/lib-dynload/_asyncio.cpython-314-x86_64-linux-gnu.so contains the build machine's home directory
        … and 90 more
```

**R3 exempted `sys.base_prefix` — the path the interpreter is *installed* at — and that is not
the path in the binary.** CPython embeds the directory it was **built** in, in `__FILE__`
strings, `sysconfig` data and debug sections. Whoever built that CPython did so somewhere, and if
they did it in a home directory then every copy of it quotes one for ever. The run also reported
the **user-name-in-a-path** literal, which R3's exemption did not cover at all.

**Why this was not caught before pushing, which is the part worth recording.** R3 was verified
two ways, and neither could have failed: a unit test that monkeypatched `Path.home()` and
`sys.base_prefix` into agreement, and a local artifact whose Python lives at `/usr` — where the
exemption never fires because there is nothing to exempt. **The configuration that breaks it is
the one CI has and this desk does not**, and the gate had never run in CI before that push.

**The fix is by file, and only for the two path literals.** `is_interpreter_owned` names the
CPython runtime and its extension modules — `libpython*`, `lib-dynload/`, `python3.dll`, `DLLs/`
— which PyInstaller copies in byte-for-byte. A path inside one is a fact about a dependency, not
about this build: we copy those files, we do not author them.

**What that gives up, stated rather than implied:** a personal path existing *only* inside the
bundled interpreter would not be reported. Nothing here can put one there, and the alternative
measured worse — the gate failed every CI build, which is how a gate gets switched off.

**Reproduced against a real artifact, not only in unit tests.** CI's topology planted into a
fresh PyInstaller build on this machine — the build path in `libpython3.14.so.1.0` and twenty
`lib-dynload/*.so`, with the install prefix deliberately at `/usr`, nowhere near home:

| Planted | Gate |
|---|---|
| home + user name in 21 interpreter files | **passes**, reporting `42 path literal(s) excused as provenance` |
| the same path in `_internal/build_settings.json` | **FAIL** — the exemption is by file, not by string |
| `Cookie: sid=…` inside `libpython3.14.so.1.0` | **FAIL** — only the path literals are excused |

Four mutations, four caught — including one that **survived the first attempt**: excusing *every*
literal rather than the two path ones would have let a `.netrc` reference through an interpreter
file, and the docstring claiming otherwise was untested. 46 tests now.

**22 tests added, and every defect above mutated back in:**

| Mutation | Caught by |
|---|---|
| skip NUL-bearing files for the pattern half | `test_a_cookie_header_inside_a_real_binary_is_found` |
| cap the loader half at four bindings | `test_every_binding_is_inspected_not_only_the_first_few` |
| glob without `is_file()` | `test_a_dangling_symlink_is_not_a_usable_library` |
| an inspection that cannot run returns no problems | `test_an_inspection_that_cannot_run_is_not_a_pass` |
| drop the positive per-module linkage evidence | `test_bindings_that_declare_no_qt_at_all_do_not_pass_silently` |
| truncate silently instead of reporting | `test_truncating_the_costly_half_is_reported` |
| exempt the whole file once the prefix appears | `test_the_interpreters_own_prefix_is_provenance_not_a_leak` |
| skip the filename check | `test_a_cookie_store_is_a_leak_by_its_name` |

8 of 8, each caught by exactly the test that names it. The `ldd` cases use a **script on `PATH`**
rather than a patched `subprocess.run`, so the call the gate actually makes stays inside the test.

**Owner:** Implementer
**Priority:** High — four release-gate items are currently prose, and prose is not a gate
**Phase:** Phase 5
**Depends on:** `T-319` and `T-321` for something to gate; written so it runs against the smoke
build until they land
**Relevant context:** `TESTING.md` §8 items 9, 11, 12, 13; `NFR-009`; `LIC-001` (*"ship the
license texts, and keep those libraries dynamically linked so a user could substitute their own
build"*); `OPS-002` (the wheel-extraction update path needs a pure yt-dlp); `NFR-007`; `T-033`'s
probe extension and `T033-R4`'s data blindness; `T-298`
**Affected surfaces:** `packaging/`, `.github/workflows/ci.yml`'s `frozen` job, a new
`packaging/artifact_gates.py`, `docs/project/TESTING.md` §8
**Risk:** Low — each check is small; the risk is the usual one, a gate that passes with its
subject removed, which is why each is mutation-checked

#### Scope

Four checks, each **a mutation that turns the job red** (the house rule since `T031-R2`):

| §8 item | Check | The mutation that must fail it |
|---|---|---|
| 11 · Qt dynamically linked | The bundle contains Qt as shared libraries (`libQt6*.so*` / `Qt6*.dll`) and the executable imports none of Qt's symbols statically | Strip the Qt libraries from `dist/` and re-link a static stand-in — or simpler: assert the library files' presence *and* that `ldd`/`dumpbin /dependents` on the Qt plugin names them; deleting one fails |
| 12 · Licence texts present | `licenses/` in the artifact holds Qt's LGPLv3, ffmpeg's LGPL (Windows), yt-dlp's Unlicense, and a `NOTICE` stating the dynamic-link obligation in `LIC-001`'s words | Delete any one file |
| 13 · No secrets or personal paths | A scan of every file in `dist/` for the maintainer's home path, user name, `.netrc`, cookie-jar names and anything `logging.remember_a_secret` would redact | Plant one string in a data file |
| 9 · yt-dlp purity | The bundled `yt_dlp` tree contains no compiled extension (`*.so`, `*.pyd`), so `OPS-002`'s wheel-extraction update remains viable | Drop a `.pyd` into the tree |

**The scan for item 13 is the interesting one.** It reuses `core/logging`'s redaction vocabulary
rather than a second list, so a secret class added there is scanned for here without anyone
remembering — `T015-R1`'s rule applied to a gate.

#### Acceptance criteria

- All four checks run in the `frozen` job on both platforms and in `T-324`'s release workflow, and
  each was turned red by its named mutation on a real build, with the run ids recorded
- `docs/project/TESTING.md` §8 marks items 9, 11, 12 and 13 as **executable**, pointing at the
  check, and the manual release prompt in `docs/RELEASE.md` is narrowed to what remains manual
- The licence directory's contents are the exact upstream texts, with their versions and sources
  recorded in `packaging/licenses/README.md`

#### Out of scope

- Items 7, 14 and 15 — clean machine, cold start, the human session — which are `T-318`, `T-325`
  and `T-327` because a machine cannot take them

---

### T-320 — Versioning policy, release documentation, and the first version number

**Status:** **In Review** — implemented 2026-09-11 under the maintainer's ruling relaxing
§Phase 5's *Phase 4 approved* prerequisite for the start of the work. **Gates the start**: every
build stamps the version this decides, and `T-319`, `T-321`, `T-322` and `T-324` all depend on it.

#### 2026-09-11 — what was built, and the one judgement call in it

- **`docs/RELEASE.md`**, created per `DOC-002`'s *"when Phase 5 begins"* trigger. It references
  `TESTING` §8 rather than copying it — a copied gate drifts, and the copy is what people read —
  and names the three items no workflow can perform, so they are planned rather than discovered.
  Covers the version steps, the tag check, the release-commit-only files, draft-then-publish, the
  SmartScreen click-through `REL-005` makes necessary, and rollback.
- **`tools/version_tag_check.py`** and **`tests/unit/test_version_tag_check.py`** — the
  tag-to-version rule as a pure function with a CLI, the way `T240-R1` requires a decision that a
  workflow would otherwise bury in shell. **14 cases.** It refuses a mismatched number, a tag on a
  `.devN` commit, and seven tag spellings `REL-003` did not decide — `v0.1.0-rc1` among them,
  because accepting a pre-release channel here would be this checker deciding one.
  `test_the_repository_as_it_stands_today_cannot_be_tagged` is a **live** positive control: it
  fails if `main` ever stops carrying `.devN`.
- **Rollback is documented as asymmetric, which is the point.** The project and the user have a way
  back; **their data does not.** `DAT-001`'s migrations are forward-only and the application
  *refuses* a newer database rather than corrupting it, so a downgrade across a schema change costs
  the queue and history. `RELEASE.md` says so and requires it on the release page whenever a
  release carries a migration. *(That refusal did not exist when this was written — see
  `T320-R2` below.)*

#### 2026-09-12 — the review's two findings

**`T320-R1`: a release version turned the suite red.** Two tests here asserted flatly that this
checkout cannot be tagged, because `main` carries `.devN` between releases. But the commit that
drops the suffix is exactly the commit §8 item 2 runs the full suite on — so the assertions turned
the release gate red at the one moment it has to be green. Measured on `__version__ = "0.1.0"`:
`test_the_repository_as_it_stands_today_cannot_be_tagged` and
`test_the_tool_runs_as_a_script_against_this_checkout` both failed.

The property that holds in **both** states is the one worth asserting: *the tool's verdict about
this checkout is correct*. Between releases that means refusing to tag; on a release commit it
means accepting that version's own tag and no other. Both tests now branch on which state they
find, and both were run in both states.

**`T320-R2`: the documented refusal did not exist.** `RELEASE.md` and this entry both said the
application *refuses* a database from a newer version rather than corrupting it. `migrate()` skips
every migration at or below the database's version, so a database at 11 opened by a build that
knows 10 matched nothing, applied nothing, and returned `[]` — indistinguishable from an
up-to-date database. It then opened, and `compose()` ran recovery over a schema it does not
understand on the very next line.

`persistence/db.NewerSchemaError` is the refusal the documentation had already promised: raised
from `migrate()` before anything is applied, carrying the two versions and the file's path,
surfaced by `run()` as a message box and **exit 4** — distinct from 3 so a script can tell *another
copy is running* from *your library is newer than this build*.

| Mutation | Result |
|---|---|
| remove the guard (the behaviour as submitted) | 3 tests fail |
| `>=` instead of `>` | the boundary test fails, and two ordinary restart tests with it |

Five tests: the refusal, its message (it has to name the file — a dialog a user cannot act on is
not a remedy), the boundary at exactly the latest version, that the refused database is **byte-for
-byte unchanged**, and that it aborts `compose()` before recovery. The last hop — `run()`'s
`except` clause — is inside the uncovered region `present()`'s docstring already names, and is
left there rather than claimed.

**The judgement call, flagged rather than taken quietly.** Scope says the README *"gains an Install
section pointing at releases and loses 'there are no installers or packages yet'"*. **It has not**,
because that line is still **true** — no release exists, and swapping it now would make the README
claim installers that are not there. It is written into `RELEASE.md` as a release-commit step
beside `CHANGELOG.md` and `SECURITY.md` §Supported versions, both of which the same scope already
defers to the tag. If the reviewer reads that as unmet rather than sequenced, it is a two-line
change at the release commit.

**Criterion 5 evidence.** `grep -rniE "parity|everything yt-dlp|all of yt-dlp" README.md` returns
**no match** (exit 1). The only parity mention in the tree is `docs/YTDLP_OPTION_AUDIT.md`, which
describes `REQ-030`'s claim rather than making it.

**The scheme and the first number are ruled.** The maintainer accepted the proposal below on
2026-09-11, recorded as [`REL-003`](DECISIONS.md#rel-003--semver-and-the-first-release-is-010):
SemVer, `0.y.z` until `1.0` is declared, first release `0.1.0`. **What remains is the
documentation and the gate** — `docs/RELEASE.md`, `SECURITY.md` §Supported versions, the README's
install section, and the test that fails a `vX.Y.Z` tag on a commit whose `__version__` is not
`X.Y.Z`. It stays `Proposed` because Phase 5 has not opened, not because the decision is
outstanding.
**Owner:** Implementer proposes; Maintainer rules on the scheme and the first number
**Priority:** High
**Phase:** Phase 5
**Depends on:** nothing
**Relevant context:** `DOC-002` (`docs/RELEASE.md` is created *"when Phase 5 begins"*;
`CHANGELOG.md` *"at the first tagged release"*); `SECURITY.md` §Supported versions (*"when releases
begin, this section will name which of them receive fixes"*); `IMPLEMENTATION_PLAN.md` §Phase 5
deliverable *"versioning policy, release gate, and rollback procedure documented"*; `DAT-001`;
`OPS-002`; `docs/RELEASE.md`'s release review; `tests/unit/test_skeleton.py` (asserts
`--version` prints `__version__`); `[tool.hatch.version]` reads `src/tracks_and_trails/__init__.py`
**Affected surfaces:** `src/tracks_and_trails/__init__.py`, `docs/RELEASE.md` (new),
`CHANGELOG.md` (new, at tag time), `SECURITY.md`, `README.md`, `docs/DEVELOPMENT.md`
**Risk:** Low

#### Scope

**The policy, proposed.** SemVer, `0.y.z` until the maintainer declares `1.0`. `main` carries
`X.Y.Z.devN` between releases; a release commit sets `__version__ = "X.Y.Z"` and is tagged
`vX.Y.Z`; the next commit bumps to `X.Y.(Z+1).dev0`. **The first release is `0.1.0`** — it is what
`__init__.py` already says minus the `.dev0`, and `0.x` is honest about a release that ships before
`REQ-030`'s parity (`IMPLEMENTATION_PLAN.md` §Phase 4.5's resequencing note). Patch releases carry
fixes only; a yt-dlp baseline bump is at least a minor release, because it changes behaviour on
every site (`OPS-002`, release gate item 10a).

**`docs/RELEASE.md`**, created now per `DOC-002`: the gate (`TESTING.md` §8, by reference not
copy), the version bump, the tag, `T-324`'s workflow, the draft-then-publish step, the SmartScreen
note if `T-317` chose unsigned, and **rollback** — for the *project*: unpublish the release and
re-point *latest*; for the *user*: reinstall the previous installer, which the release page keeps;
for the *data*: **not promised** — `DAT-001`'s migrations are forward-only, so a downgrade across a
schema change is refused by the application rather than silently corrupting, and the document says
so instead of implying a rollback that does not exist.

**`SECURITY.md` §Supported versions** filled at the first tag: the latest minor receives fixes,
older ones do not. **`README.md`** gains an *Install* section pointing at releases and loses *"there
are no installers or packages yet"* — and is checked for any wording that claims yt-dlp parity,
which `REQ-030`'s resequencing forbids until Phase 4.5 lands.

#### Acceptance criteria

- `docs/RELEASE.md` exists and a reader with no context can cut a release from it alone
- The version scheme is a `REL-` decision or a section of `docs/RELEASE.md`, named by the
  maintainer's ruling on the scheme and on `0.1.0`
- `test_skeleton`'s `--version` contract still holds, and a test asserts the tag-to-version rule
  (a `vX.Y.Z` tag on a commit whose `__version__` is not `X.Y.Z` is a gate failure in `T-324`)
- `CHANGELOG.md` is created **in the release commit**, not before — `DOC-002`'s trigger is the
  first tagged release, and an empty changelog is the speculative document that decision forbids
- The README makes no parity claim; grep evidence recorded

#### Out of scope

- Application self-update. `REL-001` and `OPS-002`'s amendment leave it open, and it reopens
  `OPS-002`; it is not a `0.1.0` deliverable

---

### T-106 — Decide the Linux packaging format before Phase 5

**Status:** **In Review** — the maintainer ruled on 2026-09-11 and the decision is recorded as
[`REL-004`](DECISIONS.md#rel-004--the-linux-artifact-ships-as-an-appimage). Every acceptance
criterion below is met by that entry; nothing else remains in this task. *(Filed 2026-08-01 from
the Phase 5 roadmap review, when `IMPLEMENTATION_PLAN.md` required the decision before the first
build and it did not exist.)*
**Owner:** Architect / maintainer decision
**Priority:** Medium — nothing is blocked until Phase 5, and the answer shapes work well before then
**Phase:** Phase 5 prerequisite
**Depends on:** nothing
**Relevant context:** `REL-001` (ship frozen artifacts, no Python on the user's machine),
`IMPLEMENTATION_PLAN.md` §Phase 5, `LIC-001`, `NFR-009` (Qt stays dynamically linked), `OPS-001`
**Affected surfaces:** `docs/project/DECISIONS.md`, and later `packaging/`
**Risk:** Medium — taken late, it constrains a build that has already been written

#### Scope

§Phase 5's trigger reads: *"A `REL-` decision recording the Linux packaging format must be accepted
before the first build."* The only `REL-` entry is `REL-001`, which decides that artifacts are
frozen and self-contained and says nothing about **format**. The deliverable list says only
"Linux: packaging per the `REL-` decision" — pointing at an entry that does not exist.

**Why it is worth taking early rather than at Phase 5.** The candidates differ in ways that reach
back into the build: AppImage wants everything in one tree and is closest to what PyInstaller
already produces; Flatpak has its own runtime and sandbox, which changes how the application finds
`ffmpeg` and where it may write (`NFR-004`, `REQ-024`); a `.deb`/`.rpm` pair means system packaging
per distribution and a dependency story rather than a bundle. `NFR-009` constrains all of them —
Qt must stay dynamically linked (`LIC-001`'s LGPL condition).

#### Acceptance criteria

- A `REL-` entry naming the format, with the rejected alternatives and **why**, in the house style
- States how the choice interacts with `REQ-024`'s ffmpeg detection and `NFR-004`'s directories,
  since that is where a sandboxed format differs most from a bundle
- States what it means for `NFR-009`, and how that is checked in the release gate
- Names its reopening condition

#### Proposal, 2026-09-11 — for the maintainer to accept, amend or reject

**Recommended: AppImage.** Three reasons, in order of weight:

1. **`OPS-001` makes ffmpeg a *system* dependency on Linux**, and a Flatpak cannot see the host's
   ffmpeg without a portal or an extension. Choosing Flatpak would either reverse `OPS-001` on
   Linux (bundle ffmpeg after all) or ship a sandbox in which the merge feature is dead on arrival.
   An AppImage runs as an ordinary process and `find_ffmpeg`'s `PATH` search works unchanged.
2. **It is what `packaging/tracks-and-trails.spec` already produces.** PyInstaller one-dir *is* an
   AppDir minus a `.desktop`, an icon and `AppRun`; `T-020`/`T-033` have been building and probing
   that tree in CI since Phase 0. Flatpak means a manifest, a runtime and a second build system.
3. **`NFR-004`'s directories are unaffected**: `platformdirs` resolves the same `XDG_*` paths from
   an AppImage as from source, which `T-298`'s frozen-isolation gate already pins.

**What it costs, stated.** An AppImage carries no dependency story — Qt's own `.so` files ship
inside it (`NFR-009`, still dynamically linked *within* the bundle), so it is large (the smoke
artifact is ~223 MiB before ffmpeg) and it must be built against the **oldest glibc it claims to
support** (`OPS-012`'s recorded surrender: a Fedora-built binary may not run on an older distro).
That is `T-321`'s problem and is named there, not deferred.

**Reopening condition:** if ffmpeg is ever bundled on Linux, or a distribution store becomes a
requirement, revisit Flatpak. `.deb`/`.rpm` stay where `REL-001` left them — a later secondary, never
the primary.

**Acceptance is unchanged**: this becomes a `REL-` entry in the house style only when the maintainer
accepts it. Until then it is a proposal in a task, which is the narrowest honest record.

#### Out of scope

- Building anything. This is the decision; Phase 5 owns the packaging work (`T-321`)
- Windows, which `OPS-001` already settles

---

## Ready

### T-322 — The Windows installer

**Status:** **In Progress** — the script is written 2026-09-12; it cannot be built or verified
without Inno Setup on `STARBASE`.
**Owner:** Implementer
**Priority:** High
**Phase:** Phase 5
**Depends on:** `T-319` (what it installs), `T-320` (the version), `T-317` (whether it is signed)

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
- **Uninstall removes the installed tree and shortcuts and leaves user data, settings and the job
  database in place**, and says so on the uninstaller's final page — `DAT-001`. `T-039` asserts
  the two halves separately: leftovers under the install root are a failure; leftovers under the
  user directories are the intended behaviour.
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
  application under the real platform plugin, and an uninstall leaves nothing under the install
  root and everything under the user directories
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

### T-331 — The Windows mutation driver's positive control is not one

**Status:** **In Progress** — the driver is corrected and validated on Linux 2026-09-11; the
`STARBASE` run its last criterion asks for needs the machine. Filed the same day from the first
execution of `tools/windows/mutations/` there, which `T-040` had asked for since it was filed.

#### 2026-09-11 — corrected, and what the Linux run establishes

**It names the tree, and refuses one it cannot.** The header prints `HEAD` and whether the working
tree is dirty, and a dirty tree **stops the run** rather than warning — a warning is exactly what
scrolled past on 2026-09-11. `--allow-dirty` is the deliberate override.

**A broken baseline no longer manufactures kills.** Each selection's baseline is tracked, and
every later case in a selection whose baseline failed reports `NO RESULT (baseline broken)`. The
second run that evening reported `KILLED` for all six cases including the expected survivor,
purely because the suite was failing whatever the plugin did.

**The summary is pytest's result line**, found by pattern rather than taken as the last line of
output, and its absence is reported as `NO SUMMARY LINE` instead of a row of progress dots.

**The table and every full output are written to `reports/windows-mutations.txt`.** `T329-R2` asks
for a recorded result and this driver left only a console window.

**The control is a control now.** `mut_control_title` changes the window title, and
`test_windows_desktop.py` asks **Windows** for it through `GetWindowTextW` rather than asking Qt —
so no arrangement of widgets can pass it. `mut_control_chain` is reclassified as a mutation and
runs against the suite that detects it; its docstring no longer claims that its survival voids
every other verdict.

**Validated on Linux, where three of the four new behaviours are observable:**

| Case | Verdict |
|---|---|
| the six desktop cases | `NO RESULT (exit 5)` — deselected here, and *reported* as no result rather than passed over |
| baseline: the chain suite | **OK**, 205 passed |
| dialog: the declared chain is emptied | **KILLED**, 4 failed / 201 passed |
| baseline: the rendered focus sweep | **OK** |
| header: draws no focus ring of its own | **KILLED** |

The chain row is the finding demonstrated: the mutation the old driver called a surviving control
is killed outright by the suite that detects it.

**What remains is the `STARBASE` run**, which is the one thing about a driver's own correctness
that cannot be argued from Linux.
**Owner:** Implementer
**Priority:** Medium — it does not break the product, and it means a driver that claims to know
when its own verdicts are worthless does not
**Phase:** Phase 5 (test infrastructure)
**Depends on:** nothing
**Relevant context:** `tools/windows/mutations/mut_control_chain.py` and `run_mutations.py`;
`T-026`, `T-040`, `T-060`/`T060-R2`; `tests/ui/test_windows_desktop.py:483–490`
**Affected surfaces:** `tools/windows/mutations/`
**Risk:** Low

#### What happened

The first real run on `STARBASE`, 2026-09-11:

```
OK                     baseline, unmutated
SURVIVED (unexpected)  CONTROL: focus_chain returns nothing
KILLED                 dialog: two declared widgets reordered
KILLED                 dialog: undeclared focusable control
KILLED                 progress view: undeclared focusable control
SURVIVED (expected)    progress view: delivered order reversed
```

`mut_control_chain` says of itself: *"It MUST be reported as killed. If it survives, the plugin
mechanism is not taking effect and every other verdict in this run is meaningless."*

#### Both halves of that are wrong, and the run proves it

**The mechanism took effect.** Three mutations were killed in the same run, which is only possible
if the plugins applied. So the other verdicts stand rather than being void.

**The mutation is caught — by tests this driver does not select.** Applying
`mut_control_chain` on Linux against `tests/ui/test_accessibility.py` and
`tests/ui/test_add_dialog.py` fails **4 tests**. The driver runs `-m windows_desktop`, and none
of the four carries that marker.

**Why the desktop suite cannot see it.** `_set_tab_order` pairs `focus_chain()` and calls
`setTabOrder`; an empty chain simply makes no calls, leaving **Qt's construction order**.
`test_windows_desktop.py:490` writes its expected order out by hand rather than deriving it —
*"that is the whole point"* — so it passes whenever the delivered order matches, and on this
dialog construction order already does. The tests are right about the delivered order. They are
not evidence that the *declaration* is load-bearing, and the control assumed they were.

#### What the same evening then showed, and it voids the table above

**The machine's interactive checkout was six weeks stale**, at a 2026-07-29 commit, with
uncommitted edits to `core/logging.py`. Its `origin` is `C:/dev/tt.bundle` — a hand-carried bundle
file — so every `git pull` answered *"Already up to date"* while following nothing. **The run
above tested July's code**, as did a second run whose baseline broke outright.

**So the `SURVIVED (unexpected)` result is not evidence**, and this task does not rest on it: the
reasoning below was reproduced on Linux from the committed tree, where the mutation fails 4 tests
in `test_accessibility.py` and `test_add_dialog.py` — none carrying the `windows_desktop` marker
the driver selects. The Windows numbers are still to be taken.

#### Acceptance criteria

- **The driver refuses, or at least records, a tree it cannot identify.** It already refuses the
  wrong interpreter and the wrong directory, and it printed six cases from a six-week-old checkout
  without a word. `git log --oneline -1` and a dirty-tree check in its header would have cost
  thirty seconds and saved three runs
- **It distinguishes a killed mutation from a broken run.** The second run reported `KILLED` for
  every case including the expected survivor, because it treats any non-zero exit as a kill and
  its summary line had been swallowed — the same class of mistake its own comments record being
  fixed for once already
- The positive control is one the selected suite **cannot** pass — or the driver selects the
  tests that detect the existing one, stated either way rather than left to coincide
- The claim in `mut_control_chain`'s docstring and `run_mutations.py`'s comment is corrected: a
  surviving control does not by itself void the other verdicts, and this run is why
- **Run on `STARBASE` and the table recorded**, since a driver's own correctness is exactly the
  thing that cannot be argued from Linux
- `run_mutations.py` **writes its table to a file** as well as printing it. `T329-R2` asks for a
  recorded result and the driver currently leaves only console output, which is how this run
  nearly went unrecorded

#### Out of scope

- The dialog's construction order, which is correct
- `T-060`'s expected survivor, which is recorded and understood

---


### T-319 — The Windows release build: windowed, versioned, with ffmpeg inside

**Status:** **In Progress** — the ffmpeg search order landed 2026-09-11; the build itself needs
a Windows machine. Filed the same day with the Phase 5 plan.

#### 2026-09-11 — scope item 2's search order, which is the half that runs on any platform

`find_ffmpeg` gains a **bundled** candidate between the explicit override and `PATH`, exactly as
scope item 2 describes, plus `bundled_ffmpeg()` to locate it beside the executable where the spec
will put it.

**The ordering is the point and it is mutation-tested.** A user with their own newer ffmpeg
installed must not silently displace the build this artifact was tested against — a different
build is a different set of encoders, and `OPS-001` bundles one so the feature works without the
user arranging anything. Moving the branch after `PATH` fails
`test_the_bundled_copy_is_preferred_over_one_on_path` and nothing else. The explicit override
still outranks both, because that is the user saying which one they mean.

**One judgement recorded rather than left implicit:** a bundled binary that exists but is not
executable **falls through to `PATH`** instead of being reported unusable, which is the opposite of
the override's rule. The override is something the user asked for, so failing it silently would
hide their setting; this is something the artifact provided, and a broken one should not also cost
the user their own copy.

`bundled_ffmpeg` had to be justified into `test_environment.REVIEWED_PUBLIC_API` — `T035-R3`'s
allowlist, working as designed. It is a locate-side name: it imports nothing, executes nothing and
answers neither *what version* nor *does it work*.

#### 2026-09-12 — scope items 1 and 3, and the reason they could be done here

**One spec, two modes**, selected by `TT_RELEASE_BUILD=1` rather than by a second spec file —
`T-233`/`T-237` were both about spec comments drifting from the spec beside them. The release mode
sets `console=False`, the icon, and a Windows version resource generated at build time from
`__init__.py` rather than checked in, because `[tool.hatch.version]` already reads that module and
a checked-in resource is a third place for the version to disagree.

**`console=False` costs the probes their `stdout`, and that is the interesting half.** All four
probes now report through `_freeze_probe.say`, which prints *and* appends to `TT_PROBE_REPORT`
when the caller sets one — the same shape as `TT_PROBE_LOG` beside it rather than a fifth
mechanism. **45 report lines** were converted; a test asserts **no bare `print` survives** in that
module, because a probe that kept one would report nothing in a windowed build while its siblings
reported normally, and the file would not even be empty.

**Verified by building it**, which is why these were worth doing on Linux: `TT_RELEASE_BUILD=1`
builds, and `--ytdlp-probe` against that artifact with an isolated `HOME` wrote its eight lines to
the report file, ending `OK: the frozen artifact carries a usable yt-dlp with its extractors`. Six
unit cases cover the helper, including that an unwritable report does not fail the probe — the
report is evidence, not the probe's purpose.

#### 2026-09-12 (later) — the ffmpeg binary, its licence, and the open question answered

**The open question was between a build-time download with a recorded URL and checksum and a copy
placed on `STARBASE` by hand — `OPS-012` §3 arguing for the second, the release workflow for the
first. The answer is one mechanism with two callers**, which satisfies both rather than picking:
`packaging/fetch_ffmpeg.py` is scripted, pinned and digest-verified, so it is reproducible and
reviewable; and **it is not wired into the build**, so a self-hosted runner never provisions
itself as a side effect of a build. The spec reads what is on disk and **raises** if it is absent,
naming the script. *(Recorded as a judgement rather than a ruling; the maintainer said to do this
task, not that this is the shape.)*

**Which ffmpeg, and every part of the name is load-bearing:**

    BtbN/FFmpeg-Builds  autobuild-2026-09-12-13-12
    ffmpeg-n9.0.1-29-gad500d59cb-win64-lgpl-shared-9.0.zip
    sha256 609245cc0a906c1423f2cdb96e27925302d375fe8024dcbc4b3f6aaf757a43ff

`lgpl` because `LIC-001` forbids bundling a GPL ffmpeg with an MIT application — `gyan.dev`'s
builds are GPL. `shared` because the same requirement says the libraries must stay *replaceable*,
which a static build is not. An `autobuild-*` tag rather than `latest`, because `latest` is
rolling and the same URL would serve different bytes tomorrow.

**Verified rather than assumed.** The configure line embedded in `ffmpeg.exe` carries
`--enable-version3` and **no `--enable-gpl`** and **no `--enable-nonfree`**; `avutil-61.dll`
self-reports `libavutil license: LGPL version 3 or later`. So it is LGPL **3**, and the
`Qt-GPLv3.txt` already shipped covers its incorporated GPL terms.

**`ffprobe.exe` is bundled and `ffplay.exe` is not.** Not a size decision: yt-dlp's
`FFmpegExtractAudioPP.run` calls `get_audio_codec`, which runs **ffprobe on the downloaded file**,
so `REQ-010`'s audio extraction needs it. Nothing here launches a media player. Nine files,
**155 MB**, gitignored — that half of the question was never in doubt.

**The licence cannot drift from the build.** `fetch_ffmpeg.py` compares the committed
`ffmpeg-LGPL.txt` against the archive's own `LICENSE.txt` on every run and **refuses** if they
differ, because the gate downstream only asserts the file is present and non-empty — it cannot
know which ffmpeg it belongs to. Tested: a substituted licence text fails with the reason.

**Refusals checked before the happy path was trusted:**

| Handed | Result |
|---|---|
| a digest that does not match what the URL serves | **exit 1**, and nothing written before verification |
| a licence text that is not the archive's | **exit 1**, naming the fix |
| a corrupted cached archive | re-downloads and repairs, which is the right answer |
| a second run | uses the verified cache, no download |

**`NOTICE.txt` corrected while here.** It said `ffmpeg-LGPL.txt` is *"absent from Linux artifacts
by design"*. It is not: `licenses/` is bundled as a unit, so the text ships on Linux too, where
ffmpeg is a system dependency and covers nothing in the artifact. The notice now says that rather
than the opposite.

**Verified on Linux**: `TT_RELEASE_BUILD=1` builds, the ffmpeg branch is correctly skipped
(`OPS-001`), and `ffmpeg-LGPL.txt` is in the artifact's `licenses/`. **19 cross-reference tests,
11 mutations, 11 caught** — a GPL build, a static build, a rolling pin, a dropped ffprobe, ffmpeg
placed under `_internal/` where `bundled_ffmpeg` would not find it, a release permitted to build
without it, and the smoke build bundling 155 MB it does not need.

#### 2026-09-12 (later still) — built on `STARBASE`, and it found two defects

**Every criterion beginning *"on the built artifact"* is now met, measured on a real Windows
release build** at `ace8e31` plus the three fixes below. The route is
`tools/windows/run-on-starbase.sh`, so each command ran in the **logged-on session** rather than
SSH's session 0.

| Criterion | Measured |
|---|---|
| no console window | PE subsystem field = **2 (GUI)**, read from the executable's own header rather than inferred from the spec |
| `find_ffmpeg` reports `source="bundled"` | `bundled with this build (OPS-001)`, resolving `_internal\ffmpeg.exe` |
| `--version` on the built exe | `0.1.0.dev0`, rc 0 |
| the Windows version resource | `FileVersion 0.1.0.dev0`, `ProductVersion 0.1.0.dev0`, `CompanyName Sean Kottman`, `FileDescription Tracks & Trails` |
| `T-323`'s four gates | **all four pass**, over an artifact now carrying 155 MB of third-party binary |
| every frozen probe | **5 of 5 pass** — spawn, yt-dlp, database, in-app update, and the new ffmpeg probe |

**Three defects, and none of them was visible from Linux.**

**1. The licence check compared bytes, and git converts them.** `core.autocrlf=true` is the
Windows default and `STARBASE` has it set, so the committed `ffmpeg-LGPL.txt` is checked out with
CRLF while the archive's copy has LF: **7,816 bytes against 7,651**, exactly one extra byte per
line. `fetch_ffmpeg.py` failed on its first Windows run and would have failed on every release
build. It now compares content with line endings normalised, and still refuses a licence whose
content differs.

**2. `bundled_ffmpeg()` looked in the wrong directory, on the strength of a comment.** It read
`Path(sys.executable).parent`, because the spec said `binaries` with a destination of `"."` puts
files *beside the executable*. **PyInstaller 6 puts a one-dir bundle under `_internal/`**, so
`"."` is the root of *that*: the build put ffmpeg at `_internal\ffmpeg.exe`, one level below where
the application was looking. It now asks `sys._MEIPASS` — the runtime's own answer — and keeps the
executable's directory as a second candidate.

**The test agreed with the bug.** `test_a_frozen_build_finds_the_ffmpeg_beside_its_executable`
planted the file beside a fake `sys.executable` and passed, and a cross-reference test asserted
the destination *"is where `bundled_ffmpeg` looks"*. Both were written from the same wrong
premise as the code, so neither could contradict it. They now build the real `_internal/` layout,
and the cross-reference test asserts only what spec text can honestly support — that the binaries
are declared and passed — leaving *where they land* to the probe that can see it.

**3. A probe that compared a sentence to a keyword.** The first `--ffmpeg-probe` tested
`report.source == "bundled"` and failed a build that was entirely correct: `FfmpegReport.source`
is prose for a human, `"bundled with this build (OPS-001)"`. It now compares the resolved **path**
against the bundled one — which is what the criterion actually asks — and checks the wording only
for the word, so the UI cannot say one thing while the loader does another.

**`--ffmpeg-probe` is new, and it exists because nothing else could answer this.** The unit tests
plant files beside a fake executable; only a probe inside the artifact can say which ffmpeg a
frozen build resolves. It also checks `ffprobe.exe` is beside it, since yt-dlp runs ffprobe on
the downloaded file for `REQ-010`'s audio extraction.

**One claim in the entry above needs narrowing.** It says *"`console=False` costs the probes their
`stdout`"*. Measured: a parent that **captures** the handle — `subprocess` with pipes, or a shell
redirect — still receives it, and all five probes were read that way. What `console=False` removes
is a console *window* for a user who double-clicks. `TT_PROBE_REPORT` is therefore robustness
rather than necessity in CI, which is still worth having: it is the only route that survives a
caller which does not redirect.

*(This paragraph previously read **"still not done, and it needs a Windows machine"**, listing
the three built-artifact criteria and noting that `STARBASE_HOST` was unset here. The maintainer
authorised the key on 2026-09-12 and all three are measured above. Kept as a correction rather
than deleted: the blocker was one environment variable, exactly as it said, and saying so is what
made it worth asking for.)*

*(Filed 2026-09-11 with the Phase 5 plan.)*
**Owner:** Implementer
**Priority:** High — it is the artifact
**Phase:** Phase 5
**Depends on:** `T-320` (the version it stamps); `T-317` only for the signing step, which may be a
no-op
**Relevant context:** `REL-001`; `OPS-001` (ffmpeg bundled on Windows, **LGPL build only**);
`LIC-001`; `NFR-009`; `packaging/tracks-and-trails.spec` and its `console=True` note, which says
*"Phase 5 makes this windowed; the probe needs stdout in CI"*; `app.py`'s four `--*-probe` flags;
`downloader/environment.find_ffmpeg`; `T-020`, `T-033`, `REL-002`
**Affected surfaces:** `packaging/tracks-and-trails.spec`, `_freeze_probe.py`, `app.py`,
`downloader/environment.py`, `.github/workflows/ci.yml`'s `frozen` job, `docs/DEVELOPMENT.md`
**Risk:** Medium — the windowed switch is the one place the smoke build and the release build
genuinely differ, and the probes CI depends on write to a `stdout` that a windowed process does
not have

#### Scope

**One spec, two modes.** The Phase 0 spec stays the CI smoke build; the release build is the same
`Analysis` with three differences, selected by an environment variable rather than a second file
(two specs is two things to keep true — `T-233`/`T-237` were both about spec comments drifting):

1. **`console=False`.** A user must not get a console window behind the application. The probes
   then have no `stdout`, so `_freeze_probe` **writes its report to a file as well as printing**,
   and CI reads the file. `dist/frozen-probe.log` already exists for one probe; extend the pattern
   to all four rather than adding a fifth mechanism.
2. **ffmpeg bundled.** An **LGPL** build — `OPS-001` and `LIC-001` are explicit, and the two common
   Windows build sources differ on exactly this: `gyan.dev`'s builds are GPL and may **not** be
   bundled; `BtbN`'s `*-lgpl-shared` builds may. The choice of source is recorded in the task on
   completion with its licence text. `find_ffmpeg` gains a **bundled** candidate, searched *after*
   the explicit override and *before* `PATH`, so a user's own newer ffmpeg on `PATH` does not
   silently win over the one that was tested — and the Settings screen reports the source, which
   it already does for the override.
3. **Version metadata.** A Windows version resource (file and product version from
   `__version__`, product name, copyright), and `icon.ico` on the executable.

**What does not change**: `freeze_support()` first (`REL-001`'s highest-risk item, `T-020`'s
smoke keeps proving it), one-dir, Qt dynamically linked inside the bundle, `collect_data_files`
for yt-dlp (`REL-002`).

#### Acceptance criteria

- The `frozen windows` job builds in **both** modes and runs all four probes against the
  **windowed** build, reading their file reports; a mutation that drops the file-write turns the
  job red rather than silently green
- Launching the windowed build opens no console window — asserted on the runner by
  `T-026`'s harness (no console `HWND` belonging to the process)
- `find_ffmpeg` on the built artifact reports `source="bundled"`, and the same build with the
  bundled binary deleted degrades exactly as `REQ-024` describes rather than crashing
- The ffmpeg licence text and a statement of *which* build it is (source, version, LGPL) ship
  inside the artifact — `T-323` gates their presence; this task puts them there
- `--version` on the built artifact prints `__version__` (`test_skeleton`'s existing contract,
  now on the frozen binary)
- `docs/DEVELOPMENT.md`'s *Building the frozen artifact* section documents both modes

#### Out of scope

- The installer (`T-322`). This produces `dist/tracks-and-trails/`; that wraps it
- The Linux artifact (`T-321`)
- Size work. `REL-001` accepted the size; record the number, do not chase it

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

---

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

---

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

---


## Proposed — Phase 5

*Created 2026-09-10, when Phase 4.5 was resequenced to follow the first release and this
phase became the next one to run. `T-039` also carries `**Phase:** Phase 5` and stays under
`## Blocked`, because that section is about status rather than phase.*

### T-212 — The recorded checklist run: the built window against the agreed flow

Historical evidence relocated 2026-09-08:
[Additional historical evidence](COMPLETED_TASKS.md#t212-validation).

**Carries one row by maintainer direction, 2026-08-13:** the **deferred panel mount**. `T-221` was
closed on a real-display observation — the maintainer did not see the one-turn transient — and the
maintainer directed that it be re-checked by hand in this pass rather than left as an open task.
One observation on one machine is evidence about that machine; this run is where a second is taken
deliberately, in front of the whole built window, and **recorded** in `docs/project/evidence/`. Both panel
kinds, since `T-209`'s audit found both spend that turn at 190×26.

> **Superseded — ruled by the maintainer on 2026-09-10:** *"the direction is overridden by the work
> done for T-312."*
>
> The mechanism it aimed at no longer exists. A panel is a **page of the add dialog** now rather
> than a widget mounted into a list row, so there is no `setIndexWidget` turn at 190×26 for either
> kind and the transient the direction asked to have confirmed cannot occur. **This run no longer
> carries a directed row**, and `T-221` needs no second observation.
>
> Checklist row `5.6` stays, as an ordinary row rather than a directed one: a page swap can still
> land badly, and looking costs nothing. It is no longer evidence anybody is owed.

**Status:** Proposed — filed 2026-08-09, owning the exit criterion the maintainer added the same
day; **the checklist half is written**, 2026-08-16, at `docs/PHASE_4_CHECKLIST.md` — before the
run, which is this task's first acceptance criterion. **Forty-eight** rows across seven sections
— counted; forty-seven when written, after the entry first said forty-one from an estimate, and
`6.1a` added 2026-08-28 with `T-292` — derived from
`docs/UX_SPEC.md` §2/§3/§8/§11/§12 and the accepted criteria of every surface Phase 4
added or reshaped, in `docs/CRITERION_8_CHECKLIST.md`'s shape and under its guards: rows say what
a user should see, task ids are back-references, and a failed row becomes a task entry rather than
an inline repair. The maintainer-directed panel-mount row is **5.6**, covering both panel kinds.
**What remains is the run itself** — a real display and a person looking at it — recorded in
`docs/project/evidence/` at a named head. A **run sheet** is published for the sitting, generated *from* this
file so the two cannot drift: it marks each row pass / fail / not run, keeps the marks per head,
and emits the `docs/project/evidence/` markdown to paste back. The criterion had no owner in the map above, which is exactly the
failure that map exists to surface.
**Owner:** Implementer
**Priority:** High — it is a release gate. *(Was: "a phase exit criterion, and the phase cannot
exit without the evidence". **Amended 2026-09-10**: the maintainer ran the list informally, ruled
that sufficient for Phase 4 closure, and moved the recorded run to Phase 5 — so it now gates the
first release rather than the phase.)*
**Phase:** **Phase 5** *(moved 2026-09-10 from Phase 4, by maintainer ruling: "I did a mostly
full informal run … please defer that task to the end of phase 4.5 or as part of phase 5"; Phase 5
rather than 4.5 because 4.5 was resequenced the same day to follow the release, and a checklist
run that happens **after** shipping is not a release gate at all)* — **last.** The plan's own criterion text says why: a run taken before the
phase's surfaces land checks an application that is about to change.
**Depends on:** `T-146`, `T-195`–`T-202`, and the add-dialog chain — `T-203`, `T-204`'s
corrections (`T-207`, `T-209`, `T-210`, `T-211`) and whatever `T-208`'s investigation changes.
**Relevant context:** `IMPLEMENTATION_PLAN.md` §Phase 4 exit criteria; Phase 2's criterion 8 —
`docs/project/evidence/2026-08-05-criterion-8-checklist-run.md` and its two successor runs; `P2EXIT-R10`,
`P2EXIT-R12`; `docs/UX_SPEC.md`
**Affected surfaces:** `docs/project/evidence/` (the recorded run) and new task entries for what it finds
**Risk:** Medium — not that the run is hard, but that it is treated as a formality. Phase 2's
first run found **eleven defects against 2153 passing tests, none reported by any gate**, and
needed two further runs to reach 40 of 40

#### Scope

The criterion reads: *"The built window matches the flow that was agreed — evidenced by a recorded
checklist run against the running application, in `docs/project/evidence/`, the way Phase 2's criterion 8 was
evidenced."* This task writes the checklist, runs it against the running application, records the
run, and files what it finds. The checklist derives from `docs/UX_SPEC.md` — the agreed flow — plus
the accepted criteria of the surfaces this phase adds: the settings screen and its panes, the
reshaped add-dialog row, and the phase's queue and error-presentation changes.

**A walked-through session is not evidence.** `P2EXIT-R12` was a checklist claiming a pass over its
own recorded failures, and `P2EXIT-R10` was the same row claimed met and reset twice. The recorded
run is the deliverable; the pass is only what it hopefully shows.

#### Moved to Phase 5 on 2026-09-10, and what that changes

**Ruled by the maintainer** after an informal pass over the built window: *"I did a mostly full
informal run … and I think things are looking good for it. Please defer that task to the end of
phase 4.5 or as part of phase 5."*

**Phase 5, not the end of 4.5**, because 4.5 was resequenced the same day to follow the first
release — a checklist run taken after shipping gates nothing. In Phase 5 it sits beside the Windows
manual verification session, which needs a real desktop too, so the two sittings can be arranged
together.

**What the informal run does not do, said plainly.** This task's own reasoning is that *a
walked-through session is not evidence* — Phase 2's equivalent found **eleven defects against 2153
passing tests** and needed two further runs to reach 40 of 40. The informal pass is what closes
Phase 4; it is not what closes this task. The acceptance criteria below are unchanged, and the run
happens against the built artifact rather than a developer checkout, which is strictly better
evidence than a Phase 4 run would have been.

#### Acceptance criteria

- **The checklist is written before the run**, derived from `docs/UX_SPEC.md` and the phase's
  accepted task criteria, and covers every surface Phase 4 added or reshaped
- **The run is recorded in `docs/project/evidence/`**, item by item, pass or fail, at a named commit — the
  format Phase 2's criterion-8 runs established
- **A failed item becomes its own task entry**, filed rather than repaired inline and re-claimed
  within the same run
- **A re-run after corrections repeats the whole checklist**, not only the failed rows — Phase 2
  needed three runs, and each was complete
- **The evidence names the commit and states that every depended-on task above was integrated at
  it** — a run over a tree still missing one of them is the "about to change" application the plan
  warns against

#### Out of scope

- **Fixing what the run finds.** Each finding is its own filed task with its own review
- **The Windows half.** `OPS-003`: there is no Windows machine, so the run is Linux; the
  pre-release Windows session inherits the same checklist, and the gap is named the way the plan's
  screen-reader split names its Narrator gap





### T-326 — The release-candidate suite: everything the gate asks a machine for, on both platforms

**Status:** Proposed — filed 2026-09-11 with the Phase 5 plan
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
- Item 8: the frozen smoke, on the **release** builds — `T-324` runs it; the record is the run id
- Item 10: the in-app yt-dlp update from the release artifact — `T-324` runs the probe; the record
  is the run id
- Item 10a: only if the baseline is bumped in this release; for `0.1.0` it is not, and that is
  recorded

#### Acceptance criteria

- One evidence file for the release candidate listing each item, the command or run id that
  satisfied it, and the platform — no item marked passed without its artifact
- The network-suite output is retained for both platforms
- `docs/RELEASE.md` gains the `0.2` migration-fixture obligation

#### Out of scope

- Items 6, 7, 11–15: `T-212`, `T-318`, `T-323`, `T-325`, `T-327` respectively

---

### T-327 — The Windows manual verification session

**Status:** Proposed — filed 2026-09-11 with the Phase 5 plan. **Human, and blocking**: `TESTING.md`
§8 item 15 says *"CI green is not a substitute"*
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
that session, for Windows); `REQUIREMENTS.md` §3; `T-212` (the same sitting, other list)
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

**`T-212`'s recorded checklist run is the same sitting**, deliberately: one afternoon with the
built artifact rather than two.

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

### T-328 — The first release

**Status:** Proposed — filed 2026-09-11 with the Phase 5 plan. **This is the phase exit.**
**Owner:** Reviewer runs the release review; Maintainer tags and publishes
**Priority:** High
**Phase:** Phase 5
**Depends on:** every task above, `T-212`, `T-039`
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
   `T-318`'s clean-machine files, `T-327`'s and `T-212`'s sessions. Recorded in a review record
   indexed by `REVIEWS.md`. Its verdict is the phase's.
3. **Publish**: the draft becomes public by the maintainer's hand. The README's install section
   goes live in the same push.
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

---

## Blocked

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

### T-039 — Verify Windows installer behavior on the runner

**Status:** **Blocked — until Phase 5 produces an installer.** Proposed work with nothing to do
until then; the installer it would verify does not exist yet
**Owner:** Implementer
**Priority:** Medium now, High once Phase 5 starts — it must land before the first public release
**Phase:** Phase 5
**Depends on:** the Phase 5 installer, `T-026` (establishes the real-plugin Windows job)
**Relevant context:** `OPS-004`, `REL-001`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Risk:** Medium — same failure mode as `T-026`: a shallow check would retire a
release-blocking manual item without replacing it

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

#### Acceptance criteria

- Each of the four is a **gate**, stated as a mutation that turns the suite red: a missing
  shortcut, a file placed outside the install root, a non-zero silent-install exit code, and a
  leftover file after uninstall each fail the job. Screenshots, if any, stay retained evidence
  and fail nothing on their own (`T031-R2`, `P0-R7`)
- Uninstall leaving user data behind is asserted as **intended** behavior, not tolerated as a
  leftover — the test distinguishes the two
- `docs/project/TESTING.md` §9's manual list drops installer placement and removal, and
  `REQUIREMENTS.md` §3 narrows to match — **only once this job is landed and green**
- The added CI time is recorded against `T-006`'s budget

#### Out of scope

- Whether the installer *feels* normal — `OPS-004`'s subjective residue, still human, still
  blocks first release
- Upgrade-over-existing-install and downgrade paths — real, but a separate task once the
  versioning story exists
- Any non-Windows packaging

---
