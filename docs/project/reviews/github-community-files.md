# GitHub community files and source installation

**Purpose:** Independent review of the community files and README installation changes.
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
