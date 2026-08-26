# The `T-272` specimen, alive on `Spock` — captures of 2026-08-25 and 2026-08-26

**Retained on `T272-R6`'s direction.** That finding asked for this capture to be kept *"if it
survives"*. **It survives**: at the timestamp of the last block below the processes are running,
and this file is read-only state taken while they were.

**Nothing here signalled, traced, attached to or reaped anything** (`T258-R4`). Every block is
`ps`, `/proc` and `tools/orphan_scan.py` output.

**Why this is here rather than regenerated on demand.** While the processes live, re-running the
scanner does reproduce *a* capture — but not *these*: each block is the state at one timestamp, and
the sequence is the evidence that the pair persisted across the dates `T-272` records them as
having ended. The parent is already gone, so a future orphan would be a different specimen. This is
the same justification the 2026-08-20 file carries, and it is being applied earlier this time
because that file's subject was believed lost while it was in fact still running.

## What this contradicts

| Claim | Where | Status |
|---|---|---|
| *"Both PIDs are gone from `ps`"*, 2026-08-20 | `T-272`, evidence file, `STATUS.md` | **False.** `T272-R6` establishes this. |
| *"No specimen remains available"* (struck criterion) | `T-272` acceptance criteria | **False.** The criterion is unmet, not overtaken. |
| *"The specimen ended between the August 25 capture and this review"* | `T272-R6`, 2026-08-26 | **Not true of `Spock`.** See the final block: both PIDs present, scanner exit 1. |

**The last row is why the machine is named in every block below.** `T272-R5` establishes that one
shared runner label selects either `kirk` or `Spock`; a check of "current state" is a statement
about whichever machine it ran on. Every block here records `hostname` and `machine-id`.

## Capture 1 — 2026-08-25T16:49:41Z

```
# Live orphan specimen, captured 2026-08-25 2026-08-25T16:49:41Z
# READ-ONLY. Nothing here signals, traces or reaps. T258-R4.

## host
2026-08-14 12:18:08
Linux Spock 7.1.4-204.fc44.x86_64 #1 SMP PREEMPT_DYNAMIC Wed Jul 22 16:25:06 UTC 2026 x86_64 GNU/Linux

## pid 434366
    PID    PPID                  STARTED     ELAPSED NLWP   RSS STAT WCHAN                    CMD
 434366    2139 Sun Aug 16 01:12:15 2026  9-10:37:25    2 21528 Sl   hrtimer_nanosleep        /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=16, pipe_handle=40) --multiprocessing-fork
-- /proc/434366/status (subset)
Name:	python
State:	S (sleeping)
Tgid:	434366
Pid:	434366
PPid:	2139
VmRSS:	   21528 kB
Threads:	2
voluntary_ctxt_switches:	6293146
nonvoluntary_ctxt_switches:	4891
-- cmdline
/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=16, pipe_handle=40) --multiprocessing-fork 
-- cwd / exe
lrwxrwxrwx. 1 sean sean 0 Aug 25 11:49 /proc/434366/cwd -> /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails
lrwxrwxrwx. 1 sean sean 0 Aug 17 09:46 /proc/434366/exe -> /usr/bin/python3.14
-- threads and their stacks
   tid 434366 wchan=hrtimer_nanosleep state=S
   tid 434371 wchan=futex_do_wait state=S
-- open fds
   total 0
   lr-x------. 1 sean sean 64 Aug 19 21:35 0 -> /dev/null
   lrwx------. 1 sean sean 64 Aug 19 21:35 1 -> /tmp/#464048 (deleted)
   l-wx------. 1 sean sean 64 Aug 19 21:35 16 -> pipe:[1629660]
   lrwx------. 1 sean sean 64 Aug 19 21:35 2 -> /tmp/#464049 (deleted)
   lr-x------. 1 sean sean 64 Aug 19 21:35 21 -> pipe:[1631932]
   l-wx------. 1 sean sean 64 Aug 19 21:35 22 -> pipe:[1631932]
   lr-x------. 1 sean sean 64 Aug 19 21:35 25 -> pipe:[1631945]
   lr-x------. 1 sean sean 64 Aug 19 21:35 3 -> pipe:[1631947]
   l-wx------. 1 sean sean 64 Aug 19 21:35 35 -> pipe:[1631945]
   l-wx------. 1 sean sean 64 Aug 19 21:35 39 -> pipe:[1631946]
   lr-x------. 1 sean sean 64 Aug 19 21:35 4 -> /dev/null

## pid 432922
    PID    PPID                  STARTED     ELAPSED NLWP   RSS STAT WCHAN                    CMD
 432922    2139 Sun Aug 16 01:10:39 2026  9-10:39:01    1  7484 S    anon_pipe_read           /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.resource_tracker import main;main(15)
-- /proc/432922/status (subset)
Name:	python
State:	S (sleeping)
Tgid:	432922
Pid:	432922
PPid:	2139
VmRSS:	    7484 kB
Threads:	1
voluntary_ctxt_switches:	2946
nonvoluntary_ctxt_switches:	2
-- cmdline
/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.resource_tracker import main;main(15) 
-- cwd / exe
lrwxrwxrwx. 1 sean sean 0 Aug 25 11:49 /proc/432922/cwd -> /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails
lrwxrwxrwx. 1 sean sean 0 Aug 17 09:46 /proc/432922/exe -> /usr/bin/python3.14
-- threads and their stacks
   tid 432922 wchan=anon_pipe_read state=S
-- open fds
   total 0
   lr-x------. 1 sean sean 64 Aug 19 21:35 0 -> /dev/null
   lrwx------. 1 sean sean 64 Aug 19 21:35 1 -> /tmp/#464048 (deleted)
   lr-x------. 1 sean sean 64 Aug 19 21:35 15 -> pipe:[1629660]
   lrwx------. 1 sean sean 64 Aug 19 21:35 2 -> /tmp/#464049 (deleted)
   lrwx------. 1 sean sean 64 Aug 19 21:35 8 -> /tmp/#464049 (deleted)

## the shared pipe both hold
pid 434366:
         1 pipe:[1629660]
         2 pipe:[1631932]
         2 pipe:[1631945]
         1 pipe:[1631946]
         1 pipe:[1631947]
pid 432922:
         1 pipe:[1629660]

## scanner output
1 orphaned worker(s) — spawned, parent gone, still running:
  pid  434366  age 9d10h  dead parent    2139  threads 2  rss 22 MB
Reported, not reaped — see this module's docstring for why (`T258-R4`).
exit=1
```

## Capture 2 — 2026-08-25T~23:00Z

```
# Live orphan specimen — re-captured 2026-08-25T20:36:15Z
# READ-ONLY. Nothing signalled, traced or reaped (T258-R4).

## host
     Static hostname: Spock
          Machine ID: 71ff7aaf85db4b63bad898cff9151e36
boot: 2026-08-14 12:18:08
runner name: "agentName": "Spock"

## pid 434366
    PID    PPID                  STARTED     ELAPSED NLWP   RSS STAT WCHAN                CMD
 434366    2139 Sun Aug 16 01:12:15 2026  9-14:23:59    2 21528 Sl   hrtimer_nanosleep    /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=16, pipe_handle=40) --multiprocessing-fork
-- threads
   tid 434366 wchan=hrtimer_nanosleep
   tid 434371 wchan=futex_do_wait
-- pipes
         1 pipe:[1629660]
         2 pipe:[1631932]
         2 pipe:[1631945]
         1 pipe:[1631946]
         1 pipe:[1631947]

## pid 432922
    PID    PPID                  STARTED     ELAPSED NLWP   RSS STAT WCHAN                CMD
 432922    2139 Sun Aug 16 01:10:39 2026  9-14:25:35    1  7484 S    anon_pipe_read       /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.resource_tracker import main;main(15)
-- threads
   tid 432922 wchan=anon_pipe_read
-- pipes
         1 pipe:[1629660]

## scanner
1 orphaned worker(s) — spawned, parent gone, still running:
  pid  434366  age 9d14h  dead parent    2139  threads 2  rss 22 MB
Reported, not reaped — see this module's docstring for why (`T258-R4`).
exit=1
```

## Capture 3 — taken now, after the review reported the specimen gone

```
host:        Spock  machine-id=71ff7aaf85db
utc:         2026-08-26T00:16:09Z
boot:        2026-08-14 12:18:08   (predates both processes; no reboot since)

    PID    PPID                  STARTED     ELAPSED NLWP   RSS STAT CMD
 434366    2139 Sun Aug 16 01:12:15 2026  9-18:03:52    2 21528 Sl   /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=16, pipe_handle=40) --multiprocessing-fork
 432922    2139 Sun Aug 16 01:10:39 2026  9-18:05:28    1  7484 S    /mnt/storage/software_projects/tracks-and-trails/tracks-and-trails/.venv/bin/python -c from multiprocessing.resource_tracker import main;main(15)

/proc/434366: present  state=S  threads=2
/proc/432922: present  state=S  threads=1

pipe inode T-272 names, held by 434366:
  l-wx------. 1 sean sean 64 Aug 19 21:35 16 -> pipe:[1629660]

scanner:
  1 orphaned worker(s) — spawned, parent gone, still running:
    pid  434366  age 9d18h  dead parent    2139  threads 2  rss 22 MB
  Reported, not reaped — see this module's docstring for why (`T258-R4`).
  exit=1
```

*(**The exit code above was first written as `0` and that was a capture defect, not a result.** The
scanner's output was piped through `sed` to indent it, so `$?` reported `sed`'s status rather than
the scanner's. Re-run unpiped, the scanner exits **1**, which is what "one orphaned worker found"
means. Recorded because an evidence file that reports the wrong exit code is the same class of
defect as the record this file exists to correct.)*
