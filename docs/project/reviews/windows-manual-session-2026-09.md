# Windows manual verification session review

**Purpose:** `T-327`'s record of the pre-release Windows session (`TESTING.md` §8 item 15).
**Owner:** Maintainer performs; Implementer records
**Update when:** A later Windows manual session is recorded, or a disposition here changes.

## 2026-09-12 to 2026-09-14 — the session before `0.1.0`

**Performed by:** the maintainer. **Recorded by:** Claude, from the maintainer's own reports. Quoted
text is the maintainer's; an answer chosen from options put to them is marked *(answered)*.
**Machine:** Windows Sandbox on `STARBASE` (Windows 10 Enterprise, build 19041), over RDP.
**Final artifact:** `Tracks-and-Trails-0.1.0.dev0-setup.exe`, sha256
`4d4313364540aac867e6dd3b8a44dbfc94d172378471ac4528b29bad3b97f376`, the installer approved at
`66b674c`. Earlier installers in the sitting are named where a result was taken on one.
**Not independent review:** this is the maintainer's manual check, which `OPS-004` leaves as the
subjective residue CI cannot judge. It records what a person saw; it approves no code.

| # | Item (`TESTING.md` §9, `OPS-004`) | Result | In the maintainer's words |
|---|---|---|---|
| 1 | Install, watching the prompts; `T-317`'s SmartScreen screenshot | **Pass**, after two corrections | *"installer works fine"*; after the artwork, *"everything looks good"*. SmartScreen: first *"I didn't get a smartscreen warning at all"* on a mapped-folder copy, which carries no Mark of the Web; with the mark added, both prompts appeared, screenshot filed |
| 2 | Rendering under light and dark themes | **Pass**, after the defects below were fixed | On the final installer: *(answered)* "Yes, both looked right" |
| 3 | Narrator coherence | **Deferred past `0.1.0` by ruling** (`T-339`) | *"im not really sure I care if the narrorator works right now or not"*; then *(answered)* "Defer, say so" |
| 4 | Native dialogs, *Show in folder*, *Open* | **Pass**, *Show in folder* after a fix; *Open*'s playback judged a Sandbox limit | *Show in folder* on the final installer: *(answered)* "Yes, works now". *Open*: *"it works fine on a linux machine, im pretty certain its just the sandbox"* |
| 5 | A long real download with the window in use | **Pass** | *"yes I did and didn't note any issues from it. I tested it on a 24 hour long rain sounds video on youtube"* |
| 6 | Uninstall, reading what it says about user data | **Pass**, after the uninstaller was redesigned in the sitting | *"everything is verified on my end. The uninstaller does not continue while the app is open. I was unable to open the app in the amount of time that it took the uninstaller to run"* |

**Item 1's SmartScreen prompts**, transcribed: **Windows protected your PC** — *Microsoft Defender
SmartScreen prevented an unrecognized app from starting. Running this app might put your PC at
risk.* After *More info*: **App** `Tracks-and-Trails-0.1.0.dev0-setup.exe`, **Publisher** *Unknown
publisher*, **Run anyway** / **Don't run**. Screenshot of the second:
[`2026-09-14-T327-smartscreen-more-info.png`](../evidence/2026-09-14-T327-smartscreen-more-info.png).
The mark was added by hand (`Zone.Identifier`, `ZoneId=3`) because the Sandbox has no GitHub sign-in
for a draft release; SmartScreen's check is keyed on that mark.

**Item 6, what the words cover and what they do not.** The single dialog from Windows' app list, its
tick box, the final message for keeping and for removing, and the refusal while the application is
open were seen. The remark about launching the application mid-uninstall describes how short that
window is; it is not a guard, and the removal's own checks report *incomplete* if a file is held or
recreated. The automated half is `T-039`'s Sandbox run and the evidence of
`docs/project/evidence/windows-0.1.0.dev0-sandbox-2026-09-14*.md`.

### What the session found

Each was fixed during the sitting and carries a commit. **Severity is the implementer's assessment
under `TESTING.md` §14**, for `T-327`'s third criterion (only Critical or High blocks the release);
none remains open.

| Found during | Defect | Severity | Fixed by |
|---|---|---|---|
| 1 | an *install for me / for all users* question before the wizard | Medium | `c427ad3` |
| 1 | the wizard's stock artwork, then a fuzzy logo at pre-6.6 slot sizes | Low | `0577c7c`…`80bda5c` |
| 2 | a grey line after each status-bar message | Low | `3294cfd` |
| 2 | a closing full stop on the ffmpeg summary | Low | `c7ef559` |
| 2 | dark-mode menu titles unreadable under the pointer | Medium | `b060966` |
| 2 | the chosen entry of a drop-down invisible | Medium | `5461053` |
| 2 | dark mode: `Start` and `Clear finished` highlighted only at the border | Low | `fcff105` |
| 2 | tooltips white on white | Medium | `fcff105` |
| 2 | a disabled option's label drawn in full ink | Low | `f91ea9d` |
| 2 | a band behind labels and tick boxes inside a group | Low | `a5cd14f` |
| 2 | row buttons with no face, hover or press; the status chip read as a button | Medium | `3f576e1` |
| 2 | tick boxes a white square in every theme | Low | `9511238` |
| 4 | *Show in folder* reported *exit 1* and opened Documents | Medium | `7e82d0f` |
| 5 | **every YouTube download failed**, `CERTIFICATE_VERIFY_FAILED` | **Critical** | `1f377db`, `4e20c70`; `REL-007` amended |
| 5 | **YouTube downloads failed with `403`** | **High** | `663838e` (`T-332`) |
| 5 | reads failing intermittently, each clearing when retried by hand | Medium | `0661275` |
| use | no way back from a cancelled download | Medium | `e9549fd`, `6f1b8ca` (`T-335`) |
| use | naming as a per-download template editor | ruled redesign | `T-337`, `UX-014` |
| 6 | removing settings after an uninstall meant finding the folder by hand | ruled redesign | `T-322`, through `66b674c` |

**Not defects:** *Open* played no picture or sound in the Sandbox's media player, and vertical bars
appeared across the empty dark queue; the first plays normally on Linux, and the second is not drawn
by the application (measured on `STARBASE`), so both were judged Sandbox display limits. **One crash**
(`0xc0000374`, heap corruption opening the old naming panel) was seen once and never reproduced; it
is `T-336`, a potential task, and the panel no longer exists.

**Changes of behaviour ruled in the sitting:** the yt-dlp section's three versions (`T-333`), a
queue that stops once its work is done (`T-334`), naming as a Preferences setting (`T-337`), the
update check (`T-338`, `REL-009`), and the one-dialog uninstaller (`T-322`).

**A departure from the third criterion, stated.** It says anything found *becomes a task*. Most
defects here were fixed the same evening under `Task: none` commit trailers that name the session,
and are listed above rather than filed after the fact; the redesigns did get tasks.

**A correction to an earlier claim.** The handoff for the 2026-09-13 session-changes review said the
maintainer had confirmed the *Show in folder* fix. That had not happened: the installer in use then
predated the fix. The confirmation is the 2026-09-14 answer in item 4 above. The session review's
note that *Show in folder* rested on the maintainer's observation (`T-337.md`) was made on that
claim; it is true only from 2026-09-14.

### `REQUIREMENTS.md` §3

The *known-unverified on Windows* paragraph is rewritten, in the same change, to what this session
observed, with Narrator named as the one item deferred.

## 2026-09-14 — Independent review of the session record

**Reviewer:** Codex, independent of the implementer and recorder.
**Tasks:** T-327; accompanying T-322, T-335 and T-337 record changes and T-339 routing.
**Round:** Initial review of this record and the seven intervening commits.
**Base:** `9791c7e933003874f06f7549559ba2d4b0ded137`.
**Head:** `5d3f37df3b8edd7b80dd49a4967e3ff1b2c9370d`.
**Platforms verified:** Linux checks; direct inspection of the retained Windows screenshot and
supplied human reports. No new Windows installation or manual execution by this reviewer.
**Verdict:** **Changes requested** for T327-R1's evidence/completion wording. No new application
defect is established. The accepted product rulings, including Narrator's deferral, stand.

The dated implementer record above is preserved. This assessment distinguishes its reports from
the conclusions review can support. Subsequent release-preparation commit `f22b2c7` appeared
during review and is outside this range; this pass grants it no approval.

### Findings

| ID | Severity | Blocks approval | Finding and evidence | Disposition/status |
|---|---|---|---|---|
| T327-R1 | Medium | Yes — accuracy of the required manual gate | Item 4 above is marked **Pass** for native dialogs, Show in folder and Open. The selected answer establishes Explorer opening the download folder with the file highlighted; it does not establish automatic foregrounding, and no native-dialog starting-folder observation is supplied. Both are explicitly in T-327's item 4. REQUIREMENTS §3 nevertheless drops shell foreground from the unverified list. Its phrase **a 24-hour download ran** also confuses the reported video's runtime with elapsed download time; neither elapsed time nor completion was reported. | **Open — T-327 correction.** Record the missing foreground and dialog observations if the maintainer actually made them; otherwise retain them as unverified and mark item 4 partial. Describe a download **of a 24-hour rain-sounds video**, with no issues noticed during the reported use and elapsed time/completion unreported. Reconcile REQUIREMENTS §3 and current task/status wording. The reviewer asked for these missing observations; no additional answer was available when this review was recorded. No 24-hour soak or completed-download requirement is added. An unverified remainder needs the existing check or an explicit maintainer disposition before closing the gate. |
| T327-R2 | Low | No | Item 6's explanation says the removal checks report incomplete if a file is **held or recreated**; the dated T-327 task entry repeats this. The preceding T-322 review already explains that recreation after a file's absence check can escape detection. The unsuccessful attempt to launch during the short uninstall does not establish that every concurrent launch would be detected. | **Open — ordinary T-327 completion sync.** Append a qualification to the dated session/task explanations: incomplete is reported when deletion or a checked absence fails; recreation after that check remains possible and was not exercised. This requests accurate evidence wording, without a new launch guard or reopening the approved implementation. |
| T327-R3 | Low | No | Current descriptions have not all caught up: REQUIREMENTS §3 still begins by saying no Windows machine is available; TESTING §12 says Windows has automated coverage only, and §§8–9 omit the explicit 0.1.0 Narrator exception. STATUS still says the filed SmartScreen screenshot is awaited. | **Open — ordinary T-327/T-322 completion sync.** Update these current descriptions to the observed scope and existing Narrator deferral, retaining T327-R1's unverified remainder. No separate task or new ruling is needed. |

### Evidence dispositions

- **Selected answers count as human reports.** The theme and Show in folder answers are labeled
  as selections. The criterion's provenance purpose is met without repeating them in free text.
  Item 4's gap is its unanswered subchecks, not the use of options. The long-video answer supports
  the reported real-use observation in item 5, subject to the timing/completion limit above.
- **The screenshot matches the corrected release transcription.** The reviewer opened the actual
  531 × 497 PNG: unrecognized-app warning, risk sentence, installer filename, Unknown publisher,
  Run anyway and Don't run. It is the expanded screen; the initial More info link was not captured.
  The manually applied `ZoneId=3` and mapped-copy provenance remain explicit. This establishes
  the warning observed for that artifact in that Sandbox, not every future download or Windows build.
- **T-335/T-337's final manual criteria are supported.** Their code approvals stand; the selected
  Queue Again + Rename answer identifies installer
  `4d4313364540aac867e6dd3b8a44dbfc94d172378471ac4528b29bad3b97f376`. The completed-record moves
  preserve their earlier bodies and limitations. The false earlier Show in folder attribution
  is corrected in [the review that made it](T-337.md#2026-09-14--correction-of-the-show-in-folder-attribution).
- **The uninstall report supplies the missing subjective observation.** The recorder identifies
  the custom checkbox, keep/remove messages and refusal while the app is open as seen. It does
  not prove a successful mid-uninstall launch. T322-R6 is
  [resolved in its own record](T-322.md#2026-09-14--disposition-of-the-test-scope-correction).
- **Narrator remains deferred to T-339 by the recorded maintainer choice.** No speech quality is
  inferred from UI Automation. Open's report establishes the expected associated player launched;
  absent playback remains the maintainer's Sandbox diagnosis, not proof of playback on physical
  Windows or Windows 11.
- **The fixed defects remain traceable by commit.** TESTING §14's task threshold takes precedence
  over retrospective bookkeeping tasks for already-finished fixes. Under its consequence-based
  severity definitions the TLS failure is **High**, rather than the implementer's Critical: it
  blocked core downloads while failing closed, with no established data loss or security bypass.
  This reviewer clarification does not request rewriting the dated assessment or reopening the
  fixed defect. The listed 403 failure is also High and already fixed.

### Independent checks

| Check | Actual result |
|---|---|
| Ruff lint and whole-tree formatting at the submitted head | Passed; 422 files already formatted. |
| `python -m pytest tests/unit/test_task_placement.py tests/unit/test_windows_packaging.py -q` | **70 passed**, 0.84 s. |
| Bare `mypy` and `mypy --platform win32` | Both passed; 192 source files each. These supply the checks required for the Python test edit, despite its lack of executable changes. |
| Test comparison across the range | ASTs identical after removing docstrings and normalizing the renamed test. No executable assertion or body changed. |
| Captured uninstall evidence | Report body after the header separator is byte-identical. Only explanatory header prose changed; the completion-marker description now names the pattern's exit-code alternative. |
| T-335/T-337 record moves | Bodies from `**Owner:**` onward match after normalizing only the final installed-build checkbox and its dated annotation. Neither task remains in the active queue. |
| Source/packaging boundary | No files under `src/` or `packaging/` differ between `9791c7e` and `5d3f37d`. No full application suite or mutation rerun was needed for this range. |
| GitHub state, authenticated read-only API | Releases, including drafts, and tags endpoints both returned **[]** on 2026-09-14. This establishes current absence, not independent reconstruction of the deleted draft or proof that a tag never existed historically. |

### Readiness

T-327 needs the focused correction in T327-R1. Low findings belong in its ordinary completion
sync; no new task is requested. T-333's installed-build table observation and existing T333-R1
remain open. The workflow-built installer, release-candidate checks and first published update
response retain their existing tasks. No version bump, tag, release publication or push is
performed by this review. T-335/T-337 completion and T322-R6's disposition do not imply approval
of the remaining release gates.

Review-document validation passes: `git diff --check`, 163 local file links and the new
cross-review anchors. All three appended records retain the submitted head's bytes as exact
prefixes. The historical migration verifier preserves 381 entries in 105 files, totaling
2,403,546 bytes. Final Ruff lint and formatting also pass (423 files in the working tree after
the separate `f22b2c7` commit); that check does not extend this review's approval boundary.

## 2026-09-14 — Implementer correction for T327-R1…R3

**Recorded by:** Claude, after the maintainer answered the review's questions the same day. The
dated record at the top is left as it was; this entry supersedes the parts it names.
**Base:** `9db1594` (the review). Answers chosen from options are marked *(answered)*.

| Finding | Correction |
|---|---|
| `T327-R1`, item 4 | **The two missing observations, from the maintainer, on the final installer:** *Show in folder*'s Explorer window *(answered)* "Yes, on top by itself", in front of Tracks & Trails without using the taskbar; and a native file or folder picker *(answered)* "Yes, sensible folder", starting in the current download folder or another sensible place. Item 4 is therefore **Pass** on all three of its parts. The picker was not named: the question offered *Preferences, download folder, Browse* and *choosing a cookies file* as examples. |
| `T327-R1`, item 5 | **A download of a 24-hour rain-sounds video**, not a 24-hour download. The maintainer reported using the application during it and noticing no issues; how long it ran and whether it finished were not reported, and are not claimed. |
| `T327-R2`, item 6 | *Incomplete* is reported when a deletion fails or a checked item is still present at its check. **A file recreated after its check is not detected**, and that case was not exercised: the maintainer's failed attempt to launch the application during an uninstall shows the window is short, not that a launch in it would be caught. |
| `T327-R3` | `REQUIREMENTS.md` §3's opening constraint, `TESTING.md` §8 item 15, §9's Narrator line and §12's Windows gap, and `STATUS.md` are brought to what this session observed, with Narrator's `0.1.0` deferral (`T-339`) stated where the gate is. |

**Also answered, outside the findings:** `T-333`'s table on the installed build, *(answered)* "Yes,
looked right": the versions showed correctly and *Check* worked. Recorded on `T-333`; its `T333-R1`
disposition is the reviewer's.

**On severity:** the review reads the TLS failure as High under §14's consequence-based definitions,
not the recorder's Critical. The table above is left as dated; the reviewer's reading stands.

## 2026-09-14 — Focused review of the session-record corrections

**Reviewer:** Codex, independent of the implementer and recorder.
**Round:** Focused correction re-review of T327-R1 through T327-R3.
**Base:** `9db159495d5bc1e0061be1ce1c54ac0178ab827c`.
**Head:** `07082ac086a37e8f2aa02463d0dd0f69d2dc9e0f`.
**Verdict:** **Approved for T-327's session record**, with the recorded `0.1.0` Narrator
exception. This approves the evidence and its scope, not the remaining release-candidate gates.

| ID | Severity | Blocks approval | Disposition and independent evidence |
|---|---|---|---|
| T327-R1 | Medium | No | **Resolved.** The appended entry records the maintainer's selected answers: Explorer appeared in front without using the taskbar, and a native picker started in a sensible place. The latter does not identify the picker; the record explicitly preserves that limit. Together with the prior associated-player observation, these answer item 4's three requested behaviors. Item 5 and REQUIREMENTS §3 now describe the video's 24-hour runtime and explicitly leave elapsed download time and completion unreported. No 24-hour soak is claimed or newly required. |
| T327-R2 | Low | No | **Resolved.** Both the appended session correction and the qualification added to the dated task explanation limit incomplete-removal detection to a deletion failure or an item present at its check. Recreation after its check remains unexercised and is not claimed to be detected. The original report and prior review remain intact. |
| T327-R3 | Low | No | **Resolved.** REQUIREMENTS §3 identifies both CI and the STARBASE Sandbox session; TESTING §8 item 15 and §9 state the Narrator deferral, and §12 distinguishes observed behavior from the remaining platform/accessibility limits. STATUS now says the SmartScreen screenshot is filed and retains the workflow-build requirement. |

The reports identify the previously named final installer,
`4d4313364540aac867e6dd3b8a44dbfc94d172378471ac4528b29bad3b97f376`. The human evidence is the
maintainer's recorded selections, not a Windows run performed by this reviewer. One unnamed
picker is not an inventory of every dialog; item 4 requested the reported native-dialog behavior,
not a newly added per-picker matrix. Windows 11, physical Windows hardware and Narrator coherence
remain outside this session. The original timing and mid-uninstall limitations remain in force.

The same correction supplies T-333's installed-build observation. Its finding is resolved in
[T-333's own record](T-333.md#2026-09-14--installed-build-observation-review); no completion move
or source approval is inferred merely from ticking the task's box.

Checks: task placement **30 passed** in 0.61 s; `git diff --check`, Ruff lint and formatting
passed (423 files). The old session/independent-review bytes remain an exact prefix of the
corrected record. The historical migration verifier preserves all 381 entries in 105 files,
totaling 2,403,546 bytes. The additional full Linux run for the separately requested release-commit
review passed at this head: **4,610 passed, 22 skipped, 17 warnings**, 175.15 s; both bare mypy
runs, including `--platform win32`, passed on 192 files. No application, installer or test code
changed in `07082ac`.

T-327 may leave review in the task/status owner's normal completion update. Its accepted manual
scope does not replace T-326's candidate checks, the workflow artifact checks, or T-328's separate
publication review. No additional task, tag, publication, new Windows execution or push is
performed by this disposition.
