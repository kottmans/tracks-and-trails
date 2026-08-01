# Focused correction re-review — the 2026-08-01 batch findings

You are the Reviewer (`AGENTS.md` §3). This is my own work; none of it is signed off.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Correction boundary:** `05e5312..aff4e87` — **one commit**
**Platforms:** Linux only. No CI job has executed a step since 2026-07-30.
**Evidence:** `ruff check`, `ruff format --check`, `mypy src`, `mypy --platform win32 src` clean.
Full Linux suite **1738 passed / 11 skipped / 2 deselected**. **Ten mutations, all killed**, tree
hash identical before and after.

## Read this first: the commit boundary is wrong and I cannot fix it

`aff4e87`'s subject and `Task:` trailer name **`T-046` only**. It actually carries **all five
corrections** — `T046-R1`, `T081-R1`, `T083-R1`, `T102-R1`, `T092-R1` — plus `T087-R1` and the
coordination updates. I intended one commit per task and committed the whole working tree in one
step.

It is pushed, and `AGENTS.md` §7 forbids rewriting published history, so the message stands wrong.
**Use this file and the task entries for the per-finding boundary, not the trailer.** Each entry's
`#### Correction, 2026-08-01` section is accurate.

*(This is the second boundary muddle in two rounds. The previous one was `3fed547` carrying your
test edit. Both are mine and both come from staging the whole tree at the end rather than as I go.)*

## The five findings

### `T046-R1` — Critical, data loss

**Download into a per-job staging directory; claim the produced name afterwards.** Predicting the
final extension was rejected — it is a function of yt-dlp's postprocessor chain, and a wrong
prediction is the same defect with more code. `_extract` writes into a private directory inside the
destination's own folder (so the move is a same-filesystem rename, not a copy of a multi-gigabyte
file); `claim_output_path` then reserves the **actual** produced name with `O_CREAT | O_EXCL` and
`os.replace`s into it.

**Two things I want you to attack:**

1. **A cancelled or failed download now leaves nothing behind**, where it used to leave a `.part` in
   the user's folder. I judged that an improvement and flagged it for `REQ-017`/`T-113`, and I
   replaced the cancel test's `.part` assertion rather than deleting it — the cooperative-unwind
   signal it carried is now the worker's own "parent process cancelled" message. **If you think
   discarding the partial is wrong, this is the moment.**
2. **Three test fakes were reporting successful downloads that wrote no file**, and the worker could
   not notice while the reservation was itself a file — `T-077`'s lesson reproduced in the harness.
   They write now. Please check I have not made them lie in some new way.

### `T081-R1` — the barrier hole you found

Both admission rules now sit on one condition in `start()`, PROBE exempt from both. **And a settled
reorder re-decides admission**: a parked job was chosen against the *old* order, so honouring it
as-is starts the old head immediately after the user said otherwise. The jobs named in a settled
reorder become candidates and `_next_waiting` picks by the new positions — **only while something is
already parked**, so a reorder of an idle queue starts nothing.

**That last rule is a product judgement I made**, not one a decision records. It is what makes your
regression's second assertion pass. If you disagree with it, say so.

### `T083-R1` — retry operation identity

The failed session's kind is carried from `_on_session_ended` and recorded in `_intended_kind` for
every deferred start — pause, slot, reorder barrier, backoff. Paired PROBE/DOWNLOAD tests, and the
probe half asserts **no output in the directory**, which is where the user would feel it.

**A mutation found a second path after the first battery**: `_perform_due_retries` passes the kind
explicitly, so an immediate retry keeps it either way; a retry *parked behind a full pool* is
restarted by `_fill_free_slots`, which has no kind of its own. Now tested.

### `T102-R1` — decoding failure

Treated as another unusable existing file, keeping the codec's reason and byte offset. The
never-raises matrix had **no encoding case at all**; it now has two, including a truncated
multi-byte sequence.

**One of my assertions was vacuous**: `any(ch.isdigit() ...)` to check the offset was present — and
`"UTF-8"` satisfies that by itself, so a mutation replacing the whole reason survived. It computes
the expected offset and asserts it exactly now.

### `T092-R1` — provenance and disclosure

**Nothing is uploaded.** Both jobs stamp their start time and write `reports/crashdumps.txt` naming
any dump written during that run — name, size, timestamp — and leave the dump on `STARBASE`. The
report states in as many words that a dump is not by itself evidence of `T-074`, because WER is
keyed by executable *file name* and there is no narrower key. The narrower alternative (copy the
interpreter to a distinct name) is recorded rather than done, since it changes how the suite is
launched.

**Three acceptance criteria remain unmet and still need the machine.** Unchanged.

## `T087-R1` — corrected, and deliberately still blocked

The Windows primitive is now `CreateFileW` with `dwShareMode = 0`, which is what `ARC-006`'s
amendment actually names. **You were right that substituting `msvcrt.locking` was a different
architectural choice**, and doing it in the one branch nothing here can execute is how a decision
gets rewritten by its implementer.

**This does not unblock the task and should not.** The branch has still never run. `T-087` is
`Blocked` in `TASKS.md`, `A-004` stays unverified, and **Phase 2 exit criterion 4 is blocked with
it**. What changed is that the outstanding item is now *evidence* rather than evidence plus an
unauthorised design change.

## Where I would look first

1. **The staging rename under failure.** `claim_output_path` gives the reservation back if the move
   fails, but a move that fails halfway on a filesystem that is not POSIX-atomic is not something I
   can test here.
2. **`_admit_reordered`'s scope** — see the product judgement above.
3. **The `CreateFileW` call itself.** `ctypes` + `msvcrt.open_osfhandle`, type-checked and never
   executed. The handle-to-fd conversion is the part I am least able to verify from Linux.
4. **The staging directory in the user's downloads folder.** It is created and removed per download;
   a crash between the two leaves a dot-prefixed directory behind. I did not add a startup sweep.

## Approved last round, unchanged since

`T-080`, `T-053`, `T-099`, `T-101`, `T-103` are filed `Complete`.
