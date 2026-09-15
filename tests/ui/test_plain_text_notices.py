"""Boxes that show a path show it as plain text (`T346-R1`).

A folder named `<style>downloads` is a valid Linux name. In `QMessageBox`'s default mode the
sentence holding it was read as markup: the label, and what a screen reader heard, stopped at the
folder. `box.text()` still returns the original string, so these read what is **rendered for
assistive technology**, and the first test proves that reading sees the defect.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from tracks_and_trails import app as application
from tracks_and_trails.core.settings import SettingsProblem
from tracks_and_trails.ui.file_actions import FileActions
from tracks_and_trails.ui.reveal import Refusal

MARKUP_FOLDER = "<style>downloads"


def heard(box: QMessageBox) -> str:
    """What a screen reader is given for the box's sentence."""
    label = box.findChild(QLabel, "qt_msgbox_label")
    assert label is not None, "Qt's message label was not found, so this reads nothing"
    interface = QAccessible.queryAccessibleInterface(label)
    assert interface is not None
    return interface.text(QAccessible.Text.Name)


def test_the_reading_sees_markup_eat_a_sentence(qapp: QApplication) -> None:
    """The positive control: in Qt's default mode the same reading loses the folder."""
    box = QMessageBox()
    sentence = f"clip.mp3 is no longer in /tmp/x/{MARKUP_FOLDER}. It may have been moved."
    box.setText(sentence)

    assert heard(box) != sentence, "the default mode kept the sentence, so this proves nothing"


@pytest.fixture
def sentence(tmp_path: Path) -> str:
    folder = tmp_path / MARKUP_FOLDER
    return f"clip.mp3 is no longer in {folder}. It may have been moved, renamed or deleted."


def test_the_windows_missing_file_box_is_heard_whole(
    qapp: QApplication, tmp_path: Path, sentence: str
) -> None:
    from tracks_and_trails.ui.main_window import MainWindow

    window = MainWindow(geometry_file=tmp_path / "window.toml")
    try:
        box = window._show_file_refusal(Refusal(sentence, missing=True))
        assert heard(box) == sentence
        box.close()
    finally:
        window.deleteLater()


def test_the_plain_fallback_box_is_heard_whole(
    qapp: QApplication, tmp_path: Path, sentence: str
) -> None:
    from PySide6.QtWidgets import QListView

    table = QListView()
    actions = FileActions(
        table=table,
        selected_path=lambda: None,
        output_directory=lambda: tmp_path,
        report=lambda _sentence: None,
    )
    try:
        box = actions._show_plain_box(Refusal(sentence, missing=True))
        assert heard(box) == sentence
        box.close()
    finally:
        table.deleteLater()


def test_the_settings_problem_box_is_plain_text(qapp: QApplication, tmp_path: Path) -> None:
    """**Set for the next wording, not because today's is eaten.** Qt guesses markup from the first
    line only, and this summary's first line is fixed text with the path below it, so the default
    mode renders it whole today (a mutation removing the setting passed a rendering assertion). The
    format is asserted directly, so a sentence starting with the path cannot bring the defect back.
    """
    from tracks_and_trails.ui.main_window import MainWindow

    path = tmp_path / MARKUP_FOLDER / "settings.toml"
    problem = SettingsProblem(path=path, reason="line 3: expected a value")
    window = MainWindow(geometry_file=tmp_path / "window.toml")
    try:
        box = window.report_settings_problem(problem)
        assert box is not None
        assert box.textFormat() is Qt.TextFormat.PlainText
        assert heard(box) == problem.summary
        box.close()
    finally:
        window.deleteLater()


@pytest.fixture
def recorded_boxes(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[QMessageBox]]:
    """`_refuse_to_start` waits in `exec`; record the box instead of blocking the suite."""
    shown: list[QMessageBox] = []

    def record(box: QMessageBox) -> int:
        shown.append(box)
        return 0

    monkeypatch.setattr(QMessageBox, "exec", record)
    yield shown
    for box in shown:
        box.deleteLater()


def test_a_refusal_to_start_is_heard_whole(
    qapp: QApplication, tmp_path: Path, recorded_boxes: list[QMessageBox]
) -> None:
    """Both startup refusals name the database's path (`ARC-006`, `T-320`)."""
    sentence = f"another Tracks & Trails instance is already using {tmp_path / MARKUP_FOLDER}."

    application._refuse_to_start(QMessageBox.Icon.Information, sentence)

    assert len(recorded_boxes) == 1
    assert recorded_boxes[0].textFormat() is Qt.TextFormat.PlainText
    assert heard(recorded_boxes[0]) == sentence
