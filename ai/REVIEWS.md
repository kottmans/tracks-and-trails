# REVIEWS.md — Tracks & Trails

**Purpose:** Record code review, QA, and readiness findings and their evidence.
**Authority:** Canonical for review evidence and finding status. Historical record — append, never rewrite.
**Owner:** Reviewer (Codex)
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-07-25
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
