"""The preset manager (`REQ-007`, `T-111`, `docs/UX_SPEC.md` §8).

`REQ-007` names five verbs — create, edit, duplicate, delete, set default — and this is the screen
all five are performed on. `core/settings` holds the operations; this module is the surface.

## One list, and the built-ins are in it

`P-6`, ruled by `UX-007`: built-ins and the user's own presets appear **together**, with the
built-ins marked. Two lists would ask the user to know which kind a preset is before they can look
for it, and the kind is the one thing the mark already tells them.

`core.settings.all_presets` builds the sequence rather than this module concatenating it, so the
order the manager shows and the order the dialog offers cannot drift apart.

## A list beside a form, with buttons

`P-20`, ruled by `UX-007`, and `T118-R5` is why it is not a context menu: a menu-only route is not
authority to drop an approved visible control. Every operation is a button in the list's own `Tab`
order (`NFR-005`).

## A built-in is marked, not disabled

`docs/UX_SPEC.md` §8: *"`Delete` on a built-in does nothing and is not drawn disabled — `UX-005` §5
is explicit that nothing is drawn that would be refused, so the built-in is marked as one instead."*
The form is read-only while a built-in is selected for the same reason `REQ-006` gives: a built-in
edited in place no longer matches the name it ships under, which is `REQ-009`'s promise broken at
the source. **Duplicating one is how you start from it**, and that button is live for every row.

## Nothing here learns where settings live

`save` is a sink, exactly as `OptionsDialog` takes a `PresetSink`: composition wires
`core.settings.save`, and a test hands over a list. `ARC-007` keeps the file with composition, and a
widget that opened `settings.toml` itself would be the second place that knows the path.

## The ffmpeg fact is passed in, not looked up

`ui/` may not call yt-dlp (`ARC-002`), and `app.py` already answers *"is ffmpeg here"* once for the
manager and the status bar. Asking again would be a second answer to one question that could differ
from the first — `AddUrlDialog._ffmpeg_available` carries the same note, for the same reason.
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Final, Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core import settings as settings_store
from tracks_and_trails.core.models import Preset
from tracks_and_trails.core.settings import Settings

#: Object names, so a test reaches a control by identity rather than by the text on it — the habit
#: every other dialog in `ui/` follows, and what keeps a reworded label from breaking a test that
#: is about behaviour.
PRESET_LIST_NAME: Final = "presetManagerList"
PRESET_NAME_NAME: Final = "presetManagerName"
SELECTOR_NAME: Final = "presetManagerSelector"
TEMPLATE_NAME: Final = "presetManagerTemplate"
NEW_NAME: Final = "presetManagerNew"
DUPLICATE_NAME: Final = "presetManagerDuplicate"
DELETE_NAME: Final = "presetManagerDelete"
SET_DEFAULT_NAME: Final = "presetManagerSetDefault"
APPLY_NAME: Final = "presetManagerApply"
RESULT_NAME: Final = "presetManagerResult"

NEW_TEXT: Final = "New"
DUPLICATE_TEXT: Final = "Duplicate"
DELETE_TEXT: Final = "Delete"
SET_DEFAULT_TEXT: Final = "Set as default"
APPLY_TEXT: Final = "Save changes"

#: How a built-in is marked in the one list `P-6` requires. A suffix rather than an icon: it is read
#: aloud by a screen reader in the row's own text (`NFR-005`), where a decoration would not be.
BUILT_IN_MARK: Final = " — built-in"

#: How the default is marked. `P-7` guarantees exactly one row carries this.
DEFAULT_MARK: Final = " — default"

#: The name a newly created preset arrives under, before the user renames it.
NEW_PRESET_NAME: Final = "New preset"

#: Said where a built-in is selected, in the form's own place, so the reason a field cannot be typed
#: into is on screen rather than inferred (`T-139`'s rule, one surface over).
BUILT_IN_REASON: Final = (
    "This preset ships with the application and cannot be edited or deleted. "
    "Duplicate it to start from it."
)

#: Said where a preset asks for post-processing this installation cannot perform (`REQ-024`).
#:
#: **The same shape as `merge_refusal`'s sentence and deliberately not the same words**: that one
#: refuses a chosen pair of formats, and this one describes a preset that will fail later. Both name
#: the missing tool and what to do, which is `NFR-006`'s habit.
NO_FFMPEG_REASON: Final = (
    "This preset converts or embeds, which needs ffmpeg. ffmpeg was not found, so downloads using "
    "it will fail until it is installed."
)


class SettingsSink(Protocol):
    """Where changed settings go. Answers `None` on success, or why the write failed.

    `core.settings.save` has exactly this shape, and returns the failure rather than raising for
    the reason `T109-R9` records: a read-only config directory produced a cheerful *Saved.* and no
    preset, because the only channel the writer had was an exception it had promised not to raise.
    """

    def __call__(self, settings: Settings) -> str | None: ...


class PresetManager(QDialog):
    """Create, edit, duplicate, delete and set a default preset (`REQ-007`).

    Holds a `Settings` and replaces it wholesale on every operation — `Settings` is frozen, like
    every model in `core/`, so there is no partially applied state to reason about. The sink is
    called once per operation, so a failed write is reported at the moment it happened rather than
    at close, when the user has stopped thinking about it.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        save: SettingsSink,
        requires_ffmpeg: Callable[[Preset], bool] | None = None,
        ffmpeg_available: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._save = save
        #: Whether a preset's options need ffmpeg. Injected for the module docstring's reason — the
        #: definitive answer reads a `DownloadRequest` through `ARC-002`'s boundary, and this widget
        #: is not allowed to ask yt-dlp itself. Absent means the warning is never shown, which is
        #: the honest answer for a caller that never said.
        self._requires_ffmpeg = requires_ffmpeg
        self._ffmpeg_available = ffmpeg_available
        self.setWindowTitle("Presets")
        self.setObjectName("presetManager")
        self._build()
        self._reload(select=settings_store.default_preset_of(settings).name)

    # --- construction -------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        body = QHBoxLayout()

        self._list = QListWidget(self)
        self._list.setObjectName(PRESET_LIST_NAME)
        self._list.setAccessibleName("Presets")
        self._list.currentItemChanged.connect(lambda *_: self._show_selected())
        body.addWidget(self._list)

        body.addWidget(self._build_form())
        layout.addLayout(body)
        layout.addLayout(self._build_buttons())

        self._result = QLabel("", self)
        self._result.setObjectName(RESULT_NAME)
        self._result.setWordWrap(True)
        # A refusal names the preset the user tried to save over, which is their own text
        # (`T016-R6`), and so is the name they typed.
        self._result.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._result)

        closer = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        closer.rejected.connect(self.reject)
        layout.addWidget(closer)

    def _build_form(self) -> QWidget:
        """The fields a preset is edited in. `REQ-010`'s seven are `OptionsDialog`'s, not these.

        Name, selector and template are the fields that have no other editor. The post-processing
        options already have one — `docs/UX_SPEC.md` §6's screen, which `T-109` built to be opened
        *"from the preset manager, editing a saved preset"* — and building a second set of controls
        for them here would be two screens answering one question.
        """
        form = QWidget(self)
        fields = QFormLayout(form)

        self._name = QLineEdit(form)
        self._name.setObjectName(PRESET_NAME_NAME)
        self._name.setAccessibleName("Preset name")
        fields.addRow("Name", self._name)

        self._selector = QLineEdit(form)
        self._selector.setObjectName(SELECTOR_NAME)
        self._selector.setAccessibleName("Format selector")
        fields.addRow("Format", self._selector)

        self._template = QLineEdit(form)
        self._template.setObjectName(TEMPLATE_NAME)
        self._template.setAccessibleName("Output template")
        fields.addRow("Save as", self._template)

        self._reason = QLabel("", form)
        self._reason.setWordWrap(True)
        self._reason.setTextFormat(Qt.TextFormat.PlainText)
        fields.addRow(self._reason)
        return form

    def _build_buttons(self) -> QHBoxLayout:
        """Every operation as a button in the list's own `Tab` order (`P-20`, `NFR-005`)."""
        row = QHBoxLayout()
        self._buttons: dict[str, QPushButton] = {}
        for name, text, handler in (
            (NEW_NAME, NEW_TEXT, self._create),
            (DUPLICATE_NAME, DUPLICATE_TEXT, self._duplicate),
            (DELETE_NAME, DELETE_TEXT, self._delete),
            (SET_DEFAULT_NAME, SET_DEFAULT_TEXT, self._set_default),
            (APPLY_NAME, APPLY_TEXT, self._apply),
        ):
            button = QPushButton(text, self)
            button.setObjectName(name)
            button.setAccessibleName(text)
            button.clicked.connect(handler)
            self._buttons[name] = button
            row.addWidget(button)
        return row

    # --- what the list holds ------------------------------------------------------------

    def _reload(self, *, select: str | None = None) -> None:
        """Redraw the list from `self._settings`, keeping `select` current where it still exists.

        Rebuilt wholesale rather than patched per operation: a rename, a delete and a new default
        each change a different part of a row's text, and five incremental updates would be five
        chances for the list to disagree with the settings it is drawn from.
        """
        wanted = select if select is not None else self.selected_name
        self._list.blockSignals(True)
        self._list.clear()
        # Resolved once rather than per row: `default_preset_of` is total, so it names a preset even
        # when the stored field is empty, and asking it per row would be the same answer six times.
        default = settings_store.default_preset_of(self._settings).name
        for preset in settings_store.all_presets(self._settings):
            item = QListWidgetItem(self._label_for(preset, default), self._list)
            # The name, not the label: the label carries marks, and every operation below is
            # addressed by the preset's own name.
            item.setData(Qt.ItemDataRole.UserRole, preset.name)
            self._list.addItem(item)
        self._list.blockSignals(False)
        self._select(wanted)
        self._show_selected()

    def _label_for(self, preset: Preset, default: str) -> str:
        """One row's text: the name, then whichever of the two marks apply. Both can."""
        marks = ""
        if preset.built_in:
            marks += BUILT_IN_MARK
        if preset.name == default:
            marks += DEFAULT_MARK
        return f"{preset.name}{marks}"

    def _select(self, name: str | None) -> None:
        for position in range(self._list.count()):
            if self._list.item(position).data(Qt.ItemDataRole.UserRole) == name:
                self._list.setCurrentRow(position)
                return
        if self._list.count():
            self._list.setCurrentRow(0)

    @property
    def selected_name(self) -> str | None:
        """The name of the preset the list is on, or `None` when the list is empty.

        Read through `currentRow()` rather than `currentItem()`, which PySide6's stubs type as
        always returning an item while it returns `None` for an empty list at runtime. Testing that
        against `None` type-checks as unreachable, so the check would be deleted as dead code by
        anyone who trusted the gate — and `T118-R6` is this project's record of what happens when a
        narrowing mypy believes makes real code unreachable. An `int` sentinel has no such gap.
        """
        row = self._list.currentRow()
        if row < 0:
            return None
        return str(self._list.item(row).data(Qt.ItemDataRole.UserRole))

    @property
    def selected_preset(self) -> Preset | None:
        name = self.selected_name
        return settings_store.preset_named(self._settings, name) if name is not None else None

    @property
    def settings(self) -> Settings:
        """What has been stored. Read by the caller so composition can hold the new settings."""
        return self._settings

    def _show_selected(self) -> None:
        """Put the selected preset in the form, and say what cannot be done to it."""
        preset = self.selected_preset
        if preset is None:
            return
        self._name.setText(preset.name)
        self._selector.setText(preset.format_selector)
        self._template.setText(preset.output_template)

        editable = not preset.built_in
        for field in (self._name, self._selector, self._template):
            field.setReadOnly(not editable)
        self._reason.setText(self._reason_for(preset))

    def _reason_for(self, preset: Preset) -> str:
        """The sentences that belong beside this preset. Both can apply at once."""
        reasons = []
        if preset.built_in:
            reasons.append(BUILT_IN_REASON)
        if (
            not self._ffmpeg_available
            and self._requires_ffmpeg is not None
            and self._requires_ffmpeg(preset)
        ):
            # **`T-108`/`T-109`'s behaviour, at the surface that stores the preset.** The download
            # still refuses with the worker's definitive answer; this says so while the preset is
            # being written, which is the only moment the user can do anything about it.
            reasons.append(NO_FFMPEG_REASON)
        return "\n\n".join(reasons)

    # --- the five operations ------------------------------------------------------------

    def _store(self, settings: Settings, *, select: str | None, message: str) -> None:
        """Persist `settings`, and say what happened either way.

        The sink is called before the list is redrawn, so a failed write leaves the manager showing
        what is actually on disk rather than what the user asked for.
        """
        failure = self._save(settings)
        if failure is not None:
            self._result.setText(f"Not saved: {failure}")
            return
        self._settings = settings
        self._reload(select=select)
        self._result.setText(message)

    def _create(self) -> None:
        """Create, of the five. A blank preset under a free name, ready to be edited.

        Derived from the registry's first built-in rather than from an empty `Preset`: every field
        it carries is one the user would otherwise have to fill in before the preset was usable,
        and `REQ-006`'s first entry is the application's own answer to what a sensible one looks
        like.
        """
        from tracks_and_trails.core.presets import BUILT_IN_PRESETS

        name = settings_store.free_preset_name(self._settings, NEW_PRESET_NAME)
        fresh = replace(BUILT_IN_PRESETS[0], name=name, built_in=False)
        self._store(
            settings_store.add_preset(self._settings, fresh),
            select=name,
            message=f"Created {name}.",
        )

    def _duplicate(self) -> None:
        """Duplicate, of the five — and the way a built-in is started from (`docs/UX_SPEC.md` §8).

        Live for every row, built-in included. That is the whole point of the operation.
        """
        name = self.selected_name
        if name is None:
            return
        settings, copy = settings_store.duplicate_preset(self._settings, name)
        self._store(settings, select=copy.name, message=f"Duplicated {name} as {copy.name}.")

    def _delete(self) -> None:
        """Delete, of the five.

        **Does nothing on a built-in, and the button is not drawn disabled** — `docs/UX_SPEC.md` §8
        rules exactly that, on `UX-005` §5's grounds that nothing is drawn which would be refused,
        so the built-in carries a mark instead of the button carrying a disabled state.
        """
        preset = self.selected_preset
        if preset is None or preset.built_in:
            return
        self._store(
            settings_store.remove_preset(self._settings, preset.name),
            select=None,
            message=f"Deleted {preset.name}.",
        )

    def _set_default(self) -> None:
        """Set default, of the five. A built-in may be chosen — `P-7` is about there being one."""
        name = self.selected_name
        if name is None:
            return
        self._store(
            settings_store.set_default_preset(self._settings, name),
            select=name,
            message=f"{name} is what a new download will use.",
        )

    def _apply(self) -> None:
        """Edit, of the five: the form's contents onto the selected preset.

        **A refusal is shown and nothing is written.** The only refusals `update_preset` has are a
        name already taken and a value `Preset` will not hold, and both are things the user fixes by
        typing something else — so they land beside the form as words, which is `PresetSink`'s
        reasoning for returning a string rather than raising.
        """
        preset = self.selected_preset
        if preset is None or preset.built_in:
            return
        try:
            edited = replace(
                preset,
                name=self._name.text(),
                format_selector=self._selector.text(),
                output_template=self._template.text(),
            )
            settings = settings_store.update_preset(self._settings, preset.name, edited)
        except (TypeError, ValueError) as refusal:
            self._result.setText(str(refusal))
            return
        self._store(settings, select=edited.name, message=f"Saved {edited.name}.")
