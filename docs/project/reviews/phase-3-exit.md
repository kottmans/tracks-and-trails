# phase-3-exit — Review record

**Purpose:** Dated review evidence and disposition history for this task or shared scope.
**Owner:** Assigned Reviewer · **Update when:** This scope is reviewed or rechecked.
**Covered tasks:** Cross-cutting scope; see the dated entries.

[Review index](../REVIEWS.md) · [Review policy](../TESTING.md#14-review-policy)

Moved from `85422bc0b086de9b18d2f809abb4d6bcebb180e4:docs/project/REVIEWS.md` on 2026-09-08.
The entries below retain their exact original bytes and relative order. Historical
path spellings, line citations and references to “above” describe that source;
the [migration manifest](../evidence/2026-09-08-review-migration.json) records the
original order and byte ranges. Shared entries are stored once; covered tasks
link to this same record. Navigation grants no approval or new review provenance.

## Recorded rounds

- [2026-08-08 — Phase 3 exit review, initial submission](#migrated-review-0197)
- [2026-08-08 — Phase 3 exit findings focused re-review](#migrated-review-0198)
- [2026-08-09 — Phase 3 exit authorized third pass](#migrated-review-0199)
- [2026-08-09 — P3EXIT-R3 focused correction re-review](#migrated-review-0200)
- [2026-08-09 — Phase 3 post-approval coordination review](#migrated-review-0201)
- [2026-08-09 — P3EXIT-R4 focused correction re-review](#migrated-review-0202)

<a id="migrated-review-0197"></a>
<!-- review-migration:0197:start -->


## 2026-08-08 — Phase 3 exit review, initial submission

**Reviewer:** Codex

**Candidate implementation head:** `7958518`
**Review-request commit:** `b3fb6df` (handoff only)
**Scope:** Phase 3’s six exit criteria, the current-truth records that claim criteria 1–5 met, and
the exact candidate-head validation. `T-192` is Phase 4 and received no product verdict, but its
test edit is part of the submitted exact head and therefore remains subject to the repository’s
required gates.

**Verdict:** **Changes requested.** Criteria 1–5 are substantiated, including the five functional
properties in one independent **293-pass** focused run and an independently repeated full suite of
**2803 passed, 17 skipped, 2 deselected**. Criterion 6 is not met: the exact head fails both bare
mypy gates, and the authoritative exit records materially contradict the state they are asking the
reviewer to sign.

### Findings

| ID | Severity | Blocks approval | Area | Finding | Required correction | Status |
|---|---|---|---|---|---|---|
| `P3EXIT-R1` | **Medium** | **Yes — Phase 3 exit truth** | Current-truth records and handoff | The phase record cannot currently support criterion 6 because its live claims disagree. `IMPLEMENTATION_PLAN.md` says all loose items are dispositioned and criterion 6 alone remains immediately after marking T-189, T-171, T-186, and T-188 **Open**; it calls the phase’s deliverables nine while its Deliverables table contains eleven rows, including T-169/T-170. `STATUS.md`’s top/current snapshot likewise says those four items still need disposition and T-189 remains to be done. `TASKS.md`’s header still says T-111 is in review and that the current phase is Phase 2, while its live section correctly says Phase 3 has an empty review queue. The handoff then narrows the stale-record warning to one TASKS line, lists nine deliverables but says two of “them” removed Phase 2 deliverables without listing T-169/T-170, and presents FPS as still resting on a derived fixture even though T-185 had already captured and approved real 30/60 FPS values. These are current exit/scope claims, not harmless historical entries. | Sweep the live Phase 3 claims in `IMPLEMENTATION_PLAN.md`, `STATUS.md`, and the TASKS header so task dispositions, deliverable scope/count, and the one outstanding criterion agree. Correct the handoff when carrying the re-review: criterion 1’s current FPS evidence is T-185’s recorded PeerTube fixture; the later T-188 DASH FPS observation does not reopen the already-satisfied column. Preserve historical review/decision text as history. | **Open** |
| `P3EXIT-R2` | **Medium** | **Yes — required exact-head gate** | `tests/ui/test_main_window.py:778` | Both test-inclusive type gates fail at `7958518`: mypy 2.3.0 reports `Left operand of "and" is always true [redundant-expr]` for `assert bar is not None and gate is not None and summary is not None`. `QMainWindow.statusBar()` is statically non-optional, so the new T-192 assertion makes a required gate red. `ai/TESTING.md` §2 requires bare `mypy` and `mypy --platform win32` whenever a test file changes. The handoff claims both passed at this exact head, but neither does; its format count is also 221 while the same tree reports 222. | Remove the redundant `bar is not None` test (or otherwise make the assertion type-correct without weakening the two nullable child checks), then rerun and report Ruff format plus both bare mypy gates from the corrected exact head. | **Open** |

Both findings are Medium because no reviewed product behavior is shown broken. Both block: one is a
required validation failure, and the other materially misstates the phase gate and scope being
signed. The correction re-review is the ordinary focused second pass allowed by `AGENTS.md` §10.

### Exit-criterion results

| # | Result | Evidence and residual |
|---|---|---|
| 1 | **Met.** | `test_the_table_matches_what_yt_dlp_f_reports` passed against the recorded fixture set. T-185’s approved `peertube_big_buck_bunny_60fps` capture supplies real 30/60 FPS values; the handoff’s description of FPS as derived-only is stale. `OPS-013`’s temporary allowance therefore does not need to carry the current FPS evidence. |
| 2 | **Met, with recorded CI residual.** | The real selected-pair route produced one file with audio and video locally. The recorded Windows run `31233348009` passed the exact test with ffmpeg 8.1.2. T-189’s capability suite independently passed, including the negative probe that makes a required tool-less run fail rather than skip. The workflow edit itself has still never executed on a runner; that is a real external residual, but it does not erase the earlier Windows merge proof or change the present-tools path. |
| 3 | **Met.** | The real download preview/written-path case passed through an MP3 conversion, a subdirectory, and a title containing Windows-illegal characters. |
| 4 | **Met.** | The path/containment suite passed, including traversal, absolute-path, symlink, Windows-illegal, device-name, and long-component cases; preview and worker converge on `contained_output_path`. |
| 5 | **Met.** | The real-kill restart test passed: a partial survived, the resumed request carried a non-zero range, and the completed bytes matched. The focused path/partial coverage also passed. |
| 6 | **Not met.** | `P3EXIT-R1` and `P3EXIT-R2` are open and block sign-off. |

### Reviewer verification at `7958518`

The repository’s `.venv/bin/python` points at a moved, nonexistent interpreter. The review created
a temporary venv under `/tmp` and copied the project’s already-installed site-packages into it; no
dependency was downloaded or installed into the maintainer’s environment. The test subprocesses
therefore used the same Python 3.14 / PySide6 6.11.1 / pytest 9.1.1 / mypy 2.3.0 packages while
retaining a valid interpreter path.

| Check | Result |
|---|---|
| `.venv/bin/ruff check .` | **pass** |
| `.venv/bin/ruff format --check .` | **pass**, **222 files** (not the handoff’s 221) |
| `python -m mypy src` | **pass**, 51 files |
| `python -m mypy` | **fail**, one `redundant-expr` at `tests/ui/test_main_window.py:778`, 125 files |
| `python -m mypy --platform win32` | **fail**, the same one error, 125 files |
| Focused criteria: format table, capabilities, paths, task placement, merge, preview/write, and real-kill resume | **293 passed** |
| Full suite, offscreen, bytecode disabled | **2803 passed, 17 skipped, 2 deselected**, four existing PySide disconnect warnings, 381.15 s |

The first sandboxed integration attempt produced three socket-permission failures before test
behavior ran; the permitted consolidated rerun is the 293-pass result above. Windows was not rerun,
real sites were not contacted, and the T-189 workflow remains unexecuted. Only `ai/REVIEWS.md` was
modified by the reviewer; reviewed source, tests, current-truth coordination files, and the handoff
were not edited. No commit or push was made.

<!-- review-migration:0197:end -->

<a id="migrated-review-0198"></a>
<!-- review-migration:0198:start -->


## 2026-08-08 — Phase 3 exit findings focused re-review

**Reviewer:** Codex

**Prior candidate:** `7958518`
**Correction implementation head:** `dc2161c`
**Candidate head:** `2049980` (adds the prior review record only)
**Re-submission commit:** `1943149` (review metadata only)
**Scope:** `P3EXIT-R1`, `P3EXIT-R2`, and regressions in their correction diff. T-192’s product
behavior and the five already-substantiated functional exit criteria were not reopened.

**Verdict:** **Blocked.** `P3EXIT-R2` is **Resolved**. `P3EXIT-R1` remains **Open — Medium,
blocks approval** because the corrected deliverable count still contradicts the table and prose it
is meant to reconcile. This is the ordinary focused correction re-review; with only a blocking
Medium remaining, `AGENTS.md` §10 requires the maintainer to authorize a third focused pass, accept
the documented risk, change scope, or carry the issue into a named follow-up. Criterion 6 and the
Phase 3 exit remain not met pending that choice.

### Finding results

| ID | Severity | Blocks approval | Re-review result | Evidence / remaining correction |
|---|---|---|---|---|
| `P3EXIT-R1` | **Medium** | **Yes — Phase 3 exit truth** | **Open — partially corrected.** The four loose-item dispositions now agree; STATUS’s top snapshot and TASKS’ header describe the current phase; and the FPS correction is accurate. The committed PeerTube fixture independently reports FPS on five formats with values 30 and 60, so the T-188 DASH observation reopens nothing. **The count/scope half remains contradictory:** the section is headed `### Deliverables`, its table contains T-169/T-170, and the paragraph below explicitly calls them “Two Phase 3 deliverables.” The new explanation then says that counting them as deliverables would be wrong. Its proposed distinction—nine “REQ-bearing” deliverables—also cannot carry the difference, because the T-169 row explicitly bears `REQ-020` and `REQ-021` and T-170 bears `REQ-020`. | Choose one taxonomy and apply it consistently: either eleven deliverables, of which nine are additive and two subtractive; or nine deliverables plus two withdrawal tasks, with T-169/T-170 moved/labelled outside the Deliverables set and the “Two Phase 3 deliverables” sentence rewritten. Then make STATUS and the re-submission use the same terms. Do not use “REQ-bearing” as the discriminator. |
| `P3EXIT-R2` | Medium | No | **Resolved.** The correction removes only the statically impossible `bar is not None` check. The genuinely nullable `gate` and `summary` results remain guarded, and the position assertions are unchanged. Both required test-inclusive mypy invocations now pass at the candidate source tree. | Direct diff inspection plus both bare mypy gates and the affected test suite. |

### Reviewer verification at `2049980`

The repository’s moved `.venv` interpreter remains unusable, so the review again used a temporary
venv under `/tmp` populated only from the already-installed project site-packages. It was removed
after verification. No dependency was downloaded or installed into the maintainer’s environment.

| Check | Result |
|---|---|
| `git diff --check 7958518..2049980` | **pass** |
| `.venv/bin/ruff check .` | **pass** |
| `.venv/bin/ruff format --check .`, excluding the later re-submission file absent at `2049980` | **pass, 222 files** |
| `python -m mypy` | **pass, 125 files** |
| `python -m mypy --platform win32` | **pass, 125 files** |
| Task placement plus affected main-window suite | **73 passed** (14 + 59) |
| Recorded FPS audit | PeerTube: **5**, values **30/60**; derived: **4**; DASH: **10**, value **30** |

Running Ruff format at `1943149` reports 223 rather than 222 because Ruff formats Python code
blocks in Markdown and that review-metadata commit adds the re-submission file. Excluding that file
reproduces the candidate’s 222 count, so the implementer’s corrected figure is accepted.

The implementer’s corrected-head full-suite result (**2803 passed, 17 skipped, 2 deselected**) was
not independently repeated in this focused pass; the initial review independently obtained the
same result, and the correction changes only documents plus one dead type guard. Windows runtime,
real sites, and the first execution of T-189’s workflow remain unverified as previously recorded.
Only `ai/REVIEWS.md` was modified by the reviewer. No commit or push was made.

<!-- review-migration:0198:end -->

<a id="migrated-review-0199"></a>
<!-- review-migration:0199:start -->


## 2026-08-09 — Phase 3 exit authorized third pass

**Reviewer:** Codex

**Prior candidate:** `2049980`
**Taxonomy correction:** `7032241`
**Measured code head:** `a5f65c9`
**Submission commit:** `d85bf85`
**Current evidence head:** `c317625` (review metadata only after `a5f65c9`)
**Scope:** The maintainer-authorized third focused pass on the unresolved count/scope half of
`P3EXIT-R1`, exact-code-head gates, and the T-189 workflow execution offered by the re-submission.
T-192, T-193 and T-194 are Phase 4 work and receive no product verdict here.

**Verdict:** **Blocked.** `P3EXIT-R1` is **Resolved** and `P3EXIT-R2` remains **Resolved**. A new
blocking Medium, `P3EXIT-R3`, is open: the canonical Phase 3 plan says T-189’s workflow has never
executed, while the current STATUS, handoff, and independently verified CI run say it has executed
successfully. Criterion 6 and the Phase 3 exit remain not met. This was the explicitly authorized
third pass; another focused pass on a Medium blocker requires a new maintainer authorization under
`AGENTS.md` §10.

### Finding results

| ID | Severity | Blocks approval | Result | Evidence / required correction |
|---|---|---|---|---|
| `P3EXIT-R1` | Medium | No | **Resolved.** The plan, STATUS and current handoff now use one taxonomy: **eleven deliverables, nine additive and two subtractive**. T-169/T-170 remain under `### Deliverables` and the sentence “Two Phase 3 deliverables remove a Phase 2 deliverable” remains correctly unchanged under that taxonomy. “Nine” is explicitly historical decomposition count, not current deliverable count; “REQ-bearing” is rejected rather than reused. | Direct inspection of `7032241` and every live occurrence. All eleven table rows are approved and the six loose items remain separately dispositioned. |
| `P3EXIT-R2` | Medium | No | **Remains Resolved.** No source or test file differs between measured head `a5f65c9` and current evidence head `c317625`. Both test-inclusive mypy gates pass over 125 files; the handoff’s 223-file format count is reproduced when the later third-pass handoff file is excluded from current HEAD. | Exact tree comparison plus local gates. |
| `P3EXIT-R3` | **Medium** | **Yes — Phase 3 exit truth / criterion 2 evidence** | **Open.** `IMPLEMENTATION_PLAN.md:634-637` says “One residual survives,” that T-189’s workflow “has never executed on a runner,” and cites only older run `31233348009`. Current STATUS and the re-submission say the opposite: run `31295392039` at `9fe22fb` executed the workflow, all five jobs passed, and the residual is closed. The reviewer independently queried GitHub: the run is completed/success, head SHA is `9fe22fb`, and `linux`, `frozen linux`, `frozen windows`, `STARBASE coverage`, and `windows desktop` all concluded success; the Windows job’s type, desktop, and Full suite steps all succeeded. The old plan paragraph is therefore false current truth at the exact exit record being signed. | Replace the plan’s present-tense “never executed” residual with the verified execution result and close the residual there, using the same run/head and bounded claim already in STATUS. Preserve the earlier unexecuted state in historical review text rather than as the plan’s current answer. |

`P3EXIT-R3` is Medium rather than High because the gate actually passed and no product behavior is
broken. It blocks because `IMPLEMENTATION_PLAN.md` is current truth and materially misstates the
execution of the gate protecting exit criterion 2.

### Reviewer verification

The repository’s moved `.venv` interpreter remains unusable, so local Python checks used a
temporary `/tmp` venv populated only from the already-installed project site-packages. It was
removed after verification; no dependency was downloaded or installed into the maintainer’s
environment.

| Check | Result |
|---|---|
| `git diff --check 2049980..c317625` | **pass** |
| `.venv/bin/ruff check .` | **pass** |
| Ruff format at measured code head shape (excluding the later third-pass handoff file) | **pass, 223 files** |
| `python -m mypy` | **pass, 125 files** |
| `python -m mypy --platform win32` | **pass, 125 files** |
| Task placement | **14 passed** |
| `git diff a5f65c9..c317625 -- src tests` | **empty** |
| GitHub Actions run `31295392039` | **completed/success at `9fe22fb`; all five jobs success** |

The implementer’s local full-suite result (**2807 passed, 17 skipped, 2 deselected, 4 warnings**)
was not independently repeated. The count is consistent with T-193/T-194 adding four tests to the
initial review’s independently reproduced 2803, the relevant source/test tree is unchanged after
the measured head, and the five-job CI run is independently verified. T-193/T-194 remain unreviewed
Phase 4 work outside this exit verdict. Real sites remain unverified. Only `ai/REVIEWS.md` was
modified by the reviewer; no commit or push was made.

<!-- review-migration:0199:end -->

<a id="migrated-review-0200"></a>
<!-- review-migration:0200:start -->


## 2026-08-09 — P3EXIT-R3 focused correction re-review

**Reviewer:** Codex

**Prior evidence head:** `c317625`
**Correction head:** `ccdbd0f`
**Handoff-only head:** `1863da8`
**Scope:** `P3EXIT-R3` and the semantic sibling sweep in its docs-only correction. The maintainer’s
standing instruction authorizes as many focused exit-review passes as necessary, superseding the
handoff’s statement—written before that instruction—that no fourth pass was authorized.

**Verdict:** **Approved at `ccdbd0f`.** `P3EXIT-R3` is **Resolved**. `P3EXIT-R1` and `P3EXIT-R2`
remain resolved, no open blocking Phase 3 finding remains, and **Phase 3 exit criterion 6 is met**.
Phase 3 is reviewed and signed off. The later `1863da8` adds only the correction handoff and does
not move the approved implementation/evidence boundary.

### Finding result

| ID | Severity | Blocks approval | Result | Evidence |
|---|---|---|---|---|
| `P3EXIT-R3` | Medium | No | **Resolved.** Both current occurrences in `IMPLEMENTATION_PLAN.md` now close T-189’s residual by execution: the six-item table row and the exit-summary paragraph name run `31295392039` at `9fe22fb`, all five jobs successful, and the required-run variable active without turning the merge proof into a failure. The old “never executed” state remains only as explicit history. | Direct correction inspection and semantic search. The reviewer had already independently queried GitHub and verified the run head/conclusion, all five job conclusions, and the successful Windows-platform type, desktop, and Full suite steps. STATUS and the handoff now agree with the canonical plan. |

The correction’s sibling sweep matters: the original finding cited the exit-summary paragraph, but
the T-189 table row repeated the same false current claim. Correcting both closes the defect class;
fixing only the named line would not have.

### Phase 3 exit result

| Criterion | Result |
|---|---|
| Format table matches recorded `yt-dlp -F` evidence | **Met** |
| Separate video/audio pair merges on Linux and Windows | **Met**; T-189’s CI residual is now closed by execution |
| Preview matches the written Windows-safe path | **Met** |
| Rendered template containment | **Met** |
| Partial download resumes across restart or states refusal | **Met** |
| Reviewed and signed off | **Met at `ccdbd0f`** |

### Reviewer verification

| Check | Result |
|---|---|
| `git diff --check c317625..1863da8` | **pass** |
| `.venv/bin/ruff check .` | **pass** |
| Ruff format at correction-head shape (excluding the later handoff) | **pass, 224 files** |
| Task placement | **14 passed** |
| Source/test diff after the previously verified code head | **empty** |
| GitHub Actions run `31295392039` | **completed/success at `9fe22fb`; all five jobs success** |

The full suite and both mypy gates were not repeated for this docs-only correction. Their accepted
results remain **2807 passed, 17 skipped, 2 deselected, 4 warnings** and both mypy platforms clean
over 125 files; no source or test file changed after those measurements. T-192, T-193 and T-194
remain unreviewed Phase 4 work and receive no verdict here. Real sites remain unverified. Only
`ai/REVIEWS.md` was modified by the reviewer; no commit or push was made.

<!-- review-migration:0200:end -->

<a id="migrated-review-0201"></a>
<!-- review-migration:0201:start -->


## 2026-08-09 — Phase 3 post-approval coordination review

**Reviewer:** Codex

**Approved implementation/evidence head:** `ccdbd0f`
**Coordination head:** `6114f51`
**Scope:** The current-truth coordination commits made after Phase 3 approval. The approved
implementation, Phase 3 product evidence, and unreviewed Phase 4 tasks are not reopened.

**Verdict:** **Changes requested on exit coordination.** Approval at `ccdbd0f` remains the exact
implementation/evidence verdict, but `P3EXIT-R4` is a blocking Medium against the records that are
supposed to carry that verdict forward: the latest pushed current-truth files simultaneously say
Phase 3 has and has not exited.

### Finding

| ID | Severity | Blocks approval | Area | Finding | Required correction | Status |
|---|---|---|---|---|---|---|
| `P3EXIT-R4` | **Medium** | **Yes — coherent exit coordination** | `ai/STATUS.md`, `ai/TASKS.md` | Commit `6114f51` correctly changes STATUS's top snapshot to Phase 4 and says the Phase 3 exit is complete, but leaves the live `### Where the findings stand` table saying `P3EXIT-R3` is “Corrected, unverified” and the following sentence saying criterion 6 is the only criterion unmet. TASKS remains dated 2026-08-08 and says in both its header and “Start here” line that Phase 3 is current and only its exit review remains; the live `## In Review` preface repeats that claim while the section actually contains T-192, T-193 and T-194. These are not merely the explicitly dated historical blocks lower in the files. | Sweep the live STATUS finding/submission block and TASKS header/current-phase/`## In Review` preface so they agree with the approved plan: Phase 3 exited at `ccdbd0f`; `P3EXIT-R1..R3` are resolved; criterion 6 is met; Phase 4 is current; T-192/T-193/T-194 are the unreviewed Phase 4 queue. Preserve genuinely dated historical narrative as history. | **Open** |

This is the same defect class as the earlier findings—a current claim stayed in place after the
fact it described changed—and is Medium because no product behavior or earlier evidence is broken.
It blocks the coordination close because `STATUS.md` and `TASKS.md` are authoritative for current
state and actionable work. The maintainer's standing authorization covers the next focused pass.

### Reviewer verification at `6114f51`

| Check | Result |
|---|---|
| `git status --short --branch` | **clean; `main` matches `origin/main`** |
| Direct inspection of `6114f51` | **STATUS top corrected; live findings/submission block unchanged** |
| Semantic search across STATUS, TASKS, and IMPLEMENTATION_PLAN | **plan coherent; the live STATUS and TASKS contradictions above remain** |
| Source/test changes after approved evidence head | **not reopened; finding is confined to post-approval coordination truth** |

Only `ai/REVIEWS.md` was modified by the reviewer. No commit or push was made.

<!-- review-migration:0201:end -->

<a id="migrated-review-0202"></a>
<!-- review-migration:0202:start -->


## 2026-08-09 — P3EXIT-R4 focused correction re-review

**Reviewer:** Codex

**Prior coordination head:** `6114f51`
**Review-record head:** `ed43469`
**Correction head:** `4aea3dc`
**Scope:** `P3EXIT-R4` and its current-claim sibling sweep in STATUS and TASKS. Phase 3's approved
implementation/evidence boundary at `ccdbd0f` and the Phase 4 task implementations are not reopened.

**Verdict:** **Approved — exit coordination complete at `4aea3dc`.** `P3EXIT-R4` is
**Resolved**. STATUS, TASKS, and IMPLEMENTATION_PLAN now agree that Phase 3 exited at `ccdbd0f`,
all six criteria are met, Phase 4 is current, and T-192/T-193/T-194 are unreviewed Phase 4 work.

### Finding result

| ID | Severity | Blocks approval | Result | Evidence |
|---|---|---|---|---|
| `P3EXIT-R4` | Medium | No | **Resolved.** STATUS's live findings block now marks P3EXIT-R1 through R3 resolved and criterion 6 met. TASKS's header and “Start here” line name Phase 4 as current, and its `## In Review` preface names the three entries the section actually contains. The lower 2026-08-08 STATUS narrative and T-188 completion clause remain explicitly dated history rather than live claims. | Direct correction inspection, semantic search across all three current-truth files, and the task-placement gate. |

The correction-head STATUS row describes P3EXIT-R4 as open because only the Reviewer may resolve a
finding; that was accurate when the implementer returned the batch. The routine post-verdict
snapshot update may change that row to Resolved or replace the duplicated state with a link to this
canonical review record. It does not require another product or exit-criterion pass unless it
introduces a new contradiction.

### Reviewer verification at `4aea3dc`

| Check | Result |
|---|---|
| `git diff --check ed43469..4aea3dc` | **pass** |
| `.venv/bin/ruff check .` | **pass** |
| `.venv/bin/ruff format --check .` | **pass, 226 files** |
| `python -m pytest -q tests/unit/test_task_placement.py` | **14 passed** |
| Semantic search for the superseded live claims | **none outside explicitly dated/history-qualified text** |
| Correction diff | **STATUS and TASKS only; no source or test change** |

The product suite and mypy gates were not repeated for this docs-only correction. Their accepted
Phase 3 evidence remains unchanged. Only `ai/REVIEWS.md` was modified by the reviewer; no commit or
push was made.

<!-- review-migration:0202:end -->
