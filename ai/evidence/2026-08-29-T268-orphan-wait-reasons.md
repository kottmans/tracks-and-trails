# T-268 — what the seven `STARBASE` orphans are waiting on

**Taken:** 2026-08-29, run `33267794308`, `STARBASE orphan inspect`, read-only.
**Raw report:** `2026-08-29-T268-starbase-orphan-wait-reasons.txt` (as the machine wrote it).

**How this was taken without a person at the machine.** `T-268` has been *Blocked on a person at
`STARBASE`* since 2026-08-19. What it asks for is narrow — *"process and thread wait reason, or
suspend count… non-destructively, on the machine"* — and that needs **code running on** the machine
rather than hands on it. A self-hosted runner is code running on the machine. `T-092` remains
genuinely different: it needs WER configured, which changes how the machine behaves.

Read-only by construction: `Get-Process` and `Get-CimInstance` only. Nothing was terminated,
suspended or resumed, and all seven are preserved as `T268-R1` requires.

## The reading

All seven specimens, without exception:

| pid | created | parent | thread | state | **waitReason** | user ms |
|---|---|---|---|---|---|---|
| 3400 | 08/17 13:07:40 | 1204 | 8688 | 5 (Waiting) | **37** | 1406 |
| 6924 | 08/17 13:07:40 | 1204 | 2168 | 5 | **37** | 1437 |
| 2432 | 08/05 12:33:44 | 9176 | 3384 | 5 | **37** | 1656 |
| 3408 | 08/05 12:33:44 | 9176 | 7792 | 5 | **37** | 1640 |
| 11000 | 08/05 12:33:44 | 9176 | 8248 | 5 | **37** | 1812 |
| 7028 | 08/04 20:07:13 | 1052 | 2792 | 5 | **37** | 1671 |
| 10524 | 08/04 19:43:00 | 12144 | 6484 | 5 | **37** | 1859 |

## What this establishes

**1. The suspended-process candidate is refuted.** `T-268`'s answer ends by naming *"something
outside the interpreter — a suspended process"* as the one candidate its four eliminations leave,
and by saying that confirming or refuting it needs the machine. **Suspended is
`ThreadWaitReason=5` in every version of that enum — the raw one also has `12`, `WrSuspended` — and
not one of the seven reports either.** That candidate is now eliminated by measurement rather than
left standing by absence of evidence.

**The state column is not the discriminating one**, and reading it as such is how the first source
correction went wrong (`T268-R5`). `ThreadState=5` is `Waiting`; every one of the seven reports it,
and a suspended thread would report it too. The wait *reason* is what separates them.

**2. They are blocked on an in-process synchronisation primitive.** `37` is outside
`Win32_Thread.ThreadWaitReason`'s documented 0–13, so WMI is surfacing the raw kernel
`KWAIT_REASON`, in which **37 is `WrAlertByThreadId`** — the wait behind
`NtWaitForAlertByThreadId`, which is what `WaitOnAddress`, SRW locks, condition variables and
modern critical sections are built on. .NET's `ProcessThread.WaitReason` reporting `Unknown`
corroborates a value outside the documented set rather than contradicting it.

**That is a lock wait inside the process.** It is not a pipe read, and `T-268`'s structural
elimination of the payload reads is untouched and now agrees with a positive observation instead of
only with an absence.

**3. They got very much further than "blocked before the second load" suggests.** Every one has the
**full Qt stack resident** — `Qt6Core.dll`, `shiboken6.abi3.dll` and `pyside6.abi3.dll` in all
seven, `QtWidgets.pyd` and `QtTest.pyd` in six of them, 63–84 modules each. A child stalled in
`prepare()` re-importing a `pytest` parent's main module would not have imported PySide6's widget
and test bindings. **The region `T-268` bounded is the right region and its far end is much closer
to `prepare_this_worker()` than the entry supposed** — these processes completed a large import
graph and then stopped.

`threads=1` still holds and still bounds them before the watchdog, so the stall sits between
finishing those imports and starting `prepare_this_worker()`'s thread.

**4. Two independent same-second clusters, not one.** `T-268` records *"three of the five share a
parent and one second"*. There are two such events: `2432`/`3408`/`11000` under parent `9176` at
08/05 12:33:44, and `3400`/`6924` under parent `1204` at 08/17 13:07:40. **Siblings spawned together
blocking together on an in-process lock is what lock contention during concurrent import looks
like** — and it no longer needs a parent-side event outside the interpreter to explain the shared
second.

## What this does not establish

- **Which lock.** `WrAlertByThreadId` names the mechanism, not the object. CPython's import lock,
  a `shiboken`/Qt static initialiser, and an allocator lock are all consistent with it, and this
  reading does not separate them. A stack would; nothing here produces one.
- **Why the lock was never released.** A holder that died, a re-entrant acquisition, or a lock
  taken across a fork-like boundary are all candidates and none is measured.
- **That these are this project's processes.** The scanner does not prove ownership and this does
  not either — though the command lines are `multiprocessing.spawn` children of a Python that
  loaded PySide6, on the machine that runs this project's Windows jobs.

## What would settle it

A stack for one blocked thread. That *is* `T-092`'s territory — a dump needs WER or an attached
debugger, which is an administrative change to the machine — so the next step is genuinely the one
`T-268` has been blocked on, but the question it would answer is now much narrower: **which lock,
not whether a lock.**
