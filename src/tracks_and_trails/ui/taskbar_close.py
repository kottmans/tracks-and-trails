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

import ctypes
import sys
from dataclasses import dataclass
from functools import partial
from typing import Any, Final, Protocol

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QWidget

__all__ = [
    "FilterHost",
    "Message",
    "NativeMessage",
    "TaskbarClose",
    "a_windows_message",
    "asks_to_close",
    "close_from_the_taskbar",
    "installed_on",
    "owned_by",
    "read_message",
    "shows_in",
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

    # Qt's override name, hence the camelCase: this is not a project naming choice. Qt calls it
    # positionally, so the parameters take the project's own spelling.
    def nativeEventFilter(self, event_type: object, message: Any) -> object:
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
        owner = self.window()
        if owner is None or not asks_to_close(message) or not shows_in(owner, message.window):
            return False
        blocking = QApplication.activeModalWidget()
        if blocking is None:
            return False
        if not owned_by(owner, blocking):
            # A modal window this window does not own. Nothing in the application makes one, and
            # closing somebody else's dialog on a taskbar gesture is not this rule's to do.
            return False
        if not self._close_the_dialogs():
            # A dialog refused to close, so the application stays. The gesture was still acted on,
            # which is why this is handled rather than passed on.
            return True
        owner.close()
        return True

    def window(self) -> QWidget | None:
        """The window this serves, reached through Qt's parent pointer.

        **Nothing here holds a widget**, and that is not a style preference: the filter is a child
        of the window, so an attribute pointing back at it closes a loop through Qt's own
        ownership. That is the shape `T-289` forbids, because a widget the collector frees is
        destroyed off Qt's terms.

        **This module did hold one**, and the `windows desktop` job died at that test's teardown —
        *Windows fatal exception: access violation*, inside `Garbage-collecting`, in the guard that
        looks for exactly this shape. Whether the reference was the cause is not proven here; what
        is certain is that it was forbidden, and it is gone.
        """
        owner = self.parent()
        return owner if isinstance(owner, QWidget) else None

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


def shows_in(widget: QWidget, window: int) -> bool:
    """Whether `window` is the native window `widget` is showing in.

    **`windowHandle()` is typed non-optional and is not**: it returns `None` until the widget has
    been shown, which is why the annotation is written out — the same guard, and the same reason,
    as `main_window._watch_the_native_window`.
    """
    handle: QWindow | None = widget.windowHandle()
    return handle is not None and int(handle.winId()) == window


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


class Message(ctypes.Structure):
    """The head of Windows' `MSG`, as far as the last field this reads.

    `HWND hwnd; UINT message; WPARAM wParam;` — a pointer, a 32-bit unsigned, and a pointer-sized
    unsigned, which is what `c_void_p`, `c_uint` and `c_size_t` are on both of Windows' word
    sizes. `ctypes` inserts the padding Windows does. The tail (`lParam`, `time`, `pt`) is not
    declared because nothing here reads it, and `from_address` reads only what is declared.

    **Written out rather than taken from `ctypes.wintypes`**, which exists on Windows alone: with
    the layout here, `read_message` is exercised by the ordinary suite on any machine. A
    Windows-only test asserts this against `wintypes.MSG` field by field, so Windows' own
    definition is what pins it where that can be asked.
    """

    _fields_ = (
        ("window", ctypes.c_void_p),
        ("identifier", ctypes.c_uint),
        ("parameter", ctypes.c_size_t),
    )


def read_message(message: Any) -> NativeMessage:
    """The `MSG` Qt is pointing at, as the three fields the decision uses.

    **`message` is a `shiboken6.Shiboken.VoidPtr`, not the `int` PySide6's own stub promises.**
    Measured on this machine under the `xcb` plugin, where a filter is handed
    `shiboken6.Shiboken.VoidPtr(0x55fd908b1e3…)` for every native event; `int()` gives the address
    for either spelling.

    **Getting this wrong was invisible off Windows.** The first version called
    `wintypes.MSG.from_address(message)`, which raised `TypeError` for **every** Windows message
    the application received — so the taskbar's close did nothing, and the launch test on the real
    desktop failed too. `Any` is deliberate: this parameter is a pointer whose Python type Qt's
    own stubs state wrongly, and narrowing it here would encode that mistake.
    """
    raw = Message.from_address(int(message))
    return NativeMessage(
        window=int(raw.window or 0),
        identifier=int(raw.identifier),
        parameter=int(raw.parameter),
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

    **The filter is taken out again when `owner` is destroyed, explicitly.** See `installed_on`:
    relying on Qt to do it was measured and does not hold.
    """
    if platform != "win32":
        # The gesture does not exist elsewhere, and a filter called for every xcb event would cost
        # something for nothing.
        return None
    return installed_on(app, owner)


class FilterHost(Protocol):
    """What installing needs of the application: somewhere to put a native event filter.

    A protocol rather than `QApplication` so a test can watch the two calls. Qt offers no way to
    ask what native event filters are installed, so watching the host is the only way to assert
    that one was taken out again.
    """

    # Qt's names, hence the camelCase: this is not a project naming choice. The parameter is
    # positional-only, so its name is Qt's business rather than a caller's.
    def installNativeEventFilter(self, event_filter: QAbstractNativeEventFilter, /) -> None: ...

    def removeNativeEventFilter(self, event_filter: QAbstractNativeEventFilter, /) -> None: ...


def installed_on(app: FilterHost, owner: QWidget) -> TaskbarClose:
    """Install the filter, whatever the platform. `close_from_the_taskbar` decides whether to.

    **Removed again when `owner` is destroyed, and that is not belt and braces.** Qt documents
    `~QAbstractNativeEventFilter` as *"Destroys the native event filter. This automatically removes
    it from the application"*, and this module relied on it. **Measured on the `windows desktop`
    job, it did not hold**: after the filter's window was destroyed, the dispatcher still called
    the filter, and every later `QWidget.show()` in that process raised

        NotImplementedError: pure virtual method
        'QAbstractNativeEventFilter.nativeEventFilter' not implemented

    — Qt calling a filter whose Python half had gone. Fifteen tests in that job died of it.

    **The connection holds the filter, not the window**, which is what keeps `T-289`'s rule: a
    bound method of `app` plus the filter, owned by the window's own signal. Nothing here
    references a widget, so there is no cycle around one. `destroyed` is emitted at the start of
    `~QObject`, before children are deleted, so the filter is still alive to be taken out.
    """
    existing = owner.findChild(TaskbarClose, FILTER_NAME)
    if existing is not None:
        return existing
    closer = TaskbarClose(owner)
    closer.setObjectName(FILTER_NAME)
    app.installNativeEventFilter(closer)
    owner.destroyed.connect(partial(app.removeNativeEventFilter, closer))
    return closer
