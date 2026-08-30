"""The screens below the add dialog, built once and read by everything that needs them.

**Two consumers, one inventory, and that is the point** (`T200-R3`). `tests/ui/conftest.py`'s
`every_surface` audits these for accessibility; `tools/t238_widget_cycle_probe.py` needs the same
five for `T-238`'s criterion 4, which asks about **any** application widget. A second list would
drift, and `T238-R5` recorded the first cost of not having these five somewhere a second reader
could reach: the probe called their absence a deliberate scope when it was an omission.

**They are constructed rather than opened through their routes, and that is a bound rather than a
preference.** `AddUrlDialog.open_format_table`, `open_playlist_picker`, `open_template_editor`,
`open_options` and `open_preset_manager` are the real routes and `tests/ui/test_add_dialog.py`
asserts them — but reaching any of them needs a **staged row**, which needs a probe result against
a recorded fixture. A consumer that drove that would make its own failure ambiguous with a probe
failure, which is the trade `every_surface` already made deliberately.

**What that bound costs a lifetime measurement specifically.** A route wires signals and closures
that a bare construction does not, and closures across edges `gc` cannot traverse are exactly what
`T-273` found retaining a window. So a `gc` verdict taken over these five is a verdict about the
widget trees, not about the routes that would open them in a real session. Say so wherever it is
quoted.

**Nothing here parents these widgets**, and the caller therefore owns them. A parentless widget
left to the collector has its destructor run inside whichever test comes next, which is `T-238`'s
own shape: `every_surface` closes and `deleteLater`s each one for that reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cost, and the widgets are built at call time
    from PySide6.QtWidgets import QWidget


def screens_below_the_add_dialog() -> list[tuple[str, QWidget]]:
    """One realised instance of each, labelled, in a stable order.

    Imported inside the function because building these loads five UI modules and their Qt
    dependencies, and a module that is imported for its docstring should not pay for that.
    """
    from tracks_and_trails.core.models import FormatInfo
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS
    from tracks_and_trails.core.settings import Settings
    from tracks_and_trails.ui.format_table import FormatTable
    from tracks_and_trails.ui.options_dialog import OptionsDialog
    from tracks_and_trails.ui.playlist_picker import PlaylistPicker
    from tracks_and_trails.ui.preset_manager import PresetManager
    from tracks_and_trails.ui.template_editor import TemplateEditor

    return [
        # **With a row in it.** An empty table publishes no operable control, and a sweep over
        # nothing is what `T-227`'s gate did the moment it succeeded.
        ("format table", FormatTable([FormatInfo(format_id="137", extension="mp4", height=1080)])),
        ("template editor", TemplateEditor("%(title)s.%(ext)s")),
        ("playlist picker", PlaylistPicker()),
        ("options dialog", OptionsDialog(preset=BUILT_IN_PRESETS[0])),
        ("preset manager", PresetManager(Settings(), save=lambda _settings: None)),
    ]
