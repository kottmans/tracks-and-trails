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

## Open findings

- `T005-R1`, `T005-R2`, `T005-R3` — tracked by `T-024`
