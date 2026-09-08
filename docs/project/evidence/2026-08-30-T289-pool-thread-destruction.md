# T-289 — what makes shiboken destroy in place rather than marshal

**Taken:** 2026-08-30 on `Spock`, offscreen, `tools/t289_pool_gc_probe.py`. Eight runs per subject.

**The question this answers.** `T-289`'s dump shows `gc_collect_main` on a pool thread taking
`~QWidget` down with it. The probe's first version could not reproduce that: the decref happened on
`Dummy-1` and the C++ destructor ran on `MainThread` — **shiboken marshalled**, through
`BindingManager::runDeletionInMainThread`. The entry recorded the open question as *"what makes
shiboken destroy in place rather than marshal"* and named three candidates worth separating. **It is
none of them. It is whether the widget's type is defined in Python.**

## The reading

| Subject, collected on a `QThreadPool` thread | crashed | destructor **off** the GUI thread | marshalled |
|---|---:|---:|---:|
| A plain `QWidget` tree | 0/8 | 0/8 | **8/8** |
| The same tree rooted in a **one-line Python subclass** | **3/8** | **5/8** | 0/8 |
| The application's own screens (`tests/ui/surfaces.py`) | 0/8 | **8/8** | 0/8 |

The subclass has **no behaviour, no signal connections, no closures and is never shown** — its body
is a docstring. Being a Python-derived type is the whole difference from row one.

*(`--shown` was measured too and changes nothing: a realised plain `QWidget` still marshals. The
variable is the type, not the platform window.)*

## What this means for the product

**Every widget this application defines is a Python subclass.** `MainWindow`, `AddUrlDialog`,
`OptionsDialog`, `FormatTable`, `QueueView` — all of them. So the marshalling that made the first
probe's null result look reassuring **does not apply to any widget this project owns**. The
precondition is not exotic; it is the default for this codebase, and what has kept it rare is only
how seldom a widget tree becomes collectable on a pool thread's allocation.

## The crash, and why it is the dump's shape

Three of the eight subclass runs died with SIGSEGV. The stack is the *main* thread:

```text
#0  ??                                          PySide6/QtWidgets.abi3.so
#1  Shiboken::BindingManager::runDeletionInMainThread()   libshiboken6
#2  ??                                          libshiboken6
#3  _make_pending_calls                         libpython3.14
#4  make_pending_calls                          libpython3.14
#5  _Py_HandlePending                           libpython3.14
```

**Read with the observation above it, that is a double deletion.** The pool thread ran the C++
destructor in place — the probe's `DirectConnection` handler recorded `~QObject` on `Dummy-1`
immediately before — and the main thread then ran the deletion shiboken had *also* queued for it,
on an object that no longer exists. `double free or corruption (!prev)` is what `T-289` was filed
from.

**Stated as the reading, not as proof.** What is measured is the destructor thread and the crashing
stack. That the main-thread deletion targets the *same* object the pool thread destroyed is the
obvious explanation and is not separately established here; nothing dumped the pointer.

## Bounds

- **Offscreen, one machine, eight runs a subject.** The rates are indicative; the *discrimination*
  is not — 8/8 against 0/8 is not a timing artefact.
- **The crash is intermittent (3/8) and the reproduction is not** (5/8 reported, 8/8 for the real
  screens). Anything built on this should target the destructor thread, which is deterministic, not
  the abort, which is not.
- **The five screens are constructed parentless by the helper**, which is the ownership the
  mechanism needs. A widget with a C++ parent is owned by that parent and is not destroyed by
  dropping its wrapper — which is also why the fix direction the entry already names (give the tree
  a Qt parent, or dispose through the GUI thread) is unaffected by this finding.
- **This does not reproduce the double free deliberately**, and the probe still refuses to try;
  three runs did it by themselves.

## What it unblocks

`T-289`'s criterion 4 asks for *"a test that fails on the uncorrected tree… even if it has to force
the collector on a pool thread while a tree is collectable"*. **That state can now be arranged on
demand, in about ten lines, with no application involved.** The criterion is still unmet — a tool is
not a test — but it is no longer waiting on a mechanism nobody could name.
