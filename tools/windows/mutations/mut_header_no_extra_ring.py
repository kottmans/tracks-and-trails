"""`T329-R2`: the header stops drawing its own focus ring, on Windows.

`T-329`'s acceptance asks for the no-geometry-focus mutation **on both platforms**. The Linux half
is `tests/ui/test_colour_is_never_alone.py`'s own reasoning plus the reviewer's run; this is the
Windows half, and the reason it needs a real desktop run rather than an argument is that the
number the gate compares against — how many pixels a focused header changes — is drawn by the
platform style, and Windows draws **386** where Linux draws 430.

**A rendered-control mutation, not a changed measurement.** `SortableHeader.paintSection` is
replaced by `QHeaderView.paintSection`, so the application's extra ring is never painted and the
control falls back to whatever the native style does on its own. That is the real defect the
check exists to catch: focus that stops changing geometry.

EXPECTED TO FAIL, in both palettes. A pass here means the floor no longer distinguishes a header
that draws its focus from one that does not, on this platform.
"""

from PySide6.QtWidgets import QHeaderView

from tracks_and_trails.ui.format_table import SortableHeader

SortableHeader.paintSection = QHeaderView.paintSection
