# Review handoff — the criterion 8 findings, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Review base:** `965a336` — where the `T140-R3` re-review record landed
**Review head:** `405139f`, pushed. **Four commits, seven files.**

**Every open finding from the 2026-08-05 round is addressed.** `T132-R2` was resolved in the
previous pass and is context here, not a submission.

| Finding | State | Where |
|---|---|---|
| `T140-R3` | corrected — the remaining display half | `2390320` |
| `T137-R2` | corrected | `4cbebc6` |
| `T140-R5` | corrected **except `Pause all`** — see the ruling below | `57de34b`, `405139f` |
| `COORD-R22` | applied: this range is stated in full, `ai/REVIEWS.md` untouched | — |

**One thing needs a maintainer ruling before this can be called complete**, and it is stated in
§4 rather than buried.

---

## 1 · `T140-R3` — naming a format the way the editor does

`2390320`. You found the header showing `bestvideo+bestaudio/best` where its own control offers
*Best video available*. My earlier regression asserted only that the value was nonempty, so it
agreed with both — the same weakness the finding was about, one level down.

**The fix reuses `_effective_format_text`**, which has answered this for an ordinary row since
`T126-R2`, rather than formatting raw selectors beside it. Agreement between members is now judged
on the **rendered text** as well: two members can differ in a preset-owned field while sharing a
selector, and what the user is told is one line, so that line is what has to agree before the
header claims they match.

**Your suggestion closed the gap I had disclosed.** Building members with `to_request(BEST_VIDEO,
…)` makes the group's current value a name the editor offers, so re-selecting it is genuinely the
no-op the guard exists for. Asserted, with the converse — a guard that refused everything would
otherwise pass.

Mutants killed: raw selectors; dropping the same-value clause.

---

## 2 · `T137-R2` — probing a playlist's entries

`4cbebc6`, and it carries a new decision entry, **`ARC-009`**.

`admit()` schedules one session and has never chained. That was complete while the only probe in
the system was a staging probe, whose whole purpose is to stop and wait for the user. `T-137`'s
entries are durable `QUEUED` rows, so admitting them as probes *alone* would have traded one broken
promise for another: probed, then parked for ever.

**The continuation lives in the manager**, beside the outcome it follows. Composition was
considered and rejected: pause semantics, per-entry failure reporting and lane accounting are the
manager's, and `T036-R1` is what writing queue policy outside it cost. The add dialog could not
host it either — it closes on `accept()`, so the object that admitted the probes is gone before the
first one lands.

**Pause needed no special handling.** The probe half runs while paused because probes are exempt;
the continuation is an ordinary `DOWNLOAD` admission, so `_start_when_free` parks it and `resume()`
drains it. A paused queue probes a playlist's entries and starts none of them.

**The dialog admits by status, not by shape** — unprobed rows get probed — so it does not become a
second place that has to know what a playlist is.

### A submitted uncertainty, because my first regression passed against the broken version

I assumed `admit()` would refuse a staged download outright. **It does not — it parks**, and
`start()`'s `ValueError` surfaces later on drain, from a timer's thread of control. So removing the
staged guard produces a *deferred* exception, invisible to a test checking sessions and
persistence. The regression asserts the queue state instead, and both mutants now die: no
continuation, and no staged guard. Worth your independent check, because I had it wrong once.

---

## 3 · `T140-R5` — the accepted criteria `T-140` did not build

`57de34b` (keyboard) and `405139f` (verbs, removal).

**Keyboard disclosure.** `Right` opens the focused playlist, `Left` closes it. On the *list* rather
than the viewport, because key events go to the focused widget while the delegate's filter watches
the viewport for the pointer — the obvious placement would silently never fire. **Directional
rather than a toggle**: `Right` on an open group leaves it open, because a toggle makes the outcome
depend on state the user cannot see, and a screen-reader user is exactly who cannot.
`EXPANDED_ROLE` answers `None` off a group, which is the whole guard, and an ordinary row is
asserted separately so the filter cannot quietly take those keys from the list.

**Group verbs**, derived from every member rather than from one that speaks for them — a playlist
mid-run holds a completed track, a running one and fourteen queued, so no member's status is the
group's. `Retry failed` only when something failed, asserted in both directions. `Show in folder`
with no `Open`, because the entries share one folder and there is no single file.

**Count-bearing removal.** `Remove` reports the whole group in one signal so the shell can ask
*"Remove these 3 downloads from the queue?"* (`DAT-005` §4). Separate wording from history's
question, which says *from history*: removing a playlist from the queue stops downloads that have
not finished, and calling that clearing a record would understate it. Singular is written out —
"1 downloads" is the tell that a message was assembled rather than composed.

### A bug I wrote and caught, kept visible

My first cut **routed group verbs by the verb**. That is wrong: `Remove` and `Show in folder` are
ordinary row verbs too, so every row's *Remove* would have gone down the group path and asked
"Remove these N downloads?" about a single job. Routing now asks the model whether the id names a
group, and `test_an_ordinary_rows_remove_is_not_routed_as_a_group` fails against the broken
version. Flagged because the wrong version is the one a reader would naturally write.

---

## 4 · The ruling this needs: `Pause all`

**Not implemented, deliberately.** The mockup names it and `T-140`'s criteria list it. But
`UX-001` and `T-080` removed per-job pause and **deleted `JobStatus.PAUSED` outright**; pause is a
queue-level drain with no mechanism for holding one group without touching the rest of the queue.

Building it reopens an accepted decision, which `AGENTS.md` §7 makes a maintainer's call, and
`REQ-017` in Phase 3 is the named reopening condition. Drawing the button with nothing behind it
would be the `T-016` failure `row_verbs`' own docstring warns about.

Three ways out, none of which an implementer should pick:

1. `Pause all` waits for `REQ-017`, and `T-140`'s criterion is amended to say so.
2. `UX-005` row 9 drops the verb.
3. `UX-001` is reopened now to add a group hold.

`group_verbs()` documents the absence and why, so the omission is not silent in source either.

---

## Verification

| Check | Result |
|---|---|
| `tests/ui` + `tests/unit` | **1854 passed, 11 skipped** |
| `tests/integration` | **306 passed** |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 162 files already formatted |
| `mypy` | Success, 107 source files |

Mutants killed, by finding: raw selectors and the same-value clause (`T140-R3`); the probe
continuation and the staged guard (`T137-R2`); the event filter, unconditional `Retry failed`, and
retrying every member (`T140-R5`).

## The whole range, per `COORD-R22`

| Commit | Files |
|---|---|
| `2390320` | `ui/queue_view.py`, `tests/ui/test_queue_view.py` |
| `4cbebc6` | `downloader/manager.py`, `ui/add_dialog.py`, `tests/integration/test_manager.py`, `ai/DECISIONS.md` (**`ARC-009`**) |
| `57de34b` | `ui/queue_view.py`, `tests/ui/test_queue_view.py` |
| `405139f` | `ui/queue_view.py`, `ui/row_verbs.py`, `ui/main_window.py`, `tests/ui/test_queue_view.py`, `tests/ui/test_row_verb_wiring.py` |

`ai/REVIEWS.md`, `ai/TASKS.md` and `ai/STATUS.md` are untouched. `P2EXIT-R10`'s document repairs —
the nine/ten count, and whether `T-140` is Complete or reopened — are held for the maintainer.

`mypy` was run as `python -m mypy`: the `.venv/bin/mypy` shebang on this machine is still stale,
which you confirmed independently and which remains machine state, unfixed and unfiled.
