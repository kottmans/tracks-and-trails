# Criterion 8 — the built-window checklist

**Purpose:** What a person looks for when running the application, to evidence Phase 2's eighth
exit criterion.
**Owner:** Maintainer
**Status:** Active
**Required by:** `P2EXIT-R10`
**Derived from:** `T-132`–`T-141` and the adopted mockups —
`docs/mockups/2026-08-03-main-window-b1.html`, `docs/mockups/2026-08-04-playlist-rows.html`

---

## Why this exists and why CI does not replace it

Criterion 8 says the window matches the features behind it. **Automated checks are not sufficient
evidence for a criterion about what the window looks like**, and that is not a philosophical
position — it is this criterion's own history. Five visible defects escaped the gates, and
`T132-R1` was visible in the real window the moment somebody opened it. `T-139` went further: its
premise was wrong, and only measurement at the window found that out.

**This checklist is evidence for the closed list — not an invitation to add tasks.** `T-132`
through `T-141` are named by id and the list is closed at 2026-08-04. Anything new you notice is
Phase 3 work unless you rule otherwise; write it down separately rather than folding it in here.

## Running it

```bash
cd /mnt/projects/software_projects/tracks-and-trails/tracks-and-trails
git log --oneline -1          # record this: the checklist is evidence about one head
.venv/bin/python -m tracks_and_trails
```

On Spock the checkout is `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`.
Run it **on the exact candidate head**, and record which one — a run against a head that then moves
evidences nothing (`P2EXIT-R8` is that mistake).

Check both themes where a row says "both". Nothing here needs the network except the playlist
checks, which need one real playlist URL.

---

## 1 · The toolbar (`T-132`, `T-141`, `T-133`)

| # | What to look for | Task |
|---|---|---|
| 1.1 | **`Add URLs` is a filled brand button**, not a bordered one like its neighbours. This is the finding that was reported, withdrawn as reviewer error, and then confirmed: a *disabled* Add is correctly **not** filled, so check it with a real output directory set and the action enabled | `T-132` |
| 1.2 | `Pause queue` and `Clear finished` are **bordered buttons on the surface** — still buttons, not bare text | `T-132` |
| 1.3 | Those two **end to the right of** the concurrency control, not floating mid-bar | `T-132` |
| 1.4 | Hovering and pressing each toolbar button visibly changes it | `T-132`, `T-129` |
| 1.5 | **Press `Pause queue`. The control must look different paused than running** — it is a checkable action, so it has a state to show. *(Added 2026-08-05 after the maintainer found it missing from this list and from the window: `T-149`. The style sheet declares `:hover`, `:pressed` and `:disabled` and not `:checked`.)* | `T-149` |
| 1.6 | The concurrency control shows **labelled `−` and `+` buttons**, and no native spin arrows beside them | `T-141`, `T-133` |
| 1.7 | Each stepper **disables at its end of the range** — `−` at 1, `+` at 16 | `T-141` |
| 1.8 | With focus in the spin box, **Up and Down still step** the value | `T-141` |

## 2 · A queue row (`T-134`, `T-135`, `T-136`)

| # | What to look for | Task |
|---|---|---|
| 2.1 | **Moving the pointer over a row's verb highlights it**, and moving off clears it. Leaving the window entirely also clears it | `T-134` |
| 2.2 | **The list must never scroll sideways.** A long title elides; it does not widen the row. *(Added 2026-08-05: `T-151`. If a horizontal scrollbar appears, the verbs are off screen and rows 2.1–2.4 cannot be checked at all.)* | `T-151` |
| 2.3 | A **wide** window draws no `⋯` on a row whose verbs all fit | `T-135` |
| 2.4 | **Narrow the window** until verbs drop. `⋯` appears, and its menu holds **exactly the dropped ones** — not a repeat of what is still on the row | `T-135` |
| 2.5 | **Shift+F10** opens the full menu at both widths — **try it before clicking any row**, which is the case that fails today (`T-152`), then again after clicking one | `T-135`, `T-152`, `NFR-005` |
| 2.6 | In the add dialog, a staged row's **format line does not run underneath its format control** — check with a long selector that wraps | `T-136` |

## 3 · A playlist (`T-137`, `T-140`)

Paste one real playlist URL. This is the sequence that produced criterion 8 in the first place.

| # | What to look for | Task |
|---|---|---|
| 3.1 | **Every entry downloads**, not one. Sixteen items means sixteen files | `T-137` |
| 3.2 | The files **land together in a folder named from the playlist** | `T-137` |
| 3.3 | Closed, the playlist is **exactly one row**; opened, it is one plus its entries | `T-140` |
| 3.4 | **`Right` opens it and `Left` closes it** with the header focused — the keyboard route | `T-140`, `NFR-005` |
| 3.5 | The chip reads **`4 of 16`, never a percentage** | `T-140` |
| 3.6 | The segmented bar shows a **failed** entry differently from a queued one, and finished segments are **brand-coloured, not muted** | `T-140` |
| 3.7 | A child row draws **no format line** and a smaller thumbnail, and is not clipped | `T-140` |
| 3.8 | The header shows **`Download as: Best video available`** — a preset *name*, never raw yt-dlp syntax like `bestvideo+bestaudio/best` | `T140-R3` |
| 3.9 | Changing the format **on the header** changes it for every entry that can still take one | `T140-R3` |
| 3.10 | The header offers **`Cancel all`**, **`Show in folder`**, and **`Remove`** — and **no `Open`**. `Pause all` is **deliberately absent**, deferred to `REQ-017` | `T-140` |
| 3.11 | **`Retry failed` appears only when something failed.** With nothing failed it must not be there | `T-140` |
| 3.12 | `Remove` on the header asks **"Remove these 16 downloads from the queue?"** — naming its count, with **No** as the default button | `T-140`, `DAT-005` §4 |
| 3.13 | The **tab count counts downloads, not rows** — opening a group must not change it | `T-137` |
| 3.14 | Every entry shows **its own thumbnail**, not a derived placeholder tile | `T-137` |
| 3.15 | `Clear finished` on a **part-done** playlist leaves the group intact rather than dissolving it | `T-140` |

## 4 · History and the add dialog (`T-138`, `T-139`)

| # | What to look for | Task |
|---|---|---|
| 4.1 | A completed download shows the **same picture in History** it had in the queue | `T-138` |
| 4.2 | History rows respond to the pointer the way queue rows do | `T134-R1` |
| 4.3 | With a **video** preset chosen, the bitrate control **cannot be changed** | `T-139` |
| 4.4 | With an **audio** preset chosen, it can | `T-139` |
| 4.5 | The summary line and the bitrate control **agree** — neither claims a bitrate the other denies | `T-139` |

## 5 · Both themes

| # | What to look for |
|---|---|
| 5.1 | Switch to dark and repeat 1.1, 1.5, 1.6, 3.6 and 3.8. Contrast is gated automatically, but *"is that button obviously the primary one"* is not |

---

## Recording the result

The run is evidence about one head, so record it as such:

```
Head:      <sha>            (git log --oneline -1)
Platform:  <machine, OS>
Date:      <date>
Result:    <pass, or the numbered rows that failed>
```

Put the record where the exit review will read it — `ai/STATUS.md` for the narrative, and
`ai/evidence/` if there are screenshots worth keeping. **A row that fails is a finding against the
closed list**, so it belongs to whichever of `T-132`–`T-141` owns it. **Something new that is not
on this list is Phase 3**, filed as its own task, unless the maintainer rules otherwise — that edge
is what keeps criterion 8 falsifiable.
