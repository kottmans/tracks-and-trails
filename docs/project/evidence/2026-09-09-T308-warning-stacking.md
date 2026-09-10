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
