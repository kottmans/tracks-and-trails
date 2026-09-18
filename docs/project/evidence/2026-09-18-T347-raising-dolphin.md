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

## Built, and measured through the application's own function

The ruled route is in `ui/reveal.py`: after `ShowItems`, and only when a Dolphin instance already
has the folder open, ask KWin to activate **that instance's** window — found by `pid`, never by
title text or icon name. Everything that can be absent answers "no" and leaves the behaviour as it
was.

**Verified by calling `reveal_file` itself on the real desktop**, not by re-running the probe's own
version of the route:

| Case, with our window in front | Before | `reveal_file` | After |
|---|---|---|---|
| a window shows the folder, behind | `active: False` | returned `None`, meaning launched | **`active: True`** |
| a window shows the folder, minimized | `active: False, minimized: true` | returned `None` | **`active: True, minimized: false`** |

So the window is both raised and restored, which is the acceptance criterion for the case that was
failing. The other two cases open a new window that is already in front, and the route declines
there because no instance had the folder open — measured in the four-case table above.

**The offscreen half is `tests/ui/test_reveal_raises.py`**: the argv, the identity rule and every
path that declines, with the `Spawner` seam answering the D-Bus questions. Five mutations, all
caught, including "the first match wins" and "an error reply is read as a yes" — the second needed
an error message quoting a folder named `true`, because without one the guard could not fail.

## The review's six findings, and what each changed

`T347-R1` to `R5` and `T184-R4`, 2026-09-18. Three were High and one of them was a hazard rather
than a defect.

**`T347-R3`, the wrong action.** `Match` ids were read by scanning the **whole** reply, and the
matched id was handed to `Run` unchanged. KWin's runner reads the action out of that id:
`0` activates, **`1` closes**. A window whose *caption* contained `1_{uuid}` was therefore enough to
turn *Show in folder* into a request to close a window. Ids are read as record members now, only
activation records are candidates, and **the action is this module's own constant** — nothing
captured is passed through. The test for it uses the reviewer's counterexample, and the mutation
that restores the old whole-reply scan fails it.

*(My first mutation of that rule was **inert** and reported "caught" for the wrong reason: within a
record the genuine id always comes first, so per-record scanning finds it either way. The mutation
that means something is the exact pre-correction implementation.)*

**`T347-R4`, the GUI thread.** Every question was a blocking `subprocess.run` from a Qt slot, with
the **launch** timeout of ten seconds each. A stalled Dolphin could freeze the application for the
length of the whole sequence, which `NFR-001` does not allow. `reveal_file` no longer raises
anything; `ui/file_actions.py` runs the raise on a `QThreadPool` worker that holds no widget, and
discovery uses a **one second** per-question timeout, because a question nobody asked for does not
deserve a launch's patience.

**`T347-R1`, ambiguity.** `isUrlOpen(folder)` was the wrong question: several instances can have a
folder open, and the reveal went to exactly one of them. Dolphin picks its recipient by walking from
the active window and testing item visibility. The question is now
`isItemVisibleInAnyView(file)` — the nearest thing this application can ask — and **more than one
answer declines** rather than raising a window that may be showing a different tab.

**`T347-R5`, the Windows job.** The tests asked the *running machine* whether `dbus-send` exists, so
the same test asserted one thing on Linux and another on Windows, and the Windows job failed. The
availability is a seam now, like `platform`.

**`T184-R4`, the ear.** The drawn row gained a cancellation reason and the **spoken** row did not,
so a screen-reader user was told a job was cancelled and never why. The accessible text calls the
same `_cancellation_detail`, tested across foreign, default, empty and multiline reasons through
the real model roles.

## The four cases through the shipped functions

`T347-R2` asked for the production route to have a retained, runnable invocation. It does:

    PYTHONPATH=tools python -m dolphin_raise_probe --folder <…> --raise-route production

which calls `reveal_file` and `raise_the_file_manager` themselves. The full output is
[`2026-09-18-T347-production-route.txt`](2026-09-18-T347-production-route.txt); in summary:

| Case | Precondition | After the application's own call |
|---|---|---|
| 1. nothing open | established: no Dolphin window at all | a new window, **active** |
| 2. a window open elsewhere | established: it shows no folder | a new window, active; the first untouched |
| 3. shows the folder, behind ours | established: behind **and not minimized** | **`active: False → True`** |
| 4. shows the folder, minimized | `minimized, and KWin agrees` | **`minimized: true → false`, `active: True`** |

**Three corrections to the probe itself**, all from `T347-R2`:

- **Preconditions ask about the window the probe opened**, not about the room. Asking the room let
  case 4 accept an unrelated minimized window and case 3 accept a minimized target — so the two
  cases this task turns on were not distinguishable from the record.
- **Minimization is scoped to the probe's own process ids** and **waits until KWin reports it**
  before unloading the script. It minimized every Dolphin window while its own message said
  otherwise, and it unloaded before waiting — which is the ordering the previous evidence claimed
  was already corrected and was not.
- A loop variable named `minimize` shadowed the function `minimize`, so case 4 called a boolean and
  the run died there. The first attempt sent stderr to `/dev/null`, which is why it took a second
  run to say so.

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
