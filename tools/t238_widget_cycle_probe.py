"""Which `QWidget`s this application builds does the cyclic collector free? (`T-238` crit. 4)

**The question, and why it is this one.** The retained stack shows `~QAbstractItemView` under
`Shiboken::BindingManager::runDeletionInMainThread`, which Shiboken only queues when the wrapper's
last Python reference was dropped somewhere else. The sibling `t238_widget_thread_probe` then
established that **no thread has to hold a widget for that to happen**: Python's cyclic collector
runs on whichever thread crosses the allocation threshold, so a widget freed by `gc` is decref'd
wherever `gc` happens to run. Ownership was the wrong question. This is the right one: **does the
product ever put a widget on that route?**

**So the predicate is "freed by the collector", not "in a cycle".** A widget held *by* a cycle is
not itself in one — its own strongly-connected component has size one — yet it is still freed by
`gc` rather than by refcount, and still decref'd on whatever thread collected. Cycle *membership*
would answer a neighbouring question and miss exactly the shape the sibling probe demonstrated.

## What the 2026-08-20 version could not answer, and what changed

That run exited 3 and refused: the surfaces were still standing at the end, so the collector never
classified them and its zero said nothing. `T238-R5` named four reasons the counts did not reach a
conclusion, and each is answered here rather than noted:

1. **Retention is not the absence of cycles.** So the retention root is now *released* — every
   strong reference this probe holds lives in one frame, which returns before the measurement — and
   what is still alive afterwards is reported as a finding rather than as a reason to refuse.
2. **Equal aggregates do not establish identity.** So every widget is tagged and tracked
   individually. `159 before, 159 after` is not evidence that they are the same 159, and this no
   longer relies on it: each widget is classified as *freed by the collector*, *freed by refcount*
   or *still alive*, by name.
3. **The forced collection after the result was not recorded.** So the collection now happens
   **after** the release and **inside** the measurement window, with `DEBUG_SAVEALL` still armed.
4. **Five product-reachable screens were not covered.** So they are, through
   `tests/ui/surfaces.py` — the same inventory `tests/ui/conftest.py` audits, imported rather than
   restated, because two lists of them would drift.

## How identity survives a freed wrapper

Each widget gets a unique tag in its instance `__dict__` at census time, and the census holds
**weak** references and strings — never a widget. Two reasons, and the second is the one that bit:

- `gc.DEBUG_SAVEALL` parks collected objects in `gc.garbage` instead of releasing them, so a parked
  wrapper's tag is still readable. It is read out of `obj.__dict__` directly rather than with
  `getattr`, because the C++ half may already be gone and a descriptor could reach for it.
- A probe that holds the widgets it is deciding about **is** the retention root, and its own
  containers turn up in `gc.get_referrers`. That contaminated the 2026-08-20 attribution and got it
  withdrawn. Holding nothing strongly is what makes the referrer sketch below worth printing.

`id()` alone would not do: a refcount-freed widget's address can be reused by a later parked
object. The tag is the identity; the id is only cross-checked against it.

## The self-test runs first, in both directions, and the measurement is not printed without it

Its sibling shipped two defects that each made it report confidently about nothing, **one of them a
clean-looking zero**. A "no widget takes the gc route" answer is worth nothing unless the same run
shows the probe (1) *sees* a widget that is on that route and (2) does *not* name one that is not —
and, since this version answers by identity, that it reports the right *tag* rather than merely the
right class name.

**Usage** — a script, not a plugin, and it must be run from the repository root so that
`tests/ui/surfaces.py` is importable:

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t238_widget_cycle_probe.py

`ai/evidence/README.md`'s rule keeps the instrument here and the number in `T-238`.

## What this still does not establish

- **The five screens are constructed, not opened through their routes** — `tests/ui/surfaces.py`
  records why, and what it costs a lifetime measurement specifically: a route wires closures a bare
  construction does not, and closures across edges `gc` cannot traverse are what `T-273` found
  retaining a window.
- **One offscreen process is not a real session.** Criterion 4's *other* named step — the probe
  against the application driven on a display, with the thumbnail pool working — is not this.
- **A widget the collector frees here is not the crash.** It is the crash's precondition, which is
  the whole of what criterion 4 asks about.
"""

from __future__ import annotations

import gc
import sys
import weakref
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import shiboken6
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QListView, QWidget

# **Run as a script, so `sys.path[0]` is `tools/`** and the repository root is not on the path —
# which is what `tests.ui.surfaces` needs. Added here rather than asking the caller for a
# `PYTHONPATH=.` prefix: a documented command that fails when it is copied is `T268-R3`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TAG: str = "_t238_tag"


@dataclass
class Census:
    """Who was alive, by identity, holding nothing that would keep them that way.

    `alive` maps tag to a weak reference; `described` maps tag to a readable name. Both are strings
    and weakrefs by construction — see the module docstring on why this probe may not hold a widget.
    """

    alive: dict[str, weakref.ref[QWidget]] = field(default_factory=dict)
    described: dict[str, str] = field(default_factory=dict)
    address: dict[str, int] = field(default_factory=dict)
    #: `"route"` for a widget the application's own routes opened, `"constructed"` for one of the
    #: five screens `tests/ui/surfaces.py` builds. **The two do not support the same claim**: a
    #: constructed screen is parentless because the helper made it so, and Python therefore owns a
    #: C++ object the product would have parented. A verdict that pooled them would report the
    #: helper's ownership as the product's.
    origin: dict[str, str] = field(default_factory=dict)

    def take(self, widgets: list[QWidget], origin: str) -> None:
        for widget in widgets:
            if TAG in widget.__dict__:
                continue  # already censused in an earlier pass; its origin is the earlier one
            tag = uuid4().hex
            self.origin[tag] = origin
            widget.__dict__[TAG] = tag
            name = widget.objectName()
            # **Read here, while the C++ half is certainly alive.** A parked wrapper may have lost
            # it, and the class name alone does not say *which* `QListView` — the answer to that is
            # the difference between a product finding and a probe artefact.
            parent = widget.parentWidget()
            within = f" in {type(parent).__name__}" if parent is not None else " (parentless)"
            self.described[tag] = f"{type(widget).__name__}{f' ({name})' if name else ''}{within}"
            self.address[tag] = id(widget)
            try:
                self.alive[tag] = weakref.ref(widget)
            except TypeError:  # pragma: no cover - every PySide wrapper supports this today
                self.described.pop(tag)
                self.address.pop(tag)

    def __len__(self) -> int:
        return len(self.described)


def _tag_of(obj: object) -> str | None:
    """The tag, read without touching anything the C++ half owns."""
    instance = getattr(obj, "__dict__", None)
    return instance.get(TAG) if isinstance(instance, dict) else None


def _collect_and_read_the_garbage() -> tuple[dict[str, str], int]:
    """Collect with `DEBUG_SAVEALL` armed; return every parked widget's tag and the total parked.

    The total is returned because *no widget was collected* and *nothing was collected* are
    different findings and only the second says the collector had nothing to do. Quoting it from
    anywhere but here is how it once got quoted from a diagnostic holding the objects it counted.
    """
    gc.set_debug(gc.DEBUG_SAVEALL)
    try:
        gc.collect()
        parked: dict[str, str] = {}
        for obj in gc.garbage:
            if isinstance(obj, QWidget):
                tag = _tag_of(obj)
                parked[tag if tag is not None else f"untagged-{id(obj):x}"] = type(obj).__name__
        total = len(gc.garbage)
    finally:
        gc.garbage.clear()
        gc.set_debug(0)
    return parked, total


def _self_test() -> tuple[bool, bool, list[str]]:
    """Both directions, by tag, before anything below is believed.

    Positive: a widget reachable **only** from a reference cycle. Nothing holds it directly, so no
    refcount reaching zero can free it and the collector must be what does.

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
    saw_the_positive = positive_tag in parked
    notes.append(
        "positive: a widget reachable only from a cycle was "
        + (
            f"seen, by its own tag ({parked[positive_tag]})"
            if saw_the_positive
            else "MISSED — this probe cannot see its own subject"
        )
    )

    negative_tag = uuid4().hex
    dropped = QListView()
    dropped.__dict__[TAG] = negative_tag
    del dropped

    parked, _total = _collect_and_read_the_garbage()
    named_the_negative = negative_tag in parked
    notes.append(
        "negative: a widget freed by refcount was "
        + ("correctly not named" if not named_the_negative else "NAMED — this probe over-reports")
    )
    return saw_the_positive, not named_the_negative, notes


def _the_self_tests_widgets_are_gone() -> bool:
    """No `QListView` of the self-test's may survive into the census, or the result is its own.

    The positive control is **built to be freed by the collector**, which is the exact finding the
    measurement reports. If one outlived the self-test it would be censused with a fresh tag and
    counted as a product widget on the gc route — a probe manufacturing its own headline. Checked
    rather than reasoned, because the two are indistinguishable in the output.
    """
    gc.collect()
    return not any(
        type(w).__name__ == "QListView" and w.parentWidget() is None
        for w in QApplication.allWidgets()
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


def _build_drive_and_tear_down(census: Census) -> None:
    """Everything strong lives in this frame, and this frame returns before the collector is asked.

    That is the release the 2026-08-20 run had no way to perform: it read the collector while the
    composition was still on the stack, so a retained graph was never classified and its zero meant
    nothing. Here the application is composed, driven through its own routes, torn down through
    `composition.shutdown.begin()` — the route a user's close takes — and then *dropped*, because
    returning drops it.
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
        census.take(QApplication.allWidgets(), "route")

        built = screens_below_the_add_dialog()
        for _label, widget in built:
            widget.show()
        app.processEvents()
        census.take(QApplication.allWidgets(), "constructed")

        # **Automatic collection is off from here to the end of the measurement, and that closes
        # the hole the counts would otherwise have.** A censused widget freed by a *generational*
        # collection during teardown would be gone before `DEBUG_SAVEALL` was ever armed, and this
        # probe would file it under *freed by refcount* — misclassifying the exact event it exists
        # to detect. With the collector stopped, the only collections in this window are the ones
        # `_collect_and_read_the_garbage` performs with the verdict readable.
        gc.disable()

        # The constructed five are owned here because nothing else owns them, exactly as
        # `every_surface` owns them: a parentless widget left to the collector has its destructor
        # run wherever the collector next fires, which is the shape this task is about.
        for _label, widget in built:
            widget.close()
            widget.deleteLater()
        built.clear()

        # **`processEvents()` does not run a `deleteLater`.** Qt delivers `DeferredDelete` only
        # from an event loop, so a headless run that only pumps events leaves every requested
        # deletion queued — `tests/qt_lifecycle.settle_deferred_deletions` exists for this and its
        # docstring is `T-238`'s own finding. A first version of this probe pumped events and then
        # reported the five constructed screens as *retained*, which was a fact about the pump.
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        window.close()
        composition.shutdown.begin()
        for _ in range(4000):
            if composition.shutdown.finished:
                break
            app.processEvents()
        assert composition.shutdown.finished, "composition never finished shutting down"
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        del window, settings, composition


def main() -> int:
    # **Before the self-test, because the self-test builds widgets.** Qt aborts the process on a
    # `QWidget` constructed with no `QApplication`, and the first version of this file did exactly
    # that — it died before printing a line, which is at least a loud failure rather than a quiet
    # zero.
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)

    positive, negative, notes = _self_test()
    print("T-238 criterion 4 — which widgets the cyclic collector frees\n")
    for note in notes:
        print(f"  self-test {note}")
    if not (positive and negative):
        print("\nSELF-TEST FAILED. The measurement below is not evidence of anything.")
        return 2

    if not _the_self_tests_widgets_are_gone():
        print(
            "\nSELF-TEST RESIDUE. A parentless QListView survived the self-test, so a widget "
            "built to be collected would be censused as the application's. Refusing."
        )
        return 2

    census = Census()
    try:
        _build_drive_and_tear_down(census)
        # The release itself posts deletions — the objects dropped when that frame returned. They
        # are delivered here, before the collector is asked anything.
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        # **After the release, and inside the window.** This is the collection the 2026-08-20
        # run did in a `finally` after lowering the debug flag, where what it freed was
        # invisible.
        parked, total_parked = _collect_and_read_the_garbage()
    finally:
        gc.enable()

    freed_by_collector = {tag: name for tag, name in parked.items() if tag in census.described}
    still_alive = {
        tag: reference
        for tag, reference in census.alive.items()
        if tag not in freed_by_collector and reference() is not None
    }
    freed_by_refcount = len(census) - len(freed_by_collector) - len(still_alive)
    untagged = len(parked) - len(freed_by_collector)
    # **A live *wrapper* is not a live widget, and the difference is most of what survives here.**
    # `deleteLater` destroys the C++ half and leaves the Python wrapper to ordinary Python rules —
    # so a wrapper still standing with `isValid()` false is one whose decref has not happened yet,
    # and it is the object the collector would be freeing if it ever did.
    orphaned_wrappers = sum(
        1
        for reference in still_alive.values()
        if (widget := reference()) is not None and not shiboken6.isValid(widget)
    )

    routed = sum(1 for origin in census.origin.values() if origin == "route")
    print(f"\n  QWidgets in the census (every surface open):  {len(census)}")
    print(f"    opened by the application's own routes:    {routed}")
    print(f"    constructed by tests/ui/surfaces.py:       {len(census) - routed}")
    print(f"  freed by the cyclic collector:               {len(freed_by_collector)}")
    print(f"  freed by refcount:                           {freed_by_refcount}")
    print(f"  still alive after the release:               {len(still_alive)}")
    print(f"    of those, wrappers whose C++ half is gone:  {orphaned_wrappers}")
    print(f"  objects the collector parked in this window: {total_parked}")
    if untagged:
        print(f"  parked widgets built after the census:       {untagged}")

    if not census:
        print("\nREFUSED. The census is empty, so nothing was measured.")
        return 3

    if still_alive:
        # **The roots are the finding; their children are arithmetic.** A child is retained because
        # its parent is, so listing every survivor would bury the handful actually held by
        # something. Printed whatever the verdict is: what did *not* go is a fact about the run.
        roots = [
            tag
            for tag, reference in still_alive.items()
            if (widget := reference()) is not None
            and shiboken6.isValid(widget)
            and widget.parentWidget() is None
        ]
        print(
            f"\n  of the {len(still_alive)} survivors, top-level (no parent widget): {len(roots)}"
        )
        for tag in roots[:15]:
            print(f"    {census.described[tag]} [{census.origin.get(tag, '?')}]")
        # The sketch is taken of a **root**, because a child's referrer is its parent and says
        # nothing. Falls back to any survivor only when nothing is top-level.
        subject = still_alive[roots[0]] if roots else next(iter(still_alive.values()))
        label = census.described[roots[0]] if roots else "a survivor"
        sketch = _who_still_holds(subject)
        print(f"    referrers of {label}: {', '.join(sketch) if sketch else 'none readable'}")

    by_route = [tag for tag in freed_by_collector if census.origin.get(tag) == "route"]
    by_construction = [tag for tag in freed_by_collector if census.origin.get(tag) != "route"]

    if freed_by_collector:
        print("\n  freed by the collector, by identity:")
        for group, tags in (("opened by a route", by_route), ("constructed", by_construction)):
            if not tags:
                continue
            print(f"    [{group}]")
            for name, count in Counter(census.described[tag] for tag in tags).most_common():
                print(f"      {count:5d}  {name}")

    if by_route:
        print(
            "\nCRITERION 4 — PRODUCT BRANCH. A widget the application's own routes opened is "
            "freed by the collector rather than by refcount, so it is decref'd on whichever "
            "thread crossed the allocation threshold. The gc route is product-reachable in fact "
            "and not only in principle, and criterion 4 wants a deterministic regression rather "
            "than a guard."
        )
    elif by_construction:
        print(
            "\nQUALIFIED. **No widget opened by a route was freed by the collector.** What was is "
            "the tree of a screen `tests/ui/surfaces.py` constructs, and the difference decides "
            "what this supports: those are built **parentless**, so Python owns a C++ object the "
            "product would have parented, and their destruction is the helper's ownership rather "
            "than the application's.\n\nWhat it does establish is narrower and still worth having: "
            "**those widget trees participate in reference cycles**, since nothing but the "
            "collector could free them. In the product they are parented, so dropping the wrapper "
            "does not run a C++ destructor — the crash's precondition needs a widget whose C++ "
            "half Python owns, and this run does not show the product holding one.\n\nCriterion 4 "
            "is not closed either way by this. The route-opened surfaces answer *harness* for the "
            "coverage below; the cyclic trees say where to look next."
        )
    if by_route or by_construction:
        pass
    elif still_alive:
        print(
            f"\nPARTIAL. No censused widget was freed by the collector, and {len(still_alive)} of "
            f"{len(census)} are still alive after this probe dropped everything it held — so for "
            "those, the question is not answered: a live graph is never classified and may contain "
            "any number of cycles. The referrer sketch is indicative, and identifying the "
            "retention root is a separate measurement.\n\nWhat *is* answered: the "
            f"{freed_by_refcount} that did go, went by refcount, on the thread that dropped them."
        )
    else:
        print(
            f"\nCRITERION 4 — HARNESS BRANCH, for these surfaces. Every one of the {len(census)} "
            "widgets went by refcount, on the thread that dropped it; none took the collector's "
            "route. The gc precondition is not reached through the surfaces this run covers, so "
            "for them the harness reading stands. Read it with the module docstring's bounds: five "
            "screens are constructed rather than opened, and one offscreen process is not a real "
            "session."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
