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

## 2026-07-28 — T-016 fourth correction and T-017 initial review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-016`, `T-017`
**Base:** `6ad20f6`  **Head:** `6ce195a`
**Implementation commits:** `68c978d` (`T-016`), `6ce195a` (`T-017`)
**Later commits excluded from the implementation boundary:** `63f9e69`, `4a06e92`, `257b7c7`,
`9c92c32`, and coordination-only `2831973`
**Platforms verified:** Linux locally; Windows type analysis only
**Verdict by task:** `T-016` **Approved**; `T-017` **Changes requested**

### T-016 finding dispositions

| ID | Severity | Blocks approval | Disposition and evidence |
|---|---|---:|---|
| `T016-R1` | **Critical** | **Yes** | **Resolved.** A reserved start is now an owned `_PendingStart` that cancellation can withdraw; `_spawn()` re-checks the reservation and shutdown before constructing anything. The first Close that creates a withdrawal remains visible and completes itself only after durable `CANCELLED`. `PersistentJobStore` retains only in-flight revisions and falls back to the concrete repository after they settle, so two failed revisions cannot restore a failed predecessor. The committed regression tests reproduce all three exact-head probes from the preceding review. |
| `T016-R3` | **High** | **Yes** | **Resolved.** `_Chain` sequences each job's writes and dependent effects, computes transitions when their turn arrives, and orders non-moving progress behind a pending state transition. Reservations participate in `is_idle`, `active_job_ids()`, shutdown, and the tick gate. Startup cleanup is separated from announcements that require durable `FAILED`, and `start_rejected` gives the dialog the asynchronous half of `start()`'s outcome. The 2026-07-28 amendment to `ARC-005` explicitly retracts the false “only the announcement moved” equivalence. |

The two changed `active_job_ids() == ()` assertions encoded the defect rather than protecting a
useful guarantee. They now assert that the reserved job is visible and the manager is not idle;
`test_no_worker_exists_while_the_row_still_says_queued` independently checks `_sessions` and was
strengthened to assert both worker absence and reservation ownership. The judgment is accepted.
`T016-R2` and `T016-R4` through `T016-R8` remain resolved.

### T-017 findings

| ID | Severity | Blocks approval | Finding and evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T017-R1` | **Medium** | **Yes** | **The promised maximum repaint rate is not enforced when progress crosses job-status changes.** `_on_job_changed()` calls `_draw_pending()` immediately. A deterministic probe with a 100 ms interval interleaved three progress messages with `RUNNING`, `POST_PROCESSING`, and `COMPLETED`; `_show_progress()` ran three times before the first timer interval elapsed. The committed burst test calls `_on_progress()` directly and therefore never exercises the manager's `job_changed` signal that bypasses the rate limit. This leaves T-017's explicit coalescing acceptance criterion unmet. | Keep state words responsive without flushing pending progress outside the rate limiter; clear obsolete pending progress at a terminal transition if needed. Add an interleaved `progress`/`job_changed` test that counts renders inside one interval. | **Open** |
| `T017-R2` | **Medium** | **Yes** | **An indeterminate progress bar keeps a false accessible description after it becomes determinate.** `_show_totals()` sets “Total size unknown; progress cannot be measured” when `total` is absent, but the determinate branch never clears or replaces it. The reviewer drove unknown total followed by `5/10`; the bar became 50% with range `0..100` while its accessible description still said progress could not be measured. This is a common progress transition and gives screen-reader users contradictory state under `NFR-005`. | Clear the indeterminate description, or replace it with a truthful determinate description, whenever `total` becomes known. Gate both unknown→known and known→unknown transitions. | **Open** |

### Independent checks and probes

| Check | Result |
|---|---|
| `git diff --check 6ad20f6..6ce195a` | Passed. |
| `ruff check .` | Passed: “All checks passed!” |
| `ruff format --check .` | Passed: **87 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **72 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **72 source files**. |
| Focused manager/add-dialog/job-detail run | **166 passed**; ten localhost-server cases were blocked by the filesystem/network sandbox, not by assertions. |
| Full default suite with localhost permission | **1334 passed, 11 skipped, 1 deselected in 75.58 s**. |
| Repaint-rate probe | Three `_show_progress()` calls occurred inside one 100 ms interval when status changes were interleaved. |
| Accessible-description probe | After unknown→known total, the bar was determinate at 50% but retained “progress cannot be measured.” |

### Readiness and review budget

`T-016` is **Approved at `6ce195a`**. This resolves the remaining Critical and High findings;
no open blocker remains on that task.

`T-017` is **Changes requested**. Both findings are blocking Medium acceptance/correctness gaps.
The ordinary budget has its one focused correction re-review remaining; that pass should verify
these two findings and inspect only their correction diff for regressions.

## 2026-07-28 — T-057 and T-058 independent review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-057`, `T-058`
**Base:** `6ce195a`  **Head:** `4a06e92`
**Implementation commits:** `63f9e69` (`T-057`), `4a06e92` (`T-058`)
**Platforms verified:** Linux locally; Windows type analysis
**Verdict by task:** `T-057` **Approved**; `T-058` **Changes requested**

### Findings

| ID | Severity | Blocks approval | Finding and evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T058-R1` | **Medium** | **Yes** | **The count was not moved to one canonical home, contrary to the task's acceptance criterion and evidence.** At exact head `4a06e92`, `ai/STATUS.md` states “ten of ten” at lines 109 and 128; the latter immediately claims the count is stated only in `ai/TESTING.md` §12. T-058's evidence says `STATUS.md` no longer states the count at all. Coordination commit `2831973` adds a third numeric statement rather than repairing the contradiction. The task exists because duplicated counts drifted before, so retaining three copies is the same defect class, not cosmetic wording. | Leave the number only in `ai/TESTING.md` §12. Make every `STATUS.md` reference point there without restating it, and correct T-058's evidence only after the single-home claim is true. | **Open** |

### Review judgments

- The pinned local yt-dlp is **2026.07.04**, matching `pyproject.toml`. Its own
  `YoutubeDL.process_video_result()` still writes `_has_drm` using the `any` rule and excludes
  `has_drm == "maybe"`.
- `format_has_drm()` and the `has_drm()` fallback match that upstream rule. The offline canary
  drives yt-dlp's code rather than source text, records attempted DNS separately from yt-dlp's
  suppressed exception path, and fails if `_has_drm` stops being written.
- The changed mixed-format assertion is correct. The old expectation described only the fallback
  and contradicted the `_has_drm` branch every processed production info dict takes.
- `ai/TESTING.md` §7's DRM requirement text is unchanged, and §12 honestly names the two limits:
  no protected fixture under `REQ-EXCL-001`, and `_has_drm`'s absent/`None` ambiguity.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 6ce195a..4a06e92` | Passed. |
| DRM-focused adapter/errors/worker/UI suite | **196 passed in 3.97 s**. |
| Pinned upstream probe | Version **2026.07.04**; `_has_drm` assignment and `any` computation confirmed from the installed code. |
| Combined lint, type and default-suite gates | Passed; see the preceding review entry for exact counts. |

### Readiness and review budget

`T-057` is **Approved at `4a06e92`** with no findings.

`T-058` is **Changes requested** on blocking Medium `T058-R1`. Its one focused correction
re-review remains in the ordinary budget.

## 2026-07-28 — T-056 and T-054 independent review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-056`, `T-054`
**Base:** `4a06e92`  **Head:** `9c92c32`
**Implementation commits:** `257b7c7` (`T-056`), `9c92c32` (`T-054`)
**Platforms verified:** Linux locally; Windows branch type-checked but not executed
**Verdict by task:** `T-056` **Blocked**; `T-054` **Approved with follow-ups**

### Findings

| ID | Severity | Blocks approval | Finding and evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T054-R1` | **Low** | **No** | **The filing is correct, but its mechanical evidence overclaims.** Every task now sits under a section compatible with its `Status:` line. However, T-054 says a line-multiset comparison differs only by one separator; comparing `257b7c7..9c92c32` also shows the new T-054 entry/evidence, removal of the former In Review note, and extra blank lines. `git diff --check` reports a new blank line at EOF. None of those changes rewords another task's status, finding, or evidence, so the acceptance behavior holds; the stated proof does not. | Correct the evidence to state the exclusions used for the permutation check and remove the trailing blank line. **Owner/target:** Documentation Maintainer, `T-054` record correction. | **Open, non-blocking follow-up** |

### Review judgments

- On Windows, `psutil.Process.wait(timeout=0)` asks exit status through the process handle and is
  the correct distinction between a running process and a terminated-but-visible one. Keeping
  POSIX on `status() != STATUS_ZOMBIE` avoids reaping a child with `waitpid` and stealing the exit
  status from `multiprocessing`.
- The helper's stated error direction is correct: the prior implementation could return false
  alive on Windows, while `NoSuchProcess`, `ZombieProcess`, or `STATUS_ZOMBIE` could not turn an
  actually running process into false dead; `AccessDenied` failed loudly.
- The added killed-but-unwaited process exercises the right Windows shape. The Linux run can
  exercise only the already-correct zombie branch, so it does not discharge the Windows criterion.
- T-054's section/status audit found no remaining status contradiction. The two phase-heading
  questions it left out are genuinely outside its status-filing scope.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 4a06e92..9c92c32` | Failed only on `ai/TASKS.md`: new blank line at EOF (`T054-R1`). |
| Linux survival-helper test | **1 passed in 0.10 s**. |
| Configured `mypy --platform win32` | Passed: no issues in **72 source/test files**. |
| Full default suite | **1334 passed, 11 skipped, 1 deselected in 75.58 s**. |
| Windows runtime/mutation | **Not run; unavailable until the branch is pushed and the Windows job executes.** |

### Readiness and review budget

`T-056` is **Blocked**, not Changes requested: the implementation is ready for the external
Windows evidence its acceptance criterion requires, but approval cannot be produced on Linux.
The Windows job must run the killed-but-unwaited case and kill the mutation that disables the
`win32` branch. If it does, a focused evidence verification is sufficient.

`T-054` is **Approved with follow-ups at `9c92c32`**. `T054-R1` is non-blocking and has an owner
and target above.

### Coordination-only commit `2831973`

The commit changes no reviewed source or tests and preserves all three implementation boundaries.
It correctly records the ranges, T-056's Windows blocker, and the new `T-036 → T-037` critical
path. Two current-truth corrections remain:

- `T058-R1` continues and is stronger at `2831973`: `STATUS.md` now spells out “ten of ten” three
  times while its Notes section says the file does not repeat the count.
- `STATUS.md` still summarizes T-016 as “Changes requested, first correction batch returned”
  immediately after adding the fourth-correction summary. This does not change readiness, but the
  stale bullet should be updated when the blocking review findings are reflected.

## 2026-07-28 — T-017, T-058 and T-054 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Review boundary supplied:** `9c92c32` → `e66f34d`
**Correction commit:** `e66f34d` (parent `2831973`)
**Focused scope:** `T017-R1`, `T017-R2`, `T058-R1`, `T054-R1`, and regressions in their
correction diff
**Platforms verified:** Linux locally; Windows type analysis
**Verdict by task:** `T-017` **Blocked**; `T-058` **Blocked**; `T-054` **Approved**

### Finding dispositions

| ID | Severity | Blocks approval | Focused re-review evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T017-R1` | **Medium** | **Yes** | `_on_job_changed()` no longer calls `_draw_pending()`. An interleaved progress/status test observes the promised quantity, `renders`, and stays at zero inside the interval; a terminal transition clears pending progress and stops the timer. Independently restoring the unmetered draw made the rate test fail with two renders, and independently retaining the terminal message made the terminal test fail. | None. | **Resolved** |
| `T017-R2` | **Medium** | **Yes** | **The correction covers the two `_show_totals()` branches but not the third route that changes the bar.** After rendering `5/10`, `_on_job_changed(..., COMPLETED)` reaches `_refresh()`, which changes the visible bar from 50 to 100 at `job_detail.py:478-480` without changing its accessible description. The deterministic probe read range `0..100`, value `100`, description `"50 percent of 10 B downloaded"`. A job loaded completed with no stored total likewise becomes a determinate 100% bar while retaining the indeterminate “cannot be measured” description. This is the same sighted/screen-reader contradiction as the original finding, through a sibling call path the correction did not gate. | Make the completed override describe 100% truthfully, and gate completion from both a partial determinate bar and an unknown-total bar. Audit every path that changes the bar's range/value, not only `_show_totals()`. | **Open** |
| `T017-R3` | **Low** | **No** | **The new immediate-state assertion proves only the pre-first-render case.** Its view still has `_displayed is None`, so `_refresh()` writes the nonterminal word. After one progress message has rendered, `_displayed` is non-`None`; a deterministic `RUNNING` → `POST_PROCESSING` status change then left “Downloading video” until the timer-rendered progress arrived. Terminal words are immediate and the delay is bounded by the stated 100 ms interval, so this does not reopen the repaint-rate acceptance criterion, but the source and task evidence overstate what the test proves. | Either state the narrower guarantee—terminal state words are immediate and nonterminal stage changes follow the coalesced progress render—or strengthen the implementation and test after a prior render. **Owner/target:** Implementer, next authorized T-017 correction; otherwise Documentation Maintainer before T-017 closes. | **Open, non-blocking** |
| `T058-R1` | **Medium** | **Yes** | `ai/STATUS.md` no longer states the mandatory-area count or denominator, so that half is corrected. **The claimed single home is still false inside `ai/TESTING.md`.** Line 142 says “All ten are back in the default run”; line 350 says “Of §7's ten mandatory areas ten are now covered.” Both are numeric claims over the same enumerated §7 set and must change together if that set changes. The handoff's claim that line 350 is the only remaining occurrence is disproved by `rg -n '\\b(ten|nine|eight)\\b' ai/STATUS.md ai/TESTING.md`. This is a direct continuation of the duplicated-count defect, not an adjacent documentation observation. | Keep the numeric mandatory-area count/denominator in §12 only. Rewrite §7's execution note without restating the size of the set, then rerun a search broad enough to find word-form numbers rather than only “ten of ten”/“of ten mandatory.” | **Open** |
| `T054-R1` | **Low** | **No** | The evidence now says the permutation comparison covered the relocation snapshot and explicitly names the later status/evidence/note edits it excluded. `git diff --check 9c92c32..e66f34d` is clean, and `ai/TASKS.md` ends with one newline. The six affected task entries sit under sections compatible with their status lines. | None. | **Resolved** |

### Review judgments

- `renders` is the right public observation for `REPAINT_INTERVAL_MS`; the correction test now
  measures progress-field redraws rather than the absence of a displayed message.
- Dropping pending progress at a terminal transition is correct. Deferring it would let an older
  worker report overwrite the newer terminal state on the next tick.
- The determinate and indeterminate `_show_totals()` descriptions are individually correct, and
  both branch-removal mutations are killed. The remaining T017-R2 defect is `_refresh()` changing
  the same control outside those branches.
- `ai/STATUS.md` now points to `ai/TESTING.md` §12 without restating its numeric coverage result.
  The remaining T058-R1 duplication is within `TESTING.md` itself.
- T-016 and T-057 are correctly filed under `## Complete`; T-056 is correctly filed under
  `## Blocked`; T-017 and T-058 are correctly filed under `## In Review` at the reviewed head.
  This re-review does not revisit T-056's untouched Windows-only implementation or evidence.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 9c92c32..e66f34d` | Passed. |
| Corrected T-017 tests | **3 passed, 35 deselected**. |
| Four isolated mutations named in T-017's evidence | **All four killed**: unmetered status draw, retained terminal message, missing determinate description, and missing indeterminate description each failed its named test. |
| Completion accessible-description probe | Visible bar `0..100`, value `100`; accessible description remained `"50 percent of 10 B downloaded"`. |
| Post-render status-word probe | `RUNNING` → `POST_PROCESSING` left `"Downloading video"` until the coalesced progress render. |
| Coverage-count search | Found numeric §7 coverage statements at `ai/TESTING.md:142` and `ai/TESTING.md:350`; none in `ai/STATUS.md`. |
| `ruff check .` | Passed. |
| `ruff format --check .` | **87 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **72 source/test files**. |
| Configured `mypy --platform win32` | Passed: no issues in **72 source/test files**. |
| Full default suite with localhost/cache permission | **1337 passed, 11 skipped, 1 deselected in 76.24 s**. |

### Readiness and review budget

`T017-R1` and `T054-R1` are **Resolved**. T-054 is therefore **Approved at `e66f34d`**.

`T017-R2` and `T058-R1` remain blocking Medium findings. This was the one focused correction
re-review allowed by the ordinary convergence budget, so `T-017` and `T-058` are now **Blocked
pending maintainer direction**, not automatically returned for a third pass. Per `AGENTS.md`
§10, the maintainer must choose one of: authorize another focused pass, accept the documented
risk, change scope, or carry either correction into a named follow-up task. `T017-R3` is
non-blocking and does not itself consume or require another pass.

`T-056` remains **Blocked** on its Windows runtime/mutation evidence. It was untouched by
`e66f34d` and is outside this focused re-review.

## 2026-07-28 — T-017 and T-058 authorized third review pass

**Reviewer:** Codex (Reviewer)
**Base:** `e66f34d`  **Head:** `b3e156c`
**Correction commit:** `b3e156c`
**Focused scope:** `T017-R2`, `T017-R3`, `T058-R1`, and regressions in their correction diff
**Authorization:** Maintainer-authorized extra pass under `AGENTS.md` §10
**Platforms verified:** Linux locally; Windows type analysis
**Verdict by task:** `T-017` **Blocked**; `T-058` **Approved**

### Finding dispositions

| ID | Severity | Blocks approval | Focused re-review evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T017-R2` | **Medium** | **Yes** | **The structural single-writer change is sound, and the known-total completion is corrected, but the required unknown-total completion gate is still missing.** Every bar range/value/description write is now inside `_draw_bar()`. The supplied `5/10` → `COMPLETED` test passes and kills both restoring `_refresh` as a writer and removing the finished description. However, changing the finished branch to update its description only when `total` is known let an unknown-total bar become visibly 100% while retaining “progress cannot be measured”; the entire **40-test** job-detail suite still passed. That is the exact unknown-total sibling the prior recommendation required the correction to gate. The shipping branch has a related correctness gap: it derives the finished byte count from the last rendered progress. In a permitted sequence where the view last rendered `1024/unknown` and the store then completed at `2048`, the visible bar was 100% but its description was `"Complete: 1.0 KB downloaded"`, despite the persisted final total being 2 KB. | Gate unknown-total → completed explicitly and kill the conditional-description mutation above. A completed bar with no trustworthy final total should say simply “Complete”; alternatively refresh from the persisted success total before naming a size. Do not present the last coalesced `done` value as the final size. | **Open** |
| `T017-R3` | **Low** | **No** | The source docstring and new post-render test now state the behavior correctly, and independently mutating either side of the distinction failed: a running status must preserve the more specific worker stage, while an ending must replace it immediately. **The current-truth task record still retains the original overclaim**, though: the first correction section at `ai/TASKS.md:147` says “The state words stay immediate.” The newer second-correction paragraph contradicts and explains it rather than replacing it. | Rewrite that older sentence to “terminal state words stay immediate,” preserving the historical explanation without leaving two current claims. **Owner/target:** Documentation Maintainer, T-017 record before closure. | **Open, non-blocking** |
| `T058-R1` | **Medium** | **Yes** | `ai/TESTING.md` §7 now says “Every mandatory area above” without a numeral, while §12 remains the sole numeric full-set coverage statement in current-truth documents. T-014, T-034, and T-058 retain their historical numerators without repeating the denominator. The broad word/digit search was read: other matches are partial numerators, quotations describing the former defect, `REVIEWS.md`'s immutable historical snapshots, or `ARCHITECTURE.md` §7's unrelated error taxonomy. No second current coverage count remains. | None. | **Resolved** |

### Review judgments

- `_draw_bar()` is now the sole source writer of `QProgressBar` range, value and accessible
  description. `_refresh()` delegates completion rather than writing the widget independently.
- The four mutations reported for this batch are real and independently killed: restoring the
  `_refresh()` write, retaining the running description at known-total completion, overwriting a
  specific running stage, and delaying a terminal stage.
- The extra unknown-total mutation is not hypothetical source-shape policing. It restores the
  exact 100%-bar/indeterminate-description contradiction for a normal bar state and survives the
  complete widget suite.
- T058-R1's “single home” applies to current truth. Old review findings must remain as historical
  evidence under `AGENTS.md` §6 and do not become competing current coverage claims.
- Correcting T017-R3 in this batch was within scope: it changed the documentation and test of
  already-correct behavior, not product behavior. The one remaining stale sentence is likewise a
  non-blocking current-truth cleanup.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check e66f34d..b3e156c` | Passed. |
| Current job-detail suite | **40 passed in 1.98 s**. |
| Four reported mutations | **All four killed** by their intended focused tests. |
| Unknown-total conditional-description mutation | **Survived: 40 passed in 1.96 s**. |
| Unknown-total persisted-outcome probe | Stored final `2048/2048`; visible bar `0..100`, value `100`; description `"Complete: 1.0 KB downloaded"`. |
| Repository count search | §12 is the only numeric full-set coverage statement in current truth; remaining matches were inspected and classified as partial, historical, or unrelated. |
| `ruff check .` | Passed. |
| `ruff format --check .` | **87 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **72 source/test files**. |
| Configured `mypy --platform win32` | Passed: no issues in **72 source/test files**. |
| Full default suite with localhost/cache permission | **1339 passed, 11 skipped, 1 deselected in 76.02 s**. |

### Readiness and review budget

`T058-R1` is **Resolved**. T-058 is **Approved at `b3e156c`**.

`T017-R2` remains a blocking Medium finding; `T017-R3` remains non-blocking. T-017 is therefore
**Blocked pending maintainer direction**. Because this was already a maintainer-authorized pass
after the ordinary budget was exhausted, another focused correction/re-review is not automatic:
the maintainer must explicitly authorize it, accept the documented risk, change scope, or move
the work into a named follow-up task.

`T-056` remains **Blocked** on Windows runtime/mutation evidence. It was untouched by `b3e156c`
and remains outside this review.

## 2026-07-28 — T-017 additional authorized focused pass

**Reviewer:** Codex (Reviewer)
**Base:** `b3e156c`  **Head:** `5ee8d36`
**Correction commit:** `5ee8d36`
**Focused scope:** `T017-R2`, `T017-R3`, their correction regressions, and T-058 filing
**Authorization:** Maintainer-authorized extra pass under `AGENTS.md` §10
**Platforms verified:** Linux locally; Windows type analysis
**Verdict by task:** `T-017` **Blocked**; T-058 remains **Approved**

### Finding dispositions

| ID | Severity | Blocks approval | Focused re-review evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T017-R2` | **Medium** | **Yes** | `describe_bar()` and `_draw_bar()` now cover the closed value space, and the widget test derives its assertions from the rendered range/value/description relation. The 30-case cross-product kills the reviewer's prior survivor: describing a finished bar only when `total` is known failed all ten finished/unknown-total cases. Removing durable-total adoption, making a determinate bar inherit indeterminate words, and drawing without a description also failed their intended gates. A completed row with `bytes_done == bytes_total == 2048` now renders a 100% bar described as complete at 2 KB. | None. | **Resolved** |
| `T017-R3` | **Low** | **No** | The first correction entry now says an ending—not every state word—is immediate and records the former wording. It agrees with the source docstring and the post-render behavior test. | None. | **Resolved** |
| `T017-R4` | **Medium** | **Yes** | **The durable-row correction applies completion policy to every ending and assumes a row invariant the manager does not provide.** `_on_job_changed()` calls `_adopt_stored_totals()` for `COMPLETED`, `FAILED`, and `CANCELLED`. The manager deliberately does not persist same-stage progress messages. A cancel probe therefore rendered `5/10`, then jumped backwards to the row's older `1/10` when `CANCELLED` arrived. Restricting adoption to `COMPLETED` survived the entire **71-test** widget suite. Completion has a second manifestation: the manager's success transition updates `bytes_total` but not `bytes_done` (`manager.py:1276-1280`). With a legitimate completed row at `1/20`, the view displayed a full bar and `"Complete: 20 B downloaded"` beside `"1 B of 20 B"`. If success has no total, `describe_bar()` presents the row's last stage-transition `bytes_done` as a final size even though later same-stage progress was never persisted. These are ordinary protocol states, not malformed rows. | Adopt durable data only for `COMPLETED`. When a final `bytes_total` exists, render completion consistently from that total rather than pairing it with stale `bytes_done`; when it does not, say simply “Complete” and do not present persisted `bytes_done` as a final size. Gate cancellation and failure preserving the newest rendered progress, completion with `bytes_done != bytes_total`, and completion with no trustworthy total. | **Open** |
| `T017-R5` | **Low** | **No** | T-017's current evidence still says `tests/ui/test_job_detail.py` contains **35 tests** at `ai/TASKS.md:217`; the reviewed file now contains 71 after the three correction batches. This does not affect behavior or approval by itself, but it is stale current truth in the entry being corrected. | Recount or remove the volatile test count before T-017 closes. **Owner/target:** Documentation Maintainer, T-017 record. | **Open, non-blocking** |

### Review judgments

- The move from remembered examples to a rendered-state relation is the right correction to
  T017-R2. The test no longer asserts a production-authored description against a duplicated
  expected string.
- All four mutations reported for `5ee8d36` are independently killed.
- The cross-product closes the bar's local `(done, total, finished)` presentation space. It
  cannot by itself prove that the values supplied to that space are temporally appropriate;
  T017-R4 is at that caller/data-contract boundary.
- `job_changed` does guarantee that a durable row is readable. It does not guarantee that every
  field in that row was refreshed by the transition: success writes `bytes_total` but leaves
  `bytes_done`, and cancellation/failure leave both progress fields as previously persisted.
- T-058 is correctly recorded Approved at `b3e156c` and filed under `## Complete`. T-017 remains
  under `## In Review`, and T-056 remains under `## Blocked`; no reviewed entry contradicts its
  section.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check b3e156c..5ee8d36` | Passed. |
| Current job-detail suite | **71 passed in 2.03 s**. |
| Four reported mutations | **All four killed** by the cross-product or durable-row test. |
| Completion-only adoption mutation | **Survived: 71 passed in 2.03 s**. |
| Cancelled-row probe | Before ending: `5 B of 10 B`, 50%; after durable `CANCELLED`: `1 B of 10 B`, 10%. |
| Completed-row probe | Durable row `1/20`; rendered bytes `"1 B of 20 B"`, bar 100%, description `"Complete: 20 B downloaded"`. |
| `ruff check .` | Passed. |
| `ruff format --check .` | **87 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **72 source/test files**. |
| Configured `mypy --platform win32` | Passed: no issues in **72 source/test files**. |
| Full default suite with localhost/cache permission | **1370 passed, 11 skipped, 1 deselected in 75.98 s**. |

### Readiness and review budget

`T017-R2` and `T017-R3` are **Resolved**. `T017-R4` is a new blocking Medium correction
regression; `T017-R5` is non-blocking. T-017 is therefore **Blocked pending maintainer
direction**.

Because this was another maintainer-authorized pass after the ordinary budget was exhausted,
another focused correction/re-review is not automatic. The maintainer must explicitly authorize
it, accept the documented risk, change scope, or move the work into a named follow-up task.

T-058 remains **Approved at `b3e156c`**. T-056 remains **Blocked** on Windows runtime/mutation
evidence and was untouched by `5ee8d36`.

## 2026-07-28 — T-017 final authorized focused pass

**Reviewer:** Codex (Reviewer)
**Base:** `5ee8d36`  **Head:** `f100108`
**Correction commit:** `f100108`
**Focused scope:** `T017-R4`, `T017-R5`, and regressions in their correction diff
**Authorization:** Maintainer-authorized final pass under `AGENTS.md` §10; remaining work is to
be carried into the next task rather than another T-017 correction/re-review loop
**Platforms verified:** Linux locally; Windows type analysis
**Verdict:** `T-017` **Blocked; carry `T017-R4` into the next named task**

### Finding dispositions

| ID | Severity | Blocks approval | Focused re-review evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T017-R4` | **Medium** | **Yes** | The ending rule is now explicit and `_totals_for_ending()` applies it correctly when `_on_job_changed()` receives a live transition. Cancellation and failure preserve the rendered `5/10`; completion normalizes a durable `bytes_done=1, bytes_total=20` row to `20/20`; completion without a durable total says `Complete` and shows `Unknown`. All four reported mutations are independently killed. **Initialization still bypasses the rule:** `_load()` sends `job.bytes_done, job.bytes_total` directly to `_show_totals()` and only then `_refresh()` marks the bar finished. Opening a view on an already-completed `1/20` row therefore renders a 100% bar described as `"Complete: 20 B downloaded"` beside `"1 B of 20 B"`. With `bytes_done=3, bytes_total=None`, it says `"Complete"` beside `"3 B of Unknown"`. The new completed-row tests create a running view and then call `_on_job_changed()`, so neither gate covers reopen/restart. | Carry the same completed-row normalization into initial loading and gate construction from already-`COMPLETED` rows both with and without `bytes_total`. The maintainer has directed that this be resolved in the next task, not through a sixth T-017 pass; the coordinator must give it a named task owner before T-017 can close. | **Open; follow-up directed** |
| `T017-R5` | **Low** | **No** | The evidence now states **76 tests as of the fourth correction batch**, which matches independent collection at `f100108`. It avoids a self-referential commit hash and records why the earlier count was stale. | None. | **Resolved** |

### Review judgments

- The correction fixes every terminal-transition manifestation previously reported. The source
  selection rule is coherent: live display while running, durable total on completion, and the
  last rendered progress on cancellation or failure.
- The remaining manifestation is not a new source-selection rule. It is the same completed-row
  rule bypassed by the view's initialization call path.
- The completed-row gate at `tests/ui/test_job_detail.py:619` starts with a `RUNNING` row and
  exercises `_on_job_changed()`; it does not construct the view from the completed row it claims
  to represent.
- The module docstring's final table row wraps onto a second physical line, so it is not a valid
  Markdown table row. This is a non-blocking documentation cleanup and may travel with the same
  next task.
- `T-056` was untouched and remains Blocked on its Windows runtime/mutation evidence.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 5ee8d36..f100108` | Passed. |
| Job-detail collection | **76 tests collected**. |
| Four reported mutations | **All four killed**: adopting durable totals for every ending failed cancellation and failure; retaining the completion counter failed the lagging-counter test; falling back to `done` failed six finished/unknown-total cross-product cases; discarding last-shown totals failed cancellation and failure. |
| Already-completed row probe | Durable `1/20` row opened directly: bytes `"1 B of 20 B"`, bar 100%, description `"Complete: 20 B downloaded"`. |
| Already-completed unknown-total probe | Durable `3/None` row opened directly: bytes `"3 B of Unknown"`, bar 100%, description `"Complete"`. |
| `ruff check .` | Passed. |
| `ruff format --check .` | **87 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **72 source/test files**. |
| Configured `mypy --platform win32` | Passed: no issues in **72 source/test files**. |
| Full default suite with localhost/cache permission | **1375 passed, 11 skipped, 1 deselected in 76.24 s**. |

### Final disposition

This is the final T-017 review pass by maintainer direction. `T017-R5` is **Resolved** and
`T017-R4` is corrected for live transitions but remains open for initialization from an already
completed durable row. Because that is observable progress correctness under `REQ-014`, it
remains a blocking Medium finding and T-017 cannot be marked Approved at `f100108`.

Do not start a sixth T-017 correction/re-review loop. Carry `T017-R4` and its two construction
probes into the next named task, assign an owner there, and close T-017 when that task lands.

## 2026-07-28 — Section 4 independent review

**Reviewer:** Codex (Reviewer)
**Base:** `5b0ebca`  **Head:** `894d794`
**Tasks:** `T-059`, then `T-036` and `T-037`
**Excluded:** coordination-only commit `6ce26ec`
**Platforms verified:** Linux locally; Windows type analysis
**Verdict by task:** `T-059` **Approved**; `T-036` **Changes requested**; `T-037`
**Approved with follow-ups**

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T036-R1` | **High** | **Yes** | **Retry can strand a job durably `QUEUED` without starting it or leaving any usable retry affordance.** `app.retry()` persists `FAILED → QUEUED`, then calls `manager.start()` from the writer callback. The failed session still occupies the pool when that callback runs, so `start()` ordinarily refuses; the exception is logged and discarded at `app.py:236-246`. There is no Phase 1 scheduler to revisit the row. The committed test at `test_composition.py:584-590` asserts only that the store left `FAILED`, explicitly treating start as optional. An independent probe added an observation at the manager boundary and reproduced the defect: after five seconds there were no transitions at all, the store was `QUEUED`, and the view was still `FAILED`. A second Retry does nothing because the durable row is no longer failed. This breaks the retry behavior required by `REQ-015`/`REQ-018`, through the exact composition seam T-036 owns. | Make retry start only after the prior session has released, or give the queue an in-scope owner that starts it then. Keep the persistence ordering, but do not turn a start refusal into an inert durable state. Gate an actual second attempt—at minimum `PROBING`, preferably its terminal result—and agreement between the visible view and durable row; merely leaving `FAILED` is not enough. | **Open** |
| `T037-R1` | **Low** | **No** | The current-truth Scope at `ai/TASKS.md:281-292` says the two integration tests fake yt-dlp at the adapter seam and that only the opt-in network test is real. The implementation and Evidence at lines 312-315 correctly say the opposite: the default tests run real yt-dlp and its HTTP downloader against a local server. The later paragraph does not make the earlier specification cease to be current truth. | Rewrite the Scope to distinguish a real downloader over a deterministic local origin from the opt-in real-site extractor test. **Owner/target:** Documentation Maintainer, next named coordination/documentation task. | **Open, non-blocking** |
| `T037-R2` | **Low** | **No** | `tests/network/test_real_download.py:32-38` calls Big Buck Bunny “public domain.” The Blender Foundation identifies the film as Creative Commons Attribution 3.0 on its [official release poster](https://download.blender.org/ED/poster.pdf). The file may be freely reusable, but CC BY and public domain are not equivalent provenance claims. The test has never run, so its availability and size remain separately unverified. | Replace “public domain” with the actual CC BY attribution and retain the existing “never executed” caveat. **Owner/target:** Documentation Maintainer, next named coordination/documentation task. | **Open, non-blocking** |

### Prior finding disposition

| ID | Severity | Blocks approval | Independent evidence | Status |
|---|---|---:|---|---|
| `T017-R4` | **Medium** | **Yes** | `T-059` routes both live terminal transitions and construction from stopped rows through the same total-selection rule. The focused construction suite passed, and three independent weakenings were killed: bypassing the rule in `_load()`, giving an unopened cancelled/failed row an empty display source, and making a watched cancelled/failed row adopt its lagging durable counts. | **Resolved by `52f0aed`** |

### Review judgments

- T-059 closes the carried half of T017-R4 at the missing entry point. Its opened-row cases are
  construction tests, not transition tests wearing different inputs.
- T-036's object graph, environment propagation, view replacement, shutdown lifecycle, and
  cold-start evidence are otherwise coherent. The eight mutations named in its record are real
  and independently killed.
- Catching `manager.start()` prevents a Qt-slot exception, but it converts the refusal into a
  silent liveness failure. A durable `QUEUED` row is not a retry when no component will ever
  consume it.
- T-037's default end-to-end tests genuinely cross the worker, yt-dlp, local HTTP, persistence,
  and UI boundaries. Its success and unclean-restart claims do not rely on the broken retry
  callback: recovery proves that the affordance is offered, while T-036 owns performing it.
- T-037's POSIX kill path ran locally. Its Windows kill implementation type-checks but remains
  runtime-unverified until the Windows job. The opt-in real-site test remains explicitly unrun.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 5b0ebca..894d794` | Passed. |
| T-059 focused opened/ending tests | **8 passed, 85 deselected**. |
| Three independent T-059 mutations | **All three killed**. |
| Current T-036 composition suite | **12 passed in 1.32 s**. |
| Eight mutations reported for T-036 | **All eight independently killed**; the ordinary-idle writer mutation failed only at the consequential second write, as intended. |
| Retry-start probe | **Failed the intended guarantee:** no manager transition in five seconds; durable state `QUEUED`; visible state `FAILED`. |
| Current T-037 end-to-end suite | **3 passed in 1.84 s** with a local HTTP origin and real worker. |
| Five mutations reported for T-037 | **All five independently killed:** omitted startup recovery, wrong interruption kind, missing output path, halved stored total including its progress fallback, and rewritten stored request. |
| Opt-in `-m network` test | **Not run**, matching the task's explicit caveat. |

### Readiness

T-059 is **Approved at `52f0aed`**, and `T017-R4` is **Resolved**.

T-036 has a blocking High retry defect and is **Changes requested at `c794555`**. This is a
functional failure in the composition seam, not a request for stronger evidence around correct
behavior.

T-037 is **Approved with follow-ups at `894d794`** for its end-to-end behavior. `T037-R1` and
`T037-R2` are non-blocking documentation/provenance corrections and, by maintainer direction,
should be assigned to the next named task rather than start another pass here. T-037's dependency
and the Phase 1 aggregate remain unready while `T036-R1` is open.

## 2026-07-28 — Section 5 independent review

**Reviewer:** Codex (Reviewer)
**Base:** `894d794`  **Head:** `1aba441`
**Tasks:** `T-052`, `T-040`
**Excluded:** coordination-only commit `6ce26ec`
**Platforms verified:** Linux locally; Windows type analysis only
**Verdict by task:** `T-052` **Approved**; `T-040` **Blocked**

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T040-R1` | **Medium** | **Yes** | **The progress-view half does not exercise Windows focus traversal.** The dialog tests press Tab/Backtab on a shown, active window and read `QApplication.focusWidget()`. By contrast, `test_the_progress_view_controls_are_reachable_too()` at `test_windows_desktop.py:571-590` only compares `view.focus_chain()` with a literal and compares sets of focusable children. It never presses a key, observes focus, checks order/wrapping, or proves reachability from initial focus. It could run identically under the offscreen plugin. The task evidence at `ai/TASKS.md:1313-1317` says the fifth test covers the three T-017 controls, and T-017's own known-unverified note assigns those controls to T-040; the evidence therefore overstates the real-plugin boundary the test gates. Per the repository severity table, a gate that does not gate what it claims is Medium. | Show and activate the progress view under the real Windows plugin, drive Tab and Backtab through its controls, assert the hand-authored order, wrapping, and reachability, then mutation-check a reordered and an omitted/added control. Keep T-040 blocked until those mutations and all five tests execute on the Windows desktop job. | **Open** |

### Prior finding disposition

| ID | Severity | Blocks approval | Independent evidence | Status |
|---|---|---:|---|---|
| `T013-R5` | **Low** | **No** | T-052 now observes all three effects that routing before validation would leak: the complete persisted status sequence, public progress, and the resolution report. Moving routing before `SessionValidator.accept()` failed one parametrization for each route. Independently weakening either startup diagnostic also failed all three construction cases. | **Resolved by `7d67e77`** |

### Review judgments

- T-052 is a test-only correction and now proves the negative boundary it records. The production
  validation order did not need changing.
- T-040's four add-dialog tests have the right source of independence: one side is hand-authored,
  while actual focus is walked from the rendered widget with keyboard events.
- The Linux skip is correct and honest. This review does not infer Windows behavior from source
  shape or type analysis.
- The progress-view test is useful as a structural completeness check, but it is not evidence that
  the real Windows desktop delivers that chain.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 894d794..1aba441` | Passed. |
| T-052 selected manager tests | **8 passed, 63 deselected**. |
| Route-before-validation mutation | **Killed on all three named parametrizations:** stored progress stage, public progress, and resolution report. |
| Two startup-diagnostic mutations | **Both killed**; each failed all three startup cases. |
| Windows desktop module on Linux | **1 module-level skip; no Windows tests executed**, as designed. |
| `mypy --platform win32 .` at coordination head | Passed: no issues in **77 files**. |

### Readiness

T-052 is **Approved at `7d67e77`**, and `T013-R5` is **Resolved**.

T-040 remains **Blocked at `1aba441`** on the Windows desktop job and its required demonstrated
mutations. `T040-R1` adds a proof gap that must be corrected before that job can close the task:
even a green Windows run of the current file would not establish focus traversal for the T-017
progress controls.

## 2026-07-28 — Sections 4 and 5 combined validation

The two reviews above were performed against their own base/head boundaries. Afterward, the
following checks were run on coordination head `6ce26ec`; that commit changes `ai/STATUS.md` only
and is not included in either substantive review boundary.

| Check | Result |
|---|---|
| `ruff check .` | Passed. |
| `ruff format --check .` | **91 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **77 files**. |
| Configured `mypy --platform win32` | Passed: no issues in **77 files**. |
| Full default suite with localhost/process permission | **1395 passed, 11 skipped, 2 deselected in 79.29 s**. |

## 2026-07-28 — Sections 4 and 5 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `6ce26ec`  **Head:** `306840b`
**Focused scope:** `T036-R1`, `T040-R1`, `T037-R1`, `T037-R2`, and regressions or direct
siblings in their correction diff
**Platforms verified:** Linux locally; Windows type analysis only
**Verdict by task:** `T-036` **Approved**; `T-037` remains **Approved with follow-ups**;
`T-040` **Blocked**

### Finding dispositions

| ID | Severity | Blocks approval | Focused re-review evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T036-R1` | **High** | **Yes** | `DownloadManager.retry()` now owns both halves of the operation. `FAILED → QUEUED` goes through `_persist()`, so the durable transition is announced before its effect; `_start_when_free()` retains the one requested job until the failed session releases the pool, and the next tick starts it through the ordinary reservation path. The composition test observed `queued`, then `probing`/`running`, and the visible view left `FAILED`. Three independent weakenings all failed: restoring one swallowed start attempt left only `queued`; removing the tick pickup did the same; suppressing the queued announcement produced `probing, failed` without `queued`. The latter demonstrates that start and UI agreement are independently gated. | None. | **Resolved** |
| `T040-R1` | **Medium** | **Yes** | **The correction now drives focus, but its chosen widget state makes its expected three-control chain impossible.** A failed job exposes Retry and the error text, but `JobProgressView._refresh()` disables Cancel for every terminal state. `_focusable()` checks only `focusPolicy`, so it still counts that disabled button. Running the corrected test offscreen after removing only the module's Windows skip failed deterministically before any platform-specific question: Tab visited `retryJobButton → errorMessage → retryJobButton`, never `cancelJobButton`. Windows cannot make a disabled control keyboard-reachable. The test therefore is not ready to produce the Windows evidence or mutations the task requires. | Test representative *reachable* chains by state instead of one structural union: for a retryable failure, drive error and Retry; for a running job, drive Cancel. Filter structural completeness by visible/enabled keyboard reachability, and mutation-check each state on the Windows desktop job. | **Open** |
| `T037-R1` | **Low** | **No** | The Scope now accurately distinguishes real yt-dlp over a deterministic local `http.server` from the opt-in real-site test, and explains why a faked adapter could not prove bytes moved. It agrees with the implementation and Evidence. | None. | **Resolved** |
| `T037-R2` | **Low** | **No** | The network fixture no longer calls Big Buck Bunny public domain. It records CC BY 3.0 and distinguishes downloading from redistribution requiring attribution, consistent with the Blender Foundation source cited by the finding. | None. | **Resolved** |

### New non-blocking follow-ups

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T037-R3` | **Low** | **No** | The corrected network comment is not the repository's only copy of the same provenance claim. `ai/TASKS.md:3457-3460` still describes `archive_org_big_buck_bunny.json` as “public domain,” while the fixture's own `content_licence` correctly says Blender Foundation, CC BY 3.0. This is pre-existing current-truth text outside T-037's correction location, so it does not reopen the approved behavior. | Correct the stale T-012 evidence in the next named documentation/coordination task. **Owner:** Documentation Maintainer. | **Open, follow-up** |
| `T040-R2` | **Low** | **No** | T-040 is correctly filed under `## Blocked`, but `ai/TASKS.md:46-47` and `ai/STATUS.md:25-28` still call it **Ready**. Those summaries predate the Windows-evidence blocker and now contradict the task's canonical section/status. | Update both current-truth summaries when the next task records T040-R1's carry. **Owner:** Documentation Maintainer. | **Open, follow-up** |

### Review judgments

- Keeping High T036-R1 in the current review was required by `AGENTS.md` §10. Correcting it did
  not need another maintainer authorization, and resolving it here is not a downgrade or a carry.
- The retry wait is deliberately narrower than a Phase 2 scheduler: it retains only the retry
  just accepted while the session that produced its failure is being released. Repeated clicks
  for the same job see the in-flight `QUEUED` revision and do not enqueue a second retry.
- T040-R1's structural source correction is directionally right: the test now sends real keyboard
  events and reads actual focus. Its failure is in treating controls that are mutually reachable
  in different job states as one simultaneously reachable chain.
- The offscreen T-040 probe does **not** substitute for the required Windows run. It establishes
  only the platform-independent precondition that the current test already fails because Cancel
  is disabled.
- T-059, T-052, and T-037 are filed under `## Complete`; T-036 is under `## In Review`; T-040 is
  under `## Blocked`. Their task entries agree with those sections.

### Independent checks

| Check | Result |
|---|---|
| `git diff --check 6ce26ec..306840b` | Passed. |
| Corrected T-036 retry test | **1 passed in 0.48 s**. |
| Full T-036 composition suite | **12 passed in 1.49 s**. |
| Three independent T036-R1 mutations | **All three killed**: one swallowed attempt and no tick pickup each timed out with only `queued`; an unannounced requeue timed out with `probing, failed`. |
| Corrected Windows desktop module on Linux | **1 module-level skip; no Windows test executed**, as designed. |
| T040-R1 prerequisite probe | **Failed as evidence:** visited `retryJobButton, errorMessage, retryJobButton`; disabled `cancelJobButton` was unreachable. |
| T037-R1 text comparison | Scope and Evidence now agree on real yt-dlp with a local origin. |
| T037-R2 provenance search | Corrected at the network fixture; one stale sibling remains in T-012 evidence as `T037-R3`. |
| `ruff check .` | Passed. |
| `ruff format --check .` | **91 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **77 files**. |
| Configured `mypy --platform win32` | Passed: no issues in **77 files**. |
| Full default suite with localhost/process permission | **1395 passed, 11 skipped, 2 deselected in 79.76 s**. |

### Readiness and review budget

`T036-R1` is **Resolved**. T-036 is **Approved at `306840b`**.

`T037-R1` and `T037-R2` are **Resolved**. T-037 remains **Approved with follow-ups at
`306840b`**; new Low `T037-R3` is current-truth cleanup and does not reopen its behavior.

`T040-R1` remains a blocking Medium finding, and T-040 remains **Blocked at `306840b`**. This was
the ordinary focused correction re-review, so the automatic review budget for Medium-or-lower
findings is exhausted. Per the maintainer's standing direction, do not start another T-040 pass:
carry the state-specific focus correction, its Windows mutations, and Low `T040-R2` into the next
named task. The Windows desktop job remains required after that correction; the current test would
fail before it could supply the requested evidence.

## 2026-07-28 — T040-R1 carry and coordination verification

**Reviewer:** Codex (Reviewer)
**Base:** `306840b`  **Head:** `479f859`
**Scope:** Carry `T040-R1` to a named task; close `T037-R3` and `T040-R2`; synchronize Phase 1
status
**Boundary classification:** Documentation/coordination only
**Verdict:** **Carry accepted with one documentation follow-up**

### Dispositions

| ID | Severity | Blocks approval | Verification | Status |
|---|---|---:|---|---|
| `T040-R1` | **Medium** | **Yes** | T-060 owns the two measured state-specific chains, Tab and Backtab observations, undeclared-control failure, both Windows mutation classes, and the rule that T-026/TESTING §12 change only after real Windows execution. T-040 remains Blocked and the current intentionally failing Windows test is disclosed rather than skipped or xfailed. | **Open; carried to T-060** |
| `T037-R3` | **Low** | **No** | T-012's evidence now calls the fixture CC BY 3.0 rather than public domain and explains why duplicated licence claims require correction. Repository search found no remaining positive public-domain claim for the item; remaining matches describe the correction. | **Resolved** |
| `T040-R2` | **Low** | **No** | STATUS now says T-040 is Blocked, names T040-R1 and T-060, and no longer presents the Windows evidence as ready. T-054's historical relocation table preserves its original observation and records the later reversal. | **Resolved** |

### New documentation follow-up

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `COORD-R1` | **Low** | **No** | `ai/STATUS.md` correctly says the critical path is approved, but canonical `ai/TASKS.md` still opens with T-016 in review, says T-017 is the only startable task and the critical path is `T-017 → T-036 → T-037`, keeps approved T-036 under `## In Review`, and says in T-037's Complete entry that Phase 1 remains unready while T-036 is blocking. These are pre-existing current-truth statements, but they now directly contradict the coordination state this commit records. | In the next coordination task, replace the stale TASKS preamble, file T-036 under Complete at `306840b`, and remove T-037's obsolete T-036 blocker sentence. **Owner:** Documentation Maintainer. | **Open, follow-up** |

### Review judgments

- T-060 is a complete, bounded owner for the unresolved proof. It starts from observed reachable
  controls rather than inheriting the impossible structural union.
- Leaving the Windows test red is explicitly recorded and does not masquerade as evidence. Nothing
  has been pushed, and T-040 remains Blocked, so the red job cannot be mistaken for a completed
  gate.
- T-036's implementation approval at `306840b` stands. COORD-R1 is filing/readiness cleanup, not a
  reopened source finding.
- The broad TASKS preamble was already stale at the review base. Under `AGENTS.md` §10 it becomes
  follow-up work and does not reopen the corrected tasks or require another pass here.

### Independent checks

| Check | Result |
|---|---|
| Changed paths | `ai/REVIEWS.md`, `ai/STATUS.md`, `ai/TASKS.md` only. |
| `git diff --check 306840b..479f859` | Passed. |
| T-060 ownership audit | Every open T040-R1 behavior and Windows mutation has an explicit acceptance criterion. |
| Licence search | No remaining positive public-domain claim for Big Buck Bunny in current project/task/test documentation. |
| Section placement | T-060 Ready; T-040 and T-056 Blocked; T-037, T-052 and T-059 Complete. T-036's stale placement is COORD-R1. |
| Runtime/type suites | Not rerun for this documentation-only boundary. Source head `306840b` was independently validated in the preceding re-review. |

### Final disposition

The T040-R1 carry is accepted at `479f859`; it remains open under T-060 and still requires the
Windows desktop job. `T037-R3` and `T040-R2` are Resolved. COORD-R1 is a non-blocking
current-truth cleanup for the next coordination task. Do not start another review pass for this
carry commit.

## 2026-07-28 — T-062 and coordination review

**Reviewer:** Codex (Reviewer)
**Base:** `479f859`  **Head:** `a78df2f`
**Scope:** COORD-R1 correction, T-017 closure, T-062, and the T-060/T-061 coordination added in
the same boundary
**Boundary classification:** Documentation/coordination, test code, and CI workflow; no
production source
**Verdict by scope:** `T-062` **Approved with follow-ups**; T-017 closure **confirmed**;
coordination **Changes requested**

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `COORD-R2` | **Medium** | **Yes** | The range correctly adds user-visible code defect `T-061` as Ready and `T-062` as In Review, but both current-truth summaries still describe the state before those additions. `ai/TASKS.md:20-35` says everything open is Windows evidence, lists only T-060 as Ready, and says only Windows evidence plus the exit review remain; `ai/TASKS.md:52-54` calls its nonempty In Review section empty. `ai/STATUS.md:106-113` likewise says In Review is empty, “what remains is not code,” and T-060 is the one task left to write. T-061 affects whether four of five built-in presets download at all for a user without ffmpeg, so this materially misstates Phase 1 readiness rather than merely missing a task count. It also reproduces the current-truth drift COORD-R1 had just corrected. | Rewrite both summaries from the final head: T-061 and T-060 are Ready, T-062 has this review verdict, T-040/T-056 remain blocked on Windows evidence, and the exit review follows the open work. Remove the “empty” In Review note while that section contains an entry. Keep the critical-path statement if desired, but distinguish “critical path built” from “no code remains.” | **Open** |
| `T062-R1` | **Low** | **No** | T-062's record stops at the penultimate CI run. Its status still says “all three” problems and Windows is unproven, its affected surfaces omit `tests/ui/test_job_detail.py`, and its evidence cites red run `30382752254` rather than final run `30383367481`. The diagnostic acceptance criterion at `ai/TASKS.md:96-97` also says **every** assertion in both T-037 tests reports job status and stored error, while the implementation deliberately augments the two opaque state waits only; ordinary assertions at `test_end_to_end.py:257-298` and `403-462` retain their specific messages. The narrower implementation is sensible—adding `job=completed error=none` to a size mismatch would add noise—but the current claim is false. The new stage note also calls 0.15 seconds “a hundred times faster” than human reading, which is not a supportable measurement. | Record final run `30383367481`, all four corrected surfaces, and the now-proven Windows half. Narrow the diagnostic criterion/evidence to the long-running state waits whose failures otherwise concealed the durable row and environment, and remove the volatile human-reading multiplier. **Owner/target:** Documentation Maintainer, in the COORD-R2 correction batch. | **Open, non-blocking** |
| `ENV-R1` | **Low** | **No** | The handoff's unfiled environment problem reproduces. `.venv/bin/tracks-and-trails` names `/mnt/projects/software_projects/tracks-and-trails/.venv/bin/python`, which does not exist, while the editable install's `direct_url.json` targets `file:///mnt/projects/software_projects/tracks-and-trails`, one directory above this checkout. Running this checkout's `.venv/bin/python` cannot import `tracks_and_trails` without an explicit `PYTHONPATH`. This predates the review boundary and does not affect CI or the reviewed code, but “Repository path — Unsettled” in STATUS is not an actionable owner. | Have the Planner file a small environment-repair task in the COORD-R2 correction batch. Until it lands, use this checkout's `.venv/bin/python -m …` with an explicit checkout `PYTHONPATH`, as this review did. | **Open, non-blocking; pre-existing** |

### Implementation judgments

- **Installing ffmpeg in the standard matrix is the correct boundary.** `REQ-024` correctly
  refuses a selector the present worker believes needs ffmpeg; T-037 is supposed to prove a real
  download and restart path, not that refusal. Linux's supported environment uses a system
  ffmpeg, and the Windows test only needs the supported executable boundary. Skipping T-037 or
  changing its preset would weaken the exit evidence.
- This does **not** hide T-061. The defect remains observable when ffmpeg is deliberately absent,
  is filed against production code with an end-to-end no-ffmpeg criterion, and is independent of
  whether CI's ordinary supported environment provides the dependency.
- The platform-executable fake is correct: a `.bat` reaches Windows' `PATHEXT` rule while the
  executable shell file preserves the POSIX case. Both standard CI jobs execute this test.
- The 0.15-second pacing is still timing-based, but it is ten times Windows' stated coarse timer
  interval, the view requests a 1 ms repaint, and the actual Windows runner passed. No defect is
  established from the pacing change.
- T-017's closure is sound. The prior T-059 review explicitly resolved carried `T017-R4` at
  `52f0aed`; `48dc6a0` changes task/status records only and does not manufacture another verdict.
- The task-ID multiset across the coordination rewrite is unchanged except for the intended new
  T-061 and T-062 entries; no prior task was lost or duplicated.

### Independent CI verification

Run `30383367481` is at exact head `a78df2f`.

| Job/evidence | Result |
|---|---|
| `ubuntu-latest` | **Passed**; 1395 passed, 11 skipped, 2 deselected. Both T-037 tests, the T-036 ffmpeg test, and the paced stage test passed. |
| `windows-latest` | **Passed**; 1384 passed, 20 skipped, 27 deselected. The same four named tests passed. |
| Ubuntu environment artifact | `/usr/bin/ffmpeg`; ffmpeg 6.1.1 recorded. |
| Windows environment artifact | `/c/ProgramData/Chocolatey/bin/ffmpeg`; ffmpeg 8.1.2 recorded. |
| Both frozen jobs | **Passed**. |
| `windows desktop` | **Failed only on T-060's four disclosed tests**: three dialog-chain assertions and the progress-view state-union assertion; 4 failed, 21 passed, 1406 deselected. |

The overall workflow is red only because the deliberately unskipped T-060 evidence is red. That
does not invalidate the green standard-platform evidence T-062 requires.

### Independent local checks

The checked-in console scripts and editable path are stale as ENV-R1 records, so every Python
command below used this checkout's `.venv/bin/python -m …` with
`PYTHONPATH=/mnt/projects/software_projects/tracks-and-trails/tracks-and-trails/src`.

| Check | Result |
|---|---|
| Four focused changed tests | **4 passed in 2.83 s**: T-036 fake ffmpeg, T-062 stage pacing, and both T-037 end-to-end cases. |
| Full default suite with localhost/process permission | **1395 passed, 11 skipped, 2 deselected in 80.35 s**. |
| `ruff check .` | Passed. |
| `ruff format --check .` | **91 files already formatted**. |
| `mypy src` | Passed: no issues in **35 source files**. |
| Configured `mypy` | Passed: no issues in **76 source files**. |
| Configured `mypy --platform win32` | Passed: no issues in **76 source files**. |
| `git diff --check 479f859..a78df2f` | Passed. |
| Git boundary | HEAD and `origin/main` both `a78df2f`; four commits, all authored by Sean Kottman, with no AI authorship trailers. |

The first sandboxed focused run failed before application code because binding the local fixture
server was denied; the same four tests were rerun with localhost permission and passed. That
sandbox denial is not counted as project evidence.

### Final disposition

T-062's workflow and test changes are **Approved with follow-ups at `a78df2f`**. The final
standard Linux and Windows jobs supply the evidence T-037 previously lacked, and installing
ffmpeg is accepted.

The combined coordination boundary is **Changes requested** on `COORD-R2`: current-truth files
cannot say no code remains while T-061 is Ready or say In Review is empty while T-062 occupies
it. The focused correction is documentation-only: synchronize the two summaries and T-062's
final evidence/wording, and file the already-confirmed environment repair. No source, test, or
workflow correction is requested.

## 2026-07-28 — T-062 coordination focused re-review

**Reviewer:** Codex (Reviewer)
**Base:** `a78df2f`  **Head:** `8a0117e`
**Focused scope:** `COORD-R2`, `T062-R1`, and `ENV-R1`
**Boundary classification:** Documentation/coordination only
**Verdict:** **Approved with one non-blocking documentation follow-up**

### Finding dispositions

| ID | Severity | Blocks approval | Verification | Status |
|---|---|---:|---|---|
| `COORD-R2` | **Medium** | **Yes** | TASKS now says the open work includes code and evidence, places T-062 In Review, lists T-060/T-061/T-063 Ready, leaves T-040/T-056 Blocked, and explicitly says Phase 1 is not ready. STATUS names the same three Ready tasks, T-062 In Review, the two Windows blockers, and the exit review. The obsolete empty-section claim is now identified as historical rather than current. | **Resolved by `8a0117e`** |
| `T062-R1` | **Low** | **No** | The final run, fourth problem, fourth affected test surface, and Windows evidence are corrected. The evidence prose now accurately says diagnostics were added to two assertions, not the suite. **Two requested corrections remain:** the acceptance criterion at `ai/TASKS.md:108-109` still says every assertion in both T-037 tests reports status/error, and `ai/TASKS.md:167` still calls 0.15 seconds “a hundred times faster” than human reading. Both are the exact overclaims the initial finding asked to remove. | **Partially resolved; remains open, non-blocking** |
| `ENV-R1` | **Low** | **No** | T-063 separately records the stale console-script interpreter and wrong editable-install path, reproduces both, requires both invocation forms to work without `PYTHONPATH`, requires a durable documented procedure, and prevents the STATUS environment row from implying a working install. Choosing the canonical repository path remains with the maintainer. | **Resolved by filing T-063** |

### Focused review judgments

- T-063 is a concrete and complete owner for ENV-R1. Its two fault descriptions and fresh-venv
  criterion prevent repairing only the disposable local environment and calling the issue done.
- COORD-R2 no longer overstates readiness. TASKS and STATUS agree on the operative state:
  T-062 In Review; T-060, T-061 and T-063 Ready; T-040 and T-056 Blocked.
- The surviving T062-R1 wording does not change behavior, evidence, or readiness. Do not spend a
  second correction re-review on it. The Documentation Maintainer should narrow the acceptance
  criterion to the two opaque state waits and remove the human-reading multiplier when filing
  T-062 under Complete; no further review is required for those two mechanical edits.
- No source, test, workflow, requirement, architecture, or decision file changed in this
  correction boundary.

### Proportional verification

| Check | Result |
|---|---|
| Changed paths | `ai/REVIEWS.md`, `ai/STATUS.md`, and `ai/TASKS.md` only. |
| `git diff --check a78df2f..8a0117e` | Passed. |
| Section/status audit | T-062 In Review; T-060/T-061/T-063 Ready; T-040/T-056 Blocked. No duplicate task ID was introduced. |
| Stale-claim search | The old “only evidence,” “only T-060,” and currently empty In Review claims are gone; remaining empty-section text is explicitly historical. |
| Git boundary | HEAD and `origin/main` both `8a0117e`; Sean Kottman is the sole author and no AI authorship trailer is present. |
| Runtime/type suites | Not rerun for this documentation-only correction. The implementation head was independently validated in the initial review. |
| Pushed CI run `30385113813` | At review close, Ubuntu and both frozen jobs were green; the Windows desktop job had the expected T-060 failure; standard Windows was still running its tests. This documentation-only run is not required to resolve the three reviewed findings. |

### Final disposition

`COORD-R2` and `ENV-R1` are **Resolved**. The coordination correction is approved at `8a0117e`.
T-062 remains **Approved with follow-ups**: T062-R1 is still open only for two non-blocking
current-truth wording edits, assigned to the T-062 completion filing. The ordinary focused
re-review is complete; those edits do not warrant another pass.

### T062-R1 mechanical closure at `00ce157`

This is confirmation of the two edits assigned above, not another substantive review pass.

- **T062-R1 is Resolved.** The acceptance criterion now names only the two opaque waits the
  correction actually changed and explicitly distinguishes the other assertions from delivered
  evidence. The unsupported reading-speed multiplier is gone from both the task record and the
  test comment; both now state the relevant relation, that a stage must outlive a repaint
  interval.
- T-062 is correctly filed under Complete, and the top-level TASKS summary says nothing is in
  review. Moving the task did not change executable test behavior.
- CI run `30385113813` at `8a0117e` independently finished in the expected shape: Ubuntu,
  standard Windows, and both frozen jobs passed; Windows desktop failed only T-060's four known
  focus tests.

One adjacent current-truth cleanup does not reopen T-062:

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `COORD-R3` | **Low** | **No** | `ai/STATUS.md:111` still labels T-062 “In Review” in the paragraph describing what the CI run produced, after TASKS filed it Complete at `00ce157`. The following “What remains” list is correct and omits T-062, so readiness is not materially overstated, but the status label is stale. | Change it to “then In Review, now Complete” or equivalent in the next coordination update. **Owner/target:** Documentation Maintainer, next T-060/T-061/T-063 status update. | **Open, non-blocking** |

`git diff --check 8a0117e..00ce157` passed. HEAD and `origin/main` both resolve to `00ce157`;
Sean Kottman is the sole author and no AI authorship trailer is present. The filing commit's
runtime suite was not rerun locally for this confirmation: its only test-file change is a comment,
and the implementer reports 1395 passed, 11 skipped, 2 deselected. Its pushed CI run
`30386164244` was still in progress when this closure was recorded.

**Final disposition:** T062-R1 is **Resolved**, and T-062 is **Approved and Complete at
`00ce157`**. COORD-R3 is a non-blocking follow-up and requires no additional T-062 review.

## 2026-07-28 — T-060, T-061 and T-063 review

**Reviewer:** Codex (Reviewer)
**Base:** `00ce157`  **Head:** `11e1203`
**Scope:** COORD-R3, T-061's ffmpeg decision gate, T-060's state-specific Windows focus
evidence, and T-063's virtualenv repair
**Boundary classification:** Production source, tests, documentation/coordination, and a local
git-ignored environment repair
**Verdict by task:** T-061 **Approved**; T-063 **Approved with follow-up**; T-060
**Changes requested**

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T060-R1` | **Medium** | **Yes** | `DIALOG_STATES` covers only an empty editor and a typed URL (`tests/ui/test_windows_desktop.py:498-510`). Both deliberately exclude `cancelProbeButton`, even though it is the only cancellation control enabled while a probe is in flight. T-060 says nothing in the dialog chain remains out of scope and requires a newly reachable undeclared control to fail. The task record itself acknowledges that this state is absent because the present fixture cannot create it. A keyboard regression in the in-flight probe state therefore remains ungated. | Add an in-flight-probe state through a purpose-built fake manager/store or another controlled state seam; drive its real Tab and Backtab chain and include `cancelProbeButton` in the hand-authored expectation. Do not start a real worker merely to create widget state. Run the two required mutation classes against this state on Windows too. | **Open** |
| `T060-R2` | **Medium** | **Yes** | The progress-view test converts the forward-only walk to a set (`tests/ui/test_windows_desktop.py:687-695`). It never drives Backtab and never compares the delivered sequence with `EXPECTED_VIEW_ORDER`; reversing the actual two-control failed-state order still satisfies the assertion. The separate declaration assertion proves only what `focus_chain()` returns, not what Windows delivers. This does not meet T-060's real-focus Tab/Backtab criterion or its evidence claim that every state checks walked order and both wrap directions. | For each progress-view state, assert the observed forward sequence in order and drive the reverse sequence through Backtab, including wrap. Keep the hand-authored per-state availability independent of the production declaration. Mutation-check reversal and undeclared-control insertion on Windows as the task already requires. | **Open** |
| `T063-R1` | **Low** | **No** | T-063 repairs the two application entry points exactly as scoped, but reinstalling only this editable project leaves dependency-owned launchers untouched. At this head, 39 scripts under `.venv/bin/` still name `/mnt/projects/software_projects/tracks-and-trails/.venv/bin/python`; bare `.venv/bin/mypy` and `.venv/bin/pytest` both fail with `bad interpreter`. `docs/DEVELOPMENT.md:66-76` documents those bare commands, while its repair step at lines 176-181 does not repair them. Module invocations pass, so this is developer-environment residue rather than a product or T-063 acceptance failure. | Filed `T-064` under Ready to make the repair procedure rebuild or otherwise refresh the complete development environment and prove the documented bare commands. | **Open; carried to T-064** |
| `COORD-R4` | **Low** | **No** | All three task entries are under `## In Review`, and the handoff states that accurately, but the TASKS preamble still calls T-060/T-061/T-063 Ready and says nothing is in review (`ai/TASKS.md:20-43`). STATUS likewise says they are ready to write (`ai/STATUS.md:110-124`) and does not record the successful T-060 Windows run. Phase readiness is not overstated—the same text says code/evidence remain—so this is current-truth drift rather than a blocking readiness claim. | Synchronize TASKS and STATUS when filing the review results: T-061 approved, T-063 approved with T-064, T-060 in correction review, and T-040/T-056 still blocked. Record run `30388380440` as normal Windows evidence without claiming the unrun mutations. **Owner/target:** Documentation Maintainer, focused correction filing. | **Open, non-blocking** |

### Task judgments

- **T-061 is sound.** `_will_merge` prefers yt-dlp's resolved `requested_formats`, recognizes a
  single resolved `format_id`, and returns `None` for the blind case so the caller retains the
  conservative selector fallback. The merge-refusal test now contains two requested formats, the
  progressive unit case exercises the defect, and the end-to-end case proves the supported preset
  completes when the application reports ffmpeg unavailable.
- **T-060's diagnosis is correct but its gate is incomplete.** CI's original failures were caused
  by state availability, not a Windows/offscreen ordering difference. The new normal Windows run
  confirms the corrected expectations that are present. It cannot close T-040 or TESTING §12
  until T060-R1/R2 and the already-disclosed Windows mutation evidence are complete.
- **T-063 meets its application-facing acceptance criteria.** Both invocation forms work without
  `PYTHONPATH`, the import-location check points into this checkout, and the repair is documented.
  T063-R1 is intentionally carried because it concerns dependency-owned development launchers,
  not either application entry point the task was filed to restore.
- **COORD-R3 is resolved.** STATUS now describes T-062 as approved and complete. COORD-R4 is a
  later status transition left unsynchronized, not a recurrence that invalidates that correction.

### Independent CI verification

Run `30388380440`, attempt 2, is successful at exact head `11e1203`.

| Job/evidence | Result |
|---|---|
| `ubuntu-latest` | **Passed** |
| `windows-latest` | **Passed** |
| `frozen ubuntu-latest` | **Passed** |
| `frozen windows-latest` | **Passed** |
| `windows desktop` | **Passed** under the real `windows` Qt plugin |

Attempt 1 was cancelled only in Ubuntu's `Install ffmpeg` step after 14 minutes 49 seconds; its
other four jobs passed. The same step completed in 9 seconds on attempt 2, supporting the
handoff's infrastructure diagnosis. A green normal desktop job is not evidence for mutations
that were never committed and run.

### Independent local checks

| Check | Result |
|---|---|
| Four focused T-061 tests | **4 passed in 0.99 s** with localhost permission |
| Full default suite | **1398 passed, 11 skipped, 2 deselected in 83.51 s** |
| `ruff check .` | Passed |
| `ruff format --check .` | **91 files already formatted** |
| `python -m mypy src` | Passed: **35 source files** |
| Configured `python -m mypy` | Passed: **76 source files** |
| Configured `python -m mypy --platform win32` | Passed: **76 source files** |
| Application entry points and import location | Both report `0.1.0.dev0`; import resolves to this checkout |
| Bare developer entry points | `mypy` and `pytest` fail on the stale parent-checkout shebang; filed as T-064 |
| `git diff --check 00ce157..11e1203` | Passed |
| Git boundary | HEAD and `origin/main` both `11e1203`; four commits by Sean Kottman, no AI authorship trailers |

The first sandboxed focused run passed the three unit cases and failed before application code
when the end-to-end fixture could not bind localhost. The identical four-test command was rerun
with localhost permission and passed; the sandbox denial is not project evidence.

### Final disposition

T-061 is **Approved at `11e1203`**. T-063 is **Approved with follow-up at `11e1203`**; T063-R1
is owned by Ready task T-064 and does not keep T-063 in review.

T-060 is **Changes requested** on T060-R1 and T060-R2. The focused correction re-review should
inspect only those two test gaps, the Windows mutation evidence already required by T-060, and
the correction diff. Until then T-040 remains Blocked and the Windows tab-order gap in
`ai/TESTING.md` remains accurate. T-056 is untouched by this review and remains blocked on its
own Windows mutation evidence.

---

## 2026-07-28 — T-060 correction batch (Implementer)

**Implementer:** Claude (Opus 5)
**Responds to:** the 2026-07-28 review of `00ce157..11e1203`
**Status:** both blocking findings **corrected, awaiting re-review**. Appended, not edited into
the reviewer's table (`AGENTS.md` §6, §9). Nothing below is marked Resolved; that is the
Reviewer's to do.

**One of the two findings is corrected in a way its recommendation did not anticipate**, and that
is flagged here rather than buried: the mutation `T060-R2` names cannot be killed by any keyboard
observation. See the row below.

### Corrections

| ID | Correction | Evidence that weakening it fails |
|---|---|---|
| `T060-R1` | A third dialog state — **a probe in flight** — is asserted, with `cancelProbeButton` in its hand-authored expectation and `probeButton`/`addButton` out of it. Reached without a worker: `_ProbeThatNeverAnswers` subclasses `DownloadManager` and overrides `start` to record and return, so the dialog's own `_on_probe_saved` sets `started` and `_refresh_actions` does the rest. Not `entry_point=child_never_returning` — that spawns a real process, and a worker stranded by a failed assertion in this file would be attributed to the next test. The factory asserts the state was actually entered, so the chain cannot be asserted over an idle dialog. | Removing `cancelProbeButton` from the chain: **killed**. An undeclared focusable control added to the dialog: **killed**. Swapping `titleValue`/`uploaderValue`: **killed in all three states**, this one included. |
| `T060-R2` | The set is gone. Both progress-view directions are compared as **anchored sequences** — focus is placed deliberately, so the expected sequence is predicted outright rather than rotated into place — and Backtab is driven for two full laps. The identical set-containment weakness in `test_the_dialog_chain_wraps_in_both_directions` is corrected in the same batch (sibling audit, `AGENTS.md` §10). | Swapping two dialog controls: **killed ×3**. A walk that ignores `backwards` and always presses Tab: **killed** on the dialog. An undeclared focusable control in the progress view: **killed**. The two progress-view order mutations **survive**, necessarily — see below. |

### The reversal `T060-R2` names is unobservable, and that is a measurement

The finding asks that reversing the failed state's two-control order fail the test. It does not,
and it cannot: **no state of the progress view offers more than two reachable controls, and a
two-element focus cycle has no observable orientation.** `A → B → A` and `B → A → B` are the same
cycle — from either control, Tab and Backtab both deliver the other one, from any starting point.

This was run, not assumed. The mutation reverses what `setTabOrder` delivers while leaving
`focus_chain()`'s declaration untouched — exactly the scenario the finding describes — and it
survives an anchored, unrotated, both-directions sequence assertion. A four-line model of a
2-cycle shows the same thing independently.

The same limitation explains why `probeButton`/`cancelProbeButton` is not a usable swap for
`T-026`'s first mutation class: they are never enabled simultaneously, so no walk distinguishes
the two arrangements. The swap is therefore done on two controls reachable in every state.

Ordering is gated where it is observable — the dialog's three states offer nine to twelve
reachable controls — and the anchored sequence is asserted for the progress view regardless,
because it costs nothing and starts gating order by itself the day a third control becomes
simultaneously reachable. Recorded in `ai/TESTING.md` §12 as a property of small widgets, not as a
property of this test.

### Verification

| Check | Result |
|---|---|
| Focus tests, all 8 parametrised cases, offscreen pre-flight | **8/8 passed** |
| Mutation battery | **7 of 9 killed**; both survivors are the 2-cycle cases above |
| Full default suite | **1398 passed, 11 skipped, 2 deselected** |
| `ruff check .` / `ruff format --check .` | Passed / 91 files already formatted |
| `mypy src` / configured `mypy` / `mypy --platform win32` | 35 / 76 / 76 source files, all clean |

**Method, so the pre-flight can be repeated and audited.** `tests/ui/test_windows_desktop.py`
skips itself off Windows, so the harness loads the module's source with **only** the platform
guard disabled and calls the real test functions with hand-built fixture values. Nothing is
re-implemented — a pre-flight that paraphrased the assertions could pass while the file failed.

**Offscreen is not the Windows job and nothing here claims otherwise.** It answers the one
question a runner cannot answer this week: whether these assertions hold against the real widgets
at all.

### What this batch does not supply

**The `T-026` mutations still have not run on Windows**, for the dialog chain or the view's, and
that is now blocked on more than a job: GitHub Actions usage is exhausted as of 2026-07-28 and CI
cannot run for several days (maintainer). `T-040` stays Blocked, `ai/TESTING.md` §12 keeps its
gap, and `T-026`'s acceptance criterion stays unmet. `T-056` is untouched.

## 2026-07-28 — T-060 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `11e1203`  **Head:** `12dff92`
**Focused scope:** `T060-R1`, `T060-R2`, their sibling dialog traversal assertion, COORD-R4, and
the correction commit itself
**Boundary classification:** Test code and documentation/coordination only; no production source
**Verdict:** Both blocking findings **Resolved**; T-060 **Blocked on external Windows mutation
evidence**

### Finding dispositions

| ID | Severity | Blocks approval | Verification | Status |
|---|---|---:|---|---|
| `T060-R1` | **Medium** | **Yes** | The hand-authored matrix now includes the in-flight-probe state with `cancelProbeButton` reachable and Probe/Add unavailable. `_ProbeThatNeverAnswers` lets the dialog's real save callback and state transition run without spawning a worker, and the fixture independently asserts `probing_job_id` before testing focus. The three-state forward and reverse walks pass. An independent mutation that disabled Cancel after `_refresh_actions` failed the checked-in assertion. | **Resolved by `12dff92`** |
| `T060-R2` | **Medium** | **Yes** | The progress-view walk is no longer a set: focus is explicitly anchored, Tab and Backtab each run two laps, and their sequences are asserted. The sibling dialog wrap test now compares ordered two-lap sequences in both directions too. An independent mutation making Backtab walk forward failed the dialog assertion. The requested two-control view reversal cannot be observed: with only A and B reachable, either orientation maps A to B and B to A under both keys. Accepting that measured limit is more accurate than claiming a mutation can distinguish it; T-040's observable reorder criterion remains owned by the nine-to-twelve-control dialog. | **Resolved by `12dff92`** |
| `COORD-R4` | **Low** | **No** | TASKS' summary and STATUS now record T-061 approved, T-063 approved with T-064, T-060 in correction review, T-040/T-056 blocked, and normal green run `30388380440`. However, the individual T-061 and T-063 entries remain marked In Review and remain under that section. The operative summary is accurate for the correction head, so readiness is no longer misstated, but the canonical task entries still need filing under Complete; filing this verdict must also move T-060 from In Review to Blocked on Windows evidence. | **Partially resolved; completion filing remains** |
| `GIT-R1` | **Low** | **No** | Published commit `12dff92` contains `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`, directly contrary to `AGENTS.md` §7/§13, and omits the required `Task: T-060` trailer. Correcting it would require rewriting published `main`, which is separately forbidden without confirmation. This does not affect the reviewed tree or reopen T060-R1/R2. | **Open; T-065 filed Blocked on maintainer decision** |

### Focused judgments

- The in-flight state is reached through the dialog's behavior rather than manufactured by
  toggling button properties. The manager subclass changes only the external session boundary:
  `start()` accepts and records the probe, while the dialog owns `started`,
  `probing_job_id`, and `_refresh_actions`.
- No worker or process-lifetime obligation is introduced. The direct pre-flight closed the
  window cleanly after all cases.
- The two-cycle explanation is correct. A keyboard transition over exactly two reachable controls
  has one possible next control from either anchor; reversing the declared orientation produces
  the same observations for Tab and Backtab. The progress test still asserts the strongest
  observable sequence and will begin distinguishing orientation if a third control becomes
  reachable.
- T-060's original Windows acceptance remains deliberately unmet. The normal tests passed under
  the real plugin at `11e1203`, but the reordered-widget and undeclared-control mutations have not
  run there. T-040 and TESTING §12 therefore remain Blocked/ungated rather than being closed from
  offscreen evidence.
- T-056 is outside this correction and remains blocked on its separate Windows branch evidence.

### Independent verification

| Check | Result |
|---|---|
| Checked-in focused functions loaded with only the platform skip disabled | **8/8 parameter cases passed offscreen** |
| Independent T060-R1 weakening | Disabling `cancelProbeButton` in the in-flight state **failed** |
| Independent T060-R2 weakening | Making Backtab always walk forward **failed** on the dialog |
| Two-control transition model | Confirmed forward and backward both map A→B and B→A |
| Full default suite | **1398 passed, 11 skipped, 2 deselected in 85.96 s** |
| `ruff check .` | Passed |
| `ruff format --check .` | **91 files already formatted** |
| `python -m mypy src` | Passed: **35 source files** |
| Configured `python -m mypy` | Passed: **76 source files** |
| Configured `python -m mypy --platform win32` | Passed: **76 source files** |
| `git diff --check 11e1203..12dff92` | Passed |
| Git boundary | HEAD and `origin/main` both `12dff92`; one commit authored by Sean Kottman |

Workflow run `30392139504` is at exact head `12dff92` and failed before executing any project
step. All five jobs have empty step lists. The Windows desktop annotation says the job was not
started because account payments failed or the spending limit must be increased. This confirms
the external billing/quota blocker and supplies no code or mutation evidence.

### Final disposition

`T060-R1` and `T060-R2` are **Resolved at `12dff92`**. No open correction finding remains.

T-060 itself is **Blocked**, not Approved, because its pre-existing acceptance criterion still
requires the two mutation classes to be executed and recorded under the real Windows plugin.
Once Actions can run, execute the observable reorder mutation on the dialog and the
undeclared-control mutation on both surfaces; execute and record the progress-view reorder as the
documented two-cycle survivor. Then the resulting evidence-only filing can close T-060 and
T-040 without another broad review.

COORD-R4 still needs the already-approved T-061 and T-063 entries moved to Complete and T-060
moved to Blocked when this verdict is filed. GIT-R1 is a non-blocking published-history issue
owned by T-065; no history was rewritten during this review.

## 2026-07-28 — STARBASE evidence and T-066 through T-070 review

**Reviewer:** Codex (Reviewer)
**Base:** `12dff92`  **Head:** `1e9694c`
**Scope:** T-040/T-060's Windows evidence, T-065's coordination decision, T-066 through T-070,
and the new Windows verification workflow, documentation, and tools
**Boundary classification:** Workflow, tests, documentation/coordination, and privileged
developer tooling; no production source
**Verdict by task:** T-067 and T-070 **Approved**; T-068 **Blocked on its disclosed Windows
runner/frozen evidence**; T-066 and T-069 **Changes requested**; T-040/T-060 **Changes requested
on their unmet documentation criterion**; Windows verification tooling **Changes requested**

The checkout advanced to `1dd2f50` while this review was running. That later self-hosted-runner
commit is excluded from every verdict below. It did not change source or tests, so the local
runtime/type results still exercise the exact executable tree at `1e9694c`; workflow and
documentation judgments use the requested head itself.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T066-R1` | **Medium** | **Yes** | T-066 measured that on Windows in a venv `Popen(sys.executable)` returns the launcher PID while a different PID runs the interpreter (`ai/TASKS.md:180-186`). The recovery test nevertheless calls `process.kill()` on that returned handle and immediately treats `process.wait()` as proof that it killed the application (`tests/integration/test_end_to_end.py:70-80,410-469`). The two T-019 kill-parent tests have the same shape (`tests/integration/test_manager.py:1911-1938,1975-2003`). None identifies the PID reported from inside the application or asserts that interpreter ended. Therefore moving CI into a venv does not establish the crash/reaping property under the deeper shape; it establishes only that the launcher ended. This is also a concrete sibling of T-069's conditional restart failure: an application left alive can still own the database, though that causal link needs a Windows probe rather than an assertion. | Have each driver report its own `os.getpid()` in the startup handshake. Kill that interpreter PID without gracefully unwinding it, then independently assert the interpreter and the expected worker/descendant set have ended before reopening the database. Audit every Windows `Popen([sys.executable, ...])` + `kill(parent.pid)` path, reproduce T-069's predecessor sequence, and mutation-check killing only the launcher. | **Open** |
| `COORD-R5` | **Medium** | **Yes** | T-040 and T-060 each require `ai/TESTING.md` to drop the Windows tab-order gap and T-026's criterion to be marked met. Their new evidence says both happened (`ai/TASKS.md:918-919,1320-1325`), but `ai/TESTING.md:211-218`, `ai/REQUIREMENTS.md:63-68`, `ai/IMPLEMENTATION_PLAN.md:67-70`, and T-026's own current task text at `ai/TASKS.md:4897-4901` still say the gate does not exist. STATUS says T-040 is both never-run/Blocked (`ai/STATUS.md:24-30,157-164`) and In Review with the criterion met (`ai/STATUS.md:124-129`). The five new task entries are under `## Ready` while each says In Review, and the preamble says In Review contains them. This materially disagrees about whether a required gate exists, not merely where a task is filed. | Reconcile the current-truth chain in authority order: REQUIREMENTS, IMPLEMENTATION_PLAN, TESTING, T-026, T-040/T-060, STATUS, and section placement. Preserve historical statements as explicitly historical, but leave one unambiguous current answer about the manual STARBASE mutation evidence and the still-unautomated mutation run. T-040/T-060 cannot be filed Complete until their explicit documentation criterion is actually met. | **Open** |
| `WIN-R1` | **Medium** | **Yes** | `tools/windows/ssh-setup.ps1:35-48` uses `Set-Content` on the machine-wide `administrators_authorized_keys`, silently replacing any administrator keys already present; Microsoft's own setup example appends instead. Lines 54-58 then install an inbound TCP/22 allow rule without a remote-address restriction and without a profile, whose documented default is `Any`, while the script makes `sshd` automatic and the project documents that this path yields elevated administrator sessions. Running a repository helper should not delete existing access or expose privileged SSH on every network profile without an explicit choice. | Preserve and deduplicate existing authorized keys. Default the firewall rule to a deliberately scoped source (`LocalSubnet` or an explicit maintainer host) and appropriate profile, make broader exposure an explicit parameter, report the effective rule, and document removal/rollback. See Microsoft's `New-NetFirewallRule` and Windows OpenSSH key-management documentation. | **Open** |
| `WIN-R2` | **Medium** | **Yes** | `run.cmd` records the remote command's `EXITCODE`, but `tools/windows/run-on-starbase.sh:25-33` only prints the file and returns the final `ssh | sed` status. A deterministic fake transport printed `EXITCODE=1`; the wrapper exited **0**. The timeout branch likewise breaks out and can return success if the partial-output read succeeds. A local runner or caller can therefore report a red remote suite as green—the exact gate-vacuity class this harness says it prevents. | Parse and validate the final `EXITCODE=<n>` marker, return that value, and return a distinct nonzero status on timeout, missing marker, malformed output, or transport failure. Add a platform-neutral harness test with fake `ssh`/`scp` for remote 0, remote nonzero, timeout, and missing marker. | **Open** |
| `WIN-R3` | **Low** | **No** | `docs/WINDOWS_VERIFICATION.md:120-140` says `run_mutations.py` executes “both classes plus a control” and specifically says `mut_control_always_dead.py` must fail. The driver's `CASES` at `tools/windows/mutations/run_mutations.py:30-36` contains the baseline and four focus mutations only; the named control targets T-056's `still_running`, not the T-026 focus harness. | Either add a relevant positive control to the focus driver and report it, or narrow the documentation to the controls the driver actually runs. Keep the T-056 control in the T-056 procedure rather than presenting it as T-026 evidence. | **Open, non-blocking** |
| `GIT-R2` | **Low** | **No** | `git diff --check 12dff92..1e9694c` exits 2 because every added line in `tools/windows/run.cmd` and `tools/windows/ssh-setup.ps1` is seen as trailing whitespace: CRLF was committed without repository whitespace/eol configuration that treats CR at EOL correctly. | Normalize these scripts to LF if Windows PowerShell/cmd compatibility permits, or add an explicit repository eol/whitespace policy that makes intentional CRLF pass the project's ordinary diff check. | **Open, non-blocking** |

### Task judgments

- **T-040/T-060:** the recorded STARBASE table has the expected shape: 28 baseline tests,
  observable dialog reorder and undeclared-control mutations killed, and the two-control view
  reversal surviving for the already-reviewed reason. The checked-in driver correctly
  distinguishes pytest failure from usage/internal/no-test exits. That is sufficient behavioral
  evidence for the manual run. COORD-R5 still blocks closure because the acceptance criterion
  required the current-truth documents to change and they did not. WIN-R2/R3 affect repeatability
  and the claimed harness, not the already-read raw table.
- **T-065:** the maintainer's keep-history decision is accurately recorded. All four commits in
  this boundary are authored by Sean Kottman and none adds another AI authorship trailer.
- **T-066:** creating a venv in every workflow job and using a native Windows path in
  `GITHUB_PATH` is structurally sound. The changed detector assertion also states the right
  relation—depth from the walker rather than one hop from the launcher. T066-R1 means the
  kill/reaping siblings have not actually been shown under that same shape. Independently, the
  workflow and the frozen-artifact process shape remain openly unexecuted, so correction of
  T066-R1 would leave the task Blocked on Windows runner/frozen evidence rather than Approved.
- **T-067:** removing a fixture `mkdir` from a pre-filesystem rejection path is correct. The new
  test asks the OS to create a file at the accepted budget, so raising the project constant past
  what the default Windows configuration accepts can no longer agree with itself. Approved at
  `1e9694c`.
- **T-068:** `QT_QPA_FONTDIR` is set before PySide6 is imported, is Windows-only, and honors an
  explicit caller value. The STARBASE before/after evidence is credible. The task's own
  acceptance criteria still require the runner difference to be explained and a Windows frozen
  artifact to be checked; both are explicitly open. Verdict: Blocked, not Changes requested on
  the environment fix.
- **T-069:** the reproduction and predecessor are useful, but the task says plainly that no fix
  exists. T066-R1 gives the first concrete process-shape question to answer. Verdict: Changes
  requested; do not retry or xfail the WAL error.
- **T-070:** the capability is attempted in the test's own temporary directory, its skip tells a
  Windows developer which privilege or setting is missing, and the four original tests remain
  unchanged wherever the capability exists. Approved at `1e9694c`.
- **Windows tooling:** the session-0 warning and scheduled-task design are valuable, but WIN-R1
  and WIN-R2 block approval of the new setup/transport scripts. They should be corrected before
  the tools become the unattended local-runner boundary.

### Independent verification

| Check | Result |
|---|---|
| Focused T-066/T-067/T-070 tests | **7 passed, 53 deselected in 0.09 s** |
| Full default suite | **1399 passed, 11 skipped, 2 deselected in 81.84 s** |
| `ruff check .` | Passed |
| `ruff format --check .` | **101 files already formatted** |
| `python -m mypy src` | Passed: **35 source files** |
| Configured `python -m mypy` | Passed: **78 source files** |
| Configured `python -m mypy --platform win32` | Passed: **78 source files** |
| Remote-failure harness probe | Wrapper printed `EXITCODE=1` and returned **0** |
| Exact-head workflow `30401845377` | Failed all five jobs with **zero steps**; confirms the external quota outage and supplies no workflow evidence |
| `git diff --check 12dff92..1e9694c` | **Failed** on the two CRLF Windows scripts (GIT-R2) |
| Git boundary at review start | HEAD and `origin/main` both `1e9694c`; four commits by Sean Kottman, no new AI trailer |

The first sandboxed full-suite attempt produced 15 environment failures: localhost sockets were
denied and two launch subprocesses could not write the sandboxed user cache. The identical run
outside that sandbox passed as recorded above; none was a project failure. The local `.venv`'s
dependency-owned console scripts still have T064-R1's stale shebang, so validation used its
working interpreter as `python -m ...` with this checkout's `src` on `PYTHONPATH`; the import
resolved to this checkout.

### Final disposition

T-067 and T-070 are **Approved at `1e9694c`**. T-068 is **Blocked** on its already-disclosed
runner/frozen questions.

T-066 and T-069 are **Changes requested** on T066-R1. The focused correction should cover the
launcher/interpreter distinction, its raw-Popen siblings, and T-069's deterministic predecessor
sequence; T-066 will still need actual Windows workflow and frozen evidence afterward.

T-040/T-060's manual Windows behavior evidence is accepted, but the tasks remain **Changes
requested/Blocked on COORD-R5** because their own current-truth criterion is unmet. Their ordinary
Medium review budget was already exhausted before this evidence filing; do not start another
automatic loop without the maintainer either authorizing a documentation-only focused pass or
carrying COORD-R5 into a named coordination task.

The combined boundary is **Changes requested** on WIN-R1 and WIN-R2. WIN-R3 and GIT-R2 are
non-blocking cleanup, but they should travel with the same local-runner hardening work.

## 2026-07-28 — STARBASE correction focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `1e9694c`  **Implementation head:** `8938478`
**Evidence/status follow-up included:** `ec60fe4`
**Scope:** `T066-R1`, `COORD-R5`, `WIN-R1` through `WIN-R3`, `GIT-R2`, `T-069`, and the
self-hosted `windows desktop` job introduced while the correction was in flight
**Boundary classification:** Tests, workflow, privileged developer tooling, and
documentation/coordination; no production source

`ec60fe4` landed while this re-review was running. It changes only TASKS, STATUS, and the
Windows-verification guide, and records the completed job whose status the reviewer had already
queried. It is included for evidence accuracy; every code judgment remains bounded to
`1e9694c..8938478`.

This is the focused correction pass. Per the maintainer's direction that this is the last pass,
remaining Medium-or-lower work is to be carried into the next named task rather than starting
another correction loop.

### Finding dispositions

| ID | Severity | Blocks approval | Focused re-review result | Status |
|---|---|---:|---|---|
| `T066-R1` | **Medium** | **Yes — T-066** | The measured cause is credible and important: under the Windows venv launcher, killing the returned PID killed the launcher and application but left the worker; whole-tree termination removed T-069's 4/5 predecessor failure. The correction enumerates descendants before termination, which is the right order. It still suppresses every `psutil` kill error and discards both lists returned by `wait_procs` (`test_end_to_end.py:98-108`), so `kill_the_application()` may return and reopen the database with a known survivor. The direct no-survivors probe is reported but is not a lasting assertion. The task also says the unchanged T-019 siblings “deserve the same look,” while the new self-hosted job runs only `windows_desktop`; it does not execute or record T-019's `process_tree` assertions under the venv. Consequently `ai/TASKS.md:242-248` calls this the Windows half of T-066 even though its explicit T-019 criterion at lines 204-205 remains unrun. | **Partially resolved; carry.** T-069 is resolved. The next task should make a surviving `wait_procs` result fail, retain the expected descendant set as an assertion, and run/record the T-019 process-tree cases from the Windows venv. T-066 also remains externally Blocked on the four hosted/frozen jobs. |
| `COORD-R5` | **Medium** | **Yes — coordination closure** | REQUIREMENTS, IMPLEMENTATION_PLAN, TESTING, and T-026 now agree that Windows tab order is gated. The canonical task/status structure still does not: `## In Review` says it is empty while T-066 through T-070 are In Review under `## Ready`; T-040 and T-060 are In Review under `## Blocked`; TASKS' preamble still calls T-060 Blocked; and STATUS first says T-040/T-060 are In Review, then says T-069 is unfixed and T-040 remains Blocked (`ai/STATUS.md:147-175`). These are current-truth files, not an archive, and the stale paragraphs are not labelled as superseded. | **Partially resolved; carry.** The required gate statement is corrected, so the residual is task readiness/filing rather than behavior. File a named coordination follow-up and then T-040/T-060 can close with that carry. |
| `WIN-R1` | **Medium** | **Yes — Windows setup tooling** | Existing administrator keys are now preserved and deduplicated. A newly created firewall rule is correctly Private + LocalSubnet. But the script's idempotent path looks up `sshd-tt` and does nothing when it already exists (`ssh-setup.ps1:66-76`). A machine that ran the reviewed broad `Any` rule therefore stays broad on every later run of the correction. The maintainer separately fixed STARBASE, but the checked-in “safe to run more than once” tool does not repair the unsafe state it created. | **Partially resolved; carry.** Update or recreate an existing named rule, then report/verify its effective profile and remote-address filter. |
| `WIN-R2` | **Medium** | **Yes** | Independent fake-transport probes returned **0** for remote success, **7** for remote exit 7, **124** for timeout, **125** for a missing result marker, and **126** for a run already in flight. `run.cmd` isolates a bare remote `exit` in a child `cmd` and writes the marker with the redirection before the digit. | **Resolved.** |
| `WIN-R3` | **Low** | **No** | The focus mutation driver now runs a relevant positive control first and accepts only pytest exit 1 as a kill. The guide still names the old T-056 plugin `mut_control_always_dead.py`; the actual new control is `mut_control_chain.py`. | **Functionally resolved; documentation follow-up.** |
| `GIT-R2` | **Low** | **No** | `.gitattributes` declares CRLF for `*.cmd` and `*.ps1`; `git diff --check 1e9694c..ec60fe4` is clean, and `git check-attr` reports the intended policy. | **Resolved.** |
| `RUNNER-R1` | **Medium** | **No** | The workflow comment and Windows guide say `timeout-minutes: 15` bounds time spent queued while STARBASE is offline. GitHub documents two different clocks: `timeout-minutes` is the maximum time to let a job **run**, while an unmatched self-hosted job remains queued for up to **24 hours**. The current text therefore understates this single-machine gate's outage window by almost a day. See GitHub's [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idtimeout-minutes) and [self-hosted routing](https://docs.github.com/en/actions/reference/runners/self-hosted-runners#routing-precedence-for-self-hosted-runners). | **Open, non-blocking; carry with runner documentation.** |

### Task judgments

- **T-069:** **Approved at `8938478`.** The failure's exact predecessor is retained, reverting
  the whole-tree termination restores the high failure rate, and five clean file-level runs after
  the correction are strong evidence against the prior 4/5 rate. The helper-strengthening residue
  belongs to T-066's evidence contract, not to the now-explained WAL failure.
- **T-066:** **Blocked.** One real Windows venv job is now green, but it is the 28-test desktop
  slice, not the T-019 process-tree suite. Four hosted jobs—including both frozen jobs—failed
  before step 1 because of quota. The deeper T-019 shape and frozen-artifact shape therefore
  remain unverified exactly where the acceptance criteria require evidence, and T066-R1 still
  permits an unreported survivor.
- **T-040/T-060:** their behavior and manual mutation evidence are accepted. The self-hosted
  desktop job is now a repeatable normal-run gate: job `90432207805` passed all 28 selected tests
  under the real Windows plugin. Their mutation executions remain correctly described as manual.
  They are **Blocked only on carrying COORD-R5's remaining filing/current-truth cleanup into a
  named follow-up**, after which they may be filed Approved with follow-up without another
  behavioral review.
- **T-068:** unchanged: **Blocked** on the disclosed runner/frozen explanation.
- **Windows tooling:** WIN-R2 is approved. The setup script remains **Changes requested** on
  WIN-R1; WIN-R3 and RUNNER-R1 are non-blocking documentation carries.

### Independent verification

| Check | Result |
|---|---|
| Full default suite | **1399 passed, 11 skipped, 2 deselected in 81.15 s** |
| `ruff check .` | Passed |
| `ruff format --check .` | **102 files already formatted** |
| `python -m mypy src` | Passed: **35 source files** |
| Configured `python -m mypy` | Passed: **78 source files** |
| Configured `python -m mypy --platform win32` | Passed: **78 source files** |
| WIN-R2 fake transport | Exit codes **0 / 7 / 124 / 125 / 126** for success / remote failure / timeout / missing result / busy |
| Self-hosted workflow job | Run `30405803368`, job `90432207805`: **28 passed, 1410 deselected in 14.33 s**, Windows-platform mypy passed, Python 3.14.6 |
| Same workflow's hosted jobs | Four failures with **zero steps**, consistent with exhausted hosted quota; the workflow as a whole is red |
| `git diff --check 1e9694c..ec60fe4` | Clean |
| Git boundary | `main` and `origin/main` at `ec60fe4`; all four included commits authored by Sean Kottman, no AI authorship trailer |

### Final disposition

T-069 is **Approved**. The self-hosted Windows desktop gate is operational and its normal run is
accepted evidence for T-040/T-060.

The combined boundary is **Blocked / Changes requested** on the remaining parts of T066-R1,
COORD-R5, and WIN-R1. Under the maintainer's last-pass direction, do not begin a further automatic
correction round: Claude should file a named next task carrying those three items, plus the
non-blocking WIN-R3 and RUNNER-R1 documentation corrections. T-040/T-060 may then close with that
follow-up; T-066 remains Blocked until its process-tree and hosted/frozen evidence exists.

## 2026-07-28 — T-071 icon scale review

**Reviewer:** Codex (Reviewer)
**Base:** `fd99229`  **Head:** `3327fd3`
**Scope:** T-071's regenerated PNG/ICO assets, authoring script, and task/status evidence
**Boundary classification:** Static assets, developer authoring tool, and coordination
documentation; no production source
**Verdict:** **Approved**

### Findings

None.

### Independent verification

| Check | Result |
|---|---|
| Renderer reproduction with Python/Pillow 12.3.0 | All eight PNGs and `icon.ico` reproduced byte-for-byte |
| `.ico` payload audit | Seven valid PNG-compressed frames; every payload exactly matches its standalone PNG |
| Visible bounds | Master crop is 496×547 at alpha > 8; rendered padding is centred within one pixel at every size |
| Master preservation | `icon.png` is unchanged across the review boundary |
| Focused resource/UI tests | **23 passed** |
| `ruff check tools/icons/render_icons.py` | Passed |
| `ruff format --check tools/icons/render_icons.py` | **1 file already formatted** |
| `python -m mypy src` | Passed: **35 source files** |
| `git diff --check fd99229..3327fd3` | Passed |
| Git boundary | One implementation commit, authored by Sean Kottman |

The renderer's output matches the checked-in assets exactly, including the hand-written ICO
directory and each embedded frame. The delivered sizes and frame sets remain those pinned by
T-022, the visible mark occupies the intended near-full canvas, and its opposing padding differs
by no more than one pixel from integer rounding. The new authoring script is a proportionate
part of this correction: it records the threshold and scaling choices that were previously lost,
without adding Pillow to the product or its development gate.

### Final disposition

T-071 is **Approved at `3327fd3`**. The known-unverified Windows taskbar/title-bar appearance is
accurately disclosed and does not block this Linux-reported cosmetic correction.

## 2026-07-29 — T-064 and T-072 carry review

**Reviewer:** Codex (Reviewer)
**Base:** `3327fd3`  **Head:** `f20a9c8`
**Scope:** T-064's developer-environment repair; T-072's COORD-R5, T066-R1, WIN-R3 and
RUNNER-R1 work; the Windows-venv process-tree workflow step and its first evidence run
**Boundary classification:** Developer environment, integration-test helper, workflow, and
documentation/coordination; no production source
**Verdict by task:** T-064 **Approved**; COORD-R5, WIN-R3 and RUNNER-R1 **Resolved**;
T066-R1 **Changes requested**; T-072 remains **In Progress / Changes requested**

The checkout advanced to `df2b106` while this review was running, and `ai/TASKS.md` then acquired
an uncommitted edit. Both are excluded. The later commit records the maintainer's OPS-005
decision about T-056/T-068; this review judges the decision question as it stood at `f20a9c8`,
not that later implementation.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T072-R1` | **Medium** | **Yes — T066-R1's process-tree half** | `kill_the_application()` treats `len(doomed) > 1` as proof that its recursive walk found the expected tree (`tests/integration/test_end_to_end.py:112-120`). Under the documented Windows venv shape, the launcher plus application interpreter already make that count two; the worker may be absent and the assertion still passes. A deterministic mutation of the exact function reduced `children(recursive=True)` to the direct child: `len(doomed) == 2`, the helper returned successfully, and the omitted worker remained alive. By contrast, a mutation that left a process already present in `doomed` alive was correctly killed by the `assert not alive` check. The new assertion therefore proves termination of whatever the walk happened to return, but does not retain the expected worker set as T-072 requires. | Have `DOWNLOAD_AND_WAIT` report the application interpreter PID in its startup handshake. Start the descendant walk from that PID rather than infer identity from a count beneath the launcher; while the row is RUNNING, assert that the application has the expected worker descendant, capture that exact PID set, kill it, and assert every captured PID ended. Then run two Windows mutations: leave a captured victim alive, and omit the worker from the captured set. | **Open** |
| `T072-R2` | **Low** | **No** | T-072's status at `ai/TASKS.md:81-85` still says three carries are done, T066-R1 is unexecuted, and the T-019 run is not started. Its table at lines 153-160 and evidence at lines 191-210 say T066-R1 executed and the T-019 cases are done, leaving only WIN-R1. `ai/STATUS.md:314-332` has the same “three done/unexecuted” paragraph immediately before the completed-run paragraph. | Rewrite the live status/progress summary to four of five carries done, with WIN-R1 alone remaining. Keep the earlier unexecuted state only if it is explicitly historical. | **Open, non-blocking** |

### Task judgments

- **T-064:** Approved at `f20a9c8`. The repaired venv's bare `mypy`, `pytest`, application entry
  point, and import-location probe all resolve through this checkout without `PYTHONPATH`.
  Recreating the environment with `venv --clear` addresses dependency-owned launchers, which
  reinstalling only this project cannot. The one-sentence STARBASE correction in
  `docs/DEVELOPMENT.md` resolves a contradiction inside the file and is acceptable in this
  documentation repair; reverting it would knowingly restore a false current statement.
- **COORD-R5, WIN-R3 and RUNNER-R1:** Resolved. Task section placement matches the filed
  verdicts, the mutation guide names the control the driver actually runs, and both the workflow
  and guide distinguish a job's run-time limit from the self-hosted queue timeout.
- **Windows-venv workflow evidence:** Accepted. Run `30414186949` is at exact implementation head
  `185ea6d`; its `windows desktop` job collected all 75 tests from the two named modules and
  reported 72 passed and three POSIX-only skips. The named cancellation, killed-worker,
  grandchild-detector, and end-to-end recovery cases all passed. This proves the step selects and
  executes the intended tests under the Windows venv; it does not close T072-R1's vacuous
  expected-set assertion.
- **T-056/T-068 scope question at the reviewed head:** Recommend non-phase-blocking follow-ups,
  while keeping both tasks open. T-056 is test-only and its established error direction is a
  false alive result, so it can fail CI spuriously but cannot hide a broken reap. T-068's
  offscreen-test fix is validated on the supported machine that exhibited the empty font
  database; explaining why a hosted image did not exhibit it is diagnostic follow-up. T-056's
  mechanism is Windows-general rather than Windows-Server-specific: a terminated Windows process
  object becomes signaled and can remain valid while a handle remains open, and psutil's
  zero-timeout wait asks that signaled state directly. STARBASE's 20/20 therefore establishes
  absence of the trigger there, not correctness of the old helper.
- **T-033's “PyInstaller absent” sentence:** stale, but not a boundary finding. `git blame` places
  it at `a2966156`, well before this review base. File a separate coordination cleanup rather than
  folding it into T-064.

### Independent verification

| Check | Result |
|---|---|
| Captured-survivor deterministic mutation | **Killed** by `assert not alive`; survivor PID reported |
| Shallow-walk deterministic mutation | **Survived**; `len(doomed) == 2` while an omitted worker remained alive |
| Live STARBASE mutation attempt | **Not run** — direct transfer did not connect before timeout |
| Exact-head Actions run `30414186949` | STARBASE job green; **72 passed, 3 skipped** in the process-tree step; four hosted jobs had zero steps |
| Focused end-to-end tests | **4 passed** outside the filesystem/network sandbox |
| `mypy --platform win32` | Passed: **78 source files** |
| `ruff check .` | Passed |
| `ruff format --check .` | **103 files already formatted** |
| Bare repaired-venv launchers | `mypy`, `pytest`, `tracks-and-trails`, and import-location probe all passed without `PYTHONPATH` |
| `git diff --check 3327fd3..f20a9c8` | Passed |

The first focused end-to-end run failed three tests because the sandbox denied their loopback
HTTP server with `PermissionError: [Errno 1]`; the identical run with localhost sockets enabled
passed as recorded. That was an environment denial before project behavior, not a project
failure.

### Final disposition

T-064 is **Approved at `f20a9c8`**. COORD-R5, WIN-R3, RUNNER-R1, and the Windows-venv workflow
selection/evidence are accepted.

T066-R1 remains **Changes requested** on `T072-R1`; T-066 must not be narrowed to frozen-artifact
evidence alone until the test identifies and retains the application/worker set rather than
inferring it from `len(doomed) > 1`, and the correction is mutation-checked on Windows.

T-072 remains **In Progress / Changes requested**: `T072-R1` needs correction, `T072-R2` needs
current-truth cleanup, and WIN-R1 was already openly unfinished at the reviewed head.

## 2026-07-29 — OPS-005, T-073, and T-072 correction review

**Reviewer:** Codex (Reviewer)
**Base:** `f20a9c8`  **Head:** `dc02084`
**Scope:** OPS-005; T-073's self-hosted full Windows gate and evidence; the focused correction of
`T072-R1`/`T072-R2`; WIN-R1's firewall repair; and the T-074 filing
**Boundary classification:** Workflow, integration-test helper and mutation plugins, Windows
operator tooling, and documentation/coordination; no production source
**Verdict by task:** OPS-005 **Accepted as the maintainer's scope decision**; T-073
**Approved with a documentation follow-up**; T-074's filing **Accepted**; T072-R1
**Still open / Changes requested**; T072-R2 **Still open**; WIN-R1 **Changes requested on its
verification gate**; T-072 remains **In Progress / Changes requested**

The supplied boundary contains **seven commits, not eight**. `HEAD` and `origin/main` both
resolved to `dc02084` when the review began, and the tree was clean.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T072-R1` | **Medium** | **Yes — T066-R1's process-tree half** | The application-PID handshake fixes the old launcher/application ambiguity, but the checked-in mutations do not prove the expected worker set. `mut_tree_shallow_walk.py` returns `[]`; it does not perform the direct-child walk that produced the reviewed survivor. It therefore proves only that an entirely empty walk trips `assert workers`. `mut_tree_drop_worker.py` removes every worker *before* `kill_the_application()` receives `doomed`; Windows then calls `wait_procs(doomed)`, so `assert not alive` cannot possibly report the omitted process as the plugin says it must. The mutation survived locally, and neither mutation has run on Windows. Run `30416156751` proves the normal path executes, not that weakening it is detected. | Retain an independently obtained worker PID (for example in the child handshake or an external expected-PID set) through the kill and wait, so removing it from `doomed` cannot remove it from the assertion. Make the shallow mutation return the application's real direct children rather than none, and make the dropped-worker mutation assert against the independent set. Demonstrate both kills on Windows; a normal green run is not a substitute. | **Still open** |
| `T072-R2` | **Low** | **No** | `ai/TASKS.md`'s T-072 status block is corrected, but `ai/STATUS.md:346-364` still presents the superseded “four of five / assertions unexecuted / WIN-R1 last” state as ordinary current prose immediately after the new state. The previous review required the older reading to remain only if explicitly historical. | Mark the older block explicitly historical or replace it with the current state while preserving the superseded reading in a historical parenthetical. | **Still open, non-blocking** |
| `T072-R3` | **Medium** | **Yes — WIN-R1's evidence criterion** | The proposed Windows proof uses `New-NetFirewallRule -Name sshd-tt` to “recreate” the broad rule. On the machine this repair targets, that name already exists; the command can fail while the following script merely reapplies and reports an already-scoped rule. That produces a green-looking report without ever exercising broad-to-scoped repair. The script itself is statically plausible, but the acceptance criterion requires this exact repair path to be demonstrated. | Deliberately broaden the existing rule with `Set-NetFirewallRule -Name sshd-tt -Profile Any -RemoteAddress Any`, read it back and assert both values are `Any`, run `ssh-setup.ps1`, then assert `Private` and `LocalSubnet`. Make setup failures terminating for the evidence procedure. | **Open** |
| `COORD-R6` | **Medium** | **Yes — T-072's current-truth acceptance criterion** | The same filing class COORD-R5 was meant to close has recurred. `ai/TASKS.md:15-21` says nothing remains on the critical path and lists only a carry, runner evidence, and exit review, omitting newly filed High-priority T-074. Lines 29-30 still call T-072 and completed T-064 Ready. Lines 70-77 say In Review is genuinely empty while T-073 is marked In Review at lines 159-163 under Ready. `ai/STATUS.md:166-172` still says criterion 7 cannot move until hosted quota resets, contradicted by its T-073 account at lines 377-389. This materially misstates the live queue and release readiness. | Rewrite the opening queue and section placement from current task states, include T-074, and turn superseded status prose into explicitly historical notes. | **Open** |
| `T073-R1` | **Low** | **No** | The Windows behavior and counts are valid, but two evidence statements are not. Actions timestamps put job `90460498381` at **6 m 29 s** wall, not 3 m 40 s. The alleged two-test collection residual is also explained: Linux's JUnit has two module-level “collection skipped” cases for `tests.ui.test_windows_accessibility` and `tests.ui.test_windows_desktop`; Windows replaces those two placeholders with the 28 real desktop cases. `1412 - 2 + 28 = 1438`, exactly the recorded collection count. | Correct the wall time and replace the open arithmetic question with the JUnit identity reconciliation. Documentation Maintainer, target T-073 filing cleanup; no behavioral re-review needed. | **Open, non-blocking** |

### Task judgments

- **OPS-005:** Accepted as the maintainer's explicit scope decision. It preserves T-056 and
  T-068 as open, records that STARBASE non-reproduction does not prove the Windows-general
  helper correct, and does not pretend the decision alone satisfies the platform gate. This is
  the same non-phase-blocking disposition the prior review recommended.
- **T-073:** Approved with `T073-R1` as a documentation follow-up. The workflow retains the real
  `windows` plugin for the 28-test desktop slice, overrides to `offscreen` for the Qt baseline
  and default suite, does not provision the self-hosted machine, records ffmpeg, and allows 30
  minutes. Run `30415333608` is at exact implementation head `c41e2ef`; all fourteen functional
  steps in the STARBASE job passed, including 1388 passed, 20 skipped, and 30 deselected in the
  full suite. The overall workflow is red only because all four hosted jobs failed before
  executing steps on the billing annotation.
- **T-074:** The filing accurately preserves uncertainty. Run `30416495270` is at documentation-
  only head `454b80e`; the full suite exited 139 at the first-progress wait in
  `test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget`, with ResultPump blocked
  in `multiprocessing.Queue.get()`. The same code passed immediately before and after in runs
  `30416156751` and `30416723791`. Calling the cause unknown and excluding retry/xfail is correct.
- **T072-R1:** The production-facing test-helper shape is materially better: it handshakes the
  application interpreter PID, captures recursively before killing parents, and checks all
  processes it was handed. Approval is withheld because the correction still has no independent
  identity for a worker omitted from that handed-in set, and its mutation claims overstate what
  the assertions can observe.
- **WIN-R1:** Static review found the existing-rule branch reapplies and reads back profile,
  remote address, port, enabled state, and action; the file remains CRLF as required. Runtime
  approval is withheld because the documented broad-rule setup can fail vacuously and STARBASE
  was unreachable during review.

### Independent verification

| Check | Result |
|---|---|
| Exact-head Actions run `30415333608` | STARBASE job green; 28 desktop tests and **1388 passed, 20 skipped, 30 deselected** in the full suite |
| T072 baseline on Linux | **1 passed** |
| `mut_tree_shallow_walk` on Linux | **Killed** by the empty-descendants assertion |
| `mut_tree_drop_worker` on Linux | **Survived**, 1 passed; confirms an omitted process is outside the `wait_procs(doomed)` assertion |
| Full Linux default suite | **1399 passed, 11 skipped, 2 deselected** in 101.59 s |
| Linux/Windows JUnit identity comparison | Both contain 1408 selected test identities; Linux alone has two collection-skip placeholders for the Windows-only modules |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| `ruff check .` | Passed |
| `ruff format --check .` | **105 files already formatted** |
| `git diff --check f20a9c8..dc02084` | Passed |
| STARBASE mutation/firewall attempt | **Not run** — SSH to `192.168.68.65:22` timed out |

The first three focused test invocations were blocked before project behavior because the
filesystem/network sandbox denied creation of their loopback HTTP server. The identical
baseline and mutation runs with localhost sockets enabled produced the results above.

### Final disposition

T-073 is **Approved with follow-up at `dc02084`**; T-074's filing and OPS-005 are accepted.

T-072 remains **In Progress / Changes requested**. T072-R1 is not resolved until a Windows
mutation proves that omitting the independently identified worker fails, WIN-R1's broad-rule
repair needs a non-vacuous setup and Windows execution, and COORD-R6 must restore one current
answer about the live queue. `T072-R2` and `T073-R1` are non-blocking documentation corrections.

This was T-072's focused correction re-review. With only Medium-or-lower findings remaining, the
ordinary pass budget is exhausted; another focused pass requires the maintainer to authorize it,
accept the documented risk, change scope, or carry the work into another named follow-up.

## 2026-07-29 — T-072 second correction focused re-review

**Reviewer:** Codex (Reviewer)
**Base:** `dc02084`  **Head:** `825e3cd`
**Scope:** The five findings from the preceding review, their correction diff, OPS-006, and the
exact-head normal Windows run
**Boundary classification:** Integration-test helper and mutation plugins plus
documentation/coordination; no production source
**Verdict by task:** T072-R3 and COORD-R6 **Resolved**; T072-R1 **Still open / Changes
requested**; T072-R2 and T073-R1 **Partially corrected, still open and non-blocking**; OPS-006
**Accepted as the maintainer's scope decision**; T-072 remains **In Progress / Changes
requested**

The maintainer supplied this new review boundary after the prior pass-budget warning; this review
treats that handoff as authorization for the additional focused pass. The boundary contains three
commits. `HEAD` and `origin/main` both resolved to `825e3cd`, and the tree was clean.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T072-R1` | **Medium** | **Yes — T066-R1's process-tree half** | Separating `must_die` from `doomed` fixes the list aliasing, but the new positive control does not prove a **worker** can be detected. An instrumented run identified `must_die` as PID 46887 running `multiprocessing.resource_tracker` and PID 46889 running `multiprocessing.spawn`. With `kill_the_application()` disabled, the 30-second wait let the actual worker finish naturally; the assertion failed only on PID 46887, the resource tracker, while reporting it as a worker that still owned the database. A deterministic reviewer mutation then killed the application and tracker, deliberately omitted the actual spawn worker, and the test passed in 1.38 s. Separately, `mut_tree_shallow_walk` patches both `capture_the_doomed_tree` **and the independent oracle** `the_workers_that_must_die`; any deeper process removed from the capture is therefore removed from the check too. The control still has teeth only for “some long-lived descendant,” not for the worker identity T072-R1 requires. | Obtain the actual worker identity independently of the capture, excluding the resource tracker. Keep that worker alive longer than the assertion in the positive control—for example, block its HTTP response until cleanup—and show the failure names that PID. A capture mutation must not patch or shrink the oracle. Then run the drop-worker mutation on Windows; if the worker exits through another legitimate reap path, record that measured outcome rather than requiring a kill for its own sake. | **Still open** |
| `T072-R2` | **Low** | **No** | The superseded STATUS block is now explicitly historical, resolving the cited block. Two current statements remain stale: `ai/TASKS.md:467-475` still records the old empty-walk plugin as FAILED although the new shallow plugin survives, and `ai/STATUS.md:368-375` still says WIN-R1 is T-072's last carry while T072-R1 is open too. | Replace the old check table with the current control/shallow/drop results and make the later STATUS paragraph historical or current. | **Partially resolved, still open** |
| `T072-R3` | **Medium** | **No — correction resolved; execution remains owed** | The procedure now uses `Set-NetFirewallRule` on the existing rule, sets `$ErrorActionPreference = "Stop"`, and reads back both profile and remote address before running the repair. The two explicit `throw`s prevent an already-scoped rule from masquerading as the defective setup. | Execute the corrected procedure on Windows and retain its before/after output. | **Resolved; external evidence pending** |
| `COORD-R6` | **Medium** | **No** | The TASKS preamble now includes T-074, gives T-072/T-073/T-064 their current states, and the In Review section actually holds T-073. STATUS rewrites the hosted-quota claim and preserves its superseded reading explicitly. | None. | **Resolved** |
| `T073-R1` | **Low** | **No** | T-073's task now records the correct 6 m 29 s wall time and the exact `1412 - 2 + 28 = 1438` JUnit reconciliation. `ai/STATUS.md:388-395`, however, still says the same two tests are unexplained. | Carry the resolved JUnit explanation into STATUS or remove its duplicate count analysis. | **Partially resolved, still open** |

### Task judgments

- **T072-R1:** The structural direction is accepted: `must_die` and `doomed` are now separate
  list instances, and the final assertion retains the former. The focused evidence above prevents
  resolution because the independent list still conflates the worker with an unrelated,
  longer-lived multiprocessing helper, and the positive control is killed by that helper after
  the worker has already gone.
- **T072-R3 / WIN-R1:** The previously vacuous setup recipe is corrected. The script and its
  repair path remain runtime-unverified, as the task accurately says.
- **COORD-R6:** Resolved. The opening queue, section placement, and criterion narrative now agree
  on T-074 as the live blocker.
- **T073-R1:** The canonical task evidence is corrected, so T-073 remains Approved with a
  non-blocking STATUS cleanup.
- **OPS-006:** Accepted as the maintainer's explicit platform decision. It names the loss of
  bare-environment system-library coverage, retains the hosted Linux job, and gives the decision
  a concrete reopening condition rather than treating the developer desktop as equivalent to a
  clean image.
- **Exact-head Windows baseline:** Run `30418180639`, job `90469110274`, is green at `825e3cd`.
  The end-to-end recovery test and the T-074 crash site both passed; the full suite reported
  **1388 passed, 20 skipped, 30 deselected**. This is normal-path evidence only, not the owed
  T072 mutation or firewall execution.

### Independent verification

| Check | Result |
|---|---|
| Corrected baseline | **1 passed** |
| `mut_control_worker_survives` | **Killed**, but after 30 s only the resource tracker survived; the actual worker had exited |
| Instrumented descendant identity | Resource tracker PID 46887; actual spawn worker PID 46889 |
| Reviewer mutation omitting the actual worker | **Survived**, 1 passed in 1.38 s after the app and tracker were killed |
| `mut_tree_shallow_walk` on Linux | **Survived**, 1 passed |
| `mut_tree_drop_worker` on Linux | **Survived**, 1 passed |
| Full Linux default suite | **1399 passed, 11 skipped, 2 deselected** in 100.65 s |
| Exact-head STARBASE run `30418180639` | STARBASE job green; **1388 passed, 20 skipped, 30 deselected** in the full suite |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| `ruff check .` | Passed |
| `ruff format --check .` | **106 files already formatted** |
| `git diff --check dc02084..825e3cd` | Passed |
| Direct STARBASE mutation/firewall attempt | **Not run** — SSH to `192.168.68.65:22` timed out while its Actions runner remained reachable |

The temporary reviewer probes lived under `/tmp`; they did not modify the repository.

### Final disposition

T072-R3 and COORD-R6 are **Resolved**. OPS-006 is accepted. T-073 remains **Approved with the
non-blocking T073-R1 STATUS cleanup**.

T-072 remains **In Progress / Changes requested** on T072-R1. The new list separation is
necessary but the positive control is still killed by the resource tracker after the actual
worker exits, so it does not demonstrate the worker-specific gate. The Windows drop-worker
mutation and corrected firewall procedure are also still explicitly owed.

## 2026-07-29 — T-072 worker-oracle focused re-review

**Reviewer:** Codex (Reviewer)
**Base:** `825e3cd`  **Head:** `9802a6a`
**Scope:** T072-R1's worker oracle and positive control; the remaining T072-R2 and T073-R1
current-truth corrections
**Boundary classification:** Integration-test helper, mutation plugins, and
documentation/coordination; no production source
**Verdict by finding:** T072-R1 **Code correction accepted; remains open on Windows evidence**;
T072-R2 **Resolved**; T073-R1 **Resolved**
**Overall verdict:** No new findings. T-072 remains **In Progress / evidence pending**, not
Approved, because the Windows drop-worker mutation and WIN-R1 procedure are still owed.

The maintainer supplied this boundary in direct response to the preceding focused review; this
review treats that handoff as authorization for the additional pass. The boundary is the single
commit `9802a6a`. `HEAD` and `origin/main` both resolved to it, and the tree was clean.

### Finding dispositions

| ID | Severity | Blocks approval | Focused evidence | Status |
|---|---|---:|---|---|
| `T072-R1` | **Medium** | **Yes — external Windows evidence remains** | `the_workers_that_must_die()` now excludes command lines containing `multiprocessing.resource_tracker`, while retaining the actual spawn worker and any work-producing descendants. The end-to-end clip now needs about eight seconds to stream and the survivor wait is five seconds, so a missed worker cannot finish naturally before the assertion. The positive control failed after 6.36 s naming one PID—the actual spawn worker. The shallow plugin now changes only `capture_the_doomed_tree`, leaving the oracle recursive. The prior spare-worker mutation passed in 1.38 s after the application died, consistent with the product's parent-watch orphan guard; with the application left alive, the control proves the same worker remains active beyond the assertion. | **Correction accepted; still open until `mut_tree_drop_worker` runs on Windows** |
| `T072-R2` | **Low** | **No** | The stale old-mutation rows are removed from TASKS. STATUS preserves “WIN-R1 is the last carry” as an explicitly superseded historical statement and points to T-072's Progress table for current truth. | **Resolved** |
| `T073-R1` | **Low** | **No** | STATUS now carries the JUnit identity reconciliation—two Linux collection-skip placeholders replaced by 28 Windows desktop cases—and explicitly preserves the superseded “two unexplained” reading as history. | **Resolved** |

### Independent verification

| Check | Result |
|---|---|
| Corrected baseline | **1 passed** in 1.42 s |
| `mut_control_worker_survives` | **Killed** in 6.36 s; one surviving PID, the actual spawn worker |
| `mut_tree_shallow_walk` on Linux | **Survived**, 1 passed in 1.45 s; capture-only mutation |
| `mut_tree_drop_worker` on Linux | **Survived**, 1 passed in 1.39 s; POSIX group kill reached the worker |
| Reviewer spare-worker mutation | **Survived**, 1 passed in 1.38 s; worker exited through the parent-watch orphan guard |
| Full Linux default suite | **1399 passed, 11 skipped, 2 deselected** in 99.77 s |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| `ruff check .` | Passed |
| `ruff format --check .` | **106 files already formatted** |
| `git diff --check 825e3cd..9802a6a` | Passed |
| Exact-head Actions run `30419125646` | STARBASE job green in 6 m 7 s; **1388 passed, 20 skipped, 30 deselected** in the full suite |

The temporary spare-worker reviewer plugin remained under `/tmp`; it did not modify the
repository.

### Final disposition

The worker-oracle correction is accepted. It now identifies the work process rather than the
resource tracker, keeps the worker active past the observation window, and leaves the oracle
untouched by the shallow-capture mutation. T072-R2 and T073-R1 are Resolved.

T-072 remains **In Progress / evidence pending** for the two already-disclosed Windows actions:
run `mut_tree_drop_worker` on STARBASE and execute the corrected WIN-R1 procedure against a
deliberately broadened rule. Those are evidence gaps, not additional code findings.

## 2026-07-29 — T-074 diagnostic and Phase 1 evidence-table review

**Reviewer:** Codex (Reviewer)
**Base:** `9802a6a`  **Head:** `13138e3`
**Scope:** The T-074 Linux diagnostic and QThread-lifetime rule-out, the new Phase 1 exit-criteria
evidence table, and the T-033 blocker correction
**Boundary classification:** Documentation and review record only; no production source, tests,
workflow, or build configuration
**Verdict by work item:** T-074 diagnostic **Accepted as narrowing, not diagnosis**; Phase 1
evidence table **Changes requested**; T-033 blocker correction **Accepted with a non-blocking
current-truth follow-up**
**Overall verdict:** **Changes requested** on `P1EXIT-R1`. Phase 1 remains not exited, as the table
already says.

The boundary contains two commits. `c76ec43` records the preceding no-new-findings review;
`13138e3` adds the diagnostic, evidence table, and T-033 correction. `HEAD` and `origin/main` both
resolved to `13138e3`, and the tree was clean before this review record was appended.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R1` | **Medium** | **Yes — Phase 1's headless exit criterion** | The new table treats “Worker code runs with no display attached” as met by the static layering test and by running Qt with `QT_QPA_PLATFORM=offscreen`. Neither detaches a display from the worker. The purpose-built `test_the_worker_runs_in_a_real_spawned_process_with_no_display` does not do so either: `_spawn_target` is started with an ordinary `multiprocessing.Process` and inherits the parent environment unchanged. On this review host that test passed while `DISPLAY=:0` and `WAYLAND_DISPLAY=wayland-0` were both present. A separate reviewer run with both variables removed also passed, showing the behavior works, but the lasting gate does not create or assert the condition named by the phase criterion. | Make the spawned child run with the platform's display variables deliberately absent and assert that absence from inside the child before exercising the real worker session. On Linux, remove at least `DISPLAY` and `WAYLAND_DISPLAY`; preserve a cross-platform formulation for Windows. Mutation-check the gate with a worker-side display dependency, then cite that integration test in the table. Until then mark this criterion not met rather than substituting Qt's offscreen plugin. | **Open** |
| `P1EXIT-R2` | **Low** | **No** | The unsupported-URL row cites `test_the_extractor_message_survives_verbatim` and calls it evidence from recorded `info_dict` fixtures. That test constructs a generic `ExtractorError` for a private-video message and uses no fixture; it proves neither `UnsupportedError` classification nor the unsupported-URL UI/storage path. The relevant evidence already exists and passed: `test_subclass_ordering_is_not_swallowed_by_the_base_class` proves `UnsupportedError -> UNSUPPORTED_URL`, while `test_an_unsupported_url_shows_the_extractors_message_character_for_character` and `test_a_failed_probe_leaves_the_job_failed_and_recorded` drive a real manager/process boundary with `errors/unsupported_url.json`. The row's conclusion that this is thinner than a live yt-dlp failure remains correct. | Point the row at those classification and UI/storage tests, call the fixture a recorded **error** fixture rather than an `info_dict`, and retain the honest limitation: the child replays the recorded failure instead of obtaining it from live yt-dlp. | **Open, non-blocking — evidence-table correction** |
| `T033-R3` | **Low** | **No** | Correcting “PyInstaller is absent” to version 6.21.0 is right, and the required Windows frozen-job result remains externally blocked. The current T-033 task still says the repository cannot locally produce the collection-removal negative run, Linux frozen result, or size delta. That no longer follows: PyInstaller 6.21.0 is installed, the workflow publishes the exact local build/probe/size commands, and this review history already records a successful local PyInstaller 6.21 Linux artifact build for `T014-R3`. What cannot be produced on this host is the Windows result; what the acceptance criterion additionally demands is both named CI jobs green. | Keep T-033 Blocked, but distinguish the external Windows/exact-CI requirement from the Linux build, collection-removal mutation, and Linux size comparison that can now be gathered locally. Correct the stale “cannot produce locally” sentence in `ai/TASKS.md`. | **Open, non-blocking — T-033/current-truth follow-up** |

### T-074 judgment

The Linux result is accepted at its stated weight. The reviewer repeated the crash-site test in
forty separate pytest invocations with forty passes and ran the whole manager module once with
all 71 tests passing. This corroborates simple-repetition failure on Linux without clearing
suite-wide ordering or Windows.

The ownership rule-out is also useful. The manager fixture retains every `DownloadManager`,
drives `shutdown()` to `is_idle`, and `_release()` refuses to remove the `_Session` while its
`ResultPump` is running. The start-failure path briefly pops the session but `_unwind()` restores
any started pump to `_sessions` until it finishes. That rules out the straightforward
`session_ended -> _release -> last pump reference dropped inside run()` chain. It does not identify
the faulting object or make the intermittent access violation less open, and the task correctly
continues to say so.

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == origin/main == 13138e3`; clean tree before the review append |
| `git diff --check 9802a6a..13138e3` | Passed |
| Focused evidence tests | **6 passed**: the cited generic-message test, the actual unsupported classification/UI/storage tests, the spawned-worker test, and the T-074 crash-site test |
| T-074 crash-site repetition | **40 separate invocations passed**, no non-zero exit |
| `tests/integration/test_manager.py` | **71 passed** in 35.70 s with localhost sockets enabled |
| First sandboxed manager-module attempt | **61 passed, 10 failed** solely at `ThreadingHTTPServer` construction with sandbox `PermissionError`; rerun above with localhost access |
| Spawned worker with `DISPLAY` and `WAYLAND_DISPLAY` removed | **1 passed** |
| Normal spawned-worker environment | Test passed while `DISPLAY=:0` and `WAYLAND_DISPLAY=wayland-0` were present, proving the current test does not enforce its name |
| Local PyInstaller | **6.21.0** |

### Final disposition

T-074 remains **Ready / undiagnosed**. Its new negative evidence and narrow lifecycle rule-out are
accepted; no source correction is implied by this review.

The Phase 1 evidence table is not ready for sign-off because the headless row currently maps a
required condition to gates that never create that condition. The unsupported-URL behavior is
already covered, but its row names the wrong test and fixture class. T-033 remains Blocked for its
external Windows and exact-CI evidence; its local-evidence wording gets a non-blocking
current-truth follow-up.

## 2026-07-29 — Phase 1 evidence-table focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `13138e3`  **Head:** `f852bed`
**Scope:** Corrections for `P1EXIT-R1`, `P1EXIT-R2`, and `T033-R3`
**Boundary classification:** Integration-test addition and documentation/evidence; no production
source, workflow, dependency, or build-configuration change
**Verdict by finding:** `P1EXIT-R1` **Partially corrected, still open**; `P1EXIT-R2` **Still
open, non-blocking**; `T033-R3` **Partially corrected, still open and non-blocking**
**Overall verdict:** **Changes requested** on `P1EXIT-R1`. The ordinary initial-plus-focused
review budget is exhausted with a blocking Medium remaining.

The correction is the single commit `f852bed`. `HEAD` and `origin/main` both resolved to it, and
the tree was clean before this review record was appended.

### Finding dispositions

| ID | Severity | Blocks approval | Focused evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R1` | **Medium** | **Yes — Phase 1's headless exit criterion** | The environment half is genuinely corrected. `test_the_worker_really_runs_with_no_display_attached` launches a fresh interpreter with `DISPLAY` and `WAYLAND_DISPLAY` absent and asserts their absence inside that child. Removing `env=environment` failed independently and named both inherited values. The workload half remains split away from that condition: the scrubbed child calls only the private `_import_ytdlp()` helper and checks that it returned. It never calls `run_session`, emits or validates a protocol sequence, or completes worker work. The separate `test_the_worker_runs_in_a_real_spawned_process_with_no_display` does those things, but still starts an ordinary `multiprocessing.Process` under the inherited desktop environment and still calls that child “headless.” A display dependency introduced after yt-dlp resolution can therefore leave the claimed headless gate green. | Put the scrub and the worker session in the same observation. For example, remove the display variables before starting the existing real spawned-process test, assert their absence inside `_spawn_target`, then run and validate its real `run_session`/queue path. Mutation-check both halves: restoring the inherited environment and introducing a worker-path display dependency must each fail. Rename or correct the old test/docstring so it no longer independently claims an inherited-display child is headless. | **Still open** |
| `P1EXIT-R2` | **Low** | **No** | The row no longer mislabels an inline exception as a fixture, and `test_a_failure_reaches_the_parent_classified_and_verbatim` does exercise `run_session`, queue carriage, protocol validation, and exact message equality. It raises `GeoRestrictedError`, however, and asserts `GEO_RESTRICTED`. It never constructs `UnsupportedError` or observes `UNSUPPORTED_URL`, so it is still not evidence for the row “An unsupported URL produces a failed job.” `test_yt_dlps_bug_report_boilerplate_does_not_reach_the_user` likewise uses generic `ExtractorError`. The replacement therefore repeats the original mapping defect with a different unrelated error class. | Either inject `UnsupportedError("Unsupported URL: ...")` through the same `run_session` path and assert `UNSUPPORTED_URL` plus exact text, or cite the existing `UnsupportedError -> UNSUPPORTED_URL` classification and unsupported-URL UI/storage tests together. Retain the honest statement that no live unsupported URL is sent through yt-dlp. | **Still open, non-blocking** |
| `T033-R3` | **Low** | **No** | The local Linux positive evidence is real. The retained artifact occupies **194260 KiB** by the workflow's `du -sk` measure; an independent `--ytdlp-probe` reported version `2026.07.04` against pin `2026.7.4`, 1,751 extractors, and `youtube` from `yt_dlp.extractor.youtube`; `frozen_smoke.py` completed in about three seconds with one top-level start and no orphan. Two current-truth problems remain. First, `ai/TASKS.md:1325-1328` calls the collection-removal mutation “genuinely external,” although the same local PyInstaller build can remove line 37 of the spec and run the negative probe; T-033 is not “Blocked on Windows only” while that local acceptance proof remains undone. Second, lines 1345-1348 still say the local run is source-mode and both frozen platforms are pending, and `ai/STATUS.md:521-525` repeats the same superseded state. | Run and revert the collection-removal mutation locally, or accurately leave that local evidence pending. Then make TASKS and STATUS agree on one state: Linux frozen positive complete, Linux collection negative complete or pending, Windows frozen external. Only the Windows half is an external blocker. | **Partially resolved, still open and non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == origin/main == f852bed`; clean tree before the review append |
| `git diff --check 13138e3..f852bed` | Passed |
| New and related evidence tests | **7 passed** |
| `tests/integration/test_worker.py` | **55 passed** in 4.29 s |
| Headless positive control | Removing `env=environment` **failed** as intended, naming `DISPLAY=:0` and `WAYLAND_DISPLAY=wayland-0`; mutation restored |
| `ruff check tests/integration/test_worker.py` | Passed |
| `ruff format --check tests/integration/test_worker.py` | Passed; one file already formatted |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| Retained Linux artifact size | **194260 KiB** via `du -sk dist/tracks-and-trails` |
| Retained artifact `--ytdlp-probe` | Passed: bundled baseline `2026.07.04`, pin `2026.7.4`, 1,751 extractors, `youtube` resolved |
| Retained artifact `frozen_smoke.py` | Passed in about 3 s: child spawned, message exchanged, child reaped, one top-level start, no orphan |

### Final disposition

The correction establishes a real display-free child and a non-vacuous environment guard, but it
does not yet establish a **worker session** under that condition. `P1EXIT-R1` therefore remains a
blocking Medium finding and the Phase 1 headless criterion is not ready for sign-off.

`P1EXIT-R2` and `T033-R3` remain non-blocking corrections: the former still cites a geo-restriction
test for unsupported-URL behavior; the latter has real Linux positive frozen evidence but still
misclassifies its local negative proof as external and retains contradictory source-only text.

Under `AGENTS.md` §10, the ordinary review budget is now exhausted with a blocking Medium finding.
Another focused correction pass requires the maintainer to authorize it, accept the documented
risk, change scope, or carry it into a named follow-up.

## 2026-07-29 — Final authorized Phase 1 evidence-table correction review

**Reviewer:** Codex (Reviewer)
**Authorization:** The maintainer explicitly authorized one final pass
**Base:** `f852bed`  **Head:** `6e23d43`
**Scope:** Final corrections for `P1EXIT-R1`, `P1EXIT-R2`, and `T033-R3`, including the newly
measured T-033 collection-removal survivors
**Boundary classification:** Integration-test correction and documentation/evidence; no production
source or final build-configuration change
**Verdict by finding:** `P1EXIT-R1` **Resolved**; `P1EXIT-R2` **Resolved**; `T033-R3` **Local
evidence resolved, current-truth correction still incomplete**
**Overall verdict:** The Phase 1 evidence-table corrections are **Approved**. T-033 is **Blocked**
on `T033-R4`, a maintainer decision about its invalidated acceptance criterion, and the already
known external Windows build.

The boundary contains two commits: `c49ef96` records the preceding review, and `6e23d43` contains
the corrections and new T-033 evidence. `HEAD` and `origin/main` both resolved to `6e23d43`, and
the tree was clean before this review record was appended.

### Finding dispositions

| ID | Severity | Blocks approval | Final evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R1` | **Medium** | **Yes — resolved** | The display condition and worker workload are now one observation. The parent removes `DISPLAY` and `WAYLAND_DISPLAY` before `spawn`; `_spawn_target` checks their absence inside that child; the same child executes `run_session`; and the parent validates the real protocol sequence and `Probed` outcome. Independently removing the scrub failed with the child's inherited-display assertion and both values. Independently adding a post-guard `os.environ["DISPLAY"]` dependency failed with `KeyError: 'DISPLAY'` from the work process. | None. | **Resolved** |
| `P1EXIT-R2` | **Low** | **No** | `test_an_unsupported_url_fails_the_job_with_the_extractors_own_message` now raises the correct `UnsupportedError` through `run_session`, validates the sequence, and asserts both `UNSUPPORTED_URL` and the exact generated message. An independent mutation removing the `UnsupportedError` mapping failed with the observed kind `EXTRACTOR_ERROR`, while preserving the message, exactly isolating the subclass-ordering gate. The table accurately retains the limitation that yt-dlp URL recognition itself is injected rather than live. | None. | **Resolved** |
| `T033-R3` | **Low** | **No — superseded by the substantive T033-R4 blocker** | The requested local evidence was produced: baseline and both collection-removal builds completed, their distinct sizes prove the mutations applied, and both negative probes survived. The task now records that result and marks the acceptance criterion unachievable as written. Current-truth cleanup is incomplete: the T-033 status still says “Blocked on Windows only” while a maintainer acceptance decision is also owed; its Scope still states the now-disproved static-analysis premise; and `ai/STATUS.md:530-537,562-572` still says the collection negative remains to run and that hosted jobs are the only constraint. | Rewrite TASKS and STATUS around the finding below: Linux positive and negative builds complete; submodule collection redundant for this pin; package data remains load-bearing but ungated; Windows external; acceptance-criterion decision required. | **Evidence resolved; documentation follow-up remains** |
| `T033-R4` | **High** | **Yes — T-033** | The conclusion “neither collection line is necessary” does not follow from the surviving probes. The independent `collect_submodules -> []` build also passed, and the pinned `_extractors.py` really does contain 928 static relative imports, so the explicit submodule collection is redundant for this pin. The data mutation is different: removing `collect_data_files("yt_dlp")` produced a passing probe **while deleting all three yt-dlp YouTube solver assets present in the baseline artifact**: `yt.solver.core.js`, `yt.solver.deno.lib.js`, and `yt.solver.bun.lib.js`. yt-dlp loads these with `importlib.resources` through `vendor.load_script`; `EJSBaseJCP._builtin_source` uses `yt.solver.core.js`, and the Deno/Bun providers use the other two. The current probe only instantiates `YoutubeIE` and checks its URL predicate, so it never touches this runtime data. The mutation survival therefore proves the frozen gate is blind to package-data loss, not that the data line is dead. The causal record is also incomplete: PyInstaller processed a package-supplied `yt_dlp/__pyinstaller/hook-yt_dlp.py` through the `pyinstaller40` entry point, contrary to the claim that no yt-dlp hook exists. That hook does not collect these three assets, so it does not rescue the data mutant. | Keep `collect_data_files("yt_dlp")`. Extend the frozen probe to load at least the shipped built-in core solver through yt-dlp's real `vendor.load_script` path and verify its expected hash; then removing the data collection must fail. Decide separately whether `collect_submodules` stays as explicit future-pin insurance or is removed as redundant for the current pin. Replace the impossible blanket negative criterion with those two distinct decisions, and re-evaluate them whenever the yt-dlp pin changes. | **Open — T-033 Blocked pending maintainer decision and correction** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == origin/main == 6e23d43`; clean tree before the review append |
| `git diff --check f852bed..6e23d43` | Passed |
| Corrected Phase 1 tests | **2 passed** |
| Full `tests/integration/test_worker.py` | **56 passed** in 4.47 s |
| Headless scrub mutation | **Killed**: child exited 1 and named inherited `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0` |
| Headless workload mutation | **Killed**: child exited 1 with `KeyError: 'DISPLAY'` after the headless guard |
| Unsupported mapping mutation | **Killed**: expected `UNSUPPORTED_URL`, observed `EXTRACTOR_ERROR` |
| `ruff check` / `ruff format --check` on changed test | Passed; one file already formatted |
| Bare `mypy` | Passed: **78 source files** |
| Bare `mypy --platform win32` | Passed: **78 source files** |
| Maintainer-reported full suite | **1401 passed** |
| Baseline retained artifact | **194260 KiB**; yt-dlp probe and frozen spawn/reap smoke passed |
| Independent submodule-removal build | **192164 KiB**; probe still passed with 1,751 extractors and concrete `YoutubeIE` |
| Independent data-removal build | **194076 KiB**; probe still passed, but all three baseline `yt.solver*.js` assets were absent |
| Pinned extractor graph | `_extractors.py` contains **928** static `from .` imports |
| PyInstaller hook discovery | Processed `yt_dlp/__pyinstaller/hook-yt_dlp.py`; package entry point is `pyinstaller40: hook-dirs = yt_dlp.__pyinstaller:get_hook_dirs` |

Both temporary spec mutations were reverted. The independent artifacts and the unsupported-error
pytest plugin remain under `/tmp`; no build or production file in the repository was changed.

### Final disposition

`P1EXIT-R1` and `P1EXIT-R2` are **Resolved**. The Phase 1 evidence table now maps both criteria to
tests that exercise the claimed condition, and this final authorized pass introduces no new Phase
1 blocker.

T-033 is **Blocked**, not Approved and not “Windows only.” Its Linux artifact contains a usable
extractor and its collection-removal results are now known, but those results split the two spec
lines: submodule collection is redundant for the pin; data collection ships runtime YouTube
solver assets the probe cannot see. The maintainer must revise the impossible acceptance criterion
and decide the submodule line's defense-in-depth policy; the data line should remain and gain a
resource-aware frozen gate. Windows evidence remains externally pending.

Per the maintainer's instruction, this is the last review pass. No further automatic correction
review will be initiated.

## 2026-07-29 — T-073, T-075, and T-076 review

**Reviewer:** Codex (Reviewer)
**Boundaries:** T-073 `df2b106..c41e2ef`, with its evidence correction through `9802a6a`;
T-075 `26c1d4e..7515ca3`; T-076 `7515ca3..77b7165`
**Concurrent-work exclusion:** Later T-077 coordination and test commits were not part of the
review boundary. They do not change the T-075 or T-076 production code.
**Verdict by task:** T-073 **Approved**; T-075 **Changes requested**; T-076 **Changes
requested**

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T075-R1` | **Critical** | **Yes** | `DownloadManager.retarget` reads the store and invokes `then` immediately when the visible request already equals the requested one (`manager.py:839-848`). `PersistentJobStore.get` deliberately exposes the newest in-flight revision, so this equality does **not** establish durability or successful settlement. A deterministic deferred-write probe submitted `retarget(old -> new, then=start)` twice. The second call saw the first in-flight `new` revision and reserved a start immediately; the first write was then failed; the queued start settled against the durable `old` request and spawned it. The observed final row was `RUNNING` with `old-video`, and the spawn event carried `old-video`. The same fast path also skips the `RETARGETABLE` status check. This directly falsifies the task's promise that a failed request write starts nothing and recreates the Critical defect: silently downloading something other than the user's displayed choice. Existing tests use a synchronous store and do not exercise a failed in-flight retarget or two rapid Add actions. | Put the equality/no-write decision inside the job's per-job chain. When that step reaches the front, re-read the settled candidate, enforce `RETARGETABLE`, and invoke `then` only if the requested value is already durable or its replacement write succeeds. Add a deferred write-through regression reproducing two rapid retarget/Add calls with the first write failed; assert no reservation, session, or spawn and that the durable request remains unchanged. Audit other same-value fast paths for the same chain bypass. | **Open** |
| `T076-R1` | **Medium** | **Yes** | The requested control was MP3-only, but every gate uses `CONVERTING_AUDIO_CODECS`: `with_audio_quality` accepts every converting codec (`presets.py:205-226`), `selected_preset` applies the selected MP3 bitrate to each of them (`add_dialog.py:634-645`), and the control is enabled for each (`add_dialog.py:1219-1222`). An offscreen probe supplied a valid FLAC preset through `AddUrlDialog(presets=...)`; the control named **MP3 bitrate** was enabled, the selected preset became FLAC at quality `192`, and the display read `192 kbps FLAC`. FLAC, WAV, ALAC, and the other converting codecs do not use an MP3 bitrate in the sense this task exposes. Built-in-only tests miss the defect because MP3 is presently the only built-in converting preset. This violates the task's explicit “enabled only when the selected preset converts to MP3” scope and its refusal criterion. | Gate the helper, selected-preset derivation, display, and widget enablement on `AudioCodec.MP3`, not the general converting-codec set. Add a non-MP3 converting preset (at least FLAC) to the helper and dialog tests, asserting refusal and a disabled control. | **Open** |
| `T076-R2` | **Low** | **No** | The implementation offers the requested five values in the requested order and defaults to 192, but no test asserts that closed list or its default. More importantly, the persistence test changes bitrate without probing, while T-075 established that the historically failing user path is probe, change the choice, then Add. A regression that preserves the probed request's old `audio_quality` could pass the current T-075 test (which expects default 192) and the current T-076 test (which never probes). | In the T076-R1 correction, assert the exact ordered values and default, then cover probe → choose MP3 → choose 320 → Add and inspect the durable request. | **Open, non-blocking; target T-076 correction** |

### Independent verification

| Check | Result |
|---|---|
| T-073 prior finding history | `T073-R1` was independently resolved at `9802a6a`; no new evidence reopens it |
| T-073 Windows evidence | Run `30415333608`, STARBASE job `90460498381`: all 14 functional steps green, 28 desktop tests, full suite **1388 passed, 20 skipped, 30 deselected**, 6 m 29 s wall |
| `git diff --check` for T-075 and T-076 boundaries | Passed |
| Commit authorship / trailers | Sean Kottman; no AI author or co-author trailer |
| `ruff check .` at `77b7165` | Passed |
| `ruff format --check .` at `77b7165` | Passed: **106 files** already formatted |
| `mypy src` at `77b7165` | Passed: **35 source files** |
| Configured `mypy` / `mypy --platform win32` at `77b7165` | Passed: **78 files** in each scope |
| Focused preset and Add-dialog tests at `77b7165` | **176 passed** |
| Full suite at `77b7165` | **1406 passed, 11 skipped, 2 deselected** |
| T-075 deferred-write probe | Reproduced the stale-request spawn described in `T075-R1` |
| T-076 non-MP3 codec probe | Reproduced an enabled “MP3 bitrate” control and `192 kbps FLAC` result |
| Later unchanged-code Windows evidence | STARBASE run `30428815294`, job `90501143125`: desktop **30 passed, 1417 deselected**; full suite **1395 passed, 20 skipped, 32 deselected** |

### Final disposition

T-073 remains **Approved**. Its only review finding was a Low evidence-accounting correction,
and that correction was independently resolved. No new evidence justifies revisiting settled
ground.

T-075 is **Changes requested** on `T075-R1`. Its ordinary probe/change/Add path works, but the
same-value shortcut executes an effect based on an in-flight view rather than a durable revision.
Under write failure and a repeated Add action, it can still silently start the request selected
before probing.

T-076 is **Changes requested** on `T076-R1`, and it also depends on the unresolved Critical
T-075 path used to persist a post-probe bitrate change. Its MP3 control currently accepts every
converting codec. `T076-R2` is non-blocking test hardening and should be included in the focused
correction rather than opening a separate review loop.

## 2026-07-29 — T-075 through T-077 and T-072/T-074 range review

**Reviewer:** Codex (Reviewer)
**Base:** `26c1d4e`  **Head:** `71ca6dc`
**Scope:** T-075, T-076, T-077, and the T-072/T-074 evidence in the five-commit range
**Concurrent-work exclusion:** `main` advanced after the pinned head with Phase 2 task
coordination only; that later work was excluded.
**Verdict by task:** T-075 **Changes requested**; T-076 **Changes requested**; T-077
**Changes requested**; T-074 **remains Ready and blocks Phase 1 verification**; T072-R1
**Resolved**, with T-072 still In Progress on WIN-R1
**Overall verdict:** **Changes requested**

The T-075 and T-076 implementation heads and findings are identical to the immediately preceding
independent review, which this range commits unchanged. They are not duplicated below:
`T075-R1` remains Critical and blocking; `T076-R1` remains Medium and blocking; `T076-R2`
remains Low and non-blocking.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T077-R1` | **High** | **Yes — T-077** | T-077's acceptance criterion still says **each built-in preset** completes against the local server and has its resulting file inspected. The implementation executes only three of five. `Best video up to 1080p (MP4)` and `Video with embedded subtitles` are merely named in `UNCOVERABLE_BY_THIS_FIXTURE`; naming an untested case is honest accounting, not evidence that it works. The stated impossibility belongs only to the current direct-file fixture: the local server can instead expose real format metadata and a real subtitle resource without using the public network. The gate is also not mechanically exhaustive: `CONVERTING_PRESETS` and `UNCOVERABLE_BY_THIS_FIXTURE` are two hand-maintained lists, and no assertion derives the built-in set and proves their exact union, so deleting a row or adding a preset would remain green. An independent enumeration confirmed that only **3/5** built-ins execute today. This is the core acceptance criterion of a High task, not a non-blocking coverage note. | Exercise the remaining two presets with network-free fixtures that provide the facts they need, and derive an exact coverage assertion from `BUILT_IN_PRESETS`. Alternatively, obtain an explicit maintainer scope change and file named blocking follow-ups for the two missing user-visible options; the task cannot narrow its own acceptance criterion by recording the gap. | **Open** |
| `T074-R1` | **High** | **Yes — Phase 1 verification** | The 12 clean STARBASE iterations are useful evidence against the original 25% anecdote, but they do not diagnose or clear the access violation. The four original observations and the repeat batch are not one controlled population: between them the manager and the full-suite composition changed materially, including new integration tests. Even if pooled, `1/16` is only the observed aggregate point estimate after one event, not evidence that the true rate can only be lower; a single green run is common under both a 25% and a 6.25% failure probability. The task's substantive acceptance criteria remain unmet: the crash was not deliberately reproduced, the faulting object is unknown, product pump versus harness is unresolved, and there is no correction mutation. Because the only observed native crash is in ordinary `ResultPump` delivery on the exact Windows architecture path Phase 1 exists to prove, the uncertainty cannot be resolved in favor of product safety. | Keep T-074 High and keep the Windows/Phase 1 criterion unverified until the trigger and faulting object are identified or the failure is affirmatively classified as harness-only. Report the clean batch as `0/12 at ea53c71`; do not promote samples from changed heads into a stable “1 in 16” rate. A downgrade or risk acceptance requires the maintainer's explicit decision. | **Open** |
| `COORD-R7` | **Medium** | **Yes — Phase 1 exit review** | Current-truth documents disagree with the evidence at this head. `ai/IMPLEMENTATION_PLAN.md:161-163` and `ai/STATUS.md:357-366,449-450` still say T-074 is roughly one in four; `ai/STATUS.md:338-345` says its repeat workflow has not run. `ai/STATUS.md:368-377` still says the Windows drop-worker mutation is owed. Inside T-072 itself, the opening first says WIN-R1 is the sole remaining item, then says both WIN-R1 and `mut_tree_drop_worker` remain (`ai/TASKS.md:669-680`). The checked-in mutation's module docstring also still says the captured set “has to be complete” on Windows (`tools/windows/mutations/mut_tree_drop_worker.py:11-15`), contradicted by the result the same commit records. These are not harmless historical statements: they are current assertions about the evidence and blocker set for the pending exit review. | Rewrite current truth around one state: T072-R1 resolved through a legitimate independent reap path; WIN-R1 remains; T-074 has one historical crash and a separate 0/12 batch but remains unclassified and blocking. Preserve superseded readings explicitly where their history matters. Correct the mutation documentation to describe the observed watchdog/containment outcome. | **Open** |

### T072-R1 disposition

The Windows execution supplies exactly the evidence the prior review requested. The mutation
applied—the handed list fell from three processes to two and omitted the worker. The independent
worker oracle remained intact. The test passed because the application died and the product's
parent-watchdog/containment path removed the worker; the positive control that killed nothing
failed and named that same worker.

That is a legitimate reap path, not a vacuous assertion, and the prior review explicitly allowed
this measured outcome. `T072-R1` is therefore **Resolved**. The completeness of the helper's
captured list is not independently guaranteed, but it is not the product invariant: the invariant
is that no work-producing descendant survives, and the independent oracle observes that result.
T-072 remains In Progress only for the separate WIN-R1 firewall verification.

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | Reviewed `26c1d4e..71ca6dc`; later Phase 2 coordination excluded |
| `git diff --check 26c1d4e..71ca6dc` | Passed |
| Authorship / trailers | Sean Kottman throughout; no AI author or co-author trailer |
| T-077 generated-media cases | **3 passed, 4 deselected** in 2.83 s |
| Built-in coverage enumeration | **3 executed, 2 named-only; 3/5 actual file coverage** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed: **106 files** already formatted |
| `mypy src` | Passed: **35 source files** |
| Configured `mypy` / `mypy --platform win32` | Passed: **78 files** in each scope |
| Full local suite at the reviewed code state | **1409 passed, 11 skipped, 2 deselected** in 86.75 s |
| Maintainer-reported STARBASE T-074 batch | **12/12 clean** at `ea53c71`; no reproduction |
| Maintainer-reported T072-R1 Windows mutation | Drop-worker survivor applied and passed; kill-nothing control failed naming the worker |

### Final disposition

T-075 and T-076 retain the findings already filed immediately above this review. Nothing in the
larger range corrects them.

T-077 establishes valuable end-to-end evidence for best video, MP3 at 320 kbps, and original
audio, but it does not meet its five-preset acceptance criterion and cannot be approved at 3/5.

T-074's clean batch narrows the anecdote but does not settle the cause or the release consequence.
The Phase 1 Windows criterion remains **not verified** while a possible product-side native crash
on its defining message-pump path is unexplained.

T072-R1 is **Resolved**. T-072 remains open only on WIN-R1, plus the current-truth cleanup in
`COORD-R7`.

## 2026-07-29 — T-075 through T-077 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Original review head:** `71ca6dc`
**Correction boundary:** `70c96e9..0cd6321`
**Scope:** Focused verification of `T075-R1`, `T076-R1`, `T077-R1`, `T074-R1`, and
`COORD-R7`; disposition of the existing non-blocking `T076-R2`
**Concurrent-work exclusion:** The two intervening Phase 2 planning commits were not reviewed.
**Verdict by task:** T-075 **Approved**; T-076 **Approved with follow-up T-089**; T-077
**Approved**; T-074 remains **Ready and blocking Phase 1**; T-072 remains **In Progress on
WIN-R1**
**Overall verdict:** **Blocked on COORD-R7 pending maintainer direction**

### Finding dispositions

| ID | Severity | Blocks approval | Independent evidence | Status |
|---|---|---:|---|---|
| `T075-R1` | **Critical** | **Yes — resolved** | The equality decision now executes inside the per-job chain against the settled candidate. `UNCHANGED` distinguishes a successful no-write result from a declined transition and runs the successor without adding a redundant READY revision. The new overlaying held store reproduces the real store's in-flight view. The regression passed normally. Independently restoring the pre-chain shortcut failed immediately: the second successor observed durable selector `best` before any write landed. | **Resolved** |
| `T076-R1` | **Medium** | **Yes — resolved** | The helper, selected-preset derivation, display, and enablement now all require `AudioCodec.MP3`. The unit test rejects all eight other enum members. An independent offscreen FLAC dialog probe observed `enabled=False`, preserved the FLAC preset exactly, and displayed `Format selector: bestaudio/best` with no bitrate. | **Resolved** |
| `T076-R2` | **Low** | **No** | The correction adds production-derived coverage over `MP3_BITRATES`, but still does not transcribe the exact ordered five values/default or exercise Probe → MP3 → 320 → Add against the durable request. The dialog also lacks a non-MP3 converting-preset regression even though the corrected behavior is independently verified. | **Open, non-blocking — carried to T-089** |
| `T077-R1` | **High** | **Yes — resolved** | The local HLS fixture supplies real format metadata and a real VTT subtitle group. All five built-in presets execute, the two formerly excluded cases inspect the promised format/subtitle outcome, and a separate equality asserts the table's names exactly match `BUILT_IN_PRESETS`. All six focused tests passed. Independently removing `FFmpegEmbedSubtitle` failed the subtitle case with only video/audio streams observed. | **Resolved** |
| `T074-R1` | **High** | **Yes — resolved as a review finding; T-074 remains blocking** | TASKS, STATUS, and IMPLEMENTATION_PLAN now record `0/12 at ea53c71` as a clean batch rather than a stable rate, preserve the different-head limitation, and keep the unexplained ordinary-ResultPump access violation as a Phase 1 blocker requiring explicit maintainer action to downgrade. | **Resolved** |
| `COORD-R7` | **Medium** | **Yes — Phase 1 exit review** | Most cited current-truth blocks and the mutation docstring are corrected, but two live contradictions remain in canonical TASKS. The start-here preamble still says T-074 crashes “roughly one run in four” and says both T066-R1 and WIN-R1 remain open (`ai/TASKS.md:20-26`). T-072's opening first says WIN-R1 is its sole remaining item, then still says two things are owed, including the already executed drop-worker mutation (`ai/TASKS.md:755-770`). These are the exact blocker/rate claims this finding required the batch to reconcile. | **Partially resolved; still open and blocking** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == 0cd6321`; correction commit isolated from preceding Phase 2 planning |
| `git diff --check 70c96e9..0cd6321` | Passed |
| T075-R1 regression | **1 passed** |
| Restored pre-chain shortcut mutation | **Killed**: successor ran with durable selector `best` before any write landed |
| T-076 focused unit tests | **14 passed** |
| T-076 existing UI tests | **4 passed** |
| Independent FLAC dialog probe | Disabled control; unchanged FLAC preset; no bitrate displayed |
| T-077 complete preset gate | **6 passed** |
| Removed subtitle-embedding mutation | **Killed**: observed video/audio, expected video/audio/subtitle |
| `ruff check .` / `ruff format --check .` | Passed; **106 files** already formatted |
| `mypy src` | Passed: **35 source files** |
| Configured `mypy` / `mypy --platform win32` | Passed: **78 files** in each scope |
| Full local suite | **1427 passed, 11 skipped, 2 deselected** in 90.54 s |

Both temporary source mutations were reverted, and the production/source tree matches
`0cd6321`.

### Final disposition

The three implementation corrections are approved. T-075's Critical durability invariant is now
sequenced by the same per-job chain as every other transition. T-076 is behaviorally correct and
approved with its remaining Low evidence work filed as T-089. T-077 now executes and inspects all
five user-visible presets, including real subtitle embedding.

T074-R1 is resolved because the project now preserves the uncertainty correctly; the underlying
T-074 crash deliberately remains a High Phase 1 blocker.

COORD-R7 is not resolved. This was the ordinary focused correction re-review, so the §10 review
budget is exhausted with only a blocking Medium finding remaining. No further automatic pass is
authorized. The maintainer must choose whether to authorize one final documentation-only pass,
accept the documented contradiction, change scope, or carry COORD-R7 into a named follow-up.

## 2026-07-29 — COORD-R7 authorized final documentation re-review

**Reviewer:** Codex (Reviewer)
**Authorization:** The maintainer explicitly authorized one final documentation-only pass
**Prior blocked head:** `0cd6321`
**Review-record commit:** `05182e4`
**Correction boundary:** `05182e4..7c78c7e`
**Scope:** The two live TASKS contradictions left by COORD-R7
**Verdict:** **Approved — COORD-R7 Resolved**

### Finding disposition

| ID | Severity | Blocks approval | Independent evidence | Status |
|---|---|---:|---|---|
| `COORD-R7` | **Medium** | **Yes — resolved** | The current preamble now records one native crash, the separate `0/12 at ea53c71` batch, no inferred rate, and the still-blocking product-versus-harness uncertainty. Its T-072 bullet marks T072-R1 resolved and names WIN-R1 as the sole remainder. T-072's own opening now states that same single remainder once, removes the attached stale tail that claimed two items, and explicitly preserves how that contradiction was introduced. Searches for the superseded rate, two-open-items language, and owed mutation now return only passages that identify themselves as historical. | **Resolved** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `HEAD == 7c78c7e`; correction isolated as one documentation-only commit |
| Changed correction surface | `ai/TASKS.md` only |
| `git diff --check 05182e4..7c78c7e` | Passed |
| Authorship / trailers | Sean Kottman; no AI author or co-author trailer |
| Current preamble | One crash; `0/12` separate; no rate; T072-R1 resolved; WIN-R1 sole remainder |
| Current T-072 opening | WIN-R1 sole remainder; no attached second owed-item claim |
| Superseded-wording search | Remaining matches are explicitly historical |

No tests were run for this documentation-only correction, as permitted by `AGENTS.md` §8.

### Final disposition

COORD-R7 is **Resolved**. The range review is no longer blocked by coordination-file
contradictions. T-075 and T-077 remain Approved; T-076 remains Approved with non-blocking T-089;
T072-R1 remains resolved with WIN-R1 outstanding; and T-074 remains the deliberately recorded
High blocker on Phase 1 verification.

## 2026-07-29 — T-074 implementation review

**Reviewer:** Codex (Reviewer)
**Base:** `7c78c7e`  **Head:** `66e96d5`
**Scope:** T-074's diagnostic narrowing, logging-listener correction, regression, evidence, and
Phase 1 disposition
**Concurrent-work exclusion:** `main` advanced after the pinned implementation head with
`b4b67de` and `68eb7b6`, both TASKS-only coordination commits. They were inspected only to check
the current T-074 placement; neither changes the source or regression under review.
**Verdict:** **Changes requested — T-074 and the Phase 1 Windows criterion remain blocked**

The correction proves one important fact: for the most recently stopped listener, when it can
drain within five seconds, registering the wait after multiprocessing creates the queue prevents
multiprocessing from closing the pipe first. Moving that registration back to import time failed
the new regression in **6/6** independent mutation runs with the expected queue-read exception.

It does not yet establish the lifecycle invariant it claims, and the evidence does not identify
the historical access violation as this race.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T074-R2` | **High** | **Yes — T-074** | `worker_log_queue()` registers one `_wait_at_exit` callback per queue, but the callback captures neither that queue nor its listener thread. Every callback later reads the single mutable `_stopping` slot, and `stop_listening_for_worker_logs()` overwrites that slot on the next lifecycle. A deterministic two-lifecycle probe held the first listener in a handler, stopped it, created and stopped a second listener, and confirmed the second was gone. At interpreter exit every T-074 callback waited for that same second thread; multiprocessing closed the first queue while its untracked listener remained live, producing `Exception in thread Thread-1 (_monitor)` and `OSError: handle is closed`. Successive process-wide listener lifecycles are supported explicitly by this module and occur in the integration process, so the callback cannot protect only the newest one. | Give each registered exit action ownership of the listener/queue lifecycle it was created for, or maintain a collection of every listener still alive. Add a subprocess regression with two stopped lifecycles that fails if either listener reads after its queue is finalized. | **Open** |
| `T074-R3` | **High** | **Yes — T-074** | Even for one lifecycle, `_wait_at_exit()` ignores the `False` returned by `wait_for_the_log_listener_to_stop(timeout=5.0)`. A listener held in a 5.1-second handler call reproduced the committed failure at exit: the wait expired, multiprocessing finalized the pipe, and stderr ended with `Exception in thread Thread-1 (_monitor)`. This is a supported state, not an invented dependency: the existing manager and logging documentation deliberately allow a slow or wedged handler and bound the GUI shutdown wait. The comment that registration makes the listener “finished before anything closes what it is reading” is therefore false whenever that deadline is crossed. | Preserve bounded application shutdown, but make the timeout branch a real closure protocol rather than proceeding to queue finalization with a live reader. Gate it with a deterministic blocked-handler subprocess test and verify both release-before-deadline and deadline-expired paths. | **Open** |
| `T074-R4` | **High** | **Yes — Phase 1 verification** | T-074's four acceptance criteria concern the Windows **access violation**: reproduce that failure with a rate, identify its faulting thread and object, make a mutation restore that crash, and classify product versus harness. This range reproduces and mutation-checks a different failure—an `OSError` from a logging listener during interpreter finalization. The historical fatal dump listed both `ResultPump` and `_monitor`; listing a live thread does not establish that it faulted, and no captured frame ties the access violation to the log queue. The task itself correctly says the access violation was never reproduced and product versus harness remains unresolved, but labels the task “diagnosed and fixed”; the TASKS preamble, STATUS, and IMPLEMENTATION_PLAN still say it is unclassified and blocking. On the evidence presented, the logging race is real but the original High finding is not closed. | Correct the logging race under the scope its evidence supports, then either keep T-074 open until its original acceptance criteria are met, or split the demonstrated logging defect from the unexplained access violation. Closing or downgrading the latter requires an explicit maintainer risk decision; it cannot be inferred from the candidate defect's removal. Reconcile the current-truth documents to that disposition. | **Open** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | Reviewed `7c78c7e..66e96d5`; implementation head remained the pinned source/test state |
| `git diff --check 7c78c7e..66e96d5` | Passed |
| Authorship / trailers | Sean Kottman for both commits; no AI author or co-author trailer |
| Committed T-074 regression | Passed **3/3**, then passed again after restoring the source |
| Import-time registration mutation | **Killed 6/6** with `OSError: [Errno 9] Bad file descriptor` in `_monitor` |
| Two-listener lifecycle probe | **Failed the invariant**: the first listener was untracked and read its finalized queue |
| Single slow-listener probe | **Failed the invariant** after the five-second exit wait expired |
| Logging unit/integration tests plus the historical manager test | **45 passed** in 3.99 s |
| `ruff check` / `ruff format --check` on changed source and test | Passed; **2 files** already formatted |
| `python -m mypy` on changed source / all `src` / changed source under `--platform win32` | Passed: **1 / 35 / 1** source files |
| Maintainer-reported full suite at `66e96d5` | **1428 passed, 11 skipped, 2 deselected** |
| Maintainer-reported platform mutation | Before **6/6 Linux, 8/8 Windows** raced; after **0/6, 0/8** for the one fast-listener shape |

The direct `.venv/bin/mypy` console script could not execute because its shebang still names the
old parent-checkout interpreter. The equivalent venv interpreter invocation
`.venv/bin/python -m mypy` is what produced the passing results above; this environment defect is
outside T-074.

Both temporary probes and the source mutation were removed. No production or test change remains
from this review.

### Final disposition

The post-queue-creation registration is correct for the case the new regression samples, and its
mutation evidence is strong. Approval still blocks on two unsynchronized cases in that same
lifecycle—an earlier stopped listener and a listener that outlives the five-second wait.

Independently, fixing those cases would prove the logging race fixed; it would not by itself prove
that race caused the historical Windows access violation. T-074 therefore remains High and the
Phase 1 Windows criterion remains **not verified** unless the original failure is tied to this
mechanism or the maintainer explicitly accepts the residual risk.

## 2026-07-29 — Previously excluded work review

**Reviewer:** Codex (Reviewer)
**Authorization:** The maintainer requested review of every committed boundary that earlier
reviews explicitly excluded
**Boundaries:**

- T-033 record correction: commit `26c1d4e`
- Phase 2 task and decision planning: `71ca6dc..70c96e9`
- Approved-task filing cleanup: `66e96d5..68eb7b6`
- T-072 final WIN-R1 evidence and current coordination: `68eb7b6..b0a6e07`

**Concurrent-work exclusion:** Claude's active, uncommitted T-074 correction in
`core/logging.py` and `test_logging.py` was not read as a finished boundary and is not covered by
this review.

**Verdict by scope:** T-072 **Approved**; T-033's record correction **Accepted with a
non-blocking cleanup**, while T-033 remains Blocked on T033-R4 and Windows evidence; approved-task
filing **correct for T-075 through T-077 but incomplete at the current head**; Phase 2 planning
**Changes requested before any task becomes Ready**

### T-072 final disposition

WIN-R1 supplies the exact evidence the preceding review required. The maintainer first established
the defective existing state—both profile and remote address were `Any`—then ran the real
`ssh-setup.ps1` existing-rule branch. Its own readback reported `Private` and `LocalSubnet`, and
the independent readback reported the same pair. `key already authorised` also exercises the
idempotent append path without replacing the administrator key file.

The evidence is not vacuous: the precondition would have stopped the procedure before the repair
if the broad state had not actually been created. The script path had already been statically
reviewed; runtime execution was the sole remaining condition. WIN-R1 is therefore **Resolved**,
all five T-072 carries are discharged, and **T-072 is Approved**.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `COORD-R8` | **Medium** | **Yes — Phase 1 exit review** | Current TASKS still gives three incompatible live answers after `b0a6e07`. The start-here bullet calls T-072 **In Progress** and says WIN-R1 remains; T-072's own entry says all five carries are discharged and STATUS calls it complete and in review. T-073 is still filed under In Review with “approved with a documentation follow-up,” although `T073-R1` was independently Resolved at `9802a6a` and the later review explicitly approved T-073. After this review, T-072 is Approved too, so the In Review section should contain only active T-074, not three tasks. The opening “crash, a carry, and frozen-artifact evidence” summary likewise retains a carry that is now closed. These are the exact placement/current-truth failures COORD-R5 through R7 were intended to prevent, and they materially misstate what remains before the exit review. | File T-072 and T-073 under Complete, narrow In Review to T-074, and rewrite the start-here blocker list from the final dispositions. Preserve superseded readings only as explicitly historical text. | **Open** |
| `T033-R5` | **Low** | **No** | Commit `26c1d4e` correctly separates the two collection mutations and records T033-R4 and the Windows build as the blockers. One attached sentence in the status block still says T033-R1 remains open for “the Windows frozen result and the collection-removal negative run,” immediately after saying the Linux negative is complete. The entry also contains the identical `Phase:` field twice. Neither changes T-033's correctly Blocked disposition, but both are current-truth defects in the correction whose purpose was to reconcile that record. | Remove the completed negative run from the remaining T033-R1 evidence and deduplicate the Phase field when T-033 is next edited. | **Open, non-blocking** |
| `P2PLAN-R1` | **Medium** | **Yes — Phase 2 planning** | The accepted REQ-015 amendment makes pause/resume **queue-level** and lets in-flight work drain. The higher-level IMPLEMENTATION_PLAN still requires a queue view with **per-job pause/resume**, while T-080 remains titled “Pause, resume, retry and remove, per job.” Its current Scope quotes the old requirement as though it still governs and says REQ-015 “needs” the amendment already made in the same commit. The task's later acceptance criteria describe queue-level behavior. A Phase 2 implementer therefore receives mutually exclusive instructions from the plan and from different halves of the task. | Amend the Phase 2 deliverable to queue-level pause/resume; retitle and rewrite T-080 from current truth, with per-job cancel/retry/remove separated from queue pause/resume. Move the old requirement wording to explicit history or the decision rationale. | **Open** |
| `P2PLAN-R2` | **Medium** | **Yes — T-087 and durable Phase 2 choices** | Commit `70c96e9` says it records three decisions, but no decision was added to `ai/DECISIONS.md`. QLocalServer keyed from the resolved database path is an architectural, cross-platform choice made over lock files, mutexes, sockets, and `flock`; T-087 itself says it wants a DECISIONS entry first and requires an ID. Queue-draining pause and remove-never-deletes are also durable user-visible trade-offs whose rationale currently lives only in a mutable task. This conflicts with AGENTS §12's canonical home for durable choices and leaves the commit's “recorded” claim false. | Add accepted decision entries for the queue action semantics and the single-instance mechanism, including crash recovery, database-path name derivation, and alternatives. Link their IDs from REQ-015, T-080, and T-087 before those tasks become Ready. | **Open** |
| `P2PLAN-R3` | **Medium** | **Yes — T-078 readiness** | REQ-013 and the Phase 2 deliverable require a **user-configurable** concurrency limit. T-078 calls it the first setting with runtime effect but leaves where it lives as a decision for the implementer, while the full settings dialog is assigned to Phase 4. Its acceptance criteria prove that different N values work but never require a user-accessible, persisted way to select N. The task can therefore pass with only a constructor or test seam and still miss the product requirement at the centre of the phase. | Decide and state the Phase 2 configuration surface and persistence boundary—whether a minimal settings control lands now or a narrower approved mechanism precedes Phase 4—and add an acceptance criterion that changes the limit through that real user-facing path. | **Open** |
| `P2PLAN-R4` | **Low** | **No** | T-084 simultaneously requires per-job logs to be “verbatim” and requires credential/cookie redaction. REQ-026 makes the redaction mandatory, so the literal word “verbatim” cannot govern sensitive substrings. The task also says T-053 is the concurrency proof it rests on without making the ordering explicit. | Say “verbatim except for mandatory handler-level redaction” and make T-053 an explicit prerequisite or an acceptance test owned by T-084. | **Open, non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Working-tree isolation | Only Claude's two active T-074 source/test files were modified; all reviewed material came from committed objects |
| `git diff --check` on all four reviewed boundaries | Passed |
| Authorship / trailers | Sean Kottman throughout; no AI author or co-author trailer |
| WIN-R1 setup gate | Evidence states and checks `Any / Any` before invoking the repair |
| WIN-R1 repair branch | Real script's existing-rule path reapplies scope and reads rule/address filters separately |
| WIN-R1 result | Maintainer-recorded `Private / LocalSubnet`, with `WIN-R1 PASS` |
| T-033 correction | Correctly preserves T033-R4, data-file load bearing, submodule uncertainty, and external Windows evidence |
| Phase 2 deliverable mapping | T-078 through T-087 map every Phase 2 plan deliverable; T-088 owns all six exit criteria |
| Tests | Not run: every reviewed commit is documentation, planning, or external evidence only |

### Phase transition disposition

The previously excluded work does not hide another unreviewed production implementation.
T-072 is approved, T-073 was already approved, and T-033 gates Phase 5 rather than Phase 1.

Phase 1 still cannot exit today. T-074 remains in active correction and the explicit T-066
frozen-artifact evidence blocker remains. COORD-R8 must then make the current-truth files agree,
after which the Phase 1 exit review can be called.

Phase 2's task coverage is otherwise complete, but P2PLAN-R1 through R3 should be corrected before
the first task is promoted from Proposed to Ready. They do not require production work; they
require one coherent pause contract, durable decision records, and a real user configuration
surface for the concurrency limit.

## 2026-07-29 — T-090 initial review and inherited-High correction verification

**Reviewer:** Codex (Reviewer)
**Base:** `b0a6e07`  **Head:** `35fc7ec`
**Scope:** T-090's one-commit logging correction, the inherited `T074-R2` and `T074-R3`
corrections, and the `T074-R4` task split
**Boundary classification:** One source/test correction commit. The three commits between the
old T-074 review head and this base were already covered by the **Previously excluded work
review** and were not re-reviewed.
**Concurrent-work exclusion:** `COORD-R8` and its stale current-truth instances, including the
P1EXIT-R1/R2 sentence in STATUS, remain open and out of this boundary. T-074's unreproduced
access violation remains its own Ready task.
**Verdict:** **Approved with non-blocking follow-up T-091**

The split gives T-090 a task identity and acceptance criteria that had not received an initial
review. This pass therefore uses T-090's **initial comprehensive review budget**, while also
serving as the focused correction verification for the inherited High findings. That
classification does not weaken the High rule: T074-R2 and T074-R3 had to be independently
resolved before approval regardless of the ordinary budget.

### Finding dispositions

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T074-R2` | **High** | **No — resolved** | `_stopping` now retains every live stopped listener and `wait_for_the_log_listener_to_stop()` joins a snapshot of all of them under one shared deadline. Registration occurs once, so duplicate exit callbacks no longer conceal an incomplete collection. Both new probes install their slow handler on `APP_SLUG`, not root. Independently changing the join to `_stopping[-1:]` failed with **3/41** records delivered; omitting the append failed with **1/41**. The committed two-lifecycle test passed. | None. | **Resolved** |
| `T074-R3` | **High** | **No — resolved** | The bounded wait remains five seconds, while `_ToWhicheverHandlersWeHaveNow.dequeue()` converts a queue closed underneath the listener into its normal sentinel path. The 5.1-second handler probe passed at the committed head. Replacing the closure catch with `RuntimeError` failed after 5.32 s with `Exception in thread Thread-1 (_monitor)`. | None; the catch-width hardening below is separate from the supported closure path. | **Resolved** |
| `T074-R4` | **High** | **No — resolved** | TASKS now gives the demonstrated logging race its own T-090 scope and returns T-074 to Ready with all four access-violation criteria unmet, its faulting object unknown, and product-versus-harness unresolved. The commit does not claim that absence after a correction proves causation. | Keep T-074 separate until its evidence or an explicit maintainer risk decision changes. | **Resolved** |
| `T090-R1` | **Medium** | **No — adjacent narrow-trigger hardening** | `src/tracks_and_trails/core/logging.py:529` catches every `OSError`, although its own contract identifies only closure errors (`EBADF` and Windows invalid-handle) as end-of-stream and says real faults still raise. A real `multiprocessing.Queue` with its receive path made to raise `OSError(EIO)` returned the listener sentinel instead of propagating. `_monitor()` would then end normally and sweep pending drains, silently losing every later record. This is a narrow abnormal-transport case, not a failure of the verified queue-closure behavior. | Recognize only verified closure codes, retain `EOFError`/closed-queue `ValueError`, and add a `multiprocessing.Queue.get()`-path regression proving a non-closure `OSError` still raises. | **Open, non-blocking — T-091** |
| `T090-R2` | **Low** | **No** | With T074-R3's guard present, moving `_wait_at_exit` back to import time passed `tests/unit/test_logging.py:657`'s `test_the_log_listener_is_not_left_reading_a_closed_queue`: the original ordering defect still closed the queue under the reader, but the guard hid the exception that test treats as its proof. The mutation is not wholly uncovered—the two-lifecycle delivery test failed with **1/41** records—but the named single-lifecycle regression no longer establishes the causal claim in its docstring. No other logging test installs a meaningful handler on root; the two new tests correctly use the application logger, and the remaining listener tests drive the application handlers or records explicitly. | Give the ordering rule a one-lifecycle delivery count with a slow application-logger handler, so it fails the import-time mutation even while the closure guard remains. | **Open, non-blocking — T-091** |

### Independent verification

| Check | Result |
|---|---|
| Boundary identity | `b0a6e07` is the sole parent of `35fc7ec`; `HEAD == origin/main == 35fc7ec` at inspection |
| Changed surfaces | `ai/REVIEWS.md`, `ai/TASKS.md`, `core/logging.py`, and `test_logging.py`; no hidden implementation commit |
| `git diff --check b0a6e07..35fc7ec` | Passed |
| Authorship / trailers | Sean Kottman; no AI author or co-author trailer |
| Python baseline / PEP 758 syntax | Python **3.14.6**; the unparenthesized `except OSError, EOFError, ValueError:` compiles, imports, lints, and type-checks |
| Focused logging suite | **39 passed in 8.07 s** |
| Full unit suite | **1053 passed, 9 skipped in 10.59 s** |
| Full integration suite | **167 passed in 71.20 s** with loopback sockets allowed |
| Initial sandboxed integration attempt | **18 failed, 149 passed**; every failure was `PermissionError: [Errno 1]` creating a loopback socket. Re-run outside that network restriction produced the passing result above. |
| Full default suite | **1430 passed, 11 skipped, 2 deselected in 123.05 s** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed: **106 files** already formatted |
| `mypy src` | Passed: **35 source files** |
| Configured `mypy` / `mypy --platform win32` | Passed: **78 files** in each scope |
| T074-R2 newest-only mutation | **Killed:** 3/41 records delivered |
| T074-R2 no-append mutation | **Killed:** 1/41 records delivered |
| T074-R3 wrong-exception mutation | **Killed:** thread exception reproduced after the bounded wait |
| Import-time-registration mutation | Named original regression **survived**; the two-lifecycle delivery regression killed it at 1/41, producing T090-R2 |
| Non-closure queue-error probe | A real `multiprocessing.Queue.get()` path raising `OSError(EIO)` returned the sentinel, producing T090-R1 |
| Windows evidence | Not independently rerun in this pass. The committed record reports 39 logging tests passing on STARBASE and the original exit-race probe at 0/8 after 8/8 before. |

All reviewer mutations ran from an isolated `/tmp` archive with that archive's `src` first on
`PYTHONPATH` and bytecode writes disabled. No reviewed source or test file was changed.

### Final disposition

T074-R2 and T074-R3 are independently **Resolved**. Every stopped listener is represented in the
wait, and a listener that outlives the bound exits cleanly when queue finalization closes its
transport. T074-R4 is also Resolved: the demonstrated race is honestly T-090, while the
historical Windows access violation remains T-074 and remains unexplained.

The two new findings do not reopen those outcomes. T090-R1 is a narrow non-closure transport
fault outside the demonstrated teardown path; T090-R2 is test hardening because another committed
regression still kills the ordering mutation. Both are carried to T-091 with an owner and
acceptance criteria.

No blocking finding remains. T-090 is **Approved with follow-up T-091** and its implementation
head is ready to file Complete. This approval does not approve T-074, resolve COORD-R8, or make
Phase 1 ready for its exit review.

## 2026-07-29 — Phase 1 exit review

**Reviewer:** Codex (Reviewer)
**Subject:** The eight Phase 1 exit criteria and their evidence table in
`ai/IMPLEMENTATION_PLAN.md`
**Phase span inspected for context:** `7b7860d..e2e60e9`; previously approved implementation
boundaries were not re-reviewed
**Verdict:** **Approved — Phase 1 exits with the `OPS-005` and `OPS-007` residuals explicit**

This review challenged the two decisions that removed the last blockers rather than treating
them as fixes. Neither decision closes its underlying task. `T-066` remains Blocked on
frozen-artifact evidence deferred to Phase 5, and `T-074` remains open at Medium with an
unexplained access violation and all four diagnostic criteria unmet.

### Finding

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P1EXIT-R3` | **Low** | **No — corrected in the reviewed table** | `IMPLEMENTATION_PLAN.md:146` cited only `test_an_unsupported_url_fails_the_job_with_the_extractors_own_message`. That worker-level test proves the typed `Failed` protocol outcome and exact text, but it neither creates a durable `Job` nor shows text in the UI, so by itself it did not prove the criterion's “failed job showing” claim. `tests/ui/test_add_dialog.py:1448` proves character-for-character display and `:1469` proves the queued job is stored `FAILED` with the same kind and message. Both passed in the full gate. | Cite all three observations and keep the existing `_extract`-seam limit explicit. | **Resolved in this review** |

No blocking finding remains.

### Decision challenge: `OPS-007`

The access violation is a real, unresolved event in a production-path module, and accepting it
weakens the confidence conveyed by “verified on Windows.” It is nevertheless an acceptable
phase residual on the record available:

- The event was loud—an interpreter crash and red gate—not a silent wrong download or path-safety
  failure. Product-versus-harness remains unknown and is stated that way.
- The evidence does not imply that `T-090` fixed it. The pre-`T-090` population was already clean,
  and both the decision and the updated table say so.
- The attempt arithmetic is internally consistent: `12 + 24 + 15 = 51` deliberate full-suite
  runs, and `51 + 60 + 250 = 361` total attempts. The earlier 373 count would double-count the
  12-run batch already included in the 36-run pre-fix population.
- The High-to-Medium downgrade satisfies `AGENTS.md` §10. `OPS-007` is an explicit maintainer
  approval; it states the reasons—reproduction routes exhausted, further repetition costly, loud
  failure mode—and records the downgrade against `T-074`. This exit review records that
  disposition with the finding rather than inferring it from a clean run.
- `T-092` makes recurrence diagnostic by capturing a dump, and `OPS-007` reopens on any recurrence
  or on a user-reachable defect traced to `result_pump.py`.

This is risk acceptance, not proof that the event cannot recur.

### Decision challenge: amended `OPS-005`

Deferring `T-066`'s remaining frozen evidence to Phase 5 is sound for this phase:

- Phase 1's deliverables and eight exit criteria contain no frozen-build, installer, virtualenv,
  or packaging condition.
- Phase 0 owns and has exited on the frozen `spawn` smoke through `T-020`. The plan's additional
  frozen-build risk-register row also assigns that mitigation to Phase 0.
- Phase 5 owns the actual Windows PyInstaller distribution, and `T-033` owns inclusion and
  validation of the yt-dlp baseline there.

The concession is material: a different frozen process-tree shape could mean `T-019`'s source or
virtualenv reaping evidence does not describe the shipped application. The decision names that
assumption and places its measurement beside the artifact that creates the shape. Holding the
vertical-slice exit for a Phase 5 artifact would invert the plan's sequencing.

The earlier review sentence saying the frozen blocker remained predates this explicit amendment.
It is superseded history, not an unresolved contradiction.

### Exit-criterion verification

| Criterion | Reviewer result |
|---|---|
| Real download, progress, final bytes | Met. Real yt-dlp downloaded from a loopback HTTP server; the evidence test asserts file, reported, stored, and served byte counts agree |
| Cancel under 2 seconds, no orphan | Met. Real-byte cancellation, stubborn-worker escalation, and both descendant-reaping cases passed |
| Killed worker becomes `WORKER_CRASH`; app survives | Met. Exit-code mapping, zero-without-outcome, and restart-after-crash tests passed |
| State survives restart mid-download | Met. Separate-interpreter hard kill leaves a confirmed `RUNNING` row which the next application start recovers |
| Unsupported URL becomes a failed job with exact message | Met after `P1EXIT-R3`'s citation correction; the `_extract` injection limit remains explicit |
| Worker runs with no display | Met. One spawned-child observation asserts the variables absent and runs real `run_session`; both display mutations were independently killed |
| Linux and Windows verified | Met with residual. Linux passed below; approved `T-073` evidence records the full `STARBASE` gate, with `T-074` dispositioned by `OPS-007` |
| Reviewed and signed off | Met by this review |

### Independent verification

| Check | Result |
|---|---|
| Working-tree isolation | Clean at `e2e60e9` before reviewer-owned documentation edits; no concurrent work observed |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **106 files** already formatted |
| `mypy src` | Passed; **35 source files** |
| Configured `mypy` | Passed; **78 files** |
| Configured `mypy --platform win32` | Passed; **78 files** |
| Thirteen named criterion tests | **13 passed, 125 deselected** in 10.36 s |
| Full default suite | **1430 passed, 11 skipped, 2 deselected** in 124.41 s |
| Headless inherited-display mutation | Killed: the spawned child observed `DISPLAY` and `WAYLAND_DISPLAY` and failed |
| Headless workload-display mutation | Killed: adding a display lookup to `run_session` prevented the required protocol sequence |
| Unsupported-error mapping mutation | Killed: removing the `UnsupportedError` mapping produced `EXTRACTOR_ERROR` instead of `UNSUPPORTED_URL` |
| Windows run arithmetic and workflow | Run IDs, populations, totals, and `windows desktop` gate shape agree across `T-073`, `T-074`, `OPS-007`, and the workflows |

The first concurrent mypy attempt shared one incremental cache across native and Windows-platform
processes and produced two spurious `ctypes.windll` errors. After moving that cache aside, the
documented commands passed sequentially; a no-incremental Windows-platform run passed as a control.
This was a review-harness collision, not a project finding.

The private GitHub run contents were not independently downloadable with the credentials available
in this environment. This review therefore relies on the already-approved committed `T-073`
external evidence for the Windows execution, while independently checking its workflow shape and
the arithmetic carried into `OPS-007`.

### Residuals carried out of the phase

- `T-074`: one unexplained Windows access violation in or adjacent to `ARC-002` result delivery;
  accepted by `OPS-007`, open at Medium, with `T-092` as the recurrence trap.
- `T-066`: frozen-artifact process-tree evidence remains unobtainable while hosted quota is
  exhausted; accepted by amended `OPS-005` and measured with `T-033` in Phase 5.
- Linux verification is a maintainer-machine run under `OPS-006`; it does not detect a dependency
  newly introduced on a system library already present on that desktop.
- yt-dlp's own unsupported-URL recognition is not exercised by the criterion test; the typed error
  is injected at the adapter `_extract` seam.

### Final disposition

All eight Phase 1 criteria are met at the level the accepted decisions define. The two unresolved
items are documented residuals with owners and reopening conditions, not hidden green claims.

**Phase 1 exits on 2026-07-29.**

## 2026-07-29 — T-050 initial review and P2PLAN-R2 correction review

**Reviewer:** Codex (Reviewer)
**Base:** `e2e60e9`  **Head:** `f4384b0`
**Boundary treatment:** `da6a761`'s reviewer-owned `REVIEWS.md` and
`IMPLEMENTATION_PLAN.md` writes were not re-reviewed. Its implementer-owned STATUS/TASKS
reconciliation was checked against the Phase 1 exit verdict. `6dbe175` and `f4384b0` received
full review.
**Verdict:** **Changes requested — T-050 and the P2PLAN-R2 correction are not merge-ready**

`Succeeded.format_used`, the repository mapping, schema reuse, writer-thread connection ownership,
and the real composition all work on the ordinary path. The blocking failures are at the
boundaries this change exists to protect: crash atomicity, visible persistence failure, the
required test type gate, and Windows single-instance exclusivity.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T050-R1` | **Critical** | **Yes — T-050** | `downloader/manager.py:1443-1446` first persists `COMPLETED`; only its GUI-thread success callback enters `_on_completed`, which queues the history insert at `:1503-1512`. These are two SQLite transactions with an event-loop turn between them. A deterministic child process withheld GUI event delivery, waited until the writer committed the completed job, then hard-exited. On restart the exact result was `{'child_exit': 0, 'job_status': 'completed', 'history': None}`. No startup recovery backfills history, and `format_used` exists nowhere else, so `REQ-012`'s unexpected-termination promise and `REQ-020`'s durable record are both violated by silent, irreversible record loss. | Make completion one injected persistence operation that updates the job and records history in one transaction on the writer connection. Gate the old between-write boundary with a hard-exit subprocess mutation. Do not announce success until that transaction commits. | **Open — T-093** |
| `P2PLAN-R5` | **High** | **Yes — P2PLAN-R2 / T-087 readiness** | `DECISIONS.md:1727-1742` chooses `QLocalServer` itself as the single-instance guard and says connect failure proves the owner is gone. [Official Qt 6 documentation](https://doc.qt.io/qt-6/qlocalserver.html#listen) says the opposite property matters on Windows: **two local servers can listen on the same pipe simultaneously**, and connections may go to either. Two concurrent launches can both fail their initial connect and both successfully listen, creating the exact two-writer state `ARC-006:1719-1722` calls a data-integrity threat. The header also says the decision “Discharges” A-004 before T-087 exists, contradicting its own consequence at `:1755`. | Reopen ARC-006. Use an atomic cross-platform ownership primitive, optionally retaining QLocalServer as the attach channel. Test simultaneous starts—not only stale-owner recovery—on Linux and STARBASE, and leave A-004 unverified until implementation lands. | **Open — T-094** |
| `T050-R2` | **Medium** | **Yes — T-050** | `_on_completed` sends a history write error only through `persistence_failed` (`manager.py:1506-1511`). The composed application installs no stable receiver. `AddUrlDialog` is the only production listener (`add_dialog.py:586`), is temporary, and `_on_persistence_failed` ignores every job not in its private withdrawal set (`:843-849`). A failed history insert during an ordinary completion therefore leaves a `COMPLETED` job, no required history row, a success UI, and no visible or logged report. The optional `history=None` constructor path at `manager.py:421,433-438` provides a second silent-disable route, though the real `app.compose()` currently supplies the sink and its integration test catches omission there. | Give completion persistence one required injected path, and route a failed atomic completion transaction to a stable application-level consumer or log. Test the real composition with no Add-URL dialog alive and force the history half to fail. | **Open — T-093** |
| `T050-R3` | **Medium** | **Yes — required gate** | Both bare `mypy` and `mypy --platform win32` fail at `tests/integration/test_manager.py:3382`: `active_job_ids()` returns `tuple[str, ...]`, but the new test compares it with `[]`. `ai/TESTING.md` §3 requires both whole-project gates for every test-file edit. `mypy src` passes, which explains how a “35 source files” run missed this. | Use a type-correct truth test and rerun both required whole-project gates. | **Open — T-093** |
| `COORD-R9` | **Low** | **No** | The Phase 1 reconciliation is substantively accurate, but `STATUS.md:48` still says calling criterion 7 met is for the exit review to decide after `:31-33` says that review already decided it. `STATUS.md:54` repeats “all four frozen references,” while the exit review explicitly noted the additional Phase 0 risk-register row. Separately, TASKS declares `## In Review` empty at `TASKS.md:97-112`, while T-050 says In Review at `:1018` under Proposed. | Reconcile the post-exit tense/count and file T-050 under the section its status names when recording this verdict. | **Open, non-blocking — T-095** |

### What passed review

**IPC contract.** `ARC-003` supports the change: parent and child ship from the same artifact, so
version skew is unreachable and no handshake is required. `format_used` is keyword-only,
optional and defaulted, preserving existing constructors while carrying the resolved
post-download `format_id`. The selector-substitution mutation failed all three focused tests.
The recorded fixtures are adapter inputs rather than serialized `Succeeded` objects; nevertheless,
the full fixture and adapter suites loaded every committed JSON/error fixture successfully.

**Persistence shape.** The history table and all seven columns already exist in
`0001_initial.sql` and the frozen v1 schema fixture; the schema snapshot test passed, so no
migration is required. Dropping `format_used` from `_HISTORY_COLUMNS` failed the whole-object
round-trip and upsert tests. Replacing `job.finished_at` with a fresh `_now()` failed the real
completion test.

**Writer-thread ownership.** The `_perform` widening keeps the connection factory invocation in
the writer slot and constructs both repository types there. `db.connect()` retains SQLite's
default `check_same_thread=True`. Existing submit/revise tests and the focused suite passed. A
review probe queued `record_history()` and immediately called `close()`; the callback returned
success and a fresh connection found the row, proving the already-submitted write remains ahead of
shutdown.

**Other challenged points.**

- The false “a retry can complete twice” justification has no surviving positive claim. The task,
  repository and tests all state that `COMPLETED` is terminal and that the repository-level upsert
  is presently unreachable through the manager.
- The `_run_download` merge of a default mapping with overrides is correct; existing and new
  worker tests pass.
- `UX-001` is an appropriate first `UX-` decision. Its queue-level semantics, unreachable PAUSED
  edges, T-080 ownership and REQ-017 reopening condition agree with current code and requirements.
- `P2PLAN-R2`'s missing-durable-home defect is resolved in form: UX-001 and ARC-006 exist and the
  requirements/tasks cite them. ARC-006's chosen mechanism remains unapproved because of
  P2PLAN-R5.
- The optional history sink is not a separate finding beyond T050-R2 because `app.compose()`
  supplies it and the real-composition test detects omission today. T-093 should still remove the
  silent production-capable path while making completion atomic.

### Independent verification

| Check | Result |
|---|---|
| Boundary and working tree | `e2e60e9..f4384b0`, three commits as handed off; clean before reviewer record edits; `HEAD == origin/main == f4384b0` |
| `git diff --check e2e60e9..f4384b0` | Passed |
| Authorship / trailers | Sean Kottman for all three commits; no AI author or co-author trailer |
| Focused persistence/protocol/fixture/worker/manager/composition/boundary set | **442 passed, 8 skipped** in 73.02 s |
| Recorded fixtures plus adapter | **183 passed, 5 skipped** in 2.22 s |
| Full default suite | **1448 passed, 11 skipped, 2 deselected** in 187.89 s |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **106 files** already formatted |
| `mypy src` | Passed; **35 source files** |
| Bare `mypy` | **Failed:** one new comparison-overlap error at `test_manager.py:3382` |
| Bare `mypy --platform win32` | **Failed:** the same error; **78 files** checked |
| Selector-for-resolved-format mutation | **Killed 3/3** |
| Dropped `_HISTORY_COLUMNS` entry mutation | **Killed:** two focused history tests failed |
| Fresh-write-time mutation | **Killed:** real completion timestamp differed from the stored job |
| Non-success history mutation | Failed-job branch killed by the real no-history assertion; the unmodified real cancellation branch passed its no-history case |
| QueueWriter history-then-close probe | Passed; callback success and row present after immediate close |
| Crash-between-completion-and-history probe | **Reproduced T050-R1:** child exit 0, durable job `COMPLETED`, history absent |
| Schema/migration snapshot | Passed inside `test_persistence.py`; no migration file changed |
| Windows runtime | **Not run.** No T-050 code or threading test has executed on Windows |

All mutations and probes ran from `/tmp` or standalone temporary files. No production or committed
test file was changed by verification.

### Final disposition

T-050 is **Changes requested**. Its ordinary success path is well structured, but history is not
crash-atomic with the job state and a write failure is not actually surfaced by the composed
application. Both required whole-project mypy gates also fail.

The UX-001 half of P2PLAN-R2 is accepted. The ARC-006 half is **Changes requested** because
QLocalServer is not an exclusive Windows ownership primitive; T-087 must not become Ready on that
decision.

The Phase 1 STATUS/TASKS reconciliation says what the exit review found in substance, with the
non-blocking current-truth drift carried to T-095.

**Do not merge `e2e60e9..f4384b0` as an approved boundary.** T-093 and T-094 require correction
and focused re-review. The missing Windows execution remains required for T-093's writer-thread
correction.

## 2026-07-29 — T-050 / P2PLAN-R2 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `90be487`  **Head:** `67535b7`
**Boundary treatment:** `90be487` is the prior review record and is not re-reviewed.
`f858da9` is the correction implementation; `67535b7` adds only the STARBASE evidence.
**Verdict:** **Changes requested — the production correction is atomic, but its required
regression gate does not reject a split transaction**

T050-R2 and T050-R3 are Resolved. P2PLAN-R5 is Resolved, so the ARC-006 half of P2PLAN-R2 is
approved alongside the UX-001 half accepted in the initial review. COORD-R9's three named
contradictions are corrected. T050-R1 remains open because the correction's production behavior
passes independent fault injection but the acceptance criterion requiring a transaction-split
mutation to fail is not met.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T093-R1` | **Medium** | **Yes — T-093 / T-050** | `test_manager.py:3468-3550` hard-exits only from `settled`, after `_Worker._perform` has returned and therefore after every statement in `complete_job` has finished. In an isolated archive I changed `complete_job` from one `with connection:` block to two consecutive blocks, leaving every other line alone. The committed hard-exit test still passed. A separate child that replaced `_write_history` with `os._exit(0)` distinguished the shapes exactly: current code restarted as `{'status': 'queued', 'history': None}`, while the split mutation restarted as `{'status': 'completed', 'history': None}`. The production fix is correct; the committed gate does not gate its defining invariant or satisfy T-093:737-738. | In the subprocess, inject the hard exit immediately before the history statement—not after the success callback—and accept either both rows or neither. The unmodified code must produce neither at that injection; splitting the transaction must produce `COMPLETED` without history and fail. Keep the current after-callback case separately if desired as a positive durability check. | **Open — T-093** |
| `COORD-R10` | **Medium** | **Yes — T-095** | T-095:834-835 requires the start-here/readiness summaries to account for T-093 and T-094. `TASKS.md:15-18` and `STATUS.md:15-17` still name only P2PLAN-R1/R2/R3, while T-093, T-094 and T-095 all say In Review at `TASKS.md:696`, `:759` and `:805` but remain physically under `## Ready` (`:295-838`). The correction therefore repeats the status/section contradiction COORD-R9 existed to remove and materially misstates the review queue. | Reconcile both start-here summaries with this disposition; put T-093 and T-095 under In Review, file approved T-094 Complete, and keep P2PLAN-R1/R3 open. T-085 remains blocked on T-050 until T093-R1 clears. | **Open — T-095** |

### Original-finding disposition

| Finding | Result |
|---|---|
| `T050-R1` | **Open pending T093-R1.** `complete_job()` itself is one real SQLite transaction and fault injection proved rollback, but its required regression mutation survives the committed gate. |
| `T050-R2` | **Resolved.** The optional `HistorySink` path is gone. Completion failure now takes `_persist`'s ordinary error path, logs on the stable `tracksandtrails.manager` logger, emits `persistence_failed`, and returns before `job_succeeded`. |
| `T050-R3` | **Resolved.** The tuple/list comparison is gone and both configured whole-project type gates pass on 78 files. |
| `P2PLAN-R5` | **Resolved.** ARC-006 withdraws QLocalServer as ownership, keeps it only as the attach channel, specifies kernel-backed exclusive ownership on both platforms, adds simultaneous-start evidence to T-087, and leaves A-004 unverified. |
| `COORD-R9` | **Resolved as written.** Criterion 7 tense, the five-reference count, and T-050's filing are corrected. COORD-R10 is the correction batch's new readiness/placement contradiction. |

### What passed re-review

**Atomic production path.** `DownloadManager` sends the completed `Job` and resolved format
through required `JobStore.complete`; `PersistentJobStore` projects the `HistoryEntry`; one
QueueWriter signal carries both objects to the existing writer-thread connection; and
`complete_job()` executes both SQL statements inside one `with connection:` transaction.
Forcing the history insert to abort left the stored job `QUEUED` and history absent, proving
rollback rather than a partial commit. SQLite's default `check_same_thread=True` remains in
force, and submit/revise still construct their repository operations inside the writer slot.

**Failure and layering.** A completion error runs `_settle`'s stable error log and
`persistence_failed` branch and returns before `job_changed` or `job_succeeded`. The manager
imports no persistence module. `app.compose()` has no optional history argument left to omit;
the concrete store supplies the required `complete` operation.

**ARC-006.** The amendment engages Qt's documented Windows non-exclusivity directly and separates
ownership from messaging. A POSIX nonblocking exclusive `flock` is atomic. On Windows, an
exclusive-access file open with sharing mode zero prevents a second open until the owning handle
closes, which is the required kernel-released property
([Microsoft CreateFile documentation](https://learn.microsoft.com/en-us/windows/win32/fileio/creating-and-opening-files)).
T-087 now owns simultaneous-start and killed-owner tests on Linux and STARBASE; implementation
remains future work, and A-004 remains unverified.

### Independent verification

| Check | Result |
|---|---|
| Boundary / working tree | `90be487..67535b7`; clean before reviewer documentation edits; `HEAD == origin/main == 67535b7` |
| `git diff --check 90be487..67535b7` | Passed |
| Authorship / trailers | Sean Kottman for both commits; no AI author or co-author trailer |
| Focused correction set | **503 passed, 3 skipped in 122.51 s** with loopback sockets allowed |
| Initial sandboxed focused attempt | **12 failed, 491 passed, 3 skipped**; every failure was `PermissionError: [Errno 1]` at local socket creation. The permitted rerun above passed. |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **106 files** already formatted |
| Bare `mypy` | Passed; **78 files** |
| Bare `mypy --platform win32` | Passed; **78 files** |
| Forced history-insert failure | Passed: exception raised, stored job remained `QUEUED`, history absent |
| Between-statement hard exit, current code | Passed atomicity: restart found `QUEUED`, history absent |
| Literal one-transaction → two-transaction mutation | **Survived the committed gate:** the named hard-exit test passed |
| Between-statement hard exit, split mutation | Reproduced the forbidden state: restart found `COMPLETED`, history absent |
| STARBASE run `30506962680` | Independently queried: head `f858da9`; `windows desktop` successful; Windows mypy **78 files**; named hard-exit test passed; full suite **1438 passed, 20 skipped, 32 deselected** |
| Hosted jobs in that run | Four failures, each with zero steps; consistent with the recorded billing/quota condition, not test evidence |
| Full default suite | **1449 passed, 11 skipped, 2 deselected in 183.66 s** |

All mutation archives and probes lived under `/tmp`; no reviewed source or test file was changed.
The STARBASE evidence is at
[GitHub run 30506962680](https://github.com/kottmans/tracks-and-trails/actions/runs/30506962680).

### Final disposition

The T-050 production implementation is corrected, including the silent-failure and type-gate
findings, and its Windows execution is real. It is nevertheless **not approved** because the one
regression test T-093 explicitly requires passes when the transaction is split. T050-R1 therefore
stays open through T093-R1, and T-085 remains blocked on T-050.

P2PLAN-R2 is **Approved**: UX-001 was already accepted and amended ARC-006 now has an exclusive
ownership primitive rather than treating QLocalServer as one. T-094 may be filed Complete.

T-095 is **Changes requested** because its correction left all three correction tasks under
`## Ready` while their own statuses say In Review and omitted them from both readiness summaries.

## 2026-07-29 — T-050 / T-093 / T-095 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `d202417`  **Head:** `6d14e78`
**Boundary treatment:** exactly one correction commit. No production code changed;
`complete_job()` is byte-identical to the implementation already fault-injected in the preceding
review. This pass reviewed the corrected gate, its evidence, and `COORD-R10`, not settled production
ground.
**Verdict:** **Approved with follow-up — T093-R1 and COORD-R10 are Resolved**

T-050 and T-093 are approved at `6d14e78`. T-095 is approved at the same head. T-094 was already
approved at `f858da9`; this boundary only files it consistently. T-085 is therefore no longer
blocked by T-050, although the Phase 2 planning findings still govern when Phase 2 tasks may move
out of Proposed.

### Finding disposition

| Finding | Result |
|---|---|
| `T093-R1` | **Resolved.** With the committed test and injection unchanged, splitting only `complete_job()` into two consecutive transaction blocks fails on the forbidden durable state: job `COMPLETED`, history absent. |
| `COORD-R10` | **Resolved.** T-093 and T-095 are under In Review, approved T-094 is under Complete, and the TASKS and STATUS opening summaries account for all three without claiming P2PLAN-R1 or P2PLAN-R3 is resolved. |

### Focused challenges

**The gate can fail for the defect's own reason.** The child replaces `_write_history` with
`os._exit(17)` before calling the unchanged production operation. On current code, restart finds
the pre-completion `QUEUED` row and no history. In an isolated archive, the reviewer changed only
`complete_job()` from one `with connection:` block to two consecutive blocks. The unmodified test
then failed: the first block had durably committed `COMPLETED`, while the injected exit prevented
history. The adjacent after-callback test still passed under the split, confirming that it is a
separate positive durability check rather than a second atomicity gate.

The two exact-state assertions are useful diagnostics, not accidental over-constraint. The probe
creates a known `QUEUED` preimage and submits only one completion; at this injection point a real
rollback must preserve that preimage exactly. The invariant assertion catches the split, while
`entry is None` and `status is QUEUED` distinguish an injection move, an unexpected history write,
or a partial commit.

**The transaction wrapper is real.** A direct probe of the project connection reported legacy
transaction control with `isolation_level == ""`: DML changed `in_transaction` from false to true,
and rollback removed the probe row. The context manager therefore encloses one deferred SQLite
transaction rather than two autocommits.

**The Windows claim is true, but the committed citation was stale.** TASKS named run
`30506962680`, whose head was `f858da9` and therefore could not contain this correction. The
reviewer independently found the current-head execution in
[run 30509335111](https://github.com/kottmans/tracks-and-trails/actions/runs/30509335111):
the `windows desktop` job at `6d14e78` passed both named hard-exit tests, both whole-project mypy
gates checked 78 files, and the full Windows suite reported **1439 passed, 20 skipped,
32 deselected**. The four hosted jobs had zero executed steps; they are the already-recorded quota
condition, not contrary test evidence. The TASKS citation and count were corrected to this run as
review evidence.

**The recurring coordination defect needs a mechanism.** COORD-R10's present repair is accurate,
but it is still a sixth manual late reconciliation in the COORD-R5 through COORD-R10 class. That
does not reopen T-095. Non-blocking T-096 now owns a parser-backed invariant that task status and
containing section agree, including mutations in both directions.

**Mutation evidence now has an explicit rule.** TESTING §13 records the lesson from two consecutive
gate corrections: a claimed mutation changes production only. The committed test, its input, and
its fault scenario stay fixed; adding the distinguishing crash to the mutation is not evidence
that the test can detect the production weakening.

### Independent verification

| Check | Result |
|---|---|
| Boundary / working tree | `d202417..6d14e78`, one commit; clean before reviewer documentation edits; `HEAD == origin/main == 6d14e78` |
| Production boundary | No production file changed; `complete_job()` unchanged from the previously validated implementation |
| `git diff --check d202417..6d14e78` | Passed |
| Authorship / trailers | Sean Kottman; no AI author or co-author trailer |
| Both committed hard-exit tests | **2 passed in 0.39 s** |
| Literal one-block → two-block production-only mutation | **Killed:** the atomicity test failed on durable `COMPLETED` with no history; the positive durability test still passed |
| SQLite transaction-mode probe | Deferred transaction observed; rollback removed the inserted row |
| Full default suite | **1450 passed, 11 skipped, 2 deselected in 126.39 s** |
| Bare `mypy` | Passed; **78 files** |
| Bare `mypy --platform win32` | Passed; **78 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **106 files** already formatted |
| STARBASE at correction head | Run `30509335111`, `windows desktop` successful; both hard-exit tests passed; **1439 passed, 20 skipped, 32 deselected** |

The mutation archive and SQLite probe lived under `/tmp`; verification changed no reviewed source
or test file.

### Final disposition

T093-R1 is **Resolved**. The test now rejects exactly the transaction split its acceptance
criterion names without help from the mutation. T050-R1 is consequently Resolved, and T-050 /
T-093 are **Approved at `6d14e78`**. T-085's dependency on T-050 is clear.

COORD-R10 is **Resolved**, so T-095 is **Approved at `6d14e78`**. T-096 is a non-blocking
coordination-invariant follow-up and does not keep T-095 in review. No production blocker remains
from this boundary.

## 2026-07-29 — P2PLAN-R1 / P2PLAN-R3 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** `6768f06`  **Head:** `8306378`
**Boundary treatment:** two documentation-only planning commits. P2PLAN-R2 and ARC-006 were
already approved and were not re-reviewed. This pass verifies the P2PLAN-R1 reconciliation against
accepted UX-001 and the P2PLAN-R3 correction against REQ-013, DAT-001 and the existing settings
ownership.
**Verdict:** **Approved with non-blocking follow-ups — all three Phase 2 planning gates are clear**

P2PLAN-R1 and P2PLAN-R3 are Resolved. Together with the prior P2PLAN-R2 approval, the condition
recorded by the initial Phase 2 planning review is now met. T-078 may be promoted from Proposed to
Ready; downstream Phase 2 tasks remain governed by their stated dependencies.

### Finding disposition

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P2PLAN-R1` | **Medium** | **No — resolved** | IMPLEMENTATION_PLAN now separates queue-level pause/resume from per-job cancel/retry/remove and adds queue draining to the exit criterion. T-080 is retitled, its two granularities are explicit, and its test criterion rejects a single-job pause as proof of the queue contract. The stale pre-amendment reading is marked historical. | None. | **Resolved** |
| `P2PLAN-R3` | **Medium** | **No — resolved** | Accepted ARC-007 gives the setting a durable owner (`core/settings.py` / `settings.toml`), a reachable Phase 2 control in the existing main window, live raise/drain semantics, and an injected manager boundary. T-078 must drive the real control, prove restart persistence, and handle missing, malformed and below-minimum file values at the settings layer. A constructor-only seam cannot pass those criteria. | None. | **Resolved** |
| `P2PLAN-R6` | **Low** | **No — T-078 is not implemented** | ARC-007 says `downloader/manager.py` receives a value and never reads `core/settings.py`, but neither static boundary analyzer enforces that dependency. A synthetic `from tracks_and_trails.core import settings` produced no layering violation and no manager-boundary offender; all 130 existing boundary tests remained green. | Extend the manager-boundary analyzer with an independently mutation-checked prohibition on direct `core.settings` imports in `downloader/manager.py`. | **Open, non-blocking — T-097; required by T-078 approval, not readiness** |
| `P2PLAN-R7` | **Low** | **No — T-080 remains Proposed** | The P2PLAN-R1 correction also adds “manual retry re-enters at the back and does not jump waiting jobs.” UX-001 does not decide retry order, REQ-018 only requires retry, and T-083's existing no-jump criterion is explicitly about automatic retries. The policy is coherent with queue fairness, but it is new task scope rather than reconciliation from UX-001. | Before T-080 starts, either confirm this as the manual-retry consequence of the scheduler T-078 records or remove it; do not describe it as part of P2PLAN-R1's already-made pause decision. | **Open, non-blocking — T-080** |

### Focused challenges

**The PAUSED-edge deferral is accepted.** UX-001 itself assigns T-080 the choice to remove the
unreachable transitions or record why they remain. REQ-017 supplies a concrete Phase 3 reopening
condition, so choosing with the implementation in view is not missing product semantics. T-080
cannot silently ignore the issue: its Scope names the choice and its acceptance criteria require
that no Phase 2 job reaches `PAUSED`.

**ARC-007 closes the user-path hole.** A TOML file alone would have invited the same argument as a
constructor seam. The existing-main-window control is reachable in T-078's own sequence, persists
through the already-assigned settings owner, and applies live. The decision also avoids pulling
Phase 4's eight-setting dialog forward. Missing and malformed files fall back to the REQ-013
default, while invalid values are constrained below the widget, so direct file editing cannot
create a zero-slot pool.

**“Clear” means independently resolved here.** The initial planning review said R1 through R3 must
be corrected before the first promotion, and AGENTS §10 says only the Reviewer marks findings
Resolved. Holding T-078 at Proposed until this verdict was therefore the sound reading. This review
clears that condition; it does not promote every dependent task at once.

**The Phase 2 exit wording remains binding.** IMPLEMENTATION_PLAN now requires both lowering the
limit and pausing the queue to drain. T-080 owns the queue-pause behavior, and T-088's acceptance
criterion still requires one test for every current plan exit criterion. Its explanatory inventory
abbreviates the concurrency bullet to lowering the limit, but cannot narrow the higher-authority
plan; mirror the full wording when T-088 is prepared rather than treating the shorthand as an
exclusion.

### Independent verification

| Check | Result |
|---|---|
| Boundary / working tree | `6768f06..8306378`, two commits; clean before reviewer record edits; `HEAD == origin/main == 8306378` |
| Changed surfaces | DECISIONS, IMPLEMENTATION_PLAN, STATUS and TASKS only; no production or committed test file changed |
| `git diff --check 6768f06..8306378` | Passed |
| Authorship / trailers | Sean Kottman for both commits; no AI author or co-author trailer |
| UX-001 / REQ-015 / plan / T-080 mapping | Queue pause/resume and per-job cancel/retry/remove agree; stale wording is explicitly historical |
| REQ-013 / DAT-001 / architecture / ARC-007 / T-078 mapping | Owner, location, UI surface, live propagation, restart persistence, default and minimum agree |
| Current static-boundary suites | **130 passed in 0.20 s** |
| Direct manager → settings synthetic import | **Not detected**, confirming P2PLAN-R6 and T-097 |
| Full suite, lint and type gates | Not rerun for this documentation-only boundary; implementer reports **1450 passed**, Ruff clean, format clean, and both mypy gates clean at 78 files |

### Final disposition

P2PLAN-R1 and P2PLAN-R3 are **Resolved at `8306378`**. The correction is planning-complete and
T-078 may become Ready. The PAUSED-state choice remains deliberately owned by T-080 rather than
being mistaken for an unresolved planning decision.

P2PLAN-R6 is carried to T-097 as non-blocking pre-implementation test infrastructure.
P2PLAN-R7 is carried to T-080 for explicit confirmation before that dependent task starts. Neither
finding reopens the corrected planning gates or delays T-078 readiness.

## 2026-07-30 — T-085 / T-049 / T-047 / T-097 four-task review

**Reviewer:** Codex (Reviewer)
**Pinned span:** `1beb6f8..2457313`
**Per-task boundaries:** T-085 `1beb6f8..36bfba6`; T-049 `36bfba6..0027299`; T-047
`0027299..e8af655`; T-097 `e8af655..2457313`
**Concurrent-work exclusion:** T-078 began after the pinned head in the same checkout. Every review
check used a `2457313` archive under `/tmp`; commit `256b411` and any later T-078 work are not part
of these dispositions.

**Verdicts:**

- **T-085 — Approved with a planning follow-up.** The record meets its three criteria.
- **T-049 — Approved.** DAT-003's append-only amendment is the correct historical-record shape.
- **T-047 — Changes requested.** The “no” answer is reasoned, but its durable rationale is in the
  wrong canonical document.
- **T-097 — Changes requested.** The new absolute-import cases pass, but an ordinary relative
  spelling bypasses the gate and the shared rule exceeds ARC-007's named module.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `P2PLAN-R8` | **Medium** | **No — T-085 record approval; yes — T-086 readiness** | T-085's original Scope says it delivers the record **and the view**, while the higher-authority Phase 2 plan names only history persistence and records. T-050 points the UI to a nonexistent Phase 3 deliverable, and T-086 presupposes a history view for its history half. The correction correctly refuses to invent the owner, but adding the view to Out of scope does not resolve which task delivers a Phase 2 surface REQ-021 already requires. | Before T-086 becomes Ready, assign the history view explicitly—either amend T-085, make it part of T-086, or create a separate task—and reconcile T-050's stale Phase 3 pointer. The completed record work need not wait on that planning decision. | **Open, non-blocking for T-085** |
| `T047-R1` | **Medium** | **Yes — T-047** | T-047's only deliverable is a recorded choice not to close three known test blind spots. The measurement, trade-off, rejected direction and premise that reopens it live only in mutable TASKS prose. TESTING states what the gate does, but not why these gaps are deliberately accepted. AGENTS §12 assigns “why a durable choice was made” to DECISIONS, and the task's own title and first criterion call this a decision. | Add a durable decision entry with the measured current structure, the five failed enumeration attempts, the limited purpose of the gate, and the structural changes that reopen the choice. Link TESTING and T-098 to it. | **Open** |
| `T097-R1` | **Medium** | **Yes — T-097** | `imported_modules()` ignores every relative `ImportFrom` (`node.level != 0`). In an isolated `2457313` archive, adding `from ..core import settings` to the real `downloader/manager.py` left **all 23 boundary tests passing**; `from .. import persistence` is likewise invisible. Separately, adding an absolute settings import to `result_pump.py` fails even though ARC-007 and T-097 name only `manager.py`. The failure message then talks about repository injection for a settings violation. The gate is both bypassable and broader than its authority. | Resolve relative imports against the module under analysis; mutation-check relative settings and persistence spellings against the real manager. Represent prohibitions per module so persistence remains where ARCHITECTURE §3 puts it while ARC-007's settings rule applies only to manager.py. Add an allowed result-pump/settings synthetic case unless ARC-007 is deliberately amended, and give each rule its own diagnostic. | **Open** |
| `COORD-R11` | **Low** | **No — this review supersedes the pending summary** | At `2457313`, TASKS first says “In Review: nothing,” later lists all four tasks In Review, retains “Proposed review follow-up: T-097,” and labels the In Review section empty immediately before the four entries. The commit did restore the missing Ready heading and physical placement, but its live summary still gives incompatible answers. | Rebuild the top summary and In Review note once these four dispositions are filed. T-096 remains the structural owner of this recurring class. | **Open, non-blocking coordination** |

### T-085 — record evidence

**The projection/live split is accepted.** The existing real-completion test drives
`DownloadManager`, `PersistentJobStore`, `QueueWriter` and a fresh database read, proving the path
is composed and durable. The new projection test supplies deliberately non-null values for every
REQ-020 fact and compares one complete `HistoryEntry`, proving that the persistence projection
does not discard one merely because the local HTTP fixture lacks metadata. Neither test is asked to
claim what its fixture cannot establish.

The lifetime evidence is also proportionate. Directly deleting the job proves the present schema
does not couple the rows, while reading the `history` definition independently rejects a declared
foreign-key relationship. T-081 must still avoid adding an explicit second history deletion when
its clear-completed operation exists; T-085 cannot drive an operation that has not been built.

### T-049 — decision amendment

**Amend, not rewrite, is the correct §6 reading.** DAT-003 is historical record. Its appended
amendment explicitly supersedes the false scope rows, preserves why they were once believed, and
restates the controlling rule by provenance without silently changing the accepted verbatim-storage
trade-off.

The challenged facts reproduce: a source URL containing userinfo is accepted, and
`cookies_from_browser` accepts path-shaped text. REQ-026 already binds only application-supplied
values and links DAT-003; the amendment adds cookie-file support and new secret-bearing persisted
fields as pre-implementation reopening conditions. T-038 remains origin-agnostic at emission.

### T-047 — decision substance

**The substantive “no” is defensible.** Parsing the pinned environment module finds exactly the
reported top-level shape: no module-scope `if`, no module-scope `try`, and no call to `globals`,
`locals`, `setattr`, `vars`, `exec` or `eval`. The gate is not a security boundary, five syntax
enumerations already failed, and the interpreter-namespace check still catches the accidental
public export it exists to catch. T-098 is a reasonable separate guard on the measured premise.

What is not accepted is treating TASKS plus TESTING as the durable decision record. TESTING owns
the executable/testing promise; it does not preserve the rationale for knowingly leaving the three
blind spots open.

### T-097 — what remains valid

Recording `node.module + alias.name` fixes two real absolute-import holes:
`from tracks_and_trails.core import settings` and the pre-existing
`from tracks_and_trails import persistence`. The dot-boundary matching and legitimate-import cases
are useful, and no implementation change to ARC-007 is needed. The correction should retain those
parts while making the rule module-specific and relative-import aware.

### Independent verification

| Check | Result |
|---|---|
| Isolation | All reviewed files came from a `git archive` of `2457313`; concurrent T-078 work was excluded |
| Span identity | Four commits in `1beb6f8..2457313`, matching the four handed-off sections |
| `git diff --check 1beb6f8..2457313` | Passed |
| Authorship / trailers | Sean Kottman on all four commits; no AI author or co-author trailer |
| T-085 new record tests | **3 passed** |
| Existing real-completion history path | **1 passed** with loopback sockets permitted |
| T-085 `format_used → None` production-only mutation | **Killed** by the unmodified whole-entry projection test |
| T-097 baseline boundary file | **23 passed** |
| T-097 relative manager/settings mutation | **Survived: 23 passed** |
| T-097 result-pump/settings mutation | Failed, confirming the surplus prohibition |
| DAT-003 fact probes | Userinfo URL accepted; path-shaped `cookies_from_browser` accepted |
| T-047 AST measurement | No top-level `if`/`try`; no named dynamic-rebinding calls |
| Full pinned default suite | **1467 passed, 11 skipped, 2 deselected in 128.60 s** |
| Bare `mypy` | Passed; **78 files** |
| Bare `mypy --platform win32` | Passed; **78 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **106 files** already formatted |
| Windows runtime | Not run; no production file changed in the pinned four-task span |

### Final disposition

T-085's record implementation is **Approved at `36bfba6`**, with P2PLAN-R8 blocking T-086
readiness rather than reopening the completed persistence evidence. T-049 is **Approved at
`0027299`**.

T-047 is **Changes requested at `e8af655`** until its accepted “no” has a DECISIONS entry. T-097
is **Changes requested at `2457313`** until relative imports cannot bypass it and the settings
prohibition is narrowed to ARC-007's manager boundary. Those corrections are independent and may
return as separate focused passes.

## 2026-07-30 — T-091 / T-096 / T-098 three-task review

**Reviewer:** Codex (Reviewer)
**Pinned span:** `34addcb..9860c2f`
**Per-task boundaries:** T-096 `34addcb..7d1fd04`; T-098 `7d1fd04..5ab8f49`; T-091
`5ab8f49..9860c2f`
**Boundary treatment:** three commits and three initial task reviews. All inspection and runtime
checks used a `9860c2f` archive under `/tmp`, so later T-089/T-078 work in the primary checkout is
excluded.

**Verdicts:**

- **T-091 — Changes requested.** The OSError predicate is appropriately narrow, but the adjacent
  broad catches still turn malformed queue payloads into orderly end-of-stream, and two explicit
  acceptance tests were not delivered.
- **T-096 — Changes requested.** Status/section mismatches are detected only for entries that
  already have a status; an entry with no status is silently omitted.
- **T-098 — Approved.** The OPS-008 premise guard is proportionate, and the inverted shape check
  is independently load-bearing.

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T091-R1` | **Medium** | **Yes — T-091** | `core/logging.py:576-587` says `EOFError` and `ValueError` are unambiguous closure signals and converts every instance to the listener sentinel. They are also deserialization failures on the real queue path. Writing `b""` and `b"\x80\xff"` through a real `multiprocessing.Queue` pipe made `Queue.get()` raise `EOFError("Ran out of input")` and `ValueError("unsupported pickle protocol: 255")`; the committed `dequeue()` returned its sentinel for both. The listener would then exit normally and sweep pending drains, reproducing T090-R1's silent log-loss consequence one exception type over. | Suppress only the verified same-process-close form of `ValueError`, and distinguish an expected lifecycle EOF from malformed/truncated serialization before suppressing it. Add real-queue regressions for both malformed payloads and mutation-check the classification. | **Open** |
| `T091-R2` | **Medium** | **Yes — T-091** | Two acceptance criteria remain unevidenced. `test_a_non_closure_oserror_propagates_out_of_dequeue` at `test_logging.py:867-881` supplies a fake object whose `get()` raises directly, not the required real `multiprocessing.Queue.get()` path. The required dedicated one-lifecycle post-registration delivery assertion is absent: `test_the_log_listener_is_not_left_reading_a_closed_queue` checks only stderr, while the only delivery count at lines 771-797 is the pre-existing **two-lifecycle** T074-R2 test. The task's own evidence says that named one-lifecycle test passes when the registration defect is restored. | Inject a non-closure OSError through an actual queue reader so `Queue.get()` is in the call path. Add the specified one-lifecycle application-logger delivery count and show the unmodified test fails when `_wait_at_exit` is moved back to import time with the closure guard retained. | **Open** |
| `T096-R1` | **Medium** | **Yes — T-096** | `live_entries()` at `test_task_placement.py:81-102` adds a task only after it finds a `**Status:**` line. `test_each_entry_states_its_status_once` counts headings but reports only counts greater than one, never zero. Removing T-091's only status line left 95 entries, above the anti-vacuity threshold, and all **12 placement tests passed**. The gate therefore does not enforce the first criterion that every live entry exposes exactly one status and can skip an entry entirely. | Parse headings independently, retain every live task in the result, and assert each has exactly one status—including reporting zero. Mutation-check removal of one existing status line with the committed tests unchanged. | **Open** |

### Review judgments

**The literal OSError match is accepted.** Equality with CPython's exact
`OSError("handle is closed")` sentinel is narrower than either substring matching or accepting
every errno-less OSError. The committed negative case proves prose merely containing the phrase
still raises. If the supported runtime changes its private sentinel, failing loudly is safer than
silently widening the transport-fault catch.

**The `setattr` test setup is accepted.** `OSError.winerror` is platform-dependent, and the local
assignment is test construction rather than production namespace manipulation. The targeted
`B010` suppression is explicit; both host and Win32 whole-project mypy gates pass with the same
source spelling.

**T-098's inverted check is load-bearing.** Adding a module-scope `for` to the real environment
module left all three named construct checks green (**7 tests passed** when the inverted test was
deselected) and failed only `test_the_module_scope_is_still_the_shape_ops_008_measured`, naming
`For` and directing the reader to revisit OPS-008. That is the claimed distinction between an
enumeration of the three known gaps and a closed description of the measured module shape. The
failure asks for decision review rather than forbidding the production construct, so the broader
tripwire does not silently expand OPS-008.

### Independent verification

| Check | Result |
|---|---|
| Isolation | All reviewed files came from a `git archive` of `9860c2f`; later primary-checkout work was excluded |
| Span identity | Exactly three commits in `34addcb..9860c2f`, one for each handed-off task |
| `git diff --check 34addcb..9860c2f` | Passed |
| Authorship / trailers | Sean Kottman on all three commits; no AI author or co-author trailer |
| Focused changed tests | **67 passed in 8.00 s** |
| Real Queue malformed-payload probes | Direct `Queue.get()` raised EOFError / ValueError; committed `dequeue()` returned its sentinel for both |
| T-096 missing-status mutation | **Survived: 12 passed** |
| T-098 unlisted module-scope `for` mutation | Named checks **7 passed**; inverted shape test failed on `For` |
| Full pinned suite | **1555 passed, 11 skipped, 2 deselected in 131.04 s**, with loopback allowed and an isolated writable cache |
| Bare `mypy` | Passed; **81 files** |
| Bare `mypy --platform win32` | Passed; **81 files** |
| `mypy src` / `mypy --platform win32 src` | Passed; **35 source files** in each mode |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **109 files** already formatted |
| Windows runtime | Not rerun for this span; WinError 6 is exercised synthetically and both Win32 type gates pass |

### Final disposition

T-098 is **Approved at `5ab8f49`**. Its named premise checks and inverted shape assertion jointly
guard OPS-008 without claiming to close the three accepted blind spots.

T-091 is **Changes requested at `9860c2f`** for T091-R1 and T091-R2. T-096 is **Changes requested
at `7d1fd04`** for T096-R1. These are initial reviews of the new task IDs, so each has its ordinary
focused correction pass available under AGENTS §10.

## 2026-07-30 — T-091 / T-096 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Correction boundary:** `92903f3..25f7879`
**Inherited implementation heads:** T-091 `9860c2f`; T-096 `7d1fd04`
**Boundary treatment:** `92903f3` records the initial review and changes no implementation.
`25f7879` is the one correction commit. Every check used a `25f7879` archive under `/tmp`, excluding
any later T-089/T-078 work in the primary checkout.
**Verdict:** **Approved — T091-R1, T091-R2 and T096-R1 Resolved**

### Finding disposition

| ID | Severity | Blocks approval | Independent evidence | Status |
|---|---|---:|---|---|
| `T091-R1` | **Medium** | **No — resolved** | `dequeue()` now consults the Queue's `_closed` state before suppressing EOFError/ValueError. Through an actual Queue pipe, `b""` raised EOFError and `b"\x80\xff"` raised ValueError while `_closed` remained false; both propagated through the corrected listener. A closed Queue returned the listener sentinel. Restoring unconditional suppression failed `test_a_deserialization_fault_on_an_open_queue_still_raises`. Keeping the OSError predicate separate is correct: connection-handle teardown can occur without Queue closure state. | **Resolved** |
| `T091-R2` | **Medium** | **No — resolved** | The OSError regression now uses a real `multiprocessing.Queue`, injecting EIO at its `_recv_bytes` seam so `Queue.get()` remains the caller. The new single-lifecycle subprocess installs its slow handler on `APP_SLUG` and counts 40 delivered records. Moving registration back to import time with the closure guard retained produced **0/40** and failed the unmodified test. | **Resolved** |
| `T096-R1` | **Medium** | **No — resolved** | `status_line_counts()` starts from task headings and therefore retains zero-status entries; the separate parse-set comparison guards drift between heading and status views. Removing T-091's sole status line failed both checks, naming T-091 directly (**2 failed, 12 passed**), rather than silently reducing the parsed entry count. | **Resolved** |

### Review judgments

**Queue state is the right discriminator for the sibling exception arm.** `Queue.get()` owns both
the receive and deserialize operations, so EOFError/ValueError alone cannot say whether the stream
ended or a record was malformed. Queue closure state can. The private `_closed` dependency is
contained in a named helper and defaults to false for an unknown queue type, which fails loudly
rather than recreating the original silent-loss behavior.

**The one-lifecycle gate isolates registration order.** Unlike the existing two-lifecycle probe,
it cannot acquire a second exit handler that masks the first handler's wrong ordering. Its
application-logger handler is actually consulted by the production listener, and the 40-record
count—not absence of a teardown exception—is the observable.

**T-096 now has an independent source of task identity.** Counting from headings closes the exact
vacuity in the initial parser. The set comparison is useful defense in depth, while the zero-count
assertion is the load-bearing check for the reported mutation.

### Independent verification

| Check | Result |
|---|---|
| Correction identity | `92903f3..25f7879`, one implementation correction commit touching TASKS, logging source, and the two relevant unit-test files |
| `git diff --check 92903f3..25f7879` | Passed |
| Authorship / trailers | Sean Kottman; no AI author or co-author trailer |
| Focused logging / placement / environment files | **73 passed in 10.34 s** |
| Real malformed Queue payloads | Open queue propagated EOFError / ValueError; closed queue returned the sentinel |
| Unconditional EOFError/ValueError suppression mutation | Killed |
| Import-time registration mutation | Killed — **0 of 40** records delivered |
| Missing-status mutation | Killed — T-091 named by two placement failures |
| Full pinned suite | **1561 passed, 11 skipped, 2 deselected in 131.85 s** |
| Bare `mypy` | Passed; **81 files** |
| Bare `mypy --platform win32` | Passed; **81 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **109 files** already formatted |
| Windows runtime | Not rerun; both Win32 type gates pass and this correction does not change the accepted OSError/WinError predicate |

### Final disposition

T091-R1 and T091-R2 are **Resolved**. T-091 is **Approved at `25f7879`**.

T096-R1 is **Resolved**. T-096 is **Approved at `25f7879`**. No open follow-up was created from
this correction pass.

## 2026-07-30 — Settings / T-047 / T-097 / T-089 backlog review

**Reviewer:** Codex (Reviewer)
**Pinned span:** `2457313..faf374f`
**Unreviewed commits:** settings foundation `256b411`; T-047 correction `321c672`; T-097 correction
`34addcb`; coordination reconciliation `8ea4fc9`; T-089 `128be39`; settings ceiling `faf374f`
**Boundary treatment:** the span contains eleven commits, but `7d1fd04..25f7879` was independently
reviewed in the intervening T-096/T-098/T-091 passes and is not reviewed again here. All checks used
a `faf374f` archive under `/tmp`, excluding later T-078 pool work.
**Verdict:** **Approved with non-blocking follow-ups**

Per subject:

- **ARC-007 settings foundation and ceiling — Approved for T-078 to build on at `faf374f`.** This
  approves `256b411` plus `faf374f`; it is not approval of T-078's still-unimplemented pool,
  main-window control, live propagation, or real-path criteria.
- **T-047 — Approved at `321c672`; T047-R1 Resolved.**
- **T-097 — Approved at `34addcb` with non-blocking diagnostic follow-up T-099; T097-R1 Resolved.**
- **T-089 — Approved at `128be39`.**
- **Coordination reconciliation — COORD-R11 remains Open, non-blocking.** `8ea4fc9` corrected the
  leading summary and filed approved tasks, but did not reconcile the other live-state prose.

### Finding disposition

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T047-R1` | **Medium** | **No — resolved** | `OPS-008` now owns the durable “do not close the three blind spots” decision, including the measured module shape, five failed enumeration attempts, intended gate purpose, alternatives, accepted limits, and explicit reopening conditions. The task links to it and T-098 independently guards its structural premise. | None. | **Resolved** |
| `T097-R1` | **Medium** | **No — resolved** | Relative imports are resolved against the analysed module: a real `from ..core import settings` added to `downloader/manager.py` failed the unmodified boundary file, as did the persistence relatives. Settings prohibitions apply only to manager.py; the result pump remains permitted while the shared T-013 persistence/sqlite rules still bind both modules. | None. | **Resolved** |
| `T097-R2` | **Low** | **No — T-099** | The enforcement is correct but the real-module assertion at `test_manager_boundaries.py:124-138` is still named `test_the_manager_never_imports_persistence` and always explains repository injection. A real relative settings import was correctly reported as `tracks_and_trails.core.settings`, followed by the false explanation “The repository is injected as a protocol.” This leaves T097-R1's requested rule-specific diagnostic unfinished and points the first person who trips ARC-007 at the wrong architecture rule. | Report persistence/sqlite and manager/settings offenders through rule-specific assertions or diagnostics while retaining one real-source read and the current per-module rules. | **Open, non-blocking — T-099** |
| `COORD-R11` | **Low** | **No — coordination only** | The new leading queue summary is materially better, but current TASKS still says `## In Review` is empty immediately above T-089, T-047 and T-097; lines 63-67 call approved T-091/T-096 Ready and now-In-Review T-089 Ready; lines 80-83 say Phase 1 exit criterion 7 is unmet; and lines 97-99 say Phase 1 “is not ready,” contradicting the current header that Phase 1 exited with all eight criteria met. T-096 passes because these are prose contradictions rather than status/section mismatches. | Remove or explicitly mark the obsolete live-state blocks as historical, and make the In Review note name the actual entries. Rebuild from the current sections as COORD-R11 originally required rather than retaining several prior snapshots beneath the new one. | **Open — correction incomplete** |

### Settings-layer judgments

**The ceiling is accepted.** REQ-013 names default 3 and minimum 1 but also calls the concurrent
pool “bounded.” ARC-007's maintainer amendment fills the unspecified upper bound without
contradicting the requirement. Six independent failures after removing the upper clamp confirm the
file path and live-update helper both enforce the decision. Sixteen is candidly a typo guard rather
than a hardware measurement, and the decision records the process-per-job reopening condition and
the risk of obstructing a legitimate power user.

**Hand-formatted TOML is proportionate.** The only emitted value is an already-validated integer,
so there is no quoting or escaping surface. Adding a runtime writer dependency for one scalar would
require its own architectural decision and would not make this output safer. The whole-object
round-trip test will expose a future field that `save()` forgets, at which point Phase 4 can
reconsider the implementation.

**The duplicated `APP_SLUG` is accepted.** Importing it from downloader or UI would create a
wrong-direction dependency from core. Centralising the slug would require moving the existing
owners into a new neutral module; that is a separate refactor with no behavioral gain in this
foundation commit.

**Never-raising load/save is accepted for this phase.** Missing, unreadable and malformed settings
falling back to defaults is an explicit T-078 criterion whose first obligation is that the
application starts. A read-only configuration directory must likewise not turn shutdown into a
crash. The trade-off is real—corruption and failed persistence are not surfaced—but no Phase 2
diagnostic surface is specified. Revisit it when Phase 4 introduces the settings dialog rather
than inventing a hidden exception policy now.

**P2PLAN-R8 remains unresolved.** The history-view owner still blocks T-086 readiness exactly as
the prior review recorded. Nothing in these six subjects assigns it, and it does not block the
settings foundation, T-047, T-097, T-089, or T-078 implementation.

### Independent verification

| Check | Result |
|---|---|
| Isolation | All reviewed content came from a `faf374f` archive; later pool work was excluded |
| Span accounting | Eleven commits in `2457313..faf374f`; six unreviewed commits separated from five already-reviewed commits |
| `git diff --check 2457313..faf374f` | Passed |
| Authorship / trailers | Sean Kottman on all six unreviewed commits; no AI author or co-author trailer |
| Settings file | **39 passed** |
| Boundary / environment-shape / task-placement files | **74 passed** |
| T-089 focused cases | **4 passed** |
| Settings upper-clamp removal | Killed — **6 failed, 33 passed** |
| Real relative manager/settings import | Killed — **1 failed, 51 passed** |
| T-089 MP3 → converting-codec enablement mutation | Killed by exactly the FLAC test — **1 failed, 1 passed, 77 deselected** |
| Full pinned suite | **1573 passed, 11 skipped, 2 deselected in 135.38 s** |
| Bare `mypy` | Passed; **81 files** |
| Bare `mypy --platform win32` | Passed; **81 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **109 files** already formatted |
| Windows runtime | Not run; T-089/settings changes are test or platform-neutral core code, and the Win32 type gate passes |

### Final disposition

The previously skipped settings foundation is approved for the pool to consume. The accepted
ceiling stands; corrupt-file fallback, hand-written TOML, the local slug and never-raising file API
are accepted at this phase boundary.

T047-R1 and T097-R1 are **Resolved**. T-047, T-097 and T-089 may be filed Complete at their approved
heads. T097-R2 is a non-blocking diagnostic follow-up owned by T-099. COORD-R11 remains open as a
coordination correction and does not reopen any production or task approval above.

## 2026-07-30 — T-078 initial review

**Reviewer:** Codex (Reviewer)
**Task:** `T-078`
**Pinned span:** `faf374f..1ef59f1`
**Implementation commits:** pool `a642482`; user-facing control `1ef59f1`
**Boundary treatment:** the span also contains review-only `90b8b66` and coordination-only
`b0cec64`; neither is implementation under review here. All source inspection, tests and mutations
used an isolated `1ef59f1` archive. The live checkout advanced to documentation-only `dc50e62`
during the pass and did not enter the evidence.
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Evidence | Recommendation | Status |
|---|---|---:|---|---|---|
| `T078-R1` | **Medium** | **Yes — T-078** | `DownloadManager.active_job_ids()` at `manager.py:519-526` returns only `_sessions ∪ _reserved`, although `_start_when_free()` at `:1021-1032` has accepted jobs into `_waiting`. This contradicts both the method's “Every job this manager is holding” contract and T-078's criterion that `active_job_ids()` account for every waiting job. In the committed waiting-job scenario, `_waiting == ["job-2"]` while `active_job_ids() == ("job-1",)`. Adding the exact expected pair to the unmodified test failed. `is_idle` and shutdown do account for the list, so this is a narrow accounting defect rather than abandoned work. | Include waiting ids in the public accounting result, with duplicate-safe deterministic ordering, and retain a test whose expected set distinguishes the waiting job from the running/reserved reason the method is already non-empty. Recheck the busy diagnostic and shutdown caller against the expanded result. | **Open** |
| `T078-R2` | **Medium** | **Yes — T-078** | The two lowering criteria are not gated. `test_lowering_the_limit_drains_rather_than_killing` lowers three running jobs with **nothing waiting**, so it proves only “does not kill.” All seven committed pool tests still passed after `_fill_free_slots()` was changed to start waiting work specifically while the live count was above the lowered limit. Separately, the only real-control test changes 3 → 5; changing composition to apply increases but merely save decreases left the entire **14-test composition file green**. T-078 explicitly requires lowering through the user-facing path, with in-flight work finishing and no new job starting. | Through the real spinbox/composed graph, lower a saturated pool while another accepted job waits. Assert the original sessions remain, the waiting job does not start while the live count is at or above the new limit, and it becomes eligible only after the pool drains below that limit. Demonstrate that the unmodified test kills both the decrease-not-applied mutation and the over-limit fill mutation. | **Open** |

### Review judgments

**`valueChanged` is accepted.** Entering `12` may transiently apply `1`, but lowering is defined to
drain rather than stop work, and the final increase must start eligible waiting work immediately.
The intermediate value can produce an extra settings write; it cannot kill or retarget a running
job. Nothing in REQ-013 or ARC-007 requires focus loss as the commit point.

**A pool of N does not reopen T-019 on the evidence available here.** Process and containment state
is held per `_Session`, and shutdown/tick iterate every session rather than one shared group. A
reviewer-only probe started three workers, each with a signal-resistant grandchild, then shut down
the manager; all six processes were reaped and the manager reached idle on Linux. That validates
the new iteration shape without rewriting T-019's settled one-tree tests.

**Windows runtime remains unverified.** The Win32 whole-project type gate passes, but it cannot
execute spawn, Job-object containment or simultaneous process teardown. Project policy does not
make a Windows runtime run a completion gate for this source change, so this is an explicit
platform risk rather than a third finding. It should be exercised when hosted Windows capacity is
available, especially because T-078 is the first task to run several worker trees at once.

### Independent verification

| Check | Result |
|---|---|
| Isolation | Source and tests loaded from an exact `1ef59f1` archive |
| Span accounting | Two implementation commits separated from two intervening documentation commits |
| `git diff --check faf374f..1ef59f1` | Passed |
| Authorship / trailers | Sean Kottman on both implementation commits; no AI author or co-author trailer |
| Nine new T-078 pool/control cases | **9 passed** after the loopback-only cases were rerun with socket permission |
| `is_idle` ignores `_waiting` mutation | Killed by the dedicated waiting-with-nothing-running case |
| Reservations omitted above N=1 mutation | Killed by the dedicated limit-2 reservation case |
| Waiting id added to `active_job_ids()` expectation | **Failed as expected:** got only `("job-1",)` |
| Decreases saved but not applied mutation | Survived the complete composition file — **14 passed** |
| Waiting work starts while above the lowered limit mutation | Survived all committed T-078 pool cases — **7 passed** |
| Three-worker / three-grandchild shutdown probe | **1 passed** on Linux |
| Full pinned suite, corrected external XDG paths | **1582 passed, 11 skipped, 2 deselected in 196.86 s** |
| First full-run harness error | XDG cache was incorrectly placed inside the archive; the repository-destination guard correctly failed. Moving it outside made the isolated guard and full rerun pass |
| Bare `mypy` | Passed; **81 files** |
| Bare `mypy --platform win32` | Passed; **81 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **109 files** already formatted |
| Windows runtime | Not run |

### Final disposition

T-078 is **Changes requested at `1ef59f1`**. T078-R1 and T078-R2 are both blocking Medium findings
owned by the existing T-078 correction, so no separate follow-up task is created. The pool's
capacity, reservation, ordering, immediate-raise, settings persistence and Linux multi-tree
shutdown behavior otherwise passed. Approval of the phase's centre—and therefore the dependency
release for its eight descendants—waits on the two focused corrections and their mutation evidence.

## 2026-07-30 — T-078 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-078`
**Correction boundary:** `1ef59f1..0f9986f`
**Correction commit:** `0f9986f`
**Boundary treatment:** the history span also contains the prior review record (`4df0d21`) and the
documentation-only history-view ownership decision (`dc50e62`). The focused implementation
re-review covers only `0f9986f`'s manager and test changes. All checks used an exact isolated
`0f9986f` archive.
**Verdict:** **Approved — T078-R1 and T078-R2 Resolved**

### Finding disposition

| ID | Severity | Blocks approval | Verification | Status |
|---|---|---:|---|---|
| `T078-R1` | **Medium** | **No — resolved** | `active_job_ids()` now returns the duplicate-safe sorted union of sessions, reservations and waiting ids. Restoring the original omission failed the committed pair assertion with `("job-1",)` instead of `("job-1", "job-2")`. The two production callers that need occupancy rather than ownership use `_occupant_ids()`. | **Resolved** |
| `T078-R2` | **Medium** | **No — resolved** | The pool-level and composed-path tests now lower a saturated pool with a fourth accepted job waiting, preserve the three occupants, hold the fourth while the count is above the new limit, and start it only after the pool drains. Applying increases while merely saving decreases failed the composed test at `manager.concurrency == 1`. Allowing `_fill_free_slots()` to start waiting work above the lowered limit failed both pool and composition tests because the waiting list emptied early. | **Resolved** |

### Review judgments

**`_occupant_ids()` is the right split.** The class has three storage collections but only two
semantic questions: every job the manager has accepted, and the subset consuming a pool slot.
`active_job_ids()` answers the first; capacity diagnostics and shutdown cancellation need the
second. Inlining `sessions ∪ reservations` twice would hide that distinction at exactly the two
callers whose behavior changed when waiting ids joined the public answer. The helper introduces a
name for an existing concept, not a fourth state collection.

**The synthetic overlap test earns its place.** Ordinary transitions remove a waiting id before
reserving it, so the overlap is deliberately unreachable today. The assertion protects a public
reporting contract—one logical job appears once—rather than asserting that the internal overlap
must occur. T078-R1 explicitly required duplicate-safe ordering, and the direct arrangement is a
small discriminating test of that property. It is not being offered as lifecycle evidence.

**Submitting to the real store satisfies “through the composed graph.”** The acceptance criterion
is about the concurrency control reaching the live pool. The test uses the real composition,
writer-backed store, manager, settings file and `QSpinBox`; only the worker entry point is the
existing process-boundary stand-in. Typing four URLs into the add dialog would add unrelated
probing/dialog behavior and still could not create the state under test: public `start()` refuses
at saturation, while `_start_when_free()` is the manager's sole waiting-list admission path.
Driving that path directly is therefore the narrow setup for the control → pool assertion, not a
substitute for it.

### Independent verification

| Check | Result |
|---|---|
| Isolation | Source and tests loaded from an exact `0f9986f` archive |
| `git diff --check 1ef59f1..0f9986f` | Passed |
| Authorship / trailers | Sean Kottman; no AI author or co-author trailer |
| Four focused correction cases | **4 passed** |
| Original waiting-id omission | Killed — exact pair assertion failed |
| Original decrease-not-applied mutation | Killed — composed control test failed |
| Original fill-above-lowered-limit mutation | Killed by both pool and composed control tests |
| Full pinned suite | **1586 passed, 11 skipped, 2 deselected in 205.73 s** |
| Bare `mypy` | Passed; **81 files** |
| Bare `mypy --platform win32` | Passed; **81 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **109 files** already formatted |
| Windows runtime | Not run; the explicit platform risk from the initial review remains |

### Final disposition

T078-R1 and T078-R2 are **Resolved**. T-078 is **Approved at `0f9986f`**. No new finding or
follow-up task was created. The phase's central dependency may be filed Complete and its downstream
tasks may use this approved pool/settings/control foundation, subject to their own readiness gates.

## 2026-07-31 — T-079 initial review

**Reviewer:** Codex (Reviewer)
**Task:** `T-079`
**Pinned span:** `df6c7b8..cb008da`
**Implementation commit:** `cb008da`
**Boundary treatment:** the span also contains documentation-only `1be3449`, which routes T-084
to its accepted redaction decision and does not implement T-079. All source inspection, tests,
mutations and probes used an exact isolated `cb008da` archive. The live checkout remained at that
head and clean until this review record was written.
**Platforms verified:** Linux; Win32 static analysis only
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T079-R1` | **Medium** | **Yes — T-079 accuracy criterion** | Attempt lifecycle / row rendering | `_on_job_changed()` replaces only `_Row.job` at `queue_view.py:395-399`; it never retires `displayed` or `totals` when a failed attempt becomes queued again. `refresh()` deliberately preserves the same fields at `:348-356` without distinguishing an attempt boundary. A reviewer-only test drew a running job at 50% with speed and ETA, changed it through `FAILED → QUEUED`, and expected the durable queued state. It failed: the status cell still said **“Downloading video”** instead of **“Queued”**; the old percentage, size, speed and ETA likewise remain eligible until the new attempt emits progress. A saturated pool can leave that lie visible while the retry waits. | On the terminal-to-new-attempt transition, clear pending and displayed live state (or key it to the attempt it belongs to) before rendering the durable row. Add an unmodified regression that first draws non-default stage/totals/speed/ETA, retries the job, and distinguishes every reset field from the old attempt; mutation-check the reset. Audit the detail view's analogous cached-message lifecycle rather than assuming one widget's correction covers both. | **Open** |
| `T079-R2` | **Medium** | **Yes — NFR-001 / interactivity criterion** | GUI-thread persistence read | Every known-row `job_changed` signal calls `_durable()` at `queue_view.py:402-405`, which implements a point lookup by calling `QueueReader.all_jobs()` and scanning the result. In the real graph that reaches `PersistentJobStore.all_jobs()` at `store.py:85-92`, then `SELECT * ... fetchall()` plus deserialization of every stored job at `repositories.py:258-267`, synchronously in the Qt slot. This contradicts `ARCHITECTURE.md:114-115`, whose allowed synchronous GUI reads are **indexed single-row lookups**, and makes each transition scale with queue history. A delayed local-reader probe made one status change spend **150.7 ms** in the slot, beyond NFR-001's ~100 ms interaction budget; the committed responsiveness test has only three rows, so the full enumeration is too cheap there to expose the path. | Give `QueueReader` an indexed `get(job_id)` shape (already supplied by `PersistentJobStore`) and use it for known-row state changes, retaining `all_jobs()` for initial/explicit refresh only. Add a gate proving a known-row signal does not enumerate the queue and a budget probe whose single-row lookup remains fast when full enumeration is slow or large. | **Open** |

### Review judgments

**The one-timer/table design is sound.** Redirecting every live message into row zero made both
the widget-level live-row test and the real composed-application test fail. Four hundred messages
across eight rows are absorbed without a draw and rendered on one timer tick. T079-R2 is therefore
not a rejection of the coalescing design; it is a separate blocking read performed by each durable
status update.

**Preserving drawn totals across a refresh remains necessary within one attempt.** The committed
refresh test correctly protects T017-R4/T-059's ending rule. T079-R1 requires an attempt boundary,
not unconditional deletion on every rebuild: a newly added neighbour must not erase the closer
live total of a still-running job, while `FAILED → QUEUED` must not carry the failed attempt's live
message into the retry.

**Windows runtime remains unverified.** The queue table and coalescing logic are platform-neutral
Qt code, and the required Win32 whole-project type gate passes. The composed evidence nevertheless
spawns three workers, so the T-078 Windows multi-process risk remains relevant. Project policy does
not make a Windows runtime run a completion gate for this task; this is an explicit residual risk,
not a third finding.

### Independent verification

| Check | Result |
|---|---|
| Isolation | Source and tests loaded from an exact `cb008da` archive |
| Span accounting | T-079 implementation `cb008da` separated from documentation-only `1be3449` |
| `git diff --check df6c7b8..cb008da` | Passed |
| Authorship / trailers | Sean Kottman on both commits; no AI author or co-author trailer |
| Queue-view file | **26 passed** |
| Three T-079 composed cases | **3 passed, 15 deselected** |
| Previous-attempt live-state probe | **Failed as expected:** re-queued row said `Downloading video`, not `Queued` |
| GUI-thread full-enumeration budget probe | **Failed as expected:** one status slot took **150.7 ms** |
| Live progress routed into row zero mutation | Killed by both independent-progress gates — **2 failed, 42 deselected** |
| First full pinned run in restricted sandbox | **1593 passed, 11 skipped, 2 deselected; 22 failed solely because loopback socket creation was denied** |
| Full pinned suite with loopback permission | **1615 passed, 11 skipped, 2 deselected in 204.63 s** |
| `mypy src` | Passed; **35 files** |
| Bare `mypy` | Passed; **82 files** |
| Bare `mypy --platform win32` | Passed; **82 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **110 files** already formatted |
| Windows runtime | Not run |

### Final disposition

T-079 is **Changes requested at `cb008da`**. T079-R1 and T079-R2 are blocking Medium findings
owned by the existing T-079 correction, so no separate follow-up task is created. The focused
re-review should verify the old-attempt reset with an unmodified discriminating test, verify that
known-row status changes use an indexed read rather than full enumeration, and rerun the affected
queue/composition evidence. The task cannot be filed Complete or release T-080/T-081 until both
findings are independently resolved.

## 2026-07-31 — T-079 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Task:** `T-079`
**Correction boundary:** `cb008da..da49a51`
**Correction commit:** `da49a51`
**Boundary treatment:** the span also contains review-only `2fd9208`; the focused implementation
re-review covers `da49a51`'s two UI modules, their tests and the finding response in TASKS. All
source inspection, tests and mutations used an exact isolated `da49a51` archive. Unrelated live
work entered three downloader/core files and two associated tests while the review ran; none
entered the evidence or the review edits.
**Platforms verified:** Linux; Win32 static analysis only
**Verdict:** **Approved with non-blocking follow-up — T079-R1 and T079-R2 Resolved**

### Finding disposition

| ID | Severity | Blocks approval | Verification | Status |
|---|---|---:|---|---|
| `T079-R1` | **Medium** | **No — resolved** | A queued row now drops pending progress and calls `_Row.retire_live_state()`, while `JobProgressView` clears its pending/drawn message, failure, speed and ETA and re-adopts durable totals. The committed regressions distinguish 50% live state from a 10% durable row and retain 50% across an ordinary same-attempt refresh. Independently removing the table retirement failed with `Downloading video` instead of `Queued`; retaining the detail view's drawn message, failure or speed each failed its unmodified test; deleting preservation on every refresh failed with 10% instead of 50%. | **Resolved** |
| `T079-R2` | **Medium** | **No — resolved** | `QueueReader` now exposes `get(job_id)` and known-row status changes use exactly that lookup; `all_jobs()` remains on construction/explicit refresh. Restoring a scan made the structural gate report one enumeration and zero indexed lookups, and made the independent budget gate spend **250.3 ms** in the Qt slot. | **Resolved** |
| `T079-R3` | **Low** | **No — T-101** | The correction resets both detail-view labels, but `test_retrying_a_job_retires_the_failed_attempts_live_state` asserts only `speedValue`. Deleting only `_eta.setText(UNKNOWN_TEXT)` left the complete **82-test** detail-view file green, so the response's combined “speed and ETA labels” mutation does not independently gate its ETA half. The shipped behavior is correct and the original blocker is resolved; this is test granularity, not an observable defect at `da49a51`. | **Open, non-blocking — T-101** |

### Review judgments

**Status is the usable attempt boundary.** `Job.attempts` is persisted and validated but no
production path increments it; comparing it would leave every retry at zero and never retire old
state. `FAILED → QUEUED` is the explicit REQ-018 retry edge and gives both views the boundary they
need without inventing an attempt identity this model does not maintain.

**The correction is not over-applied.** A normal `refresh()` still transfers `displayed` and
`totals` into the rebuilt row. Removing that transfer failed the committed lagging-row scenario,
so fixing retry does not reopen T017-R4/T-059 by discarding closer live totals whenever a neighbour
is added.

**The two T079-R2 gates answer different questions.** The enumeration/lookup counters enforce the
indexed-read architecture even when a small in-memory queue is fast; the delayed enumeration
measures NFR-001's consequence. Restoring the scan failed both for their own reasons.

**T079-R3 does not consume another T-079 pass.** The ETA reset exists and works in the reviewed
source. Under AGENTS.md §10, a new Low test-strength gap found during the focused re-review becomes
a named non-blocking follow-up rather than reopening an otherwise-correct task. T-101 owns the
single-label assertion and its ETA-only mutation.

**Windows runtime remains unverified.** The correction changes platform-neutral Qt state and a
repository protocol already implemented by the composed store; the Win32 whole-project type gate
passes. The previously recorded Windows multi-process residual risk remains and is not enlarged by
this correction.

### Independent verification

| Check | Result |
|---|---|
| Isolation | Source and tests loaded from an exact `da49a51` archive |
| Boundary accounting | Review-only `2fd9208` separated from implementation `da49a51` |
| `git diff --check cb008da..da49a51` | Passed |
| Authorship / trailers | Sean Kottman on both commits; no AI author or co-author trailer |
| Six focused correction cases | **6 passed, 107 deselected** |
| Complete affected UI files | **113 passed** |
| Table keeps old drawn state | Killed — queued row still said `Downloading video` |
| Every refresh clears live state | Killed — same-attempt row fell from 50% to its durable 10% |
| Detail view keeps drawn state | Killed — re-queued detail remained at the prior ending |
| Detail view keeps failure | Killed — public `failure` retained the prior network error |
| Detail view keeps speed | Killed — label retained `2.1 MB/s` |
| Detail view keeps ETA only | **Survived:** complete detail-view file remained **82 passed** — `T079-R3` / T-101 |
| Status lookup restored to full enumeration | Killed by both gates — one enumeration observed and **250.3 ms** elapsed |
| Full pinned suite | **1621 passed, 11 skipped, 2 deselected in 144.87 s** |
| `mypy src` | Passed; **35 files** |
| Bare `mypy` | Passed; **82 files** |
| Bare `mypy --platform win32` | Passed; **82 files** |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **110 files** already formatted |
| Task-placement invariant after filing T-101 | **14 passed** |
| Windows runtime | Not run |

### Final disposition

T079-R1 and T079-R2 are **Resolved**. T-079 is **Approved at `da49a51`** and may be filed
Complete, releasing T-080 and T-081 subject to their remaining gates and maintainer decisions.
T079-R3 is a non-blocking Low test-strength follow-up owned by T-101; it does not reopen T-079 or
require another focused pass.

## 2026-07-31 — T-080 and T-081 initial review

**Reviewer:** Codex (Reviewer)
**Tasks:** `T-080`, `T-081`
**Review base:** `733209d`
**Implementation boundary:** the bounded uncommitted T-080/T-081 source and test diff over that
base; the implementation source was not edited during review. Reviewer-only regression tests were
added to the three existing test files named below. The two handoff files named by the maintainer
were not present in the checkout, so the matching `TASKS.md` handoff sections supplied the stated
boundary, risks and evidence.
**Platforms verified:** Linux; Win32 static analysis only
**CI:** Not run — consistent with the handoff and current `STATUS.md`; no CI result is claimed.
**Verdict:** **Changes requested**

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T080-R1` | **High** | **Yes — UX-001 / REQ-015** | Pause admission | `pause()` gates `_fill_free_slots()` and `_start_when_free()`, but `start()` itself has no pause check (`manager.py:811-894`). The comment at `:594-597` exempts a direct start because the add dialog must still probe, but the exemption is not limited to `SessionKind.PROBE`. The normal add-after-probe path calls `start(job_id, SessionKind.DOWNLOAD)` (`add_dialog.py:968`), so pressing Add while paused starts a new download. The implementer test described a probe but called `start("job-1")`, whose default is `DOWNLOAD`, and therefore positively protected the defect. The reviewer split the cases: the explicit PROBE case passes; the DOWNLOAD negative fails with occupant `('job-1',)`. | Exempt only metadata probes. Route or refuse direct `DOWNLOAD` starts while paused so the durable queued job remains for resume, and retain the paired PROBE/DOWNLOAD regression. Exercise the composed add-after-probe path while paused if the correction changes that call site. | **Open** |
| `T080-R2` | **High** | **Yes — T-080 visible remove behavior** | Queue view / composition | Remove reaches the real manager and writer and deletes the row, but the row remains visible. `DownloadManager.job_removed` is emitted only after durability, yet `QueueModel` connects only `progress` and `job_changed` (`queue_view.py:216-218`) and composition adds no removal listener. Qt reports zero receivers. The assembled regression successfully waits until `store.get("job-2") is None`, then fails because the model still contains `job-2`. The user is shown a job that no longer exists, and another unrelated refresh is the only workaround. | Connect the durable removal signal to the queue UI, update or refresh the model only after success, and detach the connection with the existing model lifecycle. Keep the assembled control → manager → writer → table regression. | **Open** |
| `T081-R1` | **High** | **Yes — T-081 scheduler-order acceptance criterion** | Reorder/start race | The single writer serialises writes but not the GUI-thread scheduling read that precedes a start write. While `reorder(["job-2", "job-1"])` is in flight, `resume()` or a tick can run `_next_waiting()` against the old positions at `manager.py:1312-1333`, choose job-1, and queue its start transition. The writer then commits the reorder first and job-1's start second: both writes succeed, while the committed queue says job-2 is first. A held-reorder regression deterministically fails because job-1 becomes the occupant before the reorder callback. | Treat an in-flight reorder as an admission barrier (including tick, resume and limit-change paths), then fill slots from durable positions after it settles. Define and test the failure path as well: a refused reorder must release the barrier and schedule from the unchanged order. Audit multiple queued reorder requests rather than representing the barrier as a boolean that the first callback can clear too early. | **Open** |
| `T081-R2` | **High** | **Yes — REQ-016 visible behavior** | Queue view / composition | Reorder and Clear finished both commit through the assembled toolbar path, but the table never reflects either result. `queue_reordered` and `queue_cleared` have zero UI receivers for the same reason as T080-R2. The real-store regressions observe `job-2, job-1, job-3` durably while the table remains `job-1, job-2, job-3`, and observe a cancelled row deleted while it remains onscreen. This directly contradicts the handoff's claim that the view refreshes from the reorder callback and leaves Clear finished appearing to do nothing. | Wire both success signals into one explicit queue-model refresh/update path, preserve persist-then-announce ordering, and add the two assembled regressions. A persistence failure must retain the old model rather than applying the requested order optimistically. | **Open** |
| `T081-R3` | **Medium** | **Yes — observable control correctness** | Selection state | `QueueView._announce_selection()` emits only when a row exists, while `MainWindow._selection_changed()` is the sole action-state updater. Clearing selection therefore sends nothing and leaves Remove, Move up and Move down enabled for no selected row. The reviewer regression selects a pending row, calls the real table's `clearSelection()`, and all three actions remain enabled; their handlers then silently do nothing. Model resets required by T080-R2/T081-R2 reach the same state. | Represent deselection explicitly and disable every per-job action when it occurs. Gate move directions at the ends as well if the correction centralises action-state calculation; retain a test that clears selection independently of a model refresh. | **Open** |
| `T080-R3` | **Medium** | **Yes — current architecture materially misstates behavior** | State-machine documentation | T-080 removes `JobStatus.PAUSED` and its transitions under the accepted UX-001 decision, but current `ARCHITECTURE.md:223-238` still draws `RUNNING → PAUSED → RUNNING`. The source comment says its transition table is transcribed from that diagram while deliberately no longer matching it. This is not harmless history: the canonical current architecture still advertises per-job pause capability the product explicitly rejected. | Have an authorised architecture owner update §5 to the accepted queue-level drain and remove the per-job state/edges. Keep the rationale in UX-001 rather than duplicating it. | **Open** |

### Review judgments

**The persistence primitives are otherwise coherent.** Repository reordering validates all ids
and statuses inside the transaction, temporarily leaves the unique partial index through `NULL`,
and rolls both phases back together on failure. The real toolbar regressions prove that reorder,
remove and clear reach those primitives through `app.py`; the failure is the missing return path
to the table, not the injected handlers or the database operations.

**The reorder race is not closed by FIFO writer delivery.** FIFO is what makes the reproduced
outcome deterministic: reorder commits, then the already chosen old-head job transitions. The
stale decision happens before either write, on the GUI thread. Any correction that changes only
the transaction or signal ordering leaves that decision window open.

**T080-R1 is distinct from the scheduler race.** It needs no write latency and no reorder. The
public direct-start path simply bypasses the only pause guards. The probe exception is required;
the download exception is the violation.

**The view defects are user-visible, not test-strength notes.** In every assembled probe the
database reaches the requested state. The user-facing queue alone remains wrong indefinitely,
which is core functionality these tasks exist to deliver and therefore High rather than a Low
request for extra integration coverage.

**Windows runtime remains unverified.** The whole-project Win32 type gate passes, but no Windows
process or Qt runtime check ran. That residual matches the handoff and is not an additional
finding.

### Independent verification

| Check | Result |
|---|---|
| Review boundary | Base `733209d`; implementation source left unchanged; reviewer tests only |
| `git diff --check` | Passed |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **110 files** already formatted |
| `mypy src` | Passed; **35 source files** |
| `mypy --platform win32 src` | Passed; **35 source files** |
| Five affected files without reviewer negatives | **262 passed, 7 reviewer tests deselected**; 16 loopback cases required the permitted rerun outside the restricted network sandbox |
| Reviewer pause pair | Explicit PROBE **passed**; direct DOWNLOAD **failed as expected** with job-1 occupying a slot |
| Reviewer reorder/start race | **Failed as expected**; job-1 occupied the slot while the new order naming job-2 first was in flight |
| Assembled queue controls | Pause **passed**; reorder, remove and clear each reached the real store, then **failed as expected** on the stale table |
| New manager-signal receiver gate | **Failed as expected**; `job_removed`, `queue_reordered` and `queue_cleared` each have zero UI receivers (`queue_paused` has one) |
| Deselection action-state gate | **Failed as expected**; all three per-job actions remained enabled |
| Full suite / CI / Windows runtime | Not run |

### Final disposition

T-080 and T-081 are **Changes requested** against the uncommitted implementation over `733209d`.
The focused correction re-review should verify all six findings and the correction diff, including
the reorder-failure and multiple-in-flight cases named in T081-R1. Reviewer regressions are left in
place as failing evidence. No task or status coordination file was changed by the reviewer.

## 2026-08-01 — complete overnight batch review

**Reviewer:** Codex (Reviewer)
**Review base:** `da49a51` — T-079's approved head
**Review head:** `05e5312`
**Complete span:** `da49a51..05e5312` — twelve commits, including the T-080/T-081 correction,
T-046, T-053, T-083, T-102, T-087, T-099, T-101, T-092 and T-103
**Platforms verified:** Linux; Win32 static analysis only
**CI:** no job has executed a step since 2026-07-30 04:08 UTC; no CI evidence is claimed
**Boundary treatment:** T-080/T-081 received the focused correction pass allowed by their six
initial findings. Every other named task received its initial review. Reviewer-only tests were
added for four reproduced defects and one diagnostic-gate strengthening; production source was not
edited.
**Overall verdict:** **Changes requested**

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-080` | **Approved at `05e5312`** | T080-R1, T080-R2 and T080-R3 are resolved. Pause parks direct downloads while retaining the explicit probe exemption; durable removal refreshes the table; current architecture no longer advertises per-job `PAUSED`. |
| `T-081` | **Changes requested** | T081-R2 and T081-R3 are resolved, and the counter handles the tested waiting-list paths, refusal and multiple reorders. T081-R1 remains open because public direct DOWNLOAD admission bypasses the barrier. |
| `T-046` | **Changes requested** | T046-R1 reproduces silent overwrite of a post-processed final file. |
| `T-053` | **Approved at `05e5312`** | The concurrent process/log-queue test establishes overlapping live workers, deliberate interleaving, per-job isolation, shared-log delivery and rejection of unstamped records. |
| `T-083` | **Changes requested** | T083-R1 changes a failed metadata probe into a DOWNLOAD on the first automatic retry. |
| `T-102` | **Changes requested** | T102-R1 lets non-UTF-8 settings bytes escape as `UnicodeDecodeError`, violating `load()`'s never-raises/start-with-defaults contract. |
| `T-087` | **Blocked; changes required before Windows verification** | The Linux implementation is coherent, but T087-R1 covers an unexecuted Windows primitive that also differs from ARC-006's accepted primitive. The task's own both-platform criterion and A-004 remain unmet. |
| `T-099` | **Approved at `05e5312`** | Each prohibited boundary maps to its own decision and the real failing assertion now has a reviewer gate, not only the explanation helper. |
| `T-101` | **Approved at `05e5312`** | The test first proves ETA is non-default and then independently asserts its reset; the T079-R3 gap is closed. |
| `T-092` | **Changes requested; not complete** | Three acceptance criteria remain externally unmet as recorded, and T092-R1 makes the prepared automatic upload unsafe and causally ambiguous even before STARBASE execution. |
| `T-103` | **Approved at `05e5312`** | Cancellation drops waiting intent at the cause; remove drops retry intent; clear-after-cancel remains covered without the unreachable sweep. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T081-R1` | **High** | **Yes — T-081** | Reorder admission barrier | The correction gates `_fill_free_slots()` and `_start_when_free()` on `_reorders_in_flight` (`manager.py:1410`), but public `start(..., DOWNLOAD)` checks only pause before reserving and persisting a start (`:894-942`). The add-dialog seam uses that public path. A reviewer regression holds `reorder([job-2, job-1])`, directly starts job-1, and finds `('job-1',)` occupying the pool before the reorder settles. The new durable order can therefore say job-2 first while job-1 has already been admitted. This is the untested third path named in the handoff and a continuation of the original High finding, not a new review round. | Apply the same in-flight-reorder admission rule to every DOWNLOAD entry, including public `start`; park the intent and admit from durable positions after the final reorder settles. Preserve the PROBE exemption explicitly. | **Open** |
| `T046-R1` | **Critical** | **Yes — T-046; data loss** | Final output collision | The worker reserves only the pre-postprocessor target (`worker.py:450-469`). It then passes `overwrites=True`, and when yt-dlp reports a different final extension it merely releases the old reservation (`:471-480`). A real yt-dlp/ffmpeg MP3 download with an existing final `master.mp3` replaced that user's bytes with an ID3 file. The `O_EXCL` guarantee at `:873-900` never covered the file that survived conversion, so the comment that overwrite is safe is false for every extension-changing postprocessor. Concurrent MP3 jobs have the same unclaimed-final-path race. | Reserve/claim the actual final path atomically, or use an yt-dlp/postprocessor collision mechanism that protects both source and final names without global overwrite. Keep the real existing-MP3 regression and add a concurrent extension-changing pair. Preview must show the chosen final name. | **Open** |
| `T083-R1` | **High** | **Yes — T-083** | Retry operation identity | `_retry_at` stores only `job_id -> deadline` (`manager.py:1990-1997`); `_perform_due_retries()` later calls `_start_when_free(job_id)`, which reaches `start(job_id)` with the default DOWNLOAD kind (`:1999-2015`, `:1419-1425`). The reviewer started a PROBE, made it fail NETWORK, and recorded the spawned kinds as `['probe', 'download']`. A transient preview failure can therefore begin writing media without the user confirming a download. All committed retry tests start the default DOWNLOAD kind, so none distinguishes this. | Carry the failed session kind through retry scheduling and restart that same operation. Add paired PROBE and DOWNLOAD retry tests; the former must never create output. | **Open** |
| `T102-R1` | **High** | **Yes — T-102** | Settings fallback | `load()` catches `OSError` and `TOMLDecodeError` around `tomllib.load()` (`settings.py:230-241`), but `tomllib` decodes bytes first and raises `UnicodeDecodeError` for a non-UTF-8 file. The reviewer wrote `concurrency = \xff`; `load()` raised instead of returning defaults plus `SettingsProblem`. This aborts application composition for an existing unusable settings file, contradicting both ARC-008 and the explicit never-raises criterion. | Treat decoding failure as another existing-file parse problem, preserving its codec/offset reason. Add it to both the report-direction table and the never-raises matrix. | **Open** |
| `T087-R1` | **High** | **Yes — T-087 / A-004** | Windows ownership primitive | ARC-006's accepted amendment and T-094 choose an **exclusive-access open** on Windows. The implementation instead opens normally and applies a one-byte `msvcrt.locking(LK_NBLCK)` range (`instance_lock.py:118-124`, `:164-177`). That may be a defensible primitive, but it is a different architectural choice and its branch has never executed. Linux `flock` tests and Win32 mypy cannot establish simultaneous-start exclusivity, killed-holder recovery, or even first acquisition on Windows; those are the task's explicit both-platform criteria and the exact half the withdrawn design got wrong. | Either implement ARC-006's chosen Windows primitive or obtain an authorised amendment for the byte-range-lock design, then run simultaneous starts and killed-holder recovery on STARBASE. Keep A-004 unverified and T-087 out of Complete until that evidence exists. | **Open — blocked on decision/evidence** |
| `T092-R1` | **High** | **Yes — T-092 prepared implementation** | Crash-dump provenance and disclosure | WER is keyed by the filename `python.exe`, so it captures any Python process for that user, not only this project (`crash-dumps.ps1:46-50`). Both persistent-runner workflows then copy **every** dump in the folder, without clearing it or filtering by job start time (`ci.yml:382-388`; `t074-repeat.yml:106-112`), and automatically upload full-memory dumps. A deliberate proof dump, a stale T-074 dump, or an unrelated Python crash will be uploaded on every later run and announced as “T-074 may have recurred.” Besides destroying causal attribution, a full dump can expose unrelated heap contents in a CI artifact; the documentation discusses disk cost but not artifact sensitivity or provenance. | Do not automatically upload an unscoped persistent folder. Establish per-run provenance (or a dedicated executable/account/folder), collect only new dumps attributable to the run, and explicitly decide access/retention for full-memory artifacts. A safe alternative is to upload metadata only and leave the dump for deliberate maintainer retrieval. Exercise both “new dump” and “stale/unrelated dump” paths before arming STARBASE. | **Open** |

### Focused correction disposition

| Prior finding | Result |
|---|---|
| `T080-R1` | **Resolved.** Explicit PROBE starts still run while paused; direct DOWNLOAD starts are parked and remain durably queued until resume. |
| `T080-R2` | **Resolved.** `job_removed` now refreshes `QueueModel` after durability and is disconnected in `detach()`; the composed remove path updates store and table. |
| `T081-R1` | **Open.** Waiting-list admission, refusal and multiple in-flight reorder cases are covered, but public DOWNLOAD admission bypasses the counter as described above. |
| `T081-R2` | **Resolved.** Reorder and clear success signals refresh the model after the write; composed controls update the durable order/set and the visible table. |
| `T081-R3` | **Resolved.** Deselection emits the empty job id, model reset re-announces selection state, and every per-job action disables when nothing is selected. |
| `T080-R3` | **Resolved.** ARCHITECTURE.md §5 no longer draws the removed PAUSED state or its edges. |

### Review judgments

**T-080 can be approved independently of T-081.** The surviving barrier hole violates reordered
DOWNLOAD admission, not pause semantics. The three T-080 findings are independently corrected and
their assembled wiring passes. T-081 remains the inherited dependency risk for later manager work.

**T-103 makes the old clear sweep unnecessary.** A waiting id can become clearable through cancel,
which now discards it synchronously before the terminal write is queued. `remove()` also discards
waiting and retry intent before deletion. Under the manager-owned write boundary, no remaining path
can delete a waiting row behind the model; retaining the old read-back sweep would not add a live
guarantee.

**The changed T-102 return type is acceptable.** `SettingsFile` makes the diagnostic impossible for
the sole production caller to ignore accidentally, and repository-wide search finds every internal
caller adapted. T102-R1 is about an exception outside that return path, not the wrapper type.

**Group C is not blanket-approved through its dependency.** T-099, T-101 and T-103 satisfy their
own bounded criteria, but the manager tree they sit on still carries open T081-R1 and T083-R1.
Approval of those task-specific changes does not approve the inherited manager head as a whole.

### Independent verification

| Check | Result |
|---|---|
| Span accounting | `da49a51..05e5312` contains the twelve handoff commits; base is T-079's approved head |
| `git diff --check da49a51..05e5312` | Passed |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **113 files** |
| `mypy src` | Passed; **36 source files** |
| `mypy --platform win32 src` | Passed; **36 source files** |
| Manager suite excluding the two intentional reviewer negatives | **120 passed, 2 deselected** |
| T-046/T-053/T-087 plus settings, boundary and detail-view files, excluding T102-R1 | **271 passed, 1 deselected** |
| Queue-view and main-window UI files | **79 passed** |
| Eight composed toolbar/settings/lock cases | **8 passed** |
| T081-R1 reviewer regression | **Failed as expected:** direct job-1 occupied the pool before held reorder settled |
| T046-R1 reviewer regression | **Failed as expected with real yt-dlp/ffmpeg:** existing MP3 bytes were replaced |
| T083-R1 reviewer regression | **Failed as expected:** spawned kinds were `probe`, then `download` |
| T102-R1 reviewer regression | **Failed as expected:** uncaught `UnicodeDecodeError` |
| T-099 assertion-level reviewer strengthening | **Passed** |
| Full suite | Not rerun by reviewer; handoff reports **1726 passed / 11 skipped / 2 deselected** before the reviewer negatives were added |
| CI / Windows runtime | Not run; no CI job executed a step and STARBASE evidence required by T-087/T-092 is absent |

### Final disposition

The complete batch is **not approved**. T-080, T-053, T-099, T-101 and T-103 are approved at
`05e5312` for their task-specific changes. T-081, T-046, T-083 and T-102 require corrections for
the open findings above. T-087 remains blocked on an authorised Windows primitive plus STARBASE
runtime evidence. T-092 remains both incomplete on its recorded external criteria and changes
requested on dump provenance/disclosure. The four failing reviewer regressions remain in the
checkout as correction gates; the passing T-099 assertion-level regression remains as a permanent
strengthening candidate.

## 2026-08-01 — overnight batch focused correction re-review

**Reviewer:** Codex (Reviewer)
**Prior review head:** `05e5312`
**Implementation correction head:** `aff4e87`
**Review handoff / boundary-record head:** `97f96c0`
**Correction span:** `05e5312..aff4e87`; one mixed commit carries all six tasks despite its
`T-046`-only subject and trailer. `97f96c0` records that fact and changes no implementation.
**Platforms verified:** Linux; Win32 static analysis and a deterministic ctypes failure probe only
**CI:** no job has executed a step since 2026-07-30 04:08 UTC; no CI evidence is claimed
**Overall verdict:** **Changes requested**

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-046` | **Changes requested** | T046-R1's data-loss path is structurally closed, but T046-R2 reproduces a postprocessor output path that disagrees with the required preview. |
| `T-081` | **Changes requested** | The direct-start barrier hole is closed, but T081-R4 makes a settled reorder admit and start a different job that had no start intent. |
| `T-083` | **Approved at `97f96c0`** | T083-R1 is resolved on immediate, deferred/full-pool, PROBE and DOWNLOAD paths. |
| `T-102` | **Approved at `97f96c0`** | T102-R1 is resolved; both non-UTF-8 shapes return defaults plus a precise problem instead of escaping composition. |
| `T-087` | **Blocked; changes required before Windows verification** | T087-R1's architectural mismatch is gone, but T087-R2 mishandles `CreateFileW` failure before STARBASE has executed the branch. A-004 and Phase 2 exit criterion 4 remain blocked. |
| `T-092` | **Blocked; safe correction accepted, task not complete** | T092-R1 is resolved: no dump is uploaded and the metadata report is time-filtered and honest about attribution. T092-R2 leaves the task's upload criterion inconsistent with that safe design, and the three machine-dependent criteria remain unmet. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T046-R2` | **High** | **Yes — T-046** | Postprocessed path preview | The actual-name claim fixes overwrite safety by discovering the final path after extraction (`worker.py:453-488`), but `preview_path()` still renders the pre-postprocessor target (`:1010-1020`). The reviewer fixture previews `Clip.webm`, has the postprocessor produce `Clip.mp3`, and receives success for `Clip.mp3`. This directly fails T-046's criterion that collision resolution is visible in the REQ-011 preview and the existing `preview_path()` contract that it names the path the download would write. Rejecting a predicted name for the **claim** is sound; silently predicting a different name for the **preview** is still a broken promise. | Keep the actual-file atomic claim, but reconcile preview semantics explicitly. Either derive an accurate displayed final path without trusting it for safety, or obtain an authorised requirement/task amendment and make the UI/API label the path as provisional. Retain the extension-changing regression; the existing same-extension preview test is not sufficient. | **Open** |
| `T081-R4` | **High** | **Yes — T-081** | Reorder admission intent | `_settle_reorder()` calls `_admit_reordered()` whenever anything is waiting, and that helper adds every named `QUEUED` or `READY` row (`manager.py:710-753`). A held-reorder regression parks the only explicit start for `requested`, puts a recovered `QUEUED` row first, settles, and observes `recovered` occupying the pool while `requested` remains waiting. Reordering admitted work is not itself permission to start every persisted row; startup recovery deliberately leaves queued rows dormant. This can begin an unattended download for a different job. The reviewer's earlier direct-start regression caused this rule by incorrectly demanding job-2 after only job-1 was started; that assertion is corrected in the checkout. | Preserve the set and operation kinds of already admitted intents across the barrier, then use the new durable positions only to order that set. Do not promote other reordered rows into `_waiting`. Test two already-waiting jobs for new-order selection separately from one explicitly waiting job plus dormant `QUEUED`/`READY` rows. | **Open** |
| `T087-R2` | **High** | **Yes — T-087 / A-004** | Windows `CreateFileW` wrapper | `CreateFileW` correctly uses share mode zero, but failure returns pointer-sized `INVALID_HANDLE_VALUE`. With `restype = wintypes.HANDLE`, ctypes returns the pointer value as a Python integer; on 64-bit Windows that is `18446744073709551615`, not `-1`. The check at `instance_lock.py:192-209` therefore falls through to `msvcrt.open_osfhandle()` instead of raising the `OSError` that `acquire()` converts to `AlreadyRunningError`. A deterministic branch probe supplied that exact pointer and observed it passed through, ending in `OverflowError`. The wrapper also reads `ctypes.get_last_error()` from `ctypes.windll`, which was not loaded with `use_last_error=True`, so its claimed Windows error code is not reliably captured. | Compare against `wintypes.HANDLE(-1).value` (or use `errcheck`), define the API prototype completely, and retrieve the actual last error via a `use_last_error=True` binding or direct `GetLastError`. Audit raw-handle cleanup if descriptor conversion fails and pass the non-inheritable flag. Then execute first acquisition, simultaneous refusal and killed-holder recovery on STARBASE. | **Open — code correction plus external evidence** |
| `T092-R2` | **Medium** | **Yes — T-092 completion** | Current task contract | The correction safely uploads metadata only, but current `TASKS.md:1042-1062` still scopes and requires uploading the dump, and `:1079-1094` still describes that copy as the prepared implementation. The appended correction says the opposite. T-092 can no longer meet its own current acceptance table without reintroducing T092-R1's disclosure defect. | Obtain the maintainer/Planner's explicit metadata-only scope decision and rewrite T-092's current scope, criterion and state table to match it. Keep the old unsafe proposal only as clearly superseded history. | **Open — decision required** |
| `T046-R3` | **Low** | **No** | Cancellation documentation | The Phase 2 behavior change itself is acceptable: cooperative cancellation is proved by the worker's own message and staging leaves neither a complete nor partial file. However, current manager and UI comments still say partial files survive in a known state, and `remove()` says a cancelled partial is the user's to delete (`manager.py:646-649`, `:1227-1229`, `:1958-1961`; `job_detail.py:703-708`). Those claims are now false. | Correct current source documentation with the behavior change; let T-113 decide future resumable-partial lifetime rather than preserving the old Phase 2 claim. | **Open — non-blocking** |

### Focused correction disposition

| Prior finding | Result |
|---|---|
| `T046-R1` | **Resolved.** Each job downloads in a private same-filesystem staging directory; the actual produced basename is claimed with `O_CREAT | O_EXCL` before `os.replace`. The real yt-dlp/ffmpeg existing-MP3 regression passes and the original bytes survive. The three successful fakes now write what they report. |
| `T081-R1` | **Resolved as originally stated.** Public DOWNLOAD starts now park behind the reorder counter, PROBE remains exempt, and settlement releases refusal and multiple-in-flight paths. T081-R4 is the new admission regression in the settlement policy, not a surviving barrier bypass. |
| `T083-R1` | **Resolved.** The failed session kind reaches backoff, immediate restart and `_fill_free_slots`; paired PROBE/DOWNLOAD tests pass and the deferred probe remains a probe. |
| `T102-R1` | **Resolved.** `UnicodeDecodeError` becomes a `SettingsProblem`; the never-raises matrix covers Latin-1 and a truncated multi-byte sequence, and the exact byte offset is asserted. |
| `T087-R1` | **Resolved.** The source now implements ARC-006's selected exclusive-access-open primitive. T087-R2 concerns the correctness of that wrapper and the task remains blocked on Windows evidence. |
| `T092-R1` | **Resolved.** Both workflows upload only `reports/crashdumps.txt`; stale dumps are excluded by job start time and the report disclaims executable-name attribution. No `.dmp` enters `reports/`. |

### Review judgments

**Cancellation leaving nothing is acceptable for Phase 2.** REQ-015 requires prompt cooperative
termination and no partial presented as complete; REQ-017/T-113 owns resumability and partial-file
lifetime. The worker message is stronger evidence of cooperative unwind than the old `.part`
assertion once staging is intentionally discarded. The false current comments are T046-R3, not a
reason to retain an unusable partial.

**The staging design needs a T-109 sidecar audit.** `_discard_staging()` removes everything except
the single path returned by `_written_path()`. That is correct for temporary conversion inputs and
embedded thumbnails/subtitles, but a future `embed_subtitles=False` request intentionally produces
subtitle sidecars. T-109 must claim every user-requested output before cleanup; this is a future
surface rather than a Phase 2 blocker because no current UI exposes write-only subtitles.

**Removing T-081's clear sweep remains safe.** T-103 discards waiting intent synchronously in
`cancel()` and `remove()`, before either path can delete the row. The correction introduces no new
row-deletion path; T081-R4 is an admission-set expansion, not a stale-id cleanup problem.

**T-092's metadata-only response is the safe response to T092-R1.** A timestamp narrows the window
but cannot attribute a `python.exe` dump to this project, and the report says that. Leaving a full
heap on STARBASE until deliberate retrieval avoids the disclosure boundary. The remaining problem
is that current task truth still requires the unsafe upload, so completion needs an authorised
scope amendment as well as STARBASE execution.

### Independent verification

| Check | Result |
|---|---|
| Boundary and tree | `05e5312..aff4e87` is the mixed implementation correction; `97f96c0` records the boundary; tree was clean before reviewer tests |
| `git diff --check 05e5312..aff4e87` and current `git diff --check` | Passed |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **114 files** |
| `mypy src` | Passed; **36 source files** |
| `mypy --platform win32 src` | Passed; **36 source files** |
| Workflow syntax | Both changed YAML files parsed with PyYAML |
| Focused six-file correction suite, excluding intentional reviewer negatives | **290 passed, 3 deselected** |
| Real T046-R1 yt-dlp/ffmpeg regression | **Passed**; protected MP3 bytes survived |
| T046-R2 reviewer regression | **Failed as expected:** preview `Clip.webm`, success `Clip.mp3` |
| T081-R4 reviewer regressions | **Failed as expected:** `job-2` / `recovered` occupied the slot instead of the sole explicitly started job |
| Windows invalid-handle probe | **Failed as expected:** pointer value `18446744073709551615` reached `open_osfhandle`, producing `OverflowError` in the probe |
| Implementer full suite | Reported **1738 passed / 11 skipped / 2 deselected** before reviewer negatives; not rerun by reviewer |
| CI / Windows runtime | Not run; no CI step executed, and STARBASE evidence remains absent |

### Final disposition

The correction batch is **not approved as a whole**. T046-R1, T081-R1, T083-R1, T102-R1,
T087-R1 and T092-R1 are independently resolved. T-083 and T-102 are approved at `97f96c0`.
T-046 and T-081 require another focused High-severity correction for T046-R2 and T081-R4.
T-087 needs T087-R2 corrected before its already-required STARBASE run. T-092's unsafe upload is
gone, but the task remains blocked on an authorised metadata-only criterion plus its recorded
machine evidence. The three reviewer regressions remain in the checkout as failing gates; no
production source or coordination status was edited by the reviewer.

## 2026-08-01 — second correction batch, third focused review

**Reviewer:** Codex (Reviewer)
**Implementation boundary:** `97f96c0..9a8eaeb` — four correction commits, one per task
**Implementation head reviewed:** `9a8eaeb`
**Later heads observed during review:** `7f877d2` and `049b595`; coordination changes only with
respect to the reviewed production source
**Platforms verified:** Linux; Win32 source inspection and static analysis only
**CI:** no job has executed a step since 2026-07-30; no CI evidence is claimed
**Overall verdict:** **Changes requested**

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-046` | **Changes requested** | MP3 preview is corrected, but the built-in original-audio preset still promises a path the real postprocessor changes, and `mergeall` is a merge the provisional test misses. |
| `T-081` | **Approved at `eb1bd70`** | T081-R4 is resolved. Reorder settlement preserves the admitted set and operation kinds, then uses the new durable positions only to order that set. Dormant recovered rows stay dormant. |
| `T-087` | **Blocked; code correction still required before Windows verification** | The invalid-handle and last-error fixes are sound, but the unexecuted wrapper still has two handle-ownership holes in the conversion/cleanup path. `A-004` and Phase 2 exit criterion 4 remain blocked. |
| `T-092` | **Blocked; T092-R2 remains partly open** | The metadata-only criterion and implementation agree, but the live task Scope still instructs both jobs to upload a dump artifact. The STARBASE criteria also remain externally unmet. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T046-R4` | **High** | **Yes — T-046** | Original-audio preview | `postprocessed_name()` treats `AudioCodec.ORIGINAL` as “keep the source container” (`worker.py:1023-1035`). yt-dlp's `best` extraction keeps the **codec**, not necessarily the container. The reviewer drove the built-in **Audio only (original)** preset through the real HLS/yt-dlp/ffmpeg path: the preview promised `master.mp4`, while `FFmpegExtractAudio` copied AAC into `master.m4a`. This is one of the exact Phase 2 cases the amended `REQ-011` explicitly calls non-provisional, so the correction's premise and its fake `.webm` assertion are false. The same shortcut also assumes every supported `preferredcodec` value is its extension, although yt-dlp maps AAC and ALAC to M4A and Vorbis to OGG. | Do not infer a final container from “keep source codec” or from the raw codec enum. Either derive the postprocessor's actual output semantics from enough resolved information and cover every supported codec, or label cases that cannot be known before the write as intended and amend the exactness claim accordingly. Keep the real built-in regression. | **Open** |
| `T046-R5` | **Medium** | **Yes — T-046** | Provisional merge detection | `preview_is_provisional()` equates merging with a raw `+` in the selector (`worker.py:1055-1060`). Pinned yt-dlp also recognizes the special selector `mergeall`, which folds all selected formats into a merged format without containing `+`. The reviewer regression receives `False`, so the UI presents yt-dlp's container choice as an exact path in precisely the direction the amendment was meant to prevent. | Classify all yt-dlp merge forms rather than scanning for one token. Keep `mergeall` as the no-`+` regression; if complete pre-resolution classification is not maintainable, make the label conservative. | **Open** |
| `T087-R3` | **High** | **Yes — T-087 / A-004** | Win32 handle ownership | T087-R2 fixed `CreateFileW`'s prototype, sentinel and saved error, but its ownership cleanup remains only superficially gated. `kernel32.CloseHandle(handle)` is called without declaring `CloseHandle(HANDLE)`: ctypes passes an undeclared Python integer as the platform C `int`, which is narrower than `HANDLE` on 64-bit Windows, so the conversion-failure cleanup can truncate the handle it is meant to release (`instance_lock.py:237-244`). The successful conversion also calls `open_osfhandle(handle, os.O_RDWR)` without `os.O_NOINHERIT`; Python explicitly documents the returned descriptor as inheritable by default. Both omissions were named in T087-R2's recommendation, and both new static regressions fail. | Bind `CloseHandle` with `argtypes = (wintypes.HANDLE,)` and `restype = wintypes.BOOL`; pass `os.O_NOINHERIT` when transferring ownership to the CRT descriptor. Then execute the already-required first-acquire, simultaneous-refusal and killed-holder cases on STARBASE. See the official [ctypes argument conversion](https://docs.python.org/3/library/ctypes.html) and [open_osfhandle inheritance](https://docs.python.org/3/library/msvcrt.html#msvcrt.open_osfhandle) contracts. | **Open — code plus external evidence** |
| `T092-R2` | **Medium** | **Yes — T-092 prepared contract** | Current task truth | The authorised metadata-only criterion and state table are corrected, but the live `#### Scope` still directs `t074-repeat.yml` and `windows desktop` to “upload any dump they find as an artifact” (`TASKS.md:1691-1694`), and the affected-surface label still says “artifact upload only” (`:1679-1680`). Those are current instructions, not text inside the clearly marked superseded parenthetical. The entry therefore still tells the next reader both to upload and never upload. | Rewrite the remaining live Scope and affected-surface text to metadata-only reporting. Preserve the former upload design only inside an explicitly superseded historical note. | **Open — partial closure** |

### Focused correction disposition

| Prior finding | Result |
|---|---|
| `T046-R2` | **Open in a narrower form.** MP3 extension preview now matches the real write, but T046-R4 disproves the correction's broader claim that every Phase 2 audio extraction is exact. |
| `T046-R3` | **Resolved.** Current manager comments no longer claim cancellation leaves a partial; the cooperative worker message remains the asserted evidence. |
| `T081-R4` | **Resolved.** `_admit_reordered` is removed. A settled reorder orders only existing `_waiting` intents, and the corrected direct-start assertion no longer invents admission of job-2. |
| `T087-R2` | **Partly resolved.** Pointer-width failure detection, a `use_last_error=True` binding and the full `CreateFileW` prototype are correct. T087-R3 covers the two ownership details left from the same recommendation. |
| `T092-R2` | **Partly resolved.** The maintainer's metadata-only decision is taken in the criterion and prepared-state table, but current Scope still requires upload as described above. |

### Review judgments

**Removing `_admit_reordered` does not reopen the original barrier.** Public DOWNLOAD admission,
the waiting-list fill path, resume, concurrency changes and retry deferral all meet at the same
reorder counter. Settlement calls `_fill_free_slots()`, which observes any remaining in-flight
reorder and otherwise selects only from existing waiting intents by the now-durable positions.
The seven focused reorder tests pass, including refusal, two outstanding writes, direct admission,
two already-waiting jobs and a recovered dormant row.

**The T-046 staging/claim design remains approved.** These findings affect what is promised before
the write, not the structural data-loss fix: the actual produced file is still claimed with
`O_CREAT | O_EXCL` and moved on the same filesystem. The real original-audio failure completes
successfully and records the correct `master.m4a`; it is the preview's `master.mp4` promise that is
wrong.

**T-092's runtime design is still the safe one.** Both YAML files parse, only metadata enters
`reports/`, stale files are time-filtered, and the report disclaims attribution to this project.
The finding is the remaining contradictory current instruction, not a request to restore upload.

### Boundary and process observation

`049b595` was committed and pushed while this review was active. Its subject and `Task:` trailer
name only Phase 2 / T-080 / T-087 coordination, but it also stages all four reviewer regressions
for T-046 and T-087 from the shared working tree. That is the same stage-the-whole-tree habit the
handoff said had been corrected, for a third boundary muddle. It does not change the frozen
implementation verdict above, and published history must not be rewritten, but the real contents
of `049b595` need to be carried forward: current `main` deliberately has four failing reviewer
tests until these findings close.

### Independent verification

| Check | Result |
|---|---|
| Correction boundary | `97f96c0..9a8eaeb`; four task commits, production source unchanged by later observed heads |
| `git diff --check 97f96c0..9a8eaeb` and `9a8eaeb..049b595` | Passed |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; **115 files** |
| `mypy src` | Passed; **36 source files** |
| `mypy --platform win32 src` | Passed; **36 source files** |
| Bare `mypy` / `mypy --platform win32` | **Failed: 14 / 16 errors** in the existing test tree. None points at the new assertions, but `ai/TESTING.md` requires these wider gates when tests change, so the stronger gate is not clean. |
| Focused passing reviewer slice | **25 passed, 191 deselected**: 13 instance-lock, 5 preview and 7 reorder tests |
| T046-R4 real yt-dlp/ffmpeg regression | **Failed as expected:** preview `master.mp4`, stored output `master.m4a` |
| T046-R5 merge regression | **Failed as expected:** `preview_is_provisional("mergeall")` returned false |
| T087-R3 source gates | **2 failed as expected:** no typed `CloseHandle`, no `O_NOINHERIT` |
| Workflow syntax | Both changed workflow YAML files parsed; no `.dmp` path is copied into `reports/` |
| Implementer full suite | Reported **1747 passed / 11 skipped / 2 deselected** before reviewer regressions; not reproducible at current head because those four failures are now committed |
| CI / Windows runtime | Not run; STARBASE evidence remains absent |

### Final disposition

T-081 is approved at `eb1bd70`; its third correction removes the invented scheduling rule without
reopening the admission race. T-046 remains Changes requested on T046-R4 and T046-R5. T-087 remains
Blocked with T087-R3 requiring a code correction before its external Windows evidence can be
meaningful. T-092 remains Blocked, and T092-R2 is not fully closed until all live task text says
metadata-only. Reviewer production edits were not made. The four failing regressions are committed
at `049b595`; this review record is left uncommitted for the maintainer.

## 2026-08-01 — fourth focused correction re-review: T-046 and T-087

**Reviewer:** Codex (Reviewer)
**Correction boundary:** `049b595..ea9d752`
**Implementation commits reviewed:** `9c5745a` (`T-046`) and `bddf1bb` (`T-087`)
**Evidence head:** `ea9d752`
**Handoff head:** `d818c77`; coordination only after the evidence head
**Platforms verified:** Linux locally; Linux and Windows on GitHub-hosted runners
**Overall verdict:** **Implementation approved; coordination-only changes requested before either
task is filed Complete. No fifth implementation pass is required.**

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-046` | **Implementation approved at `9c5745a`; current task text must be corrected before filing** | T046-R4 and T046-R5 are closed. Named audio codecs follow yt-dlp's container table; ORIGINAL is honestly provisional; current pinned yt-dlp has exactly the two classified merge spellings. T046-R6 leaves the live acceptance criterion contradicting the authorised REQ-011 amendment. |
| `T-087` | **Implementation and Windows gate approved at `ea9d752`; current task text must be corrected before filing** | T087-R3 is closed and all three required Windows process cases passed on the exact evidence head. Under the 2026-08-01 OPS-005 amendment, `A-004` is verified and Phase 2 exit criterion 4 is met. T087-R4 leaves the canonical task record saying the opposite in several places. |

### Findings

| ID | Severity | Blocks filing | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T046-R6` | **Medium** | **Yes — task filing, not implementation** | Current task contract | `REQ-011` now explicitly permits an *intended* path where yt-dlp chooses the final container and marks ORIGINAL audio provisional. `TASKS.md:289-294` still requires every resolution to be visible before the write and calls any preview/write disagreement a failure. The approved ORIGINAL behavior can preview `.mp4` and correctly write `.m4a`, so the canonical requirement and canonical task criteria prescribe opposite verdicts. | Narrow T-046's live criterion to atomic collision resolution and the exact-preview cases REQ-011 still promises. State the authorised intended-path exception in the criterion, not only in the later correction narrative. | **Open — coordination only** |
| `T087-R4` | **Medium** | **Yes — task filing, not implementation** | Current task and status truth | The current T-087 entry correctly says hosted Windows executed at `TASKS.md:98-106`, but its criterion still demands STARBASE (`:168`), its built description still names withdrawn `msvcrt.locking` (`:185-187`), and its not-covered/correction sections still say Windows never ran and `A-004` is unverified (`:223-250`). The live-queue summary likewise says both that T-087 is no longer blocked (`:23-26`) and that it is blocked with an unexecuted branch (`:31-32`). `STATUS.md:23-26` and `:49-53` repeat stale counts and unverified-Windows claims before `:64-101` says the reverse. | Rebuild current TASKS/STATUS truth from the accepted OPS-005 amendment and exact CI run, preserving obsolete claims only as explicitly superseded history. Move T-087 to Complete once that record is internally consistent. | **Open — coordination only** |
| `T046-R7` | **Low** | No | Merge update gate | `presets.py:200-201` says `test_presets` asserts `MERGE_TOKENS` against yt-dlp's documented selectors, but no such test exists. The two behavior regressions cover `+` and `mergeall`; they do not detect a future upstream spelling. Current behavior is correct for pinned yt-dlp, so this is an evidence overclaim rather than a present defect. | Remove the nonexistent-gate claim or add a real, maintainable upstream-syntax gate. Keep the user-managed yt-dlp update risk explicit. | **Open — non-blocking** |
| `T087-R5` | **Low** | No | Handle-inheritance rationale | `O_NOINHERIT` is the correct defensive flag, but `instance_lock.py:246-250` says current ARC-002 workers would otherwise inherit the lock. CPython's Windows multiprocessing spawn path invokes `CreateProcess` with `bInheritHandles=False`, so those workers do not inherit arbitrary handles. A normal spawned-worker test therefore cannot prove this flag. | Describe the flag as defense against a child explicitly launched with handle inheritance. If dynamic mutation evidence is wanted, use such a child (for example an inheriting subprocess), not the existing multiprocessing worker path. | **Open — non-blocking** |

### Focused correction disposition

| Prior finding | Result |
|---|---|
| `T046-R4` | **Resolved.** Named codecs use yt-dlp's `ACODECS` output extension, including AAC/ALAC to M4A and Vorbis to OGG. ORIGINAL bypasses that table even if a future table contains `best`, remains provisional, and the real HLS/ffmpeg regression asserts the honest contract. The simulated table entry is useful: it pins the product distinction rather than today's table contents. |
| `T046-R5` | **Resolved for the pinned parser.** Inspection of yt-dlp's selector parser finds the `+` merge operator and special `mergeall` form; both regressions pass. Unrecognised future forms remain the update risk described by T046-R7. |
| `T087-R3` | **Resolved.** `CloseHandle` has pointer-width-correct `HANDLE -> BOOL` types, conversion failure transfers no ownership and closes the raw handle, and successful CRT conversion uses `O_NOINHERIT`. |

### Review judgments

**T-046's staging and actual-name claim remain the safety boundary.** Preview classification does
not participate in collision ownership: every successful output is discovered, atomically claimed
with `O_CREAT | O_EXCL`, then renamed on the destination filesystem. The authorised provisional
label makes the unavoidable pre-write uncertainty honest without weakening overwrite protection.

**The ORIGINAL guard test earns its place.** Its synthetic `ACODECS["best"]` entry prevents a future
table update from silently converting an explicitly provisional product case into an exact one.
That is a contract mutation which current real table data cannot exercise.

**Hosted Windows satisfies T-087 under the amended OPS-005 gate.** The exact evidence head ran
first acquisition/refusal, simultaneous launches and killed-holder recovery on `windows-latest`.
The desktop job was skipped, not left queued. STARBASE still owns the desktop-specific and
subjective residue, but neither is a T-087 or Phase 2 completion gate under the amendment.

**The OPS-005 amendment is narrow enough.** It substitutes reachable hosted Windows for STARBASE
only while the latter is unreachable for cases hosted Windows can execute, preserves STARBASE-only
work, and makes the self-hosted workflow opt-in via `STARBASE_AVAILABLE`. It does not turn a skipped
desktop job into evidence.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `049b595..ea9d752` inspected; `git diff --check` passed; production source last changed by `9c5745a` / `bddf1bb` |
| Exact GitHub Actions evidence | Run `30707898266`, exact SHA `ea9d752f36ac4112c0b7f236715bedade6577451`, conclusion **success** |
| Hosted jobs | Ubuntu, Windows and both frozen jobs **passed**; Windows desktop **skipped with zero steps** |
| Full Ubuntu suite | **1753 passed / 11 skipped / 2 deselected** |
| Full Windows suite | **1741 passed / 21 skipped / 32 deselected** |
| Required T-087 Windows cases | **3 passed:** acquisition/refusal, two launches racing, killed-holder recovery |
| `ruff check .` / `ruff format --check .` | Passed; format checked **116 files** |
| `mypy src` / bare `mypy` | Passed; **36 / 84 files** |
| `mypy --platform win32 src` / bare `mypy --platform win32` | Passed; **36 / 84 files** |
| Focused T-046 preview slice | **7 passed / 70 deselected** |
| Full Linux instance-lock file | **15 passed** |
| Real ORIGINAL HLS/yt-dlp/ffmpeg case | **1 passed** |

### Final disposition

T046-R4, T046-R5 and T087-R3 are closed. T-046's implementation is approved at `9c5745a` and
T-087's implementation plus amended Windows gate is approved at `ea9d752`; `A-004` is verified and
Phase 2 exit criterion 4 is met. Do not send either implementation through a fifth correction pass.

Neither task should be filed Complete while its canonical current text contradicts the approved
contract or evidence. T046-R6 and T087-R4 require a coordination-only correction and mechanical
recheck; T046-R7 and T087-R5 are non-blocking documentation/evidence follow-ups. Reviewer production
source was not edited. A separate T-100 working tree appeared after the frozen-head verification and
was preserved untouched and excluded from every result above; only this review record was added.

## 2026-08-01 — Phase 2 feature batch: T-100, T-086, T-084, T-082 and T-088

**Reviewer:** Codex (Reviewer)
**Review boundary:** `eb6f690..57518ce`
**Implementation commits:** `c242dd3` (`T-100`), `46c1709` (`T-086`), `d86240c`
(`T-084`), `b1b7cd6` (`T-082`) and `de7d13b` (`T-088`)
**Handoff head:** `7ffca9b`
**Coordination/test correction during review:** `ff16034`; no reviewed production source changed
**Overall verdict:** **Changes requested.** T-100 and T-082 are approved. T-084, T-086 and T-088
are not approved, and Phase 2 cannot exit while T-115 remains open.

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-100` | **Approved at `c242dd3`** | The history projection is read-only, newest-first, covers every REQ-020 field including null output paths, refreshes only after the committed success signal, and remains separate from clear-completed persistence. |
| `T-082` | **Approved at `b1b7cd6`** | Interrupted rows recover in one transaction; the composed application offers exactly those ids before ordinary interaction; Not now is safe/default; Retry all reuses the per-job retry path and its existing waiting-list admission. |
| `T-086` | **Changes requested at `46c1709`** | T086-R1 leaves Windows Open-file behavior unimplemented by the documented associated-application route. The Windows-hosted argv test proves only list construction, not that Explorer opens the file. |
| `T-084` | **Changes requested at `d86240c`** | T084-R1 permits credentials in yt-dlp-originated job logs despite the accepted DAT-003 emission rule; T084-R2 copies only the capped rendering rather than the file. |
| `T-088` | **Changes requested at `de7d13b`** | T088-R1 is an unconditional xfail that cannot detect T-115 being fixed. T088-R2 and T088-R3 overstate what the phase-level progress and restart tests observe. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T084-R1` | **Critical** | **Yes** | Credential redaction / accepted decision | `core/logging.py:181-209` returns third-party records after replacing only values registered through `remember_a_secret()`. No production caller registers any value. An ordinary yt-dlp bridge line that echoes a source URL therefore writes its userinfo password and signed query to the per-job log verbatim; the reviewer regression proves both survive. This contradicts accepted DAT-003 at `DECISIONS.md:1015-1020`, which explicitly keeps T-038 log emission origin-agnostically redacted even when database storage is verbatim. DAT-004 remains **Proposed** and cannot silently supersede that accepted rule. The new Copy-diagnostics surface makes the exposure easy to carry into a bug report, which is also DAT-003's named reopening condition. | Keep database storage and log emission as the two distinct sinks DAT-003 defines. Apply the established emission redaction to yt-dlp records too, and have the maintainer resolve the now-live copy/export reopening condition before loosening it. Do not rely on exact registration unless every production path registers every secret before yt-dlp can emit it. | **Open** |
| `T084-R2` | **High** | **Yes** | Log copy contract | `read_job_log()` deliberately renders at most the newest 512 KiB (`ui/log_view.py:66-91`), but `copy_to_clipboard()` copies `self.text()` (`:189-202`). For a larger log, the clipboard loses the beginning—session versions and initial extractor decisions—and can contain only the truncation notice for a long line. That violates REQ-019's current explicit promise at `REQUIREMENTS.md:99-104`: “What is copied is the file exactly.” The reviewer regression fails on this route. | Keep the bounded GUI rendering, but read the bounded log artifact independently when Copy is invoked. Report a read refusal rather than copying the placeholder or a truncated view. | **Open** |
| `T086-R1` | **High** | **Yes** | Windows Open file | `open_command(path, "win32")` returns `explorer <path>` and asserts in a comment that this opens the file with its associated application (`ui/reveal.py:127-136`). The implementation never executes that route in a desktop session, and an injected-spawner argv assertion cannot establish the semantic claim. Windows' documented associated-application operations are `ShellExecuteW`'s `open` verb or Python's `os.startfile`; Explorer is the file-manager process and is separately appropriate for the `/select,` reveal route. Consequently REQ-021's Windows Open half is not established and is very likely to open/navigate Explorer rather than launch the associated media application. | Give Open a platform launcher seam distinct from Reveal: use `os.startfile`/`ShellExecuteW` on Windows and retain `xdg-open` on Linux; keep `explorer /select,` only for Reveal. Test the API seam on hosted Windows and retain the real-desktop residue honestly. Official contracts: <https://docs.python.org/3/library/os.html#os.startfile> and <https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew>. | **Open** |
| `T088-R1` | **High** | **Yes** | T-115 executable evidence | `test_a_job_beyond_the_limit_never_starts_even_once_the_pool_empties` has no setup or behavioral assertion; it immediately calls `pytest.xfail()` (`test_phase_2_exit.py:575-610`). It is not decorated `@pytest.mark.xfail(strict=True)` despite TASKS and the implementation plan saying it is strict. It will remain XFAIL after the queue is fixed, so the promised “fixing it fails the build until inverted” gate cannot fire. | Build the measured five-job reproduction, assert the desired queue-draining outcome, and mark that real test `xfail(strict=True)` until T-115 closes. The expected behavior need not choose which layer owns durable admission. | **Open** |
| `T088-R2` | **Medium** | **Yes** | Exit criterion 1 evidence | `test_three_downloads_progress_independently_while_the_ui_keeps_answering` claims distinct progress and UI event-loop service (`test_phase_2_exit.py:507-522`), but it samples only durable status dictionaries, terminal file sizes and final states (`:535-569`). It never observes a progress byte, progress signal, table cell, UI event, or response latency. A mutation that drops every live progress update still passes this test. Existing T-079 composition coverage does observe three rendered rows; the Phase-2 evidence should cite it rather than assigning claims this test cannot prove. | Either observe three distinct live progress values through the composed UI and an explicit event-loop heartbeat here, or narrow/rename this test and make the evidence row cite the existing composed progress test for the missing claim. | **Open** |
| `T088-R3` | **Medium** | **Yes** | Exit criterion 2 evidence | After hard-killing the child, `test_a_hard_kill_mid_queue_restores_every_job_state_at_the_next_start` directly constructs `JobRepository` and calls `recover_interrupted()` (`test_phase_2_exit.py:253-327`). There is no next application start, despite the test name, comment and evidence table saying there is. T-082 separately proves startup recovery for seeded rows, but this phase test does not join that seam to the rows produced by the hard kill. | Start the composed application against the killed database and observe its recovered/untouched rows (and offer), or state explicitly that the criterion is covered by the hard-kill persistence test together with T-082's startup composition test rather than claiming this one crosses both boundaries. | **Open** |

### T-115 judgment

T-115 is confirmed as a **High Phase-2 blocker**. The manager drains only its in-memory waiting
list, public `start()` refuses at saturation, durable QUEUED rows are not admitted after restart, and
the Add dialog starts at most the explicitly probed job. Of the three placements in the handoff,
durable admission must ultimately be manager-owned or supplied to it by composition: a dialog-only
loop cannot cover restart, and a periodic full-table sweep is unnecessary. A public enqueue/admit
operation plus one startup admission of durable QUEUED intent is the smallest direction that covers
both newly-added and recovered queues without resurrecting T081-R4's “reorder means start” rule.
This is a design recommendation, not an implementation approval.

### CI and independent verification

| Check | Result |
|---|---|
| Boundary | `eb6f690..57518ce` inspected; `git diff --check` passed. |
| Exact evidence-head CI | Run `30713168373` at `57518ce` was **cancelled** by the later push. Ubuntu and both frozen jobs had passed; Windows tests were killed mid-step, so that run supplies no full Windows verdict. |
| Handoff-head CI | Run `30713509567` at `7ffca9b` completed **failure**: Ubuntu and both frozen jobs passed; Windows had **1 failed / 1852 passed / 21 skipped / 32 deselected / 1 xfailed**. The sole failure was T-086's Linux-only `xdg-open` expectation. All five substantive Phase-2 exit tests passed on Windows and the unconditional T-115 case reported XFAIL. |
| During-review correction | `ff16034` corrected the platform-name assertion without changing production source. It also committed the two intentionally failing reviewer regressions before their implementation fixes; those remain failures, not approval evidence. |
| Replacement CI | Run `30713931554` at `ff16034` was still **in progress** when this review closed: both frozen jobs, lint, formatting, both mypy gates and both Qt baselines had passed; the Ubuntu and Windows full-test steps had no conclusion after 15 minutes. It is not cited as a pass or failure. |
| Local full gates before reviewer regressions | `ruff check .`, `ruff format --check .`, `mypy src`, bare `mypy`, `mypy --platform win32 src`, and bare `mypy --platform win32` passed. |
| Local T-088 | **5 passed / 1 xfailed** when rerun with localhost access. The xfail result is vacuous for T088-R1. |
| Reviewer regressions | **2 failed as expected:** credentialed requested URL survives the yt-dlp log route; copying a log beyond `MAX_DISPLAY_BYTES` does not equal the file. |

### Final disposition

T-100 and T-082 are approved without follow-up. T-084, T-086 and T-088 require correction and
re-review on the findings above. T-115 remains an independent High product defect and means Phase 2
exit criterion 7 is not met. The hosted Windows run corrected a real test portability lapse, but it
does not turn argv construction into desktop Open-file evidence. No reviewed production source was
edited by the Reviewer.

## 2026-08-01 — Phase 2 correction re-review: T-084, T-086 and T-088

**Reviewer:** Codex (Reviewer)
**Correction boundary:** `ff16034..2a41c5f`
**Exact candidate head:** `2a41c5fdc58763506e830401793ce231a023f7cd`
**Overall verdict:** **Changes requested for T-088.** T-084 and T-086 are approved at the exact
candidate head. T-115 remains a separate High Phase-2 blocker. T-087's approved implementation is
not reopened, but its killed-holder evidence test needs correction.

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-084` | **Approved at `2a41c5f`** | Log redaction again follows accepted DAT-003 origin-agnostically; the database/log distinction is asserted on one diagnostic; Copy reads the bounded artifact rather than the capped rendering and refuses on read failure; the contradictory criterion and all live pre-ruling prose are reconciled. |
| `T-086` | **Approved at `2a41c5f`** | Windows Open uses the associated-application API through a separately testable starter; Reveal alone uses Explorer; every test caller is pinned or injected safely; the non-vacuous default-starter and FileActions routes passed on hosted Windows. Real desktop association remains explicitly outside this gate. |
| `T-088` | **Changes requested at `2a41c5f`** | T088-R1/R2/R3 are substantively corrected, including the Add-only strict xfail and real composed restart, but T088-R4 leaves the phase's three-worker evidence unreliable on Windows and makes the exact-head Windows job fail. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T088-R4` | **Medium** | **Yes — T-088** | Windows phase-test lifecycle | `test_three_real_workers_each_write_their_whole_file` receives the application's reported PID and discards it, then kills only the `Popen` process before reopening the database. Under a Windows virtualenv that process can be the launcher rather than the composed application—the exact distinction the shared process-tree helpers document. The real application may still own SQLite; hosted Windows failed at the post-kill `PRAGMA journal_mode = WAL` with `sqlite3.OperationalError: disk I/O error`. | Keep the terminal snapshot before teardown, retain the reported application PID, capture the real tree, and reap it through `capture_the_doomed_tree` / `kill_the_application`. Do not reopen the database in the window between killing a launcher and proving the application is gone. | **Open** |
| `T087-R6` | **Medium** | No — implementation approval unchanged; **yes — reliable CI evidence** | Windows killed-holder gate | `test_a_killed_holder_leaves_a_lock_the_next_launch_can_take` has the same launcher/holder confusion. It kills and waits for the `Popen` process, not the process that acquired the lock. The failure previously classified as flaky has now recurred: the child still held the lock and reacquisition correctly received WinError 32. This is a test-evidence defect, not evidence that `InstanceLock` failed to release a handle owned by a dead process. | Have the holder report its own PID with `HELD`; kill and wait for that exact process, then assert reacquisition. Preserve the stale lock-file assertion. | **Open** |

### Resolved prior findings

| Prior finding | Result |
|---|---|
| `T084-R1` | **Resolved.** The provenance flag and caller parameter are gone; yt-dlp lines take the same emission redaction as application lines. The amended criterion separately proves verbatim database storage and redacted log emission on one value. |
| `T084-R2` | **Resolved.** Copy re-reads the live bounded log artifact and refuses rather than silently falling back to the rendered tail. |
| `T086-R1` | **Resolved.** Windows Open calls the associated-application seam and builds no argv; Explorer remains only on Reveal. The default seam is observed by monkeypatching and invoking `os.startfile`, not by source-string inspection. |
| `T088-R1` | **Resolved.** The strict xfail now drives Add only, with no priming `manager.start()` calls, and asserts the wanted eventual-drain outcome. |
| `T088-R2` | **Resolved as a claim correction.** The real-worker test is narrowed to spawned workers and complete independent outputs; progress and UI responsiveness cite the tests that actually observe them. T088-R4 concerns its Windows lifecycle, not that narrower claim. |
| `T088-R3` | **Resolved.** Recovery is observed through a real composed restart against the killed database, including the offer over rows produced by the real kill. All embedded launchers compile, and settings are parent-written, parsed and non-default where the limit is under test. |

### CI and independent verification

| Check | Result |
|---|---|
| Boundary and tree | `ff16034..2a41c5f` inspected; `HEAD == origin/main == 2a41c5fdc58763506e830401793ce231a023f7cd`; worktree clean; `git diff --check` passed. |
| Local full suite (implementer) | **1875 passed / 11 skipped / 1 xfailed** on the exact tree. The xfail is T-115. |
| Local static/mutation evidence (implementer) | Ruff, format and all four mypy gates passed; **14 mutations killed** with source restored byte-identically. |
| Reviewer focused checks | T-084/T-086 focused slice previously **72 passed**; embedded-launcher compile gate passed at the exact head; `ruff check .` and `ruff format --check .` passed (**129 files**). |
| Exact GitHub Actions run | Run `30717153962`, exact SHA `2a41c5fdc58763506e830401793ce231a023f7cd`, conclusion **failure**. |
| Ubuntu / frozen jobs | Ubuntu **1875 passed / 11 skipped / 2 deselected / 1 xfailed**; frozen Ubuntu and frozen Windows passed; Windows desktop skipped with zero steps. |
| Hosted Windows | **2 failed / 1861 passed / 21 skipped / 32 deselected / 1 xfailed**. The failures are T088-R4's SQLite reopen race and T087-R6's launcher/holder confusion. All corrected T-086 Windows-route tests passed. |

### Final disposition

T-084 and T-086 need no further implementation pass and are approved at `2a41c5f`. T-088 needs a
focused correction for T088-R4 and new exact-head Windows evidence. T087-R6 should be corrected in
the same lifecycle-focused pass because it is the identical process-identity error and currently
keeps the Windows gate red; that correction does not reopen T-087's production implementation.

T-115 remains confirmed High and keeps Phase 2 exit criterion 7 unmet independently of this CI
failure. No reviewed production source was edited by the Reviewer.

## 2026-08-01 — T-115 and the final T-088 correction re-review

**Reviewer:** Codex (Reviewer)
**Review boundary:** `2a41c5f..f5dd8cb`
**Implementation commits:** `d999df1` (`T088-R4`, `T087-R6`) and `9e133a6` (`T-115`)
**Handoff head:** `6cdf1fc`
**Overall verdict:** **Changes requested for T-115. T-088 is approved.** The phase proof and its
Windows lifecycle corrections are sound, but the new admission route violates T-115's own queue
ordering criterion when a probed first row is retargeted before download.

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-088` | **Approved at `9e133a6`** | T088-R4's observer cannot turn a partial read into a terminal verdict; authoritative snapshots fail loudly; all four application teardowns reap the reported process tree; the three-worker snapshot precedes teardown; T087-R6 kills the holder's reported PID. The corrected suite passed on hosted Windows and Ubuntu. |
| `T-115` | **Changes requested at `9e133a6`** | Add-only draining, restart admission, recovery exclusion and pause all work, but the probed multi-URL route starts later queue positions before the probed head. That directly fails the task's explicit `queue_position` ordering criterion. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T115-R1` | **High** | **Yes — T-115** | Probed batch admission order | `AddUrlDialog._on_queue_saved()` admits every fresh, later-position row at `add_dialog.py:943-957`, then begins the probed row's asynchronous retarget at `:959-976`; the probed row is admitted only from its completion callback at `:980-993`. With a pool of one, probing the first URL and then adding it with a second URL leaves queue position 0 `READY` and starts position 1 at `PROBING`. The deterministic reviewer regression `test_a_probed_first_url_keeps_its_queue_position_when_the_batch_is_admitted` fails on exactly those states. The table says the probed row is first while the scheduler starts the second, contradicting T-115's acceptance criterion and T-081's established table/scheduler agreement. | Treat the saved batch as one admission decision. When a usable probe exists, settle its retarget first, then admit the probed id followed by the fresh ids in durable queue order. On retarget refusal, keep the probed row stopped as T-075 requires but still admit the other saved rows. Preserve the no-probe path and add a pool-of-one regression that distinguishes positions 0 and 1. | **Open** |
| `T115-R2` | **Low** | No | Behavioral prose | The implementation moved and several behavioral statements did not. `app.compose()` still promises “Constructs everything; starts nothing” at `app.py:220` although it now admits durable queued rows. The embedded phase launchers at `test_phase_2_exit.py:139-147` and `:185-187` still say the application has no route that drains a queue and that T-115 remains unfixed; the first also retains a now-redundant explicit-start loop. These are executable-surface comments/docstrings describing obsolete behavior. | Reconcile the compose contract with startup admission and update the embedded launcher prose. Remove the redundant priming loop if the phase tests do not intentionally need a second route; otherwise state that it is deliberately redundant and what independent claim it serves. | **Open, non-blocking** |
| `COORD-R12` | **Low** | No | Current-state coordination | Canonical current truth gives incompatible review queues. `TASKS.md:81-94` says five old tasks await verdict immediately above T-088/T-115. `STATUS.md:19-29` says four await review, T-088 is not started and T088-R4 remains open, while `:32` says T-115 is fixed and `:180-198` again says T-115 is an unfixed phase blocker. This is the same prose-drift class COORD-R11 and the session's stale behavior docstrings recorded. | Rebuild the TASKS In Review note and the leading STATUS snapshot from this verdict; mark superseded narrative explicitly historical or remove it from current truth. Do not leave both “fixed” and “blocks the exit” as live headings. | **Open, non-blocking coordination** |

### Resolved prior findings

| Prior finding | Result |
|---|---|
| `T088-R4` | **Resolved.** `settled()` requires a complete, non-empty id set; `snapshot()` retries and raises on incomplete reads; polling uses SQLite `mode=ro`; application trees are reaped by reported PID at every site; the three-worker final snapshot is taken before teardown. Direct helper tests and both hosted suites pass. |
| `T087-R6` | **Resolved as test evidence.** The holder reports its interpreter PID, the killed-holder case kills and waits for that process, and `_kill_tree` asserts no descendant survives. The production `InstanceLock` approval remains unchanged. |

### Review judgments

**T-115's placement is otherwise right.** A public durable-intent operation plus one startup
enumeration covers both newly added and previously queued work without a periodic database sweep.
Reading durable QUEUED ids after recovery prevents interrupted work restarting unattended, and the
direct filter test makes that rule independent of a downstream state-machine refusal.

**The probed-order defect is not a retarget-versus-safety trade.** T-075 correctly requires the
chosen request to be durable before the probed download starts. The defect is admitting later
positions while that prerequisite settles. Sequencing the batch after retarget preserves both
contracts; it does not require predicting the write or weakening persist-before-start.

**T-088 has real Windows evidence now.** Run `30719224116` at the T088-R4 coordination head passed
Windows with **1868 passed / 21 skipped / 32 deselected / 1 xfailed** and Ubuntu with **1880 passed /
11 skipped / 2 deselected / 1 xfailed**. The exact handoff-head run `30721559613` also passed after
T-115 inverted the xfail: Windows **1872 passed / 21 skipped / 32 deselected**, Ubuntu **1884 passed /
11 skipped / 2 deselected**; both frozen jobs passed and Windows desktop was skipped.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `2a41c5f..f5dd8cb` inspected; `git diff --check` passed. `6cdf1fc` is handoff only. |
| Exact-head CI | Run `30721559613`, SHA `6cdf1fce7b59cacae0e35e91b61ba915f67d0760`, conclusion **success**; Ubuntu, Windows and both frozen jobs passed; Windows desktop skipped with zero steps. |
| Focused existing unit/UI slice | **90 passed** (`test_interrupted_offer.py` + `test_add_dialog.py`, before adding the reviewer regression). |
| T-115 real application routes | **3 passed / 9 deselected**: Add-only drain, previous-run drain and paused admission. The sandbox initially refused localhost sockets; the same command passed with localhost access. |
| T088-R4 helper slice | **3 passed / 26 deselected**: incomplete settled read, refusing snapshot and whole-tree reap. |
| Full single-instance file | **17 passed**, including the corrected holder PID and survivor-reporting checks. |
| Ruff / format | `ruff check .` and `ruff format --check .` passed before the regression (**130 files**); the added regression separately passes both checks. |
| Reviewer regression | **1 failed as expected:** the probed position-0 row remained `READY` while the later position-1 row took the only slot and entered `PROBING`. |

### Final disposition

T088-R4 and T087-R6 are closed, and T-088 is approved at the final implementation/test head
`9e133a6`. T-115 needs one focused correction for T115-R1 before approval; Phase 2 does not exit
while that High acceptance-criterion failure remains. T115-R2 and COORD-R12 are non-blocking but
should be reconciled in the same handoff so the next review is not asked to infer current behavior
from contradictory prose. Reviewer production source was not edited. The intentionally failing
reviewer regression is the only test change in the working tree; this review record is the only
other change. Nothing was committed or pushed.

## 2026-08-02 — UI rework and T-115 correction: T-115, T-116, T-117, T-118 and T-120

**Reviewer:** Codex (Reviewer)
**Review boundary:** `6cdf1fc..3bdbbfa`
**Implementation commits:** `f6dd691` (`T-115`), `bdd6aea` (`T-116`), `af9bfa1`
(`T-117`), `6c2d1eb` (`T-118`) and `44091a1` (`T-120`); `6a7d07e` is the accepted
`UX-003`/task decomposition and `3bdbbfa` is the handoff.
**Exact candidate head:** `3bdbbfadfd79daafc1a98713464e29917ce4f7da`
**Overall verdict:** **Changes requested for T-116 and T-118.** T-115 and T-120 are approved.
T-117's implementation is approved with one non-blocking canonical-model follow-up. Phase 2
must not be declared exited on this head: its exact Windows job is red, and the failure exposed a
real same-job process-lifecycle race rather than supplying a trustworthy limit verdict.

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-115` | **Approved at `f6dd691`** | Add admits a saved batch as one ordered decision after all retargets settle; startup admits durable waiting intent after recovery; the Add-only and restart routes drain without a priming loop; pause and recovery exclusions remain intact. T115-R1, T115-R2 and COORD-R12 are closed. |
| `T-116` | **Changes requested at `3bdbbfa`** | Separate bounded lanes, a fixed default probe ceiling of four and lane-aware fill/refusal behavior are sound, but T116-R1 allows the download for a just-probed job to overwrite that job's still-live probe session before its process is released. Hosted Windows observed the resulting extra worker. |
| `T-117` | **Approved with follow-up at `af9bfa1`** | Migration `0002`, frozen historical data, null handling and the one-revision probe write are sound. T117-R1 is a non-blocking current-truth correction: `ARCHITECTURE.md`'s canonical Job field list still omits `thumbnail_url`. |
| `T-118` | **Changes requested at `6c2d1eb`** | The staging UI and Qt-free row state are substantial, but the implementation contradicts accepted UX-003 by persisting before Add, reproduces two asynchronous ownership races with Critical consequences, omits per-row preset overrides, and implemented a mock divergence before its explicit T-105 dependency. |
| `T-120` | **Approved at `44091a1`** | The canonical swatches have one source, both themes are independently defined and applied through palette plus inherited selectors, and text/control contrast is exhaustively measured. The reviewer added the missing all-`JobStatus` textual-name assertion; it passes. Dark-theme visual inspection remains honestly unverified, not a mechanical blocker. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T116-R1` | **High** | **Yes — T-116** | Same-job lane handoff / process ownership | `media_probed` is emitted by `_on_session_ended()` after the probe stream ends but before `_release()` has established that the probe process is gone (`manager.py:1909-1931`, `2156-2172`). Because download and probe capacity are now separate, the dialog may immediately admit the same READY id. `_spawn()` then assigns the download to `self._sessions[job_id]` unconditionally (`:1100-1129`), replacing the only `_Session` that owns and reaps a still-live probe. The deterministic reviewer child sends a valid final sentinel and lingers: the download starts while **two** worker processes exist for one job. Exact hosted Windows independently observed three workers against a download limit of two after all dialog rows had finished probing. This is not merely a stale assertion: the manager has lost the probe session object and its queue/log/process cleanup. | Treat an existing session for the same job as an admission barrier even when it belongs to the other lane. Release the probe process, pump, queue and job log before starting that id's download, then re-decide its queued admission. Preserve concurrency between probes and downloads for *different* jobs. Keep the deterministic same-id lingering-process regression and make the phase process sample distinguish legitimate cross-job lane work from an overwritten/unreleased session. | **Open** |
| `T117-R1` | **Low** | No | Canonical data model | `ARCHITECTURE.md:211-219` is current truth for core entities but its Job field list still omits `thumbnail_url`, the durable field T-117 added. The implementation, migration and tests agree; the canonical description does not. | Have the Documentation Maintainer add `thumbnail_url` to the Job entity list as T-117's coordination close. No implementation re-review is needed for that prose-only correction. | **Open, non-blocking follow-up owned by Documentation Maintainer / T-117** |
| `T118-R1` | **Critical** | **Yes — T-118** | Accepted UX-003 / durable queue intent | Accepted UX-003 says a job enters the queue only after it is probed, a URL that cannot probe never becomes a job, probe state appears only in the dialog, and nothing is persisted until Add (`DECISIONS.md:2505-2530`). `resolve()` instead builds QUEUED `Job`s and submits them before starting probes (`add_dialog.py:517-606`). These are not harmless temporary records: composition admits every durable QUEUED or READY row on startup (`app.py:166-195`). A crash after probe success therefore leaves a READY row that the next launch downloads even though the user never pressed Add. The reviewer regression proves that merely resolving already populates the store. | Give staging probes transient, non-durable identity/request ownership. Persist the resolved rows, their final per-row requests and queue positions only when Add commits them. A dialog close cancels transient probes; there is no durable queue row to remove or cancel. | **Open** |
| `T118-R2` | **Critical** | **Yes — T-118** | Asynchronous resolve ownership | When an initial batch write is outstanding, `resolve()` returns and claims its callback will resolve again (`add_dialog.py:527-532`), but `_on_rows_saved()` never does (`:562-585`). Replacing URL A with URL B during that write leaves A on screen and starts A's probe when the callback lands. Closing in the same window is worse: the rows have no ids yet, so `done()` closes without withdrawing anything; the callback then persists and starts the abandoned URL. Both deterministic reviewer regressions fail. The consequence is the exact T016-R1 class: wrong or abandoned work runs because an asynchronous completion was accepted against stale UI ownership. | Every asynchronous resolution completion must validate the current input generation and dialog lifetime before starting anything. Superseded work must be cancelled without becoming durable queue intent, and pending work must keep the close owned until cancellation is established. Retain separate edit-during-pending and close-during-pending regressions. | **Open** |
| `T118-R3` | **Critical** | **Yes — T-118** | Asynchronous Add/retarget ownership | `add_to_queue()` records `_retargets_pending` but `_refresh()` does not treat it as saving (`add_dialog.py:841-897`), so Add remains enabled and a second click schedules duplicate retargets. More seriously, `_committed` makes `done()` exempt those ids from withdrawal (`:967-1009`) even though the chosen request is not durable yet. The dialog can disappear while the retarget is outstanding; if the real write then fails, `_admit_when_ready()` clears `_committed` on a hidden dialog and leaves the durable READY row carrying its old request (`:899-921`). Startup admits that row and silently downloads the wrong format. Reviewer regressions prove both that Add remains enabled and that close abandons an unsettled commit. | Make retarget settlement part of the dialog's owned commit lifecycle: disable Add after the first commit request, refuse/hold close while it is unsettled, and on failure retain visible ownership or durably remove every uncommitted row. Do not expose a READY row with an old request to startup admission. Mutation-check failure, close and double-click variants. | **Open** |
| `T118-R4` | **High** | **Yes — T-118** | Required per-row format choice | T-118's acceptance criterion says the paste preset is overridable per row and the effective selector shown is what will run (`TASKS.md:167-176`). The implementation has only one batch preset; its row context menu supplies Retry and Remove, with no per-row request/preset model or action. Core user-visible task functionality is absent. | Add a per-row override with an explicit inherited/default state, show the effective selector for each committable row, and build each final request from that row's effective choice at Add. Test a mixed-preset batch through durable retarget and admission. | **Open** |
| `T118-R5` | **High** | **Yes — T-118** | Unmet dependency / approved mock divergence | T-118 explicitly depends on `T-105`'s `docs/UX_SPEC.md` (`TASKS.md:140-143`), and the Phase-3 trigger requires that document before the phase starts (`IMPLEMENTATION_PLAN.md:335-365`); the file does not exist. The implementation then deliberately replaces the approved mock's visible per-row controls with a context menu. Keyboard reachability is useful evidence but does not authorize changing the approved interaction, and the missing per-row preset action makes the divergence substantive rather than cosmetic. | Complete T-105 and implement the approved anatomy, or obtain and record an explicit maintainer amendment choosing the context menu and defining where the per-row preset override lives. This is a scope/design ruling, not something review can infer from code. | **Open** |

### Review judgments requested in the handoff

**Withdrawal by remove versus cancel is not accepted as the governing choice.** UX-003's accepted
rule is stronger: before Add, there is no durable job. A transient probe still needs cooperative
cancellation and process reaping, but closing or editing the staging list must not manufacture a
`CANCELLED` row *or* delete a temporary queue row. After Add, ordinary queue cancel/remove semantics
apply unchanged. This avoids adding `FAILED → CANCELLED` to ARC-004 because an uncommitted failed
probe never entered that state machine as a Job.

**A fixed `DEFAULT_PROBE_CONCURRENCY = 4` is accepted.** REQ-013 is the user-facing download limit,
not a promise of a second setting. The probe limit is separately constructor-injectable, its own
capacity/refusal/waiting behavior is tested with non-default values, and four is a bounded internal
policy that can be revisited if measured. T116-R1 concerns same-id lifetime, not the value four.

**The context-menu divergence is not approved on this record.** It needs T-105 plus either fidelity
to the approved mock or a maintainer amendment. A context menu may remain as a keyboard-accessible
secondary route; it cannot silently replace the only visible per-row affordances, particularly
while one required per-row action is missing entirely.

### Independent verification

| Check | Result |
|---|---|
| Boundary and tree | `6cdf1fc..3bdbbfa` inspected; `HEAD == origin/main == 3bdbbfadfd79daafc1a98713464e29917ce4f7da` before reviewer tests; implementation tree was clean; `git diff --check 6cdf1fc..3bdbbfa` passed. |
| Implementer local evidence | Reported **1932 passed / 11 skipped / 2 deselected**, all four mypy gates, ruff/format and **39 mutations killed**. This remains valid local evidence but is not an exact-head Windows pass. |
| Exact GitHub Actions | Run `30760049031`, exact SHA `3bdbbfadfd79daafc1a98713464e29917ce4f7da`, conclusion **failure**. Ubuntu and both frozen jobs passed; Windows desktop skipped. |
| Hosted Windows | **1 failed / 1919 passed / 21 skipped / 32 deselected**. `test_the_pool_never_exceeds_the_configured_limit` observed **3 worker processes** with download limit 2 while durable download-row accounting stayed at or below 2. All other selected Windows tests passed. |
| Frozen pre-T118 slices | T-115 **3 passed**; T-116 **6 passed**; T-117 **8 passed**; focused ruff/format and both source mypy platforms passed against the frozen implementation heads. |
| Current focused T-116/T-117/T-120 slice | **56 passed / 291 deselected**, including both lane ceilings, lane-aware fill/pause/cancel/shutdown, migration/thumbnail cases, both themes and the reviewer all-status textual-name assertion. |
| Reviewer T-116 regression | **1 failed as expected:** a valid probe stream lingered after its sentinel and the same job's download started, leaving **2 live workers for one job** and replacing the probe's `_Session`. Teardown then verified the processes ended. |
| Reviewer T-118 regressions | **5 failed as expected / 1 passed**: persistence before Add; edit during pending resolution; close during pending resolution; Add enabled during pending retarget; close during pending retarget. The passing case is T-120's all-status textual-name assertion. |
| Reviewer test hygiene | `ruff check`, `ruff format --check` and `git diff --check` pass for the three changed test files. |

### Final disposition

T-115 and T-120 need no further implementation pass. T-117's code and migration need no further
implementation pass; its documentation owner should close T117-R1. T-116 needs a focused
same-job-lifecycle correction and exact-head Windows evidence. T-118 needs one correction batch
covering all five findings, including the maintainer-owned T-105/mock decision; its three Critical
findings cannot be waived by an agent. T-119 must not build on T-118 until those blockers close.

Reviewer production source was not edited. The working tree contains only the six reviewer
regressions (five failing T-118 cases and one failing T-116 case), the passing T-120 state-name
assertion, and this review record. Nothing was committed or pushed.

## 2026-08-03 — T-116 and T-118 focused correction re-review

**Reviewer:** Codex (Reviewer)
**Correction boundary:** `3bdbbfa..253bbce`
**Implementation commits:** `5351be7` (T-116/T-118 corrections, T117-R1 and UX-004) and
`253bbce` (mutation/CI gaps)
**Coordination head inspected:** `a4d9ad1`; the later `bff9713` and `a4d9ad1` change only the CI
workflow and coordination documents, not reviewed source or tests.
**Overall verdict:** **T-116 is approved. Changes requested for T-118.** The transient-staging and
commit-lifecycle corrections close T118-R1 through T118-R3, and UX-004 supplies the maintainer
decision T118-R5 required. The new per-row implementation silently loses MP3 quality, does not
render a usable row, omits the required effective selector and declared focus order, and fails its
own cross-platform interaction gate.

### Task verdicts

| Task | Verdict | Reason |
|---|---|---|
| `T-116` | **Approved at `253bbce`** | One job cannot occupy both lanes: direct start refuses, admission parks, fill skips the held id, and release re-decides immediately. Different jobs still use the two lanes concurrently. The deterministic lingering-probe regression and focused process-backed checks pass. |
| `T-118` | **Changes requested at `253bbce`** | Transient staging and atomic final-request persistence are sound, but the correction introduces one Critical wrong-request defect and leaves four High user-visible acceptance failures in the row-control path. |
| `T-117` follow-up | **T117-R1 resolved at `5351be7`** | `ARCHITECTURE.md` now includes `thumbnail_url` in the canonical Job entity. T-117's prior implementation approval is unchanged. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T118-R6` | **Critical** | **Yes — T-118** | Per-row MP3 quality / wrong durable request | A row override stores the raw registry preset at `add_dialog.py:667-682`; only the inherited batch path applies the selected MP3 bitrate at `:497-501`, and `preset_for()` returns the raw row preset at `:927-934`. Deterministic offscreen proof: choose batch **Audio only (MP3)** at **320 kbps**, explicitly choose **Audio only (MP3)** for one row, then build its request. The visible batch selector says `320 kbps MP3`, but the row's durable request carries `audio_quality == "192"`. T-076 explicitly requires the displayed bitrate to be the one that runs and derives the preset to keep display and request in step. This correction splits them again: the application silently downloads at a quality other than the one its visible control says will run. The existing row test checks only `media_kind`, so both bitrates satisfy it. | A row override must derive the complete effective preset, including the currently selected MP3 quality, or expose and persist a row-specific quality choice. Show the effective quality with the row and add a non-default-bitrate end-to-end regression that reads the durable `DownloadRequest`; mutation-check replacing it with `MP3_QUALITY`. | **Open** |
| `T118-R7` | **High** | **Yes — T-118** | Staging-row rendering | `_refresh()` first lets the item delegate own the thumbnail and two lines of metadata, then installs a `QWidget` over the same item at `add_dialog.py:1024-1046`. That widget contains only `Download as` and the combo (`:605-639`). Offscreen rendering confirms the collision: a 96×54 thumbnail is put in a **25 px-high** row, and the row widget begins at x=102—the exact x where the delegate paints the title—so title/state text and controls overlap while the thumbnail is clipped. `item_texts()` claims to read what is shown but merely returns `QListWidgetItem.text()` (`test_add_dialog.py:533-541`), so the tests pass on obscured model data. This breaks the task's core staging-row anatomy: title, uploader, duration, state and thumbnail are not legibly rendered. | Give one renderer ownership of the complete row. A composite row must include the image and all visible metadata as well as the control; a delegate/editor design must paint them without collision. Gate actual geometry/rendered ownership—not just `item.text()` and `item.icon()`—including a long title and every state. | **Open** |
| `T118-R8` | **High** | **Yes — T-118** | Required per-row effective selector | T-118 still requires “the effective selector shown stays the one that will run” (`TASKS.md:175-176`). A row override shows only a preset name: the combo is populated from `preset.name` (`add_dialog.py:634-636`) and `describe_preset()` returns the name plus inheritance wording (`:224-234`). The only literal selector/quality display is the batch-level `_selector_value`; selecting an audio override while the batch is video leaves that display describing the video batch. The request may use the row selector, but the required per-row truth is absent. | Show each row's literal effective selector and applicable quality derived from the same `Preset` object passed to `to_request()`. Add a mixed video/audio batch regression asserting the per-row displayed selector equals each durable request's `format_selector`, plus the non-default MP3 case from T118-R6. | **Open** |
| `T118-R9` | **High** | **Yes — T-118** | Keyboard focus order | The new row combos are created after `_set_tab_order()` and are absent from `focus_chain()` (`add_dialog.py:298-308`, `:438-465`). With two READY rows, Qt's actual focus chain puts both `rowPresetChoice` controls **after Close**, rather than at their rows. The purported independent test creates no rows, filters every `ROW_PRESET_NAME` out of its observation, and never counts or orders them (`test_add_dialog.py:1236-1258`). This repeats the exact vacuity its docstring warns about and leaves T-118's explicit “focus order is declared per state” criterion unmet. | Define where the dynamic row controls belong in keyboard order and rebuild/maintain that order as rows reconcile. Test at least two READY rows and a failed/resolving mix by traversing the actual Qt focus chain; assert the row-control count and positions rather than filtering them out. | **Open** |
| `T118-R10` | **High** | **Yes — T-118** | Cross-platform responsiveness / exact CI | UX-004's support claim is based on one Linux measurement and says 150 rows cost 85.7 ms. Exact-head run `30786142921` measured the same operation at **0.722 s** on hosted Windows and failed `test_a_paste_the_design_supports_stays_inside_the_interaction_budget`; the job finished **1 failed / 1928 passed / 21 skipped / 32 deselected**. That exceeds even the test's relaxed 0.5 s allowance and is over seven times NFR-001's ~100 ms interaction target. The decision already says the threshold is machine-dependent; naming 150 as the supported paste anyway does not make it cross-platform evidence. | Remove the per-row construction cost from the synchronous path—most naturally by bringing the reusable delegate/editor work forward—or establish and state a genuinely supported cross-platform bound that still exceeds the probe lane. Keep a required hosted-Windows measurement at that bound. Do not weaken or delete the red gate as “runner speed.” | **Open** |
| `T118-R11` | **Low** | No | Behavioral prose and dead correction residue | Current code says the list is “a plain item list, not a widget per row” (`add_dialog.py:381-389`) while creating one widget per row; `_committing` is assigned and never read (`:295-296`); and `Staging.unresolved_job_ids()` / `written_job_ids()` still describe rows persisted before probing although transient staging removed that design (`staging.py:220-240`). These are behavior claims in current source, not harmless history, and they now point maintenance toward the rejected implementation. | Remove the unused state/helpers or give them a truthful current contract, and reconcile the list comment with the selected UX-004 design. Audit the touched docstrings for pre-T118-R1 durable-staging language. | **Open, non-blocking** |

### Prior-finding resolution

| Prior finding | Result |
|---|---|
| `T116-R1` | **Resolved.** `_holds()` covers sessions and reservations across lanes; `start()` refuses while `admit()` parks; `_release()` fills only after process/pump ownership is released. The lingering-probe regression ends with one worker for one job. |
| `T118-R1` | **Resolved.** `stage()` creates only an in-memory job; staged transitions route through `_settle` without repository writes; `unstage()` cancels and reaps without manufacturing a durable `CANCELLED` row. A staged id cannot be downloaded. |
| `T118-R2` | **Resolved.** Staging identity is returned synchronously. Edit and close immediately own an id they can unstage, and the deterministic stale-edit/abandoned-close regressions pass without persistence. |
| `T118-R3` | **Resolved.** Add creates new durable jobs carrying their final requests in one batch write; `_saving` disables duplicate Add and holds close until settlement. The corrected `finished`-signal regression observes the lifecycle rather than a falsy dialog result. |
| `T118-R4` | **Not resolved.** A per-row preset control now exists and its broad media kind reaches persistence, but T118-R6 and T118-R8 show that the complete effective request is neither preserved nor shown. |
| `T118-R5` | **Resolved as a maintainer decision.** Accepted UX-004 authorizes visible per-row format controls with Retry/Remove in the context menu and removes T-105 as this task's prerequisite. The implementation still has to satisfy that decision. |
| `T117-R1` | **Resolved.** The canonical Job field list names `thumbnail_url`. |

### Review judgments

**The transient manager seam is acceptable.** The audited staged paths keep the state-machine and
session machinery shared while putting the persistence split in `_persist`; queue-only listeners
receive `job_changed`, and transient listeners receive `staged_changed`. `_require()` serving both
lifetimes does not itself imply persistence, and the focused edit, close, refusal, cancellation and
same-job release paths showed no durable staging trace.

**UX-004 is accepted but its measurement does not waive NFR-001.** The decision explicitly records
that its one-machine threshold moves on slower hardware. Hosted Windows supplied that missing
measurement and failed even the test's 500 ms allowance. More importantly, the implemented widget
does not compose with the item renderer at all; the visual collision is not a scale trade-off.

**T118-R6 is not a cosmetic mismatch.** A user-facing 320 kbps choice reaching yt-dlp as 192 kbps
is a silent wrong download request, the same consequence that made the earlier retarget ownership
finding Critical. Giving the row a preset name without its derived fields is precisely the split
`with_audio_quality()` was introduced to prevent.

### Independent verification

| Check | Result |
|---|---|
| Boundary and branch movement | `3bdbbfa..253bbce` inspected; `git diff --check` passed. During review `main` advanced through `bff9713` and `a4d9ad1`; `git diff 253bbce..a4d9ad1 -- src tests pyproject.toml` is empty, so the reviewed implementation head remains `253bbce`. |
| Implementer local evidence | Reported **1941 passed / 11 skipped / 2 deselected**, all four mypy gates, ruff/format, and **9/9 mutations killed** with sources restored byte-identically. |
| Focused reviewer slice | **8 passed in 12.52 s**: same-job lingering release, direct-start refusal, staged-download refusal, transient persistence, stale edit, close during resolve, commit-close ownership and per-row broad media-kind persistence. |
| Deterministic MP3 probe | Batch selected MP3 at 320; explicit row MP3 override produced `row_quality == request.audio_quality == "192"` while the visible batch selector said `320 kbps MP3`. |
| Deterministic render/focus probes | One row: thumbnail target 96×54, item/row-widget height 25 px, widget starts at the title's x=102. Two READY rows: actual Tab order reaches both `rowPresetChoice` controls only after `closeButton`; declared `focus_chain()` contains neither. |
| Exact-head CI | Run `30786142921`, SHA `253bbcea0297cb6fdc3182a3592bd79bf68627a4`, conclusion **failure**. Ubuntu and both frozen jobs passed. Hosted Windows failed only T118-R10. |
| Windows desktop at candidate | Failed before checkout at “Stamp the job start time” because STARBASE had Windows PowerShell 5.1 but the workflow required `pwsh`; no desktop test executed. `bff9713` changes those two workflow steps only, so its later run may supply additional desktop evidence but cannot change the T-118 source verdict. |
| Post-candidate desktop evidence | Run `30821625627` at workflow/coordination head `a4d9ad1` reached the real STARBASE desktop after `bff9713`, then finished **2 failed / 28 passed / 1952 deselected**. Both failures are the pre-existing T-084 progress-view focus expectation omitting `diagnosticsBox`, not T-116/T-118 behavior. A concurrent uncommitted test correction appeared while this review was being written; it is outside this boundary and was not reviewed. |

### Final disposition

T-116 is approved at the exact implementation head `253bbce`; its one blocking finding is closed.
T-118 remains in review and must not be a dependency for T-119 while T118-R6 through T118-R10 are
open. The next focused correction must preserve the transient/commit ownership fixes and address
the complete per-row contract as one design: one rendered row, one declared keyboard route, and one
fully derived preset/request/display source of truth. T118-R11 is non-blocking cleanup but belongs
in that correction because it describes the rejected design.

No reviewed production source or tests were edited. This review record is the only reviewer change;
nothing was committed or pushed.

## 2026-08-03 — CI corrections and Phase 2 roadmap review

**Reviewer:** Codex (Reviewer)
**Review boundary:** `2ec9c45..7202a5d`
**Handoff head inspected:** `71fa992` (handoff only after the reviewed boundary)
**Overall verdict:** **CI corrections approved; changes requested for the coordination record.**
The corrected T-083 test wait and `OPS-009` workflow implementation are sound. The rebuilt
current-truth documents still give incompatible instructions about Phase 2 sign-off and the merged
T-118/T-119 correction, and the task ledger has not actually filed three tasks it says are filed.

### Component verdicts

| Component | Verdict | Reason |
|---|---|---|
| T-083 retry-test correction | **Approved at `6c38d5f`** | The wait now observes the final automatic attempt's durable `FAILED` outcome before testing the bound. The following one-second event-pumping hold is twenty times the installed 50 ms backoff, so the ordinary fourth-attempt mutation is observable after the session releases. The final exact count and manual-retry assertions remain. T-083's production implementation and prior approval are unchanged. |
| `OPS-009` frozen-workflow correction | **Approved at `6c38d5f`** | `runner.environment` is a documented two-valued runner property, both branches executed in run `30826638984`, and the frozen build and smoke passed on both hosted Ubuntu and self-hosted Windows. `matrix.name` now supplies distinct artifact names and non-empty platform evidence. |
| Phase 2 / UI-rework coordination | **Changes requested at `7202a5d`** | The plan's rebuilt table is useful, but STATUS and TASKS contradict its exit state, the maintainer's merged-task decision, and the recorded task approvals. |
| T-118 source | **Not re-reviewed** | This boundary records the known T-118 failures but does not change their source. T118-R6 through T118-R10 remain open under the prior verdict. |

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `COORD-R13` | **Medium** | **Yes — coordination record** | Phase 2 exit truth | `IMPLEMENTATION_PLAN.md:183-191` and criterion 6 at `:329` correctly say the phase has **not** exited: all deliverables are approved, but independent phase sign-off is absent, and T-118/T-119 is only a maintainer sequencing edge. `STATUS.md:19-22` instead says criterion 6 is met and that T-118 is what remains open. That turns a lower-authority sequencing decision into the exit criterion and materially misstates phase readiness. | Make STATUS use the plan's distinction verbatim: 13/13 deliverables approved; criterion 6 pending an independent phase exit review; T-118/T-119 precedes that review only because of the named maintainer sequencing decision. | **Open** |
| `COORD-R14` | **Medium** | **Yes — coordination record** | T-118/T-119 merged scope | The new text says T-118 and T-119 are one task (`TASKS.md:99-107`, `:887-893`), but the executable task instructions still say queue rendering is out of T-118 (`:187-191`) and T-119 depends on T-118 (`:897`), making the combined work depend on itself. T-118 also retains T-105 as a dependency at `:146-147` after accepted UX-004 explicitly removed it as this correction's prerequisite (`DECISIONS.md:2586`); because T-119 still names T-105 too, the merged record does not say whether that original dependency is deliberately retained for the combined work. STATUS compounds the ambiguity by leaving “T-119 is deliberately not started” at `:62-64` immediately before “corrected as one task” at `:66-71`. An implementer cannot tell whether to start, what owns the delegate, or which prerequisite governs it. | Express one actionable work item. Either subsume T-119 into T-118 and move its scope/criteria under that task, or keep two tasks with a non-circular delivery order. Remove the obsolete hold and out-of-scope line, remove T-105 from T-118 as UX-004 requires, and state explicitly whether T-119's original T-105 dependency survives the merge. Preserve T-119's caching/accessibility criteria rather than losing them during the merge. | **Open** |
| `COORD-R15` | **Medium** | **Yes — coordination record** | Canonical task ledger | The In Review note says T-115, T-117 and T-120 are approved and filed under Complete (`TASKS.md:81-85`), but T-115 remains an `In Review` entry at `:241-258`, T-117 remains an `In Review` entry at `:195-205`, and no `### T-120` task entry exists anywhere in the file. `test_task_placement.py` still passes because the stale entries' status text agrees with their stale section; it cannot compare the ledger to review verdicts. This is the same approval/queue drift the roadmap rebuild claims to close and affects the evidence for Phase 2 readiness. | File T-115 and T-117 under Complete with their approved heads and resolved findings, and restore/file T-120 under Complete at `44091a1`. Then rebuild the In Review count from the actual section, not its leading prose. | **Open** |
| `COORD-R16` | **Low** | No | Exact-run evidence wording | STATUS `:103-106` and the handoff evidence table describe the desktop “full suite” as **1929 passed, 0 failed**. Run `30826638984` concluded failure: those 1929 test calls passed, but two teardown errors made the job red. The errors are disclosed later, so this is not hidden evidence, but presenting only the failure count makes a failed full-suite job look green and calls the self-hosted desktop run “hosted” in the handoff. | Report the whole result together: 1929 passed plus two teardown errors, job failed; identify the desktop as self-hosted. State narrowly that the corrected T-083 test passed and the frozen Windows job passed. | **Open, non-blocking** |

### Review judgments requested in the handoff

**The corrected T-083 gate is stronger for the failure actually observed.** The old predicate
returned as soon as attempt three *started*, then gave that worker a fixed second to finish. The new
predicate cannot return until attempt three has persisted `FAILED`; only then does it hold for
twenty patched backoffs and assert the exact attempt count. The fake child sends `Failed` and
`WorkerFinished` in order, and the hold continues pumping events, so a fourth ordinary retry has a
free lane and becomes visible. A hypothetical retry delayed beyond twenty times its configured
backoff is not covered, but neither was it covered by the old finite wait; that is not a weakening
of this gate.

**T-116 did not cause the observed `PROBING` row.** `start()` captures the expected transition and
`entering()` recomputes `_ENTRY_STATUS` from the row at persistence time (`manager.py:1129-1143`).
A row already moved to `FAILED` yields no goal, declines the pending start and cannot be written
back to `PROBING`. The observed attempt count of three with `PROBING` is the final retry already in
flight, exactly the state the old test raced.

**`runner.environment` is the right boundary.** It expresses the property that matters—who owns
the machine—rather than coupling provisioning safety to a matrix display name. GitHub's runner
context documents only `github-hosted` and `self-hosted`; run `30826638984` exercised both values.

### Independent verification

| Check | Result |
|---|---|
| Boundary and tree | `2ec9c45..7202a5d` inspected; `git diff --check` passed. `HEAD == origin/main == 71fa992`; the tree was clean before this review record. |
| Focused local checks | Corrected bounded-retry test plus `tests/unit/test_task_placement.py`: **15 passed in 2.69 s**. |
| Exact Actions run | Run `30826638984`, SHA `6c38d5f91607a0fd7b6dd602aa274b88f22ccfa1`, conclusion **failure** from known T-118 failures. Hosted Ubuntu passed. Hosted Windows finished **1 failed / 1928 passed / 21 skipped / 32 deselected** on T118-R10. The self-hosted desktop reached the corrected T-083 case but ended with two recorded T-118 teardown errors. |
| Frozen branch coverage | `frozen ubuntu-latest`: setup-python success, machine check skipped, build/smoke success. `frozen windows`: setup-python skipped, machine check success, build/smoke success. |
| Runner expression authority | GitHub Actions' official runner-context reference lists `runner.environment` as a string whose possible values are `github-hosted` and `self-hosted`; step-level `if` permits the runner context. |
| Task-ledger gate | `tests/unit/test_task_placement.py`: **14 passed**, but direct ledger inspection shows why it cannot catch COORD-R15: the stale status and stale section agree. |

### Final disposition

The T-083 test-only correction and `OPS-009` workflow correction need no further implementation
pass. T-083 and T-116 retain their prior approvals. The roadmap/coordination batch needs one focused
reconciliation of COORD-R13 through COORD-R15; COORD-R16 is non-blocking evidence cleanup. T-118's
existing source verdict is unchanged, and its two newly observed teardown defects remain part of
that correction rather than this CI/docs review.

No reviewed source, tests or workflow files were edited. This review record is the only reviewer
change; nothing was committed or pushed.

## 2026-08-03 — Coordination corrections focused re-review

**Reviewer:** Codex (Reviewer)
**Submitted span:** `7202a5d..890fb5d`
**Focused correction boundary:** `71fa992..890fb5d`
**Correction commit:** `890fb5d`
**Overall verdict:** **Approved with follow-up.** COORD-R13 through COORD-R16 are resolved. One
non-blocking current-truth sentence and one Markdown typo remain; neither changes the task queue,
phase gate, or T-118 scope, so T-118 may proceed.

The submitted span contains two commits: `71fa992` adds the prior handoff and `890fb5d` contains the
coordination corrections. The latter is the one-commit re-review boundary.

### Prior-finding resolution

| Finding | Result |
|---|---|
| `COORD-R13` | **Resolved.** STATUS now says 13/13 Phase 2 deliverables are approved while criterion 6 remains unmet pending an independent phase exit review. It names T-118's position before that review as a maintainer sequencing choice, not a phase criterion. This agrees with the higher-authority plan and its criterion-6 row. |
| `COORD-R14` | **Resolved.** T-119 is a `Cancelled — subsumed into T-118` tombstone, not a second actionable task. T-118 removes the queue-rendering exclusion and T-105 dependency, carries T-119's affected surfaces, context, complete acceptance criteria and risk, and has no circular dependency. STATUS and the plan describe the same single item. |
| `COORD-R15` | **Resolved.** T-115, T-117 and restored T-120 each appear exactly once under Complete at their reviewed heads. In Review contains exactly T-118, and the leading count says one. The placement test passes against the corrected ledger. |
| `COORD-R16` | **Resolved.** STATUS and the handoff identify `windows desktop` as self-hosted and report the whole result together: corrected T-083 test passed, 1929 test calls passed, two teardown errors, job failed. The frozen Windows success remains stated separately. |

### New non-blocking follow-up

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Owner / target | Status |
|---|---|---:|---|---|---|---|---|
| `COORD-R17` | **Low** | No | Current-truth prose / Markdown | STATUS `:85-88` still calls the earlier T-083/OPS-009 fixes “two red gates on main” and says neither correction has been reviewed, although the review committed at this same head approves both. `IMPLEMENTATION_PLAN.md:391-393` also attempts to nest backticks in `` `Cancelled — subsumed into `T-118`` ``, producing malformed inline code. Neither changes the now-correct gate or task state. | Say the two gate corrections were approved in the preceding review and leave only T-118 red. Render the tombstone without nested backticks, for example **Cancelled — subsumed into T-118**. | Documentation Maintainer; next coordination/status update before the Phase 2 exit review | **Open, non-blocking** |

### Independent verification

| Check | Result |
|---|---|
| Boundary | `71fa992..890fb5d` inspected; the wider submitted span contains the prior handoff as a separate commit. `git diff --check` passed for both spans. |
| Change isolation | No files under `src/`, `tests/`, `.github/` or `pyproject.toml` changed in the focused correction. T-118 source and its existing verdict are unchanged. |
| Task placement | `tests/unit/test_task_placement.py`: **14 passed in 0.09 s**. |
| Ledger audit | Exactly one heading each for T-115, T-117, T-119 and T-120. T-115/T-117/T-120 are under Complete; T-119 is the subsumed tombstone; T-118 is the only In Review entry. |
| Scope preservation | All seven T-119 acceptance criteria, its cache policy, affected surfaces, accessibility rule, out-of-scope history rendering and risk are carried into T-118. T-105 is explicitly not a dependency of the merged correction. |

### Final disposition

The coordination correction is approved at `890fb5d`; no maintainer waiver is needed. COORD-R17
is a non-blocking documentation follow-up and does not consume another correction pass or prevent
work on T-118. Phase 2 criterion 6 remains pending the independent phase exit review, exactly as
the corrected plan and status say.

No reviewed coordination/source/test files were edited. This review record is the only reviewer
change; nothing was committed or pushed.

## 2026-08-03 — T-118 delegate correction re-review

**Reviewer:** Codex (Reviewer)
**Submitted delegate span:** `446d151..d4d05de`
**Effective review boundary:** `890fb5d..d4d05de`
**Implementation head:** `797db86`; `d4d05de` is the handoff-only head
**Overall verdict:** **Changes requested for T-118.** The transient staging teardown and effective
request corrections are sound, and the shared delegate fixes the clipping and widget-per-row
scaling defects. The rendered staging row does not provide the visible per-row control UX-004
requires, elides the exact selector T118-R8/REQ-009 require, and performs thumbnail disk/lifecycle
waits synchronously on the GUI thread. T118-R10 also remains open until the required Windows
measurement runs on a corrected candidate.

The submitted range is not a complete task boundary. Because Git ranges exclude their left-hand
commit, it omits the Critical T118-R6 correction at `446d151`; it also omits the two teardown
corrections at `e300b04`. Both were still unreviewed. This review therefore starts at the last
approved coordination head, `890fb5d`, and covers those corrections as well as the delegate batch.

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T118-R8` | **High** | **Yes — T-118** | Exact effective selector | The model now carries the correct per-row selector, but the renderer does not keep it visible. `row_delegate.py:76-80` says this line must survive eliding intact because a truncated selector cannot teach the syntax; `_paint_text()` nevertheless passes it through `elidedText(..., ElideRight, ...)` at `:277-283`. The delegate also removes a fixed 200 px from the text area for an empty editor slot at `:205-212`. At the tests' own 700 px render width, the available selector area is 382 px; the built-in 1080p line is 962 px and paints only through “following the batch …”, omitting the literal selector entirely. The other built-ins are also truncated. Existing tests assert the model's full string, not the text the sighted user sees, so they pass. This leaves the original “effective selector shown stays the one that will run” acceptance criterion and REQ-009 unmet. | Render the literal selector in full on the staging surface in a form that remains visible and selectable/copyable at realistic widths—wrapping or a dedicated selectable detail are preferable to a tooltip. Add a regression against the rendered/visible contract, not only `DisplayRole`. | **Open; prior finding not resolved** |
| `T118-R12` | **High** | **Yes — T-118** | UX-004 visible per-row control | UX-004 says every row carries a visible **Download as** control and specifically rejects hiding the override behind discovery (`DECISIONS.md:2576-2583`, `:2612-2622`). The delegate reserves `EDITOR_WIDTH` but paints nothing in that slot (`row_delegate.py:202-212`); the only `QComboBox` is created after editing starts (`:308-330`). `SelectedClicked` at `add_dialog.py:548-555` opens it only after the row is already selected, while F2 and the context menu require the user to know the feature exists. The structural test at `test_add_dialog.py:1682-1701` requires **zero** controls until one is asked for, so it encodes the missing affordance rather than catching it. The accepted T-119 sequencing note permits one reused widget on the row under pointer or focus; it does not permit an empty 190 px slot. | Keep the one-editor scaling design, but draw a recognizable combo/control affordance and current value on the hovered or focused row, and make the direct pointer interaction open that same editor. Add a shown-dialog test that distinguishes a visible affordance from an editable model flag or programmatic `edit_row()` call. | **Open** |
| `T118-R13` | **High** | **Yes — T-118** | NFR-001 / ARC-005 thumbnail lifecycle | Thumbnail fetch/decode are asynchronous, but cleanup is not. Every queue model reset invokes `_sweep_thumbnails()` synchronously (`queue_view.py:669-672`, `:760-772`), and `ThumbnailStore.sweep()` enumerates the cache directory, stats entries and unlinks files inline (`thumbnails.py:305-328`). Closing the add dialog and detaching the queue call `ThumbnailStore.close()`, which runs `QThreadPool.waitForDone(5000)` inline (`add_dialog.py:1124-1131`; `queue_view.py:709-712`; `thumbnails.py:330-341`). These are disk waits of unbounded duration, up to an explicit five seconds on close, on the GUI thread. NFR-001 and ARCHITECTURE §8 are unqualified: nothing on that thread may block on disk or long operations. The same project previously rejected blocking shutdown on exactly that basis. Current tests use a small local cache and completed workers, so they do not exercise either wait. | Move cache enumeration/deletion and pool retirement into an asynchronous lifecycle. Closing should mark the store closed, cancel network work, return, and complete ownership from a signal/callback when worker tasks have drained; do not replace the five-second wait with a shorter GUI-thread wait. Add slow-sweep and slow-runnable regressions that assert the UI call returns inside the interaction budget. | **Open** |
| `COORD-R18` | **Medium** | No | Review boundary | `446d151..d4d05de` correctly describes the six commits after R6, but not a complete approval boundary: it excludes `446d151` itself and the unreviewed teardown correction at `e300b04` while asking for T-118's verdict. Following the range literally would sign off a Critical correction and two observed Windows teardown defects without reviewing them. The handoff discloses that they are ancestry, but disclosure does not put them inside the diff. This review compensated by inspecting `890fb5d..d4d05de`, so it no longer blocks this verdict. | For the next handoff, name the prior independently reviewed implementation head as the approval base and separately identify docs/handoff-only commits. A correction sub-range may start at `797db86`, but it must not be presented as the complete T-118 approval boundary unless this review record is included as the prior review. | **Open, non-blocking process follow-up** |

### Prior-finding resolution

| Prior finding / correction | Result |
|---|---|
| `T118-R6` | **Resolved.** `effective()` is the single derivation for batch and row presets; per-row MP3 overrides carry the selected non-default bitrate into both display and the durable request. The mixed-selector and non-default bitrate regressions cover the silent-wrong-request class. |
| `T118-R7` | **Resolved.** The row widget is gone; `sizeHint()` is derived from the 54 px thumbnail plus padding and from three lines in the active font. The staging and queue views use the same delegate. |
| `T118-R8` | **Not resolved.** The role value is correct, but the sighted rendering truncates the literal selector as recorded above. |
| `T118-R9` | **Resolved for keyboard ownership.** The editor belongs to the row, F2/edit-trigger behavior is declared, the context menu reaches the same editor, and no persistent editor enters the fixed tab chain. T118-R12 is the separate UX-004 visibility failure. |
| `T118-R10` | **Correction design accepted; verification remains open.** The widget-per-row design is gone, one editor exists only while editing, viewport paint cost is flat in model size, and the structural assertion kills restoration of persistent editors. The prior finding explicitly required a Windows measurement at the replacement bound. None has run on this candidate, and the maintainer-authorized STARBASE substitution is a different machine from the hosted runner where the flap was observed. Do not spend that run until the blocking source corrections above produce the actual candidate. |
| `T118-R11` | **Resolved.** `_committing` and obsolete durable-staging helpers are gone, and the touched module prose now describes transient staging and the shared delegate. |
| T-118 teardown corrections at `e300b04` | **Resolved.** `cancel()` drops an unknown occupant and its reservation without persistence; `_cancellation_of()` asks `can_transition` and declines FAILED→CANCELLED; an unstaged record survives only until its live session is reaped. The three direct regressions pass independently. |

### Review judgments

**The model's two vocabularies are acceptable.** `QueueModel` keeps the per-field columns REQ-014
and existing consumers use, while the delegate roles compose those same `_text()` values. Column
zero's accessible text reads the whole row. No independent formatter was found that could make the
sighted and accessible values disagree; the current by-value tests are proportionate evidence.

**The structural scaling gate is the useful one, but its UX premise is wrong.** Counting persistent
row widgets correctly detects the Windows regression class. The two unshown-dialog timing tests
remain coarse evidence at best, as the handoff discloses. The correction is not to restore 500
combo boxes; it is to paint a discoverable control and reuse one live editor on hover/focus, which
is exactly the C design UX-004 already authorized.

**No STARBASE variable was changed and no CI run was spent.** The six delegate commits are not on
`origin/main`, and this head already has blocking source findings. The owed Windows measurement
belongs on the corrected implementation head so the limited run supplies evidence for the code
that could actually be approved.

### Independent verification

| Check | Result |
|---|---|
| Boundary and tree | `890fb5d..d4d05de` inspected, including `e300b04` and `446d151`; `git diff --check` passed. Before the review record, `HEAD == d4d05de`, `origin/main == 446d151`, and the implementation tree was clean. |
| Focused UI/model/cache slice | `tests/ui/test_add_dialog.py`, `test_row_delegate.py`, `test_queue_view.py` and `tests/unit/test_staging.py`: **122 passed in 35.29 s**. |
| Excluded teardown corrections | Three named manager regressions: **3 passed in 1.46 s**. |
| Wider manager/UI attempt | **246 passed / 1 deselected**; 16 integration cases failed before their assertions because this sandbox forbids the tests' localhost `ThreadingHTTPServer` socket (`PermissionError: Operation not permitted`). Those are environment denials, not counted as passing evidence. |
| Selector render probe | Default Qt 9 pt font, 700 px row: 382 px remains after thumbnail, gaps and reserved editor. Built-in selector lines measure 507-962 px and every one is right-elided; the 1080p literal selector is entirely absent from the painted prefix. |
| Static gates | `ruff check .`: passed; `ruff format --check .`: **140 files** formatted; bare `mypy`: clean, **101 files**; bare `mypy --platform win32`: clean, **101 files**. |
| Implementer evidence | Reported **1972 passed / 11 skipped / 2 deselected** and ten killed mutations with byte-identical restoration. No CI or Windows execution exists for this candidate. |

### Final disposition

T-118 remains in review. T118-R8, T118-R10, T118-R12 and T118-R13 block approval. The next focused
correction should preserve the resolved transient-staging, effective-request, row-height,
keyboard-ownership and manager-teardown work; make the row's control genuinely visible; keep the
literal effective selector visible/selectable; and remove all GUI-thread disk/pool waits. Then run
the mutation battery and the STARBASE Windows job on the exact corrected implementation head.

No reviewed production source or tests were edited. This review record is the only reviewer
change; nothing was committed, pushed or changed in GitHub repository variables.

## 2026-08-03 — T-118 second delegate correction re-review

**Reviewer:** Codex (Reviewer)
**Approval base:** `890fb5d`
**Focused correction boundary:** `d4d05de..d1d9cbb`
**Implementation head:** `d1d9cbb`; `adc5355` is its handoff-only head
**Coordination amendments inspected:** `c7ac845`, `2514d30` (local, unpushed)
**Overall verdict:** **Changes requested for T-118.** The visible control, exact current-row
selector and scaling evidence are now sound, and the Windows debt is discharged. T118-R13 remains
open because destruction still waits on the pool and permits workers to emit through a deleted
store. The model-reset correction also creates T118-R14: an open row editor becomes orphaned and
its format choice is silently discarded when any other row refreshes.

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T118-R13` | **High** | **Yes — T-118** | Thumbnail-store ownership / GUI-thread lifecycle | `close()` itself now returns, but the promised asynchronous ownership has no consumer: production connects nothing to `ThumbnailStore.closed`, while the `QThreadPool` remains the store's QObject child (`thumbnails.py:236-245`, `273-279`, `392-426`). Deleting the parent therefore invokes the pool destructor on the GUI thread, where Qt waits for its runnables. Worse, each runnable still emits through the store (`:133-150`, `:163-187`, `:204-224`) even though a Python reference does not keep the wrapped C++ QObject alive. A deterministic reviewer probe filled the pool, queued one real store read, called `close()` and delivered `DeferredDelete`; deletion blocked **1.008 s** until a timer released the pool, then `_ReadFromDisk` raised `RuntimeError: Signal source has been deleted` for both `disk_missed` and `task_done`. Queue shutdown has the same route: the queue store is parented to `QueueView`, and the main-window close path does not detach it. This still violates NFR-001 and can lose worker completion during shutdown. | Give the outstanding work real asynchronous ownership. For example, detach/retain a closing store until its counted tasks drain and only then `deleteLater`, or move worker signals to a separately owned result object. Wire the production owner to that lifecycle; do not rely on a child `QThreadPool` destructor. Add a regression that closes **and deletes** a store with a blocked, store-owned task and proves both that deletion returns within the interaction budget and that the worker emits through no deleted QObject. | **Open; prior finding not resolved** |
| `T118-R14` | **High** | **Yes — T-118** | Per-row editor / model reset | `StagingModel.refresh()` uses `beginResetModel()` for every value change (`add_dialog.py:402-410`), and `_refresh()` restores only the numeric current index after the reset (`:1154-1163`). Qt invalidates the live editor's model index during that reset; `RowDelegate` nevertheless retains `_editing_row`, and the old `QComboBox` remains under the view (`row_delegate.py:451-468`). A deterministic shown-view probe opened row 0's control, reset the model, changed the surviving editor and committed it: Qt reported `commitData called with an editor that does not belong to this view`, `setData` was never called, and the editor remained orphaned. This is an ordinary multi-row path, not teardown: another row finishing or failing a probe calls `_refresh()` at `add_dialog.py:885-935` while the user is choosing a format. The visible choice can therefore be discarded, defeating the per-row request the task exists to deliver. | Emit `dataChanged` for value-only row updates and reserve model reset for structural reconciliation, or explicitly close/commit the active editor before a reset and reopen it against stable row identity. Do not preserve only a row number across a changing visible set. Add a shown-dialog regression that keeps row A's editor open while row B settles, then commits A and asserts A's effective and durable request changed. | **Open** |
| `T118-R15` | **Medium** | No | Font scaling / row-selector claim | The dedicated selector detail resolves T118-R8, but the row's stronger “wraps rather than clips” claim is true only for the default 9 pt test font. `SELECTOR_LINES` is fixed at two and `sizeHint()` reserves four total lines (`row_delegate.py:109-125`, `173-184`, `359-384`). At the correction test's 582 px selector width, the longest built-in needs two lines at 9 pt, **three at 12–15 pt and five at 18 pt**. The existing large-font assertion still checks only three total lines (`test_row_delegate.py:230-232`), and the render test measures the default font. A user can select the row and read/copy the full value below the list, so this has a workaround and does not keep T-118 open. | Either size/layout the rendered selector from the active font and available width, or narrow the row contract and make the dedicated detail the explicit full-selector surface. Add a scaled-font case so the prose and test cannot claim clipping protection from a default-font measurement. | **Open, non-blocking; Implementer to file a follow-up target or close in the next correction** |
| `T118-R16` | **Medium** | No | Atomic thumbnail-cache write | The new partial path is unique per **process**, not per writer: `f"{target.name}.{os.getpid()}.partial"` (`thumbnails.py:170-179`). The application has separate queue and add-dialog `ThumbnailStore`s sharing one cache root, so two stores fetching the same URL in one process open and truncate the same temporary file. On POSIX one writer can rename that inode while the other still writes through its open handle, making the published target change after the supposedly atomic replace; the second replace then has no source. The cache is regenerable and a failed decode refetches, so this is a narrow robustness defect rather than user-data corruption. | Allocate a unique same-directory temporary with exclusive creation for every write, then replace; clean its own temporary on failure. A deterministic two-writer regression can coordinate the writes before either rename instead of racing wall-clock timing. | **Open, non-blocking; Implementer to file a follow-up target or close in the next correction** |

### Prior-finding resolution

| Prior finding | Result |
|---|---|
| `T118-R8` | **Resolved.** The row carries the literal selector without right-eliding it, and the selectable detail below the list follows the current row. The full value remains visible and copyable even where T118-R15's scaled-font row clipping occurs. |
| `T118-R10` | **Resolved.** One live editor remains the structural rule, viewport cost is flat in model size, and exact run `30853680183` exercised all nine correction tests on hosted `windows-latest`—the runner that observed the flap—and on STARBASE. A pass proves the 500-row paste stayed below 1.0 s but does not quantify the margin; that caveat is correctly preserved. |
| `T118-R12` | **Resolved.** Every editable row paints a native-style combo affordance and current value, one direct click opens the single live editor on an unselected row, and the paint/editor/click geometry shares one definition. The corrected differential paint test and shown-dialog click test exercise the missing behavior rather than only the editable model flag. |
| `T118-R13` | **Partly corrected, not resolved.** Sweep enumeration/deletion is off the GUI thread and `close()` no longer calls `waitForDone`. The ownership/destruction half remains open above. |
| `COORD-R18` | **Resolved.** The handoff names `890fb5d`, the last independently reviewed head, as the approval base and separately identifies `d4d05de..d1d9cbb` as a focused correction sub-range. No Critical correction is excluded from the requested verdict. |

### Review judgments

**T-121 is separate from T-118.** Exact run `30853680183` is red only because the phase-exit
fixture's localhost server aborted one hosted-Windows connection. Its own final state shows zero
jobs queued, four completed and one download failed; STARBASE passed the same test. Filing the
fixture and misleading assertion under T-121 is the correct scope boundary and does not erase the
Windows evidence for the nine T-118 tests.

**The selector's dedicated detail is enough to close R8.** REQ-009 promises that the effective
selector remains visible so a user can learn and copy it. The current-row label now supplies that
literal, selectable surface. R15 records that the additional at-a-glance row rendering is less
font-robust than its comments claim; it does not pretend the full value has disappeared from the
dialog again.

**Do not push `c7ac845` and `2514d30` yet.** They correctly record the CI verdict and roadmap as of
the submitted candidate, but the source verdict now needs another correction and those documents
will need to say so. Let them travel with the next source/handoff update rather than spending a CI
run on coordination text that is already stale.

### Independent verification

| Check | Result |
|---|---|
| Boundary and isolation | `890fb5d..d1d9cbb` and focused `d4d05de..d1d9cbb` inspected; both `git diff --check` clean. `d1d9cbb` is source/test plus the prior review/task record; `adc5355` is the pushed handoff; `c7ac845` and `2514d30` are local coordination-only commits. |
| Focused correction tests | `tests/ui/test_add_dialog.py tests/ui/test_row_delegate.py`: **75 passed in 36.65 s**. |
| Static and ledger gates | `ruff check .`: passed; `ruff format --check .`: **141 files** formatted; bare `mypy`: clean, **101 files**; bare `mypy --platform win32`: clean, **101 files**; task placement: **14 passed**. |
| Exact GitHub Actions | Run `30853680183`, SHA `adc53555f0c67d9239c2911cdef8f9a83de3dcd4`: Ubuntu, STARBASE desktop, both frozen jobs and STARBASE coverage succeeded. Hosted Windows ended **1 failed / 1967 passed / 21 skipped / 32 deselected** on T-121's phase-exit fixture; the nine T-118 correction tests passed. |
| Editor-reset probe | Open editor survived a model reset as an orphan; committing produced Qt's foreign-editor warning and made zero model `setData` calls. |
| Store-destruction probe | `close()` returned, but delivering `DeferredDelete` blocked **1.008 s** until the occupied pool was released, followed by two “Signal source has been deleted” errors from the queued store task. |
| Implementer evidence | Reported **1980 passed / 11 skipped / 2 deselected**, all static gates, and sixteen mutations across two rounds. The exact Windows run supplies the owed platform evidence but does not cover the two lifecycle probes above. |

### Final disposition

T-118 remains in review. Preserve the resolved visible-control, selectable-selector, scaling,
transient-staging and effective-request work. The next focused correction must close T118-R13's
actual QObject/pool lifetime and T118-R14's editor/reset ownership, with deterministic regressions
that reach destruction and another row's live refresh respectively. T118-R15 and T118-R16 are
non-blocking but need either correction in that batch or a named owner/target before approval.

No production source or tests were edited. This review record is the only reviewer change; nothing
was committed, pushed or changed in GitHub repository variables.

## 2026-08-03 — T-118 third delegate correction re-review

**Reviewer:** Codex (Reviewer)
**Approval base:** `890fb5d`
**Focused correction boundary:** `d1d9cbb..05e8b13`
**Implementation head:** `05e8b13`; `0ace824` is the handoff/plan-only head
**Overall verdict:** **Changes requested for T-118.** T118-R13, R15 and R16 are resolved. The
value-only half of T118-R14 is fixed, but its structural path assigns an open editor's choice to a
different URL when a preceding row leaves the list. That is a silent wrong-format result, so
T118-R14 remains open and is escalated from High to Critical.

### Finding

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T118-R14` | **Critical** | **Yes — T-118** | Structural model refresh / per-row request identity | `_shown` records the identities the view was told about, but none of the model's index mapping uses it: `rowCount()`, `data()` and `setData()` all read the already-mutated `dialog.rows` (`add_dialog.py:321-338`, `373-397`). `_refresh()` likewise asks `_current_row()` to interpret the old current index through the **new** visible tuple before calling `model.refresh()` (`:1174-1185`). Therefore “commit before reset while the index is valid” is not enough: the index is numerically valid but no longer names the same row. The deterministic user route starts with A/B/C, edits the text to B/C (starting the debounce), opens old row 1's editor for B and selects MP3, then lets `resolve()` reconcile. The new tuple is B/C before the structural refresh; committing the old index 1 writes MP3 into **C**, while B remains inherited. The reviewer regression reproduced exactly that. Pressing Add would durably queue the wrong per-URL request—the same silent wrong-format consequence that made T118-R6 Critical. The submitted test calls `_refresh()` with an unchanged row tuple, so it proves only the value-only branch and cannot reach this shift. | Keep model indices mapped through the old `_shown` snapshot until the reset: commit the editor against that snapshot's row identity, then swap to the new tuple and restore selection by the old identity if it survives. Make the commit path re-entrancy-safe, since `setData()` currently calls `dialog.refresh()` itself. Alternatively, commit before any structural staging mutation, but cover every reconcile/remove route. Preserve the existing sibling-value test and add the actual debounce regression above, asserting both surviving row objects and their durable requests so applying the choice to the following URL cannot pass. | **Open; prior finding not resolved, severity escalated** |

### Prior-finding resolution

| Finding | Result |
|---|---|
| `T118-R13` | **Resolved.** The pool is module-level and parentless, so deleting a store no longer runs a pool destructor on the GUI thread. Runnables retain and emit only through a parentless `_Sink`; none touches the store, and Qt disconnects the dead receiver. The blocked-task deletion regression passes. A separate reviewer probe also deleted the C++ store and dropped the last store-wrapper reference while work was queued: the sink remained alive through the task, was released afterward, and no worker exception or GUI wait occurred. Exact-head Windows evidence remains appropriately unclaimed. |
| `T118-R14` | **Partly corrected, not resolved.** A value-only refresh now emits `dataChanged`, leaves the editor open and carries its eventual choice into the durable request. Structural mutation before refresh still changes what that editor's index names, as recorded above. |
| `T118-R15` | **Resolved.** The contract is now honest: uniform rows show only `SELECTOR_LINES`, while the wrapping, selectable current-row detail is the guaranteed complete selector. The 18 pt regression first proves the row cannot fit the value, then proves the dedicated surface retains it. |
| `T118-R16` | **Resolved.** Every cache write gets an exclusively created same-directory temporary from `mkstemp`, closes it before `replace`, and removes its own temporary on a failed write. The two stores no longer share a PID-derived partial pathname. The handoff correctly continues to label the atomic race as not dynamically verified. |

### Review judgments

**Do not spend the Windows run on this head.** The thumbnail ownership change is exactly the part
that ultimately needs Windows evidence, but the same candidate still has a platform-neutral
Critical wrong-request defect. Push and run only after R14's structural identity path is corrected;
then one run measures the implementation that could actually be approved.

**The external roadmap artifact was not reviewable from this environment.** The linked Claude
artifact rejected automated access. `ai/IMPLEMENTATION_PLAN.md` is the canonical roadmap under
`AGENTS.md` §5 and was inspected locally; it honestly says the third correction awaits re-review
and will need another current-truth update for this verdict.

### Independent verification

| Check | Result |
|---|---|
| Boundary and tree | `d1d9cbb..05e8b13` source/test correction and `05e8b13..0ace824` handoff/plan update inspected; all diff checks clean. Before this review record, `HEAD == 0ace824`, `origin/main == adc5355`, four local commits ahead, working tree clean. |
| Focused submitted tests | `tests/ui/test_add_dialog.py tests/ui/test_row_delegate.py`: **78 passed in 38.71 s**. The five named R13/R14/R15 tests also pass independently. |
| Static and ledger gates | `ruff check .`: passed; `ruff format --check .`: **142 files** formatted; all four mypy scopes passed sequentially with `--no-incremental`—host and win32, **43 src files** and **101 unscoped files**; task placement: **14 passed**. |
| Reviewer structural regression | **Failed as expected.** With visible A/B/C changed to B/C during an open editor on B, C received the MP3 preset and B remained unchanged. The same failure reproduced through the real `type_urls()` → debounce/`resolve()` route, not only by calling `remove_row()`. The temporary probe was removed after recording the result. |
| Store-wrapper lifetime probe | Passed: delete the store, drop its Python wrapper, release a queued task, process completion; the parentless sink stayed alive until completion and was then collected without a worker exception. The temporary probe was removed. |
| Implementer evidence | Reported **1983 passed / 11 skipped / 2 deselected**, all static gates, and nineteen mutations across three rounds. No Windows run exists for `05e8b13`, accurately disclosed. |

### Final disposition

T-118 remains in review on T118-R14 alone. Preserve the resolved shared-pool/sink ownership,
complete-selector surface, unique atomic temporary, visible control and all earlier corrections.
The next focused correction needs one identity model for both value and structural changes: an
editor and current selection must keep naming the same `Row` while the visible tuple changes.

Do not push `c7ac845`, `2514d30`, `05e8b13` or `0ace824`, and do not spend the Windows run yet. No
production source or submitted tests were edited; this review record is the only lasting reviewer
change. Nothing was committed, pushed or changed in GitHub repository variables.

## 2026-08-03 — T-118 fourth delegate correction re-review

**Reviewer:** Codex (Reviewer)
**Approval base:** `890fb5d`
**Focused correction boundary:** `05e8b13..c724770`
**Candidate head:** `53b07ec`; `c724770` is the implementation head
**Overall verdict:** **Blocked pending exact-head Windows verification.** `T118-R14` is resolved:
the model now keeps every index mapped through the tuple the view was told about until the reset,
commits the open editor against that tuple, and restores the current row by identity. No source
correction remains open. The last two correction rounds have not run on Windows, so the candidate
is ready to push and spend the hosted Ubuntu/Windows run, but is not yet approved.

### Prior-finding resolution

| Finding | Result |
|---|---|
| `T118-R14` | **Resolved.** `rowCount`, `data`, `setData` and the dialog's current-row lookup all resolve through `StagingModel._shown`. On a structural refresh, the editor commits before `_shown` is replaced; its `setData` callback re-enters `dialog.refresh()`, where the real `_refreshing` guard returns and lets the outer refresh finish one reset. The exact shown-dialog A/B/C → B/C regression keeps old index 1 bound to B at `modelAboutToBeReset`, restores B at its new position, leaves C inherited, and durably queues B as audio and C as video. The focused test and the complete add-dialog/delegate surface pass independently. |

### Non-blocking findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `COORD-R19` | **Low** | No | Current-truth status | `TASKS.md`'s T-118 status headline still says “three rounds … and three corrections,” immediately before its fourth-round correction. STATUS, the plan and the handoff say four. | Change the headline to four rounds/four corrections in the next coordination update, before the Phase 2 exit review. | **Open, non-blocking; Documentation Maintainer** |
| `COORD-R20` | **Low** | No | Review boundary hygiene | `c724770` is presented and titled as the implementation correction, but it also stages the complete prior Codex review record into `ai/REVIEWS.md`. The text is the reviewer's unchanged record and the approval boundary remains recoverable, so this does not invalidate the source review; it is another mixed-boundary commit of the class already recorded this session. | Keep the current published/local history intact. On the next round, commit an outstanding reviewer record separately before staging implementation files, and name both SHAs in the handoff. | **Open, non-blocking process follow-up** |

### Independent verification

| Check | Result |
|---|---|
| Boundary and implementation | `05e8b13..c724770` inspected. `_shown` is initialized before the first refresh, `Row` is identity-valued (`eq=False`), every index-to-row consumer uses the model snapshot, and production calls `StagingModel.refresh()` through the guarded dialog refresh. `git diff --check` passed. |
| Exact regression | `test_a_choice_made_during_the_debounce_lands_on_the_row_it_was_made_for` passed on the real shown-dialog debounce route. The preserved sibling-editor regression passed in the same focused run: **2 passed**. |
| Focused UI surface | `tests/ui/test_add_dialog.py tests/ui/test_row_delegate.py`: **79 passed in 40.25 s**. |
| Static gates | `ruff check .`: passed; `ruff format --check .`: **143 files** formatted; `mypy --no-incremental src`: **43 files** passed; bare host and `--platform win32` mypy: **101 files each** passed. The mypy scopes were run sequentially. |
| Implementer evidence | Reported full suite **1984 passed / 11 skipped / 2 deselected** and twenty-five mutations across four rounds. No exact-head Windows evidence is claimed. |

### Final disposition

Push the six candidate commits through `53b07ec` and spend the normal hosted Ubuntu/Windows run.
For this review, the useful Windows evidence is execution of the four tests introduced after
`adc5355`—the two add-dialog editor tests, scaled-selector test and store-deletion ownership test—
plus the existing T-118 correction surface. The known T-121 phase-exit failure may keep the full
Windows job red; report the per-test breakdown rather than treating that unrelated expected red as
a T-118 failure. If those T-118 tests pass on the exact candidate and no new relevant failure
appears, T-118 can be approved without another source pass.

This review record is uncommitted. No source, submitted test, repository variable, remote ref or CI
state was changed by the reviewer.

### Exact-head verification and final verdict

**Verified run:** GitHub Actions `30859578131`, SHA
`53b07ec9b36656664672912af36c653b094a6873`.

**Final verdict:** **Approved with follow-ups at `53b07ec`.** Hosted Windows and the real STARBASE
desktop both executed the corrected T-118 surface. STARBASE passed the full suite; the hosted job
finished **1 failed / 1971 passed / 21 skipped / 32 deselected**, with every T-118 correction test
passing except the independent paste-scaling ratio oracle described below. Ubuntu, both frozen
jobs and STARBASE coverage passed. The required exact-head Windows evidence is therefore present,
and no production or T118-R14 blocker remains.

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T118-R17` | **Medium** | No — follow-up `T-122` | Paste-scaling CI oracle | `test_a_four_times_larger_paste_does_not_cost_four_times_more_than_linearly` claims two nearby measurements cancel runner speed, but one sample per size cannot cancel a transient scheduler/host stall. Hosted Windows measured 125 rows at 0.0321 s and 500 at 1.4935 s, producing 46.5x; in the same job, the separate 500-row absolute-budget test passed below 1.0 s, and STARBASE passed both. The ratio test also did not kill restoration of the widget-per-row design in the earlier mutation battery; the structural control-count test did. Thus this failure neither disproves the accepted 500-row interaction bound nor detects the design property on which approval depends. | Remove the ratio as a required gate and retain the 500-row absolute budget plus structural control count. If scaling remains useful as diagnostic evidence, report it as a benchmark, or use repeated/interleaved samples with a robust estimator and separately prove that a single outlier cannot fail the suite while a sustained regression can. Delete the claim that a ratio is runner-invariant. | **Open, non-blocking; Implementer, `T-122`, before the Phase 2 exit review** |
| `COORD-R21` | **Low** | No | Exact-run current truth | Local docs commit `a610250` correctly records that T-121 did not recur and that the hosted job is red on the T-118 ratio gate, but `IMPLEMENTATION_PLAN.md` immediately continues with “What is red is T-121”; STATUS repeats “What is red on main now is T-121,” and T-121's task entry still calls itself the only red item. | Keep T-121 Proposed because its captured fixture defect remains real, but distinguish “did not recur” from “resolved” and say the exact current red belongs to T-122's ratio oracle. Apply the same wording to the external roadmap artifact. | **Open, non-blocking; Documentation Maintainer, next coordination commit** |

`COORD-R19` is closed in local docs commit `a610250`: the T-118 status headline now says four
rounds/four corrections. `COORD-R20` remains a non-blocking process follow-up. The docs-only commit
is outside the approved implementation head and does not alter this verdict.

The reviewer independently queried the Actions run and failed-job log. The run SHA and all six job
conclusions match the handoff; the hosted failure log contains only the ratio assertion above.
This addendum and the `T-122` filing are uncommitted. No source, submitted test, repository
variable, remote ref or CI state was changed by the reviewer.

## 2026-08-03 — Phase 2 exit review

**Reviewer:** Codex (Reviewer)
**Approval base:** `dca3bfa`
**Submitted implementation head:** `5eb2611`
**Handoff-only head:** `f8f8638`
**Overall verdict:** **Changes requested — Phase 2 has not exited.** The cold reconstruction finds
criteria 1 and 5 unproved by the tests named for them, the `T-122` correction is not yet a sound
timing gate, and the CI rewrite changes an accepted operations decision without a maintainer
ruling. Criteria 2, 3, 4 and 7 are met. Criterion 6 is not met while the findings below remain.

### Cold criteria reconstruction

| # | Verdict | Independent reading |
|---|---|---|
| 1 | **Not met — `P2EXIT-R2`.** | The real-worker/file and per-row progress evidence is substantive. The only named responsiveness gate, however, also passes when none of its three jobs is started. It therefore does not establish “interactive throughout while three downloads run.” |
| 2 | **Met.** | The phase test hard-kills a real composed application with in-flight and never-started jobs, starts a new composed application against the killed database, distinguishes the recovered states, and observes the recovery offer. |
| 3 | **Met.** | The phase test samples both durable in-flight rows and actual worker processes against a non-default limit over the whole run. Approved lowering and pause tests cover draining without over-admission. |
| 4 | **Met.** | A second real launch refuses while the first owns the guard and a full pool; the Windows acquisition, racing-start and killed-holder cases have prior hosted-Windows evidence. No source governing this behavior changed after that evidence. |
| 5 | **Not met — `P2EXIT-R1`.** | The N-worker phase test kills the same captured process tree whose survivors it later inspects. It passes with the product's parent-death watchdog removed, so it proves the test helper can reap workers, not that application exit leaves none. |
| 6 | **Not met.** | This independent phase review requests changes. All thirteen deliverables do have prior reviewer verdicts, subject to the boundary corrections in `P2EXIT-R5`; deliverable approval alone is not phase sign-off. |
| 7 | **Met.** | The Add-only gate admits every durable job without priming `start()`, drains beyond the pool limit, and is complemented by restart and paused-queue routes. |

### Blocking findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `P2EXIT-R1` | **Medium** | **Yes** | Criterion 5 / orphan-worker gate | `test_no_worker_outlives_a_hard_kill_with_a_full_pool` obtains `workers`, then builds `doomed` from the application's complete tree and passes that tree to `kill_the_application`. On POSIX the helper kills the process group; on Windows it kills every captured process. The later assertion asks whether the same workers are alive. A reviewer mutation deleting `_exit_when_the_parent_does()` from `worker.prepare_this_worker()` left this phase test green: **1 passed in 9.52 s**. The gate therefore survives removal of the mechanism its docstring says it proves and cannot discharge the “no worker outlives application exit” criterion at N=3. | Capture the worker set independently, kill only the actual application process (not its launcher and not its process tree/group), and assert the captured workers exit through their own parent watchdog. Put full-tree cleanup only in `finally`, after the behavioral assertion, so a failed gate still cleans up. Execute this corrected route on Linux and Windows. | **Open; Implementer** |
| `P2EXIT-R2` | **Medium** | **Yes** | Criterion 1 / responsiveness gate | `test_the_interface_stays_inside_its_budget_while_three_downloads_run` records only the worst `processEvents()` duration. It never requires a job to enter an active state, emit progress, or finish; after its 60-second deadline it asserts only the latency. A reviewer mutation deleting all three `manager.start(job_id)` calls still passed: **1 passed in 60.24 s**. An idle GUI therefore satisfies the test whose name and criterion require three concurrent downloads. | Give the measurement a positive control: hold three workers at a barrier, require all three active and independently producing/queued to produce progress before sampling, measure while that state holds, release them, and require all three to settle. It should fail promptly rather than wait 60 seconds when concurrency was never reached. | **Open; Implementer** |
| `P2EXIT-R3` | **Medium** | **Yes** | `T-122` / timing-gate correction | Repeating the ratio did not make its live samples comparable. Every `cost()` creates another manager and dialog backed by `child_never_returning`; the fixture shuts them down only after the test. Warm-up plus three small/large pairs can therefore leave seven managers and up to 28 probe workers alive, and every large sample follows its small sample under monotonically increasing background load. A median cannot remove load introduced systematically by the harness. The sample-count contract is also unguarded: changing `SCALING_PAIRS` from 3 to 1 left both the deterministic oracle test and the live gate green (**2 passed**), because the oracle supplies its own three-element lists. `T-122` was explicitly required before this exit review and remains “awaiting review,” so it is not clean evidence yet. | Prefer the original review recommendation: keep the absolute 500-row budget and structural control count as required gates, and make the relative ratio diagnostic. If the ratio remains required, shut down and reap each sample outside the timed region, alternate which size runs first, reject insufficient or unequal sample sets in `superlinear_growth`, and pin the live sample count independently. | **Open; Implementer** |
| `P2EXIT-R4` | **High** | **Yes** | CI policy / accepted `OPS-009` | Accepted `OPS-009` says the full `windows-latest` suite stays hosted and `WINDOWS_RUNNER` is a fallback that routes it to STARBASE when hosted minutes run out. The new workflow goes further without a later accepted decision: while the variable is set it deletes the Windows matrix leg, and it removes the full Windows desktop suite from ordinary pushes unless the commit says `[win]`. That is a durable coverage-policy change made below the authority of an accepted decision. Its “nightly backstop” is not guaranteed either: global `cancel-in-progress: true` lets an ordinary push cancel the scheduled Windows run, while the replacement push can skip the full Windows suite. | Obtain an explicit maintainer ruling and amend/supersede `OPS-009`, or restore the accepted policy. The ruling should state whether clean hosted-Windows evidence and every-push full Windows coverage are being surrendered, and make the nightly guarantee true (for example, do not let an ordinary push cancel a scheduled full-Windows run). Then align the workflow and canonical testing contract to that ruling. | **Open; Maintainer ruling, then Implementer** |
| `P2EXIT-R5` | **Medium** | **Yes** | Exit record / current truth | The records being signed off still contradict current evidence. `IMPLEMENTATION_PLAN.md` says the Blocked list “wants re-reading” and `STATUS.md` says nobody re-read it, although `5eb2611` records the completed re-triage. `TESTING.md` opens §10 with “Runs on every push and pull request, on Linux and Windows matrix runners,” then says ordinary pushes omit the full Windows suite. The deliverable and criterion tables also call `75f1c32` and `233c5fd` the T-084/T-086 approval heads; the reviewer record approved both only at `2a41c5f`, after later corrections. These are current-truth documents and approval boundaries, not harmless historical wording. | Reconcile the live plan, status and testing contract after the `P2EXIT-R4` ruling. Record T-084 and T-086's reviewer-approved head as `2a41c5f` (implementation commits can be named separately), and remove the already-discharged Blocked-list warning. | **Open; Planner / Documentation Maintainer** |

### Non-blocking findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `P2EXIT-R6` | **Low** | No | `T-121` diagnostic | `describe_drain_failure()` correctly stops blaming admission when no row remains queued, but it then directs every such failure to the clip server. Its input contains only final statuses; it cannot know whether a failed/cancelled download came from the observed `ConnectionAbortedError`, another worker failure, or test teardown. The new wording replaces one unjustified causal claim with a narrower but still unjustified one. | Report only what the statuses establish—admission drained and one or more jobs failed—then direct the reader to captured stderr for the cause. Name the clip-server abort only when the test observed it. | **Open, non-blocking; fold into Proposed `T-121`** |
| `P2EXIT-R7` | **Low** | No | Handoff boundary | The handoff says `origin/main` is `53b07ec`, but the reviewed checkout has `origin/main` at `dca3bfa`; it also labels `5eb2611` as the head while `f8f8638` is the handoff-only head. The implementation boundary remains recoverable and no code is hidden, so this does not affect the substantive findings. | In the correction handoff, report both implementation head and handoff head and resolve the remote immediately before writing the boundary. | **Open, non-blocking process follow-up** |

### Independent verification

| Check | Result |
|---|---|
| Submitted boundary | `dca3bfa..5eb2611` and handoff commit `f8f8638` inspected; working tree was clean before and after reviewer mutation probes. No product source changed in this boundary. |
| Cold phase suite | `tests/integration/test_phase_2_exit.py`: **13 passed in 47.57 s**. Passing the suite does not resolve `P2EXIT-R1` because the watchdog-removal mutation also passed. |
| Supporting criterion surface | Focused progress, composition, lowering, pause, graceful-shutdown, parent-kill and grandchild tests: **13 passed in 14.10 s**. Changed T-083/T-121/T-122/task-placement tests: **18 passed in 3.57 s**. |
| Static gates | `ruff check .` passed; `ruff format --check .`: **144 files**; `mypy --no-incremental src`: **43 files**; bare host and bare `--platform win32` mypy: **101 files each**. |
| Reviewer mutation: criterion 5 | Removed the worker parent-watchdog call. The named N-worker phase test still passed. Mutation reverted; tree verified clean. |
| Reviewer mutation: criterion 1 | Removed every `manager.start()` from the named responsiveness test. The idle 60-second loop still passed. Mutation reverted; tree verified clean. |
| Reviewer mutation: T-122 | Reduced live timing pairs from three to one. The synthetic oracle test and live timing test both passed. Mutation reverted; tree verified clean. |
| Windows evidence | The last full Windows product evidence remains run `30859578131` at `53b07ec`. Production source has not changed since it. An exact-head Windows run now would not repair the platform-neutral gate defects above; the corrected criterion-5 route itself needs exact Linux and Windows execution before exit. |

### Final disposition

Do **not** spend a Windows run on `f8f8638`. First correct `P2EXIT-R1`, `P2EXIT-R2` and
`P2EXIT-R3`, obtain the `P2EXIT-R4` maintainer ruling, and reconcile `P2EXIT-R5`. Then push the
correction head with `[win]` or dispatch the workflow against that exact head. The useful final
evidence is the corrected N-worker parent-watchdog test on both Windows and Linux, the
positive-controlled three-download responsiveness measurement, the selected T-122 policy, and a
workflow whose observed jobs match the newly accepted policy.

No source, submitted test, repository variable, remote ref or CI state was changed by the
reviewer. The three temporary mutations above were reverted and the working tree was clean before
this review record was appended.

## 2026-08-04 — Indexed Phase 2 / UX-005 review

**Reviewer:** Codex (Reviewer)
**Index handoff:** `d2ff1a9` (`ai/handoffs/2026-08-04-review-index.md`)
**Prior Phase 2 exit submission:** `5eb2611`
**Reviewed implementation head:** `47299aa`
**Last CI-backed coordination head:** `8d1b01c`
**Checkout while recording:** `b7d0200` — later commits are coordination-only
**Overall verdict:** **Changes requested for `T-122` and UX-005 (`T-124`/`T-125`/`T-126`).
`T-127` is approved with one non-blocking follow-up, and `DAT-005` is approved. Phase 2 is
blocked pending those corrections and a maintainer reconsideration of `OPS-007`.**

The review followed the index order. Findings are grouped by the item whose verdict they control;
`UX-005` was submitted and requested as one review.

### `T-127` — Approved with follow-up

`P2EXIT-R1` and `P2EXIT-R2` are **Resolved**. The N-worker orphan gate captures the workers
independently, kills exactly the application PID, bounds observation below the clip's own lifetime,
and cleans the tree only afterwards. The responsiveness gate proves three reservations, requires
all three jobs `RUNNING` together, observes per-job progress inside the measured window, and
requires all three to finish after release.

The reviewer's original mutations now fail for the stated reasons: removing
`_exit_when_the_parent_does()` leaves all three workers alive past the five-second grace; removing
the three `start()` calls fails in 0.54 seconds. The unmutated pair passed locally, and the exact
implementation subsequently ran in the green `8d1b01c` Windows desktop job.

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T127-R1` | **Medium** | No | Process-test cleanup | `reap_the_captured_tree()` catches every `psutil.Error` while killing, excludes the direct `Popen` child from `wait_procs`, suppresses `TimeoutExpired` from `process.wait()`, and returns only survivors from the remaining list. A refused kill or stuck launcher can leak while `assert not leaked` passes. This occurs after the behavioral assertion and does not weaken the watchdog proof. | Tolerate only normal `NoSuchProcess`/`ProcessLookupError` races, make wait timeouts visible, and include every survivor without replacing an earlier behavioral failure. | **Open, non-blocking; process-test hardening follow-up** |

### `T-122` — Changes requested

The core correction is sound: relative scaling is no longer asserted; the 500-row absolute budget
and structural one-editor bound remain required; and `superlinear_growth()` refuses thin or
unequal samples. `P2EXIT-R3`'s defective required ratio gate is therefore **Resolved**.

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T122-R1` | **Medium** | **Yes — T-122** | Required current-truth correction | The task requires removal of prose claiming a ratio is runner-invariant. `tests/ui/test_add_dialog.py:121-123` still calls the ratio the “finer claim” and says it “does not move with runner speed at all,” immediately before the later comment correctly explains the opposite. This is the exact false claim T-122 exists to retire. | Remove or rewrite the stale sentence so the module has one current rule: this ratio is diagnostic and transient load can move it. | **Open** |
| `T122-R2` | **Low** | No | Diagnostic isolation | `cost()` says every manager is “reaped inside the sample loop,” but `DownloadManager.shutdown()` explicitly begins asynchronous teardown and returns. Managers are pumped to idle only at fixture teardown, so later samples can overlap earlier probe workers. This no longer weakens a gate because the result is printed only. | Wait outside the timed region until each manager is idle, or describe this as a coarse non-isolated diagnostic. | **Open, non-blocking** |

### `UX-005`, `T-124`, `T-125`, `T-126` — Changes requested

The two-tab/no-splitter structure, state-to-verb table, shared rendering, file-action containment,
history confirmation and status-bar file guarantee are present. These findings block the grouped
UX verdict:

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T126-R1` | **Critical** | **Yes — T-126 / UX-005** | Open editor across queue reset | Queue rows reuse the delegate editor but not T118-R14's reset lifecycle. `QueueModel.refresh()` fully resets on remove/reorder/clear, while QueueView never commits the open editor first or restores identity. In a shown reviewer probe, choosing MP3 for job B and emitting `queue_reordered` produced no `preset_chosen` request (`asked == []`). The visible choice is silently discarded, so the download can run the old format. Existing coverage calls `model.setData()` directly and cannot see this route. | Commit the delegate editor before every structural reset while its index still names the shown job, then restore by identity. Add a shown-view reorder/remove regression asserted through the durable request. | **Open** |
| `T125-R1` | **High** | **Yes — T-125 / UX-005** | History deletion transaction | `HistoryRepository.remove()` executes `DELETE` without a transaction context or commit. Unit tests read through that same connection and see the uncommitted deletion. Production reports success, refreshes through a separate read connection where the row still exists, and later closes the writer connection, rolling the deletion back. A reviewer probe reported `removed 1`, `same_connection_has_row False`, `other_connection_has_row True`, and `after_writer_close_has_row True`. | Commit atomically like the other repository writes. Test through the real writer/read connection boundary and after writer shutdown/reopen. | **Open** |
| `T124-R1` | **High** | **Yes — T-124 / T-125** | Keyboard and overflow | UX-005 declares `⋯` as the no-pointer route. `RowDelegate.editorEvent()` handles only left-button mouse events; neither list installs a keyboard/context-menu route. Queue tests invoke `_show_row_menu()` directly. Pressing the Menu key in a shown reviewer probe produced no `rowVerbsMenu`. History is worse: its drawn `⋯` emits `verb=None`, which `HistoryView._on_verb()` ignores, so that visible control does nothing even with a pointer. History removal consequently has no keyboard route. | Give both lists a real focused-row keyboard/context-menu activation through the pointer action path. Drive the actual key in shown-view tests, including History removal selection. | **Open** |
| `T124-R2` | **High** | **Yes — T-124** | Live tab counts | MainWindow refreshes labels only from explicit shell refresh helpers. QueueModel also resets itself on `job_removed`, `queue_reordered` and `queue_cleared`, but `modelReset` is not connected to `_refresh_tab_labels()`. A probe removed one backing job and emitted `job_removed`: the model fell to one row while the tab stayed `Queue (2)`. The committed test calls `window.refresh_queue()` directly. | Refresh labels from each model's structural-change signal and test manager-driven remove/clear. | **Open** |
| `T126-R2` | **High** | **Yes — T-126 / UX-005** | Format after admission | UX-005 §6 and T-126 require a control before start and plain format text afterwards. QueueModel answers `PRESET_ROLE` and `PRESET_CHOICES_ROLE` but never `SELECTOR_ROLE`; after a job leaves `RETARGETABLE`, the control disappears and no format text is drawn. The status matrix checks choices only. | Supply effective format/selector text after the retarget window closes, including custom selectors, and assert it against the durable request. | **Open** |
| `T124-R3` | **High** | **Yes — T-124 / UX-005** | Rejected toolbar design remains | UX-005 chooses row verbs “rather than a toolbar acting on a selection,” because two tabs make that toolbar guess its target. MainWindow still creates selection-based **Remove**, **Move up**, and **Move down** actions tied to the hidden queue selection even while History is frontmost. The chosen row route was added without removing the rejected route. | Keep queue-wide Pause and Clear-finished, but remove the per-row toolbar actions or obtain an explicit amendment retaining them. | **Open** |
| `T124-R4` | **High** | **Yes — T-124 / UX-005** | Accepted row anatomy | UX-005 §3 requires thumbnail, title, uploader and duration, progress and state. `Job` persists title and thumbnail URL but has no uploader or duration, so QueueModel cannot render them. T-124's task text weakens this to the older REQ-014 fields, but a task cannot narrow an accepted decision. | Carry probed uploader/duration into the durable row and render them, or amend UX-005 if §3 was intended as visual anatomy rather than named data. Test after the add dialog closes. | **Open** |

`DAT-005` itself is **Approved**. Selected-record scope, permanent and confirmation-time file
guarantees, irreversible counted confirmation, refusal to touch files, and the REQ-020 amendment
form one coherent decision preserving UX-001. `T125-R1` is an implementation failure, not a defect
in that decision.

### Phase 2 exit re-review — Blocked

| # | Verdict | Independent reading |
|---|---|---|
| 1 | **Met, subject to T-127's approved gate.** | Three workers overlap; each advances progress inside the measured responsive window; all complete after release. The start-removal mutation fails promptly. |
| 2 | **Met.** | A real composed application restarts against the killed database, preserves never-started rows, recovers in-flight rows and shows the offer. |
| 3 | **Met.** | Real worker and durable-state counts stay within the limit, with approved lowering/pause evidence. |
| 4 | **Met.** | The single-instance route retains its approved Linux/Windows evidence. |
| 5 | **Behavior met by T-127; table evidence stale.** | The corrected test kills one application PID and fails without the watchdog. It passed on Linux and Windows desktop at `8d1b01c`; the plan still cites the old vacuous gate's run. |
| 6 | **Not met.** | This review requests changes for the sequenced UX batch and T-122, and the crash-class risk needs the maintainer ruling below. |
| 7 | **Met.** | Add-only admission, restart and paused-queue routes remain substantive and approved. |

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `P2EXIT-R8` | **Medium** | **Yes** | Criterion-5 current truth | The exit table still cites hosted-Windows run `30712201443`, which predates T-127 and exercised the gate proven to pass with the watchdog removed. Correct Windows evidence exists at `8d1b01c`, while the T-127 task still says Windows is pending. | Cite the corrected Linux and Windows executions and remove the stale pending sentence. Keep behavioral evidence distinct from generic “all phase tests passed.” | **Open; Documentation Maintainer** |
| `P2EXIT-R9` | **Medium** | **Yes — maintainer decision** | `OPS-007` / result-pump crash | `OPS-007` accepted T-074 because 361 attempts produced no recurrence and explicitly said recurrence reopens the decision. T-128 now records 2 Linux SIGSEGVs in 39 serial full-suite runs, both at the same completed-test position with a live `ResultPump`. T-128 correctly preserves uncertainty about identity and product versus harness, but that uncertainty does not preserve the zero-event premise. | Reconsider `OPS-007` explicitly: re-accept the measured risk, require T-128 diagnosis before exit, or classify the reproduction separately once evidence supports it. The reviewer cannot silently reuse the old premise. | **Open; Maintainer** |

`P2EXIT-R4` is **Resolved** by accepted `OPS-010`: Windows desktop runs on every push, the duplicate
matrix leg is conditionally absent when it would use the same runner, and scheduled runs have a
separate non-cancelling concurrency policy. P2EXIT-R5's broader reconciliation is resolved except
for P2EXIT-R8.

`T-123` and `T-128` are correctly separate. The xdist measurement found its predicted
process-contention hazard and should not be adopted until that class is serialized. The Linux
segfault resembles T-074 but does not establish identity; a separate task preserves uncertainty.

### Independent verification

| Check | Result |
|---|---|
| Boundary | Reviewed `5eb2611..47299aa`, both detailed handoffs, the index at `d2ff1a9`, and coordination through `8d1b01c`. Later commits through `b7d0200` alter coordination only. `git diff --check 5eb2611..47299aa` passed. |
| T-127 unmutated | Orphan-worker and responsiveness gates: **2 passed in 6.12 s**. |
| T-127 mutations | Removing the watchdog failed with **3/3 workers alive**; removing all starts failed in **0.54 s**. Mutations were restored and the tree verified clean. |
| Submitted focused UI | Existing row-verbs, wiring, history, queue, main-window and T-122-focused tests: **75 passed / 123 deselected in 7.93 s**. They bypass the missing user routes above. |
| UX probes | Shown F2 route: no editor. Shown Menu-key route: no menu. Manager-driven removal: one model row while tab stayed `Queue (2)`. Open job-B editor plus reorder/reset: no retarget request. Temporary probes were removed. |
| T-125 probe | Same connection saw deletion; a second connection and reopen both retained the row. Exact booleans: `False`, `True`, `True` for row present on same, other, reopened connections. |
| CI | `8d1b01c` is green on all five jobs, including Windows desktop, and contains source head `47299aa`. Green CI does not exercise these keyboard/reset and cross-connection routes. |

### Final disposition

Approve `T-127` with T127-R1 as a non-blocking follow-up and approve `DAT-005`. Correct T122-R1
before completing T-122; T122-R2 may remain a follow-up. `T-124`, `T-125` and `T-126` need one
correction batch, with the Critical editor/reset path independently mutation-checked and history
deletion tested across the real writer/read boundary.

Phase 2 remains blocked until that UX correction is approved, T-122's required prose is reconciled,
P2EXIT-R8 cites corrected platform evidence, and the maintainer answers the reopened `OPS-007`
premise. No reviewed source, submitted test, workflow, decision, task state, remote ref or CI state
was changed. This review record is the only reviewer edit; nothing was committed or pushed.

## 2026-08-04 — Indexed Phase 2 / UX-005 correction re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `b7d0200`
**Submitted state:** bounded uncommitted diff over that base; no implementation commit or Windows
run yet
**Overall verdict:** **Changes requested.** Nine original corrections are sound, the maintainer's
`OPS-007` ruling is coherent, and `T122-R1`, `T124-R1`–`R4`, `T125-R1`, `T126-R2`, `T127-R1`
and `P2EXIT-R8` are resolved. The `T126-R1` correction introduces a new Critical refresh loop.
`T122-R2` also retains one non-blocking timeout hole. Phase 2 remains blocked by this correction,
the accepted `T-128` prerequisite, and the absent Windows execution of the final correction head.

### Blocking finding

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T126-R3` | **Critical** | **Yes — T-126 / UX-005** | Editor restore / retarget success refresh | `QueueView` commits the editor on every reset and reopens it afterwards. If the retarget write becomes visible before the reorder reset rereads the queue, the reopened editor already contains the new preset. `retarget()` then runs its success-side `refresh_queue`; that reset commits the redisplayed, unchanged value as another user choice. `DownloadManager` recognizes `UNCHANGED` and calls the same success callback synchronously, forming `refresh → commit → retarget(UNCHANGED) → refresh` until `RecursionError`. The submitted regression replaces `retarget()` with a list append and never updates its reader, so the reopened editor contains the inherited value and cannot enter this path despite describing its assertion as durable. A deterministic reviewer regression updates the backing reader before invoking the success refresh and receives the same MP3 request twice; an uncapped composed probe reached `RecursionError` inside the Qt event loop. | Distinguish a user edit from lifecycle commit of an unchanged editor. Viable shapes include making the model refuse `setData` when the selected preset already describes the durable request, or suppressing the success refresh's lifecycle commit without losing a real in-progress choice. Preserve commit-before-reset and reopen-by-id, then make the reviewer regression pass and add a real composed/durable route that cannot recurse. | **Open** |

The deterministic regression is
`test_a_fast_retarget_does_not_turn_the_success_refresh_into_a_loop` in
`tests/ui/test_row_verb_wiring.py`. It is intentionally red on the submitted implementation:

```text
asked = [('job-b', 'bestaudio/best'), ('job-b', 'bestaudio/best')]
```

### Non-blocking residual

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T122-R2` | **Low** | No | Diagnostic isolation | `cost()` now pumps each manager outside the timed region, which fixes the ordinary overlap. But the 30-second deadline falls through without asserting `manager.is_idle`; a stuck teardown therefore resumes sampling under the old manager after exactly 30 seconds and prints a contaminated diagnostic as though isolation succeeded. | Assert idle after the bounded wait, or fail with a diagnostic naming the manager that did not settle. | **Open, non-blocking residual** |

### Corrections accepted on source review

- **`T127-R1` is Resolved.** Only real disappearance races are ignored while killing; refused
  kills and a direct-child wait timeout enter the returned survivor set. The exact orphan-worker
  phase gate passed locally.
- **`T122-R1` is Resolved.** The stale runner-invariance claim is gone. The ratio is consistently
  described as diagnostic and the absolute 500-row budget remains the gate.
- **`T124-R1`–`R4` are Resolved.** Both lists own one context-menu route with current-row fallback;
  History's drawn overflow reaches the shell; FileActions no longer installs a competing menu;
  tab labels follow model resets; selection-scoped toolbar verbs are gone; and migration 0003
  carries uploader plus fractional duration from the probe into the durable queue row and its
  accessible text.
- **`T125-R1` is Resolved.** History deletion now owns a transaction, and the regression observes
  it through another connection and after the writer connection closes.
- **`T126-R2` is Resolved.** Once retargeting is no longer legal, the row derives plain effective
  format text from the durable request and the delegate no longer drops the progress bar merely
  because that text is present.
- **`P2EXIT-R8` is Resolved.** Criterion 5 now cites the corrected N-worker watchdog gate at
  `8d1b01c`, not the earlier vacuous run.
- **`P2EXIT-R9` has the required maintainer ruling.** The `OPS-007` amendment does not claim that
  T-074 and T-128 are identical; it correctly says the zero-recurrence premise fired and makes
  T-128 diagnosis a Phase 2 exit prerequisite.

### Independent verification

| Check | Result |
|---|---|
| Boundary and whitespace | Inspected the complete uncommitted diff over `b7d0200`; `git diff --check b7d0200` passed. |
| Submitted focused set | Queue/history/UI, model, persistence, composition and non-network end-to-end selection: **325 passed / 1 skipped** before ten localhost-server cases were denied by this sandbox (`PermissionError` at socket creation, not product assertions). |
| T-127 exact gate | `test_no_worker_outlives_a_hard_kill_with_a_full_pool`: **1 passed in 2.70 s** with localhost/process permission. |
| T-122 focused | Scaling oracle, reported ratio diagnostic and absolute supported-paste budget: **3 passed / 58 deselected**. |
| Reviewer regression | **1 failed**, deterministically observing two identical retarget requests. The earlier uncapped composed probe reached `RecursionError`; it was removed in favour of the bounded regression. |
| Reviewer test hygiene | `ruff check` and `ruff format --check` pass for the touched test files; `git diff --check` passes. |
| Windows | **Not run.** Migration 0003, Qt reset/editor behavior and the keyboard routes remain owed on the exact corrected head. |

### Final disposition

Do not commit this batch as approved and do not spend the final Windows verification run on the
current source. Correct `T126-R3`, keep the red reviewer regression, and rerun the focused reset
tests plus a composed durable-request regression. `T122-R2` remains non-blocking but is a one-line
hardening worth closing in the same pass. Then run the full Linux gates and the exact correction
head on Windows; Phase 2 still cannot exit until `T-128` satisfies the accepted `OPS-007`
amendment.

The reviewer changed only this review record and the one failing reviewer regression in
`tests/ui/test_row_verb_wiring.py`. No production source, submitted correction test, decision,
task state, remote ref, commit or CI state was changed.

## 2026-08-04 — `T126-R3` / `T122-R2` second correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** still the bounded uncommitted diff over `b7d0200`
**Verdict:** **The two submitted corrections are approved, but UX-005 / T-126 still needs one
High correction.** `T126-R3` and `T122-R2` are Resolved. A shared-editor option that is meaningful
in staging remains visible and inert in the durable queue.

### Submitted residuals

- **`T126-R3` is Resolved.** `QueueModel.setData()` now compares the submitted preset name with
  `_preset_name_for(job)` before emitting. That is the right boundary: it answers from durable
  value rather than reset-call provenance, preserves the commit-before-reset ordering, and also
  removes ordinary unchanged manager round trips. The reviewer's fast-write regression passes.
  The new `_WritableStore` tests exercise the real `DownloadManager.retarget()` both ways: an
  unchanged lifecycle commit never reaches it, while a genuine MP3 choice reaches job B's stored
  request and not the row that inherited its old position.
- **`T122-R2` is Resolved.** The bounded pump is followed by an explicit `manager.is_idle`
  assertion naming the sample size. A teardown that misses the deadline can no longer contaminate
  later samples while returning a plausible number.

### New finding

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T126-R4` | **High** | **Yes — T-126 / UX-005** | Queue format editor | `RowDelegate.createEditor()` unconditionally prepends **Same as all**, which is valid in the staging dialog because a whole-paste format exists there. A durable queue row has only its own stored request: the former group choice is neither persisted nor exposed. Selecting this entry supplies `None`, and `QueueModel.setData()` rejects `None`, so the queue displays an option which silently does nothing. The text is also false on this surface—there is no “all” to match. This violates UX-005 §5's “nothing offered that would be refused” rule. No submitted test selects the first entry. | Make the inherited entry model/surface-specific: retain it for staging, but do not offer it on queue rows unless the queue gains a real, specified group default. Ensure a custom durable selector still has an honest current representation rather than falling onto a misleading first built-in. | **Open** |

The failing reviewer regression is
`test_a_queue_editor_does_not_offer_an_inapplicable_group_default`. Current result:

```text
editor.findText("Same as all") == 0
expected -1
```

### Verification

| Check | Result |
|---|---|
| T126-R3 focused routes | **7 passed / 43 deselected**: original reset pair, restore-by-id, fast-write regression, real-manager unchanged and changed controls. |
| Complete row-wiring file | **50 passed / 1 failed**; the sole failure is the new reviewer regression above. |
| T122-R2 diagnostic | **1 passed / 110 deselected**, reporting paste cost within the diagnostic headroom. |
| Static hygiene touched paths | `ruff check`, `ruff format --check`, and `git diff --check b7d0200` pass. The implementer's four mypy gates are reported green; the full suite was still running at submission. |
| Windows | Still not run, correctly deferred until a reviewable source head exists. |

### Disposition

Correct `T126-R4` before completing T-126 or UX-005. Keep the staging dialog's inherited choice;
the finding is that the shared delegate silently exports it to a surface with no corresponding
state. After the reviewer regression passes, finish the Linux suite and spend Windows verification
on that exact head. Phase 2 remains independently blocked on the accepted `T-128` prerequisite.

This second pass changed only this review record and the new failing reviewer regression in
`tests/ui/test_row_verb_wiring.py`. No production source, submitted test, decision, task state,
commit, remote ref or CI state was changed by the reviewer.

## 2026-08-04 — `T126-R4` focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** bounded uncommitted diff over `b7d0200`
**Verdict:** **`T126-R4` Resolved. The corrected UX-005 / T-126 source is approved pending the
submitted full-suite result and exact-head Windows evidence.** Phase 2 remains separately blocked
by the accepted `T-128` prerequisite.

The inheritance decision now belongs to the model through `PRESET_INHERITABLE_ROLE`. Staging
answers true because its whole-paste choice is real; QueueModel and models unaware of the role
answer false by absence. `RowDelegate` uses that one fact for the live editor's entries, its
accessible description and the painted inherited label, so the option cannot survive on one of
those surfaces after disappearing from another.

The custom-selector consequence is also handled correctly rather than hidden by deleting the
entry. On a queue row where no built-in describes the durable request:

- `setEditorData()` leaves the combo with no selected built-in rather than coercing the miss to
  index zero;
- the painted combo carries no false inherited label;
- `SELECTOR_ROLE` supplies the literal durable selector even while the row remains editable; and
- `_whole_row()` consumes that same role, so screen-reader text follows the drawn condition rather
  than maintaining a second status/preset test.

That preserves all three honest states: staging inheritance, a named queue built-in, and an
editable queue custom selector.

### Verification

| Check | Result |
|---|---|
| T126-R4 plus reset/accessible controls | **8 passed / 105 deselected**. |
| Complete row-wiring file | **52 passed**. |
| Full UI suite in reviewer sandbox | **405 passed / 2 skipped / 2 failed**. Both failures are launch subprocesses trying to open `/home/sean/.cache/tracksandtrails/tracks-and-trails.log`, which this sandbox mounts read-only; they fail before application behavior and are not source regressions. The implementer reports the same suite outside this restriction as **407 passed / 2 skipped**. |
| Static hygiene on affected paths | `ruff check`, `ruff format --check`, and `git diff --check b7d0200` pass. The implementer reports all four mypy gates clean. |
| Full suite | Running at submission; the last baseline before R4 was **2061 passed**. |
| Windows | Not run; still owed on the committed exact correction head. |

No further source correction is requested. Once the full Linux suite reports, commit the bounded
batch, preserve the reviewer regressions, and run Windows against that exact head. A green Windows
run closes the platform-evidence condition for this UX correction; it does not waive the
independent `T-128` exit prerequisite accepted in the `OPS-007` amendment.

This pass changed only this review record. The previously added reviewer regression remains in
`tests/ui/test_row_verb_wiring.py`. No production source, submitted test, decision, task state,
commit, remote ref or CI state was changed by the reviewer.

## 2026-08-04 — `T-128` / `T-129` initial review

**Reviewer:** Codex (Reviewer)
**Base:** `05ad990`
**Submitted state:** bounded uncommitted diff over that base, including the untracked files named
in `ai/handoffs/2026-08-04-t128-t129-review.md`
**Overall verdict:** **Changes requested.** `T-129` has no source finding. `T-128`'s shared
`drain()` correction addresses the diagnosed teardown window, but the submitted warning detector
is blind in the full suite. The required 60-run Linux soak and exact-head Windows evidence remain
unperformed, so Phase 2 cannot exit on this state regardless of the source verdict.

### Blocking finding

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T128-R1` | **Medium** | **Yes — T-128** | Qt warning detector | Both `tests/integration/conftest.py` and `tests/ui/conftest.py` call `fail_on_orphaned_timers()` in the same pytest process. Qt keeps one message handler, so the second call replaces the first. Each call appends a new `seen` list, but `assert_no_orphaned_timers()` always reads `_orphaned[0]`. A warning therefore reaches the newest recorder while every autouse assertion inspects the detached oldest one. In a full run the detector cannot produce the failure it claims to provide. pytest-qt temporarily owns the handler during each test call and restores the newest project handler before fixture teardown, so it does not rescue this mismatch; teardown is the exact interval T-128 intends to guard. | Make installation process-idempotent and keep one recorder shared by the installed handler and every assertion, or otherwise ensure each assertion reads the currently installed handler's recorder. Preserve pytest-qt's temporary capture/restore behavior. Keep the reviewer regression that installs through both conftest routes and injects the warning into the live handler. | **Open** |

The reviewer regression is
`test_both_qt_suites_share_the_detector_that_they_assert` in
`tests/ui/test_qt_lifecycle.py`. It deterministically fails on the submitted implementation:

```text
Failed: DID NOT RAISE AssertionError
recorders: [[], ['Timers cannot be stopped from another thread']]
```

This is blocking because the submitted T-128 correction explicitly claims that this warning is
converted into a failure naming its cause. The defect is confined to the test harness and does not
undermine the separate evidence that `drain()` waits for both idle work and inactive child timers.

### T-129 disposition

`T-129`'s source is approved pending platform evidence. The three attack points in the handoff
were checked rather than inferred:

- The `0.9em` margin scales on the product route, where the application font is established before
  `theme.apply()` parses the sheet. The default font retained 5 px clearance and an 18 pt
  application font retained 4 px. A per-widget font applied after the style sheet does not cause Qt
  to recompute `em`, but no product surface changes a group box's font that way.
- Application-wide selection colours agree with `RowDelegate`: `theme.apply()` assigns
  `Highlight=primary` and `HighlightedText=on_primary`, the same pair the style sheet declares,
  and the delegate reads `highlightedText()` only for selected rows. No competing selected-state
  colour path was found.
- The dark theme uses the same stylesheet structure with separately contrast-checked roles. It is
  still correctly disclosed as never having been displayed and is not presented as T-129 evidence.

The four rendering tests pass, including their native-style positive control. Windows remains a
real completion condition because Qt supplies the metrics being asserted; the last Windows run at
`05ad990` does not cover this diff.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 05ad990` passed before the reviewer additions. |
| Known T-128 teardown case | `test_a_ready_job_starts_a_download_at_running`: **1 passed**. |
| T-129 rendering tests | **4 passed**. |
| Changed manager/UI surface | **307 passed / 16 failed**. All 16 failures were localhost-server setup denials (`PermissionError: Operation not permitted`) in this restricted runner; no product assertion ran in those cases. |
| Reviewer regression | **1 failed**, reproducing `T128-R1` deterministically. |
| Reviewer test hygiene | `ruff check`, `ruff format --check`, and bare mypy pass for `tests/ui/test_qt_lifecycle.py`. |
| Required soak | **Not run.** OPS-007 still requires 60 clean full-suite Linux runs. |
| Windows | **Not run on this diff.** Last evidence is the base `05ad990`. |

### Disposition

Correct `T128-R1`, keep the reviewer regression, and re-run it alongside the known teardown test.
Then finish the submitted full Linux gate, run the 60-pass soak, and obtain Windows evidence on the
exact committed head. `T-129` needs no source correction from this review, but is not complete
until that Windows rendering execution reports.

This review changed only this record and added the failing reviewer regression
`tests/ui/test_qt_lifecycle.py`. No submitted source, submitted test, coordination document,
decision, task state, commit, remote ref or CI state was changed by the reviewer.

## 2026-08-04 — `T128-R1` focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** still the bounded uncommitted diff over `05ad990`
**Verdict:** **`T128-R1` Resolved. The T-128 and T-129 source corrections are approved; the
batch remains Blocked on evidence rather than code.** The submitted full Linux result, OPS-007's
60-run Linux soak, and exact-head Windows execution are still outstanding.

The recorder now has exactly one identity for the process. Every handler installed by either Qt
conftest appends to the module-level `_orphaned: list[str]`, and every autouse assertion reads and
clears that same list. It therefore does not matter which of the two project handlers pytest-qt
restores before fixture teardown: the live handler and the assertion share the state that decides
the failure. This closes the mismatch from the initial review without adding installation-state
bookkeeping that would itself have to reason about pytest-qt's temporary replacement.

The reviewer regression now passes unchanged. A direct Qt message-dispatch probe also installed
both project handlers, emitted `CROSS_THREAD_TIMER` through `qWarning()`, and observed
`assert_no_orphaned_timers()` raise with the recorded warning. The known manager teardown case
continues to pass with the shared `drain()` helper.

### Evidence

| Check | Result |
|---|---|
| Reviewer regression + known teardown + T-129 render set | **6 passed**. |
| Real Qt handler dispatch | Two installations, one `qWarning(CROSS_THREAD_TIMER)`, then the project assertion: **detected and raised**. |
| Correction static gates | `ruff check`, `ruff format --check`, and bare mypy on `tests/qt_lifecycle.py` plus `tests/ui/test_qt_lifecycle.py`: **pass**. |
| Boundary hygiene | `git diff --check 05ad990`: **pass**. |
| Full Linux suite | **Running at re-review submission; no final result reviewed yet.** |
| Required soak | **Not started.** OPS-007 still requires 60 clean full-suite Linux runs. |
| Windows | **Not run on the corrected diff.** An exact commit head is still required. |

One handoff discrepancy is non-blocking but should not enter the durable evidence record as
written: the implementer reported adding a test in which real cross-thread QObject destruction
emits the warning, but no such test exists in the current tree. The persisted regression injects
the message into the captured handler; the reviewer independently exercised Qt's real
`qInstallMessageHandler`/`qWarning` dispatch, not real cross-thread destruction. Neither stronger
claim is needed to resolve `T128-R1`, whose defect was recorder identity, but the eventual handoff
must distinguish a one-off probe from a committed test.

No further source or test correction is requested. Report the full Linux result, commit the exact
reviewed tree, obtain Windows evidence on that head, and run the 60-pass soak before presenting the
Phase 2 exit again. This re-review changed only this review record; no submitted source, submitted
test, coordination document, task state, commit, remote ref or CI state was changed by the
reviewer.

## 2026-08-04 — `T-130` initial review

**Reviewer:** Codex (Reviewer)
**Base:** `bd4dde8`
**Submitted state:** bounded uncommitted diff over that base, including
`docs/mockups/2026-08-03-main-window-b1.html`
**Overall verdict:** **Changes requested.** The maintainer ruling is recorded coherently and the
mockup is preserved, but one selection change escapes the rows and makes selected text nearly
invisible. Two smaller adopted details are also absent while their tests report the ruling met.

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T130-R1` | **High** | **Yes — T-130 / NFR-005** | Application palette / text selection | T-130's quiet row tint is assigned to application-wide `QPalette.Highlight` and `on_selection` to `HighlightedText`. Those roles also draw selections in `QPlainTextEdit`, including the add-dialog URL input and the copyable job log. Those widgets have no inset bar, so the tint is their only selection signal. A real editor created after `theme.apply()` measures **1.14:1** in light mode (`#EBF1EE` on white) and **1.33:1** in dark mode (`#1D382E` on `#10201A`), below the project's 3:1 control-state floor; keyboard-selected text is effectively unmarked. The submitted test asserts selected text against the tint, but never tint against the editor surface. | Keep the subtle tint and inset bar scoped to row views. Restore a high-contrast application `Highlight`/`HighlightedText` pair for generic text selection, or otherwise give text editors an explicit visible pair. Qt's QSS selection properties resolve a `QListView`'s palette to `selection`/`on_selection` even when the application palette stays `primary`/`on_primary`, so `RowDelegate` need not force the row choice into the global palette. Keep the real-editor reviewer regression for both themes. | **Open** |
| `T130-R2` | **Medium** | **Yes — accepted UX-005 amendment** | Primary toolbar action | The adopted ruling and preserved mock name the first action **`+ Add URLs`**. The toolbar reuses the correct `QAction`, but its visible text is `Add URLs...`; the submitted regression checks only `actionAddUrls`'s object name and therefore passes while the ruled `+` is absent. | Preserve the shared action semantics while making the toolbar's visible primary label begin `+ Add URLs`. Keep the reviewer assertion on the rendered action text as well as its first position and identity. | **Open** |
| `T130-R3` | **Medium** | **Yes — accepted UX-005 amendment** | Running state chip | UX-005 adopts the mock's chip examples `Done`, `Queued`, **`62%`**, `Failed`. The delegate always draws `STATE_ROLE`; on a running row that is a worker stage such as `Downloading video`, while `PROGRESS_ROLE` already carries `0.62`. The role test proves only that Queue asks for some chip, and the pixel test proves only that some pixels change, so neither can catch the missing adopted running value. Completed rows likewise inherit the existing `Completed` vocabulary rather than the adopted chip label `Done`. | Give the chip its own display value: use compact progress text while a determinate download runs, and the ruled state labels otherwise, without replacing the separate state/accessibility vocabulary. Keep the reviewer paint regression that varies `STATE_ROLE` under a fixed `PROGRESS_ROLE=0.62`; the correct running chip renders `62%` in both cases. | **Open** |

### Submitted uncertainties resolved

- **Monochrome chip: upheld.** The accepted amendment requires words and says never colour alone;
  it does not require semantic colour. A bordered, word-bearing chip satisfies that decision and
  avoids introducing a second status-semantic channel solely for decoration.
- **Global `QListView::item:selected`: no current defect found.** Queue, History and staging are
  the application's row lists, so a common tint/bar is coherent. Combo popups keep their more
  specific primary selection fill; the same-primary border is not an additional visible signal.
  Scope may become worth narrowing if another list surface is added, but no present behavior is
  broken by this selector.
- **Chip/title geometry: source is sound, submitted test is weak.** The test only proves the role
  changes pixels, as disclosed. The implementation computes the chip rectangle first and limits
  `elidedText()` to the width before it, so no overlap path was found. This does not block on its
  own.
- **`T124-R3` rewrite: upheld.** The exact action set still rejects selection-scoped toolbar verbs,
  and comparing enabled states before, during and after selection now tests the underlying chosen
  property without incorrectly requiring Add URLs to be enabled in a deliberately unwired window.

The reviewer extended the selection test to render the adopted two-pixel inset bar; it passes.
That closes the submitted test gap for the bar itself and would fail if the QSS border were removed.

### Independent verification

| Check | Result |
|---|---|
| Boundary hygiene | `git diff --check bd4dde8`: **pass** before and after reviewer tests. |
| Focused main-window/delegate/theme set | **180 passed / 4 failed**. The four failures are exactly the three findings: toolbar label, running-chip rendering, and text-selection visibility in both themes. |
| Text selection contrast | Real post-theme `QPlainTextEdit`: **1.14:1 light / 1.33:1 dark**, reviewer regression red. |
| Inset bar rendering | Real selected `QListView` item: first two pixels are `primary` for the full item height, reviewer assertion green. |
| Reviewer test hygiene | `ruff check`, `ruff format --check`, and bare mypy: **pass**. |
| Submitted Linux suite | Implementer reports **2075 passed / 11 skipped / 2 deselected** before the reviewer regressions. |
| Windows | **Not run on this diff.** Base evidence at `bd4dde8` predates T-130. |

### Disposition

Correct all three findings in one focused batch. Preserve the one shared Add action, the queue-only
chip decision, the row tint plus bar, and the stronger rewritten `T124-R3` property. Run the three
reviewer regressions, the complete changed UI/theme set, all static gates and the full Linux suite;
then obtain Windows evidence on the exact committed correction head.

This review changed only this record and reviewer regressions in
`tests/ui/test_row_verb_wiring.py`, `tests/ui/test_row_delegate.py` and
`tests/ui/test_theme_metrics.py`. No submitted source, submitted test meaning, decision, task
state, commit, remote ref or CI state was changed by the reviewer.

## 2026-08-04 — `T-130` focused correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** still the bounded uncommitted diff over `bd4dde8`
**Overall verdict:** **Blocked pending maintainer direction.** `T130-R1` and `T130-R2` are
resolved. `T130-R3` remains a blocking Medium finding. This was the one focused correction
re-review allowed by `AGENTS.md` §10; because the remaining blocker is not High or Critical, the
reviewer will not silently start a third implementation/review round. The maintainer must choose
whether to authorize another focused pass, accept the risk/change the ruling, or carry the defect
to a named follow-up. Exact-head Windows execution and OPS-007's 60-run soak remain owed after the
source is approved.

### Finding status

| ID | Severity | Blocks approval | Finding | Recommendation | Status |
|---|---|---:|---|---|---|
| `T130-R1` | High | No | The row tint is now scoped to item views, while the application palette retains the brand highlight for text selection. The real `QPlainTextEdit` regression executes for both light and dark themes and passes; the submitted `chosen` fixture matches the reviewer's intent. | Keep both-theme coverage. | **Resolved** |
| `T130-R2` | Medium | No | The toolbar renders and announces `+ Add URLs`, the File menu retains `Add URLs...`, and both surfaces share one action. Reading `QToolButton.text()` rather than `QAction.text()` is the correct assertion for the rendered label; pinning its accessible name strengthens the ruling without changing it. | Keep the amended regression. | **Resolved** |
| `T130-R3` | Medium | **Yes — T-130 / accepted UX-005 amendment** | The correction obtains `62%` from `PROGRESS_ROLE`, but then drops `STATE_ROLE` from the second line whenever a chip exists (`row_delegate.py:554-558`). Consequently `Downloading video` and `Post-processing` produce pixel-identical rows: the handoff and `T-130` say the stage remains visible, but it does not. The same rule also turns a completed row into `100%`, because `QueueModel._fraction()` deliberately returns `1.0` for `COMPLETED`; the adopted compact label is `Done`. More generally, a numeric progress role cannot distinguish a running percentage from the ruled labels for queued and terminal states. | Give the chip a status-aware display value at the model boundary (for example, make the queue's chip role answer `62%`, `Queued`, `Done`, or `Failed`) and leave `PROGRESS_ROLE` as the bar's numeric value. Suppress the second-line state only when the chip truly duplicates it; a percentage chip must retain the worker stage. Keep both reviewer paint regressions. | **Open** |

### Why the first reviewer regression changed

The original `T130-R3` reviewer test was wrong. It varied `STATE_ROLE` under one progress value and
required the **entire rows** to be identical, even though its own prose and the submitted handoff
said the worker stage remains on the second line. The correction passed that assertion by erasing
the stage. A reviewer assertion is evidence, not a specification, so the focused re-review replaces
that mechanism-shaped oracle with two independent visual claims: the title-line chip is identical
under one `PROGRESS_ROLE`, while the whole rows differ when the visible worker stage differs. A
second regression pins the adopted completed label `Done` rather than accepting `100%`.

### Independent verification

| Check | Result |
|---|---|
| Corrected changed UI/theme set | **183 passed / 2 failed**. Both failures are `T130-R3`: the worker stage is erased and completion draws the wrong compact label. |
| `T130-R1` real editor route | Both parametrized themes pass. The supplied fixture is an appropriate repair of the missing test input. |
| `T130-R2` rendered/announced route | Toolbar label, accessible name and shared-action tests pass. |
| Reviewer test hygiene | `ruff check`, `ruff format --check`, and bare mypy over 107 files: **pass**. |
| Boundary hygiene | `git diff --check bd4dde8`: **pass**. |
| Submitted Linux suite | Implementer reports **2078 passed / 11 skipped / 2 deselected** before the corrected reviewer oracles. |
| Windows | **Not run on this diff.** Base evidence at `bd4dde8` predates T-130. |
| Required soak | **Not run.** OPS-007's 60 clean full-suite Linux runs remain Phase 2 evidence. |

This re-review changed only this review record and the two `T130-R3` reviewer regressions in
`tests/ui/test_row_delegate.py`. No submitted source, submitted test meaning, decision, task state,
commit, remote ref or CI state was changed by the reviewer.

## 2026-08-04 — `T130-R3` authorized final correction re-review

**Reviewer:** Codex (Reviewer)
**Base:** still the bounded uncommitted diff over `bd4dde8`
**Authorization:** The maintainer proceeded with and recorded the additional focused pass requested
by the preceding review under `AGENTS.md` §10.
**Verdict:** **`T130-R3` Resolved. T-130's source is approved.** The reviewed tree may be committed.
Exact-head Windows execution is still required before the platform evidence is complete;
OPS-007's 60-run Linux soak remains a separate Phase 2 exit gate.

### Resolution

The compact vocabulary now belongs to `QueueModel`, the component that knows `JobStatus`.
`STATE_CHIP_ROLE` carries display text rather than a boolean: `_chip()` returns a percentage only
for `RUNNING`, and returns the ruled compact status word otherwise. The delegate draws that text
without consulting `PROGRESS_ROLE`, so completion cannot become `100%` merely because the progress
bar correctly reports a fraction of `1.0`.

The second line now removes `STATE_ROLE` only when it is textually identical to the chip. A running
`62%` chip therefore retains `Downloading` or the worker's more specific stage, while `Queued` and
`Failed` are not repeated word-for-word. This resolves both clauses of the finding without
hard-coding lifecycle vocabulary or inferring terminality from a fraction in the shared delegate.

The implementer was right to amend the two reviewer paint tests after changing the role's
contract. Supplying boolean `True` to a text role made both crops empty and let the assertions pass
without a chip. They now supply literal chip text, and the real-model parameterized regression
independently pins `RUNNING=62%`, `COMPLETED=Done`, `FAILED=Failed`, and `QUEUED=Queued` while
holding byte counts constant. Those tests divide the responsibility cleanly: the model chooses the
word, and the delegate preserves it and the separate worker stage.

### Deliberate percentage repetition

The running row's `62%` chip and the detailed second-line `62% · 620 B of 1000 B` are redundant but
not a finding. `REQ-014` explicitly requires percent in the per-job live-progress transcription,
and `QueueModel._detail()` is intentionally composed from those retained column values. UX-005
adds a glanceable chip; it does not remove REQ-014's detailed percentage. Both renderings use the
same `_fraction()` value, so they cannot contradict one another. Removing the detailed value would
widen T-130 into changing an established requirement solely to match mockup whitespace.

### Independent verification

| Check | Result |
|---|---|
| Changed main-window/queue/delegate/theme surface | **222 passed**. |
| Corrected reviewer paint regressions | Both pass with literal chip text; neither can pass through an absent chip. |
| Real-model vocabulary regression | All four ruled examples pass with identical byte counts and differing statuses. |
| Reviewer test hygiene | `ruff check`, `ruff format --check`, and bare mypy over 107 files: **pass**. |
| Boundary hygiene | `git diff --check bd4dde8`: **pass**. |
| Submitted full Linux suite | **2083 passed / 11 skipped / 2 deselected**. |
| Submitted static gates | ruff, format over 158 files, mypy and win32 mypy over both configured trees, placement gate: **reported clean**. |
| Windows | **Not run on this diff.** Base evidence at `bd4dde8` predates T-130. |
| Required soak | **Not run.** OPS-007's 60 clean full-suite Linux runs remain Phase 2 evidence. |

No further source or test correction is requested. This re-review changed only this review record;
no submitted source, submitted test, coordination document, decision, task state, commit, remote
ref or CI state was changed by the reviewer.

## 2026-08-04 — criterion 8 UI batch initial review

**Reviewer:** Codex (Reviewer)
**Base:** `bd4dde8`
**Submitted source head:** `768937c` (the later `36df043` changes only the handoff header)
**Overall verdict:** **Changes requested.** The criterion amendment is recorded as an amendment,
not inferred from the former Phase 3 sequencing rule, and the performance measurement is a
reasonable structural guard. The closed list is not complete as implemented, however. Seven
reviewer regressions fail, two accepted T-140 surfaces have no implementation at all, and the
phase record calls the criterion met while exact-head Windows evidence is explicitly owed.

### Findings

| ID | Severity | Blocks approval | Area | Finding | Recommendation | Status |
|---|---|---:|---|---|---|---|
| `T137-R1` | **High** | **Yes — T-137 correctness** | Playlist entry routing | `_entries()` prefers a flat entry's `url` and discards `ie_key`. yt-dlp itself resolves that shape as the pair `url + ie_key`; a number of extractors put only an extractor-local id in `url`. T-137 then persists that value as a new standalone job and launches a fresh yt-dlp invocation with neither the extractor key nor a necessarily routable URL. Literal full-URL fixtures cannot expose this. The reviewer case supplies `url="abc123"`, `ie_key="Youtube"` and a public `webpage_url`; the durable entry is incorrectly `abc123`. | Persist enough routing information to reproduce yt-dlp's entry route, or select a public/original URL when one is available and prove it can be opened by a fresh extraction. Add an extractor-directed flat-entry fixture; do not assume every `url` is an absolute URL. | **Open** |
| `T137-R2` | **High** | **Yes — UX-003 / T-137** | Playlist admission | The code correctly observes that a flat entry is not probed and therefore creates it as `QUEUED`, but `_on_committed()` immediately calls `admit(job_id)` with the default `DOWNLOAD` kind. The state word and comment do not create the missing probe: every entry bypasses UX-003's queued-job probe and goes directly to download. Filing T-143 outside criterion 8 cannot defer a violation in T-137's submitted behavior. | Route each new entry through a real probe before its download is admitted, preserving pause/probe semantics and per-entry failure reporting; alternatively obtain a maintainer amendment to UX-003 that explicitly accepts direct flat-entry downloads and their information loss. | **Open** |
| `T132-R1` | **High** | **Yes — accepted UX-005 row 6** | Real toolbar styling | The isolated style test sets `primaryAction` before styling a bare button. The product lets `QToolBar` create the button and sets the dynamic property afterwards without repolishing it. In the shown real window the Add action therefore remains a neutral bordered button rather than the mock's filled brand primary. The reviewer sample is `#EAEFE9` against required `#1E5E47`; the screenshot agrees. | Exercise the actual `MainWindow` construction order and repolish the rendered button (or establish the property before its first style polish). Keep the real-window regression; the bare-button test is not evidence for this route. | **Open** |
| `T134-R1` | **Medium** | **Yes — T-134** | History row hover | Queue installs `RowDelegate.watch_hover()`; History carries the same painted Open/Show-in-folder controls and even says the pointer is watched, but never calls it. Its viewport has mouse tracking disabled, so pointer-move hover feedback is absent unless a button is held. | Install the delegate's hover route on the History list and retain the viewport-level regression. | **Open** |
| `T140-R1` | **High** | **Yes — wrong-target risk** | Visible selection mapping | `QueueView.selected_job_id()` applies a visible row number to `QueueModel.job_ids()`, which is the underlying durable order. A collapsed three-entry playlist followed by `solo` has two visible rows; selecting visible row 1 returns hidden `entry-1`, not `solo`. Open/reveal and any selection-scoped action can therefore target a different job than the one drawn as selected. | Resolve selection through the selected model index's `JOB_ID_ROLE`. Give group headers an explicit non-job/group selection path rather than treating their playlist id as a job id. Keep the collapsed-group reviewer regression. | **Open** |
| `T140-R2` | **High** | **Yes — accepted UX-005 row 9d** | Clear finished | The accepted rule and T-140's own acceptance criteria say a partly finished group stays intact. `JobRepository.clear_completed()` still deletes every completed/cancelled row independently. The reviewer case removes the completed child beside a running sibling, shrinking or dissolving the group underneath the user. | Make clear-finished choose terminal playlist members only when every surviving member of that playlist is terminal, in the same transaction; retain ordinary standalone behavior and test the partly finished and all-finished cases. | **Open** |
| `T140-R3` | **High** | **Yes — adopted mock / UX-005 row 9c** | Playlist format contract | The adopted mock puts the common `Download as` value on the group because short children drop their format line. `_group_data()` answers neither `SELECTOR_ROLE` nor a preset role, so a closed playlist shows no effective format anywhere. The implementation also continues to offer each retargetable child its own editor, which can make members differ; that contradicts the stated premise that every entry inherits the group's format. | Obtain one coherent ruling and implement it end to end. Under the adopted mock, persist/derive a common group format, display it on the header, and make retargeting honor group inheritance. If independent child formats are intended instead, amend row 9c/mockup and give every child an honest visible control/value without restoring the clipping defect. | **Open; maintainer disposition required** |
| `T140-R4` | **Medium** | **Yes — T-140 grouping** | Flattened order | `_rebuild_visible()` inserts each expanded member at its durable queue position. Moving one member can place an unrelated standalone row between the header's children; the reviewer reproduction draws depths `[group, 1, 0, 1]`. One opened playlist is no longer one contiguous branch and the connecting rail visually claims the unrelated row's placement. | Either render a group's members contiguously beneath its first position regardless of member positions, or make reorder operations group-aware so the durable order cannot split a group. Pin the chosen ordering semantics with the interleaving regression. | **Open** |
| `T140-R5` | **High** | **Yes — accepted T-140 criteria / NFR-005** | Scope completion | T-140 is marked Complete while its own acceptance criteria require group verbs, count-bearing group removal, and keyboard-reachable disclosure. The task explicitly says group verbs are “not done” and moves them to T-142; the only disclosure route in source is a left-button release from the delegate, with no key route. A closed criterion list may exclude genuinely later work, but it cannot make accepted work complete by moving that work outside the list without a maintainer amendment. | Implement the accepted criteria in T-140, including an explicit tested keyboard disclosure route, or obtain a maintainer ruling that amends UX-005/T-140 and criterion 8 together. Keep T-142 outside criterion 8 only for scope that was not already part of the adopted row and acceptance criteria. | **Open; maintainer disposition required** |
| `P2EXIT-R10` | **High** | **Yes — Phase 2 exit truth** | Criterion 8 evidence | The plan calls criterion 8 **Met** while its own row says T-140's exact-head Windows run is owed, the handoff says the corrected UI has not run on Windows, and this review finds visible and behavioral failures. The plan/status also alternate between “nine tasks” and the ten ids T-132–T-141. Because five earlier visible defects escaped the gates and the real window exposes `T132-R1` immediately, automated checks alone are not sufficient evidence for this explicitly visual criterion. | Mark criterion 8 Not met. Correct and re-review the closed list, obtain exact-head Windows evidence, and run the built application against a written checklist derived from T-132–T-141 and the adopted mockups on the exact candidate head. This checklist is evidence for the existing closed list, not an invitation to add unrelated tasks. Correct the task count to ten. The 60-run OPS-007 soak remains separately owed. | **Open** |

### Submitted uncertainties resolved

- **Criterion amendment form: upheld.** `IMPLEMENTATION_PLAN.md` and `STATUS.md` identify the
  maintainer's 2026-08-04 amendment rather than pretending these Phase 3 tasks were implied by an
  older exit criterion. The problem is the premature **Met** verdict, not the authority or form of
  the amendment.
- **Closed edge: not upheld as currently drawn.** It is reasonable to close the list at T-141 so
  later observations do not make “the UI is caught up” unfalsifiable. It is not reasonable to put
  T-140's already accepted verbs, removal and keyboard criteria into T-142 outside that edge.
- **Repaint/layout budget: upheld.** The test separately measures opening, every `sizeHint`, and a
  real delegate paint, proves row heights differ, and keeps the 0.5 s threshold as a broad
  structural alarm rather than a runner-speed claim. No defect was found in that instrument.
- **Monochrome chips: upheld.** UX-005 requires words and forbids colour as the only signal; it
  does not require semantic fill colours. The segmented group bar already distinguishes its
  states visually and the text/count carries the accessible meaning.

### Independent verification

| Check | Result |
|---|---|
| Boundary | Reviewed `bd4dde8..768937c`. The checkout later advanced through docs/task-only T-144/T-145 commits; no committed `src/` delta exists after the submitted source head. Concurrent uncommitted T-146 theme work was excluded. |
| Reviewer regressions | **7 failed**, each at its stated property: extractor-directed URL, part-finished group clearing, visible selection identity, contiguous group order, group format visibility, History hover tracking, and real-window primary fill. |
| Real window | Shown offscreen at 900×620 using the product composition and light theme. The primary button remained neutral; its sampled fill was `#EAEFE9`, not brand `#1E5E47`. The playlist format was absent from its header, agreeing with the model regression. |
| Reviewer test hygiene | `ruff check`, `ruff format --check`, `git diff --check`, bare `mypy --no-incremental`, and bare `mypy --platform win32 --no-incremental`: **pass** for the working tree containing the reviewer tests. |
| Submitted Linux evidence | Implementer reports **2132 passed / 11 skipped / 2 deselected** at the corrected source head before these reviewer regressions. |
| Windows | **Not run on `a884035`/`768937c`.** Last evidence is `1d87929`, before the correction source. |
| Required soak | **Not run.** OPS-007's 60 clean full-suite Linux runs remain an independent Phase 2 evidence gate. |

### Disposition

Correct the seven reproduced source defects and reconcile T-140's missing accepted scope before
spending the exact-head Windows run. Reset criterion 8 to Not met, then use a written built-window
checklist on the reviewed candidate rather than deriving visual completion from unit gates. After
focused re-review, exact-head Windows and the 60-run soak can supply the remaining platform and
stability evidence.

This review added failing regressions to `tests/unit/test_ytdlp_adapter.py`,
`tests/unit/test_persistence.py`, `tests/ui/test_queue_view.py`,
`tests/ui/test_history_view.py`, and `tests/ui/test_row_verb_wiring.py`, and appended this record.
No submitted source, submitted test meaning, decision, task state, commit, remote ref or CI state
was changed by the reviewer.

## 2026-08-05 — criterion 8 corrections focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `a591a6d`
**Correction head:** `d929d98` (local only; handoff untracked)
**Verdict:** **Changes requested.** Five source findings are resolved. `T132-R1` is withdrawn as a
reviewer error, not corrected. `T140-R3` is only half implemented, `T137-R2` and `T140-R5` remain
open by disclosure, and the committed boundary contains unrelated unsubmitted work. Do not spend
the Fedora/Windows run on this head.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `T137-R1` | High | No | `_entries()` now prefers the standalone public/original address over the extractor-local `url`. The reviewer-directed entry resolves to the YouTube webpage URL, and the previous literal fixtures remain covered. | **Resolved** |
| `T137-R2` | High | **Yes — T-137 / UX-003** | Unchanged by disclosure: durable entries are `QUEUED`, then immediately admitted as `DOWNLOAD`, so no per-entry probe occurs. | **Open** |
| `T132-R1` | High | No | The initial review measured a deliberately disabled action. `_window_over()` supplies no job sink or output directory, so T-016 disables Add and UX-005 correctly paints it `sunken`. A genuinely composed enabled window paints the action brand-filled. Removing the new explicit repolish leaves that corrected product-route regression green. | **Withdrawn — reviewer error** |
| `T134-R1` | Medium | No | History now installs `RowDelegate.watch_hover()` on its list; the viewport-level reviewer regression passes. | **Resolved** |
| `T140-R1` | High | No | Selection resolves through the model's visible mapping. A header returns no job id, while the ordinary row after a collapsed group returns its own id. | **Resolved** |
| `T140-R2` | High | No | Clear-finished retains terminal members while any playlist sibling is non-terminal. The clause is applied to both the selected ids and deletion inside the repository transaction; ordinary terminal rows remain covered. | **Resolved** |
| `T140-R3` | High | **Yes — accepted UX-005 row 13** | The correction displays a group format and suppresses child editors, but the ruling also says **“retargeting happens on the group.”** `_group_data()` answers no `PRESET_CHOICES_ROLE`, `flags()` therefore leaves the header non-editable, and `setData()` explicitly refuses `_Group`. The new reviewer regression fails with `choices is None`. The implementation has moved the old control away without creating its ruled replacement. It also renders a common built-in as the raw selector rather than `_effective_format_text()`'s preset name. | **Open — partially corrected** |
| `T140-R4` | Medium | No | `_rebuild_visible()` gathers members once and emits an expanded group contiguously at its first member's position. The interleaving reviewer regression passes. | **Resolved** |
| `T140-R5` | High | **Yes — accepted T-140 / NFR-005** | Correctly disclosed as unimplemented. No group verbs, count-bearing removal, or keyboard disclosure route exists. | **Open** |
| `P2EXIT-R10` | High | **Yes — Phase 2 truth** | Criterion 8 is correctly reset to Not met, but the current-truth repair is incomplete: its title and explanatory paragraph still say nine tasks for T-132–T-141; the row says nine review findings remain; `STATUS.md` still says all ten tasks are complete; and `TASKS.md` still files T-140 under Complete while T-142 retains the work the maintainer ruled back into it. The row also repeats the now-withdrawn T132-R1 claim. | **Open — accepted, not reconciled** |

### New correction-round findings

| ID | Severity | Blocks approval | Finding | Recommendation | Status |
|---|---|---:|---|---|---|
| `T132-R2` | **Medium** | **Yes — correction truth** | Although the handoff correctly disproves T132-R1's mechanism, `main_window.py` now carries an explicit unpolish/polish and a long comment asserting the disproved mechanism as fact; the reviewer test docstring says the same. The enabled route passes with those calls deleted. This is unnecessary source behavior justified by false behavioral prose—the exact “code moved and prose did not” class the project treats as a defect. | Remove the unnecessary repolish or provide a product state that requires it. Keep the enabled real-composition regression, rewrite it as a positive guard for UX-005/T-016, and record T132-R1 as withdrawn rather than corrected. | **Open** |
| `COORD-R22` | **Medium** | **Yes — review boundary** | `d929d98` is presented as the six-finding correction commit but also includes the unrelated `primary_hover` theme change and its tests (T-146 in source comments), which the handoff never names and no current T-146 task record specifies. It also sweeps the reviewer-owned `ai/REVIEWS.md` into the implementer's commit. The correction boundary therefore contains unreviewed source outside the stated submission. | Before pushing, either give T-146 its own filed task and explicit review scope/evidence, or separate it from this correction boundary using the repository's permitted local-history process. Disclose the reviewer-record inclusion rather than treating `d929d98` as one-purpose. | **Open** |

### Independent verification

| Check | Result |
|---|---|
| Seven original reviewer regressions | **7 passed**. |
| T132 mechanism mutation | Removed `unpolish()`/`polish()` temporarily; the corrected enabled real-window regression still passed. `main_window.py` hash was identical before and after the probe. |
| New group-format control regression | **1 failed**: the group header answers `PRESET_CHOICES_ROLE=None`. |
| Reviewer test/static hygiene | `ruff check`, `ruff format --check`, bare `mypy --no-incremental`, and bare win32 mypy: **pass** over 107 files. |
| Submitted full Linux suite | **2143 passed / 11 skipped / 2 deselected** at `d929d98`, as reported in the completed handoff. |
| CI | **None on this head.** Fedora and Windows are both owed after source approval. |
| Soak | **Not run.** The 60-run Linux soak remains owed. |

### Disposition and sequencing

Do not push `d929d98`. First close `T140-R3`, remove/reconcile the false T132 correction, repair the
task/plan/status truth, and resolve `COORD-R22`'s hidden T-146 boundary. Then complete the already
ruled `T140-R5`; beginning with keyboard disclosure is sensible, but partial keyboard work does not
close the finding without group verbs and count-bearing removal. `T137-R2` remains a separate High
correctness blocker and must also land before criterion 8 can return to review.

The untracked handoff should be committed only after it is amended with this verdict and the real
boundary contents. Once the resulting exact head is source-complete and locally green, push once
to exercise Fedora and Windows rather than spending those runs on another intermediate state.

This re-review appended this record and added one failing reviewer regression to
`tests/ui/test_queue_view.py`. The temporary T132 mutation was fully reverted. No submitted source,
decision, task state, commit, remote ref or CI state was changed by the reviewer.

## 2026-08-05 — `T132-R2` focused correction re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `6ad7ce9`
**Correction head:** `ff95990` (`d7af554` is the submitted source/test head; `ff95990` adds the
committed handoff)
**Verdict:** **Changes requested for the round; `T132-R2` resolved.** This submission contains one
finding only. `T137-R2`, `T140-R3` and `T140-R5` remain open and were not re-reviewed here.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `T132-R2` | Medium | No | The unnecessary `unpolish()` / `polish()` pair is removed from the product, and the source comment, regression docstring and failure message no longer state `T132-R1`'s disproved mechanism as fact. They identify `T132-R1` as withdrawn reviewer error and describe the enabled composition route accurately. The retained regression is appropriately scoped: T-132 explicitly requires the brand fill to be sampled from the rendered widget, and this remains the only assertion against an enabled `MainWindow` composed through the product route. It need not mutation-prove a repolish that no longer exists; it can still fail if the composed action loses its primary property, discoverable object name, enabled state or UX-005 row 6 fill. | **Resolved** |

### Boundary and submitted uncertainty

The complete reviewed range is `6ad7ce9..ff95990`: `7d66726` changes only `AGENTS.md`,
`ai/TESTING.md` and `docs/DEVELOPMENT.md`; `d7af554` contains the T132-R2 source and regression
correction; `ff95990` commits the handoff. The unrelated one-worker-per-machine prose is disclosed
and has no source or test effect. `ai/REVIEWS.md`, `ai/TASKS.md` and `ai/STATUS.md` are untouched in
the submitted range. This focused pass does not adjudicate `COORD-R22` or any other open finding.

The submitted uncertainty is resolved in favor of keeping the regression. Its old explanation was
wrong, but its observable contract is not: an enabled Add URLs action in the real window must draw
the adopted brand fill. The isolated theme test does not exercise that composition route.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 6ad7ce9..ff95990`: **pass**. Six files are changed: three disclosed prose files, the submitted source and test, and the committed handoff. |
| T-132 product/style routes | **7 passed / 73 deselected** across the targeted `test_row_verb_wiring.py` and `test_theme_metrics.py` cases, including the enabled real-window fill. |
| Lint | `.venv/bin/python -m ruff check .`: **pass**. |
| Format | `.venv/bin/python -m ruff format --check .`: **pass**, 161 files already formatted. |
| Source types | `.venv/bin/python -m mypy src`: **pass**, 44 source files. |
| Test-inclusive types | `.venv/bin/python -m mypy`: **pass**, 107 source files. |
| Windows type route | `.venv/bin/python -m mypy --platform win32`: **pass**, 107 source files. |
| Environment disclosure | Confirmed: `.venv/bin/mypy` and `.venv/bin/pytest` name `/mnt/projects/software_projects/tracks-and-trails/.venv/bin/python` in their shebangs, one directory above this checkout. `.venv/bin/python -m ...` resolves this checkout's `src/tracks_and_trails`. This is machine state, not a defect in the submitted repository range. |

No reviewer regression was added: the retained test already asserts the accepted product behavior.
This review appended this record only. No submitted source, test meaning, decision, task state,
commit, remote ref or CI state was changed by the reviewer.

## 2026-08-05 — `T140-R3` focused correction re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `5b8ebfa`
**Correction head:** `9de7204` (`2e0837e` adds the committed handoff)
**Verdict:** **Changes requested.** The group editor and inheritance effect were already implemented
and the submitted proof is sound, but one part of the original High finding remains: a common
built-in is displayed on the playlist header as raw yt-dlp selector syntax rather than by the
preset name offered by that header's editor. `T137-R2` and `T140-R5` remain outside this pass.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `T140-R3` | High | **Yes — accepted UX-005 row 13** | The handoff is right that the finding's status lagged part of the tree: `f74de02`, now an ancestor of the submitted base, added `PRESET_CHOICES_ROLE`, editable group flags, and `_Group` handling in `setData()`. The two submitted tests prove that one group choice emits the same preset for every retargetable member, excludes a completed member, and refuses a write when no member can move. However, the original re-review also recorded that `_group_data(SELECTOR_ROLE)` renders a common built-in as its raw selector instead of `_effective_format_text()`'s preset name. That code is unchanged: members using `Best video available` produce `Download as: bestvideo+bestaudio/best`. The earlier regression asserted only a nonempty string and could not catch this. | **Open — inheritance effect proved; display half remains** |

### Submitted uncertainties and merge audit

- **`not movable`: equivalent redundancy confirmed.** For an empty `movable`, `all(...)` is true,
  so deleting the explicit empty check does not change the result. Leaving the simplification out
  of this correction is appropriate.
- **Same-value guard: not a blocker for this submitted proof, but testable without teaching
  `FakeQueue` to apply writes.** Members can be constructed with one built-in request before the
  view is built, then `setData()` can be called with that already-current preset name. Existing
  individual-row lifecycle coverage proves the underlying `T126-R3` recursion class; the group
  branch should gain the direct no-emission case when this finding returns with its display fix.
- **Merge audit confirmed.** `f74de02` is an ancestor of the submitted base. Of its ten touched
  files, only `ai/DECISIONS.md`, `tests/ui/test_queue_view.py` and
  `tests/ui/test_row_verb_wiring.py` differ at the reviewed head, and each contains later work.
  The other seven are byte-identical. `main_window.py` was not part of `f74de02`; the repolish came
  from `d929d98` on the other merge line, so the corrected attribution in the handoff is accurate.

### Independent verification

| Check | Result |
|---|---|
| Submitted boundary | `5b8ebfa..9de7204` changes only `tests/ui/test_queue_view.py`; `git diff --check`: **pass**. |
| Submitted T140-R3 tests | **2 passed** after restoring the mutation probe. |
| RETARGETABLE mutation | Replaced the filtered member list with all group members: **2 failed**, one by emitting for completed `entry-0`, one by accepting a fully finished playlist. The source diff was empty after restoration. |
| Queue-view test file with reviewer regression | **49 passed, 1 failed**. The sole failure is the common built-in display: actual `Download as: bestvideo+bestaudio/best`, expected `Download as: Best video available`. |
| Lint | `.venv/bin/python -m ruff check .`: **pass**. |
| Format | `.venv/bin/python -m ruff format --check .`: **pass**, 162 files already formatted. |
| Source types | `.venv/bin/python -m mypy src`: **pass**, 44 source files. |
| Test-inclusive types | `.venv/bin/python -m mypy`: **pass**, 107 source files. |
| Windows type route | `.venv/bin/python -m mypy --platform win32`: **pass**, 107 source files. |

This review added one failing regression to `tests/ui/test_queue_view.py` and appended this record.
The temporary source mutation was fully reverted. No submitted source, submitted test meaning,
decision, task state, commit, remote ref or CI state was changed by the reviewer.

## 2026-08-05 — criterion 8 remaining findings focused re-review

**Reviewer:** Codex (Reviewer)
**Correction base:** `965a336`
**Implementation head:** `405139f` (`191292c` adds the committed handoff)
**Verdict:** **Changes requested.** `T140-R3` and `COORD-R22` are resolved, and the implemented
parts of `T137-R2` and `T140-R5` are real. A restart path still bypasses the new probe session,
however, group retry defeats the permanent DRM non-retry boundary, and the durable-continuation
regression leaves a live Qt thread. `Pause all` also remains blocked on the maintainer ruling the
handoff correctly requests.

### Finding status

| ID | Severity | Blocks approval | Re-review result | Status |
|---|---|---:|---|---|
| `T140-R3` | High | No | A common built-in is now rendered through `_effective_format_text()`, so the header says `Download as: Best video available`, matching its editor. The group remains editable, a choice reaches every retargetable member and excludes the completed member, re-choosing the current preset emits nothing, and a different choice still emits. | **Resolved** |
| `T137-R2` | High | **Yes — T-137 / UX-003 / ARC-009** | The live add-dialog route now admits `QUEUED` entries as `PROBE`, and the manager correctly continues a durable successful probe into `DOWNLOAD` while excluding staging probes. Startup does not preserve that distinction: `queued_job_ids()` returns bare ids for both `QUEUED` and `READY`, and composition admits every id with the default `DOWNLOAD`. If the process exits after the durable playlist rows land but before the add callback admits their probes, restart takes the new `QUEUED` rows directly down the download route. The reviewer restart regression reaches `RUNNING` with the title still `None`; a probe-first restart would persist `A video that exists`. | **Open — partially corrected** |
| `T140-R5` | High | **Yes — accepted T-140 criterion** | Right/Left disclosure, group Cancel all / conditional Retry failed / Show in folder / Remove, ordinary-row routing, and one count-bearing removal confirmation are implemented and their submitted regressions pass. `Pause all` remains absent. The handoff correctly establishes a conflict with accepted `UX-001`, which removed per-job pause and `JobStatus.PAUSED`; neither implementer nor reviewer may silently choose among waiting for REQ-017, amending UX-005/T-140, or reopening UX-001. | **Blocked — maintainer disposition required** |
| `COORD-R22` | Medium | No | The hidden hover work was separated, retrospectively filed as T-147 after its id collision was disclosed, and the reviewer record was separated from source. This submitted range names every commit and file in its range table, keeps `ai/REVIEWS.md` out of the implementation, and identifies `191292c` as handoff-only. The header's “seven files” count is a non-blocking arithmetic error—the table names all nine implementation files and the exact SHAs leave the boundary unambiguous. | **Resolved** |

### New correction-round findings

| ID | Severity | Blocks approval | Finding | Recommendation | Status |
|---|---|---:|---|---|---|
| `T140-R6` | **Critical** | **Yes — SEC-001 / REQ-EXCL-001** | Group retry is derived from `JobStatus` alone. A playlist containing only `FAILED` / `DRM_PROTECTED` jobs offers `Retry failed`, and `_on_group_verb()` emits retry for both. Ordinary rows call `is_retryable(error_kind)`; the group route bypasses that guard even though SEC-001 says DRM is permanent and **never retried**. Two reviewer regressions fail independently: one on the offered verb and one on a stale/direct group action, which emits `entry-0` and `entry-1`. This defeats a documented non-negotiable safety boundary, so AGENTS.md §10 makes it Critical. | Derive the group offer from the member jobs and `is_retryable()`, not statuses alone. Apply the same failed-and-retryable filter in the route so a stale menu action cannot bypass the hidden verb. Audit mixed retryable/non-retryable failures and retry only the eligible members. | **Open** |
| `T137-R3` | **Medium** | **Yes — required relevant test** | `test_a_durable_probe_carries_the_job_on_into_its_download` stops at `RUNNING` and calls asynchronous `shutdown()` without driving the manager to idle. In isolation it prints `1 passed` and exits **134** with `QThread: Destroyed while thread '' is still running`; outside the sandbox the complete manager file likewise prints `143 passed` and exits 134. A later integration test can pump the leaked lifecycle and conceal it in the reported full-suite result, so this regression is not isolated and its own file is not a passing command. | Use the manager fixture that drains shutdown, or explicitly spin through `download.is_idle` after `shutdown()`. Re-run the manager file as its own process and require exit zero. | **Open** |

### Submitted uncertainties and maintainer ruling

- **Staged-guard uncertainty resolved.** The submitted test passes normally. Temporarily deleting
  only `if not self.is_staged(job_id)` makes it fail on the queued staged id exactly as described;
  the manager source was restored byte-for-byte afterward.
- **`Pause all` conflict upheld.** The omission cannot be approved against the current T-140
  criterion, but implementing it without a ruling would reopen accepted queue semantics. The
  maintainer must select and record one of the handoff's three dispositions.
- **ARC-009 is coherent but incompletely applied.** The manager is the right owner for the
  continuation. Composition still owns startup admission and must retain enough status/kind
  information to enter that same contract after a restart.
- **`P2EXIT-R10` remains outside this correction range.** Criterion 8 cannot be marked met while
  these blockers remain; the document/evidence finding is not otherwise re-reviewed here.

### Independent verification

| Check | Result |
|---|---|
| Boundary | `git diff --check 965a336..191292c`: **pass**. Four implementation commits change nine files; `191292c` adds the tenth, the handoff. The handoff's range table is complete despite its incorrect “seven files” header count. |
| Submitted T140 routes | **13 passed** across group format, retargeting, keyboard disclosure, group verbs, group removal and ordinary-row routing. |
| Queue-view file with reviewer DRM regressions | **58 passed, 2 failed**. The failures independently prove the forbidden offer and route. |
| T137 staged guard | **1 passed** normally; deleting the guard produces the expected **1 failed** on `_waiting`. The mutation was fully restored. |
| T137 durable continuation test | Assertion reports **1 passed**, but the command exits **134** because its QThread is still running. Full `test_manager.py` outside the socket sandbox reports **143 passed** and also exits 134. |
| Reviewer restart regression | **1 failed**: the restarted playlist entry reaches `RUNNING` with `title=None` instead of the probed title. |
| Lint / format | `ruff check .`: **pass**. `ruff format --check .`: **pass**, 163 files. |
| Types | `python -m mypy src`: **pass**, 44 files; bare mypy and win32 mypy: **pass**, 107 files each. |
| Environment disclosure | Confirmed again: `.venv/bin/mypy` has a dead shebang one directory above the checkout. `python -m mypy` succeeds. This is machine state, not a repository finding. |
| Submitted full suites | Implementer reports unit + UI **1854 passed / 11 skipped** and integration **306 passed**. The reviewer did not reproduce the whole union; the manager-file exit defect explains how later integration tests can mask the leaked thread. |

### Disposition

Return one correction batch that preserves status when admitting the startup queue, applies
`is_retryable()` to both group-verb presentation and routing, and makes the new manager regression
terminate cleanly. Separately, the maintainer must rule on `Pause all`; until then `T140-R5` and
criterion 8 remain open. Because a Critical and a High defect remain, focused correction and
independent verification continue under AGENTS.md §10 despite the ordinary two-pass budget.

This review added two failing DRM regressions to `tests/ui/test_queue_view.py`, one failing restart
regression to `tests/integration/test_composition.py`, and appended this record. The temporary
manager mutation was fully reverted. No submitted source, submitted test meaning, decision, task
state, commit, remote ref or CI state was changed by the reviewer.
