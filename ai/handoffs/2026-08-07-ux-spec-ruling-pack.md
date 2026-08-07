# Ruling pack — `docs/UX_SPEC.md` §10, 2026-08-07

**From:** Claude Code (Planner)
**To:** Sean Kottman (Maintainer)
**Status:** **Spent — all 25 were ruled on 2026-08-07** and the record is `UX-007`. Kept as the
material the ruling was taken from; `docs/UX_SPEC.md` §10 is where the answers live.
**Purpose:** Turn 25 open questions into one sitting.
**Authority:** None. Nothing here is a decision, and no task may build any of it until you rule.
Where I recommend, the recommendation is an implementer's opinion and is marked as one.

---

## Why this exists

**`docs/UX_SPEC.md` §1 bars any task from building a `[P]` clause until it is ratified**, and every
Phase 3 deliverable's *surface* is decided by at least one — `T-107` by `P-1` and `P-14`, `T-108` by
`P-2`, `P-13` and `P-15`, `T-109` by `P-16`, `P-3`, `P-4` and `P-17`, `T-110` by `P-19`, `P-5` and
`P-25`, `T-111` by `P-6`, `P-7`, `P-20` and `P-21`, `T-112` by `P-9`, `P-22` and `P-23`, `T-113` by
`P-10` and `P-24`, `T-114` by `P-26`, `P-27` and `P-28`.

**So the roadmap's "all nine deliverables are startable" is true of dependencies and false of the
spec.** Every one of them can be *begun* — the data work, the model, the tests — and none of them
can be *finished*, because finishing means drawing a surface the spec has not settled. `T-181` was
the exception and is now complete: `UX-006` settled its surface when it was accepted.

**Ruling these is worth more than any single deliverable.** It is the difference between eight
tasks that can start and eight tasks that can land.

### The state of the numbering, precisely

28 numbers; **two withdrawn** (`P-8`, presets already decided by `DAT-001`; `P-11`, the duplicate
warning's date, which nothing records); **one ruled** (`P-12`, by `ARC-010` on 2026-08-07: typed
fields, the model widens); **one half-ruled** (`P-18`: the free post-processor field stays refused,
its capability arrives through `REQ-031`; per-entry post-processing still open). **25 open.**

---

## If you rule on nothing else, rule on these four

They decide more than a layout, and three of them block a task from being specified at all.

| # | Question | What it actually decides | My recommendation |
|---|---|---|---|
| **P-16** | Do `T-109` and `T-111` share one screen? | **Whether `T-109` has a screen of its own.** Not a layout preference — it changes what `T-109` builds | **Share one screen**, reached two ways. The fields are identical by construction (`PRESET_OWNED_FIELDS` is derived from the two dataclasses), so two screens is two renderings of one thing, and this project's recurring defect is exactly that |
| **P-10** | Does `REQ-017` reopen per-job pause? | Reopens `UX-001` and `T-080`'s removal of `PAUSED`; also decides `Pause all` on a group | **Decide it inside `T-113`, not before.** It is the one question whose right answer depends on what resume turns out to cost, and `T-113` is scheduled early precisely to find that out. `UX-006` did **not** pre-empt it |
| **P-22** | Is the template preview an unfocusable live region, a focusable read-only field, or announced on demand? | A real accessibility trade-off; `NFR-005` does not settle it | **Focusable read-only field.** A user who cannot `Tab` to the preview cannot review it at their own pace, and a live region announces on the writer's schedule rather than the reader's. Costs one more stop in the tab order |
| **P-23** | Is a containment failure shown at edit time or at download time? | `T-112` carries the same proposal as an acceptance criterion — **one ruling settles both** | **Edit time, with the reason.** The failure is a property of the template, which is in front of the user while they type; at download time it is a failure of something they have stopped looking at |

---

## Group A — six scope refusals, rulable as one line

These all ask *does this task refuse the thing beyond its edge?* They can be answered together:
**"Yes — these are the boundary of Phase 3's UI, and anything past it needs its own task."**

| # | Refuses | Cost of refusing | Cost of not |
|---|---|---|---|
| P-14 | Re-probe from the format table, download-from-table, filtering | A user with a stale probe reopens the dialog | A refresh button implies the list goes stale within a session, which nothing establishes |
| P-15 | Three-way merges, external audio, automatic pairing | An expert uses `REQ-009`'s selector string | Each is a second selection model on a table that already has two |
| P-18 (rest) | Per-entry post-processing inside a playlist | A playlist is post-processed as one batch | Per-entry anything is `T-110`'s structural question, not `T-109`'s |
| P-21 | Preset import/export, per-site rules | Presets stay local; `settings.toml` is hand-editable, which covers sharing crudely | Per-site rules are a rules engine, and this is a downloader |
| P-25 | Filtering the playlist picker | A 200-entry playlist is scrolled | A filter is a second interaction to learn on a list you already chose to open |
| P-28 | Content matching, automatic duplicate skipping | Two URLs for one video are not detected | Content matching needs a heuristic nobody has specified; auto-skip decides for the user, and `REQ-022` says confirm rather than refuse |

**Recommendation: refuse all six**, and record that each is a *scope* boundary rather than a
judgement that the feature is bad — which is what makes it cheap to revisit.

---

## Group B — six questions a mockup answers faster than prose

`T-130`'s lesson is that a mockup and a window disagreed and nobody noticed, so these are the ones
where a picture beats a paragraph. **If you would rather see them than read them, say so and I will
build one page showing all six.**

| # | Question | Options | My recommendation |
|---|---|---|---|
| P-1 | How does the format table open? | Modal dialog · sheet · expanding row | **Expanding row.** The staging list is already a list of rows that open; a modal over a modal is the alternative |
| P-2 | Video+audio: a mode, or two pickers? | One table with a mode switch · two side-by-side pickers | **Mode.** Two pickers doubles the table and most downloads use neither |
| P-5 | Playlist entries: checkboxes with a tri-state header? | Checkboxes · selection-as-checked | **Checkboxes.** Selection-as-checked collides with `ExtendedSelection` and loses the choice on a stray click |
| P-6 | One preset list or two? | Built-ins and user presets together · two lists | **Together**, with built-ins marked. `Preset.built_in` already carries the flag so the UI cannot lose track |
| P-19 | Playlist picker: the staging row opened, or a dialog? | Row · dialog | **The row.** Same argument as `P-1`, and one mechanism for both |
| P-20 | Preset manager: a list beside a form, with buttons? | List+form+buttons · a menu | **List beside a form.** `T118-R5` forbids dropping a control, not this layout |

---

## Group C — the remaining nine

| # | Question | Options and costs | My recommendation |
|---|---|---|---|
| P-3 | Is the post-processing editor reachable as a per-download *Options…*? | **Yes**: a one-off tweak needs no saved preset. **No**: every option change becomes a preset, and the preset list fills with *Best video (1)* | **Yes** — and note it interacts with `P-16`: if the screen is shared, this is the same screen with a different title and save action |
| P-4 | Does a one-off change offer *Save as preset…*? | **Yes**: explicit. **No**: the user retypes it next time | **Yes, explicitly** — never silently, which is the half that matters |
| P-7 | Is there always exactly one default preset? | **Always one**: a paste always has something to inherit. **Allow none**: the dialog needs an inherit rule for the empty case | **Always one.** Deleting the default promotes another; "no default" is a state with no useful meaning for a paste |
| P-9 | Does the template editor list supported fields inline? | **Inline list** · link to yt-dlp's docs · nothing | **Inline**, for the fields the app actually supports. `REQ-009`'s learn-the-syntax rule is the precedent, and a link leaves the GUI as a launcher for a manual |
| P-13 | With ffmpeg absent, is the merge mode hidden, shown-and-refused, or the table drawn without it? | Hidden with the reason stated where it would have been · shown and refused at commit · table drawn without the mode | **Hidden, with the reason in its place.** `UX-005` §5 forbids drawing what would be refused; stating the reason is what stops "hidden" reading as "missing" |
| P-17 | Is the subtitle language control a multi-select? | Multi-select from a known set · comma-separated text | **Multi-select** — but note `SUBTITLE_LANGUAGES` is `("all",)` today, so **the set itself is unspecified** and this ruling implies a second small decision about where the list comes from |
| P-24 | Does a non-resumable job say so on its row and offer *start again*? | **Yes**: honest, one more verb · **No**: restart transparently and say nothing | **Yes.** `REQ-017`'s second half — *state clearly when resumption is not possible* — is as much of the requirement as the first, and a silent restart spends the bytes again without saying so |
| P-26 | Is the duplicate warning a row state or a modal? | Row state · modal | **Row state.** `UX-003` made the staging list the place where a URL's status is said; a modal for a non-blocking condition trains people to dismiss modals |
| P-27 | Is ordinary *Add to queue* the override, or is a per-row *download anyway* wanted? | Ordinary Add · explicit per-row verb | **Ordinary Add.** `REQ-022` says a duplicate is *confirmed, not refused*, and an extra verb to do the ordinary thing is a discouragement the requirement rules out |

---

## What I would do with the answers

Ruling Group A and the four headline questions unblocks `T-107`, `T-108`, `T-112` and `T-114`
completely. Group B unblocks the rest, and I would rather draw it than argue it.

**One thing to decide alongside these:** `docs/UX_SPEC.md` §2 item 7 says a waiting row reads
**Held**. It has never been built, `T-181` deliberately did not build it — the stopped state is
said once, at queue level, because `UX-001` makes the gate a property of the queue and never of a
job — and it is marked `[T]` rather than `[P]`, so nothing currently flags it as open. It is worth
either re-deciding or striking, because as it stands the spec describes a row rendering that
contradicts the decision above it.
