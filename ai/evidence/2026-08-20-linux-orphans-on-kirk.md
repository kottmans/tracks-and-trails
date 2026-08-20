# Two orphaned workers on `kirk` — Linux, 2026-08-20

Found while setting up `T-238`'s loaded-reproduction campaign, by noticing two long-lived
Python processes that were not mine. **Preserved, not reaped**, on the same reasoning
`T258-R4` and `T-268` apply to `3400`/`6924`: a live specimen is worth more than the
37 MB it costs, and killing it destroys the only inspectable instance.

Captured non-destructively: `/proc`, `ps`, and `eu-stack` (read-only). No debugger was
attached, nothing was signalled, and the project scanner was run in its report-only form.

> **Both processes ended between this capture and 2026-08-20T06:20:48Z, and this file is now the
> only record of them.** See *What became of them* at the bottom. Everything above is retained
> exactly as captured; nothing in it is revised by their ending.

## What they are

```
 432922    2139 Sun Aug 16 01:10:39 2026  332872        0    1  7500 S
 434366    2139 Sun Aug 16 01:12:15 2026  332777      157    2 29764 Sl
```

| | 432922 | 434366 |
|---|---|---|
| role | `multiprocessing.resource_tracker` | `multiprocessing.spawn_main`, `--multiprocessing-fork` |
| threads | **1** | 2 |
| CPU over ~3d20h | **0 s** | 157 s |
| blocked in | `anon_pipe_read` | `hrtimer_nanosleep` (`time.sleep`) |
| parent | **gone** — adopted by `systemd --user` (2139) | **gone** — same |
| cwd | the repository root | the repository root |

## The retention chain, which is the mechanism

Both hold **`pipe:[1629660]`**. `434366` is the worker; `432922` is the resource tracker
reading that pipe for EOF. **The sleeping worker holds the write end, so the tracker can never
see EOF and never exits.** One orphan is keeping the second alive.

**Which pipe this is matters, and the first version of this file did not say** (`T272-R1`). It is
the **resource-tracker channel**, not a spawn payload pipe. `popen_spawn_posix._launch()` obtains
`resource_tracker.getfd()` and passes it in the child's pass-FD set **independently of** the payload
`pipe_handle`, so a POSIX spawned worker holding the tracker's writer is **documented behaviour**.
The Windows pipe `T-268` reasons about is the payload one, created by `popen_spawn_win32` and
started with `bInheritHandles=False`. **Different channel, different platform, different pair.**

## Native stacks (`eu-stack`, read-only)

### 432922 — one thread, blocked reading its pipe
```
PID 432922 - process
TID 432922:
#0  0x00007fb61ce7654e __internal_syscall_cancel
#1  0x00007fb61ce76574 __syscall_cancel
#2  0x00007fb61cef045e read
#3  0x00007fb61d2cc634 _Py_read
#4  0x00007fb61d2e371e _io_FileIO_readinto.lto_priv.0
#5  0x00007fb61d218a24 PyObject_VectorcallMethod.constprop.0
#6  0x00007fb61d2e347e _bufferedreader_raw_read.lto_priv.0
#7  0x00007fb61d2e339e _bufferedreader_fill_buffer.lto_priv.0
#8  0x00007fb61d307fdb _buffered_readline.lto_priv.0
#9  0x00007fb61d313e48 buffered_iternext.lto_priv.0
#10 0x00007fb61d025e86 _PyEval_EvalFrameDefault.cold
#11 0x00007fb61d195d12 _PyEval_Vector.constprop.0
```

### 434366 — sleeping, plus a parked thread
```
PID 434366 - process
TID 434366:
#0  0x00007ff11c682312 __syscall_cancel_arch
#1  0x00007ff11c67652c __internal_syscall_cancel
#2  0x00007ff11c6c5c82 clock_nanosleep@GLIBC_2.2.5
#3  0x00007ff11cb516e0 time_sleep.lto_priv.0
#4  0x00007ff11c8304c6 _PyEval_EvalFrameDefault.cold
#5  0x00007ff11c995d12 _PyEval_Vector.constprop.0
```

## What the project scanner says

```
1 orphaned worker(s) — spawned, parent gone, still running:
  pid  434366  age 3d20h  dead parent    2139  threads 2  rss 30 MB
Reported, not reaped — see this module's docstring for why (`T258-R4`).
EXIT=1
```

**It finds it, on Linux, with no change.** `tools/orphan_scan.py` is `psutil` and carries no
Windows-specific path. It reports `434366` and not `432922`, correctly: `_SPAWN_MARKERS`
matches `spawn_main`/`--multiprocessing-fork`, and the tracker is neither — it is a
*consequence* of the orphan rather than one.

## What this is not

**It is not a counterexample to `T-258`'s POSIX measurement.** That claim is about the window
*before a spawned worker installs its watchdog* — a child stopped before it reads its payload.
**This worker used 157 s of CPU**, so it ran far past that window. Different state, same
outcome.

**It is not established as product-reachable.** These are children of a `multiprocessing`
parent that died, in a checkout used for test runs; a killed `pytest` session produces exactly
this. Which one it was is **not** recoverable from what is here — the parent is gone and took
its identity with it. That is the same product-versus-harness question `T-238` criterion 4 and
`T-074` both carry, and this does not answer it.

## What it does establish

1. **The phenomenon is not Windows-only.** An orphaned spawned worker of the class `T-258`
   built the scanner for exists on `kirk`, and had been there **3 days 20 hours** when it was
   found by accident — which is how the original five were found.
2. **Nobody was looking.** The `STARBASE orphans` job runs the scanner **only on the Windows
   runner**. The same scanner works here and is not scheduled here.
3. **A retention chain is directly observable here**, which on Windows it has never been: the
   worker holds the tracker's writer, so the tracker cannot reach EOF. That is a mechanism for
   *these two processes*, on POSIX, through the tracker channel.

**Withdrawn from the first version of this file** (`T272-R1`): it claimed the five's
**one-thread** shape was reproduced outside Windows, and that the mechanism visible here was the one
`T-268` eliminated. Both are false. The one thread and 0 s of CPU belong to the **`resource_tracker`**;
the **spawned worker** — the process `T-268` classifies — has **two threads and 157 s of CPU**. The
union of the two is not a process shape, and the tracker channel is not the payload channel `T-268`
eliminated a peer from. Nothing here bears on why the five looked as they did.

## What became of them

**Both are gone.** `ps -o pid,ppid,etime,nlwp,time,rss,stat,args -p 432922,434366` on `kirk` at
**2026-08-20T06:20:48Z** returns a header and no rows, and `tools/orphan_scan.py` reports
**`no orphaned workers found`, exit 0** where the capture above recorded one worker and exit 1.

**It was not a reboot.** `kirk` has been up since **2026-08-10 09:04:32**, 9 days 16 hours — the
specimens were created on 2026-08-16 and the host has not restarted since before that. **Nothing in
this session signalled them**; both scanner runs were report-only, and `--kill` does not exist.

**Why they exited is not established, and nothing here ranks the candidates** (`T272-R3`).

- **The worker's sleep elapsed.** `434366` was blocked in `hrtimer_nanosleep` — a `time.sleep`,
  which is **finite by construction**. This candidate is distinguished only by **requiring nothing
  outside the process**, which is a property of the candidate and **not evidence that it happened**.
  **Unverified**: no duration was recoverable from the capture, and a stack is not a cause.
- **Something outside ended it.** Another session on `kirk`, an OOM kill, or a user-level cleanup.
  **Neither observed nor excluded** — `kirk` is a shared working machine, and this cannot be
  recovered after the fact.

**So the record stops at what was seen: the PIDs are gone, the host did not reboot, and this
session signalled nothing.** Whether anybody else terminated, inspected or deliberately released
them is **unknown**, and no sentence in this file may assume otherwise.

**The tracker's exit follows from the mechanism this file already recorded**, whichever ended the
worker: `432922` was blocked reading `pipe:[1629660]` for EOF and `434366` held the write end, so
the worker's exit closes it and the tracker's read returns. That is an **inference from the recorded
retention chain**, not an observation — the order of the two deaths was not watched.

**What this costs and what it changes.**

- **No specimen remains available**, so `T-272`'s preservation criterion is **overtaken by events**
  rather than met or waived. That is a statement about **availability**, not about anybody's
  conduct (`T272-R3`): whether someone inspected or deliberately released them is **unknown**, and
  the earlier wording here — *"without anyone deciding to spend it"* — asserted an absence of
  intent this file's own evidence disclaims two paragraphs above.
- **This one did not persist indefinitely**, and that is worth stating against `T-258`'s title.
  On Linux, this pair was present and then, roughly **four days** later, absent. **Disappearance
  proves a finite lifetime, not its cause.** It says nothing about `3400` and `6924` on `STARBASE`,
  which are a different platform, a different channel and a different process shape — the
  distinction `T272-R1` required.
- **Nothing above is withdrawn.** The 3d20h existence, the scanner finding it unmodified on Linux,
  the absent Linux schedule, and the unproved product reachability are all observations of a window
  that closed; their ending does not reach back into them.
- **The scheduling gap `T-272` is filed for is unchanged, and this is what it looks like.** A
  scheduled Linux scan would have reported this pair on 2026-08-16. Nobody was looking, it was found
  by accident four days later, and the subject was gone within hours of being written up.
