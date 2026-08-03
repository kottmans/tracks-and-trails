# Review handoff — two CI corrections and the Phase 2 roadmap rebuild

You are the Reviewer (`AGENTS.md` §3). This is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Review boundary:** `2ec9c45..7202a5d`

| Commit | What |
|---|---|
| `6c38d5f` | the retry test's race, and three defects in `OPS-009`'s workflow implementation |
| `5ff0ccf` | `T-119` merged into `T-118`'s correction (`TASKS.md`) |
| `b78e8dd` | what the desktop runner found in `T-118`, recorded not fixed |
| `7202a5d` | Phase 2's roadmap rebuilt against the repository |

**No task is claimed complete by this batch.** It corrects two red gates and repairs four
coordination documents. `T-118` remains in review and is untouched as source.

---

## 1. `test_the_attempt_count_is_bounded_and_the_last_error_survives` was racing a spawn

**Test-only change; `T-083`'s implementation is untouched and its approval is not in question.**

The `windows desktop` job failed it in runs `30822454998` and `30823595744` — both times
`assert <JobStatus.PROBING> is <JobStatus.FAILED>`, with `attempts=3`, `error_kind=NETWORK` and
`error_message='failed as network'` already stored.

**`attempts` is incremented by the retry that *starts* an attempt** (`_perform_due_retries`,
`manager.py:2379`), so `attempts >= AUTOMATIC_RETRY_LIMIT` becomes true a whole session before that
session reports. The test then allowed a fixed **1.0 s** for the spawn, the child, the `Failed`
message and the persist. It now waits for the count **and** the settled `FAILED` from one snapshot,
and derives the subsequent hold from the backoff actually in force rather than a literal.

**Where the ~1.07 s figure comes from — the failing row, not a guess.** `created_at`
`14:30:40.039Z` and the final `started_at` `14:30:43.582Z` are 3.543 s apart, covering three
completed attempts and three retry gaps measured at 0.114 s. Locally the same operation traces at
0.246 s per attempt.

### Evidence

| Check | Result |
|---|---|
| Corrected test, ordinary run | passes, 2.2 s |
| Corrected test vs. a child whose attempt costs 1.4 s | **passes** — the same construction reproduced `PROBING is FAILED` on Linux before the change |
| Mutation: `attempts >= LIMIT` → `>= LIMIT + 1` | **killed** — `IndexError` from `RETRY_BACKOFF_SECONDS[3]`, which is the failure the derived-constant comment at `manager.py:109-113` predicts. It is a kill, but by a crash rather than by the assertion |
| Mutation: `_schedule_automatic_retry` returns unconditionally | **killed** by the new wait's own message, `"the automatic attempts never reached the bound and settled"` (120 s) |
| Source after each mutation | `sha256` byte-identical, checked |
| `tests/integration/test_manager.py` | 138 passed |
| Exact-head hosted run `30826638984`, `windows desktop` full suite | **1929 passed, 0 failed** |

### The thing I would check hardest

**Whether the correction weakened the gate rather than fixing it.** The old wait would also have
caught a bound that did not hold, by observing `attempts == 4` after a fixed delay; the new one
waits for `FAILED` first, so an implementation that failed and *then* retried a fourth time is
caught by the hold that follows rather than by the wait itself. I believe the hold is sufficient —
20× the 0.05 s backoff `quick_backoff` installs — and the second mutation shows the wait is not
vacuous, but this is the assertion I would try to break.

**Also worth your scepticism: I ruled out `T-116`.** My reasoning is that `entering()` recomputes
`_ENTRY_STATUS.get(current.status)` when the write runs (`manager.py:1134`), `FAILED` is not a key,
so a stale start declines into `_abandon_start` and no `PROBING` can follow a terminal state; and
the observed `FAILED → QUEUED` gap is the backoff rather than a wait for `_release`. If that is
wrong, an approved task has a defect and this correction hid it behind a longer wait.

---

## 2. `OPS-009`'s workflow implementation had three defects

**The ruling is not in question** — the Windows frozen leg belongs on `STARBASE`. Its
implementation did not honour it.

1. **`actions/setup-python@v7` stayed in the job after it moved to a self-hosted machine.** On
   `STARBASE` the action ran the real installer: it deleted the tool-cache interpreter and then
   failed the reinstall (`30823595744`, *"Error happened during Python installation"*). **The
   desktop job's own comment records this exact incident from the first time it happened**
   (`ci.yml:308-321`) — a machine somebody uses must not provision itself as a side effect of a
   build. The leg now checks the machine's Python, as that job does.
2. **`matrix.os` was replaced and three references were left behind.** Both frozen legs uploaded to
   `frozen-evidence-`, so the matrix's two artifacts became one — verified against the run's
   artifact list, which shows `frozen-evidence-windows-latest` and `frozen-evidence-ubuntu-latest`
   before, and a single `frozen-evidence-` after.
3. The artifact-size report recorded an empty `platform:` for the same reason.

### Evidence

Run `30826638984`, both branches of the new condition exercised in one run:

| Leg | `setup-python` | `Check the machine's Python` | Build | Smoke |
|---|---|---|---|---|
| `frozen ubuntu-latest` (hosted) | success | skipped | success | success |
| `frozen windows` (`STARBASE`) | **skipped** | **success** | success | success |

`frozen windows` passed in 5m18s — **the first frozen build that machine has ever completed**; both
prior attempts died in `setup-python` before reaching PyInstaller.

### The thing I would check hardest

**`runner.environment` is the only load-bearing new expression.** If it were ever absent or empty,
both branches invert and the hosted leg would silently stop installing its pinned Python. The
failure would be loud rather than silent — the check step asserts 3.14 and would fail there — but I
chose it over `matrix.name` deliberately, so that the job adapts if the runner moves again, and
that is a judgement you may disagree with.

---

## 3. Four coordination documents were carrying claims that had stopped being true

Recorded here because these are current-truth defects, not tidying:

- **`STATUS.md`** said `T-115` was in review (approved 2026-08-02), that `STARBASE` was offline (it
  returned 2026-08-03), and that `T-116`/`T-117`/`T-120` were in review (all approved).
- **`IMPLEMENTATION_PLAN.md`** exit criterion 6 read *"Four deliverables await review: `T-100`,
  `T-086`, `T-084`, `T-082`"* — all four approved 2026-08-01. Deliverable rows 9–12 said the same,
  the status line said "nine of thirteen built", and the phase diagram coloured eight approved
  tasks amber or grey. **The plan named the UI rework nowhere at all**, despite five tasks existing
  against it since 2026-08-02.

Rebuilt from the tables rather than edited beside them. `test_task_placement.py` passes.

**What I did not do:** I have not claimed Phase 2 exits. Criterion 6 still reads **not met**, and
now says what it actually wants — an independent phase exit review, which is yours and not mine.

---

## 4. Recorded, not fixed: two teardown defects in `T-118`

Both are `shutdown()` cancelling a staged probe, which is an occupant:

- **`KeyError: no job with id …`** — `_require()` finds the id neither staged nor durable. Runs
  `30822454998` and `30826638984`.
- **`IllegalTransitionError: cannot move a job from failed to cancelled`** — `_persist`'s guard at
  `manager.py:1441` is `is_terminal(current.status)`, and **`FAILED` is not terminal here because
  retry exists**, so `_cancelled()` is computed and the state machine refuses it. Run
  `30826638984`.

**`cancel()`'s own comment already says the second cannot work** (`manager.py:1428-1433`):
*"A job awaiting an automatic retry is `FAILED`, and `FAILED` allows only `QUEUED` — so cancelling
one raises out of the state machine and this line could never run."* `T-118` created a caller that
reaches that line, through `unstage()`. So the `T118-R1` correction batch's claim that *"the
remove-versus-cancel question disappears … `ARC-004` needs no `FAILED → CANCELLED` edge"* is **false
as implemented**.

Left for `T-118`/`T-119`'s correction, which rewrites that seam. Neither reproduces on Linux; both
are teardown-only, so the tests they hang off still report as **passed** — which is why two full
CI runs went by without either being noticed.

---

## What is still red on `main`, and it is all `T-118`

**`T118-R10` has now flapped three times on one unchanged path:** 0.722 s at `253bbce` (red), a
pass at `4b0fe10`, and **0.520 s at `6c38d5f` against the test's own 0.5 s allowance** (red). The
bound is marginal rather than wrong, and the correction is required to establish one with real
headroom plus a hosted-Windows measurement taken at it.

## Evidence for this batch

`ruff check`, `ruff format --check` and **all four `mypy` gates** clean. `tests/integration/
test_manager.py` **138 passed**; `tests/unit/test_task_placement.py` **14 passed**. Four mutations
run across two batteries, all four killed, sources `sha256`-verified byte-identical after each.

**A full-suite local run was not performed for this batch** — the change is one test's wait plus
workflow YAML and prose. The exact-head hosted evidence above is `30826638984`; the coordination
commits after it are prose plus `TASKS.md`, and `ai/handoffs/**` is in `paths-ignore`.

**One incident worth knowing about.** A mutation run hit my own two-minute command timeout and left
the mutation on disk — the same trap the previous handoff records, and a `finally` does not survive
that kill either. I noticed on the next command, reverted, and confirmed the `sha256` matched
before continuing. Nothing was committed or run in that state, and it was caught by inspection
rather than by a gate.

## What is still not verified

- **The two `T-118` teardown defects are recorded, not diagnosed to a fix.** I have the mechanism
  and not a correction.
- **A real extractor.** Every probe here still replays a fixture or a localhost server.
- **The dark theme has never been on a screen.**
- **`T-092` and `T-074`** are unblocked now that `STARBASE` is back, and still open.
