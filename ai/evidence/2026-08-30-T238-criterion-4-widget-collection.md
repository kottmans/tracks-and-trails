# T-238 criterion 4 — which widgets the cyclic collector frees

**Taken:** 2026-08-30 on `Spock`, offscreen, `tools/t238_widget_cycle_probe.py` at `c5a5292` plus
the probe rewrite this record belongs to. Deterministic: two consecutive runs agree on every
number below.

**The question.** The retained stack shows `~QAbstractItemView` under
`Shiboken::BindingManager::runDeletionInMainThread`, and the sibling thread probe established that
**no thread has to hold a widget** for that: `gc` runs wherever the allocation threshold trips, so a
widget freed by the collector is decref'd there. Criterion 4 asks whether the product ever puts a
widget on that route. The 2026-08-20 attempt **refused** — the surfaces were still standing, so the
collector never classified them — and `T238-R5` named four reasons its counts reached no
conclusion. Each is answered here rather than noted.

## The reading

| | |
|---|---|
| Widgets censused, every surface open | **364** |
| — opened by the application's own routes | **159** |
| — constructed by `tests/ui/surfaces.py` | **205** |
| **Freed by the cyclic collector** | **17** — all of them constructed, all one tree |
| Freed by refcount | **252** |
| Still alive after the release | **95** — all one tree, **1** top-level |
| Wrappers among those whose C++ half is gone | **0** |
| Objects the collector parked in this window | 35 |

Arithmetic, because the split is the finding: the 205 constructed are 17 collected + 188 refcount;
the 159 route-opened are 95 still alive + 64 refcount.

## What it answers

**1. No widget the application's own routes opened was freed by the collector.** Of the 159, the
**64 that were released all went by refcount**, on the thread that dropped them. For those, the gc
precondition is not reached and the harness reading stands.

**2. It does not answer the other 95, and that is a finding of its own.** They are the
`MainWindow` tree — one top-level widget, 94 descendants — **still alive after
`composition.shutdown.begin()` completed and after the probe dropped every reference it held**.
A live graph is never classified by the collector, so for those the question is not open-and-unmeasured, it is *unmeasurable while they are retained*. The referrer sketch of the root is
**6 bound methods and 3 closure cells** — which is `T-273`'s mechanism exactly, on a tree that task
was meant to have released.

**3. The `OptionsDialog` tree is cyclic, and that is worth less than it looks.** All 17
collector-freed widgets are its: the dialog itself and sixteen descendants. Nothing but the
collector could have freed them, so they participate in reference cycles. **But
`tests/ui/surfaces.py` builds them parentless**, so Python owned a C++ object the product would have
parented — the destruction measured is the helper's ownership, not the application's. In the product
the dialog has a parent, and dropping a wrapper then runs no C++ destructor. **This is not the
crash's precondition**; it is a place to look for one.

## The instrument, proved in three directions before any number was believed

- **Positive**: a widget reachable only from a reference cycle is seen, *by its own tag* rather than
  by class name.
- **Negative**: a widget freed by refcount is not named.
- **Residue**: a parentless `QListView` surviving the self-test makes the probe **refuse** (exit 2).
  Forced deliberately to check the refusal fires, because the guard's normal path never reaches it.

**That third guard exists because the first version of this run reported a false positive.** It
printed *"1 QListView freed by the collector — CRITERION 4, PRODUCT BRANCH"*, and the widget was the
probe's **own positive control** surviving into the census. Reproduced deliberately with the guard
disabled: the census is 306 instead of 300 and the freed widget is described as
`QListView (parentless)`, which the application never builds. **A probe manufacturing its own
headline is the third instrument in this family to report confidently about nothing**, and the
class name alone would never have shown it — identity is what did.

## Two corrections to the method, either of which would have changed the answer

- **`processEvents()` does not run a `deleteLater()`.** Qt delivers `DeferredDelete` only from an
  event loop. A version that only pumped events reported the five constructed screens as *retained*
  — a fact about the pump. `sendPostedEvents(None, DeferredDelete)` is what teardown needs, which is
  `tests/qt_lifecycle.settle_deferred_deletions`'s own docstring.
- **Automatic collection is off for the measured phase.** A censused widget freed by a
  *generational* collection during teardown would be gone before `DEBUG_SAVEALL` was armed and would
  be filed under *freed by refcount* — misclassifying the exact event being measured. With `gc`
  disabled, every collection in the window is one the probe performed with the verdict readable.

## Bounds

- **The five screens are constructed, not opened through their routes.** Reaching them needs a
  staged row from a recorded extraction; `tests/ui/surfaces.py` records the trade and what it costs
  a lifetime measurement — a route wires closures a bare construction does not.
- **One offscreen process is not a real session.** Criterion 4's *other* named step — the
  application driven on a display with the thumbnail pool working — is not this.
- **A collector-freed widget is the precondition, not the crash.** Nothing here reproduces the
  segfault, and nothing here claims to.
