"""`T-255`: the *Extractor arguments* group of the preset editor.

Ruled 2026-10-19 (`UX-015` amended, third): one text field above the options field, one
`KEY:ARG=VALUE;…` per line, checked as typed and shown back merged and normalized. Driven through
the editor's own controls by object name.
"""

from collections.abc import Callable, Iterator
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel, QPlainTextEdit

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.extractor_args import FORBIDDEN
from tracks_and_trails.core.models import Preset
from tracks_and_trails.ui.options_dialog import (
    EXTRACTOR_ARGS_NAME,
    EXTRACTOR_ARGS_REFUSALS_NAME,
    OptionsDialog,
)


@pytest.fixture
def editor(qapp: QApplication) -> Iterator[Callable[..., OptionsDialog]]:
    built: list[OptionsDialog] = []

    def build(preset: Preset | None = None) -> OptionsDialog:
        dialog = OptionsDialog(preset or preset_registry.BEST_VIDEO)
        built.append(dialog)
        return dialog

    yield build

    for dialog in built:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


def field(dialog: OptionsDialog) -> QPlainTextEdit:
    found = dialog.findChild(QPlainTextEdit, EXTRACTOR_ARGS_NAME)
    assert found is not None
    return found


def refusals(dialog: OptionsDialog) -> str:
    found = dialog.findChild(QLabel, EXTRACTOR_ARGS_REFUSALS_NAME)
    assert found is not None
    return found.text()


def ok(dialog: OptionsDialog) -> bool:
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    return buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_the_editor_shows_the_preset_s_arguments_merged_and_normalized(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**Ruling 4**: one line per key, arguments in order, whatever was typed."""
    preset = replace(
        preset_registry.BEST_VIDEO,
        name="Args",
        extractor_args=(
            ("twitch", "client_id", ("abc",)),
            ("youtube", "lang", ("fr",)),
            ("youtube", "player_client", ("web", "ios")),
        ),
    )

    dialog = editor(preset)

    assert (
        field(dialog).toPlainText() == "twitch:client_id=abc\nyoutube:lang=fr;player_client=web,ios"
    )
    assert dialog.result_preset().extractor_args == preset.extractor_args


def test_typed_lines_are_merged_into_the_result(editor: Callable[..., OptionsDialog]) -> None:
    dialog = editor()

    field(dialog).setPlainText("YouTube:player-client=web\nyoutube:lang=fr")

    assert refusals(dialog) == ""
    assert ok(dialog)
    assert dialog.result_preset().extractor_args == (
        ("youtube", "lang", ("fr",)),
        ("youtube", "player_client", ("web",)),
    )


@pytest.mark.parametrize(
    ("typed", "said"),
    [
        ("nosuchie:anything=1", "nosuchie is not a name yt-dlp reads"),
        ("youtube:nosucharg=1", "youtube has no argument called nosucharg"),
        ("youtube:innertube_host=example.com", FORBIDDEN["youtube", "innertube_host"]),
    ],
)
def test_what_yt_dlp_would_ignore_or_is_forbidden_is_refused_as_typed(
    editor: Callable[..., OptionsDialog], typed: str, said: str
) -> None:
    """**Checked as typed** (ruling 4), and the reason shown; *OK* waits until it is gone."""
    dialog = editor()

    field(dialog).setPlainText(f"youtube:lang=fr\n{typed}")

    assert said in refusals(dialog)
    assert not ok(dialog)
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted

    field(dialog).setPlainText("youtube:lang=fr")

    assert refusals(dialog) == "" and ok(dialog)


def test_the_field_names_itself_for_a_screen_reader(editor: Callable[..., OptionsDialog]) -> None:
    dialog = editor()

    assert field(dialog).accessibleName() == "Extractor arguments"
    assert "youtube:player_client=web" in field(dialog).accessibleDescription()


def test_a_value_ending_in_a_backslash_survives_accepting_and_reopening(
    editor: Callable[..., OptionsDialog],
) -> None:
    r"""**`T255-R2`, the review's case through the real editor**: `x=\` beside `y=2` was shown back
    as `x=\,y=2`, which reads as one value, so reopening the editor and accepting it again changed
    the preset's arguments without a word."""
    first = editor()
    field(first).setPlainText("generic:key_query=x=\\ ,y=2")
    assert refusals(first) == "" and ok(first)
    accepted = first.result_preset()
    assert accepted.extractor_args == (("generic", "key_query", ("x=\\", "y=2")),)

    reopened = editor(replace(accepted, name="Args"))

    assert refusals(reopened) == "" and ok(reopened)
    assert reopened.result_preset().extractor_args == accepted.extractor_args
