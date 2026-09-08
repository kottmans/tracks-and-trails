# PROMPTS.md — Tracks & Trails

**Purpose:** Reusable prompts for starting common AI-assisted tasks in this repository.
Supporting workflow material, not the product's introduction.
**Authority:** **None.** Convenience templates only.
**Owner:** Documentation Maintainer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-09-08
**Update when:** A repeated workflow needs a template, or completion-reporting requirements change.

> These prompts are convenience templates only. `AGENTS.md` and the authoritative project
> documents take precedence if wording conflicts. **No project rule may exist only here.**

---

## Implementation task

Unfinished records are in `docs/project/TASKS.md`; retrieve closed-task history
by ID from `docs/project/COMPLETED_TASKS.md` when relevant. At closure, the
task/status owner transfers the full record in the same update, with no stub
left in TASKS. During a parallel wave, workers propose this transfer to the
coordinator rather than editing either shared file.

```text
Act as the Implementer for Tracks & Trails.

Read AGENTS.md, then the T-### entry in docs/project/TASKS.md, then docs/project/STATUS.md.
Read only the requirement/decision IDs, architecture sections, source paths, and tests
that the task entry links to. Do not read the repository front-to-back.

Task: T-###
Review base: <commit or bounded uncommitted snapshot>

Implement exactly the task's scope. Do not touch its "Out of scope" list, do not refactor
adjacent code, and do not implement future-phase work. If you find an adjacent problem,
propose a task rather than fixing it inline.

Respect the layering rules in AGENTS.md §7: core/ and downloader/worker.py must not import
Qt; ui/ must not import yt_dlp.

Add or update tests for every behavior change. Run the required checks for this change class
per docs/project/TESTING.md §3.

Do not commit or push. Do not add AI attribution anywhere.

Finish with the AGENTS.md §11 report, including the actual results of every check you ran and
the review base/head for the reviewer.
```

## Review task

```text
Act as the Reviewer for Tracks & Trails. You did not write this code; do not assume the
implementer's reasoning is correct.

Scope — base: <commit>  head: <commit>
Task(s): T-###

Review the diff against:
- the task's acceptance criteria and out-of-scope list
- docs/project/REQUIREMENTS.md (the specific REQ/NFR IDs the task cites)
- accepted entries in docs/project/DECISIONS.md
- docs/project/ARCHITECTURE.md, especially the §4 layering rules and the §7 error taxonomy
- docs/project/TESTING.md §3 and §7

Apply the review policy and standing risk focus in docs/project/TESTING.md §14: process lifecycle and orphaned workers,
the IPC boundary, filesystem path safety, log redaction, migrations and crash recovery,
Qt threading, and REQ-EXCL boundaries.

Inspect the code and the evidence. Do not accept an explanation in place of a check —
re-run the checks yourself.

Do not modify source unless explicitly asked to fix findings.

Report: verdict, findings ordered by severity with file:line, why each matters, recommended
correction, checks run and their real results, unresolved risks, and a merge readiness call.
Record the review in docs/project/REVIEWS.md, then disposition every finding under AGENTS.md §10's
task-creation threshold: a Note requests no change; a small requested change is a Low
finding, not a Note; a minor actionable finding rides the current task's completion sync or
the next existing task; and a new TASKS.md entry is for independently substantial work only.
Accepted Risk and Won't Fix need the maintainer's explicit no-action decision.
In a parallel wave, write docs/project/reviews/T-###.md on the task branch instead, name the exact
implementation head you approved, and leave the index and task routing to the coordinator.
```

## Planning task

```text
Act as the Planner for Tracks & Trails.

Read AGENTS.md, docs/project/STATUS.md, docs/project/IMPLEMENTATION_PLAN.md, and the relevant parts of
docs/project/REQUIREMENTS.md, docs/project/ARCHITECTURE.md, and docs/project/DECISIONS.md.

Task: <planning problem>

Update only planning and coordination documents. Do not modify source, tests, or build config.

Keep the boundaries: requirements describe user-visible intent; architecture describes
technical design; decisions preserve rationale and status; the plan sequences phases; tasks
are concrete, testable, and route the worker to its exact context.

New tasks must include scope, observable acceptance criteria, an out-of-scope list, relevant
context IDs, affected surfaces, risk, and required checks.

Record a DECISIONS.md entry only for a durable choice or a real trade-off — not as a
completion note.

Report conflicts between documents rather than silently resolving them.
```

## Opening a parallel wave (coordinator)

```text
Act as the Coordinator / Integrator for Tracks & Trails. Read AGENTS.md §9 first.

Candidate tasks: T-###, T-###
Integration branch: main

For each candidate, check the six qualification conditions in AGENTS.md §9 and say which
fail. Do not open the wave for a task that fails one — sequence it instead, or propose the
shared piece as its own task first.

Then propose, and wait for my approval before creating anything:
- wave ID PW-###, and the exact main commit used as the common base
- per task: branch name, exclusive write set, read-only shared surfaces, runtime allocation
  (PYTHONPATH/venv, process_tree slot, temp and DB paths), required checks, reviewer,
  review-record path, integration order

Do not implement any worker's task yourself. Do not create branches or worktrees, or write
docs/project/TASKS.md and docs/project/STATUS.md, until I authorize the wave.
```

## Parallel worker

```text
Act as the Implementer for Tracks & Trails, as a worker in a parallel wave.
Read AGENTS.md §9, then the T-### entry in docs/project/TASKS.md.

Task: T-###          Wave: PW-###
Branch: task/T-###-<slug>, already created from main@<sha> — stay on it
Worktree: <path> — work only here; the shared checkout belongs to another agent
Exclusive write set: <paths>
Read-only shared surfaces: <paths>
Runtime: run tests as
  PYTHONPATH=$PWD/src <primary-checkout>/.venv/bin/python -m pytest <args>
  and verify once that tracks_and_trails resolves inside this worktree

Do not switch, merge, rebase, or delete branches. Do not edit another worker's paths,
docs/project/TASKS.md, docs/project/STATUS.md, or any review record. If the task turns out to need a file outside
your write set, stop that part and report the scope expansion instead of editing it.

Finish with the AGENTS.md §11 report including the worker items (9–12): wave, branch, exact
base/head, runtime resources used, write-set expansions needed, and proposed — not applied —
TASKS.md/STATUS.md updates.
```

## Debugging a download failure

```text
Act as the Implementer for Tracks & Trails, debugging a download failure.

Symptom: <what the user saw>
URL / site: <if shareable>
yt-dlp version reported by the app: <version>
Job log: <path or paste>

First determine which of these it is, and say so explicitly before proposing any fix:
(a) yt-dlp itself fails on this URL — reproduce with the yt-dlp CLI at the same version.
    If so, this is upstream (C-002); the fix path is OPS-002, not project code.
(b) our options-building or info_dict projection is wrong — downloader/ytdlp_adapter.py.
(c) our process, IPC, state machine, or persistence handling is wrong.
(d) the failure is correct but classified or presented badly — core/errors.py,
    ARCHITECTURE.md §7.

Do not add a retry or a workaround to paper over an unclassified failure, and never add a
circumvention path (SEC-001, REQ-EXCL).

If it is ours, add a regression test — a recorded info_dict fixture where that captures it.
```

## Adding or updating an info_dict fixture

```text
Act as the Implementer for Tracks & Trails.

Capture a yt-dlp info_dict for <URL/site> and add it to tests/fixtures/infodicts/.

Record the yt-dlp version and capture date alongside the fixture. Strip anything
user-identifying: cookies, tokens, session or auth query parameters, and personal paths.

If you are REPLACING an existing fixture, state exactly what changed in the dict shape and
why — a silently refreshed fixture hides the upstream breakage the fixture exists to catch
(docs/project/TESTING.md §5). If the shape changed, ytdlp_adapter.py likely needs a corresponding
change, and that is a separate task.
```

## Cold-start orientation check

```text
You have no prior context on this repository. Do not edit anything.

Read only what you need to answer, and report:
1. What is this project, what phase is it in, and what is the immediate next task?
2. Where is the authoritative source for requirements, architecture, decisions, tasks,
   status, reviews, and testing policy?
3. For the active task: scope, acceptance criteria, relevant context IDs, out-of-scope.
4. As an Implementer, which files may you and may you not modify?
5. What checks are required for a source change, and what is the release gate?
6. What are the non-negotiable safety, secret-handling, destructive-action, and Git rules?
7. What are the current blockers, assumptions, and unverified areas?
8. How many files did you have to read, and was anything contradictory or missing?

Question 8 is the point: if answering required reading the whole repository or guessing
between conflicting documents, the documentation system has a defect. Say so.
```

## Release verification

```text
Act as the Release Manager for Tracks & Trails.

Release candidate: <version / tag / commit>

Work through the docs/project/TESTING.md §8 release gate item by item, on Linux AND Windows. Do not
mark an item passed without the actual evidence.

Also verify: version numbers consistent across sources, CHANGELOG current, the pinned yt-dlp
baseline recorded (OPS-002), Qt dynamically linked (NFR-009, LIC-001), third-party license
texts present, and no secrets or personal paths in the artifact.

Record the verdict and any blockers in docs/project/REVIEWS.md.
Do not tag, commit, push, or publish unless explicitly instructed.
```

## Review entry template

Optional wording; [TESTING §14](TESTING.md#14-review-policy) governs review.

```markdown
## YYYY-MM-DD — <Scope title>

**Reviewer:** <actual person/tool; independent of implementer>
**Task(s):** T-###
**Base:** <commit>  **Head:** <commit or bounded diff>
**Platforms verified:** <actual scope>
**Verdict:** Approved | Approved with follow-ups | Changes requested | Blocked

### Findings

| ID | Severity | Blocks approval | Finding and evidence | Disposition/status |
|---|---|---|---|---|

### Checks run

| Check and scope | Actual result |
|---|---|

### Readiness

<Remaining risks, unverified areas and approval/merge limits.>
```
