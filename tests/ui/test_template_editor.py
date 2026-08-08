"""The output template editor widget (`REQ-011`, `T-112`, `docs/UX_SPEC.md` §9.1).

Three rulings, and each is a property a test can fail:

- **`P-22`** — the preview is a focusable read-only field and a second stop in the tab order. A
  label would satisfy "shows the path" and fail this.
- **`P-23`** — an invalid template is refused at edit time, with the reason. Asserted through
  `textEdited`, which is what a keystroke raises, rather than by calling the slot.
- **`P-9`** — the supported fields are listed beside the input, built from the set the validator
  enforces so the two cannot describe different applications.

The widget renders nothing and validates nothing: `DownloadManager.preview_output_path` answers
both questions and this displays the answer. What is under test here is the *displaying*.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from tracks_and_trails.core.output_template import SUPPORTED_FIELDS, OutputPreview
from tracks_and_trails.ui.template_editor import (
    PREVIEW_LABEL,
    PROVISIONAL_LABEL,
    TemplateEditor,
)


@pytest.fixture
def editor(qapp: QApplication) -> Iterator[TemplateEditor]:
    widget = TemplateEditor("%(title)s.%(ext)s")
    yield widget
    widget.deleteLater()
    qapp.processEvents()


def caption_text(editor: TemplateEditor) -> str:
    label = editor.findChild(QLabel, "outputPreviewCaption")
    assert label is not None
    return label.text()


# --- P-22: the preview is a field, and it is in the tab order ------------------------------------


def test_the_preview_is_a_focusable_read_only_field(editor: TemplateEditor) -> None:
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
    editor: TemplateEditor, qapp: QApplication
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


# --- P-9: the fields are listed beside the input -------------------------------------------------


def test_every_supported_field_is_listed_beside_the_input(editor: TemplateEditor) -> None:
    """`P-9`: listed here rather than linked to, because this set is not yt-dlp's whole set.

    Built from `SUPPORTED_FIELDS` in the widget too, so this asserts the list is *shown*; that it
    is the same set the validator enforces is `test_output_template.py`'s claim.
    """
    fields = editor.findChild(QLabel, "templateFields")
    assert fields is not None
    shown = fields.text()

    for field in SUPPORTED_FIELDS:
        assert f"%({field.name})s" in shown, f"{field.name} is not offered"
        assert field.describes in shown, f"{field.name} is offered without saying what it is"
    assert "/" in shown, "nothing says a subfolder is possible, which is half of REQ-011"


# --- P-23: the refusal arrives at edit time ------------------------------------------------------


def test_a_keystroke_asks_for_a_new_preview(editor: TemplateEditor) -> None:
    """`P-23` costs a validation path that runs on every keystroke, and this is that path.

    Typed with `QTest.keyClicks` rather than `setText`: `textEdited` is what a keystroke raises and
    `textChanged` is what a programmatic change raises too, and connecting the wrong one is how a
    surface ends up re-previewing its own writes.
    """
    seen: list[str] = []
    editor.template_changed.connect(seen.append)

    editor.input_field.clear()
    QTest.keyClicks(editor.input_field, "abc")

    assert seen == ["a", "ab", "abc"], seen


def test_setting_the_text_programmatically_is_not_reported_as_typing(
    editor: TemplateEditor,
) -> None:
    """The caller that sets the text is the caller that asks for the first preview.

    A signal here would make it ask twice, and the second answer would arrive against a row whose
    panel may already have closed.
    """
    seen: list[str] = []
    editor.template_changed.connect(seen.append)

    editor.set_template("%(uploader)s/%(title)s.%(ext)s")

    assert seen == []
    assert editor.template == "%(uploader)s/%(title)s.%(ext)s"


def test_a_refusal_empties_the_path_and_says_why(editor: TemplateEditor) -> None:
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


def test_an_exact_path_is_labelled_as_one(editor: TemplateEditor) -> None:
    editor.show_preview(OutputPreview(path="/downloads/Clip.mp3"))

    assert caption_text(editor) == PREVIEW_LABEL
    assert editor.message_text() == "", "an exact path carried a note about being uncertain"


def test_a_provisional_path_says_so_in_the_label_and_in_the_note(editor: TemplateEditor) -> None:
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
    editor: TemplateEditor,
) -> None:
    """State that only ever turns on is state that ends up wrong. Both directions are asserted."""
    editor.show_preview(OutputPreview(path="/downloads/Clip.ext", provisional="later"))
    editor.show_preview(OutputPreview(path="/downloads/Clip.mp3"))

    assert caption_text(editor) == PREVIEW_LABEL
    assert editor.message_text() == ""
    assert editor.preview_field.accessibleDescription() == "/downloads/Clip.mp3"
