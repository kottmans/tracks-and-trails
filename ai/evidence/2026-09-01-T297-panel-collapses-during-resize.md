# The open panel collapses to 26 px on every resize step, and the row underneath is painted

**Taken:** 2026-09-01, on Spock, by `tools/t297_resize_session.sh` — a disposable
`kwin_wayland --virtual` with its own bus and its own XDG roots. **The maintainer's session was not
touched.**
**Head:** `58630a0`.
**Platform:** Fedora 44, Linux 7.1.4-204.fc44, nested **KWin/Wayland**, `QT_QPA_PLATFORM=wayland`.
**Runtime:** Python 3.14, PySide6 6.11.1.
**Instrument:** `tests/ui/_t297_resize_probe.py`.

**Recorded before anything was changed**, which is `T-297`'s first acceptance criterion.

## The report this answers

*"When changing the window size while the naming information is up, the thumbnail cuts in and out
very rapidly. That shouldn't happen."* — the maintainer, 2026-08-28, filed as `T-297` **without a
cause**.

## What was measured

A staged playlist row with its template panel open, the window walked 760 → 430 → 760 px in 6 px
steps — 110 steps, because a drag is continuous and the question is what happens *between* two
settled states.

```
platform            : wayland
resize steps        : 110
delegate paints     : 126 (before the resize: 2)
paints of the row   : 126
EXPOSED paints      : 107        # the delegate painted the open row where the panel did not cover it
panel resize events : 214
  first twenty (old h -> new h): 354->26 26->354 354->26 26->354 354->26 26->354 354->26 26->354
                                 354->26 26->354 354->26 26->348 348->26 26->342 342->26 26->336
                                 336->26 26->336 336->26 26->336
  resizes TO the 26 px minimum: 107
  steps where the settled panel matched the row: 109/110
VERDICT: REPRODUCED — 107 paints of the open row were not covered by its panel
```

**The panel oscillates once per resize step**: full height → **26 px** → full height. 107 collapses,
107 exposed paints, 110 steps. `26` is the geometry an index widget keeps when the view has not
given it one — the same number `T-108`'s comment records as `190x26`, and the same one `T-296` was
about at mount.

## The cause

**`_on_list_resized` re-measures the row and then defers the panel's geometry by one event-loop
turn, and the view repaints inside that gap.**

1. The list's `resizeEvent` emits `viewport_resized`.
2. `_on_list_resized` emits `dataChanged(SizeHintRole)` — the row's height depends on the viewport,
   because `panel_height_for` reads `viewport().height()` — and the view re-lays out. The index
   widget is left at its own minimum, 26 px.
3. **The view paints.** `RowDelegate.paint` draws the thumbnail on every row it is given, expanded
   or not; its own comment says an opened row *"is covered by its panel"*, so it does not check.
   With 26 px of a 354 px row covered, the row's tile, headline and detail are on screen.
4. `relayout_panel`'s `QTimer.singleShot(0, restore)` runs and sets the right geometry.

Step 4 is why **109 of 110 steps settle correctly** — and why sampling after each step, which is what
the first `T-297` reading did, saw nothing wrong. The defect lives entirely between steps 2 and 4.

**The deferral is deliberate and is not itself the bug.** `T204-R4` put it there: `dataChanged` is
delivered *before* the view re-measures, so reading `visualRect` during the emit returns the stale
rectangle, and an earlier fix that stamped it onto a live panel **made the panel vanish on open**.
Any correction has to give the panel a right-sized geometry without reading a rectangle the view
has not recomputed yet.

## Why offscreen said nothing

The same instrument, same 110 steps, on the offscreen platform:

```
platform            : offscreen
delegate paints     : 29
EXPOSED paints      : 0
VERDICT: NOT REPRODUCED
```

**Offscreen coalesces paints** — 29 against a compositor's 126 — and never lands one inside the gap.
This is why the task was filed without a cause: `T-297`'s first reading measured thumbnail *loads*
(0) and panel geometry *after each settled step* (correct), and both are true.

## The capture, and what it is not

`2026-09-01-T297-panel-collapses-during-resize.png`.

**It is a reconstruction of the measured state, not a frame from the drag**, and the difference
matters. The nested compositor renders to its own framebuffer, there is no screencast portal in this
harness, and `QWidget.grab()` re-renders a widget rather than reading the frame that was shown — so
a "screenshot" taken mid-drag would picture an already-repaired panel. Instead the panel was put
back into the exact geometry the trace above recorded, 26 px, and the viewport was rendered. What it
shows is what the row underneath contributes to a frame in that state: the tile, the headline and
the detail lines, with a 26 px sliver of panel at the top.

## What this does not establish

- **That it is `T-296`'s cause.** It is not. `T-296` was `scrollTo` undoing `setGeometry` at *mount*;
  this is a deferred restore during *resize*, a different call path with a different trigger. They
  are the same family — panel geometry against paint timing — and `T-297`'s criteria ask for that
  distinction to be made rather than assumed.
- **That a person's drag produces exactly 107 exposures.** A synthetic walk of 110 steps is not a
  pointer drag; it establishes the mechanism and its rate per step, not a user-visible count.
- **Anything about Windows.** Measured on nested KWin/Wayland only.
