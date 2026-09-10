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
