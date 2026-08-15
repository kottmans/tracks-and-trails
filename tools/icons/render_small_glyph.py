"""Render the reduced small-size glyph master from the full logo (`T-021`).

Run from the repository root, with Pillow available:

    python3 -m pip install --user pillow
    python3 tools/icons/render_small_glyph.py

Writes `icon-small.png`, a 1024x1024 master, into
`src/tracks_and_trails/resources/icons/`. `tools/icons/render_icons.py` then renders the 16 px
and 24 px assets from it and the full logo from `icon.png`.

## What this keeps, and why it is derived rather than drawn

`T-003`'s 16 px asset meets its acceptance criterion — the note and the gold trail stay
recognizable (`T003-R2`) — and what it loses is the landscape: the trees and the mountain
collapse into the green mass. That is a property of the artwork's detail level, so no better
downscale recovers it.

**The maintainer's ruling, 2026-08-15: keep the note head, the stem and the gold trail sweep.**

This *derives* those from `icon.png` rather than redrawing them, because the second acceptance
criterion is that the glyph stay recognizably the **same mark**. A hand-drawn approximation would
have to be argued; a derivation cannot drift. Three of the four elements are the master's own
pixels:

- **The stem and the flag** are copied. Measured on the master: everything green at `x >= 512` is
  stem or flag, and the trees and the mountain end well left of it. Their curve is the most
  distinctive thing about this mark and nothing here re-cuts it.
- **The trail** is copied, and dilated by `TRAIL_GROWTH`. At 16 px the master's trail is under one
  pixel wide at its waist and drops to a broken dotted line; the growth is a fraction of a pixel at
  that size and is what keeps it a continuous sweep.
- **The head is redrawn as a plain ellipse**, and it is the one element that is. It has to be: the
  landscape *is* the head's interior, so keeping the head's own pixels would keep the trees. The
  ellipse is measured from the master's own boundary rather than chosen — see `HEAD`.
- **The sound arcs are dropped.** They are three hairlines at 1024 px and three stray gold pixels
  at 16 px. The ruling did not name them either way; they are named here rather than quietly lost.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ICONS = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails" / "resources" / "icons"

#: `ARCHITECTURE.md` §8's brand values, and the master's own dominant pixels agree with both.
FOREST_GREEN = (0x1E, 0x5E, 0x47, 0xFF)
TRAIL_GOLD = (0xD9, 0xA2, 0x4C, 0xFF)

#: Alpha below this is the master's invisible halo — `render_icons.VISIBLE_ALPHA`'s reason.
VISIBLE_ALPHA = 8

#: Left edge of the stem-and-flag region, measured on the master.
#:
#: The flag's tail reaches its lowest point at y≈515 and the stem occupies x 517..571 below that;
#: the trees and the mountain never reach past x≈500. So a single vertical cut separates the note
#: from the landscape without a mask per element.
NOTE_LEFT = 512

#: Top of the trail, measured on the master: gold above this row is a sound arc, gold below it is
#: the trail. The two never share a row.
TRAIL_TOP = 515

#: The head, measured from the master's own outline rather than chosen.
#:
#: Left edge x=261 at y≈650, bottom y=740 at x≈380, and the widest span is 261..571. Taking those
#: as the extremes gives centre (416, 615) with radii 155 and 125, which reproduces the measured
#: left edge to within 2 px at y=550 and 6 px at y=650. The master's blob is not a true ellipse —
#: it is drawn art — and a simplified glyph is the one place that difference does not matter.
HEAD = (261, 490, 571, 740)

#: Pixels of dilation applied to the trail at 1024 px, ≈0.4 px once rendered at 24 px.
TRAIL_GROWTH = 9


def is_green(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return alpha > VISIBLE_ALPHA and green > red + 25 and green > blue + 15


def is_gold(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    return alpha > VISIBLE_ALPHA and red > 150 and green > 110 and blue < 130 and red > blue + 60


def masks(master: Image.Image) -> tuple[Image.Image, Image.Image]:
    """The note (stem and flag) and the trail, as alpha masks over the master's own pixels.

    **The note is taken from alpha rather than from greenness**, and the difference is a visible
    defect rather than a preference. The stem carries a one-pixel column of `ARCHITECTURE.md` §8's
    deep-green shading — measured `(7, 30, 18)` at x=518, where the mark's two overlapping shapes
    meet — and a greenness test rejects it, because 30 is not more than 7 + 25. Keeping only the
    green pixels therefore cut a hairline slit down the whole stem, which at 16 px is a white
    speck in the middle of the note.

    Alpha has no such edge. The only thing at `x >= NOTE_LEFT` that is not the note is the sound
    arcs, and those are gold, so they come out by subtraction.
    """
    width, height = master.size
    note = Image.new("L", master.size, 0)
    trail = Image.new("L", master.size, 0)
    source = master.load()
    note_px = note.load()
    trail_px = trail.load()
    for y in range(height):
        for x in range(width):
            pixel = source[x, y]
            gold = is_gold(pixel)
            if x >= NOTE_LEFT and pixel[3] > VISIBLE_ALPHA and not gold:
                note_px[x, y] = pixel[3]
            if y >= TRAIL_TOP and gold:
                trail_px[x, y] = pixel[3]
    return note, trail


def build(master: Image.Image) -> Image.Image:
    """The reduced glyph: a plain head, the master's stem and flag, the master's trail."""
    note, trail = masks(master)

    glyph = Image.new("RGBA", master.size, (0, 0, 0, 0))

    # The head first, so the stem and the trail both sit on top of it exactly as they do on the
    # full mark.
    head = Image.new("L", master.size, 0)
    ImageDraw.Draw(head).ellipse(HEAD, fill=255)

    glyph.paste(FOREST_GREEN, mask=head)
    glyph.paste(FOREST_GREEN, mask=note)

    # **The silhouette the trail is allowed to occupy.** On the full mark the trail runs to the
    # head's own outline, and the head here is a plain ellipse rather than that outline — so
    # without this the gold spills past the green along the bottom and lower left, and the glyph
    # reads as a trail with a bite out of the disc behind it.
    silhouette = Image.new("L", master.size, 0)
    silhouette.paste(head, mask=head)
    silhouette.paste(note, mask=note)

    # **Solid gold through the mask, not the master's own pixels.** The trail on the full mark is
    # bordered in white, and copying the master through a *grown* mask brings that border with it —
    # which at 16 px is a pale fringe on both sides of a sweep barely a pixel wide, exactly the
    # mush this glyph exists to avoid. Gold directly against green is the highest-contrast pair the
    # palette has.
    #
    # **Grown before it is pasted, not after**, so the widening happens in the mask rather than in
    # the colour: `MaxFilter` over an RGBA image would drag the green out with it.
    grown = trail.filter(ImageFilter.MaxFilter(TRAIL_GROWTH * 2 + 1))
    clipped = Image.new("L", master.size, 0)
    clipped.paste(grown, mask=silhouette)
    glyph.paste(TRAIL_GOLD, mask=clipped)
    return glyph


def main() -> None:
    master = Image.open(ICONS / "icon.png").convert("RGBA")
    if master.size != (1024, 1024):
        raise SystemExit(f"expected a 1024x1024 master, found {master.size[0]}x{master.size[1]}")

    glyph = build(master)
    visible = glyph.getchannel("A").point(lambda value: 255 if value > VISIBLE_ALPHA else 0)
    bounds = visible.getbbox()
    if bounds is None:
        raise SystemExit("the reduced glyph came out empty")
    print(f"reduced glyph artwork: {bounds[2] - bounds[0]}x{bounds[3] - bounds[1]} at {bounds}")

    glyph.save(ICONS / "icon-small.png", format="PNG", optimize=True)
    print(f"wrote icon-small.png to {ICONS}")


if __name__ == "__main__":
    main()
