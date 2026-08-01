# Fourth focused correction re-review — `T-046` and `T-087`

You are the Reviewer (`AGENTS.md` §3). This is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Correction boundary:** `049b595..ea9d752`
**Awaiting a verdict:** `T-046` and `T-087`. Nothing else is in review.

| Commit | Task | Findings |
|---|---|---|
| `bddf1bb` | `T-087` | `T087-R3` |
| `9c5745a` | `T-046` | `T046-R4`, `T046-R5` |
| `2c12982` | — | the type gate I had broken (no task; see below) |
| `17e7ba5` | `T-087`, `T-092` | `OPS-005` amendment and the workflow gate |
| `6171812`, `7516f61`, `ea9d752` | — | coordination only |

## **There is CI evidence this time**

Every previous handoff said "no CI or Windows execution occurred". That is no longer true.

- **`ea9d752` is green on all four hosted jobs.** `ubuntu-latest` **1753 passed / 11 skipped / 2
  deselected**; `windows-latest` **1741 passed / 21 skipped / 32 deselected**.
- **The Windows locking branch executed.** `T-087`'s three required cases — first acquisition and
  refusal, **two launches racing**, and killed-holder recovery — all passed on `windows-latest`.
- `windows desktop` is **skipped**, not queued. See the `OPS-005` amendment below.

Locally: `ruff`, `ruff format`, and **all four** `mypy` gates (`src` and full tree, both platforms)
clean. Six mutations, all killed, tree hash identical before and after.

## `T046-R4` — the premise was wrong twice, and a real download proved it

**The codec is not the extension.** yt-dlp copies `aac` and `alac` into `m4a` and `vorbis` into
`ogg`, so `codec.value` was right for five of eight and confidently wrong for three. The container
now comes from yt-dlp's own `ACODECS` table rather than being restated.

**And `ORIGINAL` is not derivable at all.** The obvious next move is to read the codec from the
probed `info_dict`; that does not work either. `FFmpegExtractAudioPP.run` calls
`get_audio_codec(path)` — **ffprobe on the downloaded file** — and skips converting entirely when
the *downloaded* extension is already a common audio one. Both inputs exist only after the write.

So it is labelled provisional, and **`REQ-011`'s exactness claim is narrowed** to extraction with a
**named** codec. Your real regression is kept with its assertion amended, per the second route your
recommendation allowed.

## `T046-R5` — `mergeall`

Merge classification moved to `core/presets.selector_merges`, which lists the forms rather than
scanning for one token, and says plainly that an unlisted form is reported *exact* — so the list is
the thing to keep short and visible.

## `T087-R3` — both details, and both were already in your previous recommendation

`CloseHandle` bound with `argtypes = (wintypes.HANDLE,)` and `restype = wintypes.BOOL`;
`open_osfhandle` given `os.O_NOINHERIT`. I fixed the sentinel and the saved error last round and
missed these two from the same paragraph.

## `OPS-005` amended, on its own reasoning

`STARBASE` is registered and **offline**, and the maintainer is away from it. The entry was written
when the hosted quota had run out and argued *"blocking on an environment nobody can reach is not a
gate, it is a stall"*. The positions reversed, so hosted Windows carries the gate while that holds.

**The `windows desktop` job is skipped unless `STARBASE_AVAILABLE` is set.** An offline self-hosted
runner does not fail its job — it **queues**, holding the whole run at `queued` so nothing reaches a
conclusion. That is why every run since 30 July showed cancelled or pending.

The desktop slice (`T-026`, `T-040`) and `OPS-004`'s subjective residue stay with `STARBASE` and
still block first release. `T-092` and `T-074` stay blocked on it and neither gates this phase.

## Two things about my own process you should weigh

**Four failing tests reached `main`, and CI is how I found out.** `049b595` was a `git add -A`
during your review that swept in four of your regressions, and I pushed **without re-running the
suite** — which `AGENTS.md` §8 forbids in as many words. That is the fourth boundary problem in this
session and the first to leave `main` red.

**A gate had been red for the whole session.** `pyproject.toml` declares `files = ["src", "tests"]`,
so plain `mypy` covers the test tree; CI ran `mypy src` only. I checked a worktree at this session's
starting commit: **plain `mypy` was green then and red by the end**, 14 errors, all mine — six
`JobStore` fakes fallen behind a protocol `T-080` and `T-081` extended, and a property narrowed
across asserts making three tests unreachable. Fixed, and CI now runs it (`2c12982`).

## Where I would look first

1. **`selector_merges` is a token list.** `+` and `mergeall` today. If yt-dlp has a third merge
   spelling, a merging request is reported exact — the direction the amendment exists to prevent.
2. **`audio_extension_for` reads `ACODECS` at call time.** If a yt-dlp update changes an entry the
   preview follows it silently, which I think is right and is worth disagreeing with.
3. **The `ORIGINAL` guard is only reachable by simulation.** `ACODECS` has no `best` key, so the
   guard and the lookup agree; a mutation removing it survived until I added a test that inserts one.
   Judge whether that test earns its keep or merely pins an implementation detail.
4. **`O_NOINHERIT` is now in the path that hosted Windows exercises**, so it has run — but nothing
   asserts a spawned worker *fails* to inherit the lock. The static gate only checks the flag.
5. **The `OPS-005` amendment is mine to have drafted, not to have decided.** The maintainer
   instructed it ("let's just use github for now"); check I have not widened it beyond that.

## What is still not verified

- **A real Windows desktop session.** The desktop slice does not run on a hosted image.
- **`T-092`'s three machine-dependent criteria**, unchanged.
- **A spawned worker's inheritance of the lock descriptor**, per point 4 above.
