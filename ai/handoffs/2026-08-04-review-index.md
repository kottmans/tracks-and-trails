# Review index — everything outstanding as of 2026-08-04

You are the Reviewer (`AGENTS.md` §3). **Start here.** Five things await review across two detailed
handoffs, and one of them is a phase exit that depends on two of the others being sound — so the
order below is not arbitrary.

**Repository:** `/mnt/storage/software_projects/tracks-and-trails/tracks-and-trails`, branch `main`
**Head:** `444b7fc`. The last head with full CI evidence is `8d1b01c` — green on all five jobs
including `windows desktop`. `444b7fc` is documents only.

---

## Review in this order

### 1. `T-127` — the two phase-proof gates *(read first)*

**Handoff:** `ai/handoffs/2026-08-03-phase-2-exit-corrections.md`, sections `P2EXIT-R1` and `R2`.

Both were the named evidence for exit criteria 1 and 5, and both passed with their subject removed.
Read this first because **item 5 below cannot be judged until you believe these two gates**.

The thing to check hardest: `P2EXIT-R1` had a *second* defect the review did not name — a 60-second
wait for orphans to die against an 8-second download, so an orphan finished and exited inside the
window and was recorded as reaped. Verify that claim, because it means the correction has two
load-bearing parts and only one of them was asked for.

### 2. `T-122` — the paste-scaling gate

**Handoff:** same document, `P2EXIT-R3`. Short. It was reworked to your original recommendation
rather than the one `T-122` first implemented: the absolute budget and structural count are the
gates, the ratio is diagnostic.

### 3. `T-124`, `T-125`, `T-126` — `UX-005` in code

**Handoff:** `ai/handoffs/2026-08-03-t124-window.md`. The largest piece of work here: the window
became two tabs with no detail pane, the row carries every verb its state permits, `HistoryView`
moved onto the shared delegate, the format control appears exactly while `retarget()` accepts it,
and history removal exists.

**Two places I would push on if I were you:**

- **Where the verbs sit.** `UX-005` §4 says they share the row's last line with the format control,
  while its *"what this does not decide"* defers that control's slot to `UX-004`. I read that as
  "verbs right-aligned inside the text area, left of the existing slot". That is a reading, and a
  different one is defensible.
- **`DAT-005` §2.** A decision was *made* during this work, not just implemented — history removal
  never touches a file, and it refuses an opt-in rather than offering one. The reasoning is that
  `UX-001`'s promise stops being a promise once it is conditional. Disagree and the rest follows
  differently.

### 4. `DAT-005` itself

**Where:** `ai/DECISIONS.md`. Obtained from the maintainer mid-work because `UX-005` §9 describes a
removal control and then refuses to specify it — *"a `DAT-` entry, not a button"* — and `T-125`'s
first acceptance criterion was that the decision exist **before** any code. Worth reviewing as a
decision, separately from the code that implements it.

### 5. **The Phase 2 exit re-review** *(last)*

**Handoff:** `ai/handoffs/2026-08-03-phase-2-exit-corrections.md`, in full.

Your verdict at `5eb2611` was *changes requested — Phase 2 has not exited*, on five findings. All
five are answered:

| Finding | Answer |
|---|---|
| `P2EXIT-R1` | item 1 above |
| `P2EXIT-R2` | item 1 above |
| `P2EXIT-R3` | item 2 above |
| `P2EXIT-R4` | **`OPS-010`**, a maintainer ruling. The Windows suite is back on every push; the `check` duplicate stays dropped; a push can no longer cancel a scheduled run |
| `P2EXIT-R5` | `IMPLEMENTATION_PLAN.md` now records your verdict and which rows failed, rather than claiming criteria 1–5 and 7 met |

**`UX-005`'s three tasks were sequenced in before the exit** by that decision, so items 3 and 4 are
part of what the exit is now being asked about.

---

## Not under review, but read before you finish

**`T-128` and `T-123`** — filed 2026-08-04 from an unattended overnight run. **Nothing was
implemented and nothing was fixed**; they are findings.

- **`T-128`: the result-pump segfault reproduces on Linux.** 2 crashes in 39 full-suite runs,
  `SIGSEGV` in `QEventDispatcherGlib::processEvents` with a live `ResultPump` thread, **both at
  exactly 97 completed tests**. It resembles `T-074` — which is named *"segfaults intermittently
  while the result pump is delivering"* — and is filed **separately on purpose**: Windows produced
  an access violation, this is a SIGSEGV, `T-074`'s faulting object was never determined, and a
  stack is not a cause. **Tell us if you think that separation is wrong.**
- **It changes `OPS-007`'s premise.** That decision accepted `T-074` as residual risk *because* 361
  attempts produced zero events. Neither `OPS-007` nor `T-074` was rewritten — re-accepting is a
  reasonable outcome and it is the maintainer's — but the reasoning no longer stands unexamined.
- **`T-123` is answered:** `-n auto` is ~7x (58 s against ~400 s). The single failure was
  `test_the_survival_check_can_tell_a_live_process_from_a_dead_one`, which is the predicted hazard
  rather than a flake.

**The mutation numbers are in `ai/handoffs/2026-08-04-overnight-results.md` and should be
discounted.** ~433 survivors of 1185 sounds alarming and mostly is not: tests reference
`Verb.CANCEL` and `HEADLINE_ROLE` as symbols, so mutating the value moves both sides together and
the mutant is equivalent by construction. Quoting a kill rate from that file would mislead in the
flattering direction. The genuine logic survivors underneath are untriaged and are honest work.

---

## Evidence

| Gate | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | clean, 151 files |
| `mypy src` / `mypy` / `mypy --platform win32` | clean — 44, 104, 104 files |
| Full suite (Linux) | **2034 passed, 11 skipped, 2 deselected** in 6m47s |
| Soak | **39 passes, 37 green, 2 segfaults** (`T-128`) |
| CI at `8d1b01c` | all five jobs green, `windows desktop` included |

**2034 against 1986 at the start of this work: 48 net new tests.**

## What is still not verified

- **`444b7fc` on Windows** — it is documents only, and CI runs on push regardless.
- **`T-121`'s root cause.** Unreproduced, and doubly latent now that hosted Windows does not run.
- **A real extractor.** Every probe replays a fixture or a localhost server.
- **The dark theme has never been on a screen**; `T-120`'s contrast is arithmetic.
- **`OPS-004`'s subjective half** — whether Windows rendering looks right. Blocks first release,
  not this phase, and has said so since Phase 0.

## Corrections I made to my own work, which you may want to check landed

- Two tests I wrote were **deleted rather than committed** — one `assert ... or True`, one asserting
  a list stayed empty when nothing could have filled it.
- A mutation **survived twice for reasons that were not the code**: the test used the first of four
  presets sharing a selector, and then `ruff format` reflowed the target so the replace matched
  nothing. Both are in `ai/TESTING.md` §13 now.
- `JobProgressView.detach` got a **view-level test before** its only test anywhere was deleted.
  `UX-005` defers that widget's fate, and a deferral must not become a silent deletion.
