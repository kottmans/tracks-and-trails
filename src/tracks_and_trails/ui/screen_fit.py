"""Every dialog opens inside the screen's working area, title bar included.

## What this is for

Reported from a friend's Windows laptop (1920x1200 at 125%): *Add URLs* and *Preferences* opened
with their title bars above the top of the screen, so they could not be moved and no URL could be
typed. Reproduced on `STARBASE` (Windows 10, 1600x900 with `QT_SCALE_FACTOR=1.25`, a 1280x720
logical screen): *Add URLs* asks for 788 pixels of height on Windows fonts, and Qt placed its frame
at y = -241.

Qt centres a dialog over its parent and does not keep the frame on the screen. `T-242` and
`T222-R1` had bounded the **height** of *Preferences* and *Options*, one dialog at a time, and
nothing bounded where any dialog lands.

## One rule, for every dialog

`DialogsOnScreen` is installed on the application while the main window lives, and acts each time
**any** top-level `QDialog` is shown: a message box, and a dialog written later, get it without
remembering to. It **caps and shrinks** a dialog that is larger than the working area, and
**moves** one that is outside it. It never grows one, and it does nothing to a dialog that fits.

**Not enough on its own for *Add URLs***, measured on Windows: that dialog also bounds its own
size hint with `bounded_to_screen` and is given that size before it is shown. Without either,
it grew past the screen after being fitted.

**Checked on Windows at 100% only.** With Qt's `QT_SCALE_FACTOR` standing in for 125% and 150%,
Windows refused the dialog's geometry and the results did not match a true 100% screen, so a
real scaled display is still owed a look.

It runs when the dialog is shown, once more after the event loop has turned (the frame's size is
the window manager's and is not known until the native window exists), and whenever a visible
dialog is resized, because a dialog can grow after it is shown. The main
window is not touched: `main_window.moved_onto_a_screen` already governs its restored geometry.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QEvent, QObject, QRect, QSize, QTimer
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication, QDialog, QWidget

__all__ = [
    "DialogsOnScreen",
    "bounded_to_screen",
    "fit_on_screen",
    "fitted_geometry",
    "keep_dialogs_on_screen",
]

#: The name the filter is found by, so it is installed once however often composition asks.
FILTER_NAME: Final = "dialogsOnScreen"


#: Width and height left for the window manager's frame when a size is chosen before the frame
#: exists. The same allowance `settings_dialog` makes (`T-242`); the fit on show corrects the rest.
#: Used by `bounded_to_screen`, which a dialog's own `sizeHint` calls (`AddUrlDialog`).
WINDOW_CHROME: Final = 48


def bounded_to_screen(window: QWidget, size: QSize) -> QSize:
    """`size`, no larger than `window`'s screen's working area less `WINDOW_CHROME`."""
    room = window.screen().availableGeometry().size()
    return size.boundedTo(QSize(room.width() - WINDOW_CHROME, room.height() - WINDOW_CHROME))


def fitted_geometry(client: QRect, frame: QRect, available: QRect) -> QRect | None:
    """Where a window's client area should be so its whole frame is inside `available`.

    `client` is `QWidget.geometry()` and `frame` is `frameGeometry()`; the difference between them
    is the title bar and borders, which are kept as they are. `None` when nothing needs to change.

    **The top edge wins.** When the frame is taller than the working area even after shrinking
    (a minimum size can stop it), the frame's top is put at the working area's top, so the title
    bar, the one thing a user needs to move the window, is on screen. The same holds for the left
    edge.
    """
    left = client.x() - frame.x()
    top = client.y() - frame.y()
    right = frame.width() - client.width() - left
    bottom = frame.height() - client.height() - top

    width = max(1, min(client.width(), available.width() - left - right))
    height = max(1, min(client.height(), available.height() - top - bottom))
    outer_width = width + left + right
    outer_height = height + top + bottom

    x = min(frame.x(), available.x() + available.width() - outer_width)
    y = min(frame.y(), available.y() + available.height() - outer_height)
    x = max(x, available.x())
    y = max(y, available.y())

    result = QRect(x + left, y + top, width, height)
    return None if result == client else result


def fit_on_screen(window: QWidget) -> bool:
    """Cap, shrink and move `window` so its frame is inside its screen's working area.

    **The cap is what holds on Windows.** Shrinking alone was undone there: a dialog whose layout
    still wanted its full height was grown back past the screen, and Windows reported *Unable to
    set geometry*. A maximum size is honoured by the layout and by the window manager alike, so
    the dialog can no longer grow out of the working area, and the user cannot drag it larger than
    the screen either. The cap never goes below the dialog's minimum size.

    `True` when anything was changed, so the caller can look again once the window manager has
    answered.
    """
    # Typed optional on purpose: the stub says a widget always has a screen, and on a platform
    # with none `screen()` answers `None` (`settings_dialog._room_on_screen` keeps the same guard).
    screen: QScreen | None = window.screen()
    if screen is None:
        return False
    changed = False
    available = screen.availableGeometry()
    client = window.geometry()
    frame = window.frameGeometry()
    room = QSize(
        available.width() - (frame.width() - client.width()),
        available.height() - (frame.height() - client.height()),
    ).expandedTo(window.minimumSize())
    if window.maximumSize().boundedTo(room) != window.maximumSize():
        window.setMaximumSize(window.maximumSize().boundedTo(room))
        changed = True
    wanted = fitted_geometry(window.geometry(), window.frameGeometry(), available)
    if wanted is not None:
        window.setGeometry(wanted)
        changed = True
    return changed


#: How many fits one showing of a dialog may make before this stops asking (see `DialogsOnScreen`).
MAX_PASSES: Final = 4

#: The dynamic property counting a dialog's fits since it was last shown.
_PASSES: Final = "tracksAndTrailsFitPasses"


class DialogsOnScreen(QObject):
    """Fits each top-level dialog to its screen as it is shown. See the module docstring."""

    # Qt's override name, hence the camelCase.
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not (isinstance(watched, QDialog) and watched.isWindow()):
            return False
        kind = event.type()
        if kind is QEvent.Type.Show:
            watched.setProperty(_PASSES, 0)
            self._fit(watched)
            # Again once the native frame has its real size.
            QTimer.singleShot(0, watched, lambda: self._fit(watched))
        elif kind is QEvent.Type.Resize and watched.isVisible():
            # **A dialog can grow after it is shown**, and *Add URLs* does: measured on Windows at
            # 480 pixels when shown and 786 a moment later, once its list's size hint had been
            # asked again. Fitted only on show, it opened inside the screen and then grew out of
            # the bottom. A fit that changes nothing sends no further resize, so this settles.
            self._fit(watched)
        return False

    def _fit(self, dialog: QDialog) -> None:
        """Fit `dialog`, and look once more after the window manager has answered a change.

        **Windows can refuse a geometry** and apply another (*Unable to set geometry*, measured
        with `QT_SCALE_FACTOR=1.25`): the cap then held but the move did not, leaving the title bar
        above the screen with nothing left to trigger another fit. So a fit that changed something
        is followed by one more after the event loop turns, up to `MAX_PASSES` per showing, which
        bounds a window manager that never agrees.
        """
        passes = int(dialog.property(_PASSES) or 0)
        if passes >= MAX_PASSES:
            return
        dialog.setProperty(_PASSES, passes + 1)
        if fit_on_screen(dialog):
            QTimer.singleShot(0, dialog, lambda: self._fit(dialog))


def keep_dialogs_on_screen(app: QApplication, owner: QObject) -> DialogsOnScreen:
    """Install `DialogsOnScreen` on `app` for as long as `owner` lives, once per owner.

    **Owned by the main window, not the application.** Qt drops an event filter from the
    application's list when the filter object is destroyed, so the rule lasts exactly as long as
    the window whose dialogs it serves, and a test session's shared `QApplication` is not left
    carrying it after that window has gone.
    """
    existing = owner.findChild(DialogsOnScreen, FILTER_NAME)
    if existing is not None:
        return existing
    keeper = DialogsOnScreen(owner)
    keeper.setObjectName(FILTER_NAME)
    app.installEventFilter(keeper)
    return keeper
