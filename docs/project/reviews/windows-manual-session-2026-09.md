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
