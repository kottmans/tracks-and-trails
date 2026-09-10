# The startup warning on a real compositor — Wayland and X11, 2026-09-09

**Taken:** 2026-09-09 on `Spock`, Fedora 44, KDE. **Head:** the working tree at `e47f17f` plus
`T308-R2`'s extraction of `app.present`.
**Required by:** `T308-R1`. **Ran:** `tools/t308_warning_stacking_probe.py`, twice.
**Profile:** an isolated `XDG_CONFIG_HOME` whose `settings.toml` names a folder that does not
exist, so the warning fires the way it did for the maintainer. Nothing in the real profile is read
or written.

---

## What ran

`app.present(composition)` — the production sequence `run()` calls — against the real display,
after `compose()` carried the problem. Not `run()` itself, which builds its own `QApplication`.

| | **Wayland** | **X11 (`xcb`)** |
|---|---|---|
| Platform reported by Qt | `wayland` | `xcb` |
| Settings problem carried | yes | yes |
| Window shown | **yes** | **yes** |
| Dialog visible | **yes** | **yes** |
| Dialog **exposed** (native surface mapped) | **yes** | **yes** |
| Dialog **active** | **yes** | **yes** |
| Modality | `WindowModal` | `WindowModal` |
| **Transient parent is the window** | **yes** | **yes** |
| Dialog geometry | `(220, 150, 500, 260)` | `(220, 150, 500, 260)` |
| Window geometry | `(0, 0, 960, 640)` | `(480, 211, 960, 640)` |
| Its `OK` button activates and closes it | **yes** | **yes** |
| Window enabled afterwards | **yes** | **yes** |

On both platforms the dialog is centred inside the window's own rectangle, exposed and focused, and
owned by the window as a transient — which is the relationship a compositor keeps above its parent.

## What this establishes

**The corrected ordering behaves on both compositors.** The dialog's native surface is mapped and
focused *after* the window exists, it is a transient of that window, it can be dismissed by its own
default button, and the window is usable once it is gone.

## What this does not establish

- **Stacking order is not read here, and cannot be from inside the client on Wayland.** Exposure,
  activation and transient parentage are the strongest facts available in-process; they are the
  conditions under which a compositor raises a dialog, not an observation that it did.
- **Whether a person would find it.** `T308-R1` asks whether the warning "appears above its parent"
  as seen, and that is perceptual. It stays with the maintainer.
- **KDE only.** One compositor on Wayland and one window manager on X11, both KDE's. GNOME, wlroots
  and others are unmeasured. `T-288` is why that is written down: a Wayland-only behaviour is
  invisible from a headless run, and by the same argument a KDE-only one is invisible from this one.

---

## Amendment, 2026-09-09 — two corrections to the record above

**The measurements above are unchanged.** What follows corrects two claims made around them.

### The isolation claim was false, and `T308-R3` is why

The tool replaced `XDG_CONFIG_HOME` but used `setdefault` for the data and cache roots, so an
**inherited** `XDG_DATA_HOME` would have survived while this record said the profile was isolated.
`compose()` opens that database and runs `JobRepository.recover_interrupted()` before any window
appears — a reviewer reproduced it against a temporary canary and watched a stored job go from
`RUNNING` to `FAILED / INTERRUPTED`, with the tool exiting `0`.

**On the machine these measurements were taken, it did not fire, and that is checkable rather than
asserted.** `XDG_DATA_HOME` and `XDG_CACHE_HOME` were both unset in that shell, so `setdefault`
supplied the temporary profile; the real database at `~/.local/share/tracksandtrails/library.sqlite3`
carries an mtime of **2026-09-03**, six days before this run. Nothing here reached it. **That is
luck about one environment, not a property of the tool**, which is exactly the finding.

The tool now sets all four XDG roots unconditionally, resolves `db.database_path()` and
`paths.cache_directory()`, prints them, and **refuses to compose anything** if either lands outside
the temporary profile. `test_the_stacking_probe_cannot_reach_an_inherited_profile` keeps the
reviewer's canary reproduction; removing both the unconditional roots and the refusal makes it fail.

### "Centred inside its parent" was wrong on X11

The table above reports the dialog at `(220, 150, 500, 260)` on both platforms, and the window at
`(0, 0, 960, 640)` on Wayland but `(480, 211, 960, 640)` on X11. **On X11 the dialog's coordinates
are therefore not inside the window's rectangle**, and the sentence claiming it was centred in its
parent does not follow from the numbers printed beside it. The coordinate spaces differ — Wayland
gives a client no global position — so the two rows are not comparable in the way that sentence
assumed. What the measurements support is exposure, activation and transient parentage; position
relative to the parent is **not established on either platform**.

### What still is not done

`T308-R1` asks for a **visual** observation and **normal input**. The probe activates the default
button through `QAbstractButton.click()`, which is a call rather than a click: it does not
demonstrate that pointer or keyboard input reaches the dialog, nor that a person looking at the
screen finds it. Neither is available from inside the client, and that half remains open.

---

## Second amendment, 2026-09-09 — the visual half of `T308-R1`, observed

**Method.** An isolated profile as above, `compose()` then `present()`, the window held up for
twelve seconds, and the **composited desktop** photographed with `spectacle` — once in the session's
native Wayland and once with `QT_QPA_PLATFORM=xcb`. The captures were then read.

| | **Wayland** | **X11 (`xcb`)** |
|---|---|---|
| The warning is drawn **over** the main window | **yes** | **yes** |
| Centred within the window's visible rectangle | **yes** | **yes** |
| The main window is visible around it, not hidden | yes | yes |
| Its own titlebar and `OK` button are drawn | yes | yes |
| The corrected `T-309` text is what is rendered | yes | yes |

Both captures show *"Some of your settings could not be used as written, so they have been
adjusted. The rest of the file is unchanged"*, the profile path, *"The folder named in your
settings was …/gone/nowhere"*, and *"Change them in Settings to stop this message."* — so the
`T-309` corrections are confirmed as rendered rather than only as composed strings.

**This supersedes the first amendment's "position relative to the parent is not established".** It
is established, on both platforms, by looking: the earlier conclusion came from comparing
coordinates across two coordinate spaces that are not comparable, and a photograph does not have
that problem.

**The images are deliberately not committed.** They are full-desktop captures and contain unrelated
application windows belonging to the maintainer; this repository is public. The observation is
recorded here instead. A cropped capture of the application alone could be committed if the record
wants a picture.

## What remains open in `T308-R1`

**Normal input.** No input-injection tool is installed on this machine — `xdotool`, `ydotool` and
`wtype` are all absent — so pointer and keyboard events cannot be delivered through the display
server. `QAbstractButton.click()` remains a call, not a click. **Whether real input reaches the
dialog and the window behind it is still unobserved**, and installing a tool to inject it is a
change to the maintainer's machine rather than something to do unasked.

---

## Third amendment, 2026-09-09 — normal input, on X11

`xdotool` was installed at the maintainer's hand after the second amendment recorded its absence,
which makes **XTEST** input available: events delivered by the X server itself, not synthesised
inside the client.

**Sequence, on `QT_QPA_PLATFORM=xcb`, isolated profile as before.**

| Step | Real input | Observed |
|---|---|---|
| Locate the windows | — | Two: main at `480,211 960x640`, dialog at `220,150 500x260` |
| Activate the dialog and press `Return` | `xdotool key --clearmodifiers Return` | `xdotool search --onlyvisible` then lists **only the main window** |
| Photograph | — | The warning is gone; the main window is drawn in its normal empty state — *"Nothing queued. Use File > Add URLs… to add a download"*, both status lines present |
| Click in the main window | `xdotool mousemove --sync … click 1` | **The `+ Add URLs` dialog opened**, fully rendered: URL field, *"What you pasted"*, preset `Best video available`, `192 kbps`, the effective format selector, and its own buttons |

**All three clauses of `T308-R1` are therefore observed on X11**: the warning appears above its
parent, it is dismissed by real keyboard input, and the main window takes real pointer input
afterwards. The click was aimed at the `File` menu and landed on `+ Add URLs`; that it opened a
working dialog is the stronger result, so the aim is recorded rather than corrected.

**Wayland is observed for stacking only.** Its input half is still not done: `ydotool` and `wtype`
remain absent, and Wayland gives a client no way to inject events. Closing it needs `ydotool` with
`uinput` permissions, or a person at the keyboard.

---

## Fourth amendment, 2026-09-09 — the Wayland observation, by the maintainer

**Reported by the maintainer**, running the application himself on his own Wayland session with a
throwaway profile whose `[downloads] directory` names a folder that does not exist. **This is his
observation, not a measurement taken here**, and it is recorded as such because `T308-R1` asks
whether *a person* can see and dismiss the warning — which is a question no probe can answer.

Asked the three clauses the finding names, the answer was **yes to all three**:

| Clause | Wayland, as observed |
|---|---|
| The warning is visible above the window rather than needing to be hunted for | **yes** |
| Clicking `OK` or pressing `Return` dismisses it | **yes** |
| The main window responds to input afterwards | **yes** |

**With the X11 results in the third amendment, `T308-R1`'s three clauses are now observed on both
platforms** — synthetically on X11 through XTEST, and by a person on Wayland.

**`ydotool` was installed and removed again during this.** Its daemon's socket is root-only at
`/tmp/.ydotool_socket` while its client looks in `$XDG_RUNTIME_DIR`, and closing that gap means
making an input-injection socket world-writable — a wider hole than the one being closed, on a
machine whose repository is public. It was not done. A person pressing `Return` was the cheaper and
better evidence, and it is the evidence the criterion actually asked for.
