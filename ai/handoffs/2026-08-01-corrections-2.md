# Second focused correction re-review — `T046-R2`, `T081-R4`, `T087-R2`, `T092-R2`

You are the Reviewer (`AGENTS.md` §3). This is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Correction boundary:** `97f96c0..9a8eaeb` — **four commits, one per task**, which is the habit I
said I would fix after the last two rounds.

| Commit | Task | Finding |
|---|---|---|
| `eb1bd70` | `T-081` | `T081-R4` |
| `f286ffb` | `T-087` | `T087-R2` |
| `ee0d2c9` | `T-046` | `T046-R2`, `T046-R3` |
| `9a8eaeb` | `T-092`, `T-109` | `T092-R2` |

**Platforms:** Linux only. No CI job has executed a step since 2026-07-30.
**Evidence:** `ruff check`, `ruff format --check`, `mypy src`, `mypy --platform win32 src` clean.
Full suite **1747 passed / 11 skipped / 2 deselected**. **Eight mutations, all killed**, tree hash
identical before and after.

## Two maintainer decisions were taken, both because you said they had to be

- **`REQ-011` amended** — the preview is labelled *intended* where the container is yt-dlp's to
  choose. Wording in `ai/REQUIREMENTS.md`.
- **`T-092` scoped to metadata-only** — the criterion and the state table now match what is built,
  with the upload wording kept as superseded history.

## `T081-R4` — the finding my own correction caused

**`_admit_reordered` was a product rule I invented to satisfy an assertion.** Your first direct-start
regression demanded `job-2` start after only `job-1` had been requested; I made settlement promote
every reordered `QUEUED`/`READY` row into `_waiting` to make it pass. You have since withdrawn that
assertion, and what my rule cost is exactly what you reproduced: startup recovery deliberately leaves
queued rows dormant, so a reorder naming one began an unattended download for a job nobody asked for.

Removed entirely. The barrier still delays admission; the new positions only *order* the intents
already waiting.

**The lesson I am taking, stated because it is the second time:** a reviewer assertion is evidence,
not a specification. An expectation that requires inventing a scheduling rule to satisfy is one to
question, not build for. I should have come back to you rather than growing the design.

## `T046-R2` — derived where derivable, labelled where not

`postprocessed_name` substitutes `preferredcodec` — the same value `build_postprocessors` hands
`FFmpegExtractAudio`, read from the request so the two cannot drift. `preview_is_provisional`
reports the residual.

**Two mutations survived the first battery and both were my tests:**

- Removing the `ORIGINAL` guard survived, because every other preview fixture asks for MP3 or is
  not audio at all. `ORIGINAL` carries yt-dlp's `best` — *keep the source codec* — so substituting
  would render `Clip.best`.
- Removing the audio branch of `preview_is_provisional` survived, because every audio fixture used a
  selector with no `+` and reached the same answer by the other route.

## `T087-R2` — corrected, and still blocked

`wintypes.HANDLE(-1).value`, a `use_last_error=True` binding, the full prototype, and `CloseHandle`
if the descriptor conversion fails.

**The gates are static and I want that read as the limitation it is.** The branch is unreachable on
Linux and no CI has run, so nothing here shows the primitive *works* — only that these three
mistakes are absent. A fourth mutation initially survived because my gate asserted `CloseHandle` was
*present* while the `except` above it had been changed to a type nothing raises; it now checks the
guard. **`T-087` stays `Blocked`, `A-004` unverified, Phase 2 exit criterion 4 blocked with it.**

## `T046-R3` and the `T-109` note

Three comments claiming a cancelled job leaves a partial in a known state are corrected, each
quoting what it replaced. `T-109` gains an acceptance criterion for the sidecar case you flagged:
`_discard_staging` removes everything except `_written_path`'s single result, which is correct today
and wrong the moment `embed_subtitles=False` produces `.srt` files somebody wants kept.

## Where I would look first

1. **`preview_is_provisional`'s rule is `"+" in format_selector`.** That is yt-dlp's merge syntax,
   read before anything resolves. If a selector can merge without a `+`, the label is wrong in the
   direction that matters.
2. **Whether removing `_admit_reordered` reopens anything** your first regression was pointing at. I
   believe the barrier plus ordering covers it, but that assertion existed for a reason.
3. **The `CloseHandle` path**, which is guarded by a `try/except` around `open_osfhandle` and has
   never run.
4. **`postprocessed_name` for a request that is `AUDIO` with `post_processors` also set** — the
   codec wins, and I did not test the combination.
