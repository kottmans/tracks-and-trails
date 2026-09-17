"""The taskbar's *Close window* reaches the application through a dialog (`ui/taskbar_close.py`).

`T-343`: with *Add URLs* or *Preferences* open, the taskbar's *Close window* did nothing, because
Windows disables the owner of a modal dialog and Qt will not deliver a close to a blocked window.
The ruling on 2026-09-17 was Windows-only handling, so the filter reads the message before Qt does.

**These are the offscreen halves.** Everything except reading the `MSG` out of memory is a decision
about values, and `TaskbarClose.consider` takes those values, so the whole decision is tested on
either platform. The message path itself — a real taskbar message, posted to a real `HWND`, through
Qt's own filter chain — is in `tests/ui/test_windows_desktop.py` and only runs on Windows.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator

import pytest
import shiboken6
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from tracks_and_trails.ui.taskbar_close import (
    FILTER_NAME,
    SYSTEM_CLOSE,
    WM_CLOSE,
    WM_SYSCOMMAND,
    NativeMessage,
    TaskbarClose,
    a_windows_message,
    asks_to_close,
    close_from_the_taskbar,
    installed_on,
)

#: `SC_MINIMIZE`. A system command that is not a close, so the mask cannot be a blanket pass.
SYSTEM_MINIMIZE = 0xF020

#: `WM_MOUSEMOVE`, standing for the flood of messages that must reach Qt untouched.
WM_MOUSEMOVE = 0x0200


@pytest.fixture
def shown(qapp: QApplication) -> Iterator[Callable[[], QWidget]]:
    """Makes shown top-level widgets and takes them all down afterwards.

    **Dialogs are hidden before their window goes**, which is what releases the modality: a
    modal dialog left up would block the next test in this session's shared application, and a
    window a modal dialog blocks does not act on `close()` either.
    """
    made: list[QWidget] = []

    def make() -> QWidget:
        widget = QWidget()
        widget.show()
        QApplication.processEvents()
        made.append(widget)
        return widget

    yield make

    for widget in reversed(made):
        if not shiboken6.isValid(widget):
            continue
        for dialog in widget.findChildren(QDialog):
            dialog.hide()
        widget.hide()
        widget.deleteLater()
    QApplication.processEvents()


@pytest.fixture
def window(shown: Callable[[], QWidget]) -> QWidget:
    """One shown widget, which is what gives it a window handle to be addressed by."""
    return shown()


def _window_id(widget: QWidget) -> int:
    handle = widget.windowHandle()
    assert handle is not None, "the widget was never shown, so nothing addresses it"
    return int(handle.winId())


def _close_of(widget: QWidget, identifier: int = WM_CLOSE, parameter: int = 0) -> NativeMessage:
    return NativeMessage(window=_window_id(widget), identifier=identifier, parameter=parameter)


def _modal_dialog(parent: QWidget) -> QDialog:
    """A window-modal dialog opened the way the application's own dialogs are (`open()`)."""
    dialog = QDialog(parent)
    dialog.open()
    QApplication.processEvents()
    assert dialog.isModal(), "the dialog is not modal, so it blocks nothing and proves nothing"
    return dialog


# --- which messages are a close -----------------------------------------------------------


def test_wm_close_is_a_close() -> None:
    assert asks_to_close(NativeMessage(window=1, identifier=WM_CLOSE, parameter=0))


def test_the_system_menus_close_is_a_close() -> None:
    """`WM_SYSCOMMAND` with `SC_CLOSE`, the other form the report's gesture arrives as."""
    assert asks_to_close(NativeMessage(window=1, identifier=WM_SYSCOMMAND, parameter=SYSTEM_CLOSE))


def test_the_system_keeps_the_low_four_bits_and_a_close_is_still_a_close() -> None:
    """Windows documents the low four bits of a system command as its own.

    A comparison against `SC_CLOSE` itself would miss the close that arrives from a mnemonic,
    which is the reading this mask exists for.
    """
    assert asks_to_close(
        NativeMessage(window=1, identifier=WM_SYSCOMMAND, parameter=SYSTEM_CLOSE | 0x0002)
    )


def test_another_system_command_is_not_a_close() -> None:
    assert not asks_to_close(
        NativeMessage(window=1, identifier=WM_SYSCOMMAND, parameter=SYSTEM_MINIMIZE)
    )


def test_an_ordinary_message_is_not_a_close() -> None:
    assert not asks_to_close(NativeMessage(window=1, identifier=WM_MOUSEMOVE, parameter=0))


# --- what the filter does with one ---------------------------------------------------------


def test_a_close_with_a_dialog_open_closes_the_dialog_and_the_window(window: QWidget) -> None:
    """The report, as a decision: the gesture now reaches the application."""
    dialog = _modal_dialog(window)
    closer = TaskbarClose(window)

    handled = closer.consider(_close_of(window))

    assert handled, "the message was passed on to Qt, which is what ignored it"
    assert not dialog.isVisible(), "the dialog that blocked the window is still up"
    assert not window.isVisible(), "the application was asked to close and did not"


def test_the_system_menus_close_does_the_same(window: QWidget) -> None:
    """Both forms were measured as ignored, so both are handled."""
    dialog = _modal_dialog(window)
    closer = TaskbarClose(window)

    handled = closer.consider(_close_of(window, WM_SYSCOMMAND, SYSTEM_CLOSE))

    assert handled
    assert not dialog.isVisible()
    assert not window.isVisible()


def test_stacked_dialogs_are_all_closed(window: QWidget) -> None:
    """*Preferences* with a box on top of it: the innermost blocks, so it goes first."""
    outer = _modal_dialog(window)
    inner = _modal_dialog(outer)

    handled = TaskbarClose(window).consider(_close_of(window))

    assert handled
    assert not inner.isVisible(), "the inner dialog is still up"
    assert not outer.isVisible(), "the outer dialog is still up"
    assert not window.isVisible()


def test_a_close_with_no_dialog_open_is_left_to_qt(window: QWidget) -> None:
    """Qt already closes an unblocked window, and `closeEvent` is where the shutdown starts.

    Handling it here would bypass `MainWindow.closeEvent`'s geometry save and `closing` signal,
    so the message must be passed on untouched.
    """
    closer = TaskbarClose(window)

    handled = closer.consider(_close_of(window))

    assert not handled, "the filter took a close Qt was going to handle correctly"
    assert window.isVisible(), "the filter closed the window instead of letting Qt do it"


def test_a_close_addressed_to_another_window_is_ignored(
    window: QWidget, shown: Callable[[], QWidget]
) -> None:
    """One message queue carries every window's messages, this window's neighbours included."""
    _modal_dialog(window)
    other = shown()
    closer = TaskbarClose(window)

    handled = closer.consider(_close_of(other))

    assert not handled
    assert window.isVisible(), "a close for another window closed this one"


def test_an_ordinary_message_for_this_window_is_ignored(window: QWidget) -> None:
    _modal_dialog(window)
    closer = TaskbarClose(window)

    assert not closer.consider(_close_of(window, WM_MOUSEMOVE))
    assert window.isVisible()


def test_a_modal_window_this_window_does_not_own_is_left_alone(
    window: QWidget, shown: Callable[[], QWidget]
) -> None:
    """Closing somebody else's dialog on a taskbar gesture is not this rule's to do."""
    other = shown()
    dialog = _modal_dialog(other)
    closer = TaskbarClose(window)

    handled = closer.consider(_close_of(window))

    assert not handled
    assert dialog.isVisible(), "a dialog belonging to another window was closed"
    assert window.isVisible()


class _DialogThatRefuses(QDialog):
    """A dialog whose close event is ignored, which is what `close()` returning false means."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.refusing = True
        self.asked = 0

    # Qt's override name, hence the camelCase: this is not a project naming choice.
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt's name
        self.asked += 1
        if self.refusing:
            event.ignore()
            return
        super().closeEvent(event)


def test_a_dialog_that_refuses_to_close_keeps_the_application_open(window: QWidget) -> None:
    """*Add URLs* is the shipped dialog that does this, and closing over it would be worse.

    `AddUrlDialog.done` holds the close while a commit is in flight (`T118-R3`): it returns
    without hiding, so Qt ignores the close event and `close()` answers false. This is that
    mechanism, on a dialog small enough to be the subject.

    The gesture is still **handled**: passing it on would reach the window Qt is blocking, which
    is where this began.
    """
    dialog = _DialogThatRefuses(window)
    dialog.open()
    QApplication.processEvents()

    handled = TaskbarClose(window).consider(_close_of(window))

    assert handled
    assert dialog.isVisible(), "the dialog refused the close and was closed anyway"
    assert window.isVisible(), "the application closed over a dialog that refused"
    assert dialog.asked == 1, (
        f"the dialog was asked to close {dialog.asked} times. A refusal is an answer: asking "
        "again until the loop runs out spends the bound on a dialog that already said no"
    )
    dialog.refusing = False


def test_a_dialog_that_deletes_itself_on_close_is_gone(window: QWidget) -> None:
    """*Diagnostics…* carries `WA_DeleteOnClose`, so this close has to behave like any other."""
    dialog = _modal_dialog(window)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    TaskbarClose(window).consider(_close_of(window))
    QApplication.processEvents()

    assert not shiboken6.isValid(dialog), "the dialog was hidden rather than closed"
    assert QApplication.activeModalWidget() is None, "something is still blocking the window"


class _RecordsItsClose(QWidget):
    """Counts the close events it is given, which is how the window's own path is proved run."""

    def __init__(self) -> None:
        super().__init__()
        self.closes = 0

    # Qt's override name, hence the camelCase: this is not a project naming choice.
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt's name
        self.closes += 1
        super().closeEvent(event)


def test_the_close_reaches_the_windows_own_close_event(qapp: QApplication) -> None:
    """`MainWindow.closeEvent` saves the geometry and starts the shutdown, so it must run.

    Hiding the window would look the same to a person and lose both.
    """
    window = _RecordsItsClose()
    window.show()
    QApplication.processEvents()
    dialog = _modal_dialog(window)

    TaskbarClose(window).consider(_close_of(window))

    assert window.closes == 1, "the window was hidden rather than closed"
    dialog.hide()
    window.hide()
    window.deleteLater()
    QApplication.processEvents()


# --- installation ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="the Windows half is the installation itself")
def test_nothing_is_installed_off_windows(qapp: QApplication, window: QWidget) -> None:
    """The gesture is Windows-only by the ruling, and a native filter is called for every event.

    On xcb that is every mouse move, so the cost is only paid where the behaviour exists.
    """
    assert close_from_the_taskbar(qapp, window) is None
    assert window.findChild(TaskbarClose, FILTER_NAME) is None


def test_it_is_installed_once_however_often_composition_asks(
    qapp: QApplication, window: QWidget, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Composition asks once, but `present` is called by tests as well as by `run`."""
    monkeypatch.setattr(sys, "platform", "win32")

    first = close_from_the_taskbar(qapp, window)
    second = close_from_the_taskbar(qapp, window)

    assert first is not None
    assert second is first, "a second installation added a second filter"
    assert window.findChild(TaskbarClose, FILTER_NAME) is first


def test_the_filter_belongs_to_the_window_it_serves(
    qapp: QApplication, window: QWidget, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Qt removes a native event filter when it is destroyed, and this is what destroys it.

    A filter that outlived its window would be called for every message of every window after
    it, holding a pointer into freed memory.
    """
    monkeypatch.setattr(sys, "platform", "win32")

    closer = close_from_the_taskbar(qapp, window)

    assert closer is not None
    assert closer.parent() is window


def test_a_message_that_is_not_a_windows_message_is_not_read(window: QWidget) -> None:
    """The one guard `read_message` depends on: nothing else reaches memory.

    An xcb event carries a pointer to something that is not an `MSG`, and the filter is installed
    on Windows only — but this is what keeps *installed* and *reads memory* separate claims.
    """
    closer = TaskbarClose(window)

    assert closer.nativeEventFilter(b"xcb_generic_event_t", 0) == (False, 0)


# --- which native events are Windows messages ------------------------------------------------
#
# Qt's own type for the name is a `QByteArray` and PySide6 has handed it over as `bytes`, so both
# are recognised. Neither spelling can be observed from this machine, which is why each is
# asserted rather than assumed: the wrong guess would either read an xcb event as an `MSG` or
# never act at all.


@pytest.mark.parametrize("name", [b"windows_generic_MSG", b"windows_dispatcher_MSG"])
def test_qts_own_type_for_the_name_is_recognised(name: bytes) -> None:
    assert a_windows_message(QByteArray(name))


@pytest.mark.parametrize("name", [b"windows_generic_MSG", b"windows_dispatcher_MSG"])
def test_the_name_as_plain_bytes_is_recognised(name: bytes) -> None:
    assert a_windows_message(name)


@pytest.mark.parametrize(
    "event_type",
    [
        pytest.param(b"xcb_generic_event_t", id="xcb"),
        pytest.param(QByteArray(b"xcb_generic_event_t"), id="xcb-as-QByteArray"),
        pytest.param("windows_generic_MSG", id="a-string-is-not-the-name"),
        pytest.param(None, id="nothing-at-all"),
    ],
)
def test_anything_else_is_not_a_windows_message(event_type: object) -> None:
    assert not a_windows_message(event_type)


def test_installing_is_separate_from_deciding_to(qapp: QApplication, window: QWidget) -> None:
    """`installed_on` is what the platform branch calls, and it is checked on both platforms.

    The branch itself is written so the type checker reads it as platform-conditional; this is
    the half of it that has behaviour.
    """
    closer = installed_on(qapp, window)

    assert closer.objectName() == FILTER_NAME
    assert installed_on(qapp, window) is closer
