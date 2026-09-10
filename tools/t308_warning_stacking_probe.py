"""Does the startup warning land above the window it blocks, on a real compositor?

`T308-R1`. The offscreen guards establish ordering, visibility and transient parentage; they cannot
establish **stacking**, because there is no compositor to ask. This runs `app.present()` — the
production sequence — against the real display, with an isolated profile whose settings name a
folder that does not exist, and records what the windowing system actually did.

    tools/t308_warning_stacking_probe.py            # the session's own platform
    QT_QPA_PLATFORM=xcb tools/t308_warning_stacking_probe.py

**What it establishes:** that the dialog is exposed, active, owned by the window as a transient,
and that its default button can be activated — and that the window is interactive afterwards.

**What it does not:** whether a person looking at the screen would find it. Stacking order is not
queryable on Wayland from inside the client, and `T-288` is this project's reminder that a
compositor's behaviour is not visible from a headless run. The perceptual half stays with the
maintainer, and `T-308` says so.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SETTINGS = 'default_preset = "Best video available"\n\n[downloads]\ndirectory = "{folder}"\n'


def main() -> int:
    with tempfile.TemporaryDirectory() as profile:
        config = Path(profile) / "tracksandtrails"
        config.mkdir(parents=True)
        missing = Path(profile) / "gone" / "nowhere"
        (config / "settings.toml").write_text(SETTINGS.format(folder=missing), encoding="utf-8")
        os.environ["XDG_CONFIG_HOME"] = profile
        os.environ.setdefault("XDG_DATA_HOME", profile)
        os.environ.setdefault("XDG_CACHE_HOME", profile)

        from PySide6.QtWidgets import QApplication, QMessageBox

        from tracks_and_trails import app as application
        from tracks_and_trails.ui import theme

        qapp = QApplication(sys.argv[:1])
        theme.apply(qapp, theme.LIGHT)
        composition = application.compose(qapp)
        print(f"platform:        {qapp.platformName()}")
        print(f"settings problem carried: {composition.settings_problem is not None}")

        application.present(composition)
        for _ in range(60):
            qapp.processEvents()

        boxes = composition.window.findChildren(QMessageBox, "settingsProblemDialog")
        if not boxes:
            print("RESULT: no warning was shown — nothing to check")
            return 1
        box = boxes[0]
        handle = box.windowHandle()
        window_handle = composition.window.windowHandle()
        print(f"window shown:    {composition.window.isVisible()}")
        print(f"dialog visible:  {box.isVisible()}")
        print(f"dialog exposed:  {handle.isExposed() if handle else 'no native handle'}")
        print(f"dialog active:   {box.isActiveWindow()}")
        print(f"dialog modality: {box.windowModality()}")
        transient = handle.transientParent() is window_handle if handle else "unknown"
        print(f"transient of the window: {transient}")
        print(f"dialog geometry: {box.geometry()}")
        print(f"window geometry: {composition.window.geometry()}")

        button = box.defaultButton() or box.button(QMessageBox.StandardButton.Ok)
        print(f"default button:  {button.text() if button else 'none'}")
        if button is not None:
            button.click()
        for _ in range(30):
            qapp.processEvents()
        print(f"dialog gone after clicking it: {not box.isVisible()}")
        print(f"window enabled afterwards:     {composition.window.isEnabled()}")
        composition.window.close()
        for _ in range(10):
            qapp.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
