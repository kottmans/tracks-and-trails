# REVIEWS.md — Tracks & Trails

**Purpose:** Record code review, QA, and readiness findings and their evidence.
**Authority:** Canonical for review evidence and finding status. Historical record — append, never rewrite.
**Owner:** Reviewer (Codex)
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-27
**Update when:** A review completes, a defect is found, a prior finding is rechecked, or a release review occurs.
**Does not contain:** The work required to fix findings — that goes to `TASKS.md`.

---

## How reviews work here

- **The reviewer is a different agent than the implementer** (`AGENTS.md` §3). An implementer
  never signs off on its own change.
- **One coherent change unit per review.** Record the exact base and head commit, or a
  clearly bounded uncommitted diff. Unrelated features must not accumulate into one review
  because they share a working tree.
- **Inspect the diff and the evidence, not the explanation.** A confident narrative from the
  implementer is not proof of correctness; it anchors the review. Verify against
  `REQUIREMENTS.md`, the task's acceptance criteria, and `TESTING.md`.
- **Corrections get a focused re-review** as a distinct follow-up diff, before the work unit
  expands.
- Only **Open** findings require a `TASKS.md` entry. Closed outcomes are recorded here.
- **This file is the record for serial work.** During a parallel wave (`AGENTS.md` §9) reviews
  are partitioned: the assigned reviewer writes `ai/reviews/T-0NN.md` on the task branch, this
  file carries only the index entry and the integration result, and approval names the exact
  implementation head it covers. Every severity, blocking, verdict, and budget rule below is
  the same in both modes.

**Severity:** Critical · High · Medium · Low · Note
**Finding status:** Open · Resolved · Accepted Risk · Won't Fix · Superseded

### Standing risk focus

Apply deliberate adversarial attention to these on every review that touches them — they are
where this project's failures are silent or destructive:

- Process lifecycle: orphaned workers, zombie processes, cancellation races, shutdown ordering
- Anything crossing the IPC boundary: picklability, unbounded queues, partial messages
- Filesystem writes: path traversal via rendered templates, Windows-illegal names, overwrite of existing files
- Log and history content: cookie material, proxy credentials, tokens in URLs (`NFR-007`)
- SQLite migrations and crash recovery: data loss, states that lie
- Qt threading: any object touched off the GUI thread
- Layering violations (`ARCHITECTURE.md` §4) — the enforcement test can be weakened as easily as bypassed
- `REQ-EXCL` boundaries: anything resembling circumvention (`SEC-001`)

### Review entry template

```markdown
## YYYY-MM-DD — <Scope title>

**Reviewer:** <role/tool>
**Task(s):** T-###
**Base:** <commit>  **Head:** <commit>
**Platforms verified:** Linux / Windows / both
**Verdict:** Approved | Changes requested | Blocked

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|

### Checks run

| Check | Result |
|---|---|

### Readiness

<merge/release call, and what remains>
```

---

## Reviews

## 2026-07-25 — T-003 application icon assets

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-003`
**Base:** `a2cf514eb6dbb6a1c5812ddc1b4355d04c987d4d`
**Head:** bounded uncommitted snapshot — tracked patch SHA-256
`37deb9c436df1ccaa1266cbcaa82c132c1bd952c1ce2f44653ca250c31837371`;
ordered ten-asset manifest SHA-256
`9310f20576bc05311c483833fe2e4d3b9e8628c8e102fcbbecb6e04017b70a1e`
**Platforms verified:** Linux; Windows remains assigned to `T-006`
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T003-R1` | Medium | Palette evidence | `ai/ARCHITECTURE.md:288` calls the hexes and shares exact, while `ai/TASKS.md:299` specifies only a radius, not a clustering algorithm. Reasonable radius-40 implementations did not reproduce all published values: fixed-seed assignment gave weighted centers `#1E5E47` / `#D9A24C` / `#093224` at 72.48% / 24.67% / 2.55%; greedy mode clustering gave `#1E5E47` / `#D8A24C` / `#0C3626` at 72.25% / 24.33% / 2.59%. Radius 20–60 also changed the shares materially. The green and gold choices are visually representative, but the measurement does not uniquely establish the published table. | Supply a deterministic method whose output matches the table, or treat the hexes as adopted canonical swatches and remove the method-dependent share claims. | Resolved — `T-022` |
| `T003-R2` | Low | Task truth | `ai/TASKS.md:288` marks `T-003` Complete while `ai/TASKS.md:328` says an acceptance criterion was not fully met. Independent inspection finds the 16 px note silhouette and gold path recognizable; only the landscape detail collapses. The minimum “not unreadable mush” criterion is met narrowly, so `T-021` is a justified enhancement rather than a blocker, but the current wording records a contradictory completion state. | Record the criterion as narrowly met, retain the marginal visual assessment, and keep `T-021` as the optional simplified-glyph improvement. | Resolved — `T-022` |
| `T003-R3` | Low | Test coverage | `ai/TESTING.md:48` requires tests relevant to a source change, but the default suite has no assertion that the assets exist, have the required dimensions, load through Qt, or expose the ICO frame set. The green suite therefore proves only that unrelated Python behavior did not regress. | Add a default-suite resource test and run the same assertion on Windows through `T-006`. | Resolved — `T-022` |
| `T003-R4` | Note | File ownership | The `ai/ARCHITECTURE.md` edit is authorized in this instance. The task explicitly ordered the exact values recorded and pointed to the approximate Theme entry, and Claude Code holds the Planner capability in `AGENTS.md:40`. The Implementer's restriction at `AGENTS.md:51` was therefore not used to self-authorize an unrelated architecture change. | None for this review. A future task without equally explicit scope would still require Planner direction. | Resolved |
| `T003-R5` | Note | Source provenance | The current `icon.png` is clean and its SHA-256 is `f0e202c714ac316fdaa75b4cccbc0b46fee4686129ac09d0d276446abfe74b8d`, but no pre-placement hash or second copy exists in the review evidence. Byte identity to the maintainer's original cannot be independently established after the fact. | Preserve the recorded hash as the baseline for future changes. | Accepted Risk |

### Checks run

| Check | Result |
|---|---|
| Bounded snapshot | Base equals `HEAD`; tracked patch and ordered asset-manifest hashes recorded above. A commit was not required to make this review specific. |
| PNG structure and hygiene | Nine PNGs have only `IHDR` / `IDAT` / `IEND`, end exactly at `IEND`, contain no text/profile metadata, and have the claimed RGBA dimensions. No personal path or unexpected payload found. |
| Framing and derivation | Source alpha bounding box is exactly 498×743 at +260+192, leaving 266 right / 89 bottom. Alpha >250 covers 9.06% of the canvas. Recreating the 844×844 master at offset +173+50 and resizing with Pillow Lanczos matches all eight derived PNGs pixel-for-pixel. |
| ICO structure | Seven non-overlapping PNG frames: 16/24/32/48/64/128/256; no trailing payload. Pillow's ICO writer resampled the 16–128 frames again rather than embedding the standalone PNG bytes; the 16/24/32 white-composite maximum channel differences are 2/3/3 and are visually equivalent. |
| Qt load, Linux offscreen | Every PNG and the ICO are non-null through `QIcon`; the ICO reports all seven expected sizes. |
| Visual inspection | 16 px is marginal but recognizable; 24 px acceptable; 32 px and above progressively clear. `T-021` is correctly scoped as an improvement and does not block `T-007`. |
| Scope and coordination | No SVG exists and its unavailability is explicit. No theme ramps, installer assets, or artwork redesign were added. The `T-006` Windows carry is required by `OPS-003`, not a hidden pass. |
| `git diff --check` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 49 files already formatted. |
| `mypy src` | Passed: no issues in 30 source files. |
| `pytest -q` | Passed: 4 passed, 1 deselected in 0.14s. No test exercised the icon assets. |

### Readiness

The asset set itself is usable, the 16 px criterion is met narrowly, and `T-007` need not be
re-blocked. The change is not ready to merge until `T-022` corrects the palette evidence and
completion wording and adds the resource invariant test, followed by focused re-review.
Windows loading remains genuinely unverified until `T-006`. The Phase 0 exit review remains
pending after `T-001`, `T-005`, `T-006`, and `T-007` are complete.

## 2026-07-25 — T-022 focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-022`; re-review of `T003-R1`, `T003-R2`, `T003-R3`
**Base:** bounded `T-003` snapshot recorded in the preceding review
**Head:** bounded uncommitted correction manifest SHA-256
`09b7b21dd72d0285bb4cba03d728435f5127976de8e0cbf6790311dbc65cbade`;
unchanged ten-asset manifest SHA-256
`9310f20576bc05311c483833fe2e4d3b9e8628c8e102fcbbecb6e04017b70a1e`
**Platforms verified:** Linux; Windows remains assigned to `T-006`
**Verdict:** Approved

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T003-R1` | Resolved | `ARCHITECTURE.md` now makes the hexes normative adopted swatches, removes the unstable shares, and distinguishes artwork provenance from measurement. The modal-color example is accurate for fully opaque pixels: `#D8A14C` is 1.068% and `#D8A24C` is 0.942%. Using alpha >250 reverses those two modes (0.845% vs. 0.906%), independently confirming sensitivity to a reasonable sampling choice. |
| `T003-R2` | Resolved | The completion note now records the 16 px criterion as narrowly met while preserving the marginal assessment. Rewording `T-021` is a necessary consistency correction, not scope creep: its former premise contradicted that disposition and its former threshold was already met; side-by-side improvement makes the proposed enhancement falsifiable. |
| `T003-R3` | Resolved | The new unit and Qt tests cover presence, exact PNG dimensions, the complete delivered ICO frame contract, Qt decoding, and nonblank 16 px content. All five requested mutations failed for the intended assertions and were restored. The seven-frame pin matches the delivered `T-003` contract; the weak opacity assertion leaves legitimate `T-021` artwork changes possible. |

### New findings

None.

### Checks run

| Check | Result |
|---|---|
| Resource suite baseline | 23 passed. |
| Missing `icon-48.png` | Failed the parameterized presence check, directory manifest check, and Qt load check. |
| `icon-32.png` resized to 31×31 | Failed the declared-dimension check with `(31, 31) != (32, 32)`. |
| `icon.ico` truncated to 200 bytes | Failed both Qt availability/frame checks; 21 other resource cases passed. |
| `icon.ico` reduced to 16/32/48 | Failed both the parsed and Qt-reported full-frame assertions. |
| Stray `icon-99.png` | Failed the exact directory manifest assertion. |
| Restoration | Asset manifest returned to `9310f205...70a1e`; source master remained `f0e202c7...74b8d`. |
| Qt platform default | With no caller value, `tests/ui/conftest.py` selects `offscreen`, matching `TESTING.md` and `T-006`. With `QT_QPA_PLATFORM=minimal`, `setdefault` preserved `minimal`; all 12 UI resource cases passed. The setting does not bypass Qt image decoding and does not claim native taskbar verification. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 52 files already formatted. |
| `mypy src` | Passed: no issues in 30 source files. |
| `pytest -q` | Passed: 27 passed, 1 deselected in 0.16s. |
| `git diff --check` | Passed. |

### Readiness

The combined `T-003` + `T-022` change unit is approved and ready to commit and merge once the
coordination owner advances `T-022` and `STATUS.md` from “re-review pending” to completed. All
three open findings are resolved. `T003-R5` remains an accepted provenance risk, and Windows
execution of the resource test remains an explicit `T-006` carry; neither is hidden or newly
introduced by this correction.

## 2026-07-25 — T-006 Linux and Windows CI

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-006`
**Base:** `8d30c884236eb07d05649efa29529fa9b0dc7d74`
**Head:** `8db0518de72c17139ce34b832f8cbeed24ec4d21`
**Platforms verified:** Linux and Windows through GitHub-hosted runner artifacts and logs
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T006-R1` | Low | Failure evidence | `.github/workflows/ci.yml:91` writes lint, format, and mypy output only to the Actions job log, while only the baseline and pytest commands tee into `reports/`. This is observable in run `30179263484`: `if: always()` uploaded the failed Windows artifact, but it contained only `environment.txt`; the actual `F401` diagnostic was absent and had to be retrieved from the job log. That contradicts `ai/TESTING.md:175` and the workflow comments calling uploaded artifacts the retained failure output and the only Windows debugging material. The failed-pytest case is captured correctly. | Preserve stdout/stderr for the controllable gates in `reports/` without swallowing their exit status, and document honestly that early action/setup failures remain available through Actions-owned logs rather than the artifact. | Open — `T-023` |
| `T006-R2` | Low | Coordination truth | The `T-006` record says both Windows carries are discharged, but the canonical completed-task notes still say the opposite: `ai/TASKS.md:475` calls `T-003`'s Windows check unverified and `ai/TASKS.md:536` / `ai/TASKS.md:571` leave `T-002` Linux-only and carried into `T-006`. `TASKS.md` is current truth, so readers receive mutually exclusive states in one file. | Update the `T-002` and `T-003` completion notes to cite the verified `T-006` Windows evidence while preserving genuinely Linux-only probes. | Open — `T-023` |
| `T006-R3` | Note | Linux packages | `ubuntu-latest` and unpinned `apt` packages can drift, and the five-package list is sufficient rather than proven minimal. Exact package-version pins on a moving hosted image would be brittle and would suppress security updates; exercising the current supported Ubuntu environment is useful portability pressure. The Linux baseline and suite prove the present list sufficient. | Keep the acknowledged assumption and treat future runner/package drift as CI maintenance, not a reproducibility guarantee. | Accepted Risk |
| `T006-R4` | Note | Qt environment | The job-level `QT_QPA_PLATFORM=offscreen` and `tests/ui/conftest.py` do not conflict. CI makes the value explicit; local tests default to it; `setdefault` preserves any caller override. The standalone baseline reads the job value and asserts the resolved plugin. | None. | Resolved |
| `T006-R5` | Note | Baseline validation | Keeping `.github/scripts/qt_baseline.py` outside pytest is justified by its earlier, clearer failure boundary. `ruff` checks it, both matrix jobs execute it, and an independent `mypy --strict` run found no issues. The standard `mypy src` gate does not statically check future edits to it, but its size and mandatory runtime execution keep that residual risk small. | Add it to the type-check command if the script grows beyond this focused probe. | Accepted Risk |
| `T006-R6` | Note | Fork security | A fork PR does execute untrusted checked-out code through editable installation and pytest; that is intrinsic to CI and should not be described otherwise. It executes on GitHub-hosted ephemeral runners with no secrets, a read-only `contents` token, and no `pull_request_target` or third-party actions, so no privileged fork path was found. | Preserve this permission model; review any future secrets, write permissions, self-hosted runners, or `pull_request_target` use as a new threat model. | Resolved |

### Checks run

| Check | Result |
|---|---|
| Final push and PR | Runs `30179509580` and `30179510514` both resolve to head `8db0518`; Linux and Windows jobs passed. PR #1 is open, non-draft, mergeable, and `CLEAN`. |
| Deliberate lint failure | Run `30179263484`: both runners failed at `Lint` on the injected unused `os` import (`F401`); both `Upload evidence` steps succeeded. |
| Deliberate pytest failure | Run `30179308976`: both runners reached `Tests` and failed only on the injected `assert 1 == 2`; both uploads succeeded. The Windows artifact contains the complete traceback in `pytest.txt` and `pytest.xml`. |
| Revert integrity | `tests/unit/test_ci_gate_check.py` is deleted at `7406928` and absent from head. The workflow blob is identical at the lint-failure, test-failure, reverted, and final heads; post-revert changes before `8db0518` are coordination documents only. |
| Windows `T-002` carry | Final Windows artifact: Python 3.14.6 (MSC AMD64), PySide6/shiboken6/Qt 6.11.1, `platform offscreen`, `QWidget visible=True`, baseline exit zero. Discharged. |
| Windows `T-003` carry | Final Windows pytest text/XML: all 27 default cases passed, including `test_ico_exposes_every_frame_to_qt`, whose source pins all seven frames. Discharged. |
| Artifact retention | Failed-test artifacts downloaded successfully; API metadata reports `expired=false` and expiry on 2026-08-24, matching 30 days. |
| Remaining `OPS-003` automation | Orphan assertions require worker behavior, path safety requires path implementation, install/launch requires the frozen artifact (`T-020`), and screenshots require the shell (`T-007`). Deferring them is honest, not omitted current-tree coverage. |
| Local Qt baseline | Passed offscreen with PySide6/shiboken6/Qt 6.11.1 and visible 320×240 widget. |
| `mypy --strict .github/scripts/qt_baseline.py` | Passed: no issues in one source file. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 53 files already formatted. |
| `mypy src` | Passed: no issues in 30 source files. |
| `pytest -q` | Passed: 27 passed, 1 deselected in 0.09s. |
| `git diff --check 8d30c88 8db0518` | Passed. |

### Readiness

The CI gate proof is real, both Windows carries are discharged, and no product or security
blocker was found. PR #1 is not ready to merge until `T-023` closes the two evidence/current-
truth findings and receives focused re-review. After approval, prefer a squash merge so the
deliberately broken gate-proof commits do not enter `main`; published branch history must not
be rewritten.

## 2026-07-25 — T-023 focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-023`; re-review of `T006-R1`, `T006-R2`
**Base:** `8d30c884236eb07d05649efa29529fa9b0dc7d74`
**Correction boundary:** `8db0518de72c17139ce34b832f8cbeed24ec4d21` to
`24d926d103945f1abb049783d80561ee79ce88d8`
**Platforms verified:** Linux locally; Linux and Windows through GitHub-hosted runner
artifacts and logs
**Verdict:** Changes requested

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T006-R1` | Partially resolved | The workflow correction works. Run `30180163074` failed at lint on both platforms without masking the exit, both uploads succeeded, and the downloaded Windows artifact contains the complete `F401` diagnostic in `lint.txt`, including the runner-native `tests\unit\...` path. Run `30180215713` reverted the probe, passed both jobs, and retained all seven expected files per artifact. However, the required documentation correction was omitted: `.github/workflows/ci.yml:10`, `.github/workflows/ci.yml:91`, `ai/TESTING.md:173`, and `ai/TASKS.md:293` still call artifacts the only Windows debugging material. Checkout, setup, and installation failures happen before `reports/` exists, while their Actions-owned job logs remain available. This directly misses `T-023`'s scope and second acceptance criterion. Update all four descriptions to distinguish downloadable project-gate evidence from early Actions/setup logs. |
| `T006-R2` | Resolved | The completed `T-002` and `T-003` records now identify their Windows carries as discharged and cite the verified `T-006` evidence. A full `TASKS.md` search found no other stale open carry: remaining uses either define `T-006`'s historical inputs, explicitly mark them resolved, or describe the still-open real-download cancellation check assigned to `T-019`. |

### New findings

None.

### Checks run

| Check | Result |
|---|---|
| Corrected lint-failure proof | Run `30180163074` resolves to `d719ea2`; Linux and Windows failed at `Lint`, later gates were skipped, and both `Upload evidence` steps passed. Both downloadable artifacts contain `environment.txt` and `lint.txt`; Windows `lint.txt` contains the full `F401` diagnostic. Artifact metadata is current (`expired=false`) with expiry on 2026-08-24. |
| Passing revert proof | Run `30180215713` resolves to `f6e9ce1`; every gate and upload passed on Linux and Windows. Each artifact contains `environment.txt`, `lint.txt`, `format.txt`, `mypy.txt`, `qt-baseline.txt`, `pytest.txt`, and `pytest.xml`. |
| Revert and head integrity | The workflow blob is identical at `f6e9ce1` and `24d926d`; `tests/unit/test_ci_gate_check.py` is absent from head. |
| Current PR | PR #1 is open, non-draft, mergeable, and `CLEAN` at `24d926d`; both push and pull-request matrix runs at that head passed. |
| `TASKS.md` carry audit | No stale open Windows carry from `T-002` or `T-003` remains. The sleeping-worker cancellation limitation remains correctly open under `T-019`. |
| Local Qt baseline | Passed offscreen with PySide6/shiboken6/Qt 6.11.1 and a visible 320x240 widget. |
| `mypy --strict .github/scripts/qt_baseline.py` | Passed: no issues in one source file. |
| `ruff check .` | Passed: "All checks passed!" |
| `ruff format --check .` | Passed: 53 files already formatted. |
| `mypy src` | Passed: no issues in 30 source files. |
| `pytest -q` | Passed: 27 passed, 1 deselected in 0.10s. |
| `git diff --check 8d30c88 24d926d` | Passed. |

### Readiness

The retention mechanism and the `TASKS.md` carry correction are verified, but PR #1 is not
ready to merge while `T006-R1`'s explicit documentation requirement remains unmet. After the
four stale descriptions are corrected and focused re-review approves them, prefer a squash
merge so the deliberate gate-proof commits do not enter `main`.

## 2026-07-25 — T-005 layering enforcement test

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-005`
**Base:** `3fe92abfa82371e76c6be13b0cdb31d1275d503c`
**Head:** `655f53d6fcb616d0691b1aefc229fb41393a8a69`
**Platforms verified:** Linux locally; Linux and Windows through GitHub-hosted runner
artifacts and logs
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T005-R1` | **High** | Analyzer self-protection | The synthetic cases do not pin the rule definitions; they only sample them. Narrowing the core predicate at `tests/unit/test_layering.py:53` to the two sampled paths (`core/models.py` and `core/paths.py`) excluded every other core module while all 45 tests still passed. Adding the existing `downloader/environment.py` as a third `YTDLP_OWNERS` entry at line 36 also left all 45 green. Those are direct weakenings of §4 and §6 that the claimed meta-guard does not detect. The requested coarse mutations do fail, but the guard can still be weakened immediately around its fixtures. | Pin the complete rule semantics independently of `RULES`: exercise each forbidden package against every discovered source path and compare with an explicit architecture-derived expectation, or directly assert exact package/owner sets and predicate domains. Include future-path sentinels where discovery alone cannot express the domain. | Open — `T-024` |
| `T005-R2` | Low | Static-analysis purity | `tests/unit/test_layering.py:28` imports `tracks_and_trails` solely to locate `SRC`, executing `__init__.py` before the static analysis. That contradicts the implementation record's “no imports executed” claim and couples collection to the editable installation; an installed non-editable copy could make the test scan a different tree. It is harmless with today's side-effect-free `__init__.py`, but it weakens the reason this test uses AST in the first place. | Derive the repository source path from `Path(__file__).resolve()` and assert the expected package directory exists; do not import the package under test. | Open — `T-024` |
| `T005-R3` | Low | Current truth | `ai/STATUS.md:100` still says nothing in `TESTING.md` has been implemented, while the same snapshot now says `T-005` is implemented and `TESTING.md` records the layering guard, resource invariants, and CI. The branch edits `STATUS.md` but leaves its closing blanket statement false. | Replace the blanket statement with the actual boundary between implemented checks and approved future behavior. | Open — `T-024` |
| `T005-R4` | Note | Scope | Implementing four checks is not scope creep. `T-005`'s Scope explicitly enumerates all four, §4 states the Qt/UI boundaries and the worker no-Qt invariant, and §6 explicitly confines yt-dlp imports to two modules. The “two rules” out-of-scope wording is imprecise, but it does not erase the more specific Scope. | None. | Resolved |
| `T005-R5` | Note | AST coverage | `ast.walk` correctly detects aliases, star imports, multi-alias statements, and imports inside functions, classes, `TYPE_CHECKING`, and `try` blocks. Skipping relative imports is sound because they cannot name a third-party root. Literal dynamic imports remain undetected as the module docstring says; accepting that conspicuous bypass is reasonable for this task. | Revisit only if dynamic third-party imports enter the codebase. | Accepted Risk |

### Checks run

| Check | Result |
|---|---|
| Baseline layering suite | Passed: 45 tests. The sweep covers all 30 Python modules currently under `src/tracks_and_trails`; the handoff's “27 modules” count is stale. |
| Five real-tree violations | Each independently failed exactly one module case with the offending path and rule: Qt in `core/models.py`, Qt via `from` in `core/job_state.py`, yt-dlp in `ui/main_window.py` (two rule messages), Qt in `downloader/worker.py`, and yt-dlp in `persistence/db.py`. |
| Restoration | `tests/unit/test_layering.py` returned to SHA-256 `ccfdfb7c...fc563`; the aggregate source-tree hash returned to `e83a37b4...9ce`; no review mutation remains. |
| Requested analyzer weakenings | Core predicate narrowed to only `core/models.py`: 1 failed, 44 passed. Dropped `shiboken6`: 1 failed, 44 passed. Emptied owners: 2 failed, 43 passed. `check()` returning `[]`: 7 failed, 38 passed. |
| Undetected core weakening | Core predicate narrowed to only the two sampled paths: **45 passed**. |
| Undetected owner weakening | Added existing `downloader/environment.py` to `YTDLP_OWNERS`: **45 passed**. |
| Vacuity mutation | `source_files()` returning `[]`: 1 failed, 14 passed, 1 skipped; the explicit vacuity check works. |
| AST import forms | Aliased, star, `TYPE_CHECKING`, class-body, `try`/`except`, and multi-alias imports all produced the expected top-level roots. |
| CI push and PR | Runs `30180962699` and `30180972675` resolve to `655f53d`; Linux and Windows jobs passed. The downloaded Windows push artifact lists all 45 layering cases and reports 72 passed, 1 deselected. |
| Current PR | PR #2 is open, non-draft, mergeable, and `CLEAN` at `655f53d`; all four current check runs passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 54 files already formatted. |
| `mypy src` | Passed: no issues in 30 source files. |
| Bare `mypy` | Passed: no issues in 41 source files. |
| Isolated `mypy tests/unit/test_layering.py` | Failed at the package-location import because the separately analyzed installed package has no `py.typed`; this is not a required gate, but reinforces `T005-R2`. |
| `pytest -q` | Passed: 72 passed, 1 deselected in 0.32s. |
| `git diff --check 3fe92ab 655f53d` | Passed. |

### Readiness

The analyzer catches real violations, the AST walk is sound for ordinary imports, and the
Linux/Windows evidence is genuine. PR #2 is not ready to merge because the analyzer can still
be weakened around its synthetic samples while remaining fully green. `T-024` tracks the
three open corrections; focused re-review is required before merge.

## 2026-07-25 — T-024 focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-024`; re-review of `T005-R1`, `T005-R2`, `T005-R3`
**Base:** `3fe92abfa82371e76c6be13b0cdb31d1275d503c`
**Correction boundary:** `655f53d6fcb616d0691b1aefc229fb41393a8a69` to
`d6af9d92e49388eff0f9917b0e79de10687d37d9`
**Platforms verified:** Linux locally; Linux and Windows through GitHub-hosted runner
artifacts and logs
**Verdict:** Changes requested

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T005-R1` | Partially resolved | The original High false-negative bypass is closed. Narrowing the core predicate to the two former fixture paths now produces 5 failures; adding `downloader/environment.py` as a third owner produces 2; dropping `shiboken6` produces 9; emptying the owners produces 3; and returning `[]` from `check()` produces 36. Every real path is checked against an independently stated required set. The comparison is still one-way, however: adding architecture-allowed `typing` to `QT` leaves all 76 tests green. `test_every_module_is_actually_guarded` proves every required prohibition exists but not that the analyzer has no extra prohibitions, despite the correction claiming the two statements agree and the `T-024` scope requiring complete rule semantics. Compare both directions for every real path over the union of architecture packages and all packages present in `RULES`. |
| `T005-R2` | Resolved | `SRC` is derived from the test file's resolved path. A fresh-process load with an import guard reached the checkout's exact `src/tracks_and_trails` directory and attempted no `tracks_and_trails` import. Isolated mypy now passes too. |
| `T005-R3` | Partially resolved | Separating unimplemented product behavior from implemented testing scaffolding is the right correction, and the CI/resource/layering claims are exact. The replacement still overstates the first half: `STATUS.md:101` says not one module in §4 has an implementation, but `__main__.py` and `app.py` implement the runnable T-001 placeholder entry point (`freeze_support()`, dispatch, version output, exit zero). Say that no product features exist beyond the entry-point scaffold rather than that no module is implemented. |

### New findings

None.

### Checks run

| Check | Result |
|---|---|
| Corrected baseline | Layering suite passed: 76 tests. Full suite passed: 103 passed, 1 deselected. |
| Former core-predicate bypass | Narrowed to `core/models.py` and `core/paths.py`: 5 failed, 71 passed; every excluded current core module was named as an enforcement hole. |
| Former owner bypass | Added `downloader/environment.py` as a third owner: 2 failed, 74 passed; both the exact allowlist check and the path sweep failed. |
| Other weakening probes | Dropped `shiboken6`: 9 failed, 67 passed. Emptied owners: 3 failed, 73 passed. `check()` returning `[]`: 36 failed, 40 passed. |
| Surplus-prohibition probe | Added architecture-allowed `typing` to `QT`: **76 passed**. This is the remaining one-way-comparison gap in `T005-R1`. |
| Five real-tree violations | Injected together; exactly five module cases failed with the offending file and rule, including both yt-dlp rules for `ui/main_window.py`. |
| Restoration | Test file returned to SHA-256 `bc4b530b...f1211`; aggregate source-tree hash returned to `e83a37b4...9ce`; no experimental mutation remains. |
| Static source discovery | A guarded fresh-process load resolved `SRC` to this checkout and attempted zero project-package imports. |
| CI | Push run `30182191197` and the current PR run passed on Linux and Windows at `d6af9d9`. The downloaded Windows push artifact lists all 76 layering cases and reports 103 passed, 1 deselected. |
| Current PR | PR #2 is open, non-draft, mergeable, and `CLEAN` at `d6af9d9`; all four current check runs passed. |
| `ruff check .` | Passed: "All checks passed!" |
| `ruff format --check .` | Passed: 54 files already formatted. |
| `mypy src` | Passed: no issues in 30 source files. |
| Bare `mypy` | Passed: no issues in 41 source files. |
| `mypy tests/unit/test_layering.py` | Passed: no issues in one source file. |
| `pytest -q` | Passed: 103 passed, 1 deselected in 0.17s. |
| `git diff --check 3fe92ab d6af9d9` | Passed. |

### Readiness

The original High false-negative defect is corrected, but PR #2 is not ready to merge while
the self-check still permits silent over-constraint and the current-truth note still denies
the implemented T-001 entry-point scaffold. Both remaining corrections are small and stay
inside `T-024`; focused re-review is still required.

## Open findings

- `T005-R1`, `T005-R3` — remaining corrections tracked by `T-024`

## 2026-07-25 — Phase 0 exit review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-001`, `T-002`, `T-003`, `T-004`, `T-005`, `T-006`, `T-007`,
`T-020`, `T-022`, `T-023`, `T-024`, `T-025`; proposed `OPS-004`
**Base:** `158057661196adfe2730c820c6898724e446c116`
**Head:** `adb25f81019916849933c7b36091514f8d9db259`
**Platforms verified:** Linux locally; Windows from retained check, frozen-build, and desktop
spike artifacts
**Verdict:** Changes requested

### Prior finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T005-R1` | Resolved | The final set-equality guard closes both former bypasses. Narrowing the core predicate to the two old fixture paths now yields 10 failures; adding `downloader/environment.py` as a third owner yields 3; adding allowed `typing` to `QT` yields 8. The restored layering suite passes all 109 cases and a real `PySide6` import in `core/models.py` fails the exact production-path assertion. |
| `T005-R3` | Resolved | At the correction head, the replacement accurately separated the T-001 entry-point scaffold from unimplemented product behavior and counted 30 modules as 27 stubs plus 3 code modules. Later T-007/T-020 work made that exact snapshot stale; that new coordination drift is `P0-R8`, not a failure of the T-024 correction at its reviewed boundary. |

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `P0-R1` | **Medium** | T-007 geometry restore | `src/tracks_and_trails/ui/main_window.py:58-80` promises `load_geometry()` never raises but accepts TOML numeric forms beyond Qt's geometry domain. `x = inf` raises `OverflowError` during `int()`; `x = 1e100` and `x = 9223372036854775808` reach `setGeometry()` at line 173 and raise a shiboken 32-bit overflow. Ordinary but stale multi-monitor coordinates are also never checked for intersection with an available screen, so the only window can restore invisibly. The eight cases at `tests/ui/test_main_window.py:107-137` miss this class. | Validate types and Qt integer bounds, catch conversion overflow, and clamp or relocate geometry that intersects no screen. Pin `inf`, huge integer/float, boolean, and off-screen cases. | Open — `T-027` |
| `P0-R2` | **Low** | T-007 Qt threading | `tests/ui/test_app_launch.py:21-47` says both cross-thread calls are documented thread-safe. Qt 6.11 documents `QMetaObject::invokeMethod()` and `QCoreApplication.quit()` as thread-safe, but does not give that guarantee to `QCoreApplication::instance()`. The watcher polls `QApplication.instance()` concurrently with application construction, recreating a smaller undocumented race in the harness that already proved unstable once. It also ignores the boolean result of `invokeMethod()`. | Drive shutdown using only a documented thread-safe API, propagate a failed request, and repeat the launch test on both platforms. | Open — `T-028` |
| `P0-R3` | **Medium** | T-020 negative gate | `ai/TASKS.md:289-290` explicitly requires removing `freeze_support()` to fail on Windows. The implementation record at lines 325-337 records only a Linux mutation. Positive Windows evidence proves the current build works; it does not prove the detector turns red on the platform named by the acceptance criterion. The reviewer repeated the Linux mutation: the smoke exited 1 after 120.4 s and recorded 4 starts, including `--multiprocessing-fork` and both resource-tracker invocations. | Run and retain the same deliberate mutation in Windows CI, restore it, and re-run both final frozen jobs. | Open — `T-029` |
| `P0-R4` | **Low** | T-020 frozen-child proof | `_freeze_probe.py:94-112` prints that the parent and child are frozen but never asserts either value. Both retained platform artifacts happen to report `True`; a future configuration that starts the target in an external interpreter could still exchange the message and pass, weakening `REL-001`'s self-contained-process claim. | Make the frozen smoke fail unless both values are exactly true while preserving any intentionally supported source-mode diagnostic separately. | Open — `T-029` |
| `P0-R5` | **Low** | T-020 retained evidence | `packaging/frozen_smoke.py:88` writes `dist/frozen-probe.log`, while `.github/workflows/ci.yml:193-200` uploads root-level `frozen-probe.log`. The downloaded Windows frozen artifact contains only the three `reports/` files; the raw log is absent. `frozen-smoke.txt` does repeat the start lines, so the diagnostic is retained indirectly and this is not evidence loss. | Upload the actual path or remove the redundant path and state that `frozen-smoke.txt` is canonical. | Open — `T-029` |
| `P0-R6` | **Low** | Architecture truth | The two implementation calls are technically sound: ephemeral geometry belongs in a separate UI-owned TOML file, and an in-package probe is necessary to exercise the real `__main__.py` ordering; the environment-gated marker is acceptable same-user diagnostic code. But the implementer explicitly left both “reported, not decided.” `ARCHITECTURE.md:128-169` omits `_freeze_probe.py`, and the §5 ownership table at lines 173-179 omits `window.toml`, so canonical architecture no longer describes the approved tree or its first real filesystem write. | Have the Planner ratify both current choices in §4/§5/§12; no source redesign or durable decision entry is needed. | Open — `T-030` |
| `P0-R7` | **Medium** | Proposed OPS-004 | The retained spike supports the premise: real `windows` plugin, 1024×768 screen, native visible HWND/title, and a nonblank 960×640 capture. UI Automation is also an appropriate objective test surface. `OPS-004` is not acceptable as written, though. `OPS-003` lists native dialogs and open/reveal behavior at `ai/DECISIONS.md:609-615`; they appear in neither `OPS-004`'s automated list nor its remaining-human list at lines 437-448, yet its consequence would shrink the manual list to that residue. `T-026:160-162` also says a broken layout need only be visible in an artifact while its note claims every weakening fails a gate. | Restore an explicit owner for native dialogs/open/reveal; distinguish screenshot evidence from a red/green assertion; shrink the manual list only as replacements land. Then accept the corrected decision and run T-026. | Open — `T-031` |
| `P0-R8` | **Low** | Current truth | Phase-exit coordination is internally stale. `STATUS.md:65-71` still asks to merge and then run completed T-020/T-025; lines 124-138 call T-007/T-005 “in review,” describe the removed placeholder `app.run`, and state 30/27/3 when the head has 31 Python modules, 26 stubs, and 5 code modules. `TASKS.md:15-23` says nothing is Ready while placing Complete T-007 and Proposed T-026 under Ready. `TESTING.md:13-16` still says only skeleton structural tests exist. | Reconcile navigation, statuses, exact counts, and the coverage status note after the correction tasks settle. | Open — `T-032` |

### Exit criteria

| Criterion | Reviewer result |
|---|---|
| Local and CI lint, format, types, tests | **Met with an evidence-access caveat.** Current local checks pass. Retained Windows check evidence passes at the T-007 code boundary, retained Windows frozen evidence exercises the only later source addition, and only documentation changed after `41e9f6e`. The local `gh` credential is expired, so the reviewer could not freshly query the final `adb25f8` run. |
| Deliberate Qt import in `core/` fails | **Met.** `core/models.py` injection: 1 failed, 108 passed, naming the file and rule; restored hash matched. |
| Clean-checkout Linux window launch | **Met.** A 73-file tracked-only archive launched with the real Linux platform plugin, exited 0 with empty stderr, and wrote redirected geometry. T-025 separately records the full clean environment setup. |
| Clean-checkout Windows window launch | **Not met.** Offscreen UI tests and the frozen `--spawn-probe` path are not the documented end-user launch. The spike constructs `MainWindow` directly rather than exercising `python -m tracks_and_trails` from the documented setup. `OPS-004` makes this automatable; it does not supply the missing evidence retroactively. |
| Frozen child without relaunch, both platforms | **Met for the positive behavior.** Current Linux build: one start, frozen parent/child, exit 0, no orphan. Retained Windows build: the same, 128 MB, build 56 s, smoke 3 s. `P0-R3` remains an unmet T-020 negative acceptance criterion. |
| `LIC-001` Accepted and `LICENSE` exists | **Met.** `LIC-001` is Accepted; root `LICENSE` is MIT with the 2026 Sean Kottman copyright; project metadata says MIT. |

### Review judgments

- **Phase exit:** No. The Windows documented launch criterion is genuinely unmet. The open
  Medium corrections `P0-R1`, `P0-R3`, and `P0-R7`, plus their dependent evidence and
  coordination work, also prevent sign-off.
- **OPS-004:** Changes requested, then accept. The objective/subjective distinction is sound
  and the spike proves the runner can host meaningful GUI automation. The current text must
  not silently retire native-dialog/open/reveal verification.
- **T-007 design call:** Keep `window.toml`; it is disposable UI state, not a user-authored
  setting. Ratify its owner and location in architecture.
- **T-020 design call:** Keep `_freeze_probe.py` and the environment-gated start marker. A
  separate entry point would evade the ordering under test. Document the infrastructure
  exception and finish its negative/evidence assertions.
- **Orphan scope:** The resolved-executable scan catches this probe's child and resource
  tracker because frozen multiprocessing re-executes the same binary. A descendant that
  explicitly executes another image can escape, but no current probe path does that; Phase 1
  must test the real worker/ffmpeg process tree rather than making T-020 simulate future work.
- **Coverage honesty:** The count is 158, but its profile is 109 layering cases (69%), 23
  resource cases, 22 shell-window cases, and 4 skeleton cases. Nothing downloads, parses
  media, persists jobs, or exercises a real worker. Exactly one of `TESTING.md` §7's ten
  mandatory areas is covered. Section 12 states that boundary honestly; the stale header and
  raw count should not be read as broad behavioral coverage.

### Checks run

| Check | Result |
|---|---|
| Working boundary | Started at clean `main` `adb25f8`; base/head diff is 67 files, 3,370 insertions, 145 deletions. Review mutations were restored by SHA-256; only this review's coordination edits remain. |
| `git diff --check 1580576 adb25f8` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 58 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `pytest -q` | Passed: 158 passed, 1 deselected in 0.75 s. |
| Geometry adversarial values | `inf` raised in `load_geometry`; `1e100` and `9223372036854775808` reached Qt and raised `OverflowError`, reproducing `P0-R1`. |
| T005 historical bypasses | Narrow core: 10 failed/99 passed. Add `typing`: 8 failed/101 passed. Add third owner: 3 failed/106 passed. Restored baseline: 109 passed; hash `a2324a26...bff62`. |
| Layering production mutation | Added `import PySide6` to `core/models.py`: 1 failed/108 passed. Restored hash `ba3e24c...09cf`. |
| Clean tracked-only launch | 73 archived files; real Linux Qt plugin; exit 0; empty stderr; redirected `window.toml` written. |
| Frozen positive, Linux | 284 MB; build about 15 s; spawn 0.3 s; one top-level start; parent/child frozen; no orphan. |
| Frozen negative, Linux | With `freeze_support()` commented and rebuilt: exit 1 after 120.4 s; 4 starts with multiprocessing argv. Restored `__main__.py` hash `e085dd5b...b95`, rebuilt positive, and confirmed no process remained. |
| Frozen retained evidence, Windows | Windows Server 2025 / Python 3.14.6; 128 MB; build 56 s; smoke 3 s; one start; frozen parent/child; message and exit 0; no orphan. Artifact confirms `P0-R5` because the raw log is absent. |
| OPS-004 spike evidence | Retained output and 960×640 PNG confirm real `windows` plugin, HyperVMonitor, native visible HWND/title, and nonblank capture. |
| Final CI query | Not run: the installed `gh` credential reports invalid. Retained artifacts were inspected directly; final status was not accepted solely from the handoff. |

### Readiness

Phase 0 is not approved for exit. Complete `T-027` through `T-032`, correct and decide
`OPS-004`, then use the resulting real-plugin Windows job to exercise the documented
application launch from a clean checkout. Re-review the focused correction boundary before
advancing Phase 1.

## 2026-07-25 — Phase 0 exit corrections focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-027` through `T-032`; corrected `OPS-004`; PR #7
**Base:** `adb25f81019916849933c7b36091514f8d9db259`
**Head:** `67da109bc8de8bb02ecbd582b9d2e27710e3e981`
**Platforms verified:** Linux locally; Windows from GitHub Actions runs and retained artifacts
**Verdict:** Changes requested

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `P0-R1` | **Open** | The hostile TOML type/range cases are rejected, and ordinary off-screen coordinates are recovered. Exact signed-32-bit coordinates still defeat `QRect.intersects()`: with `x = -2147483648`, `y = 2147483647`, width 640 and height 480, Qt reports an intersection with the 800x800 offscreen display after edge arithmetic wraps, and `MainWindow` restores the unreachable rectangle unchanged. `test_int32_boundary_values_are_accepted` checks only `load_geometry()`, not restoration. Also, the new `nan-x` case already passes at the base, contrary to the comment and criterion saying every new adversarial case failed there. |
| `P0-R2` | **Resolved** | The foreign watcher thread is gone. `showEvent()` schedules a zero-delay timer on the GUI thread, the callback checks the live application and quits it, timeout diagnostics retain subprocess output, and the test asserts `WINDOW-SHOWN` before `QUIT-REQUESTED`. The launch test passed 50 consecutive local runs and both final Windows check runs. |
| `P0-R3` | **Resolved** | Run `30186080950` is at the temporary mutation commit `a4c7214`. Its Windows frozen smoke step failed after 120.2 s and the retained raw log contains two top-level starts, including `--multiprocessing-fork parent_pid=3344 pipe_handle=608`. Commit `10bae7e` exactly restores `__main__.py`; restored run `30186222977` and final head run `30186320675` are green on both platforms. |
| `P0-R4` | **Resolved** | The smoke script now rejects either parent or child `frozen=False`. Direct injection produced exit 0 only for true/true and `SystemExit(1)` for false/true and true/false. Final Windows evidence reports both true. |
| `P0-R5` | **Resolved** | The workflow uploads `dist/frozen-probe.log`. The downloaded negative, restored-positive, and final artifacts all contain the raw log at that path; the final Windows log records exactly one start. |
| `P0-R6` | **Open** | The two design calls are now represented in architecture and remain approved in substance. The new text is self-contradictory, though: §4's structure now lists `_freeze_probe.py`, while §12 says it is “deliberately outside §4's structure”; the module docstring still says it is absent from §4. It is outside the product *layers*, not outside the documented structure. |
| `P0-R7` | **Open** | The corrected decision assigns native dialogs/open/reveal, keeps subjective behavior manual, and makes screenshots evidence rather than a gate. `T-026` still ends by saying “Each criterion above is therefore stated as a mutation that must fail,” contradicting its screenshot criterion. More importantly, `OPS-004` remains `Proposed — needs maintainer acceptance`, so `T-031`'s explicit accept/reject criterion is not met. The reviewer accepts the corrected substance; the canonical decision status still needs the maintainer's explicit action. |
| `P0-R8` | **Open** | Counts and the placeholder description were corrected, but current truth remains inconsistent. `TASKS.md` says T-027–T-032 are Ready and files their `In Review` entries under `## Ready`; `STATUS.md` says seven findings although the review has eight, says only `main` exists while PR #7 is active, and still calls completed T-007 and T-005 “in review.” This is the exact heading/status/stale-state class T-032 was meant to close. |

### Remaining findings

| ID | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| `P0-R1` | **Medium** | Geometry recovery | Signed-32-bit membership is not sufficient to make Qt rectangle intersection safe. Boundary coordinates can wrap Qt's derived edges, be misclassified as visible, and restore the only window off-screen. | Compute intersection with Python integer arithmetic before constructing/consulting `QRect`, or reject a narrower geometry domain whose derived edges are safe. Exercise `MainWindow`, not only `load_geometry`, at all four coordinate boundaries. Correct the base-failure claim for `nan`. |
| `P0-R6` | **Low** | Architecture truth | The architecture and module docstring simultaneously list the probe in §4 and say it is not there. | Say it is a top-level infrastructure module outside the product layers, and make the source docstring agree. |
| `P0-R7` | **Low** | OPS-004 / T-026 | The correction is substantively acceptable, but its task-level mutation claim still overstates the screenshot gate and the decision remains formally Proposed. | Narrow the final T-026 note to objective assertions, then have the maintainer mark `OPS-004` Accepted or Rejected explicitly. |
| `P0-R8` | **Low** | Current truth | T-032 still leaves status headings and several exact current-state claims stale. | Reconcile the named TASKS/STATUS lines against the actual PR and the eight-finding review before marking T-032 complete. |

### Checks run

| Check | Result |
|---|---|
| PR boundary and final CI | PR #7 is open and mergeable at the exact reviewed head. Both final push and pull-request workflows are green: Linux, Windows, frozen Linux, and frozen Windows. |
| `git diff --check adb25f8..67da109` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 58 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `pytest -q` | Passed: 172 passed, 1 deselected in 0.79 s. |
| T-028 repetition | Real launch/quit test passed 50/50 consecutive local subprocess runs. |
| T-027 base replay | Base rejects `nan` already; the other new hostile values and off-screen case reproduce their claimed old failures. |
| T-027 boundary replay | Current head restores exact int32-extreme rectangles unchanged because Qt reports a false intersection after coordinate wrap. No exception or Qt warning is emitted, so the existing suite misses it. |
| T-029 Windows negative | Downloaded run `30186080950`; frozen Windows failed at the smoke step, and `dist/frozen-probe.log` contains two starts with Windows multiprocessing argv. |
| T-029 restored/final positive | Downloaded runs `30186222977` and `30186320675`; both platform matrices pass, both raw logs are retained, and each final frozen log records one start with frozen parent/child and no orphan. |
| T-029 frozen-flag injections | true/true returned 0; false/true and true/false each exited 1. |

### Readiness

PR #7 is not approved at this head. `P0-R1` is still a functional Medium finding, and
`P0-R6`–`P0-R8` are small but direct failures of their correction criteria. Phase 0 also
still cannot exit while its documented Windows launch criterion remains unmet. When the
remaining corrections are complete, squash merge is the appropriate strategy because this
branch intentionally contains the broken `freeze_support()` proof commit.

## 2026-07-26 — T-010 domain models, state machine, and error taxonomy

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-010`
**Base:** `c8651676ca5ab62e825eb03dc73d9e4e79cdc74a`
**Head:** `eb0b4c8a1cb292e989dcd48f881d37b2cee2377f`
**Implementation commit:** `1f1263dcfbe9bf7da30088cee5457173254bcd5f`
**Platforms verified:** Linux locally; the handoff reports green Linux and Windows CI, but the
reviewer could not query those private runs because the installed `gh` credential is invalid
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T010-R1` | **High** | State-machine anti-vacuity | The exhaustive illegal-transition test asks `can_transition()`—the production table itself—which pairs are illegal before asserting that `apply()` rejects them. It therefore proves that two views of the same table agree, not that the table matches `ARCHITECTURE.md` §5. Adding the undocumented `QUEUED → READY` edge left all 48 state/model tests green. This is exactly the silent state-corruption class `TESTING.md` §7 makes mandatory. | Put the complete architecture-derived transition relation in the test, independent of `_TRANSITIONS`, and check all 81 ordered pairs against it through `allowed_from()`, `can_transition()`, and `apply()`. Retain the new-status coverage guard. | Open |
| `T010-R2` | **Medium** | Cross-process immutability | `FailureDetail` is declared frozen and described as an immutable cross-process record, but `context` is a mutable `dict`. `failure.context["exit_code"] = "0"` succeeds. This matters for an IPC value: `multiprocessing.Queue` may serialize on its feeder thread after `put()`, so a post-put mutation can change what crosses the boundary. The current immutability test reassigns `kind` only and misses nested mutation. | Store context in a genuinely immutable, picklable representation and test both mutation rejection and pickle round-trip. | Open |
| `T010-R3` | **Low** | State semantics / task truth | `FAILED` is deliberately non-terminal, yet the acceptance criterion says `CANCELLED` is reachable from every non-terminal state. The test silently excludes `FAILED`, and production correctly permits only `FAILED → QUEUED`. Adding `FAILED → CANCELLED` would be the wrong fix: cancellation stops active work, a failed job has none, and `REQ-015`'s remove action is deletion rather than a lifecycle transition. | Keep the production transition unchanged. Have the Planner replace “every non-terminal state” with an explicit in-flight/cancellable set and distinguish retryable from actively cancellable states. | Open |
| `T010-R4` | **Low** | Model contract / task truth | The acceptance criterion says a `Job` without an explicit status fails construction, while `Job.status` defaults to `QUEUED` and the tests affirm that default. A new job always having a valid queued status is a reasonable API, but the task currently records the opposite contract. | Keep the default unless a caller genuinely needs to distinguish omitted from queued; have the Planner amend the criterion to require a non-null valid status that defaults to `QUEUED`. Correct “ten kinds” to eleven in the same Planner pass. | Open |

### Review judgments

- `FAILED` should remain non-terminal because retry is a real outgoing transition; it is not
  an actively cancellable state.
- `Job.progress is None` when total size is unknown is correct. Zero would conflate unknown
  progress with known zero progress.
- `classify()` should not infer policy-bearing kinds from message substrings. Mapping typed
  yt-dlp failures at the adapter seam is the safer boundary.
- Implementing eleven `ErrorKind` members is correct: §7 has ten rows but names eleven kinds.
  This is a task-wording correction, not a reason to collapse ffmpeg failures.

### Checks run

| Check | Result |
|---|---|
| Bounded review | Clean `main` at exact head `eb0b4c8`; base/head diff is 17 files, 2,020 insertions and 151 deletions. |
| Focused T-010 baseline | Passed: 65 tests across `test_models.py`, `test_job_state.py`, and `test_errors.py`. |
| Invalid transition mutation | Added `QUEUED → READY`; **48 state/model tests still passed**, reproducing `T010-R1`. Mutation was restored and the file returned to the committed diff. |
| Failed cancellation probe | `is_terminal(FAILED)` returned false; `apply(FAILED, CANCELLED)` raised `IllegalTransitionError`, while the acceptance test excludes `FAILED`. |
| Failure context probe | Mutating `FailureDetail.context["exit_code"]` from `"1"` to `"0"` succeeded, reproducing `T010-R2`. |
| Layering | The full default suite includes the architecture-derived layering cases and passed; no Qt or yt-dlp import was added to `core/`. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 64 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 49 source files. |
| `pytest -q` | Passed: 243 passed, 2 skipped, 1 deselected in 0.42 s. |
| `git diff --check c865167..eb0b4c8` | Passed. |

### Readiness

The production transition relation and taxonomy are substantively sound, but `T-010` is not
ready for dependent Phase 1 work while its mandatory state-machine gate can be weakened by
adding illegal edges. Fix `T010-R1` and the mutable IPC record, reconcile the two task-contract
wordings, then perform a focused re-review.

## 2026-07-26 — T-026 real Windows desktop verification

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-026`; accepted `OPS-004`
**Base:** `c8651676ca5ab62e825eb03dc73d9e4e79cdc74a`
**Head:** `eb0b4c8a1cb292e989dcd48f881d37b2cee2377f`
**Platforms verified:** Linux static review and local collection behavior; Windows run
`30208677607` and screenshots were reported in the handoff but could not be independently
queried or downloaded because the installed `gh` credential is invalid
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T026-R1` | **High** | Phase 0 clean-launch gate | The dedicated job runs only tests marked `windows_desktop`. Those tests construct `MainWindow` inside pytest; they do not exercise `tracks_and_trails.app.run`, the console/module entry point, argument handling, or a fresh application event loop. The existing end-to-end launch test is unmarked, excluded by `-m windows_desktop`, and hard-codes `QT_QPA_PLATFORM=offscreen`. Native `HWND` evidence proves that a widget can be constructed, but not the still-documented exit criterion: the application launches on Windows from a clean checkout following `docs/DEVELOPMENT.md`. This is the same distinction the prior Phase 0 review explicitly recorded. | Add a subprocess launch through the real application startup path under the inherited `windows` plugin, with deterministic GUI-thread shutdown and a positive shown-window marker. Select it in the dedicated job and keep the independent Win32 HWND/title assertions. Do not record the Phase 0 criterion as met until that test is green. | Open |
| `T026-R2` | **High** | Accessibility anti-vacuity | The UI Automation tests do not pin every interactive control and role as claimed. They require a window, some menu bar, some non-empty menu items, and the names `File` and `Help`. `Quit` and `About Tracks & Trails` are not required, so either action can disappear or be published under a wrong role while the checks remain green. The About dialog is never opened, leaving its Close control wholly outside the queried tree. `REQUIREMENTS.md` §3 and `TESTING.md` §9/§10 therefore retired the manual name/role gap too broadly. | Compare the current UIA tree with an explicit expected name/role contract for the window, menu bar, File, Quit, Help, and About action. Open the About dialog and assert its window and Close control separately. Include removal, empty-name, and wrong-role mutations before narrowing the current-truth claims again. | Open |
| `T026-R3` | **Medium** | Incomplete acceptance criterion | Deferring widget tab order is correct today—zero focusable widgets would make a theatrical test—but it leaves an explicit T-026 acceptance criterion unmet while the task is treated as completed. `T-016` mentions a deliberate tab order but does not explicitly require extending the real-Windows `windows_desktop` gate or prove that reordering two controls fails there; `T-017` does not mention tab order. Unlike the installer gap, there is no concrete split task. | Keep the vacuous assertion out now. Either keep this criterion open or split it into a concrete follow-up that explicitly extends the Windows real-plugin suite when `T-016`/`T-017` add focusable controls. | Open |
| `T026-R4` | **Low** | Windows-test type gate | The mypy override is tightly scoped to the two Windows test modules, but those modules have no effective type-checking path. Bare mypy on Linux treats their post-guard code as unreachable; the Windows `check` job runs only `mypy src`; and the dedicated desktop job runs no mypy. A deliberate `int = "not an int"` after the platform guard passed bare mypy locally, while `mypy --platform win32` caught it. | Run bare mypy, or a Windows-platform explicit test target, in the Windows desktop job. Keep the override module-scoped, but let Windows analyze the reachable bodies. | Open |
| `T026-R5` | **Low** | Current truth / coordination | The changed coordination set remains internally stale. `TESTING.md` still says the suite is near-empty and only one §7 area is covered, and its §12 Windows paragraph still says real keyboard and screen-reader behavior are wholly unverified under superseded `OPS-003`. `TASKS.md` files both implemented, awaiting-review tasks under `Ready` while `In Review` is empty. `STATUS.md` gives the review head as `697e024` rather than `eb0b4c8` and retains the nonexistent `/mnt/storage/...` repository path. | Reconcile the status note, §12, task headings, exact review boundary, and repository path after the functional gates are corrected. | Open |

### Review judgments

- The `addopts` exclusion is acceptable because the dedicated opt-in exists. On Linux,
  `pytest -m windows_desktop` collected no runnable desktop tests and exited 5, so a marker
  selection that collects none does fail rather than pass.
- Explicitly setting `QT_QPA_PLATFORM=windows` is equivalent to removing the offscreen
  override for this purpose, and the platform-name assertion protects that assumption.
- Screenshot assertions are correctly limited to capture-pipeline evidence, not visual
  correctness. The PNG content must not become a red/green layout gate without a separate
  decision. The reviewer could not inspect the retained images in this pass.
- Splitting installer automation into `T-039` is correct, and native dialog/shell behavior
  remains tracked under the objective/subjective split in `OPS-004`.
- Editing `REQUIREMENTS.md` §3 was within the explicit T-026 acceptance surface after the
  maintainer accepted `OPS-004`; the defect is that the resulting claim outruns `T026-R2`,
  not that the Implementer touched the file.

### Checks run

| Check | Result |
|---|---|
| Workflow selection review | `windows-desktop` sets the real plugin but invokes only `pytest -m windows_desktop`; the end-to-end startup module is unmarked and forces offscreen. |
| Accessibility contract review | The queried tree never includes the About dialog; only `File` and `Help` are required by name, and filtering by `UIA_MENU_ITEM` cannot detect a missing/mis-typed Quit or About action. |
| Desktop collection guard, Linux | `pytest -q -m windows_desktop` reported 2 skipped and 244 deselected, then exited 5. The no-tests guard works. |
| Mypy suppression mutation | A deliberate post-guard incompatible assignment passed bare mypy on Linux; `mypy --platform win32 tests/ui/test_windows_desktop.py` reported the assignment error. Mutation was restored. |
| Screenshot source review | Main-window capture asserts save/file/nontrivial size; About capture asserts save/file. No assertion evaluates visual content, so screenshots are not accidental layout gates. |
| Local required checks | `ruff check .`, `ruff format --check .`, `mypy src`, bare `mypy`, and `pytest -q` all passed with the results recorded in the T-010 entry above. |
| Windows CI/artifacts | Not independently checked: `gh auth status` reports the configured `kottmans` token invalid. The handoff reports run `30208677607` green with 15 tests and native HWND/title evidence. |

### Readiness

T-026 is not approved, and Phase 0's clean-checkout Windows launch criterion remains
unverified at this head. The real-plugin job is a strong foundation, its marker/skip guards
are meaningful, and the screenshot evidence is correctly classified. It still needs an
end-to-end startup assertion, a non-vacuous complete accessibility contract, and a concrete
owner for the deferred tab-order gate, followed by focused Windows re-review.

## 2026-07-26 — T-010 and T-026 final focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-010`, `T-026`; dispositions for `T010-R1`–`T010-R4` and
`T026-R1`–`T026-R5`
**Base:** `eb0b4c8a1cb292e989dcd48f881d37b2cee2377f`
**Head:** `8e5f9a6f6d11facf7b67d057c3d3c915e2cacaf0`
**Platforms verified:** Linux locally; Windows run `30210954363` was reported green with
19 desktop tests, but the reviewer could not independently query or download it because the
installed `gh` credential remains invalid
**Verdict:** `T-010` — **Approved** · `T-026` — **Changes requested**

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T010-R1` | **Resolved** | `EXPECTED` is independent of production and covers every `JobStatus`. The reviewer's original `QUEUED → READY` mutation now fails both `test_production_matches_the_architecture_relation_exactly` and `test_every_ordered_pair_agrees_with_the_architecture`: 2 failed, 40 passed. |
| `T010-R2` | **Resolved** | Context is normalized to a sorted tuple of string pairs; both the tuple and `context_map` reject writes, and pickle restores an equal immutable value. The runtime validation also rejects malformed non-string pairs. |
| `T010-R3` | **Resolved** | The task now names the exact cancellable states, and the tests pin `CANCELLABLE` by equality. `FAILED` remains retryable only through `QUEUED`, with the reviewer-approved semantics preserved. |
| `T010-R4` | **Resolved** | The acceptance criterion now says status defaults to valid `QUEUED`, and the taxonomy criterion says eleven kinds. The older “reported, not decided” paragraph remains stale, but that is current-truth cleanup under `T026-R5`, not an unresolved model contract. |
| `T026-R1` | **Resolved** | The new test starts a fresh interpreter, invokes `app.run`, creates its own `QApplication` and event loop under the `windows` plugin, probes Win32 only after a zero-delay event-loop turn, and asserts native handle, visibility, title, clean exit and clean stderr. Reported Windows CI is green. |
| `T026-R2` | **Open** | The popup-menu equalities are a real improvement, and leaving `TitleBar`/`MenuBar` containers unnamed is acceptable. The overall contract is still not an equality. The main-window checks pass with only Windows' native System menu bar/items—no `File` or `Help` header—and the About check passes when its only button is the native title-bar `Close`. Therefore a missing/mis-roled application menu bar or missing QMessageBox Close button can still leave the suite green. |
| `T026-R3` | **Resolved** | `T-040` is a concrete blocked task tied to the first focusable controls. It explicitly extends the existing real-plugin suite and requires a demonstrated reorder mutation before retiring the gap. No vacuous test was added now. |
| `T026-R4` | **Resolved** | The desktop job runs config-scoped `mypy --platform win32`. A fresh deliberate post-guard `int = "not an int"` mutation is caught as one assignment error across the 49-file scope and was restored. |
| `T026-R5` | **Open** | Task placement, §7 coverage count, and repository path were corrected, but current truth is not reconciled. `ai/TESTING.md` now has a duplicate Windows-desktop section at lines 1–35 before its document title and again in §10; its update metadata remains 2026-07-25. `STATUS.md` still says CI forces offscreen and does not use the real desktop, contradicting the dedicated job. `TASKS.md` still says the ten-kind wording “needs correcting” directly above the corrected eleven-kind criterion. |

### Remaining findings

| ID | Severity | Area | Finding | Recommendation |
|---|---|---|---|---|
| `T026-R2` | **High** | Accessibility anti-vacuity | The test does not distinguish the application menu bar from Windows' System menu and does not distinguish the About content button from the native title-bar Close button. The current `REQUIREMENTS.md` and `TESTING.md` claims still outrun the gate. | Require `File` and `Help` with `MenuItem` roles in the main-window tree and identify the application menu-bar contract independently of the System menu. For About, require the content Close control in addition to title-bar furniture—an exact multiset/count or richer node identity/hierarchy is sufficient. Re-run missing/wrong-role mutations on Windows. |
| `T026-R5` | **Low** | Current truth / coordination | The finding response introduced a duplicated pre-header section and retained contradictory task/status statements. | Remove the stray pre-header copy, retain the corrected §10 subsection once, update document metadata, correct the Windows-environment row, and delete the obsolete ten-kind paragraph. |

### Review judgments

- An unnamed `MenuBar` or `TitleBar` container is not itself an `NFR-005` defect. Containers
  can be announced by role while their operated children carry names. The remaining finding
  is identity and coverage, not a demand to invent labels Windows or Qt does not expose.
- Excluding Windows' System menu and checking title-bar buttons separately is the right model.
  The application-owned controls still need assertions that cannot be satisfied by that
  excluded furniture.
- Moving the visibility probe from `showEvent` to a zero-delay timer is correct: it observes
  the mapped window after the event loop starts rather than asserting premature visibility.
- `T-040` is an adequate split of the currently impossible tab-order criterion. It remains a
  named gap and does not block the Phase 0 launch evidence.

### Checks run

| Check | Result |
|---|---|
| Correction boundary | Clean `main` at exact head `8e5f9a6`; correction diff is 12 files, 1,023 insertions and 334 deletions. All temporary mutations were restored. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 64 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 49 source files. |
| `mypy --platform win32` | Passed: no issues in 49 source files. |
| `pytest -q` | Passed: 242 passed, 2 skipped, 1 deselected in 0.44 s. |
| Focused T-010 baseline | Passed: 64 model, state and error tests. |
| T010 transition mutation | Added `QUEUED → READY`: failed the two independent architecture assertions; 40 other state/model tests passed. Restored. |
| T010 context probe | Tuple and read-only mapping writes raised; pickle produced an equal immutable copy. |
| T026 type mutation | A post-guard incompatible assignment failed `mypy --platform win32` with exactly the intended assignment error. Restored. |
| T026 accessibility adversarial harness | A fabricated main tree containing only an unnamed native menu bar, `System`, and title-bar buttons passed both main-tree guards. A fabricated About tree whose only button was the native title-bar `Close` passed `test_the_about_dialog_and_its_close_button_are_announced`. This reproduces the remaining anti-vacuity holes without needing to emulate UI Automation itself. |
| Desktop collection guard, Linux | `pytest -q -m windows_desktop` reported 2 skipped and 243 deselected, then exited 5. |
| `git diff --check eb0b4c8..8e5f9a6` | Passed. |
| Windows CI/artifacts | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30210954363` and all five jobs green, with 19 desktop tests. |

### Readiness

`T-010` is approved and ready to unblock its Phase 1 dependents. `T-026` is not approved:
`T026-R1`, R3 and R4 are genuinely resolved, but the accessibility gate can still pass without
the application-owned controls it claims to pin, and its current-truth cleanup is incomplete.
Because Phase 0 requires independent sign-off, it should not be recorded as formally exited
at this head. This is the requested final re-review; no further verification is implied by
this entry.

## 2026-07-26 — T-011 IPC message contract

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-011`
**Base:** `831a726fcbb11427caa3645b3318457ca2d158c5`
**Head:** `bd794186470a5b511246c360b691db56f76be9aa`
**Platforms verified:** Linux locally; Windows CI run `30212659385` was reported green in the
handoff, but the reviewer could not independently query it because the installed `gh`
credential is invalid
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T011-R1` | **High** | Probe outcome semantics | A successful probe has no terminal outcome under this contract. `T-012` runs one probe or one download; the natural successful probe sequence is `Probed`, then `WorkerFinished`. Neither is terminal, so `is_terminal()` counts zero. `T-013` simultaneously requires a worker exiting 0 without a terminal message to become `WORKER_CRASH`. As written, the planned receiver either misclassifies every successful probe or special-cases a rule the protocol does not express. Keeping `WorkerFinished` separate from the job outcome is correct; success/failure is not the only outcome distinction the receiver needs. | Specify complete legal sequences for probe success/failure and download success/failure. Give the receiver an explicit way to recognize a successful probe outcome—such as a separate outcome predicate/type distinction or a documented probe-session rule—while retaining `WorkerFinished` as clean stream completion. Test every sequence and the missing/duplicate/out-of-order cases before T-012 consumes the contract. | Open |
| `T011-R2` | **High** | Runtime boundary validation / immutability | The runtime contract validates only the outer class. `Probed(job_id="j", media={"formats": []})` is accepted by both its constructor and `is_message()`, pickles with the raw dict intact, and directly violates `ARC-002`'s load-bearing projection rule. A string stage and string failure kind are also accepted. `Failed.context` accepts a dict and remains mutable after construction, reproducing the exact feeder-thread race `T010-R2` fixed. Finally, `isinstance(candidate, MESSAGE_TYPES)` accepts an undeclared subclass even though the contract says only declared types cross. The positive projection and tuple-sample tests do not exercise any of these rejection paths. | Validate payload types and nested immutable shapes in `__post_init__` (or reuse a fully validated `FailureDetail`), and make declared-type validation exact rather than subclass-based if “declared” is the invariant. Add negative tests for a wrapped raw dict, wrong enum types, mutable/malformed context, and an undeclared subclass; pickle the rejected/adversarial cases where relevant. | Open |
| `T011-R3` | **Medium** | Required-field API | The runtime and type-level contracts disagree. `Probed.media` and `Failed.kind` are typed optional and default to `None`; `Succeeded.output_path` and `Failed.message` default to invalid empty strings. Their constructors reject those defaults only after construction starts. More importantly, `Progress.stage` silently defaults to `PROBING`, so forgetting the required stage creates a valid but false progress report. The public signatures therefore advertise optional fields that the task calls required and conceal an omission that changes meaning. | Use keyword-only dataclasses (or another inheritance shape) so required payloads have no defaults and honest non-optional annotations. Make `Progress.stage` required. Keep runtime validation as protection against `Any` and deserialized/untyped inputs. | Open |
| `T011-R4` | **Medium** | Terminal-once ownership | The rule is not completely ownerless: the T-011 entry explicitly assigns enforcement to `T-013`, which is the right layer. However, T-013's own scope and acceptance criteria never require rejecting or reporting a second terminal outcome for the same job. It can currently meet every listed criterion without implementing the promised terminal-once rule. | Add an explicit T-013 acceptance criterion and test: after one outcome for a job ID, a second success/failure outcome is a protocol violation and cannot produce a second state transition or signal. Tie it to the protocol predicate after `T011-R1` resolves the meaning of probe outcomes. | Open |
| `T011-R5` | **Low** | Accepted-decision consistency | Accepted decision `ARC-002` says the IPC protocol is a “versioned internal contract.” The T-011 task and module instead say “No protocol versioning, deliberately.” Avoiding runtime negotiation between two ends of one artifact is reasonable, but that narrower claim does not resolve the direct authority conflict over whether the contract is versioned. | Clarify whether `ARC-002` meant release/version-control evolution or an explicit protocol version. Preserve the historical decision and add an accepted clarification/superseding decision if “versioned” is being withdrawn; otherwise narrow T-011 to “no runtime negotiation” and implement the versioning the decision requires. | Open |
| `T011-R6` | **Low** | Current truth / coordination | `ai/TASKS.md` changes T-011 to implemented/awaiting review but leaves it under `Ready`, uses a status phrase outside the canonical status list, leaves the “Start here” paragraph saying it is Ready, and retains `Last updated: 2026-07-25`. `STATUS.md` calls it Started while its In-progress section says nothing is active. | Move T-011 to `In Review` with the canonical status, update the metadata and start-here text, and reconcile the concise status snapshot. | Open |

### Review judgments

- `WorkerFinished` should **not** be folded into `is_terminal()`. Job outcome and clean stream
  completion are genuinely different facts. `T011-R1` means the protocol needs a richer
  outcome model, not that the sentinel should pretend to be success or failure.
- Terminal-once enforcement belongs to the stateful receiver, not a dataclass constructor.
  The missing piece is an explicit T-013 gate, not enforcement inside T-011.
- Carrying `Failed.kind` and `Failed.message` as separate fields is acceptable. It maps
  directly to the durable `Job` shape. Reusing `FailureDetail` is optional, but duplicating
  the shape requires duplicating its runtime validation and immutability guarantees correctly.
- A real multiprocessing queue is reasonably out of scope here. Pickle round-tripping is the
  right T-011-level proof; T-012 and T-013 own the actual send and receive seams.
- The independently transcribed `REQ_014_STAGES` set is a good anti-vacuity check. The
  `MESSAGE_TYPES`/sample equality also detects a declared tuple entry with no sample, but does
  not prove that each sample is a valid, meaningful contract instance.

### Checks run

| Check | Result |
|---|---|
| Review boundary | Clean `main` at exact head `bd79418`; `831a726..bd79418` is one commit touching 3 files, with 497 insertions and 2 deletions. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 65 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 50 source files. |
| `mypy --platform win32` | Passed: no issues in 50 source files. |
| `pytest -q` | Passed: 290 passed, 2 skipped, 1 deselected in 0.44 s. |
| Focused protocol baseline | Passed: 48 tests. |
| Layering | Passed: 109 cases; the protocol imports neither Qt nor yt-dlp. |
| Malformed-sample mutation | Replaced the representative `Probed.media` with a raw dict and omitted the representative `Progress.stage`; all 48 protocol tests still passed. Restored. |
| Direct runtime probes | A wrapped raw dict survived pickle and passed `is_message`; invalid string stage/kind values passed; a dict `Failed.context` remained mutable; an undeclared `Progress` subclass passed `is_message`; a successful-probe sequence contained zero terminal messages. |
| `git diff --check 831a726..bd79418` | Passed. |
| Windows CI | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30212659385` with all five jobs green. |

### Readiness

T-011 is not approved and should not unblock T-035 or T-038 at this head. The message shapes,
stage enumeration, pickling coverage, layering, and outcome/stream distinction form a good
base. Before downstream code binds to it, the contract needs a coherent successful-probe
sequence, strict runtime payload validation, honest required-field signatures, and an
explicit terminal-once acceptance gate in T-013. The decision and coordination conflicts
should be reconciled in the same correction pass.

## 2026-07-26 — T-011 final focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-011`; dispositions for `T011-R1`–`T011-R6`
**Base:** `bd794186470a5b511246c360b691db56f76be9aa`
**Head:** `c247e54e11cbe7b4f84505e5aa7f14673c80351f`
**Platforms verified:** Linux locally; Windows CI run `30213417231` was reported green in the
handoff, but the reviewer could not independently query it because the installed `gh`
credential remains invalid
**Verdict:** Changes requested — final review disposition

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T011-R1` | **Resolved** | The contract now distinguishes probe/download sessions, makes `Probed` an outcome, retains `WorkerFinished` as non-outcome stream completion, declares kind-specific legal outcomes, and validates the four success/failure sequences plus missing, duplicate, illegal, misplaced, mixed-ID and undeclared cases. A successful probe now has exactly one outcome. |
| `T011-R2` | **Partially resolved — Open** | All five original reproductions are fixed: wrapped dict media, string stage/kind, mutable context, and an undeclared subclass are rejected or normalized correctly. `normalise_context()` is shared with `FailureDetail`, avoiding a second implementation. The runtime shape is still incomplete: `Progress.speed_bytes_per_second` and `Succeeded.total_bytes` accept mutable dictionaries, pass `is_message()`, survive pickle, and can change after construction. Replacing the representative values with those dicts left all 100 protocol tests green. The same typed-boundary and feeder-thread invariant therefore remains open on two fields. |
| `T011-R3` | **Resolved** | All message dataclasses are keyword-only; `Probed.media`, `Progress.stage`, `Succeeded.output_path`, and `Failed.kind/message` are required and non-optional in the inspected signatures. Omitting the stage no longer constructs. |
| `T011-R4` | **Resolved** | T-013 now explicitly requires one outcome per job ID, suppresses a second state transition/signal, applies `validate_sequence()` per completed session, and tests the duplicate. Enforcement is owned by the correct stateful layer. |
| `T011-R5` | **Open — maintainer decision required** | The module narrowed its claim to no runtime negotiation and `STATUS.md` accurately raises the authority question. The accepted `ARC-002` wording has not been clarified or superseded, and the T-011 task still says “No protocol versioning.” The Implementer correctly did not decide an accepted decision's intent, but this means the finding is parked rather than resolved. |
| `T011-R6` | **Resolved** | T-011 is under `In Review` with canonical status, the task metadata and start-here text are current, and `STATUS.md` now reports the active review accurately. Its statements that all six findings are corrected should be read subject to the explicitly parked R5 above. |

### New finding

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T011-R7` | **Medium** | Executable session grammar | The module declares the probe grammar as `Progress(PROBING)*` followed by its outcome and sentinel, and says `validate_sequence()` is the executable form. In fact, a probe sequence containing `Progress(stage=MERGING)` validates. Full download-stage ordering can reasonably remain outside this contract because yt-dlp pipelines skip and repeat stages, but a probe reporting merge/download/post-processing is impossible and misreports `REQ-014` state. | Enforce `Stage.PROBING` as the only progress stage in a probe session and add a rejection test. If probe sessions are intentionally allowed to report every stage, change the declared grammar and justify that broader contract instead. | Open |

### Final review judgments

- The strict choice that a download session cannot emit `Probed` is sound for the current
  vertical slice: probing and downloading are separate worker operations, and the UI obtains
  media metadata from the probe session first.
- Full download-stage monotonicity need not be enforced in T-011. Real yt-dlp pipelines can
  omit or repeat stages; T-012 maps its hooks and the later end-to-end gate owns observed
  progression. `T011-R7` is narrower: the known probe operation cannot merge or download.
- A real `multiprocessing.Queue` remains properly out of scope. Pickle and sequence validation
  are sufficient here; T-012/T-013 own transport behavior and process lifetime.
- The correction to the original fixture mutation is non-vacuous. It fails during invalid
  construction as well as in the explicit sample-validity guard; the 28 failures are expected
  fan-out from a shared invalid fixture, not 28 independent proofs.

### Checks run

| Check | Result |
|---|---|
| Correction boundary | Clean `main` at exact head `c247e54`; `bd79418..c247e54` is two commits and 6 files, with 797 insertions and 297 deletions. Commit `60edd4e` records the prior review unchanged; the implementation correction is `60edd4e..c247e54`, 5 files. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 65 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 50 source files. |
| `mypy --platform win32` | Passed: no issues in 50 source files. |
| `pytest -q` | Passed: 342 passed, 2 skipped, 1 deselected in 0.46 s. |
| Focused protocol baseline | Passed: 100 tests. |
| Layering | Passed: 109 cases; the protocol imports neither Qt nor yt-dlp. |
| Original malformed-sample mutation | Replaced `Probed.media` with a raw dict and omitted `Progress.stage`: 28 failed, 72 passed. Both invalid constructors were reached through the shared fixture. Restored. |
| Residual payload mutation | Replaced representative progress speed and success byte count with mutable dictionaries: all 100 protocol tests passed. Restored. |
| Direct residual probes | Both mutable dictionaries constructed, passed `is_message()`, survived where pickled, and retained mutable state. A probe reporting `Stage.MERGING` passed `validate_sequence(SessionKind.PROBE, ...)`. |
| `git diff --check bd79418..c247e54` | Passed. |
| Windows CI | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30213417231` with all five jobs green. |

### Readiness

T-011 is not approved at `c247e54` and should not unblock T-035 or T-038. The two original
High-level design failures are substantially corrected, and R1, R3, R4 and R6 are closed.
Strict runtime validation remains incomplete under R2, the advertised probe grammar is not
fully enforced, and R5 still requires the maintainer to interpret or supersede `ARC-002`.
This is the requested last review pass: these are the final reviewer dispositions at this
head, and no additional Codex re-review is implied.

## 2026-07-26 — T-011 post-final correction verification

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-011`; verification of reopened `T011-R2` and new `T011-R7`
**Base:** `c247e54e11cbe7b4f84505e5aa7f14673c80351f`
**Head:** `a9225145266424d0663fdbf175dd9d9b8ec0facc`
**Platforms verified:** Linux locally; Windows CI run `30214219218` was reported green in the
handoff, but the reviewer could not independently query it because the installed `gh`
credential remains invalid
**Verdict:** The submitted R2 and R7 corrections are verified; T-011 remains blocked by
parked `T011-R5` and the carry-forward finding below

### Finding dispositions

| ID | Result | Evidence |
|---|---|---|
| `T011-R2` reopened fields | **Resolved** | `Progress.speed_bytes_per_second` now accepts only a non-negative real number or `None`; `Succeeded.total_bytes` accepts only a non-negative integer or `None`. Reapplying the exact two-dictionary sample mutation produced 33 failures and 80 passes. The new generic audit visits every dataclass field of every declared message. Adding an otherwise-unvalidated field to `WorkerFinished` made that audit fail specifically for the new field: 1 failed, 4 passed. Both mutations were restored. |
| `T011-R7` | **Resolved** | Probe sessions now reject downloading-video, downloading-audio, merging and post-processing progress. Disabling the probe-stage branch caused exactly those four parametrized cases to fail while 109 protocol tests passed. The explicit allowance for arbitrary/repeated download stages matches the narrow review judgment and remains intentional. |
| `T011-R5` | **Open — unchanged** | The task and status now accurately say this is parked rather than corrected, and the task heading is narrowed to “No runtime version negotiation.” Nothing in this correction interprets or supersedes accepted `ARC-002`; the maintainer decision remains the only blocker of this type. |

### Carry-forward finding

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T011-R8` | **High** | Recursive projection / immutability | The systematic audit is sound for direct message fields but does not traverse declared model payloads. `MediaInfo` accepts its `formats` field as a mutable list containing raw yt-dlp format dictionaries; `Probed` accepts that `MediaInfo`; the list and dictionaries remain mutable, pass `is_message()`, and survive pickle. A caller can therefore wrap `info_dict["formats"]` one level down and cross the process boundary without producing `FormatInfo` projections, violating the same `ARC-002` rule and feeder-thread invariant as R2. | In the following task, make `MediaInfo` reject or normalize `formats` to an immutable tuple of actual `FormatInfo` instances, with negative tests for a list of raw dictionaries, a tuple containing a raw dictionary, and mutation after construction/pickle. Apply the same runtime-shape audit to the other IPC-reachable core models rather than duplicating validation in `Probed`. | Open — carry forward per maintainer instruction |

### Checks run

| Check | Result |
|---|---|
| Correction boundary | Clean `main` at exact head `a922514`; `c247e54..a922514` is two commits and 5 files, with 271 insertions and 20 deletions. Commit `88c3b1f` records the prior review; the correction itself is one commit, `a922514`, touching 4 files. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 65 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 50 source files. |
| `mypy --platform win32` | Passed: no issues in 50 source files. |
| `pytest -q` | Passed: 355 passed, 2 skipped, 1 deselected in 0.53 s. |
| Focused protocol baseline | Passed: 113 tests. |
| Layering | Passed: 109 cases. |
| R2 exact mutation | Mutable dictionaries substituted for progress speed and success byte count: 33 failed, 80 passed. Restored. |
| R2 future-field mutation | Added an unvalidated defaulted field to `WorkerFinished`; the generic audit failed for that field: 1 failed, 4 passed. Restored. |
| R7 branch mutation | Disabled probe-stage enforcement: the four illegal probe-stage cases failed; 109 other protocol tests passed. Restored. |
| Recursive projection probe | `Probed(MediaInfo(formats=[{"format_id": "137", "ext": "mp4"}]))` constructed and passed `is_message`; mutating the original nested dictionary changed the message, and pickle restored another list/dict graph. |
| `git diff --check c247e54..a922514` | Passed. |
| Windows CI | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30214219218` with all five jobs green. |

### Readiness

The corrections actually submitted for review are verified: reopened R2's two direct fields
and R7 are closed. No further T-011 re-review is requested. T-011 still must not unblock
T-035/T-038 until the maintainer resolves R5; the newly identified recursive projection hole
is explicitly carried to the following task, as directed, rather than starting another
correction pass here.

## 2026-07-26 — T-041 nested payload validation

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-041`; carried finding `T011-R8`
**Base:** `b933940a009e437f30a83a52553676e6f50464ad`
**Head:** `cc201a7df5cb798c3fd77ae7f1388d9615e16f09`
**Platforms verified:** Linux locally; Windows CI run `30215562522` was reported green in the
handoff, but the reviewer could not independently query it because the installed `gh`
credential remains invalid
**Verdict:** Changes requested

### Findings

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T041-R1` | **Medium** | Job counter invariants | `_require_optional_count()` is used for non-optional `Job.bytes_done` and `Job.attempts`. Both now accept and store `None` despite their `int` annotations and defaults. This can move an invalid value toward persistence and makes `Job.progress` fail when a total is present. The systematic hostile-container audit does not try `None`, so all 54 model tests remain green. | Add a non-optional count validator and use it for `bytes_done` and `attempts`; retain the optional validator for `bytes_total`, `queue_position`, and other genuinely optional fields. Test `None`, booleans, wrong scalar types, and negative values against both paths. | Open |
| `T041-R2` | **Medium** | Audit anti-vacuity | `test_every_model_in_the_module_is_covered` compares `valid_kwargs()` with `MODELS`, but both are hand-maintained in the same test file. Adding a sixth frozen dataclass with an unvalidated mutable payload to `core/models.py` without editing either list left all 54 model tests green. The test therefore does not guard the condition its name and docstring claim. The field-level loop is effective for models already in `MODELS`: adding an unvalidated field to `FormatInfo` failed all three hostile payload cases. | Derive the production-side set independently by discovering dataclasses defined by `tracks_and_trails.core.models` (excluding imported classes and enums), then compare that set with the sample map. Keep the current field loop for the independently discovered types. Mutation-check both a new model and a new field. | Open |
| `T041-R3` | **Medium** | Declared-model boundary | `_as_tuple_of()` and `_require_model()` use `isinstance`. A frozen `FormatInfo` subclass with an extra mutable-dict field is accepted inside `MediaInfo.formats`, and mutating the original dict changes the already-constructed media graph. The same bypass applies to a `DownloadRequest` subclass stored by `Job`. This repeats the reason T-011 changed message validation from `isinstance` to exact declared types: a subclass can add fields outside the reviewed projection. | Require exact declared model types at IPC-reachable model boundaries, or recursively validate the complete dataclass graph. Add adversarial subclasses carrying a mutable mapping for `FormatInfo` and `DownloadRequest`, and verify construction rejects them. | Open |
| `T041-R4` | **Low** | Exception contract | The stated TypeError/ValueError split is not implemented consistently. Wrong types for required text fields such as `DownloadRequest.url` and `Job.id` raise `ValueError` from bespoke truthiness checks, while `_require_text()` correctly raises `TypeError` for wrong types and `ValueError` only for empty strings. Existing tests cover empty strings but not wrong types on these required fields. | Route every required text field through `_require_text()` and add a representative wrong-type matrix. Preserve `ValueError` for validly typed empty strings and negativity. | Open |
| `T041-R5` | **Low** | Current truth / coordination | T-041 remains under the `Ready` heading with a non-canonical “Implemented, awaiting review” status, while `In Review` is elsewhere. `STATUS.md` says `T011-R8` is closed before independent approval. | Move T-041 to `In Review` with the canonical status and describe R8 as implemented/awaiting review until the functional findings close. | Open |

### Review judgments

- Keeping collection annotations as `tuple[...]` while safely accepting broader runtime
  sequences is acceptable. The annotation describes the stable stored/read shape, and the
  mismatch is safe in the opposite direction from T011-R3: static callers are restricted to
  tuples while untyped callers receive extra normalization, rather than the signature
  advertising an invalid omission. Rejecting strings explicitly is necessary and reachable.
- The small validator duplication with `downloader/protocol.py` is acceptable at this scope.
  Importing private downloader helpers into `core/` would invert the layer boundary; the
  helpers are simple enough that sharing is not worth a new cross-layer API.
- PEP 695 type parameters are appropriate on the established Python 3.14 baseline.
- The exact `T011-R8` list-of-format-dicts reproduction now raises with the intended
  `ARC-002` diagnostic, and correct `FormatInfo` lists are copied into tuples. The remaining
  findings concern the broader guarantee T-041 adds around that fix.

### Checks run

| Check | Result |
|---|---|
| Review boundary | Clean `main` at exact head `cc201a7`; `b933940..cc201a7` is one commit touching 4 files, with 346 insertions and 24 deletions. All review mutations were restored. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 65 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 50 source files. |
| `mypy --platform win32` | Passed: no issues in 50 source files. |
| `pytest -q` | Passed: 379 passed, 2 skipped, 1 deselected in 0.67 s. |
| Focused models | Passed: 54 tests. |
| Layering | Passed: 109 cases; `core/` imports neither Qt nor yt-dlp. |
| Exact R8 regression | Passed: raw format dictionaries are rejected with an `ARC-002` message; a valid caller list becomes a detached tuple and survives pickle with `FormatInfo` elements. |
| New-field mutation | Added an unvalidated field to `FormatInfo`: the systematic audit failed its raw-dict, list-of-dicts, and mutable-string-list cases; 3 failed, 12 passed, 39 deselected. Restored. |
| New-model mutation | Added a sixth frozen dataclass with an unvalidated payload but did not edit the two test lists: all 54 model tests passed. Restored. |
| Direct invariant probes | `Job(bytes_done=None, attempts=None)` constructed and stored both `None` values. Required text fields given dictionaries raised `ValueError`, not the documented `TypeError`. |
| Subclass probe | A frozen `FormatInfo` subclass carrying a mutable dictionary was accepted in `MediaInfo.formats`; mutating the source dictionary changed the stored graph. |
| `git diff --check b933940..cc201a7` | Passed. |
| Windows CI | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30215562522` with all five jobs green. |

### Readiness

T-041 is not approved at `cc201a7`, and `T011-R8` should not yet be recorded as fully closed.
The direct raw-format-dictionary defect is fixed, the collection normalization strategy is
sound, and the field audit is useful for known models. Approval still requires restoring the
non-optional Job invariants, making the model-set guard independent, closing declared-model
subclass bypasses, and aligning the documented exception contract. Coordination can then
reflect the independently verified result.

## 2026-07-26 — T-041 focused correction re-review (final)

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-041`; carried finding `T011-R8`
**Re-review base:** `cc201a7df5cb798c3fd77ae7f1388d9615e16f09`
**Head:** `0268e13a88055358a733d368dc631e7f6ea7f71b`
**Platforms verified:** Linux locally; Linux, Windows, frozen Linux, frozen Windows, and
Windows desktop in independently queried CI run `30216176642`
**Verdict:** **Approved.** One Low test-hardening finding is carried into the next Phase 1
implementation at the maintainer's direction; it does not leave any current model accepting
the invalid values or nested carriers found in the first pass.

### Finding dispositions

| ID | Disposition | Evidence |
|---|---|---|
| `T041-R1` | **Resolved** | `Job.bytes_done` and `Job.attempts` now use the non-optional `_require_count`; both reject `None`, while `bytes_total` and `queue_position` retain their legitimate `None`. Reverting `bytes_done` to `_require_optional_count` fails its dedicated regression test. |
| `T041-R2` | **Resolved** | The production-side model set is independently discovered from dataclasses defined by `core.models`, with imported types excluded by `__module__`. A sixth module-defined dataclass now produces five failures, and an unvalidated field on an existing model produces three. The acknowledged re-export and non-dataclass cases do not describe any current `core.models` model or violate this task's current acceptance boundary. |
| `T041-R3` | **Resolved** | Both nested boundaries require exact declared types. Reverting `_require_model` and `_as_tuple_of` to `isinstance` makes the two adversarial subclass tests fail. Rejecting subclasses is the right constraint for these declared IPC projections; future tasks must add a declared model rather than smuggle extra state through inheritance. |
| `T041-R4` | **Resolved** | The eleven formerly bespoke required-text checks now route through `_require_text`; the matrix distinguishes `TypeError` for a wrong type from `ValueError` for an empty string on every changed field. Existing helper-routed required fields remain unchanged. |
| `T041-R5` | **Resolved** | T-041 is under `In Review` with canonical status, and `STATUS.md` correctly describes `T011-R8` as implemented but awaiting this approval rather than already closed. |

### Review judgments

- `_require_count(None)` raising `ValueError` is acceptable here. The implementation treats
  explicit `None` as absence of a required value; other wrong scalar types still take the
  `TypeError` path. No requirement or caller-facing contract assigns a different exception.
- Excluding enums from model discovery is correct for this audit. They declare members, not
  dataclass payload fields capable of storing the nested mutable data T-041 governs.
- Exact-type checks at `FormatInfo` and `DownloadRequest` boundaries deliberately prohibit
  subclass extension. That matches `ARC-002`'s declared-projection rule and is preferable to
  accepting unreviewed fields.
- The first-pass judgments remain unchanged: tuple annotations with safe runtime
  normalization, local validator duplication, explicit string rejection, and PEP 695 syntax
  are all accepted.

### Carry-forward finding

| ID | Severity | Area | Finding | Recommendation | Status |
|---|---|---|---|---|---|
| `T041-R6` | **Low** | Counter-test anti-vacuity | Adding `("none", None)` to `test_no_field_accepts_raw_or_mutable_payloads` does not make that sweep police nullability. If construction accepts `None`, the only postcondition is `not isinstance(stored, dict \| list)`, which `None` satisfies. With `bytes_done` deliberately routed back through the optional validator, all five generic `None` cases passed; only the dedicated two-field test caught the regression. Separately, removing `_require_optional_count`'s explicit `bool` rejection left all 76 model tests green, although R1 requested boolean coverage. Production behavior is correct and the two current required counters are explicitly protected, so this does not block T-041; it does mean the handoff's stronger claim that the sweep protects the class or future count fields is unproven. | In the next Phase 1 implementation, make nullability coverage derive required/optional status independently from the model annotations (or maintain an explicit invariant table with its own completeness check), add boolean cases for required and optional counters, and narrow the comments so they state what the mapping/container sweep actually proves. | Open — carry forward to the next Phase 1 task per maintainer instruction; no further T-041 pass requested |

### Checks run

| Check | Result |
|---|---|
| Correction boundary | Clean `main` at exact head `0268e13`; `cc201a7..0268e13` is the advertised two commits and five files. Commit `828799b` records the first review; `0268e13` contains the four-file correction. All reviewer mutations were restored. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 65 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| Bare `mypy` | Passed: no issues in 50 source files. |
| `mypy --platform win32` | Passed: no issues in 50 source files. |
| `.venv/bin/pytest -q` | Passed: 401 passed, 2 skipped, 1 deselected in 0.53 s. |
| Full unit suite | Passed: 347 tests. |
| Integration suite | No tests collected; `tests/integration/` currently contains only `__init__.py`, so the direct command exited 5. The default suite above passed. |
| Focused models | Passed: 76 tests. |
| Layering | Passed: 109 cases. |
| System-interpreter focused attempt | Not a product failure: the first `pytest` invocation used the system interpreter and stopped at collection because the `src/` package was not installed there. Re-running through the repository `.venv` passed all 76 tests. |
| New-model mutation | Added a sixth module-defined dataclass without sample kwargs: 5 failed, 75 passed. Restored. |
| New-field mutation | Added an unvalidated field to `FormatInfo`: the raw-dict, list-of-dicts, and mutable-string-list cases failed; 3 failed, 73 passed. Restored. |
| Required-counter mutation | Routed `bytes_done` through the optional validator: its dedicated regression failed, while the generic `None` sweep still passed all 5 model cases. Restored. |
| Boolean mutation | Removed `_require_optional_count`'s explicit `bool` rejection: all 76 model tests passed. Restored; recorded as `T041-R6`. |
| Exact-boundary mutation | Reverted both declared-model boundaries to `isinstance`: both adversarial subclass tests failed. Restored. |
| `git diff --check cc201a7..0268e13` | Passed. |
| CI `30216176642` | Independently verified successful at exact head `0268e13`; all five jobs green. |

### Readiness

T-041 is approved at `0268e13`, and the functional `T011-R8` payload/immutability defect is
independently verified closed. The task is ready for the implementer or maintainer to move to
Complete. Per the explicit final-pass instruction, `T041-R6` is carried into the next Phase 1
implementation and does not request another T-041 re-review.

## 2026-07-26 — T-034, T-035, T-042 and T-043 initial review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-034`, `T-035`, `T-042`, `T-043`; carried finding `T041-R6`
**Review base:** `64c9dfdc3bfc73dc207bb3dd00201f114cb5b99e`
**Head:** `f08f5a6bbba0551494dd731ea66c55d444b43c07`
**Platforms verified:** Linux locally; Linux, Windows, frozen Linux, frozen Windows, and
Windows desktop in independently queried CI run `30218288265`
**Overall verdict:** **Changes requested**

### Per-task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-034` | **Changes requested** | Four open Medium findings violate the path-safety gate or explicit acceptance criteria. |
| `T-035` | **Changes requested** | The candidate list contradicts an explicit acceptance criterion, and an unusable override is reported as fully available. |
| `T-042` | **Approved** | The annotation-driven nullability and boolean guards are independently mutation-verified; no open finding applies to this task. |
| `T-043` | **Approved** | The equivalent protocol guards are independently mutation-verified; no open finding applies to this task. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status / owner / target |
|---|---|---|---|---|---|---|
| `T034-R1` | **Medium** | **Yes** | Required containment gate | The final `safe_output_path()` containment check is reachable, contrary to its comment and the handoff's mutation claim. An existing symlink under the output directory that points outside makes the current entry point raise. Disabling only the final branch allowed that path to escape while all 115 focused path tests still passed, because the suite tests `is_contained()` directly but never drives a symlink through `safe_output_path()`. The mandatory `TESTING.md` §7 gate therefore does not prove that its public entry point invokes the security check. | Add an entry-point regression using an in-directory symlink to an outside directory, then repeat the exact branch-removal mutation and require it to fail. Retain the final containment check and correct its dead-code comment. | **Open** — Implementer; `T-034` correction batch |
| `T034-R2` | **Medium** | **Yes** | Long-name collision | Truncation preserves only the prefix. Two 401-character stems with the same first 400 characters and different final characters sanitize to the same 200-byte filename. The existing collision test differs near the beginning, exactly where naive prefix truncation already preserves the distinction, so it does not establish the acceptance criterion that shortening must not collide with a neighbouring file. | Preserve a deterministic differentiator, such as a stable digest suffix derived from the truncated input, and test two names that differ only beyond the retained prefix. Mutation-check removal of the differentiator. | **Open** — Implementer; `T-034` correction batch |
| `T034-R3` | **Medium** | **Yes** | Extension preservation | `_shorten_to()` falls back to `name[:limit]` when the remaining full-path budget cannot fit the extension. A directory leaving two filename characters returns `cl` for `clip.mp4`, losing `.mp4`, although the acceptance criterion says over-long paths are shortened without losing the extension. | If the complete suffix cannot fit, raise `UnsafePathError` rather than return a misleading extensionless path; add a positive small-budget case as well as the existing no-room case. | **Open** — Implementer; `T-034` correction batch |
| `T034-R4` | **Medium** | **Yes** | Windows-illegal names | The Windows device-name set covers ASCII `COM1`–`COM9` and `LPT1`–`LPT9` only. Windows also reserves `COM¹`, `COM²`, `COM³`, `LPT¹`, `LPT²`, and `LPT³`; all six currently pass unchanged, including with extensions. That violates the cross-platform Windows-illegal-name acceptance criterion. Microsoft's naming rules explicitly list these superscript-digit forms. | Add the six reserved forms to production and parameterize bare, case/extension, and allowed-neighbour cases. Use the [Microsoft file-naming rules](https://learn.microsoft.com/windows/win32/fileio/naming-a-file) as the platform source. | **Open** — Implementer; `T-034` correction batch |
| `T035-R1` | **Medium** | **Yes** | yt-dlp candidate contract | `T-035` says that with no user copy the candidate list contains the baseline alone. `ytdlp_candidates()` always returns two entries, the first being a missing user candidate with `exists=False`. The test silently weakens the criterion to “the baseline is the only *present* candidate.” This is an executable/documented contract mismatch at the Phase 1 worker seam. | Return only the baseline when the user directory is absent, while retaining an existing-but-empty directory for worker import validation; alternatively obtain a deliberate task-contract amendment before retaining absent candidates. Test the tuple itself, not a filtered projection. | **Open** — Implementer; `T-035` correction batch |
| `T035-R2` | **Medium** | **Yes** | ffmpeg capability detection | An explicit override is accepted on `Path.is_file()` alone. On POSIX, a regular file with mode `0644` is reported available and the summary says every post-processing feature works even though it cannot be executed. The positive override fixture itself creates a non-executable file, so the test enshrines the incorrect result. The `PATH` branch already uses `shutil.which()`, whose default check includes executability. | Apply executable-discovery semantics to the override on each platform; make the positive fixture executable (and appropriately named on Windows) and add a non-executable regular-file rejection. Python's [`shutil.which()` documentation](https://docs.python.org/3/library/shutil.html#shutil.which) describes its `F_OK | X_OK` and Windows `PATHEXT` behavior. | **Open** — Implementer; `T-035` correction batch |
| `T035-R3` | **Low** | **No** | Ownership-boundary test strength | The test claiming that `environment.py` exposes no version/usability verdict checks six exact export names. Adding an ordinary `get_ytdlp_version()` export left all 20 focused environment tests green while violating the locate/import ownership split the test claims to protect. The AST checks still block the currently named import mechanisms; this finding is about the broader export claim, not a current production import. | Replace the finite exact-name set with an explicit reviewed public API or a semantic naming/pattern check that at least covers ordinary `get_*version*`, `verify*`, and usability variants. Mutation-check an obvious new export. | **Open, non-blocking** — Implementer; `T-035` correction batch. If not corrected there, add a named `TASKS.md` follow-up before approval. |
| `P1-R1` | **Low** | **No** | Coordination accuracy | `STATUS.md` says “All three await review” after listing four tasks, and its recommended next list still starts with completed `T-041` and includes the already-implemented `T-034`/`T-035`. This does not change the code verdicts, but current-truth documents should not direct the next implementer to completed work. | Update `TASKS.md`/`STATUS.md` after this review: move approved `T-042`/`T-043` to Complete, keep `T-034`/`T-035` in review for the focused correction pass, and recompute the next-work list. | **Open, non-blocking** — Implementer; coordination update accompanying the `T-034`/`T-035` correction batch |

### Review judgments

- The final `is_contained()` call is appropriate defence in depth and should remain. The
  review disagreement is factual rather than philosophical: existing filesystem state makes
  the branch reachable, and the required gate must exercise it through the public entry point.
- Neutralizing traversal components rather than rejecting every hostile input is acceptable:
  the task expressly permits neutralization and the resolved result remains under the selected
  directory.
- `environment.py` locating candidates while `worker.py` imports them is accepted. The
  ownership split is consistent with the current task and layering rules; `T035-R3` concerns
  only the claimed future-proof strength of one test.
- T-042's test discovery follows module-defined dataclasses and annotations independently.
  Removing either count validator's boolean guard made the annotation-driven cases fail, and a
  new required numeric model field failed without editing the test's field list. This resolves
  `T041-R6`.
- T-043 applies the same independent annotation approach to declared protocol messages.
  Removing the two previously unprotected boolean guards failed their respective cases, and a
  new numeric message field failed without editing a field list. The deliberate nullability
  extension is small, relevant, and accepted.

### Checks and adversarial evidence

| Check | Result |
|---|---|
| Review boundary | `64c9dfd..f08f5a6` contains **7**, not the handoff's stated 8, commits and 9 changed files. The two disclosed broken intermediate commits were inspected as history; approval is assessed only at the clean head. Current local HEAD is later at `901a22c`, whose only changes after the review head are the two explicitly excluded `AGENTS.md` commits; source and tests match `f08f5a6`. |
| `.venv/bin/ruff check .` | Passed: “All checks passed!” |
| `.venv/bin/ruff format --check .` | Passed: 67 files already formatted. |
| `.venv/bin/mypy src` | Passed: no issues in 31 source files. |
| `.venv/bin/mypy` | Passed: no issues in 52 source files. |
| `.venv/bin/mypy --platform win32` | Passed: no issues in 52 source files. |
| `.venv/bin/pytest -q` | Passed: 553 passed, 5 skipped, 1 deselected in 0.78 s. |
| Full unit suite | Passed: 499 passed, 3 skipped. |
| Integration suite | No tests collected; `tests/integration/` contains only `__init__.py`, so the direct command exited 5. The default suite above passed. |
| Focused path baseline | Passed: 115 tests. |
| Focused environment baseline | Passed: 20 tests. |
| Focused model baseline | Passed: 85 passed, 1 skipped. |
| Focused protocol baseline | Passed: 121 passed, 2 skipped. |
| Layering | Passed: 109 cases. |
| Containment-call mutation | Disabled only `safe_output_path()`'s final containment branch: all 115 path tests passed. A direct in-directory symlink probe raised before the mutation and returned an outside-resolving path during it. Restored. |
| Long-name probes | Names with 400 identical leading characters and different final characters produced identical 200-byte `.mp4` results. A path budget leaving two filename characters returned `cl`, with no extension. |
| Windows reserved-name probe | `COM¹`, `COM².mp4`, `COM³`, `LPT¹`, `LPT².mp4`, and `LPT³.mkv` all passed unchanged. |
| Candidate-list probe | A definitely absent user directory returned two entries: one absent user candidate and one present baseline. |
| ffmpeg override probe | A regular non-executable override was reported available with “all post-processing features are available.” |
| Ownership-export mutation | Added `get_ytdlp_version()` without importing yt-dlp: all 20 environment tests passed. Restored. |
| Model boolean mutations | Removing the optional-count boolean guard failed 3 annotation-driven cases. Removing the required-count guard failed its derived cases. Restored. |
| Protocol boolean mutations | Removing the optional-rate and exit-code boolean guards failed the corresponding `Progress` and `WorkerFinished` cases. Restored. |
| New numeric-field mutations | A new required `int` field on `FormatInfo` failed the derived nullability/boolean guards; one on `WorkerFinished` failed the corresponding protocol guards. Restored. |
| `git diff --check 64c9dfd..f08f5a6` | Passed. |
| CI `30218288265` | Independently verified successful at exact head `f08f5a6`; all five jobs green. |
| Worktree after review | All temporary source/test mutations were restored. The only local modification is this reviewer-owned `ai/REVIEWS.md` entry. |

### Review-policy clarification

This append-only record does not rewrite the eight earlier review entries, but the current
`AGENTS.md` §9 policy changes how two of their dispositions should be read:

- `T011-R5` was Low and should have recorded **Blocks approval: No**. Its maintainer-owned
  target was `ARC-003`, now accepted. It should not by itself have kept T-011 in review; after
  the maintainer-directed carry-forward, the applicable exact verdict was **Approved with
  follow-ups**, not a freeform blocked variant.
- The final T-041 correction review carried Low `T041-R6` to owner Implementer and target
  `T-042`. Its exact verdict under §9 was therefore **Approved with follow-ups**, not
  **Approved**. This review independently verifies T-042 and resolves that follow-up.
- All findings from this entry onward record **Blocks approval: Yes | No**, and task verdicts
  use only the four exact §9 values.

### Readiness and review budget

`T-042` and `T-043` are approved at `f08f5a6` and can move to Complete without waiting for the
other two tasks. `T-034` and `T-035` are not approved and do not yet unblock `T-012`. Their
remaining standard budget is one focused correction re-review covering the findings above and
regressions introduced by their corrections; it is not another unbounded audit. The
Implementer should return all blocking corrections in one batch with failing regressions and
mutation evidence, then update the coordination documents.

## 2026-07-26 — T-034 and T-035 focused correction re-review (final standard pass)

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-034`, `T-035`; non-blocking coordination finding `P1-R1`
**Re-review base:** `f08f5a6bbba0551494dd731ea66c55d444b43c07`
**Head:** `fb2dab9634405282d02044270c8e25750222ff65`
**Functional correction diff:** `1454591..fb2dab9` — one commit, six files
**Platforms verified:** Linux locally; Linux, Windows, frozen Linux, frozen Windows, and
Windows desktop in independently queried CI run `30219285036`
**Overall verdict:** **Changes requested**

### Per-task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-034` | **Changes requested** | `T034-R2` remains open with a concrete 32-bit digest collision, and the R4 correction introduced a false `COM0`/`LPT0` Windows rule that also creates legal-name collisions. |
| `T-035` | **Approved with follow-ups** | Both functional blockers are resolved. The new Low reviewed-API gap and remaining coordination cleanup are owned by `T-044` and do not keep T-035 in review. |

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---|---|
| `T034-R1` | **Medium** | **No** | **Resolved.** Both directions now go through `safe_output_path()`: an outward symlink raises and an inward symlink remains allowed. Disabling only the final containment branch produced 1 failed and 129 passed path tests. The comment and task record now accurately say the branch is reachable and load-bearing. |
| `T034-R2` | **Medium** | **Yes** | **Open — the submitted correction does not establish the acceptance criterion.** Removing `_marker()` makes the late-difference regression fail, so that test is no longer vacuous. The marker itself is only a 4-byte/32-bit digest, however. A bounded probe found two distinct overlong stems with the same retained prefix at suffixes `68297` and `96718`; both sanitize to the exact same filename. The collision was found in 0.2 seconds, so the differentiator does not make attacker-influenced neighbouring names practically collision-resistant. Use a materially longer digest (at least 128 bits is reasonable within the 200-byte budget), retain the known 32-bit collision pair as a regression, and mutation-check shrinking it back to 4 bytes. |
| `T034-R3` | **Medium** | **No** | **Resolved.** `_shorten_to()` now raises when the suffix and marker cannot fit and keeps the suffix when they can. Replacing the raise with the old `name[:limit]` fallback produced 1 failed and 129 passed path tests. Directly testing this private boundary is justified because the public filesystem setup cannot construct the same tiny budget reliably on every host; the public positive and no-room paths remain covered separately. |
| `T034-R4` | **Medium** | **No** | **Resolved as originally reported.** The six Microsoft-documented superscript forms are sanitized, and the expectation is now independent of production. Removing only the superscript digits produced 7 failed and 123 passed tests: one independent completeness case plus six behavioral cases. The handoff's “9” applies only when the two separately added zero forms are removed too, not to the superscript-only mutation. |
| `T034-R5` | **Medium** | **Yes** | **Open — correction regression.** The new table and its supposedly Microsoft-transcribed expectation add `COM0` and `LPT0`, but Microsoft's reserved filename list is `COM1`–`COM9`, `LPT1`–`LPT9`, and the six superscript forms; it does not include zero. Production therefore changes legal titles (`COM0` → `COM0_`) and makes legal neighbours collide (`COM0` and `COM0_` sanitize identically). Removing zero is a correctness fix even though the current false expectation makes 3 tests fail. Transcribe the [actual Microsoft list](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file), add `COM0`/`LPT0` to the allowed-neighbour cases, and remove the false claims from source, tests, and task records. |
| `T035-R1` | **Medium** | **No** | **Resolved.** An absent or non-directory user path now returns the baseline tuple alone, while an existing empty directory remains first for worker-side import validation. Reintroducing an absent user entry produced 2 failed and 20 passed environment tests. Removing the redundant `exists` flag makes the returned tuple itself the candidate contract. |
| `T035-R2` | **Medium** | **No** | **Resolved.** The override branch now uses `shutil.which()` on the concrete path, the positive fixture is executable, and a mode-0644 regular file is unavailable on POSIX. Reverting the branch to file-presence semantics produced 1 failed and 21 passed environment tests. CI independently verifies the Windows fixture/path behavior. |
| `T035-R3` | **Low** | **No** | **Resolved for the original finding.** Adding the exact `get_ytdlp_version()` mutation now produces 1 failed and 21 passed tests. The denylist has been replaced with an independently spelled expected function/class API. The broader constant hole is separated below because it is a new Low test-strength issue and cannot reopen T-035 during this focused pass. |
| `T035-R4` | **Low** | **No** | **Open — carry-forward.** The test calls itself a reviewed public-API allowlist and includes constants in `reviewed_api`, but the discovery side filters on `value.__module__`; constants have no such attribute and are never compared. Adding `YTDLP_VERSION = "unreviewed"` left all 22 environment tests green. `T-044` owns making the public API explicit and independently testing functions and constants. |
| `P1-R1` | **Low** | **No** | **Partially resolved — carry-forward.** T-042/T-043 correctly moved to Complete and T-034/T-035 remained in review. Current-truth navigation is still inconsistent: `TASKS.md` starts at completed T-041, while `STATUS.md` says T-038 is the only Ready task even though T-014 and T-015 are canonically Ready. Owner Implementer; target `T-044`. |

### Review judgments

- The R1 correction directly addresses the failed security gate and is non-vacuous. The
  implementer's explicit correction of the earlier false dead-code claim is accurate.
- A digest is a reasonable way to preserve a differentiator while retaining deterministic,
  idempotent shortening. The issue under R2 is its 32-bit size, not the choice of a digest.
  No finite shortening can be mathematically injective, but a collision found in fewer than
  100,000 ordinary attempts is not a practical interpretation of “without colliding.”
- Independently transcribing an external platform rule is the right anti-vacuity design for
  R4. It does not protect against mistranscribing the source; the zero forms are exactly that
  failure, and the correction's mutation evidence currently rewards the wrong behavior.
- The T-035 locate/import split, absent-candidate representation, and override executable
  semantics are accepted. No open production defect remains in T-035 at this head.
- `T035-R4` and `P1-R1` are Low and non-blocking under `AGENTS.md` §9. Filing `T-044` gives
  them an owner and target without serializing T-035 behind another review round.

### Checks and adversarial evidence

| Check | Result |
|---|---|
| Correction boundary | Clean `main` at exact head `fb2dab9` before reviewer documentation. `f08f5a6..fb2dab9` contains the two previously excluded `AGENTS.md` commits, the committed initial review, and correction commit `fb2dab9`; the functional correction is the one-commit `1454591..fb2dab9` diff. |
| `.venv/bin/ruff check .` | Passed: “All checks passed!” |
| `.venv/bin/ruff format --check .` | Passed: 67 files already formatted. |
| `.venv/bin/mypy src` | Passed: no issues in 31 source files. |
| `.venv/bin/mypy` | Passed: no issues in 52 source files. |
| `.venv/bin/mypy --platform win32` | Passed: no issues in 52 source files. |
| `.venv/bin/pytest -q` | Passed: 570 passed, 5 skipped, 1 deselected in 0.82 s. |
| Full unit suite | Passed: 516 passed, 3 skipped. |
| Focused paths + environment | Passed: 152 tests. |
| Layering | Passed: 109 cases. |
| R1 containment mutation | Disabled the final `safe_output_path()` containment branch: 1 failed, 129 passed. Restored. |
| R2 differentiator-removal mutation | Removed `_marker()`: 2 failed, 128 passed; the late-difference collision case was one of the two. Restored. |
| R2 direct collision | Distinct names ending in `68297.mp4` and `96718.mp4` after the same 400-character prefix share the 4-byte BLAKE2b digest `ede58bb2` and sanitize to the same output. |
| R3 extension-loss mutation | Replaced the tight-budget raise with `name[:limit]`: 1 failed, 129 passed. Restored. |
| R4 superscript-only mutation | Removed `¹²³` from production: 7 failed, 123 passed. Restored. |
| R5 zero-form correction probe | `COM0` and `LPT0` are not in Microsoft's reserved filename list and `PureWindowsPath.is_reserved()` also reports them false, but production returns `COM0_`/`LPT0_`. Removing zero from production makes 3 current tests fail because the independent expectation contains the same transcription error. Restored. |
| R1 absent-candidate mutation | Reintroduced an absent user entry: 2 failed, 20 passed. Restored. |
| R2 override-presence mutation | Accepted any regular override file: 1 failed, 21 passed. Restored. |
| R3 function-export mutation | Added `get_ytdlp_version()`: 1 failed, 21 passed. Restored. |
| R4 constant-export mutation | Added `YTDLP_VERSION`: all 22 environment tests passed. Restored; assigned to `T-044`. |
| `git diff --check f08f5a6..fb2dab9` | Passed. |
| CI `30219285036` | Independently verified successful at exact head `fb2dab9`; all five jobs green. |
| Worktree after mutations | All temporary source/test mutations were restored. The only local changes are this reviewer-owned entry and the `T-044` follow-up in `ai/TASKS.md`. |

### Readiness and exhausted budget

`T-035` is **Approved with follow-ups** at `fb2dab9`; it can move to Complete, and `T-044`
owns the two Low carry-forwards. `T-034` remains **Changes requested**, so `T-012` remains
blocked on path safety.

This was the one focused re-review allowed by the Standard budget. The review found a direct
continuation of R2 and a regression introduced by the R4 correction, both against T-034's
acceptance boundary. No further implementer/reviewer loop is implied or authorized. The
maintainer must choose: authorize one additional focused pass, accept the two risks, change
the acceptance scope, or carry the work forward under a new task and approve T-034 with that
explicit exception.

## 2026-07-26 — T-034 second authorized exception verification

**Reviewer:** Codex (Reviewer)
**Task:** `T-034`
**Verification base:** `eca1f7e7adfe7b97bec9e4392f8dcc9abf64f86f`
**Head:** `313198d08b5e8f537cde77add662d22a45e3a824`
**Scope:** The two implementer-found defects in this one-commit correction only; no T-045
review or broader T-034 audit
**Platforms verified:** Linux locally; Linux, Windows, frozen Linux, frozen Windows, and
Windows desktop in independently queried CI run `30221188245`
**Verdict:** **Approved with follow-ups**

### Authorized verification items

These are correction defects found by the Implementer's verification, not a new reviewer
finding round. Both would have blocked T-034 at the prior behavior and are resolved at this
head.

| Item | Severity | Blocks approval | Disposition and evidence |
|---|---|---|---|
| Trailing decoration bypassed reserved-name defusing | **Medium** | **No** | **Resolved.** `sanitize_component()` strips ASCII dots/spaces from the stem once, before the case-insensitive reserved-name lookup. `CON`, `CON `, `CON.`, and `CON .mp4` now defuse on the same stripped stem and remain idempotent. Removing this one line produced 21 failed and 179 passed path tests, proving it is load-bearing rather than redundant. The later final `rstrip()` remains a separate general rule for non-reserved components; it cannot replace the pre-check normalization. |
| Drive-prefixed legal title was discarded | **Medium** | **No** | **Resolved.** The first component is discarded only when `PureWindowsPath(part).drive == part`, so an exact `C:` root is removed while `A: The Movie.mp4`, `E: Live at Wembley.mp4`, and drive-relative-looking `C:file.mp4` are retained and have their colon sanitized. Reverting to any truthy drive match produced 3 failed and 197 passed path tests. Removing drive handling entirely produced 2 failed and 198 passed tests, so real `C:\...`/`C:/...` paths still exercise the security branch. |

### Review judgments

- One stem-normalization guard is sufficient. It operates on the value used for reserved-name
  membership and for the defusing digest. The final component strip has a different job and
  does not make it redundant; the exact removal mutation demonstrates the distinction.
- Collapsing `CON`, `CON `, and `CON.` is the correct cross-platform choice. Windows treats
  trailing dots/spaces as the same filename, so preserving a Linux-only distinction would make
  preview/write behavior platform-dependent and could emit an unusable Windows name.
- Relaxing the drive predicate does not re-enable an escape. A longer drive-relative-looking
  component remains an ordinary component, its colon is replaced, it is joined beneath the
  selected directory, and the final resolved containment check still applies. Direct probes
  for `C:../evil.mp4` and `C:..\evil.mp4` produced contained `C_/evil.mp4` paths; ordinary
  absolute drive paths still lost the exact `C:` component.
- NFC/NFD spellings and literal `~` components are unchanged and outside this two-defect
  verification. Nothing in the current path pipeline calls `expanduser()`.
- T-045 is implemented but unreviewed work in the same module. Its Low collision follow-up
  remains independently owned and does not block T-034 under `AGENTS.md` §9.

### Checks and evidence

| Check | Result |
|---|---|
| Boundary | Clean `main` at exact head `313198d` before reviewer documentation. `eca1f7e..313198d` is one commit, three files, and 29 changed production lines. |
| `.venv/bin/ruff check .` | Passed: “All checks passed!” |
| `.venv/bin/ruff format --check .` | Passed: 67 files already formatted. |
| `.venv/bin/mypy src` | Passed: no issues in 31 source files. |
| `.venv/bin/mypy` | Passed: no issues in 52 source files. |
| `.venv/bin/mypy --platform win32` | Passed: no issues in 52 source files. |
| `.venv/bin/pytest -q` | Passed: 640 passed, 5 skipped, 1 deselected in 1.65 s. |
| Focused path suite | Passed: 200 tests. |
| Layering | Passed: 109 cases. |
| Stem-strip mutation | Removed the single pre-check stem strip: 21 failed, 179 passed. Restored. |
| Broad-drive mutation | Reverted to dropping any first component with a drive: 3 failed, 197 passed. Restored. |
| Removed-drive mutation | Disabled drive-component handling: 2 failed, 198 passed. Restored. |
| Direct reserved probes | `CON`, `CON `, and `CON.` produced the same defused name; `CON .mp4`, `AUX  `, and tab-decorated `COM1` were defused and idempotent. |
| Direct drive probes | Legal drive-prefixed titles and `C:../evil.mp4`/`C:..\evil.mp4` were sanitized beneath the output directory; drive-absolute and UNC inputs remained contained. |
| Prior blocker retention | The known 32-bit collision pair now produces distinct names; `COM0`, `COM0.mp4`, `LPT0`, and `LPT0.mp4` remain unchanged. |
| `git diff --check eca1f7e..313198d` | Passed. |
| CI `30221188245` | Independently verified successful at exact head `313198d`; all five jobs green. |
| Worktree after mutations | All temporary source mutations were restored. The only local modification is this reviewer-owned `ai/REVIEWS.md` entry. |

### Readiness

T-034 has no open blocking finding and is **Approved with follow-ups** at `313198d`. It may
move to Complete, and its dependency edge no longer blocks T-012. T-045 remains separately
In Review and T-044 remains Ready; neither requests or implies another T-034 pass.

## 2026-07-26 — T-012 and T-033 initial review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-012`, `T-033`
**Review base:** `7bd9e7b46a241d27dec8e81f7a05b40d12f58439`
**Head:** Bounded uncommitted working-tree snapshot from
`ai/handoffs/T-012-T-033-review-handoff.md`; `AGENTS.md` and the handoff itself are excluded
from the functional change
**Platforms verified:** Linux locally. Frozen Linux and all Windows evidence remain pending
because this snapshot is not committed or pushed.
**Overall verdict:** **Changes requested**

### Per-task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-012` | **Changes requested** | Five High functional/contract defects remain in resolution reporting, fallback isolation, taxonomy mapping, output-path handling, and option translation; the playlist data-contract gap is a non-blocking Medium follow-up. |
| `T-033` | **Changes requested** | The frozen probe does not assert the bundled version against the pin, and the required frozen/negative/size evidence is not yet present. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status / owner / target |
|---|---|---|---|---|---|---|
| `T012-R1` | **High** | **Yes** | Resolution reporting / IPC | Successful sessions never report the resolved yt-dlp version, source, or rejected override to the parent. `_run()` builds that context, but only attaches it while rebuilding a `Failed`; `Probed` and `Succeeded` have no context or resolution field. A direct successful probe emitted only `Progress`, `Probed(media=...)`, and `WorkerFinished`. Thus `REQ-025`'s version-reporting criterion and the broken-override criterion's “says so” half are both unmet even though `_import_ytdlp()` returns the information internally. The current tests inspect `ResolvedYtdlp` directly and therefore bypass the process contract the criteria require. | Extend the declared protocol so successful sessions carry one validated, picklable resolution report (or add an explicit message), then assert through `run_session()` that a normal success reports the actual version/source and a successful fallback reports the rejected candidate. Keep raw paths and credentials out of it. | **Open** — Implementer; `T-012` correction batch |
| `T012-R2` | **High** | **Yes** | Broken-override fallback | A failed user import can leave `yt_dlp.*` submodules in `sys.modules`; the fallback removes the path but not those partial modules. A fresh-interpreter probe used a user package whose `__init__` imported its own `yt_dlp.version` and then raised `ImportError`. The baseline attempt reused that stale submodule and failed with `cannot import name 'CHANNEL'`, ending in `no usable yt-dlp`. The existing test raises before importing any submodule, so it proves only the cleanest broken-package shape. This violates `OPS-002` and the explicit requirement that a broken user copy fall back to the baseline. | Isolate each candidate attempt. On failure, remove the `yt_dlp` modules introduced by that attempt before trying the baseline, without replacing classes already bound by a successfully selected module. Add the partial-import reproduction in a fresh spawned interpreter and verify both fallback success and taxonomy identity. | **Open** — Implementer; `T-012` correction batch |
| `T012-R3` | **High** | **Yes** | Error taxonomy | Real yt-dlp transport exceptions are absent from `_EXCEPTION_MAPPING`. `yt_dlp.networking.exceptions.TransportError`, `ProxyError`, `IncompleteRead`, `SSLError`, and `CertificateVerifyError` all classified locally as `EXTRACTOR_ERROR`; yt-dlp's networking layer raises these types directly. `NETWORK` is the only auto-retryable taxonomy kind, so a transient transport failure loses the behavior §7 assigns it. The test matrix covers built-in `ConnectionError`/`TimeoutError` but not yt-dlp's own networking hierarchy, despite the criterion claiming every yt-dlp-raised kind is accounted for. | Audit the pinned yt-dlp exception hierarchy, map concrete transport failures to `NETWORK` in most-specific-first order, and add direct plus wrapped cases. Treat HTTP/auth/unsupported subclasses by their actual consequence rather than mapping all `RequestError` instances indiscriminately. | **Open** — Implementer; `T-012` correction batch |
| `T012-R4` | **High** | **Yes** | Output template, containment, and preview | The worker validates a different path contract from the one the user configured. `_validated_target()` reduces the rendered result to `Path(rendered).name`, so `nested/%(title)s.%(ext)s`, `../outside/%(title)s.%(ext)s`, and `/tmp/outside/%(title)s.%(ext)s` all became `/tmp/chosen/Clip.mp4`: directory control is discarded and the task's required rejection of an outside-rendering template never occurs. The advertised escape test calls `safe_output_path()` directly and never drives `_validated_target()` or `run_session()`, so it passes if the worker drops or bypasses the rendered path. Separately, the sanitized target is handed back to yt-dlp as another template: a title `%(uploader)s` previewed as a literal `%(uploader)s.mp4`, then yt-dlp rendered it again to a different filename. The reserved-name test does not exercise this drift. This breaks `REQ-011` and `ARCHITECTURE.md` §8's post-render path rule. | Preserve intended relative template components, reject absolute/traversal renderings at the worker seam as specified, and ensure the validated final path is passed to yt-dlp as a literal rather than interpreted as a second template. Add worker-entry tests for nested paths, absolute/traversal rejection, percent/template syntax in metadata, and preview equality against the path yt-dlp actually computes. | **Open** — Implementer; `T-012` correction batch |
| `T012-R5` | **High** | **Yes** | Request/environment option translation | Several configured behaviors never reach the library call. `build_options(..., probe_only=True)` returns before adding proxy, cookie, or rate-limit settings, while every download performs that probe first; a URL that requires the configured proxy or cookies therefore fails before the actual download. `ffmpeg_override` is resolved and used to bypass `_ffmpeg_gap()`, but the resolved path is never passed as yt-dlp's `ffmpeg_location`. Finally, `DownloadRequest.post_processors` is ignored and `extractaudio=True`/`embedsubtitles=True` are CLI-parser flags, not sufficient `YoutubeDL` library configuration: constructing `YoutubeDL` from the submitted audio options produced an empty postprocessor list. Audio extraction/MP3 and embedded-subtitle presets would therefore be no-ops or failures. | Audit every `DownloadRequest` and resolved-environment field against `YoutubeDL`'s library API. Apply network options to probe and download, pass the resolved ffmpeg location, translate declared postprocessors into the dictionaries `YoutubeDL` consumes, and test behavior by constructing the library object or observing postprocessor execution—not by checking that an ignored key exists in the input dict. | **Open** — Implementer; `T-012` correction batch |
| `T012-R6` | **Medium** | **No** | `REQ-002` playlist data contract | `REQ-002`, which T-012 cites, requires a probe to say whether the input is a single item or playlist. `MediaInfo` has no such field, `project_media()` cannot preserve it, and the options force `noplaylist=True`. T-016 later promises to display the distinction, but no typed value can reach it. This is adjacent Phase 1 contract work rather than a reason for another T-012-only review round once the blockers above close. | Add an explicit playlist/single-item projection before T-016. Amend `T-018` to own the fixture-backed adapter/model change (and make T-016 depend on it), or deliberately assign it to the current correction while the protocol seam is already changing. | **Open, non-blocking** — Planner/Implementer; target `T-018` before `T-016` |
| `T033-R1` | **High** | **Yes** | Frozen artifact gate | The first acceptance criterion is not asserted: `run_ytdlp_probe()` prints `resolved.version` but never compares it with the exact `pyproject.toml` pin (`2026.7.4`; runtime reports `2026.07.04`). A stale or otherwise wrong bundled version can pass. The required negative proof that removing collection breaks the frozen probe, both-platform frozen results, and artifact-size delta are also absent; the handoff correctly labels only the source-mode probe as complete. PyInstaller is not installed in the local review environment, so an attempted independent local frozen build could not run. | Add a canonical expected-baseline value derived from the project pin at build time and fail the in-artifact probe on a normalized mismatch. Commit/push the corrected boundary, run both frozen jobs, exercise and revert the collection-removal mutation, and record the artifact-size change with the CI evidence. | **Open** — Implementer; `T-033` correction batch and CI |
| `P1-R2` | **Low** | **No** | Coordination accuracy | `STATUS.md` lists T-033 under In progress and says its frozen evidence is pending, but its Known gaps section calls T-033 “closed 2026-07-26.” That is premature before review and before its own platform gate. | Keep T-033 In Review until `T033-R1` and both frozen jobs are verified; then describe it as closed in one consistent update. | **Open, non-blocking** — Implementer; coordination update with corrections |

### Review judgments

- Keeping `ai/handoffs/T-012-T-033-review-handoff.md` during the review is acceptable. It is
  clearly a convenience artifact and does not replace `TASKS.md`, `STATUS.md`, or this review
  record. Delete or archive it after the review closes unless the project deliberately gives
  `ai/handoffs/` an owner, retention rule, and non-authoritative label.
- `_origin_of()` is adequate for the supported baseline and extracted-wheel layouts: a bundled
  baseline has no candidate path to compare, and the user-managed copy is an extracted
  filesystem package with an ordinary origin. Frozen-platform evidence is still required.
  The concrete importer defect is the partial-module contamination in `T012-R2`, not a
  hypothetical synthetic `__file__`.
- `_written_path()` falling back to the validated target is acceptable for an outcome that
  lacks a more precise yt-dlp path. The blocking issue is that the target is currently stripped
  and then reinterpreted before use.
- The finding set is deliberately class-level. In particular, `T012-R5` requires a field audit
  rather than five one-name patches, and `T012-R3` requires the pinned upstream exception
  hierarchy rather than the two concrete types named by the first failing probe.

### Checks and adversarial evidence

| Check | Result |
|---|---|
| Review boundary | Base `7bd9e7b46a241d27dec8e81f7a05b40d12f58439`; 11 functional/coordination files in the bounded working-tree snapshot. `AGENTS.md` and `ai/handoffs/` excluded. Production blob IDs include worker `73ef6568`, adapter `4a571da6`, and freeze probe `026cdaf0`. |
| `.venv/bin/ruff check .` | Passed: “All checks passed!” |
| `.venv/bin/ruff format --check .` | Passed: 70 files already formatted. |
| `.venv/bin/mypy src` | Passed: no issues in 31 source files. |
| `.venv/bin/mypy` | Passed: no issues in 54 source files. |
| `.venv/bin/mypy --platform win32` | Passed: no issues in 54 source files. |
| `.venv/bin/pytest -q` | Passed: 700 passed, 5 skipped, 1 deselected in 1.62 s. |
| Adapter + worker + layering | Passed: 169 tests. |
| Source-mode `--ytdlp-probe` | Passed: runtime `2026.07.04`, 1751 extractors, `youtube` resolved. This is not frozen-artifact evidence. |
| Successful-message probe | Emitted `Progress`, `Probed`, `WorkerFinished`; none carried version, source, or fallback context. |
| Partial-import fallback probe | A broken override that imported its own `yt_dlp.version` before raising poisoned the baseline attempt; `_import_ytdlp()` raised `no usable yt-dlp` with the stale user module named in the baseline error. |
| Networking taxonomy probe | `TransportError`, `ProxyError`, `IncompleteRead`, `SSLError`, and `CertificateVerifyError` each classified as `EXTRACTOR_ERROR`. |
| Rendered-path probes | Nested, traversal, and absolute templates all silently collapsed to the same root-level chosen-directory filename. A percent-bearing title produced different first- and second-render results. |
| Library-option probe | Probe options omitted configured proxy/cookies/rate limit. `YoutubeDL({"extractaudio": True})` constructed no audio postprocessor. |
| Frozen build attempt | Not run: the repository venv lacks PyInstaller, so no local artifact was produced. The source probe above cannot substitute for CI. |
| `git diff --check` | Passed for the tracked review diff excluding `AGENTS.md`; ruff/format covered the new Python files. |

### Readiness and review budget

Neither task is approved. T-012 has High defects in core user-visible behavior and its process
contract; T-033 has an unmet High packaging gate. Under `AGENTS.md` §9 these findings remain
blocking regardless of pass count. The Standard budget still provides one focused correction
re-review; if any High/Critical finding remains after it, focused correction and independent
verification continue until the serious defect is resolved or the maintainer makes an explicit
scope/risk decision.

## 2026-07-26 — T-012 and T-033 correction batch (Implementer)

**Implementer:** Claude (Opus 5)
**Responds to:** the 2026-07-26 T-012/T-033 initial review
**Status:** all six blocking findings **corrected, awaiting re-review**. Nothing below is marked
Resolved — only the Reviewer does that (`AGENTS.md` §9).

The reviewer's findings table is left as written. This is appended rather than edited because
`AGENTS.md` §6 classifies `REVIEWS.md` as a historical record.

### Corrections

| ID | Correction | Evidence that weakening it fails |
|---|---|---|
| `T012-R1` | New declared message `ResolutionReport` (version, source, rejected), emitted once after resolution and before the outcome, for **every** session that gets that far. Not an outcome, so the "exactly one outcome" rule is untouched; `validate_sequence` gains an at-most-one rule. Rejection reasons have the candidate directory replaced with its label (`NFR-007`). | Not emitting it: 4 failed. Dropping `rejected`: 1 failed. Removing the path redaction: 1 failed. Asserted through `run_session`, and the fallback case through a real spawned process. |
| `T012-R2` | Each candidate import is snapshotted and, **on failure only**, the `yt_dlp` modules that attempt added are discarded. Also widened to `except Exception`: a broken user copy is arbitrary code and `SyntaxError`/`RuntimeError` shapes previously killed the worker instead of falling back. | Removing the cleanup: 2 failed. Narrowing back to `ImportError`: 4 failed. The reviewer's partial-import repro is now a parametrised shape in `BROKEN_SHAPES`, run in a fresh interpreter, and each shape also asserts the taxonomy still classifies after the fallback. |
| `T012-R3` | `TransportError` mapped to `NETWORK`, covering `ProxyError`, `SSLError`, `CertificateVerifyError` and `IncompleteRead`. `HTTPError` classified by `.status`, since one class spans opposite retry consequences. | Dropping the mapping: 12 failed. Classifying HTTP by class: 6 failed. The test walks the pinned hierarchy rather than naming five types, so a new upstream subclass cannot reintroduce the defect. |
| `T012-R4` | The rendered path keeps its directories; an escaping render is **rejected** (`escapes_directory`, new in `core/paths.py`) rather than neutralised; the validated path is handed to yt-dlp `%%`-escaped so it is data, not a second template. Rejection classifies as `DISK`, not `EXTRACTOR_ERROR`. | Restoring `Path(rendered).name`: 1 failed. Removing rejection: 6 failed. Passing the raw path as `outtmpl`: 1 failed. Neutering `escapes_directory`: 6 failed. All new tests drive `run_session`, not `safe_output_path`. |
| `T012-R5` | Connection options (proxy, cookies, rate limit) and `ffmpeg_location` now apply to **both** phases; `postprocessors` built as the dicts the library consumes; `post_processors` names validated against yt-dlp's own registry, unknown ones raising `UnsupportedPostProcessorError` (→ `FFMPEG_ERROR`) instead of being dropped. | Six mutations, 1–5 failures each. Tests construct a real `YoutubeDL` and read `_pps`, per the reviewer's instruction not to assert on keys in the input dict. |
| `T033-R1` | `BASELINE_YTDLP_VERSION` restated in `environment.py` and asserted against the `pyproject.toml` pin by test; the probe fails on a normalised mismatch (`2026.7.4` vs `2026.07.04`). CI now also records artifact size and yt-dlp's share of it. | Wrong pin: 2 failed **and** the probe exits 1 with an explicit message. `normalise_version` returning a constant: 4 failed. |

### Non-blocking

- `T012-R6` — assigned to `T-018`, which now owns the playlist/single-item projection and
  **blocks `T-016`**; `T-016`'s dependency list updated. It needs a recorded playlist fixture,
  which is `T-018`'s job.
- `P1-R2` — `STATUS.md` no longer calls `T-033` closed; it stays In Review until both frozen
  jobs pass.

### Also found while correcting

Not reported findings; recorded because they were defects in the same surfaces.

- `preview_path` (`REQ-011`) had **no test at all** — found while auditing acceptance criteria
  for the handoff, before this review arrived. Its first test was vacuous on Linux, because
  yt-dlp's `prepare_filename` already maps `: " ?` to fullwidth forms and left `T-034` nothing
  to change. A reserved device name diverges on every platform.
- The frozen probe's `matched is None` branch was dead code: `get_info_extractor` raises
  `KeyError`. The gate worked; its diagnostic did not.
- `_discard_partial_ytdlp`'s `before` guard is **deliberately unverified** and says so in its
  docstring. Removing it survives the suite, and that is honest: the cleanup runs only when
  `import yt_dlp` failed, which cannot happen while any `yt_dlp` module is cached, so nothing
  pre-existing can be protected and no reachable test distinguishes the two.

### Checks — actual results

| Check | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | Passed; 70 files formatted |
| `mypy`, `mypy --platform win32` | Passed: no issues in 54 source files |
| `pytest -q` | **765 passed, 6 skipped, 1 deselected** |
| Consolidated mutation sweep | **18 mutations, 18 killed** |
| Source-mode `--ytdlp-probe` | Passed; version now asserted against the pin. Still not frozen evidence. |

### Still outstanding on T-033

`T033-R1`'s remaining evidence — the collection-removal negative proof, both-platform frozen
results, and the size delta — **requires the frozen CI jobs**. PyInstaller is in the `build`
extra and is not installed locally, and `AGENTS.md` §7 forbids committing or pushing without
maintainer instruction. The CI machinery is in place; the run is not. `T-033` therefore cannot
be approved on this batch alone.

---

## 2026-07-26 — T-012 and T-033 focused correction re-review

**Reviewer:** Codex
**Responds to:** the 2026-07-26 T-012/T-033 correction batch
**Boundary:** the correction applied to the same uncommitted working tree reviewed from
`7bd9e7b46a241d27dec8e81f7a05b40d12f58439`; there is still no head commit. Maintainer-owned
`AGENTS.md` and `.gitmessage`, and the convenience handoff, remain excluded.
**Overall verdict:** **Changes requested**

### Verdict by task

| Task | Verdict | Reason |
|---|---|---|
| `T-012` | **Changes requested** | `T012-R1`, `T012-R3`, and `T012-R4` are resolved, but the broken-override fallback still has an unclean-import shape that bypasses fallback and `T012-R5` still cannot represent the MP3/quality half of the required audio behavior. Both are High functional continuations of the original findings. |
| `T-033` | **Changes requested** | The pin comparison is corrected, but the frozen probe can pass without the real named extractor module and the workflow does not yet produce the required collection size delta. Frozen evidence is still pending. |

### Finding disposition

| ID | Severity | Blocks approval | Re-review evidence | Status |
|---|---|---:|---|---|
| `T012-R1` | **High** | **Yes** | `ResolutionReport` is a declared, validated, picklable message and `run_session()` emits it before work and before either successful outcome. Success and fallback tests observe it through the queue. Rejection text replaces the candidate root with its source label; the path-bearing package shape makes that assertion non-vacuous. The report remains outside `OUTCOME_TYPES`, preserving one-outcome semantics. | **Resolved** |
| `T012-R2` | **High** | **Yes** | The per-attempt snapshot and failure-only cleanup resolve the reported partial-submodule contamination for ordinary exceptions, and the fresh-process tests verify taxonomy identity after fallback. The correction is still incomplete for an import that raises `SystemExit`: a deterministic first-attempt import finder raising `SystemExit("broken override exited during import")` escaped `_import_ytdlp()` instead of trying the baseline. `SystemExit` is not an `Exception`, but it is still a user copy that “does not import cleanly,” which `ARCHITECTURE.md` §6 requires to fail loudly **and fall back**. The same applies to arbitrary `BaseException` raised by that third-party module unless cancellation semantics deliberately reserve one. | **Open** — extend the candidate-failure boundary beyond `Exception`, retain failure-only namespace rollback, and add the `SystemExit` shape to the fresh-interpreter fallback/taxonomy matrix |
| `T012-R3` | **High** | **Yes** | `TransportError` now covers the pinned transport hierarchy as `NETWORK`; `HTTPError` is classified structurally by status before the type table. Direct and wrapped cases, the hierarchy walk, retryable statuses, `401`, and permanent statuses all pass. The deliberate `403` treatment is consistent with the taxonomy's requirement not to invent authentication from ambiguous evidence. | **Resolved** |
| `T012-R4` | **High** | **Yes** | Worker-entry tests now preserve nested template directories, reject POSIX/Windows absolute and traversal renders as `DISK`, retain containment against symlinks, and drive a percent-bearing title through a real second yt-dlp render. `as_literal_template()` prevents the validated path from being interpreted as another template, and the independently observed `Succeeded.output_path` agrees with the preview. | **Resolved** |
| `T012-R5` | **High** | **Yes** | Proxy, browser cookies, and rate limit now reach both adapter phases; the resolved ffmpeg path reaches the actual download; named processors are no longer silently discarded; and real `YoutubeDL` construction proves that audio extraction and subtitle embedding processors are installed. However, constructing the submitted audio request produced `FFmpegExtractAudioPP.mapping == "best"` and no quality, and `DownloadRequest` has no codec, quality, container, or structured processor-argument field. Consequently the required **MP3** preset and best/original preset are indistinguishable: both preserve/choose the source codec rather than one requesting MP3 conversion. A processor class being installed is not proof that it is configured to deliver the selected output. This is the same functional half of R5, not an adjacent preset-only issue: `T-015` can translate only into the request shape and `ytdlp_adapter` options this correction defines. | **Open** — make the request carry the required processor parameters, translate them into real yt-dlp processor dictionaries, and assert on the constructed processor's codec/quality behavior for MP3 versus best/original; include known ffmpeg-dependent processors in the early ffmpeg gate |
| `T012-R6` | **Medium** | **No** | `T-018` now explicitly owns the recorded playlist fixture and playlist/single-item projection, and `T-016` depends on it. | **Open, non-blocking follow-up** — owner `T-018` before `T-016` |
| `T033-R1` | **High** | **Yes** | The restated baseline is tied to the exact `pyproject.toml` pin, numeric normalization distinguishes wrong releases, and the source probe now fails on a normalized mismatch. That half is verified. The required frozen negative proof and both-platform results still do not exist. The workflow's size step prints one artifact total and a pathname-based `yt_dlp` subtotal, not the **before/after artifact-size change** the criterion requires. Moreover, it runs after the probe, so the collection-removal run that is expected to fail skips the size step and cannot supply the no-collection comparison. | **Open, partially corrected** — retain the version check; arrange for both the normal and collection-removal builds to record total size (before the deliberately failing probe or under an appropriate condition), then record the actual delta with the two-platform frozen evidence |
| `T033-R2` | **High** | **Yes** | The claimed extractor gate resolves only a class from `yt_dlp.extractor.lazy_extractors`; it never instantiates that class and therefore never imports the real dynamic module. With a meta-path finder deliberately making `yt_dlp.extractor.youtube` unimportable, `run_ytdlp_probe()` still reported 1,751 extractors, “resolved youtube,” and exit 0. Instantiating the returned class immediately afterward failed with `ModuleNotFoundError`. Thus an artifact can pass this gate while lacking the code needed to handle the named URL pattern—the exact failure T-033 exists to catch. | **Open** — instantiate the named lazy class (and exercise its stable URL-pattern predicate without network), fail with a diagnostic on dynamic-module import failure, and add the blocker reproduction so removing the real extractor module cannot leave the probe green |
| `P1-R2` | **Low** | **No** | `STATUS.md` consistently leaves T-033 In Review and explicitly names its pending frozen evidence. | **Resolved** |

### Independent checks

| Check | Result |
|---|---|
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; 70 files already formatted |
| `mypy src` | Passed; 31 source files |
| `mypy` | Passed; 54 source files |
| `mypy --platform win32` | Passed; 54 source files |
| `pytest -q` | **765 passed, 6 skipped, 1 deselected** |
| Source `--ytdlp-probe` | Passed for the installed baseline; still not frozen evidence |
| Dynamic-extractor blocker probe | **Gate incorrectly exited 0** while actual `YoutubeIE` instantiation failed with `ModuleNotFoundError` |
| Broken-override `SystemExit` probe | **Fallback did not run**; `SystemExit` escaped `_import_ytdlp()` |
| Real audio postprocessor inspection | `FFmpegExtractAudioPP` installed, but with `mapping="best"` and no requested quality; no MP3 distinction exists |
| `git diff --check -- ai/REVIEWS.md` | Passed after this entry |

### Review decision and next boundary

Do **not** commit or push this correction boundary yet. Fix the two remaining T-012 High
continuations and make the T-033 probe load real extractor code; also make the size evidence
step capable of recording the negative-run comparison. Those are focused continuations of
unresolved High findings, so `AGENTS.md` §9 permits another verification pass without consuming
a Medium-or-lower exception.

After that focused correction is verified, commit under `AGENTS.md` §12 and push. T-012 may
then be approved from source evidence; T-033 remains In Review until the collection-removal
negative run and both Linux and Windows frozen jobs supply their actual results and size delta.

## 2026-07-26 — T-012 and T-033 second correction batch (Implementer)

**Implementer:** Claude (Opus 5)
**Responds to:** the 2026-07-26 focused correction re-review
**Status:** the three remaining High findings and the size-evidence ordering are **corrected,
awaiting re-review**. Appended, not edited into the reviewer's table (`AGENTS.md` §6, §9).

### Corrections

| ID | Correction | Evidence that weakening it fails |
|---|---|---|
| `T033-R2` | The probe now **instantiates** the resolved class, which is what makes yt-dlp's lazy placeholder load the concrete module, then checks the resulting class is not from `lazy_extractors` and exercises its offline URL predicate in both directions. `ImportError` is caught with a diagnostic naming the packaging cause. | The reviewer's meta-path blocker is now a permanent test in the new `tests/integration/test_freeze_probe.py`, which did not exist — the probe had been CI-only, which is part of why this passed. Reverting instantiation: 4 failed. |
| `T012-R2` (cont.) | Candidate failure widened from `Exception` to `BaseException`, with `KeyboardInterrupt` deliberately re-raised. `SystemExit` and a bare `BaseException` are now shapes in the fresh-interpreter fallback/taxonomy matrix. | Narrowing back to `Exception`: 4 failed. Swallowing `KeyboardInterrupt`: 1 failed. |
| `T012-R5` (cont.) | `DownloadRequest` gains `audio_codec` (a new `AudioCodec` enum carrying yt-dlp's own `preferredcodec` vocabulary) and `audio_quality`, translated into the real processor dict. The early ffmpeg gate now consults **every** processor the request will install, deciding ffmpeg-dependence structurally via `issubclass(..., FFmpegPostProcessor)` rather than a name list. | MP3 now yields `mapping="mp3"`, quality `192`; original yields `mapping="best"`, quality `None`. Six mutations, 1–14 failures each. `Exec` is a control row in the gate table, since it is a real processor that needs no ffmpeg. |
| `T033-R1` (size) | The size step moved **before** the probe and given `if: always()`, so the collection-removal run — whose probe is expected to fail — still records its total. | Ordering verified by inspection; the run itself still needs CI. |

### Grounding for the new model fields

`AudioCodec` and `audio_quality` are additions to an approved contract, so their basis is
stated rather than assumed: `REQ-006` requires "audio only (MP3)" and "audio only
(best/original)" as **two distinct presets**, and `REQ-010` requires "extract/convert audio to
a chosen codec and quality". Without a field for it the two presets were byte-identical
configuration. `ORIGINAL` carries yt-dlp's `best` — which means *no conversion*, not *highest
quality* — and is spelled for the reader.

### Three mutations survived and became tests

Reported rather than smoothed over, per `ai/TESTING.md` §13.

- Deleting the probe's `lazy` module check survived: instantiation already covers the blocked
  module case, so nothing distinguished it. A class that constructs while remaining the
  generated stub is constructible, and now is one.
- Deleting the URL-predicate check survived for the same reason.
- Dropping only the *negative* half of that predicate check (`suitable(_UNRELATED_URL)`)
  survived even after the first two tests existed — an extractor claiming every URL passes
  "does it match its own URL?" while being exactly as broken.

### Checks — actual results

| Check | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | Passed; 71 files formatted |
| `mypy`, `mypy --platform win32` | Passed: no issues in 55 source files |
| `pytest -q` | **796 passed, 6 skipped, 1 deselected** |
| Mutation sweep (this batch) | 14 mutations, 14 killed after the three above became tests |
| Reviewer's blocked-extractor repro | Probe now exits 1 with "lazy extractor table" diagnostic |
| Reviewer's `SystemExit` repro | Falls back to the baseline and reports the rejection |
| Real audio processor | MP3 `mapping="mp3"` / quality `192`; original `mapping="best"` / `None` |

### Still outstanding

`T-033`'s frozen evidence — collection-removal negative run, both-platform results, actual size
delta — still requires the CI jobs. Unchanged from the last batch: PyInstaller is in the
`build` extra and absent locally, and `AGENTS.md` §7 forbids pushing without instruction.
Nothing has been committed or pushed.

---

## 2026-07-26 — T-012 and T-033 second focused verification

**Reviewer:** Codex
**Responds to:** the 2026-07-26 T-012/T-033 second correction batch
**Boundary:** the current uncommitted T-012/T-033 tree based on
`7bd9e7b46a241d27dec8e81f7a05b40d12f58439`; maintainer-owned `AGENTS.md` and `.gitmessage`,
and the convenience handoff, remain outside this reviewed task boundary.

### Verdict by task

| Task | Verdict | Reason |
|---|---|---|
| `T-012` | **Approved with follow-ups** | All High blocking findings are independently resolved. The sole open finding, `T012-R6`, is non-blocking and has owner/target `T-018` before `T-016`. |
| `T-033` | **Blocked** | The source and gate logic are ready to commit and run, but approval still requires the collection-removal negative proof, Linux and Windows frozen results, and their recorded artifact-size delta. Those are external CI evidence, not another source correction. |

### Finding disposition

| ID | Severity | Blocks approval | Verification evidence | Status |
|---|---|---:|---|---|
| `T012-R2` continuation | **High** | **Yes** | `_import_ytdlp()` now treats any candidate-raised `BaseException` other than `KeyboardInterrupt` as a failed candidate, performs the same failure-only namespace rollback, removes the candidate path, and tries the baseline. Replaying the reviewer's first-attempt `SystemExit` finder returned the pinned baseline and a `SystemExit` rejection report. Fresh-interpreter tests cover both `SystemExit` and bare `BaseException`, then re-check taxonomy identity. `KeyboardInterrupt` is explicitly re-raised and independently tested, so the widening does not turn an interruption into silent fallback. | **Resolved** |
| `T012-R5` continuation | **High** | **Yes** | `DownloadRequest` now carries a validated `AudioCodec` and optional quality. A real constructed `YoutubeDL` produced `FFmpegExtractAudioPP.mapping == "mp3"` and quality `192.0` for MP3, versus `mapping == "best"` and no quality for original, so the two required behaviors are no longer the same configuration. The early missing-ffmpeg gate derives dependency from each installed processor's class hierarchy; worker-entry tests cover metadata, thumbnail, subtitle, audio, and merge cases, with non-ffmpeg `Exec` and a plain request as negative controls. | **Resolved** |
| `T033-R2` | **High** | **Yes** | The probe now instantiates the lazy class, verifies the resulting class is concrete, and exercises its URL predicate positively and negatively without network access. Replaying the original meta-path blocker made the probe return 1 with the packaging-specific “lazy extractor table” diagnostic; the previous false success is now a permanent fresh-interpreter integration test. The normal source probe and the two predicate mutation cases also pass. | **Resolved** |
| `T033-R1` | **High** | **Yes** | The version-against-pin logic remains verified. The artifact-size step now runs before the deliberately failing probe and uses `if: always()`, so both the normal and collection-removal builds can produce the totals needed for the delta. The required frozen runs and comparison have not happened yet. | **Open — externally blocked**; commit and push this exact reviewed boundary, then record the negative run, both-platform frozen results, and actual size delta |
| `T012-R6` | **Medium** | **No** | Ownership remains explicit: `T-018` supplies the recorded playlist fixture and projection, and blocks `T-016`. | **Open, non-blocking follow-up** — `T-018` |

### Independent checks

| Check | Result |
|---|---|
| Focused freeze-probe, worker, adapter, and model tests | **225 passed, 1 skipped** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; 71 files already formatted |
| `mypy src` | Passed; 31 source files |
| `mypy` | Passed; 55 source files |
| `mypy --platform win32` | Passed; 55 source files |
| `pytest -q` | **796 passed, 6 skipped, 1 deselected** |
| Dynamic-extractor blocker replay | Probe returned **1** with a packaging diagnostic |
| `SystemExit` fallback replay | Baseline `2026.07.04` selected; rejected override reported |
| Real audio processor replay | MP3: `mp3` / `192.0`; original: `best` / no quality |
| `git diff --check -- ai/REVIEWS.md` | Passed after this entry |

### Commit and CI decision

The reviewed T-012/T-033 task files and this review record are ready to commit under
`AGENTS.md` §12 and push to `main` so the frozen jobs can run. Do not fold the excluded
maintainer-policy files (`AGENTS.md`, `.gitmessage`) or the non-authoritative handoff directory
into that task commit; handle those separately.

The commit may close `T012-R1` through `T012-R5`, `T033-R2`, and `P1-R2`. It must not claim
`T033-R1` or T-033 complete yet. After the green normal frozen run, exercise and revert the
collection-removal mutation, retain both platforms' evidence, calculate the artifact-size
delta from the two totals, and return only that external evidence for final T-033 verification.

---

## 2026-07-26 — note: commit SHAs in this file were remapped

**This file is a historical record (`AGENTS.md` §6), so this rewrite is recorded rather than
performed silently.** No finding, verdict, evidence line or date has been altered. Only commit
SHAs changed, and only so they keep pointing at the same commits.

All 80 commit messages were rewritten to the `AGENTS.md` §12 convention at the maintainer's
instruction: subjects shortened to ≤50 characters and stripped of task IDs, which moved into
`Task:`/`Refs:`/`Review:` trailers. Rewriting a message changes its SHA and every descendant's,
so the 112 SHA references across `REVIEWS.md`, `TASKS.md` and `STATUS.md` were remapped to the
rewritten commits.

Verified before and after:

- all 80 trees are byte-identical to the originals — **no file content changed**, only messages;
- all 61 commit references in `ai/*.md` resolve in the rewritten history;
- the 26 remaining hex tokens in this file were never commits on `main` — three are blob IDs a
  reviewer cited, the rest are uncommitted working-tree snapshots — and are deliberately
  untouched;
- CI run numbers (`3020867`, `3021095`, `3021516`, `3021617`) are seven-digit decimals that a
  hex pattern also matches; they were excluded explicitly rather than by luck.

The pre-rewrite history is preserved at tag `pre-message-rewrite-backup` and branch
`backup/pre-message-rewrite` (old head `435d780`, new head `a296615`).

**One consequence worth stating plainly:** the passing CI run for the `T-012`/`T-033` boundary
(run `30226122180`) was recorded against `435d780`, which this rewrite orphans. Its evidence
remains valid and is quoted below, but the run no longer corresponds to a reachable commit.
`T-033`'s outstanding CI work will be re-run against the rewritten head.

### The orphaned run's evidence, preserved

Both frozen jobs passed on `435d780`. Quoted here because the run's own artifacts name a commit
that no longer exists:

| Platform | Probe | Artifact |
|---|---|---|
| ubuntu-latest | `2026.07.04`, pin `2026.7.4`, 1751 extractors, `youtube from yt_dlp.extractor.youtube` | 227348 KiB |
| windows-latest | identical | 136020 KiB |

`T033-R2` is therefore confirmed **in the real frozen artifact**, not only in source: the probe
loaded the concrete extractor module rather than the lazy placeholder, on both platforms.

**A defect in that same evidence step, found while reading it.** The step also prints
`yt_dlp files: 3` / `yt_dlp KiB: 24`. That is misleading: PyInstaller packs pure-Python modules
into the PYZ archive, so a filesystem search finds only the few loose data files and reports 24
KiB for a dependency contributing far more. The artifact total is sound; the yt-dlp subtotal is
not, and must not be quoted as the size delta. Filed as part of `T-033`'s remaining CI work.

## 2026-07-26 — T-012/T-033 pre-review self-audit (retained from the deleted handoff)

Recorded here because `ai/handoffs/` was deleted on 2026-07-26 as a maintenance burden and a
second source of project truth. The handoff itself is not worth keeping — its design notes live
in the modules' docstrings and its findings in the entries above — but this table did not exist
anywhere else, and it is the evidence that the *implementer's own* mutation pass found real
gaps before any reviewer saw the code.

Eleven mutations were run against `T-012`/`T-033` before the first review. Nine were killed
immediately. **Two survived, and both were genuine missing tests rather than redundant code**,
which is `ai/TESTING.md` §13's default reading and the correct one on both occasions.

| # | Mutation | Result |
|---|---|---|
| M1 | `ExtractorError` moved first in the mapping | killed |
| M2 | `extractor_message` ignores `orig_msg` | killed |
| M3 | `unwrap` returns the wrapper | killed |
| M4 | `has_drm`: `all` → `any` | killed |
| M5 | `has_drm` ignores `_has_drm` | killed |
| M6 | `'none'` codec sentinel kept as a string | killed |
| M7 | `filesize_approx` fallback deleted | **survived** |
| M8 | `_origin_of` always trusts its candidate | killed |
| M9 | probe threshold raised above reality | killed |
| M10 | probe given an unresolvable extractor name | killed, but via an uncaught `KeyError` |
| M11 | preview computed by a route parallel to the write | **survived** |

**M7** survived because the archive.org fixture populates `filesize` on every format, so nothing
exercised the fallback. YouTube's DASH formats commonly carry only `filesize_approx`, so the gap
would have shown "unknown" for sizes yt-dlp knows — on the site that matters most.

**M11** survived twice. `preview_path` (`REQ-011`) had no test at all, and the first test written
to cover it was **vacuous on Linux**: the chosen title used `: " ?`, which yt-dlp's own
`prepare_filename` already maps to fullwidth forms, leaving `T-034` nothing to change. A preview
that skipped sanitisation entirely still matched. A reserved device name (`CON`) diverges on
every platform, because yt-dlp does not handle those and `T-045` defuses them with a digest.

**M10** exposed a third defect without surviving: `get_info_extractor` *raises* `KeyError` rather
than returning `None`, so the probe's `matched is None` branch was dead code and a packaging
failure escaped as a bare traceback — in the one log `OPS-003` says Windows failures are
diagnosed from.

## 2026-07-26 — T-045 reserved-name defusing

**Reviewer:** Codex (Reviewer)
**Task:** `T-045`
**Base:** `1c8096407f8479f004fba29aebf382f060a8924c`
**Head:** `c0f48817e1d0a622115247000ca5c07bc6a2d4df`
**Platforms verified:** Linux locally; Windows not rerun
**Verdict:** **Blocked**

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status / owner / target |
|---|---|---:|---|---|---|---|
| `T045-R1` | **Medium** | **Yes** | Collision acceptance criterion | The digest removes the specific `COM1`/`COM1_` collision but does not satisfy “cannot produce a path a legal filename also produces.” `sanitize_component("CON")` returns the legal name `CON-1bc43d851d28ada0`, and sanitizing that exact legal neighbour returns the same string. This is not a hash collision. More fundamentally, that acceptance criterion conflicts with idempotence: for any reserved `x`, let `y = sanitize_component(x)`; `y` is legal, and idempotence requires `sanitize_component(y) == y`, so `x` and legal input `y` necessarily collide. | The maintainer must reconcile the criteria. Either narrow the promise to practical collision resistance against a named neighbour class and retain the digest, or move true uniqueness to a target-existence/collision policy that has filesystem context. A stateless idempotent sanitizer cannot meet both absolute requirements. | **Open — maintainer scope decision required** |
| `T045-R2` | **Low** | **No** | Review-boundary metadata | The task entry has no review base. The actual parent is `1c80964`; without it, this non-contiguous history invites a diff that includes unrelated approved work. | Record `1c80964` as T-045's review base. | **Open — Implementer; T-045 correction/coordination batch** |

### Review judgments

- The submitted change does correct the pinned example. Reserved names no longer collide with
  their `_`-suffixed neighbours, the old pinning test is replaced, direct reserved names and
  extensions are stable and idempotent, and reverting to the bare `_` suffix fails the five
  parametrized cases.
- The new test proves only `sanitize_component(reserved) !=
  sanitize_component(f"{reserved}_")`. It then asserts idempotence, which actually supplies the
  counterexample to the broader criterion: the legal input equal to the defused output must map
  to itself.
- At the exact T-045 head, the pre-existing decorated-reserved interaction remains:
  `sanitize_component("CON ")` returns `CON` and is not idempotent. The later, separately
  approved T-034 correction `313198d` strips the stem before the reserved check. At current
  `HEAD` (`51f3a03`), `CON`, `CON `, and `CON .mp4` are defused on the stripped stem,
  idempotence holds, and the deliberate merge agrees with Windows treating trailing dots and
  spaces as the same name. The combined behavior introduces no additional finding.
- Defusing adds only a 17-character marker to a genuinely reserved stem, so it does not put the
  component near the 200-byte limit. Extensions survive the direct and combined-head probes.

### Checks run

All boundary checks used an archive of exact head `c0f4881`, with its `src/` forced ahead of
the current editable checkout.

| Check | Result |
|---|---|
| Boundary | `c0f4881` has sole parent `1c80964`; four changed files. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 67 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `pytest -q` | Passed: **587 passed, 5 skipped, 1 deselected**. |
| `pytest -q tests/unit` | Passed: **533 passed, 3 skipped**. |
| `pytest -q tests/integration` | Exit 5: no tests collected at this boundary. The default suite above passed. |
| Focused path baseline | Passed: **147 tests**. |
| Bare-underscore mutation | Replaced `_marker(stem)` with `_REPLACEMENT`: **5 failed, 142 passed**. Restored. |
| Exact legal-neighbour probe | `CON` and legal `CON-1bc43d851d28ada0` both sanitize to `CON-1bc43d851d28ada0`, at both `c0f4881` and current `HEAD`. |
| Combined-head path suite | Passed: **200 tests** at `51f3a03`. |
| Combined-head default suite | Passed: **796 passed, 6 skipped, 1 deselected** at `51f3a03`. |
| `git diff --check 1c80964..c0f4881` | Passed. |
| Mutation restoration | The archived source matches the `c0f4881` blob after restoration; the repository worktree was untouched. |

### Readiness

T-045 cannot be approved under its current pair of acceptance criteria. This is **Blocked**,
not Changes requested: choosing which guarantee the product actually means is a maintainer
scope decision, and collision policy with filesystem context is explicitly out of this task's
scope. After that decision, the remaining work gets one focused correction re-review. The
current implementation is still a real improvement over the bare `_` behavior; the blocker is
the stronger claim it does not and cannot establish alongside idempotence.

## 2026-07-26 — T-044 reviewed environment API

**Reviewer:** Codex (Reviewer)
**Task:** `T-044`
**Base:** `6c0a7735784696f3c93c66040983732109b34493`
**Head:** `d01a7821ff3900e857f3946737f0052ddedc640a`
**Platforms verified:** Linux locally; Windows not rerun
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status / owner / target |
|---|---|---:|---|---|---|---|
| `T044-R1` | **Medium** | **Yes** | Reviewed-public-API gate | `defined_public_names()` inspects only direct nodes in `tree.body` and only simple-name assignment targets. Public exports introduced under module-scope control flow or by destructuring are invisible. A runtime-present `if os.name: YTDLP_VERSION = "unreviewed"` left the ownership test green, as did `YTDLP_VERSION, YTDLP_USABLE = ...`. The task's gate therefore does not meet its acceptance criterion that adding a public function or constant outside the independent API fails. | Collect every name bound in module scope, including definitions inside module-level `if`/`try`/loop/match blocks, destructuring targets, and Python 3.14 type aliases, while excluding function/class-local bindings and imports deliberately. Add at least conditional and tuple-assignment survivor regressions. If `__all__` is adopted, compare it to the independent expectation as an additional check, not as a substitute for the ownership boundary. | **Open — Implementer; T-044 correction batch** |
| `T044-R2` | **Low** | **No** | Coordination accuracy | At `d01a782`, `TASKS.md` puts both T-044 and T-045 in In Review, but `STATUS.md` lists only T-045 under In progress and removes T-044 from Next. This misses the task's documentation-reconciliation criterion at its own review head. Later coordination work now lists both at `51f3a03`. | No further correction for the state list; retain the current two-task wording. | **Resolved at current `HEAD` (`51f3a03`)** |
| `T044-R3` | **Low** | **No** | Review-boundary metadata | T-044's current task entry records stale base `fb2dab9`; its actual parent is `6c0a773`. Using the recorded base would include seven unrelated commits. | Replace the stale base with `6c0a773`. | **Open — Implementer; T-044 correction/coordination batch** |

### Review judgments

- The expected API is genuinely independent at this boundary: `REVIEWED_PUBLIC_API` is a
  hand-transcribed eight-name literal, and it exactly matches the eight direct public
  definitions in `environment.py`. Production does not supply the expectation.
- Direct public constants, functions, classes, and annotated constants each fail the ownership
  test independently. A private constant is correctly allowed. Renaming `APP_SLUG` to a private
  internal name while updating its internal use fails on the reverse-direction assertion.
- The two surviving mutations are ordinary module bindings, not dynamic tricks such as
  `globals()[...]`. They establish the same defect class at both the control-flow traversal and
  assignment-target seams.
- `Path(module.__file__)` is sound for this source test. If `__file__` is absent, the helper
  fails rather than silently passing; frozen/import-only modules are not this test's execution
  environment.
- `6c0a773..d01a782` changes no production source. Environment resolution, candidate ordering,
  ffmpeg detection, and the architecture ownership split are behaviorally unchanged.
- Apart from the T-044 omission recorded as R2, the bounded `TASKS.md` and `STATUS.md` Ready
  lists agree on T-012, T-038, T-014, and T-015, and the start-here text points to T-012.

### Checks run

All boundary checks used an archive of exact head `d01a782`, with its `src/` forced ahead of
the current editable checkout.

| Check | Result |
|---|---|
| Boundary | `d01a782` has sole parent `6c0a773`; three changed files and no `src/**` change. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 67 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `pytest -q` | Passed: **640 passed, 5 skipped, 1 deselected**. |
| `pytest -q tests/unit` | Passed: **586 passed, 3 skipped**. |
| `pytest -q tests/integration` | Exit 5: no tests collected at this boundary. The default suite above passed. |
| Focused environment baseline | Passed: **22 tests**. |
| Direct declaration mutations | A public constant, function, class, and annotated constant each failed the API test independently; a private constant passed. All were restored. |
| Removed-export mutation | Renaming `APP_SLUG` private and updating its internal use failed the reverse check with `['APP_SLUG'] disappeared`. Restored. |
| Conditional-export mutation | Runtime `YTDLP_VERSION` existed under `if os.name`, but the API test **passed** and detected no addition. Restored. |
| Destructuring-export mutation | Public `YTDLP_VERSION, YTDLP_USABLE = ...` left the API test **passing**. Restored. |
| Independent expectation | The literal expected set and the parsed direct-definition set were equal at `d01a782`. |
| `git diff --check 6c0a773..d01a782` | Passed. |
| Mutation restoration | The archived source matches the `d01a782` blob after restoration; the repository worktree was untouched. |

### Readiness

T-044 is **Changes requested** because `T044-R1` is a blocking Medium gap in the gate this task
exists to deliver. The direct declaration cases and reverse check are useful and verified, but
the two surviving ordinary exports keep the first acceptance criterion open. Return one
correction batch covering the defect class and the two review-base metadata fixes; the task's
remaining standard budget is one focused correction re-review.

## 2026-07-26 — T-044 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-044`
**Correction base:** `51f3a03a3ca273e1431a1dab2930bc7df8af7f1a`
**Head:** uncommitted working tree on `main`
**Review unit:** `tests/unit/test_environment.py` plus T-044 coordination changes;
`ai/REVIEWS.md` excluded
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T044-R1` | **Medium** | **Yes** | **Open — direct continuation.** The two originally reported survivors are fixed: planting `if os.name: YTDLP_VERSION = ...` or a destructuring `YTDLP_VERSION, YTDLP_USABLE = ...` in the real module makes the ownership test fail. The runtime and source halves are independently load-bearing exactly as reported. The corrected gate still misses ordinary bindings at the same boundary, however. A non-executed platform `match` capture (`case "nonesuch" as YTDLP_VERSION`) is absent from `vars()` and `_declared_names()` never reads match patterns, so the ownership test passes. A runtime `globals()["YTDLP_VERSION"] = ...` also passes when that name was first bound as an import alias, because `_imported_names()` subtracts it from the final runtime namespace and the source half cannot see the dynamic overwrite. Both are public constants outside the independent API. |
| `T044-R2` | **Low** | **No** | **Resolved, unchanged.** Current `TASKS.md` and `STATUS.md` list both T-044 and T-045 in review. |
| `T044-R3` | **Low** | **No** | **Resolved.** T-044 now records actual parent `6c0a773`, not stale `fb2dab9`. |

### Correction-diff judgments

- The correction is a substantial improvement. It kills the exact conditional and
  destructuring mutations from the initial review, covers common statement targets, and avoids
  asking production for the expected API.
- Both halves are demonstrably live. Setting `runtime` empty failed only the
  `globals()`-assignment case (**1 failed, 48 passed**). Removing `_declared_names()` from the
  union failed only the non-executed platform-guarded case (**1 failed, 48 passed**).
- The remaining misses arise at the seam between those halves. Runtime import subtraction uses
  source provenance without accounting for a later dynamic overwrite, while the source walker
  enumerates statement targets but omits `ast.MatchAs`/other pattern bindings.
- The walker is not yet scope-accurate in the other direction either. A walrus or exception
  alias inside a function is reported as a module public name because `ast.walk(node)` and the
  final `ast.walk(tree)` descend into function bodies; a completed module-level
  `except ... as EXC` is also reported after Python has deleted `EXC`. These false positives do
  not independently block approval, but confirm that the correction's “scope-aware” claim is
  not established.
- A module-level import inside `try` was correctly excluded. The defect-class audit is also
  correct: the only other AST source gate is `test_layering.py`; it deliberately uses
  `ast.walk` because imports inside function bodies still violate layering, and its synthetic
  nested-function import case covers that behavior.

### Independent checks and probes

| Check | Result |
|---|---|
| Original conditional mutation in real `environment.py` | Ownership test failed on `YTDLP_VERSION`. Restored. |
| Original destructuring mutation in real `environment.py` | Ownership test failed on `YTDLP_USABLE` and `YTDLP_VERSION`. Restored. |
| Runtime-half removal | **1 failed, 48 passed**; only `globals-assignment` failed. Restored. |
| Source-half removal | **1 failed, 48 passed**; only the non-executed platform guard failed. Restored. |
| Platform `match` capture in real `environment.py` | Ownership test **passed** even though `YTDLP_VERSION` would be a public module binding on the matched platform. Restored. |
| Import-alias dynamic overwrite in real `environment.py` | Ownership test **passed** with runtime public `YTDLP_VERSION = "unreviewed"`. Restored. |
| Module-level `try` import | Correctly excluded from the module-owned API. |
| Scope probes | Module-level expired exception alias was reported; function-local walrus and function-local exception alias were also reported as public. |
| Focused environment baseline | **49 passed**. |
| Mutation restoration | The temporary source and test files match the uncommitted review boundary; the repository source/test worktree was untouched. |

### Readiness and exhausted budget

`T044-R1` remains open, so T-044 is not approved. This focused pass exhausts the ordinary
review budget with only a blocking Medium finding remaining. Per `AGENTS.md` §9 the verdict is
therefore **Blocked**, not another automatic Changes requested loop. The maintainer must choose
whether to authorize another focused pass, accept the documented risk, narrow the gate's
supported binding model, or carry the remainder into a named follow-up task.

## 2026-07-26 — T-045 focused decision re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-045`
**Correction base:** `51f3a03a3ca273e1431a1dab2930bc7df8af7f1a`
**Head:** uncommitted working tree on `main`
**Review unit:** `tests/unit/test_paths.py`, `DAT-002`, and T-045/T-046 coordination changes;
`ai/REVIEWS.md` excluded
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T045-R1` | **Medium** | **No** | **Resolved by maintainer decision `DAT-002`.** The original absolute non-collision criterion is removed rather than pretended true. Keeping deterministic idempotence, retaining the digest improvement against `COM1_`, and assigning filesystem-aware uniqueness to T-046 is a coherent trade-off. The implementation meets the reachable parts of the narrowed criterion. |
| `T045-R2` | **Low** | **No** | **Resolved.** T-045 now records actual parent `1c80964`. |
| `T045-R3` | **Medium** | **Yes** | **Open — correction overclaim.** `DAT-002` says “the residual colliding set is pinned by test,” and the new test says it pins the “exact bound” and that the only colliders are the reserved name, its trailing-dot/space forms, and the defused output. It checks only six hand-picked candidates. Direct counterexamples exist for every parametrized reserved name: `defused + " "` and `defused + "."` sanitize to `defused`; control-character forms such as `"CON\\t"` and `"C\\x00ON"` do too. The test therefore passes while the claimed exact set is incomplete. The narrowed practical-neighbour promise is sound, but the decision and test add a stronger guarantee they do not establish. Remove the “only”/“exact set” claim and state that normalization creates other equivalence classes, or define a precise input domain and prove the claimed bound over it. T-046 should remain the sole uniqueness guarantee. |

### Decision and correction-diff judgments

- `DAT-002` states the central impossibility argument and selected trade-off honestly:
  idempotence forces the defused output to be a fixed point, while real uniqueness belongs at a
  layer with filesystem and queued-job context.
- The statement that the *exact residual colliding set* is pinned is not honest yet. The new
  test computes equality only within its local candidate list; it does not constrain any input
  omitted from that list.
- The renamed plausible-neighbour test retains the old substance. Reverting the digest to the
  bare `_` suffix makes its five cases fail. The new residual test adds five more failures, for
  **10 failed, 195 passed** in the focused path suite.
- T-046 is an appropriate owner for absolute uniqueness and explicitly covers existing files,
  queued jobs, concurrent writers, and preview/write agreement. Its before-first-release
  assumption is recorded both in `DAT-002` and the canonical task with an acceptance item that
  discharges it. That is sufficient at Phase 2 planning time; release preparation must treat
  the assumption as a gate rather than merely raising priority.
- `DAT-002` also says dropping idempotence would make sanitization non-deterministic across
  processes. Non-idempotence does not logically imply nondeterminism; the load-bearing reason
  is that applying a deterministic non-idempotent sanitizer twice changes the path. This
  wording should be corrected with R3, though it does not change the selected decision.

### Independent checks and probes

| Check | Result |
|---|---|
| Focused path baseline | **205 passed**. |
| Plausible-neighbour assertion | `reserved_` remains distinct for COM1, CON, aux, LPT¹, and NUL. |
| Bare-underscore mutation | **10 failed, 195 passed**; both five-case collision tests failed. Restored. |
| Residual-set probe | For every parametrized reserved name, `defused + " "` and `defused + "."` also map to `defused`; tab and embedded-NUL forms provide further omitted inputs. |
| Production diff | No `src/**` file differs from `51f3a03`; the digest implementation is unchanged. |
| Mutation restoration | Temporary `core/paths.py` and path tests match the uncommitted review boundary; the repository source/test worktree was untouched. |

### Readiness and exhausted budget

T045-R1 is resolved by the accepted scope decision, but the correction overstates the narrowed
guarantee in an accepted decision and a test that does not prove its own name. T045-R3 is a
blocking Medium correction finding, so T-045 is not approved. This focused pass exhausts the
ordinary review budget; under `AGENTS.md` §9 the verdict is **Blocked** pending a maintainer
choice: authorize one more focused documentation/test correction pass, narrow and accept the
documented bound now, or carry the precision fix into a named follow-up.

## 2026-07-26 — T-044/T-045 focused re-review shared checks

These checks apply to the complete uncommitted correction boundary
`51f3a03..working tree`, excluding reviewer-owned `ai/REVIEWS.md`.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 70 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 55 source files. |
| `mypy --platform win32` | Passed: no issues in 55 source files. |
| Full suite | Passed: **820 passed, 6 skipped, 1 deselected**. |
| Baseline suite at `51f3a03` | Passed: **796 passed, 6 skipped, 1 deselected**. |
| `git diff --check 51f3a03 -- . ':!ai/REVIEWS.md'` | Passed. |
| Working tree after review | Reviewer changed only `ai/REVIEWS.md`; all temporary mutations were restored outside the repository. |

## 2026-07-26 — T-044 maintainer-authorized final focused re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-044`
**Correction base:** `51f3a03a3ca273e1431a1dab2930bc7df8af7f1a`
**Head:** uncommitted working tree on `main`
**Review unit:** `tests/unit/test_environment.py` plus T-044 coordination changes;
`ai/REVIEWS.md` excluded
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T044-R1` | **Medium** | **Yes** | **Open — direct continuation.** The round-one conditional and destructuring survivors and the round-two `MatchAs` and `MatchStar` survivors now fail the real ownership test. The scope-stopping traversal also removes the reported function-local and expired-exception false positives. It stops too early at `def`, `class`, and `lambda`, however: their bodies open nested scopes, but decorators, function/lambda defaults, and class bases are evaluated in the enclosing module scope. On Linux, planting `if os.name == "nt": def _probe(x=(YTDLP_VERSION := "unreviewed")): ...` in the real `environment.py` left the ownership test passing and `defined_public_names()` empty. On Windows that default expression creates the public module attribute. Equivalent non-executed probes through a function decorator, class base, and lambda default also returned no public name. This contradicts the stated support for walrus bindings nested in module-level control flow and the acceptance criterion that adding an unreviewed public constant fails. |
| `T044-R2` | **Low** | **No** | **Resolved, unchanged.** The bounded coordination state remains aligned. |
| `T044-R3` | **Low** | **No** | **Resolved, unchanged.** The task records base `6c0a773`. |

### Correction-diff judgments

- `_module_scope_nodes()` correctly distinguishes nested bodies from module-level control flow,
  but a whole `FunctionDef`, `ClassDef`, or `Lambda` is not one indivisible evaluation scope.
  The body must be skipped while fields evaluated in the enclosing scope remain reachable.
- The accepted dynamic imported-alias rebinding limitation is stated precisely and pinned:
  changing the runtime half to include imported names made the blind-spot test fail as
  instructed. It is not reopened by this review.
- Both union halves and the match handling are load-bearing exactly as reported. Emptying the
  runtime half failed only `globals-assignment` (**1 failed, 57 passed**); emptying the source
  half failed only the two non-executed cases (**2 failed, 56 passed**); removing match-pattern
  handling failed only the platform-match case (**1 failed, 57 passed**).
- A module-level import inside `try` is excluded correctly, a completed module-level
  `except ... as EXC` leaves no reported name, and a dynamic `globals()` assignment is caught.
- The defect-class audit remains correct. The only other source AST gate is
  `tests/unit/test_layering.py`; it intentionally uses `ast.walk` and already tests an import
  nested in a function body.

### Independent probes

| Check | Result |
|---|---|
| Original `if os.name: YTDLP_VERSION = ...` in real module | Ownership test failed on `YTDLP_VERSION`. Restored. |
| Original destructuring in real module | Ownership test failed on `YTDLP_USABLE` and `YTDLP_VERSION`. Restored. |
| Platform `MatchAs` in real module | Ownership test failed on `YTDLP_VERSION`. Restored. |
| Platform `MatchStar` in real module | Ownership test failed on `YTDLP_VERSION`. Restored. |
| Windows-guarded function-default walrus in real module, run on Linux | Ownership test **passed** and reported no added public name. Restored. |
| Same default with an executed guard | Runtime created `YTDLP_VERSION`; ownership test failed. Restored. |
| Adjacent enclosing-scope expressions | Non-executed function decorator, class base, and lambda-default walruses each produced an empty reported set. |
| Dynamic imported-alias limitation pin | Closing the blind spot made its pinning test fail. Restored. |
| Focused environment baseline | **58 passed** as part of the 263-test focused run. |
| Mutation restoration | Temporary source and tests match the review boundary byte-for-byte. |

### Readiness and exhausted budget

`T044-R1` remains a blocking Medium acceptance-criterion gap. This was the
maintainer-authorized pass after the ordinary budget was exhausted, so `AGENTS.md` §9 requires
**Blocked**, not another automatic correction loop. Approval now needs a fresh maintainer
choice: authorize another tightly focused pass, explicitly narrow the supported binding model,
accept the documented risk, or carry the remainder into a named follow-up.

## 2026-07-26 — T-045 maintainer-authorized final focused re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-045`
**Correction base:** `51f3a03a3ca273e1431a1dab2930bc7df8af7f1a`
**Head:** uncommitted working tree on `main`
**Review unit:** `tests/unit/test_paths.py`, `DAT-002`, and T-045/T-046 coordination changes;
`ai/REVIEWS.md` excluded
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Approved with follow-ups**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T045-R1` | **Medium** | **No** | **Resolved by `DAT-002`, unchanged.** The decision keeps idempotence, limits the sanitizer to a reachable plausible-neighbour promise, and assigns absolute uniqueness to filesystem-aware T-046. |
| `T045-R2` | **Low** | **No** | **Resolved, unchanged.** The task records base `1c80964`. |
| `T045-R3` | **Medium** | **No** | **Resolved.** The test, task criterion, and dated `DAT-002` amendment no longer claim an exact colliding set. They state the many-to-one normalization trade-off, assert the fixed point and plausible-neighbour distinction, and use trailing dot/space forms only to demonstrate that the class is wider. The corrected rationale turns on repeated application changing the path, not on the false implication that non-idempotence means nondeterminism. |

### Decision and correction-diff judgments

- The rewritten acceptance criteria are reachable and met. The renamed
  `test_defusing_a_reserved_name_does_not_collide_with_its_plausible_neighbour` retains the old
  five-case assertion, including idempotence.
- `test_a_defused_name_is_a_fixed_point_and_shares_it_with_a_whole_class` makes no exhaustive
  claim. Its assertions hold for all five reserved forms and explicitly demonstrate additional
  colliders through reserved-name and defused-output trailing dot/space forms.
- Reverting reserved-name defusing to the bare `_` suffix failed exactly the two five-case
  tests (**10 failed, 195 passed**), so the narrowed practical distinction remains pinned.
- `DAT-002`'s before-first-release assumption is safe to leave explicit at this stage. T-046 is
  a concrete Phase 2 task with an owner, dependencies, concurrency/existing-file criteria, and
  an acceptance item that discharges the assumption. It remains a release prerequisite, not a
  sanitizer guarantee.

### Readiness

No blocking T-045 finding remains. T-045 is **Approved with follow-ups**; T-046 owns absolute
filesystem-aware uniqueness before first release.

## 2026-07-26 — T-044/T-045 final focused re-review shared checks

These checks apply to the complete uncommitted correction boundary
`51f3a03..working tree`, excluding reviewer-owned `ai/REVIEWS.md`.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 70 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 55 source files. |
| `mypy --platform win32` | Passed: no issues in 55 source files. |
| Full suite | Passed: **829 passed, 6 skipped, 1 deselected**. |
| Focused environment + paths | Passed: **263 passed**. |
| `git diff --check 51f3a03 -- . ':!ai/REVIEWS.md'` | Passed. |
| Working tree after review | Reviewer changed only `ai/REVIEWS.md`; all temporary mutations were restored outside the repository. |

## 2026-07-26 — T-044 second-decision focused re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-044`
**Correction base:** `51f3a03a3ca273e1431a1dab2930bc7df8af7f1a`
**Head:** uncommitted working tree on `main`
**Review unit:** `tests/unit/test_environment.py`, the new `ai/TESTING.md` gate dependency,
and T-044 coordination changes; `ai/REVIEWS.md` excluded
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T044-R1` | **Medium** | **Yes** | **Open — direct continuation at the new design boundary.** Runtime namespace inspection catches every historical survivor that executes, including default/decorator/base-expression walruses without syntax-specific code. The two completeness claims around it are not established. First, `_imported_names()` does not answer exactly which runtime names came from imports; it answers which aliases occur in import statements. Planting `try: import package_that_does_not_exist as YTDLP_VERSION` with `except ImportError: YTDLP_VERSION = "unreviewed"` in the real module created the public runtime constant, yet the ownership test passed because the failed import alias was subtracted. This is an ordinary optional-import fallback, not the accepted dynamic imported-name rebinding blind spot—the import never bound the name. Second, the Linux/Windows matrix compensates only for branches distinguished by those two hosts. An export guarded by an unset environment variable passed on Linux and would take the same branch in the unchanged Windows workflow; enabling that variable on the same supported host created the public name and made the test fail. Architecture, optional-dependency, feature-flag, and other runtime-state guards have the same gap. The local pin itself uses `sys.platform == "nonesuch"`, which is false on both runners, so its claim that the other runner covers that case is literally untrue. These counterexamples leave the broad acceptance criterion (“adding a public function or constant … fails”) unmet and contradict the docs’ claim that only unsupported platforms remain. |
| `T044-R2` | **Low** | **No** | **Resolved, unchanged.** `TASKS.md` and `STATUS.md` agree that T-045 is complete and T-044 remains in review. |
| `T044-R3` | **Low** | **No** | **Resolved, unchanged.** The task records base `6c0a773`. |

### Correction-diff judgments

- Deleting binding-shape parsing is a sound simplification for names the interpreter actually
  bound during the test run. A public constant and function failed independently; one combined
  real-module mutation reported conditional, destructured, match-captured, default-walrus,
  decorator-walrus, and class-base-walrus names together. A private name remained allowed.
- The import traversal is scope-correct for locating import *statements*: imports inside
  functions/classes are not module bindings, while module-level conditional imports are found.
  The defect is provenance, not traversal—an import statement may fail or its alias may later
  hold a different value.
- The existing dynamic imported-alias limitation remains deliberately accepted and pinned. The
  failed-import fallback above is distinct because no imported value ever entered the namespace
  and the fallback is a direct ordinary assignment.
- The CI matrix is present and its default pytest step runs on both `ubuntu-latest` and
  `windows-latest`. It is load-bearing for an actual `win32` guard, but cannot turn arbitrary
  runtime conditions true.
- Several correction comments still describe the retired two-half design:
  `_module_from_source` says “both halves,” `SMUGGLING_ROUTES` refers to a source half, and the
  T-044 entry retains a present-tense paragraph saying the gate unions runtime and source.
  These are cleanup within the open R1 correction, not a separate blocker.
- Moving T-045 to Complete is consistent with the prior **Approved with follow-ups** verdict;
  T-046 remains its explicit before-release owner. No T-045 behavior changed.

### Independent checks and probes

| Check | Result |
|---|---|
| Eight executed historical survivors in real `environment.py` | Public constant and function failed independently; conditional, destructuring, match capture, default walrus, decorator walrus, and class-base walrus were all reported by one combined ownership-test failure. Restored. |
| Private-name mutation | Ownership test passed. Restored. |
| Failed-import fallback in real module | Runtime `YTDLP_VERSION == "unreviewed"` existed, but the ownership test **passed**. Restored. |
| Environment-guarded export, variable absent | Ownership test **passed** on Linux. |
| Same export, same host, variable enabled | Runtime public name existed and ownership test failed. Restored. |
| Drop import subtraction | **5 failed, 53 passed**. Restored. |
| Make `defined_public_names()` empty | **17 failed, 41 passed**. Restored. |
| Rename reviewed `APP_SLUG` private and update its use | Reverse ownership assertion failed on `APP_SLUG`. Restored. |
| Focused environment + paths baseline | **263 passed**. |
| Mutation restoration | Temporary source and tests match the review boundary byte-for-byte. |

### Readiness and exhausted budget

`T044-R1` remains a blocking Medium acceptance-criterion gap after the second maintainer design
decision. Per `AGENTS.md` §9 there is no automatic sixth correction pass. Given that T-044
changes no production behavior and blocks no downstream task, the maintainer should now choose
explicitly among:

1. narrow the acceptance criterion to the runtime namespace observed under the states CI
   actually executes, and record failed/import-rebound aliases plus other unexecuted conditions
   as accepted limitations;
2. redesign the expectation so imported bindings are reviewed rather than inferred away;
3. retire or carry the gate into a named follow-up; or
4. authorize another tightly focused correction pass.

The current wording cannot be approved as option 1 because it claims broader coverage than the
implementation and matrix provide.

## 2026-07-26 — T-044 second-decision shared checks

These checks apply to the complete uncommitted boundary `51f3a03..working tree`, excluding
reviewer-owned `ai/REVIEWS.md`.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 70 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 55 source files. |
| `mypy --platform win32` | Passed: no issues in 55 source files. |
| Full suite | Passed: **829 passed, 6 skipped, 1 deselected**. |
| Focused environment + paths | Passed: **263 passed**. |
| `git diff --check 51f3a03 -- . ':!ai/REVIEWS.md'` | Passed. |
| Production diff | No `src/**` file differs from `51f3a03`; T-044 and T-045 remain test/docs-only at this boundary. |
| Working tree after review | Reviewer changed only `ai/REVIEWS.md`; all temporary mutations were restored outside the repository. |

## 2026-07-26 — T-044 maintainer final disposition

**Reviewer:** Codex (Reviewer)
**Task:** `T-044`
**Boundary:** `51f3a03a3ca273e1431a1dab2930bc7df8af7f1a..uncommitted working tree`
on `main`; `ai/REVIEWS.md` excluded
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Approved with follow-ups**

### Finding dispositions

| ID | Severity | Blocks approval | Final disposition |
|---|---|---:|---|
| `T044-R1` | **Medium** | **No** | **Resolved by narrowed scope and explicit maintainer acceptance.** The gate promises only that, under the interpreter/platform/configuration actually executing the suite, a public runtime name not accounted for by an import statement is reported. The false-guard, failed-import fallback, and dynamic imported-name rebinding gaps are stated in `defined_public_names`, asserted by dedicated tests, recorded in `ai/TESTING.md`, and owned by T-047. The maintainer directed T-044 forward without another mechanism-design loop. |
| `T044-R2` | **Low** | **No** | **Resolved.** T-044 and T-045 are complete in both current-truth coordination files; T-014 is next. |
| `T044-R3` | **Low** | **No** | **Resolved.** The task records review base `6c0a773`. |

### Final judgments

- The narrow guarantee is established directly by `vars(module)` and by positive tests over all
  historical executed binding routes. Returning an empty set fails 17 tests; dropping import
  subtraction fails 5; removing a reviewed runtime name fails the reverse assertion.
- Each excluded class has a negative pin that would fail if the behavior changed without its
  caveat changing with it. No broader completeness claim remains in the authoritative
  acceptance criteria or gate documentation.
- While recording the final disposition, stale references to the retired runtime/source union
  were removed from the task and test comments, and the acceptance criterion was rewritten to
  match the demonstrated runtime scope.
- T-047 is the correct owner for any future decision about strengthening this Low-priority test
  gate. T-014 remains a separate High-risk persistence task and is not expanded with unrelated
  T-044 cleanup.

### Final checks

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 70 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 55 source files. |
| `mypy --platform win32` | Passed: no issues in 55 source files. |
| Full suite | Passed: **830 passed, 6 skipped, 1 deselected**. |
| Focused environment + paths after final coordination cleanup | Passed: **264 passed**. |
| `git diff --check` | Passed. |

### Readiness

T-044 is **Approved with follow-ups** and complete. No further T-044 review pass is pending.
T-047 carries the three accepted limitations; T-014 may start next on the critical path.

## 2026-07-26 — T-014 initial comprehensive review

**Reviewer:** Codex (Reviewer)
**Task:** `T-014`
**Platforms verified:** Linux locally; Windows not run

### Unit 1 — taxonomy amendment

**Base:** `92ab377cf445eb6f9d1e81b836b5b02772c35d9f`
**Head:** `d816fa0c89f1b0256d7f2856bd223b6e5c146f13`
**Verdict:** **Approved**

No findings.

- The `INTERRUPTED` / `WORKER_CRASH` distinction is real. The parent observes and classifies a
  worker crash while it is alive; startup recovery can infer only that the whole application
  stopped while persisted work was in flight.
- `ErrorKind.INTERRUPTED` is retryable and is not auto-retryable. That matches §7's policy and
  avoids relaunching directly into a download after an application-level interruption.
- Both taxonomy pins continue to transcribe §7 as literal sets. Neither imports or derives the
  expected member from production.
- Listing `INTERRUPTED` in `UNMAPPED_KINDS` is honest: it is created by startup recovery, not
  raised or classified from a surviving yt-dlp process.

### Unit 2 — persistence

**Base:** `d816fa0c89f1b0256d7f2856bd223b6e5c146f13`
**Head:** `cfb66af5433044e33e057c50d9e23a1fe5350060`
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Finding | Required correction |
|---|---|---:|---|---|
| `T014-R1` | **Critical** | **Yes** | The narrowed no-secret database criterion is still false at the persistence boundary. First, `DownloadRequest.proxy` accepts any non-empty string, but `strip_credentials()` examines only `urlsplit(...).netloc`; the model-valid `user:pass@proxy.invalid:8080` therefore returns unchanged and is serialized with both credentials. Second, `_job_to_values()` writes `error_message` verbatim. A failed job whose diagnostic is `proxy failed: http://secretuser:hunter2@proxy.invalid:8080` stores `hunter2` in the raw row even though the request copy is stripped. The same unrestricted diagnostic sink can persist a cookie path. Downstream proxy validity is not a defense: the job is persisted before a worker can reject the setting. This is an exposed-credential path and therefore Critical under `AGENTS.md` §9. | Enforce the exclusion at the database sink across every persisted field that can carry diagnostics or settings, and handle accepted proxy forms without relying on `urlsplit()` recognizing a netloc. Add raw-database negative tests for a scheme-less credential-bearing proxy and for credentials/cookie paths arriving through an error message; audit all sibling stored text fields. Preserve the maintainer-approved verbatim job URL exception explicitly. |
| `T014-R2` | **High** | **Yes** | A migration and its `user_version` bump are not atomic. `migrate()` runs `BEGIN; <DDL>; COMMIT;`, then sets `PRAGMA user_version` and commits again. A simulated interruption on the pragma left both tables committed with version 0; the next `migrate()` failed with `OperationalError: table jobs already exists`. This is exactly the schema/version split the docstring says cannot happen and violates the migration and unclean-exit guarantees. | Put the version pragma before the migration transaction's `COMMIT`, with rollback/error handling, and add a deterministic interruption test proving both schema and version roll back together. SQLite accepts `PRAGMA user_version` inside this transaction; a local `BEGIN; CREATE TABLE; PRAGMA user_version=1; ROLLBACK` left neither the table nor the version. |
| `T014-R3` | **High** | **Yes** | The only frozen-artifact specification collects `resources/icons/*` and yt-dlp data, but not `persistence/migrations/*.sql`. PyInstaller does not collect arbitrary package data through Python import analysis. In that environment `available_migrations()` sees an empty directory, `connect()` silently creates a version-0 database with no tables, and the first repository write fails `OperationalError: no such table: jobs`. The persistence layer therefore cannot run in the no-Python artifact required by `REL-001`. | Collect the migration SQL in `packaging/tracks-and-trails.spec` and exercise database creation/schema version from inside the frozen artifact on both CI platforms. Prefer also failing clearly when a build that expects migrations finds none, so a packaging omission cannot masquerade as a valid version-0 schema. |
| `T014-R4` | **Medium** | **Yes** | `test_every_migration_runs_forward_from_every_prior_version_with_data_intact` does not construct historical data. It replays the old DDL but seeds each old schema through the **current** `JobRepository`, current model, and current JSON serializer. When a future request field or representation changes, a real v1 row has the old JSON shape, while this harness writes the new shape into a v1 table before running v2; a missing data migration can therefore pass. Conversely, a current repository that expects a newly added SQL column may fail while seeding the old schema before the migration is exercised. The test is not the v4-capable historical gate claimed by the task and `ai/TESTING.md` §7. | Freeze representative seed data or database fixtures for each schema version while that version is current, then migrate those historical bytes using only the new runner/repository. Mutation-check a representation-changing migration, not only DDL replay with current objects. |
| `T014-R5` | **Low** | **No** | `test_recovery_routes_through_the_state_machine` never calls `recover_interrupted()`. It directly calls `stored.with_failure()`, so it tests the already-covered model method rather than the repository seam named by the test. Replacing `JobRepository.recover_interrupted` at runtime with a function that always raises still left this test passing. A direct `replace(job, status=FAILED, error_kind=..., ...)` implementation with identical output would also satisfy the other recovery assertions, so the reported “writing FAILED directly” mutation did not isolate the claimed route. Current production does call `with_failure`; this is test-strength and mutation-evidence accuracy, not a present behavior defect. | Exercise `recover_interrupted()` with a state-machine spy or force an illegal source into the repository's recovered set and assert that the repository raises. Record mutation evidence for a behavior-preserving direct-state-write bypass. |

### Scope and decision judgments

- Widening startup recovery to `PROBING`, `RUNNING`, and `POST_PROCESSING` was the implementer's
  authority-order resolution to make. Architecture §5 names the exact set and outranks the
  stale single-status task/test wording; no new design choice was introduced.
- The maintainer-approved URL amendment is honest in what it gives up: a retryable durable job
  requires its source URL, and the URL is explicitly stored verbatim. The amendment itself does
  not overclaim. `T014-R1` concerns the narrower promise it retains—credentials and cookie data
  outside that source URL still reach other database fields.
- Creating `history` in version 1 while leaving writes to T-013 is a sound boundary. Its columns
  transcribe REQ-020's source URL, title, resolved path, format, size, and completion time; no
  premature history behavior is claimed.
- The SQL normalizer did not reveal a semantic blind spot in the current schema comparison.
  Both sides lose comments and whitespace only, while table, column, constraint, and index
  changes remain visible in `sqlite_master`.
- The POSIX-only integrity test is supplemented by the second crash test, which calls
  `Process.kill()` without a Windows skip and reopens and parses every persisted job before
  recovery. Windows execution remains unverified locally, as reported.

### Independent evidence

| Probe | Result |
|---|---|
| Scheme-less proxy | `strip_credentials("user:pass@proxy.invalid:8080")` returned the credential-bearing input unchanged. |
| Encoded userinfo, IPv6, and `file://` | The tested canonical authority forms were stripped while preserving their host/path; they do not close the scheme-less route. |
| Diagnostic credential sink | The serialized request omitted `hunter2`, but the same raw job row's `error_message` retained it. |
| Migration interruption | Raising on `PRAGMA user_version = 1` left `jobs` and `history` committed at version 0; retry failed because `jobs` already existed. |
| Atomic pragma control | Putting `PRAGMA user_version = 1` before `ROLLBACK` removed both the created table and the version bump. |
| Missing migration assets | With an absent migration directory, `connect()` produced version 0 and no tables; `JobRepository.add()` failed `no such table: jobs`. The frozen spec contains no persistence migration data rule. |
| Recovery seam test | The named test passed after replacing `recover_interrupted()` with an always-raising function, proving it never reaches that method. |
| Hard-kill tests | Focused Linux run passed both real-process kill tests. |

### Checks

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 72 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 57 source/test files. |
| `mypy --platform win32` | Passed: no issues in 57 source/test files. |
| Full default suite | Passed: **864 passed, 6 skipped, 1 deselected**. |
| Taxonomy-focused tests | Passed: **102 passed**. |
| Persistence-focused tests | Passed: **34 passed**. |
| `git diff --check 92ab377 d816fa0` | Passed. |
| `git diff --check d816fa0 cfb66af` | Passed. |

### Readiness

Unit 1 is **Approved**. Unit 2 has one Critical, two High, and one blocking Medium finding, so
it is **Changes requested**. The focused correction re-review should verify `T014-R1` through
`T014-R4`, check their correction diff for regressions, and re-check `T014-R5` if it is included
in the same batch. No reviewed source or test file was changed during this review; only this
historical review entry was appended.

## 2026-07-26 — T-014 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-014`
**Correction base:** `cfb66af5433044e33e057c50d9e23a1fe5350060`
**Head:** `e15dee473a5777549e17101123aceecdb25a8fe3`
**Review unit:** Persistence correction commit; the approved taxonomy amendment is unchanged
**Platforms verified:** Linux locally, including a real frozen build; Windows not run
**Verdict:** **Changes requested**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T014-R1` | **Critical** | **Yes** | **Open — direct continuation with correction regressions.** Redacting scalar strings by default does close the two original examples: adding a new scalar `DownloadRequest` field carrying a canonical credential caused it to be masked without listing the field, and canonical proxy/error-message cases are masked. The generic recognizer is not a safe database boundary, however. Credentials still reached the raw request JSON through the model-valid `secretuser:hunter2@proxy:8080` (single-label host), `secretuser:hunter2@éxample.invalid:8080` (Unicode host), and a string nested in `post_processors`; username-only userinfo and an IPv6 zone identifier also survived `redact()`. Cookie paths with spaces/quotes are only partly masked, while UNC, relative, and extended Windows paths with a space survived. The stated free-form boundary explicitly pins `password is hunter2` and a cookie value as unredacted even though the retained acceptance criterion says credentials and cookie content never reach the database. The opposite direction now corrupts frozen request behavior: `/downloads/cookie-videos` is persisted as `[redacted]`, and `%(uploader)s:%(id)s@example.invalid.%(ext)s` is rewritten. The first turns the user's absolute output directory into a relative path on retry, risking a write outside the directory the user chose—independently Critical under §9—and both violate the exact settings-freeze criterion. Ordinary prose such as `retry at 10:30@example.invalid` is also mangled. A heuristic applied to every functional string therefore neither excludes secrets nor preserves the request. |
| `T014-R2` | **High** | **Yes** | **Resolved.** `PRAGMA user_version` is inside the same transaction before `COMMIT`, and the exception path rolls back. Moving the pragma after `COMMIT` made the succeeding-script interruption test fail with tables committed at version 0. Removing the explicit rollback made the failed-migration test fail with `jobs` still visible. The `DiesAtCommit` subclass executes through the real commit and raises before any old-style following pragma could run, so it reproduces the original split rather than merely testing an ordinary SQL failure. |
| `T014-R3` | **High** | **Yes** | **Resolved.** The spec declares the migration data, an empty migration set now fails loudly, the internal CLI route runs before Qt, and both-platform CI invokes the real repository probe. Removing the spec data line failed the early unit gate. More importantly, an independent PyInstaller 6.21 Linux build placed `0001_initial.sql` under the artifact's internal package path; running that artifact with `--database-probe` reported one migration, schema version 1, wrote/read a real job, and exited successfully. Windows remains locally unverified, but the same artifact gate is correctly wired into the non-fail-fast Windows matrix job. |
| `T014-R4` | **Medium** | **Yes** | **Open — direct continuation.** `v1.sql` is now loaded before any current model, serializer, or repository touches it, and adding a temporary v2 migration made the missing-v2-fixture gate fail as intended. The data assertion is nevertheless byte equality over the old `jobs` columns. A legitimate temporary v2 migration that added forward metadata to the request JSON changed the stored bytes while preserving both rows and leaving both readable through the current repository; this harness would reject it. The representation-changing migration cited as the reason for historical fixtures is therefore exactly what the test forbids. It also seeds and compares no `history` row, so a future migration can discard completed-download history while this “data intact” gate passes. Assert preserved domain meaning with version-specific expectations, including every durable table, rather than requiring all old storage representations to remain byte-identical. |
| `T014-R5` | **Low** | **No** | **Resolved.** The rewritten test calls `recover_interrupted()`, forces `COMPLETED` into the recovered set, expects `IllegalTransitionError`, and proves the row remains unchanged. Replacing `recover_interrupted()` with an always-raising `AssertionError` now reaches the replacement and fails the test rather than passing unnoticed. |
| `T014-R6` | **Low** | **No** | **Open — correction cleanup.** `test_queue_order_survives_a_restart` contains its docstring twice. This has no behavioral effect; remove the duplicate line in the correction cleanup. |

### R1 focused judgments

- The sink inversion works only for direct scalar strings already present in the value mapping.
  It does not recursively protect tuple/list strings inside the serialized request, and a new
  SQL column still has to be added to `_job_to_values()` before the default loop can see it.
- Canonical percent-encoded userinfo, bracketed IPv6, `file://`, an empty password, and a
  canonical scheme-less dotted host were masked. The misses above are ordinary accepted model
  values within the claimed userinfo/path structures, not the acknowledged arbitrary-prose
  boundary.
- Partial cookie-path masking is still a leak: for a quoted path containing spaces the
  directory prefix remains in the stored diagnostic. Redaction must remove the complete path,
  not merely make the exact input string absent.
- Masking credentials inside an otherwise retained diagnostic is compatible with `NFR-006`.
  The problem is not that interpretation; it is that the recognizer changes non-secret
  diagnostics and functional request fields while known credentials still pass.
- `core.redaction.redact(str) -> str` is a usable seam for T-038, but T-038 must not inherit the
  present completeness or false-positive claims until R1 is redesigned.

### R4 budget

R4's historical-input half is materially improved, but the mandatory “data intact” gate remains
unmet after the ordinary initial-plus-focused budget. Per `AGENTS.md` §9, another review of R4
requires an explicit maintainer choice: authorize one more tightly focused verification, narrow
the criterion, or carry it into a named follow-up. R1 remains Critical and therefore continues
through correction and independent verification without further authorization.

### Independent checks and probes

| Check | Result |
|---|---|
| Scalar-field default-deny mutation | A newly added scalar request field containing `http://u:hunter2@proxy.invalid` was stored as `http://[redacted]@proxy.invalid`. Restored. |
| Credential adversarial probes | Single-label/Unicode hosts, username-only userinfo, IPv6 zone IDs, and a credential nested in `post_processors` survived; canonical dotted host, encoded `@`, bracketed IPv6, `file://`, and empty-password cases were masked. |
| Cookie-path adversarial probes | Quoted paths with spaces were only partly masked; UNC, relative, and extended Windows paths containing a space survived. |
| False-positive probes | A legitimate output directory became `[redacted]`; a legitimate output template and `10:30@example.invalid` prose were rewritten. |
| R2 old-order mutation | Intended interruption test failed: tables survived at version 0. Restored byte-identical. |
| R2 no-rollback mutation | Intended failed-migration test failed: `jobs` remained visible. Restored byte-identical. |
| R3 spec mutation | Spec-collection unit test failed. Restored byte-identical. |
| R3 real frozen build | PyInstaller 6.21 build succeeded on Linux; migration SQL was present and the in-artifact database probe passed. |
| R4 v2-fixture gate | Adding a temporary v2 migration without a v2 fixture failed the gate as intended. |
| R4 representation probe | A v2 JSON representation update changed bytes, preserved both rows, and remained readable by the current repository, demonstrating the byte-equality false positive. |
| R5 replacement probe | The always-raising replacement was reached; the rewritten test no longer passed. |
| Mutation restoration | All temporary repository mutations were restored; only this review entry remains modified. |

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 74 files already formatted. |
| `mypy src` | Passed: no issues in 32 source files. |
| `mypy` | Passed: no issues in 59 source/test files. |
| `mypy --platform win32` | Passed: no issues in 59 source/test files. |
| Focused redaction + persistence + crash tests | Passed: **66 passed**. |
| Full default suite | Passed: **899 passed, 6 skipped, 1 deselected**. |
| Source `--database-probe` | Passed: migrations 1, schema version 1, database ok. |
| Frozen Linux `--database-probe` | Passed with the same result from the built artifact. |
| `git diff --check cfb66af e15dee4` | Passed. |

### Readiness

T014-R2, R3, and R5 are resolved. T014-R1 remains Critical and T014-R4 remains a blocking
Medium, so the persistence unit is **Changes requested**. The next correction batch should
redesign R1 at the boundary between functional frozen data and arbitrary diagnostics rather
than extending the regex enumeration. R4 needs the maintainer disposition described above.

## 2026-07-26 — T-014 second focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-014`
**Correction base:** `e15dee473a5777549e17101123aceecdb25a8fe3`
**Head:** `a0fb4e4f3444b2e29c8872979431987a4fd70b6a`
**Review unit:** Persistence correction commit; R2, R3, and R5 are unchanged
**Platforms verified:** Linux locally; Windows not run; frozen build not rerun because R3's
specification and probe are unchanged
**Verdict:** **Changes requested**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T014-R1` | **Critical** | **Yes** | **Open — third direct survivor.** The field taxonomy is an improvement: the five supplied functional-value cases round-trip exactly, and caller prose cannot reach `error_message` through `add()`, `update()`, or startup recovery. The structured proxy bound is still false for a model-valid network-path reference. `proxy_without_credentials("//secretuser:hunter2@proxy.invalid:8080")` returns the input unchanged, and adding that request leaves both `secretuser` and `hunter2` in the raw database row. The first `urlsplit()` correctly puts this form in `netloc`, but `scheme_less = not parts.scheme or not parts.netloc` is true merely because the scheme is absent; reparsing `placeholder:////...` then loses the authority, sees no `@` in `netloc`, and returns the original. `http:///secretuser:hunter2@proxy.invalid:8080` is another accepted value that survives. This remains exposed credential material, hence Critical. Validate `DownloadRequest.proxy` to a deliberately supported grammar or make the persistence boundary fail closed for every value the model accepts; add raw-row cases for `//userinfo@host` and malformed authority forms. |
| `T014-R4` | **Medium** | **Yes** | **Open — the allowance is a blanket for a column.** Seeding `history` is corrected: deleting its two fixture rows makes the gate fail, and row deletion is now detected in both durable tables. However, once `(table, column)` is present in `TRANSFORMED_BY_MIGRATION`, comparison of that column is skipped for every fixture, row, and migration, and neither the stated reason nor an expected transformed value is checked. I added a temporary v2 migration that changed every stored request's `format_selector` to the valid but wrong string `wrong-format`, declared `("jobs", "request")` as transformed, and ran the actual test; it passed, including the current-repository readability check. Readability is not preserved domain meaning. Key an allowance to the relevant source/target migration and assert its version-specific expected semantic result; require a real reason instead of merely skipping equality. |
| `T014-R6` | **Low** | **No** | **Retracted — reviewer error.** `test_queue_order_survives_a_restart` has exactly one docstring at both `e15dee4` and `a0fb4e4`. The earlier observation came from concatenated tool output, not either file. No correction was required. |
| `T014-R7` | **High** | **Yes** | **New correction regression — the repository now discards the diagnostic that its contracts require it to preserve.** Persisting a failed `Job` replaces `Job.error_message` with `_STORED_MESSAGES[kind]`; reading it back therefore does not round-trip the job. This directly conflicts with `core/models.py` (`Job` is a direct persistence mapping and `with_failure()` stores the message verbatim), `downloader/protocol.py` (the persisted fields mirror `Failed`), `ARCHITECTURE.md` §7 (the original message is always preserved verbatim alongside classification), and `NFR-006` (extractor messages are never swallowed or replaced by a generic message). The proposed destination cannot currently cure the loss: T-038's per-job log does not exist, while stored messages already tell the user to “See the job log.” This is a user-visible requirement failure with no present workaround, so it is High. The privacy/verbatim conflict now needs a maintainer design decision, not another implementer-local reinterpretation in `TASKS.md` and `STATUS.md`: either introduce an authorized durable diagnostic seam before making this repository lossy, or amend the architecture/model/protocol contracts and reconsider whether `error_message` belongs in the schema this phase. Any chosen design must also close R1 without persisting credentials. |

### Focused judgments

- The split between functional, structured, and prose fields is useful, but its proxy branch
  still assumes a URL grammar that the model does not enforce. The third Critical survivor is
  enough evidence to stop extending examples around the current parser. The accepted input
  grammar and persistence treatment need to be designed together.
- Storing `post_processors` verbatim is acceptable for T-014's intended domain: the values are
  yt-dlp post-processor names, and the adapter validates them against yt-dlp's registry before
  use. The core model does accept arbitrary strings, so this judgment does not support a broader
  claim that every model-valid nested string is non-sensitive; no such broader claim should be
  made.
- Project-authored summaries can be useful alongside diagnostics, but substituting one for the
  other is not the behavior the current requirement, architecture, model, or protocol specifies.
  Moving the verbatim diagnostic to a future cache log is a sequencing and durability decision,
  especially because the architecture classifies that log under cache rather than the database.
- R4's new `history` coverage is real. The remaining defect is specifically the transform
  exception: an unchecked skip is not evidence that a declared transformation preserved data.
- R6 is closed without a code change. Historical review entries are not silently rewritten, so
  this entry records the correction to the review record.

### Independent probes and mutation checks

| Check | Result |
|---|---|
| Network-path proxy | `//secretuser:hunter2@proxy.invalid:8080` was returned unchanged; a real repository write retained both credential components in the raw row. |
| Other parser edges | Normal scheme/scheme-less, encoded-userinfo, Unicode-host, IPv6-zone, and second-`@` cases were stripped; `http:///userinfo@host` survived, while bare/empty-authority forms such as `@`, `user:pass@`, and `http://@` were changed into invalid values rather than preserved. |
| Error-message write paths | `add()` and `update()` persisted only the project-authored message; `recover_interrupted()` persisted its authored interruption message. Caller prose did not reach the raw rows. |
| Store caller message mutation | Failed 1 intended database-secret test. Restored byte-identical. |
| Skip proxy stripping mutation | Failed all 7 intended parametrized cases. Restored byte-identical. |
| Remove scheme-less reparse mutation | Failed 4 intended cases. Restored byte-identical. |
| Rewrite functional values mutation | Failed all 5 exact round-trip cases. Restored byte-identical. |
| Remove history fixture rows mutation | Failed the migration test because `history` was empty. Restored byte-identical. |
| R4 corrupt-but-readable probe | A temporary v2 rewrite of `jobs.request.format_selector` to `wrong-format` passed when `jobs.request` was listed in `TRANSFORMED_BY_MIGRATION`; the current repository still parsed the corrupted jobs. |
| R6 source check | Both reviewed revisions contain one function docstring, not two. |

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 72 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 57 source/test files. |
| `mypy --platform win32` | Passed: no issues in 57 source/test files. |
| Full default suite | Passed: **878 passed, 6 skipped, 1 deselected**. |
| Source `--database-probe` | Passed: migrations 1, schema version 1, database ok. |
| `git diff --check e15dee4 a0fb4e4` | Passed. |
| Mutation restoration | All temporary source, test, and fixture mutations were restored byte-identical before validation. |

### Budget and readiness

T014-R1 remains Critical and continues automatically under `AGENTS.md` §9. The repeated
credential-boundary failures now warrant a maintainer-level design decision about the accepted
proxy grammar and whether `error_message` is part of this phase's durable schema.

T014-R4 remains a blocking Medium after the explicitly authorized pass. Another focused
verification of R4 requires fresh maintainer authorization, narrowing the criterion, or carrying
the remaining transform-expectation work into a named follow-up. T014-R7 is a new High correction
regression and must be resolved with the same design decision or an aligned implementation.

The persistence unit is **Changes requested**. R2, R3, and R5 remain resolved; R6 is retracted.

## 2026-07-26 — T-014 third focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-014`
**Correction base:** `a0fb4e4f3444b2e29c8872979431987a4fd70b6a`
**Head:** `04dd8af`
**Review unit:** Persistence correction commit plus the maintainer-authorized upstream
`DownloadRequest.proxy` invariant
**Platforms verified:** Linux locally; Windows not run; frozen build not rerun because the
specification and probe are unchanged
**Verdict:** **Changes requested**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T014-R1` | **Critical** | **Yes** | **Open — proxy-credential half resolved; cookie-data half still directly fails.** Moving the proxy boundary into `DownloadRequest` is the right design. Every prior credential-bearing form, including `//userinfo@host`, is rejected before a `Job` can exist; valid credential-free HTTP and SOCKS proxies still reach the adapter unchanged. I found no eighth valid URL-userinfo form that bypasses the literal authority delimiter. Restoring verbatim `error_message`, however, reopens the other unrestricted database sink covered by this finding and by T-014's unchanged criterion. A failed job with diagnostic `cookies /home/someone/cookies.txt; Cookie: SID=hunter2` stored both the path and cookie value verbatim in `jobs.error_message`. T-038 redacts logs; it cannot redact a separate database write. The task's claim that the only residual secret is the already-approved job URL is therefore false. Under §9, cookie material crossing a documented privacy boundary remains Critical. The maintainer may choose the stated trade-off, but §9 requires known Critical harm to be accepted in `ai/DECISIONS.md`, with its reasoning; the current commit neither records that decision nor narrows the contradictory T-014 acceptance criterion. Record and propagate the decision explicitly, including why local database diagnostics may contain cookie paths/content, or restore a design that satisfies both verbatim diagnostics and the database exclusion. |
| `T014-R4` | **Medium** | **No** | **Resolved.** `TRANSFORMED_BY_MIGRATION` and its unchecked skip are gone. The v1 fixture still seeds both `jobs` and `history`, and strict per-column equality is correct while every migration is pure DDL. Repeating the prior corrupt-but-readable v2 mutation now failed closed on `jobs.v1-queued.request`. T-048 has an owner trigger and the right acceptance criterion for the first actual data migration: assert the transformed value is correct while retaining strict equality elsewhere. The present review request explicitly authorizes verification of this removal; no additional pass authorization is needed to close R4. |
| `T014-R7` | **High** | **No** | **Resolved.** `_job_to_values()` again writes `job.error_message`, `_row_to_job()` returns that column unchanged, and both `add()` and `update()` use the shared mapping. Independent repository probes returned the exact original message after add, the exact replacement after update, and the exact authored interruption message after `recover_interrupted()`. No remaining repository paraphrase was found. This closes R7's contract failure; it does not by itself close R1's separate cookie-data exclusion. |
| `T014-R6` | **Low** | **No** | **Remains retracted.** No code change was needed. |

R2, R3, and R5 remain resolved and their reviewed surfaces are unchanged.

### Proxy-policy and wider-surface judgment

- Rejecting authenticated proxies is compatible with the literal requirements: REQ-023 requires
  proxy configuration but does not promise proxy authentication, while REQ-026 concerns
  authenticated access to content through cookies. The current maintainer direction therefore
  authorizes the capability trade-off.
- Because that trade-off changes a durable public capability and is also being used to close a
  Critical security finding, it should be recorded with the cookie-diagnostic decision in
  `ai/DECISIONS.md`, not only in the editable T-014 task narrative.
- `urlsplit()` rejects all valid userinfo forms because the authority delimiter remains a literal
  `@`, including when username/password characters are percent-encoded. NFKC variants that
  normalize into an authority delimiter raise as invalid. Control characters and backslashes did
  not hide the delimiter.
- The helper is not a complete proxy-validity checker despite its `scheme://host[:port]`
  wording: it accepts examples such as `http://:8080`, `http://proxy.invalid:abc`, an unsupported
  `ftp://` scheme, whitespace, and backslashes in the authority. Those do not create userinfo and
  yt-dlp has its own supported-scheme validation, so this is not a T-014 credential-boundary
  defect. The Phase 4 settings surface should still avoid presenting this helper as complete URL
  validation.
- Rejecting a non-slash path is reasonable for a proxy endpoint. A trailing slash remains
  accepted. No current T-011 protocol or T-012 worker path reconstructs or weakens the request:
  both carry the already-validated frozen model, and their normal HTTP/SOCKS construction cases
  remain green.
- Validation errors for scheme-less credential-bearing input interpolate the rejected value.
  Such an exception must be treated as sensitive by T-038 if it is ever logged; this does not
  reach the T-014 database because construction fails before a job exists.

### Mutation and correction evidence

| Check | Result |
|---|---|
| Remove proxy-validation call | Failed all 7 credential-form cases. Restored byte-identical. |
| Remove userinfo rejection | Failed the 4 cases that otherwise have a valid explicit scheme/authority. Restored byte-identical. |
| Remove the full scheme/authority guard | Failed only the scheme-relative no-credential case; the path check independently rejected the two other supplied strings. Restored byte-identical. |
| Retain only the authority half of that guard | Failed only the same scheme-relative case, confirming the explicit-scheme test is load-bearing. Restored byte-identical. |
| Paraphrase every non-null persisted error message | Failed **1**, not the claimed 2: `test_the_extractors_own_message_is_stored_verbatim`. The shared production sink and direct add/update/recovery probes establish current behavior, but the task's mutation count should be corrected. Restored byte-identical. |
| Rewrite all four pinned functional fields | Failed all 4 parametrized round-trip cases. Restored byte-identical. |
| R4 corrupt-but-readable v2 mutation | Failed strict equality on `jobs.request`; it no longer survives through an allowance. |
| Cookie diagnostic probe | Raw `jobs.error_message` retained both `/home/someone/cookies.txt` and `SID=hunter2`. |
| Construction-path regression run | Models, persistence, protocol, adapter, and worker tests passed: **393 passed, 4 skipped**. |

### Coordination accuracy

`ai/STATUS.md` still describes the superseded second-correction design: it says
`error_message` never carries external text and that NFR-006 is satisfied only in the per-job
log. That is the opposite of `04dd8af`. The T-014 task also reports two failures for the
paraphrase mutation, while the faithful conditional paraphrase above failed one. Both
current-truth records need correction with the R1 disposition.

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 72 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 57 source/test files. |
| `mypy --platform win32` | Passed: no issues in 57 source/test files. |
| Focused model + persistence + protocol + adapter + worker tests | Passed: **393 passed, 4 skipped**. |
| Full default suite | Passed: **879 passed, 6 skipped, 1 deselected**. |
| Source `--database-probe` | Passed: migrations 1, schema version 1, database ok. |
| `git diff --check a0fb4e4 04dd8af` | Passed. |
| Mutation restoration | All temporary source mutations were restored byte-identical before validation. |

### Readiness

R4 and R7 are resolved; R2, R3, and R5 remain resolved; R6 remains retracted. The upstream
proxy invariant closes every established proxy-credential route and introduces no regression
in T-011 or T-012.

R1 remains Critical because the unchanged database criterion covers cookie paths/content as
well as proxy credentials, and arbitrary diagnostics still enter that database verbatim. The
maintainer's stated decision can resolve this without another filtering mechanism, but the
Critical accepted risk must be recorded in `ai/DECISIONS.md` and the contradictory acceptance
criterion/current-truth text must be aligned before approval. The persistence unit is
**Changes requested**.

## 2026-07-26 — T-014 final documentation re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-014`
**Correction base:** `04dd8af`
**Head:** `db14cc2`
**Review unit:** Documentation-only decision and authority alignment; the committed
`ai/REVIEWS.md` addition is the prior reviewer entry, not part of the correction
**Platforms verified:** Linux locally; Windows not run; frozen build not rerun because no
executable, specification, or probe file changed
**Verdict:** **Approved with follow-ups**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T014-R1` | **Critical** | **No** | **Resolved by explicit maintainer decision.** DAT-003 records the controlling trade-off in the historical decision log: the local, user-owned database preserves third-party diagnostics verbatim even when they contain a cookie path. REQ-026 and T-014 now scope their exclusion to values this application supplies. That is the option the maintainer selected, it states the accepted harm and rationale, and it satisfies `AGENTS.md` §9's requirement that an agent not silently accept a Critical privacy trade-off. The proxy half remains structurally closed and unchanged. |
| `T014-R4` | **Medium** | **No** | **Remains resolved.** No migration-test or executable file changed. T-048 still owns the first real data migration. |
| `T014-R7` | **High** | **No** | **Remains resolved.** The verbatim diagnostic contract and implementation are unchanged. |
| `T014-R6` | **Low** | **No** | **Remains retracted.** |
| `T014-R8` | **Medium** | **No** | **Follow-up — DAT-003's explanatory table overstates the guarantee established by its controlling decision.** “Credentials — never in the database” is not absolute: a user-entered source URL may contain userinfo and is stored verbatim under the earlier URL disposition. `cookies_from_browser` is passed to yt-dlp in the browser-name position, but its model type accepts any non-empty string, including a path-shaped value. Nothing currently reads a cookie jar into a job, but arbitrary third-party diagnostic prose cannot support the exhaustive claim that an echoed path is the “only residue.” Finally, the reopening list correctly names database externalization but omits REQ-026's future cookie-file support, which will cause this application to hold and pass a cookie path. These are documentation-scope defects, not an unaccepted runtime risk: DAT-003's controlling provenance rule already accepts verbatim third-party text, and the database remains local. Per the maintainer's final-pass direction, T-049 owns tightening the table and adding the missing reopening trigger before cookie-file support or first release. |

R2, R3, and R5 remain resolved and unchanged.

### Decision-scope verification

- **Proxy credentials:** verified last round and unchanged. `DownloadRequest.proxy` rejects valid
  URL userinfo before a job can exist.
- **Cookie contents supplied by the application:** no request or job field carries a cookie jar
  or cookie value. `build_options()` passes only `(request.cookies_from_browser,)`, and projected
  yt-dlp data does not become stored cookie state.
- **`cookies_from_browser`:** semantically used as a browser name by the adapter, and every
  current application construction site supplies either a browser name or `None`. This is a
  current-flow fact, not a structural property of the string-typed model.
- **Third-party residue:** current yt-dlp cookie loading reads cookie values internally and
  reports generic failures while its diagnostic/logging paths may name filesystem locations.
  Because `NFR-006` deliberately preserves arbitrary upstream prose, no exhaustive list of what
  a future yt-dlp diagnostic may contain is supportable. DAT-003's main decision correctly turns
  on provenance; T-049 removes the narrower “only residue” claim.
- **REQ-026 authority:** the maintainer explicitly selected an option requiring a narrowed
  REQ-026 note. That is sufficient authorization for the Planner-owned requirement edit. The
  resulting requirement and T-014 criterion both use the same “application-supplied” boundary
  and link to DAT-003 rather than inventing separate rationales.
- **Reopening condition:** sync, export, cloud backup, or attaching the database to a report are
  correct triggers because they break the local/user-owned premise. T-049 adds the other premise:
  revisit the decision when cookie-file support or another secret-bearing persisted input is
  introduced.
- **T-038:** not weakened. Its unchanged acceptance criterion scans final emitted log output for
  cookie paths/content, proxy credentials, and token-like parameters regardless of where the
  message originated. T-049 will replace DAT-003's weaker “the application writes it” explanation
  with that origin-agnostic rule.

### Follow-up filed

`T-049 — Tighten DAT-003 before cookie-file support` is Proposed, owned by the Planner, and
targets Phase 4 before cookie-file support or first release. It does not reopen T-014 or change
approved persistence code.

### Validation

No mutation run was needed or useful for a four-file documentation correction: no executable
source, test, build, or configuration input changed. Read-only model/repository probes were used
to check the decision's factual claims.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: 72 files already formatted. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy` | Passed: no issues in 57 source/test files. |
| `mypy --platform win32` | Passed: no issues in 57 source/test files. |
| Full default suite | Passed: **879 passed, 6 skipped, 1 deselected**. |
| `git diff --check 04dd8af db14cc2` | Passed. |
| Reviewer working diff | Passed `git diff --check`; only `ai/REVIEWS.md` and the approved T-049 follow-up in `ai/TASKS.md` were added. |

### Readiness

T-014 is **Approved with follow-ups**. No further T-014 review pass is pending. T-049 owns the
non-blocking decision-wording correction; T-048 remains the future data-migration guard.
T-013 is unblocked.

## 2026-07-27 — T-013 initial review

**Reviewer:** Codex (Reviewer)
**Task:** `T-013`
**Base:** `a29661566696beb105805c45b49bce1bd4779e3d`
**Reviewed commit:** `0a19daf407d6c2665450f68515e4108f6cbcb1f2`
**Review unit:** `git show 0a19daf`; T-014's already-approved persistence commits and the later
coordination-only commits through `420cef9` are excluded
**Branch at review start:** `main`, not pushed
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Status | Finding |
|---|---|---:|---|---|
| `T013-R1` | **High** | **Yes** | **Open** | **The receiver reports several illegal streams only after their messages have already mutated durable job state, and it silently legalizes a missing sentinel.** `ResultPump.run()` emits each declared message at `result_pump.py:157` and calls `validate_sequence()` only in its finalizer at lines 161–165. The manager therefore persists an outcome before learning whether that outcome is legal for the session kind; `_on_session_ended()` then returns immediately whenever any outcome was claimed (`manager.py:597-601`), even when validation recorded violations. A deterministic probe started a `PROBE` session whose child sent `Succeeded`: the pump reported the forbidden outcome, but the job remained `COMPLETED` and `job_succeeded` had already been emitted. The same ordering lets a download end `READY` on an illegal `Probed`, lets a wrong-stage probe advance into download states before validation, and routes progress or resolution messages sent after an outcome. The committed test at `test_manager.py:730-756` explicitly codifies one contradiction by requiring a stream with a message after its outcome to remain completed, although T-013 says such violations fail loudly. Separately, `_end_the_stream()` inserts `WorkerFinished` without recording that the child omitted it (`manager.py:478-487`); a child that sent `Succeeded` and exited with no sentinel completed with no protocol violation in a second probe. This leaves the executable receiver weaker than `protocol.validate_sequence()`, violates T-013's session-validation acceptance criterion and `ARC-002`'s declared IPC contract, and can persist a false result for the requested session. Enforce every decidable grammar rule before routing its message, bind messages to the pump's expected job and session kind, suppress post-outcome traffic, and distinguish a synthetic sentinel from one the worker actually sent. Preserve the separate accepted rule that a **legal** outcome remains authoritative when the process later exits non-zero. Add negative tests for sibling outcome kinds, probe stages, job IDs, post-outcome message types, duplicate resolution reports, and a missing sentinel; mutation-check the guards. |
| `T013-R2` | **High** | **Yes** | **Open** | **`shutdown()` knowingly blocks the GUI thread, contrary to the unqualified NFR and architecture invariant and to T-013's own acceptance criterion.** `manager.py:409-436` runs a polling loop with `time.sleep()` and manual `processEvents()` for up to five seconds; its fallback then performs `Process.join()` and two `QThread.wait()` calls on that same thread (`manager.py:498-515`). A deterministic child that ignored cancellation occupied the caller for **1.52 s**. `NFR-001` says the UI thread is never blocked on subprocess work, Architecture §8 says nothing on it may block, and T-013 requires that no manager or pump call perform a blocking wait there. Teardown is not an authority-level exception, and processing arbitrary events inside a blocking shutdown loop also permits reentrant GUI actions. Make shutdown an event-driven lifecycle: initiate cancellation, keep the Qt loop and escalation timer alive, refuse new sessions, and announce completion through `idle` so composition code can finish quitting only after workers and pumps are gone. Keep any last-resort hard stop outside an interactive GUI-thread wait and mutation-check both graceful and forced paths. |
| `T013-R3` | **Medium** | **Yes** | **Open** | **Failures before `Process.start()` strand a durable `PROBING` job without a session or error.** `start()` persists `PROBING` at `manager.py:318-319`, but queue, event, pump, process and pump-thread construction occur before the only protected operation at lines 321–360. The exception handler covers only `process.start()`. A deterministic `Queue()` failure raised `OSError`, left `_sessions` empty, and left the repository at `PROBING`; no `job_failed` or protocol-violation signal was emitted. Resource exhaustion or a pump-thread start failure therefore looks like active work that does not exist, violating `REQ-018`'s recorded-failure rule. Cover the complete startup transaction: all failures after the durable transition must persist a useful failure, emit it after persistence, and close or stop every resource that was successfully created. Audit queue/event/process construction, pump construction/start, process start, and failures while synthesizing the cleanup sentinel. |

### Rulings on the five implementation judgments

1. **Worker surface expansion accepted.** Cancellation observation, process exit status and the
   killed-parent watchdog are the child halves of explicit T-013 criteria and belong in
   `worker.py`; separating them into another task would split one acceptance boundary without
   reducing risk.
2. **Blocking shutdown rejected.** It is `T013-R2`; the lower-authority task explanation cannot
   create an exception to `NFR-001` or Architecture §8.
3. **Loopback yt-dlp exception accepted.** The two tests bind only `127.0.0.1`, fake the site
   rather than the process/library boundary, and uniquely prove bytes moving through the real
   progress hook. They are not external-network tests and should remain in the default suite,
   not behind `-m network`.
4. **QUEUED-only start accepted for T-013.** Inventing `READY → PROBING` in source would violate
   the approved state machine. It does, however, block T-016's probe-then-queue flow from reusing
   the probed job. Planner-owned `T-051` now resolves that lifecycle before T-016; this is not a
   T-013 approval blocker.
5. **Injected entry point accepted.** It is a narrow fault-injection seam whose tests still use
   real spawned processes and real queues. The malformed streams under test cannot be produced
   by the correct production entry point, and no user-controlled value selects the callable.

### Validation and negative evidence

The checkout changed concurrently during review from `main` to `phase1-presets-and-fixtures`
and gained an unrelated uncommitted T-015 edit in `core/models.py`. It was preserved untouched.
All gates below therefore ran from a clean `/tmp` archive of the exact reviewed commit, using
the repository virtual environment.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **75 files already formatted**. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Full default suite | Passed with loopback permission: **913 passed, 6 skipped, 1 deselected**. The first sandboxed run failed 9 tests only because socket creation was denied with `PermissionError`; the unchanged suite passed after loopback binding was allowed. |
| Illegal probe-outcome review probe | Failed as intended: the job was `COMPLETED`, not `FAILED`, despite the recorded protocol violation (`T013-R1`). |
| Missing-sentinel review probe | Failed as intended: a child-emitted success plus process exit produced no `WorkerFinished` violation (`T013-R1`). |
| Startup-construction review probe | Failed as intended: a `Queue()` error left the job `PROBING`, not `FAILED` (`T013-R3`). |
| GUI-thread shutdown review probe | Failed as intended: a cancellation-resistant child held `shutdown()` for **1.52 s** (`T013-R2`). |
| `git show 0a19daf --check` | Passed. |

The four review probes existed only in the temporary clean archive and were not added to the
working tree. The implementer's reported 15-mutation run was not rerun wholesale; the review
instead established three missing negative cases and one direct timing contradiction that the
correction batch must freeze and mutation-check.

### Readiness

T-013 remains **In Review — changes requested**. `T013-R1` and `T013-R2` are High blockers;
`T013-R3` is a blocking Medium. One focused correction re-review remains available for R3 under
the ordinary budget; the two High findings continue until independently resolved regardless of
that cap. Windows remains unverified for cancellation timing, the killed-parent watchdog and
`TerminateProcess`.

## 2026-07-27 — T-015 and T-018 initial reviews

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-015`, `T-018`
**Base:** `cc79bb8b0379bcd7dd8f30e808e1cbfb25d2b542`
**Reviewed commit:** `1156007b3316e46f35a5714402efb977ec048bb7`
**Review unit:** the single combined commit on `phase1-presets-and-fixtures`; findings and
verdicts remain task-specific
**Platforms verified:** Linux locally; Windows not run
**T-015 verdict:** **Changes requested**
**T-018 verdict:** **Changes requested**

### T-015 findings

| ID | Severity | Blocks approval | Status | Finding |
|---|---|---:|---|---|
| `T015-R1` | **High** | **Yes** | **Open** | **The translation can download a selector or container different from the preset the UI presents.** `BEST_VIDEO_1080P` ends with `/best[height<=1080]`, a fallback with no MP4 constraint. Feeding the pinned yt-dlp selector engine a single 720p WebM format selected that WebM successfully, although `REQ-006` and the preset name promise “≤1080p (MP4).” The capability test at `test_presets.py:47-50` only checks that the whole selector contains both `height<=1080` and `ext=mp4`; it stays green when another fallback branch permits a different container. Independently, `to_request()` applies unrestricted `**overrides` through `dataclasses.replace()` after copying the preset. A probe passed `format_selector="worst"` and received a request for `worst` while `effective_selector(BEST_VIDEO_1080P)` still displayed the original selector. That directly defeats `REQ-009`'s promise that the effective selector shown is the one used. Both routes are the same wrong-result class: a named/displayed choice is not the request that runs. Remove the non-MP4 fallback or add an explicit conversion contract that still guarantees MP4, and reject overrides of preset-owned fields (or derive the displayed effective value from the final request). Audit `media_kind`, codec/quality, subtitles, post-processors and output template as sibling preset-owned fields. Freeze the format case through yt-dlp's real selector engine, test every fallback branch, test hostile overrides, and mutation-check both guards. |

### T-018 findings

| ID | Severity | Blocks approval | Status | Finding |
|---|---|---:|---|---|
| `T018-R1` | **Critical** | **Yes** | **Open** | **The capture sanitizer and its independent gate both allow credential material into committed fixtures.** `capture.redact()` recurses through dictionaries and lists only; a tuple containing `{"cookies": "SID=secret"}` passed unchanged and serialized as JSON with the cookie intact. `redact_url()` removes only an exact short list of parameter names, and the committed scanner uses the same narrow vocabulary in another form. A URL carrying the standard signed-request fields `X-Amz-Signature`, `X-Amz-Credential` and `X-Amz-Expires` passed through unchanged, and `leaks_in()` returned no findings. URL userinfo and other provider token names are likewise outside the asserted boundary. The current six fixtures contain no established live secret, but the stated gate is specifically meant to prevent the next deliberate refresh from permanently writing one into git; a false-negative credential gate crosses `REQ-026`/`NFR-007` and has Critical consequence under `AGENTS.md` §9. Make sanitization fail closed across every JSON-serializable container and URL authority/query shape. Prefer removing URL userinfo and all query parameters unless a small reviewed allowlist proves one is contract data. Keep the committed-file scanner independent and add hostile cases for tuple nesting, cookie values, mixed/case-varied keys, percent-encoded names, AWS/CloudFront-style signed URLs and userinfo. Mutation-check each class, not only one spelling. |
| `T018-R2` | **High** | **Yes** | **Open** | **The playlist projection misclassifies yt-dlp's declared `multi_video` result as a single item.** `project_media()` uses `info.get("_type") == "playlist"`. The pinned yt-dlp's extractor contract defines both `"playlist"` and `"multi_video"` as multiple-video results, and `YoutubeDL.process_ie_result()` dispatches both through its playlist processor. A deterministic `_type="multi_video"` payload with two entries projected as `is_playlist=False, entry_count=None`. `REQ-002` requires the binary single-item/playlist distinction and T-018 exists to close `T012-R6`; leaving a supported multi-item type on the single side means that follow-up is not closed and T-016 is not yet unblocked. Represent both multi-item result types honestly (an enum may preserve the distinction if future UI behavior needs it), add a fixture-backed or explicitly derived `multi_video` case, and audit `_entry_count()`'s accepted shapes so strings/bytes are not counted merely because they implement `Sequence`. Mutation-check each supported `_type`. |

### Scope and implementation rulings

- **T-015 model expansion accepted.** Codec/quality and subtitle fields are necessary to make
  the required presets behaviorally distinct, and they stay within the pure-core layering rule.
- **T-015 selector-validation deviation accepted.** Empty/non-string selectors are already
  unrepresentable in `Preset` and `DownloadRequest`; duplicating an unreachable built-in-only
  branch would not strengthen the boundary.
- **T-018 recorded/derived fixture split accepted.** The DRM fixture clearly identifies its
  synthetic fields and does not probe a service outside `SEC-001`.
- **Leaving `build_options(noplaylist=True)` unchanged is not itself a finding.** An explicit
  playlist URL can still produce a playlist result in the pinned engine. The incomplete
  `_type` projection is the blocking defect.

### Validation and negative evidence

All validation ran from a clean `/tmp` archive of `1156007`, with `PYTHONPATH=src` so the
repository's editable virtual environment could not import `main` instead of the archived
branch.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **78 files already formatted**. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Full default suite | Passed: **1070 passed, 11 skipped, 1 deselected**. An initial run without `PYTHONPATH=src` imported the active main checkout through the editable environment and failed collection; the exact archived source produced the recorded passing result. |
| MP4 selector probe | The real pinned yt-dlp selector chose a 720p WebM from the unconstrained final fallback (`T015-R1`). |
| Selector-override probe | The shown selector remained the built-in string while the resulting request carried `"worst"` (`T015-R1`). |
| Multi-video projection probe | `_type="multi_video"` with two entries projected as a single item with no count (`T018-R2`). |
| Signed-URL probe | AWS-style signature, credential and expiry parameters survived both capture redaction and the scanner with zero findings (`T018-R1`). |
| Nested-cookie probe | A tuple-nested `SID=secret` survived redaction, JSON serialization and the scanner with zero findings (`T018-R1`). |
| `git show 1156007 --check` / bounded `git diff --check` | Passed. |

The implementer's reported mutation batches were not rerun wholesale. The review established
four missing negative classes that the correction batches must freeze and mutation-check.
No test touched the network; the fixture capture script was inspected, not executed.

### Readiness

T-015 remains **In Review — changes requested** with one High blocker. T-018 remains
**In Review — changes requested** with one Critical and one High blocker; `T012-R6` remains
open through `T018-R2`, so T-016 is not unblocked. High and Critical corrections continue until
independently verified regardless of the ordinary pass budget. `ai/STATUS.md` still says the
playlist projection unblocks T-016; the Implementer must align that current-truth claim in the
correction batch.

## 2026-07-27 — T-013 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-013`
**Correction base:** `cc79bb8b0379bcd7dd8f30e808e1cbfb25d2b542`
**Correction head:** `65303a2826ec0f71693f17e6b8e922451674bf2d`
**Review unit:** `git diff cc79bb8..65303a2`, limited to `T013-R1`–`T013-R3` and correction
regressions; later T-019 coordination commit `9bdb8c4` is excluded
**Branch at recording:** `main`, not pushed
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T013-R1` | **High** | **No** | **Resolved.** `SessionValidator` is the incremental form of the protocol grammar and `validate_sequence()` now delegates to it. `ResultPump` binds it to the requested job, calls `accept()` before any route, stops on a violation, and calls `complete()` at session end. The manager records a synthetic sentinel as a violation and defers every terminal transition until the stream is judged. The committed illegal-kind, wrong-stage, foreign-job, duplicate-report, post-outcome and missing-sentinel cases all pass; the cancellation exception applies only after the user has requested cancellation and preserves the worker's own `CANCELLED` outcome when present. |
| `T013-R2` | **High** | **No** | **Resolved as originally stated.** `shutdown()` now marks the lifecycle, refuses new sessions, initiates cancellation and returns. Timer ticks perform escalation; no positive-duration process join, `QThread.wait()`, sleep loop or manual event pumping remains. A cancellation-resistant real spawned worker verified that the call returns inside the interaction budget and later reaches `idle`. The forced-pump release regression is recorded separately as `T013-R4`. |
| `T013-R3` | **Medium** | **Yes** | **Open — the correction does not survive failure of its own cleanup sentinel.** `_abort_start()` calls `queue.put(WorkerFinished(...))` before it records the failed job, and that cleanup write is unprotected. A deterministic process-start failure paired with a queue whose cleanup `put()` fails raised the cleanup `RuntimeError` instead of the original spawn `OSError`, left the repository at `PROBING`, and emitted no durable failure. This is the exact “failures while synthesizing the cleanup sentinel” sibling named in the initial finding. Protect cleanup operations so they cannot pre-empt persistence of the useful original failure, then close/terminate whatever was built without leaking it. |
| `T013-R4` | **Medium** | **Yes** | **Open — the new pump-abandon path can announce shutdown completion before the pump has finished and leaves the job in flight.** `_abandon()` calls asynchronous `QThread.terminate()`, immediately closes the queue and removes the session, and neither observes `finished` nor finalizes the job. `_tick()` can consequently emit `idle` while that thread is still running. A deterministic pump whose `terminate()` had not yet completed left `is_idle == True`, `isFinished() == False`, and the repository at `PROBING`. This is a narrow forced-cleanup path, hence Medium, but it violates T-013's no-thread/no-in-flight-job shutdown criterion and blocks. Retain ownership until `finished`, and durably cancel or fail the job before `idle`. |
| `T013-R5` | **Low** | **No** | **Open follow-up — the recorded 16/16 mutation result overstates the committed gate.** Moving `_routes[type(item)].emit(item)` immediately before `SessionValidator.accept()` left all five cases in `test_an_illegal_message_never_reaches_the_job` green. The production order is correct, but the test permits an illegal progress message to persist `RUNNING` and does not assert that foreign progress or a duplicate resolution report was withheld. The startup test's useful-message assertion is also vacuous because it ends in `or True`. Implementer-owned `T-052` targets these tests; it does not keep T-013 in review. |

### Focused verification

The correction was read and executed from a clean `/tmp` archive of exact commit `65303a2`.
The working branch changed independently while review was running; neither the T-015/T-018
review commit on `phase1-presets-and-fixtures` nor main's later T-019 task update is in this
review unit.

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **75 files already formatted**. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Focused manager + protocol + boundary tests | Passed: **175 passed, 3 skipped**. |
| Full default suite, reviewer probes excluded | Passed: **925 passed, 6 skipped, 1 deselected**. |
| Cleanup-sentinel negative probe | Failed against `65303a2`: cleanup `put()` replaced the spawn error and left the job `PROBING` (`T013-R3`). |
| Asynchronous-abandon negative probe | Failed against `65303a2`: the manager became idle with an unfinished pump and an in-flight job (`T013-R4`). |
| Route-before-validation mutation | **Survived:** all five parameterized illegal-message cases passed (`T013-R5`). |

The reviewer-only probes and mutation existed only in the archived tree. The production source
was restored before the committed suite run. Windows remains unverified for cancellation timing,
the orphan guard and `TerminateProcess`.

### Convergence and readiness

The two High findings are resolved. Two blocking Medium findings remain after the one focused
correction re-review, so the ordinary budget in `AGENTS.md` §9 is exhausted. T-013 is
**Blocked** pending the maintainer's choice: authorize one more focused pass, accept the
documented risk, change scope, or carry the blockers into a named follow-up. `T013-R5` is
non-blocking and assigned to `T-052`.

## 2026-07-27 — T-013, T-015 and T-018 merged correction re-review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-013`, `T-015`, `T-018`
**Correction commits:** `d5034a00d7b55940b20397e3926a16fdc23d64eb` (`T013-R3`,
`T013-R4`); `0973fee967cff164b799e5b3e752953faa751e85` (`T015-R1`, `T018-R1`,
`T018-R2`)
**Merged head:** `7021a01c0721edaf2d95dafc26d9e15590b2de7d`
**Review unit:** the two correction commits and merge resolution only
**Branch:** `main`, clean, 12 commits ahead of `origin/main`, not pushed
**Platforms verified:** Linux locally; Windows not run
**T-013 verdict:** **Blocked**
**T-015 verdict:** **Changes requested**
**T-018 verdict:** **Changes requested**

### T-013 finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T013-R3` | **Medium** | **Yes** | **Open — the correction closes the reported cleanup-write failure but leaves two parts of the startup transaction unsound.** The durable `FAILED` record now precedes cleanup, and cleanup writes/closes are guarded. However, `start()` now calls `process.start()` before `pump.start()` and does not set `session.started` until both return. If the pump start raises after the process start succeeds, `_release_half_built()` sees a non-running pump, closes the queue, drops the session and never terminates the already-live worker. A deterministic process/pump probe left the fake process alive with neither `terminate()` nor `kill()` called while the manager claimed idle. This is the pump-start sibling the original finding explicitly required. Separately, `_abort_start()` still calls `_on_violation()` before `_save_and_announce(FAILED)`: a signal observer deterministically read `PROBING`, contradicting the original “emit after persistence” requirement. Track process start independently, stop/reap it on every later startup failure, and persist before either failure signal. |
| `T013-R4` | **Medium** | **No** | **Resolved.** `_abandon()` resolves the job through `_on_session_ended()` and retains the session; `_release()` requires either the delivered `finished` signal or `isFinished()`. A stubborn-pump probe stayed non-idle with a terminal job until the real thread finished. Removing `_on_session_ended()` made the direct mechanism test fail, so the correction is not being supplied by an incidental second path. The recorded survivor—removing the `isFinished()` fallback while Qt still delivers `finished` in every test—is genuine redundant evidence, not a demonstrated behavior defect. |
| `T013-R5` | **Low** | **No** | **Remains Open and unchanged.** The implementer's correction note confirms the earlier claimed route-before-validation mutation had duplicated emission rather than moved it, so the old 16/16 number measured the test shape rather than the ordering guard. `T-052` still owns the non-blocking hardening. |

### T-015 finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T015-R1` | **High** | **No** | **Resolved as originally reported.** Every selector alternative now has `ext=mp4`; the pinned yt-dlp engine selects nothing from a WebM-only set. `PRESET_OWNED_FIELDS` is derived from the intersection of `Preset` and `DownloadRequest`, and every such override is rejected while proxy/rate/cookie settings remain accepted. Removing the override guard failed its focused test. |
| `T015-R2` | **High** | **Yes** | **Open correction regression — the new final fallback can silently download video without audio.** The third alternative is `bestvideo[height<=1080][ext=mp4]`, which by definition accepts a video-only stream. Given a 720p MP4 video-only format plus available WebM/Opus audio, the pinned selector chose only the MP4 row (`acodec="none"`). The committed “every branch” table never isolates this branch: its 720p row is pre-muxed and is selected by the preceding `best[ext=mp4]` alternative. A common “best video ≤1080p” preset silently producing a mute file is core user-visible wrong output and blocks. Remove the video-only fallback or define an explicit, truthful audio/container policy; add a real-engine case that can only reach each distinct alternative and asserts audio as well as extension. |

### T-018 finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T018-R1` | **Critical** | **Yes** | **Open — both fail-closed claims still have credential/privacy false negatives.** The correction does fix tuple/container traversal, mixed-case credential markers, ordinary query removal and URL userinfo, and the current committed fixtures contain no established live secret. But `capture_info()` and `capture_error()` write their `source_url` metadata raw instead of passing it through the sanitizer; a fake capture returned `https://someone:hunter2@…?X-Amz-Signature=secret` verbatim. More fundamentally, both halves miss supported shapes outside their enumerations: `D:\Users\Sean\private.txt` survives `redact()` and produces no `leaks_in()` finding, as does `https://example.invalid/video#access_token=secret`. Windows profiles are not confined to `C:`, and URL fragments are a real bearer-token location. A future deliberate refresh can therefore still write private material into a file whose scanner returns clean—the irreversible privacy consequence that made R1 Critical. Sanitize every capture-owned metadata/error field, remove URL fragments when no fragment is allowlisted, and make user-directory recognition drive/UNC-independent and case-insensitive in both independent halves. Add negative tests at the public capture functions and at the committed-file scanner, not only against `redact()` in isolation. |
| `T018-R2` | **High** | **No** | **Resolved.** `MULTI_ITEM_TYPES` independently transcribes `playlist` and `multi_video`; both project to `is_playlist=True` with an honest count. String, bytes and generator `entries` are not counted or consumed. Removing `multi_video` failed the independent declared-type test. `T012-R6` is resolved. |

### Merge verification

`7021a01` is a true two-parent merge of `d5034a0` and `0973fee`; `main` contains both and the
local feature branch is deleted. The merged manager and manager tests are byte-identical to the
T-013 parent, while the preset, projection, capture, fixture and associated test surfaces are
byte-identical to the T-015/T-018 parent. `git show --remerge-diff` reports content conflicts
only in `ai/REVIEWS.md` and `ai/STATUS.md`: the merge preserves both append-only reviews and
rewrites the status snapshot to contain both work streams. `ai/TASKS.md` combined without a
content conflict. No production-code conflict was resolved manually.

### Validation and negative evidence

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **78 files already formatted**. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Focused manager suite | Passed: **50 passed**. |
| Focused preset + fixture + model suite | Passed: **279 passed, 6 skipped**. |
| Full merged-tree default suite | Passed: **1123 passed, 11 skipped, 1 deselected**. |
| Pump-start negative probe | Failed: the process remained alive after `pump.start()` raised (`T013-R3`). |
| Startup signal-order probe | Failed: `protocol_violation` observed the repository at `PROBING`, not `FAILED` (`T013-R3`). |
| MP4/audio selector probe | Failed: the pinned engine selected one MP4 video-only row and discarded available Opus audio (`T015-R2`). |
| Capture-owned source URL probe | Failed: userinfo and an AWS signature remained verbatim in `_fixture.source_url` (`T018-R1`). |
| Windows-profile and fragment-token probes | Failed: both sanitizer and scanner accepted the private material (`T018-R1`). |
| R4 mechanism mutation | Killed: removing `_on_session_ended()` failed the direct `_abandon()` test. |
| R2 declared-type mutation | Killed: removing `multi_video` failed its focused projection test. |
| Preset override mutation | Killed: removing the owned-field guard failed its focused test. |
| Commit/merge whitespace and parent-code comparisons | Passed. |

Reviewer probes and mutations existed only in a clean archive of merged head `7021a01`; the
working tree remained untouched until these review records were written. Windows remains
unverified.

### Convergence and readiness

- **T-013 is Blocked.** `T013-R4` is resolved, but `T013-R3` remains a blocking Medium after
  the maintainer-authorized extra pass. Another Medium-or-lower pass requires a new maintainer
  choice under `AGENTS.md` §9.
- **T-015 has Changes requested.** `T015-R1` is resolved, but new High correction regression
  `T015-R2` blocks and continues through correction and focused verification without a pass cap.
- **T-018 has Changes requested.** `T018-R2` is resolved; Critical `T018-R1` remains open and
  cannot be accepted or deferred by an agent. The projection half `T012-R6` is closed, but
  T-018 itself is not approved.

## 2026-07-27 — T-013, T-015 and T-018 focused blocker verification

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-013`, `T-015`, `T-018`
**Correction commits:** `d3bac037ca5cd9e4dab0605f1537b778975c3181` (`T015-R2`,
`T018-R1`); `14a50e59f012161851c6cd78ca68b4b6154023d9` (`T013-R3`)
**Review unit:** the two correction commits, limited to the three unresolved blockers and
correction regressions
**Branch at inspection:** `main` at `14a50e5`, clean, 14 commits ahead of `origin/main`, not
pushed. While review ran, `main` advanced to docs-only `2ff5606` (15 ahead); that concurrent
`ai/TASKS.md` status alignment does not change either correction diff.
**Platforms verified:** Linux locally; Windows not run
**T-013 verdict:** **Approved with follow-ups**
**T-015 verdict:** **Approved**
**T-018 verdict:** **Changes requested**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T013-R3` | **Medium** | **No** | **Resolved.** `_Session` now records `process_started` and `pump_started` separately as each start returns, and `_abort_start()` reads that record rather than inferring it from locals or one late flag. The durable `FAILED` write precedes both failure signals and every cleanup operation. A real-process test in which `process.start()` succeeds and `pump.start()` raises leaves no worker and a failed, idle manager; a signal-order test observes `FAILED` from `protocol_violation`; and the real successful-download test passes through the restructured ordinary path. All 52 focused manager and boundary tests passed. |
| `T015-R2` | **High** | **No** | **Resolved.** The video-only fallback is gone. The remaining alternatives are a separate MP4/M4A pair and a pre-muxed MP4; committed cases isolate each through the pinned yt-dlp selector and assert both audio and video, while MP4-video plus WebM/Opus-audio selects nothing. That refusal is consistent with `REQ-006`: silently merging to MKV would violate the named MP4 preset, while remux/recode is a separate `REQ-010` choice. |
| `T018-R1` | **Critical** | **Yes** | **Open — the claimed fail-closed policy still has two deterministic false negatives in both independent halves.** `write()` does sanitize the whole payload now, and the source-URL, drive-letter, nested-UNC and fragment cases reported in the preceding pass are corrected. However, `CREDENTIAL_KEY_MARKERS` deliberately removed `"auth"` to avoid matching `"author"` and did not replace it with boundary-aware or exact-key handling. Consequently `write(..., {"info_dict": {"auth": "fixture-secret-7c6c"}})` writes the secret unchanged and `leaks_in()` returns no finding. Exact `"auth"` is itself a credential key; preserving `"author"` does not require accepting it. The path patterns also miss the common UNC profile form `\\server\Users\name` because both require an extra component before `Users`; under a neutral key, that path survives `redact()` and produces no scanner finding. A future deliberate refresh can therefore still commit credential material or a personal path through a gate that reports clean. This retains the irreversible privacy consequence and Critical severity. Match bare/delimited `auth` without matching `author`, teach the independent scanner the same class without sharing the sanitizer's constant, and cover both `\\server\Users\name` and the already-tested nested UNC form. |

### Verification

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **78 files already formatted**. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Focused manager + boundary suite | Passed: **52 passed**. The first sandboxed run had 9 local-server `PermissionError` failures; rerunning with permission to bind `127.0.0.1` passed cleanly. |
| Focused preset + fixture suite | Passed: **200 passed, 5 skipped**. |
| Full merged-tree default suite | Passed: **1132 passed, 11 skipped, 1 deselected**. |
| Bare-auth write probe | Failed closed-policy claim: the known secret remained in the written JSON and `leaks_in()` returned `[]` (`T018-R1`). |
| UNC-share probe | Failed closed-policy claim: `\\nas\Users\Sean\private.txt` survived `redact()` and `leaks_in()` returned `[]`; the nested `\\nas\home\Users\Sean\private.txt` control was correctly detected (`T018-R1`). |

The implementer's mutation batches were not rerun wholesale. The focused tests exercise the
corrected T-013 and T-015 mechanisms and ordinary success path; the two direct privacy probes
establish that `T018-R1` is still live. Windows runtime behavior remains unverified.

### Convergence and readiness

- **T-013 is Approved with follow-ups.** Its last blocking finding, `T013-R3`, is resolved.
  `T013-R5` remains non-blocking and assigned to `T-052`; `T-019` still owns descendant
  process-tree cleanup and Windows process-lifetime evidence.
- **T-015 is Approved.** `T015-R1` and `T015-R2` are resolved; no blocking or non-blocking
  finding remains.
- **T-018 has Changes requested.** Critical `T018-R1` remains open. Under `AGENTS.md` §9,
  Critical correction and independent verification continue without the ordinary pass cap.

## 2026-07-27 — T-018 third Critical correction verification

**Reviewer:** Codex (Reviewer)
**Task:** `T-018`
**Correction base:** `b3e30da`
**Correction head:** `73d04c6f47cb55403f88b7764df08c51d1e9751f`
**Review unit:** `git show 73d04c6`, limited to `T018-R1` and correction regressions
**Branch:** `main`, clean at inspection, 17 commits ahead of `origin/main`, not pushed
**Platforms verified:** Linux locally; Windows not run
**Verdict:** **Blocked**

### Finding disposition

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T018-R1` | **Critical** | **Yes** | **Open — the two reported shapes are fixed, but the recognizer still writes credential material that both gates report clean.** The new word splitter correctly distinguishes `auth`, `X-Auth`, `xAuth` and `authToken` from `author`; the sanitizer and parsed gate agree on those controls. Both path patterns now catch `\\server\Users\name`, nested UNC, mixed separators and extended UNC under a neutral key. However, the public `capture.write()` boundary preserved known values under `passwd`, `passphrase`, `private_key` and `accessKey`; the text scanner and parsed-key gate both returned no finding on the written file. The parsed gate also disagrees with the sanitizer's own classification: unredacted raw fixtures under `cookiejar`, `sessionid`, `clientsecret`, `httpheaders` and `oauth2` pass both committed-file checks even though the sanitizer recognizes and removes them. These are not requests for nine more markers. They demonstrate the same defect class for a fourth time: an open-ended credential namespace is being protected by a recognizer whose accepted complement is treated as safe. A deliberate refresh or derived-fixture edit can still commit a credential through a gate that reports clean, retaining the irreversible privacy consequence and Critical severity. |

### Deterministic evidence

The public-boundary probe called `capture.write()` with:

```python
{
    "info_dict": {
        "passwd": "opaque-password-7c6c",
        "passphrase": "opaque-passphrase-7c6c",
        "private_key": "opaque-private-key-7c6c",
        "accessKey": "opaque-access-key-7c6c",
    }
}
```

All four values remained byte-for-byte in the JSON. `leaks_in(written_text)` and
`credential_keys_left_intact(parsed_json)` both returned `[]`.

A separate gate-independence probe supplied raw parsed objects under `cookiejar`,
`sessionid`, `clientsecret`, `httpheaders` and `oauth2`. The sanitizer returned
`"<redacted>"` for each, but the parsed gate returned no finding for any of them. That makes
the committed-file check unable to detect a sanitizer regression over names the sanitizer
already claims to cover.

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **78 files already formatted**. |
| `mypy src` | Passed: no issues in 31 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Focused fixture suite | Passed: **112 passed, 5 skipped**. |
| Full default suite, bounded rerun | Passed: **1145 passed, 11 skipped, 1 deselected** in 33.85 s. |
| Initial full-suite attempt | Hung after early manager tests with a defunct spawned child and ignored two interrupts; the reviewer terminated only that pytest process. The isolated test at the apparent position passed, no worker/resource-tracker remained, and the bounded clean rerun passed. This is recorded as process-harness instability, not attributed to `73d04c6`. |
| Reported auth/UNC controls | Passed: `auth`/`xAuth` redacted and reported, `author` preserved; direct-root, nested, mixed-separator and extended UNC detected. |
| Public-write credential probe | Failed the privacy claim: four known credential-key forms survived both gates (`T018-R1`). |
| Parsed-gate independence probe | Failed the gate claim: five sanitizer-recognized compound names produced no finding (`T018-R1`). |

The implementer's six-mutation batch was not rerun wholesale. Its five killed production
mutations do not cover the unbounded accepted complement established above. Windows remains
unverified, but the reproduced defect is platform-independent.

### Stop condition and recommended design decision

This is **not returned for a fourth marker-list correction**. Three correction batches have
established that the recognizer cannot make an open-ended raw `info_dict` safe by enumerating
credential spellings. T-018 is **Blocked pending a maintainer scope/design choice**:

1. **Recommended — constrain what is committed.** Persist values only for the explicit fields
   `ytdlp_adapter` projects, plus the reviewed provenance/error fields. Reject or drop every
   unlisted key before serialization. URL-valued allowed fields still lose query, userinfo and
   fragment; path checks remain defense in depth.
2. **Preserve churn evidence without preserving unknown values.** Alongside that allowlisted
   projection input, record a value-free recursive schema fingerprint for discarded raw data:
   key names, container shape and scalar type, but no scalar values. An upstream shape change
   remains visible while an unfamiliar key cannot carry its value into git.

This keeps the fixture's actual purpose—a pinned contract for the projection—while making a
new leak spelling irrelevant by construction. Continuing with the full raw dict requires the
maintainer to accept a known Critical privacy risk; an agent cannot close that as accepted risk
under `AGENTS.md` §9.

## 2026-07-27 — T-018 fourth correction batch returned (`T018-R1`, structural)

**Implementer:** Claude Code
**Task:** `T-018`
**Correction base:** `73d04c6`
**Correction head:** `2f85a32` (structure), plus test coverage added afterwards — see below
**Authorization:** maintainer, recorded as `SEC-002` in `ai/DECISIONS.md`
**Awaiting re-review.** Only the Reviewer marks a finding Resolved.

### What changed, and why it is not a fifth marker list

The reviewer's stop condition is accepted in full. Three batches established that an open-ended
`info_dict` cannot be made safe by enumerating credential spellings, and the recommended scope
change was authorized rather than another recogniser pass.

`capture.write()` now commits **values only for fields `ytdlp_adapter.py` demonstrably reads**,
plus the reviewed provenance and error fields. Every other key is dropped before serialization.
`ALLOWED_QUERY_PARAMETERS` stays empty; userinfo and fragments still go; the path and key patterns
remain as defence in depth rather than as the control being relied on.

Churn evidence is kept as `schema_fingerprint()` — key names, container shape, scalar *types*, no
scalar values — so `NFR-008`'s canary still fires on an upstream rename while a fingerprint
cannot carry data.

The allowlist is transcribed in `capture.py` and **derived from `ytdlp_adapter`'s AST** in the
gate, so the two must agree or the suite fails.

### The reviewer's two probes, re-run against this head

| Probe | Result |
|---|---|
| `passwd` / `passphrase` / `private_key` / `accessKey` through `capture.write()` | All four keys **absent** from the written file. Not redacted — dropped. Their existence survives in `_schema` as type names. |
| `cookiejar` / `sessionid` / `clientsecret` / `httpheaders` / `oauth2` as raw parsed objects | `unexpected_keys()` reports each by path. The gate no longer depends on agreeing with a sanitizer's vocabulary, because there is no vocabulary. |

The first probe's written file, in full:

```json
{"_fixture": {}, "_schema": {"accessKey": "str", "passphrase": "str", "passwd": "str",
 "private_key": "str"}, "info_dict": {}}
```

155 bytes. `leaks_in()` and `unexpected_keys()` both return `[]` — and this time that is the
right answer, because there is nothing in the file to find. The second probe's gate output is
`['info_dict.cookiejar', 'info_dict.sessionid', 'info_dict.clientsecret',
'info_dict.httpheaders', 'info_dict.oauth2']`.

Both are asserted permanently: `test_the_writer_keeps_only_what_the_projection_reads` and
`test_the_gate_rejects_a_fixture_carrying_anything_else` carry every spelling that beat a marker
list, and none of them is recognised by name.

### Mutation evidence — 10 mutations, 10 killed, and one of them found a hole

The battery was **re-run from a written list** rather than reported from the previous session's
count. That was the right call: one mutation survived the first pass.

**Survivor, now fixed.** Removing `clean_scalar`'s user-directory branch left the whole suite
green. The key allowlist answers *may this field carry a value*, not *what is that value* — and
`title`, `url` and `format_note` can all hold a local path, which `NFR-007` keeps out of anything
that persists. No committed fixture contains one, so nothing exercised the branch.
`test_a_consumed_field_still_loses_a_user_directory` now asserts it at `write()` across
`C:\Users\…`, `D:/Users/…`, `\\server\Users\…`, `/home/…` and `/Users/…`; the mutation dies.

The nine killed on the first pass:

| Mutation | Killed by |
|---|---|
| `keep_consumed` iterates the info dict instead of the allowlist | writer and gate tests |
| `_keep_format` keeps every format key | writer test |
| `schema_fingerprint` records the scalar value | fingerprint tests, every fixture |
| `schema_fingerprint` flattens container shape | fingerprint and projection tests |
| `ALLOWED_QUERY_PARAMETERS` gains `x-amz-signature` | committed-file gate |
| `redact_url` leaves userinfo in place | writer allowlist test |
| `redact_url` keeps the fragment | writer allowlist test |
| `write()` lets the provenance block bypass its allowlist | writer allowlist test |
| `write()` lets a recorded error bypass its allowlist | writer allowlist test |

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed — all checks passed |
| `ruff format --check .` | Passed — 78 files already formatted |
| `mypy src tests` | Passed — no issues in 63 source files |
| `mypy --platform win32 src` | Passed — no issues in 31 source files |
| Focused fixture suite | Passed — 92 passed, 5 skipped |
| Default suite | Passed — **1082 passed, 11 skipped, 44 deselected** in 15.4 s |
| Mutation battery | 10 of 10 killed (one after the coverage it exposed was added) |
| Windows | Not run — no runner in this environment |

### A note on the deselected 44

`tests/integration/test_manager.py` moved behind `-m process_tree` in `9010794`, because
`T-019`'s live defect leaves descendants that wedge later runs — which is what produced the
reviewer's own hung full-suite attempt on `73d04c6`. Those 43 tests still pass on demand
(`pytest -m process_tree`: 43 passed, 2 skipped) and CI still runs them. `T-019` removes the
marker. Recorded in `ai/TESTING.md` §2 and §7 and in `T-019`'s entry, and called out here because
it changes what a default run proves.

## 2026-07-27 — T-018 structural correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-018`; the bounded head also contains `T-019`'s test-selection commit
**Correction base:** `73d04c6f47cb55403f88b7764df08c51d1e9751f`
**Correction head:** `5f0a6c4a2954cfbc68eb8e956118f68e53e1e454`
**Review unit:** `2f85a32` (structural fixture correction), `9010794` (process-tree marker),
and `5f0a6c4` (decision/records and mutation-survivor coverage)
**Branch:** `main`, clean at inspection, 20 commits ahead of `origin/main`, not pushed
**Platforms verified:** Linux locally; Windows not run
**T-018 verdict:** **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T018-R1` | **Critical** | **Yes** | **Open — the allowlist closes the credential-name class, but `_schema` can itself carry captured data.** The structural correction faithfully implements `SEC-002` and the reviewer’s earlier recommendation: the four prior credential keys are absent from `info_dict`, and the raw-fixture gate rejects all five sanitizer/gate disagreements by path. However, `schema_fingerprint()` copies every mapping key verbatim and both schema checks inspect only leaf *values*. `capture.write()` given `{"unknown_map": {"credential-value-as-key-7c6c": "ignored"}}` wrote that known credential into `_schema`; `unexpected_keys()`, `values_in_schema()` and `leaks_in()` all returned `[]`. Mapping keys are captured data too—nested maps commonly use data-derived labels—so the claim that a fingerprint “cannot carry data” is false. `write()` also trusts a caller-supplied `_schema` instead of deriving it at the serialization boundary, and `keep_consumed()` recursively retains values from playlist `entries` although `ytdlp_adapter` reads only their length. The first reproduction alone preserves the irreversible privacy consequence. This is an oversight in the authorized design, including the reviewer’s recommendation, not another credential-marker miss. `SEC-002` must be amended: do not persist arbitrary raw mapping keys; either drop `_schema` or make it name-free (container/type/count only), always derive it inside `write()`, and represent playlist entries by cardinality placeholders rather than unconsumed child values. |
| `T019-R1` | **Medium** | **Yes** | **Open — `9010794` says CI still runs the process-tree suite, but CI excludes it.** `pyproject.toml` adds `not process_tree` to global `addopts`; `.github/workflows/ci.yml` invokes bare `pytest`, so both Linux and Windows check jobs inherit that exclusion. No workflow step opts the marker back in. Consequently all 43 selected manager tests—including mandatory Cancellation and Worker-crash coverage plus unrelated manager protocol/startup tests—are absent from both the local default and CI, contrary to `ai/TESTING.md`, the test-module comment, the implementer record and the commit message. The opt-in suite itself passes locally (**43 passed, 2 skipped**), so add an explicit CI `pytest -m process_tree` step with evidence/timeout, or narrow/remove the module marker; align the records with what actually runs. This is owned by `T-019` and does not alter the substance of the T-018 privacy finding, but a required gate that does not gate blocks approval of the coverage change. |

### Structural verification

The reported correction behavior is real:

- the reviewer’s `passwd`, `passphrase`, `private_key` and `accessKey` payload writes a
  155-byte file with an empty `info_dict`; only their names and `"str"` leaves appear in
  `_schema`;
- raw fixtures containing `cookiejar`, `sessionid`, `clientsecret`, `httpheaders` and
  `oauth2` are all rejected by `unexpected_keys()`;
- consumed URL values lose userinfo, query and fragment, and the five committed user-directory
  shapes are removed at `write()`;
- every committed fixture passes the independent allowlist, schema-leaf and text scans and
  still projects into the declared model.

The new negative proof is:

```python
capture.write(
    path,
    {
        "_fixture": {},
        "info_dict": {
            "unknown_map": {
                "credential-value-as-key-7c6c": "ignored",
            }
        },
    },
)
```

The written `_schema` is
`{"unknown_map": {"credential-value-as-key-7c6c": "str"}}`. All three committed-file gates
report it clean. A second probe showed that a supplied `_schema` is copied directly; its scalar
value is caught by `values_in_schema()`, but only after `write()` has accepted it. A third
showed playlist-entry `title` and `uploader` values retained even though projection uses only
`len(entries)`.

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **78 files already formatted**. |
| `mypy src tests` | Passed: no issues in 63 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Focused fixture + adapter suite | Passed: **172 passed, 5 skipped**. |
| Default suite | Passed: **1082 passed, 11 skipped, 44 deselected** in 15.11 s. |
| Opt-in process-tree suite | Passed: **43 passed, 2 skipped, 1092 deselected** in 18.81 s. |
| Prior credential probes | Passed under the structural policy: dropped or rejected as intended. |
| Dynamic schema-key probe | Failed the privacy claim: captured data appeared in `_schema` while every gate returned clean (`T018-R1`). |
| CI-selection inspection | Failed the recorded claim: both check jobs run bare `pytest` and inherit `not process_tree` (`T019-R1`). |

The implementer’s ten-mutation batch was not rerun wholesale. Its recorded survivor and ten
final kills are consistent with the committed tests, but the battery did not mutate schema
*keys*, supplied schemas, or entry-value retention. Windows runtime behavior remains
unverified.

### Stop condition

T-018 remains **Blocked**, not returned for another recognizer patch. The allowlist is the right
primary control. Closing `T018-R1` now requires a narrow amendment to `SEC-002` about the
secondary churn record: arbitrary captured key strings cannot be called value-free. The safest
choice is to omit names for all unconsumed data (or omit `_schema` entirely), retaining only
name-free container/type/count information if that evidence is still worth keeping. This gives
up detection of a rename the adapter does not read, which is consistent with the task’s actual
projection-contract purpose and safer than hashing potentially low-entropy personal data.

## 2026-07-27 — T-018 fifth correction batch and T-019's first, returned

**Implementer:** Claude Code
**Tasks:** `T-018` (`T018-R1`, Critical), `T-019` (`T019-R1`, Medium)
**Correction base:** `5f0a6c4`
**Authorization:** maintainer, 2026-07-27 — `SEC-002` amended, and an explicit CI step chosen
over narrowing the marker
**Awaiting re-review.** Only the Reviewer marks a finding Resolved.

### `T018-R1` — the finding is accepted in full, including that it was my design

The reviewer's probe is reproduced and it is exactly right. `schema_fingerprint()` copied every
mapping key verbatim; a mapping key is captured data; `{"unknown_map": {"<secret>": "ignored"}}`
therefore wrote the secret to disk with all three gates reporting clean. The claim that a
fingerprint "cannot carry data" was false as written, and it was false in the recommendation
that produced it as well as in the implementation.

**The fingerprint is removed rather than made name-free**, on the maintainer's ruling. A record
that can say only "a mapping of nine things, one of them a list" names nothing that changed and
churns on every yt-dlp release — it would have become a noisy test somebody deleted, while
remaining a second place data could appear. Hashing was rejected: the material at risk is
low-entropy personal data, which a hash does not protect.

Two further corrections from the same finding:

- **`write()` derives everything it writes.** A caller-supplied `_schema` was previously copied
  through, so a value that had never passed the allowlist reached disk. Nothing outside
  `_fixture`, `info_dict` and `error` is carried, and those three are rebuilt.
- **A playlist entry is a count.** `ytdlp_adapter` reads `len(entries)`; capture recursed into
  each entry and kept its consumed fields — the largest body of retained data in the set, held
  for no reader. Entries are placeholders.

### The reviewer's three probes, re-run against this head

| Probe | Result |
|---|---|
| `{"unknown_map": {"credential-value-as-key-7c6c": "ignored"}}` through `capture.write()` | 40-byte file: `{"_fixture": {}, "info_dict": {}}`. Neither the secret nor the containing key's own name appears. |
| A caller-supplied `_schema` | Dropped. `write()` emits only the three derived blocks. |
| Committed playlist entries | `[{}, {}, {}, {}, {}, {}, {}]`, `playlist_count: 7`. No title, no uploader. 12 KB → 1.4 KB. |

All three are permanent assertions now: `test_a_secret_used_as_a_mapping_key_is_not_written`,
`test_the_writer_ignores_anything_the_caller_supplies_beside_the_known_blocks`, and
`test_a_playlist_entry_is_a_count_and_never_a_record`. The gate refuses both a restored `_schema`
and any key inside an entry, independently of the writer
(`test_the_gate_refuses_a_shape_record_and_a_populated_entry`).

### The fixtures were re-applied, not re-captured

Each committed file was fed back through `capture.write()` — no network call, no new extraction.
Every fixture is therefore, by construction, what the writer produces under the amended policy;
the `captured` dates still describe the extractions they came from, which is what they always
meant. `policy` strings were rewritten to the sentence that now holds.

### `T019-R1` — accepted; the claim was false and is corrected in all four places

`addopts` is global, both check jobs ran bare `pytest`, no step opted the marker back in. For one
day Cancellation and Worker crash gated nothing anywhere. `.github/workflows/ci.yml` now carries
a **Process-tree suite** step in the `check` job on both platforms, after the main test step:
`-m process_tree` load-bearing against pytest's exit-5-on-empty-collection (`T031-R2`),
`timeout-minutes: 10` because the defect under test is one that hangs, and its own junit XML and
log in the evidence artifact. `ai/TESTING.md` §2 and §7, the module comment and `T-019`'s entry
each now name the step that makes the claim true. **The CI step itself cannot be verified from
here** (`OPS-003`); locally, `pytest -m process_tree` is 43 passed, 2 skipped.

### Mutation evidence — 12 mutations, 12 killed

Including the four the reviewer named as unmutated last round:

| Mutation | Killed by |
|---|---|
| `write()` carries the caller's blocks, including a restored `_schema` | supplied-payload and gate tests |
| `keep_consumed` recurses into entries again | entry-cardinality test, committed-fixture gate |
| the gate accepts a restored `_schema` | `test_the_gate_refuses_a_shape_record_and_a_populated_entry` |
| the gate accepts an entry carrying allowed info-dict keys | same test |
| the eight fourth-batch guards (allowlist, formats, query allowlist, userinfo, fragment, provenance, error, user directories) | as recorded in the previous entry |

### Validation

| Check | Result |
|---|---|
| `ruff check .` | Passed |
| `ruff format --check .` | Passed — 78 files already formatted |
| `mypy src tests` | Passed — no issues in 63 source files |
| `mypy --platform win32 src` | Passed — no issues in 31 source files |
| Default suite | Passed — **1086 passed, 11 skipped, 44 deselected** in 15.1 s |
| Opt-in process-tree suite | Passed — **43 passed, 2 skipped** |
| Mutation battery | 12 of 12 killed |
| Windows, and the CI step | Not run — no runner in this environment (`OPS-003`) |

## 2026-07-27 — T-018 fifth correction verified; T-019 coverage correction verified

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-018` (`T018-R1`) and the bounded `T-019` coverage correction (`T019-R1`)
**Correction base:** `5f0a6c4a2954cfbc68eb8e956118f68e53e1e454`
**Correction head:** `e3c9596f127fe6b288dbb790052c02ca1d81454d`
**Review unit:** `git show e3c9596`, focused on the two unresolved findings and correction
regressions
**Repository state at inspection:** clean; checked out on
`phase1-orphans-logging-lifecycle`, with `main` and `origin/main` resolving to the same
correction head. The branch is intentional staging for subsequent work.
**Platforms verified:** Linux locally; Windows and the GitHub Actions step were not run
**T-018 verdict:** **Approved**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T018-R1` | **Critical** | **No** | **Resolved.** The amended `SEC-002` boundary is implemented at the serialization door. `schema_fingerprint()` and every committed `_schema` block are gone; `write()` rebuilds only `_fixture`, `info_dict` and `error`, so caller-supplied `_schema` and unrelated blocks do not reach disk; and playlist entries preserve cardinality as empty placeholders rather than retaining child values the projection never reads. The public dynamic-key probe wrote the exact 40-byte `{"_fixture": {}, "info_dict": {}}` payload, with neither the credential nor `unknown_map` present. A supplied `_schema` carrying `SID=secret` was dropped. A hostile two-entry playlist became `[{}, {}]`, with its titles, uploader and cookie absent. Independently, `unexpected_keys()` rejected both a restored `_schema` and `info_dict.entries[0].title`. The committed seven-entry fixture contains seven empty placeholders and `playlist_count: 7`. The correction removes the leaking secondary design instead of extending the recognizer again; no privacy-boundary escape remains in the reviewed correction. |
| `T019-R1` | **Medium** | **No** | **Resolved.** The `check` job's `ubuntu-latest` / `windows-latest` matrix now contains a dedicated `pytest -m process_tree` step after the default suite, with a ten-minute step timeout and separate JUnit/text evidence included by the existing always-run artifact upload. Local collection proves the explicit selector is load-bearing and selects **43** tests despite global `not process_tree` addopts; the opt-in run passed **43 passed, 2 skipped**. `ai/TESTING.md` §2 and §7 and the integration-module comment now accurately say CI has an explicit step. GitHub Actions and Windows runtime results remain unverified locally under `OPS-003`; that does not make the gate vacuous, and any platform failure is evidence for `T-019`'s original descendant-process work rather than a recurrence of this finding. |

### Independent verification

| Check | Result |
|---|---|
| `git diff --check 5f0a6c4..e3c9596` | Passed. |
| Public writer/gate probes | Passed: dynamic mapping key dropped in a 40-byte file; supplied `_schema` dropped; playlist contents reduced to placeholders; hostile `_schema` and populated entry rejected by path. |
| Fixture + adapter tests | Passed: **176 passed, 5 skipped**. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **78 files already formatted**. |
| `mypy src tests` | Passed: no issues in 63 source files. |
| `mypy --platform win32 src` | Passed: no issues in 31 source files. |
| Default suite | Passed: **1086 passed, 11 skipped, 44 deselected** in 14.98 s. |
| Process-tree suite | Passed outside the restricted socket sandbox: **43 passed, 2 skipped, 1096 deselected** in 18.88 s. The first sandboxed attempt was invalid infrastructure evidence: nine localhost-dependent cases received `PermissionError` while 34 passed. |

The implementer's 12-mutation battery was not repeated wholesale. The four mechanisms added
for this correction are directly pinned by discriminating tests and were exercised through
the public writer and independent gate during this review.

### Verdict and remaining boundary

`T018-R1` no longer blocks and **T-018 is closed as Approved**. No new finding is opened against
T-018. The narrower `NFR-008` trade—an unconsumed upstream field rename is no longer detected—is
explicitly authorized in amended `SEC-002`.

`T019-R1` is also resolved. This does **not** approve or complete `T-019`: that task still owns
the pre-existing live defect in descendant-process cleanup and its Windows proof. The new CI
step makes that work observable on both platforms; its first real Windows result remains
unverified here.

## 2026-07-27 — T-019, T-038 and T-051 implemented on `phase1-orphans-logging-lifecycle`

**Implementer:** Claude Code
**Tasks:** `T-019` (live defect + Windows proof), `T-038` (logging), `T-051` (Planner decision)
**Base:** `e3c9596` (the reviewed and approved head)
**Awaiting review.** No finding is marked Resolved by this record.

### `T019-R1` is verified running, which the previous record could not claim

CI run `30293051118` on `e3c9596` executed the Process-tree suite step on both platforms:
**ubuntu-latest 43 passed, 2 skipped; windows-latest 43 passed, 0 skipped.** That is the first
Windows *runtime* evidence in the vertical slice, and it discharges the "the CI step itself
cannot be verified from here" caveat recorded against `T019-R1`.

### `T-019` — the defect, and two ways my own tests were wrong about it

The production fix is `downloader/process_tree.py`: containment in the child (POSIX `setsid`,
Windows Job object with `KILL_ON_JOB_CLOSE`), signalling from the parent, and three paths covered
— cancellation, a worker that dies unasked, and application exit. The task entry describes it.

What is worth reviewing carefully is that **the first two versions of the tests passed while
proving nothing**, and both were found by mutation rather than by reading:

1. **The cancel test was carried by another mechanism.** Removing the escalation's group
   signalling left the suite green, because the release-path reaping killed the descendant a
   moment later anyway. The guard had no evidence of its own.
   `test_a_descendant_is_asked_to_stop_before_it_is_killed` now separates them: the grandchild
   handles `SIGTERM` and writes a marker, so being *asked* to stop is distinguishable from being
   stopped — which is the difference `REQ-015` cares about, since `ffmpeg` asked can close its
   output and `ffmpeg` killed cannot.

2. **Every survival assertion was blind in the state it was asserting about.** A grandchild whose
   parent has died is reparented to `init` and stops being our descendant, so
   `worker_processes()` — a recursive walk — reported nothing left while the process was still
   running. Verified with a standalone probe, not reasoned about. The three tree tests now
   capture pids while the tree is intact and ask about them by identity (`still_running`).

**That second fix exposed a real production bug**, which is the part most worth checking. The
reaping resolved a pid to a group at signalling time, and `Process.is_alive()` reaps the zombie
as a side effect of asking — so by the time a dead session was released there was no pid left to
resolve, `getpgid` raised, and nothing was signalled. The module now takes **group ids**;
`group_of()` is the only place a pid becomes one, and the manager learns it on a tick while the
worker is alive (`_learn_the_group`). Reading it at `start()` does not work either: the pid
exists before the child has run `contain_this_process()`.

**Two rules, opposite in shape**, and this cost a debugging round: from the parent a group equal
to ours is refused, because it means containment failed and signalling it would kill the GUI;
from inside the worker our group *is* the target, so the check is that we **lead** it.

**`tests/unit/test_process_tree.py` exists because those two rules are unreachable when
everything works.** They only fire when a worker failed to contain itself, which healthy
integration tests never produce — and the mutation removing the parent's guard did not merely
survive, it `killpg`'d the group the harness was in and killed the mutation run. That is the
behaviour the guard prevents, and it cannot be demonstrated in-process. Four unit tests, no
skips; an earlier version skipped when pytest happened to lead its own group, which is where it
mattered most.

### `T-038` — redaction is a `Formatter`, and the limits are asserted

`core/logging.py`. Every handler installed here renders through `RedactingFormatter`, which
rewrites the finished string — so `%`-args, a caller's f-string, an `extra` field the format
names, and an exception traceback all converge on one rewrite. A test asserts every handler on
the application's tree has it.

Every URL loses query, userinfo and fragment: an empty allowlist rather than a judgement about
which parameter names look like secrets, which is the `T-018` lesson applied before rather than
after four rounds. Two limits are stated and tested rather than left to be discovered — an output
path is never touched (`T014-R6`), and a bare `NAME=value` is not chased, because it is
indistinguishable from `height=1080` and cookie *contents* are outside what `REQ-026` binds.

### `T-051` — `ARC-004`, and no source changed

A download starts from `READY` as well as `QUEUED`, using edges the machine already has; the
download re-extracts rather than re-probing, because `YoutubeDL.download()` resolves the URL
itself and cannot be handed a previous extraction. `T-016` owns the code.

## 2026-07-27 — T-019, T-038 and T-051 independent review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-019`, `T-038`, `T-051`
**Review base:** `e3c9596f127fe6b288dbb790052c02ca1d81454d`
**Review head:** `e08c265051552624a0447d18ef803c3c8f30879a`
**Review unit:** `git diff e3c9596..e08c265` (five commits, including the Windows correction
and its evidence record)
**Repository state at inspection:** clean `main`; `HEAD`, `origin/main` and `origin/HEAD` all
resolve to the review head
**Platforms verified:** Linux locally; Windows from GitHub Actions run `30303348265`
**T-019 verdict:** **Changes requested**
**T-038 verdict:** **Changes requested**
**T-051 verdict:** **Approved**

### Finding summary

| ID | Severity | Blocks approval | Status |
|---|---|---:|---|
| `T019-R2` | **High** | **No** | **Resolved within the review range.** |
| `T019-R3` | **Medium** | **Yes** | Open — a containment failure deliberately runs work whose descendants cannot be stopped. |
| `T019-R4` | **Medium** | **Yes** | Open — three explicit acceptance claims are not established, and failed mutation runs leak their proof processes. |
| `T019-R5` | **Medium** | **Yes** | Open — the restored bare default test command reproducibly wedges. |
| `T038-R1` | **Critical** | **Yes** | Open — credential/cookie shapes named by the task still reach emitted logs. |
| `T038-R2` | **High** | **Yes** | Open — per-job logging and listener shutdown are helper-only, with no production caller. |

### `T019-R2` — the Windows handle defect is corrected

**Severity:** High
**Blocks approval:** No
**Disposition:** **Resolved.**

At `989ef46`, `CreateJobObjectW` had no `ctypes` return declaration, so Python's default
`c_int` return truncated a 64-bit `HANDLE`. GitHub Actions run `30302798113` is tied to that
exact head and failed the Windows job, including the four descendant-lifetime tests. Commit
`8644c95` declares the return and argument types for all five Win32 calls used by the module.

Run `30303348265`, at `8644c953e0108af894e97ea43597372637cd98de`, is green on
`windows-latest`: `test_containment_succeeds_on_this_platform` and all four descendant paths
pass; the job reports **1163 passed, 20 skipped**. The review head only adds the evidence record
after that code. This is the required runtime proof, not an inference from the Linux branch or
from `mypy --platform win32`.

### `T019-R3` — containment failure recreates the defect this task owns

**Severity:** Medium
**Blocks approval:** Yes

`contain_this_process()` returns `False` when `setsid()`, Job creation, Job configuration or
Job assignment fails. `prepare_this_worker()` logs that its descendants will outlive it and
then `spawn_session()` proceeds directly into `run_session()` (`worker.py:596-612, 640-650`).
That is an accurate warning about an acceptance failure, not a recovery:

- on POSIX, the parent's group guard refuses the shared GUI group and falls back to killing
  only the worker; the watchdog also refuses to kill a group it does not lead;
- on Windows, a failed Job object leaves no kernel-owned set to reap when the worker dies.

The trigger is narrow, so this is Medium rather than High, but the consequence is exactly
`T-019`'s live defect: cancel can return while an `ffmpeg` descendant keeps writing. The task's
unqualified “no surviving descendant” criterion is therefore not met.

**Required correction:** fail the session before yt-dlp can spawn anything when containment
cannot be established, or provide and prove another containment mechanism. Logging that the
guarantee is absent does not satisfy it. Add a discriminating test in which containment fails
and the session is shown not to enter yt-dlp or spawn a descendant.

### `T019-R4` — the acceptance evidence does not prove what its record says

**Severity:** Medium
**Blocks approval:** Yes

Three explicit criteria in `T-019` remain unproved:

1. `test_the_detector_sees_a_grandchild_and_not_just_a_worker` creates `child` and
   `grandchild` as two direct `Popen` children of pytest. Its only parentage assertion is
   `assert child.pid == psutil.Process(grandchild.pid).ppid() or True`
   (`test_manager.py:617-655`), which is unconditionally true. The test therefore proves that
   the detector sees two siblings, not that it sees the required second-level process.
2. The real cancellation test asserts that a `.part` file exists, but never asserts that the
   completed output is absent (`test_manager.py:817-819`). A simultaneous completed rename
   would pass, contrary to the “no completed-file rename” criterion.
3. Cancellation durations are calculated only for pass/fail assertions. They are not emitted
   as a test property, report, or other retained evidence, so the criterion that timings be
   recorded and trendable is not met.

The mutation evidence also needs failure-safe cleanup. Before final validation, **111** exact
`GRANDCHILD_PROGRAM` processes and three childless worker/resource-tracker pairs from earlier
mutation attempts were still alive, some for more than two hours. The ordinary current-head
manager run created no new leak, but a mutation is supposed to make an assertion fail; tests
that clean up only after their assertions necessarily leak the deliberately stubborn process
when the evidence works. The reviewer removed those exact test helpers before the final run.

**Required correction:** build a real parent→grandchild relationship in the detector
self-test and assert it without a vacuous clause; assert both partial presence and completed
output absence; retain elapsed values in test evidence; and put tracked-process cleanup in
`finally` paths so a killed mutation cannot contaminate later runs.

### `T019-R5` — bare `pytest` is still an intermittent hard gate failure

**Severity:** Medium
**Blocks approval:** Yes

`T-019` says it restores the default test run after loose descendants made it wedge
intermittently. On a clean process table, the canonical bare command did not complete:

- two full `timeout 180 .venv/bin/pytest` runs stopped with exit 124 after 46 manager tests;
- the bounded minimal order
  `pytest test_crash_kill.py test_freeze_probe.py test_manager.py` also stopped with exit 124
  after the same 46 manager tests;
- at the stall, no worker remained, but pytest's main thread waited on a futex while one Qt
  thread and the multiprocessing resource tracker remained alive.

The same 62-test ordered subset passed **62/62 in 35.78 s** with `-vv`, and the final verbose
full run passed **1174 passed, 11 skipped, 1 deselected in 39.84 s**. Verbosity changing the
timing is evidence of the race, not a discharge of the canonical `pytest` gate. The next test
in collection order is
`test_the_failure_is_recorded_before_anything_is_cleaned_up`, which drives `_abort_start`
against a live pump and calls `QThread.terminate()` through the unwind; focused investigation
should start there, but the review does not claim that as the established root cause.

**Required correction:** make the bare command complete reliably, add a bounded regression
that distinguishes a stopped pump from a merely requested termination, and retain the
timeout/reproduction evidence. This is a required-check failure, so it blocks despite the
verbose pass and green CI's `pytest -v`.

### `T038-R1` — the redactor's documented carve-outs violate its task contract

**Severity:** Critical
**Blocks approval:** Yes

The task and `ARCHITECTURE.md` §8 require emitted output to redact cookie paths, cookie
contents, proxy credentials and token-bearing URL queries at the handler. The implementation
instead declares several inputs out of scope without a higher-authority amendment. Real-handler
probes on the review head showed:

- `SID=review-cookie-7c6c` survives unchanged;
- a cookie path containing a space is only partly replaced, leaving the identifying prefix;
- a relative `cookies.txt` survives;
- a syntactically malformed URL containing `?token=review-url-token-7c6c` survives because
  `_bare_url()` returns its input on `urlsplit()` failure;
- a schemeless `user:review-proxy-pass-7c6c@proxy.invalid:8080` survives.

These are false negatives at the sink the task says must fail closed. A credential or cookie
written to a persistent log is a breached privacy boundary, hence Critical under `AGENTS.md`
§9 even though the correction may be small.

There is also an authority conflict to resolve deliberately: `REQ-026` preserves a cookie path
that yt-dlp itself names in a diagnostic, while the lower-authority task and architecture say
cookie paths are redacted. The implementer's bare-value carve-out does not resolve that
conflict and does not authorize weakening the other shapes.

**Required correction:** either implement the current task/architecture boundary for every
emitted route, including parser failure and schemeless credentials, or obtain a Planner/
maintainer amendment that states the narrower boundary and reconciles `REQ-026`,
`ARCHITECTURE.md` §8 and `T-038`. Tests must write every accepted shape through a real
installed handler and scan the resulting file for the marker.

### `T038-R2` — no production path creates a per-job log

**Severity:** High
**Blocks approval:** Yes

`open_job_log()` and `job_log_path()` exist, and unit tests manually attach their handler, but
`rg open_job_log src` finds only the function definition. No manager/session code installs,
filters, removes or closes a job handler. Likewise,
`stop_listening_for_worker_logs()` has no production caller. The only production integration
is the application-wide handler plus worker queue.

Consequently the task's “add per-job log files” scope and `ARCHITECTURE.md` §8 are not
implemented. A helper that could create the file is not a per-job log users or later UI code
can rely on. Attaching it naively to the application logger would also route every worker into
every active job once Phase 2 permits concurrency, so the correction must establish job
isolation rather than merely call the helper.

**Required correction:** make session ownership install a redacting handler filtered to that
job, close/remove it on every normal, cancellation, crash and startup-unwind path, and stop the
process-wide listener during application shutdown. Prove two distinct job IDs cannot cross
write, and validate the actual production lifecycle rather than attaching a handler only in a
unit test. `job_log_path()` also assumes IDs are UUIDs although the current model accepts
arbitrary non-empty text; the production wiring must not turn an unchecked ID into a path
component.

### T-051 disposition

`ARC-004` answers the linked Planner question without changing source: a previously probed job
downloads from `READY`, the download re-extracts without presenting a second `PROBING` state,
and `T-016` owns the manager/state implementation. The decision, architecture amendment and
`T-016` task entry agree. **T-051 is Approved with no findings.**

### Independent verification

| Check | Result |
|---|---|
| `git diff --check e3c9596..e08c265` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **83 files already formatted**. |
| `mypy src` | Passed: no issues in **33 source files**. |
| `mypy --platform win32 src` | Passed: no issues in **33 source files**. |
| Manager integration module, verbose | Passed: **52 passed in 23.94 s**. |
| Ordered crash/freeze/manager subset, verbose | Passed: **62 passed in 35.78 s**. |
| Default command, bounded | **Failed to complete:** two full 180-second timeouts and one minimal 90-second timeout, all after the same 46 manager tests. |
| Full suite, verbose | Passed: **1174 passed, 11 skipped, 1 deselected in 39.84 s**. |
| Windows failure run | Confirmed: Actions `30302798113`, head `989ef46`, `windows-latest` failed. |
| Windows correction run | Confirmed: Actions `30303348265`, head `8644c95`, `windows-latest` passed with **1163 passed, 20 skipped** and all five Job-object/descendant checks passing. |
| Early worker-exit probe on POSIX | Ten spawned sessions exited before the first 50 ms manager tick; every manager became idle and every grandchild was dead. No `_learn_the_group` finding. |

The first sandboxed full-suite attempt is not counted as product evidence: localhost sockets
were denied and the subprocess launch inherited a read-only home cache, causing 12
environmental failures. It was rerun with normal OS access. The implementer's mutation counts
were not repeated wholesale; their process residue was observed, identified by the exact test
program, and removed before the final runs.

### Review verdict

`T019-R2` is independently resolved and the Windows Job-object path now has real runtime
evidence. `T-019` remains **Changes requested** on three blocking Medium findings. `T-038`
remains **Changes requested** on one Critical and one High finding. `T-051` is **Approved**.

This is the initial comprehensive review. One focused correction re-review remains available
for the Medium findings; the Critical and High findings remain in the current review until
corrected and independently verified.

## 2026-07-27 — T-019 and T-038 corrections returned (`T019-R3/R4/R5`, `T038-R1/R2`)

**Implementer:** Claude Code
**Correction base:** `e08c265`
**Authorization:** maintainer, 2026-07-27 — the `ARCHITECTURE.md` §8 carve-out for a bare
`NAME=value`, and failing a session outright when containment cannot be established
**Awaiting re-review.** No finding is marked Resolved by this record.

### `T019-R5` — root cause found, and it was not where either of us looked

Reproduced on the first attempt: bare `pytest`, exit 124 after 46 manager tests. The reviewer's
pointer at `_abort_start` was correct, and the mechanism underneath it was `QThread.terminate()`.

A `SIGABRT` stack dump at the stall shows the main thread parked on an internal CPython mutex
(`_PyMutex_LockTimed` / `_PyParkingLot_Park`) inside `multiprocessing.Queue.put` →
`Thread.start()`, and **two threads carrying no Python frame at all**. That is a thread killed at
an arbitrary point, holding an interpreter lock that will never be released.

Two hypotheses, one discarded: the `T-038` log listener's monitor thread was visibly alive in the
same dump, and is innocent — the wedge reproduces with the log queue removed entirely. Disabling
`terminate()` produced **22 consecutive clean runs** against a ~20 % baseline (p ≈ 0.007).

`ResultPump` now reads with a `POLL_SECONDS` timeout and returns when `stop()` is set. **No
`QThread.terminate()` remains in the project.** This changes `T-013`-approved code and the module
docstring that argued against a timed `get()`; that argument is corrected rather than removed —
the timeout is not a competing definition of "the stream ended", it is the only way a stopped
thread can learn it was stopped.

| Gate | Before | After |
|---|---|---|
| Minimal reproduction (`crash_kill`, `freeze_probe`, `manager`) | wedged ~1 run in 5 | **10 / 10 clean** |
| Canonical bare `pytest` | exit 124, reproduced | **3 / 3 clean**, then 3 more after the later corrections |

### `T019-R3` — the guarantee, not a warning about its absence

`spawn_session()` refuses: a legal failed session (one outcome, then the sentinel) and
`UNCONTAINED_EXIT_CODE`, before yt-dlp can spawn anything.
`test_a_worker_that_cannot_be_contained_refuses_to_run` asserts `run_session` is never reached.

### `T019-R4` — each of the three claims, plus the cleanup

- The detector self-test spawns a **real** two-level tree and asserts `ppid()` first. The
  mutation that hands it siblings instead now fails it; the old `or True` could not fail at all.
- Cancellation asserts the completed output is **absent** as well as the partial present.
- Elapsed times go to `record_property`, landing in the junit XML CI already uploads.
- Stray cleanup is an autouse fixture keyed to a unique marker, so it runs when an assertion
  **fails** — precisely when a working mutation leaks its stubborn process.

**A second `or True` was found while fixing the first**, the one `T013-R5` filed as `T-052`.
Removing it showed the production code was right and the assertion was wrong: it looked for the
parametrised component name, which the message never claimed to carry. It now asserts that the
original `OSError`'s own words survive the unwind. That part of `T-052` is discharged here.

### `T038-R1` — all five reproduced, four closed, one documented

| Probe | Before | After |
|---|---|---|
| `C:\Users\A Person\cookies.txt` | directory and name survived | `<redacted>` |
| relative `cookies.txt` | survived | `<redacted>` |
| `https://[bad/v?token=…` (parser failure) | returned **unchanged** | `<redacted>` |
| `user:pass@proxy.invalid:8080` (schemeless) | survived | `<redacted>@proxy.invalid:8080` |
| bare `SID=…` | survived | still survives — **authorized carve-out**, `ARCHITECTURE.md` §8 |

Closing the second nearly broke the log in the other direction: matching any token containing
"cookie" also matches the *word*. The rule is split into a path-with-directory and a filename
that must carry an extension, and `test_ordinary_prose_survives_the_cookie_rules` holds that
line — the mutation removing the extension requirement is killed by the **prose** test.

`ARCHITECTURE.md` §8 now states the carve-out and reconciles it with `REQ-026`/`DAT-003`: a
stored diagnostic keeps a cookie path yt-dlp named, because `NFR-006` requires that message
verbatim; a log is written by this application rather than quoted by it, so the path goes.

### `T038-R2` — wired, isolated, closed

A session opens its own log and closes it on every exit path including the startup unwind;
`shutdown()` stops the process-wide listener. The worker stamps each record with its job id and
the per-job handler admits only that job's — an unstamped record is refused rather than shared.
`job_log_path()` sanitises the id through `core/paths.py` rather than trusting that every `Job.id`
is a UUID. `test_two_jobs_cannot_write_into_each_others_logs` and
`test_a_job_id_never_chooses_its_own_path` cover both.

### Evidence

| Check | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | Passed |
| `mypy` and `mypy --platform win32` (both over `src` **and** `tests`) | Passed — 68 source files each |
| **Canonical bare `pytest`** | **1186 passed, 11 skipped, 1 deselected** — three consecutive runs, 40 s each |
| Mutation battery | **14 of 14 killed** |
| Windows | Not re-run locally; CI will exercise it on push |

## 2026-07-27 — T-019 and T-038 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-019`, `T-038`; focused re-review of `T019-R3`, `T019-R4`, `T019-R5`,
`T038-R1`, and `T038-R2`
**Correction base:** `e08c265051552624a0447d18ef803c3c8f30879a`
**Head:** `eaa5b504d57bec14e55b38b36b4f40f168662523`
**Review unit:** the correction commit at `eaa5b50`; final runtime checks used a clean archive
of that exact head because unrelated `T-016` work began in the shared worktree during review
**Platforms verified:** Linux locally; Windows from the maintainer-reported green CI jobs at
this head
**T-019 verdict:** **Approved**
**T-038 verdict:** **Changes requested**

### Finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T019-R3` | **Medium** | **No** | **Resolved.** `spawn_session()` checks the result of `prepare_this_worker()` before `run_session()` and emits exactly one `Failed` outcome followed by `WorkerFinished` when containment is unavailable. The direct test forces containment failure, proves `run_session()` is never reached, and checks the distinct exit code and diagnostic. The maintainer reports the same refusal path green on Windows. |
| `T019-R4` | **Medium** | **No** | **Resolved.** The detector test now constructs and asserts a real parent→grandchild relationship before consulting `worker_processes()`. Cancellation asserts both the partial file's presence and the completed file's absence. `cancel_seconds`, `cancel_budget_seconds`, and `tree_cleanup_seconds` are retained with `record_property`; the generated test path ran in the focused and full suites. The autouse cleanup fixture scans by the test-only marker after every outcome, including assertion failure, instead of relying on code after the assertion. |
| `T019-R5` | **Medium** | **No** | **Resolved.** No production call to `QThread.terminate()` remains. `ResultPump.stop()` sets a thread-safe event, the queue read polls only to observe that event, and the pump returns through its `finally`, emitting `session_ended`. The focused stopped-pump test passed, as did three consecutive exact-head canonical runs: **1186 passed, 11 skipped, 1 deselected** each, in 53.21 s, 52.57 s, and 52.38 s. None wedged at the former 46-test boundary. |
| `T038-R1` | **Critical** | **No** | **Resolved under the maintainer-authorized boundary.** Real-handler tests remove the identifying part of the spaced cookie path, relative cookie filename, malformed tokenized URL, and scheme-less proxy credential. `_bare_url()` fails closed when parsing fails. Ordinary cookie prose remains readable. `ARCHITECTURE.md` §8 now records the authorized bare `NAME=value` carve-out and reconciles the stored-diagnostic rule in `REQ-026`/`DAT-003` with the stricter emitted-log sink. |
| `T038-R2` | **High** | **Yes** | **Open — the production wiring routes and filters by job, but its two lifecycle ends are not correct yet.** First, result messages and log records use separate multiprocessing queues. `_release()` closes and removes the per-job handler as soon as the result pump and process finish, without establishing that the log listener drained records the worker emitted before `WorkerFinished`. A deterministic probe delayed the listener for two seconds: the worker emitted its stamped line first, the manager became idle and closed the job handler, and the line later reached the application log while the per-job log remained empty. Second, `stop_listening_for_worker_logs()` calls blocking `QueueListener.stop()` from `shutdown()` or its GUI-thread timer completion. Holding one queued handler call for two seconds held `DownloadManager.shutdown()` for **2.001 s**. That reopens `T013-R2`'s exact High consequence: teardown again waits on the GUI thread, only now on log I/O rather than a process or pump. Establish an ordered per-session log drain before closing its handler, and stop/drain the process-wide listener without joining it on the GUI thread. Add deterministic tests for a delayed final worker record and a blocked listener handler. |

### Re-examination of the T-013 guarantees

- **`T013-R4` remains resolved.** `_abandon()` now requests `pump.stop()` rather than killing
  the thread, durably finalizes the job, and retains the session until `finished` or
  `isFinished()` establishes that the thread actually returned. The direct stubborn-pump test
  and the cooperative-stop test both passed.
- **`T013-R3`'s startup unwind remains resolved.** A failed cleanup write requests a cooperative
  pump stop and keeps the session under watch; the original startup failure is persisted before
  cleanup and remains the diagnostic.
- **`T013-R2` is reopened by the logging correction, not by the pump change.** The event-driven
  process/pump lifecycle still performs no blocking wait, but its new final logging call invokes
  `QueueListener.stop()`, which joins the listener on the GUI thread. The open `T038-R2`
  disposition owns that correction regression; it is not a second independent fix.

### Per-job isolation scope

The job-id stamp and rejecting handler filter establish per-job routing for Phase 1's
one-session-at-a-time manager. They cannot establish concurrent non-cross-write because Phase 1
cannot keep two sessions open simultaneously. `T-053` owns that non-blocking Phase 2 proof when
the pool first permits concurrency; it does not excuse the current ordered-drain failure above.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check e08c265..eaa5b50` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **83 files already formatted**. |
| `mypy` | Passed: no issues in **68 source files**. |
| `mypy --platform win32` | Passed: no issues in **68 source files**. |
| Focused logging/process-tree/worker-logging/manager suite | Passed: **94 passed in 33.27 s** with normal localhost access. The sandboxed attempt's ten loopback `PermissionError`s were environmental and excluded. |
| Canonical bare `pytest`, exact head | Passed three consecutive runs: **1186 passed, 11 skipped, 1 deselected** each. |
| Maintainer-reported CI | Green: Ubuntu **1186 passed, 11 skipped, 1 deselected**; Windows **1175 passed, 20 skipped, 21 deselected**; both Windows desktop/frozen jobs succeeded. |
| QThread termination search | No production `QThread.terminate()` call; remaining executable `.terminate()` calls target processes. |
| Delayed final-log probe | Failed as described: application log contained the worker's stamped line; the per-job log was empty. |
| Listener-shutdown probe | Failed as described: a queued two-second handler delay made `shutdown()` take **2.001 s**. |
| Working-tree isolation | One repeated run was discarded after unrelated uncommitted `T-016` changes appeared mid-run. The final two runs used a clean `git archive eaa5b50`; no reviewed-source file was changed by the reviewer. |

### Verdict and budget

`T-019` is **Approved**: R3, R4, and R5 are independently resolved, and the Windows
containment and cooperative-pump paths have the requested CI evidence.

`T-038` remains **Changes requested** because High `T038-R2` is still open and directly
regresses High `T013-R2`. This is the focused correction re-review. The remaining High defect
continues through correction and independent verification under `AGENTS.md` §9; it is not
stopped by the ordinary pass budget. `T038-R1` is resolved.

## 2026-07-27 — T-038 R2 second focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-038`; focused re-review of High `T038-R2`
**Correction base:** `eaa5b504d57bec14e55b38b36b4f40f168662523`
**Head:** `dd1dad8`
**Review unit:** `b0879d7` contains every source/test correction; `dd1dad8` adds only its CI
evidence record
**Repository state at inspection:** source and tests inspected and run from a clean
`git archive dd1dad8`; the shared checkout's unrelated uncommitted `T-016` work was not used
**Platforms verified:** Linux locally; Windows from GitHub Actions run `30315752749`
**Verdict:** **Changes requested**

### Finding disposition

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T038-R2` | **High** | **Yes** | **Open — both original probes are corrected, but two direct lifecycle siblings still lose the guarantee.** The marker establishes ordering for one session's ordinary release, and the listener stop no longer joins on the GUI thread. However, reopening the same job closes its pending handler before the replacement is created and attached. A deterministic probe queued a stamped record before the old marker, held replacement-handler creation after `_close_any_drain_for()`, and dispatched both queued records in that interval: the old handler was closed, the new one was later attached, and the per-job log remained empty. This is the ordinary `T-016` probe→download path the correction claims to support. Separately, non-blocking stop is not yet a complete shutdown lifecycle: `DownloadManager` emits `idle` immediately after requesting listener stop, although its own contract says `idle` is when composition may quit. With a handler held inside `emit`, the reviewer observed `idle` while that handler was still blocked and the listener thread was alive. A process that obeys `idle` may therefore exit before the daemon listener drains the marker and final records. Reuse or atomically hand over a same-job draining handler so there is never a no-handler interval; and make listener completion part of the event-driven shutdown lifecycle, emitting `idle` only after the listener has actually returned and its drains have been swept, without waiting on the GUI thread. Add deterministic assertions for the reopen gap and for withholding safe-to-quit `idle` while the listener is blocked. |

### What the correction does establish

- **The ordinary end-of-session marker is ordered correctly.** The worker process has exited
  before `_release()` queues the marker, so its multiprocessing feeder has flushed the worker's
  records first. A shutdown sentinel queued by the parent afterwards follows the marker on the
  same parent-side queue.
- **The original delayed-record probe is fixed.** The gated integration test holds a worker
  record in dispatch while the session releases, then proves it reaches the still-attached
  per-job handler before the marker detaches and closes that handler.
- **The original GUI-thread join is removed.** The listener's `stop()` enqueues its sentinel
  and returns. The committed blocked-handler test and reviewer inspection confirm neither
  `shutdown()` nor `_tick()` joins the listener.
- **The four exceptional drain edges are useful and tested:** no active queue, marker enqueue
  failure, listener exit before a marker, and an attempted same-job reopen all close their old
  handler. The last edge's resource cleanup is real; its claim that queued records cannot be
  lost during the handover is the remaining defect above.

### T-013 regression check

- **`T013-R2`'s original no-GUI-wait consequence is resolved again.** A blocked log handler no
  longer holds `shutdown()`. The open problem is the new logging subsystem announcing safe
  completion too early, and remains owned by `T038-R2`.
- **`T013-R3` and `T013-R4` remain resolved.** No startup-unwind, pump-stop, session-retention,
  or durable-finalization line changed in this correction. The focused manager module passed,
  including the direct cleanup and stubborn-pump mechanisms.

### Live-handler iteration

The listener still iterates `logging.getLogger(APP_SLUG).handlers` live. That does not create a
separate Phase 1 blocker once the same-job handover is made atomic: ordinary marker removal
happens on the listener thread between records, and Phase 1 has only one live session. It
remains a concurrency-sensitive shape. `T-053` should exercise handler addition/removal while
both Phase 2 job streams are active, not only compare their final file contents.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check eaa5b50..dd1dad8` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **83 files already formatted**. |
| `mypy` | Passed: no issues in **68 source files**. |
| `mypy --platform win32` | Passed: no issues in **68 source files**. |
| Focused logging/worker-logging/manager suite | Passed: **93 passed in 50.85 s**. |
| Canonical bare `pytest`, exact head | Passed: **1192 passed, 11 skipped, 1 deselected in 82.01 s**. |
| Maintainer correction runs | Three Linux bare runs passed; six claimed mutations were killed. |
| CI at code head `b0879d7` | Run `30315752749` green: Ubuntu **1192 passed, 11 skipped, 1 deselected**; Windows **1181 passed, 20 skipped, 21 deselected**; Windows desktop **20 passed, 1202 deselected**; both frozen jobs succeeded. |
| Same-job handover probe | Failed as described: old handler closed, replacement attached later, queued stamped record absent from the per-job file. |
| Safe-to-quit probe | Failed as described: `idle` observed while the gated handler was blocked and the listener thread was alive; listener stopped only after the gate was released. |

### Readiness and budget

`T-038` remains **Changes requested** on High `T038-R2`. The original two deterministic
failures are fixed, but the correction has not yet made the per-job drain lossless across the
normal same-job handover or made asynchronous listener completion part of the shutdown
lifecycle. Because the survivor is High, focused correction and independent verification
continue under `AGENTS.md` §9 regardless of the ordinary review-pass budget.

## 2026-07-27 — T-038 R2 third focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-038`; focused re-review of High `T038-R2`
**Correction base:** `dd1dad83ae1e327421fb593d4e700c524fd55e86`
**Head:** `098ba3f93ad2f9d0e8a045d936b21f0845b7c500`
**Review unit:** `d6f3581` contains every source/test correction; `098ba3f` adds only the CI
evidence record
**Repository state at inspection:** source and tests inspected and run from a clean
`git archive 098ba3f`; the shared checkout's unrelated uncommitted `T-016` work was not used
**Platforms verified:** Linux locally; Windows from the implementer-provided GitHub Actions run
`30317992554`
**Verdict:** **Approved**

### Finding disposition

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T038-R2` | **High** | **No** | **Resolved.** A same-job, same-file reopen now atomically removes the pending drain and returns the identical still-open, still-attached handler. The listener therefore has no interval in which a stamped record lacks a per-job sink; the obsolete marker later finds no drain and cannot close the reclaimed handler. The file comparison is independently exercised: a pending handler for the same job but a different path is not reclaimed or misrouted. During shutdown, `idle` is withheld while the exact listener thread returned by the stop request remains alive. Completion is polled by the existing Qt timer, never joined; if the listener remains wedged past the bounded `reap_seconds` deadline, shutdown records `gave_up_on_the_log` and proceeds. The committed gap, different-file, in-flight-listener, and bounded-wedge tests all passed, as did the full exact-head suite. |

### Shutdown failure reporting

The `gave_up_on_the_log` property is sufficient for this correction; a new signal is not
required to resolve the finding. An `idle` consumer can query the property synchronously when
the lifecycle completes. Writing a warning through the same logger is unsafe on precisely this
path because `Handler.handle()` may be waiting on the lock held by the wedged listener, restoring
the GUI-thread freeze. Adding a second signal without a current composition consumer would not
make the condition more visible yet; `T-036` may decide how the assembled application presents
this exceptional state.

The bounded escape deliberately weakens “all records are written before `idle`” only when a
handler has failed to return for the full reap deadline. That is an explicit, observable
fail-open choice between a truncated diagnostic and an application that cannot close, not the
ordinary loss that opened `T038-R2`.

### T-013 regression check

- **`T013-R2` remains resolved.** `shutdown()` starts the lifecycle and returns; `_tick()` polls
  listener liveness and deadlines. No positive-duration process join, listener join,
  `QThread.wait()`, sleep loop, manual event pumping, or `QThread.terminate()` is present.
- **`T013-R3` remains resolved.** The startup transaction still records process and pump starts
  independently, persists the original failure before signaling, and retains half-built work
  until cooperative cleanup completes.
- **`T013-R4` remains resolved.** `_abandon()` requests `pump.stop()`, finalizes durably, and
  retains the session until `finished` or `isFinished()` proves that the pump returned.

The manager-inclusive focused suite passed all of those paths. The changed logging lifecycle
adds only timer-driven listener observation and does not alter the startup or pump ownership
mechanisms.

### Remaining limits

- Windows exercised the three new tests once in CI; the repeated local runs reported by the
  implementer and this reviewer's run were Linux only.
- The test gate deliberately does not wedge GUI-thread log calls. A GUI-thread call through an
  independently wedged handler can still block; that application-wide logging shape predates
  this correction and is not evidence that the listener lifecycle itself waits.
- The listener still iterates the live application-handler list. Phase 1's single-session
  routing is established, but `T-053` still owns concurrent add/remove and cross-write proof
  when Phase 2 permits two live sessions.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check dd1dad8..098ba3f` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **83 files already formatted**. |
| `mypy src` | Passed: no issues in **33 source files**. |
| `mypy --platform win32 src` | Passed: no issues in **33 source files**. |
| Configured `mypy` | Passed: no issues in **68 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **68 source files**. |
| Logging and worker-logging subset | Passed: **43 passed in 2.75 s**. |
| Focused logging/worker-logging/manager suite | Passed: **96 passed in 34.08 s**. The `95 passed` in the handoff and `ai/TASKS.md` is an off-by-one evidence-record error; all selected tests passed and the canonical count below matches the correction record. |
| Canonical bare `pytest`, exact head | Passed: **1195 passed, 11 skipped, 1 deselected in 54.60 s**. |
| Implementer-provided CI at code head `d6f3581` | Run `30317992554` green: Ubuntu **1195 passed, 11 skipped, 1 deselected**; Windows **1184 passed, 20 skipped, 21 deselected**; Windows desktop **20 passed, 1205 deselected**; both frozen jobs succeeded. |
| Same-job reopen mechanism | Passed: the handler is identical before and after reclaim, the record dispatched before caller reattachment is written, and adding the returned handler does not duplicate it. |
| Different-file mechanism | Passed: the old drain is not reclaimed for another path. |
| Listener completion mechanisms | Passed: `idle` remained withheld while the gated listener was alive, arrived after release, and arrived with `gave_up_on_the_log == True` when the shortened deadline expired while the handler remained blocked. |

The first focused attempt is excluded from product evidence: the shared virtual environment's
editable install took import precedence over the archive, pairing archived tests with the dirty
shared source, and the sandbox denied localhost sockets. Forcing the archive's `src` first and
granting normal local-process/socket access produced the clean focused and canonical results
above.

### Readiness

`T038-R2` is independently resolved. No blocking finding remains, so `T-038` is **Approved**.
The focused-count typo is mechanical evidence bookkeeping and does not change the verdict.

## 2026-07-27 — T-016 initial review

**Reviewer:** Codex (Reviewer)
**Task:** `T-016` — Add-URL dialog with probe results
**Review base:** `098ba3f93ad2f9d0e8a045d936b21f0845b7c500`
**Head:** `33ebd118f40b4c0f4137f3c1d82db91e15706d05`
**Implementation commits:** `d9936f4`, `57c7e5c`, and `33ebd11`
**Excluded coordination commits in the range:** `0b914a5` preserves prior reviewer records;
`3b9d937` records T-038's already-issued approval
**Repository state at inspection:** clean `main`, in sync with `origin/main`; source and tests
were inspected and run from a clean `git archive 33ebd11`
**Platforms verified:** Linux locally; Windows from the implementer-provided GitHub Actions run
`30320408833`
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Finding and required correction |
|---|---|---:|---|
| `T016-R1` | **Critical** | **Yes** | **The probe result is bound only to a job id, not to the first URL that is still on screen.** `_on_urls_changed()` invalidates a completed `_probed_job_id`, but returns immediately while `_probing_job_id` is set. `_on_media_probed()` later accepts that old job unconditionally. A deterministic child delayed its result while the first URL changed from `old.invalid` to `new.invalid`; the dialog accepted the old metadata, `add_to_queue()` skipped the currently displayed first URL because a probe existed, and the only queued/started job was `old.invalid`. This silently downloads the wrong URL and drops the one the user submitted, which is Critical under `AGENTS.md` §9. The same incomplete state model has a second observable edge: pressing the still-enabled default **Add to queue** button while a probe is outstanding persists the first URL a second time, because `probe()` already added its job but `add_to_queue()` skips it only after `_probed_job_id` exists. Bind every result to the input generation/current first URL; invalidate and cancel or ignore an in-flight probe when that identity changes; and make add-during-probe preserve exactly one job per entered line. Audit start refusal, cancellation, failure, repeated probe, and appended-line siblings. Add deterministic delayed-result and outstanding-add tests. |
| `T016-R2` | **High** | **Yes** | **Closing the dialog can strand a worker and make the pool-of-one manager unusable.** The Close button connects directly to `reject()` and the dialog has no reject/close lifecycle that cancels `_probing_job_id`. A never-returning probe remained alive and `manager.is_idle` remained false two seconds after the dialog was rejected. The only cancel control was then hidden; every later Add-URL dialog can only receive “a session is already running” until the application exits. This fails the task's no-worker-behind cancellation criterion and breaks the core flow with no in-app workaround. Closing/rejecting an active dialog must initiate the same non-blocking cancellation ownership as the explicit button, and a test must close a genuinely non-returning child and prove the manager becomes idle and a later dialog can probe. |
| `T016-R3` | **High** | **Yes** | **The new widget performs synchronous SQLite work on the GUI thread despite the unqualified no-disk-wait invariant.** `JobSink.next_queue_position()` and `add()` are synchronous, and both `probe()` and `add_to_queue()` call them directly from button slots—once per URL and once per committed row. With a real `JobRepository` and another connection holding SQLite's writer lock, a 300 ms busy timeout made `add_to_queue()` hold the GUI thread for **0.302 s** and then raise `OperationalError`. A large pasted batch also performs an unbounded number of separate queries and commits in one interaction. This violates `NFR-001` and Architecture §8, and persistence failure is not surfaced through the dialog. Move queue persistence off the GUI thread or obtain an accepted architecture change; retain the required persist-before-close ordering, and surface write failure without closing or losing the user's input. The evidence must exercise the concrete repository under deterministic contention, not only a zero-latency fake. |
| `T016-R4` | **Medium** | **Yes** | **The repaired tab-order test is independent but still filters out focusable controls, so the full keyboard-order acceptance criterion remains ungated and the implemented order contradicts the dialog's own prose.** `titleValue`, `uploaderValue`, `durationValue`, `kindValue`, `selectorValue`, and `statusMessage` all acquire `StrongFocus` from `TextBrowserInteraction`, but `focus_chain()` names only the editor, buttons, and preset. The test skips every Qt focus-chain node outside that declared subset. The exact-head chain therefore runs `url → probe → cancel → preset → add → close → title → uploader → duration → kind → selector → status`, although `_set_tab_order()` says users read the result before choosing a preset and acting. Transcribe and assert the complete set and order of named keyboard-focusable widgets, including the selectable result/status fields; do not filter undeclared focusable nodes out of the observation. |
| `T016-R5` | **Medium** | **Yes** | **A failed thumbnail request leaves the dialog claiming “Loading thumbnail…” forever.** `ThumbnailLoader` has only a successful-byte callback; `NetworkThumbnailLoader.finished()` calls it only on `NoError`, while `_load_thumbnail()` sets the loading text before the request and has no failure transition. A real `QNetworkAccessManager` request for a nonexistent local image finished, `_reply` became `None`, and the label still read `Loading thumbnail…`. This is a common expired/offline-thumbnail path and an observable false state. Give the loader an explicit failure/completion result and render a truthful text state such as unavailable/no thumbnail; test the shipping loader's failure path rather than a loader that can only succeed. |
| `T016-R6` | **Medium** | **Yes** | **Extractor/site text is left in `QLabel.AutoText`, so HTML-looking titles and uploader names are interpreted as rich text instead of shown as data.** With the title `<b>VISIBLE</b>`, the exact-head title label retained that source string but rendered it as markup: its auto-text width was 47 px versus 90 px when forced to plain text, consuming the tags. `REQ-002` requires the title supplied by the probe to be shown, not interpreted as UI markup. Set `Qt.PlainText` on every label that receives extractor, site, URL, or failure text, and assert rendered/plain-text semantics with markup-shaped fixture values rather than reading `QLabel.text()` back—the latter returns the input and misses the display defect. |
| `T016-R7` | **Low** | **No** | **The replacement manager refusal test does not cover “every status that is not an entry point” as its docstring and handoff claim.** Its parameter list omits `PROBING`, `COMPLETED`, and `CANCELLED`. Production `_ENTRY_STATUS` is correct, so this is test strength rather than a behavior finding. **Owner/target:** Implementer, T-016 correction test hardening; enumerate the complement of the two allowed statuses independently of `_ENTRY_STATUS`. |
| `T016-R8` | **Low** | **No** | **The repository's current-truth handoff is stale after the merge and CI fixes.** `TASKS.md` still gives `eaa5b50` and `phase1-add-url-dialog`, records only the scoped mypy gates, and says the full suite has 1230 passes; the reviewed merged boundary is `098ba3f..33ebd11`, bare mypy covers 69 files, and the exact-head suite has 1239 passes. `STATUS.md` likewise retains the old branch/base and says “No widget touches any of it yet” shortly before saying T-016's widget does. The scratchpad handoff is accurate but is not canonical current truth. **Owner/target:** Implementer, T-016 correction record. |

### What is established

- **`ARC-004` is implemented correctly.** `_ENTRY_STATUS` has exactly `QUEUED → PROBING` and
  `READY → RUNNING`; a probe from `READY` is refused before persistence; and a READY download
  retains the attempt's existing `started_at`. The focused manager tests passed.
- **The injected thumbnail seam is honest for the success half of `REQ-002`.** The committed
  tests decode real image bytes into a real pixmap. Independently, the shipping
  `NetworkThumbnailLoader` returned from `load()` in 0.0226 s and delivered all 213,475 bytes
  through `QNetworkAccessManager`. R5 is the omitted failure half, not a claim that injection
  itself hides a broken successful implementation.
- **The tab expectation is no longer derived from production order.** Reversing two declared
  controls is meaningfully gated now. R4 concerns the focusable controls excluded from both
  sides, not the independence correction.
- **The mypy scope correction is real.** Bare Linux and Windows-platform checks each analysed
  all 69 configured files successfully. The two test-file errors caught by CI are corrected.
- **The Windows menu contract has the new item.** The three-dot spelling and expected UIA item
  are consistent, and the implementer-provided Windows desktop job passed all 20 tests.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check 098ba3f..33ebd11` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **84 files already formatted**. |
| `mypy src` | Passed: no issues in **33 source files**. |
| Configured `mypy` | Passed: no issues in **69 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **69 source files**. |
| Focused add-dialog and manager suite | Passed: **97 passed in 48.86 s**. |
| Canonical bare `pytest`, exact head | Passed: **1239 passed, 11 skipped, 1 deselected in 72.17 s**. |
| Implementer-provided CI at `33ebd11` | Run `30320408833` green: Ubuntu **1239 passed, 11 skipped, 1 deselected**; Windows **1228 passed, 20 skipped, 21 deselected**; Windows desktop **20 passed, 1249 deselected**; both frozen jobs succeeded. |
| Delayed stale-result probe | Failed as intended: after the first input changed, the old result was accepted and Add queued/started only the old URL. |
| Add-while-probing probe | Failed as intended: one entered URL produced two persisted jobs with the same URL. |
| Close-while-probing probe | Failed as intended: a never-returning child and the manager session remained alive two seconds after rejection. |
| Concrete SQLite contention probe | Failed as intended: `add_to_queue()` blocked **0.302 s** on the GUI thread, then raised `OperationalError`. |
| Complete focus-chain inspection | Failed the stated order: all six selectable result/status labels were focusable but appeared after Close and were filtered from the committed assertion. |
| Shipping thumbnail success/failure probes | Success returned immediately and delivered the real icon bytes; a completed error left the UI at `Loading thumbnail…`. |
| Plain-text display probe | Failed: `<b>VISIBLE</b>` was interpreted under `AutoText` (47 px) rather than displayed literally (90 px under `PlainText`). |

The reviewer probes lived only in a temporary archive and did not alter repository source or
tests.

### Readiness and budget

`T-016` is **Changes requested**. Critical `T016-R1`, High `T016-R2/R3`, and blocking Medium
`T016-R4/R5/R6` must be corrected and independently verified. This is the initial comprehensive
review; one focused correction re-review remains available for Medium-or-lower findings, while
the Critical and High findings continue under `AGENTS.md` §9 until resolved.

## 2026-07-27 — T-016 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-016` — Add-URL dialog with probe results
**Correction base:** `a9317362c043825a79a85d3fde85be4609e714cd`
**Head:** `162f2860e02d3fe7daf2c9523d9de8fd214b82e0`
**Correction commits:** `4e1bf64`, `5ba0ea3`, and `8bde969`
**Excluded commits in the range:** `14e63ec` preserves the initial review above; `162f286`
records the unrelated `T-056` Windows survival-check intermittent and changes no reviewed source
or test
**Repository state at inspection:** clean `main`, in sync with `origin/main`; source and tests
were inspected and run from a clean `git archive 162f286`
**Platforms verified:** Linux locally; Windows from the implementer-provided GitHub Actions run
`30324097829` at code head `8bde969`
**Verdict:** **Changes requested**

### Finding disposition

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T016-R1` | **Critical** | **Yes** | **Open — the result-arrival guard is now real, but the asynchronous save creates an earlier wrong-URL window.** `probe()` publishes `_probe` and submits the row before the session starts. The URL editor remains enabled while `_saving`, and `_discard_probe()` can cancel only when `probe.started` is true. If the first line changes while SQLite is still writing, `_on_probe_saved()` records the superseded URL and returns without starting or cancelling it. Under a real held SQLite writer lock, changing `old.invalid/unwanted` to `new.invalid/wanted` left the old row durably `QUEUED`; adding afterward left **both** old and new rows queued. The UI still displayed only the new URL. That can later download the URL the user replaced, so the Critical consequence remains. The multiplicity sibling is also still wrong: `_Persisted.by_url` is keyed by URL text and `fresh` excludes every occurrence whose text is present. After probing the first of two identical entered lines, Add stored only one job although `split_urls()` and the acceptance criterion say two identical lines are two requested jobs. Cover the pending-save generation, ensure a superseded saved probe cannot remain a live queued job, and track entered occurrences rather than URL membership. Add delayed-save edit and probe-then-duplicate-line tests. |
| `T016-R2` | **High** | **Yes** | **Open — `done()` handles a started worker, not a probe whose persistence callback can still start one.** During the pending save, `_Probe.started` is false and therefore `probe.in_flight` is false. Close is not disabled, so `done()` hides the dialog without superseding the probe. Releasing a deterministic deferred save afterward invoked `_on_probe_saved()` and called `manager.start()` for the hidden dialog: **one start, zero cancellations**. The committed close tests all wait until `probing_job_id` is non-`None`, which places them after synchronous fake persistence and misses this lifecycle stage. Closing must either be refused while a write owns the outcome or retire that outcome so its callback cannot start hidden work. Exercise Close/Escape/reject during a genuinely deferred probe save and prove a later dialog can still probe. |
| `T016-R3` | **High** | **Yes** | **Open — `ARC-005` is accepted, but the implementation serializes only appends.** `QueueWriter` owns `JobRepository.append()`, while `DownloadManager._save_and_announce()` still calls `JobRepository.update()` synchronously on the GUI thread for start, cancel, progress-stage, success, failure, and cleanup transitions. In the intended concrete flow, the writer committed the probe row and queued its GUI callback; another connection then held the writer lock. Processing that callback reached `DownloadManager.start()` and blocked the GUI event loop for **5.017 s**, then raised an **uncaught** `sqlite3.OperationalError` out of `QueueWriter._on_done()`. A direct non-running `DownloadManager.cancel()` reproduced the same synchronous write at **5.013 s**. The new writer also makes `close()` call `QThread.wait(5000)`; a submitted contended write held that GUI-thread call for **4.921 s**, contrary to the unqualified NFR and the event-driven shutdown rule already established by `T013-R2`. One persistence owner must serialize the manager's updates as well as appends, preserve persist-before-signal through callbacks, surface every failure, and expose an event-driven shutdown completion rather than waiting. The gate needs the integrated writer → dialog callback → real manager/repository path under contention, plus the contended-close sibling. |
| `T016-R4` | **Medium** | **Yes** | **Resolved.** The declared order contains all twelve controls. The set assertion observes every `TabFocus` widget in the dialog's own window without filtering by declared name, and the chain walk independently compares Qt's order with the hand transcription. Both focused assertions passed. |
| `T016-R5` | **Medium** | **Yes** | **Resolved.** `ThumbnailLoader` reports `bytes | None`; the dialog renders `None` and undecodable bytes as `Thumbnail unavailable`; and the shipping `QNetworkAccessManager` implementation is exercised against both a missing local file and a readable one. Both focused tests passed. |
| `T016-R6` | **Medium** | **Yes** | **Resolved.** Every foreign-text label is set to `Qt.PlainText`. The markup-shaped title proof uses the same explicitly sized widget, asserts equal grab sizes, demonstrates that RichText renders differently, then restores PlainText and reproduces the shipped pixels. It passed locally, and the implementer-provided Windows desktop job passed the final hardened form. |
| `T016-R7` | **Low** | **No** | **Resolved.** The two allowed statuses are independently transcribed, their complement is derived over the complete `JobStatus` enum, and a separate assertion compares the transcription with `_ENTRY_STATUS`. The previously omitted `PROBING`, `COMPLETED`, and `CANCELLED` cases are collected and passed. |
| `T016-R8` | **Low** | **No** | **Resolved.** The stale branch/base, mypy scope, suite evidence, and “no widget” contradiction are corrected in current-truth records. This review records the exact correction head separately from the initial implementation boundary. |

### What the correction establishes

- A late `media_probed` signal for a retired probe is refused at the arrival point. Keeping the
  superseded `_Probe` record makes that identity check reachable, and changing the first line
  after the worker starts cancels the session and leaves its job `CANCELLED`.
- Add is disabled and defensively refused while a worker probe is in flight. The original
  add-while-running duplicate edge is closed; R1 now concerns the unmodelled persistence stage
  and duplicate input occurrences.
- A started never-returning worker is cancelled through `done()` for reject, visible-window
  close, and direct done routes. R2 now concerns the callback that can create the worker only
  after the dialog has closed.
- `JobRepository.append()` allocates a batch's positions and inserts it atomically; a second
  batch continues after the first. `QueueWriter` opens and closes its connection on its own
  thread with `check_same_thread=True`, and returns append success/failure on the GUI thread.
  R3 concerns the unconverted manager writes and blocking writer shutdown, not those mechanics.
- `T-056` remains an explicitly open, unrelated intermittent. This range changes no
  `process_tree.py` behavior; the canonical Linux suite passed its survival check.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check a931736..162f286` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **85 files already formatted**. |
| `mypy src` | Passed: no issues in **34 source files**. |
| Configured `mypy` | Passed: no issues in **70 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **70 source files**. |
| Focused add-dialog, append, and refusal suite | Passed: **66 passed in 22.26 s**. |
| Canonical bare `pytest`, exact head | Passed: **1267 passed, 11 skipped, 1 deselected in 79.92 s**. |
| Implementer-provided CI at code head `8bde969` | Run `30324097829` green: Ubuntu **1267 passed, 11 skipped, 1 deselected**; Windows **1256 passed, 20 skipped**; Windows desktop **20 passed**; both frozen jobs succeeded. `162f286` changes `ai/TASKS.md` only. |
| Edit during concrete contended probe save | Failed the correction as intended: after the lock was released, the replaced old URL was durably `QUEUED`; adding the displayed new URL left both queued. |
| Duplicate occurrence after probe | Failed the correction as intended: two identical entered lines produced one stored row after the first occurrence had been probed. |
| Close during deferred probe save | Failed the correction as intended: the hidden dialog's completion callback started the probe and issued no cancellation. |
| Integrated concrete persistence path | Failed the correction as intended: writer callback → `DownloadManager.start()` → synchronous repository update blocked event processing **5.017 s** and raised an uncaught `OperationalError`. |
| Manager cancel sibling | Failed the correction as intended: cancelling a non-running queued job blocked **5.013 s** and raised `OperationalError` under the same real lock. |
| Writer shutdown sibling | Failed the correction as intended: `QueueWriter.close()` blocked **4.921 s** waiting for a contended write. |

The first canonical-suite attempt is excluded from evidence: the sandbox denied facilities used
by the process/IPC integration tests. The same exact archive passed when run with its normal
local-process and IPC access. Reviewer probes lived only in temporary archives and did not alter
repository source or tests.

### Readiness and review budget

`T016-R4` through `T016-R8` are independently resolved. Critical `T016-R1` and High
`T016-R2/R3` remain open, so `T-016` remains **Changes requested**.

This was the ordinary focused correction re-review. No further pass is available merely to
revisit the resolved Medium-or-lower findings. The remaining findings are Critical/High direct
continuations of the original blockers, so `AGENTS.md` §9 permits another focused correction and
verification pass without maintainer authorization; it must stay confined to R1, R2, R3 and
their correction diff.

## 2026-07-27 — T-016 second focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-016` — Add-URL dialog with probe results
**Correction base:** `162f2860e02d3fe7daf2c9523d9de8fd214b82e0`
**Head:** `c5dddae46bb82f18e655636ad9c26e5ca8eeeec4`
**Correction commit:** `c5dddae`
**Excluded content in the commit:** the preceding focused review record was committed verbatim
with the correction; that historical text is not implementation
**Repository state at inspection:** clean `main`, in sync with `origin/main`; source and tests
were inspected and run from a clean `git archive c5dddae`
**Platforms verified:** Linux locally; Windows from the implementer-provided GitHub Actions run
`30326537991`
**Verdict:** **Changes requested**

### Finding disposition

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T016-R1` | **Critical** | **Yes** | **Open, narrowed — the successful path is corrected, but withdrawal does not fail closed when its revision cannot be written.** The pending-save callback now cancels a superseded row, and occurrence counting correctly makes two identical entered lines two jobs. Under ordinary completion, the old row becomes `CANCELLED` and only the displayed URL remains live. But that cancellation is an asynchronous manager revision whose result the dialog does not own. With the append already durable and a real SQLite writer lock held through the revision timeout, `persistence_failed` fired while the dialog continued to say only “The URL changed. Probe again”; the write-through view said `CANCELLED`, but the concrete repository still held the replaced URL as `QUEUED`. A restart discards the view and exposes it as live work again — the original wrong-URL consequence. A Critical withdrawal cannot depend on a best-effort revision. Either make edit/close unable to retire a not-yet-finalized append, or keep the interaction pending and visibly retry/refuse progress until the cancellation is durable. Gate the failure path against the concrete repository and a fresh-store/restart read, not the in-memory view. |
| `T016-R2` | **High** | **Yes** | **Resolved.** `done()` retires every usable, not-ready probe, including one whose row is still being saved. Its callback sees `superseded` and never starts a worker. Reject, visible-window close, and direct done were exercised with genuinely deferred saves; all left the manager idle and a later dialog could probe. The cancellation-write failure above can leave a durable queued row, but it does not recreate R2's hidden worker or occupied pool and remains part of Critical R1. |
| `T016-R3` | **High** | **Yes** | **Open — every write is on the writer thread, but moving only `job_changed` into the callback does not preserve the ordering that synchronous persistence used to provide.** `QueueWriter.revise()`, `PersistentJobStore`, read-your-writes, `persistence_failed`, and event-driven `closed` all work as mechanisms. The write-through view, however, is not durable persistence. Under a held real lock, `DownloadManager.start()` started both the process and pump while the concrete row was still `QUEUED`; `_abort_start()` emitted `protocol_violation` and `job_failed` and ran queue cleanup while the row was still `QUEUED`; and `job_succeeded` observed the row still `RUNNING`, with only `job_changed` waiting until `COMPLETED` was durable. A failed revision can therefore announce success/failure or start work before later emitting `persistence_failed`. This directly regresses T-013's approved startup transaction, cleanup-before-persistence guard, and acceptance criterion that every transition is persisted before its corresponding UI signal. Keeping the ten call sites unchanged is the cause, not proof of equivalence: the old synchronous call sequenced all following effects. Make persistence completion gate worker construction, cleanup, and every companion signal (`progress` when it moves state, `media_probed`, `job_succeeded`, `job_failed`, and startup violation), with an explicit failure continuation that does not perform the success-side effect. Test the concrete repository's status at process/pump start, cleanup, and each companion signal under a held lock. |

### What is independently established

- `_Persisted` now tracks lists/counts per URL. After one occurrence is probed, the difference
  calculation creates a job for the second identical line; the regression test passed.
- A pending save retired by edit or close cannot start a worker. The normal successful
  cancellation ordering is append then revision on the same writer thread.
- `QueueWriter.submit()` and `revise()` share one receiver and connection with
  `check_same_thread=True`; manager reads see accepted revisions immediately through
  `PersistentJobStore`.
- A contended manager revision returns immediately, completes after the lock is released, and
  no exception escapes the Qt slot. A failed write emits `persistence_failed`.
- `QueueWriter.close()` returns immediately, drains prior writes, closes the connection on its
  owning thread, and emits `closed`; the former GUI-thread `QThread.wait()` is gone.
- `T016-R4` through `T016-R8` remain resolved. `T-056` remains separately open and this commit
  changes no process-survival helper.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check 162f286..c5dddae` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **86 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **71 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **71 source files**. |
| Full add-dialog and manager focused suite | Passed: **130 passed in 63.06 s**. |
| Canonical bare `pytest`, exact head | Passed: **1281 passed, 11 skipped, 1 deselected in 85.58 s**. |
| Implementer-provided CI at `c5dddae` | Run `30326537991` green: Ubuntu **1281 passed**; Windows **1270 passed, 20 skipped**; Windows desktop and both frozen jobs succeeded. |
| Failed pending-save withdrawal | Failed the correction as intended: `persistence_failed` arrived, the store view was `CANCELLED`, but the replaced URL remained durably `QUEUED` and the dialog displayed no persistence failure. |
| Start-side-effect ordering | Failed the correction as intended: both fake process start and pump start observed the concrete database still at `QUEUED`; only the write-through view held `PROBING`. |
| Startup-failure signal ordering | Failed the correction as intended: `protocol_violation` and `job_failed` each observed the concrete row at `QUEUED`; it became durably `FAILED` only after the lock was released. |
| Startup cleanup ordering | Failed the correction as intended: the cleanup queue's `close()` observed the concrete row at `QUEUED`, reopening the exact `T013-R3` mechanism that required durable failure before cleanup. |
| Success-signal ordering | Failed the correction as intended: `job_succeeded` observed the concrete row at `RUNNING`; `job_changed` arrived only after `COMPLETED` was durable. |

Reviewer probes lived only in the temporary exact-head archive and did not alter repository
source or tests.

### Readiness and review budget

`T016-R2` is independently resolved. Critical `T016-R1` and High `T016-R3` remain open, so
`T-016` remains **Changes requested**.

The remaining defects are direct Critical/High continuations and include a regression of the
approved High `T013-R3` guarantees. `AGENTS.md` §9 therefore permits another correction and
focused verification pass without maintainer authorization. It must remain confined to R1's
durable withdrawal and R3's persistence continuations; R2 and R4–R8 are settled.

## 2026-07-27 — T-016 third focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-016` — Add-URL dialog with probe results
**Correction base:** `c5dddae46bb82f18e655636ad9c26e5ca8eeeec4`
**Head:** `9c959ea`
**Correction commit:** `9c959ea`
**Excluded commit in the range:** `416c867` preserves the preceding reviewer record and changes
no reviewed source or tests
**Repository state at inspection:** `main` at `9c959ea`, in sync with `origin/main`; the shared
checkout had pre-existing uncommitted edits in `AGENTS.md`, `ai/DECISIONS.md`, and
`ai/PROMPTS.md`, so source and tests were inspected and run from a clean
`git archive 9c959ea`. Those three edits were neither read as part of the boundary nor changed.
**Platforms verified:** Linux locally; Windows from the implementer-provided GitHub Actions run
`30329071900`
**Verdict:** **Changes requested**

### Finding disposition

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T016-R1` | **Critical** | **Yes** | **Open — the withdrawal is recorded, but it is still not owned across the operation that creates it or across overlapping revisions.** First, `done()` tests `_withdrawing` before retiring the current probe. Retiring a started probe then calls `_withdraw()`, but execution continues directly to `super().done()`. An exact-head probe showed the dialog becoming invisible while `withdrawing` was still populated and no cancellation was durable; an immediate crash/restart can therefore expose the disowned URL as live work. Second, cancelling while `start()` is reserved queues `CANCELLED`, but the earlier `PROBING` completion still runs its unconditional `_spawn` callback. A deterministic write-through store completed `PROBING` then `CANCELLED`; the durable record ended `CANCELLED`, yet `_spawn` ran for that job. That is the original Critical consequence in a stronger form: work for the replaced URL can start after its withdrawal is accepted. Third, the store rollback is correct for one failed revision but not two overlapping failures. If revision A is followed by B, A's failure leaves B in the view; B's failure then restores A as its `previous` record even though A also failed. The concrete probe ended with SQLite at `QUEUED` and `PersistentJobStore.get()` at `PROBING`. Model the accepted revisions as an ordered per-job lifecycle, invalidate a reserved start when cancel wins, refuse the first Close after it creates a withdrawal, and roll back to the last actually durable record rather than a failed predecessor. Gate first-close visibility, start/cancel callback ordering, and two consecutive failed revisions. |
| `T016-R3` | **High** | **Yes** | **Open — a callback gates its own `then`, but the manager still does not sequence overlapping continuations or own a reserved start as lifecycle state.** `_reserved` prevents a second admission, but `is_idle` and `active_job_ids()` ignore it, `shutdown()` cancels only `_sessions`, and `_spawn()` does not re-check shutdown or supersession. At exact head, `is_idle` was true with a reserved start; shutdown could announce `idle`; releasing the write afterward still ran `_spawn`. Other continuations have the same hole. A second progress message observed the write-through `RUNNING` value and emitted immediately while the durable row was still `PROBING`. `_abort_start()` passes the same `announce_and_unwind` function as both `then` and `otherwise`, so a failed `FAILED` write still emitted `protocol_violation` and `job_failed`; both observers read durable `PROBING`, contradicting the new docstring's “success-side effect does not run” guarantee. Finally, a failed initial `PROBING` write discards the reservation in the manager, but the dialog has already set `probe.started = True` and ignores `persistence_failed` unless that id is in `_withdrawing`; it remains permanently at “Probing …” with no worker. Sequence per-job writes and effects rather than treating the write-through view as completion; make reserved starts cancellable and part of idle/shutdown; separate mandatory failure cleanup from signals that require durable `FAILED`; and give the probe caller an asynchronous start-rejection path. Gate two progress messages behind one held stage write, failed startup-failure persistence, start-write rejection in the real dialog, and shutdown/cancel while start is reserved. Re-derive the affected `T013-R2/R3/R4` guarantees against that lifecycle. The accepted `ARC-005` amendment also still says “only the announcement moved” and “callers unchanged,” the equivalence this correction itself rejects; the Planner must append an accurate amendment before eventual approval. |

### What the correction establishes

- A single start transition gates initial process and pump construction until that transition
  succeeds. Under a held concrete row, no session appeared while SQLite still said `QUEUED`.
- A single failed revision removes its own newest view entry, and a failed withdrawal is surfaced
  in words, blocks Add, remains retryable, and can end durably `CANCELLED` for a fresh reader.
  R1 concerns the first-close path and overlapping revision chain, not those single-write
  mechanics.
- On an isolated successful transition, `media_probed`, `job_succeeded`, `job_failed`, startup
  violation, and the first state-moving `progress` are placed in the persistence continuation.
- A second start is refused while the first start is reserved. R3 concerns cancellation,
  shutdown, idle reporting, and later events while that reservation exists.
- The revised spawn-failure delivery preserves the successful-persistence T-013 assertions: the
  failure becomes durable and is reported through manager signals instead of being raised back
  through `start()`.
- `T016-R2` and `T016-R4` through `T016-R8` remain resolved. This pass did not reopen their
  settled surfaces.

### Independent verification

| Check | Result |
|---|---|
| `git diff --check c5dddae..9c959ea` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **86 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. Its first invocation was run concurrently with the other mypy scopes and hit mypy 2.3.0's cache-related internal error; the immediate standalone rerun passed and is the result reported here. |
| Configured `mypy` | Passed: no issues in **71 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **71 source files**. |
| Full add-dialog and manager focused suite | Passed: **134 passed in 67.87 s**. |
| Canonical bare `pytest`, exact head | Passed: **1285 passed, 11 skipped, 1 deselected in 90.28 s**. |
| Implementer-provided CI at `9c959ea` | Run `30329071900` reported green on all five jobs. |
| First Close while a start was pending | Failed the correction as intended: `withdrawing` contained the job, but the dialog was already invisible before the cancellation callback. |
| Cancel during a reserved start | Failed the correction as intended: durable writes completed in `PROBING`, `CANCELLED` order, and the earlier completion still invoked `_spawn`. |
| Reserved-start shutdown | Failed the correction as intended: `is_idle` was true with `_reserved` populated; the pending success continuation remained able to spawn after shutdown. |
| Consecutive failed revisions | Failed the correction as intended: both writes failed, SQLite remained `QUEUED`, and the store view restored failed predecessor `PROBING`. |
| Overlapping progress | Failed the correction as intended: the second message emitted while the durable record remained `PROBING`; only the write-through view said `RUNNING`. |
| Failed probe-start transition | Failed the correction as intended: the manager rejected the write, but the dialog retained `probing_job_id` and still displayed “Probing …”. |
| Failed startup-failure transition | Failed the correction as intended: the `FAILED` write failed, yet `job_failed` and `protocol_violation` both emitted while the durable record remained `PROBING`. |

All seven reviewer probes ran only in the temporary exact-head archive and were removed before
the submitted and canonical gates. They did not alter repository source or committed tests.

### Readiness and review budget

Critical `T016-R1` and High `T016-R3` remain open, so `T-016` remains **Changes requested**.

These are direct continuations of the existing serious findings: R1 still permits wrong,
withdrawn work to run, and R3 still breaks the persistence and shutdown ordering approved under
T-013. `AGENTS.md` §9 permits another focused correction and independent verification pass
without maintainer authorization. It must stay on durable withdrawal, ordered per-job
continuations, and the affected T-013 lifecycle guarantees; R2 and R4–R8 remain settled.
