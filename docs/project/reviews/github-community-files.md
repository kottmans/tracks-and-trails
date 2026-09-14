# GitHub community files, installation and page artwork

**Purpose:** Independent review of community files, source installation, page artwork and their integration.
**Owner:** Reviewer
**Last updated:** 2026-09-14
**Update when:** This scope receives a review, correction verification or disposition update.

## 2026-09-14 — Initial review

**Reviewer:** Codex, independent of implementer Claude Code
**Task:** None — direct maintainer request for installation instructions and GitHub community files.
**Round:** Initial comprehensive review
**Base:** `a305d0bafd7674135bb164b6fab1c9c266c7fe2c`
**Head:** `5f540c0f79e1cbe8f377633ec35919a6032dc2ee`
**Platforms verified:** Fedora 44 x86-64, Python 3.14.7; installation and CLI checks only.
**Verdict:** **Approved** — no blocking findings. Two Low corrections are routed below;
they do not require a separate task or keep this scope in review (TESTING §14).

### Scope and authority

Reviewed both implementation commits, `6c85a38` and `5f540c0`, in full: **seven changed files**
(README, CONTRIBUTING, CODE_OF_CONDUCT, three issue-template YAML files, and the PR template).
Also checked the already-live repository description through the GitHub API. Source, tests and
workflows are unchanged in this range.

Applied [AGENTS](../../../AGENTS.md), [review and validation policy](../TESTING.md#14-review-policy),
[STATUS](../STATUS.md), [T-328](../TASKS.md#t-328--the-first-release),
[requirements](../REQUIREMENTS.md) (`REQ-024`, `REQ-029`, `REQ-EXCL`),
[decisions](../DECISIONS.md) (`SEC-001`, `OPS-001`, `OPS-011`, `REL-001`),
[architecture](../ARCHITECTURE.md) and [SECURITY](../../../SECURITY.md).
The source-install instructions describe the present unreleased state; they do not discharge
REQ-029 or T-328's release-download instructions.

### Findings

| ID | Severity | Blocks approval | Finding and evidence | Disposition/status |
|---|---|---|---|---|
| GITHUB-R1 | Low | No | **Qualify diagnostic commands for the unactivated virtual environment.** The new install steps deliberately use `.venv/bin/…` or `.venv\Scripts\…` without activation, but README:120, CONTRIBUTING:39 and the bug form's version/log hints give bare `tracks-and-trails` commands. After a fresh non-editable install, `tracks-and-trails --help` in a clean shell exits **127**, while `.venv/bin/tracks-and-trails --help` exits **0**. Explain that source users append these options to the platform-specific launcher, or give the qualified commands. Installation and qualified CLI commands work; this is a diagnostic-instruction clarity gap. | **Open.** Documentation Maintainer: current documentation completion sync, or T-328's existing README refresh with mechanically matching reporting hints. No separate task. |
| GITHUB-R2 | Low | No | **Name the complete ffmpeg settings route.** README:112 says “in Settings”; `ui/main_window.py:1983–1986` defines **Settings → Preferences…**, and `ui/settings_dialog.py:523` titles the dialog **Preferences**. This wording predates the range but is retained in the rewritten install section. Change it to “Settings → Preferences…”. The inspected `origin/main` README still has the old ffmpeg sentence; its “Preferences” mention belongs to the new update-check bullet, so integration alone will not fix this. | **Open.** Documentation Maintainer: the same completion sync, or T-328's existing README refresh. Non-blocking, pre-existing wording; no separate task. |

### Checks run

| Check and scope | Actual result |
|---|---|
| `git diff a305d0b..5f540c0 --check`; full diff and commit metadata inspection | Pass; seven changed files, no source/test/workflow changes. Both commit identities name Sean Kottman. |
| `python3 tools/commit_message_check.py --range a305d0b..5f540c0` | Pass: **2 commits checked**. |
| Fresh temporary local clone detached at the full reviewed head; `python3 -m venv .venv`, `.venv/bin/python -m pip install --upgrade pip`, `.venv/bin/python -m pip install .` | Pass. Installed `tracks-and-trails 0.1.0.dev0`, PySide6 **6.11.2**, yt-dlp **2026.8.19**, platformdirs **4.11.8**, truststore **0.10.4**, pip **26.2.1**. Import resolves to the new venv's `site-packages`; `direct_url.json` has no editable flag. Used an isolated temporary pip cache. |
| Installed `.venv/bin/tracks-and-trails --version` and `--help`, with config/data/cache redirected under the temporary directory | Both exit **0**; version is **0.1.0.dev0**, help names the isolated log path. Bare-command negative control exits **127** as recorded in GITHUB-R1. No GUI launch is claimed. |
| Relative links and heading anchors in README, CONTRIBUTING and CODE_OF_CONDUCT | Pass: **46** local links resolved. |
| New review links and index preservation | Pass: **9** local links/anchors; removing the added index row and reverting its metadata date recovers the previous index bytes exactly. Reviewed implementation files remain unchanged. |
| All three issue-template YAML files, parsed with `yaml.safe_load`; form keys/types inspected against GitHub's schema | Pass: bug form **11 inputs**, feature form **4 inputs**, unique IDs/labels, string dropdown options, boolean validation/checkbox requirements; blank issues enabled and **2** contact links. This is local validation, not GitHub rendering evidence. |
| Read-only `gh api` calls for repository metadata, private vulnerability reporting, labels and collaborators | Public repository, default branch `main`; description exactly **“A desktop GUI for yt-dlp, for Linux and Windows.”**; reporting `enabled: true`; `bug` and `enhancement` labels exist; only listed repository collaborator is `kottmans`, role `admin`. Initial sandbox network attempt failed; the permitted network retry succeeded. No settings were changed. |
| Official Contributor Covenant 2.1 Markdown comparison, removing upstream TOML front matter | Only the Enforcement contact paragraph differs. Pledge, standards, enforcement ladder and attribution are preserved. |
| `rg` inspection of documentation consumers; existing workflow parser over `.github/workflows/*.yml` | No executable test/tool consumer of the changed community/README files found. **All 8 workflows** lack `pull_request` and `pull_request_target` events. CI ignore paths do not include the new community files. |
| Source inspection of entry point, platformdirs storage and ffmpeg settings route | Console entry point matches the documented launcher. Default settings, database and log paths are outside the clone. Menu/dialog spelling confirms GITHUB-R2. |
| Windows package manifests and Python launcher documentation | The inspected Python **3.14.7** manifest declares `py` and PATH configuration; the inspected Gyan.FFmpeg **8.0** manifest declares `ffmpeg`/`ffprobe` portable aliases. These support the commands' intent, not their runtime success on Windows. |
| Fedora `f44` ffmpeg build specification and codec allowlists, fetched during review | Spec identifies **8.1.2-4**; restricted build uses explicit allowlists containing AAC/libfdk_aac and libmp3lame encoders, AAC/MP3 decoders, and relevant image codecs. No evidence that the stated merge/audio/thumbnail needs require rejecting `ffmpeg-free`; this is build-configuration evidence, not a media-operation test. |

The relative-link and form checks were one-off review probes; no test files were added.
No application suite, Ruff/mypy run, Windows execution, package-manager installation, actual
download/conversion, or end-to-end GUI test was run. Documentation-only validation applies
under TESTING §3; this is not a release review.

### Reporting, scope and CI judgments

**The maintainer's chosen conduct-report route is acceptable for this scope.** Private reporting
is enabled, and GitHub's [reporting documentation](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately)
says the reporter form needs only a title and description. A conduct report can therefore be
submitted without inventing vulnerability metadata; the title prefix distinguishes it.
This is a project use of a vulnerability-reporting channel, not a GitHub endorsement of that use.
No report or message was submitted during review. GitHub's
[advisory permissions](https://docs.github.com/en/code-security/reference/permissions/repository-security-advisory)
allow repository administrators and added advisory collaborators access, and the reporter also
retains access. The “only the maintainer” wording describes the currently verified project
recipient, not an immutable GitHub access restriction. Reassess it if project access changes.

**The README status correction is within the authorized documentation scope.** It agrees with
STATUS, grants no phase sign-off, and says no release is published. T-328 still owns the tagged
release, download instructions and AppImage menu guidance. The PR template agrees with the
existing outside-contribution policy and CI trust boundary. Private advisory collaboration does
not create a public fork-PR CI trigger.

**Leaving CI exclusions unchanged is acceptable.** Adding the new files to `paths-ignore` would
be a separate coverage decision under OPS-011. They currently cause full CI on push; this is
extra work, not missing validation. No workflow edit is requested by this review.

The Debian/Ubuntu commands are conditional on the stated Python 3.14+ prerequisite. They do not
provide a complete way to obtain that interpreter on distributions with an older default, and
were not executed there. Likewise, Windows install/start behavior and GitHub's rendered forms
remain unverified. These limitations do not imply a failed installation or a release-gate pass.

External references inspected: [GitHub form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema),
[issue-form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms),
[Contributor Covenant 2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/),
[Python winget manifest](https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/p/Python/Python/3/14/3.14.7/Python.Python.3.14.installer.yaml),
[FFmpeg winget manifest](https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/g/Gyan/FFmpeg/8.0/Gyan.FFmpeg.installer.yaml),
[Python Windows documentation](https://docs.python.org/3.14/using/windows.html),
[Fedora build spec](https://src.fedoraproject.org/rpms/ffmpeg/raw/f44/f/ffmpeg.spec),
[encoder allowlist](https://src.fedoraproject.org/rpms/ffmpeg/raw/f44/f/enable_encoders), and
[decoder allowlist](https://src.fedoraproject.org/rpms/ffmpeg/raw/f44/f/enable_decoders).

### Readiness and coordination

Approval covers only the exact implementation range above and the read-only metadata observation.
At review start, local `main` was clean and **2 ahead / 2 behind** cached `origin/main`
(`d8576a999ba9e72abdd405eb8c800e8cd6b5936d`). Upstream T-338 and its Windows verification are
outside this review. During final checks, the cached remote advanced to
`39dab46599661d204fffe1bc59283fe7cbd6f3ff` (“Correct T-337's commit count”), making the
implementation head **2 ahead / 3 behind**. No merge, rebase, branch switch, fetch or push was
performed by this reviewer; the additional upstream commit is also outside scope.

This review adds this record and its [REVIEWS index](../REVIEWS.md) link only. No task was
created or closed, no STATUS rewrite was required within reviewer ownership, and the ignored
handoff remains untracked. The review-document commit is distinct from the approved head.

## 2026-09-14 — Corrections verified; logo and merge reviewed

**Reviewer:** Codex, independent of implementer Claude Code
**Task:** None — direct maintainer requests for the GitHub page and the correction check.
**Round:** Focused verification of GITHUB-R1/R2; initial review of the new artwork and merge.
**Platforms verified:** Fedora 44, Python 3.14.7, PySide6 6.11.1; live GitHub in headless Chromium
151.0.7922.34 with a fresh, signed-out profile.
**Verdict:** **Approved** for each boundary below. GITHUB-R1 and GITHUB-R2 are resolved;
one new Low documentation finding does not block or create a follow-up task.

### Exact boundaries

| Scope | Reviewed revisions |
|---|---|
| Diagnostic-command and Preferences corrections | `90126e5c43713b275f380d69b34f96adad2c280d` → `9a77d9dc62f1d039795893564fe480c13b08bc44` |
| Initial logo and social-preview implementation | `9a77d9dc62f1d039795893564fe480c13b08bc44` → `caf67fcbe36e4c361f46b04f763b49b51df994db` |
| Integration | Merge `6aaca43e7a3f4077092dc78e9af6a9156aeed746`, parents `caf67fcbe36e4c361f46b04f763b49b51df994db` and `39dab46599661d204fffe1bc59283fe7cbd6f3ff`; merge base `a305d0bafd7674135bb164b6fab1c9c266c7fe2c` |
| Cropped, larger logos and requested sentence removal | `6aaca43e7a3f4077092dc78e9af6a9156aeed746` → `fcdaf79a1a651e66619a1303d03d49d49712cf9c` |

Upstream commits `f29a542`, `d8576a9` and `39dab46` are outside implementation review. Integration
verification checks their preservation, not their design or correctness. Both artwork diffs were
read; image reproduction and live-page checks cover the final `fcdaf79` assets.

### Findings and dispositions

These rows supersede the earlier Open dispositions without changing the initial review's evidence.

| ID | Severity | Blocks approval | Finding and evidence | Disposition/status |
|---|---|---|---|---|
| GITHUB-R1 | Low | No | README now explains the unactivated venv and gives both launcher paths. CONTRIBUTING and the bug form give qualified `--help` commands; the version field offers Help → About and both qualified `--version` commands. YAML parsing preserves the single Windows backslashes. In the prior fresh non-editable installation, the qualified Linux commands still exit **0**, and the bare-command control exits **127**. Source and the entry-point declaration are unchanged across the correction. | **Resolved at `9a77d9d`**, independently verified; retained at `fcdaf79`. Windows execution is not claimed. |
| GITHUB-R2 | Low | No | README names **Settings → Preferences…**, matching the menu and dialog. The actual merge and final head each have exactly one ffmpeg-location sentence, with this corrected route; neither restores “Running it”. | **Resolved at `9a77d9d`**, independently verified and preserved through `6aaca43`/`fcdaf79`. The initial integration observation is superseded by the corrected parent and actual merged tree. |
| GITHUB-R3 | Low | No | **Describe the opaque preview as a project choice.** `tools/icons/render_github_art.py:14–16` says GitHub wants an opaque image. GitHub explicitly supports transparent PNG previews and recommends 1280×640 for best display. The rendered sand card works; its documentation gives the wrong reason for opacity. See [GitHub's preview guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview). | **Open.** Implementer / Documentation Maintainer: correct the docstring in the current artwork completion sync, or the next existing documentation completion pass. No asset change or separate task is required. |

### Artwork and policy judgments

**The sand social card is acceptable.** The [pack](../../../tools/icons/masters/PACK-README.txt)
says “Do not flatten the PNGs onto a background
colour”, and also instructs placing OnLight art on light grounds. My interpretation is that the
first rule protects the reusable logo exports; it does not prohibit composing the vector mark
onto a complete page/card. Here the SVG and transparent logo exports remain intact, while a
separately named social-preview image combines the vector, a light ground and text. That is
consistent with the maintainer's already chosen installer panel and the specific preview they
uploaded. No additional approval is needed for the selected composition. This is a bounded brand
usage judgment, not permission to replace the transparent logo exports with opaque tiles.

**The OnDark derivation is acceptable.** The vendored Icon SVG has exactly the two published
Brand-OnLight fills. XML comparison shows the substitution changes only `#1E5E47` to the
published Brand-OnDark `#48906C`; `#D9A24C`, geometry, transforms and other attributes remain
unchanged. The pack gives those colour values and consistent geometry within a cut. The result
implements an existing colourway. Byte identity to the absent original OnDark SVG is not claimed
or needed for this bounded derivation.

**The requested README deletion is presentation only.** It removes a sentence, not a capability
or requirement. AGENTS and REQUIREMENTS still correctly state the approved video/audio scope;
the README contains no contrary statement. The instruction named the README, so no canonical
product-scope edit is owed.

**No new renderer test is required for this change.** These are static promotional assets,
outside the application's runtime resources. Actual regeneration, independent colour/alpha/space
checks, link checks and browser inspection give proportionate evidence. A permanent font-sensitive
PNG snapshot would add environment coupling without establishing visual quality. The current
application-resource tests do not cover `docs/assets/`, and this review does not claim they do.
The older helpers' five type errors below are pre-existing; no adjacent repair is requested here.

### Checks and actual results

| Check | Result |
|---|---|
| Merge-parent tree comparison | **Pass.** README is the only path changed on both sides. Every other merged tree entry, including mode/blob and deletions, exactly matches the appropriate parent. The first-parent README added/removed lines exactly match the upstream README delta. Corrected installation and reporting guidance, prior review bytes, and all upstream changes survive. |
| `git diff 90126e5..fcdaf79 --check`; commit-message check over the same range | **Pass**; **7 commits** checked for message policy, including the three upstream messages without reviewing their implementation. |
| README, CONTRIBUTING, CODE_OF_CONDUCT links; corrected bug-form values | **Pass:** **48** relative Markdown links/anchors and HTML image paths; both version/log descriptions retain the correct qualified commands and literal Windows backslashes. |
| Renderer executed from an isolated `git archive fcdaf79 tools/icons` under `/tmp`, using the project interpreter and `QT_QPA_PLATFORM=offscreen` | **Pass:** all three PNG outputs match the committed bytes exactly. Repository assets were not overwritten. |
| Independent PNG inspection | Both logos are **750×938**, transparent. Counting every nonzero-alpha pixel gives bounds `(28,28)`–`(721,909)`: **694 px** ink width and **28 px** on each side, exceeding the **27.76 px** minimum. Preview is **1280×640**, opaque, **60,223 bytes**, corner colour `#F3EBDA`. The three images were visually inspected. |
| Live signed-out GitHub page, Playwright with Chromium | HTTP **200**. With `data-color-mode="auto"`, changing the browser preference **light → dark → light** switches `img.currentSrc` between the corresponding logo URLs and back. Background changes white → `#0d1117` → white; natural image size stays **750×938**, displayed **200×250**. Screenshots in both themes were inspected. This verifies the live automatic theme path, not every signed-in theme override or browser. |
| Public asset downloads and GraphQL preview metadata | **Pass.** Both logos return HTTP **200** and match the exact-head local assets. `usesCustomOpenGraphImage` is true; downloading `openGraphImageUrl` matches the committed preview byte-for-byte. No upload or repository setting was changed by this reviewer. |
| `.venv/bin/ruff check .`; `.venv/bin/ruff format --check .` | **Pass**; **416 files** already formatted. Ruff **0.16.3** and mypy **2.3.1** match the project pins. |
| `.venv/bin/python -m pytest -q tests/unit/test_resources.py tests/unit/test_appdir_metadata.py tests/unit/test_workflow_triggers.py` | **45 passed**, **0.19 s**. The first bare `pytest` attempt exited **4** before collection: its stale shebang selected the outer checkout's interpreter, which lacked platformdirs. The explicit project interpreter above resolves that environment mismatch. |
| Source types, Linux and Windows-platform analysis | Both **pass: 64 source files**. Initial ordinary `mypy src` failed with one missing `truststore` import because the project venv lacks that declared dependency. Re-ran `.venv/bin/python -m mypy --python-executable /tmp/tt-community-review-t84ifqc7/clone/.venv/bin/python src`, and the same command with `--platform win32`, using the prior fresh installation's declared runtime dependencies (including truststore **0.10.4**, PySide6 **6.11.2**). No dependency declaration or shared environment was changed. |
| Additional direct type check of `tools/icons/render_github_art.py` | **5 errors**, all in unchanged `render_icons.py`/`render_installer_art.py`: Qt `save` format-argument stubs, `QByteArray` conversion and resulting `Any` return. Checking those helpers directly produces the same five errors; their blobs are unchanged from `9a77d9d`. No error is located in the new renderer. This check is not reported as passing. |

Reproduced SHA-256 values at `fcdaf79`:

| File | SHA-256 |
|---|---|
| `logo-on-light.png` | `3dcbbd6382c2bf66ad3e9c666cf177ccb07d82f150e4636534703b8aac798d68` |
| `logo-on-dark.png` | `83137da2ea856ad9ee42f6ee24969e898f954aaa00d3bc21d35f86f8825b55c0` |
| `social-preview-1280x640.png` | `9b555fc298a328c33d05d7b97d13482ba372384fea4c25e25aced8a03c953573` |

### Readiness and coordination

The [CI run on `fcdaf79`](https://github.com/kottmans/tracks-and-trails/actions/runs/34809985094)
was still **queued** when checked; its
[commit-message run](https://github.com/kottmans/tracks-and-trails/actions/runs/34809985080)
had succeeded. No full-suite result is claimed for the merge or final head, and this review does
not approve T-338, a release, or Windows runtime behavior. The bounded page-artwork and merge
preservation checks above do not require waiting for an unrelated full application CI result.
Font-dependent reproducibility is established only on this Fedora environment.

Only this review record and its existing index description are updated. The earlier dated review
body is preserved; its two resolved findings are updated by the appended dispositions above.
No source, test, asset, task/status record, branch or remote setting was changed by the reviewer.
No new task is warranted. The review-document commit is separate from the approved implementation
head, and is not pushed by this review.
