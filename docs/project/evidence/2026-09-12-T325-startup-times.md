# `NFR-002` startup, measured on both artifacts — 2026-09-12 (`T-325`)

**Why this is here rather than only in the task:** four five-run sets on two machines whose state
at the time cannot be reconstructed, and the first run of each set is the number the task turns on.
The *harness* is regenerable and lives in `tools/startup_time.py`; only the captures live here,
which is this directory's own rule.

## How it was measured

**Not a stopwatch** (`T-325` asks for that in terms). `tools/startup_time.py` takes wall clock
before spawning; the application writes its own wall clock when the compositor confirms the surface
is on screen — `core.startup.record_first_paint`, riding the exposure watch `T287-R1` installed.
`showEvent` is deliberately *not* the hook: it fires before the window exists on screen, and on
Wayland the widget is never told at all.

Each run gets a fresh profile (`XDG_*` / `WIN_PD_OVERRIDE_*`), so no launch measures a machine that
already has the user's settings, geometry or database. Every artifact below was built from the tree
that carries the recorder, not from an earlier one.

## Linux — the AppImage, on the reference machine

Fedora, KWin/Wayland, `DISPLAY=:0`. `Tracks_and_Trails-0.1.0.dev0-x86_64.AppImage`, 66 MB.

| Run | Seconds |
|---|---|
| 1 | **1.077** |
| 2 | 0.667 |
| 3 | 0.569 |
| 4 | 0.630 |
| 5 | 0.634 |

**Median 0.634 s.** From source on the same machine, for comparison: **0.318 / 0.343 s** — so
freezing costs about **1.9×**, against the 2–4× `T-325`'s Risk line anticipated. Real in
direction, immaterial in absolute terms.

## Windows — the release build, on `STARBASE`

`TT_RELEASE_BUILD=1`, run in the logged-on session via `tools/windows/run-on-starbase.sh` — session
0 has no window station, so an SSH launch would not be measuring a window at all.

**Three five-run passes.** The first two are one build; the third is a rebuild from the current
tree.

| Run | Pass 1 (fresh build) | Pass 2 (same files) | Pass 3 (fresh build) |
|---|---|---|---|
| 1 | **3.780** | 1.514 | **4.656** |
| 2 | 1.591 | 1.573 | 1.428 |
| 3 | 1.562 | 1.564 | 1.457 |
| 4 | 1.514 | 1.494 | 1.550 |
| 5 | 1.563 | 1.536 | 1.574 |
| **median** | 1.563 | 1.536 | 1.550 |

## The finding

**Warm meets `NFR-002` on both platforms, with room**: 0.634 s and 1.55 s against 3 s. Windows is
about 2.4× Linux, which is unsurprising and not close to the bound.

**The first launch of a freshly written Windows artifact does not meet it, and that is
reproducible.** Two independent builds: **3.780 s** and **4.656 s**, both over the 3 s bound. Pass
2 — the same files, minutes later — has no outlier at all, so this is a first-touch cost rather
than run-to-run variance. Defender scanning a newly written 155 MB tree and a cold page cache are
the obvious candidates; **neither was isolated**, and saying which it is would be a guess.

**Linux shows the same shape and stays inside the bound**: 1.077 s first against 0.634 s warm, a
comparable ~1.7× penalty on a much smaller number.

**Why the first-launch figure is the one that matters.** It is not a laboratory artefact — it is
precisely the state a user's machine is in immediately after an installer has written the files.
`T-325` asks for *cold*, defined as first launch after a reboot; that is a different clearing of
the same caches, and it was **not measured** because a reboot kills the `STARBASE` runner and
Linux's `drop_caches` needs root.

**So `NFR-002`'s status is: warm met on both platforms; first-launch-after-write over the bound on
Windows, twice; cold-after-reboot unmeasured.** `T-325` says the honest outcomes are *meets*,
*does not meet and here is the profile*, or a maintainer amendment of the number with the reason.
This is the second of those for the case a user actually meets, and it is not the implementer's to
resolve: the options are to accept 3 s as a warm-start bound and say so, to amend the number, or to
attack the first-launch cost (a Defender exclusion is not something an artifact can arrange for
itself).
