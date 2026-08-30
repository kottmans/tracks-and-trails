"""Can collecting a Python wrapper destroy a live Qt widget here? (`T-238` criterion 4)

**The question, and why it is this one.** The retained stack shows `~QAbstractItemView` under
`Shiboken::BindingManager::runDeletionInMainThread`, which Shiboken only queues when the wrapper's
last Python reference was dropped somewhere else. The sibling `t238_widget_thread_probe` then
established that **no thread has to hold a widget** for that: Python's cyclic collector runs on
whichever thread crosses the allocation threshold, so a widget freed by `gc` is decref'd there.
Ownership was the wrong question. This is the right one.

## The distinction this probe exists to make, learned by getting it wrong

**`T238-R7`.** The 2026-08-30 version reported *"17 widgets freed by the cyclic collector"* over an
`OptionsDialog` tree and called it the crash's precondition. Every one of those seventeen was an
**already-dead wrapper**: the probe had called `deleteLater()` and flushed `DeferredDelete` first,
so Qt destroyed the C++ widgets and the collector then parked the Python halves. Clearing a dead
wrapper runs no `QWidget` destructor and reaches no cross-thread deletion path. The number was real
and the claim on top of it was not.

So the predicate is not *"the collector freed it"*. It is:

| Parked wrapper | `shiboken6.isValid` | What collecting it does |
|---|---|---|
| **Live** | `True` | **Destroys the C++ widget, on the collecting thread.** The precondition |
| Dead | `False` | Python bookkeeping. Qt already destroyed it, on whatever thread did that |

Validity is read **before `gc.garbage` is cleared**, while the parked wrappers are still alive, and
`QObject.destroyed` is connected to every censused widget so a destruction that happens *inside* the
instrumented collection is **observed with its thread** rather than inferred from a count.

## Two arms, because ownership is the variable

Neither arm is the default reading of the other, and running only one is how the first version drew
a conclusion the run could not support:

- **`--leave-the-constructed-screens-to-the-collector`.** `tests/ui/surfaces.py`'s five screens are
  built parentless, so Python owns their C++ objects. Without this flag they are closed and
  `deleteLater`'d exactly as `every_surface` owns them, and Qt destroys them before the collector
  ever looks — which is what produced `T238-R7`. With it, they are simply dropped, and whether the
  collector then destroys live widgets is the thing measured.
- **`--owner-deletes-the-window`.** `T-273` ruled that `shutdown.begin()` does **not** own the
  window's lifetime: the `composed` fixture does, and it performs `window.deleteLater()` plus a
  **receiver-scoped** `DeferredDelete` flush. Without this flag the window tree survives teardown,
  and that is `T-273`'s documented baseline for product shutdown alone rather than a new finding
  (`T238-R8`). With it, the owner's step is applied and the tree goes.

## What "freed by the collector" does and does not say about cycles

`DEBUG_SAVEALL` parks everything a collection frees. An object can be there because it is in a cycle
**or** because its only referents were — so *"these are in cycles"* is stronger than the predicate
supports (`T238-R7`), and this file does not say it.

## How identity survives a freed wrapper

Each widget gets a unique tag in its instance `__dict__` at census time, and the census holds
**weak** references and strings — never a widget. Two reasons, and the second is the one that bit:

- A parked wrapper's tag is still readable, out of `obj.__dict__` directly rather than with
  `getattr`, because the C++ half may be gone and a descriptor could reach for it.
- A probe that holds the widgets it is deciding about **is** the retention root, and its own
  containers turn up in `gc.get_referrers`. That contaminated the withdrawn 2026-08-20 attribution.

## The self-test runs first, in three directions

Two earlier instruments in this family each reported confidently about nothing, **one with a
clean-looking zero**, and this one shipped a false positive of its own:

- **Positive**: a widget reachable only from a reference cycle is parked, by its own tag, and it is
  **valid** at that moment — which is also the control for the distinction above.
- **Negative**: a widget freed by refcount is not named.
- **Residue**: a parentless `QListView` outliving the self-test makes the probe **refuse**, because
  the positive control is built to be collected and would otherwise be censused as the
  application's. That is not hypothetical: it is what the first version reported.

**Usage** — a script, not a plugin, run from the repository root so `tests/ui/surfaces.py` imports:

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t238_widget_cycle_probe.py [flags]

## What this still does not establish

- **The five screens are constructed, not opened through their routes** — `tests/ui/surfaces.py`
  records the trade and what it costs a lifetime measurement.
- **One offscreen process is not a real session.** Criterion 4's other named step — the application
  on a display with the thumbnail pool working — is not this.
- **A destruction observed here is on the main thread.** The crash needs one on a pool thread; what
  this can show is that the *route* exists, not that the product takes it under load.
"""

from __future__ import annotations

import argparse
import gc
import sys
import threading
import weakref
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QListView, QWidget

# **Run as a script, so `sys.path[0]` is `tools/`** and the repository root is not on the path —
# which is what `tests.ui.surfaces` needs. Added here rather than asking the caller for a
# `PYTHONPATH=.` prefix: a documented command that fails when it is copied is `T268-R3`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TAG: str = "_t238_tag"


@dataclass
class Destructions:
    """Every `QObject::destroyed` this run saw, with the thread and the phase it arrived in.

    The handler closes over a **tag and this recorder** — never a widget — so connecting it cannot
    become the reference that keeps the subject alive.
    """

    phase: str = "setup"
    seen: list[tuple[str, str, str]] = field(default_factory=list)

    def watch(self, widget: QWidget, tag: str) -> None:
        recorder = self

        def note(*_args: object) -> None:
            recorder.seen.append((tag, threading.current_thread().name, recorder.phase))

        widget.destroyed.connect(note)

    def during(self, phase: str) -> list[tuple[str, str, str]]:
        return [entry for entry in self.seen if entry[2] == phase]


@dataclass
class Census:
    """Who was alive, by identity, holding nothing that would keep them that way."""

    alive: dict[str, weakref.ref[QWidget]] = field(default_factory=dict)
    described: dict[str, str] = field(default_factory=dict)
    #: `"route"` for a widget the application's own routes opened, `"constructed"` for one of the
    #: five screens `tests/ui/surfaces.py` builds. **The two do not support the same claim**: a
    #: constructed screen is parentless because the helper made it so, and Python therefore owns a
    #: C++ object the product would have parented.
    origin: dict[str, str] = field(default_factory=dict)

    def take(self, widgets: list[QWidget], origin: str, watcher: Destructions) -> None:
        for widget in widgets:
            if TAG in widget.__dict__:
                continue  # censused in an earlier pass; its origin is the earlier one
            tag = uuid4().hex
            widget.__dict__[TAG] = tag
            name = widget.objectName()
            # **Read here, while the C++ half is certainly alive.** A parked wrapper may have lost
            # it, and the class name alone does not say *which* widget — which is the difference
            # between a product finding and a probe artefact.
            parent = widget.parentWidget()
            within = f" in {type(parent).__name__}" if parent is not None else " (parentless)"
            self.described[tag] = f"{type(widget).__name__}{f' ({name})' if name else ''}{within}"
            self.origin[tag] = origin
            self.alive[tag] = weakref.ref(widget)
            watcher.watch(widget, tag)

    def __len__(self) -> int:
        return len(self.described)


@dataclass(frozen=True)
class Parked:
    """One wrapper the collector freed, and whether its Qt widget was still alive at that moment."""

    tag: str
    class_name: str
    cpp_was_alive: bool


def _tag_of(obj: object) -> str | None:
    """The tag, read without touching anything the C++ half owns."""
    instance = getattr(obj, "__dict__", None)
    return instance.get(TAG) if isinstance(instance, dict) else None


def _collect_and_read_the_garbage() -> tuple[list[Parked], int]:
    """Collect with `DEBUG_SAVEALL` armed and classify every parked widget wrapper.

    **`shiboken6.isValid` is read here, before `gc.garbage` is cleared**, which is the whole
    correction `T238-R7` required: afterwards the wrapper is gone and the question cannot be asked.
    A parked wrapper whose C++ widget is still alive is one whose collection destroys a widget; a
    parked wrapper whose C++ widget is already gone is Python catching up with Qt.

    The total is returned because *no widget was collected* and *nothing was collected* are
    different findings, and only the second says the collector had nothing to do.
    """
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        gc.collect()
        parked = [
            Parked(
                tag=_tag_of(obj) or f"untagged-{id(obj):x}",
                class_name=type(obj).__name__,
                cpp_was_alive=shiboken6.isValid(obj),
            )
            for obj in gc.garbage
            if isinstance(obj, QWidget)
        ]
        total = len(gc.garbage)
    finally:
        gc.garbage.clear()
        gc.set_debug(0)
    return parked, total


def _self_test() -> tuple[bool, bool, list[str]]:
    """Three checks, by tag, before anything below is believed.

    Positive: a widget reachable **only** from a reference cycle. Nothing holds it directly, so no
    refcount reaching zero can free it and the collector must be what does — **and it must be valid
    when parked**, which makes it the control for `T238-R7`'s distinction as well.

    Negative: a widget held by an ordinary local reference that is then dropped. Its refcount
    reaches zero at the `del`, the collector never touches it, and a probe that names it anyway is
    reporting the wrong thing about everything underneath.
    """
    notes: list[str] = []

    class _Node:
        """Two of these referring to each other is the cycle; the widget hangs off one."""

    positive_tag = uuid4().hex
    first, second = _Node(), _Node()
    first.other, second.other = second, first  # type: ignore[attr-defined]
    view = QListView()
    view.__dict__[TAG] = positive_tag
    first.view = view  # type: ignore[attr-defined]
    del view, first, second

    parked, _total = _collect_and_read_the_garbage()
    positive = next((entry for entry in parked if entry.tag == positive_tag), None)
    saw_the_positive = positive is not None and positive.cpp_was_alive
    notes.append(
        "positive: a widget reachable only from a cycle was "
        + (
            "parked by its own tag, with its Qt widget still alive"
            if saw_the_positive
            else f"MISSED or already dead ({positive}) — this probe cannot see its own subject"
        )
    )

    negative_tag = uuid4().hex
    dropped = QListView()
    dropped.__dict__[TAG] = negative_tag
    del dropped

    parked, _total = _collect_and_read_the_garbage()
    named_the_negative = any(entry.tag == negative_tag for entry in parked)
    notes.append(
        "negative: a widget freed by refcount was "
        + ("correctly not named" if not named_the_negative else "NAMED — this probe over-reports")
    )
    return saw_the_positive, not named_the_negative, notes


def _the_self_tests_widgets_are_gone() -> bool:
    """No parentless `QListView` of the self-test's may survive into the census.

    The positive control is **built to be freed by the collector**, which is the finding the
    measurement reports. One that outlived the self-test would be censused with a fresh tag and
    counted as the application's — a probe manufacturing its own headline, which is exactly what
    the first version of this file did.
    """
    gc.collect()
    return not any(
        type(widget).__name__ == "QListView" and widget.parentWidget() is None
        for widget in QApplication.allWidgets()
    )


def _who_still_holds(reference: weakref.ref[QWidget]) -> list[str]:
    """A sketch of what refers to a widget that outlived the release. Indicative, not a proof.

    Referrer *kinds* only, and this probe's own frame is dropped by name: the strong reference the
    lookup needs exists only inside this function, and reporting it would repeat the contamination
    that got the 2026-08-20 attribution withdrawn.
    """
    widget = reference()
    if widget is None:
        return []
    kinds: Counter[str] = Counter()
    for referrer in gc.get_referrers(widget):
        if referrer is not None and getattr(referrer, "f_code", None) is not None:
            name = getattr(referrer.f_code, "co_name", "?")
            if name == "_who_still_holds":
                continue
            kinds[f"frame:{name}"] += 1
        else:
            kinds[type(referrer).__name__] += 1
    del widget
    return [f"{count}x {kind}" for kind, count in kinds.most_common(6)]


def _build_drive_and_tear_down(
    census: Census,
    watcher: Destructions,
    *,
    owner_deletes_the_window: bool,
    leave_the_screens_to_the_collector: bool,
) -> None:
    """Everything strong lives in this frame, and this frame returns before the collector is asked.

    That is the release the 2026-08-20 run had no way to perform: it read the collector while the
    composition was still on the stack, so a retained graph was never classified.
    """
    from tests.ui.surfaces import screens_below_the_add_dialog

    from tracks_and_trails import app as application
    from tracks_and_trails.downloader.ytdlp_service import YtdlpService

    class _QuietYtdlp(YtdlpService):
        """Answers nothing and spawns nothing — `open_settings()` calls `refresh()` (`T200-R6`)."""

        def __init__(self) -> None:
            super().__init__(directory=Path("/nonexistent-in-probes"))

        def refresh(self) -> None: ...

    app = QApplication.instance()
    assert isinstance(app, QApplication), "main() constructs the QApplication before it gets here"

    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        composition = application.compose(
            app,
            database=tmp / "queue.sqlite3",
            output_directory=tmp / "downloads",
            geometry_file=tmp / "window.toml",
            settings_file=tmp / "settings.toml",
            cache_directory=tmp / "cache",
            entry_point=lambda *_a, **_k: None,
            ytdlp_service=_QuietYtdlp(),
        )
        window = composition.window
        window.show()
        app.processEvents()

        window.open_add_dialog()
        app.processEvents()
        settings = window.open_settings()
        assert settings is not None, (
            "composition wired no settings writers, so the Settings screen never opened and this "
            "measurement would silently cover one surface fewer"
        )
        app.processEvents()
        window.show_about()
        app.processEvents()

        # **Censused in two passes, because the two groups do not answer the same question.**
        # Everything alive now was opened by the application's own routes; the five screens built
        # below are the helper's, parentless, and are tagged separately.
        census.take(QApplication.allWidgets(), "route", watcher)

        built = screens_below_the_add_dialog()
        for _label, widget in built:
            widget.show()
        app.processEvents()
        census.take(QApplication.allWidgets(), "constructed", watcher)

        # **Automatic collection is off from here to the end of the measurement.** A censused
        # widget freed by a *generational* collection during teardown would be gone before
        # `DEBUG_SAVEALL` was armed and would be filed under *freed by refcount* — misclassifying
        # the exact event being measured. With the collector stopped, every collection in this
        # window is one this probe performed with the verdict readable.
        gc.disable()
        watcher.phase = "teardown"

        if leave_the_screens_to_the_collector:
            # **Dropped, not deleted.** Python owns these C++ objects, so if the collector is what
            # frees the wrappers it is also what destroys the widgets — the precondition, live.
            built.clear()
        else:
            # The fixture's own ownership: `every_surface` closes and `deleteLater`s each one,
            # because a parentless widget left to the collector has its destructor run wherever
            # the collector next fires. **This arm is what produced `T238-R7`**: Qt destroys them
            # here, and the collector later parks wrappers that are already dead.
            for _label, widget in built:
                widget.close()
                widget.deleteLater()
            built.clear()
            # `processEvents()` does not run a `deleteLater()`; Qt delivers `DeferredDelete` only
            # from an event loop (`tests/qt_lifecycle.settle_deferred_deletions`).
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        window.close()
        composition.shutdown.begin()
        for _ in range(4000):
            if composition.shutdown.finished:
                break
            app.processEvents()
        assert composition.shutdown.finished, "composition never finished shutting down"
        app.processEvents()

        if owner_deletes_the_window:
            # **`T-273`'s owner step, applied deliberately.** `shutdown.begin()` stops what
            # composition owns and does not own the window's lifetime; the `composed` fixture does,
            # and this is its exact sequence — including the **receiver-scoped** flush `T273-R2`
            # required, rather than the process-wide one.
            window.deleteLater()
            app.processEvents()
            QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
            app.processEvents()

        del window, settings, composition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--owner-deletes-the-window",
        action="store_true",
        help="apply T-273's owner deletion after shutdown, as the composed fixture does",
    )
    parser.add_argument(
        "--leave-the-constructed-screens-to-the-collector",
        action="store_true",
        help="drop the five parentless screens instead of deleteLater-ing them, so Python still "
        "owns live C++ widgets when the collector runs",
    )
    arguments = parser.parse_args()

    # **Before the self-test, because the self-test builds widgets.** Qt aborts the process on a
    # `QWidget` constructed with no `QApplication`.
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)

    positive, negative, notes = _self_test()
    print("T-238 criterion 4 — can collecting a wrapper destroy a live Qt widget here?\n")
    screens_arm = (
        "dropped for the collector"
        if arguments.leave_the_constructed_screens_to_the_collector
        else "closed and deleteLater-ed (fixture ownership)"
    )
    window_arm = (
        "released by its owner (T-273's step)"
        if arguments.owner_deletes_the_window
        else "left to product shutdown alone (T-273's baseline)"
    )
    print(f"  arm: constructed screens are {screens_arm}")
    print(f"       the window is {window_arm}\n")
    for note in notes:
        print(f"  self-test {note}")
    if not (positive and negative):
        print("\nSELF-TEST FAILED. The measurement below is not evidence of anything.")
        return 2
    if not _the_self_tests_widgets_are_gone():
        print(
            "\nSELF-TEST RESIDUE. A parentless QListView survived the self-test, so a widget built "
            "to be collected would be censused as the application's. Refusing."
        )
        return 2

    census = Census()
    watcher = Destructions()
    try:
        _build_drive_and_tear_down(
            census,
            watcher,
            owner_deletes_the_window=arguments.owner_deletes_the_window,
            leave_the_screens_to_the_collector=(
                arguments.leave_the_constructed_screens_to_the_collector
            ),
        )
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        watcher.phase = "collection"
        parked, total_parked = _collect_and_read_the_garbage()
    finally:
        gc.enable()

    censused = {entry.tag: entry for entry in parked if entry.tag in census.described}
    live_when_collected = [entry for entry in censused.values() if entry.cpp_was_alive]
    dead_when_collected = [entry for entry in censused.values() if not entry.cpp_was_alive]
    still_alive = {
        tag: reference
        for tag, reference in census.alive.items()
        if tag not in censused and reference() is not None
    }
    gone_by_refcount = len(census) - len(censused) - len(still_alive)
    routed = sum(1 for origin in census.origin.values() if origin == "route")

    print(f"\n  QWidgets in the census (every surface open):   {len(census)}")
    print(f"    opened by the application's own routes:     {routed}")
    print(f"    constructed by tests/ui/surfaces.py:        {len(census) - routed}")
    print(f"  wrappers the collector parked:                {len(censused)}")
    print(f"    with their Qt widget STILL ALIVE:           {len(live_when_collected)}")
    print(f"    with their Qt widget already destroyed:     {len(dead_when_collected)}")
    print(f"  gone by refcount:                             {gone_by_refcount}")
    print(f"  still alive after the release:                {len(still_alive)}")
    print(f"  objects the collector parked in this window:  {total_parked}")

    if still_alive:
        # **The roots are the finding; their children are arithmetic.** A child is retained because
        # its parent is, so listing every survivor would bury the handful actually held.
        roots = [
            tag
            for tag, reference in still_alive.items()
            if (widget := reference()) is not None
            and shiboken6.isValid(widget)
            and widget.parentWidget() is None
        ]
        print(f"\n  of the {len(still_alive)} survivors, top-level: {len(roots)}")
        for tag in roots[:15]:
            print(f"    {census.described[tag]} [{census.origin.get(tag, '?')}]")
        if roots:
            sketch = _who_still_holds(still_alive[roots[0]])
            print(f"    referrers: {', '.join(sketch) if sketch else 'none readable'}")

    if live_when_collected:
        print("\n  parked while their Qt widget was alive:")
        for name, count in Counter(
            census.described[entry.tag] for entry in live_when_collected
        ).most_common(15):
            print(f"    {count:5d}  {name}")
        # **`DEBUG_SAVEALL` parks; it does not release.** Everything above is *what the collector
        # would free*; no destructor has run. Clearing `gc.garbage` drops one reference each, which
        # is not enough for objects that reference one another — they need another collection.
        #
        # **This is that collection, and it is deliberately the last thing this process does that
        # can fail.** Releasing a live widget runs `~QWidget` here, on this thread, and on these
        # surfaces that has been seen to abort the process: the classification above is printed and
        # flushed first so a crash costs the crash, not the measurement.
        print(
            f"\n  releasing {len(live_when_collected)} live-widget wrappers now — if this is the "
            "last line, the release crashed, and that IS the observation"
        )
        sys.stdout.flush()
        watcher.phase = "release"
        gc.collect()
        destroyed_on_release = watcher.during("release")
        censused_destroyed = [
            entry for entry in destroyed_on_release if entry[0] in census.described
        ]
        threads = Counter(thread for _tag, thread, _phase in censused_destroyed)
        origins = {census.origin.get(entry.tag, "?") for entry in live_when_collected}
        print(f"    destroyed when released, by thread: {dict(threads) or 'none observed'}")
        if censused_destroyed:
            print(
                f"\nPRECONDITION OBSERVED, on {'/'.join(sorted(origins))} surfaces. The collector "
                f"— not a refcount — identified {len(live_when_collected)} wrappers whose Qt "
                f"widgets were still alive, and releasing them ran {len(censused_destroyed)} Qt "
                "destructors on the collecting thread. That is the route the retained stack needs. "
                "**On this run the collecting thread is the main one**, and these are surfaces "
                "`tests/ui/surfaces.py` builds parentless, so Python owns C++ objects the product "
                "would have parented: the mechanism is shown, the product taking it is not."
            )
        else:
            print(
                f"\nCLASSIFIED, NOT OBSERVED. {len(live_when_collected)} wrappers were parked "
                "while their Qt widgets were alive, but no `QObject::destroyed` arrived when they "
                "were released — so what would have destroyed them is not established here, and "
                "the count alone is not the precondition."
            )
    elif dead_when_collected:
        print(
            f"\nNO LIVE DESTRUCTION. The collector parked {len(dead_when_collected)} censused "
            "wrappers and Qt had already destroyed every one of their widgets, so clearing them "
            "runs no destructor and reaches no cross-thread deletion path. This is Python catching "
            "up with Qt, not the crash's precondition — which is exactly the claim `T238-R7` "
            "withdrew from the first version of this measurement."
        )
    else:
        print(
            f"\nNOTHING COLLECTED. No censused wrapper reached the collector at all: "
            f"{gone_by_refcount} went by refcount and {len(still_alive)} are still alive. For the "
            "widgets that were released, the gc route is not taken on these surfaces."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
