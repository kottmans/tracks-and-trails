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
| **`KWin.WindowsRunner.Run`** | **yes**, false → true, and it un-minimizes | yes, `ShowItems` does the selecting | KDE only. Candidates come from matching text; **identity comes from `pid`** |

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

**That third member is `iconName`, not an application id** (`T347-R1`, correcting this file).
`Match` returns `a(sssuda{sv})` — `(id, text, iconName, categoryRelevance, relevance, properties)` —
and KWin fills it from `window->icon().name()`. It reads `org.kde.dolphin` because KDE names icons
after desktop ids; an icon can be shared or changed, and filtering on it would not tell two Dolphin
windows apart at all.

**Identity comes from `getWindowInfo`.** The match id embeds KWin's window uuid, and
`org.kde.KWin.getWindowInfo(uuid)` answers `pid`, `resourceClass`, `desktopFile` and `minimized`.
Dolphin's bus name **is** `org.kde.dolphin-<pid>`, so the instance that answered `isUrlOpen` ties to
exactly one KWin window. The text query only generates candidates; `pid` picks among them.

## The four cases, with a retained probe (`T347-R2`)

`tools/dolphin_raise_probe.py` performs them and prints before and after for **every** Dolphin
window. Re-runnable:

    PYTHONPATH=tools python -m dolphin_raise_probe --folder <a folder holding one file>
    PYTHONPATH=tools python -m dolphin_raise_probe --folder <…> --raise-route windowsrunner

**Each case states whether its precondition held**, which is the half the first record lacked. That
check immediately caught two cases that were not what they claimed:

- *"Open on another folder"* was not: **Dolphin restores its previous tabs**, so a window opened
  elsewhere still had the target folder open and `isUrlOpen` answered **true** before the reveal.
  The probe now starts Dolphin with a per-run `XDG_CONFIG_HOME`, and measured both ways: with the
  operator's profile the answer is true, with a fresh one it is false.
- *"Nothing open"* was not, because windows `ShowItems` itself spawns were left behind between
  cases. The probe now closes every window **this run caused** and nothing that was open before it.

| Case | Precondition | `ShowItems` today | With `WindowsRunner` |
|---|---|---|---|
| 1. nothing open | established | a **new** window, active, item visible | unchanged |
| 2. a window open elsewhere | established | a **new** window, active; the existing one untouched | unchanged |
| 3. a window shows the folder, behind ours | established | **nothing changes** — not raised | **active: true** |
| 4. a window shows the folder, minimized | established | **nothing changes** — stays minimized | **active: true, minimized: false** |

**The report's own table needed correcting, and this is how.** It grouped *"open on another folder,
or minimized"* as the case that works. Measured, the dividing line is not behind-versus-minimized:
it is **whether a window already shows that folder**. When none does, `ShowItems` opens a new window
and that window is in front (cases 1 and 2). When one does, it is reused and left exactly where it
was, whether behind (3) or minimized (4). That matches what the maintainer said afterwards —
*"It only stays collapsed on the taskbar if the downloads folder is already open"* — and not what
the first table said.

**The minimized case is measured rather than narrowed away.** Nothing on Dolphin's interface
minimizes a window and a Wayland client cannot minimize somebody else's, so the probe uses KWin
scripting. Unloading the script immediately after `run` left every window un-minimized while
reporting success; it now settles first.

## What the instruments cannot say

Stated because `T347-R2` asked for the claim to be narrowed to what is observable:

| Instrument | Answers | Does **not** answer |
|---|---|---|
| `isActiveWindow` | whether that window is active | whether a non-active window is behind another or minimized |
| `getWindowInfo(uuid)` | `minimized`, and the `pid` that identifies the window | — |
| `isUrlOpen(folder)` | whether **the instance** has that folder open, in any tab or view | what the window is currently showing |
| `isItemVisibleInAnyView(file)` | whether the item is shown in a view | whether it is **selected** |

**So "with the file selected" is not machine-observable here.** The probe establishes that the
window came to the front showing the item; that it is highlighted is left to the person doing the
end-of-phase walk, and neither the task entry nor this file claims otherwise.

## What this leaves for the maintainer

The correct fix — a token passed to `ShowItems` as its startup id — is not available from this
toolkit. Three shapes are, and the choice is a ruling rather than an implementation detail. They are
written up in `T-347`'s entry with what each costs.
