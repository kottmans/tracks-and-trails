# T-288 — the scroll bar rendered on a real display

**Taken:** 2026-08-28
**Why:** `T288-R1`. T-288's fourth acceptance criterion requires a rendered check **on a real
display**, naming platform and style, and the implementation record left it open. `T-202`'s own
history — rendered sweeps that ran both theme cases as light — is why the criterion says so, and an
earlier offscreen attempt on this task returned a light-theme result that contradicted what the
maintainer saw. So this had to be taken where the report came from.

## What it ran under

| | |
|---|---|
| Session | KDE Plasma on Wayland (`XDG_CURRENT_DESKTOP=KDE`, `XDG_SESSION_TYPE=wayland`) |
| Qt platform plugin | **`wayland`** — `QT_QPA_PLATFORM` unset, *not* `offscreen` |
| Base style | **`fusion`** (`QApplication.style().objectName()`) |
| Style actually drawing the bars | `QStyleSheetStyle` over that base, which is `T-133`'s switch |
| Qt / PySide6 | 6.11.1 / 6.11.1 |
| Host | the maintainer's Fedora desktop — the machine the report came from |

## What was inspected

Both themes, both orientations, three scrollers, three pointer states each:

- the **Settings** screen's scroller (`settingsScroll`), vertical;
- the **Options** dialog's scroller, vertical;
- a horizontal probe, because neither dialog scrolls sideways and the criteria ask for both axes.

Colours are read from a capture of the window the bars are drawn into, **not** from
`QScrollBar.grab()`. Grabbing the bar alone renders it onto an uninitialised surface, and the sheet
gives the bar and both pages `background: none` — so the groove came back `#000000` in every theme,
which is that surface showing through rather than anything on screen. The first reading of this
probe said exactly that, and it was wrong about the one sub-control whose whole question is what it
composites over.

## What it found — no rendering defect

Every reading is the sheet's own value, identical across all three scrollers and both axes:

| Theme | State | Handle measured | Sheet says | Groove / page | Stepper strip |
|---|---|---|---|---|---|
| light | rest | `#748a7e` | `border` `#748A7E` | `#f5f7f4` = `window` | `#f5f7f4` — no ink |
| light | hover | `#1e5e47` | `primary` `#1E5E47` | `#f5f7f4` | `#f5f7f4` — no ink |
| light | pressed | `#467b68` | `primary_hover` `#467B68` | `#f5f7f4` | `#f5f7f4` — no ink |
| dark | rest | `#547866` | `border` `#547866` | `#0a1712` = `window` | `#0a1712` — no ink |
| dark | hover | `#57a888` | `primary` `#57A888` | `#0a1712` | `#0a1712` — no ink |
| dark | pressed | `#75b89d` | `primary_hover` `#75B89D` | `#0a1712` | `#0a1712` — no ink |

Bar geometry is **12×504** and **12×462** vertical, **254×12** horizontal — the sheet's `width`/
`height`, so `QStyleSheetStyle` is what sized them rather than the platform.

**The groove reads as the window colour in both themes**, which is the transparent `add-page` /
`sub-page` compositing over what the bar sits on rather than drawing a second surface. **The
stepper strip carries no ink**, so `add-line` and `sub-line` are gone rather than left to render as
`T-133`'s blank blocks.

## The instrument was shown a known positive first

A probe that reports a clean result is worth nothing until it has been made to report a dirty one.
The `QScrollBar` block — 15 selectors — was stripped from `ui/theme.py`, the same run repeated, and
`theme.py` restored from a copy taken beforehand:

| Reading | With the sheet | With the block stripped |
|---|---|---|
| Handle, light **and** dark | `#748a7e` / `#547866` — the theme's | **`#525860` in both** — a platform grey the theme never chose |
| Hover | `#1e5e47` / `#57a888` | **`#525860`** — identical to rest; the control does not answer the pointer |
| Stepper strip | window colour, no ink | **`#151618`** — arrow ink, top and bottom |
| Bar width | 12px, the sheet's | 14px, Fusion's |

`2026-08-28-T288-scrollbars-on-kde-wayland.png` is the cropped comparison, light and dark, sheet
against stripped. The dark "before" panel is the maintainer's report as an image: the handle is not
faint, it is not locatable, and the only thing visible in the bar is a stepper arrow.

## Limits of this measurement

- **It is one machine and one style.** Fusion under KDE/Wayland is where the report came from; a
  different base style is a different `QStyleSheetStyle` base and is not covered here. Windows is
  `T212-R3`'s run, not this one.
- **Hover and pressed were driven by synthesised events** — `QEnterEvent`, `QHoverEvent` and
  `QTest.mousePress` on a shown window — because a Wayland client cannot warp the real pointer. The
  states are the ones the style resolved; the pointer that produced them was not a hand.
- **The colours are sampled, not swept.** One pixel per sub-control per state, at a stated offset,
  on three bars. Contrast against the groove remains asserted arithmetically from the theme's own
  values by the unit test, which is the criterion that owns the floor.
