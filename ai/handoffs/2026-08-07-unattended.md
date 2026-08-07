# Handoff — the unattended session, 2026-08-07

**From:** Claude Code (Implementer, and Planner for the pack)
**To:** Sean Kottman (Maintainer), and Codex (Reviewer) for `T-181` and `T-176`
**Authorised:** the maintainer chose three items and standing commit/push for this session's work.
**Base:** `dd607dc` — the last commit before this session's unattended half.
**Branch:** `main`. Serial mode, no wave.

---

## What was done

| Item | State |
|---|---|
| **`T-181`** — the queue is stopped until Start | **Complete, awaiting review.** Source, tests, spec and task record |
| **`T-176`** — the withdrawn History prose | **Complete, awaiting review.** Source and test prose only |
| **The §10 ruling pack** | `ai/handoffs/2026-08-07-ux-spec-ruling-pack.md` — 25 questions, options, costs, a recommendation each |
| **The board's "startable" claim** | Corrected: `1 of 9 buildable today`, and why |

---

## `T-181`, and the three things it turned up

The gate now starts closed, the pair is `start_queue()`/`stop_queue()` with a `queue_running`
signal, the toolbar control reads *Start queue* / *Stop queue*, and the status bar carries
*Queue stopped — press Start to download*. `UX-001`'s drain is untouched.

**1. A criterion in the task entry could not be met as written, and the entry was wrong to ask.**
It required "a test that fails if the gate check is removed from the retry path". There is no such
single check: `_start_when_free` and `start()` both carry the gate and each catches what the other
releases. **All three mutants were run** — removing either alone leaves the five gate tests green;
removing both fails the retry test. Neither guard is individually load-bearing. The test's docstring
says exactly this, because my first version claimed the single-point mutation worked and the
measurement disproved it.

**2. `active_job_ids()` cannot express "nothing started".** It counts *waiting* jobs as active by
design (`T078-R1`), so a correctly parked job makes it non-empty. Two of my tests used it and failed
against correct code. They now assert on `_sessions` and the durable status.

**3. A retried *probe* is exempt from the gate, correctly.** A `QUEUED` job's session is a probe
(`ARC-004`), so its automatic retry is a probe, and probes are never gated. My first retry test
started from `QUEUED`, watched the retry run, and would have reported a correct exemption as a
defect. It starts from `READY` now.

**Not built:** `docs/UX_SPEC.md` §2 item 7's *Held* row. The stopped state is said once, at queue
level; writing it into per-row status text would put a queue-level fact in as many places as there
are jobs, which is what `UX-001` exists to prevent. §2.1 records the choice and flags that clause as
worth re-deciding — it is marked `[T]`, so nothing currently lists it as open.

**Test-harness note for the reviewer.** The `manager` fixture in `tests/integration/test_manager.py`
now presses Start by default and takes `running=False` for the tests that are about the gate. That
is a harness convenience deliberately opposite to the product's default, and
`test_a_manager_starts_stopped_and_runs_nothing_until_it_is_started` builds a manager directly so
the shipped default is asserted by something the fixture cannot mask. 91 direct constructions across
the suite gained a `start_queue()` line; every one is mechanical.

## `T-176`

Semantic classification, not a replacement pass. Corrected where a live contract claimed the
surface still exists — `store.clear_completed` ("History is not touched"), `models.py`'s
`HistoryEntry` paragraph, `grouping.py`'s "both tabs", `app.py`'s history-view argument,
`presets.py` and `format_text.py`'s `REQ-026` boundary, `errors.py`'s "persisted history", and
three test comments about the ledger. Left alone where the prose was already past tense or is
historical rationale that still explains a live invariant — `repositories.py` was already correct,
`theme.py` and most of `main_window.py` are parenthetical history.

**What I did not do:** an exhaustive audit of every one of the 63 matches. I took the ones that
state a current contract and the ones `T175-R1` named. A reviewer wanting the full sweep should
treat this as the first pass rather than the last.

---

## Checks

| Check | Result |
|---|---|
| Full suite, `--ignore=tests/network` | **2196 passed, 11 skipped** in 4m58s |
| `ruff check .` / `ruff format --check .` | pass / all files formatted |
| `mypy src` / `mypy --platform win32 src` | Success, 44 source files each |
| Task placement | 14 passed |
| `T-181` gate tests | 5 passed |
| Mutants (gate) | `_start_when_free` alone: 5 pass · `start()` alone: 1 fail · **both: 2 fail** |
| CI on `76fe48d` | green, all jobs (run `31191147925`) |

---

## A process failure worth recording

Reverting the second gate mutant with `git checkout -- src/.../manager.py` **discarded every
uncommitted change in that file** — the whole `T-181` implementation — and it had to be reapplied
from the session's own record. The earlier `T168-R1` mutation was safe because that file's work was
already committed; this one was not, and I did not check before reusing the idiom.

**The rule I would write down:** revert a mutation by inverting the exact string it introduced, or
mutate a copy. `git checkout` is for files whose work is committed, and "is this file clean?" is a
question worth asking every time rather than remembering the answer from last time.

Nothing was lost permanently and no committed state was touched. It cost one reapplication.

---

## Also worth your attention

**Two full test suites ran concurrently for several minutes** before I noticed and killed both —
`AGENTS.md` §9 warns that the integration tests which spawn worker processes contend, and one of
the two showed a failure at 3% that did not reproduce in the clean run. Treat any single failing
run in this session's scratch output as suspect unless it reproduced afterwards.

**`T-182` is still unruled**, and it is the item I would put in front of you next: it blocks part of
Phase 4.5, it needs no implementer, and six option families are waiting on it.

---

## Suite result, and the hour it cost

**2196 passed, 11 skipped, in 4 minutes 58 seconds**, on a machine with nothing else running.

**Getting that number took about an hour longer than the run does, and the reason is worth
writing down.** Two things compounded:

1. **`pkill -f "pytest tests -q"` matched its own parent shell**, because the pattern appeared as
   an argument on that shell's own command line. It killed the compound command it was part of and
   left the pytest child orphaned and running. Kill by pid, or use a pattern that cannot match the
   killing command.
2. **Orphans made the suite look broken.** A manager run crawled to 34 tests in 45 minutes and I
   started diagnosing a hang in the code. On a clean machine the same file is **141 passed in
   107 seconds**. `AGENTS.md` §9 says the integration tests contend; what it does not say, and now
   might, is that the symptom is *slowness that looks like a defect* rather than a failure.

**One real defect did hide in there, though, and it is `UX-006`'s:** two embedded subprocess
scripts in `test_manager.py` construct a manager and wait for a worker, and a stopped queue never
spawns one, so the parent waited forever. `tests/integration/test_end_to_end.py`'s
`DOWNLOAD_AND_WAIT` and `tests/network/test_real_download.py` had the same shape. All four now press
Start. **An AST-based sweep cannot see inside a string literal**, and that is exactly where these
lived.
