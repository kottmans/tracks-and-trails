# `T-347` — what raises a Dolphin window that already shows the folder

**Date:** 2026-09-18 (measured overnight, by the maintainer's permission to drive their desktop)
**Task:** `T-347`, Phase 4.5 stage 1
**Machine:** the development host, Fedora 44, KDE Plasma on Wayland — **the desktop the report came
from**, which is why this could be measured at all: no runner has Plasma, CI is headless and
`STARBASE` is Windows.

## The instrument, and the first version of it that was wrong

Dolphin publishes `org.kde.dolphin.MainWindow` on the session bus, which answers **`isActiveWindow`**
and **`isUrlOpen`**. So "did the window come to the front" is a textual measurement rather than a
person looking at a screen. `dolphin --daemon` has no main window and is skipped, which is also how
the maintainer's own long-running instance is left alone.

**The first measurement was unsound and said the defect was reproduced anyway.** It asked *one*
instance whether it was active while `ShowItems` had launched a *second* window
(`dolphin --new-window --select`): a window that is not the one being asked can be the one in
front, so "not active" said nothing. Every measurement below enumerates **every** Dolphin window
before and after the call, and a route counts only if the window that **already** showed the folder
becomes the active one.

The window that takes focus first is one the probe owns, a Qt window shown and activated, so
Dolphin is demonstrably behind something when the route is fired.

## The report, reproduced

| | |
|---|---|
| A Dolphin window showing the folder | `isUrlOpen` → true |
| Our own window in front | Dolphin `isActiveWindow` → false |
| **After `ShowItems`, the call the application makes today** | **`isActiveWindow` → false**, and no new window |

That is the maintainer's report as a measurement: the item is selected in the window that is
already there, and the window stays behind.

## Every route tried

| Route | Raises the existing window | Selects the file | Cost |
|---|---|---|---|
| `FileManager1.ShowItems`, as shipped | **no** | yes | the report |
| `portal OpenURI.OpenDirectory` | **no**, and it opened a new window | no, the folder only | a window per call, and the selection is lost |
| `dolphin --select`, a second process | **no** | yes | none, and no effect |
| `xdg-open` the folder | **no** | no | none, and no effect |
| `dolphin --new-window --select` | n/a — **the new window is active** | yes | a second window every time |
| **`KWin.WindowsRunner.Run`** | **yes**, false → true | yes, `ShowItems` does the selecting | KDE only, and it finds the window by matching text |

**`Dolphin.activateWindow` takes an activation token** (`activateWindow(s activationToken)`), and an
empty one does nothing: measured, `isActiveWindow` stayed false. That is the underlying rule rather
than a Dolphin quirk — on Wayland only an application that holds user focus can hand activation to
another, and **PySide6 exposes no way to obtain a token**: `xdg_activation_v1` lives behind Qt's
private Wayland interfaces.

**Two corrections to my own probes**, both found by re-reading output rather than by the tests:

- `WindowsRunner` was first reported as *"no window matched"*. It matched perfectly; the id is
  shaped `0_{uuid}` and the regex expected quotes that `dbus-send --print-reply=literal` does not
  print. The route was never run. Re-run with the id parsed correctly, it raises the window.
- The portal route was first measured against a stale instance, for the reason in the instrument
  section above.

## What `WindowsRunner` matches

```
query 'downloads' → 0_{0b2444a6-…}  "downloads — Dolphin"  org.kde.dolphin  relevance 0.8
query 'dolphin'   → the same window, relevance 0.7
query 'clip'      → nothing
```

Each match carries the **application id** (`org.kde.dolphin`) beside the title, so a caller can
filter on the application and not only on words in a title. That matters for the proposal: matching
on title text alone would pick the wrong window the moment two windows read alike.

## What this leaves for the maintainer

The correct fix — a token passed to `ShowItems` as its startup id — is not available from this
toolkit. Three shapes are, and the choice is a ruling rather than an implementation detail. They are
written up in `T-347`'s entry with what each costs.
