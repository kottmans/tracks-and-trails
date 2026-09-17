# `T-343` — the taskbar's *Close window*, through a dialog

**Date:** 2026-09-17
**Task:** `T-343`, Phase 4.5 stage 1, shipping in `0.1.1` (`T-349`)
**Shape:** Windows-only handling, ruled by the maintainer on 2026-09-17
**Built:** `ui/taskbar_close.py`, installed by `app.present` on Windows only
**Machine for everything below marked offscreen:** this development host, Fedora 44, the project
virtual environment

## What was wrong

The maintainer reported that with *Add URLs* or *Preferences* open, right-clicking the taskbar
button and choosing *Close window* does not close the application. The reproduction at `8d70e01`
posted the taskbar's own messages to the main window on `STARBASE`:

| Open dialog | `WM_CLOSE` | `WM_SYSCOMMAND` / `SC_CLOSE` | Main window enabled |
|---|---|---|---|
| none | closes | closes | yes |
| *Add URLs* | ignored | ignored | **no** |
| *Preferences* | ignored | ignored | **no** |

Windows disables the owner of a window-modal dialog, and Qt will not deliver a close to a window a
modal dialog blocks.

## The offscreen suite

`tests/ui/test_taskbar_close.py`, **28 passed**. It drives `TaskbarClose.consider` with the three
`MSG` fields as values, so every decision is checked on either platform: which messages are a close
(including a system command carrying the low bits Windows reserves), that a close for another
window is ignored, that a close with no dialog open is passed to Qt untouched, that stacked dialogs
all close, that a dialog refusing to close keeps the application open **and is asked once**, that a
`WA_DeleteOnClose` dialog is destroyed as it would be by any other close, and that the window's own
`closeEvent` runs rather than a bare `hide()`.

`tests/integration/test_composition.py` gained the wiring: `present()` asks for the rule, for the
application it composed and the window it is showing.

## The mutation campaign

Eighteen mutations, each a defect the module's own words claim to prevent. **Control first**: the
unmutated pair of suites passes (116 tests), so a broken instrument could not read as a clean
sweep. **All eighteen were caught.**

*(The first run of this campaign said the opposite and was wrong: the two suites were named by a
path that does not exist, so `pytest` collected nothing, exited non-zero, and every mutation read
as caught. The harness now runs the control first and refuses a run that collects nothing.)*

| Mutation | Caught by |
|---|---|
| `WM_CLOSE` is no longer a close | 6 failures |
| The system command's low bits are compared too | 1 |
| Any window's close is taken | 1 |
| A close with no dialog open is taken as well | 1 |
| A modal window this window does not own is closed | 1 |
| Ownership is only one level deep | 1 |
| Only the innermost dialog is closed | 4 |
| A dialog that refuses is asked until the bound runs out | 1 |
| The window is hidden rather than closed | 1 |
| Every native event is read as an `MSG` | the run dies reading address 0 as an `MSG` |
| Qt's own type for the event name is not recognised | 2 |
| The name as plain bytes is not recognised | 2 |
| Anything at all counts as a Windows message | the run dies the same way |
| The filter is installed on every platform | 3 |
| The platform it reads by default is not the running one | 1 |
| A second installation adds a second filter | 2 |
| The filter is not a child of the window | 3 |
| Composition never installs it | 1 |

Two of them kill the test process rather than failing an assertion: both make the filter read an
arbitrary address as a `MSG`, and `ctypes.wintypes` does not exist off Windows. That is a failure
either way, and it is recorded as what it is rather than as a clean assertion.

## Two things measured rather than assumed

- **`QWidget.isAncestorOf` will not answer whether a dialog belongs to a window.** It requires both
  widgets to be *within the same window*, and a dialog is a window of its own, so it reported
  false for exactly the case this rule has to recognise. The first version used it and no dialog
  was ever recognised as the window's own. `owned_by` walks the parent chain instead.
- **Qt removes a native event filter when the filter is destroyed.**
  [Qt's own documentation](https://doc.qt.io/qt-6/qabstractnativeeventfilter.html) for
  `~QAbstractNativeEventFilter`: *"Destroys the native event filter. This automatically removes it
  from the application."* So the filter is a child of the window it serves and nothing is connected
  to `destroyed` — a callable holding the filter, held in turn by the window, is the Python
  reference cycle around a widget that `T-289` forbids.

## The Windows measurement

`tests/ui/test_windows_desktop.py` gained two parametrized tests, four cases in total. They run on
`STARBASE` in the `windows desktop` job, which is where a real `HWND` and a real shell message
exist. **They post the message Windows itself would post** and assert on what happens:

1. `test_windows_disables_the_window_a_dialog_blocks_and_drops_its_close` — the **positive**: with
   nothing installed, Windows reports the owner disabled and the window stays open. Without this,
   the test below could pass on a machine where the defect never existed.
2. `test_the_taskbar_close_closes_the_dialog_and_the_application` — with the filter installed, the
   same message closes the dialog and the window.

### First attempt, `270ce3a`: the job went red before the suite ran

Run [`35264831884`](https://github.com/kottmans/tracks-and-trails/actions/runs/35264831884), the
`windows desktop` job: **failed at *Types under the Windows platform***, so the desktop suite never
started and no measurement came back.

**What failed, and why it could not have passed:** `close_from_the_taskbar` branched on
`sys.platform` inline. `mypy` narrows that, so *one* of the two runs always read a branch as dead
code — `mypy src` on Linux called the Windows branch unreachable, and `mypy --platform win32`
called `return None` unreachable. Writing it as the positive branch satisfied the Linux run, which
is the one this machine can see, and that is exactly the check `--platform win32` exists to add.

**The fix is the pattern `ui/reveal.py` already documents**: the platform is a parameter with
`sys.platform` as its default. Both branches then typecheck under both runs, **and the off-Windows
answer is asserted by the ordinary suite on any machine** rather than by a `skipif`. A test pins
the default to `sys.platform`, because the parameter's whole production behaviour is that default.

*(Recorded rather than quietly amended: the pushed commit's job is red in the history, and this is
what it was.)*

### Second attempt, `36cdd69`: the defect is confirmed, and the fix was broken

Run [`35267703210`](https://github.com/kottmans/tracks-and-trails/actions/runs/35267703210), the
`windows desktop` job. The suite ran this time:

| Test | Result |
|---|---|
| `test_windows_disables_the_window_a_dialog_blocks_and_drops_its_close[WM_CLOSE]` | **PASSED** |
| `test_windows_disables_the_window_a_dialog_blocks_and_drops_its_close[SC_CLOSE]` | **PASSED** |
| `test_the_taskbar_close_closes_the_dialog_and_the_application[WM_CLOSE]` | **FAILED**, then the process crashed |
| `test_the_taskbar_close_closes_the_dialog_and_the_application[SC_CLOSE]` | never ran |
| `test_the_application_launches_on_a_real_windows_desktop` | **FAILED** |

**The report is confirmed on the runner.** With nothing installed, Windows reports the dialog's
owner disabled and drops both forms of the close. That is the positive this file needed, and it is
now a test rather than a one-off reproduction.

**The fix did not work, and the run crashed.** `pytest` never printed its summary — exit code 139,
*Windows fatal exception: access violation* — so the assertion texts are lost. What the crash
trace does say is where it happened: `Garbage-collecting`, inside
`qt_lifecycle.widgets_the_collector_would_destroy`, from the `T-289` boundary guard in
`tests/ui/conftest.py`. Two defects, both then measured rather than guessed at:

**1. The pointer Qt passes is a `VoidPtr`, not an `int`.** PySide6's own stub types
`nativeEventFilter`'s `message` as `int`; a probe under the `xcb` plugin **on this machine** shows
what a filter is really handed:

```
event_type type: ['QByteArray']
event_type value: ["b'xcb_generic_event_t'"]
message type: ['VoidPtr']
message repr: ['shiboken6.Shiboken.VoidPtr(0x55fd908b1e3…']
```

`wintypes.MSG.from_address(<VoidPtr>)` raises `TypeError`, and `a_windows_message` is true for
**every** Windows message, so the filter raised on every message the application received. That is
both failures: the taskbar's close did nothing, and the application's own launch test failed.
`int()` gives the address for either spelling.

**2. The filter held a Python reference to its window.** `self._owner = owner`, on a `QObject`
whose parent *is* that window, closes a loop through Qt's own ownership — the shape `T-289`
forbids. The crash was inside the guard that looks for that shape, at that test's teardown. The
filter now reaches its window through `self.parent()`.

**The causation is not claimed.** The reference was forbidden and is gone; whether it was what
crashed the process is answered by the next Windows run, not by this file.

**Neither defect was visible from this machine before, and one of them still is not.**

- **The pointer is now covered offscreen.** Its Python type is not Windows-specific, so
  `nativeEventFilter` is driven end to end with a `QByteArray` name and a real `VoidPtr` over a
  `MSG` built in memory. `Message` is written out in the module so that is possible at all, and a
  Windows-only test pins its field offsets against `ctypes.wintypes.MSG`.
- **The reference is checked directly, because the collector guard does not see it here.** The
  first version of that test built the state and asked
  `qt_lifecycle.widgets_the_collector_would_destroy` — and **passed with the reference put back**,
  under both mutations that restore it. A test built on it would have been decoration. What is
  asserted instead is the rule the module states: the filter's own attributes hold no `QWidget`,
  and it can still reach its window.

### The measurement

**Still owed**: the fix half of the table above, on a job that gets to the end. It goes here with
its run id, and `T-343`'s acceptance criterion is that rather than any sentence here.
