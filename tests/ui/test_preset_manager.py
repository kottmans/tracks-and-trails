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

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import MediaKind, Preset
from tracks_and_trails.core.settings import Settings, add_preset, default_preset_of
from tracks_and_trails.ui.preset_manager import (
    APPLY_NAME,
    BUILT_IN_MARK,
    DEFAULT_MARK,
    DELETE_NAME,
    DUPLICATE_NAME,
    NEW_NAME,
    NO_FFMPEG_REASON,
    PRESET_LIST_NAME,
    PRESET_NAME_NAME,
    SELECTOR_NAME,
    SET_DEFAULT_NAME,
    PresetManager,
)


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
