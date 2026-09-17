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

### The measurement

**Not yet run at the time of writing.** The result goes here, with the run id, once the job has
been through it, and `T-343`'s acceptance criterion is that table rather than this sentence.
