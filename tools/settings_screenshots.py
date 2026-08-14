"""Render the Settings screen to PNG, both themes, from the composed application (`T-242`).

**Why this is a tool rather than a test.** `T-242`'s fourth acceptance criterion asks for
screenshots of the fixed screen attached to its entry, and `ai/evidence/README.md` asks that
nothing regenerable be stored. Both are satisfied by a committed generator: the images in
`ai/evidence/` are the record of one head, and this is how anyone gets the *current* screen back.

**It is not verification of anything.** The platform is `offscreen`, so what this produces is a
faithful render of the widget tree and says nothing about a real display — `T-221` is this
project's record of a transient no offscreen grab can see, and `T-212`'s recorded checklist run is
where that gap closes.

    python tools/settings_screenshots.py ai/evidence 2026-08-14-T242-settings

Writes `<prefix>-light.png` and `<prefix>-dark.png`, and prints the size of each and how many
labels were drawn shorter than the text in them — which should be zero, and is the measurement
`T-242` turns on.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from tracks_and_trails import app as application
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.ui import theme as ui_theme

#: A 1366x768 laptop's working area, near enough — the size `T-242`'s criterion names.
WIDTH = 620
HEIGHT = 700


def clipped(screen: object) -> list[str]:
    """Every label drawn shorter than the text in it needs. Empty is the point."""
    short = []
    for label in screen.findChildren(QLabel):  # type: ignore[attr-defined]
        if not label.text().strip():
            continue
        needs = (
            label.heightForWidth(label.width()) if label.wordWrap() else label.sizeHint().height()
        )
        if needs > label.height():
            short.append(f"{label.objectName() or label.text()[:30]} ({label.height()} < {needs})")
    return short


def main() -> int:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    prefix = sys.argv[2] if len(sys.argv) > 2 else "settings"
    directory.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp())
    app = QApplication([])

    for name in ("light", "dark"):
        settings_file = temporary / f"settings-{name}.toml"
        core_settings.save(core_settings.with_theme(core_settings.Settings(), name), settings_file)
        composition = application.compose(
            app,
            database=temporary / f"queue-{name}.sqlite3",
            output_directory=temporary / "downloads",
            geometry_file=temporary / f"window-{name}.toml",
            settings_file=settings_file,
            cache_directory=temporary / f"cache-{name}",
            # Nothing is downloaded: this is about pixels.
            entry_point=lambda *_args, **_kwargs: None,
        )
        ui_theme.apply(app, ui_theme.THEMES[name])
        screen = composition.window.open_settings()
        if screen is None:  # pragma: no cover - composition always wires the writers
            raise SystemExit("composition wired no settings writers, so there is no screen")
        screen.resize(WIDTH, HEIGHT)
        screen.show()
        QApplication.processEvents()

        target = directory / f"{prefix}-{name}.png"
        screen.grab().save(str(target))
        print(f"{target}  {screen.width()}x{screen.height()}  clipped={clipped(screen) or 0}")

        screen.close()
        composition.window.close()
        QApplication.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
