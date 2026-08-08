"""The preset manager (`REQ-007`, `T-111`, `docs/UX_SPEC.md` §8).

`REQ-007` names five verbs and `core/settings` holds all five; what is under test here is the
*surface* — that each verb is a button, that what it does reaches the store, and that the two
rulings about built-ins hold:

- **`P-6`** — one list holding built-ins and the user's own together, with the built-ins marked.
- **`P-7`** — always exactly one default, so a paste always has something to inherit.
- **`P-20`** — a list beside a form with buttons, each in the list's own `Tab` order (`NFR-005`).
- **`docs/UX_SPEC.md` §8** — `Delete` on a built-in does nothing and is *not* drawn disabled.

The store is a fake that records what it was handed, so every assertion is on what would have been
written rather than on what the widget is showing about itself.
"""

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLineEdit, QPushButton

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import MediaKind, Preset
from tracks_and_trails.core.settings import (
    Settings,
    add_preset,
    default_preset_of,
    preset_named,
)
from tracks_and_trails.ui.options_dialog import (
    EMBED_THUMBNAIL_NAME,
    SAVE_PRESET_NAME,
    OptionsDialog,
)
from tracks_and_trails.ui.preset_manager import (
    APPLY_NAME,
    BUILT_IN_MARK,
    DEFAULT_MARK,
    DELETE_NAME,
    DUPLICATE_NAME,
    EDIT_OPTIONS_NAME,
    NEW_NAME,
    NO_FFMPEG_REASON,
    PRESET_LIST_NAME,
    PRESET_NAME_NAME,
    SELECTOR_NAME,
    SET_DEFAULT_NAME,
    PresetManager,
)


def box(dialog: OptionsDialog, name: str) -> QCheckBox:
    found = dialog.findChild(QCheckBox, name)
    assert found is not None, f"no checkbox called {name}"
    return found


class FakeStore:
    """Where the manager writes. Records every call, and can be told to refuse one.

    A list rather than a file: `ARC-007` keeps the file with composition, and a test that wrote one
    would be testing `core/settings.save`, which `tests/unit/test_settings.py` already does.
    """

    def __init__(self, failure: str | None = None) -> None:
        self.written: list[Settings] = []
        self.failure = failure

    def __call__(self, settings: Settings) -> str | None:
        if self.failure is not None:
            return self.failure
        self.written.append(settings)
        return None


def a_preset(name: str = "Weekend viewing", **overrides: object) -> Preset:
    fields: dict[str, object] = {
        "name": name,
        "media_kind": MediaKind.VIDEO,
        "format_selector": "bestvideo+bestaudio/best",
        "output_template": "%(title)s.%(ext)s",
    }
    return Preset(**{**fields, **overrides})  # type: ignore[arg-type]


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def manager(qapp: QApplication, store: FakeStore) -> Iterator[PresetManager]:
    widget = PresetManager(add_preset(Settings(), a_preset()), save=store)
    yield widget
    widget.deleteLater()
    qapp.processEvents()


def press(manager: PresetManager, name: str) -> None:
    button = manager.findChild(QPushButton, name)
    assert button is not None, f"no button called {name}"
    button.click()


def field(manager: PresetManager, name: str) -> QLineEdit:
    found = manager.findChild(QLineEdit, name)
    assert found is not None, f"no field called {name}"
    return found


def labels(manager: PresetManager) -> list[str]:
    listing = manager.findChild(type(manager._list), PRESET_LIST_NAME)
    assert listing is not None
    return [listing.item(row).text() for row in range(listing.count())]


def select(manager: PresetManager, name: str) -> None:
    manager._select(name)
    manager._show_selected()


def drive_options(
    monkeypatch: pytest.MonkeyPatch, edit: Callable[[OptionsDialog], None], *, accept: bool = True
) -> list[OptionsDialog]:
    """Intercept the modal `OptionsDialog`, apply `edit` to the real widget, and answer instead.

    **The real dialog is built and its real controls are set** — only `exec()` is replaced, because
    a modal event loop in a test hangs it. That keeps the assertion about `OptionsDialog`'s own
    projection of a preset rather than about a stand-in that agrees with the manager by
    construction.
    """
    opened: list[OptionsDialog] = []

    def instead(self: OptionsDialog) -> int:
        opened.append(self)
        edit(self)
        return int(QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected)

    monkeypatch.setattr(OptionsDialog, "exec", instead)
    return opened


# --- T111-R1: the saved preset's own options screen ----------------------------------------


def test_options_on_a_saved_preset_stores_what_the_screen_changed(
    manager: PresetManager, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T111-R1`.** The accepted `P-3`/`P-16` route, asserted on what is stored.

    `_build_form` deliberately draws only name, selector and template and says the seven options
    have an editor already — and nothing here ever opened it, so `REQ-010`'s options could not be
    changed on a saved preset at all. That is most of what `T-109` put in a preset: media kind,
    codec, quality, remux, recode, thumbnail, metadata, chapters and subtitles.

    Asserted through the **real** `OptionsDialog` widget and on the settings handed to the sink,
    because a route that opens the screen and then writes something else is the same defect wearing
    a different hat.
    """
    select(manager, "Weekend viewing")
    opened = drive_options(
        monkeypatch, lambda dialog: box(dialog, EMBED_THUMBNAIL_NAME).setChecked(True)
    )

    press(manager, EDIT_OPTIONS_NAME)

    assert len(opened) == 1, "the Options… button did not open the shared editor"
    assert store.written, "the options were accepted and nothing was written"
    stored = preset_named(store.written[-1], "Weekend viewing")
    assert stored is not None, "the preset lost its name on the way through the options screen"
    assert stored.embed_thumbnail is True, (
        "the options screen was opened and its answer was discarded; REQ-010's fields are not "
        "editable on a saved preset"
    )


def test_the_options_screen_names_the_preset_it_is_editing(
    manager: PresetManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saved-preset semantics rather than the one-off route's generic title.

    This editor is reached from a list of presets, so "Options for this download" would not say
    which one is about to change.
    """
    select(manager, "Weekend viewing")
    opened = drive_options(monkeypatch, lambda dialog: None)

    press(manager, EDIT_OPTIONS_NAME)

    assert opened[0].windowTitle() == "Options for Weekend viewing"


def test_the_options_screen_offers_no_second_way_to_create_a_preset(
    manager: PresetManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No sink, so no *Save as preset…* — `UX-005` §5, nothing drawn that would be refused.

    Saving a preset from inside the editor of a preset is a second creation route on the screen
    whose whole job is managing them, and it leaves two presets where the user meant to change one.
    """
    select(manager, "Weekend viewing")
    opened = drive_options(monkeypatch, lambda dialog: None)

    press(manager, EDIT_OPTIONS_NAME)

    assert opened[0].findChild(QPushButton, SAVE_PRESET_NAME) is None


def test_cancelling_the_options_screen_writes_nothing(
    manager: PresetManager, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rejected is not accepted, and a modal that was dismissed must leave the preset alone."""
    select(manager, "Weekend viewing")
    drive_options(
        monkeypatch,
        lambda dialog: box(dialog, EMBED_THUMBNAIL_NAME).setChecked(True),
        accept=False,
    )

    press(manager, EDIT_OPTIONS_NAME)

    assert store.written == [], "a cancelled options screen still wrote to the store"


def test_options_on_a_built_in_opens_nothing_and_writes_nothing(
    manager: PresetManager, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same clause `_delete` transcribes: a built-in is not the user's to edit (`§8`).

    The button is not drawn disabled, for `UX-005` §5's reason and `T-111`'s recorded reading of it;
    what it must not do is write.
    """
    select(manager, preset_registry.BUILT_IN_PRESETS[0].name)
    opened = drive_options(
        monkeypatch, lambda dialog: box(dialog, EMBED_THUMBNAIL_NAME).setChecked(True)
    )

    press(manager, EDIT_OPTIONS_NAME)

    assert opened == [], "a built-in's options screen opened; §8 says it cannot be edited"
    assert store.written == []


def test_editing_options_keeps_the_preset_as_the_default(
    manager: PresetManager, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`P-7` survives the round trip: the name is unchanged, so the default must be too."""
    press_default = "Weekend viewing"
    select(manager, press_default)
    press(manager, SET_DEFAULT_NAME)
    select(manager, press_default)
    drive_options(monkeypatch, lambda dialog: box(dialog, EMBED_THUMBNAIL_NAME).setChecked(True))

    press(manager, EDIT_OPTIONS_NAME)

    assert default_preset_of(store.written[-1]).name == press_default, (
        "editing a preset's options took away its default"
    )


# --- P-6: one list, built-ins marked -------------------------------------------------------


def test_the_list_holds_built_ins_and_the_users_own_together(manager: PresetManager) -> None:
    """Two lists would ask the user to know which kind a preset is before looking for it."""
    shown = labels(manager)

    assert len(shown) == len(preset_registry.BUILT_IN_PRESETS) + 1
    assert any(line.startswith(preset_registry.AUDIO_MP3.name) for line in shown)
    assert any(line.startswith("Weekend viewing") for line in shown)


def test_a_built_in_is_marked_as_one(manager: PresetManager) -> None:
    """The mark is what replaces a disabled `Delete`, so its absence is a real defect."""
    shown = labels(manager)

    built_in = next(line for line in shown if line.startswith(preset_registry.AUDIO_MP3.name))
    users = next(line for line in shown if line.startswith("Weekend viewing"))

    assert BUILT_IN_MARK in built_in
    assert BUILT_IN_MARK not in users


def test_the_mark_is_in_the_rows_own_text_rather_than_a_decoration() -> None:
    """`NFR-005`: a screen reader reads the row, so the mark has to be part of what it reads."""
    assert BUILT_IN_MARK.strip("— ") == "built-in"


# --- P-7: always exactly one default -------------------------------------------------------


def test_exactly_one_row_is_marked_default(manager: PresetManager) -> None:
    marked = [line for line in labels(manager) if DEFAULT_MARK in line]

    assert len(marked) == 1


def test_a_fresh_install_marks_the_registrys_first_preset(manager: PresetManager) -> None:
    """There is a default before the user has ever chosen one, which is what `P-7` promises."""
    marked = next(line for line in labels(manager) if DEFAULT_MARK in line)

    assert marked.startswith(preset_registry.BUILT_IN_PRESETS[0].name)


def test_setting_a_default_stores_it_and_marks_it(manager: PresetManager, store: FakeStore) -> None:
    select(manager, "Weekend viewing")

    press(manager, SET_DEFAULT_NAME)

    assert store.written[-1].default_preset == "Weekend viewing"
    marked = [line for line in labels(manager) if DEFAULT_MARK in line]
    assert len(marked) == 1, "P-7's exactly-one broke"
    assert marked[0].startswith("Weekend viewing")


def test_a_built_in_may_be_made_the_default(manager: PresetManager, store: FakeStore) -> None:
    select(manager, preset_registry.AUDIO_MP3.name)

    press(manager, SET_DEFAULT_NAME)

    assert default_preset_of(store.written[-1]) == preset_registry.AUDIO_MP3


# --- the five operations, asserted on what would be stored ---------------------------------


def test_new_creates_a_preset_under_a_free_name(manager: PresetManager, store: FakeStore) -> None:
    press(manager, NEW_NAME)

    assert [preset.name for preset in store.written[-1].presets] == [
        "Weekend viewing",
        "New preset",
    ]


def test_new_twice_does_not_collide(manager: PresetManager, store: FakeStore) -> None:
    """`add_preset` refuses a collision outright, so a second create must find another name."""
    press(manager, NEW_NAME)
    press(manager, NEW_NAME)

    assert [preset.name for preset in store.written[-1].presets][-1] == "New preset (copy)"


def test_duplicate_copies_the_selected_preset(manager: PresetManager, store: FakeStore) -> None:
    select(manager, "Weekend viewing")

    press(manager, DUPLICATE_NAME)

    assert [preset.name for preset in store.written[-1].presets] == [
        "Weekend viewing",
        "Weekend viewing (copy)",
    ]


def test_duplicating_a_built_in_is_how_you_start_from_one(
    manager: PresetManager, store: FakeStore
) -> None:
    """The operation that makes refusing to edit a built-in a redirection rather than a dead end."""
    select(manager, preset_registry.AUDIO_MP3.name)

    press(manager, DUPLICATE_NAME)

    copy = store.written[-1].presets[-1]
    assert copy.name == f"{preset_registry.AUDIO_MP3.name} (copy)"
    assert copy.built_in is False
    assert copy.format_selector == preset_registry.AUDIO_MP3.format_selector


def test_delete_removes_the_selected_preset(manager: PresetManager, store: FakeStore) -> None:
    select(manager, "Weekend viewing")

    press(manager, DELETE_NAME)

    assert store.written[-1].presets == ()


def test_editing_writes_the_forms_contents(manager: PresetManager, store: FakeStore) -> None:
    select(manager, "Weekend viewing")
    field(manager, SELECTOR_NAME).setText("bestaudio/best")

    press(manager, APPLY_NAME)

    assert store.written[-1].presets[0].format_selector == "bestaudio/best"


def test_editing_can_rename(manager: PresetManager, store: FakeStore) -> None:
    select(manager, "Weekend viewing")
    field(manager, PRESET_NAME_NAME).setText("Weeknight viewing")

    press(manager, APPLY_NAME)

    assert [preset.name for preset in store.written[-1].presets] == ["Weeknight viewing"]


def test_a_rename_onto_a_taken_name_is_refused_and_nothing_is_written(
    manager: PresetManager, store: FakeStore
) -> None:
    """The refusal is words beside the form, because it is fixed by typing something else."""
    select(manager, "Weekend viewing")
    field(manager, PRESET_NAME_NAME).setText(preset_registry.AUDIO_MP3.name)

    press(manager, APPLY_NAME)

    assert store.written == [], "a colliding rename reached the store"
    assert "already exists" in manager._result.text()


# --- UX_SPEC §8: a built-in is marked, not disabled ----------------------------------------


def test_delete_on_a_built_in_does_nothing_and_writes_nothing(
    manager: PresetManager, store: FakeStore
) -> None:
    """`docs/UX_SPEC.md` §8 rules exactly this, on `UX-005` §5's never-draw-what-is-refused."""
    select(manager, preset_registry.AUDIO_MP3.name)

    press(manager, DELETE_NAME)

    assert store.written == []


def test_the_delete_button_is_not_drawn_disabled_for_a_built_in(manager: PresetManager) -> None:
    """The other half of the same clause, and the half a naive implementation gets wrong."""
    select(manager, preset_registry.AUDIO_MP3.name)

    button = manager.findChild(QPushButton, DELETE_NAME)
    assert button is not None
    assert button.isEnabled(), "the built-in was expressed as a disabled button, not as a mark"


def test_a_built_ins_fields_cannot_be_typed_into(manager: PresetManager) -> None:
    """`REQ-009`: a built-in edited in place no longer matches the name it ships under."""
    select(manager, preset_registry.AUDIO_MP3.name)

    assert field(manager, PRESET_NAME_NAME).isReadOnly()
    assert field(manager, SELECTOR_NAME).isReadOnly()


def test_a_users_own_fields_can_be_typed_into(manager: PresetManager) -> None:
    select(manager, "Weekend viewing")

    assert not field(manager, PRESET_NAME_NAME).isReadOnly()


def test_applying_to_a_built_in_writes_nothing(manager: PresetManager, store: FakeStore) -> None:
    select(manager, preset_registry.AUDIO_MP3.name)

    press(manager, APPLY_NAME)

    assert store.written == []


# --- P-20 / NFR-005: every operation is a button ------------------------------------------


def test_every_operation_is_a_button_rather_than_a_context_menu(manager: PresetManager) -> None:
    """`T118-R5`: a menu-only route is not authority to drop an approved visible control."""
    for name in (NEW_NAME, DUPLICATE_NAME, DELETE_NAME, SET_DEFAULT_NAME, APPLY_NAME):
        button = manager.findChild(QPushButton, name)
        assert button is not None, f"{name} is not a button"
        assert button.accessibleName(), f"{name} has no accessible name (NFR-005)"


# --- a failed write is reported, and nothing is claimed ------------------------------------


def test_a_failed_write_is_reported_and_the_list_still_shows_what_is_on_disk(
    qapp: QApplication,
) -> None:
    """`T109-R9`: a read-only config directory produced a cheerful *Saved.* and no preset."""
    refusing = FakeStore(failure="PermissionError: nope")
    widget = PresetManager(add_preset(Settings(), a_preset()), save=refusing)

    press(widget, NEW_NAME)

    assert "Not saved" in widget._result.text()
    assert [preset.name for preset in widget.settings.presets] == ["Weekend viewing"]
    widget.deleteLater()
    qapp.processEvents()


# --- REQ-024: a preset that needs ffmpeg says so when ffmpeg is absent ---------------------


def test_a_preset_needing_ffmpeg_says_so_when_it_is_absent(qapp: QApplication) -> None:
    """This task's fifth criterion: behave like `T-108`/`T-109` where the tool is missing."""
    widget = PresetManager(
        add_preset(Settings(), a_preset(name="Converts")),
        save=FakeStore(),
        requires_ffmpeg=lambda preset: preset.name == "Converts",
        ffmpeg_available=False,
    )
    select(widget, "Converts")

    assert NO_FFMPEG_REASON in widget._reason.text()
    widget.deleteLater()
    qapp.processEvents()


def test_the_same_preset_says_nothing_when_ffmpeg_is_present(qapp: QApplication) -> None:
    """The warning is about the installation, not about the preset — so it must not always show."""
    widget = PresetManager(
        add_preset(Settings(), a_preset(name="Converts")),
        save=FakeStore(),
        requires_ffmpeg=lambda preset: True,
        ffmpeg_available=True,
    )
    select(widget, "Converts")

    assert NO_FFMPEG_REASON not in widget._reason.text()
    widget.deleteLater()
    qapp.processEvents()
