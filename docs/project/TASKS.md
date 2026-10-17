# TASKS.md — Tracks & Trails

**Purpose:** Unfinished work: review, ready, proposed and blocked tasks.
**Owner:** Planner (priorities); Implementer (task/status); Reviewer (review disposition)
**Last updated:** 2026-10-11
**Update when:** Work starts, changes scope/status, closes or reopens.

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
Complete and Cancelled records live in [COMPLETED_TASKS](COMPLETED_TASKS.md).
Move each record there in the same update that closes it; keep no closed-task
stubs here. Preserve IDs, evidence, limitations and follow-up routes. Check both
files before allocating an ID; IDs are never reused. Task-reading tests and
the placement gate read both files. Current phase and blockers are in [STATUS](STATUS.md).

## In Review

### T-249 — The sidecar writers: description, info JSON and thumbnail files

**Status:** In Review — correction 1 built 2026-10-17, awaiting the focused re-review of
`T249-R1`. Changes requested 2026-10-16 at `8b0aad6`, one Critical blocker
([record](reviews/T-249.md#2026-10-16--initial-sidecar-writer-review)); built 2026-10-14.
*(Was Ready:)* ruled 2026-10-11 (`DAT-003` and `UX-015` amended), after `T-362`. *(Was
Proposed:)* filed 2026-08-16 by `T-183`
**Options (7):** `--write-description`, `--no-write-description`, `--write-info-json`,
`--no-write-info-json`, `--write-thumbnail`, `--no-write-thumbnail`, `--write-all-thumbnails`
**Specific criteria:** every file these write lands inside the chosen directory, through `T-034`
rather than beside it. **`--write-thumbnail` shares `writethumbnail` with the application**
(`T-183` Finding 6): `build_options` sets it to embed and then delete, this control sets it to
keep, and the resolution is one written rule with a test — the control is tri-state (off, one,
all). **`--write-info-json` writes a file yt-dlp's own help calls personal information**, so
`DAT-003`'s redaction question is asked of it before it ships, not after.


#### Maintainer rulings, 2026-10-11 — the design, before the code

Mapped first, with a real worker session. **Through the options field, `--write-info-json` already
keeps a file that carries the session's cookie values and any typed request headers**: with a
cookies file, every format's `cookies` field held the cookie, and `--add-headers "Authorization:
Bearer …"` was in each format's `http_headers`. yt-dlp's *clean* step strips neither. Nothing
shipped it, since `0.1.0` predates the field. Three rulings, all as recommended:

1. **Strip them and keep the file** (`DAT-003`, amended): before an info JSON is moved into the
   download folder, every `cookies` field and the request headers are removed, whichever route
   asked for it. Everything else stays as yt-dlp writes it.
2. **Fixed within this task**, not by an interim refusal: `main` is unreleased and `0.2.0` cannot
   ship before this task.
3. **One *Keep beside the file* group, directly below *Embed in the file*** (`UX-015`, amended):
   two checkboxes and three thumbnail radio buttons, none, the best or all.

Settled already, and not reopened: the thumbnail key is shared as a union, the user's keep
surviving the application's embed (`ARC-010`, amended 2026-09-20); and a sidecar lands in the
chosen folder with its media, which the options field's own work built (`claim_outputs`, the
probe's file landed there).

#### Built 2026-10-14

- **Three fields, shared by `Preset` and `DownloadRequest`**: `write_description`,
  `write_info_json` and `keep_thumbnails`, a `KeptThumbnails` of `none`, `best` or `all`. They are
  copied by `to_request`, kept in `FormatChoice`, and read back as the enum from `settings.toml`
  and from a job's stored request. An older row without them keeps nothing.
- **`build_options` asks for each on the download only**: `writedescription`, `writeinfojson`,
  and `writethumbnail` for the best thumbnail or `write_all_thumbnails` for all of them. yt-dlp's
  own key for `--write-all-thumbnails` is separate, and no option string names it. The embed's
  `already_have_thumbnail` now follows the keep, which completes `ARC-010`'s 2026-09-20 union.
  **Six intents are held to `parse_options`**, key by key. Embedding is left out of that
  comparison: there the application sets `writethumbnail` itself so there is a picture to embed,
  which yt-dlp's command line arranges differently with the same result; the union tests hold
  that.
- **The info JSON is stripped twice, by design** (ruling 1). A `before_dl` postprocessor strips
  the file the moment yt-dlp writes it, because yt-dlp writes it before downloading. So the copy
  in staging is clean for the whole download, and stays clean when a failed attempt keeps staging
  for its resume (`T-113`). The worker strips again before claiming, so a yt-dlp that does not
  record the path cannot move secrets into the folder. `without_secrets` removes every `cookies`
  and `http_headers` key at any depth. The file is rewritten through a sibling and replaced
  atomically, and one that cannot be read raises rather than being kept as it is.
- **The editor's *Keep beside the file* group** sits directly below *Embed in the file*
  (ruling 3): two checkboxes, a line under the info JSON saying what is taken out of it, and
  three radio buttons that each name their whole choice. None needs ffmpeg, so none is
  withdrawn without it. The format description adds *keeping the description, the info JSON
  and the thumbnail*, and these three are set aside when finding the built-in a download
  starts from.
- **The hatch.** The seven spellings join the audit's built table, now 35 rows against 30
  unbuilt. Admission refuses all seven for their control, `--write-info-json` included, which
  closes ruling 2's interim route through the options field. `write_all_thumbnails` joins the
  library-only keys. `merge_thumbnail` stays as the union's written rule, though no admitted
  spelling now reaches it.
- **Tests that used these spellings through the hatch moved to the fields**:
  `test_retained_sidecars.py`, whose page now carries a description too, and three of
  `test_hatch_request.py`'s thumbnail cases. They test the same claim, reached the way a user now
  asks.
- **New tests.** `test_kept_beside.py` covers the model, storage, the mapping and the stripping.
  `test_kept_info_json.py` uses real yt-dlp with a cookies file and a typed `Authorization`
  header, on three routes: the kept file after success; the staging file after a failed
  download; and success with the hook replaced by one that does nothing. The editor tests cover
  placement, opening and coming back, the radio buttons, the name, the note and the keyboard.
- **Mutations, 14 of 14 caught**, on a copy of the tree. Each of the four keys removed; the
  embed deleting a kept thumbnail; `http_headers` kept; either stripping pass removed; the preset
  not carrying the keep; either enum read back as a bare string; the editor ignoring its radio
  buttons; the name clause emptied; the built-in match not setting the three aside.

**Checks, 2026-10-14, on Linux:** `ruff check .` and `ruff format --check .`; `mypy src`, bare
`mypy` and `mypy --platform win32`; `python tools/ytdlp_option_table.py --check`; `tests/unit
tests/ui` under `-n auto`, **5,503 passed**, 21 skipped; `tests/integration` **530 passed**, the
three new info JSON cases among them. No Windows run.

**Correction, 2026-10-14, found while gating `T-251`: bare `mypy` was not clean at `8b0aad6`.**
It reports one error, `tests/ui/test_options_dialog.py`, in this task's
`test_the_kept_files_group_sits_directly_below_embed_in_the_file`: `scroller.widget()` is
`QWidget | None`, and asserting a call's result does not narrow the next call. Reproduced on a
clean `git archive` of `8b0aad6`. The line above recorded it as passing, which it did not; the
test is unchanged in what it asserts and is narrowed through a local in `T-251`'s commit.

#### Correction 1, 2026-10-17 — `T249-R1`

The review of `8b0aad6` requested changes with one Critical blocker; the Reviewer also verified
the bare-`mypy` correction at `bfda7c9` and asked for nothing more on it. **Corrected, awaiting
re-review.** The correction is on `44d35ff`, whose worker and adapter are `530f114`'s.

| Finding | Correction | Evidence |
|---|---|---|
| `T249-R1`, Critical — a `before_dl` processor failing ahead of the stripper left the cookie and the header in the staging info JSON kept for the resume | **The secrets are never written.** `keep_secrets_out` replaces the `before_dl` hook: it wraps the session `YoutubeDL`'s `sanitize_info`, which every info JSON yt-dlp writes goes through at the pin, so no ordering can bypass it and no file holds the secrets at any moment. The worker strips again, as a second line: before claiming, as before, and now **when the download attempt fails or is cancelled**, removing a staged info JSON it cannot read rather than raising over the job's own reason | `test_a_conversion_that_fails_before_the_download_keeps_no_secret_in_staging`, the review's localhost reproduction through `T-251`'s typed SRT conversion of malformed TTML, with the cookies file and the typed `Authorization` header: **fails at `44d35ff`**, both secrets in `clip (1).info.json`. Run three ways: both lines, `keep_secrets_out` alone, the worker's line alone. `test_without_keep_secrets_out_the_file_is_still_stripped_before_it_is_kept` holds the claim's line alone. Unit tests hold the wrapper over clean and `--no-clean-info-json` serializing, leaving other instances alone, and the staged strip never raising |

**Sibling audit, and a second route it found.** Every way yt-dlp writes an info JSON at the pin
goes through the instance's `sanitize_info`, so each route below is covered by the one wrapper:

- **`--embed-info-json`, admitted through the options field, attached an unstripped info JSON
  inside the kept MKV** of a download that succeeded: `FFmpegMetadataPP` writes it through its
  downloader's `sanitize_info` and attaches it, so no strip of a sidecar could reach it. Reproduced
  with the real worker on `127.0.0.1` at `44d35ff`, both secrets in the kept file. Same ruling,
  same class: *never in a file this application keeps*. Now
  `test_an_info_json_embedded_in_the_file_carries_no_cookie_and_no_header`, which **fails at
  `44d35ff`** and checks the attachment is still there.
- The other `before_dl` processor at the pin, `--convert-thumbnails` (admitted), and any failure
  between the write and the download, including the admitted link-file writers, which run after
  the info JSON and return early when they fail.
- A playlist's own info JSON (`_write_info_json('playlist')`), and `--no-clean-info-json`, which
  keeps `requested_formats` with their headers; stripping is at any depth.
- A worker killed between the write and the download: the file was never written with them.
- The probe writes no info JSON. `--use-postprocessor`, `--exec`, `--load-info-json`,
  `--print-to-file`, `--print` and `--dump-json` are refused already.

**Correction mutations, 9 of 9 caught**, each on a fresh copy of the tree: the wrapper doing
nothing; applied only with `writeinfojson`; stripping the top level only; changing every
`YoutubeDL` rather than the session's; no strip on the failure path; the staged strip doing
nothing, raising on an unreadable file, or keeping it; no strip before claiming.

**Stand-ins.** Three test modules stand in for yt-dlp or the adapter around `_extract`, and each
gained the name the worker now calls. The worker does not step around a `YoutubeDL` without
`sanitize_info`: a yt-dlp lacking it fails the job loudly rather than writing the secrets.

**Checks, 2026-10-17, on Linux, after the correction**, with the project `.venv` on `PATH`:
`ruff check .` and `ruff format --check .` (485 files); `mypy src` (70), bare `mypy` and `mypy
--platform win32` (221 each); the table check up to date; `tests/unit tests/ui` under `-n auto`,
**5,620 passed**, 21 skipped; `tests/integration` **545 passed**. An earlier run without the
`.venv` on `PATH` failed the two toolchain checks, which test exactly that. No Windows run.

---

### T-251 — Subtitle depth: automatic captions, format and conversion

**Status:** In Review — **blocked 2026-10-16 at `bfda7c9` on `T249-R1` alone**
([record](reviews/T-251.md#2026-10-16--initial-subtitle-depth-review)): its typed conversion is a
route to that Critical, so it is corrected in `T-249`, whose correction 1 (2026-10-17) adds this
route's regression; nothing else was asked of this task. Built 2026-10-14 on the implementer's
recommended design, ahead of
`T-249`'s review by the maintainer's instruction that evening
([the amendment](IMPLEMENTATION_PLAN.md#amended-2026-10-14-t-251-may-be-built-before-t-249s-review-returns)).
**All three design questions were ruled on 2026-10-15 as recommended**, so the build stands as
built (`ARC-010` and `UX-015` amended 2026-10-15). *(Was Proposed:)* filed 2026-08-16 by `T-183`
**Options (4):** `--write-auto-subs`, `--no-write-auto-subs`, `--sub-format`, `--convert-subs`
**Specific criteria:** `--convert-subs` installs an ffmpeg post-processor, so `requires_ffmpeg`
answers true for it and the user is told **before** the bytes are spent (`REQ-024`); automatic
captions and real subtitles are distinguishable in the UI, because "no subtitles" and "no *human*
subtitles" are different answers.

#### Mapped 2026-10-14

Measured with the pinned yt-dlp (2026.08.19), on a real YouTube probe and offline against its
captured subtitle maps; the probes are in the implementer's scratch notes, not the repository.

- **A caption map is huge.** A video with five subtitle languages listed **160** automatic
  captions: the same five, `en-orig`, and machine translations into nearly every language YouTube
  has. yt-dlp merges the caption map into the subtitle map before it reads the languages, so
  `all` with captions requested **160 files**, and `all` without them five.
- **That combination was reachable on unreleased `main`.** At `8b0aad6` the options field
  admitted `--write-auto-subs`, and the built-in *Video with embedded subtitles* carries `all`, so
  the two together built `writesubtitles`, `writeautomaticsub` and `subtitleslangs: ['all']` —
  one request to the site per caption. Nothing shipped it, since `0.1.0` predates the field;
  `--convert-subs` and `--sub-format` were admitted the same way. Closed within this task: all
  four spellings and their aliases are now refused for their control, and the model refuses
  captions beside `all`.
- **The flag alone fetches a caption nobody chose.** With no languages named, yt-dlp takes
  English, or the first it finds. So nothing here reaches yt-dlp unless languages are chosen.
- **A language with both is taken as subtitles.** With captions on and `en,fr` asked for, `en`
  came from the subtitles and `fr` from the captions: yt-dlp's own precedence, per language.
- **`--sub-format` takes any text.** `SRT` matched nothing and fell back to the site's last
  format, `vtt`, with only a warning in the log; `srt/best` took `srt`.
- **A conversion replaces the record as well as the file.** `FFmpegSubtitlesConvertorPP` runs
  before the download, deletes the old file and rewrites `requested_subtitles`, which is what the
  worker claims from; so no claim change was needed, and the integration tests below show it.

#### Questions for the maintainer, and what was built meanwhile

Each was built as recommended, provisionally. **Ruled 2026-10-15: all three as recommended**, and
the amendments they imply are written: `ARC-010` (subtitle depth acts on chosen languages, and never
captions for `all`) and `UX-015` (subtitle depth inside *Subtitles*).

1. **How are automatic captions offered?**
   - **(Recommended, built)** In the same language list, after the subtitles, each marked
     *(automatic captions)* and listing only languages with no subtitles, behind one checkbox,
     *Use automatic captions where a language has no subtitles*, which is `--write-auto-subs`
     exactly. A marked entry can be checked only while the box is. The line under the group says
     *no subtitles* and *no subtitles, only automatic captions* apart. Costs: a YouTube list grows
     by about 150 entries, below the subtitles.
   - A checkbox only, applied to the chosen subtitle languages. Costs: a source with captions and
     no subtitles, the case captions exist for, offers nothing to choose.
   - A second list beside the first. Costs: two lists to explain, for one yt-dlp language list.
2. **Format and conversion: one control per yt-dlp option, or one combined?**
   - **(Recommended, built)** Two, each mapping to one option: a *Fetch them as* field in
     yt-dlp's own grammar (`srt/vtt/best`), refused at edit time when it is not one, and five
     radio buttons from *Keep the format they arrive in* to *Convert them to LRC*, withdrawn
     without ffmpeg (a new `FfmpegFeature.SUBTITLES`). No precedence rule is needed. Costs: two
     controls where most users mean one thing, *I want SRT*.
   - One *Subtitle files as* choice setting both. Costs: `--sub-format`'s other preferences, such
     as `ttml`, become unreachable, which `REQ-030` forbids before `0.2.0`.
   - Conversion only, with `--sub-format` reclassified to the hatch. Costs: an audit change, and
     ffmpeg converts what the site would have sent as SRT anyway.
3. **Automatic captions beside `all`: refused, or narrowed?**
   - **(Recommended, built)** Refused by the model, so no preset or request can hold it, and the
     editor never produces it: `all` checks every subtitle and no caption, and naming them is what
     lets a user add captions. Costs: *Video with embedded subtitles* cannot take captions
     without its languages being named.
   - Narrowed silently to the subtitle languages. Costs: a box that is ticked and does nothing.

#### Built 2026-10-14

- **Three fields, shared by `Preset` and `DownloadRequest`**: `automatic_captions`,
  `subtitle_format` and `convert_subtitles`, a `SubtitleFormat` held equal to yt-dlp's
  `FFmpegSubtitlesConvertorPP.SUPPORTED_EXTS`. Copied by `to_request`, kept in `FormatChoice`,
  read back as the enum from `settings.toml` and a job's stored request. An older row has none.
  `ALL_SUBTITLE_LANGUAGES` moved from `core/presets.py` to `core/models.py`, which now refuses it
  beside captions.
- **`build_options` asks for each on the download only, and only with languages**:
  `writeautomaticsub` and `subtitlesformat`. `build_postprocessors` installs
  `FFmpegSubtitlesConvertor` before the download, as yt-dlp's command line does, so
  `requires_ffmpeg` and the pure `needs_ffmpeg` both answer true for a conversion.
- **The probe** gives `MediaInfo.caption_languages`: the caption map's keys less the subtitle
  map's. Fixture capture keeps that map's keys and nothing under them, as for `subtitles`.
- **The editor's *Subtitles* group** gains the checkbox, the field with its refusal line, and the
  radio buttons, inside the existing group. With nothing probed, a queued job or the preset
  manager, every subtitle control carries the preset's own (`T109-R2`). With no language chosen,
  none of the three is kept. The name gains *with automatic captions*, *subtitles fetched as …* and
  *subtitles converted to …*, set aside to find the built-in.
- **The hatch.** The seven spellings join the audit's built table, now 39 rows against 26
  unbuilt, and leave `NOT_SECRET_VALUES`. The redaction test's ordinary word moved from
  `--sub-format best` to `--merge-output-format mkv`.
- **New tests.** `test_subtitle_depth.py`: the model, storage, the probe, the mapping held to
  `parse_options` key by key and converter by converter, the ffmpeg answers and the name.
  `test_automatic_captions.py` downloads a hand-built source through real yt-dlp: the person's
  subtitles for a language with both, the caption for one without, none without the box, nothing
  from the box alone. `test_post_processing.py` converts a served WebVTT to SRT and to ASS with
  real ffmpeg, embeds a converted one, and refuses a conversion before the download without
  ffmpeg. The editor tests cover the list, the gating, the four reason lines, `all`, the round
  trip, carrying, clearing, the radio buttons, the field's refusal on an immediate OK and save,
  ffmpeg, names and the keyboard.
- **Mutations, 19 of 19 caught**, on a copy of the tree: either key removed; captions sent
  without languages; the converter removed or moved after the download; the pure ffmpeg answer
  forgetting conversion; captions admitted beside `all`; any format text admitted; captions
  listing subtitled languages; clearing the box leaving captions checked; the gate never run;
  nothing offered no longer carrying; depth kept with no language; conversion not withdrawn
  without ffmpeg; OK taking an unchecked format; either store reading a bare string; the name not
  setting the depth aside; the hatch admitting `--convert-subs`. **Two survived the first run**,
  and both were code repeating a rule: the editor's opening checked captions by a second rule the
  caption gate already applies, so that branch went, and carrying with nothing offered differed
  only for a preset with depth and no language, which now has its test.
- **Also fixed here, from `T-249`:** bare `mypy` failed at `8b0aad6` on one of that task's editor
  tests (recorded in `T-249`'s entry); the test is narrowed through a local.

**Checks, 2026-10-14, on Linux, base `8b0aad6`:** `ruff check .` and `ruff format --check .`
(480 files); `mypy src` (70), bare `mypy` and `mypy --platform win32` (219 each);
`python tools/ytdlp_option_table.py --check`; `tests/unit tests/ui` under `-n auto`, **5,583
passed**, 21 skipped; `tests/integration` **537 passed**. No Windows run, and `STARBASE` was offline.


### T-363 — The options field can write outside the chosen folder, and switch off a safety check

**Status:** In Review — correction 1 built 2026-10-17, awaiting the focused re-review of
`T363-R1` and `T363-R2`. Changes requested 2026-10-16 at `530f114`, one Critical and one Medium
blocker ([record](reviews/T-363.md#2026-10-16--initial-containment-and-compatibility-review)).
Built 2026-10-15, ahead of `T-249`'s and `T-251`'s reviews by the maintainer's ruling that day.
*(Was Ready:)* filed 2026-10-15 by the maintainer's ruling, to run
next, before `T-250` and before `T-364`. Found 2026-10-14 while mapping `T-248` and `T-250`.
**Owner:** Implementer
**Priority:** Critical — `TESTING.md` §14 names *writing outside the directory the user chose*.
`main` only: `0.1.0` predates the options field.
**Phase:** Phase 4.5 (stage 3, before `T-250`)
**Depends on:** nothing
**Relevant context:** `T-034`; `T-046`; `ARC-010` §§3–4; `REQ-031`; `T-361`;
[`T-248`'s mapping](#t-248--filename-shaping-and-the-modification-time) and `T-250`'s;
`downloader/worker.py` (`_validated_target`, `as_literal_template`, `claim_outputs`);
`downloader/ytdlp_adapter.build_options`; `downloader/extra_options`
**Affected surfaces:** `build_options`, the hatch's admission and its generated table, and their
tests
**Risk:** High — the containment boundary and the hatch's refusal rules.

#### Evidence

- **The breach.** The worker renders and contains a name once, then hands yt-dlp the absolute
  staging path as a literal template; yt-dlp applies `--trim-filenames` and `--windows-filenames`
  again to that **whole path**. Measured in real sessions at `8b0aad6`: a trim of 80 wrote eight
  levels above the chosen folder; a trim of 201 created a sibling folder; a trim of 189 wrote
  inside the folder but outside staging, past `T-046`'s reservation; a folder `Talks: 2026`
  became `Talks# 2026/…`. Reproduced with yt-dlp's `prepare_filename`: for `/home/sean/Videos` a
  trim of 15 names `/home/sean/Vide. 2 of the set.mp4`. The claim's source check fails the job
  only after the file and folders exist, and nothing removes them.
- **The safety switch.** `--compat-options all` or `allow-unsafe-ext` turns off yt-dlp's
  unsafe-extension check **for the whole process** (yt-dlp: *"compat option changes global state
  destructively; only allow from cli"*). Measured: `exe` refused, then accepted after the
  edit-time check of `--compat-options all` ran in the same process — the GUI's.
- **Values reaching a control's key.** `mtime-by-default` and its bundles set `updatetime`, and
  `format-sort` and its bundles set `format_sort`, which `T-361`'s alias derivation and the
  destination test both miss because the option's destination is `compat_opts`.
  `--compat-options filename` is admitted and does nothing (`REQ-031`).

#### Maintainer rulings, 2026-10-15

1. **Fixed now, as its own task**, before `T-250`, as `T-361` ran before `T-247`; Linux evidence
   suffices, since yt-dlp's `_prepare_filename` is the same on every platform.
2. **The `--compat-options` values are folded in**: a value that disables a safety check, or sets a
   key a control owns, is refused at edit time with its reason, derived value by value from
   yt-dlp's own parser; harmless values stay admitted. This answers `T-248`'s question 4 and
   `T-250`'s third route into the sort.

#### Acceptance criteria

- [ ] The download pass never carries `trim_file_name` or `windowsfilenames`; they act where the
      name is rendered and contained, and nowhere else.
- [ ] The measured sessions are regression tests on `127.0.0.1` that fail at `8b0aad6` and pass,
      and a mutation restoring either key on the download pass is caught **before** the claim's
      source check, which stays as the second line.
- [ ] No `--compat-options` value that disables a safety check, or sets a key a control owns, is
      admitted; each is refused with its reason, derived from yt-dlp's parser so a new value is
      classified rather than missed, and the edit-time check never changes yt-dlp's process-wide
      state in the GUI.
- [ ] `--compat-options filename` and any other value with no effect here is refused rather than
      dropped (`REQ-031`).
- [ ] The generated table regenerates cleanly, and Ruff, both mypy platforms and the hatch's and
      worker's tests pass.

#### Out of scope

- `T-248`'s controls themselves, and its other questions (the Windows pair, where shaping lives).

#### Built 2026-10-15

- **The breach.** `build_options` keeps `trim_file_name` and `windowsfilenames`
  (`RENDER_ONLY_KEYS`) off the download pass. They still act on the probe pass, where
  `_validated_target` renders the user's template and contains it, so the name is shaped once and
  the path it became is handed to yt-dlp untouched. The claim's source check stays as the second
  line.
- **The values, decided one by one.** `tools/ytdlp_option_table.py` parses each `--compat-options`
  value alone, restoring yt-dlp's process-wide state after each, and classes it: *safety* where
  yt-dlp names it `allow-unsafe-*` or it switched the extension check off (`allow-unsafe-ext`,
  `allow-unsafe-exec-expansion`); *app* where it sets a key `app:sets` owns (`filename`, which sets
  `outtmpl`); *control* where it sets a key a built control owns (none today: `format-sort` and
  `mtime-by-default` reach `T-250`'s and `T-248`'s keys, and are refused the day those are built,
  by regenerating). The table carries `COMPAT_VALUES` and `COMPAT_ALIASES`, and the option's keys
  are now what its admitted values change.
- **Admission** resolves the values the whole line leaves chosen — aliases, `all`, `-` removals,
  case and spaces, a second option adding to the first — as yt-dlp's `orderedSet_from_options`
  does, and refuses before anything is parsed, naming the value and why. A value yt-dlp does not
  know is left to its parser. `all,-allow-unsafe-ext,-allow-unsafe-exec-expansion,-filename` is
  usable.
- **The GUI's process is left as it was.** `prefer-vp9-sort` stays admitted, and parsing it
  rewrites yt-dlp's default format order for every later `YoutubeDL`; that is its effect in a job's
  own process. The editor's check (`unparseable`) and the offer's ffmpeg question
  (`hatch_requires_ffmpeg`) now parse inside `process_state_kept`, which puts back the format
  order and the extension check.
- **Also fixed:** `multistreams` was admitted and then dropped, because the option's keys were
  measured from two other values; its two keys are now carried (`REQ-031`).
- **The audit** says, under the classes, that this option is decided value by value.
- **Tests.** `test_compat_options.py`: shaping reaches the render and never the download; yt-dlp's
  own `prepare_filename` writes where the worker contained it, for the three measured breaches;
  the resolution held to `parse_options` over twelve inputs; each refused value and its reason;
  harmless values usable; every `allow-unsafe-*` refused; `multistreams` carried; the editor and the
  offer leaving the process as it was; and the generator's rule refusing `format-sort` and
  `mtime-by-default` once their controls exist. `test_shaping_containment.py` runs four real worker
  sessions on `127.0.0.1` into a plain folder and one named `Talks: 2026`, and asserts the only
  thing written is the download, in the chosen folder.
- **Mutations, 12 of 12 caught**, on copies of the tree: shaping left on the download pass, or
  only trim kept off it; compat values never refused; a removal ignored; only the last occurrence
  resolved; the state not put back, or either parse unguarded; the generator forgetting the
  unsafe names, not checking the application's keys, or measuring the option by two values again;
  and `multistreams`' keys dropped from the table. **Restoring `8b0aad6`'s download pass fails all
  four real sessions and all three naming cases** — and the run wrote
  `/tmp/pytest-. 2 of the set.mp4`, outside its test directory, which was removed.

**Limit against the fourth criterion.** A value is refused as doing nothing only where its whole
effect is a key the application sets. Most values act at run time through `compat_opts`, which a
parse cannot measure, so a value such as `list-formats`, which this application never exercises,
stays admitted. Measuring that needs a run per value and is not done here. *(The review held
this short of the criterion, `T363-R2`; correction 1 below classifies every value instead.)*

**Checks, 2026-10-15, on Linux, base `e6c58ed`:** `ruff check .` and `ruff format --check .` (482
files); `mypy src` (70), bare `mypy` and `mypy --platform win32` (221 each); the table check up to
date; `tests/unit tests/ui` under `-n auto`, **5,618 passed**, 21 skipped; `tests/integration`
**541 passed**. No Windows run: the fix is platform-independent yt-dlp code, and `STARBASE` is
offline.

#### Correction 1, 2026-10-17 — `T363-R1` and `T363-R2`

The review of `530f114` requested changes with one Critical and one Medium blocker; both are
corrected together. **Corrected, awaiting re-review.** The correction is on `9e917ec`, `T-249`'s
correction, which leaves this task's admission and parses as `530f114` had them.

| Finding | Correction | Evidence |
|---|---|---|
| `T363-R1`, Critical — the missing-ffmpeg attribution parsed each option alone outside the guard, so opening the editor without ffmpeg on an admitted line that names `allow-unsafe-ext` and takes it away switched the GUI's extension check off, and `prefer-vp9-sort` changed its format order | `options_needing_ffmpeg` parses inside `process_state_kept`, as the editor's check and the offer's question do. **The parses are listed, not sampled**: a test reads the adapter and the worker for every call to yt-dlp's parser and holds them to five functions, each with why it is safe in the GUI's process, so a new route fails until someone looks at it | `test_naming_what_needs_ffmpeg_leaves_the_process_as_it_was`, the review's three lines through `options_for` and `ffmpeg_refusals`, with `exe` still refused afterwards: **all three fail at `9e917ec`**. `test_opening_without_ffmpeg_leaves_yt_dlp_s_process_state_alone`, the real dialog offscreen opening the preset: **both cases fail there**. An attribution raising after its parse still leaves the state as it was |
| `T363-R2`, Medium — runtime-only values with no effect here were admitted, `list-formats` and the empty `2025`; criterion 4 unmet | **Every admitted value is classified in the audit, with its reason** (*What each admitted value does here*): 14 act here, 12 do not. The generator reads the table into `COMPAT_VALUES` as `inert`, and **stops** on an admitted value with no row, or on one called `effect` that nothing in yt-dlp reads and whose parse changes no key. Admission refuses an `inert` value where it is **named**, and a bundle bringing nothing that acts (`2025`), saying it *changes nothing this application does*. A value `all` or a year's bundle brings along, and one named and taken away again, stay usable | Each of the 12 refused by name, `2025` refused; `2021`, `2022`, `2024`, `all,-…` and the cancellations usable; eight runtime-only values that act stay usable. The generator's two stops each tested. The count, bundle, generator and unread-value tests **fail at `9e917ec`** |

**How the twelve were judged**, each by where yt-dlp 2026.08.19 reads it:

- **Read nowhere**: `no-external-downloader-progress`, `no-youtube-prefer-utc-upload-date`,
  `seperate-video-versions`.
- **A choice between a package this application does not install and what is used without it**:
  `no-certifi` (certifi), `embed-thumbnail-atomicparsley` (mutagen), `prefer-legacy-http-handler`
  (requests or curl_cffi; urllib is the only handler).
- **Acting only beside options already refused**: `no-keep-subs` (`--embed-subs`'s processor),
  `no-attach-info-json` (that of `--embed-metadata` or `--embed-chapters`), `playlist-index`
  (after `--playlist-random` or `--lazy-playlist`), and `abort-on-error`, which sets `ignoreerrors`
  false where every read treats false as absent and `build_options` leaves it absent.
- **On a path this application never takes**: `list-formats` (the console table) and `format-spec`
  (the format chosen when none is given).

Each kind's evidence is a test: the unread values found by scanning yt-dlp; the four packages
absent and urllib alone; the companion options refused; every pass naming a format and leaving
`ignoreerrors` absent. **And the other side, values that act although their parse changes no
key**: `filename-sanitization` changes the name the probe pass renders, `a⧸b` to `a_b`, and
`embed-metadata` changes the comment the application's own metadata processor writes, both
through real yt-dlp with the application's options.

**Limits.** The classification reads yt-dlp at the pin against what this application ships. A
dependency that brought certifi, mutagen or another request handler would change three rows, and
the package test fails then; a new yt-dlp value stops the generator.

**Sibling audit, `T363-R1`.** yt-dlp's parser writes two process-wide values at the pin, the
default format order and the extension check, both in `parse_options`. The GUI reaches a parse
three ways, the editor's check, the offer's ffmpeg question and the attribution, now all guarded;
`hatch_options` parses unguarded only in a job's own process, where the effect is the option
working, and its one GUI caller guards it. The other two parses read nothing typed or use
`parseOpts`, which writes neither value.

**Correction mutations, 10 of 10 caught**, each on a fresh copy of the tree: the attribution
unguarded; the guard putting back only the format order; a named `inert` value admitted; the empty
bundle admitted; a passenger refused; a cancellation refused; the generator admitting an
unclassified value, dropping its contradiction check, ignoring `inert` rows, or taking every value
as read.

**Checks, 2026-10-17, on Linux, after the correction**, with the project `.venv` on `PATH`:
`ruff check .` and `ruff format --check .` (485 files); `mypy src` (70), bare `mypy` and `mypy
--platform win32` (221 each); the table check up to date; `tests/unit tests/ui` under `-n auto`,
**5,671 passed**, 21 skipped; `tests/integration` **545 passed**. The first Ruff run failed on
three long lines and the big solidus in a new test, corrected and rerun with both mypy runs and the
three option modules (118 passed); no source changed after the suites ran. No Windows run.

## Ready

### T-364 — Fragmented downloads retry, and never finish with a piece missing

**Status:** Ready — filed 2026-10-15 by the maintainer's ruling, to run after `T-363` and before
`T-250`. Found 2026-10-14 while mapping `T-252`. Ships in `0.2.0`; there is no `0.1.1`.
**Owner:** Implementer
**Priority:** Critical guess — a silent wrong result in the shipped `0.1.0`: a download reported
*Done* whose file is missing media.
**Phase:** Phase 4.5 (stage 3, before `T-250`)
**Depends on:** `T-363`
**Relevant context:** [`T-252`'s mapping](#t-252--download-tuning-and-the-retry-policy-the-settings-screen-shows);
`T-196`; `UX-002`; `ARCHITECTURE.md` §8; `downloader/ytdlp_adapter.build_options`;
`ui/settings_dialog.py` (`NETWORK_EXPLANATION`, the retries default); `core/settings.py`
**Affected surfaces:** `build_options`, the settings screen's retry text and default label, the
`retries` docstrings, the changelog, and their tests
**Risk:** Medium — behaviour changes for `0.1.0`'s users.

#### Evidence

Measured at `8b0aad6` with the worker's `run_session` against a local 12-second HLS stream: one 503
on fragment 3 ended `Succeeded` with 250 of 300 video frames, and a 403 did the same with retries
set to 3. yt-dlp's command line, on its own defaults, delivered the whole file in both cases.
yt-dlp the library reads absent `retries` and `fragment_retries` as zero, where its command line
sends ten, and skips a missing fragment by default. One 503 in a progressive transfer failed the
job as `EXTRACTOR_ERROR`, which the automatic retry never takes. `v0.1.0`'s `build_options` and pin
are the same. The settings screen's account of retries is untrue in three ways at `HEAD`.

#### Maintainer ruling, 2026-10-15

**Its own task, next after `T-363`, on `T-252`'s recommended answers to its first two questions**:
when nobody chose a count, `build_options` sends yt-dlp's command-line defaults, read from
`parse_options([])` at the pin and held there by a test, and the screen says the number; and a
fragment still missing after its retries fails the attempt (`skip_unavailable_fragments=False`),
so the job's own retry resumes it from staging, with the options field's
`--skip-unavailable-fragments` kept as the user's explicit opt-in.

#### Acceptance criteria

- [ ] With no count chosen, the download sends `retries` and `fragment_retries` equal to yt-dlp's
      command-line defaults at the pin, and a test fails when the pin's defaults change.
- [ ] A local fragmented stream with a 503 and with a 403 on one fragment delivers every frame, and
      a fragment that never arrives fails the attempt rather than ending *Done*.
- [ ] The failure a job's automatic retry can take is classified so it takes it, or the reason it
      cannot is recorded.
- [ ] `--skip-unavailable-fragments` typed in the options field still skips, as the user's choice,
      and that sharing of one key is written down as `ARC-010`'s rule for `writethumbnail` is.
- [ ] The settings screen, its default label, the `retries` docstrings and the settings file's
      comment say what is true; the changelog tells `0.1.0` users their downloads now retry.

#### Out of scope

- `T-252`'s controls for fragment retries, extractor retries, the socket timeout, `-N`, sections
  and live-from-start, and its questions 3 and 4.

### T-301 — Four UI tests break when the application font grows by one point

**Status:** In Progress — **three of the four repaired 2026-09-10**; the fourth is diagnosed and
not fixed, and what was tried is recorded below. *(Found 2026-09-08 while repairing the two that
`ubuntu-latest` broke.)*
**Owner:** Implementer
**Priority:** Low — contained test debt with no user-facing evidence behind it. It is recorded so
the measurement is not lost, not because it blocks anything.
**Phase:** Phase 4 (test infrastructure; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012`'s 2026-09-08 amendment, `tools/bigger_font_plugin.py`,
`tools/dialog_width_floor_probe.py`
**Affected surfaces:** `tests/ui/test_row_verb_wiring.py`, `tests/ui/test_add_dialog.py`
**Risk:** Low
**Required checks:** `ruff check .` · `ruff format --check .` · `pytest tests/ui` at the default
font **and** under `tools/bigger_font_plugin.py`

#### Scope

Four tests fail at one point larger than the default font:

```
tests/ui/test_row_verb_wiring.py::test_the_drawn_verbs_are_where_the_click_is_tested
tests/ui/test_row_verb_wiring.py::test_the_overflow_keeps_its_place_as_the_state_changes
tests/ui/test_row_verb_wiring.py::test_the_verbs_leave_the_message_its_width
tests/ui/test_add_dialog.py::test_the_menu_key_reaches_the_current_rows_menu
```

Three are one cluster — where verbs and the overflow land as a row narrows — and probably share a
cause. Reproduce with `PYTHONPATH=tools python -m pytest -q -p bigger_font_plugin tests/ui`.

#### 2026-09-10 — the cluster of three, and what a larger font actually does

**All three were test debt, and the product was never wrong.** Each invented a row —
`QRect(0, 0, 700, 66)`, sometimes with 100 px carved off the left — which is a row *at one font*.
A point larger and nothing fitted inside it, so `_verb_rects` answered empty and the test failed
for having guessed the geometry rather than for anything the delegate did.

**Re-expressed against the seam the paint itself uses:** `visualRect` for the row and `_verb_area`
for the region reserved in it. The claims are unchanged — verbs inside the row, right to left, not
overlapping, off the first two lines — and now hold at both fonts.

**One of the three also had a literal the comment beside it rejected.** It searched for the width
where two rows both overflow *"rather than writing it down, because a literal here would be a
number that passed on this machine"* — and then bounded the search at `range(24, 200, 2)`. The band
moves with the font, a point larger put it past 200, and the search ran off the end. The ceiling is
now the row's own width.

**So: a larger font does nothing to verb placement**, which is this task's fourth criterion
answered. `tests/ui/test_row_verb_wiring.py` passes in full — 62 tests — at both fonts.

#### The fourth is not fixed, and these are the measurements

`test_the_menu_key_reaches_the_current_rows_menu` still fails its second half at one point larger:
*"with no current row and no row under the point, a menu opened anyway."* Established by probe:

- The current index **is** invalid when the event is sent (`row: -1`).
- The probe point **is** off every row, and still is with a twenty-pixel margin.
- Exactly **one** `QMenu` exists; `_close_menu` hides it and `WA_DeleteOnClose` does **not** destroy
  it. The same object becomes visible again when the next context event reaches the viewport.

So the menu is not built a second time — a hidden popup is re-shown. `AddUrlDialog._show_row_menu`
cannot be the route, since with no valid index it returns before building anything.

**Two fixes were tried and both rejected**, recorded so the next reader does not repeat them:

- **Widening the probe point's margin** from 2 px to 20. The original margin was exactly two pixels
  at the larger font, which looked like a coordinate-space bug between `customContextMenuRequested`
  (list coordinates) and `indexAt` (viewport coordinates). **It is not that** — the failure survives
  the wider margin. The margin is kept anyway: a probe whose correctness depends on a frame width
  being zero is measuring the frame.
- **Forcing the menu's destruction** in `_close_menu` with `setParent(None)` plus `deleteLater`.
  This made the test fail at the **default** font too, so it trades a font-specific failure for an
  unconditional one. Reverted.

**Ruled 2026-09-11: leave it failing and documented.** The font lever is deliberately not wired
into CI — this task's own *Out of scope* says why — so nothing is red anywhere, and the diagnosis
plus both rejected fixes are the record a later reader inherits. **An `xfail` scoped to the lever
was offered and declined**: this task's own criteria forbid loosening an assertion to reach green,
and a marker saying a known failure is expected is that with extra steps.

#### Acceptance criteria

- For each, establish **product or test** by measurement, the way
  `tools/dialog_width_floor_probe.py` established the add-dialog floor. A pixel that moved is not
  by itself a defect, and an assertion that was only ever true at one font is not by itself sound.
- Repair whichever is wrong. **Do not loosen an assertion to reach green** — the two repaired on
  2026-09-08 were re-expressed as the property each was actually protecting.
- Record what a larger font does to verb placement, whichever way it goes.

#### Out of scope

- **Wiring the font lever into CI.** Gating on a standard nobody has established the product meets
  would leave the board red for a known reason, which is what removed the `STARBASE orphans` job.
- The other UI tests. **A 45-failure figure recorded earlier that day was wrong** — the lever that
  produced it did not restore the font between tests, so it compounded a point per test. At a true
  one point the count is four, and every accessibility-sounding test named in that figure passes.

<a id="t-302"></a>

### T-304 — Should a focus ring appear when the control was clicked?

**Status:** Ready — **ruled by the maintainer on 2026-09-09: option (2), the keyboard-only
ring.** The options and their costs are kept below as the reasoning the ruling was made on. The
decision entry recording it is part of this task, since the rule it supersedes has a review
finding and a test for authority and no numbered decision.

**Sequenced by the maintainer on 2026-09-11: not started until Phase 4's exit is approved.** The
build touches every `:focus` selector in `ui/theme.py`, the generated `BORDERED_CONTROLS` ones
included — and a type-and-attribute selector out-specifying a universal pseudo-class one is the
defect behind both `T-303` and `P4EXIT-R1`'s collapse triangle. It would also rewrite the rule
that `test_focus_is_visible_on_every_control_the_application_shows` enforces, which is the test
carrying `P4EXIT-R1`'s evidence while that finding is under verification. The ruling on *what* to
build is unchanged; only *when* is settled here.
**Owner:** Maintainer to rule; Implementer to build
**Priority:** Low — it is a comfort question, not a defect. Raised 2026-09-09: *"I don't
necessarily think that mode should be enabled by default — if you are clicking around with a
mouse all of the highlighted boxes are distracting."*
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** `T-303` should land first, so the ring is correct before its trigger is argued
**Relevant context:** `T202-R1`; `STATE_RULES` in `ui/theme.py`;
`tests/ui/test_colour_is_never_alone.py`; `NFR-005`
**Affected surfaces:** `ui/theme.py`, the application's input handling, and the accessibility tests
**Risk:** Medium — it changes a rule that currently has a test and a recorded rationale

#### The question

Qt shows the focus ring wherever focus lands, including a mouse click, because `QCheckBox` and
friends take `StrongFocus`. The web solved this with `:focus-visible`: ring for keyboard, none for
pointer. **Qt has no native equivalent**, so it would be built — track the last input device and
carry it as a dynamic property the style sheet selects on.

#### What makes it a decision rather than a tweak

The ring is not decoration here. `STATE_RULES` records it as the **geometry** channel for focus,
adopted so that focus reads without colour — *"ink against background, which needs no colour to
read"* — and `tests/ui/test_colour_is_never_alone.py` enforces that every state has a non-colour
channel. **No numbered decision governs it**: its authority is review finding `T202-R1` and the
test. So a ruling here would be the first time this is written down as a decision rather than as
code.

#### Options

1. **Leave it.** Every focus is drawn. Costs nothing, and the maintainer finds it distracting.
2. **Keyboard-only ring (`:focus-visible`).** Mouse focus draws no ring; keyboard focus does.
   Standard on the web and in modern toolkits. **It does not weaken the keyboard case**, which is
   what `NFR-005` and the accessibility pass are about. It does mean a control can hold focus with
   nothing showing it, which matters to a mouse user who then reaches for the keyboard — the
   handover is the case to check, not the steady state.
3. **Keep the ring, reduce it** — thinner, or a lower-contrast hue — for every focus. Keeps one
   code path and one rule; likely fails the contrast floor that made it 2px.

**Recommendation: (2), after `T-303`.** It is what the maintainer asked for, it leaves the
keyboard route untouched, and the objection it must answer — focus invisible until the user
reaches for the keyboard — is testable rather than theoretical.

#### Acceptance criteria

- Whatever is ruled is **recorded as a decision with the maintainer's authority**, since the
  current rule's authority is a review finding and this would supersede it in one direction.
- If (2): pressing a key after clicking reveals the ring on the already-focused control, and that
  handover is asserted by a test rather than described.
- `tests/ui/test_colour_is_never_alone.py` still passes, or is amended deliberately with the
  ruling cited — not adjusted to fit.

## Proposed — Phase 0

## Proposed — Phase 1

## Proposed — Phase 2

### T-121 — The phase-exit clip server aborts connections on hosted Windows

**Status:** **Proposed — narrowed 2026-08-03, and still open.** Two of its three parts are struck
off: the misleading assertion and the missing `ConnectionAbortedError`. What remains is the part
nothing here can reproduce — **why the loopback connection aborts under load on hosted Windows.**
Filed rather than fixed inline (`AGENTS.md` §7): it is not `T-118`'s.

**It is now latent for two independent reasons, and only one of them is about the defect.** It did
not recur in run `30859578131` — which is not the same as resolved (`COORD-R21`) — **and the
configuration it appeared in is no longer exercised at all.** It only ever failed on hosted
`windows-latest`, and that job does not run while `WINDOWS_RUNNER` points at `STARBASE`
(`docs/project/TESTING.md` §10). *Not running the job that found a defect is not evidence about the defect*,
and in six weeks the silence will read as resolution unless this paragraph is here.

The current red on `main` belongs to nothing: `T-122`'s ratio oracle is corrected.
*(This read "it is the only thing red on `main`" until 2026-08-03, which stopped being true the
moment `T-118`'s own scaling gate failed and this test passed.)*
**Owner:** Implementer
**Priority:** Medium — a gate that fails for its own fixture's reasons is a gate that will be
dismissed, which is `T118-R10`'s lesson in a different costume
**Phase:** Phase 2 (its gate), though the defect is in test infrastructure
**Relevant context:** `tests/integration/test_phase_2_exit.py`, its `media_url` fixture,
`tests/network/conftest.py`
**Affected surfaces:** `tests/**`
**Risk:** Low to fix, and it is *not* a production defect

**`test_every_queued_job_eventually_starts_as_slots_free` failed on hosted `windows-latest` while
passing on `STARBASE`.** The assertion reads:

```
0 of 5 jobs were still QUEUED after Add with nothing else done
Final: {'af90cb': 'completed', '660db5': 'completed', '83cc82': 'failed',
        'bdd939': 'completed', '7cbf8e': 'completed'}
```

**Read the numbers before the message.** Zero jobs were still `QUEUED`, so the behaviour the test
exists to prove — that a queue drains with no user action after Add — *held*. Four of five
completed. The fifth **failed**, and the captured stderr says why:

```
ConnectionAbortedError: [WinError 10053] An established connection was aborted
by the software in your host machine
```

That is the test's own `ThreadingHTTPServer` losing a connection to its own client, twice, on the
loopback interface. The predicate demands all five `COMPLETED`, so one aborted download reddens a
test whose subject is admission.

**The message is now misleading, which is the part worth fixing.** It reports the `QUEUED` count
and concludes "nothing admits durable queued intent" — a sentence that is false whenever the count
it prints is zero. A reader who trusts the prose over the dict diagnoses the scheduler.

#### Scope

- Make the fixture server survive an aborted client connection rather than propagating it.
- Distinguish the two failures in the message: *jobs did not start* is the defect this gate exists
  for; *a job started and its download failed* is a different sentence and should say so.
- Neither reproduces on Linux, and it is hosted-Windows-only so far — `STARBASE` ran the same test
  in the same run and passed. Codex separately reported 16 localhost-server tests denied outright
  by its sandbox, so this fixture is fragile in more than one constrained environment.

#### Out of scope

- The download path itself. Nothing here suggests a production defect: the worker did what a
  worker does when a server drops the connection.

#### Corrected 2026-08-03 — the two parts that could be fixed without reproducing it

**The assertion named the wrong defect.** It printed the `QUEUED` count and then concluded
"nothing admits durable queued intent" *whatever that count was*, so a run where every job started
and one download failed reported "0 of 5 still QUEUED" and blamed admission — the one part that was
working. It now branches: a stalled queue says so, and a queue that drained with a failed download
says **that**, and points at the clip server.

**`ConnectionAbortedError` was missing from the handler.** `media_handler` already caught
`BrokenPipeError` and `ConnectionResetError` with the comment *"the expected end of a killed
download: the worker went away mid-stream"* — and `ConnectionAbortedError` is that same condition
on Windows. Its absence is why the abort escaped to `socketserver`, which printed a traceback for a
state two lines of the fixture already called expected. Added in **both** copies: the shared
`media_handler` in `test_end_to_end.py` that `test_phase_2_exit.py` imports, and `test_manager.py`'s
own.

**Neither makes the download succeed**, and neither is claimed to. Swallowing the abort stops the
noise; the connection still died mid-stream and that is what failed the job. Both changes are
improvements a reader can verify without Windows, which is exactly why they were worth doing
separately from the part that needs it.

---

### T-104 — Hand a second launch's URL to the running instance

**Status:** Proposed — **filed 2026-08-01 by `T-087`**, which built the ownership half of `ARC-006`
and deliberately not the attach half.
**Owner:** Implementer
**Priority:** Low — `T-087` satisfies exit criterion 4 and `A-004` by refusing; this is the nicer
half of "attaches **or** refuses"
**Phase:** Phase 2
**Depends on:** `T-087`
**Relevant context:** **`ARC-006`** and its 2026-07-29 amendment, `A-004`, `REQ-001`
**Affected surfaces:** `app.py`, a new channel module
**Risk:** Low — the ownership guard already prevents the harm; this only improves the outcome

#### Scope

`ARC-006` keeps `QLocalServer`/`QLocalSocket` as an **attach channel**, and is explicit that this is
what makes *attach* possible rather than only *refuse*: "a second launch can hand its URL to the
running instance and raise its window. A lock file can only say no."

`T-087` built the ownership lock and stopped there, because the criterion it owns is satisfied by
refusing. Today a user who double-clicks the application a second time — or opens a link with it
while it is running — gets a message box naming the running instance and nothing happens to the URL.

**The channel is started by whoever wins the lock, and never decides who owns the database.** That
separation is the whole point of the amendment and must survive this task: the loser connects to the
channel and hands over; it does not attempt to become a server.

#### Acceptance criteria

- A second launch with a URL passes it to the running instance, which enqueues it, and the second
  process exits reporting that it did so
- The running instance's window is raised and focused
- **A second launch with no URL still raises the window** rather than doing nothing visible
- The channel is started **after** the lock is won, asserted — a channel started first would
  reintroduce the design `P2PLAN-R5` withdrew
- A second launch when the channel is unreachable — the owner is alive but wedged — still refuses
  rather than hanging, within a stated timeout
- Verified on both platforms. **`OPS-005` amended 2026-08-01:** hosted Windows carries the Windows
  gate while `STARBASE` is unreachable, so `check (windows-latest)` satisfies this and the desktop
  slice stays with `STARBASE` for first release
  *(This read "`STARBASE` included" without qualification, which after the amendment demanded a
  machine nobody could reach for a criterion hosted Windows had already met — `T087-R4`.)*: the named-pipe and Unix-socket halves are
  different system calls

#### Out of scope

- Anything that makes the channel decide ownership (`ARC-006` amendment)
- Multi-user or networked access (`A-004`)

---

## Proposed — Phase 3

### T-190 — `docs/UX_SPEC.md` §6 still says its screen is unspecified

**Status:** Proposed — filed by `T-109`, 2026-08-07.
**Owner:** Planner / Documentation Maintainer
**Priority:** Low — no runtime behaviour depends on it; the defect is a current-truth document
stating a solved problem in the present tense, which is `T185-R1` exactly.
**Phase:** Phase 3 cleanup
**Depends on:** `T-109`'s verdict, so the correction describes what was approved rather than what
was submitted.

#### Scope

`docs/UX_SPEC.md` §6 carries a `[T]` clause reading *"This clause stays because `T-109`'s screen has
not been specified against the ruling yet"*, and a `P-16` paragraph asking whether `T-109` and
`T-111` share a screen as though it were open. `UX-007` ruled `P-16`, and the screen now exists:
`ui/options_dialog.py`, reached as `Options…` on the row's format control.

`AGENTS.md` §4 does not put `docs/UX_SPEC.md` in the Implementer's write set, which is why `T-109`
filed this rather than editing it.

#### Acceptance criteria

- §6's open questions read as ruled and built, in the past tense, with the built surface named.
- The `Save as preset…` clause describes the control **as built by `T-109`** (`T109-R5`), rather
  than saying it arrives with `T-111`. `T-111` still owns the other four operations.
- Nothing else in §6 changes: the ruled clauses are the contract the implementation was built
  against.

---

### T-191 — A queued row shows no size until it downloads

**Status:** Proposed — **filed 2026-08-08 by the `T143-R1` amendment**, which deferred pre-download
size here rather than declining it. A criterion cannot be narrowed into nowhere, so this is where it
went.
**Owner:** Implementer
**Priority:** Low — no defect, and no user has reported it. `UX-005` §3 does not promise a size
before a download starts, which is why `T-143` was amended rather than expanded
**Phase:** Phase 4 — polish, and it is a schema change, so it does not belong in a phase that is
exiting
**Depends on:** nothing
**Relevant context:** `T-143`, `T143-R1`, `UX-005` §3, `DAT-001`, `core/models.py` (`Job`,
`FormatInfo.filesize`, `FormatInfo.filesize_is_estimate`), `persistence/` migrations
**Affected surfaces:** `core/models.py`, `persistence/`, `ui/queue_view.py`, a migration
**Risk:** Low in mechanism, **Medium in honesty.** A size shown before a download is a *prediction*,
and `FormatInfo.filesize_is_estimate` exists because yt-dlp's own number is sometimes
`filesize_approx`. A row that states an estimate as a fact is the class of confident lie
`Job.progress` already refuses to tell

#### What is wrong

Nothing, today — and that is why this is Low. **No row of any kind shows a size before it runs.**
A pasted URL and a playlist entry are equally bare, so there is no inconsistency for a user to
notice; there is a field the application could show and does not.

`T-143`'s first acceptance criterion asked for it and could not have delivered it: a size lives
per-format in `FormatInfo.filesize`, and `Job` carries only `bytes_total`, which a *download*
reports. `T143-R1` found the criterion unmet, the maintainer amended it to the `UX-005` §3 anatomy,
and the deferred half is this entry.

#### Scope

Decide whether a queued row shows a predicted size, and if so store it. That means a field on `Job`
populated from the chosen format, a migration for it, and a decision on what the row says when the
number is `filesize_approx` rather than `filesize`.

**The estimate question is the real work.** Storing a number is a morning; deciding what a row says
when the number is a guess is the part that needs a ruling, because `REQ-003` already names the
column *"filesize/estimate"* and `T107-R7` made the two distinguishable for exactly this reason.

#### Acceptance criteria

- A queued row shows the size of the format it will actually download, before it downloads
- An estimated size is **shown as an estimate**, distinguishable from a size the site stated
- A format with no size at all leaves the row saying nothing rather than zero
- The stored size survives a restart, and a re-probe that changes the chosen format updates it
- Changing the format on a row changes the size it shows

#### Out of scope

- Predicting a size for a format the user has not chosen. The row shows what it will download

## Proposed — Phase 4

### T-350 — A staged format fixture races a real probe and loses its format control

**Status:** Proposed — filed during the independent 2026-09-18 correction review at `0cec265`.
**Owner:** Implementer
**Priority:** Medium — intermittent failures obscure the full-suite gate; the fixture also starts
the real network worker despite the UI suite's fixture-only network contract.
**Phase:** Phase 4 (test infrastructure; not a product deliverable)
**Depends on:** nothing
**Effort:** Small, estimated: control the staged probe, audit this helper's callers and verify the
combined integration/UI run. Do not change production state handling to accommodate the test.
**Relevant context:** `T310-R2`, `T118-R10`, [T-347 review](reviews/T-347.md), TESTING §§1 and 14.
**Affected surfaces:** `tests/ui/test_add_dialog.py`, particularly `_staged` and
`_probed_with_formats`; any shared fixture extracted for their callers.
**Risk:** Low — keep the mounted-panel geometry assertions and process cleanup intact.
**Required checks:** Ruff lint/format, bare mypy and Windows-platform mypy; the nine mounted-panel
cases, affected helper callers, the combined integration/UI selection, and the full-suite gate.
Retain the exact revision, command and actual pytest exit status for each gate.

#### Evidence and scope

The implementer reports **6 failed, 4,807 passed, 22 skipped** in the full suite, all at
`test_the_mounted_format_panel_fits_the_dialog_it_asked_for`: `row 0 offered no format control`.
The supplied narrower baseline log has five such failures but does not identify its revision.
Neither that log nor a passing isolated test establishes the stated machine-load cause.

The reviewer independently reproduced the same assertion at `0cec265`. `_staged` creates
`managers()` with the default real worker, resolves `https://example.invalid/one`, and waits only
for a job ID. `_probed_with_formats` then calls `_on_media_probed` directly to mark the row ready.
Processing events for up to three seconds before opening the editor delivered the real probe's
DNS failure: the row changed from `READY` to `FAILED`, and its format control disappeared.
This produced **1 failed** in 2.07 seconds. Repeating the same delayed check with the existing
`child_never_returning` injected kept the row ready and produced **1 passed** in 4.91 seconds.
These were temporary reviewer instrumentation, not repository test changes.

The test helper, dialog and manager files are unchanged between `72a0979` and `0cec265`.
This is independently actionable test-fixture work, separate from T-301's four font-growth
tests. The race is established; attribution of every reported suite failure or the desktop's
slowdown is not. Merely waiting longer for a format control is insufficient once the row failed.

#### Acceptance criteria

- [ ] A format-fixture test cannot start the real site probe. Use a controlled worker/result
      sequence consistent with the suite's process-boundary contract.
- [ ] Exercise delayed event delivery between staging and opening the editor, and prove the row
      remains ready with the intended formats. Restoring the uncontrolled probe must fail the
      regression check; do not rely on a fixed sleep or external DNS timing as the permanent test.
- [ ] Audit sibling callers of the helper for competing real callbacks and preserve teardown of
      workers, timers and widgets.
- [ ] All nine existing geometry cases retain their assertions and pass with the relevant combined
      suites. Record failing gates honestly; a successful `tail` is not a successful pytest run.

#### Investigated 2026-10-14 — cause confirmed, a fix prototyped, nothing applied

Investigated overnight at the maintainer's request, **as investigation only**: this task is not
scheduled in Phase 4.5's order, so nothing here changes the repository's tests. All work was on
copies of `8b0aad6`; the prototype applies cleanly at `3275a36` too, and is kept as an ignored
file, `docs/project/handoffs/2026-10-14-T350-prototype.diff`.

- **The cause is the one recorded above, now deterministic.** Delivering events until the probe
  session was released failed all nine geometry cases (exit 1), each row going `FAILED` about
  0.65 s after staging with the real worker's DNS error; the same delay with
  `child_never_returning` passed all nine. In unloaded runs no callback reached a test, so the
  race is latent and load-dependent.
- **The exposure is wider than the nine.** All 38 `_staged` callers (51 items) start the shipping
  worker against `example.invalid`, 43 of them failing under the delay. **Nineteen more tests
  (100 items) do the same through `_two_resolved_rows`, `_resolved_as`, `_probed_playlist` and
  inline**, and fail under it too; some of those also start durable probes and downloads, whose
  NETWORK failures do schedule automatic retries. No other `tests/ui` file starts the real worker,
  checked statically and by tracing spawns at run time (151 items at `HEAD`).
- **The prototype meets all four criteria for `_staged`.** A module-level child answers a probe with
  the fixture's formats and finishes, and `_staged` waits for the manager to be idle, so the
  fixture can no longer start the real probe; a new regression test over the three geometry
  fixtures opens the editor after everything has arrived. Restoring `HEAD`'s `_staged` fails the
  regression test while **the nine still pass** — the nine alone never caught it. Checks on the
  copy: Ruff clean; nine plus regression 12 passed; `tests/ui` 1,645 passed; integration and UI
  2,175 passed; the full suite under `-n 4` **6,032 passed**, 25 skipped, all exit 0. Bare and
  Windows-platform `mypy` failed only on `T-249`'s pre-existing error, fixed since in `bfda7c9`.
- **How often it has failed a full serial run**, all as *"row 0 offered no format control"*: 1 at
  `428f65d`, 6 at `78a5f9f`, 4 at `a7310d1` and 5 at `T-184`'s sixth round (2026-09-26 and 27),
  and 4 at `3275a36` (2026-10-15), with the DNS error in the log. Parallel runs under `-n auto`
  have not shown it.
- **Not fixed, and for this task's scope to decide:** the nineteen sibling tests above (the same
  child, or a controlled default for the module's `managers` fixture, which changes every default
  user); the module docstring's claim that the network is faked (Low); and three latent test-network
  routes found on the way — `test_app_launch.py`'s subprocess outside the GitHub guard,
  `QuietYtdlp` not stubbing `check_latest_version`, and `test_queue_view.py` building a real
  thumbnail loader for rows it never paints (all Low).

---

### T-302 — Nothing detects orphaned workers automatically on either platform

**Status:** Proposed — the gap opened 2026-09-08 and is recorded rather than accepted silently.
**Owner:** Implementer, with the maintainer for where a scan is allowed to run
**Priority:** Medium — process lifecycle and orphaned workers are the first item in
`TESTING.md` §14's standing risk focus, and there is now no automatic signal for either.
**Phase:** Phase 4 (operations; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012` as amended 2026-09-08, `OPS-010`, `docs/RUNNER_ORPHANS.md`,
`tools/orphan_scan.py`, `T-268`, `T-272`
**Affected surfaces:** `tools/orphan_scan.py`, possibly a local hook or schedule; **not**
`.github/workflows/` unless the maintainer rules otherwise
**Risk:** Medium — a detector that runs where orphans do not accumulate is worse than none,
because it reports a clean zero
**Required checks:** whatever the design needs; a **known positive** before any clean result is
trusted (`2026-08-29-orphan-scan-known-positive-soak.md` is the precedent)

#### Scope

`STARBASE orphans` was removed 2026-09-03 because it found `T-268`'s seven preserved specimens
every night and correctly failed, leaving the board permanently red. `Linux orphans` stopped on
2026-09-08 when `LINUX_RUNNER` was deleted and `kirk` and `Spock` were unregistered.

**Restoring either is not the answer, and this task exists because the obvious fix is unavailable.**
A hosted runner's VM is destroyed after every job, so a scan there finds nothing by construction.
Putting a self-hosted Linux runner back would undo the exposure reduction the maintainer chose the
same day.

#### First measurement, 2026-09-09 — not from clean suite runs on this machine

`tools/t302_orphan_accumulation_sampler.sh` ran nine rounds on `Spock` over two hours: a full
`tests/integration` + `tests/ui` pass each round, then two scans, at age 0 and again 90 seconds
later. **Nine suite exits of `0`, nineteen scans, no orphan reported**, with the known positive
passing first so that zero can be read. Rounds 5 to 9 ran alongside a live application session,
which the record treats as a property of the evidence rather than noise.

[The record](evidence/2026-09-09-T302-orphan-accumulation-sampling.md) states its own limits: a
run that exits cleanly is not the route that orphaned `T-268`'s specimens, two hours is not a
distribution, and the scanner only sees a process whose parent died. **So the first criterion is
answered by elimination rather than satisfied**, and the remaining candidate is a session that
ends badly — the shape `2026-08-27-T212-ytdlp-update-double-free.md` recorded.

#### Acceptance criteria

- Establish **where orphans actually accumulate now** that Linux CI is ephemeral. The working
  assumption was a developer's own machine; the 2026-09-09 sampling rules out clean suite runs on
  one, and the next measurement belongs on a session that ends badly rather than on more rounds of
  the same.
- Propose a detector that runs there — a pre-push hook, a periodic local run, or a documented
  manual step — and say plainly what it does **not** cover.
- **Prove it sees a known positive before any clean result is reported.** A blind scan prints the
  zero the author wanted.
- Do not reintroduce a nightly job that fails on known specimens; that is the shape `2026-09-03`
  removed.

#### Out of scope

- Reversing the runner move.
- `T-268`'s seven preserved specimens, which remain its own.

## Proposed — Phase 4.5

### T-358 — The `0.2.0` release

**Status:** Proposed — filed 2026-10-11 by the maintainer's rulings that day: `0.1.1` is skipped
and its preparation lands here, and the README's `REQ-030` statement, an exit criterion with no
owner, is owned here.
**Owner:** Implementer prepares; Maintainer tags and publishes
**Priority:** High at the end of the phase; nothing to do before stage 3 and the debt are done
**Phase:** Phase 4.5 — stage 4, the exit
**Depends on:** `T-247`…`T-255`; `T-351`…`T-354`; `T-339` and the `§11` walk, which happens on
this release's finished build; `T-355` and `T-357`, without which a fresh build installs PySide6
6.12 and cannot fetch the Windows ffmpeg; `T-360`, so this release's ffmpeg archive is kept
beside it.
**Relevant context:** `docs/RELEASE.md` (the five steps); `TESTING.md` §8 (the release gate);
`REL-003` (SemVer); `REL-009` (the checker that tells users); `REQ-030`; `OPS-001`, amended
2026-10-11; the cancelled `T-349` in COMPLETED_TASKS, whose preparation this inherits.

#### Scope

`0.2.0` from `main`: the escape hatch, the nine typed fields, the `0.1.0` debt, and the two fixes
that would have been `0.1.1`. Inherited from `T-349`, three things happen for the first time:

- **`TESTING.md` §8 item 5 gets its first real use**: the migration check opens `0.1.0`'s real
  database rather than a fabricated one.
- **The update checker reaches real users**: everyone on `0.1.0` is told by `T-338`'s check, and
  updates by hand (`REL-009`).
- **The release notes are written for people who already have the application.**

#### Acceptance criteria

- [ ] **The README states `REQ-030` with its exclusions**, as three lists: what has a typed
  control, what goes through the hatch, and what is refused, matching the audit
- [ ] The changelog names `T-343` and `T-347`'s fixes, the bundled ffmpeg's move from 9.0.1-29 to
  9.0.2-17 (`T-357`), and PySide6 held at 6.11 (`T-355`)
- [ ] `TESTING.md` §8 on both platforms, **item 6 included**: the walk, by the 2026-09-17 ruling;
  item 5 against `0.1.0`'s database
- [ ] This release's pinned ffmpeg archive is attached to it (`OPS-001`, amended 2026-10-11)
- [ ] `main`'s version names `0.2.0` before the release commit; it has read `0.1.1.dev0` since
  `0.1.0`'s bump, and no `0.1.1` will exist
- [ ] The five steps of `RELEASE.md` followed, and `main` back to a `.devN` version afterwards

---

### T-359 — Promote the options users reach for in the hatch

**Status:** Proposed — filed 2026-10-11 by the maintainer's ruling: a Phase 4.5 deliverable, in
the plan since 2026-08-07, that had no owning task.
**Owner:** Implementer; the maintainer rules on what promotes
**Priority:** Low, but it is what stops the hatch becoming the interface (`ARC-010`)
**Phase:** Phase 4.5
**Depends on:** `T-184`, complete
**Relevant context:** `ARC-010` §2 and its *"the hatch becomes the roadmap"* consequence; `NFR-007`

#### Scope

**There is no telemetry, by `NFR-007`, so the evidence is what users report**: issues and
discussions naming an option they type into the hatch. Put to the maintainer a written rule for
what promotes an option, then apply it to the reports gathered by the end of the phase. Each
option promoted becomes a typed-field task of its own, on the pattern `T-247`…`T-255` share.

#### Acceptance criteria

- [ ] A recorded ruling on what evidence promotes an option, with no telemetry
- [ ] The reports reviewed before `T-358`, and each promotion filed as its own task, or none, with
  the reason recorded

---

*(**The nine typed-field tasks, `T-247` … `T-255`**, filed 2026-08-16 by `T-183`, which is where
the option lists come from: `docs/YTDLP_OPTION_AUDIT.md`. **44 options over nine tasks** — the
typed class minus the 21 that already have a `DownloadRequest` field. Counted, and
`tests/unit/test_option_audit.py` asserts the partition, so a task that quietly grows or drops an
option fails a gate. **`T-247` built its seven on 2026-10-11 and `T-249` its seven on
2026-10-14**, so the built table holds 35 and the other seven tasks 30; two of `T-247`'s are
`Preset` fields, by `ARC-010`'s amendment that day.)*

**The following is true of all nine.** Each still states its own `**Status:**`, because `T-096`'s
gate reads that line per entry and a shared one would exempt nine tasks from the check that six
review rounds exist to enforce:

- **Owner:** Implementer · **Phase:** Phase 4.5, filed 2026-08-16
- **Depends on:** `T-183` approved. **Not on `T-184`** — a typed field is a declared member of
  `DownloadRequest` and needs nothing from the hatch. Nine independent tasks, in any order
- **Relevant context:** `ARC-010` §1, `REQ-030`, `docs/YTDLP_OPTION_AUDIT.md`,
  `core/models.DownloadRequest`, `core/presets.py`, `downloader/ytdlp_adapter.build_options`
- **Affected surfaces:** `core/models.py`, `downloader/ytdlp_adapter.py`, `persistence/` (each new
  field is a migration), the preset and options UI, and their tests
- **Acceptance criteria, common to all nine.** Each option below becomes a declared, typed,
  validated, frozen and picklable member of `DownloadRequest` (`ARC-002`, `ARCHITECTURE.md` §8);
  **the value is proved to arrive by asserting on the option dictionary the worker receives**, not
  by the download succeeding — `T-012` produced five defects that were values computed correctly
  and then not acted on, and `T012-R5` two more where yt-dlp accepted a key and ignored it; a
  malformed value fails **at edit time**; the migration round-trips an existing queue and an old
  row without the field loads; every control is keyboard-reachable and screen-reader-labelled
  (`NFR-005`); `ruff`, both mypy platforms and the touched suites are clean
- **Risk:** Medium for all nine — breadth rather than depth, and `NFR-008`'s churn lands on each

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data.
*(Premise re-checked 2026-08-06 after `T169-R5`. Still true, and narrower than it was: `0009`
**destroys** data rather than transforming it. That is a different problem with a different answer
— it needs a test proving the rows are gone, which it has, not an allowance for values that
legitimately changed, which is what this task is for. What did move is the strict per-column rule
below: it now covers `jobs` only, because `history` no longer exists to compare.)*
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** Phase 4.5 — inside `T-184`'s review
**Scheduled:** 2026-09-17 — `T-184` adds a field to `DownloadRequest`, so its migration is expected
to be the first that transforms stored values. The maintainer's order does this task **in that
review** rather than after it ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17)). The premise
still has to hold: a migration that only adds a column with a default transforms nothing, and then
this task waits again
**Depends on:** the first migration that changes stored values
**Relevant context:** `T014-R4`; `docs/project/TESTING.md` §7 (Migrations)
**Affected surfaces:** `tests/unit/test_persistence.py`

#### Scope

`T-014`'s migration test asserts strict per-column equality **for the tables in
`_MIGRATED_TABLES`**, which since 2026-08-06 means `jobs` alone. That is correct while every
migration either leaves a table's values alone or removes the table outright, and any unasked-for
change is loss. It will be **wrong** the day a migration legitimately transforms values.

**A destructive migration is not the case this task covers**, and `0009` is the reason to say so:
it removes rows on an explicit ruling and proves it with its own regression. This task is about the
opposite situation — values that change and are still correct — where equality has no way to tell a
good transformation from a corrupt one.

A `TRANSFORMED_BY_MIGRATION` allowance was written and then removed: `T014-R4` established that
an allowance can conceal a corrupt-but-readable migration, and an empty allowance protects
nothing while adding a mechanism nobody has exercised. Designing it against a real migration
beats designing it against an imagined one.

#### Acceptance criteria

- The first data migration ships with a test asserting the transformed values are **correct**,
  not merely different — a readable row holding wrong data is the failure mode `T014-R4` named
- Untransformed columns stay under strict equality
- The v1 fixture remains untouched; a new version freezes its own

#### Out of scope

- Any change to `T-014`'s current strict comparison, which is right until then

### T-248 — Filename shaping and the modification time

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--restrict-filenames`, `--no-restrict-filenames`, `--windows-filenames`,
`--no-windows-filenames`, `--trim-filenames`, `--mtime`, `--no-mtime`
**Specific criteria:** **`T-034`'s containment check runs after these, not before.** All three
filename options change what yt-dlp writes, and `--trim-filenames` can shorten a name into a
collision; the containment and collision tests are extended over each, and a test fails when the
check is removed. `--windows-filenames` is asserted on **both** platforms — its whole purpose is a
platform difference, and a Linux-only assertion proves nothing about it.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` with fourteen real worker sessions on `127.0.0.1`; probes in the
implementer's scratch notes.

- **On unreleased `main`, `--trim-filenames` and `--windows-filenames` in the options field make
  yt-dlp write outside the chosen folder.** The worker renders and contains the name once, then
  hands yt-dlp the absolute staging path as a literal template, and yt-dlp applies both options
  again to the **whole path**: a trim keeps the first N characters of it, and Windows names
  replace a reserved character in any folder of it. Measured in sessions: a trim of 80 wrote
  `…/tmp/claude-1000/-mnt-storage-…-tracks-and-tra. 2 of the set.mp4`, eight levels above the
  chosen folder; a trim of 201 created a sibling folder; a folder named `Talks: 2026` became
  `Talks# 2026/…`. Reproduced independently with yt-dlp's `prepare_filename`: for
  `/home/sean/Videos`, a trim of 15 names `/home/sean/Vide. 2 of the set.mp4`. The claim's
  source check then fails the job, **after** the file and any folder exist, and nothing removes
  them. **Critical guess** (`TESTING.md` §14: *writing outside the directory the user chose*).
- Medium: the `REQ-011` preview ignores shaping typed in the options field; `--no-windows-filenames`
  lets a title's backslash through, which `core/paths` then splits into a folder (*AC\DC live* →
  `AC/DC live.mp4`), or blames the user's template for a title's text.
- `--windows-filenames` otherwise only swaps `#` for `_` in typed text, since `DAT-002` already
  enforces Windows-legal names on both platforms, and both spellings are no-ops on Windows (read).
  A trim can merge two names, which `T-046` numbers (measured). yt-dlp's file date is off by
  default and the application never sets it; `--mtime` dated a file to `Last-Modified`.
- `--compat-options mtime-by-default`, and its bundles, reach `updatetime` through the options
  field, which neither `T-361`'s derivation nor the destination test sees.
- **Adjacent, outside this task:** `--compat-options all` or `allow-unsafe-ext` turns off yt-dlp's
  unsafe-extension check **for the whole process**, and the edit-time check alone does it in the
  GUI process (`exe` refused, then accepted after checking `--compat-options all`). **High guess.**
  `--compat-options filename` is admitted and does nothing, `REQ-031`'s *accepted and dropped*
  (Medium guess).

**Ruled 2026-10-15:** question 1 as recommended, as `T-363`, which also takes question 4 as
recommended. Questions 2 and 3 are open.

**Questions for the maintainer** (recommended first):

1. **When the breach is fixed.** A small task now, before `T-250`, as `T-361` ran before `T-247`:
   the download pass stops carrying `trim_file_name` and `windowsfilenames`, which keep acting
   where the name is rendered, and the sessions become regression tests; Linux evidence suffices.
   / Within this task at its slot (it waits on `STARBASE`). / Refuse the spellings now and lift the
   refusal here.
2. **The Windows pair.** Reclassified `app:policy` and refused, since `DAT-002` already owns
   Windows-legal names; this task then builds five options. / A checkbox for
   `--windows-filenames` only. / Both, as yt-dlp's tri-state (`core/paths` would stop splitting
   titles on `\`, a `T-034` boundary).
3. **Where shaping and the date live.** In Settings beside *How files are named*, frozen into the
   request as the template is (`UX-014` amended). / Preset fields in a *File names* group. / Split.
4. **A `--compat-options` value reaching a control's key** — `mtime-by-default` here, `format-sort`
   for `T-250`, one ruling for both. Refused at edit time naming the control, derived per value
   from yt-dlp's parser. / yt-dlp's precedence. / The control wins silently (`REQ-031` forbids).

### T-250 — Format depth: sorting, checking and the merge container

**Status:** Proposed — **design ruled 2026-10-15, all four questions as recommended** (`ARC-010`
and `UX-015` amended, second, that day); runs after `T-363` and `T-364`. Filed 2026-08-16 by
`T-183`
**Options (4):** `-S/--format-sort`, `--check-formats`, `--no-check-formats`,
`--merge-output-format`
**Specific criteria:** `--format-sort`'s field grammar is validated against yt-dlp's own accepted
fields rather than passed through; `--check-formats` costs a request per format and the format
table's probe budget is stated (`T-161`'s per-entry lesson); `--merge-output-format` and
`remux_container` are two ways to name a container and the precedence between them is written down.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on a real YouTube probe and downloads; probes in the implementer's
scratch notes.

- **No defect at `HEAD` for the four**, but building them breaks a recorded invariant:
  `--check-all-formats` and `--format-sort-reset` are other options sharing the typed
  destinations, so `T-361`'s recorded claim that only aliases share a built option's destination
  stops being true, and the audit's drift test fails on both once the keys are emitted.
  `--compat-options format-sort` is a third route into the sort (`T-248`'s question 4).
- **A sort never changes a format chosen from the table** (IDs resolve the same under four sorts);
  it moves the built-ins' selectors and reorders the probe's list.
- **yt-dlp refuses nothing about a sort's meaning**: an unknown field logs a deprecation and is
  ignored, `res:abc` silently sets no limit, and **`vcodec:nonsense` silently picks a different
  format**. Its field table is a class-level dict an unknown field writes into, so the vocabulary
  must be read in a fresh process.
- **Checking costs**: 3 requests to read a URL normally, 5 with `--check-formats`, **79 over 12.9 s
  with `--check-all-formats`**, 44 of them thumbnail checks — and the options field applies to the
  add dialog's own read, so such a preset makes each pasted URL about ten times slower. Check
  downloads write to `/tmp`, or with `--windows-filenames` to the worker's working directory
  (Medium guess).
- **A remux or recode runs after the merge**, so it decides the final container and a merge
  container becomes an intermediate (two passes); merging into `avi` failed *Conversion failed!*
  after the download was paid for.

**Ruled 2026-10-15: all four as recommended.** Building them moves `--check-all-formats` to
`typed`, makes `--format-sort-reset` the typed counterpart of clearing the sort, and corrects
`T-361`'s recorded claim that only aliases share a built option's destination.

**Questions for the maintainer** (recommended first):

1. **How far the sort check goes.** Fields and limits, against a transcription bound to yt-dlp by
   a fresh-process drift test, deprecated aliases refused naming the replacement. / Fields only. /
   Ask yt-dlp lazily in the GUI process.
2. **The check's positions and phase.** Four radio buttons — yt-dlp decides, the chosen formats,
   every format, never — on the download only, `--check-all-formats` becoming typed (five options).
   / Three, with `--check-all-formats` an application policy. / Four, on both phases.
3. **Merge container and remux.** A separate merge choice with a written precedence (recode, remux,
   merge, yt-dlp), set to the remux's container when it fits so there is one pass, offering
   *fall back to mkv*. / Exclusive in the model. / No merge control.
4. **Where they go.** A *Choosing the format* group at the top for the sort and the check, disabled
   for a format chosen from the table, and the merge choice in *Container* (`UX-015`). / The format
   dialog. / One *Format* group.

### T-252 — Download tuning and the retry policy the settings screen shows

**Status:** Proposed — filed 2026-08-16 by `T-183`. **Measured 2026-09-18, while correcting
`T184-R1`: fragment retries are zero today, not yt-dlp's ten.** `build_options` deliberately sets
`--retries` and not `--fragment-retries` (its own comment, from the maintainer's 2026-08-13 ruling),
and the consequence was not measured at the time: `downloader/fragment.py` reads
`self.params.get('fragment_retries')` with **no default** into `RetryManager`, whose first line is
`self.retries = _retries or 0`. So an absent key is **no retries at all** on every fragmented
format, which is most of YouTube. That is this task's to decide rather than a defect to fix
quietly — the policy it presents has to start from what the application really does now.
**Options (7):** `-N/--concurrent-fragments`, `--fragment-retries`, `--extractor-retries`,
`--socket-timeout`, `--download-sections`, `--live-from-start`, `--no-live-from-start`
**Specific criteria:** **the three retry knobs this task owns are presented as one policy**, not
three integers — and the entry no longer calls them *the whole* retry policy, because
`--file-access-retries` and `--retry-sleep` stay in the hatch (`T183-R4`'s wording point) —
`--retries` already exists and `ytdlp_adapter` carries a comment deferring `--fragment-retries`
here by name, so this task is where the difference between them stops needing a comment to explain.
`--download-sections` takes a time-range grammar that is parsed and refused at edit time.
`-N` interacts with the pool's own concurrency (`ARC-007`, `CONCURRENCY_MAXIMUM = 16`) and the
interaction is measured rather than assumed.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` with the worker's own `run_session`, a local HLS stream and a scripted
server that fails chosen requests; probes are in the implementer's scratch notes, not the
repository.

- **A fragmented download can end *Done* with a fragment missing — in `0.1.0` as on `main`.** One
  503 on fragment 3 of a 12-second stream: the job ended `Succeeded` with 250 of 300 video frames
  (155,465 bytes against 185,873), and yt-dlp's `Skipping fragment 3` reached no row. A 403 did
  the same with retries set to 3. yt-dlp's own command line, on its defaults, retried both and
  delivered the whole file. The cause is two library defaults the command line overrides:
  `fragment_retries` absent is zero, and `skip_unavailable_fragments` is on. `v0.1.0`'s
  `build_options` and pin are the same. **Severity guess Critical** under §14's *silent wrong
  result*, at least High given the narrow trigger.
- **`retries` absent is zero as well**, not only `fragment_retries` (`downloader/http.py:360`,
  read). Ten is the *command line's* default. So Settings' *The downloader's own* means no retries:
  one 503 partway through a progressive transfer failed the job as `EXTRACTOR_ERROR`, which the
  queue's automatic retry (NETWORK only) never takes. With retries 3 it succeeded. **Medium guess.**
- **The settings screen's retry text is untrue three ways at `HEAD`**: pieces retry zero times by
  default; the setting does govern a fragment's 5xx and connection errors (each fragment is
  fetched by an HTTP downloader built from the same params); only a 4xx or an incomplete read falls
  to the fragment count.
- **This entry's *most of YouTube* is wrong here**: all three built-ins chose `https` formats on a
  YouTube probe, so `retries` is the one that matters there. Fragments matter on HLS and DASH
  sites and on every `--live-from-start` capture.
- **Two hatch defects with `--download-sections`.** Two ranges are admitted and the second
  overwrites the first in the one output path (`Deleting existing file`, job `Succeeded`): a
  `REQ-031` defect, **High guess**. And it aborts *"ffmpeg is not installed"* whenever ffmpeg is
  reached through `ffmpeg_location` rather than `PATH`, because yt-dlp's ffmpeg *downloader* reads
  only `PATH` unless its command line sets a class attribute; that is how the Windows installer
  finds its bundled copy (inferred, not run on Windows). **Medium guess, High once a control ships.**
- **`-N` multiplies with the pool**: one job at `-N 4` peaked at 4 concurrent requests, three jobs
  at 12; the worst case is 16 × N and yt-dlp sets no ceiling. `--socket-timeout -1` passes edit
  time and fails the job (`T184-R8`'s class, Low).

**Ruled 2026-10-15:** the shipped defect is fixed first, as `T-364`, on questions 1 and 2 as
recommended. Questions 3 and 4 are open.

**Questions for the maintainer** (recommended first):

1. **What *nobody chose* sends for `retries` and `fragment_retries`.** yt-dlp's command-line
   defaults, read from `parse_options([])` at the pin and held there by a test, shown as *10 — the
   downloader's own*; changes behaviour for `0.1.0` users, which the changelog says. / Numbers
   chosen in `core/settings.py` (a second copy of a library default, which `T-196` declined). /
   Leave them absent and relabel the default *No retries*.
2. **A fragment still missing after its retries.** `skip_unavailable_fragments=False`, so the
   attempt fails and the job's own retry resumes from staging, with the hatch's
   `--skip-unavailable-fragments` kept as the user's opt-in (a second shared key, an `ARC-010`
   amendment). / Keep the skip and mark the job *Done, incomplete* (log parsing, a new outcome). /
   Only restore the counts (still silent after eleven failures).
3. **Where the seven live.** Fragment retries, extractor retries, socket timeout and `-N` (capped
   at 8) in *Settings › Network* beside the retry count; sections and live-from-start per preset in
   a *Which part* group below *Which items* (`UX-015`). / All seven per preset. / All in Settings.
4. **Several sections.** One file per section, named by the stem and a section suffix, claimed as
   one family. / Refuse a second section (narrows `REQ-030`). / Join them (a new ffmpeg step).

### T-253 — Network reachability: address family and politeness delays

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-4/--force-ipv4`, `-6/--force-ipv6`, `--sleep-interval`, `--max-sleep-interval`
**Specific criteria:** `-4` and `-6` share yt-dlp's `source_address` and are mutually exclusive —
`DownloadRequest` makes that unrepresentable rather than validating it; `--max-sleep-interval` is
refused without `--sleep-interval`, which is yt-dlp's own rule, and it is refused at edit time.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on a machine with no IPv6 route; probes in the implementer's scratch
notes.

- **No defect at `HEAD`**, and one gap: `--max-sleep-interval` is refused as *cannot tell what
  this would change* because the table generator runs each option alone, so a randomized delay is
  unreachable (`REQ-030`, Low).
- **`-4`, `-6` and the hatch's `--source-address` all write `source_address`**, the last typed
  winning. Once `-4`/`-6` have a control, a typed `--source-address` beside them would be admitted
  and overridden — the `REQ-031` shape — unless the build decides.
- **`-6` with no IPv6 fails as NETWORK**, so the queue retries it three times before the user sees
  why. The family reaches yt-dlp's traffic only: thumbnails and update checks read neither it nor
  the proxy.
- **yt-dlp's library enforces none of the command line's pairing rules** (max without min, max
  below min, negatives): `{max: 1.5}` slept, so the typed fields must check themselves.
- **The sleep is per file**, so a merged download sleeps twice; **a sleeping job sends nothing**, so
  its row reads *Downloading* throughout; **a cancel during a sleep is never cooperative** (noticed
  only when the sleep ended), so the manager's escalation always answers it; and **three jobs
  started within 0.17 s of each other**, so with the pool the delay spaces nothing between jobs.

**Questions for the maintainer** (recommended first):

1. **The address family and `--source-address`.** One radio group in *Settings › Network* —
   Automatic, IPv4 only, IPv6 only, *From this address* — absorbing `--source-address` (an audit
   change; the task grows to five options). / Three choices in Settings, `--source-address` left in
   the hatch and a disagreement refused at queue time. / Three choices per preset.
2. **What the delay means with several downloads at once.** yt-dlp's meaning, in *Settings ›
   Network* beside the speed limit, saying that downloads running together do not take turns. / A
   queue-level gap between starts (new manager behaviour; parity fails). / Per preset.
3. **What the row says while a job waits.** A *Waiting* stage from yt-dlp's `Sleeping N seconds`
   line, pinned by a test (a new `Stage` member). / Nothing; the control's note says so. / The
   application sleeps itself (one wait per job; parity fails).

### T-254 — SponsorBlock, opt-in per preset

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (3):** `--sponsorblock-mark`, `--sponsorblock-remove`, `--no-sponsorblock`
**Specific criteria:** **off by default, and the control says what enabling it sends.** `SEC-003`
permitted this and `NFR-007` was amended to name SponsorBlock as a third permitted destination
*conditional on the user enabling it*; a test asserts no SponsorBlock request leaves the process
while the option is off. The category lists are validated against yt-dlp's own. `--sponsorblock-api`
is **excluded** — `SEC-003` declined a configurable endpoint — and this task does not reopen it.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on real YouTube downloads, with a loopback server standing in for the
SponsorBlock API where the request had to be read; probes in the implementer's scratch notes.

- **Through the options field on unreleased `main`, *Embed metadata* plus `--sponsorblock-mark`
  produces a file with no metadata.** The option implies a second `FFmpegMetadata` that writes
  chapters only, appended after the application's own, and it rewrites the file from a chapters
  map, dropping every tag the first wrote: the control run had `title=Me at the zoo`, the hatch
  run none. **High guess.**
- **The lookup carries every header typed through `--add-headers`**, `Authorization` included,
  captured on loopback; a youtube.com cookie was not sent. The four-character hash prefix
  `SEC-003` ruled on still holds. **High guess, Critical where the header is a credential.**
- **The hatch already turns SponsorBlock on with nothing saying what is sent, on the probe as
  well**: one lookup each from the staging probe, the session's probe and the download, three per
  queued video. **Medium guess.**
- Low: `--sponsorblock-chapter-title` and `--no-sponsorblock` are refused as *changes nothing*
  although each changes something beside a mark; `--sponsorblock-mark -sponsor` is admitted and
  builds nothing (`T012-R5`'s shape).
- SponsorBlock acts on YouTube alone, so the local integration pages can never fail a *no request
  while off* test; an offline guard through `run_all_pps('after_filter')` with requests refused
  works. A removal is ffmpeg work, and without ffmpeg the download finishes and then fails, so
  `REQ-024`'s gate is load-bearing. Two `ModifyChapters` passes leave a stale SponsorBlock chapter,
  so the build must compose one with the hatch's `--remove-chapters`.

**Questions for the maintainer** (recommended first):

1. **What a preset holds.** Per category, *leave*, *mark as a chapter* or *cut out*, stored as two
   disjoint tuples, in one *SponsorBlock (YouTube only)* group below *Keep beside the file* (eleven
   radio groups). / Two checkbox lists (an overlap rule). / One switch (no per-category choice).
2. **Marking and *Chapters*.** While anything is marked, *Chapters* shows checked and held, and one
   `FFmpegMetadata` carries both (the structural fix for the metadata loss). / Marking disabled
   until *Chapters* is ticked. / Implied in `build_options` only.
3. **Typed headers on the lookup.** Look up without them, through a subclass whose session carries
   only the network settings (overrides a private method; feasibility unverified). / Refuse
   `--add-headers` while SponsorBlock is on. / Say so and amend `NFR-007`.
4. **When `HEAD`'s defects close.** Within this task, as `T-249`'s did (`main` is unreleased). / An
   interim refusal of the two spellings now.

### T-255 — Per-extractor arguments

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** Lowest among the nine — one option, and the most expert-facing of the 44
**Options (1):** `--extractor-args`
**Specific criteria:** the `IE_KEY:ARGS` grammar is parsed into a validated structure, never stored
as the string the user typed; an unknown extractor key is refused **with the reason** rather than
accepted and ignored, which is `T012-R5`'s defect exactly; values are redacted under `DAT-004` like
any other text this application supplies, because an extractor argument can carry a token.

#### Mapped 2026-10-14 — the design, before the code

Mapped against `8b0aad6` on real YouTube requests, with every request outside YouTube's hosts
refused unsent; probes in the implementer's scratch notes.

- **Unruled and admitted on unreleased `main`: two arguments choose the host requests go to.**
  `youtube:innertube_host=H` sent all four player requests to `H` (measured, refused unsent), with
  a signed-in session's authorization computed for it (read); `tiktok:api_hostname=H` copies the
  TikTok session cookie onto `H` (read, not run). `SEC-003` declined a configurable SponsorBlock
  endpoint because *its typo is a new network destination*; nothing covers these. **High guess,
  Critical once signed in.**
- **Any key and argument is admitted and an unknown one silently ignored** — `T012-R5` live
  (`nosuchie:anything=1`, `youtube:nosucharg=1`). **A repeated `--extractor-args` for one
  extractor keeps only the last.** **Medium guesses.**
- Lower: `generic:impersonate` is `SEC-003`'s forbidden `--impersonate` as an argument, inert only
  while curl_cffi is absent; `youtube-ejs:dev=true` turns off yt-dlp's checks on the solver script
  it executes (read); `zan:split_angles=true` makes ffmpeg re-encode where `requires_ffmpeg`
  cannot see it (read).
- **The key space is not the extractor list**: `twitch`, `jiosaavn`, `wrestleuniverse`,
  `stacommu`, `youtube-ejs`, `youtubepot-*` and `youtubejsc-*` are read and are not extractor keys,
  and no extractor declares its argument names. Token-carrying arguments include `po_token`,
  `visitor_data`, `hls_key`, `device_id` and `client_id`; stored, they are secrets at rest, which
  meets `DAT-003`'s reopening condition. The entry's `DAT-004` is withdrawn since 2026-08-01;
  `DAT-003`'s `T-049` amendment and `ARC-010`'s 2026-09-26 rule are what bind.

**Questions for the maintainer** (recommended first; the first is a security ruling):

1. **Which pairs are forbidden.** Four families on `SEC-003`'s and `SEC-004`'s reasoning:
   configurable endpoints, impersonation, and the solver's developer switches; everything else,
   `hls_key` included, permitted (the documented `innertube_host=studio.youtube.com` workaround is
   lost). / Endpoints only. / Everything, as the user's own text.
2. **What *unknown* is checked against.** A generated allowlist of key and argument pairs from the
   pinned source, drift-tested like `option_table.py` (plugin keys refused). / Extractor keys only
   (refuses working `twitch` arguments). / A short hand-written list.
3. **Storing token values.** Verbatim, with `DAT-003`'s provenance row amended to name the field and
   values registered for redaction except fixed vocabularies. / Kept out of storage (no retry after
   a restart). / The system keyring (a new runtime dependency).
4. **The editor.** One *Extractor arguments* group above the hatch, one `KEY:ARG=V;…` per line,
   checked as typed and shown back merged and normalized. / A table. / Named YouTube controls.

### T-339 — Hear Narrator read the Windows application

**Status:** Proposed — **deferred past `0.1.0` by the maintainer on 2026-09-14** (`T-327` item 3). Not
release-blocking for `0.1.0`; its release notes say Narrator's speech was not checked by a person.
**Scheduled 2026-09-17** into Phase 4.5's last stage, beside the acceptance walk: both need a
person at a Windows desktop, and the walk is one sitting at the end of the phase.
**Owner:** Maintainer performs; Implementer records
**Priority:** Medium — an accessibility claim `NFR-005` makes and a person has not heard
**Phase:** Phase 4.5 — stage 4, with the end-of-phase walk
**Relevant context:** `T-327` item 3, as scoped there; `NFR-005`; `IMPLEMENTATION_PLAN.md` §Phase 4's
screen-reader amendment (coherence *"belongs to the pre-release session"*);
`tests/ui/test_windows_accessibility.py`, which gates names and roles but cannot judge speech

#### Scope

With Narrator on, on an installed build: open Add URLs, stage a URL, open its format table, choose a
format, add it, start the queue, and open Preferences. Is what Narrator says *coherent*: does each
control announce what it is and what it does, in an order that makes sense?

#### Acceptance criteria

- [ ] The walk above done by a person, described in their words in a dated record
- [ ] Anything incoherent filed as its own task, with its severity under `TESTING.md` §14
- [ ] `REQUIREMENTS.md` §3's *known-unverified* line about Narrator rewritten to what was heard

---

### T-348 — Update the application from inside it, rather than by downloading the file

**Status:** Proposed — **asked for by the maintainer on 2026-09-17**, trying the `0.1.0.dev0` build
that reports a newer release: *"is the only way to update the program to download the new file?"*
Told that it is, by `REL-009`, they answered *"that should definitely be a phase 4.5 task."*
**Sequenced 2026-09-17: ruled in this phase, built in a later one** — see below. The shape itself is
**still owed**, so `REL-009` stands unamended and the application keeps notifying only.
**Owner:** Maintainer decides the shape; Implementer builds
**Priority:** Medium — every user of `0.1.0` updates by hand today
**Phase:** Phase 4.5 — stage 4, the ruling only
**Relevant context:** `REL-009` (notify only, and its *worth revisiting* clause), `REL-005`
(the unsigned installer), `OPS-002`'s note on automatic updates, `T-338` (the checker this builds
on), `NFR-007` (what the application may talk to)

#### What exists now

`Help → Check for Updates…` and the daily check say a newer release is out and open its page
(`T-338`). **Nothing is downloaded or run** — item 3 of `REL-009` — so the user fetches the new
AppImage or installer themselves and replaces what they have. Settings and the queue live in the
user profile, so they survive either way.

#### Why `REL-009` left it open, and what has to be answered

Its own words: *"worth revisiting once installers are signed: applying an update in place becomes
reasonable then."* The two platforms do not update the same way, and each raises its own question:

- **Windows.** An applied update runs the installer, which is unsigned (`REL-005`), so SmartScreen
  is raised again on every update, and the download needs its own integrity check. Signing is named
  as the `1.0` condition, so this may be a decision about ordering rather than about mechanism.
- **Linux.** An AppImage updates through its own mechanism (zsync, as `AppImageUpdate` and Gear
  Lever use), which needs the release to publish the matching file. Replacing a running AppImage
  is not the same operation as replacing an installed tree.
- **Both.** What is verified before anything is run (`SHA256SUMS` is published; a signature is not),
  what the user is asked, and what happens to a download in flight.

#### The shape, recommended 2026-09-18, still the maintainer's to rule

**What the release actually publishes**, read from `v0.1.0` rather than assumed, because every
option below depends on it:

| Asset | Size |
|---|---|
| `SHA256SUMS` | 206 bytes |
| `Tracks-and-Trails-0.1.0-setup.exe` | 93,482,037 |
| `Tracks_and_Trails-0.1.0-x86_64.AppImage` | 68,311,544 |

**There is no `.zsync` file**, so the delta updating `AppImageUpdate` and Gear Lever do is not
available without changing what the release publishes. **`SHA256SUMS` is published**, so any option
that fetches can verify before anything runs, which is the step users skip.

| Option | What the user does | What it costs |
|---|---|---|
| **A. Status quo** | Reads the notice, opens the page, downloads, replaces the file themselves | Nothing to build. It is the friction the maintainer noticed: *"is the only way to update the program to download the new file?"* |
| **B. Fetch, verify, hand over** (recommended) | Presses one control; the application downloads the asset for its platform, checks it against `SHA256SUMS`, and shows it in the folder with what to do next | A download surface with progress and cancel, somewhere to put the file, and the verification. **Windows still raises SmartScreen** when they run it, because `REL-005` leaves the installer unsigned. Linux still needs the file made executable and moved |
| **C. Apply in place** | Presses a control and the application updates itself | The riskiest, and `REL-009`'s own clause ties it to signing. Windows must exit for the installer to replace its files, and an unsigned installer raises SmartScreen on **every** update; Linux replaces the running AppImage. Needs its own clean-machine evidence per platform, which is a release-gate-sized job |

**Ruled 2026-09-18: B**, as recommended, and recorded as an amendment to `REL-009` — which now
permits the download and its verification, and still forbids running anything. The build stays in a
later phase by the 2026-09-17 sequencing ruling.

**Recommended: B.** It removes exactly the friction that was reported, and it moves the integrity
check from something a user is told to do into something the application does. It does **not** wait
on signing, which C does. Signing improves B and C equally, so choosing B now costs nothing later.

**Two rules B would add, and they are proposed rather than inherited** (`T348-R1`). This entry said
they came from `REL-009` item 5; that item governs the construction of the **release-page URL**
only, and item 3 currently forbids downloading or running anything at all. So both belong to the
amendment B would make, not to what is already authorised:

- The asset name is **built from the parsed version**, never taken from the response — an extension
  of item 5's reasoning to a second URL, in the same spirit and by the same argument.
- The checksum is compared **before the file is offered**, never after. A new rule, and the reason
  B is worth building: it is the step a user skips.

**Until such an amendment is ruled, `REL-009` stands as written: notify only, nothing downloaded or
run.**

#### Sequencing, ruled 2026-09-17

The Phase 4.5 plan put three shapes to the maintainer — status quo, fetch and hand over, apply in
place — with the recommendation to **rule now and build later**, because in-place updating waits on
signing and signing is a `1.0` condition (`REL-005`, and `REL-009`'s own *worth revisiting* clause).
The maintainer took that recommendation.

**What that settles:** nothing is built for updating in Phase 4.5, and `REL-009` is not amended by
this phase. **What it leaves open:** which shape, which is the maintainer's to rule whenever they
choose, and at the latest with the signing decision. "Fetch and hand over" remains the one shape
that is buildable before signing, if they want something visible sooner; it still raises SmartScreen
on Windows, because that is the installer's signature rather than the download's.

#### Scope

Put the options to the maintainer with their costs, then build what is chosen. At least: check and
notify as now (the status quo); fetch the file and hand it over, verified, leaving the user to run
it; and apply the update in place, per platform. Whatever is chosen amends `REL-009`.

#### Acceptance criteria

- [x] A recorded decision, amending `REL-009` — 2026-09-18: fetch, verify, hand over. The build is
  still a later phase's by the 2026-09-17 sequencing ruling
- [ ] If built: the update is verified against what the release publishes before anything runs, on
  both platforms, with the failure path shown to the user
- [ ] If built: a clean-machine run on each platform, updating a real earlier release to a newer one
- [ ] `REQ-030`'s wording and the README's update section match what the application does

---

### T-352 — Retire `JobProgressView`, keeping the helpers the row uses

**Status:** Proposed. Filed 2026-09-24 to carry `UX-005`'s
[2026-09-24 amendment](DECISIONS.md#amended-2026-09-24--the-progress-view-is-retired-and-the-row-is-the-only-progress-surface),
the maintainer's ruling to retire the view.
**Owner:** Implementer. The Planner updates `ARCHITECTURE.md`'s module map.
**Priority:** Low. This is maintenance with no user-visible change, but it removes about 2,200
lines and their full-suite time.
**Phase:** Phase 4.5 (`0.1.0` debt)
**Depends on:** nothing. Land it after `T-351` if both are open at once: both touch `queue_view.py`
imports, and `T-351`'s fix is the user-visible one.
**Effort:** Medium, estimated. Most of the work is moving helpers and their tests without changing
behaviour.
**Relevant context:** `UX-005` §2 and its 2026-08-06 and 2026-09-24 amendments, `T-017`, `T-340`,
`T-344`, the comment in `app.compose` above the pool naming
**Affected surfaces:** `ui/job_detail.py`; its importers `ui/queue_view.py`, `ui/row_delegate.py`,
`ui/format_table.py`, `ui/add_dialog.py`, `ui/main_window.py` and `app.py`; `ui/error_text.py`
(`describe_failure`); `tests/ui/test_job_detail.py`; the view's cases in
`tests/ui/test_windows_desktop.py`, `tests/integration/test_composition.py` and the other test files
that import it; `tools/windows/mutations/mut_view_stray.py` and `mut_view_reverse.py`, with their
`CASES` entries; and comments that name the view (`ui/log_view.py`, `ui/queue_view.py`,
`ui/row_delegate.py`, `ui/row_verbs.py`)
**Risk:** Low to Medium. Deleting tests can delete coverage of the helpers they also exercised.
**Required checks:** Ruff lint and format, `mypy src`, bare `mypy` and Windows-platform `mypy`, the
full suite, and the `windows desktop` job, because Windows tests and mutation plugins change.

#### Acceptance criteria

- [ ] The pure helpers the product imports (the list is in the amendment) live in a module named for
      what they are. Every importer uses it, and their unit tests move with them rather than going
      with the view.
- [ ] `JobProgressView` and `build_progress_view` are gone, with the tests and mutation plugins that
      exist only for them. Anything they alone reached (`CANCELLED_TEXT`, `describe_failure`) goes
      too, unless another caller is found and named.
- [ ] Nothing the row draws or speaks changes. The queue, delegate, accessibility and composition
      tests pass unchanged, apart from import paths.
- [ ] No comment still describes the view as present or pending, and `ARCHITECTURE.md`'s module map
      no longer lists `job_detail.py` as a per-job detail view.

---

### T-353 — Remove unused paths and correct dialog ownership

**Status:** Proposed — the cleanup follow-up requested by the maintainer on 2026-09-24,
bounded by the independent [September codebase audit](reviews/codebase-audit-2026-09.md).
**Owner:** Implementer
**Priority:** Medium within Phase 4.5 debt — repeated dialog retention and tests exercising unused
production helpers warrant scheduled work; cosmetic simplification alone would not.
**Phase:** Phase 4.5 (`0.1.0` debt)
**Depends on:** T-352 for any overlapping progress-view/helper removals. Independent cleanup may
be prepared first; do not duplicate that task's retirement or change the phase order.
**Relevant context:** AUD26-R2/R3/R7/R9; AGENTS §§6–8; TESTING §14; T-350's controlled-probe work.
**Affected surfaces:** The audit's bounded cleanup inventory across `src/`, its actual test
consumers, and `tools/t308_warning_stacking_probe.py`.
**Risk:** Medium — Qt result-consumption order, persistence callbacks and real coverage must
survive removal. Treat tests as evidence to migrate, not as dead weight.
**Required checks:** Ruff lint/format, `mypy src`, bare mypy and Windows-platform mypy;
relevant UI/lifecycle tests, full unit/integration suites for core/downloader/persistence edits;
full UI suite if dialog lifetime/ownership changes. Record actual failures and exact heads.

#### Scope and evidence

The audit at `a7310d1` independently found five retained Settings dialogs and 475 child widgets
after five open/reject cycles. It also fault-injected a partial geometry write that destroyed the
previous layout file. These are the behavior corrections. The rest is removal of confirmed dead
members and migration of tests off obsolete wrappers, plus the small duplications enumerated in
AUD26-R7/R9. In particular, queue-order tests must reach `_next_startable`/actual scheduling rather
than asserting that the unused `_next_waiting` is the production decision.

Use the audit's inventory, including its exclusions. Preserve Qt callbacks, intentional observation
seams, lifecycle guards, historical evidence and the helpers T-352 moves. Do not redesign
`app.compose`, unify unrelated thread/network services, or introduce a generic persistence dispatcher
on the strength of a complexity/lint score. Keep the warning-stacking diagnostic's production
presentation path and temporary profile while controlling its automatic-update dependency.

#### Acceptance criteria

- [ ] Repeated production open/close cycles release closed Settings, Options, preset, format and
      add dialogs after callers consume results. Cover both accepted and rejected results and
      late callbacks; do not put `WA_DeleteOnClose` on a modal whose caller still reads it.
- [ ] A failed geometry write preserves the previous complete file; successful save/load and
      nonfatal failure behavior remain intact.
- [ ] For each inventory removal, record the live consumer search and either preserve the assertion
      through the actual production route or state why it tested only a retired API. A scheduler
      ordering mutation must fail the replacement ordering test.
- [ ] Small deduplication preserves pending-write rollback/order and variant-specific behavior.
      No test seam or documented invariant disappears merely because production does not call it.
- [ ] The warning-stacking probe uses a controlled release-check dependency and keeps its profile
      isolation, actual `present()` route, and shutdown cleanup.
- [ ] Required checks pass, or failures are independently dispositioned; review the exact final
      head. Update current navigation/comments while preserving captured historical bytes.

---

### T-354 — Bound repeated queue rendering and scheduling work

**Status:** Proposed — the performance follow-up requested by the maintainer on 2026-09-24,
bounded by the independent [September codebase audit](reviews/codebase-audit-2026-09.md).
**Owner:** Implementer
**Priority:** Medium within Phase 4.5 debt — measured quadratic format computation and repeated
store reads on the GUI thread, plus long-line formatter cost.
**Phase:** Phase 4.5 (`0.1.0` debt)
**Depends on:** T-351 before changing playlist caches or invalidation; its incorrect visible-row
mapping must not be hidden by a faster refresh. Coordinate helper moves with T-352.
**Relevant context:** AUD26-R4/R5/R6/R8; NFR-001; ARC-005; T016-R1/R3; T197 redaction invariants.
**Affected surfaces:** Queue/staging models and delegate invalidation, manager scheduling,
`core/logging.py`, and narrowly measured secondary paths listed in the audit.
**Risk:** High — a stale cache can display the wrong request; scheduler shortcuts can violate
ordering/holds; formatter optimization must not leak values or over-redact ordinary logs.
**Required checks:** Ruff lint/format, `mypy src`, bare mypy and Windows-platform mypy;
full unit/integration suites for core/downloader changes; relevant queue, staging, delegate and
accessibility UI tests. Use controlled workloads and call counts, plus before/after timings on one
machine, not timing-only tests whose result depends on host load.

#### Scope and evidence

At `a7310d1`, one selector-role read for each of 25/50/100/200 playlist members performs
650/2,550/10,100/40,200 format computations: n(n+1). The 200-member instrument took 343.9 ms,
measuring model reads rather than a viewport repaint. One scheduling decision over 500 startable
waiting jobs performs 500 store reads. A synthetic 8,000-character `/a b` log line took 549.0 ms
to redact. These independent counts and measurements establish the primary work.

Then measure the bounded secondary leads: preset resolution for unrelated staging roles,
segments computed for unrelated header roles, whole-model thumbnail invalidation, unchanged gate
label polishing, stopped-queue timer work, repeated template previews/settings saves, repeated
worker option construction, and the duplicate clear-completed predicate. Implement only changes
with measured benefit and an explicit invalidation/order contract. Keep immediate-settings
behavior, transaction boundaries and the progress chain's persistence-before-signal ordering.

#### Acceptance criteria

- [ ] Repeated group/member role reads scale linearly for an unchanged request set, with counted
      work at multiple playlist sizes. Changes to group membership, order, requests and relevant
      status immediately invalidate the affected result; mixed-group/accessibility text stays true.
- [ ] One scheduling/fill cycle avoids a fresh store read per waiting job per free slot. Preserve
      two-lane capacity, retry order, queue reordering, worker-tree holds, pending writes and
      shutdown. Exercise the actual production selection path.
- [ ] Long-line redaction has bounded growth on the captured synthetic family while every existing
      privacy case, overlapping-secret case and ordinary-prose control remains covered.
- [ ] Measure secondary changes before/after and retain those justified by the evidence. A lead
      not confirmed as worthwhile is recorded as such, not silently claimed optimized.
- [ ] Run relevant mutations/controls against caching, ordering and redaction; preserve all required
      checks and exact-head review. No external dependency or architecture change without its own
      authorization.

---

## Proposed — Phase 5

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Proposed — a potential task, not open work** (maintainer's release ruling, `T-328`, 2026-09-13, taking the recommendation). Never reproduced in 466 attempts, and repetition is spent; a recurrence turns the `windows desktop` job red on its own. It becomes a task again only if it recurs, ideally with crash capture armed (`tools/windows/crash-dumps.ps1`, `docs/WINDOWS_VERIFICATION.md`).

**Status before this ruling:** **Blocked — on `T-092`, 2026-08-20. Still undiagnosed, still not blocking Phase 1**
(`OPS-007`, maintainer risk decision 2026-07-29). Downgraded **High → Medium**.

**The dependency was always there; the entry just never said it.** This task's own text already
concluded that only a **recurrence carrying a dump** can supply criterion 2 — *a stack is not a
cause* — and arming `STARBASE` to capture that dump **is** `T-092`. Meanwhile `Depends on:` read
*"nothing"* and the entry sat under `## Ready`, which asserts somebody can pick it up and make
progress. **Nobody can.** Repetition is spent at **466 attempts** — this entry's 361 plus the 105
full-suite Windows runs counted on 2026-08-20, which are more of the same shape rather than a new
one — and the one plan that remained — accumulating clean Windows runs — was measured on 2026-08-20 and
**cannot discriminate**, because the pre-fix sample is equally clean.

**What this changes is the board, not the risk.** The residual `OPS-007` accepted is unchanged and
still accepted; the four criteria are still deliberately not rewritten; and **the detection is in
the code rather than in this entry** — a recurrence turns the `windows desktop` job red whether or
not anybody is holding this task open. What moves is the honest label: this is waiting on a
machine being armed, which is `T-092`, which is waiting on a person.

*(Filed as a correction rather than a re-triage: nothing about the defect changed on 2026-08-20.
What changed is that the last avenue this entry proposed was tried and recorded as insufficient,
which left `Ready` claiming work that does not exist.)* The faulting object of the access violation is
unknown, product-versus-harness is unresolved, and the crash has never been reproduced: the
recorded **0 in 36** deliberate full-suite runs, plus **0/15 at `35fc7ec`** (run `30478557533`,
post-`T-090`) — **51 full-suite runs** in total, with 60 clean runs of the crashing test and 250
clean in-process iterations beside them. **361 attempts, zero events**, across three shapes and two
heads.

**`T-128` is diagnosed as of 2026-08-04, and it was a *harness* defect** — a fixture teardown
dropping a `QObject` that still owned a running `QTimer`, so the dispatcher followed a pointer into
freed memory. Two core dumps and a sub-second reproduction establish it; `src/` is not implicated,
because nothing there reads `is_idle` and the application holds one manager for the life of the
process.

**The free-evidence strategy below was tried on 2026-08-20 and it does not work. The runs were
gathered; what they cannot do is discriminate.** Measured rather than assumed: **105 completed
full-suite Windows runs** on `STARBASE` between 2026-08-04 and 2026-08-20, **zero native crashes**.
Method, so it can be re-run: every `CI` run since the `T-128` teardown fix at `bd4dde8`, taking the
`windows desktop` job's **`Full suite` step conclusion** rather than the job's — 92 `success` plus
**13 `failure`**, and the 13 count because each one **ran to completion with an ordinary pytest
tally**, which a process death cannot produce. 22 `cancelled` and 14 `skipped` are excluded because
the suite did not finish; the 14 are `T-270`'s window, where the step never ran. **Four of the 145
runs are accounted for separately and were not in the first telling of this** (`T074-R5`): they have
no `windows desktop` job at all — `31080589319`, `31120246285`, `31956224066` cancelled, and
`32042191296` failed before it. 92 + 13 + 22 + 14 + 4 = **145**, and none of the four is a completed
run, so the 105 is unchanged.

**Why that settles nothing, and it is this task's own arithmetic that says so.** The pre-fix sample
was **0 events in 51 full-suite runs**. The post-fix sample is **0 events in 105**. *"If the crash
stops recurring"* cannot be observed as a change, **because it had already stopped recurring before
the fix landed** — there is no measured pre-fix rate to beat, so the comparison is undefined.

**What the 105 buys is a dated zero and nothing more, and the first version of this paragraph
claimed more** (`T074-R5`). It gave a rule-of-three **2.9% per-run ceiling**, which assumes
exchangeable trials sharing one underlying probability. **These runs do not share one.** They span
sixteen days and many heads: between `bd4dde8` and `06745fa` the manager and test-lifecycle
surfaces alone move by **2 886 insertions and 622 deletions**. **`T074-R1` had already ruled exactly
this** — samples from materially different heads are not one population, and it required exact-head
observations rather than a rate. *A rate quoted over a changing tree is the same error as a rate
quoted from four observations on different heads*, which is the sentence this entry has carried
since `T074-R1` and which I re-made from the other direction.

**The observation and the non-discrimination argument both stand**; only the ceiling is withdrawn.
Neither `OPS-007`'s accepted residual nor the Blocked-on-`T-092` disposition ever rested on it.

**This is `T238-R2`'s ruling arriving at a second task, and neither entry saw it coming.** That
finding replaced `T-238`'s criterion 6 because *"a larger clean sample cannot distinguish **the
guard worked** from **the crash was always this rare**"*. **The sentence transfers verbatim**: swap
*guard* for *corrected teardown* and it is the paragraph below. Two tasks proposed the same
instrument against the same class of defect, and one of them had already had it ruled out.

**So what would actually move this is `T-092`, and nothing cheaper.** Clean runs cannot supply
criterion 2; only a **recurrence with a dump** can, which is what `T-092` arms `STARBASE` to
capture. Until then the honest position is unchanged: the residual is accepted under `OPS-007`, and
**the accumulating-runs plan is recorded as tried and insufficient rather than left open as
available**.

*(The paragraph below proposed that plan and is kept, because it is what was tried. It was
reasonable when written — what it missed is that its own Status paragraph already recorded the
pre-fix sample as clean, which is the fact that makes it unable to discriminate.)*

**That is a lead here, and it is the strongest one this task has ever had.** The Windows crash
recorded above happened in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — **the same file and the
same `manager` fixture** whose teardown `T-128` found at fault, with the same `ResultPump` thread
alive in the traceback. The corrected teardown is now on both platforms.

**It is still not established as the same defect, and the bar has not moved.** Windows produced an
access violation and `T-128` a SIGSEGV; this task's faulting object was never determined, so there
is still nothing to compare against; and *a stack is not a cause* — this task's own words, which
apply to the resemblance as much as to the stack. What can be done now is cheap and was not before:
**`STARBASE` runs the full suite on every push (`OPS-010`), so repeated green Windows runs against
the corrected teardown are evidence that costs nothing extra to gather.** If the crash stops
recurring there over a meaningful number of runs, that is the first positive evidence this task has
had; if it recurs, the harness fix is ruled out as its cause and that is worth just as much.

*(This block read "A candidate reproduction exists … `T-128` owns finding out". `T-128` has now
found out, and what it found does not implicate the product.)*

**The four acceptance criteria below stay unmet, deliberately not rewritten.** All four presuppose
a deliberate reproduction, which is the one thing no instrument has produced, so `OPS-007` accepts
the residual rather than redefining the bar. `T-092` arms `STARBASE` to capture a crash dump so a
recurrence supplies criterion 2 — *a stack is not a cause* — instead of another anecdote.

*(This read "Ready — still undiagnosed and still blocking Phase 1" until `OPS-007`. Before that it
read "In Review — diagnosed and fixed", which `T074-R4` found unsupported; what was fixed is
`T-090`, and `T-090` is **not** established as this crash's cause — the pre-fix sample was equally
clean, so a clean post-fix run carries no causal weight.)*

**A separate defect was found on the way and is `T-090`.** The `T-038` log listener could be left
reading a queue that something else had closed — a real race on the same thread the crash
traceback names, now fixed with tests. **That is not this task.** Calling it "diagnosed and fixed"
claimed a causal link to the historical access violation that no evidence supports, which is what
`T074-R4` reports. This task's acceptance criteria remain unmet.

*(Superseded, and worth keeping: this block read "diagnosed and fixed" on 2026-07-29. Finding a
real defect near a crash is not the same as finding the crash's cause, and the wording did not
keep them apart.)*
`0/12 at ea53c71` (run `30429327464`). That is evidence against the original 25% anecdote and is
**not** a rate: the four original observations came from materially different heads, so they are
not one population, and a single event gives no bound worth quoting (`T074-R1`). The faulting
object is unknown, product-pump versus harness is unresolved, and there is no correction mutation.
**Phase 1's Windows criterion stays unverified.** *(This block claimed "1 in 16, not 1 in 4"; that
promoted samples from changed heads into a stable rate.)*
**Owner:** Implementer
**Priority:** **Medium** — downgraded from High by `OPS-007`. It is still an access violation in a
module under `src/`, in the suite `OPS-005` and `T-073` made Phase 1's only Windows gate; what
changed is that 361 attempts produced no reproduction, so there is no work left that repetition can
do. It returns to High the moment it recurs
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
**Depends on:** **`T-092`** — which is itself Blocked on somebody at `STARBASE`. The Windows
runner exists; what does not exist is a configured crash dump, and without one a recurrence
produces another anecdote rather than criterion 2
**Relevant context:** `T-073`, `OPS-005`, `ARC-002`, `src/tracks_and_trails/downloader/result_pump.py`
**Affected surfaces:** unknown — `downloader/result_pump.py` and/or
`tests/integration/test_manager.py`
**Risk:** **High to leave.** An intermittent crash makes every green Windows run mean less than it
appears to

#### Scope

The full suite on `STARBASE` died with exit **139**:

```
tests/integration/test_manager.py::test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Windows fatal exception: access violation
Thread 0x00000c88 [ResultPump] (most recent call first):
Thread 0x000024dc [Thread-50 (_monitor)] (most recent call first):
  File "...\tests\integration\test_manager.py", line 1028 in
    test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Segmentation fault
```

**It is intermittent, and the evidence for that is unusually clean.** The failing run was
`30416495270` at `454b80e` — a **documentation-only** commit whose code is byte-identical to
`38650dd`, which had passed the same suite minutes earlier.

| Run | Head | Full suite |
|---|---|---|
| `30415333608` | `c41e2ef` | pass |
| `30416156751` | `38650dd` | pass |
| `30416495270` | `454b80e` | **access violation** |
| `30416723791` | `32f9bd2` | pass |

**One in four**, with no code difference between a pass and the failure.

**Line 1028 is before the cancellation**, which narrows this usefully. It is
`assert spin(lambda: bool(recorder.progress), timeout=60)` — the wait for the *first progress
message*, three lines above `download.cancel()`. So the crash is not in the escalation path the
test is named for. It is in ordinary message delivery: `ResultPump` is a `QThread` emitting Qt
signals carrying Python objects from its `run()`, while the main thread sits in `spin()` calling
`app.processEvents()`.

#### What is not known

Everything about the cause. Recorded as a question rather than a hypothesis dressed as one:

- Whether the fault is in **product code** (`result_pump.py`, in `src/`, so `ARC-002`'s pump is a
  candidate) or in the **test harness** (fixture teardown ordering, a receiver outliving or
  predeceasing a queued emission).
- Whether it is specific to `child_ignoring_cancellation`, which is the one worker in the suite
  that deliberately refuses to stop, or reachable by any job.
- Whether it reproduces at all outside `STARBASE`. It has never been seen on Linux across many
  full-suite runs, but Linux has never been where this project's process faults show up.

#### Diagnostic progress, 2026-07-29 — two things narrowed, cause still unknown

**It does not reproduce on Linux.** Two attempts, both clean:

| Attempt | Result |
|---|---|
| The crashing test alone, 40 iterations | **40 passed, 0 non-zero exits** |
| `tests/integration/test_manager.py` entire, 5 runs | **5 × 71 passed**, no crash, no fatal exception |

That is a negative result and is worth exactly what a negative result is worth. It does **not**
clear Linux: `T-069` was ordering-dependent and failed only when one specific test ran first, and
the Windows crash happened inside a full-suite run, not a module run. What it does establish is
that the fault is not reachable by simple repetition of the failing test on this platform, so
whatever it is depends on the platform, on suite-wide ordering, or on both.

**The most obvious cause is already defended against, and this is the more useful half.** The
classic PySide6 access violation of this shape is a `QThread` object being destroyed while its
`run()` is still executing — and `ResultPump` emits `session_ended` from *inside* `run()`, so a
slot that dropped the last reference would do exactly that. It cannot: `_release()` in
`manager.py` refuses to drop a session while its pump is live —

```python
if session.pump_started and not (session.pump_finished or session.pump.isFinished()):
    return
```

— and `_sessions.pop()` is the only thing holding the pump. `_Session` even documents the two
moments as distinct: "the thread emits `session_ended` from inside `run()`." So the first
hypothesis anyone would reach for is not it, which is worth recording so nobody spends the
afternoon re-deriving it.

**Still open.** The crash traceback named two threads — `[ResultPump]` and
`Thread-50 (_monitor)`, which is `multiprocessing`'s — and the fault was at the wait for the first
progress message. Whether it is the pump, the queue read beneath it, the interaction between them,
or the harness remains unanswered. Nothing here should be read as narrowing it to product code.

#### The ordering hypothesis, tested — 2026-07-29

The earlier attempts ran the crashing test alone and its module. The Windows failure happened
inside a **full-suite** run, and `T-069`'s precedent is that suite ordering was the entire story,
so that was the remaining Linux hypothesis. Six deliberate full-suite runs:

| Attempt | Result |
|---|---|
| Crashing test alone, 40 iterations | 40 passed |
| `test_manager.py` entire, 5 runs | 5 × 71 passed |
| **Full suite, 6 runs** | **6 × 1401 passed, every exit code 0** |

**Linux is now exhausted as a route to this defect**, at least by repetition. Three shapes of
attempt, none of which reproduced it. That is not proof of a Windows-only fault — it is the
absence of a Linux reproduction after looking in the three places worth looking.

**So the measurement has to happen on the machine that shows it.** `.github/workflows/t074-repeat.yml`
runs the suite N times on `STARBASE` and reports a rate. Three things about it are deliberate:

- **Manual dispatch, in its own workflow.** `ci.yml` is a gate and runs on every push; this is an
  instrument. Folding it in would mean paying its cost on every push or making a gate
  conditional.
- **It does not stop on the first crash.** A rate needs every iteration attempted; stopping early
  turns it back into an anecdote.
- **It separates crashes from failures by exit code.** `pytest` exits 1 for a failing assertion.
  A crash takes the interpreter with it, so the code is a signal or an access violation — and
  `T-074` is not a failing assertion. Counting them together would let an ordinary red test
  inflate the crash rate.

"About one in four" came from four ordinary CI runs, where the denominator was however many times
the gate happened to run. This makes the denominator a choice, which is what the acceptance
criteria ask for.

#### The instrument ran — 2026-07-29, run `30429327464`

Twelve full-suite iterations on `STARBASE`, every one attempted:

| Iterations | Crashes | Failures |
|---|---|---|
| **12** | **0** | 0 — `1395 passed, 20 skipped, 32 deselected` each time, 209-217 s |

**"About one in four" was a denominator of four**, and this batch is not a replacement for it.
`0/12 at ea53c71` says the crash is not reliably reproducible at that head. It does **not**
establish a rate (`T074-R1`): the four earlier runs and these twelve are not one controlled
population — the manager and the full-suite composition changed materially between them, including
new integration tests — and after a single event an aggregate point estimate is not a bound. A
clean run is unremarkable under a 25% failure probability and under a 6% one alike.

The crash is real. It happened with a traceback naming `[ResultPump]` and `multiprocessing`'s
`_monitor`, on a documentation-only commit whose code was byte-identical to a passing run.

**It stays a Phase 1 blocker, and the reason is where it landed.** The only observed native crash
is in ordinary `ResultPump` delivery — the exact `ARC-002` path Phase 1 exists to prove — so the
uncertainty cannot be resolved in favour of product safety by counting clean runs. Downgrading it
or accepting the risk is the maintainer's explicit decision to record, not an inference this task
may draw.

**Still unknown: the cause.** Nothing here narrows it. A larger batch is running to either bound
the rate further or catch one with fresh diagnostics; the workflow keeps every iteration's output,
so a crash caught there arrives with its traceback rather than as a count.

*(Superseded: this section previously read "Not yet run. The job is authored and pushed;
executing it needs `STARBASE` and is the next step on this task." It has now run.)*

#### Diagnostic session, 2026-07-29 — narrowed, not diagnosed

**Both threads named in the crash are ours.** The traceback listed `[ResultPump]` and
`Thread-50 (_monitor)`, and `_monitor` was read as `multiprocessing`'s. It is not: `multiprocessing`
declares no such function, and `_monitor` is
`core/logging.py`'s `_ToWhicheverHandlersWeHaveNow._monitor` — the `T-038` log listener's thread
body. So the crash happened with the result pump and the **logging listener** both live, which
points somewhere the earlier notes did not.

**A mechanism worth testing, stated as a hypothesis.** `_monitor()`'s `finally` closes the worker
log queue — a `multiprocessing.Queue` — and `stop_listening_for_worker_logs()` **waits for
nothing**, deliberately (`T038-R2`, and it is right to: the GUI thread must not block on a slow
handler). So the close runs on the listener thread while parent threads may still be logging into
that queue and a spawned writer may still hold the other end. Closing a multiprocessing queue
under a concurrent user is the kind of thing that faults natively instead of raising, which is the
shape this crash took. The crashing test is also the one that **kills** a worker rather than
asking it to stop, so a writer dying mid-record is in scope there and almost nowhere else.

**Nothing here demonstrates that.** It is a mechanism that fits, and the file it implicates has a
recorded reason for the behaviour. It is written down so the next attempt starts from a candidate
rather than from the whole suite.

**What was attempted, and what it cost:**

| Attempt | Result |
|---|---|
| Repeat batch, 24 full-suite iterations on `STARBASE` | **0 crashes** (run `30454206697`) |
| Both batches together, recent heads | **0 in 36** |
| Repeat batch, 15 full-suite iterations at `35fc7ec`, **post-`T-090`** | **0 crashes, 0 failures** (run `30478557533`) |
| The crashing test alone, 60 iterations on Windows | **60 passed, 0 failed, 0 crashed** |
| A direct stress of the logging-teardown race | **unusable — it hung on Linux before its first iteration** |

The last row is the honest one. The harness drives a parent thread logging continuously while a
spawned writer is killed and the listener is torn down; it never reached a print, so it deadlocked
in its own setup rather than measuring anything. A failed instrument is not a negative result, and
it is recorded as neither.

**Classification is unchanged: product versus harness is still unresolved**, and `T-074` remains a
High Phase 1 blocker. What has changed is where to look — logging teardown alongside the pump,
rather than the pump alone.

#### What the diagnostic session produced — 2026-07-29

It found a **different** defect, now filed as `T-090`: the log listener could be left reading a
queue something else had closed. The evidence for that moved there with it.

**What it did not produce is anything about this crash.** The access violation has never been
reproduced — 0 in 36 full-suite runs, 60 clean runs of the crashing test alone, 250 clean
in-process iterations — so its faulting object is still unknown and it is still unclassified
between product and harness. `T074-R4`: a real race on the same thread is a candidate, not a
cause, and the crash's absence cannot distinguish them when it was already absent every time.

**What is genuinely narrowed** is that `_monitor` in the traceback is the `T-038` log listener
rather than anything in `multiprocessing`, so the next attempt has two of our own threads to
account for rather than one.

#### Acceptance criteria

- The failure is **reproduced deliberately**, with a rate, rather than waited for
- The faulting thread and the object it touched are identified — a stack is not a cause
- The fix is proven by a mutation that restores the crash, not only by runs that stop crashing
- If it turns out to be the harness rather than the pump, that is recorded explicitly, because
  the opposite conclusion is the one a reader would assume from the file it crashed in

#### Out of scope

- Retrying, `xfail`, or a rerun plugin. `T-069` established the rule: an intermittent failure gets
  its trigger found, not its symptom hidden. The one time this project reached for a retry the
  reviewer's instruction was explicit — *do not retry or xfail*
- `T-056`, which is a different intermittent on a different platform and is `OPS-005`-downgraded

---

### T-336 — The installed app crashed once with heap corruption opening *Naming and folders…*

**Status:** **Proposed — a potential task, not open work** (maintainer, 2026-09-13). Seen once, in
`T-327`'s Sandbox session, and not reproduced by any route below. It becomes a task only if it
recurs or can be reproduced; until then nothing is owed on it.
**Owner:** Implementer
**Priority:** None while it does not recur; if it does, a crash is Critical by `TESTING.md` §14
**Phase:** Phase 5
**Promoted by:** a recurrence — ideally under the crash capture below, so it arrives with a dump
**Relevant context:** `T-289` (a Qt widget destroyed on the wrong thread — a double free); `T-074`
(an access violation never reproduced, and why repetition alone does not discriminate); `T-092`
(crash dumps on `STARBASE`)
**Affected surfaces:** unknown until a dump names them

#### What happened

The maintainer, in the installed build in Windows Sandbox: pasted
`https://www.youtube.com/watch?v=NnPvX-uMYWk` into Add URLs, waited for it to be read, opened the
row's ⋮ and chose *Naming and folders…*; the application closed. Windows recorded:

- `Application Error`: `tracks-and-trails.exe` 0.1.0.0, faulting module `ntdll.dll`
  10.0.19041.6456, **exception `0xc0000374` (heap corruption)**, offset `0xff489`, 16:30:01.
- The application log ends at 16:29:47, mid-probe of the same URL, which had also been probed at
  16:24:47 in the same session — so the dialog saw that URL twice. Nothing after: a native fault
  writes no Python record.

**Heap corruption is reported where the heap is next checked, not where it was damaged.** The menu
choice is where the process died; it is not established as the cause.

#### Not reproduced, by

- The same flow from source on `STARBASE` under the real Windows plugin — real probe, the ⋮ zone
  and the menu entry clicked through `QTest`, the maintainer's own URL, and with the dialog closed
  and reopened between two reads of it: **eight runs, no crash**.
- The output-path preview the panel opens with, under `pythonw.exe` (no console, as installed): clean.
- The 17 add-dialog tests touching the panel and the menu, under the real plugin: pass.
- The maintainer, in Sandbox: the installer built before that day's later changes (`d1e03e2`) and
  the current one (`e037c05`) — **no crash with either**; no dump was produced.

#### To capture it

Kept on `STARBASE`, not in the repository: `C:\dev\interactive-dumps.wsb` (the interactive Sandbox
plus a writable `C:\dev\sandbox-out`) and `sandbox-share\arm-crash-capture.ps1`, which turns on
full page heap for `tracks-and-trails.exe` — so a double free or overrun faults at the write that
does it — and WER full dumps into that folder. WinDbg is installed on `STARBASE` to read one.

#### If it is promoted

- A dump of the recurrence, with the faulting module and stack read
- The cause named and fixed, with a test that fails without the fix

---

*Created 2026-09-10, when Phase 4.5 was resequenced to follow the first release and this
phase became the next one to run. `T-039` also carries `**Phase:** Phase 5` and stays under
`## Blocked`, because that section is about status rather than phase.*

## Blocked

### T-344 — Show progress while a download is being processed

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-344.md)); its last criterion is a person watching a long conversion on the installed build, which the waived walk would have covered (`T-328`, 2026-09-16). Phase 4.5. *(Was In Review:)* asked for by the maintainer on 2026-09-15: a long video took a long time
to process after downloading, and nothing showed the application was still working. The maintainer
chose *both, where possible* (a real percentage where ffmpeg can report one, otherwise the step's
name, a moving bar and the time so far) and chose to ship it **in `0.1.0`**, from the options put.
Moves the candidate.
**Owner:** Implementer
**Priority:** High for `0.1.0` by that choice
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `REQ-011` (indeterminate progress), `REQ-014` (stages), `NFR-005`, `T-216`
(a finished bar is furniture)
**Affected surfaces:** `downloader/protocol.py`, `downloader/worker.py`, `downloader/ytdlp_adapter.py`,
`ui/queue_view.py`, `ui/row_delegate.py`

#### What was wrong

While a job was post-processing the row showed the download's bar, which is full once the bytes are
in; the chip read *Processing*, and nothing moved. yt-dlp's post-processor hook reports only
*started* and *finished*, and `real_run_ffmpeg` runs ffmpeg through `Popen.run`, which returns when
ffmpeg ends.

#### What changed

- **`Progress` gains `step`** (yt-dlp's hook name for the step) **and `step_fraction`** (0 to 1).
- **The worker** records the step and the media's length when a step starts, and turns ffmpeg's
  position into a fraction of that length, sent at most every 0.25 s. It checks for cancellation
  there too, so a long conversion stops when asked. Downloads only; a probe runs no step.
- **`ytdlp_adapter.ffmpeg_progress`** replaces the `Popen` that yt-dlp's `postprocessor.ffmpeg` looks
  up, for step commands only (those carrying `-loglevel repeat+info`). It adds `-progress pipe:1
  -nostats`, reads the position lines, drains standard error on its own thread, returns what
  `Popen.run` returns, and kills ffmpeg if the callback raises. If yt-dlp no longer has that module
  or `Popen`, nothing is installed and the row falls back to the moving bar.
- **The row, while processing:** the step in plain words with the time so far (*Converting to audio
  · 1:05*), the step's own percentage on the chip and the bar when known, and otherwise a moving
  bar (`BUSY_ROLE`) redrawn by a timer that stops when nothing is processing. The size keeps the
  downloaded total, and the screen-reader text names the step and its percentage or says it cannot
  be measured.
- **Words are keyed by the names yt-dlp's hook reports** (`pp_key`, which drops *FFmpeg*). The first
  version used class names and would have named nothing; the end-to-end test found it.

#### Acceptance criteria

- [x] Protocol: `step` and `step_fraction` carried and validated (`tests/unit/test_protocol.py`)
- [x] Adapter: step commands recognised, arguments inserted after the executable, positions read from
  both microsecond keys, the returned shape kept, ffmpeg killed when the callback raises, a yt-dlp
  without the module left alone, and a real `FFmpegExtractAudioPP` conversion reporting positions to
  the end of the file with yt-dlp's `Popen` restored (`tests/unit/test_ffmpeg_progress.py`)
- [x] Worker: a started step announced by name; the position as a fraction, bounded and throttled;
  no fraction without a length; cancellation at the next position; the hook around downloads and
  never probes (`tests/unit/test_step_progress.py`)
- [x] Row: the step's percentage and not the download's; the moving bar, name and time without a
  position; the time restarting per step; a step without words shown as its stage; the timer
  stopping; the moving bar drawn, moving, and routed through the real delegate; and every step yt-dlp
  can report either has words or is one of six stated quick steps (`tests/ui/test_processing_progress.py`)
- [x] End to end, a real MP3 download through the composed application reports `ExtractAudio` with a
  position reaching 1.0 (`tests/integration/test_end_to_end.py`). **Also run on `STARBASE`**
  (Windows, ffmpeg 8.1.2): the new and changed test files and this test, 166 passed
- [x] Mutations, each failing those tests: hook never installed (1); no kill on raise (1); every
  command treated as a step (2); only `out_time_us` read (2); no cancellation check (1); no throttle
  (1); zero without a length (3); the download's fraction while processing (3); never busy (2); no
  timer from the status change (2); a step erasing the size (1); the time not restarted per step
  (2); no step words (3); the delegate never painting the moving bar (1). A second timer start on
  each drawn step **survived** and was removed as redundant
- [ ] Seen by a person: a long conversion on the installed build shows the step, its progress or the
  moving bar, and the time so far

---

---

### T-342 — Add URLs and Preferences opened with their title bars above a laptop's screen

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-342.md)); its last criterion is a real Windows display at 125%, which the waived walk would have covered (`T-328`, 2026-09-16). Phase 4.5. *(Was In Review:)* reported 2026-09-15 by the maintainer from a friend's Windows laptop
(1920x1200 at 125%, the maintainer's figures): *Add URLs* and *Preferences* opened with the title bar
above the top of the screen, so the window could not be moved and no URL could be typed. Moves the
`0.1.0` candidate.
**Owner:** Implementer
**Priority:** High — the first screen a user needs could not be used on an ordinary laptop
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `T-242` and `T222-R1` (height bounds for *Preferences* and *Options*);
`T-310` (`FormatDialog.sizeHint` bounded by the screen); `NFR-005`
**Affected surfaces:** new `ui/screen_fit.py`; `ui/add_dialog.py`; `app.present`

#### What was found, measured on `STARBASE` (Windows 10, 1600x900)

- **Qt does not keep a dialog's frame on the screen.** With `QT_SCALE_FACTOR=1.25` (a 1280x720
  logical screen) *Add URLs* was placed with its frame at y = -241.
- **Add URLs grew after it was shown**, at a true 100% as well: opened at 600 pixels (Qt's cap of two
  thirds of the screen for a window never resized), centred for that, then grown to 788, its layout's
  height. With its list asking for 16 rows it grew to 1364 on the 900-high screen.
- **Nothing bounded where any dialog lands**; *Preferences* and *Options* bounded only their height.

#### What changed

- `ui/screen_fit.py`: `DialogsOnScreen`, installed by `app.present` and owned by the main window,
  fits every top-level `QDialog` when it is shown, once more after the event loop turns, and on each
  resize while visible: a maximum size of the working area less the frame, then a move so the whole
  frame, title bar first, is inside. A fit that changed something looks again, at most four times per
  showing. `fitted_geometry` is the pure rule.
- `AddUrlDialog.sizeHint` is bounded to the working area less 48 pixels (`bounded_to_screen`), and the
  dialog is given that size before it is shown.

#### Measured on `STARBASE`, 100%, *Add URLs* asking for 16 rows

| Build | Frame | Inside the screen |
|---|---|---|
| Unchanged | 1395 tall from y = 110 | no |
| Rule only | 1395 tall from y = 0 | no |
| Bounded hint and rule, no size before showing | 1395 tall | no |
| All three | 900 tall from y = 0 | **yes** |

At the real row count *Add URLs* and *Preferences* fit the 900-high screen in every build. **With
`QT_SCALE_FACTOR` at 1.25, 1.5 and 2.0 the results did not agree with a true 100% screen**: Windows
refused geometries (*Unable to set geometry*) and *Add URLs* stayed partly outside at 1.25 and 1.5
with the change. That emulation is not a real scaled display, so it is recorded rather than trusted
either way.

#### Acceptance criteria

- [x] `fitted_geometry`: above the top, too tall, past each other edge, already inside (unchanged),
  and a working area shorter than the frame (the top wins) (`tests/ui/test_screen_fit.py`)
- [x] Installed rule, offscreen: a dialog shown above and taller than the screen ends inside; one
  that grows after showing is fitted again; the rule leaves with its owner; installing twice installs
  one
- [x] `present()` installs it and a dialog of the real window is fitted
  (`tests/integration/test_composition.py`)
- [x] *Add URLs* with 40 wanted rows: its hint and its size are within the working area less 48, and it
  has a size of its own before showing
- [x] Mutations, each failing those tests: no top clamp (4); no shrink (1); no refit on resize (1); no
  fit on show (2); the hint unbounded (1); not installed by `present` (1); owned by the application
  (4); no size before showing (1)
- [ ] **Seen on a real Windows display at 125%**: *Add URLs* and *Preferences* open with the title
  bar on screen and can be moved (the friend's laptop, or a Windows machine set to 125%)

#### 2026-09-15 — the `yt-dlp` canary failed two of these tests

The canary runs the suite in **one process**, and there two tests failed at `48cf076`: a dialog that
grew after showing was not fitted again, and the rule appeared to outlive its owner. **Reproduced
locally** by running `test_composition.py` then `test_screen_fit.py` in one process. A composition
window left alive by an earlier test kept its rule installed, and **both rules counted fits on one
dynamic property**, so a dialog's budget of `MAX_PASSES` was spent twice as fast. In the application
there is one window and one rule, so the shared counter did not show there; it was still wrong.

Corrected: each rule keeps its own count (a property named for that rule). The ownership test now
asserts the rule object is destroyed with its owner, instead of watching a dialog that other live
rules may still move. A new test installs two rules and grows a dialog after showing; with a shared
counter it fails. The two files together in one process: 97 passed.

---

---

### T-340 — A failed download's log could not be opened from anywhere in the application

**Status:** **Blocked** — the implementation is approved ([record](reviews/T-340.md)); its last criterion is a person seeing *Diagnostics…* on both platforms, which the §11 walk would have covered. The maintainer waived that walk on 2026-09-16 and assigned what it would have found to Phase 4.5 (`T-328`). *(Was Blocked:)* on its last criterion, a person seeing it on both platforms (`T328-R4`'s
walk). The implementation was approved by review on 2026-09-14
([record](reviews/T-340.md#2026-09-14--diagnostics-implementation-review)). Found 2026-09-14 while
preparing `T-328`'s §11 acceptance sheet; the maintainer chose to fix it in `0.1.0`.
**Owner:** Implementer
**Priority:** High — `REQ-019` is an MVP requirement and §11 criterion 6 names a copyable log
**Phase:** Phase 4.5 — stage 4, closed by the end-of-phase acceptance walk
**Scheduled:** 2026-09-17 — the maintainer ruled **one** acceptance walk, on the finished Phase 4.5
build, rather than a sitting of its own for each of these ([the order](IMPLEMENTATION_PLAN.md#order-2026-09-17))
**Relevant context:** `REQ-019`; `REQUIREMENTS.md` §11 criterion 6; `UX-005` §2 and §4 and their
2026-09-14 amendments; `T-084` (the log view); `T-135` (what the `⋯` holds)
**Affected surfaces:** `ui/log_view.py`, `ui/main_window.py`, `ui/add_dialog.py`

#### What was wrong

`LogView` (`T-084`) was built only by `ui/job_detail.py`, and `UX-005` §2 removed the detail pane
from the window. `queue_view.py` already said so (*"nothing in the product constructs that
widget"*), and no decision moved `REQ-019` elsewhere. Every log-view test passed against a widget
no user could reach. The candidate evidence for `3c011b8` and `246dcdf` did not notice.

#### What changed

- **`DiagnosticsDialog`** in `ui/log_view.py`: the existing `LogView` in a non-modal window titled
  *Diagnostics for* the job's title or URL, with Close. Escape closes it. Copy still copies the
  whole file (`T084-R2`).
- **The queue row's menus** offer *Diagnostics…* below the verbs, on the `⋯` and on the keyboard and
  right-click route.
- **A failed line in the Add dialog** offers it below *Read this URL again*. An unsupported URL
  fails there and never becomes a queue row, so this is the entry §11 criterion 6 is walked through.
- **Offered only when the job has logged something** (`has_job_log`). The manager creates a job's
  log file as its session opens, so a check for the file alone would offer it on every job that ever
  ran.

#### Acceptance criteria

- [x] A queue row whose job logged something offers *Diagnostics…* on the `⋯`, including when
  nothing was dropped, and on the context route; the window shows the file and Copy copies all of it
  (`tests/ui/test_row_verb_wiring.py`)
- [x] No entry for a job with no log file or an empty one (same file)
- [x] A failed Add dialog line, logged through the worker's real route and the parent's per-job
  handler, offers it and the window shows the extractor's message; a silent failure and a line that
  read offer nothing (`tests/ui/test_add_dialog.py`)
- [x] The window is non-modal, titled for its job, focused on the text, and closes from Escape and
  from Close (`tests/ui/test_log_view.py`)
- [x] Mutations, each run against the new tests: no queue entry (2 fail); the `⋯` still returning
  nothing when no verb was dropped (1); file existence instead of size (2); no Add dialog entry
  (1); the Add dialog entry without the log check (1); a modal window (1)
- [ ] Seen by a person on both platforms, as part of the §11 criterion 6 walk (`T-328`)

---
