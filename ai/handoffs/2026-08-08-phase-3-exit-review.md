# Phase 3 exit review — request, 2026-08-08

**From:** Implementer
**To:** Reviewer (Codex)
**What is asked:** the **independent phase exit review** — exit criterion 6. It has never been
requested, and it is the last thing between Phase 3 and its exit.
**Candidate head:** `7958518`, clean tree
**Authority for the criteria:** `ai/IMPLEMENTATION_PLAN.md` §Phase 3

---

## Read this first, because it is the row most likely to be wrong

**Phase 1's exit review found two wrong rows in its criteria table. Phase 2's found more** —
`P2EXIT-R11` was a criterion *silently broken by a change made after its proof*, `P2EXIT-R12` was a
checklist claiming a pass over its own recorded failures, and `P2EXIT-R14`/`R15` were records
disagreeing with each other six times.

**Treat the table below as a claim under review, not as context.** Every verdict in it is the
implementer's, and this project has a three-phase record of exactly this table being where the
error lives.

The two rows I would attack first are named under each.

## The six criteria, as claimed

| # | Criterion | Claimed | The part worth attacking |
|---|---|---|---|
| 1 | The format table matches `yt-dlp -F` for a fixture set of URLs | **Met** | Rests on evidence **plus a maintainer amendment** — `OPS-013`. `fps` is covered by a *derived* fixture, and the criterion was re-bound to "where the source reports it". See §1 |
| 2 | A separate video + audio selection merges correctly via ffmpeg **on both platforms** | **Met** | The Windows half is **one CI run**, `31233348009`. And until `T-189` landed this week, that proof could have become a silent skip. See §2 |
| 3 | Output template preview matches the written path in every tested case, incl. Windows-illegal titles | **Met** | `T-112`; preview and write are one function (`contained_output_path`) |
| 4 | Path containment holds: no rendered template escapes the output directory | **Met** | `T-112`, and two Criticals were found here in review — `T113-R1` and `T109-R8`, both about a path this application did not choose |
| 5 | A partial download resumes after restart, or clearly states it cannot | **Met** | `T-113` |
| 6 | Reviewed and signed off | **This request** | — |

## §1 · Criterion 1 rests on an amendment, and you should test that it was legitimate

`T-107`'s criterion refined this to *every column `REQ-003` names being populated from a recorded
fixture*, and then hit a column **no acceptable source supplies**: `fps` is reported by none of the
sources `ai/TESTING.md` §5 permits. `OPS-013` amended the criterion to bind *where the source
reports it*, leaving `fps` on the derived fixture.

**The question for you is whether that amendment narrowed the criterion honestly or narrowed it into
nowhere.** My view is the former — the alternative was a source that churns weekly, which satisfies
the letter and breaks the property §5 chose those sources for — but it is a maintainer amendment to
an exit criterion and it deserves the same suspicion as the rest of the table.

**One thing found this week that bears on it and was not acted on**: `dash_akamai_big_buck_bunny`,
captured for `T-188`, **reports `fps` on all ten video formats**. Whether that reopens `OPS-013` is
`OPS-013`'s question and `T-185`'s, not `T-188`'s, so it is recorded in `T-188`'s entry and left
alone. **You may reasonably think it should have been acted on before this request.**

## §2 · Criterion 2's Windows half is one run, and was fragile until this week

The Windows evidence is CI run `31233348009` at `870d56f`: `STARBASE` recorded **ffmpeg 8.1.2** and
`test_a_chosen_video_and_audio_pair_produce_one_merged_file` **passed rather than skipped**.

**Until `T-189` landed, nothing kept that true.** The test took a fixture that *skips* when ffmpeg is
absent, on a self-hosted runner that **records rather than installs** it — so the day that machine
lost the tool, a required proof would have become a `SKIPPED` line inside a green job and this
criterion would have been evidenced by nothing, with nothing going red. `T-189` makes that a failure.

**`T-189`'s own gate has never executed on a runner.** No `pyyaml` is available here and I would not
install one into the maintainer's environment to lint a workflow, so `ci.yml` was verified
structurally. **The first CI run at this head is the requirement's first genuine exercise**, and it
has not happened.

## §3 · What the phase delivered

**Nine deliverables, all approved.** `T-107`, `T-108`, `T-109`, `T-110`, `T-111`, `T-112`, `T-113`,
`T-114`, `T-181`.

**Two of them removed a Phase 2 deliverable**, which is deliberate and worth confirming you are
content with: `T-169` withdrew the completion record and `T-170` removed the History tab and the
private ledger behind it — migration `0009` removes the table from upgraded databases too. **The
application now keeps no record of what has been downloaded at all.**

**Six items were ruled into the phase on 2026-08-08** after sitting unruled under
`## Proposed — Phase 3`, which is the position both prior exit reviews found wrong rows in. All six
are answered: `T-143`, `T-180`, `T-189`, `T-186`, `T-188` built and approved; `T-171` **refused** by
`DAT-008`, which is a disposition rather than a gap.

**Three decisions were accepted during the phase** and are part of what you are signing off:
`OPS-013` (criterion 1's binding), `DAT-007` (the per-database thumbnail cache), `DAT-008` (no
file provenance).

## §4 · What I would look at hardest, if I were you

- **The criteria table.** Three phases, three times it was where the error was.
- **`OPS-013` and the `fps` finding** (§1). An amendment plus a fact that may undercut it.
- **`T-189`'s unexecuted workflow** (§2). The thing protecting criterion 2 has not run.
- **Whether "answered" is the right bar for the six.** The ruling asked for each to be
  *dispositioned*, not built. `T-171` is refused and `T-188` needed three passes; if you think a
  disposition is weaker than this phase should accept, that is a criterion-6 judgement.
- **`ai/TASKS.md`'s header block.** Its `Last updated` line still describes `T-111` as "implemented
  and sits in `## In Review`", which was true when written and is not now. I found it while editing
  and left it rather than quietly correcting a record inside the boundary under review — **it is
  stale and I am telling you rather than fixing it.**

## §5 · Known limits, stated rather than discovered

- **Windows runtime is verified only by CI.** `OPS-003`: the maintainer has no Windows machine, so
  the self-hosted runner is the only Windows environment this project has.
- **`ci.yml` has not executed at this head.** §2.
- **Real sites are unverified.** Every fixture is recorded or derived, by `ai/TESTING.md` §5.
- **`T-192` is open and in review** — a status-bar placement fix found by the maintainer today. It
  is Phase 4 polish and not claimed as part of this exit.

## Checks, with their actual results

Run at `7958518`, Linux, bytecode caching disabled:

| Check | Result |
|---|---|
| `git diff --check` | clean |
| `ruff check` | All checks passed |
| `ruff format --check` | 221 files already formatted |
| `mypy` (src + tests) | Success: no issues found in 125 source files |
| `mypy --platform win32` | Success: no issues found in 125 source files |
| `pytest tests/unit/test_task_placement.py` | 14 passed |
| `QT_QPA_PLATFORM=offscreen pytest` | **2803 passed, 17 skipped, 2 deselected** in 380 s |

**Last full green CI: all five jobs at `54e24ab`, run `31272628973`.** Everything since is
uncommitted-then-committed work that CI has not seen — **including `T-189`'s workflow change**.
