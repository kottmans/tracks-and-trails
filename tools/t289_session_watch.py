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

A `QTimer` scans `QApplication.allWidgets()` every 250 ms and connects `destroyed` on widgets it has
not seen. A few hundred widgets and one connection each: unmeasurable against a UI. **A widget
created and destroyed entirely between two scans is missed**, which is the honest bound — the tree
this is hunting was on screen.

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
import sys
import threading
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

#: The attribute marking a widget this watch has already connected to.
WATCHED = "_t289_watched"

#: How often the scan looks for widgets it has not connected to yet.
SCAN_MS = 250


class Watch:
    """One session's observations, written as they happen."""

    def __init__(self, report: TextIO, gui_thread: str) -> None:
        self.report = report
        self.gui_thread = gui_thread
        self.widgets_seen = 0
        self.off_gui_destructions = 0
        self.collections: dict[str, int] = {}
        self.started = datetime.now(UTC)

    def say(self, line: str) -> None:
        """Write and flush. **Flushed because the process may abort**, which is the subject."""
        stamp = datetime.now(UTC).strftime("%H:%M:%S.%f")[:-3]
        self.report.write(f"{stamp}  {line}\n")
        self.report.flush()

    def note_a_collection(self, phase: str, info: dict[str, int]) -> None:
        if phase != "start":
            return
        thread = threading.current_thread().name
        self.collections[thread] = self.collections.get(thread, 0) + 1
        if thread != self.gui_thread:
            # Worth a line of its own: a collection on a pool thread is the loaded gun, whether or
            # not it finds a widget this time.
            self.say(f"gc collection started on {thread!r} (generation {info.get('generation')})")

    def watch(self, widget: QWidget) -> None:
        tag = f"{type(widget).__name__}({widget.objectName() or 'unnamed'})"
        module = type(widget).__module__

        def destroyed(*_args: object) -> None:
            thread = threading.current_thread().name
            if thread == self.gui_thread:
                return
            self.off_gui_destructions += 1
            self.say(f"!! {tag} from {module} destroyed on {thread!r} — NOT the GUI thread")
            self.say("   Python stack of that thread:")
            for frame in traceback.extract_stack()[:-1][-12:]:
                self.say(f"     {frame.filename}:{frame.lineno} in {frame.name}")

        widget.destroyed.connect(destroyed, Qt.ConnectionType.DirectConnection)
        widget.__dict__[WATCHED] = True
        self.widgets_seen += 1

    def scan(self) -> None:
        for widget in QApplication.allWidgets():
            if WATCHED not in widget.__dict__:
                self.watch(widget)

    def summary(self) -> str:
        minutes = (datetime.now(UTC) - self.started).total_seconds() / 60
        return (
            f"watched {self.widgets_seen} widgets over {minutes:.1f} minutes; "
            f"collections by thread: {self.collections or 'none observed'}; "
            f"off-GUI destructions: {self.off_gui_destructions}"
        )


def arm(watch: Watch) -> QTimer:
    """Install the scan on the GUI thread and return the timer that owns it."""
    timer = QTimer()
    timer.setInterval(SCAN_MS)
    timer.timeout.connect(watch.scan)
    timer.start()
    watch.scan()
    return timer


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

    subject = Derived()
    watch.watch(subject)
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

    print(transcript.getvalue(), end="")
    if watch.off_gui_destructions:
        print("SELF-TEST PASSED: the watch reported a widget destroyed off the GUI thread.")
        return 0
    print(
        "SELF-TEST FAILED: a widget built to be destroyed on a pool thread was not reported. "
        "A clean session from this instrument would mean nothing — do not run the real route "
        "until this passes."
    )
    return 2


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
        gc.callbacks.append(watch.note_a_collection)

        # **Armed once the application exists, from the GUI thread.** `app.run` constructs the
        # `QApplication` itself, so there is nothing to attach to until it has; a zero-delay timer
        # posted before `exec()` runs as soon as the loop starts, which is the first moment the
        # widgets exist and the first moment a `QTimer` may be created.
        holder: list[QObject] = []
        QTimer.singleShot(0, lambda: holder.append(arm(watch)))

        try:
            code = run([sys.argv[0], *rest])
        finally:
            gc.callbacks.remove(watch.note_a_collection)
            watch.say(watch.summary())
            if watch.off_gui_destructions == 0:
                watch.say(
                    "NOTHING OFF THE GUI THREAD. That is a result about this session and this "
                    "route, not about the application: a tree destroyed between two scans is not "
                    "seen, and the crash is intermittent."
                )
        print(f"\nT-289 watch: {watch.summary()}\nreport: {destination}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
