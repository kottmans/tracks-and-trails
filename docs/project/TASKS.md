# TASKS.md — Tracks & Trails

**Purpose:** Unfinished work: review, ready, proposed and blocked tasks.
**Owner:** Planner (priorities); Implementer (task/status); Reviewer (review disposition)
**Last updated:** 2026-09-17
**Update when:** Work starts, changes scope/status, closes or reopens.

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
Complete and Cancelled records live in [COMPLETED_TASKS](COMPLETED_TASKS.md).
Move each record there in the same update that closes it; keep no closed-task
stubs here. Preserve IDs, evidence, limitations and follow-up routes. Check both
files before allocating an ID; IDs are never reused. Task-reading tests and
the placement gate read both files. Current phase and blockers are in [STATUS](STATUS.md).

## In Review

### T-343 — The taskbar's Close window does nothing while a dialog is open

**Status:** **In Review** — built and **measured on the real Windows desktop 2026-09-17**: both
forms of the gesture close the dialog and then the application, with the defect asserted in the
same run (run `35276130787`, 46 passed). The shape was ruled the same day (the Windows-only
handling, below), and this is **the first task of Phase 4.5**, shipping in `0.1.1` with `T-347`.
*(Was In Progress:)* the build landed before the measurement did, and the runner found four
defects in it that no gate on the development machine can see. *(Was Proposed:)* left as it is for
`0.1.0` by the maintainer on 2026-09-15, chosen from three options (leave it and file a task; close
the dialogs then quit, on Windows only; make *Add URLs* and *Preferences* non-modal). Not
release-blocking.
**Owner:** Maintainer decides; Implementer builds
**Priority:** Low — the standard behaviour of a modal dialog on Windows, reported as surprising
**Phase:** Phase 4.5 — stage 1, the `0.1.1` patch
**Relevant context:** `T-308` (window-modal dialogs and their parent); `C-003` (parity)
**Affected surfaces:** `ui/taskbar_close.py` (new), `app.py`'s `present`, `tests/ui/test_taskbar_close.py`,
`tests/ui/test_windows_desktop.py`, `tests/integration/test_composition.py`
**Evidence:** [`2026-09-17-T343-taskbar-close.md`](evidence/2026-09-17-T343-taskbar-close.md) — the
measured table, the offscreen suite, the mutation campaign, and each of the four defects the runner
found with what it would have shipped as

#### What was found

Reported by the maintainer: with a dialog other than the queue open, right-clicking the taskbar
button and choosing *Close window* does not close the application. **Reproduced on `STARBASE` at
`8d70e01`** by posting the taskbar's messages to the main window:

| Open dialog | `WM_CLOSE` | `WM_SYSCOMMAND` / `SC_CLOSE` | Main window enabled |
|---|---|---|---|
| none | closes | closes | yes |
| *Add URLs* | ignored | ignored | **no** |
| *Preferences* | ignored | ignored | **no** |

Both dialogs open with `open()`, which is window-modal, and Windows disables the owner of a modal
dialog, so its close is not acted on. Qt also drops a close event for a window a modal dialog blocks,
so the same holds for a window manager's close on Linux (not measured).

#### The shape, ruled 2026-09-17

Put to the maintainer with the Phase 4.5 plan, as a choice between the same two alternatives.
**Ruled: the Windows-only handling.** A Windows message filter closes the open dialog and then the
application; *Add URLs* and *Preferences* stay window-modal on both platforms. The reason offered
with the recommendation, and accepted: non-modal dialogs change how the whole application behaves,
which would need its own `UX` ruling and its own tests, while the report was about one gesture on
one platform.

**What the shape leaves to the implementer:** what happens to URLs pasted into *Add URLs* but not
yet added. Discarding them is what *Cancel* already does; anything else needs a reason and a test.

#### Unadded URLs: discarded, and nothing new is lost

**`AddUrlDialog.done` is where every exit route already arrives** — *Escape*, the window button,
*Cancel* and `accept()` — and it abandons the staging list and unstages each probe (`T016-R2`,
`T118-R1`). A taskbar close reaches the same place, so this adds no loss that the dialog did not
already have, and a prompt would be a question on a window the user has told Windows to close.

**One dialog does refuse the close, and keeps the application open.** *Add URLs* holds its close
while a commit is in flight (`T118-R3`): `done()` returns without hiding, Qt ignores the close
event, and `close()` answers false. The application then stays up with the dialog's own *"Still
adding to the queue"* message. The gesture is still consumed, and the user closes again once the
rows are written. Asserted offscreen, including that the dialog is asked exactly once.

#### The measurement, 2026-09-17

Run [`35276130787`](https://github.com/kottmans/tracks-and-trails/actions/runs/35276130787), the
`windows desktop` job: **46 passed**. Both forms of the gesture close the dialog and then the
application, and **the defect is asserted in the same run**, immediately before, so the fix cannot
be passing on a machine where the problem never existed.

**The dialog measured is a window-modal `QDialog`, not the two screens themselves.** Window
modality is what disables the owner and both of them open with `open()`, which the test asserts.
A person on the built application closes the remaining gap, at the end-of-phase walk.

**Four defects the runner found that no gate here could**, each recorded in the evidence with what
it would have shipped as: `wintypes.MSG.from_address` on the `VoidPtr` PySide6 really passes (a
filter raising on every Windows message); a Python reference from the filter to its window
(`T-289`'s shape); `deleteLater()` with `processEvents()` not deleting; and Qt **not** removing a
destroyed filter from the dispatcher, against its own documentation.

#### Scope

Build the Windows-only handling, then measure the table above again with it. Linux is out of scope
by the ruling: Qt drops a close event for a window a modal dialog blocks there too, and that was
never measured, so no behaviour is claimed for it.

#### Acceptance criteria

- [x] A recorded decision — 2026-09-17, above
- [x] The table above measured again with the chosen behaviour, on Windows — run `35276130787`
- [x] What happens to unadded URLs is decided, stated here, and covered by a test

---

### T-326 — The release-candidate suite: everything the gate asks a machine for, on both platforms

**Status:** **In Review** — **run against the `0.1.0` candidate on 2026-09-14** ([evidence](evidence/2026-09-14-T326-release-candidate-0.1.0.md)): items 1–5, 8, 10 and 10a each with their artifact on both platforms where the item asks, the network suite retained for both, and the `0.2` migration-fixture obligation in `docs/RELEASE.md`. *(Was In Progress:)* the items that do not need a release candidate were run 2026-09-12;
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

## Ready

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

### T-347 — Show in folder leaves an already-open Dolphin window minimized on KDE Wayland

**Status:** Proposed — **left for after `0.1.0` by the maintainer on 2026-09-15**, from two options
(leave it and file a task; try to fix it now). Not release-blocking. **Scheduled 2026-09-17** into
the `0.1.1` patch, second after `T-343`.
**Owner:** Implementer
**Priority:** Low — the file is selected in the window the user already has
**Phase:** Phase 4.5 — stage 1, the `0.1.1` patch
**Relevant context:** `T-086`, `ui/reveal.py` (`FileManager1.ShowItems` over `dbus-send`)

#### What was found

Tried by the maintainer on KDE Plasma (Wayland), Fedora 44, with a test window running the exact
call the application makes:

| Dolphin before the click | Result |
|---|---|
| closed | opens in front with the file selected |
| open on another folder, or minimized | comes to the front |
| **open on the download folder** | selects the file, **stays minimized on the taskbar** |

`ShowItems` is sent with an empty startup id. On Wayland, raising an existing window needs an
xdg-activation token from the application the user clicked in, and Qt gives Python no public way to
request one.

#### Scope

Find a dependable way to pass an activation token (for example through the desktop portal's
`OpenDirectory` with an `activation_token`, or a Wayland activation request), and measure the three
cases above again.

#### Acceptance criteria

- [ ] The download folder already open: Dolphin comes to the front with the file selected
- [ ] The other two cases unchanged

---

### T-349 — The `0.1.1` patch release

**Status:** Proposed — **ruled by the maintainer on 2026-09-17** with the Phase 4.5 order: the two
`0.1.0` defects left open go out as a patch before the phase's own work starts
([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17)).
**Owner:** Implementer prepares; Maintainer tags and publishes
**Priority:** Medium — it carries two Low-priority fixes, and it is the first update `0.1.0`'s users
are told about by the checker they already have
**Phase:** Phase 4.5 — stage 1
**Depends on:** `T-343`, `T-347`
**Relevant context:** `docs/RELEASE.md` (the five steps, and *patch releases carry fixes only*);
`TESTING.md` §8 (the release gate); `REL-003` (SemVer); `REL-009` (the checker that tells users)

#### Scope

`0.1.1` from `main`, carrying `T-343` and `T-347` and nothing from stages 2 to 4. It is the second
run of the release process while it is still fresh, and three things happen for the first time:

- **`TESTING.md` §8 item 5 gets its first real use.** The migration check has never had a previous
  release's database to open; `0.1.0` is the first there is one for. `tests/fixtures/schema_versions/`
  holds the per-version fixtures the suite already uses, `v12.sql` being the newest.
- **The update checker reaches real users.** Everyone on `0.1.0` is told, by `T-338`'s check, that
  a newer release exists, and updates by hand (`REL-009` item 3).
- **The release notes are written for people who already have the application**, rather than for
  someone meeting it.

#### The `§11` walk, ruled 2026-09-17

**This release ships without `TESTING.md` §8 item 6**, and that is the maintainer's ruling rather
than an omission: *"go with your recommendations, except for the acceptance walk. We'll do that at
the end of 4.5 when everything is finished."* One walk, on the finished phase, closes `T328-R4`,
`T-340`, `T-342`, `T-344` and Phase 4.5's own criterion together.

**`0.1.0` was the first release to ship without it** (2026-09-16) and this is the second. Nothing
user-facing says otherwise, and nothing here claims the criteria were checked.

#### Acceptance criteria

- [ ] `T-343` and `T-347` complete and approved
- [ ] `TESTING.md` §8 run on both platforms, **item 6 excepted by the ruling above**, with item 5
  carried out against `0.1.0`'s database rather than a fabricated one
- [ ] The five steps of `RELEASE.md` followed, evidence recorded as `0.1.0`'s was
- [ ] `main` back to a `.devN` version afterwards

---

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
**Carries:** **`T-048`** — that migration is expected to be the project's first that *transforms*
stored values rather than leaving them alone or removing a table, which is the condition `T-048` has
waited on since Phase 2. **By the 2026-09-17 order it is done inside this task's review**, not filed
onward as a later task. If the field turns out to need no data transformation, say so there and
`T-048` keeps waiting
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

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data.
*(Premise re-checked 2026-08-06 after `T169-R5`. Still true, and narrower than it was: `0009`
**destroys** data rather than transforming it. That is a different problem with a different answer
— it needs a test proving the rows are gone, which it has, not an allowance for values that
legitimately changed, which is what this task is for. What did move is the strict per-column rule
below: it now covers `jobs` only, because `history` no longer exists to compare.)*
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** Phase 4.5 — inside `T-184`'s review
**Scheduled:** 2026-09-17 — `T-184` adds a field to `DownloadRequest`, so its migration is expected
to be the first that transforms stored values. The maintainer's order does this task **in that
review** rather than after it ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17)). The premise
still has to hold: a migration that only adds a column with a default transforms nothing, and then
this task waits again
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

### T-339 — Hear Narrator read the Windows application

**Status:** Proposed — **deferred past `0.1.0` by the maintainer on 2026-09-14** (`T-327` item 3). Not
release-blocking for `0.1.0`; its release notes say Narrator's speech was not checked by a person.
**Scheduled 2026-09-17** into Phase 4.5's last stage, beside the acceptance walk: both need a
person at a Windows desktop, and the walk is one sitting at the end of the phase.
**Owner:** Maintainer performs; Implementer records
**Priority:** Medium — an accessibility claim `NFR-005` makes and a person has not heard
**Phase:** Phase 4.5 — stage 4, with the end-of-phase walk
**Relevant context:** `T-327` item 3, as scoped there; `NFR-005`; `IMPLEMENTATION_PLAN.md` §Phase 4's
screen-reader amendment (coherence *"belongs to the pre-release session"*);
`tests/ui/test_windows_accessibility.py`, which gates names and roles but cannot judge speech

#### Scope

With Narrator on, on an installed build: open Add URLs, stage a URL, open its format table, choose a
format, add it, start the queue, and open Preferences. Is what Narrator says *coherent*: does each
control announce what it is and what it does, in an order that makes sense?

#### Acceptance criteria

- [ ] The walk above done by a person, described in their words in a dated record
- [ ] Anything incoherent filed as its own task, with its severity under `TESTING.md` §14
- [ ] `REQUIREMENTS.md` §3's *known-unverified* line about Narrator rewritten to what was heard

---

### T-348 — Update the application from inside it, rather than by downloading the file

**Status:** Proposed — **asked for by the maintainer on 2026-09-17**, trying the `0.1.0.dev0` build
that reports a newer release: *"is the only way to update the program to download the new file?"*
Told that it is, by `REL-009`, they answered *"that should definitely be a phase 4.5 task."*
**Sequenced 2026-09-17: ruled in this phase, built in a later one** — see below. The shape itself is
**still owed**, so `REL-009` stands unamended and the application keeps notifying only.
**Owner:** Maintainer decides the shape; Implementer builds
**Priority:** Medium — every user of `0.1.0` updates by hand today
**Phase:** Phase 4.5 — stage 4, the ruling only
**Relevant context:** `REL-009` (notify only, and its *worth revisiting* clause), `REL-005`
(the unsigned installer), `OPS-002`'s note on automatic updates, `T-338` (the checker this builds
on), `NFR-007` (what the application may talk to)

#### What exists now

`Help → Check for Updates…` and the daily check say a newer release is out and open its page
(`T-338`). **Nothing is downloaded or run** — item 3 of `REL-009` — so the user fetches the new
AppImage or installer themselves and replaces what they have. Settings and the queue live in the
user profile, so they survive either way.

#### Why `REL-009` left it open, and what has to be answered

Its own words: *"worth revisiting once installers are signed: applying an update in place becomes
reasonable then."* The two platforms do not update the same way, and each raises its own question:

- **Windows.** An applied update runs the installer, which is unsigned (`REL-005`), so SmartScreen
  is raised again on every update, and the download needs its own integrity check. Signing is named
  as the `1.0` condition, so this may be a decision about ordering rather than about mechanism.
- **Linux.** An AppImage updates through its own mechanism (zsync, as `AppImageUpdate` and Gear
  Lever use), which needs the release to publish the matching file. Replacing a running AppImage
  is not the same operation as replacing an installed tree.
- **Both.** What is verified before anything is run (`SHA256SUMS` is published; a signature is not),
  what the user is asked, and what happens to a download in flight.

#### Sequencing, ruled 2026-09-17

The Phase 4.5 plan put three shapes to the maintainer — status quo, fetch and hand over, apply in
place — with the recommendation to **rule now and build later**, because in-place updating waits on
signing and signing is a `1.0` condition (`REL-005`, and `REL-009`'s own *worth revisiting* clause).
The maintainer took that recommendation.

**What that settles:** nothing is built for updating in Phase 4.5, and `REL-009` is not amended by
this phase. **What it leaves open:** which shape, which is the maintainer's to rule whenever they
choose, and at the latest with the signing decision. "Fetch and hand over" remains the one shape
that is buildable before signing, if they want something visible sooner; it still raises SmartScreen
on Windows, because that is the installer's signature rather than the download's.

#### Scope

Put the options to the maintainer with their costs, then build what is chosen. At least: check and
notify as now (the status quo); fetch the file and hand it over, verified, leaving the user to run
it; and apply the update in place, per platform. Whatever is chosen amends `REL-009`.

#### Acceptance criteria

- [ ] A recorded decision, amending `REL-009` — **still owed**; 2026-09-17 ruled only when it is
  taken and built, not what it says
- [ ] If built: the update is verified against what the release publishes before anything runs, on
  both platforms, with the failure path shown to the user
- [ ] If built: a clean-machine run on each platform, updating a real earlier release to a newer one
- [ ] `REQ-030`'s wording and the README's update section match what the application does

---

## Proposed — Phase 5

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Proposed — a potential task, not open work** (maintainer's release ruling, `T-328`, 2026-09-13, taking the recommendation). Never reproduced in 466 attempts, and repetition is spent; a recurrence turns the `windows desktop` job red on its own. It becomes a task again only if it recurs, ideally with crash capture armed (`tools/windows/crash-dumps.ps1`, `docs/WINDOWS_VERIFICATION.md`).

**Status before this ruling:** **Blocked — on `T-092`, 2026-08-20. Still undiagnosed, still not blocking Phase 1**
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

### T-336 — The installed app crashed once with heap corruption opening *Naming and folders…*

**Status:** **Proposed — a potential task, not open work** (maintainer, 2026-09-13). Seen once, in
`T-327`'s Sandbox session, and not reproduced by any route below. It becomes a task only if it
recurs or can be reproduced; until then nothing is owed on it.
**Owner:** Implementer
**Priority:** None while it does not recur; if it does, a crash is Critical by `TESTING.md` §14
**Phase:** Phase 5
**Promoted by:** a recurrence — ideally under the crash capture below, so it arrives with a dump
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

#### If it is promoted

- A dump of the recurrence, with the faulting module and stack read
- The cause named and fixed, with a test that fails without the fix

---

*Created 2026-09-10, when Phase 4.5 was resequenced to follow the first release and this
phase became the next one to run. `T-039` also carries `**Phase:** Phase 5` and stays under
`## Blocked`, because that section is about status rather than phase.*

## Blocked

### T-344 — Show progress while a download is being processed

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-344.md)); its last criterion is a person watching a long conversion on the installed build, which the waived walk would have covered (`T-328`, 2026-09-16). Phase 4.5. *(Was In Review:)* asked for by the maintainer on 2026-09-15: a long video took a long time
to process after downloading, and nothing showed the application was still working. The maintainer
chose *both, where possible* (a real percentage where ffmpeg can report one, otherwise the step's
name, a moving bar and the time so far) and chose to ship it **in `0.1.0`**, from the options put.
Moves the candidate.
**Owner:** Implementer
**Priority:** High for `0.1.0` by that choice
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `REQ-011` (indeterminate progress), `REQ-014` (stages), `NFR-005`, `T-216`
(a finished bar is furniture)
**Affected surfaces:** `downloader/protocol.py`, `downloader/worker.py`, `downloader/ytdlp_adapter.py`,
`ui/queue_view.py`, `ui/row_delegate.py`

#### What was wrong

While a job was post-processing the row showed the download's bar, which is full once the bytes are
in; the chip read *Processing*, and nothing moved. yt-dlp's post-processor hook reports only
*started* and *finished*, and `real_run_ffmpeg` runs ffmpeg through `Popen.run`, which returns when
ffmpeg ends.

#### What changed

- **`Progress` gains `step`** (yt-dlp's hook name for the step) **and `step_fraction`** (0 to 1).
- **The worker** records the step and the media's length when a step starts, and turns ffmpeg's
  position into a fraction of that length, sent at most every 0.25 s. It checks for cancellation
  there too, so a long conversion stops when asked. Downloads only; a probe runs no step.
- **`ytdlp_adapter.ffmpeg_progress`** replaces the `Popen` that yt-dlp's `postprocessor.ffmpeg` looks
  up, for step commands only (those carrying `-loglevel repeat+info`). It adds `-progress pipe:1
  -nostats`, reads the position lines, drains standard error on its own thread, returns what
  `Popen.run` returns, and kills ffmpeg if the callback raises. If yt-dlp no longer has that module
  or `Popen`, nothing is installed and the row falls back to the moving bar.
- **The row, while processing:** the step in plain words with the time so far (*Converting to audio
  · 1:05*), the step's own percentage on the chip and the bar when known, and otherwise a moving
  bar (`BUSY_ROLE`) redrawn by a timer that stops when nothing is processing. The size keeps the
  downloaded total, and the screen-reader text names the step and its percentage or says it cannot
  be measured.
- **Words are keyed by the names yt-dlp's hook reports** (`pp_key`, which drops *FFmpeg*). The first
  version used class names and would have named nothing; the end-to-end test found it.

#### Acceptance criteria

- [x] Protocol: `step` and `step_fraction` carried and validated (`tests/unit/test_protocol.py`)
- [x] Adapter: step commands recognised, arguments inserted after the executable, positions read from
  both microsecond keys, the returned shape kept, ffmpeg killed when the callback raises, a yt-dlp
  without the module left alone, and a real `FFmpegExtractAudioPP` conversion reporting positions to
  the end of the file with yt-dlp's `Popen` restored (`tests/unit/test_ffmpeg_progress.py`)
- [x] Worker: a started step announced by name; the position as a fraction, bounded and throttled;
  no fraction without a length; cancellation at the next position; the hook around downloads and
  never probes (`tests/unit/test_step_progress.py`)
- [x] Row: the step's percentage and not the download's; the moving bar, name and time without a
  position; the time restarting per step; a step without words shown as its stage; the timer
  stopping; the moving bar drawn, moving, and routed through the real delegate; and every step yt-dlp
  can report either has words or is one of six stated quick steps (`tests/ui/test_processing_progress.py`)
- [x] End to end, a real MP3 download through the composed application reports `ExtractAudio` with a
  position reaching 1.0 (`tests/integration/test_end_to_end.py`). **Also run on `STARBASE`**
  (Windows, ffmpeg 8.1.2): the new and changed test files and this test, 166 passed
- [x] Mutations, each failing those tests: hook never installed (1); no kill on raise (1); every
  command treated as a step (2); only `out_time_us` read (2); no cancellation check (1); no throttle
  (1); zero without a length (3); the download's fraction while processing (3); never busy (2); no
  timer from the status change (2); a step erasing the size (1); the time not restarted per step
  (2); no step words (3); the delegate never painting the moving bar (1). A second timer start on
  each drawn step **survived** and was removed as redundant
- [ ] Seen by a person: a long conversion on the installed build shows the step, its progress or the
  moving bar, and the time so far

---

---

### T-342 — Add URLs and Preferences opened with their title bars above a laptop's screen

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-342.md)); its last criterion is a real Windows display at 125%, which the waived walk would have covered (`T-328`, 2026-09-16). Phase 4.5. *(Was In Review:)* reported 2026-09-15 by the maintainer from a friend's Windows laptop
(1920x1200 at 125%, the maintainer's figures): *Add URLs* and *Preferences* opened with the title bar
above the top of the screen, so the window could not be moved and no URL could be typed. Moves the
`0.1.0` candidate.
**Owner:** Implementer
**Priority:** High — the first screen a user needs could not be used on an ordinary laptop
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `T-242` and `T222-R1` (height bounds for *Preferences* and *Options*);
`T-310` (`FormatDialog.sizeHint` bounded by the screen); `NFR-005`
**Affected surfaces:** new `ui/screen_fit.py`; `ui/add_dialog.py`; `app.present`

#### What was found, measured on `STARBASE` (Windows 10, 1600x900)

- **Qt does not keep a dialog's frame on the screen.** With `QT_SCALE_FACTOR=1.25` (a 1280x720
  logical screen) *Add URLs* was placed with its frame at y = -241.
- **Add URLs grew after it was shown**, at a true 100% as well: opened at 600 pixels (Qt's cap of two
  thirds of the screen for a window never resized), centred for that, then grown to 788, its layout's
  height. With its list asking for 16 rows it grew to 1364 on the 900-high screen.
- **Nothing bounded where any dialog lands**; *Preferences* and *Options* bounded only their height.

#### What changed

- `ui/screen_fit.py`: `DialogsOnScreen`, installed by `app.present` and owned by the main window,
  fits every top-level `QDialog` when it is shown, once more after the event loop turns, and on each
  resize while visible: a maximum size of the working area less the frame, then a move so the whole
  frame, title bar first, is inside. A fit that changed something looks again, at most four times per
  showing. `fitted_geometry` is the pure rule.
- `AddUrlDialog.sizeHint` is bounded to the working area less 48 pixels (`bounded_to_screen`), and the
  dialog is given that size before it is shown.

#### Measured on `STARBASE`, 100%, *Add URLs* asking for 16 rows

| Build | Frame | Inside the screen |
|---|---|---|
| Unchanged | 1395 tall from y = 110 | no |
| Rule only | 1395 tall from y = 0 | no |
| Bounded hint and rule, no size before showing | 1395 tall | no |
| All three | 900 tall from y = 0 | **yes** |

At the real row count *Add URLs* and *Preferences* fit the 900-high screen in every build. **With
`QT_SCALE_FACTOR` at 1.25, 1.5 and 2.0 the results did not agree with a true 100% screen**: Windows
refused geometries (*Unable to set geometry*) and *Add URLs* stayed partly outside at 1.25 and 1.5
with the change. That emulation is not a real scaled display, so it is recorded rather than trusted
either way.

#### Acceptance criteria

- [x] `fitted_geometry`: above the top, too tall, past each other edge, already inside (unchanged),
  and a working area shorter than the frame (the top wins) (`tests/ui/test_screen_fit.py`)
- [x] Installed rule, offscreen: a dialog shown above and taller than the screen ends inside; one
  that grows after showing is fitted again; the rule leaves with its owner; installing twice installs
  one
- [x] `present()` installs it and a dialog of the real window is fitted
  (`tests/integration/test_composition.py`)
- [x] *Add URLs* with 40 wanted rows: its hint and its size are within the working area less 48, and it
  has a size of its own before showing
- [x] Mutations, each failing those tests: no top clamp (4); no shrink (1); no refit on resize (1); no
  fit on show (2); the hint unbounded (1); not installed by `present` (1); owned by the application
  (4); no size before showing (1)
- [ ] **Seen on a real Windows display at 125%**: *Add URLs* and *Preferences* open with the title
  bar on screen and can be moved (the friend's laptop, or a Windows machine set to 125%)

#### 2026-09-15 — the `yt-dlp` canary failed two of these tests

The canary runs the suite in **one process**, and there two tests failed at `48cf076`: a dialog that
grew after showing was not fitted again, and the rule appeared to outlive its owner. **Reproduced
locally** by running `test_composition.py` then `test_screen_fit.py` in one process. A composition
window left alive by an earlier test kept its rule installed, and **both rules counted fits on one
dynamic property**, so a dialog's budget of `MAX_PASSES` was spent twice as fast. In the application
there is one window and one rule, so the shared counter did not show there; it was still wrong.

Corrected: each rule keeps its own count (a property named for that rule). The ownership test now
asserts the rule object is destroyed with its owner, instead of watching a dialog that other live
rules may still move. A new test installs two rules and grows a dialog after showing; with a shared
counter it fails. The two files together in one process: 97 passed.

---

---

### T-340 — A failed download's log could not be opened from anywhere in the application

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-340.md)); its last criterion is a person seeing *Diagnostics…* on both platforms, which the §11 walk would have covered. The maintainer waived that walk on 2026-09-16 and assigned what it would have found to Phase 4.5 (`T-328`). *(Was Blocked:)* on its last criterion, a person seeing it on both platforms (`T328-R4`'s
walk). The implementation was approved by review on 2026-09-14
([record](reviews/T-340.md#2026-09-14--diagnostics-implementation-review)). Found 2026-09-14 while
preparing `T-328`'s §11 acceptance sheet; the maintainer chose to fix it in `0.1.0`.
**Owner:** Implementer
**Priority:** High — `REQ-019` is an MVP requirement and §11 criterion 6 names a copyable log
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `REQ-019`; `REQUIREMENTS.md` §11 criterion 6; `UX-005` §2 and §4 and their
2026-09-14 amendments; `T-084` (the log view); `T-135` (what the `⋯` holds)
**Affected surfaces:** `ui/log_view.py`, `ui/main_window.py`, `ui/add_dialog.py`

#### What was wrong

`LogView` (`T-084`) was built only by `ui/job_detail.py`, and `UX-005` §2 removed the detail pane
from the window. `queue_view.py` already said so (*"nothing in the product constructs that
widget"*), and no decision moved `REQ-019` elsewhere. Every log-view test passed against a widget
no user could reach. The candidate evidence for `3c011b8` and `246dcdf` did not notice.

#### What changed

- **`DiagnosticsDialog`** in `ui/log_view.py`: the existing `LogView` in a non-modal window titled
  *Diagnostics for* the job's title or URL, with Close. Escape closes it. Copy still copies the
  whole file (`T084-R2`).
- **The queue row's menus** offer *Diagnostics…* below the verbs, on the `⋯` and on the keyboard and
  right-click route.
- **A failed line in the Add dialog** offers it below *Read this URL again*. An unsupported URL
  fails there and never becomes a queue row, so this is the entry §11 criterion 6 is walked through.
- **Offered only when the job has logged something** (`has_job_log`). The manager creates a job's
  log file as its session opens, so a check for the file alone would offer it on every job that ever
  ran.

#### Acceptance criteria

- [x] A queue row whose job logged something offers *Diagnostics…* on the `⋯`, including when
  nothing was dropped, and on the context route; the window shows the file and Copy copies all of it
  (`tests/ui/test_row_verb_wiring.py`)
- [x] No entry for a job with no log file or an empty one (same file)
- [x] A failed Add dialog line, logged through the worker's real route and the parent's per-job
  handler, offers it and the window shows the extractor's message; a silent failure and a line that
  read offer nothing (`tests/ui/test_add_dialog.py`)
- [x] The window is non-modal, titled for its job, focused on the text, and closes from Escape and
  from Close (`tests/ui/test_log_view.py`)
- [x] Mutations, each run against the new tests: no queue entry (2 fail); the `⋯` still returning
  nothing when no verb was dropped (1); file existence instead of size (2); no Add dialog entry
  (1); the Add dialog entry without the log check (1); a modal window (1)
- [ ] Seen by a person on both platforms, as part of the §11 criterion 6 walk (`T-328`)

---
