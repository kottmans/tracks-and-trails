# Release-candidate suite for `0.1.0` (`T-326`)

**Candidate:** tag `v0.1.0` → commit `5b1bf97e63cb6f6b3ede2f8e75d0feccda3404a3`, the thirteenth
commit the tag has named.

**Earlier candidates, none published:**

| Tag at | What happened |
|---|---|
| `ff95306`, `412e93b`, `095b788` | Release runs failed before drafting (`T-324`) |
| `3c011b8` | Drafted, and this suite passed on it. The release review requested changes: `T328-R3` (Critical, a stale menu's *Retry* re-queued a DRM failure) and `T328-R4` (the §11 walk). Corrected in `246dcdf` |
| `246dcdf` | Drafted. While preparing the §11 sheet, `T-340` found that no part of the application opened a job's log (§11 criterion 6, `REQ-019`). Corrected in `3f41813` |
| `3f41813` | Drafted. The Ubuntu clean machine, both network suites, the Sandbox and the canary passed. Then `T-341`: **the AppImage could not download on Fedora** (its Debian-built OpenSSL found no certificates there). Corrected in `93c7357` |
| `93c7357` | Drafted; every machine check passed. The focused review found two more DRM retry paths (`T328-R3`, second pass). Corrected in `8d70e01` |
| `8d70e01` | Drafted. Reported from a Windows laptop at 125%: *Add URLs* and *Preferences* opened with their title bars above the screen (`T-342`); corrected in `a988847`. The maintainer then asked for progress while a download is processed (`T-344`, in `0.1.0` by the maintainer's choice), added in `55dcf05`. `682f71d` (`T-343` filed) was tagged and its release run cancelled before drafting |
| `55dcf05` | Drafted; the Linux checks passed. Trying it, the maintainer found the retry offer opening under the window and a chip that did not say what its percentage was of (`T-345`, `81d7bdd`), and a missing-file notice that vanished (`T-346`, `ea49516`) |
| `ea49516` | Release run cancelled before drafting. Review found the missing-file boxes reading a path as markup (`T346-R1`). Corrected in `48cf076` |
| `48cf076` | Release run cancelled before drafting. The canary failed two screen-fit tests in its one-process run (two rules sharing one pass count, `T-342`). Corrected in `5b1bf97` |

Each earlier draft was deleted before the tag moved. Every machine check below was taken on `5b1bf97`'s
draft; **the one human sitting (item 8's cancellation) was on `3c011b8`**, and its row says so.

**Draft release** from run [`35021277805`](https://github.com/kottmans/tracks-and-trails/actions/runs/35021277805)
(`draft: true`, not a pre-release), with these three assets:

| Asset | Size | SHA-256 |
|---|---:|---|
| `Tracks-and-Trails-0.1.0-setup.exe` | 93,482,037 | `12dab2d3ae168bab9539ffb75fb886ef406f47fe38711df68004c727fc4111f7` |
| `Tracks_and_Trails-0.1.0-x86_64.AppImage` | 68,311,544 | `37a3a7b0c4c7aef82e80edb13404fbe0a95ebc2d8535e321169c370224656992` |
| `SHA256SUMS` | 206 | — |

`gh release download v0.1.0` then `sha256sum -c SHA256SUMS` gives **OK** for both artifacts. Every
item below that names an artifact was run on those downloaded bytes, not on a local build.

**No item is marked passed without its artifact**, which is this task's own acceptance criterion.
Items 6, 7, 9, 11–15 are outside this task's scope; `T-328`'s release review takes them from their
owning tasks.

---

| §8 item | Platform | Satisfied by | Result |
|---|---|---|---|
| 1–2: static gates and the full default suite | Linux and Windows | `ci.yml` run [`35021004959`](https://github.com/kottmans/tracks-and-trails/actions/runs/35021004959) on `main` at `5b1bf97` | **success**: `linux`, `windows desktop`, `frozen linux`, `frozen windows`, `STARBASE coverage`; `Linux orphans` skipped by its own condition. The tag's duplicate run `35021277780` was cancelled to free `STARBASE`. `STARBASE`'s runner had stopped at 18:56 UTC (its task starts only at logon) and was restarted with the maintainer's consent |
| 3: `pytest -m network` | Linux | Local run at `5b1bf97` ([output](2026-09-14-T326-network-linux-0.1.0.txt)) | **2 passed, 2 skipped** (the two Windows-only UI files) |
| 3: `pytest -m network` | Windows | `STARBASE`, logged-on session, checkout at `5b1bf97` ([output](2026-09-14-T326-network-windows-0.1.0.txt)) | **2 passed** |
| 4: every §7 mandatory test | both, in the default suite | enumerated below | **Present for all 11 areas.** The DRM area failed at `93c7357` and was corrected in `8d70e01`; the release review recorded the blocker resolved at `ea49516`. See below |
| 5: previous release's database migrates | — | — | **N/A**: `0.1.0` is the first release. The obligation for `0.2` is in `docs/RELEASE.md` §*The release commit itself*: the `0.1.0` database is `tests/fixtures/schema_versions/v12.sql` |
| 8: frozen smoke, launch and no recursive launch | Linux and Windows | run `35021277805`: `AppImage` and `installer` *The probes, on the release build* | **success** |
| 8: a real download from the release build | Linux | [`linux-0.1.0.md`](linux-0.1.0.md) (`ubuntu:24.04`) and [`linux-fedora-0.1.0.md`](linux-fedora-0.1.0.md) (`fedora:44`); and `--download-probe` run directly on the maintainer's Fedora 44 host with `SSL_CERT_FILE` and `SSL_CERT_DIR` unset | **PASS** on both clean machines, 61,878,609 bytes each; the host download **OK**, 61,878,609 bytes in 6.2 s. The `3f41813` draft **failed** that host download and the Fedora clean machine (`T-341`) |
| 8: a real download from the release build | Windows | [`windows-0.1.0.md`](windows-0.1.0.md): the draft installer in Windows Sandbox | **PASS**: two downloads, the second the 1080p MP4 preset (134,886,020 bytes in 13.5 s) |
| 8: cancel one download while another runs, and a normal exit | Linux and Windows | **A sitting**, by the maintainer, on the `3c011b8` drafts, 2026-09-14; Linux on the maintainer's machine **spock** (named by the maintainer when asked, during the review) | *(answered on an earlier candidate)* the other download kept going and finished; File → Quit closed cleanly; nothing was left running. **Not a result for `5b1bf97`**: cancellation, the other download completing, and a normal quit are owed again on the candidate being approved (`T328-R4`). Spock's distribution and trust store were not recorded |
| 10: in-app yt-dlp update from the release artifact | Linux and Windows | run `35021277805`, both jobs' probes include `--ytdlp-update-probe`; both Linux clean machines repeat it | **success**; clean machines **OK** |
| 10a: canary at the bumped baseline | Linux | `ytdlp-canary.yml` run [`35021322867`](https://github.com/kottmans/tracks-and-trails/actions/runs/35021322867), dispatched on `main` at `5b1bf97` | **success**: installed `yt_dlp-2026.8.19`; **4,692 passed, 45 skipped, 14 deselected** (the canary's expected-stale list) |

**Clean-machine runs** (`§8` item 7, owned by `T-318` and `T-039`, recorded here because item 8's
download is their transfer):

- **Linux, `ubuntu:24.04`**, [`linux-0.1.0.md`](linux-0.1.0.md), and **Linux, `fedora:44`**,
  [`linux-fedora-0.1.0.md`](linux-fedora-0.1.0.md), both verdict **PASS**:
  - the pre-install check found no Python, toolchain, Qt or ffmpeg;
  - version, process model, bundled yt-dlp, database, in-app update and a real download all passed;
  - the application stayed up for 20 s offscreen.

  The asset was made executable first (`chmod +x`), the step the release notes give users; a
  release asset downloads without its executable bit, which made the first `3c011b8` attempt fail.
  **The Fedora run is new with `T-341`**, and its control is recorded there: the `3f41813` draft
  fails it and a build with the correction passes.
- **Windows**, [`windows-0.1.0.md`](windows-0.1.0.md), verdict **PASS**:
  - installed silently, per-user, without elevation, into a directory already holding a sentinel;
  - placement checked against the installer's own log;
  - a window appeared after about 2 s;
  - two real downloads over TLS;
  - uninstall removed all installed files and kept the user data and user-owned files byte-identical;
  - the uninstall entry reads `/SILENT /ASK`;
  - with the application open, the removal is refused;
  - with the database locked, it is logged incomplete;
  - run by hand, `/REMOVEDATA` keeps the data.

  This is also `T-322`'s first criterion, *built by `T-324`'s workflow*.

---

## Item 4: the §7 mandatory tests (enumerated at `3c011b8`, all still present at `5b1bf97`)

Enumerated from `pytest --collect-only` over `tests/`, with each body read. This supersedes the
2026-09-12 list as the basis for the next release's diff. Its tests all still exist, but some prove a
neighbouring property rather than the one stated: its *Worker crash* entry names
`test_a_hard_kill_mid_write_leaves_the_database_readable`, which is about the database surviving a
kill, not about a killed worker becoming `WORKER_CRASH`. All run in the default suite: none carries `network` or
`windows_desktop`.

| §7 area | Tests |
|---|---|
| Layering | `tests/unit/test_layering.py::test_the_analyzer_detects_synthetic_violations` (a Qt import under `core/` and `import yt_dlp` under `ui/` are flagged); `::test_module_respects_the_layer_rules` (every source file, which is what fails the suite); `::test_every_module_is_actually_guarded` |
| Cancellation | `tests/integration/test_manager.py::test_cancel_stops_a_real_in_flight_download_within_the_budget`; `::test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget`; `::test_cancelling_a_download_kills_what_the_worker_spawned` |
| Worker crash | `tests/integration/test_manager.py::test_a_killed_worker_becomes_worker_crash_with_its_exit_code`; `::test_the_application_survives_a_worker_crash_and_can_start_another`; `::test_a_worker_killed_from_outside_does_not_leave_its_grandchild_behind` |
| Crash recovery | `tests/unit/test_persistence.py::test_a_job_left_in_flight_is_recovered_to_a_retryable_failure` (`running`, `probing`, `post_processing`); `tests/integration/test_crash_kill.py::test_jobs_left_in_flight_by_the_kill_are_recovered_at_the_next_startup`; `tests/integration/test_composition.py::test_interrupted_jobs_are_recovered_and_offered_by_the_composed_application` |
| State machine | `tests/unit/test_job_state.py::test_every_ordered_pair_agrees_with_the_architecture`; `::test_production_matches_the_architecture_relation_exactly`; `tests/unit/test_models.py::test_with_status_refuses_an_illegal_transition`; `tests/unit/test_persistence.py::test_recovery_routes_through_the_state_machine` |
| Path safety | `tests/integration/test_worker.py::test_a_template_that_renders_outside_is_rejected_not_written`; `tests/unit/test_paths.py::test_a_template_that_escapes_the_directory_is_refused_not_redirected`; `::test_hostile_titles_stay_inside_the_output_directory`; `::test_every_ntfs_illegal_character_is_replaced`; `::test_reserved_device_names_are_defused_including_with_extensions` |
| Log redaction | `tests/unit/test_redaction_gate.py::test_no_supplied_secret_survives_into_a_log`; `tests/unit/test_logging.py::test_a_cookie_file_path_never_reaches_the_file`; `::test_a_token_in_a_percent_style_argument_is_redacted`; `tests/integration/test_worker_logging.py::test_a_spawned_workers_line_reaches_the_parents_log_without_its_token` |
| DRM | `tests/integration/test_manager.py::test_only_a_network_failure_retries_itself[DRM_PROTECTED]`; `tests/integration/test_worker.py::test_a_drm_item_fails_without_attempting_extraction`; `tests/unit/test_errors.py::test_drm_and_cancelled_are_never_retryable`; `tests/ui/test_job_detail.py::test_a_drm_failure_offers_no_retry_at_all`; `tests/ui/test_queue_view.py::test_a_stale_group_action_never_routes_retry_for_drm` |
| Migrations | `tests/unit/test_persistence.py::test_every_migration_runs_forward_from_real_historical_data` (v1 to v12); `::test_a_frozen_fixture_exists_for_every_schema_version_but_the_latest`; `::test_the_completion_record_is_purged_upgrading_from_every_version_that_kept_one`; `::test_the_purge_takes_the_completion_record_and_nothing_else` |
| Settings freeze | `tests/integration/test_composition.py::test_a_settings_change_mid_flight_does_not_alter_a_running_jobs_request` |
| Widget destruction | enforced by the autouse fixture `_no_orphaned_views` in `tests/ui/conftest.py`, using `tests/qt_lifecycle.py`; proven to fail by `tests/ui/test_suite_isolation.py::test_a_test_that_leaves_a_collectable_widget_is_the_test_that_fails`, `::test_collecting_the_cycle_inside_the_test_does_not_hide_it` and `::test_the_exemption_marker_cannot_be_claimed_by_a_sibling` |

**Two weaknesses the enumeration found at `3c011b8`, and what became of them:**

1. **DRM's *no bypass path* was enforced at the UI, not in the manager.** This record first
   called it unreachable, and that was wrong: the release review reproduced a stale menu's *Retry*
   re-queueing a `DRM_PROTECTED` job (`T328-R3`, Critical). **Corrected in `246dcdf` for the queue
   path**: `DownloadManager.retry` refuses a failure that is not retryable, at call time and again
   at write time, and the queue view rechecks a run-again verb against the row.

   **Two further paths were open at `93c7357`**, found by the focused review with real workers, so
   this candidate **does not meet the DRM area**:
   - an automatic retry planned for a `NETWORK` failure outlived a manual retry that failed
     `DRM_PROTECTED`, and ran the job again unasked;
   - Add URLs' *Read this URL again* and *Retry the ones that failed* read a DRM line again under
     a new staged job.

   Both are corrected in `8d70e01` (`T-328`'s second-pass entry), and the release review recorded
   the DRM blocker resolved at `ea49516`. This suite was retaken on `5b1bf97`.
2. **Settings freeze had one proving test**, and a second that claimed the area without using its
   changed defaults. That test is renamed to the round trip it proves
   (`test_a_stored_request_reads_back_exactly_as_it_was_queued`, `T326-R5`); the composed test
   above is the proof.

Minor, from the same reading:

- the kill-produced database in `test_crash_kill.py` recovers PROBING rows, while RUNNING is covered
  by the unit and composed tests;
- the layering check reads import statements, so `importlib.import_module` is outside it (its
  docstring says so);
- migrations assert *data intact* for the `jobs` table, the only table that survives.

**Not covered by this file:** §8 items 6, 7, 9, 11, 12, 13, 14 and 15 as release-gate judgements. Items 9
and 11–13 ran as `artifact_gates.py` in run `35021277805` on both artifacts, item 14 is `REL-008`'s `0.1.0` exception, and
item 15 is `T-327`'s approved session. `T-328` records them.
