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

    from tracks_and_trails.ui.format_dialog import FormatDialog as _FormatDialog


def screens_below_the_add_dialog() -> list[tuple[str, QWidget]]:
    """One realised instance of each, labelled, in a stable order.

    Imported inside the function because building these loads five UI modules and their Qt
    dependencies, and a module that is imported for its docstring should not pay for that.
    """
    from tracks_and_trails.core.models import FormatInfo, MediaInfo, PlaylistEntry
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS
    from tracks_and_trails.core.settings import Settings
    from tracks_and_trails.ui.add_dialog import (
        FormatPanel,
        PlaylistPanel,
        TemplatePanel,
        row_summary,
    )
    from tracks_and_trails.ui.format_dialog import FormatDialog
    from tracks_and_trails.ui.format_table import FormatTable
    from tracks_and_trails.ui.options_dialog import OptionsDialog
    from tracks_and_trails.ui.playlist_picker import PlaylistPicker
    from tracks_and_trails.ui.preset_manager import PresetManager
    from tracks_and_trails.ui.staging import Row
    from tracks_and_trails.ui.template_editor import TemplateEditor

    # **With a row in it.** An empty table publishes no operable control, and a sweep over
    # nothing is what `T-227`'s gate did the moment it succeeded.
    # **Both halves of a merge, so a *completed* selection is expressible** (`P4EXIT-R1`). One
    # video-only row cannot complete a pair, and `FormatDialog` keeps its accept button disabled
    # until the selection names a download — so a dialog built from one format published a
    # permanently disabled control and the sweep audited it in the one state a user never acts in.
    formats = (
        FormatInfo(format_id="137", extension="mp4", height=1080, has_video=True, has_audio=False),
        FormatInfo(
            format_id="140", extension="m4a", has_video=False, has_audio=True, bitrate_kbps=128.0
        ),
    )

    # **A row carrying a probe result, because a panel opens *onto* one** (`P4EXIT-R1`). The
    # panels below read `row.media` for their bodies; a row without one yields an empty body,
    # which is the vacuous sweep the line above exists to prevent.
    def staged(*, playlist: bool = False) -> Row:
        return Row(
            url="https://example.invalid/one",
            generation=0,
            media=MediaInfo(
                url="https://example.invalid/one",
                title="A clip",
                formats=formats,
                # **`MediaInfo` refuses entries on something that is not a playlist**, so the
                # populated row and the single-item one are different rows rather than one with
                # everything set. The model is right to refuse; this is the audit matching it.
                is_playlist=playlist,
                # **Entries, because a playlist panel with none publishes no rows** (`P4EXIT-R1`).
                # `entries=()` was independently measured as zero rows, so the picker's check
                # boxes — the controls that panel exists for — were audited nowhere.
                entries=(
                    PlaylistEntry(url="https://example.invalid/one#1", title="First entry"),
                    PlaylistEntry(url="https://example.invalid/one#2", title="Second entry"),
                )
                if playlist
                else (),
            ),
        )

    return [
        # **The bodies, kept.** `tools/t238_widget_cycle_probe.py` and `tools/t289_pool_gc_probe.py`
        # both read this list for *any application widget*, and a body is one. They are no longer
        # screens in their own right, which is what the panels below are for.
        ("format table", FormatTable(formats)),
        ("template editor", TemplateEditor("%(title)s.%(ext)s")),
        ("playlist picker", PlaylistPicker()),
        ("options dialog", OptionsDialog(preset=BUILT_IN_PRESETS[0])),
        ("preset manager", PresetManager(Settings(), save=lambda _settings: None)),
        # **The pages the application actually shows** (`P4EXIT-R1`, and `T-312` is why they are
        # pages). Since `T-312` a row opens onto a *panel that fills the add dialog*, never onto a
        # bare body — so the panel's own chrome, which the bodies above do not carry, was audited
        # nowhere: the summary that says which row this is, the collapse control at the top, and
        # `Done` at the foot. Both of the latter return from the panel; neither is the only way
        # out (`P4EXIT-R4`). The phase-exit review found the same class of omission
        # one surface over and it is the same fix: audit the screen, not its contents.
        ("format panel", FormatPanel(staged(), row_summary(staged()), ffmpeg_available=True)),
        (
            "playlist panel",
            PlaylistPanel(staged(playlist=True), row_summary(staged(playlist=True))),
        ),
        (
            "template panel",
            TemplatePanel(staged(), row_summary(staged()), template="%(title)s.%(ext)s"),
        ),
        # **The queue's own format dialog** (`P4EXIT-R1`, built by `T-315`). It was constructed
        # nowhere in this sweep, and the reviewer measured what that cost: removing its Cancel
        # button's name and keyboard focus left all 103 accessibility and colour tests passing,
        # with **zero** `FormatDialog` constructions. A screen no audit builds is a screen no
        # audit covers, which is `T-201`'s finding in a second place.
        (
            "queue format dialog",
            _with_a_completed_choice(FormatDialog(formats, title="A clip", ffmpeg_available=True)),
        ),
    ]


def _with_a_completed_choice[T: "_FormatDialog"](dialog: T) -> T:
    """Choose both halves, so the dialog's accept button is **enabled** (`P4EXIT-R1`).

    `FormatDialog` disables *Use these formats* until the selection names a download, which is
    `UX-005` §5 working as intended — and it meant the audit only ever saw that control disabled.
    A disabled control is a different accessibility question from an enabled one, and the criterion
    is about the states a user meets.
    """
    for entry in dialog.table.video.model.formats():
        dialog.table.choose(entry)
    sound = dialog.table.audio
    if sound is not None:
        for entry in sound.model.formats():
            dialog.table.choose(entry)
    return dialog
