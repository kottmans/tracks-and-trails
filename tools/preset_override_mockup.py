"""What a row keeps when you pick formats by hand (`T-311`).

**The defect, in the app.** Stage a URL, set it to *Audio only (MP3)*, give it a custom filename
pattern, then open *Choose specific formats…* and pick a format. The MP3 conversion and the
filename pattern are both **silently discarded**: `ui/add_dialog.py` writes
`presets.custom_preset(selector)` onto the row, and that builds a `Preset` from nothing —
`media_kind=VIDEO`, `output_template=""`, no audio codec. The template editor one panel over does
the right thing (`with_output_template(self.preset_for(row), text)`); the format panel does not.

Afterwards the **Preset** control shows a preset the row is not using, and changing it does not
reach that row. That is the *"doesn't do anything"* the maintainer reported from the built window.

**Three ways to fix it, and they differ over time rather than in a screenshot** — which is why this
renders a sequence. Every value below is computed from `core/presets.py`; nothing is written down.

    .venv/bin/python tools/preset_override_mockup.py             # on the real display
    .venv/bin/python tools/preset_override_mockup.py --shots OUT # render each to a PNG
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core import presets as registry
from tracks_and_trails.core.presets import Preset
from tracks_and_trails.ui import theme

CHOSEN: Final = "140"
PATTERN: Final = "%(uploader)s/%(title)s.%(ext)s"

#: Where the row starts: the preset with the most to lose, and every field of it set on purpose.
START: Final = registry.with_output_template(
    next(preset for preset in registry.BUILT_IN_PRESETS if "MP3" in preset.name), PATTERN
)

#: What the Preset control is changed to at step three.
SWITCHED: Final = next(p for p in registry.BUILT_IN_PRESETS if p.name != START.name)

STEPS: Final = (
    "1 · You set the row up",
    f"2 · …then pick format {CHOSEN} by hand",
    f"3 · …then change Preset to “{SWITCHED.name}”",
)

OPTIONS: Final = (
    (
        "Today",
        "today",
        "<b>Today.</b> Picking a format throws away the conversion <i>and</i> the filename "
        "pattern, and says nothing. Changing the Preset control afterwards does not reach the row.",
    ),
    (
        "Fix the filename only",
        "filename",
        "<b>Fix the filename only.</b> About ten lines, and the one part of the loss nobody has "
        "argued for. The conversion is still lost and the control still does nothing.",
    ),
    (
        "Fix all the loss",
        "keep",
        "<b>Fix all the loss.</b> The row keeps its preset and only the streams change — what the "
        "filename editor already does. Nothing is discarded; the control still does nothing.",
    ),
    (
        "Fix the loss and the control",
        "compose",
        "<b>Fix the loss and the control.</b> The row remembers only <i>which streams you "
        "picked</i>, and whichever preset governs is applied over it. Changing Preset now reaches "
        "the row and keeps your streams.",
    ),
)


def row_after(option: str) -> tuple[tuple[Preset, str], ...]:
    """The preset actually governing the row after each step, and the name the control shows."""
    if option == "today":
        after = registry.custom_preset(CHOSEN, name=CHOSEN)
        return ((START, START.name), (after, START.name), (after, SWITCHED.name))
    if option == "filename":
        after = replace(registry.custom_preset(CHOSEN, name=CHOSEN), output_template=PATTERN)
        return ((START, START.name), (after, START.name), (after, SWITCHED.name))
    kept = replace(START, format_selector=CHOSEN)
    if option == "keep":
        return ((START, START.name), (kept, START.name), (kept, SWITCHED.name))
    return (
        (START, START.name),
        (kept, START.name),
        (replace(SWITCHED, format_selector=CHOSEN), SWITCHED.name),
    )


def readout(
    preset: Preset, parent: QWidget, *, lost_from: Preset | None, follows: bool | None
) -> QWidget:
    """What the row will download, in the words a person would use.

    **Two questions, one per step.** At step 2 nothing was asked to change but the streams, so a
    changed field is a *loss*. At step 3 the user deliberately changed the control, so a changed
    field is what they asked for — and the question is whether the row **followed** it.
    """
    frame = QFrame(parent)
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    bold = QFont(frame.font())
    bold.setBold(True)

    heading = QLabel("This row will download", frame)
    heading.setFont(bold)
    layout.addWidget(heading)

    fields = (
        ("Streams", "format_selector", preset.format_selector),
        ("Converts to", "audio_codec", preset.audio_codec.value),
        ("Saves as", "output_template", preset.output_template or "— the default name —"),
    )
    for label, field, value in fields:
        line = QHBoxLayout()
        name = QLabel(f"{label}:", frame)
        name.setMinimumWidth(90)
        line.addWidget(name)
        shown = QLabel(str(value), frame)
        if lost_from is not None and field != "format_selector":
            was = getattr(lost_from, field)
            if getattr(preset, field) != was:
                shown.setText(f"{value}    ← lost, was {getattr(was, 'value', was)}")
                shown.setFont(bold)
        line.addWidget(shown, 1)
        layout.addLayout(line)

    if follows is not None:
        verdict = QLabel(
            "Follows the control above" if follows else "Ignores the control above", frame
        )
        verdict.setFont(bold)
        layout.addWidget(verdict)
    return frame


def step(option: str, index: int, parent: QWidget) -> QWidget:
    column = QWidget(parent)
    layout = QVBoxLayout(column)
    bold = QFont(column.font())
    bold.setBold(True)

    heading = QLabel(STEPS[index], column)
    heading.setFont(bold)
    heading.setWordWrap(True)
    layout.addWidget(heading)

    preset, control_shows = row_after(option)[index]
    box = QGroupBox("Download as", column)
    inner = QVBoxLayout(box)
    row = QHBoxLayout()
    row.addWidget(QLabel("Preset", box))
    combo = QComboBox(box)
    combo.addItems([entry.name for entry in registry.BUILT_IN_PRESETS])
    combo.setCurrentText(control_shows)
    row.addWidget(combo, 1)
    inner.addLayout(row)
    layout.addWidget(box)

    layout.addWidget(
        readout(
            preset,
            column,
            lost_from=START if index == 1 else None,
            # **Every field but the streams, not one of them.** Comparing the audio codec alone
            # called *Today* a follower at step 3, because a discarded preset and the newly chosen
            # one happen to agree on it — a coincidence reported as the behaviour under test.
            follows=(
                replace(preset, format_selector=CHOSEN) == replace(SWITCHED, format_selector=CHOSEN)
            )
            if index == 2
            else None,
        )
    )
    layout.addStretch(1)
    return column


def page(option: str, caption: str) -> QWidget:
    shell = QWidget()
    layout = QVBoxLayout(shell)
    text = QLabel(caption, shell)
    text.setWordWrap(True)
    text.setTextFormat(Qt.TextFormat.RichText)
    text.setContentsMargins(0, 0, 0, 10)
    layout.addWidget(text)
    columns = QHBoxLayout()
    for index in range(len(STEPS)):
        columns.addWidget(step(option, index, shell), 1)
    layout.addLayout(columns)
    layout.addStretch(1)
    return shell


def build() -> QTabWidget:
    tabs = QTabWidget()
    tabs.setWindowTitle("What a row keeps when you pick formats — four options")
    for label, option, caption in OPTIONS:
        tabs.addTab(page(option, caption), label)
    tabs.resize(1180, 460)
    return tabs


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=Path, help="render each tab to this directory and exit")
    parsed = parser.parse_args(argv)
    if parsed.shots is not None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication([])
    theme.apply(app, theme.THEMES["light"])
    tabs = build()
    tabs.show()
    if parsed.shots is None:
        return app.exec()

    parsed.shots.mkdir(parents=True, exist_ok=True)
    for position, (_label, option, _caption) in enumerate(OPTIONS):
        tabs.setCurrentIndex(position)
        app.processEvents()
        target = parsed.shots / f"{option}.png"
        tabs.widget(position).grab().save(str(target))
        print(target)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
