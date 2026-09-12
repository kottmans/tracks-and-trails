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

## Windows — cold, after a reboot

Taken by the maintainer seconds after `Restart-Computer`, before anything else was launched. This
is the measurement `T-325` defines as cold, and the only one neither the implementer nor CI can
take: a reboot kills the `STARBASE` runner and the session driving it.

```
  run 1  3.976s
OVER THE BOUND: 3.976s against NFR-002's 3.0s.
```

**One run, deliberately.** A second launch is no longer cold, so the sample size is one by
construction and five runs would have been four warm ones averaged into it.

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

**Correction, 2026-09-12: this section first read *"`NFR-002` is not met on Windows"*. That
overstated it.** `NFR-002` reads *"under 3 seconds on the reference **Linux** machine"* and has
never covered Windows; `TESTING.md` §8 item 14 said *"the reference machine"*, dropping the word,
which is how a Windows figure came to be reported against a Linux requirement. **Linux passes
`NFR-002` with roughly five times the margin.** The real defect was the gate item disagreeing with
the requirement it cites. Both are fixed, and Windows now has its own bound in `NFR-010`
([`REL-008`](../DECISIONS.md#rel-008--windows-gets-its-own-startup-number-and-linuxs-stays-where-it-is)).

**Windows cold start is 3.976 s**, the third independent first-launch figure over three seconds — 3.780 s and 4.656 s
on freshly built artifacts, 3.976 s after a reboot. Warm is 1.55 s and was never the question.

| Windows | seconds | `NFR-010` (5 s) |
|---|---|---|
| cold, after reboot | **3.976** | within |
| first launch, freshly built | 3.780, **4.656** | within |
| warm | 1.550 | within |

**Five seconds, not four, and the difference is the point**: 4 s would clear the cold figure by
24 ms. That is a coin toss on a busy machine, not a bound.

**Linux is not in question**: 0.634 s warm, 1.077 s first-touch, against 3 s. Its cold number was
not taken — that needs a reboot of the machine this work runs on — but the gap is large enough
that nothing turns on it.

`T-325` says the honest outcomes are *meets*, *does not meet and here is the profile*, or a
maintainer amendment with the reason. **The ruling was the third**, taken 2026-09-12 and recorded
as `REL-008`: `NFR-002` stays Linux-only, `NFR-010` adds a 5-second Windows bound measured on the
installed artifact at first launch after a reboot, and §8 item 14 names both platforms.

**Both platforms now meet their own number, and each number came from a measurement on that
platform** rather than one figure chosen for neither.

**One measurement is still missing and is not inferred away**: Linux cold, which needs a reboot of
the machine doing the work. Warm 0.634 s and first-touch 1.077 s against 3 s make it unlikely to
matter — that is an inference, and it is written as one.
