# T-238 criterion 4 — can collecting a wrapper destroy a live Qt widget?

**Taken:** 2026-08-30 on `Spock`, offscreen, `tools/t238_widget_cycle_probe.py`. Three arms, each
deterministic across repeated runs.

**This record replaces the first version of itself, which was wrong** (`T238-R7`). That version
reported *"17 widgets freed by the cyclic collector"* over an `OptionsDialog` tree and called it the
crash's precondition. Every one of the seventeen was an **already-dead wrapper**: the probe had
called `deleteLater()` and flushed `DeferredDelete` first, so Qt destroyed the C++ widgets and the
collector merely parked the Python halves. Clearing a dead wrapper runs no destructor. The number
was real; the claim on top of it was not, and the reviewer's replay — validity read while
`gc.garbage` was still populated — is what separated them.

## The predicate, corrected

| Parked wrapper | `shiboken6.isValid` at parking | What releasing it does |
|---|---|---|
| **Live** | `True` | **Destroys the C++ widget, on the collecting thread** |
| Dead | `False` | Python bookkeeping; Qt already destroyed it elsewhere |

Validity is now read **before `gc.garbage` is cleared**. `DEBUG_SAVEALL` parks rather than releases,
so the classification is *what the collector would free*; the release is then performed as the last
thing the process does, after the classification is printed and flushed.

## The three arms

| Arm | Constructed screens | Window | Parked | **Live when parked** | Survivors | Outcome |
|---|---|---|---:|---:|---:|---|
| **A** | closed + `deleteLater` (fixture ownership) | product shutdown alone | 17 | **0** | 95 | no live destruction |
| **B** | **dropped for the collector** | product shutdown alone | 24 | **24** | 122 | **release → SIGSEGV** |
| **C** | closed + `deleteLater` | **+ `T-273`'s owner step** | 67 | **0** | **0** | no live destruction |

Census in every arm: **364** widgets — 159 opened by the application's own routes, 205 constructed
by `tests/ui/surfaces.py`.

## What each arm answers

**A — no widget the application's routes opened takes the collector's route.** Of the 159, the 64
released went by refcount. The 17 parked were all dead wrappers of the helper's screens. **This is
the arm the first version reported, and it establishes nothing about live destruction.**

**B — the mechanism is real, and demonstrating it aborts the process.** When Python owns the C++
objects and only the collector frees them, 24 wrappers are parked **with their widgets still
alive**, and releasing them dies:

```text
#0  QCursor::pos(QScreen const*)                    libQt6Gui
#1  ??                                              platforms/libqoffscreen.so
#2  QWindowPrivate::setVisible(bool)                libQt6Gui
#3  QWidgetPrivate::hide_helper()                   libQt6Widgets
#4  QWidgetPrivate::setVisible(bool)                libQt6Widgets
#5  QDialogPrivate::setVisible(bool)                libQt6Widgets
#6  QDialog::~QDialog()                             libQt6Widgets
#7  ??                                              PySide6/QtWidgets.abi3.so
#8  ??                                              libshiboken6
#9  _Py_Dealloc                                     libpython3.14
#10 gc_collect_main                                 libpython3.14
```

SIGSEGV, main thread, **3 of 3 runs**. `gc_collect_main` → `_Py_Dealloc` → shiboken →
`~QDialog` is the same upper stack as `T-238`'s retained crash and as `T-289`'s dump: **the cyclic
collector running a Qt widget destructor.** The lower half is different — this one dies in the
*offscreen* platform plugin asking for a cursor position while hiding a still-visible dialog, on the
main thread, where `T-238`'s dies in `~QAbstractItemView` under Shiboken's cross-thread deletion.
**So this is not `T-238`'s crash**, and it is the first time this project has reproduced the
collector-destroys-a-Qt-widget route on demand.

**C — the 95 survivors are `T-273`'s documented baseline, not a new leak** (`T238-R8`). `T-273`
ruled that `shutdown.begin()` does not own the window's lifetime; the `composed` fixture does, with
`window.deleteLater()` plus a **receiver-scoped** `DeferredDelete` flush. Apply that step and
**every censused widget goes: 0 survivors.** Arms A and B omit it, which is why the `MainWindow`
tree stands there — expected, and no evidence that `T-273` is incomplete. Its referrers in those
arms, 6 bound methods and 3 closure cells, are the mechanism `T-273` documents.

## Bounds, and they are load-bearing here

- **Arm B's widgets are the helper's.** `tests/ui/surfaces.py` builds the five parentless, so Python
  owns C++ objects **the product would have parented**. The mechanism is shown; the product taking
  it is not.
- **Main thread, not a pool thread.** The crash `T-238` is filed for needs the collector to run
  where a pool thread crossed the allocation threshold. This offscreen process does not arrange it.
- **Offscreen.** Arm B's proximate fault is in the offscreen plugin; a real display may not fault
  there at all. The upper stack is the transferable part.
- **`gc` is disabled for the measured phase**, so this is not natural teardown timing. It is what
  makes the classification possible: a generational collection during teardown would free a widget
  before `DEBUG_SAVEALL` was armed and it would be filed as refcount-freed.
- **Nothing here reproduces `T-238`'s crash**, and criterion 4 is not met by any of it.

## The instrument

Three controls, all in-run: a widget reachable only from a cycle is parked by its own tag **and is
valid at that moment**; a refcount-freed widget is not named; a parentless `QListView` outliving the
self-test makes the probe **refuse**, because the first version censused its own positive control
and reported it as a product finding. Identity is a uuid tag in each widget's instance `__dict__`;
the census holds only weak references and strings, because a probe that holds its subjects is the
retention root and its containers turn up in `gc.get_referrers`.
