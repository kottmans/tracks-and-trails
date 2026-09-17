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

import ctypes
import inspect
import sys
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest
import shiboken6
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog, QWidget
from shiboken6 import Shiboken

from tests import qt_lifecycle
from tracks_and_trails.ui import taskbar_close
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
    read_message,
)

#: What PySide6 hands a native event filter for the message, measured under `xcb` on this machine.
VoidPtr = Shiboken.VoidPtr

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


def test_another_windows_dialog_underneath_ours_is_left_alone(
    window: QWidget, shown: Callable[[], QWidget]
) -> None:
    """`T343-R1`: ownership is asked again for each dialog the loop reaches, not once.

    The review's own probe. An unrelated window's dialog is opened **first** and the target's
    **second**, so the owned one is on top of the application's modal stack and the unrelated one
    is directly beneath it. Closing the owned dialog uncovers the other, and the loop used to close
    that too — the initial check had already passed, and it was never asked again.

    Nothing in the shipped application opens a second modal owner today, so this is the bound
    rather than a user path: what it fixes is a rule that would close a dialog it does not own the
    moment one exists.
    """
    other = shown()
    theirs = _modal_dialog(other)
    ours = _modal_dialog(window)
    assert QApplication.activeModalWidget() is ours, "the owned dialog must be the one on top"

    handled = TaskbarClose(window).consider(_close_of(window))

    assert handled
    assert not ours.isVisible(), "the dialog that blocked this window is still up"
    assert theirs.isVisible(), "a dialog belonging to another window was closed as well"
    assert not window.isVisible(), "this window closed once its own dialog was gone"
    assert other.isVisible(), "the other window was closed too"


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


#: Platforms that are not Windows, named rather than inferred, so this file asserts the off-Windows
#: answer on Windows too. `reveal.py`'s reason for taking the platform as a parameter at all.
NOT_WINDOWS = ("linux", "darwin", "freebsd13")


@pytest.mark.parametrize("platform", NOT_WINDOWS)
def test_nothing_is_installed_off_windows(
    qapp: QApplication, window: QWidget, platform: str
) -> None:
    """The gesture is Windows-only by the ruling, and a native filter is called for every event.

    On xcb that is every mouse move, so the cost is only paid where the behaviour exists.
    """
    assert close_from_the_taskbar(qapp, window, platform) is None
    assert window.findChild(TaskbarClose, FILTER_NAME) is None


def test_the_platform_it_reads_by_default_is_the_running_one() -> None:
    """The parameter exists to be injected; its default is what production depends on.

    A default of anything else would install nothing on Windows, or install everywhere, and every
    other test here passes the platform explicitly and would not notice.
    """
    default = inspect.signature(close_from_the_taskbar).parameters["platform"].default

    assert default == sys.platform


def test_it_is_installed_once_however_often_composition_asks(
    qapp: QApplication, window: QWidget
) -> None:
    """Composition asks once, but `present` is called by tests as well as by `run`."""
    first = close_from_the_taskbar(qapp, window, "win32")
    second = close_from_the_taskbar(qapp, window, "win32")

    assert first is not None
    assert second is first, "a second installation added a second filter"
    assert window.findChild(TaskbarClose, FILTER_NAME) is first


def test_the_filter_belongs_to_the_window_it_serves(qapp: QApplication, window: QWidget) -> None:
    """The window is what owns it, so its lifetime is the window's and not the application's."""
    closer = close_from_the_taskbar(qapp, window, "win32")

    assert closer is not None
    assert closer.parent() is window


class _RecordsTheFilters:
    """A stand-in for the application, because Qt will not say what filters are installed."""

    def __init__(self) -> None:
        self.installed: list[object] = []
        self.removed: list[object] = []

    # Qt's names, hence the camelCase: this is not a project naming choice.
    def installNativeEventFilter(self, event_filter: object, /) -> None:  # noqa: N802 - Qt's name
        self.installed.append(event_filter)

    def removeNativeEventFilter(self, event_filter: object, /) -> None:  # noqa: N802 - Qt's name
        self.removed.append(event_filter)


def test_the_filter_is_taken_out_when_its_window_is_destroyed(qapp: QApplication) -> None:
    """Qt's documented auto-removal is not enough, and the `windows desktop` job is how we know.

    `~QAbstractNativeEventFilter` is documented as removing the filter from the application, and
    this module relied on that alone. After a run where the filter's window was destroyed, Qt
    dispatched into it anyway and **every later `QWidget.show()` in that process raised**
    `NotImplementedError: pure virtual method 'QAbstractNativeEventFilter.nativeEventFilter' not
    implemented` — a filter whose Python half had gone. Fifteen tests died of it.

    **That is dispatch, not a statement about the destructor**: whether the C++ half ever ran is
    not established, which is the reviewer's correction to how this was first written.

    So removal is explicit, and this is what says so. The host is a stand-in because Qt offers no
    way to ask what native event filters are installed.
    """
    host = _RecordsTheFilters()
    window = QWidget()
    window.show()
    QApplication.processEvents()
    closer = installed_on(cast("Any", host), window)

    assert host.installed == [closer]
    assert host.removed == [], "it was taken out before the window went anywhere"

    window.deleteLater()
    qt_lifecycle.settle_deferred_deletions(qapp)

    assert host.removed == [closer], "the window was destroyed and the filter is still installed"


def test_a_message_that_is_not_a_windows_message_is_not_read(window: QWidget) -> None:
    """The one guard `read_message` depends on: nothing else reaches memory.

    An xcb event carries a pointer to something that is not an `MSG`, and the filter is installed
    on Windows only — but this is what keeps *installed* and *reads memory* separate claims.
    """
    closer = TaskbarClose(window)

    assert closer.nativeEventFilter(b"xcb_generic_event_t", 0) == (False, 0)


# --- the pointer Qt hands over, and reading the MSG out of it ---------------------------------
#
# **This is the half that was missing, and the Windows job is what said so.** Everything above
# drives `consider` with values, and all of it passed while the entry point was broken for every
# message: `read_message` was handed `shiboken6.Shiboken.VoidPtr` and called
# `wintypes.MSG.from_address` on it, which raises. The taskbar's close did nothing, and the launch
# test on the real desktop failed as well.
#
# The pointer's Python type is not Windows-specific — it is what PySide6 passes a native event
# filter on any platform, measured here under `xcb` — so the entry point is testable on this
# machine, and now is.


def _pointer_to(window: int, identifier: int, parameter: int) -> tuple[Any, Any]:
    """A `MSG` in memory and the `VoidPtr` Qt would hand over for it.

    The structure is returned with the pointer **because it owns the memory**: dropping it frees
    what the pointer addresses, and reading that back is the bug this file is here to catch rather
    than to commit.
    """
    raw = taskbar_close.Message(window=window, identifier=identifier, parameter=parameter)
    return raw, VoidPtr(ctypes.addressof(raw))


def test_the_pointer_qt_passes_is_read_as_a_message() -> None:
    """`VoidPtr`, not `int` — PySide6's own stub says `int` and its filter passes the other."""
    raw, pointer = _pointer_to(window=0x1234, identifier=WM_CLOSE, parameter=0)

    message = read_message(pointer)

    assert (message.window, message.identifier, message.parameter) == (0x1234, WM_CLOSE, 0)
    del raw


def test_a_plain_address_is_read_as_a_message() -> None:
    """The spelling the stub promises, in case a later PySide6 passes it."""
    raw, _ = _pointer_to(window=7, identifier=WM_SYSCOMMAND, parameter=SYSTEM_CLOSE)

    message = read_message(ctypes.addressof(raw))

    assert message.window == 7
    assert (message.identifier, message.parameter) == (WM_SYSCOMMAND, SYSTEM_CLOSE)


def test_the_filter_acts_on_the_pointer_qt_would_hand_it(window: QWidget) -> None:
    """The entry point, end to end, with both of the things Qt really passes.

    A `QByteArray` for the name and a `VoidPtr` for the message: this is the test that fails when
    either is read wrongly, and the one this file did not have when the `windows desktop` job ran.
    """
    dialog = _modal_dialog(window)
    closer = TaskbarClose(window)
    raw, pointer = _pointer_to(window=_window_id(window), identifier=WM_CLOSE, parameter=0)

    handled = closer.nativeEventFilter(QByteArray(b"windows_generic_MSG"), pointer)

    assert handled == (True, 0)
    assert not dialog.isVisible()
    assert not window.isVisible()
    del raw


def test_the_filter_leaves_an_ordinary_message_to_qt(window: QWidget) -> None:
    """Every Windows message reaches this, so the common path must be the untouched one."""
    _modal_dialog(window)
    closer = TaskbarClose(window)
    raw, pointer = _pointer_to(window=_window_id(window), identifier=WM_MOUSEMOVE, parameter=0)

    handled = closer.nativeEventFilter(QByteArray(b"windows_generic_MSG"), pointer)

    assert handled == (False, 0)
    assert window.isVisible()
    del raw


def test_the_filter_holds_no_reference_to_its_window(qapp: QApplication, window: QWidget) -> None:
    """`T-289`'s boundary: nothing here may hold a widget. The filter reaches its window by parent.

    The filter is a **child** of the window, so an attribute pointing back at it closes a loop
    through Qt's ownership — the shape this project forbids, and the one the module had when the
    `windows desktop` job died in the collector guard at teardown.

    **This asks the filter directly, and that is deliberate.** The obvious test — build the state,
    then call `qt_lifecycle.widgets_the_collector_would_destroy` — was written first and **passed
    with the reference put back**, twice over, in the mutation campaign. Whatever the guard sees on
    Windows, it does not see this on Linux, so a test built on it would have been decoration.
    """
    closer = installed_on(qapp, window)
    closer.window()  # any lazily-held reference would be taken here

    held = [name for name, value in vars(closer).items() if isinstance(value, QWidget)]

    assert held == [], f"the filter holds its window in {held}"
    assert closer.window() is window, "and it must still be able to reach it"


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
