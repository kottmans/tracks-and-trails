# STATUS.md — Tracks & Trails

**Purpose:** Concise snapshot of where the project stands right now.
**Authority:** Canonical for current project state.
**Owner:** Planner / Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-28
**Last verified against repository:** 2026-07-28
**Update when:** A meaningful work session ends, a phase changes, a blocker appears or clears, or the next task changes.
**Does not contain:** Task detail (`TASKS.md`), review history (`REVIEWS.md`), decision rationale (`DECISIONS.md`).

---

**Current phase:** **Phase 1 — Vertical slice.** Phase 0 **formally exited 2026-07-26**.
**Overall state:** Phase 0's five exit criteria were each verified rather than asserted, and the
evidence is recorded in `IMPLEMENTATION_PLAN.md` §Phase 0 — including a fresh mutation run
proving the layering test still fails on a deliberate `PySide6` import in `core/`.

`T-010`, `T-011` and `T-026` are complete. `ARC-003` settled the IPC versioning question.

**Two things the phase exits with, named rather than hidden:**

- The **subjective** half of Windows verification (`OPS-004`) — whether rendering *looks* right,
  whether Narrator *sounds* coherent, whether the installer *feels* normal. Unverified, needs a
  person, and blocks **first release**, not this phase. `T-039` (installer) has no automated gate
  yet either. **`T-040` is no longer among them**: its tests ran on a real Windows desktop on
  2026-07-28 and both `T-026` mutation classes were killed there, so tab order is gated on
  Windows. *(This entry said "Ready" on 2026-07-27, "Blocked ... never run" on 2026-07-28, and
  was still saying the latter after the run happened — `COORD-R5`. Four documents disagreed about
  this one fact at once; they are reconciled as of `T066-R1`'s correction batch.)*
- **`T011-R8` is closed.** `T-041` was approved at `0268e13` and the finding is functionally
  resolved. The audit behind it found the hole was not one field but every field of every model
  in `core/models.py`.

## Completed

- Documentation system bootstrapped: `DOC-001`
- Requirements, architecture, phases, and Phase 0 tasks defined
- Foundational decisions accepted: `ARC-001`, `ARC-002`, `DAT-001`, `OPS-001`, `OPS-002`,
  `OPS-003`, `SEC-001`, `REL-001`, `LIC-001`
- **`T-004` complete** — licensed MIT; `LICENSE` written
- **`T-002` complete** — Python 3.14 baseline confirmed (PySide6 ships `abi3` wheels)
- **`T-001` complete** — `pyproject.toml`, 27-module skeleton per `ARCHITECTURE.md` §4,
  `tests/` tree, `docs/DEVELOPMENT.md`. All four checks green from a simulated clean checkout.
- **`T-003` + `T-022` complete and approved** — icon set derived from the maintainer's
  1024×1024 source; brand swatches fixed in `ARCHITECTURE.md` §8; resource invariant tests
  added. Codex requested changes, then approved the corrections on re-review; no open
  findings. Two standing caveats: no SVG exists (no vector source), and 16 px is legible only
  narrowly — `T-021` filed as an optional improvement that blocks nothing
- **First review completed** — the review process in `AGENTS.md` §3 has now been exercised
  end to end (implement → review → correct → focused re-review) and works
- **`T-006` + `T-023` complete** — CI runs on Linux and Windows for every push and pull
  request, squash-merged as `c8a72b8` and green on `main`. Reviewed twice; the final
  documentation correction was maintainer-accepted with the focused re-review waived.
- **`T-005` + `T-024` complete** — layering enforcement test, squash-merged as `d1f45e5`.
  The analyser is guarded against being weakened, verified by eight distinct weakenings. Two
  review rounds; the second re-review was waived by the maintainer.
- **`T-007` complete** — the application shell window, merged as `fa5a3c0`. Opens with the
  icon and title, File → Quit and Help → About, geometry across restarts, clean exit. Cold
  start 0.178 s median against `NFR-002`'s 3 s. **Merged without any independent review** at
  the maintainer's direction — not a waived re-review, no first pass; recorded in its task.
- **`T-020` + `T-025` complete** — frozen-build smoke test and the Phase 0 exit preparation,
  merged as `564aad0`. A frozen artifact spawns a child without relaunching itself on both
  platforms; the clean-checkout verification passes on Linux. The **negative** proof — that
  removing `freeze_support()` breaks it — has now been run on Windows too (`T-029`, run
  `30186080950`).
- **Phase 0 exit review complete, and its eight findings closed** — `T-027` … `T-032`,
  squash-merged as `7b7860d`. `P0-R2` … `P0-R5` were reviewer-verified; the corrections to
  `P0-R1`, `P0-R6`, `P0-R7` and `P0-R8` were **maintainer-accepted without a final
  re-review**, and each task records that.
- **Windows is no longer entirely unverified.** `T-006`'s runners confirmed, with downloadable
  artifact evidence: Python 3.14.6 (MSC v.1944, AMD64), PySide6/shiboken6/Qt 6.11.1, a
  `QWidget` visible offscreen, and the full 27-test suite passing. This discharges the Windows
  carries from `T-002` and `T-003`. The `OPS-003` interactive gaps (screen reader, native
  dialogs, keyboard, theming, installer) remain untouched. They no longer all need a person:
  `OPS-004` splits them into an objective half CI can assert (`T-026`) and a subjective
  residue — whether it *looks* right, whether Narrator *sounds* coherent, installer feel,
  shell foreground behavior, long-running stability — which is what still blocks first release.
- Verified 2026-07-25 that yt-dlp 2026.06.09 is pure Python (1046 `.py`, no compiled
  extensions), which is what makes the `OPS-002` pip-free updater viable
- **`T-045` complete — Approved with follow-ups**, 2026-07-26 after four rounds, with no
  production change at any point. `T-046` owns the filesystem-aware uniqueness guarantee.
- **`T-044` complete — Approved with follow-ups by maintainer direction**, 2026-07-26 after six
  rounds and three scope decisions. The gate now states only its tested runtime promise; three
  known blind spots are pinned and owned by `T-047`. No production code changed in any round.
- **The lesson from T-044 and T-045:** all six defects came from treating an enumerated set as
  exhaustive. The successful corrections were not longer enumerations: T-044 reads the
  interpreter's namespace and states its gaps, while T-045 dropped the completeness claim.
  `ai/TESTING.md` §13 records the general rule.

## In progress

**Session of 2026-07-28 — eleven tasks, split into review sections.** The commits are grouped so
each section is a contiguous range:

| Review | Tasks | Base | Head |
|---|---|---|---|
| 1 | `T-016` fourth correction, `T-017` | `6ad20f6` | `6ce195a` |
| 1a | `T-017` corrections, four batches | `9c92c32` | `f100108` |
| 2 | `T-057`, `T-058` | `6ce195a` | `4a06e92` |
| 3 | `T-056`, `T-054` | `4a06e92` | `9c92c32` |
| 4 | `T-059`, then `T-036` and `T-037` | `5b0ebca` | `894d794` |
| 5 | `T-052`, `T-040` | `894d794` | `1aba441` |
| 6 | `T036-R1` correction, `T037-R1/R2`, `T040-R1` attempt | `6ce26ec` | `306840b` |

**Every Phase 1 deliverable is approved.** `T-036` (at `306840b`) and `T-037` (at `894d794`)
closed the two exit criteria that had no owner, and `T-017` closed on 2026-07-28 with the last of
its findings resolved under `T-059`.

**Then CI ran, and the claim that only evidence remained did not survive it** (`COORD-R2`). The
first real Windows run of this work produced three tasks — `T-062`, `T-061` and a widened
`T-060` — and all three are written. **CI run `30388380440` then passed all five jobs at
`11e1203`**, `windows desktop` included; it is the first run of this project with none red.

*(This paragraph called `T-062` "In Review" for as long as it took to approve it. A narrative
sentence carrying a status is a second place for that status to live, which is the shape
`COORD-R2` and the mandatory-area count each landed on — the operative list below is the one
that is meant to hold it.)*

**What remains is evidence.** `T-061` and `T-063` are **Complete** at `11e1203` (`T-063` carrying
`T-064`), and `T-060`'s two findings were **Resolved** at `12dff92` with no further correction
requested.

**Then a Windows machine appeared that is not a CI runner.** `STARBASE`, on the maintainer's
network — Windows 10 22H2, reached over RDP in an interactive session, Python 3.14.6 and PySide6
6.11.1 matching the runners exactly. It supplied the evidence `T-040` had owed since it was filed:
28 desktop tests passing under the real `windows` plugin, and both `T-026` mutation classes
executed and killed. **`T-040` and `T-060` are now In Review rather than Blocked, and `T-026`'s
last acceptance criterion is met** — with no CI minutes spent.

**The `windows desktop` job runs on the maintainer's own machine as of 2026-07-28.** `STARBASE`
is a self-hosted runner, in a logged-on elevated session, and job `90432207805` is green end to
end — `28 passed` under the real `windows` plugin. Self-hosted minutes are not billed, so the one
job that cannot be replaced by reasoning survives the Actions quota being exhausted. It also gave
the `T-066` virtualenv change its first execution anywhere.

**It cost a repair to that machine first.** `actions/setup-python` is free on a hosted runner
because the runner is discarded; this one is a computer somebody uses, and it deadlocked the real
Python installer against `msiexec`, leaving the interpreter half-removed. The job installs nothing
now. `docs/WINDOWS_VERIFICATION.md` carries that and the two follow-on traps.

**`T-056` did not move, and now the reason is sharper.** Its defect does not reproduce on
`STARBASE`: the pre-correction helper passes 20/20, with a positive control proving the mutation
was really applied. A Windows machine was not enough; it wants `windows-latest`'s image.

**The same first run found five things CI structurally cannot see** (`T-066`…`T-070`), and all
five are implemented as of 2026-07-28. STARBASE now runs **1384 passed, 24 skipped, 0 failed** as
an ordinary unelevated user, from 8 failures at the start. Two are honestly incomplete: `T-068`
cannot say why the runners do not show the empty font database, and `T-069` is reproduced and
narrowed but not fixed. `docs/WINDOWS_VERIFICATION.md` records the machine, the harness, and the
two traps that make a Windows run look valid when it is not. The original four: The largest
is that `ci.yml` installs with no virtualenv while `docs/DEVELOPMENT.md` tells developers to use
one — and on Windows a venv's `python.exe` spawns the real interpreter as a child, so every
`multiprocessing` spawn sits one level deeper than CI ever tests. That is exactly the tree shape
`T-019`'s reaping evidence is about. Also: `LongPathsEnabled=0` is the Windows default and fails a
path test CI passes; Qt writes a font warning there and not on a runner; and an end-to-end
recovery test is intermittent. **CI is one Windows configuration, and an unusual one.** `T-040` and `T-056` still need the `windows desktop` job —
`T-040` for the two `T-026` mutations, which a green normal run does not supply, and `T-056` for a
branch that has never executed. **GitHub Actions usage is exhausted as of 2026-07-28 and CI cannot
run for several days** (maintainer) — workflow `30392139504` failed before executing a single
step, on GitHub's billing annotation — so the *verified on Linux and Windows* criterion cannot
move until it resets or another Windows runner appears. Then the exit review.

**The lesson is about method, not ffmpeg.** `T-037` was written, reviewed and approved on a machine
that had what the runners did not, and had never passed on either. Four CI failures in one batch
were one sentence: a test asserting something true of the author's machine.

**`T-040` is Blocked with `T040-R1` still open, carried to `T-060`.** The correction drove keyboard
focus as asked and then asserted a state that cannot exist: on a failed job `Cancel` is disabled
and on a running one `Retry` and the error text are hidden, so no chain offers all three controls.
The structural half passed because `focusPolicy() != NoFocus` is true of a *disabled* widget — a
list agreeing with a list, which is the shape that task exists to stop being satisfied by.
`T-060` has since landed and the job is green, but `T-040` stays Blocked: what it owes is the two
`T-026` mutations run **on Windows**, and a passing normal run is not evidence for a mutation that
was never executed.

**And one of those mutations turns out to be unkillable** (`T060-R2`, measured). No state of the
progress view offers more than two reachable controls, and a two-element focus cycle is its own
reverse — from either control, Tab and Backtab both deliver the other. Reversing those two cannot
be observed by any keyboard walk. Order is gated on the add-URL dialog instead, whose states offer
nine to twelve controls, and where the swap is killed in all three states.

**What the day's work turned on.** `T-016`'s third re-review reported its two open findings in
three places each, and all six had one cause: **a synchronous write sequenced every following
effect for free, and an asynchronous one sequences nothing.** `ARC-005` had landed on the claim
that a write-through view made the change invisible to its callers — *"only the announcement
moved"*, *"callers unchanged"* — and each defect was that equivalence failing somewhere different.
The correction is a per-job lifecycle rather than three patches, and `ARC-005` is **amended** to
say so (2026-07-28): asynchrony is not free at the call site.

**DRM was never the uncovered mandatory area this file claimed.** Reading the tests rather than
the record found three layers already gating it; `T-017` added the fourth (the UI half), `T-057`
canaried the yt-dlp field the whole boundary rests on, and `T-058` recounted `ai/TESTING.md` §7 —
where the count lives, and where this file now sends you rather than restating it. `T-057` found
two real divergences on the way: the adapter read `has_drm='maybe'` as protected, and its fallback
used `all` where `_has_drm` — the branch that actually runs — uses `any`, so the two halves of one
function disagreed about a mixed item.

**`T-036` and `T-037` found two defects nothing else could see.** Composition's retry raised out
of a write callback — the pool of one refuses while something else runs, and the refusal escaped
into a Qt slot instead of reaching whoever pressed the button. And a quit that skipped the
shutdown lifecycle *aborted the process*: Qt terminates with `SIGABRT` when a running `QThread` is
destroyed, so `T-007`'s launch test exited `-6`. Neither is visible to a component test, which is
the argument for `T-036` existing at all.

**Three `T-036` tests were written against the store and each caught the same thing.** `T-013`'s
ordering is *persist, then signal*, and `ARC-005` moved the persisting to another thread — so the
writer commits a row and **then** posts to the GUI thread, and in between `store.get()` answers
the new state while every widget still shows the old one. A test of the assembled application
waits on what the application shows. `is_idle` has the mirror-image trap: it is true before a
session starts as well as after one ends.

**`mypy --platform win32` caught a test that could not run on Windows.** `T-037`'s kill helper
reached for `os.killpg`, which does not exist there, so the `windows-latest` job would have
reported an `AttributeError` rather than a finding. `AGENTS.md` §8's "a host-only check is not the
whole gate", found by the gate that exists for it.

**`T-017` is Complete**, closed 2026-07-28 once `T-059`'s approval resolved `T017-R4` — the
finding that had been carried out of it rather than corrected in a sixth pass. All five findings
are resolved and no new verdict was needed: the review that settled the last one is `T-059`'s.
Its delivered code spans two commits, `f100108` and `52f0aed`, which a reviewer reading a single
head should know. Two of the five rounds were regressions I introduced, and the shape is worth
keeping: the widget draws from two sources — live progress and the durable row — and each
correction chose between them at one more call site. The fifth wrote the rule down; the reviewer
then found the one entry point that still bypasses it, `_load`, which no test in the task reaches
because **every test starts from a running view**. A suite that never opens a view onto a finished
job cannot see what opening one does. `T-059` owns that, and should land before or with `T-036`.

**`T-056` is corrected but not demonstrable here.** The fix is Windows-only, and the mutation that
proves it survives on Linux by construction. That is `AGENTS.md` §8's "a host-only check is not
the whole gate" in its exact form, and it needs the Windows job.

- **`T-016` is Approved**, 2026-07-28 at `6ce195a`. Four correction batches; `T016-R1` and
  `T016-R3` were independently verified resolved on the fourth. The Critical is worth carrying
  forward past approval, because each round restated it rather than repeating it: a probe result
  was first bound to a **job id** and not to the URL on screen, then to a withdrawal nothing
  owned until it was durable, then to a start that could be cancelled after it had been reserved
  and before it existed. Every version had the same consequence — work the user had taken away
  running anyway — and the last two only became reachable when `ARC-005` made writes
  asynchronous. *(This bullet said "Changes requested, first correction batch returned" until
  2026-07-28, three batches after that stopped being true, and sat directly above a description
  of the fourth. `T-054`'s reviewer found it.)*
- **`T-019` and `T-038` are both Approved**, 2026-07-27 — `T-019` at `eaa5b50`, `T-038` at
  `098ba3f` after three focused corrections of High `T038-R2`. That finding was the one that
  "directly regresses High `T013-R2`": the per-job log handler closed when the *result* pump
  finished, without establishing that the *log* listener had drained, and listener shutdown
  blocked the GUI thread for a measured 2.001 s. Both halves are fixed — a same-job reopen returns
  the identical still-attached handler, and `idle` is withheld while the listener thread is alive,
  polled by the existing timer and never joined, with `gave_up_on_the_log` as the bounded escape
  if it wedges past `reap_seconds`. `T013-R2/R3/R4` were re-examined and remain resolved.
  `ai/TESTING.md` §7's coverage was recounted by `T-058` on 2026-07-28, with the DRM row's four
  claims each mutation-checked before being recorded. The count itself lives in §12 and is not
  repeated here.
- **`T-013` closed after three correction passes.** `T013-R1`, `T013-R2` and `T013-R4` were
  verified resolved; `T013-R3` came back twice more with a different sibling each time, so the
  maintainer authorized **restructuring** the startup transaction rather than patching it again:
  the session now records each start as it happens, and the unwind reads that record instead of
  inferring it. `T013-R5` remains non-blocking hardening owned by `T-052`.
- **`T-013` approved with follow-ups and `T-015` approved**, 2026-07-27. `T-018` reached its
  **fifth** correction of the same Critical (`T018-R1`). Three recogniser passes each closed the
  reported spellings and left another the rule had not been written to see; the fourth made an
  allowlist the control (`SEC-002`), and the reviewer verified that it works. The fifth removed
  what stood beside it: the schema fingerprint copied captured mapping **keys** verbatim, so a
  secret used as a key was written to disk while all three gates called the file clean. `SEC-002`
  is amended — the fingerprint is gone, `write()` derives everything it writes, and a playlist
  entry is a count rather than a record. **`T-018` is closed as Approved on that fifth pass.**
- **The lesson, a fourth time in one task:** every one of the five rounds ended the same way —
  something was being kept without a reader for it, and the argument for keeping it was always
  "it's only shape / only names / only the parts we recognise". The allowlist survived review
  because it starts from what is *read*. Anything else in a fixture is a liability with a story.
- **`ai/TESTING.md` §12 holds the mandatory-area coverage count; §7's areas are all in the
  default local run.**
  `T-013` added Cancellation and Worker crash against real spawned processes; both moved behind
  `-m process_tree` in `9010794`, because `T-019`'s live defect left descendants that wedged later
  runs. **`T019-R1` caught that the same marker removed them from CI**, which ran a bare `pytest`
  and inherited the exclusion — so for one day two mandatory areas gated nothing anywhere, while
  three records said CI still covered them. `T-019` removed the marker along with the defect.
  Log redaction closed with `T-038`'s approval. **DRM was never the uncovered area this file
  claimed it was** — three tests already gated it, and the record had simply never been
  recomputed. `T-058` recounted it; `T-017` added the UI half and `T-057` the upstream contract.
  The count is now stated in one place, `ai/TESTING.md` §12, and this bullet points at it.
- **The lesson from `T-044`, `T-045` and `T-014`, now three for three:** each blocking finding
  came from filtering unbounded input instead of constraining what the input could be. `T-044`
  stopped parsing for exports and read the interpreter's namespace; `T-045` dropped a completeness
  claim it could not keep; `T-014` made a proxy credential *unrepresentable* in the model rather
  than strippable in persistence. **`T-038` is this problem again** and should start from that,
  not from a recogniser.

**`T-072` is filed, and it is what `T-040` and `T-060` are waiting for.** The STARBASE correction
re-review closed under the maintainer's last-pass direction: carry the residue into a named task
rather than start another correction loop. That task did not exist, so the two behaviourally
accepted tasks had nowhere to carry to. `T-072` now holds `T066-R1`'s survivor assertion and its
unrun `T-019` process-tree cases, `COORD-R5`'s filing and current-truth cleanup, and `WIN-R1`'s
firewall-rule repair, plus the non-blocking `WIN-R3` and `RUNNER-R1` documentation corrections.
`T-040` and `T-060` may close as Approved-with-follow-up on this carry **without another
behavioural review**. See `T-072`.

**`T-071` — the icon was undersized, and the master says why.** Reported from a taskbar
screenshot and fixed the same day: every derived asset drew the logo at ~66% of its canvas with
the slack as one empty band beneath it, so at 32 px the mark filled ~43% of the cell by area.
The master carries a 194 px band of alpha-1..8 pixels below the artwork — invisible, but content
to a trim on `alpha > 0`. All eight PNGs and the `.ico` are regenerated at 92% fill and centred,
now from a script (`tools/icons/render_icons.py`) so it cannot drift back unrecorded. The master
is untouched and the pinned frame sets are unchanged. **Confirmed by the maintainer in the Linux
taskbar**; Windows is unobserved. **Approved at `3327fd3` with no findings** — the reviewer
reproduced every asset byte-for-byte from the script — and filed Complete. See `T-071`.

## Next

`ARC-002`'s ordinary end-to-end path is proven: a spawned child imports yt-dlp, extracts and
reports typed messages back (`T-012`); a job survives a restart and an unclean kill (`T-014`);
and, in a test, a URL becomes a file on disk through `T-013`. T-013 is now approved, so that path
is something to build on, and cancellation now reaps the worker's descendants too (`T-019`).
**`T-016`'s dialog is the one widget that touches it**, and it is in review rather than reachable:
composition is `T-036`, so `app.py` still builds a window with no manager and the menu item stays
disabled. The first *user-visible* download is `T-037`. *(This paragraph said "no widget touches
any of it yet" until 2026-07-27, a few lines before another that described `T-016`'s widget doing
exactly that — the contradiction `T016-R8` reported.)*

1. **`T-018` is approved and closed** (2026-07-27, `T018-R1` and `T019-R1` both Resolved). The
   fifth correction removed the schema fingerprint that could carry captured mapping keys;
   `SEC-002` records the amendment and what it gives up.
2. **`T-019`, `T-038` and `T-051` are all approved and on `main`.** `T-019` fixed the live defect
   — cancelling now reaps the worker's whole process group, and the `process_tree` marker is gone
   with the reason for it. `T-038` puts redaction in a formatter, so no call site can leak by
   forgetting, and its High `T038-R2` took three focused corrections. `T-051` is a decision,
   `ARC-004`. The `phase1-orphans-logging-lifecycle` branch that carried them is merged.
3. **Windows has runtime evidence, and it found a real bug.** `30293051118` first ran the
   process-tree suite on both platforms; `30302798113` then ran `T-019`'s new descendant tests
   there and **failed**, because `ctypes` had truncated the Job object's handle — invisible on
   Linux by construction. `30303348265` is green on every job, with all four grandchild tests
   and the containment check passing on `windows-latest` (1163 passed, 20 skipped). Phase 1's
   "verified on Linux *and* Windows" criterion has moved for the first time since it was written,
   and the move was worth more than the confirmation: pushing bought a defect nothing local
   could have found (`T019-R2`).
4. **`T-016` is merged to `main` at `33ebd11` and in review.** It is the first code that makes
   any of the engine visible to a person: paste URLs, probe one in a worker process, see title,
   uploader, duration, a decoded thumbnail and whether it is a playlist, pick a preset, queue them
   all. It also implements `ARC-004` — `DownloadManager.start()` now takes a `READY` job as well
   as a `QUEUED` one — which amends code `T-013` was approved with, and replaces the `T-013` test
   that asserted the older rule.

   Twelve deliberate weakenings were run against the new tests and all twelve were killed, but
   **three gates reported clean while covering nothing**, and that is the part worth keeping. The
   tab-order test derived its expected order from the same list the dialog hands to Qt, so it
   proved only that the list equalled itself and the mutation survived. The local type gate was
   the wrong *scope* — `mypy src` reads 33 files, the `windows desktop` job reads 69 including
   `tests/` — and CI found two real errors, one of which had silently stopped mypy analysing the
   rest of a test. The Windows UI Automation menu contract then caught a File-menu item this task
   added without declaring it. Each was corrected, and `ai/TESTING.md` §12 now states the scope
   difference that nothing had written down.

5. **`T-017` is implemented** (2026-07-28) and in review, so the critical path to the phase exit
   is now **`T-036` → `T-037`**. `T-036` depends on `T-016` *and* `T-017`, so composition begins
   when both clear review rather than when either does. *(This item used to end "DRM is
   the one uncovered mandatory area and still has no owner". It was neither: see
   `ai/TESTING.md` §12.)*
6. **`T-050`** — **Phase 2**, not Phase 1: the `history` table is still empty, and
   `IMPLEMENTATION_PLAN.md` puts `REQ-020`'s history persistence in Phase 2. This file's claim
   that `T-013` owned it was `STATUS.md` running ahead of both the plan and `T-013`'s own scope;
   the task entry records the two things still missing before it can be written honestly.

**What two review rounds cost, and what they bought.** Eight blocking findings across two
passes, every one real. The pattern worth remembering: **five of them were things that
computed the right answer and then failed to act on it** — the resolved yt-dlp version never
left the worker, the rendered path was validated and then re-rendered, ffmpeg was located and
never passed to the library, an audio codec was chosen and never requested, and the frozen
probe resolved an extractor name without loading the extractor. Each looked correct in the
code and produced no error.

The tests that missed them shared a shape too: they asserted on the *input* to a boundary
rather than on what came out the far side — a key present in an options dict, a local variable
on the worker's side of the queue. `ai/TESTING.md` §13 now has the general form of this.

## Known gaps not yet scheduled

- **`T-035` was missing from the plan.** `downloader/environment.py` was claimed by no task
  and `REQ-024` (ffmpeg detection) by nothing at all, though `ARCHITECTURE.md` §6 puts yt-dlp
  resolution at worker start and `T-012` therefore needs it immediately.
- **`T-034` was missing from the plan.** Filename safety and output-path containment
  (`core/paths.py`) belonged to no task, despite `ARCHITECTURE.md` §8 requiring every output
  path to pass through it and `ai/TESTING.md` §7 listing path safety as mandatory. Found while
  planning Phase 1; now filed and blocking `T-012`.

- **`T-033` — implemented, not closed** (`P1-R2`). The spec collects yt-dlp's submodules and
  data files; the probe resolves an extractor *by name* through the lazy machinery and asserts
  the bundled version against the pin (`T033-R1`). It stays **In Review** until the frozen jobs
  run on both platforms: the local probe is source-mode and proves nothing about the artifact,
  which is the entire subject of the task. An earlier version of this file called it "closed"
  here while listing it as pending above — the contradiction `P1-R2` reported.

## Open questions for the maintainer

- *(`ARC-003` was accepted on 2026-07-26, closing `T011-R5`. It narrows `ARC-002`'s "versioned
  internal contract" to version-controlled, and names its own expiry: any packaging in which
  parent and child become separately deployable re-opens the question.)*

- **Confirm the Phase 1 prerequisite amendment.** `IMPLEMENTATION_PLAN.md` said "Phase 0
  complete" while `TASKS.md` treated `T-010` as startable — and the plan outranks `TASKS.md`
  (`AGENTS.md` §5), so `T-010` was formally blocked. The prerequisite now reads "Phase 0's
  **deliverables** complete, merged and reviewed", separating those from the exit criteria,
  one of which needs a Windows machine. The Windows criterion is **not** waived; it still
  blocks Phase 0's formal exit and first release.

*(`OPS-004` was accepted on 2026-07-26 and is no longer open. Its installer half became
`T-039`, blocked until Phase 5 produces an installer.)*

## Blockers

- **`T-033` — blocked on CI evidence, not on code.** Its corrections are reviewed and verified,
  but approval needs the collection-removal negative run, Linux **and** Windows frozen results,
  and the recorded artifact-size delta. PyInstaller is in the `build` extra and absent from the
  working venv, so none of it can be produced here. Clears when the frozen jobs run against the
  pushed boundary.

*(the `T-003` logo blocker cleared on 2026-07-25 when the maintainer supplied the source
asset)*

## Repository

`github.com/kottmans/tracks-and-trails` — **private** for now, intended to go public later.

Commits are authored as `40611149+kottmans@users.noreply.github.com`, set in **repo-local**
git config so the maintainer's personal address never enters a history that will eventually be
public. This is per-repository, not global: a fresh clone, or a new repo, needs it set again.

To do when it goes public: state that contributions are accepted under MIT (`LIC-001`), and
re-check that no personal paths or local configuration reached the history.

## Environment baseline

Development machine, verified 2026-07-25:

| Item | State |
|---|---|
| Python | 3.14.6 (`/usr/bin/python3`) — the only interpreter; **confirmed sufficient** (`T-002`) |
| `pip` | 26.0.1, installed via `ensurepip --user` into `~/.local` (no sudo, no PEP 668 marker on F44) |
| Project venv | `.venv/` — **repaired 2026-07-28** (`T-063`). It had been installed from a parent directory, so the console script's shebang named a missing interpreter and the editable `.pth` pointed one level above the checkout: neither `tracks-and-trails` nor `python -m tracks_and_trails` worked, and every command used `PYTHONPATH=$PWD/src`. Re-running `pip install -e ".[dev]"` from the checkout fixed both; `docs/DEVELOPMENT.md` carries the symptom and the check. Editable install, PySide6 6.11.1, platformdirs 4.11.0. `comtypes` is a Windows-only dev dependency and is absent here by design |
| Dev tools | ruff 0.16.0, mypy 2.3.0, pytest 9.1.1, pytest-qt 4.5.0, PyInstaller 6.21.0, psutil — no longer packaging-only, the default suite needs it since `T-013` asserts on real processes |
| ffmpeg | present |
| git | branch `main` tracking `origin/main`; CI green on every push and PR (`T-006`) |
| Repository path | **Unsettled, and this row has now been wrong in both directions.** On 2026-07-27 the `T-013` session ran entirely in `/mnt/projects/software_projects/tracks-and-trails`, where `ls`, `readlink -f` (not a symlink) and every check and test agree, while `/mnt/storage` does not exist at all. The previous entry asserted the reverse. Rather than flip the value a third time: the working checkout is wherever the maintainer's shell says it is, and **this row should record a machine, not a truth** — one of the two paths is presumably a mount that is not always present. Needs a maintainer answer, not another edit |
| Windows environment | **CI runners only** — no local Windows machine or VM. The runner is a real desktop, not a bare headless box (`OPS-004`), and the dedicated `windows desktop` job uses it: the other jobs pin `QT_QPA_PLATFORM=offscreen`, that one does not |

## Current risks

| Risk | Impact | Standing |
|---|---|---|
| ~~PySide6 may lack Python 3.14 wheels~~ | — | **Closed** by `T-002`: PySide6 ships `abi3` wheels serving all Python ≥3.10 |
| No Windows machine — CI only | Interactive Windows behavior (screen reader, dialogs, keyboard, theming, installer) is **known-unverified**, not merely untested | Narrowed by `OPS-004`: the runner has a real desktop, so the objective half is automatable and `T-026` owns it. Only the subjective residue needs a person, and that still blocks first public release |
| `ARC-002` process model is unproven | It is the project's central architectural bet | **Mechanics validated on Linux** by a `T-002` probe (spawn under a live `QApplication`, structured progress over `mp.Queue`, instant terminate with no orphan). Phase 1 still proves it under a real download. |
| `ARC-002` may break once frozen — `spawn` from a frozen binary relaunches the app | Recursive launch; invisible until Phase 5 without a guard | `freeze_support()` + `T-020` frozen smoke test in Phase 0 CI |
| yt-dlp upstream churn | Ongoing maintenance cost | Confined to two modules (`NFR-008`); pinned fixtures |

## Notes

**Something downloads now — in a test.** What `T-013` connected is the *engine*: given a job in
the repository, a real spawned worker downloads a real URL to a real file and every transition is
persisted. `T-016` adds the first widget that calls it — the add-URL dialog probes, displays and
queues through `DownloadManager`, and its tests drive that path end to end.

**A user still cannot reach any of it.** `app.py` builds `MainWindow` with no manager, no job
store and no output directory, so File → Add URLs… is **disabled**, saying so in its status tip.
Supplying those three is composition (`T-036`); the first URL a *user* can download is `T-037`.
Treat `ARCHITECTURE.md` as the approved target rather than a description of what a user can do.

Precisely, recounted 2026-07-28 by parsing each module for anything beyond its docstring: of the
**35** modules under `src/`, **11 are still docstring-only stubs** and **24 have code**. Two of
the three changes since the 2026-07-27 count came from `ARC-005` — `persistence/store.py` and
`persistence/writer.py` are new modules, which is why the denominator moved as well as the split
— and the third is `ui/job_detail.py`, `T-017`'s progress view and **the second widget beyond the
shell window**. `ui/queue_view.py` stays a stub deliberately: a multi-job table is Phase 2, and
`T-017`'s scope is one job.

*(Before `T-014` this said 23 stubs and eight coded, recomputed at `697e024`; it had gone stale
across four tasks. The previous count of 31/13/18 was itself two modules stale, missing
`core/logging.py` and `downloader/process_tree.py`, which landed with `T-038` and `T-019`. Each
count is recounted rather than adjusted, which is how that was caught.)*

The `core/` modules remain **domain vocabulary plus pure functions** — what a job, a request and
a failure *are*, the rules for moving between states, and filename safety. `persistence/` is the
first module that keeps something across a restart.

**`TESTING.md` §12 holds the mandatory-area coverage count, and this file does not repeat it —
including the denominator.** Two statements of one number in one file was the defect the last
correction named; two files stating it was the defect that survived that correction, and it is
why "DRM is uncovered" outlived being true by four tasks. `T-058` recounted the rows; `T058-R1`
then found that the correction had *restated* the new number here three times while claiming this
very sentence was true. Pointing at a number and repeating it are not the same act, and only the
first one keeps.
