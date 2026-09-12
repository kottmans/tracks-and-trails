# Release-candidate suite — the machine half of `TESTING` §8 (`T-326`)

**Status: partial, and the reason is structural.** `T-326` runs the gate **against a release
candidate**, and there is no candidate — no `v*` tag has been pushed, which is `T-324`'s trigger
and the maintainer's act. The items that do not need one were run on 2026-09-12 and are below;
the items that do are listed with what will satisfy them.

**No item is marked passed without its artifact**, which is this task's own acceptance criterion.

## Item 3 — `pytest -m network`, both platforms

**This suite runs nowhere automatically.** `pyproject.toml` sets `addopts = "-m 'not network …'"`,
so CI has never executed it. That makes this a deliberate manual run, and its first execution
found a defect.

| Platform | Command | Result |
|---|---|---|
| Linux | `pytest -m network -q` | **2 passed, 2 skipped** in 9.88 s |
| Windows (`STARBASE`, logged-on session) | same, via `run-on-starbase.sh` | **2 passed** in 31.73 s |

The two Linux skips are `tests/ui/test_windows_accessibility.py` and
`tests/ui/test_windows_desktop.py`, both Windows-only and skipping with a reason.

**The first run failed, and not because of the network.** `test_one_real_url_downloads_end_to_end`
raised in 3.35 s:

```
RuntimeError: '…' already has a download session;
one job holds one session at a time, whichever lane it is in
```

Its own docstring says *"Never executed in the environment that wrote it… the first real run is
whoever runs `pytest -m network`."* This was that run. The test pressed Start on the queue **and**
called `manager.start(job_id)` — but with the queue running, `add_to_queue` *admits* the job and
admission starts it, so the explicit start was a second one. It had drifted from the offline
sibling its docstring calls *"deliberately the same shape"*:
`test_a_url_becomes_a_file_with_the_bytes_it_reported` presses Start once and then only waits,
which is what a user does. **Never having been run, the drift could not show.** Corrected, and
both platforms pass.

## Item 4 — every §7 mandatory test, enumerated by name

Recorded so the next release **diffs this list** rather than re-reading the table.

| §7 area | Test |
|---|---|
| Layering | `test_layering.py::test_no_module_imports_upward_or_sideways` |
| Cancellation | `test_manager.py::test_cancel_stops_a_real_in_flight_download_within_the_budget`; orphans by `test_orphan_scan.py::test_the_scanner_sees_a_known_orphan` |
| Worker crash | `test_crash_kill.py::test_a_hard_kill_mid_write_leaves_the_database_readable` |
| Crash recovery | `test_persistence.py::test_a_job_left_in_flight_is_recovered_to_a_retryable_failure`; `test_the_recovered_statuses_are_the_three_the_architecture_names` |
| State machine | `test_job_state.py::test_every_status_has_an_entry_in_the_transition_table`; `test_no_status_transitions_to_itself` |
| Path safety | `test_output_template.py::test_no_escape_attempt_leaves_the_output_directory`; `test_a_symlink_escape_is_rejected_through_the_public_entry_point` |
| Log redaction | `test_log_redaction.py::test_a_cookie_path_is_redacted_even_when_yt_dlp_itself_named_it` |
| DRM | `test_errors.py::test_drm_and_cancelled_are_never_retryable` |
| Migrations | `test_persistence.py::test_every_migration_runs_forward_from_real_historical_data` |
| Widget destruction | **not one test** — `tests/qt_lifecycle.py` enforces it at every `tests/ui` boundary, with `tests/ui/_leaks_a_collectable_widget.py` as the known positive. That is how §7 describes it |
| **Settings freeze** | **not found — see below** |

### The gap this enumeration found

**§7 requires *"a settings change mid-flight does not alter a running job's `DownloadRequest`"*,
and no test asserts it.** What exists is the structural half: `test_models.py::test_every_model_is_frozen`
proves `DownloadRequest` is a frozen dataclass, and `ARC-008` has composition read settings once.
Frozen means the object cannot be mutated; it does **not** prove that a running job keeps the
request it started with when the user changes a setting — the failure mode would be a *new*
request being built and handed to something in flight.

**This is reported rather than resolved.** Closing it is a test to write, and which task owns it
is the maintainer's call: it is §7 coverage, so arguably a Phase-exit obligation rather than
`T-326`'s, whose job is to *check the list*, not to fill it.

## Item 5 — the migration check

**`N/A` for `0.1.0`, and that is only true once.** §8 item 5 is *"the previous release's database
opens, migrates, and retains data"*; there is no previous release. The obligation for `0.2` is now
written into `docs/RELEASE.md`'s release-commit steps: **keep a `0.1.0` database fixture at the
`0.1.0` tag**, because it cannot be reconstructed afterwards from a schema file — what it has to
prove is that *real rows* survive.

## Item 10a — the yt-dlp canary

**Not applicable: the pinned baseline is not being bumped in `0.1.0`.** `OPS-002` pins
`2026.07.04` and the release ships it. Recorded so a reader does not look for a canary run that
was never owed.

## Items waiting on a release candidate

| Item | What will satisfy it |
|---|---|
| 1 · static gates, both platforms | the `ruff`/`mypy` steps' run id **at the RC commit** |
| 2 · full default suite, both platforms | the `linux` and `windows desktop` job ids at the RC commit |
| 8 · frozen smoke on the release builds | `T-324`'s `build-linux` / `build-windows` probe steps |
| 10 · in-app yt-dlp update from the release artifact | `T-324`'s `--ytdlp-update-probe` step |

**Items 8 and 10 have been run by hand on the release artifacts** — 5 of 5 probes on the Windows
build and 4 of 4 on the AppImage, recorded in `T-319` and `T-321`. What is missing is *at the
candidate*, through the workflow, which is what the gate asks for.
