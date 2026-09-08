"""Force the collector where the crash ran, and ask whether the product hands it a widget.

**Why this exists as a second instrument rather than a flag on the first.**
`tools/t289_session_watch.py` observes and does not steer — no `DEBUG_SAVEALL`, no forced
collection — because parking every collected object for a whole session changes the memory
behaviour of the thing being measured. That is the right design for *"what happens on this route"*,
and it has now answered: across 60 isolated sessions and the reviewer's two real-display runs, the
collector fired on the update's pool thread every time and **never held a widget**. Criterion 2 is
not closed by that, and it cannot be closed by more of it: *"we watched and nothing happened"* does
not distinguish *the product never hands the collector a widget* from *we did not watch at the
moment it did*.

So this instrument steers, deliberately and in the open. It drives the same route, then **runs a
collection off the GUI thread at a chosen moment** and classifies what the collector would have
freed. It is a sibling of `T-238`'s arm B — which proved that releasing a live, Python-owned
wrapper runs `~QWidget` on the collecting thread and aborts the process — with one difference that
is the whole point: **arm B built its own parentless widgets, and this asks about the product's.**

**What a finding looks like.** A widget that is parked by the collector while
`shiboken6.isValid` is still true and `shiboken6.ownedByPython` is still true is a widget whose
destructor the collector would have run, on whatever thread it fired on. If its type is defined in
Python, that destruction happens **in place** on the collecting thread rather than being marshalled
to the GUI thread, which is `T-289`'s exact shape. Either answer is worth having: it names the tree,
or it says, of the moments it sampled, that there was nothing there to take — which is a
measurement rather than an absence, and is not a statement about the route between them.

**Nothing is released off the GUI thread.** `DEBUG_SAVEALL` parks what a collection frees instead
of freeing it, so the classification happens with every widget still intact; the parked list is then
cleared **on the GUI thread**, where running a widget destructor is legal. Demonstrating the abort
is not this probe's job — arm B already did it, three runs out of three.

**Bounds, stated rather than discovered later.**

- **The update route only.** The thumbnail pipeline is a different pool reached by different work;
  this probe never stages a row. `T-238`'s criterion 4 is not answered here.
- **A forced collection is not a collection the product would have run at that moment.** What it
  establishes is reachability — whether such a widget exists to be found — not that the collector
  would have found it unprompted.
- **`DEBUG_SAVEALL` and `gc.disable()` are on for the measured phases**, deliberately: without them
  an automatic collection during the phase would free a widget before the parking was armed, and it
  would be counted as *not there* — the exact event being measured.
- The route helpers are imported from `t289_session_watch` rather than copied, so there is one
  description of what Settings → yt-dlp → Update means.

    tools/t289_forced_collection_probe.py --self-test
    tools/t289_forced_collection_probe.py --report reports/t289-forced.txt
"""

from __future__ import annotations

import argparse
import gc
import os
import subprocess
import sys
import threading
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Final, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QWidget

#: Tagged onto everything this probe builds for its own controls, so a control can never be
#: reported as a product finding — the defect that made `T-238`'s first probe censure its own
#: positive control and call it a result.
PROBE_TAG: Final = "_t289_probe_built_this"


class Parked:
    """One widget the collector would have freed, classified while it was still intact."""

    def __init__(self, widget: QWidget) -> None:
        import shiboken6

        self.valid = bool(shiboken6.isValid(widget))
        # **Identity, because clearing `gc.garbage` un-parks a cycle rather than freeing it**, so
        # the same widget is parked again by the next phase. Counting it twice would report two
        # trees where there is one.
        self.identity = id(widget)
        self.kind = type(widget).__name__
        self.module = type(widget).__module__
        # **Read only from a valid wrapper.** On a dead one `ownedByPython` raises, and the name
        # is all that is left of it.
        self.owned = bool(self.valid and shiboken6.ownedByPython(widget))
        self.name = widget.objectName() if self.valid else ""
        self.ours = getattr(widget, PROBE_TAG, False)

    @property
    def defined_in_python(self) -> bool:
        """Whether the destructor would run in place on the collecting thread (`T-289`'s shape)."""
        return not self.module.startswith("PySide6")

    @property
    def is_a_finding(self) -> bool:
        """A widget the product owns from Python **whose type is defined in Python**.

        **The type is part of the discriminator, and leaving it out made this wider than the
        defect** (`T289-R20`). `docs/project/TESTING.md` §7 turns on the distinction: a plain Qt
        type is marshalled to the GUI thread by Shiboken and destroyed safely, and only a type
        defined in Python is destroyed **in place** on whichever thread collected it. A plain
        `QWidget` that Python owns classified as a finding here and the verdict would have called it
        *the tree criterion 2 asks for*, which it is not.

        **`valid` is not tested here because `owned` already carries it** — it is computed as
        *valid and `ownedByPython`*, so a dead wrapper can never arrive owned. Stating it twice
        added a term no real widget could falsify (ruled 2026-08-31).
        """
        return self.owned and self.defined_in_python and not self.ours

    def __str__(self) -> str:
        where = "probe-built" if self.ours else "product"
        state = "LIVE" if self.valid else "already destroyed"
        owner = "Python" if self.owned else "Qt"
        python = "type defined in Python" if self.defined_in_python else "type defined in C++"
        named = f" {self.name!r}" if self.name else ""
        return f"{self.kind}{named} — {where}, {state}, owned by {owner}, {python}"


class Note:
    """A flushed report, and the little the reused route helpers ask of a watch.

    Flushed per line for the reason the watch is: the process under measurement may abort, and a
    buffer is lost when it does.
    """

    def __init__(self, report: TextIO) -> None:
        self.report = report
        self.update_started = False
        self.update_finished = False
        self.settings_seen = False
        self.phases: list[tuple[str, str, list[Parked]]] = []
        #: The steps each phase took, in order, for arm 8. See its comment for why the drain is
        #: checked as a sequence rather than by its effect.
        self.sequence: list[str] = []

    def say(self, line: str) -> None:
        import time

        self.report.write(f"{time.strftime('%H:%M:%S')}  {line}\n")
        self.report.flush()

    def finish_the_update(self, outcome: str) -> None:
        self.update_finished = True
        self.say(f"route: yt-dlp update finished — {outcome}")

    def note_the_settings_screen(self, widget: QWidget) -> None:  # pragma: no cover - unused hook
        self.say(f"route: the Settings screen opened ({type(widget).__name__})")


def widgets_the_collector_parked() -> list[Parked]:
    """Classify `gc.garbage` **before it is cleared**, which is where `T238-R7` went wrong.

    Validity read after the release says every wrapper was dead, because clearing the list is what
    killed them. It is read here, with the parked graph still standing.
    """
    return [Parked(obj) for obj in gc.garbage if isinstance(obj, QWidget)]


def force_a_collection(
    note: Note, when: str, prepare: Callable[[], None] | None = None
) -> list[Parked]:
    """Collect on a thread that is not the GUI thread, and report what it would have destroyed.

    **The collection runs off the GUI thread on purpose**: the core dump's collection ran on a pool
    thread, and a widget parked by one here is a widget whose destructor would have run there. The
    *classification* afterwards is thread-independent — `isValid` and `ownedByPython` are reads —
    so it happens here, once the collecting thread has been joined.

    **The release is handed back to the GUI thread**, because running `~QWidget` off it is the
    defect, not the measurement.
    """
    previous = gc.get_debug()
    was_enabled = gc.isenabled()
    gc.disable()
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        gc.garbage.clear()
        # **The transition this phase is about happens here, inside the boundary** (`T289-R18`).
        # Phase B used to close the dialog and deliver its deletion *before* this function armed
        # anything, so an automatic collection could consume the very teardown garbage the phase
        # exists to inspect — the false-absence path this file's own header warns about, in the
        # file that warns about it. `prepare` runs with automatic collection off and parking armed,
        # and releases its target before returning, so nothing it touched is held during the
        # collection below.
        if prepare is not None:
            prepare()
        collector: dict[str, str] = {}

        def collect() -> None:
            collector["thread"] = threading.current_thread().name
            gc.collect()

        thread = threading.Thread(target=collect, name=f"t289-forced-{when}")
        thread.start()
        thread.join()

        parked = widgets_the_collector_parked()
        note.sequence.append("parked")
        note.say(
            f"forced a collection on {collector['thread']!r} — {when}: "
            f"{len(gc.garbage)} objects parked, {len(parked)} of them widgets"
        )
        for widget in parked:
            note.say(f"    parked | {widget}")
        findings = [widget for widget in parked if widget.is_a_finding]
        # **All four operative properties, because the predicate has four** (`T289-R20`). This
        # line summarised the narrowed list with the wider wording it replaced, so a live,
        # product, Python-owned plain `QWidget` — correctly not a finding, because Shiboken
        # marshals it to the GUI thread — would have been reported as *no such widget exists*.
        note.say(
            f"    -> {len(findings)} T-289 finding(s): product widget(s) Python owns whose type "
            "is defined in Python"
            if findings
            else "    -> no T-289 finding: no product widget that Python owns with a type "
            "defined in Python"
        )
        note.phases.append((when, collector["thread"], parked))
        return parked
    finally:
        # **Drained here, on the GUI thread, before automatic collection is allowed back**
        # (`T289-R19`). Clearing `gc.garbage` un-parks a cycle rather than freeing one, so the
        # earlier version returned with a live, Python-owned widget still tracked and still
        # collectable — and with `gc.enable()` already called. Any allocating code on a pool thread
        # could then have run that widget's destructor there: the probe would have caused the
        # defect it came to look for, after reporting that it had not found it. The debug flags go
        # back first so this collection frees rather than parks, and it runs on this thread, which
        # is the GUI thread and the one where `~QWidget` is legal.
        gc.garbage.clear()
        note.sequence.append("cleared")
        gc.set_debug(previous)
        gc.collect()
        note.sequence.append("drained")
        if was_enabled:
            gc.enable()
            note.sequence.append("enabled")


def the_main_window() -> QWidget | None:
    application = QApplication.instance()
    if not isinstance(application, QApplication):
        return None
    for widget in application.topLevelWidgets():
        if type(widget).__name__ == "MainWindow":
            return widget
    return None


def the_settings_dialog() -> QDialog | None:
    application = QApplication.instance()
    if not isinstance(application, QApplication):
        return None
    for widget in application.topLevelWidgets():
        if isinstance(widget, QDialog) and type(widget).__name__ == "SettingsDialog":
            return widget
    window = the_main_window()
    return None if window is None else window.findChild(QDialog)


def object_still_tracked(identity: int, kind: str, name: str) -> object | None:
    """Find a still-tracked object by **identity alone**, holding nothing across the phase.

    **This is what makes `T289-R19` observable** — the reviewer's own control, adopted. A weak
    reference cannot do it: CPython clears weakrefs to unreachable objects *before*
    `DEBUG_SAVEALL` parks them, so it reports dead whichever way the phase ends. A strong
    reference cannot do it either, because holding one is why the widget would still be there. An
    `int` holds nothing, and `gc.get_objects()` says afterwards whether anything at that identity
    is still tracked.

    **Identities are reused**, so the type and object name are checked too: a fresh object landing
    on a freed address answers for itself rather than for the one being asked about.
    """
    for candidate in gc.get_objects():
        if id(candidate) != identity:
            continue
        if type(candidate).__name__ != kind:
            return None
        return candidate if getattr(candidate, "objectName", lambda: "")() == name else None
    return None


def frames_of_this_probe_holding(target: object) -> int:
    """How many of this file's live frames hold `target`, excluding this one.

    **Because the fix for `T289-R18` is a claim about this file's own frames**, and a claim about
    the instrument is what `--self-test` cannot reach: phase B exists only in a session. So every
    run reports it, and a non-zero count means the phase's zero was the probe's doing.

    **The stack is walked rather than asked of `gc`.** The first version used
    `gc.get_referrers(target)` and filtered for frames — and it answered **0 while a deliberately
    reintroduced `T289-R18` was holding the dialog**, because CPython does not materialise a frame
    object until something asks for one, and an unmaterialised frame is not a referrer `gc` can
    report. Walking `f_back` materialises each frame, which is what makes the locals visible.
    """
    holders = 0
    here = sys._getframe()
    # **The caller is skipped, and only the caller.** Whoever asks this question is holding the
    # object in order to ask it, so counting that frame gives a clean run a permanent score of one
    # — measured, and it reads as the defect rather than as the baseline. Every frame above it is
    # a real holder: with `T289-R18` deliberately reintroduced this reports 1 and without it 0.
    frame = here.f_back.f_back if here.f_back is not None else None
    while frame is not None:
        mine = frame.f_code.co_filename == __file__ and frame is not here
        if mine and any(value is target for value in frame.f_locals.values()):
            holders += 1
        frame = frame.f_back
    return holders


def deliver_deferred_delete(receiver: QWidget) -> None:
    """Deliver `DeferredDelete` **to one receiver**, the only one this probe may speak for.

    `processEvents` does not run a `deleteLater`; Qt delivers `DeferredDelete` from a loop. The
    first version passed `None` and flushed every pending delete in the process (`T289-R18`) — a
    claim about the whole application, made while measuring one dialog, and `T-273`'s
    receiver-scope rule exists for exactly that.
    """
    QCoreApplication.sendPostedEvents(receiver, QEvent.Type.DeferredDelete)


def measure_then_quit(note: Note) -> None:
    """Two sampled moments, then the report.

    **Phase A — the update has reported and nothing has been closed.** The crash report states the
    same two facts, which is why this moment was picked; it is **not** a reconstruction of that
    session, and nothing here establishes the two states are the same one (`T289-R18`). This is a
    timer's session, seconds old, with nothing else done in it.

    **Phase B — the Settings dialog has been closed.** A dialog's teardown is where a widget most
    plausibly becomes unreachable except through a cycle, and it is where the observing watch
    reported its destructions.

    **Two samples, not a route.** Between and around them nothing is being asked, and a widget that
    becomes collector-reachable at another instant is not seen. The window is left open: product
    shutdown is `T-273`'s territory and `T-238`'s arm C measured it.
    """

    def phase_a() -> None:
        note.settings_seen = the_settings_dialog() is not None
        note.say("phase A — update reported, Settings still open")
        force_a_collection(note, "phase-A-settings-open")
        QTimer.singleShot(500, phase_b)

    def close_the_settings_dialog() -> tuple[str, object]:
        """Close it and **keep no reference to it**, which the first version did not (`T289-R18`).

        `phase_b` held the dialog in a local while the collection ran, so the probe's own frame
        kept the wrapper reachable and phase B could not have found it however the product owned
        it. That is the self-retention class that invalidated an earlier `T-238` zero, reproduced
        here by the instrument built after it. The name is returned; the wrapper is not.
        """
        dialog = the_settings_dialog()
        if dialog is None:
            return "", None
        name = type(dialog).__name__
        # **A weak reference, so the answer can be checked without becoming the reason for it.**
        # A strong one is what `T289-R18` was.
        watcher = weakref.ref(dialog)
        dialog.close()
        # **Its own deferred delete, not the process's.** `SettingsDialog` sets no
        # `WA_DeleteOnClose`, so this delivers nothing and the widget survives — which is the
        # finding rather than a step that failed. *"Its deferred deletions delivered"* claimed
        # something this cannot establish (`T289-R18`).
        deliver_deferred_delete(dialog)
        del dialog
        return name, watcher

    def what_became_of_it(name: str, watcher: object) -> str:
        """Say why phase B's number is what it is, instead of leaving it to be inferred.

        A zero has two very different causes — *nothing was collectable* and *something held it* —
        and the second is the defect `T289-R18` found here. The dialog is looked up again through
        a weak reference **after** the collection, so this reports without participating.
        """
        import shiboken6

        window = the_main_window()
        product_holds_it = getattr(window, "_settings_dialog", "unknown")
        held = "still" if product_holds_it is not None else "no longer"
        if not callable(watcher):
            return f"{name}: the product {held} references it"
        survivor = watcher()
        if survivor is None:
            return f"{name}: its wrapper is gone — the collection or a refcount freed it"
        ours_hold_it = frames_of_this_probe_holding(survivor)
        owner = "Python" if shiboken6.ownedByPython(survivor) else "Qt"
        parent = survivor.parent()
        parented = type(parent).__name__ if parent is not None else "nothing"
        state = "alive" if shiboken6.isValid(survivor) else "destroyed"
        return (
            f"{name}: wrapper survived, C++ object {state}, owned by {owner}, "
            f"parented to {parented}; the product {held} references it; "
            f"frames of this probe holding it: {ours_hold_it}"
        )

    def phase_b() -> None:
        transition: dict[str, object] = {}

        def close_it() -> None:
            name, watcher = close_the_settings_dialog()
            transition["name"] = name
            transition["watcher"] = watcher

        note.say("phase B — closing the Settings dialog with the parking already armed")
        force_a_collection(note, "phase-B-settings-closed", prepare=close_it)
        name = str(transition.get("name") or "")
        if not name:
            note.say("    no Settings dialog was open to close")
        else:
            note.say(f"    after the collection | {what_became_of_it(name, transition['watcher'])}")
        QTimer.singleShot(500, done)

    def done() -> None:
        # **Freed here, on the GUI thread, before the process goes on living.** Clearing
        # `gc.garbage` un-parks a cycle rather than freeing it, so without this line everything the
        # phases parked is still alive and still reachable only cyclically — a loaded gun for the
        # next automatic collection, which may well run on a pool thread. That is the defect, not
        # the measurement, and leaving it armed after reporting would be this instrument causing
        # the thing it came to observe.
        note.say("freeing what the phases parked, on the GUI thread")
        gc.collect()
        application = QApplication.instance()
        if application is not None:
            application.quit()

    QTimer.singleShot(500, phase_a)


def wait_for_the_route(note: Note, waited: int = 0) -> None:
    """Start measuring once the product says the update is done, not once a timer says so."""
    if note.update_finished:
        measure_then_quit(note)
        return
    if waited > 240_000:
        note.say("the update never reported; measuring anyway so the run says something")
        measure_then_quit(note)
        return
    QTimer.singleShot(1000, lambda: wait_for_the_route(note, waited + 1000))


def start_the_session(note: Note) -> None:
    """Arm the route helpers and the drive from inside the loop that will run them (`T289-R13`)."""
    from t289_session_watch import drive_the_route, watch_the_update_route

    application = QApplication.instance()
    if isinstance(application, QApplication):
        note.say(f"platform plugin selected by Qt: {application.platformName()!r}")
    watch_the_update_route(note)  # type: ignore[arg-type]
    drive_the_route(note)  # type: ignore[arg-type]
    wait_for_the_route(note)


# --------------------------------------------------------------------------------------------
# The controls. Three arms, and the instrument refuses to run a session if any of them fails.
# --------------------------------------------------------------------------------------------


class Derived(QWidget):
    """A widget whose type is defined in Python, which is the half that makes `T-289` in-place."""


def a_control_widget(*, parent: QWidget | None = None) -> Derived:
    widget = Derived(parent)
    setattr(widget, PROBE_TAG, True)
    widget._cycle = widget  # type: ignore[attr-defined]  # the only reference is now cyclic
    return widget


def self_test() -> int:
    """Prove the classification sees a positive, ignores a Qt-owned one, and knows a corpse.

    **Because three instruments in this family have reported confidently about nothing**, and each
    failed differently: one patched a base-class `__init__` Shiboken never calls, one sampled after
    the state it measured had been torn down, and one counted 17 already-dead wrappers as live
    findings (`T238-R7`). The third arm here is that last defect, as a test.
    """
    application = QApplication.instance() or QApplication([])
    assert isinstance(application, QApplication)
    failures: list[str] = []

    class Recorder(Note):
        def __init__(self) -> None:
            super().__init__(sys.stdout)

    note = Recorder()

    # Arm 1 — a live, Python-owned, Python-typed widget reachable only through a cycle.
    live = a_control_widget()
    live.setObjectName("t289-control-live")
    # **Only the identity survives this line**, which is what lets arm 8 ask about the widget
    # after the phase without being the reason it is still there.
    identity = id(live)
    del live
    enabled_before = gc.isenabled()
    parked = force_a_collection(note, "control-live")
    # **Read before anything else, because everything else disturbs it** (`T289-R19`). Whether the
    # phase put automatic collection back is a question about the instant it returned; and the
    # scan below allocates a list of every tracked object, which is itself enough to trigger the
    # collection it is looking for — so it runs with automatic collection off, restoring whatever
    # the phase left. A scan that tidies away its own evidence would pass against the defect.
    restored_enabled = gc.isenabled()
    restored_debug = gc.get_debug()
    gc.disable()
    try:
        survivor = object_still_tracked(identity, "Derived", "t289-control-live")
    finally:
        if restored_enabled:
            gc.enable()
    named = [widget for widget in parked if widget.name == "t289-control-live"]
    if not named:
        failures.append("arm 1: the collector's parked widget was not seen at all")
    elif not (named[0].valid and named[0].owned and named[0].defined_in_python):
        failures.append(f"arm 1: misclassified — {named[0]}")
    # Arm 8 — **the phase must not hand back a live, collectable widget with automatic collection
    # switched on again** (`T289-R19`), because an allocation on a pool thread could then run its
    # destructor there: the probe causing the defect it came to look for.
    #
    # **Checked by effect, on the object itself.** An earlier version checked only that the clear,
    # drain and enable happened in that order, on the claim that no effect-based control was
    # possible here. That claim was wrong and the review supplied the counter-example. Two earlier
    # attempts had failed for reasons that do not generalise: a weakref reports dead either way,
    # because CPython clears weakrefs to unreachable objects *before* `DEBUG_SAVEALL` parks them;
    # and a `__del__` flag fires on **finalization**, which is not proof that the cycle or the C++
    # widget was deallocated — a claim this file made and now withdraws. An identity holds nothing
    # and survives both problems.
    if survivor is not None:
        import shiboken6

        alive = " and its Qt object is still valid" if shiboken6.isValid(survivor) else ""
        failures.append(f"arm 8: the parked widget is still tracked after the phase{alive}")
    # **The phase must also give back the state it borrowed.** Draining is only half of the
    # promise: a phase that never calls `gc.enable()` leaves automatic collection off for the rest
    # of the process, and one that never restores the debug flags leaves `DEBUG_SAVEALL` parking
    # every later collection into `gc.garbage`. Neither shows up in the scan above, so a mutation
    # dropping either would have passed (`T289-R19`).
    if restored_enabled != enabled_before:
        failures.append(
            f"arm 8: automatic collection was {'off' if enabled_before else 'on'} after the phase "
            f"and {'on' if enabled_before else 'off'} before it"
        )
    if restored_debug != 0:
        failures.append(f"arm 8: the phase left gc debug flags at {restored_debug}")
    if note.sequence[:3] != ["parked", "cleared", "drained"]:
        failures.append(f"arm 8: the phase's steps were {note.sequence[:4]}")
    del survivor
    gc.collect()

    # Arm 2 — the same cycle, but Qt owns the widget because it has a parent.
    #
    # **The parent goes into the garbage with it, and the first version of this arm did not do
    # that** — so the child was never parked, the assertion never ran, and the arm passed by being
    # vacuous. A parented child's wrapper stays reachable *through its parent*, which is exactly
    # why dropping a wrapper the product parented destroys nothing; the discrimination only exists
    # once both are unreachable. The arm now fails if the child is not parked at all, because an
    # arm that cannot be exercised is not a control.
    holder = a_control_widget()
    holder.setObjectName("t289-control-parent")
    child = a_control_widget(parent=holder)
    child.setObjectName("t289-control-qt-owned")
    del holder, child
    parked = force_a_collection(note, "control-qt-owned")
    named = [widget for widget in parked if widget.name == "t289-control-qt-owned"]
    if not named:
        failures.append("arm 2: the Qt-owned child was never parked, so nothing was discriminated")
    elif named[0].owned:
        failures.append(f"arm 2: a Qt-owned child was reported as Python-owned — {named[0]}")
    elif not any(widget.name == "t289-control-parent" and widget.owned for widget in parked):
        failures.append("arm 2: its Python-owned parent was not reported, so the arm proves little")
    gc.collect()

    # Arm 3 — a wrapper whose C++ widget Qt has already destroyed. Clearing it runs no destructor,
    # and calling it a finding is `T238-R7`.
    corpse = a_control_widget()
    corpse.setObjectName("t289-control-corpse")
    corpse.deleteLater()
    deliver_deferred_delete(corpse)
    del corpse
    parked = force_a_collection(note, "control-corpse")
    named = [widget for widget in parked if widget.kind == "Derived" and not widget.valid]
    if not named:
        failures.append("arm 3: the already-destroyed wrapper was not parked, so nothing was told")
    elif any(widget.is_a_finding for widget in named):
        failures.append("arm 3: a dead wrapper was reported as a live finding")

    # Arm 4 — the tag itself. A probe-built widget must never count as a product finding.
    if any(widget.is_a_finding for phase in note.phases for widget in phase[2]):
        failures.append("arm 4: a control the probe built was reported as a product finding")

    # Arm 5 — **the reporting predicate, which the four arms above never reach.** Every control is
    # probe-built, so `is_a_finding` is false for all of them by the tag alone: dropping `valid` or
    # `owned` from it would change what a session reports and would not fail a single arm. The
    # three records are asked the question again with the tag lifted, which is the only way this
    # predicate gets exercised at all.
    def would_be_reported(record: Parked | None) -> bool:
        if record is None:
            return False
        record.ours = False
        try:
            return record.is_a_finding
        finally:
            record.ours = True

    def first(collected: list[Parked], **fields: object) -> Parked | None:
        for record in collected:
            if all(getattr(record, key) == value for key, value in fields.items()):
                return record
        return None

    live_arm = first(note.phases[0][2], name="t289-control-live")
    qt_owned_arm = first(note.phases[1][2], name="t289-control-qt-owned")
    corpse_arm = first(note.phases[2][2], valid=False)
    if not would_be_reported(live_arm):
        failures.append("arm 5: a live, Python-owned widget would not have been reported")
    if would_be_reported(qt_owned_arm):
        failures.append("arm 5: a Qt-owned widget would have been reported")
    if would_be_reported(corpse_arm):
        failures.append("arm 5: an already-destroyed wrapper would have been reported")
    # *(A hand-built dead-and-owned record used to be asked here, to exercise a `valid` term the
    # predicate no longer has. Ruled out on 2026-08-31: it violated `Parked`'s own invariant —
    # `owned` is computed as *valid and `ownedByPython`* — and tested no output the tool can
    # produce. The term went instead of the test.)*

    # Arm 6 — a widget whose type comes from Qt must not be called Python-defined. Nothing above
    # asks this, so a classifier that answered "defined in Python" for everything passed.
    from_cpp = QWidget()
    setattr(from_cpp, PROBE_TAG, True)
    from_cpp.setObjectName("t289-control-cpp-type")
    from_cpp._cycle = from_cpp  # type: ignore[attr-defined]
    del from_cpp
    parked = force_a_collection(note, "control-cpp-type")
    named = [widget for widget in parked if widget.name == "t289-control-cpp-type"]
    if not named:
        failures.append("arm 6: the C++-typed widget was never parked, so nothing was classified")
    elif named[0].defined_in_python:
        failures.append("arm 6: a widget whose type is Qt's was called Python-defined")
    # **Asked of the predicate too, with the tag lifted** (`T289-R20`). Checking only the type
    # classifier is what let a plain `QWidget` — Python-owned, marshalled safely by Shiboken, not
    # this defect — be reported as *the tree criterion 2 asks for*.
    elif would_be_reported(named[0]):
        failures.append("arm 6: a Qt-typed widget would have been reported as a T-289 finding")
    gc.collect()

    # Arm 7 — **the collection has to happen off the GUI thread**, which is the probe's whole
    # premise and was not checked by anything: a version that collected on the GUI thread reported
    # identical results and passed.
    if any(phase[1] == threading.main_thread().name for phase in note.phases):
        failures.append("arm 7: a phase collected on the GUI thread, which is not the measurement")

    for failure in failures:
        print(f"SELF-TEST FAILED: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(
        "SELF-TEST PASSED: a live Python-owned widget was found and named, a Qt-owned child was "
        "not called Python-owned, an already-destroyed wrapper was not called live, nothing the "
        "probe built counted as a product finding, the reporting predicate itself was exercised "
        "with the tag lifted for the live, the Qt-owned, the destroyed and the Qt-typed record, "
        "and every collection ran off the GUI thread."
    )
    return 0


def prove_the_instrument_first(note: Note) -> bool:
    """Run the controls offscreen, in a subprocess, before the session is allowed to mean anything.

    In a subprocess because the controls leave a `QApplication` and their own widgets behind, and
    a session that censused them would be reporting on the instrument.
    """
    note.say("running the controls offscreen before the session…")
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    finished = subprocess.run(  # noqa: S603 - this file, this interpreter
        [sys.executable, str(Path(__file__).resolve()), "--self-test"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    for line in (finished.stdout + finished.stderr).splitlines():
        if line.strip():
            note.say(f"  control | {line}")
    return finished.returncode == 0


def verdict(note: Note) -> str:
    """What the phases add up to, in the four shapes they can take."""
    if not note.update_finished:
        return (
            "NOT A RESULT — the update never reported, so the route this probe exists to force a "
            "collection inside did not run."
        )
    if not note.phases:
        return "NOT A RESULT — no collection was forced, so nothing was asked."
    findings = {
        widget.identity: widget
        for phase in note.phases
        for widget in phase[2]
        if widget.is_a_finding
    }.values()
    if not findings:
        return (
            "NO REACHABLE WIDGET — the route ran, a collection was forced off the GUI thread at "
            f"both moments, and across {sum(len(p[2]) for p in note.phases)} parked widget(s) none "
            "was one the product owns from Python with a type defined in Python. At these two "
            "sampled moments the collector had nothing of the product's to destroy in place; the "
            "route between and around them was not asked."
        )
    return (
        f"REACHABLE — {len(findings)} widget(s) the product owns from Python, each with a type "
        "defined in Python, were parked by a collection running off the GUI thread. Shiboken "
        "destroys those in place on the collecting thread rather than marshalling them, which is "
        "T-289's mechanism. This is the tree criterion 2 asks for; the names are above."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the controls and exit, without starting the application",
    )
    parser.add_argument(
        "--report",
        default="reports/t289-forced.txt",
        help="where to write the observations",
    )
    arguments, rest = parser.parse_known_args()

    if arguments.self_test:
        return self_test()

    destination = Path(arguments.report)
    destination.parent.mkdir(parents=True, exist_ok=True)

    from t289_session_watch import identity

    from tracks_and_trails.app import run

    with destination.open("w", encoding="utf-8") as report:
        note = Note(report)
        note.say("T-289 forced-collection probe — this instrument steers; the watch observes")
        note.say("route: Settings -> yt-dlp -> Update, then a collection forced off the GUI thread")
        for line in identity():
            note.say(line)
        note.say("a report with no VERDICT line at the end is an incomplete run and says nothing")
        if not prove_the_instrument_first(note):
            note.say("VERDICT: NOT A RESULT — the controls failed; no session was run.")
            print("controls failed; see the report", file=sys.stderr)
            return 2
        note.say("controls PASSED offscreen — this probe reports what it is built to report")

        QTimer.singleShot(0, lambda: start_the_session(note))
        try:
            code = run([sys.argv[0], *rest])
        finally:
            # **The same three flags the watch's summary carries**, in the same shape, because
            # `tools/t289_isolated_session.sh` gates both instruments on one postcondition and a
            # report that cannot be checked is a report that can be a stale file.
            note.say(
                f"route: settings={note.settings_seen} update_started={note.update_started} "
                f"update_finished={note.update_finished}"
            )
            note.say(f"VERDICT: {verdict(note)}")
        print(f"\n{verdict(note)}\n\nreport: {destination}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
