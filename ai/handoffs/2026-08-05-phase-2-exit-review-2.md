# Phase 2 exit review — re-submission, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**What is asked:** criterion 6(a), the independent phase exit review. **It is the only criterion
still open.**
**Candidate head:** `9aa3a43` and this commit. **CI evidence:** run `31051896815` on `165b6e4`,
all five jobs green.
**Supersedes:** `ai/handoffs/2026-08-05-phase-2-exit-review.md`, which you reviewed and rejected.
That document is kept as submitted with a superseded note; rewriting the claims you judged would
erase the judgement.

---

## Your five verdicts, and where each one landed

| Id | State | Where |
|---|---|---|
| `P2EXIT-R11` | **Resolved** — you confirmed at `83f3aa2` | Stage precedence gated by whether the stage can still be live in the current status |
| `P2EXIT-R13` | **Resolved** — you confirmed at `83f3aa2`, including repeated nonempty refreshes | Focus placement on first rows only, in the visible view |
| `T161-R1` | **Resolved** — you confirmed at `376407f`; both constant-answer mutations fail | Parent-only probing, request-count test, real loopback boundary |
| `P2EXIT-R14` | **Resolved** — you confirmed at `e94b412` | Five sweeps. The count you flagged as non-blocking is removed rather than corrected, at `165b6e4` |
| `P2EXIT-R12` | **Answered, and yours to close** | The 40-row run is a pass. See below |

## `P2EXIT-R12` — the row 3.15 observation you asked for

Your finding was that a **fix is not an observation**, and that `T-153`'s regression proved an
address was *selected* rather than a picture *shown*. That is now observed.

**Three checklist runs, all recorded, read as a sequence rather than a repetition:**

| Run | Result | Evidence |
|---|---|---|
| First | **Eleven defects**, none reported by any gate, against 2153 green tests | `ai/evidence/2026-08-05-criterion-8-checklist-run.md` |
| Second | **39 of 41** — rows 2.7 and 3.15 failed | `ai/evidence/2026-08-05-criterion-8-second-run.md` |
| Third | **40 of 40, pass**, on `kirk`, Fedora | `ai/evidence/2026-08-05-criterion-8-third-run.md` |

**The count changed because row 2.7 was removed, not because a failure was rewritten.** Your
disposition in `T161-R1` is applied exactly: the row is gone from the checklist, `T-160` stays
Phase 3, the property the row asked for moved to `T-160`'s acceptance evidence **unweakened**, and
the historical 39/41 result is **not recomputed** — a row removed afterwards does not retroactively
pass, and 39 of 40 would make the record flatter than the day it describes.

**Head stated as a range**, `376407f..165b6e4`, because `git diff --stat 376407f..165b6e4 -- src/
tests/` is empty — no source or test file differs, so it is one build. Please check it rather than
take it: `P2EXIT-R8` was evidence about a head that moved.

## A maintainer ruling that changes what you are judging

**Criterion 8 rests on one platform, deliberately.** Asked directly, the maintainer ruled on
2026-08-05: *"I'm okay with criterion 8 resting on one platform (linux) for now."*

I raised the one-platform limit in the last submission as something you might reject. It is now a
**ruling** rather than a gap, recorded in the plan, `STATUS.md` and the evidence file — because an
implementer who **could not** get Windows evidence and one who was **told it was not required**
look identical in a record that does not say which.

**The residual is real and is not argued away.** CI runs the suite on Windows and `windows desktop`
is green; what is unevidenced is a *person looking at the window* there. `T-134`'s hover defect and
`T-149`'s missing `:checked` state are exactly the class of thing only that catches.

## What I expect you to push on

**Four of your five findings were mine, and three were one shape** — a claim stated over the top of
evidence I had already written down. `T-162` filed as a known defect while criterion 1 was called
met; a checklist record listing its own failures underneath a *pass*; one occurrence updated with
its siblings left behind, five times running. **Assume that shape is still present somewhere in
this submission.** I have swept for it by claim-shape rather than by the words of my last fix, which
is what finally cleared `P2EXIT-R14`, but I found the last three of those only after you named them.

**Two regressions are guarded on every platform and reproduced on none.** `offscreen` runs at DPR 1
and never grows a horizontal scrollbar, so `T-154` and `T-151`'s tests cannot fail against their
defects. Disclosed in their docstrings.

**`T-152` needed two rounds and `T-140` needed two colour corrections**, both because the first fix
addressed a mechanism next to the defect rather than the defect. Worth suspecting the same of
anything else I corrected this round.

## Verification

| Check | Result |
|---|---|
| `tests/ui` + `tests/unit` | **1884 passed, 11 skipped** |
| `tests/integration` | **307 passed** |
| `ruff check .` / `ruff format --check .` | Pass, 167 files |
| `mypy` | Success, 107 source files |
| CI on the candidate | **Green, all five jobs.** Run `31051896815` on `165b6e4`: `STARBASE coverage`, `linux`, `frozen linux`, `windows desktop`, `frozen windows` |
| Built-window checklist | **40 of 40**, `kirk`, Fedora |
| Soak | **60 of 60**, `Spock`, `ef21e34`, P = 0.042 against the 2-in-39 baseline |

**CI was dispatched, not inherited.** The prior push-triggered run was on `376407f`; everything
after it is records, correctly skipped by `paths-ignore`, so the candidate had no run of its own.
**This submission is prose-ahead of that run** by the same rule — `9aa3a43` and this commit change
no source. If you would rather judge a run whose head *is* the head, say so and I will dispatch one;
it costs time and no quota.

## The criteria, as claimed

| # | Criterion | Claimed |
|---|---|---|
| 1 | Three concurrent downloads, independent progress, UI interactive | **Met** — `P2EXIT-R11` corrected the regression you found |
| 2 | Hard kill mid-queue restores state | **Met** |
| 3 | Concurrency limit exact; lowering and pausing drain | **Met** |
| 4 | Second launch refuses in favour of the running instance | **Met** |
| 5 | No worker outlives exit, both platforms | **Met** — `windows desktop` green on the candidate |
| 6 | Reviewed and signed off | **Not met — this document is the request.** (b) the soak is met |
| 7 | A user can actually start a queue | **Met** |
| 8 | The window matches the features behind it | **Met on the maintainer's evidence**, with the one-platform ruling above |

**13 of 13 deliverables approved.**

## Phase 3 is filed, not deferred quietly

Ten findings from using the application, Phase 3 by the closed-list rule: `T-146`, `T-150`,
`T-156`, `T-158`, `T-159`, `T-160`, `T-163`, `T-164` (ruled, ready to build), `T-166`, `T-167`.
`T-161` and `T-162` were reclassified **Phase 2** by your `R12` and `R11` and are fixed.

**If you judge any of the ten to be accepted Phase 2 work rather than new scope, say so.** That edge
is what keeps criterion 8 falsifiable, and it has moved six times already — five by maintainer
ruling, once by yours.
