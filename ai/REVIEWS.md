# REVIEWS.md — Tracks & Trails

**Purpose:** Record code review, QA, and readiness findings and their evidence.
**Authority:** Canonical for review evidence and finding status. Historical record — append, never rewrite.
**Owner:** Reviewer (Codex)
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-26
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
**Base:** `e131a7fb9065a19b7184a5b6b8d41b2b049be8c9`
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
**Base:** `947db1a9aa40e2c6ffadb448ca195c384bf68c02`
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
| `git diff --check 947db1a 8db0518` | Passed. |

### Readiness

The CI gate proof is real, both Windows carries are discharged, and no product or security
blocker was found. PR #1 is not ready to merge until `T-023` closes the two evidence/current-
truth findings and receives focused re-review. After approval, prefer a squash merge so the
deliberately broken gate-proof commits do not enter `main`; published branch history must not
be rewritten.

## 2026-07-25 — T-023 focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-023`; re-review of `T006-R1`, `T006-R2`
**Base:** `947db1a9aa40e2c6ffadb448ca195c384bf68c02`
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
| `git diff --check 947db1a 24d926d` | Passed. |

### Readiness

The retention mechanism and the `TASKS.md` carry correction are verified, but PR #1 is not
ready to merge while `T006-R1`'s explicit documentation requirement remains unmet. After the
four stale descriptions are corrected and focused re-review approves them, prefer a squash
merge so the deliberate gate-proof commits do not enter `main`.

## 2026-07-25 — T-005 layering enforcement test

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-005`
**Base:** `00b610f3a48ac280b8ca77841746bb20f1786b28`
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
| `git diff --check 00b610f 655f53d` | Passed. |

### Readiness

The analyzer catches real violations, the AST walk is sound for ordinary imports, and the
Linux/Windows evidence is genuine. PR #2 is not ready to merge because the analyzer can still
be weakened around its synthetic samples while remaining fully green. `T-024` tracks the
three open corrections; focused re-review is required before merge.

## 2026-07-25 — T-024 focused re-review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-024`; re-review of `T005-R1`, `T005-R2`, `T005-R3`
**Base:** `00b610f3a48ac280b8ca77841746bb20f1786b28`
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
| `git diff --check 00b610f d6af9d9` | Passed. |

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
**Base:** `606a50dbac412c20da87d2bdc5646ad6b9340213`
**Head:** `2d06153b3a3a571ad66cf0e1284c4b9cd74cd673`
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
| Local and CI lint, format, types, tests | **Met with an evidence-access caveat.** Current local checks pass. Retained Windows check evidence passes at the T-007 code boundary, retained Windows frozen evidence exercises the only later source addition, and only documentation changed after `ae30e77`. The local `gh` credential is expired, so the reviewer could not freshly query the final `2d06153` run. |
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
| Working boundary | Started at clean `main` `2d06153`; base/head diff is 67 files, 3,370 insertions, 145 deletions. Review mutations were restored by SHA-256; only this review's coordination edits remain. |
| `git diff --check 606a50d 2d06153` | Passed. |
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
**Base:** `2d06153b3a3a571ad66cf0e1284c4b9cd74cd673`
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
| `git diff --check 2d06153..67da109` | Passed. |
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
**Base:** `4a2a1e6bc1720a2085146e363d7612503cf07989`
**Head:** `e2becc0f1153f9fca078c9ed10e8955eb5bc1b2f`
**Implementation commit:** `ad4d7686158d92c4072ec0469003eef214d61765`
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
| Bounded review | Clean `main` at exact head `e2becc0`; base/head diff is 17 files, 2,020 insertions and 151 deletions. |
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
| `git diff --check 4a2a1e6..e2becc0` | Passed. |

### Readiness

The production transition relation and taxonomy are substantively sound, but `T-010` is not
ready for dependent Phase 1 work while its mandatory state-machine gate can be weakened by
adding illegal edges. Fix `T010-R1` and the mutable IPC record, reconcile the two task-contract
wordings, then perform a focused re-review.

## 2026-07-26 — T-026 real Windows desktop verification

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-026`; accepted `OPS-004`
**Base:** `4a2a1e6bc1720a2085146e363d7612503cf07989`
**Head:** `e2becc0f1153f9fca078c9ed10e8955eb5bc1b2f`
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
| `T026-R5` | **Low** | Current truth / coordination | The changed coordination set remains internally stale. `TESTING.md` still says the suite is near-empty and only one §7 area is covered, and its §12 Windows paragraph still says real keyboard and screen-reader behavior are wholly unverified under superseded `OPS-003`. `TASKS.md` files both implemented, awaiting-review tasks under `Ready` while `In Review` is empty. `STATUS.md` gives the review head as `4172fd0` rather than `e2becc0` and retains the nonexistent `/mnt/storage/...` repository path. | Reconcile the status note, §12, task headings, exact review boundary, and repository path after the functional gates are corrected. | Open |

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
**Base:** `e2becc0f1153f9fca078c9ed10e8955eb5bc1b2f`
**Head:** `918c50c9a06daed854f347b94202b4d4b2d096d2`
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
| Correction boundary | Clean `main` at exact head `918c50c`; correction diff is 12 files, 1,023 insertions and 334 deletions. All temporary mutations were restored. |
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
| `git diff --check e2becc0..918c50c` | Passed. |
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
**Base:** `db8ab66fcf4c90d93a12390baed0756b1bf42a75`
**Head:** `6663c9ea2ddc1b3f9a0aac601827c928c2a06be9`
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
| Review boundary | Clean `main` at exact head `6663c9e`; `db8ab66..6663c9e` is one commit touching 3 files, with 497 insertions and 2 deletions. |
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
| `git diff --check db8ab66..6663c9e` | Passed. |
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
**Base:** `6663c9ea2ddc1b3f9a0aac601827c928c2a06be9`
**Head:** `8fbbb2d439f4041f235deb193d57ad0af00bffac`
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
| Correction boundary | Clean `main` at exact head `8fbbb2d`; `6663c9e..8fbbb2d` is two commits and 6 files, with 797 insertions and 297 deletions. Commit `90abde5` records the prior review unchanged; the implementation correction is `90abde5..8fbbb2d`, 5 files. |
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
| `git diff --check 6663c9e..8fbbb2d` | Passed. |
| Windows CI | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30213417231` with all five jobs green. |

### Readiness

T-011 is not approved at `8fbbb2d` and should not unblock T-035 or T-038. The two original
High-level design failures are substantially corrected, and R1, R3, R4 and R6 are closed.
Strict runtime validation remains incomplete under R2, the advertised probe grammar is not
fully enforced, and R5 still requires the maintainer to interpret or supersede `ARC-002`.
This is the requested last review pass: these are the final reviewer dispositions at this
head, and no additional Codex re-review is implied.

## 2026-07-26 — T-011 post-final correction verification

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-011`; verification of reopened `T011-R2` and new `T011-R7`
**Base:** `8fbbb2d439f4041f235deb193d57ad0af00bffac`
**Head:** `83c7d4e84df42ddacd7c83debb03ffd6bb2d7f4a`
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
| Correction boundary | Clean `main` at exact head `83c7d4e`; `8fbbb2d..83c7d4e` is two commits and 5 files, with 271 insertions and 20 deletions. Commit `7fb6c6a` records the prior review; the correction itself is one commit, `83c7d4e`, touching 4 files. |
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
| `git diff --check 8fbbb2d..83c7d4e` | Passed. |
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
**Base:** `766c4ba651a4f687c0291385ba801695a21e7d81`
**Head:** `fa62d9789e1e817b33d819b1cb051235452afd8c`
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
| Review boundary | Clean `main` at exact head `fa62d97`; `766c4ba..fa62d97` is one commit touching 4 files, with 346 insertions and 24 deletions. All review mutations were restored. |
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
| `git diff --check 766c4ba..fa62d97` | Passed. |
| Windows CI | Not independently checked: `gh auth status` reports the configured token invalid. The handoff reports run `30215562522` with all five jobs green. |

### Readiness

T-041 is not approved at `fa62d97`, and `T011-R8` should not yet be recorded as fully closed.
The direct raw-format-dictionary defect is fixed, the collection normalization strategy is
sound, and the field audit is useful for known models. Approval still requires restoring the
non-optional Job invariants, making the model-set guard independent, closing declared-model
subclass bypasses, and aligning the documented exception contract. Coordination can then
reflect the independently verified result.

## 2026-07-26 — T-041 focused correction re-review (final)

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-041`; carried finding `T011-R8`
**Re-review base:** `fa62d9789e1e817b33d819b1cb051235452afd8c`
**Head:** `c693ec6da74004e37fbc92d5c7f84ffbcbba1a47`
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
| Correction boundary | Clean `main` at exact head `c693ec6`; `fa62d97..c693ec6` is the advertised two commits and five files. Commit `4ef32fa` records the first review; `c693ec6` contains the four-file correction. All reviewer mutations were restored. |
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
| `git diff --check fa62d97..c693ec6` | Passed. |
| CI `30216176642` | Independently verified successful at exact head `c693ec6`; all five jobs green. |

### Readiness

T-041 is approved at `c693ec6`, and the functional `T011-R8` payload/immutability defect is
independently verified closed. The task is ready for the implementer or maintainer to move to
Complete. Per the explicit final-pass instruction, `T041-R6` is carried into the next Phase 1
implementation and does not request another T-041 re-review.

## 2026-07-26 — T-034, T-035, T-042 and T-043 initial review

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-034`, `T-035`, `T-042`, `T-043`; carried finding `T041-R6`
**Review base:** `352f887726352a7b32198dd820792ee50ddba176`
**Head:** `666c4be1edd0cb5a54727ec6b30104b0beca27aa`
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
| Review boundary | `352f887..666c4be` contains **7**, not the handoff's stated 8, commits and 9 changed files. The two disclosed broken intermediate commits were inspected as history; approval is assessed only at the clean head. Current local HEAD is later at `8cb14d6`, whose only changes after the review head are the two explicitly excluded `AGENTS.md` commits; source and tests match `666c4be`. |
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
| `git diff --check 352f887..666c4be` | Passed. |
| CI `30218288265` | Independently verified successful at exact head `666c4be`; all five jobs green. |
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

`T-042` and `T-043` are approved at `666c4be` and can move to Complete without waiting for the
other two tasks. `T-034` and `T-035` are not approved and do not yet unblock `T-012`. Their
remaining standard budget is one focused correction re-review covering the findings above and
regressions introduced by their corrections; it is not another unbounded audit. The
Implementer should return all blocking corrections in one batch with failing regressions and
mutation evidence, then update the coordination documents.

## 2026-07-26 — T-034 and T-035 focused correction re-review (final standard pass)

**Reviewer:** Codex (Reviewer)
**Task(s):** `T-034`, `T-035`; non-blocking coordination finding `P1-R1`
**Re-review base:** `666c4be1edd0cb5a54727ec6b30104b0beca27aa`
**Head:** `51e37f0987f4effd974b223a0acc2879ef8f08a3`
**Functional correction diff:** `08787ff..51e37f0` — one commit, six files
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
| Correction boundary | Clean `main` at exact head `51e37f0` before reviewer documentation. `666c4be..51e37f0` contains the two previously excluded `AGENTS.md` commits, the committed initial review, and correction commit `51e37f0`; the functional correction is the one-commit `08787ff..51e37f0` diff. |
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
| `git diff --check 666c4be..51e37f0` | Passed. |
| CI `30219285036` | Independently verified successful at exact head `51e37f0`; all five jobs green. |
| Worktree after mutations | All temporary source/test mutations were restored. The only local changes are this reviewer-owned entry and the `T-044` follow-up in `ai/TASKS.md`. |

### Readiness and exhausted budget

`T-035` is **Approved with follow-ups** at `51e37f0`; it can move to Complete, and `T-044`
owns the two Low carry-forwards. `T-034` remains **Changes requested**, so `T-012` remains
blocked on path safety.

This was the one focused re-review allowed by the Standard budget. The review found a direct
continuation of R2 and a regression introduced by the R4 correction, both against T-034's
acceptance boundary. No further implementer/reviewer loop is implied or authorized. The
maintainer must choose: authorize one additional focused pass, accept the two risks, change
the acceptance scope, or carry the work forward under a new task and approve T-034 with that
explicit exception.
