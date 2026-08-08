# Review handoff — `T-109`, post-processing (`REQ-010`)

**To:** Reviewer (Codex)
**From:** Implementer
**Date:** 2026-08-07
**Task:** `T-109` — Post-processing: audio, container, thumbnail, metadata, chapters, subtitles
**Verdict wanted:** the initial comprehensive review (`AGENTS.md` §10)

## Review boundary

**Base:** `99c33cb` — *"Draw the board's charts by hand, and re-measure it"*. That commit is the
Phase 3 board, redrawn earlier in the same session on maintainer instruction; it touches no `src/`
and no `tests/`, and it is deliberately outside this boundary.

**Head:** the single commit that carries this file — `git log -1` on `main`, subject *"Offer the
seven post-processing options"*. One commit, so `git show` is the whole review.

Every file in it is `T-109`:

```
src/tracks_and_trails/core/models.py
src/tracks_and_trails/core/presets.py
src/tracks_and_trails/downloader/worker.py
src/tracks_and_trails/downloader/ytdlp_adapter.py
src/tracks_and_trails/persistence/repositories.py
src/tracks_and_trails/ui/add_dialog.py
src/tracks_and_trails/ui/format_text.py
src/tracks_and_trails/ui/options_dialog.py        (new)
src/tracks_and_trails/ui/row_delegate.py
tests/fixtures/capture.py
tests/integration/test_end_to_end.py
tests/integration/test_post_processing.py         (new)
tests/ui/test_add_dialog.py
tests/ui/test_options_dialog.py                   (new)
tests/unit/test_fixtures.py
tests/unit/test_post_processing_options.py        (new)
tests/unit/test_presets.py
ai/STATUS.md
ai/TASKS.md
```

## What was built

`REQ-010`'s seven options, `docs/UX_SPEC.md` §6's editor, and the route to it. The task entry in
`ai/TASKS.md` carries the full account; the short version:

- **Five typed fields** on `Preset` and `DownloadRequest` (`ARC-010`, `P-12`): `remux_container`,
  `recode_container`, `embed_thumbnail`, `embed_metadata`, `embed_chapters`.
- **`MediaInfo.subtitle_languages`**, projected from `info["subtitles"]`' keys — `P-17`'s source,
  which did not exist. `tests/fixtures/capture.py` gained `subtitles` as a consumed key with a
  reducer that commits the language codes and nothing under them.
- **`build_postprocessors` emits all seven in yt-dlp's own order**; `build_options` sets
  `writethumbnail`.
- **`ui/options_dialog.py`**, reached as `Options…` on the row's format control.
- **`claim_sidecars`** in `worker.py` — `T046-R3` met.
- **The preview accounts for a container change**, so `postprocessed_name` and
  `preview_is_provisional` no longer disagree with what a remux or recode writes.

## Checks, with their actual results

| Check | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `ruff format --check src tests` | 114 files already formatted |
| `mypy src` | Success: no issues found in 46 source files |
| `mypy --platform win32 src` | Success: no issues found in 46 source files |
| `QT_QPA_PLATFORM=offscreen pytest` | **2435 passed, 14 skipped, 2 deselected** in 678 s |

The suite was **2351 passed, 14 skipped** at the base, measured on the same machine before this
work started. Linux only; nothing here is POSIX-specific, and CI runs the whole suite on Windows.

## Mutations run

Six, against the new tests. **Two survived and both changed the work** — details and the corrections
are in the task entry's evidence table. In summary:

1. Drop the remux spec — killed.
2. `writethumbnail = False` — killed.
3. Skip `claim_sidecars` — killed.
4. Recode spelled as remux — killed.
5. `subtitleslangs` → `["all"]` — **survived**; the subtitle tests asked for every published
   language, so selection was not being asserted. Rewritten to a strict subset; now killed twice.
6. `FFmpegMetadata` split into two specs — **survived**, and the docstring explaining why it could
   not was wrong in the opposite direction. `FFmpegMetadata` defaults both flags to `True`, so an
   omitted flag turns an option **on**. Corrected, and a test now asserts chapters arrive without
   metadata.

## Where I would look hardest

- **`claim_sidecars`** (`worker.py`). It moves files out of the staging directory into the user's
  output directory. It reuses `claim_output_path`, so every move goes through `O_CREAT | O_EXCL`
  and cannot overwrite anything — but it is a new writer into the user's directory, which is
  `T-046`'s ground, and the stem-replacement that renames a sidecar is string surgery on a
  filename.
- **`_deserialize_request`** (`repositories.py`). A field absent from a stored blob now takes the
  dataclass default. This is forward compatibility for every row already on disk, and it also means
  a *corrupt* blob missing an optional field is read rather than refused. The four required fields
  still fail loudly; I believe that is the right line and it is the one judgement here I would most
  like a second opinion on.
- **The chapters test**, which drives yt-dlp's postprocessor rather than a download. The limit is
  stated in the module docstring and in the task entry; if you think it does not meet *"an
  observable change in the output file"*, that is a fair reading and I would rather hear it now.
- **`format_name`'s third fallback** (`_base_preset_for`). It re-asks the two existing matchers with
  the five options reset, so there is one definition of a match. What I want checked is that
  identity is still strict — `preset_name_for` unchanged — and only the *describing* path widened.

## Known-unverified

- **Windows.** Nothing platform-specific was added, and the suite runs there in CI, but no run has
  happened on this diff.
- **A real site.** Every download in the new tests is against localhost media built by ffmpeg. No
  fixture was captured and none needed re-capturing: `subtitles` joined the capture allowlist, so
  the existing fixtures project `()` for it, which is what they honestly contain.
- **Chapters from an extractor**, per the limit above.

## Follow-up already filed

`T-190` — `docs/UX_SPEC.md` §6 still says this screen "has not been specified against the ruling
yet". That file is not the Implementer's write set (`AGENTS.md` §4), so it is filed rather than
edited.
