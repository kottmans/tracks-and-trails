"""Three ways a row can record chosen formats, as a sequence (`T-311`).

**The defect is data loss, not wording.** Choosing formats calls `presets.custom_preset(selector)`,
which builds a `Preset` from scratch — `media_kind=VIDEO`, `output_template=''`, no audio codec. So
a row with an output template set by the template editor, or a row set to *Audio only (MP3)*,
**silently loses it** the moment formats are picked. `ui/add_dialog.py` already does the right thing
one panel over: the template editor writes `with_output_template(self.preset_for(row), text)` —
the row's own effective preset, one field replaced.

**The options differ over time, not in a screenshot**, which is why this renders a sequence. All
three look identical at the moment formats are chosen; what separates them is whether the preset
control can still reach the row afterwards.

    .venv/bin/python tools/preset_override_mockup.py             # on the real display
    .venv/bin/python tools/preset_override_mockup.py --shots OUT # render each to a PNG

Every value shown is computed from `core/presets.py`, not written down here.
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

SELECTOR: Final = "137+140"
TEMPLATE: Final = "%(uploader)s/%(title)s.%(ext)s"

#: Where the row starts: an MP3 preset with a template the user typed in the template editor.
#: Chosen deliberately — it is the row with the **most** to lose, and every field it loses is one
#: the user set on purpose.
START: Final = registry.with_output_template(
    next(preset for preset in registry.BUILT_IN_PRESETS if "MP3" in preset.name), TEMPLATE
)

#: What the batch control is switched to at step three.
SWITCHED_TO: Final = next(
    preset for preset in registry.BUILT_IN_PRESETS if preset.name != START.name
)

CAPTIONS: Final = {
    "today": (
        "<b>Today.</b> <code>custom_preset</code> builds a preset from nothing, so the template "
        "and the MP3 conversion are gone at step 2 — <i>silently</i>, with the row still claiming "
        "to be a download the user set up. At step 3 the combo cannot reach the row either."
    ),
    "e1": (
        "<b>E1 — snapshot.</b> The row's own effective preset with one field replaced, exactly as "
        "the template editor already does. The loss is fixed. <i>Cost:</i> the row now carries a "
        "preset of its own, so step 3 still cannot reach it — the original complaint is smaller, "
        "not gone."
    ),
    "e2": (
        "<b>E2 — compose.</b> The row records only <i>which streams</i> "
        "(<code>Row.format_selection</code>, which it already stores), and the preset that governs "
        "is whichever one applies. Step 3 reaches the row and keeps the formats. <i>Cost:</i> "
        "<code>format_selection</code> becomes load-bearing for the request, not only for "
        "<code>REQ-024</code>'s ffmpeg check."
    ),
}

STEPS: Final = (
    "1 · A row set up by hand",
    f"2 · …then formats {SELECTOR} chosen",
    f"3 · …then the preset switched to “{SWITCHED_TO.name}”",
)


def rows_for(option: str) -> tuple[tuple[Preset, str], ...]:
    """The row's governing preset after each step, and which preset name the combo shows."""
    if option == "today":
        chosen = registry.custom_preset(SELECTOR, name=SELECTOR)
        return ((START, START.name), (chosen, START.name), (chosen, SWITCHED_TO.name))
    if option == "e1":
        chosen = replace(START, format_selector=SELECTOR)
        return ((START, START.name), (chosen, START.name), (chosen, SWITCHED_TO.name))
    composed = replace(SWITCHED_TO, format_selector=SELECTOR)
    return (
        (START, START.name),
        (replace(START, format_selector=SELECTOR), START.name),
        (composed, SWITCHED_TO.name),
    )


def readout(
    preset: Preset, parent: QWidget, *, lost_against: Preset | None, agrees: bool | None
) -> QWidget:
    """What the row will actually run.

    **Two different questions, one per step, and conflating them flattered `E2`.** At step 2 the
    question is *did anything the user set up disappear*, so fields are marked against what the row
    held before. At step 3 the user has deliberately switched preset, so a changed field is the
    change they asked for — marking it as a loss made every option look equally lossy. The question
    there is whether the row **followed** the control above it, which is the whole of what separates
    these options, so that is what is stated.
    """
    frame = QFrame(parent)
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    layout = QVBoxLayout(frame)
    heading = QLabel("This row will run", frame)
    font = QFont(heading.font())
    font.setBold(True)
    heading.setFont(font)
    layout.addWidget(heading)

    fields = (
        ("Streams", "format_selector", preset.format_selector),
        ("Kind", "media_kind", preset.media_kind.value),
        ("Convert to", "audio_codec", preset.audio_codec.value),
        ("Save as", "output_template", preset.output_template or "— nothing —"),
    )
    for label, field, value in fields:
        line = QHBoxLayout()
        name = QLabel(f"{label}:", frame)
        name.setMinimumWidth(80)
        line.addWidget(name)
        shown = QLabel(str(value), frame)
        if lost_against is not None and field != "format_selector":
            was = getattr(lost_against, field)
            if getattr(preset, field) != was:
                # **The word, not the colour** (`NFR-005`): a lost field says it was lost.
                shown.setText(
                    f"{value}   ← lost, was {getattr(was, 'value', was) or '— nothing —'}"
                )
                shown.setFont(font)
        line.addWidget(shown, 1)
        layout.addLayout(line)

    if agrees is not None:
        verdict = QLabel(
            "Follows the preset above" if agrees else "Ignores the preset above", frame
        )
        verdict.setFont(font)
        layout.addWidget(verdict)
    return frame


def step(option: str, index: int, parent: QWidget) -> QWidget:
    column = QWidget(parent)
    layout = QVBoxLayout(column)

    heading = QLabel(STEPS[index], column)
    font = QFont(heading.font())
    font.setBold(True)
    heading.setFont(font)
    heading.setWordWrap(True)
    layout.addWidget(heading)

    preset, shown_name = rows_for(option)[index]
    box = QGroupBox("Download as", column)
    inner = QVBoxLayout(box)
    row = QHBoxLayout()
    row.addWidget(QLabel("Preset", box))
    combo = QComboBox(box)
    combo.addItems([entry.name for entry in registry.BUILT_IN_PRESETS])
    combo.setCurrentText(shown_name)
    row.addWidget(combo, 1)
    inner.addLayout(row)
    selector = QLabel(f"This row · Format selector: {preset.format_selector}", box)
    selector.setTextFormat(Qt.TextFormat.PlainText)
    selector.setWordWrap(True)
    inner.addWidget(selector)
    layout.addWidget(box)

    # Step 2 asks what disappeared; step 3 asks whether the row followed the control.
    governs = rows_for(option)[index][1] == SWITCHED_TO.name
    layout.addWidget(
        readout(
            preset,
            column,
            lost_against=START if index == 1 else None,
            agrees=(preset.media_kind is SWITCHED_TO.media_kind) if governs else None,
        )
    )
    layout.addStretch(1)
    return column


def page(option: str) -> QWidget:
    shell = QWidget()
    layout = QVBoxLayout(shell)
    caption = QLabel(CAPTIONS[option], shell)
    caption.setWordWrap(True)
    caption.setTextFormat(Qt.TextFormat.RichText)
    caption.setContentsMargins(0, 0, 0, 10)
    layout.addWidget(caption)

    columns = QHBoxLayout()
    for index in range(len(STEPS)):
        columns.addWidget(step(option, index, shell), 1)
    layout.addLayout(columns)
    layout.addStretch(1)
    return shell


VARIANTS: Final = (("Today", "today"), ("E1 · snapshot", "e1"), ("E2 · compose", "e2"))


def build() -> QTabWidget:
    tabs = QTabWidget()
    tabs.setWindowTitle("What a row records when formats are chosen — three options")
    for label, option in VARIANTS:
        tabs.addTab(page(option), label)
    tabs.resize(1180, 480)
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
    for position, (_label, option) in enumerate(VARIANTS):
        tabs.setCurrentIndex(position)
        app.processEvents()
        target = parsed.shots / f"{option}.png"
        tabs.widget(position).grab().save(str(target))
        print(target)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
