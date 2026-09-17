"""The taskbar's *Close window* closes the application, even with a dialog open (`T-343`).

## What this is for

Reported by the maintainer: with *Add URLs* or *Preferences* open, right-clicking the taskbar
button and choosing *Close window* does nothing. Measured on `STARBASE` by posting the taskbar's
own messages to the main window:

| Open dialog | `WM_CLOSE` | `WM_SYSCOMMAND` / `SC_CLOSE` | Main window enabled |
|---|---|---|---|
| none | closes | closes | yes |
| *Add URLs* | ignored | ignored | **no** |
| *Preferences* | ignored | ignored | **no** |

Both dialogs open with `open()`, which is window-modal, and Windows disables the owner of a modal
dialog. The message still reaches the window's procedure; what ignores it is Qt, which will not
deliver a close to a window a modal dialog blocks.

## The shape, ruled by the maintainer on 2026-09-17

**Windows only.** The alternative put to them was non-modal *Add URLs* and *Preferences* on both
platforms, which changes how the whole application behaves; the report was about one gesture on one
platform. So this reads the message before Qt does, closes what blocks the window, and then closes
the window.

**A dialog closed this way keeps nothing.** URLs pasted into *Add URLs* but not yet added are
discarded, which is what every other way of closing that dialog already does: `AddUrlDialog.done`
is where *Escape*, the window button, *Cancel* and `accept()` all arrive, and it abandons the
staging list and unstages each probe (`T016-R2`, `T118-R1`). The gesture is *close the
application*, and anything else would be a prompt on a window the user has already told Windows to
close.

**One dialog does refuse, and it is right to.** *Add URLs* holds its close while a commit is in
flight (`T118-R3`): `done()` returns without hiding, so Qt ignores the close event and `close()`
answers false. The application then stays open with the dialog's own *"Still adding to the queue"*
message, which is the dialog's rule rather than this one's. The gesture is still consumed — passing
it on would reach the window Qt is blocking, which is where this began — and the user closes again
once the rows are written.

**Nothing is installed off Windows.** A native event filter is called for every native event, and
on xcb that is every mouse move, so the cost is only paid where the gesture exists.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QWidget

__all__ = [
    "NativeMessage",
    "TaskbarClose",
    "a_windows_message",
    "asks_to_close",
    "close_from_the_taskbar",
    "installed_on",
    "owned_by",
    "read_message",
]

#: The name the filter is found by, so it is installed once however often composition asks.
FILTER_NAME: Final = "taskbarClose"

#: Sent to a window that something outside it wants closed — the taskbar's *Close window* among
#: them.
WM_CLOSE: Final = 0x0010

#: The system menu's commands, which *Close window* also arrives as, depending on the shell.
WM_SYSCOMMAND: Final = 0x0112

#: `SC_CLOSE`, the system menu's *Close*.
SYSTEM_CLOSE: Final = 0xF060

#: **The low four bits of a system command are the system's** — documented as used internally, and
#: set when the command comes from an accelerator or a mnemonic. Compare above them or a real
#: *Close* is missed.
SYSTEM_COMMAND_MASK: Final = 0xFFF0

#: What Qt calls a Windows message, for a window and for the dispatcher. Both carry an `MSG`.
WINDOWS_MESSAGES: Final = (b"windows_generic_MSG", b"windows_dispatcher_MSG")

#: How many stacked dialogs this will close before giving up, so a dialog that reopens itself
#: cannot spin here. Nothing in the application stacks more than *Preferences* and a box on top.
MOST_DIALOGS: Final = 8


@dataclass(frozen=True)
class NativeMessage:
    """The three fields of a Windows `MSG` this decides on, and nothing else.

    Kept as its own type so the decision is a function of values rather than of a pointer: the
    tests drive `TaskbarClose.consider` on either platform, and only `nativeEventFilter` reads
    memory.
    """

    window: int
    identifier: int
    parameter: int


def asks_to_close(message: NativeMessage) -> bool:
    """Whether `message` is something asking this window to close."""
    if message.identifier == WM_CLOSE:
        return True
    return (
        message.identifier == WM_SYSCOMMAND
        and message.parameter & SYSTEM_COMMAND_MASK == SYSTEM_CLOSE
    )


class TaskbarClose(QObject, QAbstractNativeEventFilter):
    """Closes the dialogs that block `owner`, then `owner`, when Windows asks it to close."""

    def __init__(self, owner: QWidget) -> None:
        QObject.__init__(self, owner)
        QAbstractNativeEventFilter.__init__(self)
        self._owner = owner

    # Qt's override name, hence the camelCase: this is not a project naming choice. Qt calls it
    # positionally, so the parameters take the project's own spelling.
    def nativeEventFilter(self, event_type: object, message: int) -> object:
        """Read the `MSG` Qt is about to handle, and act only on a close for this window.

        **Returns a pair**, which is what PySide6 wants of this: whether the message was handled,
        and the result to give Windows for it. Anything not a close for this window is left
        untouched, so every other message reaches Qt as before.
        """
        if not a_windows_message(event_type):
            return False, 0
        return self.consider(read_message(message)), 0

    def consider(self, message: NativeMessage) -> bool:
        """Act on `message` if it closes this window, and say whether it was handled.

        **False means Qt handles it as it does today**, which is what a close with no dialog open
        needs: the window has a close of its own (`main_window.closeEvent` saves the geometry and
        starts the shutdown), and this has no business repeating it.
        """
        if not asks_to_close(message) or not self._is_this_window(message.window):
            return False
        blocking = QApplication.activeModalWidget()
        if blocking is None:
            return False
        if not owned_by(self._owner, blocking):
            # A modal window this window does not own. Nothing in the application makes one, and
            # closing somebody else's dialog on a taskbar gesture is not this rule's to do.
            return False
        if not self._close_the_dialogs():
            # A dialog refused to close, so the application stays. The gesture was still acted on,
            # which is why this is handled rather than passed on.
            return True
        self._owner.close()
        return True

    def _is_this_window(self, window: int) -> bool:
        """Whether `window` is the native window `owner` is showing in.

        **`windowHandle()` is typed non-optional and is not**: it returns `None` until the widget
        has been shown, which is why the annotation is written out here — the same guard, and the
        same reason, as `main_window._watch_the_native_window`.
        """
        handle: QWindow | None = self._owner.windowHandle()
        return handle is not None and int(handle.winId()) == window

    def _close_the_dialogs(self) -> bool:
        """Close what blocks the window, innermost first. False if one of them refused."""
        for _ in range(MOST_DIALOGS):
            blocking = QApplication.activeModalWidget()
            if blocking is None:
                return True
            if not blocking.close():
                return False
        return False


def a_windows_message(event_type: object) -> bool:
    """Whether Qt is handing over a Windows `MSG`, whichever spelling it uses for the name.

    **Both spellings are accepted deliberately.** Qt's own type for this is a `QByteArray`, and
    PySide6 has passed it as `bytes` as well; the wrong guess here would either read an xcb event
    as an `MSG` or never act at all, and neither is visible from this machine.
    """
    if isinstance(event_type, QByteArray):
        return event_type.data() in WINDOWS_MESSAGES
    if isinstance(event_type, bytes | bytearray | memoryview):
        return bytes(event_type) in WINDOWS_MESSAGES
    return False


def owned_by(owner: QWidget, widget: QWidget) -> bool:
    """Whether `widget` hangs off `owner`, however many dialogs deep.

    **`QWidget.isAncestorOf` will not answer this**, and that was measured rather than assumed: it
    requires the two widgets to be *within the same window*, and a dialog is a window of its own,
    so it reports false for the very case this has to recognise. The parent chain is what the
    ownership question is about.
    """
    parent = widget.parentWidget()
    while parent is not None:
        if parent is owner:
            return True
        parent = parent.parentWidget()
    return False


def read_message(address: int) -> NativeMessage:
    """The `MSG` at `address`, as the three fields the decision uses.

    **Windows only** — `ctypes.wintypes.MSG` exists nowhere else, and `nativeEventFilter` reaches
    this only for a Windows message.
    """
    from ctypes import wintypes

    message = wintypes.MSG.from_address(address)
    return NativeMessage(
        window=int(message.hWnd or 0),
        identifier=int(message.message),
        parameter=int(message.wParam),
    )


def close_from_the_taskbar(
    app: QApplication, owner: QWidget, platform: str = sys.platform
) -> TaskbarClose | None:
    """Install `TaskbarClose` for as long as `owner` lives, once per owner. Windows only.

    Returns `None` off Windows, where nothing is installed and the gesture does not exist.

    **`platform` is a parameter for `reveal.py`'s reason**, and it is load-bearing here twice: the
    ordinary suite asserts both answers on any machine, and `mypy --platform win32` typechecks
    both branches instead of declaring one of them dead. Read inline, `sys.platform` made whichever
    branch the checker had narrowed away an *unreachable statement* error — on Linux for one form
    of the test and on Windows for the other, so neither spelling passed both runs.

    **It is a child of `owner`, and that is what removes it.** Qt documents
    `~QAbstractNativeEventFilter` as *"Destroys the native event filter. This automatically removes
    it from the application"*, so the filter installed here stops being called when the window it
    serves is destroyed, and a test session's shared `QApplication` is not left carrying it.
    Nothing is connected to `destroyed` for that: a callable holding this filter, held in turn by
    the window, is the Python reference cycle around a widget that `T-289` is about.
    """
    if platform != "win32":
        # The gesture does not exist elsewhere, and a filter called for every xcb event would cost
        # something for nothing.
        return None
    return installed_on(app, owner)


def installed_on(app: QApplication, owner: QWidget) -> TaskbarClose:
    """Install the filter, whatever the platform. `close_from_the_taskbar` decides whether to."""
    existing = owner.findChild(TaskbarClose, FILTER_NAME)
    if existing is not None:
        return existing
    closer = TaskbarClose(owner)
    closer.setObjectName(FILTER_NAME)
    app.installNativeEventFilter(closer)
    return closer
