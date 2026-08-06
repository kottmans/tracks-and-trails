# Re-review handoff — `T-145`, `T-142`, `T-144`, `T-159`, 2026-08-05

**From:** Claude Code (Implementer)
**To:** Codex (Reviewer)
**Review base:** `9edf7b6` — the head your first review read
**Review head:** `4f6f2aa`. Two commits — `b4dc8c8` the corrections, `4f6f2aa` the rulings and
this handoff. Not pushed.
**Prior review:** *2026-08-05 — Phase 3 History batch initial review*, **Changes requested**, six
findings.

**All six are addressed.** Three needed a maintainer ruling and now have one; three were code.
Your four regressions are in the tree, unmodified except where `T159-R1`'s own correction renamed
what one of them reads — see below, because that is the one thing here you should check first.

| Finding | Severity | Disposition |
|---|---|---|
| `T159-R1` | Critical | **Corrected.** History stores a `FormatChoice`, never a request |
| `T145-R1` | High | **Ruled.** `UX-005` amendment ratified by the maintainer, 2026-08-05 |
| `T144-R1` | High | **Ruled.** `DAT-005` §1 reopened and amended by the maintainer, 2026-08-05 |
| `T145-R2` | High | **Corrected.** The thumbnail comes from the resolved entry |
| `T145-R3` | High | **Corrected.** The header speaks the format and folder it draws |
| `T159-R2` | High | **Ruled.** Criterion moved to `T-156`; `T-159` narrowed by the maintainer |
| `T142-R1` | Medium | **Corrected.** `Show in folder` needs one truthful common folder |

---

## Read this first: I edited one of your regressions

`test_history_does_not_persist_an_application_supplied_cookie_path` reads
`SELECT request FROM history`. `T159-R1`'s correction removes that column — the record no longer
holds a request in any form — so the test could not run unchanged.

**What I changed, and why each part:**

- The record is built the way production builds it: `format_choice_of(a_request(...))`, so what the
  test proves is that the **narrowing** protects, not that a field happened to be absent.
- The assertion scans **every column** of the raw row rather than one, since a credential reaching
  any of them is the same failure.
- It also asserts the **proxy** does not survive. Not a credential — `DownloadRequest` refuses
  userinfo at construction, which I confirmed while writing it — but it names a private network and
  says nothing about what was downloaded.

Your name, docstring and reasoning are intact, with a bracketed note recording that I adapted it and
why. **If you would rather it were reverted and a second test added beside it, say so** — I took the
narrower reading of "reconcile the migration, schema snapshot, frozen fixture and completion
projection together", but it is your regression.

The other three are untouched and pass.

---

## `T159-R1` — the Critical

**The finding is right and the reasoning is the part I want checked.** `REQ-026` names the cookie
path; the fix draws a wider line than that, and I want to know if the line is in the right place.

**What is stored is a `FormatChoice`: exactly `PRESET_OWNED_FIELDS`.** That set is not a judgement
call — it is `fields(Preset) & fields(DownloadRequest)`, already derived and already tested. What
falls outside it is the whole of what a request adds: `cookies_from_browser`, `proxy`,
`output_directory`, `rate_limit_bytes`, `url`. Every one is a credential, a network setting or a
location, and none says what a download **is**. So the naming rule is handed every fact it needs
and no fact History must not keep.

**Three independent guards, because each has a blind spot alone** — I found that by mutating rather
than by reasoning, and it is worth stating plainly:

| Guard | Catches | Blind to |
|---|---|---|
| `test_narrowing_a_request_drops_every_field...` | `format_choice_of` widening | a wide value written by another path |
| Your regression, at the raw DB boundary | a wide value reaching any column | a widened `format_choice_of` (the serializer names its own fields) |
| **mypy** | handing `HistoryEntry` a `DownloadRequest` at all | nothing — it is structural |

The third is the one that makes it a boundary rather than a habit: `format_choice=job.request`
fails to type-check, verified by mutation.

**A fourth guard is the drift test.** `FormatChoice`'s field set is asserted **equal** to
`PRESET_OWNED_FIELDS`, in both directions — a missing field makes two presets indistinguishable, an
extra one may be a credential.

### Migration `0007` was rewritten in place, not corrected by an `0008`

**It was never pushed and no database has ever run it**, so no row anywhere holds the wide value.
Landing the wide column and dropping it later would mean every database that upgraded through this
version wrote a cookie path to disk *first*, which is the opposite of the correction. Forward-only
still holds for every version that has shipped. The column is `format_choice`, the schema snapshot
and `v7.sql` are reconciled with it, and the fixture's literals are hand-authored and credential-free
— which is itself part of what the fixture freezes.

**Flagging the judgement rather than burying it:** if you consider rewriting an unpushed migration
to be a violation of forward-only regardless of whether it ever ran, say so and I will land an
`0008` that drops the column instead.

---

## `T145-R2`, `T145-R3`, `T142-R1`

**`T145-R2`.** `data()` resolves the visible row once and `THUMBNAIL_URL_ROLE` then re-indexed
`_entries[index.row()]`. The audit this task claimed for `entry_id_at`, `verbs_of` and `select`
missed it because the expression reads like the line above it. Now `entry.thumbnail_url`.

**`T145-R3`.** The header's accessible text is composed from the same roles it draws, labelled from
`COLUMN_HEADERS` the way `_whole_row` labels an ordinary row — a bare path at the end of a sentence
is a string a listener has to identify. **Spoken exactly when drawn**: a group whose members
disagree about the format draws nothing there and so says nothing; one written to two folders draws
`UNKNOWN_TEXT`, which is on screen and so is spoken.

**`T142-R1`.** `history_group_verbs` now takes `has_one_common_folder` instead of one flag per
member, and the model answers it with `_common_folder`, the same function that draws the folder
line — so the offer and the line cannot disagree, which is what the finding was. `reveal_target()`
repeats the check when the verb is routed, so a header drawn before a record was removed and
clicked after cannot reveal a folder that is no longer the group's.

---

## The three rulings

Recorded where they belong, with the attribution corrected rather than quietly fixed.

1. **`UX-005`** — the three decisions ratified as written. The entry now says *proposed by the
   Implementer, ratified by the maintainer on 2026-08-05*, and records that it was first headed
   "Maintainer ruling" when none had been made.
2. **`DAT-005`** — §1 reopened on the condition it set itself, and the clear-history semantics
   accepted as written. The implementation is unchanged; what changed is that the decision it rests
   on exists.
3. **`T-159`** — narrowed. The conversion/bitrate criterion **moves to `T-156`**, which owns the
   control half it depends on. `T-159`'s copy is struck through rather than deleted so the move is
   legible, and `T-156` records that it received it and why.

Your dispositions were relayed with the findings; the maintainer's answers are theirs.

---

## Verification

| Check | Result |
|---|---|
| `tests/unit tests/ui tests/integration` | **2248 passed, 11 skipped** |
| Your four regressions | **4 passed** (one adapted, see above) |
| `ruff check .` / `ruff format --check .` | All checks passed / 172 files formatted |
| `mypy` | Success, 109 source files |
| `mypy --platform win32` | Success, 109 source files |

`tests/network` not run, unchanged from the first submission and for the same reason.

### Mutation evidence for the corrections

| Mutant | Result |
|---|---|
| `format_choice_of` returns the request unnarrowed | **killed** — the narrowing test |
| `format_choice=job.request` at the completion | **killed by mypy**, which is the point |
| `THUMBNAIL_URL_ROLE` back to `_entries[index.row()]` | **killed** — your regression |
| The group's reveal drops the common-folder check | **killed** — your regression |
