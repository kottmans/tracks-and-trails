# `double free or corruption (!prev)` while updating yt-dlp

**Taken:** 2026-08-27, during `T-212`'s checklist run, on the maintainer's machine.
**Head:** `3d1f427` — *"Close T-273, approved at b6db88d"*, the run's recorded head.
**Platform:** Fedora 44, Linux 7.1.4-204.fc44, KDE on **Wayland**, glibc 2.43.
**Runtime:** Python 3.14.6, **PySide6 6.11.1, Qt 6.11.1**.
**Core:** PID 3389367, SIGABRT, 23.5 MB, `Thu 2026-08-27 23:07:34 CDT`. Recorded here because
`systemd-coredump` rotates and this file must outlive it.

**Recorded by an assistant from the maintainer's report and this machine's core dump.** The
reproduction is a single observation; nothing below is a claim that it reproduces on demand.

## What the maintainer did

Opened the application at the head above and used **Settings → yt-dlp → Update**.

```
This plugin supports grabbing the mouse only for popup windows
This plugin supports grabbing the mouse only for popup windows
edit: editing failed
edit: editing failed
edit: editing failed
double free or corruption (!prev)
Aborted                    (core dumped) .venv/bin/python -m tracks_and_trails
```

Then, after the process was gone:

```
resource_tracker: There appear to be 3 leaked semaphore objects to clean up at shutdown:
{'/mp-fghndr_a', '/mp-b0t9xpql', '/mp-nf3prbjf'}
```

**The application log says nothing about any of it.** Its last line is `21:30:09`, the playlist
probe; the crash was at `23:07:34`. The update path writes no record of itself — which is
`T-282`'s subject arriving as evidence rather than as an argument.

## The two threads, which is the whole finding

**Main thread — freeing while delivering a posted event:**

```
#3  __libc_message_impl.cold
#4  malloc_printerr
#5  _int_free_merge_chunk
#6  _int_free_chunk
#7  (libQt6Core)
#8  QObject::disconnectImpl(...)
#9  QLabel::setBuddy(QWidget*)
#10 QObject::event(QEvent*)
#12 QApplicationPrivate::notify_helper
#15 QCoreApplicationPrivate::sendPostedEvents
#21 QEventLoop::exec
#22 QCoreApplication::exec
```

A `QLabel` is dropping a buddy that is being destroyed — `QLabel` connects to its buddy's
`destroyed()` and clears itself — and the `free()` inside that disconnect is the one glibc aborts on.

**Thread 4175234 — Python's garbage collector destroying a widget tree at the same moment:**

```
#0  __lll_lock_wait_private          <-- waiting on the malloc lock the main thread holds
#1  _int_free_chunk
#5  QObjectPrivate::deleteChildren
#6  QWidget::~QWidget
#8  QObjectPrivate::deleteChildren
#9  QWidget::~QWidget
#11 QObjectPrivate::deleteChildren
#12 QWidget::~QWidget
#13 QWidget::~QWidget [D0]
#14 QObjectPrivate::deleteChildren
#15 QWidget::~QWidget
#17 QObjectPrivate::deleteChildren
#18 QWidget::~QWidget
#20 (libshiboken6)                   <-- PySide deleting the wrapped C++ object
#21 _Py_Dealloc
#22 gc_collect_main                  <-- CPython's cyclic collector
#23 _Py_HandlePending
#24 _PyEval_EvalFrameDefault
#28 (QtCore.abi3.so) PyObject_CallNoArgs   <-- Qt calling Python on this thread
```

**Read together: two threads are freeing the same Qt object graph.** The GUI thread is delivering
a deferred deletion and running `QLabel::setBuddy`'s disconnect; a **pool thread** is at the same
time running CPython's cyclic collector, which reached an unreferenced widget tree — five nested
levels of `deleteChildren` — and had shiboken destroy it there. Neither is waiting for the other;
they are in `free()` together, and the second one is blocked on the allocator lock the first holds.

**The pool thread is where the update runs.** `downloader/ytdlp_service.py` puts the update on a
`QThreadPool`, and frame 28 is Qt calling that task's Python `run` — so the collector tripped
inside the update task, on a thread that must never touch a widget.

**Qt widgets may only be destroyed on the GUI thread.** Nothing schedules this destruction: it is
wherever CPython's allocation counters happened to trip, which is why it presents as intermittent.

## What is not established

- **Which widget tree** was collected. The frames are `QWidget` destructors without symbols for the
  Python-side types; the `QLabel::setBuddy` on the main thread narrows the *other* side to a label
  with a buddy — `settings_dialog.py:672` and `:838`, `options_dialog.py:425`,
  `template_editor.py:103` and `:127`, `add_dialog.py:1582` and `:1614` — but does not pick one
- **Whether the update is necessary to it.** The update is what the maintainer was doing; a pool
  thread running any Python at the wrong moment is the general shape
- **`edit: editing failed`, three times.** Qt's item view says this when it is asked to edit an
  index it cannot open an editor for. It is on the same console immediately before the abort and
  may be the same story or a separate one
- **The three leaked semaphores.** Consistent with an aborted process that never ran its worker
  shutdown, rather than an independent defect

## Related

`T-273` — the window retained by callables Qt objects hold across C++ and signal edges, which
`gc` cannot traverse. `T-238` — the segfault under `gw7`. This is the same family, and the first
one with a core dump.
