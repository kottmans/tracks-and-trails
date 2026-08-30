# Phase 4 — the built-window checklist

**Purpose:** What a person looks for when running the application, to evidence Phase 4's
*"the built window matches the flow that was agreed"* exit criterion.
**Owner:** Maintainer runs it; `T-212` owns it.
**Status:** Written 2026-08-16, ahead of the run — which is `T-212`'s first acceptance criterion,
so that the run executes a list rather than improvises one.
**Required by:** `IMPLEMENTATION_PLAN.md` §Phase 4 exit criteria (added 2026-08-09 by maintainer
ruling).
**Rows:** **48**, across seven sections — counted from this file, not estimated. *(47 when written; `6.1a` was added 2026-08-28 with `T-292`, which gave the download folder a behaviour the list did not previously describe.)*
**Derived from:** `docs/UX_SPEC.md` §2, §3, §8, §11, §12; the accepted criteria of the surfaces
Phase 4 added or reshaped — `T-146`, `T-195`–`T-202`, the `T-203` row chain (`T-204`, `T-207`,
`T-209`, `T-210`, `T-211`, `T-223`, `T-224`), `T-216`, `T-217`, `T-234`, `T-243`, `T-244`,
`T-246`, `T-021`; and `docs/CRITERION_8_CHECKLIST.md`, whose shape and guards this follows.

---

## Why this exists and why CI does not replace it

Phase 2's equivalent found **eleven defects in one sitting, none reported by any gate, against
2153 passing tests** — and needed two further runs to reach 40 of 40. Three of the eleven were
invisible to tests because the test arranged what the window lacks; one was deterministic and
looked intermittent because it depended on window width. Phase 4 has already produced the same
shape twice more: the dark palette that was never applied, and rendered sweeps that ran both theme
cases as light. **A green suite is evidence about assertions, not about the window.**

**Every row says what a user should see, never which commit changed it.** A row reading *"check
`T-246`'s fix"* has already failed; the same row reading *"the two queue verbs are on the `File`
menu with their shortcuts shown"* stands on its own. Task ids in the last column are
back-references, not the row's content.

**A failed row becomes its own task entry** — filed, never repaired inline and re-claimed.
`P2EXIT-R12` was a checklist claiming a pass over its own recorded failures; the recorded run is
the deliverable, and the pass is only what it hopefully shows.

## Running it

```bash
cd /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails
git log --oneline -1          # record this: the run is evidence about one head
.venv/bin/python -m tracks_and_trails
```

Run on the exact candidate head and record it — a run against a head that then moves evidences
nothing (`P2EXIT-R8`). Record the result in `ai/evidence/` item by item, pass or fail, in the
format of `ai/evidence/2026-08-05-criterion-8-checklist-run.md`.

Rows marked **both** are checked in the light **and** dark themes — the selector is in
`Settings → Settings…` now, so no throwaway launcher is needed. Rows needing the network say so;
everything else runs offline. §8's arranged failures say how to arrange each one.

### What this run deliberately does not cover

- **Screen-reader announcement coherence.** The amended criterion puts Orca and Narrator in the
  pre-release session for both platforms; this run may note anything heard, but no row asks for it.
- **Windows.** `OPS-003`; the runner covers the automated half, the pre-release session the rest.
- **The frozen build.** Phase 5's.

---

## 1 · Launch and window chrome

| # | What to look for | Task |
|---|---|---|
| 1.1 | The window opens titled with the application name, and **the titlebar/taskbar icon reads as a music note at small size** — stem and head distinct, not a smudge of landscape | `T-021` |
| 1.2 | The window is **one list — no tabs, no detail pane**. Selecting a row opens nothing | `UX-005` §2 |
| 1.3 | Close and relaunch: the window returns at its previous size and position, on screen | `T-027` |

## 2 · Theme

| # | What to look for | Task |
|---|---|---|
| 2.1 | `Settings → Settings… → theme`: switching light↔dark restyles the **whole** window live — no panel, menu, list or dialog stays in the old palette (the criterion-8 run found dark had never been applied at all) | `T-146`, `T-120` |
| 2.2 | **both** — Open every screen once in each theme: main window, add dialog, Settings, About. Nothing is unreadable, nothing is grey-on-grey | `T-202` |
| 2.3 | **both** — Tab through the main window and the Settings screen: **the focused control is obvious at a glance** — a visibly thicker edge or a ring, not a faint hue change. Check a button, a text field, a list, the Settings scroller | `T-202` |
| 2.4 | **both** — Tab to a **filled brand button** (a default button in a dialog): the focus ring is visible *on the brand fill*, not gold-on-green | `T-202` |
| 2.5 | **both** — In the format table, Tab to the header: the current column carries a visible rectangle, and ←/→ move it | `T-202`, `T107-R3` |

## 3 · Menus and keyboard routes

| # | What to look for | Task |
|---|---|---|
| 3.1 | `File` reads **Add URLs... · Start · Clear finished · ─── · Quit**, with shortcuts shown beside the two queue verbs (`Ctrl+R`, `Ctrl+Shift+C`) | `T-246` |
| 3.2 | Start the queue from the **menu**: the toolbar control flips to `Stop` too — one control, not two copies. Stop it from the **toolbar**: the menu item reads `Start` again | `T-246`, `T-130`, `UX-006` |
| 3.3 | On a **freshly opened** window with one queued row, press `Shift+F10` **before touching anything**: the row menu opens on the queue's current row — not on a toolbar widget, not nowhere | `T-234`, `T203-R3` |
| 3.4 | Tab from the window chrome: **focus lands in the queue**, never on a toolbar button | `T-234` |
| 3.5 | Every verb the window offers is reachable without a pointer: walk `File`, `Settings`, `Help`, the row menu, and the add dialog's footer by keyboard alone | `T-200`, §11 |
| 3.6 | Menu items and buttons read as **English verbs a user recognises** — no yt-dlp vocabulary anywhere the window speaks | `T-156`/`T-159` lesson |

## 4 · The queue

| # | What to look for | Task |
|---|---|---|
| 4.1 | The queue **opens stopped**, and says so in words where the work is — the status statement is present, readable, and not conveyed by colour alone (**both**) | `UX-006`, `T-181`, `T-192` |
| 4.2 | A row added to a stopped queue reads **Held** — never *Paused* | `UX-006` |
| 4.3 | The run control **looks different** running than stopped, beyond its label | `T-149` precedent |
| 4.4 | A row shows thumbnail, title, uploader and duration, progress and state; **a finished row's line reads uploader · duration · final size** — the fact once, not three times | `T-216` |
| 4.5 | An **interrupted** row (kill the app mid-download, relaunch) states what happened **once, in one voice**, with the next step on the offer line — not the same sentence twice | `T-243` |
| 4.6 | A playlist group draws its segment bar **and** a detail line that names and counts each state in words (**both**) | `T-140`, `T-202` |
| 4.7 | **An expanded playlist child draws every verb its state offers** — a queued child shows `↑ ↓ Cancel Remove`, a failed one `Retry` and `Remove` — and **removing one entry leaves the rest of the playlist** — and expand/collapse works from the keyboard (←/→) as well as the twisty | `T-244`, `T-293`, `T140-R5` |
| 4.8 | A row's media-kind mark is legible at row size: hollow film frame for video, and it does not overlap text (**both**) | `T-217` |
| 4.9 | `Clear finished` removes completed and cancelled rows only; failed rows stay; **the status bar says files are kept** | `UX-001`, `T-132` |
| 4.10 | **The list never scrolls sideways** at any window width; long titles elide | `T-151` |

## 5 · The add dialog — the reshaped row

| # | What to look for | Task |
|---|---|---|
| 5.1 | Paste one URL: the box keeps a **capped height** and the staged row appears below with title, channel and thumbnail after its probe *(network)* | `T-210`, `UX-003` |
| 5.2 | The row's **Download as control holds presets and nothing else** — no entry opens a window, and an unoverridden row shows the inherited preset **by name**, never blank. Opened, its first entry reads that name followed by *— following the batch* | `UX-011`, `T-203`, `T-284` |
| 5.3 | The **⋮ zone is drawn as a button** — border, hover, pressed — and opens the row menu; right-click, the Menu key and `Shift+F10` open **the same menu**, anchored to that row | `T-224`, `UX-012` |
| 5.4 | The menu's *Just this item* group holds `Choose specific formats…`, `Options…`, `Naming and folders…`; a playlist row's Remove reads **`Remove this playlist (N items)`** with the real count | `UX-011`, `UX-012` |
| 5.5 | `Manage presets…` is in the **dialog footer**, not on any row | `UX-009` |
| 5.6 | **Watch the row's panel at the exact moment it opens — both kinds** (the format table via `Choose specific formats…`, and a playlist's entry panel): no small box flashes at the top-left before the panel lands. *(Maintainer-directed row: both panel kinds spend one event-loop turn at 190×26 offscreen; the first real-display observation saw nothing, and this is the deliberate second — `T-221` was closed on the strength of the first.)* | `T-221`, `T-209` |
| 5.7 | The opened panel **covers its row with a visible way out at the top**, and the wheel scrolls the list **smoothly per pixel**, never catapulting past the panel | `T-210` |
| 5.8 | A URL that will not probe **stays in the dialog** with the extractor's message verbatim and its own retry; *Add to queue* counts only what resolved | `UX-003`, `NFR-006` |
| 5.9 | The template preview is labelled as the **intended** path where the container is yt-dlp's to choose | `REQ-011` |

## 6 · Settings — all eight, and the screen itself

| # | What to look for | Task |
|---|---|---|
| 6.1 | The screen holds **all eight** settings — download folder, theme, concurrency, ffmpeg location, cookie source, default preset, output template, network (proxy · speed limit · retries) — and **no "still to come" text anywhere** | `T-146`, `T-195`–`T-199` |
| 6.1a | The download folder can be **typed or pasted into** as well as chosen; a folder that does not exist is **refused in words beside the field**, and the field goes back to the one in force | `T-292` |
| 6.2 | Every control **applies as it is changed** — no OK button hunting; Esc and `Close` both leave. **The download folder is the one exception**: it commits when you leave the field or press `Return`, because applying a path as it is typed would set every prefix of it | `T-146`, `T-292` |
| 6.3 | The `−`/`+` steppers look like a matched pair of buttons and **each disables at its end of the range** | `T-236`, `T-141` |
| 6.4 | **Tab through the whole screen**: the focused control **scrolls into view** — nothing gains focus while invisible below the fold | `T-242` |
| 6.5 | Cookie source: the three radios switch which controls below are live; the file chooser and browser picker appear only for their own choice; **no cookie path ever appears in the status bar or any visible log** | `T-197` |
| 6.6 | ffmpeg: the capability line reports what was found **in words**; with no ffmpeg, the merge offer is absent elsewhere and this line says why | `T-199` |
| 6.7 | Default preset and template: emptying the template means **the application default**, and the screen says so rather than showing an error | `T-195` |
| 6.8 | Network: the three controls name their meaning — retries reads as **yt-dlp's retries**, not the file transfer's | `T-196` |
| 6.9 | yt-dlp version: the current version is **shown**; `Update` changes the shown version; `Revert` restores it; the controls refuse a second operation while one runs *(network)* | `T-198` |

## 7 · Error surfaces — arranged, not awaited

Arrange each; the row must say **what failed, why, and what to do** in its own words, with the
next step on the offer line — and a class with **no honest next step keeps the standard anatomy**.

| # | Arrange it by | What to look for | Task |
|---|---|---|---|
| 7.1 | Make the output directory unwritable (`chmod -w`), then download | The refusal appears **where the user is looking**, names the folder problem, and offers the fix route | `T-201`, `T-158` lesson |
| 7.2 | Paste a URL on a host that resolves nowhere *(network off)* | A network-shaped failure in plain words, retry offered; the extractor's own last line is there **verbatim, once** | `T-201`, `T-243` |
| 7.3 | Paste a page that is not a video (any article URL) *(network)* | An unsupported-URL failure that does not blame the network, no raw traceback anywhere | `T-201` |
| 7.4 | A DRM/geo-style failure if one is at hand *(optional, network)* | **No next-step line at all** — the row keeps the standard anatomy exactly, because there is nothing honest to suggest | `UX-005` §3, `T-201` |
| 7.5 | Any failed row, both themes | The failure is legible in **both** palettes and never carried by colour alone | `T-202`, `NFR-005` |

---

## Recording the run

Copy this table structure into `ai/evidence/<date>-T212-checklist-run.md` with the head SHA,
platform, runner, and per-row **pass / fail / not run** — a *not run* row states why and what
would make it runnable, the way the criterion-8 record did for its two. Findings get task entries;
the evidence file links them the way the 2026-08-05 run linked its eleven.
