# Criterion 8 — checklist run, 2026-08-05

**Procedure:** `docs/CRITERION_8_CHECKLIST.md`
**Head:** `f2ec6b7`
**Platform:** kirk — Fedora 42, X11
**Run by:** the maintainer
**Result:** **Not met. Eleven findings.**

`P2EXIT-R10` requires this run because *"automated checks alone are not sufficient evidence for
this explicitly visual criterion."* That judgement is now measured rather than argued: **eleven
defects in one sitting, none of which any gate had reported**, against a suite of 2153 tests that
was green throughout.

## What was found

| Finding | Belongs to | Kind |
|---|---|---|
| `T-149` | `T-132` — the style sheet declares `:hover`, `:pressed`, `:disabled` and not `:checked` | reachability |
| `T-151` | `T-134`, `T-135` — the list scrolls sideways, so verbs sit outside the viewport | reachability |
| `T-152` | `T-135`, `T124-R1` — the keyboard route needs a mouse click first | reachability |
| `T-153` | `T-137` — the flat-extraction fix reached the entries and not the playlist | drawing |
| `T-154` | `T-140` — a child's picture is drawn at the pixmap's size, over its own text | drawing |
| `T-155` | `T-140` — cumulative rounding merges the bar's blocks at most widths | drawing |
| `T-157` | `T-140`, `T140-R3` — a retargeted playlist can report neither format | design gap |
| `T-150` | new | the add dialog sets no size at all |
| `T-156` | new | the MP3 preset never states its bitrate |
| `T-158` | `T-086` | the refusal is reported where nobody is looking |
| `T-159` | new | History prints yt-dlp's format id |

## Three shapes, and the third is the one to act on

**Drawing** — `T-153`, `T-154`, `T-155`. The model is right in every case; the painter is not.

**Reachability** — `T-149`, `T-151`, `T-152`, `T-158`, and the theme itself. Behaviour that exists,
is tested, and cannot be got to. `theme.DARK` is the extreme case: built, contrast-gated, fought
over in `T130-R1`, and **never applied by the running application**, which calls `theme.apply(app)`
with no argument.

**Vocabulary** — `T-156`, `T-159`. The window speaks yt-dlp where it should speak English.
`T126-R2` fixed this for a row and `T140-R3` for a group header; History still prints `251`. Fixed
twice, still shipping — which says the answer wants to be structural rather than per-surface.

## Two things this run says about the gates

**Three of the eleven were invisible to tests because the test arranged what the window lacks.**
`T-152`'s helper calls `setCurrentIndex()` before pressing the key, so it proves the fallback works
*given* a current row and cannot speak about a window where none was ever set — which is every
window a user opens. That is `T126-R3` and `T140-R1`'s lesson at a third layer.

**`T-155` is deterministic and looked intermittent.** Seven of fifteen gaps vanish at 600 px and
none at 800 px, so it renders correctly at some widths and not others. A test that rendered one
width and looked would have passed.

## What this does not cover

Rows **3.6** (a failed entry drawn distinctly) and **§5** (both themes) were **not run**. The first
needs a download to fail and the checklist did not say how to arrange one until afterwards; the
second needs a theme control that does not exist (`T-146`). Both rows are now answerable — 3.6 by
making the download directory unwritable, §5 by the throwaway launcher — and **neither has been
checked**, so this run is evidence about 29 of 31 rows.
