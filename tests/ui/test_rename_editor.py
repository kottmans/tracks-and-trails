"""The rename editor widget and the path preview under it (`UX-014`, `REQ-011`, `T-112`).

These were the template editor's tests until `UX-014` retired that widget; the preview rulings they
assert moved with the preview, and hold for the name a user types now:

- **`P-22`** — the preview is a focusable read-only field and a second stop in the tab order.
- **`P-23`** — a refused name is refused at edit time, with the reason, through `textEdited`.

The widget renders nothing and validates nothing: `DownloadManager.preview_output_path` answers
and this displays the answer. What is under test here is the *displaying*.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from tracks_and_trails.core.output_template import OutputPreview
from tracks_and_trails.ui.rename_editor import (
    PREVIEW_LABEL,
    PROVISIONAL_LABEL,
    RenameEditor,
)


@pytest.fixture
def editor(qapp: QApplication) -> Iterator[RenameEditor]:
    widget = RenameEditor("A clip")
    yield widget
    widget.deleteLater()
    qapp.processEvents()


def caption_text(editor: RenameEditor) -> str:
    label = editor.findChild(QLabel, "renamePreviewCaption")
    assert label is not None
    return label.text()


# --- P-22: the preview is a field, and it is in the tab order ------------------------------------


def test_the_preview_is_a_focusable_read_only_field(editor: RenameEditor) -> None:
    """`UX-007` ruled against this file's own proposal of an unfocusable live region.

    *A user who cannot `Tab` to the preview cannot review it at their own pace.* Three properties
    together are what the ruling asks for and no two of them are enough: focusable, so it is a tab
    stop; read-only, so the path is not a second place a name is decided; and a real field, so the
    text can be selected and copied.
    """
    preview = editor.preview_field

    assert isinstance(preview, QLineEdit)
    assert preview.isReadOnly(), "the preview can be typed into, so a path is decided in two places"
    assert preview.focusPolicy() & Qt.FocusPolicy.TabFocus, (
        "the preview is not a tab stop, which is the unfocusable live region UX-007 ruled against"
    )


def test_the_preview_is_the_second_stop_after_the_input(
    editor: RenameEditor, qapp: QApplication
) -> None:
    """*"a single-line input with the preview below it as … a second stop in the tab order"*.

    Shown, because Qt only traverses focus inside a window that exists — an unshown widget has no
    focus to move and the assertion would pass or fail for reasons unrelated to the tab order.
    """
    assert editor.focus_chain() == [editor.input_field, editor.preview_field]

    editor.show()
    qapp.processEvents()
    try:
        editor.input_field.setFocus(Qt.FocusReason.OtherFocusReason)
        assert editor.input_field.hasFocus(), "the input could not take focus"

        editor.input_field.focusNextChild()

        assert editor.preview_field.hasFocus(), "Tab from the input did not reach the preview"
    finally:
        editor.hide()


# --- P-23: the refusal arrives at edit time ------------------------------------------------------


def test_a_keystroke_asks_for_a_new_preview(editor: RenameEditor) -> None:
    """`P-23` costs a validation path that runs on every keystroke, and this is that path.

    Typed with `QTest.keyClicks` rather than `setText`: `textEdited` is what a keystroke raises and
    `textChanged` is what a programmatic change raises too, and connecting the wrong one is how a
    surface ends up re-previewing its own writes.
    """
    seen: list[str] = []
    editor.name_changed.connect(seen.append)

    editor.input_field.clear()
    QTest.keyClicks(editor.input_field, "abc")

    assert seen == ["a", "ab", "abc"], seen


def test_a_refusal_empties_the_path_and_says_why(editor: RenameEditor) -> None:
    """**Never a path and an error together.**

    Leaving the last good path on screen beside a refusal is how a user comes to believe a broken
    template works — the same class of defect as a control that looks like a choice and converts
    nothing (`T-075`).
    """
    editor.show_preview(OutputPreview(path="/downloads/Clip.mp3"))
    assert editor.preview_text() == "/downloads/Clip.mp3"

    editor.show_preview(OutputPreview(refusal="incomplete format"))

    assert editor.preview_text() == "", "the previous path survived a refusal"
    assert "incomplete format" in editor.message_text()
    assert "incomplete format" in editor.preview_field.accessibleDescription(), (
        "a screen-reader user is told nothing about why the field went empty (NFR-005)"
    )


# --- REQ-011 as amended: intended, and said to be --------------------------------------------


def test_an_exact_path_is_labelled_as_one(editor: RenameEditor) -> None:
    editor.show_preview(OutputPreview(path="/downloads/Clip.mp3"))

    assert caption_text(editor) == PREVIEW_LABEL
    assert editor.message_text() == "", "an exact path carried a note about being uncertain"


def test_a_provisional_path_says_so_in_the_label_and_in_the_note(editor: RenameEditor) -> None:
    """`REQ-011` amended 2026-08-01: *labelled as the intended path*, not presented as the result.

    In the **caption**, because the difference between a promise and an intention is part of what
    the field is and belongs where somebody skimming will read it; and in the note, because the
    caption cannot carry the reason.
    """
    editor.show_preview(OutputPreview(path="/downloads/Clip.ext", provisional="not decided yet"))

    assert caption_text(editor) == PROVISIONAL_LABEL
    assert caption_text(editor) != PREVIEW_LABEL
    assert "not decided yet" in editor.message_text()
    assert "not decided yet" in editor.preview_field.accessibleDescription(), (
        "the distinction is drawn and not spoken, which is NFR-005's rule broken"
    )


def test_an_exact_preview_after_a_provisional_one_stops_saying_intended(
    editor: RenameEditor,
) -> None:
    """State that only ever turns on is state that ends up wrong. Both directions are asserted."""
    editor.show_preview(OutputPreview(path="/downloads/Clip.ext", provisional="later"))
    editor.show_preview(OutputPreview(path="/downloads/Clip.mp3"))

    assert caption_text(editor) == PREVIEW_LABEL
    assert editor.message_text() == ""
    assert editor.preview_field.accessibleDescription() == "/downloads/Clip.mp3"
