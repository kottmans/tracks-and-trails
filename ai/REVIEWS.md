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
