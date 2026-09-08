"""Qt tests run without a display.

`TESTING.md` §10 and `T-006` both require the UI suite to pass headless on Linux and Windows
CI runners. Setting the platform here rather than relying on the caller's environment means a
plain `pytest` reproduces what CI does.
"""

import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Imported after the platform is pinned above, so nothing can load a Qt plugin before the
# offscreen choice is in the environment.
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QWidget

from tests import qt_lifecycle
from tracks_and_trails import app as application
from tracks_and_trails.downloader.ytdlp_service import YtdlpService
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.main_window import MainWindow


@pytest.fixture
def spin(qapp: QCoreApplication) -> Callable[..., bool]:
    """Deliver queued signals until a condition holds, or the timeout expires.

    The same helper `tests/integration/conftest.py` provides, and for the same reason: a probe
    result reaches a widget as a queued signal from `ResultPump`'s thread, so a test that slept
    without processing events would observe nothing however long it waited.
    """

    def wait_for(condition: Callable[[], bool], timeout: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            qapp.processEvents()
            if condition():
                return True
            time.sleep(0.005)
        qapp.processEvents()
        return condition()

    return wait_for


# --- `T-128`: an orphaned timer fails at its cause, not at the crash it becomes ----------------
#
# Qt warns when a QObject owning a live timer is destroyed from a thread that does not own it, and
# then carries on — the dispatcher keeps a pointer to freed memory and follows it on some later
# tick, which presents as a segfault with no connection to whatever caused it. Two of those cost an
# overnight soak and two core dumps to attribute (`docs/project/evidence/SOAK-FAILED-13.txt`).
#
# Installed once per session and checked after every test, so the failure names the test that did
# it. `docs/project/TESTING.md` §13: the useful signal is the one at the cause.
qt_lifecycle.fail_on_orphaned_timers()


@pytest.fixture(autouse=True)
def _no_orphaned_timers() -> Iterator[None]:
    yield
    qt_lifecycle.assert_no_orphaned_timers()


# --- `T-238`: a widget tree is collected here, not inside somebody else's test ------------------
#
# An `-n auto` worker died with `SIGSEGV` in `~QAbstractItemView`, reached from
# `_Py_HandlePending` — a deferred deletion running at an arbitrary bytecode boundary — inside a
# test whose file constructs no view at all. Sixty runs did not reproduce it, so the maintainer
# authorised the guard instead: the useful signal is the one at the cause (`docs/project/TESTING.md`
# §13).
#
# **Two halves, and only the second is an assertion.** Collecting and draining at the boundary is
# what stops a deletion carrying into a later test; the orphan check is what names a test that
# leaves a view without an owner. `tests/qt_lifecycle.py` records the measurements that chose
# `parentless` as the predicate — 802 of 839 tests leave a view *alive*, and none leaves one
# unparented, so the obvious rule would have failed a correct suite.
#
# **Ordered after the timer check on purpose**: a collection here can run a `QObject`'s destructor,
# and if that object owns a live timer Qt warns, which is `_no_orphaned_timers`' subject rather
# than this one's. Fixtures finalise in reverse order of setup, so this one — declared later —
# runs first and any warning it provokes is still checked.
#
# **The two calls inside this fixture are ordered, and the order is load-bearing — measured, not
# reasoned.** The reviewer swapped them so the assertion ran before the drain, and the helper
# subprocess died with **SIGSEGV (-11), deterministically**. That is the closest thing this
# investigation has to a reproduction: scanning live widgets while deletions are still queued
# walks a list Qt is about to change. Drain first, then look.


#: The **only** node `T-289`'s guard may be skipped for, spelled in full.
#:
#: `T-238`'s drain regression leaves a Python-owned cyclic widget on purpose, because the next test
#: proves the boundary cleared it. That is a real exemption and it is one test.
EXEMPT_FROM_THE_COLLECTOR_GUARD: Final = (
    "tests/ui/_carries_a_deletion.py::test_leaves_a_deletion_pending"
)


def _is_the_one_exempt_test(request: pytest.FixtureRequest) -> bool:
    """Whether this node is the single diagnostic allowed to end owning a collectable widget.

    **Fails closed, because the first version did not** (`T289-R4`). It asked
    `get_closest_marker`, which is **inherited**: the same marker on a class or a module suppressed
    the guard for every test underneath, and a real violation in a marked test passed. A bypass for
    a memory-corruption guard that spreads by inheritance is a bypass nobody notices spreading.

    Two conditions, and both are required: the node id must be the one allowlisted above, **and**
    the marker must be on the function itself — `own_markers`, not the inherited view. Either alone
    is weaker than it looks: the id alone would let the file's other tests through if it grew any,
    and the marker alone is what `T289-R4` broke.
    """
    if request.node.nodeid != EXEMPT_FROM_THE_COLLECTOR_GUARD:
        return False
    return any(mark.name == "leaves_a_collectable_widget" for mark in request.node.own_markers)


@pytest.fixture(autouse=True)
def _no_orphaned_views(qapp: QApplication, request: pytest.FixtureRequest) -> Iterator[None]:
    # **Armed before the test, not at the boundary** (`T289-R2`). Everything the collector frees
    # while the test runs is parked rather than released, so a widget that reached the forbidden
    # state and was collected *inside* the test is still there to be found. Sampling at teardown
    # asked what was garbage *then*, and any earlier collection had already answered by freeing it.
    with qt_lifecycle.watch_for_collectable_widgets():
        yield
        # **Inside the watch, not after it** (`T289-R2`). The first version closed the context
        # manager at the end of the body, so the parking was down for everything below and a
        # collection in that gap released the evidence rather than parking it.
        #
        # **`widgets_the_collector_would_destroy` clears `gc.garbage` whatever the verdict**, which
        # is why it is called unconditionally: skipping it for the exempt test left that parking in
        # place, and the next test — the control asserting the boundary cleared it — failed on
        # garbage this fixture had kept alive.
        dangerous = qt_lifecycle.widgets_the_collector_would_destroy(qapp)
        if dangerous and not _is_the_one_exempt_test(request):
            qt_lifecycle.raise_for_collectable_widgets(dangerous)
    # **`T-289`'s rule, and it must run BEFORE the drain.** A widget owned by Python alone and
    # reachable only through a cycle is destroyed by the collector wherever it next runs — on a
    # `QThreadPool` thread that is a `~QWidget` off the GUI thread and the double free `T-289` was
    # filed from. Checked here rather than at the end of the session so the failure names the test
    # that produced the state, which is the attribution problem both crashes arrived with.
    #
    # **`settle_deferred_deletions` calls `gc.collect()`, which destroys exactly the state this
    # looks for** — harmlessly, because that happens on the GUI thread, and invisibly, because the
    # widget is gone before the check runs. Ordered after it, this guard passed the deliberate
    # violation written to fail it. The check does its own collection with `DEBUG_SAVEALL`, which
    # parks rather than frees, and clears the garbage afterwards — so the drain below still sees an
    # ordinary interpreter and the tree is still released on this thread.
    # **The collectable-widget check ran above, before the drain, and the orphan check below must
    # not** — the two look at different things. `T238-R1` swapped the *orphan* assertion ahead of
    # the drain and the helper subprocess died with SIGSEGV, deterministically, because enumerating
    # live widgets while deletions are queued walks a list Qt is about to change. The other one
    # walks `gc.garbage`, which the collector has already set aside, and must run first because the
    # drain's own `gc.collect()` would release its evidence.
    qt_lifecycle.settle_deferred_deletions(qapp)
    qt_lifecycle.assert_no_orphaned_views(qapp)


# --- `T-225`: the application's dressing is global, so dressing it dresses every later test -----
#
# `theme.apply` changes three things on the one `QApplication` the session shares — the style
# sheet, the palette, and the module-level theme `_applied` — and **nothing put them back**. A test
# that dressed the application therefore dressed every test that ran after it in the same process.
#
# **That is what `T-225` was.** `tests/ui/test_row_delegate.py` has one test that applies both
# themes and leaves `LIGHT` on. Two `tests/ui/test_add_dialog.py` tests assert behaviour that only
# holds on an *undressed* application, and both failed when that file ran first:
#
#   - `PlaylistPanel` calls `setAutoFillBackground(True)` for the unstyled case a test window runs
#     in, and Qt's style-sheet polish clears it — so the panel's own `autoFillBackground` assertion
#     is an assertion about a bare application.
#   - A probe point computed as *off every row* stops being off every row once the sheet's metrics
#     make the rows taller, so a keyboard-fallback test silently drove the pointer path instead.
#
# Both files passed alone. The suite was green only because pytest collects `add_dialog` before
# `row_delegate`, which is an accident of the alphabet rather than a property anything asserted.
#
# **Restored around every test rather than fixed in the two tests that failed.** A reset bolted
# onto today's failures leaves the next one to be found by accident; putting the dressing back at
# the boundary every test already has means no test can leak it, including tests not yet written.
# Dressing the application inside a test stays entirely legitimate — thirteen call sites do it on
# purpose — and now costs the tests that follow nothing.
#
# **What the regression proves, and what it does not.** `tests/ui/test_suite_isolation.py` fails
# when this restores nothing. It still **passes** when only the style sheet is put back — measured
# by mutation, not assumed — because the two tests `T-225` filed depend on the sheet alone. The
# palette and `theme._applied` are restored regardless, and not for symmetry: `ui/row_delegate.py`
# reads `theme.applied()` while painting, so a leaked one changes what a later test is shown. They
# are a leak with no test on it rather than a leak that cannot happen, and this paragraph is the
# record that they are unproven — `T180-R2`'s lesson, that a mutation check is worth only what it
# is aimed at.


def _dressing(app: QApplication) -> tuple[str, QPalette, theme.Theme]:
    """Everything `theme.apply` changes, in one value that can be compared and put back.

    Typed `QApplication` rather than the `QCoreApplication` its neighbours take: a style sheet and
    a palette are widget concerns and live on the `QtWidgets` class, which is what `qapp` is.

    The palette is compared by `QPalette.__eq__` rather than by `cacheKey()`: a restored palette
    is *equal* to the saved one but does not get its cache key back, so a key comparison would
    report a leak on every test that dressed and cleaned up correctly.
    """
    return app.styleSheet(), app.palette(), theme.applied()


@pytest.fixture(autouse=True)
def _undressed_afterwards(qapp: QApplication) -> Iterator[None]:
    """Put the application's theme back the way this test found it."""
    sheet, palette, applied = _dressing(qapp)
    yield
    if _dressing(qapp) == (sheet, palette, applied):
        return
    qapp.setStyleSheet(sheet)
    qapp.setPalette(palette)
    # The module global `theme.apply` writes. Restored directly because `theme.apply` is the only
    # thing that sets it and calling that would re-dress the application this is undressing.
    theme._applied = applied


# --- the application's own screens, shared by every sweep that walks them ----------------------
#
# **This lived in `tests/ui/test_accessibility.py` until `T202-R1`'s third round**, and moving it
# is the same lesson that file already records one level up. `T200-R3` was reopened twice because
# that module held *two* inventories of screens and each check looped over whichever was nearer;
# there has been one ever since. Then the focus sweep in `test_colour_is_never_alone.py` needed
# realised screens too, and the choice was to build a second list of them or to share this one.
# A second list is the same defect with a module boundary in front of it: nobody decides to skip a
# surface, they write the next loop over the list they were already holding.
#
# So it is here, where pytest shares things, and both files walk the same nine screens.


def reaches_by_tab(widget: QWidget) -> bool:
    """Whether a keyboard can put focus on `widget` **with Tab** (`T200-R2`).

    **The capability, not the absence of its opposite.** This asked `focusPolicy() != NoFocus`,
    and `Qt.FocusPolicy.ClickFocus` satisfies that while being exactly as mouse-only as `NoFocus`
    is — so setting a control to `ClickFocus` removed it from the keyboard and left every
    accessibility test green. `NoFocus` is 0 and `ClickFocus` is 2; neither carries the `TabFocus`
    bit, which is what the chain walks.

    Testing the bit rather than naming the three policies that happen to include it means a policy
    this project has not used yet is classified by what it *does*.
    """
    return bool(int(widget.focusPolicy()) & int(Qt.FocusPolicy.TabFocus))


def focusable(widget: QWidget) -> list[QWidget]:
    """Every visible descendant **Tab** can land on, the widget itself included.

    `isVisibleTo` rather than `isVisible`, because a surface under test is realised but not
    necessarily shown on the offscreen platform, and a control hidden inside a collapsed box is
    genuinely unreachable while a control on an unshown window is not.

    **Scoped to the surface's own top-level window, which is not a detail.** A dialog opened from
    the main window is *parented* to it, so `findChildren` reaches straight into the Settings
    screen and the add dialog and reports their controls as the window's own. The first run of the
    sweep below did exactly that: it named 39 controls the window's focus chain "never reached",
    every one of them belonging to a different window that has a chain of its own. A focus chain
    does not cross a window boundary, so neither does this.
    """
    home = widget.window()
    found = [
        child
        for child in widget.findChildren(QWidget)
        if reaches_by_tab(child) and child.isVisibleTo(widget) and child.window() is home
    ]
    if reaches_by_tab(widget):
        found.insert(0, widget)
    return found


# --- one inventory of realised surfaces (T200-R3) ---------------------------------------------
#
# **This file used to carry two of these and the second one was the defect.** Top-level screens
# were opened by `surfaces()`; the screens below the add dialog were built by a `nested_surfaces`
# fixture; and every check then chose which of the two it looked at. `T200-R3` was reopened twice
# on that shape — the name check grew a nested twin, then the route check grew one, and the
# **focus-order** check never did, so adding `setTabOrder(embed_subtitles, audio_codec)` to
# `OptionsDialog` inverted a visible order while all fourteen assertions passed.
#
# The reviewer named the class rather than the instance: *a gate asks an adjacent implementation
# question rather than the criterion's user-facing question*, four times. Two inventories is how a
# criterion comes to be applied to a subset — nobody decides to skip a surface, they just write the
# next loop over the list they were already holding.
#
# **So there is one inventory now**, and every criterion-owned check walks all of it. A surface
# records how it was realised on itself, because that is a genuine difference between these
# screens; what is not allowed is for a *check* to have an opinion about which ones it applies to.


@dataclass(frozen=True, slots=True)
class Surface:
    """One realised screen, carrying what is genuinely different about it.

    Two of these fields exist because a real difference would otherwise have to live in the checks,
    which is what produced `T200-R3`. Both are properties **of the screen**, and both are asserted
    somewhere rather than merely believed.
    """

    label: str
    widget: QWidget

    #: Whether the application opened it, or this file constructed it.
    #:
    #: The screens below the add dialog are genuinely reachable — `AddUrlDialog.open_format_table`,
    #: `open_template_editor`, `open_options` and `open_preset_manager` are the routes, asserted by
    #: `tests/ui/test_add_dialog.py` — but reaching them needs a *staged row*, which needs a real
    #: probe against a fixture. Driving that here would make an accessibility failure ambiguous
    #: with a probe failure. Everything this file asks of a screen is answerable either way; only
    #: modality, which is a fact about being *opened*, is asked of the opened ones alone.
    opened_through_its_route: bool

    #: Whether Tab is expected to reach anything at all on it.
    #:
    #: **The main window is the one surface where the answer is no, and it is a criterion rather
    #: than a gap** (`T-234`): nothing on its toolbar may take focus, because `T203-R3` recorded a
    #: focusable toolbar widget stealing `Shift+F10` from the row menu on a freshly opened window.
    #: Its verbs are reached by menu and by shortcut, asserted separately below. Every other
    #: surface with an empty chain is a defect, and `test_every_surface_is_fully_reachable_by_tab`
    #: says so.
    expects_a_tab_chain: bool = True


class QuietYtdlp(YtdlpService):
    """A version service that spawns nothing, injected through `compose`'s own seam (`T200-R6`).

    **A widget audit was starting a real yt-dlp child.** `open_settings()` calls `refresh()`, the
    real service answers it by spawning a process and importing yt-dlp, and this file opens the
    Settings screen in every check that walks the inventory. The module printed *"14 passed in
    0.56 s"* and then did not exit within twelve seconds — a passing summary measures assertion
    time, not process completion, and the Implementer's broad suite hid it by doing enough other
    work while those children finished.

    The first correction closed the window through `composition.shutdown.begin()`, which is the
    right lifecycle and does close the manager, the writer, the database and the instance lock —
    but `OrderlyShutdown` does not own this task, so the process still hung. `compose()` has had an
    injection seam for exactly this since `T-198`; this is that seam, used.

    **A subclass rather than a stand-in**, so the signals, the busy state and the guard against two
    operations at once are the production ones and only the three methods that touch a process are
    replaced. `tests/integration/test_composition.py` has one of these for the same reason; it is
    not imported from there because a `tests/ui` module reaching into `tests/integration` couples
    two suites that run separately, and the shared thing would be four lines of stub.
    """

    def __init__(self) -> None:
        super().__init__(directory=Path("/nonexistent-in-tests"))

    def refresh(self) -> None:
        """Answer nothing, and spawn nothing to answer it with."""

    def install_latest_version(self) -> None:
        """Never reached here; overridden so no audit can start an install."""

    def revert(self) -> None:
        """Never reached here; overridden so no audit can start a revert."""


@pytest.fixture
def composed(qapp: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    """The real application, wired by `app.compose`, so every route below is the real route."""
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.sqlite3",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
        settings_file=tmp_path / "settings.toml",
        cache_directory=tmp_path / "cache",
        # Nothing is downloaded: every claim here is about widgets.
        entry_point=lambda *_args, **_kwargs: None,
        # And nothing is resolved: see `QuietYtdlp` (`T200-R6`).
        ytdlp_service=QuietYtdlp(),
    )
    window = composition.window
    window.show()
    qapp.processEvents()
    yield window
    # **Torn down through the lifecycle composition owns.** Closing the window alone leaves the
    # queue writer and the database open. `shutdown.begin()` is the same route
    # `tests/integration/test_composition.py` drives and the one the application takes when a user
    # closes the window. It does not own the version service, which is why `QuietYtdlp` is above
    # rather than instead of this.
    window.close()
    composition.shutdown.begin()
    deadline = time.monotonic() + 30
    while not composition.shutdown.finished and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    assert composition.shutdown.finished, "composition never finished shutting down"

    # **Release the window, and flush the deferred delete that does it** (`T-273`).
    #
    # `shutdown.begin()` stops the manager, the writer and the database — everything composition
    # *owns*. It does not own the window's lifetime, and in the product it does not need to: one
    # composition, then the process exits. **This fixture composes once per test**, and without
    # this the tree survives teardown and the suite accumulates ~25 `QWidget`s each time —
    # measured 25 / 50 / 75 over three cycles.
    #
    # **They survive because the cycle that holds them is invisible to Python's collector.**
    # `MainWindow` hands Qt objects that are its own children — `QueueView`, `FileActions` —
    # callables that close over `self` (`main_window.py:740`, `:741`, `:903`, and eight more from
    # `app.compose`). The C++ parent-child edge and the C++ signal connection are both untraversable
    # by `gc`, so it never sees a cycle, and the refcount never falls. Clearing those closure cells
    # by hand releases all 25 immediately, which is how this was identified rather than guessed.
    #
    # **`processEvents()` alone is not enough and that is the whole trick.** `deleteLater()` posts
    # a `DeferredDelete`, which `processEvents()` does not flush; without `sendPostedEvents` the
    # count is unchanged at 25 / 50 / 75. With it, three cycles leave **0 / 0 / 0**.
    window.deleteLater()
    qapp.processEvents()
    # **Scoped to this window** (`T273-R2`). `None` flushes every pending `DeferredDelete` in the
    # process, including any a test's own objects are waiting on, which is a wider effect than
    # this fixture has any business having. The receiver form delivers to this tree alone.
    QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
    qapp.processEvents()

    # **This window, not "no window anywhere".** Several tests build a `MainWindow` of their own
    # and are entitled to; an assertion over `allWidgets()` fails in whichever test happens to run
    # after one of them, which is a false positive about the wrong object.
    # **Every use of `composed`, which is 14 of the 1,058 collected UI cases** (`T273-R3`) — not
    # every UI test, which is what this said and was wrong by two orders of magnitude. Most UI
    # tests build the widget under test directly and never compose the application at all.
    assert not shiboken6.isValid(window), (
        "this fixture's MainWindow survived its own teardown, so composing tests accumulate a "
        "window tree each — see T-273. Either the deferred delete stopped being flushed, or "
        "something new holds the tree"
    )


@pytest.fixture
def every_surface(composed: MainWindow, qapp: QApplication) -> Iterator[list[Surface]]:
    """Every screen this application shows, realised, in one list.

    The top-level screens are opened the way the application opens them — `open_add_dialog()`,
    `open_settings()`, `show_about()` — rather than constructed. **`T-201` is why.** Its text was
    written, tested and correct for twelve error classes and reached nobody, because the only
    widget that composed it was one `UX-005` §2 had left nothing constructing. A pass that
    instantiates a screen in order to audit it can pass over a screen no user can open.

    The screens below the add dialog are constructed, for the reason recorded on
    `Surface.opened_through_its_route`, and **shown**: geometry is what
    `test_tab_order_follows_visual_order_on_every_surface` compares, and an unrealised widget has
    none worth comparing.
    """
    from tests.ui.surfaces import screens_below_the_add_dialog

    inventory: list[Surface] = [
        Surface(
            "main window",
            composed,
            opened_through_its_route=True,
            expects_a_tab_chain=False,
        )
    ]

    add = composed.open_add_dialog()
    qapp.processEvents()
    inventory.append(Surface("add dialog", add, opened_through_its_route=True))

    settings = composed.open_settings()
    assert settings is not None, (
        "composition wired no settings writers, so the Settings screen never opened and this "
        "sweep would silently cover one surface fewer"
    )
    qapp.processEvents()
    inventory.append(Surface("settings", settings, opened_through_its_route=True))

    about = composed.show_about()
    qapp.processEvents()
    inventory.append(Surface("about", about, opened_through_its_route=True))

    # **The list moved to `tests/ui/surfaces.py` and did not become a second one** (`T238-R5`).
    # `tools/t238_widget_cycle_probe.py` needs the same five for `T-238`'s criterion 4, which asks
    # about *any* application widget; two lists of them would drift, and the drift would be
    # invisible to both readers.
    built: list[tuple[str, QWidget]] = screens_below_the_add_dialog()
    for label, widget in built:
        widget.show()
        inventory.append(Surface(label, widget, opened_through_its_route=False))
    qapp.processEvents()

    yield inventory

    # **The constructed ones are owned here, because nothing else owns them** (`T-238`). They are
    # built parentless, and a parentless widget left to the garbage collector has its destructor
    # run inside whichever test comes next — which segfaulted the very next `compose()` when this
    # was a plain function. `T-238`'s guard is the record of that exact shape: *views alive with no
    # parent: zero*.
    for _label, widget in built:
        widget.close()
        widget.deleteLater()
    qapp.processEvents()
