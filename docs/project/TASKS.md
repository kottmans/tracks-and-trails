# TASKS.md — Tracks & Trails

**Purpose:** Unfinished work: review, ready, proposed and blocked tasks.
**Owner:** Planner (priorities); Implementer (task/status); Reviewer (review disposition)
**Last updated:** 2026-10-27
**Update when:** Work starts, changes scope/status, closes or reopens.

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
Complete and Cancelled records live in [COMPLETED_TASKS](COMPLETED_TASKS.md).
Move each record there in the same update that closes it; keep no closed-task
stubs here. Preserve IDs, evidence, limitations and follow-up routes. Check both
files before allocating an ID; IDs are never reused. Task-reading tests and
the placement gate read both files. Current phase and blockers are in [STATUS](STATUS.md).

## In Review

### T-304 — Should a focus ring appear when the control was clicked?

**Status:** In Review — correction 1 built 2026-10-24, awaiting the focused re-review of
`T304-R1`. Changes requested 2026-10-24 at `c391e5a`, one Medium blocker
([record](reviews/T-304.md#2026-10-24--initial-keyboard-only-focus-review)); built 2026-10-18 by
the maintainer's overnight instruction that night, which also lifts the 2026-09-11 sequencing below
([the amendment](IMPLEMENTATION_PLAN.md#amended-2026-10-18-the-work-continues-while-reviews-are-pending));
the ruling is recorded as `UX-016`. *(Was Ready:)* **ruled by the maintainer on 2026-09-09: option
(2), the keyboard-only ring.** The options and their costs are kept below as the reasoning the ruling was made on. The
decision entry recording it is part of this task, since the rule it supersedes has a review
finding and a test for authority and no numbered decision.

**Sequenced by the maintainer on 2026-09-11: not started until Phase 4's exit is approved.** The
build touches every `:focus` selector in `ui/theme.py`, the generated `BORDERED_CONTROLS` ones
included — and a type-and-attribute selector out-specifying a universal pseudo-class one is the
defect behind both `T-303` and `P4EXIT-R1`'s collapse triangle. It would also rewrite the rule
that `test_focus_is_visible_on_every_control_the_application_shows` enforces, which is the test
carrying `P4EXIT-R1`'s evidence while that finding is under verification. The ruling on *what* to
build is unchanged; only *when* is settled here.
**Owner:** Maintainer to rule; Implementer to build
**Priority:** Low — it is a comfort question, not a defect. Raised 2026-09-09: *"I don't
necessarily think that mode should be enabled by default — if you are clicking around with a
mouse all of the highlighted boxes are distracting."*
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** `T-303` should land first, so the ring is correct before its trigger is argued
**Relevant context:** `T202-R1`; `STATE_RULES` in `ui/theme.py`;
`tests/ui/test_colour_is_never_alone.py`; `NFR-005`
**Affected surfaces:** `ui/theme.py`, the application's input handling, and the accessibility tests
**Risk:** Medium — it changes a rule that currently has a test and a recorded rationale

#### The question

Qt shows the focus ring wherever focus lands, including a mouse click, because `QCheckBox` and
friends take `StrongFocus`. The web solved this with `:focus-visible`: ring for keyboard, none for
pointer. **Qt has no native equivalent**, so it would be built — track the last input device and
carry it as a dynamic property the style sheet selects on.

#### What makes it a decision rather than a tweak

The ring is not decoration here. `STATE_RULES` records it as the **geometry** channel for focus,
adopted so that focus reads without colour — *"ink against background, which needs no colour to
read"* — and `tests/ui/test_colour_is_never_alone.py` enforces that every state has a non-colour
channel. **No numbered decision governs it**: its authority is review finding `T202-R1` and the
test. So a ruling here would be the first time this is written down as a decision rather than as
code.

#### Options

1. **Leave it.** Every focus is drawn. Costs nothing, and the maintainer finds it distracting.
2. **Keyboard-only ring (`:focus-visible`).** Mouse focus draws no ring; keyboard focus does.
   Standard on the web and in modern toolkits. **It does not weaken the keyboard case**, which is
   what `NFR-005` and the accessibility pass are about. It does mean a control can hold focus with
   nothing showing it, which matters to a mouse user who then reaches for the keyboard — the
   handover is the case to check, not the steady state.
3. **Keep the ring, reduce it** — thinner, or a lower-contrast hue — for every focus. Keeps one
   code path and one rule; likely fails the contrast floor that made it 2px.

**Recommendation: (2), after `T-303`.** It is what the maintainer asked for, it leaves the
keyboard route untouched, and the objection it must answer — focus invisible until the user
reaches for the keyboard — is testable rather than theoretical.

#### Acceptance criteria

- Whatever is ruled is **recorded as a decision with the maintainer's authority**, since the
  current rule's authority is a review finding and this would supersede it in one direction.
- If (2): pressing a key after clicking reveals the ring on the already-focused control, and that
  handover is asserted by a test rather than described.
- `tests/ui/test_colour_is_never_alone.py` still passes, or is amended deliberately with the
  ruling cited — not adjusted to fit.

#### Built 2026-10-18

- **`ui/focus_ring.FocusRing`** watches the application's input: a key press makes it the
  keyboard's turn, and a mouse, touch or tablet press the pointer's. On every focus change, and
  whenever the turn changes, it sets `focusRing` on the focused widget and re-polishes it if the
  answer changed. It starts on the keyboard's turn, so a window opened from the keyboard shows the
  ring. `theme.apply` installs it with the style sheet, one per application, and a second dressing
  starts it afresh.
- **Every focus rule asks for the ring** through `theme.focused`, which inserts
  `[focusRing="true"]` before each `:focus` part's first pseudo-state: the ten rules in the sheet,
  the thickened selector built from `BORDERED_CONTROLS`, `STATE_RULES` and the coincidental-value
  list, through one helper so they cannot disagree. All gain the same specificity, so their order
  among themselves is unchanged.
- **One geometry defect, exposed rather than caused.** Re-polishing a focused control makes Qt
  measure it again with the focus rules on, which never happened before, and the stepper grew 2px
  wider: its contents box is pinned and it had no side padding for the thicker edge to take. Its
  idle padding now reserves a pixel each side from a 13px contents box, 15px before.
- **Decided as `UX-016`**, with the maintainer's authority, superseding `T202-R1`'s rule in one
  direction: the first criterion.
- **Tests.** `tests/ui/test_focus_ring.py`, on what is drawn and with the focus sweep's own measure:
  a click draws no ring and the next key draws it on the same control, in both themes (the second
  criterion); `Tab` draws it from the start; a spin box is told on a click and on a key; dressing
  installs one tracker on the keyboard's turn; and every focus rule in the sheet asks for the
  ring. `tests/ui/test_colour_is_never_alone.py` passes unchanged (the third criterion), its focus
  sweep included.
- **Mutations, 8 of 8 caught**, each on a fresh copy of the tree: a click or a key changing
  nothing; no re-polish; the pointer's turn first; a second dressing keeping the pointer's turn;
  focus rules asking for nothing; `apply` installing no tracker; the stepper keeping no side
  padding.

**Not measured:** a screen reader, and a real desktop. The handover is asserted offscreen on Linux;
the Windows desktop job runs these tests when `STARBASE` is back.

**Checks, 2026-10-18, on Linux, base `f7e373a`**, with the project `.venv` on `PATH`: `ruff check
.` and `ruff format --check .` (493 files); `mypy src` (72), bare `mypy` and `mypy --platform
win32` (229 each); the table check up to date; `tests/unit tests/ui` under `-n auto`, **5,852
passed**, 21 skipped; `tests/integration` **558 passed**.

#### Correction 1, 2026-10-24 — `T304-R1`

The review of `c391e5a` requested changes with one Medium blocker. **Corrected, awaiting
re-review.** The correction is on `a3214b2`, whose `focus_ring.py`, `format_table.py` and
`test_focus_ring.py` are `c391e5a`'s.

| Finding | Correction | Evidence |
|---|---|---|
| `T304-R1`, Medium — `SortableHeader.paintSection` drew its ring whenever the header had focus, so a click on a format header painted the same 430 accent pixels as a key | **The painter asks what the sheet asks.** `focus_ring.shows_ring` is true when the widget holds focus and its `focusRing` is true, the condition every `:focus` rule carries, and `paintSection` draws the current section's ring only then | `test_a_real_click_on_a_format_header_draws_no_ring`, the review's reproduction: a real click on section 0 through the viewport, in both themes, then `Shift`. **Fails at `c391e5a`'s painter** |

**Sibling audit: the click's side measured on every control there is, and a second route it
found.** A scratch sweep walked all 112 focusable controls on every surface, in both themes, and
rendered each idle, focused while the pointer had the turn, and after a key. At `c391e5a`, the key
added a ring on 106 of 112: the six that did not were the six `SortableHeader`s on four surfaces,
430 pixels after the click and nothing more after the key. And **a click on any of the nine spin
boxes drew a ring the review's accent count could not see**: the sheet leaves `QSpinBox` to the
platform's style (`T-133`), and Fusion draws its own one-pixel focus frame in the palette's
highlight, measured at 0.91 to 1.00 of a ring. Before `T-304`, every `:focus` rule applied on a
click, so the sheet's ring would have been drawn there instead (inferred, not measured). Now:

- **`_KeyboardFocusStyle` wraps the application's style**, installed once by the tracker when it
  is made. It takes `State_HasFocus` off each option the platform's style is asked to draw while
  the pointer has the turn, and puts it back after, so nothing is measured or laid out differently.
  It asks the tracker for the turn and never the widget being drawn: calling `focusProxy()` on that
  widget from inside a draw call **deleted a table's scroll bar during `render()`**, with PySide6
  6.11 and the sheet installed, bisected to that one call.
- **After the correction**, the key adds a ring on 112 of 112 in both themes, and **focus from
  the keyboard measures the same change on all 112 as at `c391e5a`**. What a click still changes is
  the text cursor (14 to 16 pixels) and twelve dialog buttons Qt makes the default when they take
  focus, which the sheet fills so the user can see which button Enter presses. That is not the
  ring, it predates `T-304`, and the key still adds the ring to each of them.
- **The header's viewport already repainted on a change of turn** at `c391e5a`, once each way,
  counted with an event filter. Nothing held that, so a test does now.
- **The cost**: every surface's window rendered ten times, best of five, took 0.209 to 0.230 s
  against 0.175 to 0.177 s at `c391e5a`, about 0.4 ms more per window. Runs vary from 0.17 to
  0.51 s, so the figure is rough.

**Tests**, in `tests/ui/test_focus_ring.py`:
`test_a_click_draws_no_ring_on_any_control_and_the_next_key_draws_it`, the sweep kept, on every
focusable control of every surface in both themes, both ways round: the key after a click adds a
ring, and a click draws none, with the default button exempted only when Qt reports it default;
the real header click above; `test_a_real_click_on_a_spin_box_draws_no_frame_of_the_platform_s_own`;
`test_the_header_repaints_its_sections_when_the_turn_changes`; and
`test_drawing_with_the_wrapped_style_leaves_every_scroll_bar_alive`, for the hazard above.

**Correction mutations, 5 of 5 caught**, each on a copy of the two source files restored by hash:
the header asking only `hasFocus()` (the sweep and the header click fail, both themes); the style
withholding nothing, and the style never installed (the sweep and the spin-box click); a change of
turn neither re-polishing nor updating (the repaint test, and the existing handover tests); and the
style asking the drawn widget for its `focusProxy()` (the scroll-bar test).

**Not verified**: Windows 11, whose default style is `windows11`, not the `windowsvista` measured
below; and a screen reader, as before.

**Checks, 2026-10-24, on Linux, base `a3214b2`**, with the project `.venv` on `PATH`: `ruff check .`
and `ruff format --check .` (504 files); `mypy src` (73), bare `mypy` and `mypy --platform win32`
(234 each); the table check up to date; `tests/unit tests/ui` under `-n 4`, **6,096 passed**, 21
skipped; `tests/integration` under `-n 4`, **577 passed**. No Windows run: `STARBASE` is offline.

**Native Windows, measured 2026-10-26, not corrected.** `STARBASE` returned that day. CI's
`windows desktop` runs this file under `offscreen`, which leaves the native style out, and it
passed there at `d055fc6`. So it was run again in `STARBASE`'s desktop session with the real
`windows` platform (Windows 10 22H2, style `windowsvista`, which the application keeps, as it sets
none), with `test_format_table.py` beside it: **9 failed, 96 passed**.

- **The click's side holds natively**: no control the sweep reaches, in either theme, drew a ring
  on a click.
- **The key's side falls short on spin boxes**: the sweep failed *"the key after a click added no
  ring"* on all nine in light and on two in dark (`optionsAtMost`, `settingsConcurrencyChoice`),
  and the real-click spin-box test in light, *"the key drew no ring"*: 56 pixels changed against a
  floor of 136.8. **It is the native style's own focus frame, not the wrap**: sampled from 0 to
  1.5 s after the key, the change holds at 56 to 69 pixels, the difference being the caret, so it
  is not a transition caught early; and a spin box given a bare `windowsvista` style, outside the
  wrap, measures the same in both themes, 69 in light and 259 in dark, and draws nothing on a
  click either. The sheet leaves `QSpinBox` to the platform (`T-133`), so on Windows in light its
  keyboard focus is faint, by the floor `UX-016`'s tests hold every control to. Whether that is
  `T-304`'s to correct, `T-133`'s, or accepted on Windows is the Reviewer's disposition to propose.

**Adjacent, measured in the same run, not corrected** (`AGENTS.md` §7): `T-310`'s format table
states a size too small under the native style. `test_the_stated_width_is_enough_for_both_lists`
fails at 9, 10 and 11 pt, the video list scrolling sideways by 2, 2 and 3 pixels at its own stated
width, and `test_the_stated_height_shows_every_row` by 1 pixel of six rows at each size. By the
test's own account of `AddUrlDialog._widen_for`, the add dialog would then show a scroll bar on
Windows, `T-310`'s defect; inferred, not seen in the application. Both pass under `offscreen` on
Windows and on Linux.

### T-252 — Download tuning and the retry policy the settings screen shows

**Status:** In Review — correction 2 built 2026-10-27, awaiting the second focused re-review of
`T252-R1`, `R3` and `R5`; changes requested 2026-10-27 at `a3705e4`, `R2` and `R4` resolved, `R6`
routed to `T-253`
([record](reviews/T-252.md#2026-10-27--first-focused-correction-review)). Correction 1 built
2026-10-25; `T252-R1` ruled 2026-10-25, below. Changes requested 2026-10-24 at `7aadd3d`, one
Critical and two Medium blockers
([record](reviews/T-252.md#2026-10-24--initial-download-tuning-and-sections-review)); built
2026-10-19 on its rulings, at the maintainer's request that day.
*(Was Proposed:)* **design ruled 2026-10-19**, questions 3 and 4 as recommended (`ARC-010` and
`UX-015` amended that day), after questions 1 and 2 on 2026-10-15 as `T-364`. Filed 2026-08-16 by
`T-183`. *(Since `T-364`, built 2026-10-18, both
counts are the command line's ten when nobody chose, and a missing fragment fails the attempt;
this task's controls start from that.)* **Measured 2026-09-18, while correcting
`T184-R1`: fragment retries are zero today, not yt-dlp's ten.** `build_options` deliberately sets
`--retries` and not `--fragment-retries` (its own comment, from the maintainer's 2026-08-13 ruling),
and the consequence was not measured at the time: `downloader/fragment.py` reads
`self.params.get('fragment_retries')` with **no default** into `RetryManager`, whose first line is
`self.retries = _retries or 0`. So an absent key is **no retries at all** on every fragmented
format, which is most of YouTube. That is this task's to decide rather than a defect to fix
quietly — the policy it presents has to start from what the application really does now.
**Options (7):** `-N/--concurrent-fragments`, `--fragment-retries`, `--extractor-retries`,
`--socket-timeout`, `--download-sections`, `--live-from-start`, `--no-live-from-start`
**Specific criteria:** **the three retry knobs this task owns are presented as one policy**, not
three integers — and the entry no longer calls them *the whole* retry policy, because
`--file-access-retries` and `--retry-sleep` stay in the hatch (`T183-R4`'s wording point) —
`--retries` already exists and `ytdlp_adapter` carries a comment deferring `--fragment-retries`
here by name, so this task is where the difference between them stops needing a comment to explain.
`--download-sections` takes a time-range grammar that is parsed and refused at edit time.
`-N` interacts with the pool's own concurrency (`ARC-007`, `CONCURRENCY_MAXIMUM = 16`) and the
interaction is measured rather than assumed.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` with the worker's own `run_session`, a local HLS stream and a scripted
server that fails chosen requests; probes are in the implementer's scratch notes, not the
repository.

- **A fragmented download can end *Done* with a fragment missing — in `0.1.0` as on `main`.** One
  503 on fragment 3 of a 12-second stream: the job ended `Succeeded` with 250 of 300 video frames
  (155,465 bytes against 185,873), and yt-dlp's `Skipping fragment 3` reached no row. A 403 did
  the same with retries set to 3. yt-dlp's own command line, on its defaults, retried both and
  delivered the whole file. The cause is two library defaults the command line overrides:
  `fragment_retries` absent is zero, and `skip_unavailable_fragments` is on. `v0.1.0`'s
  `build_options` and pin are the same. **Severity guess Critical** under §14's *silent wrong
  result*, at least High given the narrow trigger.
- **`retries` absent is zero as well**, not only `fragment_retries` (`downloader/http.py:360`,
  read). Ten is the *command line's* default. So Settings' *The downloader's own* means no retries:
  one 503 partway through a progressive transfer failed the job as `EXTRACTOR_ERROR`, which the
  queue's automatic retry (NETWORK only) never takes. With retries 3 it succeeded. **Medium guess.**
- **The settings screen's retry text is untrue three ways at `HEAD`**: pieces retry zero times by
  default; the setting does govern a fragment's 5xx and connection errors (each fragment is
  fetched by an HTTP downloader built from the same params); only a 4xx or an incomplete read falls
  to the fragment count.
- **This entry's *most of YouTube* is wrong here**: all three built-ins chose `https` formats on a
  YouTube probe, so `retries` is the one that matters there. Fragments matter on HLS and DASH
  sites and on every `--live-from-start` capture.
- **Two hatch defects with `--download-sections`.** Two ranges are admitted and the second
  overwrites the first in the one output path (`Deleting existing file`, job `Succeeded`): a
  `REQ-031` defect, **High guess**. And it aborts *"ffmpeg is not installed"* whenever ffmpeg is
  reached through `ffmpeg_location` rather than `PATH`, because yt-dlp's ffmpeg *downloader* reads
  only `PATH` unless its command line sets a class attribute; that is how the Windows installer
  finds its bundled copy (inferred, not run on Windows). **Medium guess, High once a control ships.**
- **`-N` multiplies with the pool**: one job at `-N 4` peaked at 4 concurrent requests, three jobs
  at 12; the worst case is 16 × N and yt-dlp sets no ceiling. `--socket-timeout -1` passes edit
  time and fails the job (`T184-R8`'s class, Low).

**Ruled 2026-10-15:** the shipped defect is fixed first, as `T-364`, on questions 1 and 2 as
recommended. Questions 3 and 4 are open.

**Ruled 2026-10-19: questions 3 and 4 as recommended.** Fragment retries, extractor retries, the
socket timeout and `-N`, capped at 8, are Settings, beside the retry count in *Network*;
`--download-sections` and the live-from-start pair are preset fields in a *Which part* group below
*Which items*. Several sections write one file each, named by the stem and a section suffix and
claimed as one family.

**Questions for the maintainer** (recommended first):

1. **What *nobody chose* sends for `retries` and `fragment_retries`.** yt-dlp's command-line
   defaults, read from `parse_options([])` at the pin and held there by a test, shown as *10 — the
   downloader's own*; changes behaviour for `0.1.0` users, which the changelog says. / Numbers
   chosen in `core/settings.py` (a second copy of a library default, which `T-196` declined). /
   Leave them absent and relabel the default *No retries*.
2. **A fragment still missing after its retries.** `skip_unavailable_fragments=False`, so the
   attempt fails and the job's own retry resumes from staging, with the hatch's
   `--skip-unavailable-fragments` kept as the user's opt-in (a second shared key, an `ARC-010`
   amendment). / Keep the skip and mark the job *Done, incomplete* (log parsing, a new outcome). /
   Only restore the counts (still silent after eleven failures).
3. **Where the seven live.** Fragment retries, extractor retries, socket timeout and `-N` (capped
   at 8) in *Settings › Network* beside the retry count; sections and live-from-start per preset in
   a *Which part* group below *Which items* (`UX-015`). / All seven per preset. / All in Settings.
4. **Several sections.** One file per section, named by the stem and a section suffix, claimed as
   one family. / Refuse a second section (narrows `REQ-030`). / Join them (a new ffmpeg step).

#### Built 2026-10-19

- **Four connection settings, in *Settings › Network*** (ruling 3). `NetworkOptions` and
  `DownloadRequest` gain `fragment_retries`, `extractor_retries`, `socket_timeout` and
  `concurrent_fragments`, frozen into each request with the other network settings; the add dialog
  and `with_connection_of` now carry every `NetworkOptions` field by name, so none can be
  forgotten. `None` is the downloader's own: a piece's retries fall back to the command line's ten
  (`T-364`), and the other three are left out, which the library reads as the command line does
  (three, yt-dlp's 20 seconds, one piece). The model caps pieces at 8 and wants a positive
  timeout; `[network]` is read key by key, clamping at 100 retries, 600 seconds and 8 pieces.
- **One policy in three counts.** Each count is named by what it retries: the file transfer, a
  piece the server refuses, reading the page. Each shows the downloader's own number, read at the
  pin through the manager. The section says that waiting between retries and retrying a file the
  computer could not write stay in the options field, so the screen no longer offers these as the
  whole policy. The pieces control says the pool multiplies it.
- **Which part, per preset** (ruling 3, `UX-015`). `download_sections` and `live_from_start` join
  `Preset` and `DownloadRequest`, in a *Which part* group below *Which items*: one section per
  line, checked as typed, withdrawn without ffmpeg (`FfmpegFeature.SECTIONS`) with the preset's own
  carried. *From the start* acts on both passes, since it changes the formats a live stream offers.
  The row's name says both.
- **The grammar** is `core/sections.py`, a transcription of yt-dlp's `parse_chapters` and
  `parse_duration`, regular expressions verbatim. `test_sections.py` binds it to the pin over
  hand-picked and a few thousand generated spellings: accepted exactly when `parse_options`
  accepts, read as the same seconds. One rule is stricter: a range that ends where or before it
  starts is refused, since yt-dlp would ask ffmpeg for a negative length.
- **One file per section** (ruling 4). yt-dlp numbers only a chapter match, so a
  `download_range_func` subclass numbers every section in yt-dlp's order. A request that can write
  several — two ranges or more, or any chapter pattern — names each `Stem (section N).ext`, while
  the sidecars keep the base name and are written once for the item. The claim takes every section
  and the sidecars as one family, numbered on the base name (`Clip (2) (section 1).mp4`), and reads a
  subtitle yt-dlp recorded under a section's name at the base name it moved it to. One range writes
  the one plain file. The preview names the first section.
- **The mapped defects, closed.** Two sections no longer overwrite each other. A section works with
  ffmpeg found only through its location: yt-dlp's downloader checks a context variable only its
  command line sets, so the worker sets it for the download (`ffmpeg_for_its_downloader`),
  measured with `PATH` emptied before and after. A chapter pattern that matches nothing ends
  Cancelled; a section with no ffmpeg is refused before a byte moves.
- **`-N` measured, as the criterion asks**: on a local HLS stream of six one-second pieces, one
  download at 4 held exactly 4 pieces open at once, and at the default exactly 1.
- **The hatch.** Regenerating refuses the seven spellings, `-N` included, for their controls, and
  six left `NOT_SECRET_VALUES`. Nothing the hatch admits sets `download_ranges` any more, so its half
  of the sections' ffmpeg answer, `_cuts_sections`, is removed and its tests read the typed field.
- **Tests.** New: `test_sections.py`, `test_download_tuning.py` and, in integration,
  `test_download_sections.py`, the real worker against a clip and an HLS stream ffmpeg builds at
  test time: two sections written as two cut files and the info JSON once, one section as one file,
  ffmpeg only through its location, no ffmpeg, a pattern matching nothing, and the pieces at once.
  The Settings, options editor, add dialog and composition tests cover the four controls and the
  group.
- **Existing tests changed with the behaviour**: hatch examples that used a now-refused option took
  `--file-access-retries`, `--http-chunk-size`, `--buffer-size` or `--sleep-interval`; `-N4` and
  `-cN4` are held through their refusal, since no admitted short option takes a value any more;
  the section-ffmpeg cases, two unit tests and one case of the worker's ffmpeg gate, read the typed
  field; and the audit derivation, the group order and the network samples gained the new fields.
- **Measured while building**: a clip whose index sits at its end cannot be cut from a server
  without range requests. ffmpeg failed with *Error during demuxing*, and yt-dlp still reported
  success, keeping a 262-byte file. The test media is written with its index first.
- **Not verified**: *from the start* against a real live stream, which has no local stand-in, so it
  is held to `parse_options` and to both passes only; chapter matching against a real item with
  chapters, held by a unit test of the numbering instead; and Windows, with `STARBASE` offline.
- **Mutations, 34 of 34 caught**, each on a fresh copy of the tree: every connection key unsent,
  the sections on the probe or not sent, the media unnumbered or the sidecars numbered, yt-dlp's own
  numbering, the downloader's ffmpeg unset or its context not entered, the claim taking only the
  first section or reading sidecars under section names, the preview unsectioned, the backwards rule
  and the duration grammar, the model's checks, the cap, the file's reading and writing, the screen
  storing a sentinel, the carries dropping a field, and the editor's sections, check, withdrawal
  and name.

**Checks, 2026-10-19, on Linux, base `c6e9dd4`**, with the project `.venv` on `PATH`: `ruff check
.` and `ruff format --check .` (498 files); `mypy src` (73), bare `mypy` and `mypy --platform
win32` (234 each); the table check up to date; `tests/unit tests/ui` under `-n 4`, **6,088
passed**, 21 skipped; `tests/integration` under `-n 4`, **577 passed**. The first integration run
failed one case of the worker's ffmpeg gate, still spelled through the hatch; it was moved to the
typed field and the suite rerun whole. No Windows run: `STARBASE` is offline.

#### Correction 1 — `T252-R1`…`R4`

**`T252-R1`'s three questions, ruled 2026-10-25, all as recommended** (`ARC-010` amended that
day). Mapped first: yt-dlp clips a range's end to the item's length and hands ffmpeg `-ss` and
`-t`, so `*99-100` on a six-second item asks for a negative length; a direct link reports no length
at all (measured: the generic extractor's `duration` is `None`), so yt-dlp asks for one second from
99, and ffmpeg, seeking past the end, returned the whole file. A copied cut starts on a keyframe,
so its length can run long by up to one keyframe interval.

1. **A section past the end.** Cancel the item before it downloads, naming each such section and
   the item's length, as a chapter pattern that matches nothing does. / Download the sections that
   fit (*Done* with fewer files). / Fail the item (a retry cannot help).
2. **A cut with no picture or sound.** Fail the attempt as an ffmpeg failure, every section read
   with ffprobe before it is claimed, staging kept, no automatic retry. / Download the whole item
   and cut it here (a new step).
3. **An item whose site gives no length.** Read it from the media with ffprobe first, with the
   request's headers and cookies, and refuse the sections where none can be read. / Refuse sections
   on such items. / Check the length only after the cut (a short whole item passes the slack).

**`R1`, corrected 2026-10-25 on its rulings, awaiting re-review**, on `d7831a2`:

| Finding | Correction | Evidence |
|---|---|---|
| `T252-R1`, Critical — the worker trusted yt-dlp's success for a section: a cut from a server that cannot seek claimed 262 bytes with no streams, and `*99-100` came back as the whole six seconds, alone or beside `*0-2` | **Each section checked before it is cut and after.** Before the download, `_place_the_sections` takes the site's length or, where it gives none, reads the chosen link's with ffprobe and the request's own headers and cookies (`media_probe.remote_length`); with neither, the item is cancelled with `NO_LENGTH`, and a range starting at or after the end cancels it naming each such section (`core.sections.starting_past`). A length read here is handed to yt-dlp through `NumberedSections`. After the download, every section is read with `media_probe.holds_media` before it is claimed, and one with no picture or sound fails the attempt as `FFMPEG_ERROR` with staging kept and its info JSON stripped. The ffprobe is the one beside ffmpeg, where yt-dlp looks; without one, sections are refused before a byte moves | The review's reproductions, real worker on `127.0.0.1` from a server without range support: the cut of a clip with its index last, and of the MKV, fails as `FFMPEG_ERROR` with staging kept; `*99-100`, `*6-7`, `*0-2` with `*99-100`, and two sections past the end, each cancel the item naming only those outside; an item whose length cannot be read is cancelled; and no ffprobe beside ffmpeg is refused. **The cut and the past-the-end cases fail at `7aadd3d`'s checks**, by the mutations below |

**Sibling audit, measured 2026-10-25 from a server that cannot seek, and one more wrong result
it found.**

- **A range counted from the end, on a link that gives no length**: `*-2-inf`, the last two
  seconds, came back as all six at `7aadd3d`, since yt-dlp resolves the start by the item's length
  and had none. Now the length read from the link is written into the item for yt-dlp, only where
  the site gave none. `*3-inf` and `*1-3` cut correctly before and after.
- **Containers**: the faststart MP4 cuts correctly; ffmpeg's own MP4 with its index last cut to
  262 bytes and MKV to 765, both with no streams; WebM cut `*1-3` to 671 bytes with none and `*4-6`
  correctly to 2 seconds. Every failure seen had no streams, which the check catches; **no wrong
  part with a picture or sound in it was seen**.
- **A live stream has no length**, so ruling 3 refuses sections on one with `NO_LENGTH`. Not
  exercised against a real live stream.
- **The request's headers and cookies reach ffprobe on its command line**, as yt-dlp's own ffmpeg
  downloader passes them to the ffmpeg that cuts the section. Nothing ffprobe prints is logged.
- **A cancel during the length read** waits for ffprobe, at most 60 seconds, or for the parent to
  end the worker.

**Tests.** Integration, in `test_download_sections.py`: the five above. Unit: `test_media_probe.py`
(new), what ffprobe is asked and what its answers mean, headers and cookies included;
`test_sections.py`, the placing rules and the words; `test_download_tuning.py`, the worker's
placing on a length the site gave or did not, an oversized integer among them, the sections writing
the length in only where none was given, and the info JSON stripped on an empty cut.

**Mutations, 11 of 11 caught**, each on copies restored by hash: no section read before the claim;
a zero length held as media; the empty cut discarding staging, and leaving its info JSON
unstripped; nothing placed against the length; a range at the end held inside; the length read
not handed to yt-dlp; the sections ignoring it, and overwriting the site's own; the link's cookies
not sent; and no ffprobe gate.

**Not verified**: the Windows installer, whose bundled ffmpeg has `ffprobe.exe` beside it
(`packaging/fetch_ffmpeg.py`'s `WANTED_EXECUTABLES`), though Windows from source is measured
below; a real site, whose length yt-dlp usually has; and a real live stream.

**Checks for `R1`, 2026-10-25, on Linux**, with the project `.venv` on `PATH`: `ruff check .` and
`ruff format --check .` (506 files); `mypy src` (74), bare `mypy` and `mypy --platform win32` (236
each); the table check up to date; `tests/unit tests/ui` under `-n 4`, **6,172 passed**, 21
skipped; `tests/integration` under `-n 4`, **586 passed**. The first run failed `T-260`'s guard: the
test without ffprobe made its symlink directly, and now uses the `symlinks` fixture; both suites
were rerun whole. Bare `mypy` also caught two tests reading `NO_LENGTH` through the worker, which
does not export it. No Windows run: `STARBASE` is offline.

**Windows, 2026-10-26, on `STARBASE`, which returned that day.** CI's `windows desktop` at
`d055fc6` ([`40343995401`](https://github.com/kottmans/tracks-and-trails/actions/runs/40343995401))
failed 13 unit tests, so integration never ran. **Twelve were this task's tests, not its code**:
ten cases in `test_media_probe.py` wrote a section's path as `/` text, which Windows spells with
`\`; one made its ffprobe without `.exe`, which `shutil.which` does not find there; and
`test_the_downloader_s_ffmpeg_is_set_for_the_session_and_put_back`, from the build at `7aadd3d`,
compared a location as `/` text. The test without ffprobe would have failed for a reason of its own,
measured there: it linked ffmpeg as `ffmpeg`, which the worker refuses on Windows (*explicit
override, not usable*) before it looks for ffprobe; it now uses the real program's name. The
thirteenth is `T-248`'s, amended in its record. Then on `STARBASE`'s desktop session with these
corrections, at `d055fc6`, as CI runs it: `tests/unit tests/ui` under `-n auto`, **6,146 passed**,
44 skipped, 2 failed, `test_toolchain_versions`' check that `ruff` and `mypy` are the virtualenv's,
because that run left the virtualenv off `PATH`, which CI puts first; `tests/integration`, serial,
**579 passed**, 5 skipped, 2 failed, both `T-248`'s. The six files concerned, rerun with the
virtualenv first on `PATH`, `test_download_sections.py` among them: **235 passed**, 3 skipped,
`T-248`'s colon cases. The sections ran with winget's ffmpeg 8.1.2, `ffprobe.exe` beside it.

**`R2`, `R3` and `R4`, corrected 2026-10-25, awaiting re-review**, on `a002248`:

| Finding | Correction | Evidence |
|---|---|---|
| `T252-R2`, Medium — `socket_timeout = 10**400` in `[network]` raised `OverflowError` out of `load`, and out of `NetworkOptions` and the request | **Compared before it is converted.** `models.is_held_timeout` bounds the value before any `float` conversion and applies `math.isfinite` to floats only; the model now refuses past `MOST_SOCKET_TIMEOUT_SECONDS`, 600, which `settings.SOCKET_TIMEOUT_MAXIMUM` now reads, so no request built anywhere carries a wait yt-dlp cannot take. The reader clamps it and reports, keeping the other keys. `Settings`' own timeout ceiling, now unreachable, is removed | The review's case beside a valid `fragment_retries = 4`, read back as 4 and 600 with the report; `10**400` and 601 refused by both owners. **Both fail at `7aadd3d`**, as `OverflowError` |
| `T252-R3`, Medium — a stored 0.01 or 0.04 s opened as *20 s, the downloader's own*, and 0.06 s as 0.1 s, while the downloader was sent the value | **The model holds only what the control shows**: a whole number of tenths, from 0.1 to 600. The reader rounds a finer value, to no less than 0.1, and reports it, as it reports the other clamps. Chosen over more decimals, which only moves the edge | Five held values, from 0.1 to 600, each open as themselves, unlike the special text, and survive an unrelated edit; 0.04 and 7.55 are refused by the model and read as 0.1 and 7.5 with a report |
| `T252-R4`, Low — moving `--download-sections` out of the hatch dropped its deep-pattern case, so removing `RecursionError` from `core/sections.py`'s handler left every test green | **Restored for the field that took its place**, beside the overflow: a unit test of `section_problem`, whose positive control first asserts `re.compile` raises for that pattern, and the editor's refusal where typed | The review's mutation, the handler without `RecursionError`: **the unit and editor cases fail**: 2 failed, 242 passed, 1 skipped, 1 error |

**Mutations, 7 of 8 caught**, each on copies restored by hash: the model's or the reader's
conversion before the bound (`R2`); the model holding any precision; the reader keeping a finer
value; the screen showing two decimals; the handler without `RecursionError`, and without
`OverflowError`. The eighth, the model's floor of 0.1 set back to anything positive, survived and
is equivalent: a positive whole number of tenths is at least 0.1. The floor's test was removed
rather than kept untested.

**Adjacent, measured, not corrected here** (`AGENTS.md` §7; both predate `T-252`):

- **The rate limit is `R3`'s class.** A stored 1,500 bytes per second, inside the band, opens as
  *1 KiB/s* and an unrelated edit sends 1,500 back: the screen shows whole KiB/s and the reader
  keeps any whole number of bytes. `T-196`'s.
- **`R2`'s class in the adapter.** `ytdlp_adapter._as_optional_float(10**400)` raises
  `OverflowError`; it projects a site's `duration`, `fps` and `tbr`, and `worker._float_or_none`
  has the same shape. The helper is measured, not a path from a real site. Since `a296615`.

**Checks for `R2`…`R4`, 2026-10-25, on Linux**, with the project `.venv` on `PATH`: `ruff check .`
and `ruff format --check .` (504 files); `mypy src` (73), bare `mypy` and `mypy --platform win32`
(234 each); the table check up to date; `tests/unit tests/ui` under `-n 4`, **6,117 passed**, 21
skipped; `tests/integration` under `-n 4`, **577 passed**. Two comments were rewrapped after the
suites ran. No Windows run: `STARBASE` is offline.

**`R1`, `R3` and `R5`, corrected 2026-10-27, awaiting the second focused re-review**
([record](reviews/T-252.md#2026-10-27--first-focused-correction-review)), on `fdff1b4`. `R5`'s
correction is also `T253-R3`'s, and `R3`'s shared helper is `T253-R2`'s, as the review routed them:

| Finding | Correction | Evidence |
|---|---|---|
| `T252-R1`, Critical — `*0--100` and `*0--6` on the six-second clip, and `*0--6` beside `*0-2`, succeeded with the whole item | **Every section is placed as yt-dlp places it, and one empty once placed cancels the item** (`core/sections.empty_once_placed`): both ends resolved by `download_range_func`'s rule, counted from the end and never below zero, the end cut to the length as `process_video_result` cuts it. Zero to zero is what yt-dlp downloads as no section at all. Reversed ranges (`*3--4`) and `*from-url` with an end at or before its start are refused the same way, with each such section named | The review's three cases and `*3--4`, through the real worker on the committed clip: each **cancelled before a byte moves**, nothing left; the control `*0--2`, zero to four once placed, still cuts four seconds. `test_sections.py` holds the rule to yt-dlp's own `download_range_func` over 17 ranges at three lengths |
| (audit, same class) | **A chapter pattern matching a chapter of no length cancels the item** (`empty_chapters`). yt-dlp ends a chapter where the next starts, so two at `0:00` make the first zero to zero, the whole-item route again; elsewhere one of no length was an ffmpeg failure | **Reproduced in a yt-dlp session** on the loopback clip, outside the worker: chapters *Intro* and *Main* both at `0:00` were filled as zero to zero and zero to six, and `Intro` downloaded the whole six seconds. Held by unit cases in that filled shape. `*from-url` naming no range is the whole item, as yt-dlp reads it and as ruled 2026-10-25; unchanged |
| `T252-R3`, Medium — `1e-9` and `1e-8` were held by both owners, kept by the file unreported, and shown as *the downloader's own* | **The count of tenths must be at least one** (`models._in_tenths`), where the floor's test had been removed as equivalent: the tolerance that makes `0.3` three tenths made `1e-9` zero of them. Shared with the waits, so `T253-R2`'s model half is this change | Both owners refuse `1e-9` and `1e-8`; the file reads both as 0.1 and reports it; the tolerance's boundary on each side, held and refused. **The redundancy claim in the first round was wrong**, as the review showed |
| `T252-R5`, Critical, and `T253-R3`, Critical — the length read went around the request's proxy and its address to connect from | **The read is made by the request's route, or not at all** (`media_probe.Route`, `route_for`). Each part is passed to ffprobe and none left to its defaults: the proxy yt-dlp would use (the request's, or the system's as `urllib.request.getproxies` reads it), the address to connect from as `-local_addr`, yt-dlp's socket timeout, and **certificates checked**, which ffmpeg does not do unless asked. The proxy variables are kept out of ffprobe's environment. **ffmpeg tunnels only through an `http://` proxy**, so a SOCKS or `https://` one, or system settings naming two, cancel the item unread with the reason. **Only a format fetched as one file is read**, by a demuxer that opens nothing else | Real ffprobe through `_place_the_sections`, `tests/integration/test_length_route.py`, each with its control: through the request's proxy, the origin sees only the proxy's side (`127.0.0.3`); from `127.0.0.2`, only that address; IPv6 only against the IPv4 origin, **cancelled with nothing asked**, as yt-dlp fails; a SOCKS proxy, never tried; a certificate nobody signed, **refused with no request sent**, where ffprobe alone reads it; a playlist served as a plain link, read no further than itself |

**Measured on 2026-10-27, ffmpeg 8.1.3 on Linux, before building the route**: handed a `socks5://` or
`https://` proxy, by option or environment, ffprobe connected directly; `-local_addr` of the other
family fails the connection rather than going around it, and holds through TLS; **HLS pieces are
fetched without `-local_addr` and without a certificate check** even when the playlist had both,
which is why a manifest is not read; `-tls_verify 1` checks the chain and the host name.

**Windows, measured on `STARBASE`**: gyan's build verifies with GnuTLS against the Windows stores,
which hold only the roots Windows has already fetched (`REL-007`'s gap, `tls.py`). There,
`www.example.com` **failed the check** while YouTube passed. So on Windows a site whose root the
machine has not met cannot have its length read, and an item that does not give one is cancelled
with `NO_LENGTH` rather than read unchecked. **Flagged for the maintainer**: safe, but narrower than
Linux.

**Adjacent, measured, not corrected (Critical, needs a decision).** yt-dlp's own cut, `FFmpegFD`,
has the same defect, and it is not this client: it hands ffmpeg the proxy through `http_proxy`
only, never the address to connect from, and no certificate check. In a real yt-dlp session with
`*1-3` on the loopback clip, the probe's request went through a SOCKS proxy and from `127.0.0.2`,
and **the cut connected directly from `127.0.0.1` both times**. Every section download, and every
download yt-dlp gives to ffmpeg, is affected; it predates `T-252` through the options field.
Carrying the route as `ffmpeg_i` arguments would close the direct file; a SOCKS proxy and any
manifest cannot be closed that way, only refused, which is a product choice.

**Mutations, 22 of 22 caught**, each on copies restored by hash: each part of the route left out
(the proxy, the address, the certificate check, the timeout's unit, the request's timeout, the
demuxer list, the protocol list); any proxy kind let through; the first of several proxies taken;
the system's proxy ignored, or not read; the environment inherited; a manifest read; the worker
skipping empty ranges or empty chapters; the end not cut to the length; the ends not held at zero;
a chapter or a range of no length allowed; the address's end not passed; the floor of one tenth
removed. **One was caught only after a test gap was closed**: matching a chapter from its start
rather than searching it survived, since every pattern tested matched at the start; a pattern
found only by searching now fails it.

**Checks, 2026-10-27, on Linux**, with the project `.venv` on `PATH`: `ruff check .` and
`ruff format --check .` (524 files); `mypy src` (76), bare `mypy` and `mypy --platform win32` (249
each); both tables up to date; `tests/unit tests/ui` under `-n 4`, **6,596 passed**, 23 skipped;
`tests/integration` under `-n 4`, **615 passed**. Not yet run on Windows; the certificate check's
Windows result above is a probe of ffprobe there, not the suite.

### T-365 — yt-dlp rewrites the path the worker hands it, and can write outside the chosen folder

**Status:** In Review — built 2026-10-26, the day it was filed. Filed by the maintainer on
2026-10-26, on the finding measured while amending `T-248` for Windows, with the instruction to
build it the same day.
**Owner:** Implementer
**Priority:** Critical — `TESTING.md` §14 names *writing outside the directory the user chose*, and
a silent wrong name. In `0.1.0` too: the literal template dates from `a296615`.
**Phase:** Phase 4.5, shipping in `0.2.0`
**Depends on:** nothing
**Relevant context:** `T-363` (the same breach through the shaping options, and its criterion that
the path *"is handed to yt-dlp untouched"*); `T-034`; `T012-R4` (`as_literal_template`);
`T109-R8` (the claim's source check); `DAT-002`; [`T-248`'s amendment](COMPLETED_TASKS.md#t-248--filename-shaping-and-the-modification-time)
**Affected surfaces:** `downloader/worker.py` (`_extract`'s download pass, `as_literal_template`'s
docstring); `downloader/ytdlp_adapter.keep_the_literal_path`; their tests
**Risk:** High — the containment boundary, and two private yt-dlp methods.

#### Evidence

The worker renders a name, contains it and shows it, then hands yt-dlp the absolute path inside
staging as a literal template. **yt-dlp changes that path twice more before writing to it**, and
`as_literal_template`'s `%` escape reaches neither:

- **`_outtmpl_expandpath` expands environment variables**, on every platform. Measured in real
  sessions on Linux at `a3705e4`: a chosen folder `Notes $HOME` wrote the file under
  `Notes /home/sean/.tracks-and-trails-staging-…/`, outside the chosen folder, and the job failed
  as `disk` with the file left there; a title `Price $HOME` **succeeded as `sean.mp4`**, a name the
  preview never showed, made of the variable's value.
- **On Windows, `get_output_path` puts the whole path through `sanitize_path`**, whatever the
  options say: a folder ending in U+00A0, U+2003 or U+3000, which Windows allows, is renamed to end
  in `#`. Measured on `STARBASE` on 2026-10-26: the file was written under `Talks#\…`, outside the
  chosen folder, the job failed as `disk`, and the file stayed.

`T-363`'s ruling took *"Linux evidence suffices, since yt-dlp's `_prepare_filename` is the same on
every platform"*; the Windows pass is in `get_output_path`, after it.

#### Acceptance criteria

- [x] The download pass writes the literal path the worker built, verbatim: no variable in it is
      expanded, and on Windows no folder of the staging directory's own path is renamed.
- [x] yt-dlp's Windows pass still runs on whatever lies below staging, and any template or path
      outside staging reaches yt-dlp unchanged.
- [x] The measured cases are tests: real sessions on `127.0.0.1` for the folder, the title and the
      U+00A0 folder, and unit cases reproducing Windows' rename on Linux, each with a positive
      control that fails without the correction.
- [x] Mutation-checked; Ruff, `mypy src`, bare `mypy` and `mypy --platform win32`, and the suites
      pass, with a native Windows run, apart from one Windows test that fails the same without
      this change (below).

#### Out of scope

- A folder whose name ends in an ASCII space or a dot. Windows drops either when a folder is made
  through its ordinary paths, so one exists only if made through a `\\?\` path, which the worker's
  own paths would not reach either.

#### Built 2026-10-26

- **`ytdlp_adapter.keep_the_literal_path`**, called on the download pass's `YoutubeDL` beside
  `keep_secrets_out`, sets two instance attributes. `_outtmpl_expandpath` leaves a template under
  staging unexpanded, recognising it by its `%`-escaped spelling: the probe pass expanded the
  user's template already, and everything after that is a name the worker rendered. And
  `get_output_path` keeps the staging directory's own path out of `sanitize_path`, still running
  yt-dlp's pass on what lies below it, where a site's chapter title can land. Neither changes the
  probe pass or the preview.
- **A yt-dlp without either method is left as it is**, and the claim's source check stays as the
  second line. `--paths` is refused (`app:contained`), so nothing is joined ahead of the literal.
- **`as_literal_template`'s docstring** promised *"verbatim"*; it now says the escape is half of
  that, and names the other half.

**Tests**: `tests/unit/test_literal_path.py`, the six cases (the folder, braced, beside a `%`, the
title, U+00A0, U+3000) each written elsewhere without the correction and as built with it, *as on
Linux* and *as on Windows*; the sections' template; yt-dlp's pass below staging and outside it; a
template outside staging still expanded; a yt-dlp without the methods; and, on Windows only, the
two folders kept without forcing. `test_shaping_containment.py`'s
`test_the_path_is_written_as_it_reads`: real sessions for the folder, the title and the U+00A0
folder, the last holding by construction off Windows.

**Mutations, 8 of 8 caught on Linux**, each on copies restored by hash: either attribute not set;
the worker not asking, or passing no staging; nothing sanitized below staging; every template left
unexpanded; every path kept out of yt-dlp's pass; the prefix compared unescaped. **On Windows**,
with the Windows half removed on a copy restored by hash, 7 fail: every U+00A0 and U+3000 unit
case and the real U+00A0 session.

**Checks, 2026-10-26, on Linux, base `a3705e4`**, with the project `.venv` on `PATH`: `ruff check .`
and `ruff format --check .` (507 files); `mypy src` (74), bare `mypy` and `mypy --platform win32`
(237 each); the table check up to date; `tests/unit tests/ui` under `-n 4`, **6,197 passed**, 23
skipped; `tests/integration` under `-n 4`, **591 passed**. **On `STARBASE`'s desktop
session**, at `a3705e4` with this change, as CI runs it: `tests/unit tests/ui` under `-n auto`,
**6,174 passed**, 44 skipped; `tests/integration`, serial, **583 passed**, 7 skipped, 1 failed,
below. CI passed every job at `a3705e4`, run `40409543055`, `windows desktop` included.

**Adjacent, measured, not corrected** (`AGENTS.md` §7): on `STARBASE`,
`test_fragment_retries.py`'s `test_a_fragment_that_never_arrives_fails_and_the_retry_resumes_it`
(`T-364`'s) fails every time since the afternoon of 2026-10-26: the first session fails as it
should, and the resume cannot rename `v0.mp4.part`, *"being used by another process"*. **Not
`T-365`'s**: with both source files set back to `a3705e4` it fails the same, three runs of three,
and the same with each half alone. It passed in that machine's full run at `d055fc6` earlier that
day and in CI at `a3705e4`, and passes alone on Linux. Neither the virtualenv on `PATH` nor a
collector run every 10 allocations changes it. What holds the file is not found; a scanner is a
guess, not checked.

### T-253 — Network reachability: address family and politeness delays

**Status:** In Review — correction 1 built 2026-10-27, awaiting the focused re-review of
`T253-R1`, `R2`, `R3` and `R5`; changes requested 2026-10-27 at `1740c86`
([record](reviews/T-253.md#2026-10-27--initial-comprehensive-review)). Built 2026-10-26 on its
rulings, at the maintainer's instruction that day.
*(Was Proposed:)* **design ruled 2026-10-19, all three questions as recommended** (`ARC-010`
amended that day). Filed 2026-08-16 by `T-183`
**Options (5):** `-4/--force-ipv4`, `-6/--force-ipv6`, `--sleep-interval`, `--max-sleep-interval`,
`--source-address` *(the fifth by ruling 1, moved from `hatch`)*
**Specific criteria:** `-4` and `-6` share yt-dlp's `source_address` and are mutually exclusive —
`DownloadRequest` makes that unrepresentable rather than validating it; `--max-sleep-interval` is
refused without `--sleep-interval`, which is yt-dlp's own rule, and it is refused at edit time.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on a machine with no IPv6 route; probes in the implementer's scratch
notes.

- **No defect at `HEAD`**, and one gap: `--max-sleep-interval` is refused as *cannot tell what
  this would change* because the table generator runs each option alone, so a randomized delay is
  unreachable (`REQ-030`, Low).
- **`-4`, `-6` and the hatch's `--source-address` all write `source_address`**, the last typed
  winning. Once `-4`/`-6` have a control, a typed `--source-address` beside them would be admitted
  and overridden — the `REQ-031` shape — unless the build decides.
- **`-6` with no IPv6 fails as NETWORK**, so the queue retries it three times before the user sees
  why. The family reaches yt-dlp's traffic only: thumbnails and update checks read neither it nor
  the proxy.
- **yt-dlp's library enforces none of the command line's pairing rules** (max without min, max
  below min, negatives): `{max: 1.5}` slept, so the typed fields must check themselves.
- **The sleep is per file**, so a merged download sleeps twice; **a sleeping job sends nothing**, so
  its row reads *Downloading* throughout; **a cancel during a sleep is never cooperative** (noticed
  only when the sleep ended), so the manager's escalation always answers it; and **three jobs
  started within 0.17 s of each other**, so with the pool the delay spaces nothing between jobs.

**Ruled 2026-10-19: all three as recommended.** The address family is one radio group in
*Settings › Network* — Automatic, IPv4 only, IPv6 only, *From this address* — so building it moves
`--source-address` from `hatch` to `typed` and the task types five options. The delay keeps
yt-dlp's meaning, per file, beside the speed limit, and the control says that downloads running
together do not take turns. A sleeping job shows a *Waiting* stage, read from yt-dlp's
`Sleeping N seconds` line and held to it by a test.

**Questions for the maintainer** (recommended first):

1. **The address family and `--source-address`.** One radio group in *Settings › Network* —
   Automatic, IPv4 only, IPv6 only, *From this address* — absorbing `--source-address` (an audit
   change; the task grows to five options). / Three choices in Settings, `--source-address` left in
   the hatch and a disagreement refused at queue time. / Three choices per preset.
2. **What the delay means with several downloads at once.** yt-dlp's meaning, in *Settings ›
   Network* beside the speed limit, saying that downloads running together do not take turns. / A
   queue-level gap between starts (new manager behaviour; parity fails). / Per preset.
3. **What the row says while a job waits.** A *Waiting* stage from yt-dlp's `Sleeping N seconds`
   line, pinned by a test (a new `Stage` member). / Nothing; the control's note says so. / The
   application sleeps itself (one wait per job; parity fails).

#### Built 2026-10-26

- **One address choice in *Settings › Network*** (ruling 1): Automatic, IPv4 only, IPv6 only, or
  *From this address*. `NetworkOptions` and `DownloadRequest` gain `source_address`, which is `-4`,
  `-6` and `--source-address` as one value: `None` is automatic, `0.0.0.0` and `::` are the two
  families, as yt-dlp's command line spells them, and anything else is an address of this
  computer. So the three cannot disagree. The model holds an IP address written the shortest way,
  never a host name, since yt-dlp picks the family by whether the text has a colon. The address is
  checked as typed and stored only when the edit is finished (`T196-R1`'s rule), with the earlier
  choice kept in force, and said to be, until the box holds an address. Sent on both passes.
- **The wait before each file, beside the speed limit** (ruling 2): `sleep_interval` and
  `max_sleep_interval`, yt-dlp's own, per file, sent on the download only, with the longest
  defaulted to the shortest as the command line does. The model applies the command line's rules,
  which the library does not: the longest needs the shortest and is not shorter than it. Both are
  tenths of a second, from 0.1 to an hour (`MOST_WAIT_SECONDS`, a catcher for an extra digit, my
  choice). The screen holds the rules at the control: the longest is off until there is a wait,
  and its lowest value is the wait itself, *the same every time*, stored as no value. The note
  says a download fetching video and audio apart waits twice, and downloads running together do
  not take turns. `[network]` is read key by key, the pair held to the rules after the clamping.
- **A *Waiting* stage** (ruling 3): `Stage.WAITING`, read from yt-dlp's `[download] Sleeping N
  seconds` line, which `YtdlpLog` now passes to the worker. The manager counts it as running, so a
  download started from `QUEUED` no longer reads *Probing* through a wait; the row's chip reads
  *Waiting*, since a wait counts no bytes, and the job's detail reads *Waiting before the next
  file*. The next progress from the file puts the stage back.
- **The audit and the hatch.** `--source-address` moves from `hatch` to `typed` (ruling 1): 66
  typed, 62 built, 90 hatch. Regenerating refuses all eight spellings for their controls;
  `--max-sleep-interval` leaves `EFFECT_UNKNOWN`, and `--sleep-interval` and `--min-sleep-interval`
  leave `NOT_SECRET_VALUES`.
- **The address is not registered for redaction.** Typed into the options field, its value was
  hidden from the logs like any value the hatch cannot classify. As a setting it is neither a
  credential nor a cookie path, which is what `REQ-026` and `DAT-003` keep out of logs, and no
  decision names it; for the Reviewer to judge.
- **Unchanged, as mapped**: IPv6 only with no IPv6 route fails as `NETWORK`, so the queue retries
  it before the user sees why; the family reaches yt-dlp's traffic only, not thumbnails or update
  checks; and a cancel during a wait is noticed only when the wait ends, so the manager's
  escalation answers it.
- **`REQ-014` still names five stages.** `ARC-010`'s amendment adds the sixth; the requirement's
  text is not amended here. `test_protocol.py` names the sixth beside `REQ-014`'s five.

**Tests**: `tests/unit/test_reachability.py`: the address held the shortest way and a host name
refused; every value yt-dlp's command line refuses, refused on both owners; `[network]` read key by
key, the pair held after clamping; each choice setting the keys `parse_options` sets for its
spelling; the address on both passes and the wait on the download only; the options field refusing
all eight spellings; yt-dlp's own downloader writing the line read as a wait; and the wait sent as
its stage and put back. `tests/ui/test_settings_reachability.py`: the choice in force on opening;
a family stored as picked; no keystroke of an address stored; the earlier choice kept and said to be
while the box holds none; the close committing an unfinished address; the longest off and bounded
by the wait. `tests/integration/test_reachability.py`: real sessions on `127.0.0.1`, the wait
reported as *Waiting* before the file's first progress and not without one, IPv4 only reaching the
server and IPv6 only failing as `NETWORK`. The manager, chip and detail tests gained a *Waiting*
case each; the network and stage samples gained the new fields.

**Mutations, 30 of 30 caught**, each on copies restored by hash: either owner unchecked; any
spelling of an address, an unstripped one; the longest without the shortest or below it, in the
model and in the file's reading; a wait finer than tenths; the file's address as written, or not
saved, or the waits not saved; no address sent, the longest not defaulted, the wait on the probe;
the line not matched, not listened for, not passed on, or sent as another stage; the manager not
moving the job; the chip and the live set without *Waiting*; the address stored per keystroke, lost
on closing, or flipped back while typed; the longest below the wait, kept without one, or enabled
without one; the detail without words; and the generated table admitting `--source-address`.

**Checks, 2026-10-27, on Linux, base `b43c300`**, with the project `.venv` on `PATH`: `ruff check .`
and `ruff format --check .` (510 files); `mypy src` (74), bare `mypy` and `mypy --platform win32`
(240 each); the table check up to date; `tests/unit tests/ui` under `-n 4`, **6,326 passed**, 23
skipped, 1 failed: the placement gate, since this entry had not yet moved to *In Review*; moved, the
gate and the audit's tests pass, 53 of 53. `tests/integration` under `-n 4`, **596 passed**. No
Windows run of this change.

**Correction 1, 2026-10-27**, on `2e5f9da`, awaiting re-review
([record](reviews/T-253.md#2026-10-27--initial-comprehensive-review)):

| Finding | Correction | Evidence |
|---|---|---|
| `T253-R1`, High — a random wait from nothing up to a longest, yt-dlp's `--sleep-interval 0 --max-sleep-interval 5`, could not be held, read, set or sent | **A shortest of zero is held beside a longest**, in both owners, the file and the screen; alone it is still no wait, which `None` says. The reader rounds the shortest to the nearest tenth, which may be none; the longest to no less than a tenth. On the screen the longest is offered beside no wait too, and the wait box reads `0.0 s` rather than *No wait* while one is set. My first build's *"from a tenth"* substitute is gone | yt-dlp's real downloader, handed what the adapter builds, **draws the wait from `(0.0, 5.0)`**; the pair matches `parse_options` for that spelling; the file saves and reads it back; the screen sets it from *No wait*, opens it as `0.0 s` and `5.0 s`, and keeps it through another edit; zero alone is refused by both owners and read as no wait with a report |
| `T253-R2`, Medium — `1e-9` and `1e-8` were held as waits and shown as *No wait* | **The shared check corrected in `2e5f9da`** with `T252-R3`: the count of tenths must be at least one. Here the waits' own cases: both fields, alone and paired | Both owners refuse `1e-9` and `1e-8` as either field, alone or beside a longest; the file reads `1e-9` as no wait, `1e-8` beside a longest of 5 as from zero, and a longest of `1e-9` as a tenth, each reported |
| `T253-R3`, Critical — the section-length read went around the address to connect from | **Corrected in `2e5f9da`** with `T252-R5`, one client as the review asked: ffprobe is given `-local_addr`, and an address of the other family fails the read rather than making it another way | `tests/integration/test_length_route.py`: from `127.0.0.2` the origin sees only that address; IPv6 only against the IPv4 origin is cancelled with nothing asked, as yt-dlp's own request fails |
| `T253-R4`, Low — `REQ-014` names five stages and not *Waiting* | **Not changed**: `REQUIREMENTS.md` is not the Implementer's to edit without instruction (`AGENTS.md` §4). **Proposed wording**, for the maintainer: *"current stage (probing, waiting before a file, downloading video, downloading audio, merging, post-processing)"* | |
| `T253-R5`, Low, and `T252-R6` — 1,500 bytes per second showed as *1 KiB/s* | **Said under the box while the stored limit is not whole KiB/s**, and given to a screen reader as the box's description: *"This limit is 1,500 bytes per second, which the box shows rounded down to 1 KiB/s. Changing the box sets a whole number of KiB/s."* Nothing stored changes until the box is moved, as ruled | The review's value, said and described; gone once the box is moved to 2; nothing said for no limit, 1,024 or 2,048 |
| `T253-R6`, Medium — no Windows or CI run | `fdff1b4` is pushed and CI is running on the first build; this correction is not yet pushed | |

**Mutations, 13 of 13 caught**, each on copies restored by hash: the model refusing zero beside a
longest, or holding it alone; the reader refusing a zero shortest, rounding it up to a tenth,
rounding the longest to zero, or keeping zero alone; the screen saying *No wait* beside a longest,
offering no longest without a wait, dropping zero beside a longest or storing it alone; the exact
rate not said, not given to a screen reader, or kept after the box moves.

**Checks, 2026-10-27, on Linux**, with the project `.venv` on `PATH`: `ruff check .` and
`ruff format --check .` (524 files); `mypy src` (76), bare `mypy` and `mypy --platform win32` (249
each); both tables up to date; `tests/unit tests/ui` under `-n 4`, **6,622 passed**, 23 skipped;
`tests/integration` under `-n 4`, **615 passed**. No Windows run of this correction.

### T-254 — SponsorBlock, opt-in per preset

**Status:** In Review — blocked 2026-10-27 at `f05f720` on Windows and CI evidence only, no
source finding ([record](reviews/T-254.md#2026-10-27--initial-comprehensive-review)); its first CI
run failed one of its own tests, corrected below. Built 2026-10-27 on its rulings, at the
maintainer's instruction of 2026-10-26. *(Was Proposed:)* **design ruled 2026-10-19, all four
questions as recommended**
(`ARC-010` and `UX-015` amended that day). Filed 2026-08-16 by `T-183`
**Options (3):** `--sponsorblock-mark`, `--sponsorblock-remove`, `--no-sponsorblock`
**Specific criteria:** **off by default, and the control says what enabling it sends.** `SEC-003`
permitted this and `NFR-007` was amended to name SponsorBlock as a third permitted destination
*conditional on the user enabling it*; a test asserts no SponsorBlock request leaves the process
while the option is off. The category lists are validated against yt-dlp's own. `--sponsorblock-api`
is **excluded** — `SEC-003` declined a configurable endpoint — and this task does not reopen it.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on real YouTube downloads, with a loopback server standing in for the
SponsorBlock API where the request had to be read; probes in the implementer's scratch notes.

- **Through the options field on unreleased `main`, *Embed metadata* plus `--sponsorblock-mark`
  produces a file with no metadata.** The option implies a second `FFmpegMetadata` that writes
  chapters only, appended after the application's own, and it rewrites the file from a chapters
  map, dropping every tag the first wrote: the control run had `title=Me at the zoo`, the hatch
  run none. **High guess.**
- **The lookup carries every header typed through `--add-headers`**, `Authorization` included,
  captured on loopback; a youtube.com cookie was not sent. The four-character hash prefix
  `SEC-003` ruled on still holds. **High guess, Critical where the header is a credential.**
- **The hatch already turns SponsorBlock on with nothing saying what is sent, on the probe as
  well**: one lookup each from the staging probe, the session's probe and the download, three per
  queued video. **Medium guess.**
- Low: `--sponsorblock-chapter-title` and `--no-sponsorblock` are refused as *changes nothing*
  although each changes something beside a mark; `--sponsorblock-mark -sponsor` is admitted and
  builds nothing (`T012-R5`'s shape).
- SponsorBlock acts on YouTube alone, so the local integration pages can never fail a *no request
  while off* test; an offline guard through `run_all_pps('after_filter')` with requests refused
  works. A removal is ffmpeg work, and without ffmpeg the download finishes and then fails, so
  `REQ-024`'s gate is load-bearing. Two `ModifyChapters` passes leave a stale SponsorBlock chapter,
  so the build must compose one with the hatch's `--remove-chapters`.

**Ruled 2026-10-19: all four as recommended.** Each category is left, marked as a chapter or cut
out, stored as two disjoint tuples, in a *SponsorBlock (YouTube only)* group below *Keep beside the
file*. While anything is marked, *Chapters* shows checked and held, and one metadata step carries
both, which closes the metadata loss above. The lookup goes without typed headers, through a
session carrying only the network settings; that overrides a private yt-dlp method and is
unverified, so if it cannot be built the question comes back. Both defects above close within this
task.

**Questions for the maintainer** (recommended first):

1. **What a preset holds.** Per category, *leave*, *mark as a chapter* or *cut out*, stored as two
   disjoint tuples, in one *SponsorBlock (YouTube only)* group below *Keep beside the file* (eleven
   radio groups). / Two checkbox lists (an overlap rule). / One switch (no per-category choice).
2. **Marking and *Chapters*.** While anything is marked, *Chapters* shows checked and held, and one
   `FFmpegMetadata` carries both (the structural fix for the metadata loss). / Marking disabled
   until *Chapters* is ticked. / Implied in `build_options` only.
3. **Typed headers on the lookup.** Look up without them, through a subclass whose session carries
   only the network settings (overrides a private method; feasibility unverified). / Refuse
   `--add-headers` while SponsorBlock is on. / Say so and amend `NFR-007`.
4. **When `HEAD`'s defects close.** Within this task, as `T-249`'s did (`main` is unreleased). / An
   interim refusal of the two spellings now.

#### Built 2026-10-27

- **Per category, left, marked or cut** (ruling 1). `Preset` and `DownloadRequest` gain
  `sponsorblock_mark` and `sponsorblock_remove`, two tuples that share nothing, each of categories
  in `SPONSORBLOCK_CATEGORIES`, once each. That is a transcription of yt-dlp's own list, since
  `core/` may not import yt-dlp, held to it at the pin by a test, as is `SPONSORBLOCK_UNCUTTABLE`
  (a highlight and a chapter title, which yt-dlp's command line refuses after
  `--sponsorblock-remove` and its cutting step drops silently). A category marked and cut, which
  yt-dlp resolves by cutting, is one or the other here. Carried from preset to request, into the
  row's name, the settings file and the queue's store; a cut needs ffmpeg
  (`FfmpegFeature.SPONSORBLOCK`).
- **Marking holds *Chapters*, and one metadata step writes both** (ruling 2). The model refuses a
  mark without `embed_chapters`, since a mark is a chapter and only a written chapter is kept, and
  the editor checks *Chapters* and holds it while anything is marked, giving the user's own choice
  back once nothing is. The chain has one `ModifyChapters`, as yt-dlp's command line builds it for
  either option, before one `FFmpegMetadata` carrying the metadata and the chapters. **The first
  mapped defect is closed**: a real file keeps its title tag beside a SponsorBlock chapter, and a
  chapters-only second step after it, the options field's route, loses the tag, which shows the
  test can see it.
- **The lookup carries none of the download's headers** (ruling 3), and it was built as ruled:
  `look_up_sponsorblock` adds a subclass of yt-dlp's `SponsorBlockPP` to the download's session
  through `add_post_processor`, overriding only `_download_json`, the private method the ruling
  named. The override sends through a fresh `YoutubeDL` holding only the proxy, the source address
  and the socket timeout (`lookup_params`): never the typed headers, the cookies or a client
  certificate. yt-dlp's retry loop and its 404 rule are copied as they are at the pin, and a test
  holds the method it replaces to the pin's text. On loopback, the lookup sent no `Authorization`
  typed with `--add-headers` and found its segment; yt-dlp's own step, through the same session,
  sent it. **The second mapped defect is closed.**
- **Nothing is sent while it is off** (`T-254`'s criterion, `NFR-007`): the lookup is never an
  option, so nothing adds it while both tuples are empty, and the probe never asks, where the
  options field's route asked three times per video. Held through yt-dlp's after-filter step with
  every request refused and counted: none off, one on.
- **The options field's chapter cuts join the one pass**: `--remove-chapters` and
  `--force-keyframes-at-cuts` there are composed into the SponsorBlock pass rather than a second
  one. Unjoined, a real file kept a stale `[SponsorBlock]: Sponsor` chapter and 0.2 s more.
- **The editor**: *SponsorBlock (YouTube only)* below *Keep beside the file*, a note on what is sent
  (the first four characters of a hash of the video's ID, to `sponsor.ajay.app`) and that nothing
  is sent while every row is left, then one row per category, each an exclusive group whose buttons
  name their category for a screen reader. Without ffmpeg, only *Leave* is offered and the preset's
  own is kept.
- **The audit and the hatch**: the three spellings are built (65 of 66 typed), refused for their
  control, and leave `NOT_SECRET_VALUES`.
- **Not changed, as mapped (Low, unruled)**: `--sponsorblock-chapter-title` stays in the options
  field and is still refused as changing nothing, although beside a mark it now would; and
  SponsorBlock is unverified against a real YouTube lookup, which no test here may make.

**Tests**: `tests/unit/test_sponsorblock.py`: the categories held to yt-dlp's; every value yt-dlp
would refuse or silently resolve, refused on both owners; the preset's choices reaching the request,
the file and the store; a cut alone needing ffmpeg; the options field refusing the three spellings;
one metadata step after the chapter step, cutting what yt-dlp's own options cut, with the options
field's keyframes; nothing of SponsorBlock in any options; the lookup, through a loopback server, sent
without the typed header and finding its segment, beside yt-dlp's own step sending it; only the
network settings kept; nothing asked while off and one request while on; and the replaced method held
to the pin's text. `tests/ui/test_options_sponsorblock.py`: eleven rows, one choice each, opening on
the preset's own; *Chapters* held while marked and given back; the name; the note; names for a
screen reader; and *Leave* alone without ffmpeg. `tests/integration/test_sponsorblock.py`: the chain
on a real file, the mark kept beside the title tag and the second step losing it, a cut shortening
the file, the options field's `--remove-chapters` joined into one pass, and a real worker session
with SponsorBlock on for an item it cannot ask about. The audit, editor, preset and step-progress
tests gained the new fields, group and call.

**Mutations, 32 of 34 caught**, each on copies restored by hash. The first run caught 28; four were
gaps in the tests, closed and caught on a rerun: a category both marked and cut (the test's case
lacked *Chapters*, so it was refused for that instead), a cut alone needing ffmpeg, *Chapters* given
back as the user set it, and the row's whole name. **Two were equivalent**, the lists from the file
and from the store made tuples, which `Preset` and `DownloadRequest` already do, so that code was
removed.

**Checks, 2026-10-27, on Linux, base `1740c86`**, with the project `.venv` on `PATH` and nothing of
`T-255` in the tree: `ruff check .` and `ruff format --check .` (513 files); `mypy src` (74), bare
`mypy` and `mypy --platform win32` (243 each); the table check up to date; `tests/unit tests/ui`
under `-n 4`, **6,392 passed**, 23 skipped; `tests/integration` under `-n 4`, **601 passed**. No
Windows run of this change.

**CI at `fdff1b4`, 2026-10-27, run
[`40577746758`](https://github.com/kottmans/tracks-and-trails/actions/runs/40577746758): one of this
task's tests failed on Linux and on the Windows desktop**, and the rest passed (Linux integration
603 of 604; Windows 595 of 597, the other `T-367`'s, filed that day).
`test_a_real_session_with_sponsorblock_on_downloads_an_item_it_cannot_ask_about` heard nothing.
**The test's fault, not the code's**: it listened through `caplog`, at the root, and CI runs the
integration suite in one process, where `test_manager.py`'s two level tests run first and leave the
application's log tree passing nothing up and at `WARNING` (`configure_logging`, never put back).
Under `-n 4` they had run elsewhere. **Found by a probe printing the tree's state after each test of
a serial run**, and reproduced with those two tests and this one, 1 failed. The test now listens on
the tree itself at `INFO` and puts it back; the same three pass, and it passes alone. **Adjacent,
not corrected** (`AGENTS.md` §7): the two level tests still leave the tree configured for whatever
runs after them in that process.

### T-255 — Per-extractor arguments

**Status:** In Review — built 2026-10-27 on its rulings, at the maintainer's instruction of
2026-10-26. *(Was Proposed:)* **design ruled 2026-10-19, all four questions as recommended**, the
first a security ruling (`SEC-003`, `ARC-010`, `DAT-003` and `UX-015` amended that day). Filed
2026-08-16 by `T-183`
**Priority:** Lowest among the nine — one option, and the most expert-facing of the 44
**Options (1):** `--extractor-args`
**Specific criteria:** the `IE_KEY:ARGS` grammar is parsed into a validated structure, never stored
as the string the user typed; an unknown extractor key is refused **with the reason** rather than
accepted and ignored, which is `T012-R5`'s defect exactly; values are redacted under `DAT-004` like
any other text this application supplies, because an extractor argument can carry a token.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on real YouTube requests, with every request outside YouTube's hosts
refused unsent; probes in the implementer's scratch notes.

- **Unruled and admitted on unreleased `main`: two arguments choose the host requests go to.**
  `youtube:innertube_host=H` sent all four player requests to `H` (measured, refused unsent), with
  a signed-in session's authorization computed for it (read); `tiktok:api_hostname=H` copies the
  TikTok session cookie onto `H` (read, not run). `SEC-003` declined a configurable SponsorBlock
  endpoint because *its typo is a new network destination*; nothing covers these. **High guess,
  Critical once signed in.**
- **Any key and argument is admitted and an unknown one silently ignored** — `T012-R5` live
  (`nosuchie:anything=1`, `youtube:nosucharg=1`). **A repeated `--extractor-args` for one
  extractor keeps only the last.** **Medium guesses.**
- Lower: `generic:impersonate` is `SEC-003`'s forbidden `--impersonate` as an argument, inert only
  while curl_cffi is absent; `youtube-ejs:dev=true` turns off yt-dlp's checks on the solver script
  it executes (read); `zan:split_angles=true` makes ffmpeg re-encode where `requires_ffmpeg`
  cannot see it (read).
- **The key space is not the extractor list**: `twitch`, `jiosaavn`, `wrestleuniverse`,
  `stacommu`, `youtube-ejs`, `youtubepot-*` and `youtubejsc-*` are read and are not extractor keys,
  and no extractor declares its argument names. Token-carrying arguments include `po_token`,
  `visitor_data`, `hls_key`, `device_id` and `client_id`; stored, they are secrets at rest, which
  meets `DAT-003`'s reopening condition. The entry's `DAT-004` is withdrawn since 2026-08-01;
  `DAT-003`'s `T-049` amendment and `ARC-010`'s 2026-09-26 rule are what bind.

**Ruled 2026-10-19: all four as recommended.** Forbidden, and refused where typed with the reason:
the configurable endpoints `youtube:innertube_host` and `tiktok:api_hostname`, impersonation
through `generic:impersonate`, and the solver's developer switches `youtube-ejs:dev`, `repo` and
`script_version`. Everything else is permitted, `hls_key` included, and the documented
`innertube_host=studio.youtube.com` workaround is lost. *Unknown* means absent from an allowlist
of key and argument pairs generated from the pinned source and drift-tested like the option table;
plugin keys are refused. Values are stored verbatim and registered for redaction, except fixed
vocabularies. The editor is one *Extractor arguments* group above the options field, one
`KEY:ARG=V;…` per line, checked as typed and shown back merged and normalized.

**Questions for the maintainer** (recommended first; the first is a security ruling):

1. **Which pairs are forbidden.** Four families on `SEC-003`'s and `SEC-004`'s reasoning:
   configurable endpoints, impersonation, and the solver's developer switches; everything else,
   `hls_key` included, permitted (the documented `innertube_host=studio.youtube.com` workaround is
   lost). / Endpoints only. / Everything, as the user's own text.
2. **What *unknown* is checked against.** A generated allowlist of key and argument pairs from the
   pinned source, drift-tested like `option_table.py` (plugin keys refused). / Extractor keys only
   (refuses working `twitch` arguments). / A short hand-written list.
3. **Storing token values.** Verbatim, with `DAT-003`'s provenance row amended to name the field and
   values registered for redaction except fixed vocabularies. / Kept out of storage (no retry after
   a restart). / The system keyring (a new runtime dependency).
4. **The editor.** One *Extractor arguments* group above the hatch, one `KEY:ARG=V;…` per line,
   checked as typed and shown back merged and normalized. / A table. / Named YouTube controls.

#### Built 2026-10-27

- **A checked structure, never the text** (`T-255`'s criterion). `Preset` and `DownloadRequest` gain
  `extractor_args`, `(key, argument, values)` sorted, each pair once, out of the `repr`.
  `core/extractor_args.py` transcribes yt-dlp's grammar from `options.py` at the pin and is held to
  `parse_options` line by line. **Two lines for one extractor are merged**, the later argument
  winning, which closes the mapped defect that a repeated `--extractor-args` kept only the last.
- **The allowlist is generated from the pinned source** (ruling 2):
  `tools/ytdlp_extractor_args.py` reads every `_configuration_arg` call by syntax tree, resolving
  the key a call names, or every real extractor the enclosing method runs for, plus YouTube's token
  providers (`youtubepot-NAME`) and the solver's `ejs_setting` (`youtube-ejs`), into
  `core/extractor_arg_table.py`: 27 keys and 68 pairs at 2026.08.19. Three reads name their
  argument through a variable and are answered in the generator, each read from the class's own
  table where it has one; **any other read it cannot resolve stops it**, so a new one is classified, not missed.
  `test_extractor_args.py` regenerates and compares, as the option table's test does. A plugin's
  keys are not on it.
- **Refused with the reason, as typed** (`T012-R5`'s defect closed for this option): an unknown key,
  an argument its key does not read (with the ones it does), a line of no shape, and the six
  forbidden pairs (ruling 1, `SEC-003` amended), each with why in plain words. A hand-edited preset
  holding one is set aside when it is read, with the reason.
- **Stored as typed, redacted except a fixed vocabulary** (ruling 3, `DAT-003` amended): the
  settings file holds `[key, argument, [values]]`, the queue's store the same, and the manager
  registers every value for redaction where it registers the options field's, before a session
  starts. `FIXED_VOCABULARY` lists the 42 pairs whose values are a fixed set, a client's name or a
  sort order, and is **my classification, for review**; every other value, `po_token`,
  `visitor_data`, `hls_key`, `device_id` and `client_id` among them, is registered.
- **The editor** (ruling 4): *Extractor arguments* above the options field, one
  `KEY:ARG=VALUE;…` per line, refusals shown as typed and *OK* held until there are none, and the
  preset's own shown back merged and normalized when it opens. The row's name says which
  extractors are given arguments, never the values.
- **Sent on both passes**, merged, since an argument can change which formats exist. A real session
  on loopback: `generic:fragment_query` added to every piece's address, and not without it.
- **The audit and the hatch**: `--extractor-args` is built; all 66 typed options now have a control.
  The options field refuses it for its control. The test that held a typed option without a
  control to be usable now takes one control away to hold it.
- **Not changed, as mapped (Low, unruled)**: `zan:split_angles=true` makes ffmpeg re-encode where
  the ffmpeg gate cannot see it, so it is offered without ffmpeg; and no real site was asked.

**Tests**: `tests/unit/test_extractor_args.py`: the allowlist regenerated and compared, every read
resolved, the release it was read from, the mapping's pairs and the token-carrying ones known; each
forbidden pair and each fixed vocabulary one yt-dlp reads, and none of the tokens fixed; one line
read as `parse_options` reads it, two lines merged where yt-dlp keeps the last, the later argument
winning, the text shown back lossless; every refusal with its reason; the model's rule on both
owners, out of the `repr`, through the file and the store; both passes handed the merged arguments
as yt-dlp's own options would be; the row's name; the options field's refusal.
`tests/ui/test_options_extractor_args.py`: shown back normalized, merged into the result, refused as
typed with *OK* held, and named. `tests/integration/test_extractor_args.py`: a real session where
the argument reaches the extractor and one where it is not given. `test_manager.py`: the values
registered for redaction before the session, a client's name left readable. The audit, editor,
preset, hatch and options-field tests gained the field, the group and the spelling.

**Mutations, 35 of 35 caught**, each on copies restored by hash: each refusal let through, the
merge, the escapes, the separator, the names' case and dashes, the shown-back text, the model's
order, a semicolon held, the registration of nothing or of everything, either owner unchecked, a
value in either `repr`, the request losing the field, the file and the store not nested, nothing or
one value sent, the manager not registering, the name silent or its base match blind, the editor
blank, *OK* and *Accept* ungated, the result dropped, the refusals silent, the hatch admitting the
spelling, and the generator blind below a class, forgetting a stated reading, or its table losing a
key.

**Checks, 2026-10-27, on Linux, base `f05f720`**, with the project `.venv` on `PATH`: `ruff check .`
and `ruff format --check .` (519 files); `mypy src` (76), bare `mypy` and `mypy --platform win32`
(248 each); both tables' checks up to date; `tests/unit tests/ui` under `-n 4`, **6,479 passed**,
23 skipped; `tests/integration` under `-n 4`, **604 passed**. No Windows run of this change.

## Ready

<a id="t-302"></a>

## Proposed — Phase 0

## Proposed — Phase 1

## Proposed — Phase 2

### T-121 — The phase-exit clip server aborts connections on hosted Windows

**Status:** **Proposed — narrowed 2026-08-03, and still open.** Two of its three parts are struck
off: the misleading assertion and the missing `ConnectionAbortedError`. What remains is the part
nothing here can reproduce — **why the loopback connection aborts under load on hosted Windows.**
Filed rather than fixed inline (`AGENTS.md` §7): it is not `T-118`'s.

**It is now latent for two independent reasons, and only one of them is about the defect.** It did
not recur in run `30859578131` — which is not the same as resolved (`COORD-R21`) — **and the
configuration it appeared in is no longer exercised at all.** It only ever failed on hosted
`windows-latest`, and that job does not run while `WINDOWS_RUNNER` points at `STARBASE`
(`docs/project/TESTING.md` §10). *Not running the job that found a defect is not evidence about the defect*,
and in six weeks the silence will read as resolution unless this paragraph is here.

The current red on `main` belongs to nothing: `T-122`'s ratio oracle is corrected.
*(This read "it is the only thing red on `main`" until 2026-08-03, which stopped being true the
moment `T-118`'s own scaling gate failed and this test passed.)*
**Owner:** Implementer
**Priority:** Medium — a gate that fails for its own fixture's reasons is a gate that will be
dismissed, which is `T118-R10`'s lesson in a different costume
**Phase:** Phase 2 (its gate), though the defect is in test infrastructure
**Relevant context:** `tests/integration/test_phase_2_exit.py`, its `media_url` fixture,
`tests/network/conftest.py`
**Affected surfaces:** `tests/**`
**Risk:** Low to fix, and it is *not* a production defect

**`test_every_queued_job_eventually_starts_as_slots_free` failed on hosted `windows-latest` while
passing on `STARBASE`.** The assertion reads:

```
0 of 5 jobs were still QUEUED after Add with nothing else done
Final: {'af90cb': 'completed', '660db5': 'completed', '83cc82': 'failed',
        'bdd939': 'completed', '7cbf8e': 'completed'}
```

**Read the numbers before the message.** Zero jobs were still `QUEUED`, so the behaviour the test
exists to prove — that a queue drains with no user action after Add — *held*. Four of five
completed. The fifth **failed**, and the captured stderr says why:

```
ConnectionAbortedError: [WinError 10053] An established connection was aborted
by the software in your host machine
```

That is the test's own `ThreadingHTTPServer` losing a connection to its own client, twice, on the
loopback interface. The predicate demands all five `COMPLETED`, so one aborted download reddens a
test whose subject is admission.

**The message is now misleading, which is the part worth fixing.** It reports the `QUEUED` count
and concludes "nothing admits durable queued intent" — a sentence that is false whenever the count
it prints is zero. A reader who trusts the prose over the dict diagnoses the scheduler.

#### Scope

- Make the fixture server survive an aborted client connection rather than propagating it.
- Distinguish the two failures in the message: *jobs did not start* is the defect this gate exists
  for; *a job started and its download failed* is a different sentence and should say so.
- Neither reproduces on Linux, and it is hosted-Windows-only so far — `STARBASE` ran the same test
  in the same run and passed. Codex separately reported 16 localhost-server tests denied outright
  by its sandbox, so this fixture is fragile in more than one constrained environment.

#### Out of scope

- The download path itself. Nothing here suggests a production defect: the worker did what a
  worker does when a server drops the connection.

#### Corrected 2026-08-03 — the two parts that could be fixed without reproducing it

**The assertion named the wrong defect.** It printed the `QUEUED` count and then concluded
"nothing admits durable queued intent" *whatever that count was*, so a run where every job started
and one download failed reported "0 of 5 still QUEUED" and blamed admission — the one part that was
working. It now branches: a stalled queue says so, and a queue that drained with a failed download
says **that**, and points at the clip server.

**`ConnectionAbortedError` was missing from the handler.** `media_handler` already caught
`BrokenPipeError` and `ConnectionResetError` with the comment *"the expected end of a killed
download: the worker went away mid-stream"* — and `ConnectionAbortedError` is that same condition
on Windows. Its absence is why the abort escaped to `socketserver`, which printed a traceback for a
state two lines of the fixture already called expected. Added in **both** copies: the shared
`media_handler` in `test_end_to_end.py` that `test_phase_2_exit.py` imports, and `test_manager.py`'s
own.

**Neither makes the download succeed**, and neither is claimed to. Swallowing the abort stops the
noise; the connection still died mid-stream and that is what failed the job. Both changes are
improvements a reader can verify without Windows, which is exactly why they were worth doing
separately from the part that needs it.

---

### T-104 — Hand a second launch's URL to the running instance

**Status:** Proposed — **filed 2026-08-01 by `T-087`**, which built the ownership half of `ARC-006`
and deliberately not the attach half.
**Owner:** Implementer
**Priority:** Low — `T-087` satisfies exit criterion 4 and `A-004` by refusing; this is the nicer
half of "attaches **or** refuses"
**Phase:** Phase 2
**Depends on:** `T-087`
**Relevant context:** **`ARC-006`** and its 2026-07-29 amendment, `A-004`, `REQ-001`
**Affected surfaces:** `app.py`, a new channel module
**Risk:** Low — the ownership guard already prevents the harm; this only improves the outcome

#### Scope

`ARC-006` keeps `QLocalServer`/`QLocalSocket` as an **attach channel**, and is explicit that this is
what makes *attach* possible rather than only *refuse*: "a second launch can hand its URL to the
running instance and raise its window. A lock file can only say no."

`T-087` built the ownership lock and stopped there, because the criterion it owns is satisfied by
refusing. Today a user who double-clicks the application a second time — or opens a link with it
while it is running — gets a message box naming the running instance and nothing happens to the URL.

**The channel is started by whoever wins the lock, and never decides who owns the database.** That
separation is the whole point of the amendment and must survive this task: the loser connects to the
channel and hands over; it does not attempt to become a server.

#### Acceptance criteria

- A second launch with a URL passes it to the running instance, which enqueues it, and the second
  process exits reporting that it did so
- The running instance's window is raised and focused
- **A second launch with no URL still raises the window** rather than doing nothing visible
- The channel is started **after** the lock is won, asserted — a channel started first would
  reintroduce the design `P2PLAN-R5` withdrew
- A second launch when the channel is unreachable — the owner is alive but wedged — still refuses
  rather than hanging, within a stated timeout
- Verified on both platforms. **`OPS-005` amended 2026-08-01:** hosted Windows carries the Windows
  gate while `STARBASE` is unreachable, so `check (windows-latest)` satisfies this and the desktop
  slice stays with `STARBASE` for first release
  *(This read "`STARBASE` included" without qualification, which after the amendment demanded a
  machine nobody could reach for a criterion hosted Windows had already met — `T087-R4`.)*: the named-pipe and Unix-socket halves are
  different system calls

#### Out of scope

- Anything that makes the channel decide ownership (`ARC-006` amendment)
- Multi-user or networked access (`A-004`)

---

## Proposed — Phase 3

### T-190 — `docs/UX_SPEC.md` §6 still says its screen is unspecified

**Status:** Proposed — filed by `T-109`, 2026-08-07.
**Owner:** Planner / Documentation Maintainer
**Priority:** Low — no runtime behaviour depends on it; the defect is a current-truth document
stating a solved problem in the present tense, which is `T185-R1` exactly.
**Phase:** Phase 3 cleanup
**Depends on:** `T-109`'s verdict, so the correction describes what was approved rather than what
was submitted.

#### Scope

`docs/UX_SPEC.md` §6 carries a `[T]` clause reading *"This clause stays because `T-109`'s screen has
not been specified against the ruling yet"*, and a `P-16` paragraph asking whether `T-109` and
`T-111` share a screen as though it were open. `UX-007` ruled `P-16`, and the screen now exists:
`ui/options_dialog.py`, reached as `Options…` on the row's format control.

`AGENTS.md` §4 does not put `docs/UX_SPEC.md` in the Implementer's write set, which is why `T-109`
filed this rather than editing it.

#### Acceptance criteria

- §6's open questions read as ruled and built, in the past tense, with the built surface named.
- The `Save as preset…` clause describes the control **as built by `T-109`** (`T109-R5`), rather
  than saying it arrives with `T-111`. `T-111` still owns the other four operations.
- Nothing else in §6 changes: the ruled clauses are the contract the implementation was built
  against.

---

### T-191 — A queued row shows no size until it downloads

**Status:** Proposed — **filed 2026-08-08 by the `T143-R1` amendment**, which deferred pre-download
size here rather than declining it. A criterion cannot be narrowed into nowhere, so this is where it
went.
**Owner:** Implementer
**Priority:** Low — no defect, and no user has reported it. `UX-005` §3 does not promise a size
before a download starts, which is why `T-143` was amended rather than expanded
**Phase:** Phase 4 — polish, and it is a schema change, so it does not belong in a phase that is
exiting
**Depends on:** nothing
**Relevant context:** `T-143`, `T143-R1`, `UX-005` §3, `DAT-001`, `core/models.py` (`Job`,
`FormatInfo.filesize`, `FormatInfo.filesize_is_estimate`), `persistence/` migrations
**Affected surfaces:** `core/models.py`, `persistence/`, `ui/queue_view.py`, a migration
**Risk:** Low in mechanism, **Medium in honesty.** A size shown before a download is a *prediction*,
and `FormatInfo.filesize_is_estimate` exists because yt-dlp's own number is sometimes
`filesize_approx`. A row that states an estimate as a fact is the class of confident lie
`Job.progress` already refuses to tell

#### What is wrong

Nothing, today — and that is why this is Low. **No row of any kind shows a size before it runs.**
A pasted URL and a playlist entry are equally bare, so there is no inconsistency for a user to
notice; there is a field the application could show and does not.

`T-143`'s first acceptance criterion asked for it and could not have delivered it: a size lives
per-format in `FormatInfo.filesize`, and `Job` carries only `bytes_total`, which a *download*
reports. `T143-R1` found the criterion unmet, the maintainer amended it to the `UX-005` §3 anatomy,
and the deferred half is this entry.

#### Scope

Decide whether a queued row shows a predicted size, and if so store it. That means a field on `Job`
populated from the chosen format, a migration for it, and a decision on what the row says when the
number is `filesize_approx` rather than `filesize`.

**The estimate question is the real work.** Storing a number is a morning; deciding what a row says
when the number is a guess is the part that needs a ruling, because `REQ-003` already names the
column *"filesize/estimate"* and `T107-R7` made the two distinguishable for exactly this reason.

#### Acceptance criteria

- A queued row shows the size of the format it will actually download, before it downloads
- An estimated size is **shown as an estimate**, distinguishable from a size the site stated
- A format with no size at all leaves the row saying nothing rather than zero
- The stored size survives a restart, and a re-probe that changes the chosen format updates it
- Changing the format on a row changes the size it shows

#### Out of scope

- Predicting a size for a format the user has not chosen. The row shows what it will download

## Proposed — Phase 4

### T-350 — A staged format fixture races a real probe and loses its format control

**Status:** Proposed — filed during the independent 2026-09-18 correction review at `0cec265`.
**Owner:** Implementer
**Priority:** Medium — intermittent failures obscure the full-suite gate; the fixture also starts
the real network worker despite the UI suite's fixture-only network contract.
**Phase:** Phase 4 (test infrastructure; not a product deliverable)
**Depends on:** nothing
**Effort:** Small, estimated: control the staged probe, audit this helper's callers and verify the
combined integration/UI run. Do not change production state handling to accommodate the test.
**Relevant context:** `T310-R2`, `T118-R10`, [T-347 review](reviews/T-347.md), TESTING §§1 and 14.
**Affected surfaces:** `tests/ui/test_add_dialog.py`, particularly `_staged` and
`_probed_with_formats`; any shared fixture extracted for their callers.
**Risk:** Low — keep the mounted-panel geometry assertions and process cleanup intact.
**Required checks:** Ruff lint/format, bare mypy and Windows-platform mypy; the nine mounted-panel
cases, affected helper callers, the combined integration/UI selection, and the full-suite gate.
Retain the exact revision, command and actual pytest exit status for each gate.

#### Evidence and scope

The implementer reports **6 failed, 4,807 passed, 22 skipped** in the full suite, all at
`test_the_mounted_format_panel_fits_the_dialog_it_asked_for`: `row 0 offered no format control`.
The supplied narrower baseline log has five such failures but does not identify its revision.
Neither that log nor a passing isolated test establishes the stated machine-load cause.

The reviewer independently reproduced the same assertion at `0cec265`. `_staged` creates
`managers()` with the default real worker, resolves `https://example.invalid/one`, and waits only
for a job ID. `_probed_with_formats` then calls `_on_media_probed` directly to mark the row ready.
Processing events for up to three seconds before opening the editor delivered the real probe's
DNS failure: the row changed from `READY` to `FAILED`, and its format control disappeared.
This produced **1 failed** in 2.07 seconds. Repeating the same delayed check with the existing
`child_never_returning` injected kept the row ready and produced **1 passed** in 4.91 seconds.
These were temporary reviewer instrumentation, not repository test changes.

The test helper, dialog and manager files are unchanged between `72a0979` and `0cec265`.
This is independently actionable test-fixture work, separate from T-301's four font-growth
tests. The race is established; attribution of every reported suite failure or the desktop's
slowdown is not. Merely waiting longer for a format control is insufficient once the row failed.

#### Acceptance criteria

- [ ] A format-fixture test cannot start the real site probe. Use a controlled worker/result
      sequence consistent with the suite's process-boundary contract.
- [ ] Exercise delayed event delivery between staging and opening the editor, and prove the row
      remains ready with the intended formats. Restoring the uncontrolled probe must fail the
      regression check; do not rely on a fixed sleep or external DNS timing as the permanent test.
- [ ] Audit sibling callers of the helper for competing real callbacks and preserve teardown of
      workers, timers and widgets.
- [ ] All nine existing geometry cases retain their assertions and pass with the relevant combined
      suites. Record failing gates honestly; a successful `tail` is not a successful pytest run.

#### Investigated 2026-10-14 — cause confirmed, a fix prototyped, nothing applied

Investigated overnight at the maintainer's request, **as investigation only**: this task is not
scheduled in Phase 4.5's order, so nothing here changes the repository's tests. All work was on
copies of `8b0aad6`; the prototype applies cleanly at `3275a36` too, and is kept as an ignored
file, `docs/project/handoffs/2026-10-14-T350-prototype.diff`.

- **The cause is the one recorded above, now deterministic.** Delivering events until the probe
  session was released failed all nine geometry cases (exit 1), each row going `FAILED` about
  0.65 s after staging with the real worker's DNS error; the same delay with
  `child_never_returning` passed all nine. In unloaded runs no callback reached a test, so the
  race is latent and load-dependent.
- **The exposure is wider than the nine.** All 38 `_staged` callers (51 items) start the shipping
  worker against `example.invalid`, 43 of them failing under the delay. **Nineteen more tests
  (100 items) do the same through `_two_resolved_rows`, `_resolved_as`, `_probed_playlist` and
  inline**, and fail under it too; some of those also start durable probes and downloads, whose
  NETWORK failures do schedule automatic retries. No other `tests/ui` file starts the real worker,
  checked statically and by tracing spawns at run time (151 items at `HEAD`).
- **The prototype meets all four criteria for `_staged`.** A module-level child answers a probe with
  the fixture's formats and finishes, and `_staged` waits for the manager to be idle, so the
  fixture can no longer start the real probe; a new regression test over the three geometry
  fixtures opens the editor after everything has arrived. Restoring `HEAD`'s `_staged` fails the
  regression test while **the nine still pass** — the nine alone never caught it. Checks on the
  copy: Ruff clean; nine plus regression 12 passed; `tests/ui` 1,645 passed; integration and UI
  2,175 passed; the full suite under `-n 4` **6,032 passed**, 25 skipped, all exit 0. Bare and
  Windows-platform `mypy` failed only on `T-249`'s pre-existing error, fixed since in `bfda7c9`.
- **How often it has failed a full serial run**, all as *"row 0 offered no format control"*: 1 at
  `428f65d`, 6 at `78a5f9f`, 4 at `a7310d1` and 5 at `T-184`'s sixth round (2026-09-26 and 27),
  and 4 at `3275a36` (2026-10-15), with the DNS error in the log. Parallel runs under `-n auto`
  have not shown it.
- **Not fixed, and for this task's scope to decide:** the nineteen sibling tests above (the same
  child, or a controlled default for the module's `managers` fixture, which changes every default
  user); the module docstring's claim that the network is faked (Low); and three latent test-network
  routes found on the way — `test_app_launch.py`'s subprocess outside the GitHub guard,
  `QuietYtdlp` not stubbing `check_latest_version`, and `test_queue_view.py` building a real
  thumbnail loader for rows it never paints (all Low).

---

### T-302 — Nothing detects orphaned workers automatically on either platform

**Status:** Proposed — the gap opened 2026-09-08 and is recorded rather than accepted silently.
**Owner:** Implementer, with the maintainer for where a scan is allowed to run
**Priority:** Medium — process lifecycle and orphaned workers are the first item in
`TESTING.md` §14's standing risk focus, and there is now no automatic signal for either.
**Phase:** Phase 4 (operations; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012` as amended 2026-09-08, `OPS-010`, `docs/RUNNER_ORPHANS.md`,
`tools/orphan_scan.py`, `T-268`, `T-272`
**Affected surfaces:** `tools/orphan_scan.py`, possibly a local hook or schedule; **not**
`.github/workflows/` unless the maintainer rules otherwise
**Risk:** Medium — a detector that runs where orphans do not accumulate is worse than none,
because it reports a clean zero
**Required checks:** whatever the design needs; a **known positive** before any clean result is
trusted (`2026-08-29-orphan-scan-known-positive-soak.md` is the precedent)

#### Scope

`STARBASE orphans` was removed 2026-09-03 because it found `T-268`'s seven preserved specimens
every night and correctly failed, leaving the board permanently red. `Linux orphans` stopped on
2026-09-08 when `LINUX_RUNNER` was deleted and `kirk` and `Spock` were unregistered.

**Restoring either is not the answer, and this task exists because the obvious fix is unavailable.**
A hosted runner's VM is destroyed after every job, so a scan there finds nothing by construction.
Putting a self-hosted Linux runner back would undo the exposure reduction the maintainer chose the
same day.

#### First measurement, 2026-09-09 — not from clean suite runs on this machine

`tools/t302_orphan_accumulation_sampler.sh` ran nine rounds on `Spock` over two hours: a full
`tests/integration` + `tests/ui` pass each round, then two scans, at age 0 and again 90 seconds
later. **Nine suite exits of `0`, nineteen scans, no orphan reported**, with the known positive
passing first so that zero can be read. Rounds 5 to 9 ran alongside a live application session,
which the record treats as a property of the evidence rather than noise.

[The record](evidence/2026-09-09-T302-orphan-accumulation-sampling.md) states its own limits: a
run that exits cleanly is not the route that orphaned `T-268`'s specimens, two hours is not a
distribution, and the scanner only sees a process whose parent died. **So the first criterion is
answered by elimination rather than satisfied**, and the remaining candidate is a session that
ends badly — the shape `2026-08-27-T212-ytdlp-update-double-free.md` recorded.

#### Acceptance criteria

- Establish **where orphans actually accumulate now** that Linux CI is ephemeral. The working
  assumption was a developer's own machine; the 2026-09-09 sampling rules out clean suite runs on
  one, and the next measurement belongs on a session that ends badly rather than on more rounds of
  the same.
- Propose a detector that runs there — a pre-push hook, a periodic local run, or a documented
  manual step — and say plainly what it does **not** cover.
- **Prove it sees a known positive before any clean result is reported.** A blind scan prints the
  zero the author wanted.
- Do not reintroduce a nightly job that fails on known specimens; that is the shape `2026-09-03`
  removed.

#### Out of scope

- Reversing the runner move.
- `T-268`'s seven preserved specimens, which remain its own.

## Proposed — Phase 4.5

### T-366 — Establish native Windows focus and format-table geometry

**Status:** Proposed — scheduled by the 2026-10-27 independent T-304 review for the
Phase 4.5 debt, before T-358's release gate. Two native contracts share the same
Windows validation sitting; the offscreen CI suite does not exercise either style.
**Owner:** Implementer; independent Reviewer verifies the result
**Priority:** Medium — known failures of required native UI evidence, with keyboard
visibility needing product-versus-instrument diagnosis
**Phase:** Phase 4.5 — stage 4, before release acceptance
**Relevant context:** [T304-R2 and R3](reviews/T-304.md#2026-10-27--focused-correction-verification);
NFR-005; T-133; T-310; T-358; the native 2026-10-26 measurements in T-304 above
**Affected surfaces:** Native focus drawing/measurement and format-table sizing,
their regression tests and retained Windows evidence

#### Scope and acceptance criteria

- Reproduce under the real Windows platform/style, recording the exact tree,
  plugin, style and font. Keep an offscreen control and state the available styles;
  do not claim an unrun Windows 11 configuration.
- Establish whether the spin-box keyboard failures are product drawing, the
  measurement model, or both, using the bare native-style positive control and a
  deliberate focus-removal negative control. Correct the cause; do not lower the
  floor solely to make a native pass. Retain the keyboard-only pointer policy.
- Make the format table's stated size sufficient for its contents under the native
  style at the three reported fonts, with width/height assertions and a weakening
  control. Check the resulting Add/queue dialog geometry as well.
- Retain meaningful automated regressions at the native boundary and the actual
  Windows results. Run the applicable lint/type/UI checks and verify the Linux
  geometry/focus behavior is preserved.

This is not a new product design, a reopening of the verified pointer correction,
or approval of current native Windows release readiness.

### T-367 — Establish Windows fragment-resume file ownership

**Status:** Proposed — scheduled by the 2026-10-27 T-365 review, before T-358's release gate
**Owner:** Implementer; independent Reviewer verifies the result
**Priority:** High — a required Windows retry/resume contract fails repeatedly
**Phase:** Phase 4.5 — stage 4, before release acceptance
**Relevant context:** [T365-R1](reviews/T-365.md#2026-10-27--initial-comprehensive-review);
T-364; T-358; the native 2026-10-26 baseline measurements in T-365 above
**Affected surfaces:** Fragment retry/resume, subprocess/file lifetime, its Windows
integration fixture and retained native evidence, as diagnosis establishes

#### Scope and acceptance criteria

- Reproduce `test_a_fragment_that_never_arrives_fails_and_the_retry_resumes_it`
  under real Windows, preserving the failed first attempt and the successful retry's
  media/resume assertions. Record exact revisions and compare with `a3705e4`.
- Determine which process or handle prevents renaming `v0.mp4.part`, and whether the
  cause belongs to the worker, the fixture or an external component. Retain evidence;
  a scanner attribution without identifying evidence does not settle the failure.
- Correct the established cause and retain a meaningful regression at that boundary.
  Do not weaken OS protection or discard the resume/media assertions to obtain a pass.
- Demonstrate repeatable native Windows passes and the applicable full Windows gate;
  preserve the Linux contract and run the relevant lint/type checks for any changes.

This schedules an unresolved platform contract, not a claim that T-365 caused it or
that its containment correction should be reverted.

### T-358 — The `0.2.0` release

**Status:** Proposed — filed 2026-10-11 by the maintainer's rulings that day: `0.1.1` is skipped
and its preparation lands here, and the README's `REQ-030` statement, an exit criterion with no
owner, is owned here.
**Owner:** Implementer prepares; Maintainer tags and publishes
**Priority:** High at the end of the phase; nothing to do before stage 3 and the debt are done
**Phase:** Phase 4.5 — stage 4, the exit
**Depends on:** `T-247`…`T-255`; `T-351`…`T-354`; `T-339` and the `§11` walk, which happens on
this release's finished build; `T-355` and `T-357`, without which a fresh build installs PySide6
6.12 and cannot fetch the Windows ffmpeg; `T-360`, so this release's ffmpeg archive is kept
beside it.
**Relevant context:** `docs/RELEASE.md` (the five steps); `TESTING.md` §8 (the release gate);
`REL-003` (SemVer); `REL-009` (the checker that tells users); `REQ-030`; `OPS-001`, amended
2026-10-11; the cancelled `T-349` in COMPLETED_TASKS, whose preparation this inherits.

#### Scope

`0.2.0` from `main`: the escape hatch, the nine typed fields, the `0.1.0` debt, and the two fixes
that would have been `0.1.1`. Inherited from `T-349`, three things happen for the first time:

- **`TESTING.md` §8 item 5 gets its first real use**: the migration check opens `0.1.0`'s real
  database rather than a fabricated one.
- **The update checker reaches real users**: everyone on `0.1.0` is told by `T-338`'s check, and
  updates by hand (`REL-009`).
- **The release notes are written for people who already have the application.**

#### Acceptance criteria

- [ ] **The README states `REQ-030` with its exclusions**, as three lists: what has a typed
  control, what goes through the hatch, and what is refused, matching the audit
- [ ] The changelog names `T-343` and `T-347`'s fixes, the bundled ffmpeg's move from 9.0.1-29 to
  9.0.2-17 (`T-357`), and PySide6 held at 6.11 (`T-355`)
- [ ] `TESTING.md` §8 on both platforms, **item 6 included**: the walk, by the 2026-09-17 ruling;
  item 5 against `0.1.0`'s database
- [ ] This release's pinned ffmpeg archive is attached to it (`OPS-001`, amended 2026-10-11)
- [ ] `main`'s version names `0.2.0` before the release commit; it has read `0.1.1.dev0` since
  `0.1.0`'s bump, and no `0.1.1` will exist
- [ ] The five steps of `RELEASE.md` followed, and `main` back to a `.devN` version afterwards

---

### T-359 — Promote the options users reach for in the hatch

**Status:** Proposed — filed 2026-10-11 by the maintainer's ruling: a Phase 4.5 deliverable, in
the plan since 2026-08-07, that had no owning task.
**Owner:** Implementer; the maintainer rules on what promotes
**Priority:** Low, but it is what stops the hatch becoming the interface (`ARC-010`)
**Phase:** Phase 4.5
**Depends on:** `T-184`, complete
**Relevant context:** `ARC-010` §2 and its *"the hatch becomes the roadmap"* consequence; `NFR-007`

#### Scope

**There is no telemetry, by `NFR-007`, so the evidence is what users report**: issues and
discussions naming an option they type into the hatch. Put to the maintainer a written rule for
what promotes an option, then apply it to the reports gathered by the end of the phase. Each
option promoted becomes a typed-field task of its own, on the pattern `T-247`…`T-255` share.

#### Acceptance criteria

- [ ] A recorded ruling on what evidence promotes an option, with no telemetry
- [ ] The reports reviewed before `T-358`, and each promotion filed as its own task, or none, with
  the reason recorded

---

*(**The nine typed-field tasks, `T-247` … `T-255`**, filed 2026-08-16 by `T-183`, which is where
the option lists come from: `docs/YTDLP_OPTION_AUDIT.md`. **44 options over nine tasks** — the
typed class minus the 21 that already have a `DownloadRequest` field. Counted, and
`tests/unit/test_option_audit.py` asserts the partition, so a task that quietly grows or drops an
option fails a gate. **`T-247` built its seven on 2026-10-11 and `T-249` its seven on
2026-10-14**, so the built table holds 35 and the other seven tasks 30; two of `T-247`'s are
`Preset` fields, by `ARC-010`'s amendment that day.)*

**The following is true of all nine.** Each still states its own `**Status:**`, because `T-096`'s
gate reads that line per entry and a shared one would exempt nine tasks from the check that six
review rounds exist to enforce:

- **Owner:** Implementer · **Phase:** Phase 4.5, filed 2026-08-16
- **Depends on:** `T-183` approved. **Not on `T-184`** — a typed field is a declared member of
  `DownloadRequest` and needs nothing from the hatch. Nine independent tasks, in any order
- **Relevant context:** `ARC-010` §1, `REQ-030`, `docs/YTDLP_OPTION_AUDIT.md`,
  `core/models.DownloadRequest`, `core/presets.py`, `downloader/ytdlp_adapter.build_options`
- **Affected surfaces:** `core/models.py`, `downloader/ytdlp_adapter.py`, `persistence/` (each new
  field is a migration), the preset and options UI, and their tests
- **Acceptance criteria, common to all nine.** Each option below becomes a declared, typed,
  validated, frozen and picklable member of `DownloadRequest` (`ARC-002`, `ARCHITECTURE.md` §8);
  **the value is proved to arrive by asserting on the option dictionary the worker receives**, not
  by the download succeeding — `T-012` produced five defects that were values computed correctly
  and then not acted on, and `T012-R5` two more where yt-dlp accepted a key and ignored it; a
  malformed value fails **at edit time**; the migration round-trips an existing queue and an old
  row without the field loads; every control is keyboard-reachable and screen-reader-labelled
  (`NFR-005`); `ruff`, both mypy platforms and the touched suites are clean
- **Risk:** Medium for all nine — breadth rather than depth, and `NFR-008`'s churn lands on each

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data.
*(Premise re-checked 2026-08-06 after `T169-R5`. Still true, and narrower than it was: `0009`
**destroys** data rather than transforming it. That is a different problem with a different answer
— it needs a test proving the rows are gone, which it has, not an allowance for values that
legitimately changed, which is what this task is for. What did move is the strict per-column rule
below: it now covers `jobs` only, because `history` no longer exists to compare.)*
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** Phase 4.5 — inside `T-184`'s review
**Scheduled:** 2026-09-17 — `T-184` adds a field to `DownloadRequest`, so its migration is expected
to be the first that transforms stored values. The maintainer's order does this task **in that
review** rather than after it ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17)). The premise
still has to hold: a migration that only adds a column with a default transforms nothing, and then
this task waits again
**Depends on:** the first migration that changes stored values
**Relevant context:** `T014-R4`; `docs/project/TESTING.md` §7 (Migrations)
**Affected surfaces:** `tests/unit/test_persistence.py`

#### Scope

`T-014`'s migration test asserts strict per-column equality **for the tables in
`_MIGRATED_TABLES`**, which since 2026-08-06 means `jobs` alone. That is correct while every
migration either leaves a table's values alone or removes the table outright, and any unasked-for
change is loss. It will be **wrong** the day a migration legitimately transforms values.

**A destructive migration is not the case this task covers**, and `0009` is the reason to say so:
it removes rows on an explicit ruling and proves it with its own regression. This task is about the
opposite situation — values that change and are still correct — where equality has no way to tell a
good transformation from a corrupt one.

A `TRANSFORMED_BY_MIGRATION` allowance was written and then removed: `T014-R4` established that
an allowance can conceal a corrupt-but-readable migration, and an empty allowance protects
nothing while adding a mechanism nobody has exercised. Designing it against a real migration
beats designing it against an imagined one.

#### Acceptance criteria

- The first data migration ships with a test asserting the transformed values are **correct**,
  not merely different — a readable row holding wrong data is the failure mode `T014-R4` named
- Untransformed columns stay under strict equality
- The v1 fixture remains untouched; a new version freezes its own

#### Out of scope

- Any change to `T-014`'s current strict comparison, which is right until then

### T-339 — Hear Narrator read the Windows application

**Status:** Proposed — **deferred past `0.1.0` by the maintainer on 2026-09-14** (`T-327` item 3). Not
release-blocking for `0.1.0`; its release notes say Narrator's speech was not checked by a person.
**Scheduled 2026-09-17** into Phase 4.5's last stage, beside the acceptance walk: both need a
person at a Windows desktop, and the walk is one sitting at the end of the phase.
**Owner:** Maintainer performs; Implementer records
**Priority:** Medium — an accessibility claim `NFR-005` makes and a person has not heard
**Phase:** Phase 4.5 — stage 4, with the end-of-phase walk
**Relevant context:** `T-327` item 3, as scoped there; `NFR-005`; `IMPLEMENTATION_PLAN.md` §Phase 4's
screen-reader amendment (coherence *"belongs to the pre-release session"*);
`tests/ui/test_windows_accessibility.py`, which gates names and roles but cannot judge speech

#### Scope

With Narrator on, on an installed build: open Add URLs, stage a URL, open its format table, choose a
format, add it, start the queue, and open Preferences. Is what Narrator says *coherent*: does each
control announce what it is and what it does, in an order that makes sense?

#### Acceptance criteria

- [ ] The walk above done by a person, described in their words in a dated record
- [ ] Anything incoherent filed as its own task, with its severity under `TESTING.md` §14
- [ ] `REQUIREMENTS.md` §3's *known-unverified* line about Narrator rewritten to what was heard

---

### T-348 — Update the application from inside it, rather than by downloading the file

**Status:** Proposed — **asked for by the maintainer on 2026-09-17**, trying the `0.1.0.dev0` build
that reports a newer release: *"is the only way to update the program to download the new file?"*
Told that it is, by `REL-009`, they answered *"that should definitely be a phase 4.5 task."*
**Sequenced 2026-09-17: ruled in this phase, built in a later one** — see below. The shape itself is
**still owed**, so `REL-009` stands unamended and the application keeps notifying only.
**Owner:** Maintainer decides the shape; Implementer builds
**Priority:** Medium — every user of `0.1.0` updates by hand today
**Phase:** Phase 4.5 — stage 4, the ruling only
**Relevant context:** `REL-009` (notify only, and its *worth revisiting* clause), `REL-005`
(the unsigned installer), `OPS-002`'s note on automatic updates, `T-338` (the checker this builds
on), `NFR-007` (what the application may talk to)

#### What exists now

`Help → Check for Updates…` and the daily check say a newer release is out and open its page
(`T-338`). **Nothing is downloaded or run** — item 3 of `REL-009` — so the user fetches the new
AppImage or installer themselves and replaces what they have. Settings and the queue live in the
user profile, so they survive either way.

#### Why `REL-009` left it open, and what has to be answered

Its own words: *"worth revisiting once installers are signed: applying an update in place becomes
reasonable then."* The two platforms do not update the same way, and each raises its own question:

- **Windows.** An applied update runs the installer, which is unsigned (`REL-005`), so SmartScreen
  is raised again on every update, and the download needs its own integrity check. Signing is named
  as the `1.0` condition, so this may be a decision about ordering rather than about mechanism.
- **Linux.** An AppImage updates through its own mechanism (zsync, as `AppImageUpdate` and Gear
  Lever use), which needs the release to publish the matching file. Replacing a running AppImage
  is not the same operation as replacing an installed tree.
- **Both.** What is verified before anything is run (`SHA256SUMS` is published; a signature is not),
  what the user is asked, and what happens to a download in flight.

#### The shape, recommended 2026-09-18, still the maintainer's to rule

**What the release actually publishes**, read from `v0.1.0` rather than assumed, because every
option below depends on it:

| Asset | Size |
|---|---|
| `SHA256SUMS` | 206 bytes |
| `Tracks-and-Trails-0.1.0-setup.exe` | 93,482,037 |
| `Tracks_and_Trails-0.1.0-x86_64.AppImage` | 68,311,544 |

**There is no `.zsync` file**, so the delta updating `AppImageUpdate` and Gear Lever do is not
available without changing what the release publishes. **`SHA256SUMS` is published**, so any option
that fetches can verify before anything runs, which is the step users skip.

| Option | What the user does | What it costs |
|---|---|---|
| **A. Status quo** | Reads the notice, opens the page, downloads, replaces the file themselves | Nothing to build. It is the friction the maintainer noticed: *"is the only way to update the program to download the new file?"* |
| **B. Fetch, verify, hand over** (recommended) | Presses one control; the application downloads the asset for its platform, checks it against `SHA256SUMS`, and shows it in the folder with what to do next | A download surface with progress and cancel, somewhere to put the file, and the verification. **Windows still raises SmartScreen** when they run it, because `REL-005` leaves the installer unsigned. Linux still needs the file made executable and moved |
| **C. Apply in place** | Presses a control and the application updates itself | The riskiest, and `REL-009`'s own clause ties it to signing. Windows must exit for the installer to replace its files, and an unsigned installer raises SmartScreen on **every** update; Linux replaces the running AppImage. Needs its own clean-machine evidence per platform, which is a release-gate-sized job |

**Ruled 2026-09-18: B**, as recommended, and recorded as an amendment to `REL-009` — which now
permits the download and its verification, and still forbids running anything. The build stays in a
later phase by the 2026-09-17 sequencing ruling.

**Recommended: B.** It removes exactly the friction that was reported, and it moves the integrity
check from something a user is told to do into something the application does. It does **not** wait
on signing, which C does. Signing improves B and C equally, so choosing B now costs nothing later.

**Two rules B would add, and they are proposed rather than inherited** (`T348-R1`). This entry said
they came from `REL-009` item 5; that item governs the construction of the **release-page URL**
only, and item 3 currently forbids downloading or running anything at all. So both belong to the
amendment B would make, not to what is already authorised:

- The asset name is **built from the parsed version**, never taken from the response — an extension
  of item 5's reasoning to a second URL, in the same spirit and by the same argument.
- The checksum is compared **before the file is offered**, never after. A new rule, and the reason
  B is worth building: it is the step a user skips.

**Until such an amendment is ruled, `REL-009` stands as written: notify only, nothing downloaded or
run.**

#### Sequencing, ruled 2026-09-17

The Phase 4.5 plan put three shapes to the maintainer — status quo, fetch and hand over, apply in
place — with the recommendation to **rule now and build later**, because in-place updating waits on
signing and signing is a `1.0` condition (`REL-005`, and `REL-009`'s own *worth revisiting* clause).
The maintainer took that recommendation.

**What that settles:** nothing is built for updating in Phase 4.5, and `REL-009` is not amended by
this phase. **What it leaves open:** which shape, which is the maintainer's to rule whenever they
choose, and at the latest with the signing decision. "Fetch and hand over" remains the one shape
that is buildable before signing, if they want something visible sooner; it still raises SmartScreen
on Windows, because that is the installer's signature rather than the download's.

#### Scope

Put the options to the maintainer with their costs, then build what is chosen. At least: check and
notify as now (the status quo); fetch the file and hand it over, verified, leaving the user to run
it; and apply the update in place, per platform. Whatever is chosen amends `REL-009`.

#### Acceptance criteria

- [x] A recorded decision, amending `REL-009` — 2026-09-18: fetch, verify, hand over. The build is
  still a later phase's by the 2026-09-17 sequencing ruling
- [ ] If built: the update is verified against what the release publishes before anything runs, on
  both platforms, with the failure path shown to the user
- [ ] If built: a clean-machine run on each platform, updating a real earlier release to a newer one
- [ ] `REQ-030`'s wording and the README's update section match what the application does

---

### T-352 — Retire `JobProgressView`, keeping the helpers the row uses

**Status:** Proposed. Filed 2026-09-24 to carry `UX-005`'s
[2026-09-24 amendment](DECISIONS.md#amended-2026-09-24--the-progress-view-is-retired-and-the-row-is-the-only-progress-surface),
the maintainer's ruling to retire the view.
**Owner:** Implementer. The Planner updates `ARCHITECTURE.md`'s module map.
**Priority:** Low. This is maintenance with no user-visible change, but it removes about 2,200
lines and their full-suite time.
**Phase:** Phase 4.5 (`0.1.0` debt)
**Depends on:** nothing. Land it after `T-351` if both are open at once: both touch `queue_view.py`
imports, and `T-351`'s fix is the user-visible one.
**Effort:** Medium, estimated. Most of the work is moving helpers and their tests without changing
behaviour.
**Relevant context:** `UX-005` §2 and its 2026-08-06 and 2026-09-24 amendments, `T-017`, `T-340`,
`T-344`, the comment in `app.compose` above the pool naming
**Affected surfaces:** `ui/job_detail.py`; its importers `ui/queue_view.py`, `ui/row_delegate.py`,
`ui/format_table.py`, `ui/add_dialog.py`, `ui/main_window.py` and `app.py`; `ui/error_text.py`
(`describe_failure`); `tests/ui/test_job_detail.py`; the view's cases in
`tests/ui/test_windows_desktop.py`, `tests/integration/test_composition.py` and the other test files
that import it; `tools/windows/mutations/mut_view_stray.py` and `mut_view_reverse.py`, with their
`CASES` entries; and comments that name the view (`ui/log_view.py`, `ui/queue_view.py`,
`ui/row_delegate.py`, `ui/row_verbs.py`)
**Risk:** Low to Medium. Deleting tests can delete coverage of the helpers they also exercised.
**Required checks:** Ruff lint and format, `mypy src`, bare `mypy` and Windows-platform `mypy`, the
full suite, and the `windows desktop` job, because Windows tests and mutation plugins change.

#### Acceptance criteria

- [ ] The pure helpers the product imports (the list is in the amendment) live in a module named for
      what they are. Every importer uses it, and their unit tests move with them rather than going
      with the view.
- [ ] `JobProgressView` and `build_progress_view` are gone, with the tests and mutation plugins that
      exist only for them. Anything they alone reached (`CANCELLED_TEXT`, `describe_failure`) goes
      too, unless another caller is found and named.
- [ ] Nothing the row draws or speaks changes. The queue, delegate, accessibility and composition
      tests pass unchanged, apart from import paths.
- [ ] No comment still describes the view as present or pending, and `ARCHITECTURE.md`'s module map
      no longer lists `job_detail.py` as a per-job detail view.

---

### T-353 — Remove unused paths and correct dialog ownership

**Status:** Proposed — the cleanup follow-up requested by the maintainer on 2026-09-24,
bounded by the independent [September codebase audit](reviews/codebase-audit-2026-09.md).
**Owner:** Implementer
**Priority:** Medium within Phase 4.5 debt — repeated dialog retention and tests exercising unused
production helpers warrant scheduled work; cosmetic simplification alone would not.
**Phase:** Phase 4.5 (`0.1.0` debt)
**Depends on:** T-352 for any overlapping progress-view/helper removals. Independent cleanup may
be prepared first; do not duplicate that task's retirement or change the phase order.
**Relevant context:** AUD26-R2/R3/R7/R9; AGENTS §§6–8; TESTING §14; T-350's controlled-probe work.
**Affected surfaces:** The audit's bounded cleanup inventory across `src/`, its actual test
consumers, and `tools/t308_warning_stacking_probe.py`.
**Risk:** Medium — Qt result-consumption order, persistence callbacks and real coverage must
survive removal. Treat tests as evidence to migrate, not as dead weight.
**Required checks:** Ruff lint/format, `mypy src`, bare mypy and Windows-platform mypy;
relevant UI/lifecycle tests, full unit/integration suites for core/downloader/persistence edits;
full UI suite if dialog lifetime/ownership changes. Record actual failures and exact heads.

#### Scope and evidence

The audit at `a7310d1` independently found five retained Settings dialogs and 475 child widgets
after five open/reject cycles. It also fault-injected a partial geometry write that destroyed the
previous layout file. These are the behavior corrections. The rest is removal of confirmed dead
members and migration of tests off obsolete wrappers, plus the small duplications enumerated in
AUD26-R7/R9. In particular, queue-order tests must reach `_next_startable`/actual scheduling rather
than asserting that the unused `_next_waiting` is the production decision.

Use the audit's inventory, including its exclusions. Preserve Qt callbacks, intentional observation
seams, lifecycle guards, historical evidence and the helpers T-352 moves. Do not redesign
`app.compose`, unify unrelated thread/network services, or introduce a generic persistence dispatcher
on the strength of a complexity/lint score. Keep the warning-stacking diagnostic's production
presentation path and temporary profile while controlling its automatic-update dependency.

#### Acceptance criteria

- [ ] Repeated production open/close cycles release closed Settings, Options, preset, format and
      add dialogs after callers consume results. Cover both accepted and rejected results and
      late callbacks; do not put `WA_DeleteOnClose` on a modal whose caller still reads it.
- [ ] A failed geometry write preserves the previous complete file; successful save/load and
      nonfatal failure behavior remain intact.
- [ ] For each inventory removal, record the live consumer search and either preserve the assertion
      through the actual production route or state why it tested only a retired API. A scheduler
      ordering mutation must fail the replacement ordering test.
- [ ] Small deduplication preserves pending-write rollback/order and variant-specific behavior.
      No test seam or documented invariant disappears merely because production does not call it.
- [ ] The warning-stacking probe uses a controlled release-check dependency and keeps its profile
      isolation, actual `present()` route, and shutdown cleanup.
- [ ] Required checks pass, or failures are independently dispositioned; review the exact final
      head. Update current navigation/comments while preserving captured historical bytes.

---

### T-354 — Bound repeated queue rendering and scheduling work

**Status:** Proposed — the performance follow-up requested by the maintainer on 2026-09-24,
bounded by the independent [September codebase audit](reviews/codebase-audit-2026-09.md).
**Owner:** Implementer
**Priority:** Medium within Phase 4.5 debt — measured quadratic format computation and repeated
store reads on the GUI thread, plus long-line formatter cost.
**Phase:** Phase 4.5 (`0.1.0` debt)
**Depends on:** T-351 before changing playlist caches or invalidation; its incorrect visible-row
mapping must not be hidden by a faster refresh. Coordinate helper moves with T-352.
**Relevant context:** AUD26-R4/R5/R6/R8; NFR-001; ARC-005; T016-R1/R3; T197 redaction invariants.
**Affected surfaces:** Queue/staging models and delegate invalidation, manager scheduling,
`core/logging.py`, and narrowly measured secondary paths listed in the audit.
**Risk:** High — a stale cache can display the wrong request; scheduler shortcuts can violate
ordering/holds; formatter optimization must not leak values or over-redact ordinary logs.
**Required checks:** Ruff lint/format, `mypy src`, bare mypy and Windows-platform mypy;
full unit/integration suites for core/downloader changes; relevant queue, staging, delegate and
accessibility UI tests. Use controlled workloads and call counts, plus before/after timings on one
machine, not timing-only tests whose result depends on host load.

#### Scope and evidence

At `a7310d1`, one selector-role read for each of 25/50/100/200 playlist members performs
650/2,550/10,100/40,200 format computations: n(n+1). The 200-member instrument took 343.9 ms,
measuring model reads rather than a viewport repaint. One scheduling decision over 500 startable
waiting jobs performs 500 store reads. A synthetic 8,000-character `/a b` log line took 549.0 ms
to redact. These independent counts and measurements establish the primary work.

Then measure the bounded secondary leads: preset resolution for unrelated staging roles,
segments computed for unrelated header roles, whole-model thumbnail invalidation, unchanged gate
label polishing, stopped-queue timer work, repeated template previews/settings saves, repeated
worker option construction, and the duplicate clear-completed predicate. Implement only changes
with measured benefit and an explicit invalidation/order contract. Keep immediate-settings
behavior, transaction boundaries and the progress chain's persistence-before-signal ordering.

#### Acceptance criteria

- [ ] Repeated group/member role reads scale linearly for an unchanged request set, with counted
      work at multiple playlist sizes. Changes to group membership, order, requests and relevant
      status immediately invalidate the affected result; mixed-group/accessibility text stays true.
- [ ] One scheduling/fill cycle avoids a fresh store read per waiting job per free slot. Preserve
      two-lane capacity, retry order, queue reordering, worker-tree holds, pending writes and
      shutdown. Exercise the actual production selection path.
- [ ] Long-line redaction has bounded growth on the captured synthetic family while every existing
      privacy case, overlapping-secret case and ordinary-prose control remains covered.
- [ ] Measure secondary changes before/after and retain those justified by the evidence. A lead
      not confirmed as worthwhile is recorded as such, not silently claimed optimized.
- [ ] Run relevant mutations/controls against caching, ordering and redaction; preserve all required
      checks and exact-head review. No external dependency or architecture change without its own
      authorization.

---

## Proposed — Phase 5

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Proposed — a potential task, not open work** (maintainer's release ruling, `T-328`, 2026-09-13, taking the recommendation). Never reproduced in 466 attempts, and repetition is spent; a recurrence turns the `windows desktop` job red on its own. It becomes a task again only if it recurs, ideally with crash capture armed (`tools/windows/crash-dumps.ps1`, `docs/WINDOWS_VERIFICATION.md`).

**Status before this ruling:** **Blocked — on `T-092`, 2026-08-20. Still undiagnosed, still not blocking Phase 1**
(`OPS-007`, maintainer risk decision 2026-07-29). Downgraded **High → Medium**.

**The dependency was always there; the entry just never said it.** This task's own text already
concluded that only a **recurrence carrying a dump** can supply criterion 2 — *a stack is not a
cause* — and arming `STARBASE` to capture that dump **is** `T-092`. Meanwhile `Depends on:` read
*"nothing"* and the entry sat under `## Ready`, which asserts somebody can pick it up and make
progress. **Nobody can.** Repetition is spent at **466 attempts** — this entry's 361 plus the 105
full-suite Windows runs counted on 2026-08-20, which are more of the same shape rather than a new
one — and the one plan that remained — accumulating clean Windows runs — was measured on 2026-08-20 and
**cannot discriminate**, because the pre-fix sample is equally clean.

**What this changes is the board, not the risk.** The residual `OPS-007` accepted is unchanged and
still accepted; the four criteria are still deliberately not rewritten; and **the detection is in
the code rather than in this entry** — a recurrence turns the `windows desktop` job red whether or
not anybody is holding this task open. What moves is the honest label: this is waiting on a
machine being armed, which is `T-092`, which is waiting on a person.

*(Filed as a correction rather than a re-triage: nothing about the defect changed on 2026-08-20.
What changed is that the last avenue this entry proposed was tried and recorded as insufficient,
which left `Ready` claiming work that does not exist.)* The faulting object of the access violation is
unknown, product-versus-harness is unresolved, and the crash has never been reproduced: the
recorded **0 in 36** deliberate full-suite runs, plus **0/15 at `35fc7ec`** (run `30478557533`,
post-`T-090`) — **51 full-suite runs** in total, with 60 clean runs of the crashing test and 250
clean in-process iterations beside them. **361 attempts, zero events**, across three shapes and two
heads.

**`T-128` is diagnosed as of 2026-08-04, and it was a *harness* defect** — a fixture teardown
dropping a `QObject` that still owned a running `QTimer`, so the dispatcher followed a pointer into
freed memory. Two core dumps and a sub-second reproduction establish it; `src/` is not implicated,
because nothing there reads `is_idle` and the application holds one manager for the life of the
process.

**The free-evidence strategy below was tried on 2026-08-20 and it does not work. The runs were
gathered; what they cannot do is discriminate.** Measured rather than assumed: **105 completed
full-suite Windows runs** on `STARBASE` between 2026-08-04 and 2026-08-20, **zero native crashes**.
Method, so it can be re-run: every `CI` run since the `T-128` teardown fix at `bd4dde8`, taking the
`windows desktop` job's **`Full suite` step conclusion** rather than the job's — 92 `success` plus
**13 `failure`**, and the 13 count because each one **ran to completion with an ordinary pytest
tally**, which a process death cannot produce. 22 `cancelled` and 14 `skipped` are excluded because
the suite did not finish; the 14 are `T-270`'s window, where the step never ran. **Four of the 145
runs are accounted for separately and were not in the first telling of this** (`T074-R5`): they have
no `windows desktop` job at all — `31080589319`, `31120246285`, `31956224066` cancelled, and
`32042191296` failed before it. 92 + 13 + 22 + 14 + 4 = **145**, and none of the four is a completed
run, so the 105 is unchanged.

**Why that settles nothing, and it is this task's own arithmetic that says so.** The pre-fix sample
was **0 events in 51 full-suite runs**. The post-fix sample is **0 events in 105**. *"If the crash
stops recurring"* cannot be observed as a change, **because it had already stopped recurring before
the fix landed** — there is no measured pre-fix rate to beat, so the comparison is undefined.

**What the 105 buys is a dated zero and nothing more, and the first version of this paragraph
claimed more** (`T074-R5`). It gave a rule-of-three **2.9% per-run ceiling**, which assumes
exchangeable trials sharing one underlying probability. **These runs do not share one.** They span
sixteen days and many heads: between `bd4dde8` and `06745fa` the manager and test-lifecycle
surfaces alone move by **2 886 insertions and 622 deletions**. **`T074-R1` had already ruled exactly
this** — samples from materially different heads are not one population, and it required exact-head
observations rather than a rate. *A rate quoted over a changing tree is the same error as a rate
quoted from four observations on different heads*, which is the sentence this entry has carried
since `T074-R1` and which I re-made from the other direction.

**The observation and the non-discrimination argument both stand**; only the ceiling is withdrawn.
Neither `OPS-007`'s accepted residual nor the Blocked-on-`T-092` disposition ever rested on it.

**This is `T238-R2`'s ruling arriving at a second task, and neither entry saw it coming.** That
finding replaced `T-238`'s criterion 6 because *"a larger clean sample cannot distinguish **the
guard worked** from **the crash was always this rare**"*. **The sentence transfers verbatim**: swap
*guard* for *corrected teardown* and it is the paragraph below. Two tasks proposed the same
instrument against the same class of defect, and one of them had already had it ruled out.

**So what would actually move this is `T-092`, and nothing cheaper.** Clean runs cannot supply
criterion 2; only a **recurrence with a dump** can, which is what `T-092` arms `STARBASE` to
capture. Until then the honest position is unchanged: the residual is accepted under `OPS-007`, and
**the accumulating-runs plan is recorded as tried and insufficient rather than left open as
available**.

*(The paragraph below proposed that plan and is kept, because it is what was tried. It was
reasonable when written — what it missed is that its own Status paragraph already recorded the
pre-fix sample as clean, which is the fact that makes it unable to discriminate.)*

**That is a lead here, and it is the strongest one this task has ever had.** The Windows crash
recorded above happened in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — **the same file and the
same `manager` fixture** whose teardown `T-128` found at fault, with the same `ResultPump` thread
alive in the traceback. The corrected teardown is now on both platforms.

**It is still not established as the same defect, and the bar has not moved.** Windows produced an
access violation and `T-128` a SIGSEGV; this task's faulting object was never determined, so there
is still nothing to compare against; and *a stack is not a cause* — this task's own words, which
apply to the resemblance as much as to the stack. What can be done now is cheap and was not before:
**`STARBASE` runs the full suite on every push (`OPS-010`), so repeated green Windows runs against
the corrected teardown are evidence that costs nothing extra to gather.** If the crash stops
recurring there over a meaningful number of runs, that is the first positive evidence this task has
had; if it recurs, the harness fix is ruled out as its cause and that is worth just as much.

*(This block read "A candidate reproduction exists … `T-128` owns finding out". `T-128` has now
found out, and what it found does not implicate the product.)*

**The four acceptance criteria below stay unmet, deliberately not rewritten.** All four presuppose
a deliberate reproduction, which is the one thing no instrument has produced, so `OPS-007` accepts
the residual rather than redefining the bar. `T-092` arms `STARBASE` to capture a crash dump so a
recurrence supplies criterion 2 — *a stack is not a cause* — instead of another anecdote.

*(This read "Ready — still undiagnosed and still blocking Phase 1" until `OPS-007`. Before that it
read "In Review — diagnosed and fixed", which `T074-R4` found unsupported; what was fixed is
`T-090`, and `T-090` is **not** established as this crash's cause — the pre-fix sample was equally
clean, so a clean post-fix run carries no causal weight.)*

**A separate defect was found on the way and is `T-090`.** The `T-038` log listener could be left
reading a queue that something else had closed — a real race on the same thread the crash
traceback names, now fixed with tests. **That is not this task.** Calling it "diagnosed and fixed"
claimed a causal link to the historical access violation that no evidence supports, which is what
`T074-R4` reports. This task's acceptance criteria remain unmet.

*(Superseded, and worth keeping: this block read "diagnosed and fixed" on 2026-07-29. Finding a
real defect near a crash is not the same as finding the crash's cause, and the wording did not
keep them apart.)*
`0/12 at ea53c71` (run `30429327464`). That is evidence against the original 25% anecdote and is
**not** a rate: the four original observations came from materially different heads, so they are
not one population, and a single event gives no bound worth quoting (`T074-R1`). The faulting
object is unknown, product-pump versus harness is unresolved, and there is no correction mutation.
**Phase 1's Windows criterion stays unverified.** *(This block claimed "1 in 16, not 1 in 4"; that
promoted samples from changed heads into a stable rate.)*
**Owner:** Implementer
**Priority:** **Medium** — downgraded from High by `OPS-007`. It is still an access violation in a
module under `src/`, in the suite `OPS-005` and `T-073` made Phase 1's only Windows gate; what
changed is that 361 attempts produced no reproduction, so there is no work left that repetition can
do. It returns to High the moment it recurs
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
**Depends on:** **`T-092`** — which is itself Blocked on somebody at `STARBASE`. The Windows
runner exists; what does not exist is a configured crash dump, and without one a recurrence
produces another anecdote rather than criterion 2
**Relevant context:** `T-073`, `OPS-005`, `ARC-002`, `src/tracks_and_trails/downloader/result_pump.py`
**Affected surfaces:** unknown — `downloader/result_pump.py` and/or
`tests/integration/test_manager.py`
**Risk:** **High to leave.** An intermittent crash makes every green Windows run mean less than it
appears to

#### Scope

The full suite on `STARBASE` died with exit **139**:

```
tests/integration/test_manager.py::test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Windows fatal exception: access violation
Thread 0x00000c88 [ResultPump] (most recent call first):
Thread 0x000024dc [Thread-50 (_monitor)] (most recent call first):
  File "...\tests\integration\test_manager.py", line 1028 in
    test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Segmentation fault
```

**It is intermittent, and the evidence for that is unusually clean.** The failing run was
`30416495270` at `454b80e` — a **documentation-only** commit whose code is byte-identical to
`38650dd`, which had passed the same suite minutes earlier.

| Run | Head | Full suite |
|---|---|---|
| `30415333608` | `c41e2ef` | pass |
| `30416156751` | `38650dd` | pass |
| `30416495270` | `454b80e` | **access violation** |
| `30416723791` | `32f9bd2` | pass |

**One in four**, with no code difference between a pass and the failure.

**Line 1028 is before the cancellation**, which narrows this usefully. It is
`assert spin(lambda: bool(recorder.progress), timeout=60)` — the wait for the *first progress
message*, three lines above `download.cancel()`. So the crash is not in the escalation path the
test is named for. It is in ordinary message delivery: `ResultPump` is a `QThread` emitting Qt
signals carrying Python objects from its `run()`, while the main thread sits in `spin()` calling
`app.processEvents()`.

#### What is not known

Everything about the cause. Recorded as a question rather than a hypothesis dressed as one:

- Whether the fault is in **product code** (`result_pump.py`, in `src/`, so `ARC-002`'s pump is a
  candidate) or in the **test harness** (fixture teardown ordering, a receiver outliving or
  predeceasing a queued emission).
- Whether it is specific to `child_ignoring_cancellation`, which is the one worker in the suite
  that deliberately refuses to stop, or reachable by any job.
- Whether it reproduces at all outside `STARBASE`. It has never been seen on Linux across many
  full-suite runs, but Linux has never been where this project's process faults show up.

#### Diagnostic progress, 2026-07-29 — two things narrowed, cause still unknown

**It does not reproduce on Linux.** Two attempts, both clean:

| Attempt | Result |
|---|---|
| The crashing test alone, 40 iterations | **40 passed, 0 non-zero exits** |
| `tests/integration/test_manager.py` entire, 5 runs | **5 × 71 passed**, no crash, no fatal exception |

That is a negative result and is worth exactly what a negative result is worth. It does **not**
clear Linux: `T-069` was ordering-dependent and failed only when one specific test ran first, and
the Windows crash happened inside a full-suite run, not a module run. What it does establish is
that the fault is not reachable by simple repetition of the failing test on this platform, so
whatever it is depends on the platform, on suite-wide ordering, or on both.

**The most obvious cause is already defended against, and this is the more useful half.** The
classic PySide6 access violation of this shape is a `QThread` object being destroyed while its
`run()` is still executing — and `ResultPump` emits `session_ended` from *inside* `run()`, so a
slot that dropped the last reference would do exactly that. It cannot: `_release()` in
`manager.py` refuses to drop a session while its pump is live —

```python
if session.pump_started and not (session.pump_finished or session.pump.isFinished()):
    return
```

— and `_sessions.pop()` is the only thing holding the pump. `_Session` even documents the two
moments as distinct: "the thread emits `session_ended` from inside `run()`." So the first
hypothesis anyone would reach for is not it, which is worth recording so nobody spends the
afternoon re-deriving it.

**Still open.** The crash traceback named two threads — `[ResultPump]` and
`Thread-50 (_monitor)`, which is `multiprocessing`'s — and the fault was at the wait for the first
progress message. Whether it is the pump, the queue read beneath it, the interaction between them,
or the harness remains unanswered. Nothing here should be read as narrowing it to product code.

#### The ordering hypothesis, tested — 2026-07-29

The earlier attempts ran the crashing test alone and its module. The Windows failure happened
inside a **full-suite** run, and `T-069`'s precedent is that suite ordering was the entire story,
so that was the remaining Linux hypothesis. Six deliberate full-suite runs:

| Attempt | Result |
|---|---|
| Crashing test alone, 40 iterations | 40 passed |
| `test_manager.py` entire, 5 runs | 5 × 71 passed |
| **Full suite, 6 runs** | **6 × 1401 passed, every exit code 0** |

**Linux is now exhausted as a route to this defect**, at least by repetition. Three shapes of
attempt, none of which reproduced it. That is not proof of a Windows-only fault — it is the
absence of a Linux reproduction after looking in the three places worth looking.

**So the measurement has to happen on the machine that shows it.** `.github/workflows/t074-repeat.yml`
runs the suite N times on `STARBASE` and reports a rate. Three things about it are deliberate:

- **Manual dispatch, in its own workflow.** `ci.yml` is a gate and runs on every push; this is an
  instrument. Folding it in would mean paying its cost on every push or making a gate
  conditional.
- **It does not stop on the first crash.** A rate needs every iteration attempted; stopping early
  turns it back into an anecdote.
- **It separates crashes from failures by exit code.** `pytest` exits 1 for a failing assertion.
  A crash takes the interpreter with it, so the code is a signal or an access violation — and
  `T-074` is not a failing assertion. Counting them together would let an ordinary red test
  inflate the crash rate.

"About one in four" came from four ordinary CI runs, where the denominator was however many times
the gate happened to run. This makes the denominator a choice, which is what the acceptance
criteria ask for.

#### The instrument ran — 2026-07-29, run `30429327464`

Twelve full-suite iterations on `STARBASE`, every one attempted:

| Iterations | Crashes | Failures |
|---|---|---|
| **12** | **0** | 0 — `1395 passed, 20 skipped, 32 deselected` each time, 209-217 s |

**"About one in four" was a denominator of four**, and this batch is not a replacement for it.
`0/12 at ea53c71` says the crash is not reliably reproducible at that head. It does **not**
establish a rate (`T074-R1`): the four earlier runs and these twelve are not one controlled
population — the manager and the full-suite composition changed materially between them, including
new integration tests — and after a single event an aggregate point estimate is not a bound. A
clean run is unremarkable under a 25% failure probability and under a 6% one alike.

The crash is real. It happened with a traceback naming `[ResultPump]` and `multiprocessing`'s
`_monitor`, on a documentation-only commit whose code was byte-identical to a passing run.

**It stays a Phase 1 blocker, and the reason is where it landed.** The only observed native crash
is in ordinary `ResultPump` delivery — the exact `ARC-002` path Phase 1 exists to prove — so the
uncertainty cannot be resolved in favour of product safety by counting clean runs. Downgrading it
or accepting the risk is the maintainer's explicit decision to record, not an inference this task
may draw.

**Still unknown: the cause.** Nothing here narrows it. A larger batch is running to either bound
the rate further or catch one with fresh diagnostics; the workflow keeps every iteration's output,
so a crash caught there arrives with its traceback rather than as a count.

*(Superseded: this section previously read "Not yet run. The job is authored and pushed;
executing it needs `STARBASE` and is the next step on this task." It has now run.)*

#### Diagnostic session, 2026-07-29 — narrowed, not diagnosed

**Both threads named in the crash are ours.** The traceback listed `[ResultPump]` and
`Thread-50 (_monitor)`, and `_monitor` was read as `multiprocessing`'s. It is not: `multiprocessing`
declares no such function, and `_monitor` is
`core/logging.py`'s `_ToWhicheverHandlersWeHaveNow._monitor` — the `T-038` log listener's thread
body. So the crash happened with the result pump and the **logging listener** both live, which
points somewhere the earlier notes did not.

**A mechanism worth testing, stated as a hypothesis.** `_monitor()`'s `finally` closes the worker
log queue — a `multiprocessing.Queue` — and `stop_listening_for_worker_logs()` **waits for
nothing**, deliberately (`T038-R2`, and it is right to: the GUI thread must not block on a slow
handler). So the close runs on the listener thread while parent threads may still be logging into
that queue and a spawned writer may still hold the other end. Closing a multiprocessing queue
under a concurrent user is the kind of thing that faults natively instead of raising, which is the
shape this crash took. The crashing test is also the one that **kills** a worker rather than
asking it to stop, so a writer dying mid-record is in scope there and almost nowhere else.

**Nothing here demonstrates that.** It is a mechanism that fits, and the file it implicates has a
recorded reason for the behaviour. It is written down so the next attempt starts from a candidate
rather than from the whole suite.

**What was attempted, and what it cost:**

| Attempt | Result |
|---|---|
| Repeat batch, 24 full-suite iterations on `STARBASE` | **0 crashes** (run `30454206697`) |
| Both batches together, recent heads | **0 in 36** |
| Repeat batch, 15 full-suite iterations at `35fc7ec`, **post-`T-090`** | **0 crashes, 0 failures** (run `30478557533`) |
| The crashing test alone, 60 iterations on Windows | **60 passed, 0 failed, 0 crashed** |
| A direct stress of the logging-teardown race | **unusable — it hung on Linux before its first iteration** |

The last row is the honest one. The harness drives a parent thread logging continuously while a
spawned writer is killed and the listener is torn down; it never reached a print, so it deadlocked
in its own setup rather than measuring anything. A failed instrument is not a negative result, and
it is recorded as neither.

**Classification is unchanged: product versus harness is still unresolved**, and `T-074` remains a
High Phase 1 blocker. What has changed is where to look — logging teardown alongside the pump,
rather than the pump alone.

#### What the diagnostic session produced — 2026-07-29

It found a **different** defect, now filed as `T-090`: the log listener could be left reading a
queue something else had closed. The evidence for that moved there with it.

**What it did not produce is anything about this crash.** The access violation has never been
reproduced — 0 in 36 full-suite runs, 60 clean runs of the crashing test alone, 250 clean
in-process iterations — so its faulting object is still unknown and it is still unclassified
between product and harness. `T074-R4`: a real race on the same thread is a candidate, not a
cause, and the crash's absence cannot distinguish them when it was already absent every time.

**What is genuinely narrowed** is that `_monitor` in the traceback is the `T-038` log listener
rather than anything in `multiprocessing`, so the next attempt has two of our own threads to
account for rather than one.

#### Acceptance criteria

- The failure is **reproduced deliberately**, with a rate, rather than waited for
- The faulting thread and the object it touched are identified — a stack is not a cause
- The fix is proven by a mutation that restores the crash, not only by runs that stop crashing
- If it turns out to be the harness rather than the pump, that is recorded explicitly, because
  the opposite conclusion is the one a reader would assume from the file it crashed in

#### Out of scope

- Retrying, `xfail`, or a rerun plugin. `T-069` established the rule: an intermittent failure gets
  its trigger found, not its symptom hidden. The one time this project reached for a retry the
  reviewer's instruction was explicit — *do not retry or xfail*
- `T-056`, which is a different intermittent on a different platform and is `OPS-005`-downgraded

---

### T-336 — The installed app crashed once with heap corruption opening *Naming and folders…*

**Status:** **Proposed — a potential task, not open work** (maintainer, 2026-09-13). Seen once, in
`T-327`'s Sandbox session, and not reproduced by any route below. It becomes a task only if it
recurs or can be reproduced; until then nothing is owed on it.
**Owner:** Implementer
**Priority:** None while it does not recur; if it does, a crash is Critical by `TESTING.md` §14
**Phase:** Phase 5
**Promoted by:** a recurrence — ideally under the crash capture below, so it arrives with a dump
**Relevant context:** `T-289` (a Qt widget destroyed on the wrong thread — a double free); `T-074`
(an access violation never reproduced, and why repetition alone does not discriminate); `T-092`
(crash dumps on `STARBASE`)
**Affected surfaces:** unknown until a dump names them

#### What happened

The maintainer, in the installed build in Windows Sandbox: pasted
`https://www.youtube.com/watch?v=NnPvX-uMYWk` into Add URLs, waited for it to be read, opened the
row's ⋮ and chose *Naming and folders…*; the application closed. Windows recorded:

- `Application Error`: `tracks-and-trails.exe` 0.1.0.0, faulting module `ntdll.dll`
  10.0.19041.6456, **exception `0xc0000374` (heap corruption)**, offset `0xff489`, 16:30:01.
- The application log ends at 16:29:47, mid-probe of the same URL, which had also been probed at
  16:24:47 in the same session — so the dialog saw that URL twice. Nothing after: a native fault
  writes no Python record.

**Heap corruption is reported where the heap is next checked, not where it was damaged.** The menu
choice is where the process died; it is not established as the cause.

#### Not reproduced, by

- The same flow from source on `STARBASE` under the real Windows plugin — real probe, the ⋮ zone
  and the menu entry clicked through `QTest`, the maintainer's own URL, and with the dialog closed
  and reopened between two reads of it: **eight runs, no crash**.
- The output-path preview the panel opens with, under `pythonw.exe` (no console, as installed): clean.
- The 17 add-dialog tests touching the panel and the menu, under the real plugin: pass.
- The maintainer, in Sandbox: the installer built before that day's later changes (`d1e03e2`) and
  the current one (`e037c05`) — **no crash with either**; no dump was produced.

#### To capture it

Kept on `STARBASE`, not in the repository: `C:\dev\interactive-dumps.wsb` (the interactive Sandbox
plus a writable `C:\dev\sandbox-out`) and `sandbox-share\arm-crash-capture.ps1`, which turns on
full page heap for `tracks-and-trails.exe` — so a double free or overrun faults at the write that
does it — and WER full dumps into that folder. WinDbg is installed on `STARBASE` to read one.

#### If it is promoted

- A dump of the recurrence, with the faulting module and stack read
- The cause named and fixed, with a test that fails without the fix

---

*Created 2026-09-10, when Phase 4.5 was resequenced to follow the first release and this
phase became the next one to run. `T-039` also carries `**Phase:** Phase 5` and stays under
`## Blocked`, because that section is about status rather than phase.*

## Blocked

### T-344 — Show progress while a download is being processed

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-344.md)); its last criterion is a person watching a long conversion on the installed build, which the waived walk would have covered (`T-328`, 2026-09-16). Phase 4.5. *(Was In Review:)* asked for by the maintainer on 2026-09-15: a long video took a long time
to process after downloading, and nothing showed the application was still working. The maintainer
chose *both, where possible* (a real percentage where ffmpeg can report one, otherwise the step's
name, a moving bar and the time so far) and chose to ship it **in `0.1.0`**, from the options put.
Moves the candidate.
**Owner:** Implementer
**Priority:** High for `0.1.0` by that choice
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `REQ-011` (indeterminate progress), `REQ-014` (stages), `NFR-005`, `T-216`
(a finished bar is furniture)
**Affected surfaces:** `downloader/protocol.py`, `downloader/worker.py`, `downloader/ytdlp_adapter.py`,
`ui/queue_view.py`, `ui/row_delegate.py`

#### What was wrong

While a job was post-processing the row showed the download's bar, which is full once the bytes are
in; the chip read *Processing*, and nothing moved. yt-dlp's post-processor hook reports only
*started* and *finished*, and `real_run_ffmpeg` runs ffmpeg through `Popen.run`, which returns when
ffmpeg ends.

#### What changed

- **`Progress` gains `step`** (yt-dlp's hook name for the step) **and `step_fraction`** (0 to 1).
- **The worker** records the step and the media's length when a step starts, and turns ffmpeg's
  position into a fraction of that length, sent at most every 0.25 s. It checks for cancellation
  there too, so a long conversion stops when asked. Downloads only; a probe runs no step.
- **`ytdlp_adapter.ffmpeg_progress`** replaces the `Popen` that yt-dlp's `postprocessor.ffmpeg` looks
  up, for step commands only (those carrying `-loglevel repeat+info`). It adds `-progress pipe:1
  -nostats`, reads the position lines, drains standard error on its own thread, returns what
  `Popen.run` returns, and kills ffmpeg if the callback raises. If yt-dlp no longer has that module
  or `Popen`, nothing is installed and the row falls back to the moving bar.
- **The row, while processing:** the step in plain words with the time so far (*Converting to audio
  · 1:05*), the step's own percentage on the chip and the bar when known, and otherwise a moving
  bar (`BUSY_ROLE`) redrawn by a timer that stops when nothing is processing. The size keeps the
  downloaded total, and the screen-reader text names the step and its percentage or says it cannot
  be measured.
- **Words are keyed by the names yt-dlp's hook reports** (`pp_key`, which drops *FFmpeg*). The first
  version used class names and would have named nothing; the end-to-end test found it.

#### Acceptance criteria

- [x] Protocol: `step` and `step_fraction` carried and validated (`tests/unit/test_protocol.py`)
- [x] Adapter: step commands recognised, arguments inserted after the executable, positions read from
  both microsecond keys, the returned shape kept, ffmpeg killed when the callback raises, a yt-dlp
  without the module left alone, and a real `FFmpegExtractAudioPP` conversion reporting positions to
  the end of the file with yt-dlp's `Popen` restored (`tests/unit/test_ffmpeg_progress.py`)
- [x] Worker: a started step announced by name; the position as a fraction, bounded and throttled;
  no fraction without a length; cancellation at the next position; the hook around downloads and
  never probes (`tests/unit/test_step_progress.py`)
- [x] Row: the step's percentage and not the download's; the moving bar, name and time without a
  position; the time restarting per step; a step without words shown as its stage; the timer
  stopping; the moving bar drawn, moving, and routed through the real delegate; and every step yt-dlp
  can report either has words or is one of six stated quick steps (`tests/ui/test_processing_progress.py`)
- [x] End to end, a real MP3 download through the composed application reports `ExtractAudio` with a
  position reaching 1.0 (`tests/integration/test_end_to_end.py`). **Also run on `STARBASE`**
  (Windows, ffmpeg 8.1.2): the new and changed test files and this test, 166 passed
- [x] Mutations, each failing those tests: hook never installed (1); no kill on raise (1); every
  command treated as a step (2); only `out_time_us` read (2); no cancellation check (1); no throttle
  (1); zero without a length (3); the download's fraction while processing (3); never busy (2); no
  timer from the status change (2); a step erasing the size (1); the time not restarted per step
  (2); no step words (3); the delegate never painting the moving bar (1). A second timer start on
  each drawn step **survived** and was removed as redundant
- [ ] Seen by a person: a long conversion on the installed build shows the step, its progress or the
  moving bar, and the time so far

---

---

### T-342 — Add URLs and Preferences opened with their title bars above a laptop's screen

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-342.md)); its last criterion is a real Windows display at 125%, which the waived walk would have covered (`T-328`, 2026-09-16). Phase 4.5. *(Was In Review:)* reported 2026-09-15 by the maintainer from a friend's Windows laptop
(1920x1200 at 125%, the maintainer's figures): *Add URLs* and *Preferences* opened with the title bar
above the top of the screen, so the window could not be moved and no URL could be typed. Moves the
`0.1.0` candidate.
**Owner:** Implementer
**Priority:** High — the first screen a user needs could not be used on an ordinary laptop
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `T-242` and `T222-R1` (height bounds for *Preferences* and *Options*);
`T-310` (`FormatDialog.sizeHint` bounded by the screen); `NFR-005`
**Affected surfaces:** new `ui/screen_fit.py`; `ui/add_dialog.py`; `app.present`

#### What was found, measured on `STARBASE` (Windows 10, 1600x900)

- **Qt does not keep a dialog's frame on the screen.** With `QT_SCALE_FACTOR=1.25` (a 1280x720
  logical screen) *Add URLs* was placed with its frame at y = -241.
- **Add URLs grew after it was shown**, at a true 100% as well: opened at 600 pixels (Qt's cap of two
  thirds of the screen for a window never resized), centred for that, then grown to 788, its layout's
  height. With its list asking for 16 rows it grew to 1364 on the 900-high screen.
- **Nothing bounded where any dialog lands**; *Preferences* and *Options* bounded only their height.

#### What changed

- `ui/screen_fit.py`: `DialogsOnScreen`, installed by `app.present` and owned by the main window,
  fits every top-level `QDialog` when it is shown, once more after the event loop turns, and on each
  resize while visible: a maximum size of the working area less the frame, then a move so the whole
  frame, title bar first, is inside. A fit that changed something looks again, at most four times per
  showing. `fitted_geometry` is the pure rule.
- `AddUrlDialog.sizeHint` is bounded to the working area less 48 pixels (`bounded_to_screen`), and the
  dialog is given that size before it is shown.

#### Measured on `STARBASE`, 100%, *Add URLs* asking for 16 rows

| Build | Frame | Inside the screen |
|---|---|---|
| Unchanged | 1395 tall from y = 110 | no |
| Rule only | 1395 tall from y = 0 | no |
| Bounded hint and rule, no size before showing | 1395 tall | no |
| All three | 900 tall from y = 0 | **yes** |

At the real row count *Add URLs* and *Preferences* fit the 900-high screen in every build. **With
`QT_SCALE_FACTOR` at 1.25, 1.5 and 2.0 the results did not agree with a true 100% screen**: Windows
refused geometries (*Unable to set geometry*) and *Add URLs* stayed partly outside at 1.25 and 1.5
with the change. That emulation is not a real scaled display, so it is recorded rather than trusted
either way.

#### Acceptance criteria

- [x] `fitted_geometry`: above the top, too tall, past each other edge, already inside (unchanged),
  and a working area shorter than the frame (the top wins) (`tests/ui/test_screen_fit.py`)
- [x] Installed rule, offscreen: a dialog shown above and taller than the screen ends inside; one
  that grows after showing is fitted again; the rule leaves with its owner; installing twice installs
  one
- [x] `present()` installs it and a dialog of the real window is fitted
  (`tests/integration/test_composition.py`)
- [x] *Add URLs* with 40 wanted rows: its hint and its size are within the working area less 48, and it
  has a size of its own before showing
- [x] Mutations, each failing those tests: no top clamp (4); no shrink (1); no refit on resize (1); no
  fit on show (2); the hint unbounded (1); not installed by `present` (1); owned by the application
  (4); no size before showing (1)
- [ ] **Seen on a real Windows display at 125%**: *Add URLs* and *Preferences* open with the title
  bar on screen and can be moved (the friend's laptop, or a Windows machine set to 125%)

#### 2026-09-15 — the `yt-dlp` canary failed two of these tests

The canary runs the suite in **one process**, and there two tests failed at `48cf076`: a dialog that
grew after showing was not fitted again, and the rule appeared to outlive its owner. **Reproduced
locally** by running `test_composition.py` then `test_screen_fit.py` in one process. A composition
window left alive by an earlier test kept its rule installed, and **both rules counted fits on one
dynamic property**, so a dialog's budget of `MAX_PASSES` was spent twice as fast. In the application
there is one window and one rule, so the shared counter did not show there; it was still wrong.

Corrected: each rule keeps its own count (a property named for that rule). The ownership test now
asserts the rule object is destroyed with its owner, instead of watching a dialog that other live
rules may still move. A new test installs two rules and grows a dialog after showing; with a shared
counter it fails. The two files together in one process: 97 passed.

---

---

### T-340 — A failed download's log could not be opened from anywhere in the application

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-340.md)); its last criterion is a person seeing *Diagnostics…* on both platforms, which the §11 walk would have covered. The maintainer waived that walk on 2026-09-16 and assigned what it would have found to Phase 4.5 (`T-328`). *(Was Blocked:)* on its last criterion, a person seeing it on both platforms (`T328-R4`'s
walk). The implementation was approved by review on 2026-09-14
([record](reviews/T-340.md#2026-09-14--diagnostics-implementation-review)). Found 2026-09-14 while
preparing `T-328`'s §11 acceptance sheet; the maintainer chose to fix it in `0.1.0`.
**Owner:** Implementer
**Priority:** High — `REQ-019` is an MVP requirement and §11 criterion 6 names a copyable log
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `REQ-019`; `REQUIREMENTS.md` §11 criterion 6; `UX-005` §2 and §4 and their
2026-09-14 amendments; `T-084` (the log view); `T-135` (what the `⋯` holds)
**Affected surfaces:** `ui/log_view.py`, `ui/main_window.py`, `ui/add_dialog.py`

#### What was wrong

`LogView` (`T-084`) was built only by `ui/job_detail.py`, and `UX-005` §2 removed the detail pane
from the window. `queue_view.py` already said so (*"nothing in the product constructs that
widget"*), and no decision moved `REQ-019` elsewhere. Every log-view test passed against a widget
no user could reach. The candidate evidence for `3c011b8` and `246dcdf` did not notice.

#### What changed

- **`DiagnosticsDialog`** in `ui/log_view.py`: the existing `LogView` in a non-modal window titled
  *Diagnostics for* the job's title or URL, with Close. Escape closes it. Copy still copies the
  whole file (`T084-R2`).
- **The queue row's menus** offer *Diagnostics…* below the verbs, on the `⋯` and on the keyboard and
  right-click route.
- **A failed line in the Add dialog** offers it below *Read this URL again*. An unsupported URL
  fails there and never becomes a queue row, so this is the entry §11 criterion 6 is walked through.
- **Offered only when the job has logged something** (`has_job_log`). The manager creates a job's
  log file as its session opens, so a check for the file alone would offer it on every job that ever
  ran.

#### Acceptance criteria

- [x] A queue row whose job logged something offers *Diagnostics…* on the `⋯`, including when
  nothing was dropped, and on the context route; the window shows the file and Copy copies all of it
  (`tests/ui/test_row_verb_wiring.py`)
- [x] No entry for a job with no log file or an empty one (same file)
- [x] A failed Add dialog line, logged through the worker's real route and the parent's per-job
  handler, offers it and the window shows the extractor's message; a silent failure and a line that
  read offer nothing (`tests/ui/test_add_dialog.py`)
- [x] The window is non-modal, titled for its job, focused on the text, and closes from Escape and
  from Close (`tests/ui/test_log_view.py`)
- [x] Mutations, each run against the new tests: no queue entry (2 fail); the `⋯` still returning
  nothing when no verb was dropped (1); file existence instead of size (2); no Add dialog entry
  (1); the Add dialog entry without the log check (1); a modal window (1)
- [ ] Seen by a person on both platforms, as part of the §11 criterion 6 walk (`T-328`)

---
