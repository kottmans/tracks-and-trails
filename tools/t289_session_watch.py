"""Run the real application and report any Qt widget destroyed off the GUI thread (`T-289`).

**What this is for.** `T-289`'s criterion 2 is not met: the guard in `tests/ui` enforces the rule
over what the suite exercises, and the released crash route is still unidentified — the core dump
names no Python type. The maintainer ruled on 2026-08-30 to **instrument the real route** rather
than re-scope the task. This is that instrument.

**It changes nothing in the product.** No `src/` file is touched and no flag is read by the
application: the wrapper *is* the flag. Running `python -m tracks_and_trails` is unaffected in every
way; the watch exists only inside this process, because this script installed it before starting the
same entry point.

## What it records, and why these three things

- **Every widget destroyed on a thread that is not the GUI thread.** `QObject::destroyed` is emitted
  inside `~QObject`, so a `DirectConnection` handler runs on the thread executing the destructor.
  That is the crash's precondition, observed rather than inferred.
- **The Python stack of that thread at that moment**, which is what names the code that was running
  — the thing the core dump could not give, because it had no Python-side type.
- **Every cyclic collection and the thread it ran on**, through `gc.callbacks`. A destruction inside
  a collection is `T-289`'s shape exactly; one outside it is a different finding and must not be
  filed as this one.

**Nothing is parked and no collection is forced.** `DEBUG_SAVEALL` would keep every collected object
alive for the session, which changes the memory behaviour of the very thing being measured. The
watch observes; it does not steer.

## What it costs, stated because it runs on a machine somebody is using

An application-wide event filter sees each widget's first event and connects `destroyed` to it: one
comparison per event and one connection per widget, unmeasurable against a UI. A 200 ms heartbeat
timer does nothing except let the interpreter run pending signal handlers, so the session can be
ended and still write a verdict.

**Nothing enumerates live widgets** (`T289-R8`), which is deliberate: `T238-R1` recorded
`QApplication.allWidgets()` killing a process with SIGSEGV while deletions were queued, and an
instrument for memory corruption must not be a plausible cause of it.

**The bound is a widget that receives no event at all** — never polished, shown or laid out. Such a
widget is invisible here, and it is also not one a user interacted with.

## Running it — the route the crash came from

    .venv/bin/python tools/t289_session_watch.py --self-test        # first, and it takes a second
    env -u QT_QPA_PLATFORM .venv/bin/python tools/t289_session_watch.py \
        --report reports/t289-session.txt

Then, in the application: **Settings → yt-dlp → Update**. Let the update finish, use the window
normally for a minute, and close it from the window button. The report is written as events happen,
so it survives an abort.

**`env -u QT_QPA_PLATFORM` removes any inherited `offscreen`** rather than setting it empty, so Qt
picks the real platform. This measurement is worth nothing without a real display.

**Run `--self-test` first, every time.** It builds the arm this project measured — a Python-subclass
widget, unparented, in a cycle, collected on a pool thread — and requires the watch to report it. A
session that ends *"nothing off the GUI thread"* means only as much as that check passing
beforehand, and three instruments in this family have reported confidently about nothing.

**A clean run is a result.** *No off-GUI destruction observed* over the route that crashed is
evidence about that route, and the report says how long it watched and how many widgets it saw, so
the absence can be read.
"""

from __future__ import annotations

import argparse
import gc
import os
import signal
import sys
import threading
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

#: The attribute marking a widget this watch has already connected to.
WATCHED = "_t289_watched"


class Watch(QObject):
    """One session's observations, written as they happen.

    A `QObject` because it is installed as the application's event filter — which is how widgets
    are discovered without ever enumerating them (`T289-R8`).
    """

    def __init__(self, report: TextIO, gui_thread: str) -> None:
        super().__init__()
        self.report = report
        self.gui_thread = gui_thread
        self.widgets_seen = 0
        self.off_gui_destructions = 0
        self.off_gui_in_a_collection = 0
        self.off_gui_tags: list[str] = []
        #: Python-typed widgets the collector destroyed **on the GUI thread** — near misses, and
        #: the names criterion 2 needs even when the session never goes wrong (`T289-R6`).
        self.candidates_collected: list[str] = []
        self.gui_destructions = 0
        self.gui_destructions_in_a_collection = 0
        self.collected_objects = 0
        self.collections: dict[str, int] = {}
        self.collecting: set[str] = set()
        #: The route milestones, which decide whether a null result may be called meaningful.
        self.settings_opened = False
        self.update_started = False
        self.update_finished = False
        self.started = datetime.now(UTC)

    def say(self, line: str) -> None:
        """Write and flush. **Flushed because the process may abort**, which is the subject."""
        stamp = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        self.report.write(f"{stamp}  {line}\n")
        self.report.flush()

    def note_a_collection(self, phase: str, info: dict[str, int]) -> None:
        """Track both phases, on every thread (`T289-R6`).

        The first version logged only *starts*, and only off the GUI thread. Two things were then
        unreadable. **Whether the collector ran at all while widgets were garbage** — without which
        a null result says nothing, because *no off-GUI destruction* and *no collection that could
        have caused one* look identical. And **which destructions happened inside a collection**,
        which needs the start/stop window per thread rather than a count.
        """
        thread = threading.current_thread().name
        if phase == "start":
            self.collecting.add(thread)
            self.collections[thread] = self.collections.get(thread, 0) + 1
            if thread != self.gui_thread:
                self.say(f"gc collection started on {thread!r} — the loaded gun, widget or not")
        else:
            self.collecting.discard(thread)
            freed = info.get("collected", 0)
            self.collected_objects += freed
            if thread != self.gui_thread and freed:
                self.say(f"gc collection on {thread!r} freed {freed} objects")

    def watch(self, widget: QWidget) -> None:
        tag = f"{type(widget).__name__}({widget.objectName() or 'unnamed'})"
        module = type(widget).__module__
        # **Two properties, not one** (`T289-R6`). A type defined in Python is what makes
        # destruction happen *in place* rather than being marshalled, and `ownedByPython` is what
        # makes the wrapper's release destroy anything at all. A Python subclass **with a Qt
        # parent** is owned by C++: dropping its wrapper destroys nothing, and the first version
        # named one of those as `T-289`'s tree.
        #
        # **Kept in a cell and refreshed as the widget lives**, because ownership changes: a widget
        # reparented after this first sees it would otherwise carry a stale verdict. The filter
        # updates it on every later event, which is cheap and is the only moment the widget is
        # certainly alive — at `destroyed` time the C++ half is going and asking shiboken anything
        # then is a question about a corpse.
        state = {"candidate": self.is_a_candidate(widget)}

        def destroyed(*_args: object) -> None:
            thread = threading.current_thread().name
            inside = thread in self.collecting
            if thread == self.gui_thread:
                # **Counted, and the candidates are named** (`T289-R6`). A widget destroyed *by a
                # collection* on the GUI thread is the same event with the safe thread underneath —
                # and if its type is defined in Python, it is **the tree that would have been
                # destroyed in place had the collector fired on a pool thread instead**. That is the
                # most useful thing this instrument can find short of the crash, and the first
                # version recorded it as a number with no name.
                self.gui_destructions += 1
                if inside:
                    self.gui_destructions_in_a_collection += 1
                    if state["candidate"]:
                        self.candidates_collected.append(tag)
                        self.say(
                            f"~~ {tag} from {module} was collected on the GUI thread. Its type is "
                            "defined in Python, so the same collection on a pool thread would have "
                            "run its destructor there — this is T-289's tree, on the safe thread."
                        )
                return
            self.off_gui_destructions += 1
            self.off_gui_tags.append(tag)
            if inside:
                self.off_gui_in_a_collection += 1
            where = "inside a gc collection" if inside else "OUTSIDE any gc collection"
            self.say(f"!! {tag} from {module} destroyed on {thread!r} — NOT the GUI thread")
            self.say(f"   {where} on that thread")
            if not inside:
                self.say(
                    "   NOT T-289's mechanism: this task is the *collector* destroying a widget on "
                    "the wrong thread. A destruction off the GUI thread with no collection running "
                    "is a different defect and wants its own entry."
                )
            self.say("   Python stack of that thread:")
            for frame in traceback.extract_stack()[:-1][-12:]:
                self.say(f"     {frame.filename}:{frame.lineno} in {frame.name}")

        widget.destroyed.connect(destroyed, Qt.ConnectionType.DirectConnection)
        widget.__dict__[WATCHED] = state
        self.widgets_seen += 1
        self.note_the_settings_screen(widget)

    @staticmethod
    def is_a_candidate(widget: QWidget) -> bool:
        """Whether releasing this widget's wrapper would destroy a Qt widget in place (`T289-R6`).

        Both halves are required and each excludes a real state: a **PySide type** is marshalled to
        the GUI thread and destroys nothing dangerous wherever its wrapper goes, and a widget **not
        owned by Python** belongs to its Qt parent, which is what destroys it.
        """
        import shiboken6

        if type(widget).__module__.startswith("PySide6"):
            return False
        return bool(shiboken6.isValid(widget) and shiboken6.ownedByPython(widget))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt's name
        """Discover widgets as Qt sends them events. **Never enumerates live widgets** (`T289-R8`).

        The first version polled `QApplication.allWidgets()` every 250 ms — the exact enumeration
        `T238-R1` recorded killing a process with SIGSEGV, deterministically, when deletions were
        queued. Doing that on a loop, in a real session, in an instrument built to observe a
        memory-corruption bug, would have made the tool a plausible cause of what it saw.

        An application-wide event filter needs no list: every widget receives events, and the first
        one it gets is discovery enough. **The bound is different rather than absent** — a widget
        that receives no event at all is never seen — and it is a narrower miss than a 250 ms
        window, because a widget that was never polished, shown or laid out is not one a user
        interacted with.
        """
        if isinstance(watched, QWidget):
            state = watched.__dict__.get(WATCHED)
            if state is None:
                self.watch(watched)
            else:
                # **Refreshed, because ownership moves** (`T289-R6`). A widget parented after it was
                # first seen stops being a candidate, and one released from its parent becomes one.
                state["candidate"] = self.is_a_candidate(watched)
        return False

    def note_the_settings_screen(self, widget: QWidget) -> None:
        """The first route milestone, seen through the same discovery the widgets use."""
        if not self.settings_opened and type(widget).__name__ == "SettingsDialog":
            self.settings_opened = True
            self.say("route: the Settings screen opened")

    def finish_the_update(self, outcome: str) -> None:
        """The update actually completed — the service said so, on the GUI thread (`T289-R7`)."""
        if self.update_finished:
            return
        self.update_finished = True
        self.say(f"route: yt-dlp update finished — {outcome}")

    def the_route_ran(self) -> bool:
        """Whether this session actually drove Settings → yt-dlp → Update, start to finish."""
        return self.settings_opened and self.update_started and self.update_finished

    def summary(self) -> str:
        minutes = (datetime.now(UTC) - self.started).total_seconds() / 60
        return (
            f"watched {self.widgets_seen} widgets over {minutes:.1f} minutes; "
            f"collections by thread: {self.collections or 'none observed'}, "
            f"{self.collected_objects} objects freed; widget destructions: "
            f"{self.off_gui_destructions} off the GUI thread "
            f"({self.off_gui_in_a_collection} inside a collection), {self.gui_destructions} on it "
            f"({self.gui_destructions_in_a_collection} of those inside a collection); "
            f"candidates collected on the GUI thread: {len(self.candidates_collected)}; "
            f"route: settings={self.settings_opened} update_started={self.update_started} "
            f"update_finished={self.update_finished}"
        )

    def verdict(self) -> str:
        """What this session may be said to have shown (`T289-R7`).

        **A null result is only about the route that was driven**, and the first version called one
        clean without knowing whether Settings had ever been opened. A session that never ran the
        update proves nothing about the update.
        """
        if self.off_gui_in_a_collection:
            return (
                f"T-289 OBSERVED — {self.off_gui_in_a_collection} widget(s) destroyed off the GUI "
                "thread *inside a cyclic collection*, each with its thread and stack above. That "
                "is this task's precondition in the product."
            )
        if self.off_gui_destructions:
            return (
                f"OFF-GUI DESTRUCTION, BUT NOT T-289 — {self.off_gui_destructions} widget(s) were "
                "destroyed off the GUI thread with **no collection running on that thread**. Qt "
                "still forbids it and it is worth an entry of its own, but this task is about the "
                "*collector* doing it, and the collector did not (`T289-R6`)."
            )
        if not self.the_route_ran():
            return (
                "NOT A RESULT. The route was not driven start to finish — see the route flags in "
                "the summary — so this session says nothing about it. Run it again and complete "
                "Settings -> yt-dlp -> Update."
            )
        if not self.gui_destructions_in_a_collection:
            return (
                "INCONCLUSIVE. The route ran, but the collector was never observed destroying a "
                "widget on any thread, so there was nothing for it to get wrong. A clean answer "
                "needs the collector to have handled widgets at all."
            )
        if self.candidates_collected:
            named = ", ".join(sorted(set(self.candidates_collected)))
            return (
                "NOTHING OFF THE GUI THREAD, and the near misses are named. The collector "
                f"destroyed {len(self.candidates_collected)} Python-typed widget(s) on the GUI "
                f"thread during this route: {named}. **Those are the trees that would have been "
                "destroyed in place had the collector fired on a pool thread instead** — which is "
                "what criterion 2 needs identified. One clean session does not close it; the "
                "candidate list is what a correction can be aimed at."
            )
        return (
            "NOTHING OFF THE GUI THREAD, over a route that ran start to finish while the collector "
            f"destroyed {self.gui_destructions_in_a_collection} widget(s) on the GUI thread — none "
            "of them a Python-typed one. That is evidence about this route in this session; a tree "
            "destroyed between events is not seen, and the crash is intermittent."
        )


def arm(watch: Watch) -> None:
    """Install the event filter and the route probes. **This is the wiring the self-test runs.**

    `T289-R7`: the first self-test built a `Watch` and called `watch.watch(...)` by hand, so it
    proved the *handler* and skipped everything that finds a widget or hooks a collection. It could
    have passed with discovery broken.
    """
    application = QApplication.instance()
    assert isinstance(application, QApplication), "arm() runs after the application exists"
    application.installEventFilter(watch)
    gc.callbacks.append(watch.note_a_collection)
    watch_the_update_route(watch)

    # **A heartbeat, so the interpreter gets the floor.** Python runs a pending signal handler only
    # between bytecodes, and Qt's `exec()` is C: without this, `finish_on_a_signal`'s handler never
    # runs and installing it turns `SIGTERM` from *kills the session* into *does nothing*. The
    # callback is deliberately empty; being called is the entire job.
    heartbeat = QTimer(watch)
    heartbeat.setInterval(200)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()


def watch_the_update_route(watch: Watch) -> None:
    """Record when the yt-dlp update starts and finishes, by wrapping the service in this process.

    **`T289-R7`, and the reason a null result needs it.** *No off-GUI destruction* is a statement
    about a route, and the first version made it without knowing whether the route had been driven:
    a session where nobody opened Settings reported clean for Settings.

    **Patched here, not in `src/`.** The wrapper owns this process; the application on disk is
    unchanged, and a normal launch has none of this. `install_latest_version` is the update the
    crash came from — `T-212`'s checklist run pressed exactly it.
    """
    from tracks_and_trails.downloader.ytdlp_service import YtdlpService

    original = YtdlpService.install_latest_version

    def install_latest_version(self: YtdlpService) -> None:
        watch.update_started = True
        watch.say(f"route: yt-dlp update started on {threading.current_thread().name!r}")

        # **The call returning is not the update finishing** (`T289-R7`). `install_latest_version`
        # hands its work to a `QThreadPool` and returns at once, so the first version marked the
        # route complete before the install had begun — and a session could then be called clean
        # for a route whose pool work never ran. The service says when it is really done, through
        # the same signals the screen listens to: `reported` after the child says which yt-dlp now
        # imports, or `failed`. Connected once, on first use, because the wrapper has no other
        # handle on the instance.
        if not getattr(self, "_t289_connected", False):
            self._t289_connected = True  # type: ignore[attr-defined]
            self.reported.connect(
                lambda resolution: watch.finish_the_update(f"reported {resolution}")
            )
            self.failed.connect(lambda why: watch.finish_the_update(f"failed: {why}"))

        original(self)
        watch.say("route: the update call returned; its work is on the pool")

    YtdlpService.install_latest_version = install_latest_version  # type: ignore[method-assign]


def self_test() -> int:
    """Prove the watch reports an off-GUI destruction, before anyone trusts a clean session.

    **`ai/TESTING.md` §10: an instrument carries its own positive control**, and this family has
    produced three that reported confidently about nothing. A session that ends *"nothing off the
    GUI thread"* is worth exactly as much as this check passing beforehand, so the maintainer can
    run it in a second, offscreen, and so can a reviewer.

    The subject is the arm this project measured on 2026-08-30: a **Python subclass**, unparented so
    Python owns the C++ object, reachable only through a cycle, collected on a `QThreadPool` thread.
    That combination destroys in place — a plain `QWidget` would be marshalled to the GUI thread and
    prove nothing.
    """
    from io import StringIO

    from PySide6.QtCore import QCoreApplication, QRunnable, QThreadPool

    class Derived(QWidget):
        """Defined in Python, which is what makes the destruction happen in place."""

    class Cycle:
        def __init__(self, widget: QWidget) -> None:
            self.widget = widget
            self.myself = self

    class CollectOnThePool(QRunnable):
        def run(self) -> None:
            gc.collect()

    application = QApplication.instance() or QApplication([sys.argv[0]])
    assert isinstance(application, QApplication)
    transcript = StringIO()
    watch = Watch(transcript, threading.current_thread().name)

    # **Through `arm()`, which is the whole point** (`T289-R7`). The first version called
    # `watch.watch(...)` by hand and so proved the handler while skipping discovery and the `gc`
    # callback entirely — it would have passed with the event filter never installed.
    arm(watch)

    # **Named, so the assertions can be about *this* widget** (`T289-R7`). The first version
    # asserted only that *something* was destroyed off the GUI thread, which the subject's handler
    # being disconnected would not have disturbed — any other off-thread destruction satisfied it.
    subject = Derived()
    subject.setObjectName("t289-self-test-subject")
    expected = "Derived(t289-self-test-subject)"
    subject.show()  # any event will do; this is what the filter discovers it by
    QCoreApplication.processEvents()
    if WATCHED not in subject.__dict__:
        print("SELF-TEST FAILED: the event filter did not discover a shown widget.")
        return 2
    subject.hide()
    QCoreApplication.processEvents()

    Cycle(subject)
    del subject
    gc.disable()
    try:
        task = CollectOnThePool()
        task.setAutoDelete(False)
        pool = QThreadPool()
        pool.setMaxThreadCount(1)
        pool.start(task)
        pool.waitForDone(5000)
        for _ in range(50):
            QCoreApplication.processEvents()
    finally:
        gc.enable()

    # **The other direction** (`T289-R6`): a candidate collected on the *GUI* thread must be named,
    # not merely counted. That is the near miss a real session is most likely to produce, and the
    # reviewed version reported it as an empty transcript and a clean verdict.
    near_miss = Derived()
    near_miss.setObjectName("t289-self-test-near-miss")
    near_miss.show()
    QCoreApplication.processEvents()
    near_miss.hide()
    QCoreApplication.processEvents()
    Cycle(near_miss)
    del near_miss
    gc.collect()  # on this thread, which is the GUI thread
    QCoreApplication.processEvents()

    # **The third direction** (`T289-R6`): a Python subclass **with a Qt parent** is owned by C++,
    # so releasing its wrapper destroys nothing and it is not this task's tree. The reviewed version
    # named one, because it tested the type and not the ownership.
    owner = Derived()
    owner.setObjectName("t289-self-test-owner")
    child = Derived(owner)
    child.setObjectName("t289-self-test-child")
    owner.show()
    QCoreApplication.processEvents()
    owner.hide()
    QCoreApplication.processEvents()
    Cycle(owner)
    del owner, child
    gc.collect()
    QCoreApplication.processEvents()

    if watch.note_a_collection in gc.callbacks:
        gc.callbacks.remove(watch.note_a_collection)
    application.removeEventFilter(watch)

    print(transcript.getvalue(), end="")
    if not watch.collections:
        print("SELF-TEST FAILED: the gc callback recorded no collection, so nothing was tracked.")
        return 2
    if expected not in watch.off_gui_tags:
        print(
            f"SELF-TEST FAILED: {expected} was not reported destroyed off the GUI thread. "
            f"Reported instead: {watch.off_gui_tags or 'nothing'}. A pass on somebody else's "
            "destruction would say nothing about this widget's handler."
        )
        return 2
    if "Derived(t289-self-test-near-miss)" not in watch.candidates_collected:
        print(
            "SELF-TEST FAILED: a Python-typed widget collected on the GUI thread was not named. "
            f"Named instead: {watch.candidates_collected or 'nothing'}. A real session's most "
            "likely finding would go unrecorded."
        )
        return 2
    if "Derived(t289-self-test-child)" in watch.candidates_collected:
        print(
            "SELF-TEST FAILED: a Python subclass owned by its Qt parent was named as a candidate. "
            "Releasing its wrapper destroys nothing, so naming it would send a correction after "
            "the wrong tree."
        )
        return 2
    if "Derived(t289-self-test-owner)" not in watch.candidates_collected:
        print(
            "SELF-TEST FAILED: the parentless owner was not named, so the ownership test is now "
            f"rejecting real candidates. Named: {watch.candidates_collected}."
        )
        return 2
    print(
        "SELF-TEST PASSED: the filter discovered the widgets, the callback saw the collections, "
        "the off-GUI destruction was reported by name, the GUI-thread candidate was named, and a "
        "Qt-owned child was not."
    )
    return 0


def identity() -> list[str]:
    """What produced this report, so a reader a month from now can place it (`T289-R7`).

    **A measurement that does not say which tree, which machine and which Qt it came from is not
    evidence a month later** — `T-148`'s rule, and `tools/soak_a_test.py` carries the same one. A
    dirty tree is recorded as dirty rather than rounded to the commit it is nearest.
    """
    import platform
    import shutil
    import subprocess

    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import qVersion

    git_binary = shutil.which("git")

    def git(*arguments: str) -> str:
        if git_binary is None:
            return "unknown"
        try:
            # S603/S607 answered rather than suppressed blindly: the executable is resolved by
            # `which` above and every argument is a literal from this function.
            done = subprocess.run(  # noqa: S603
                [git_binary, *arguments],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except OSError:  # pragma: no cover - git absent is not this tool's problem
            return "unknown"
        return done.stdout.strip() or "unknown"

    head = git("rev-parse", "--short", "HEAD")
    dirty = " (tree dirty)" if git("status", "--porcelain") not in {"", "unknown"} else ""
    return [
        f"tree: {head}{dirty}",
        f"host: {platform.node()}  {platform.platform()}",
        f"python: {platform.python_version()}  PySide6 {pyside_version}  Qt {qVersion()}",
        f"QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM') or '(unset — Qt chooses)'}",
    ]


def prove_the_instrument_first(watch: Watch) -> bool:
    """Run `--self-test` in a subprocess and put its result in the report (`T289-R7`).

    **A session's null result is worth exactly what the positive control is worth**, and asking the
    maintainer to run a second command leaves the proof somewhere else — or not taken at all. This
    puts it in the same file, above the session it vouches for.

    **A subprocess, because the control needs its own `QApplication`** and this process is about to
    hand that job to `app.run`. It costs about a second.
    """
    import subprocess

    watch.say("running the positive control before the session…")
    # S603 answered: the interpreter is this process's own and the script is this file.
    done = subprocess.run(  # noqa: S603
        [sys.executable, str(Path(__file__).resolve()), "--self-test"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    for line in done.stdout.strip().splitlines()[-3:]:
        watch.say(f"  control | {line}")
    if done.returncode == 0:
        watch.say("positive control PASSED — this instrument reports what it is built to report")
        return True
    watch.say(
        "positive control FAILED — nothing this session reports may be believed, and a clean "
        "result would be meaningless. Not starting the application."
    )
    return False


def finish_on_a_signal(watch: Watch) -> None:
    """Write the summary and verdict if the process is killed rather than closed.

    **Because a report that stops mid-session looks like a clean one** (`T289-R7`'s shape, found
    while checking it): `SIGTERM` skips the `finally`, so a killed run left a header and nothing
    else, and a reader with the file in front of them has no way to know the session was cut short.
    The header now says a report without a `VERDICT` line is incomplete, and this makes sure one is
    written whenever the process is given the chance.

    An abort — which is the outcome this whole instrument exists for — cannot be caught, and that is
    what the flush-per-line design is for instead.

    **A Python signal handler does not run while Qt owns the loop**, which the first version of this
    got wrong in the worst direction: installing the handler made `SIGTERM` a no-op and the session
    unkillable except with `SIGKILL`, where before it had simply died. Python runs pending handlers
    only between bytecodes, and `exec()` is C. `arm()` starts a heartbeat timer for exactly this —
    it does nothing except give the interpreter the floor a few times a second.

    **The handler quits the application rather than raising.** An exception raised inside a signal
    handler under `exec()` has nowhere useful to go; `quit()` unwinds the loop and the `finally` in
    `main` does the rest.
    """

    def finish(signum: int, _frame: object) -> None:
        watch.say(f"session ended by signal {signum}")
        application = QApplication.instance()
        if application is not None:
            application.quit()

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, finish)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the application under T-289's watch.")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="prove the watch sees an off-GUI destruction, then exit without starting the app",
    )
    parser.add_argument(
        "--report",
        default="reports/t289-session.txt",
        help="where to write the observations (created, appended as events happen)",
    )
    arguments, rest = parser.parse_known_args()

    if arguments.self_test:
        return self_test()

    destination = Path(arguments.report)
    destination.parent.mkdir(parents=True, exist_ok=True)

    from tracks_and_trails.app import run

    with destination.open("w", encoding="utf-8") as report:
        watch = Watch(report, threading.current_thread().name)
        watch.say(f"T-289 session watch — GUI thread is {watch.gui_thread!r}")
        watch.say("route to drive: Settings -> yt-dlp -> Update")
        for line in identity():
            watch.say(line)
        watch.say(
            "a report with no VERDICT line at the end is an incomplete session and says nothing"
        )
        if not prove_the_instrument_first(watch):
            watch.say("VERDICT: NOT A RESULT — the positive control failed; no session was run.")
            print("positive control failed; see the report", file=sys.stderr)
            return 2
        finish_on_a_signal(watch)

        # **Armed once the application exists, on the GUI thread.** `app.run` constructs the
        # `QApplication` itself, so there is nothing to install a filter on until it has; a
        # zero-delay timer posted before `exec()` runs as soon as the loop starts.
        QTimer.singleShot(0, lambda: arm(watch))

        try:
            code = run([sys.argv[0], *rest])
        finally:
            if watch.note_a_collection in gc.callbacks:
                gc.callbacks.remove(watch.note_a_collection)
            watch.say(watch.summary())
            watch.say(f"VERDICT: {watch.verdict()}")
        print(
            f"\nT-289 watch: {watch.summary()}\n\n{watch.verdict()}\n\nreport: {destination}",
            file=sys.stderr,
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
