# The format table against `yt-dlp -F` — Phase 3 exit criterion 1

**Produced:** 2026-08-07, for `T107-R1`
**yt-dlp:** 2026.07.04 (the pinned baseline, `OPS-002`)
**Host:** `kirk`, Fedora
**Criterion:** *"The format table matches `yt-dlp -F` output for a fixture set of URLs"*
(`ai/IMPLEMENTATION_PLAN.md` §Phase 3)

---

## What was run

Both recorded sources were re-captured with `python -m tests.fixtures.capture <name>`, now that
`CONSUMED_FORMAT` carries `fps` and `tbr` (`T-107`). `yt-dlp -F` was then run by hand against the
same URLs and transcribed below.

The comparison is asserted in `tests/ui/test_format_table.py::test_the_table_matches_what_yt_dlp_f_reports`,
which reads the committed fixtures rather than the network — the suite must not touch it
(`ai/TESTING.md` §5). This document is the record of the run the transcription came from.

## `https://archive.org/details/BigBuckBunny_124`

```
ID EXT RESOLUTION |   FILESIZE PROTO | VCODEC  ACODEC  MORE INFO
-----------------------------------------------------------------
0  ogv 533x300    |   44.76MiB https | unknown unknown derivative
1  mp4 640x360    |   59.01MiB https | unknown unknown derivative
2  avi 1280x720   |  316.85MiB https | unknown unknown derivative
```

## `https://archive.org/details/testmp3testfile`

```
ID EXT RESOLUTION |   FILESIZE PROTO | VCODEC  ACODEC  MORE INFO
-----------------------------------------------------------------
0  ogg unknown    |  110.55KiB https | unknown unknown derivative
1  mp3 unknown    |  194.00KiB https | unknown mp3     original
```

## What agrees, and what is rendered differently on purpose

**Every format, and every fact yt-dlp reports about it, agrees.** Same ids, same extensions, same
resolutions, same sizes, same codecs, same notes.

Two renderings differ deliberately and the test asserts across the difference rather than around it:

- **Sizes.** yt-dlp prints `44.76MiB`; this window prints `44.8 MB`, the powers-of-1024 labelling
  `format_bytes` uses everywhere else. The test compares the **bytes** underneath, through
  `SORT_ROLE`, to within 1%.
- **Absences.** yt-dlp prints `unknown`; the window prints `Unknown` (`UNKNOWN_TEXT`). Same fact,
  and the test maps one to the other explicitly.

## The two divergences this comparison found

Both were real defects in the submitted implementation, and both are fixed:

1. **`0x0` where yt-dlp says `unknown`.** archive.org reports `height: 0` and `width: 0` for an
   audio item. `_as_optional_int` keeps `0` — correctly, for a *count* — so the table rendered a
   resolution of `0x0`. `_as_dimension` now projects a zero dimension as absent.
2. **"audio only" asserted from a missing codec.** `FormatInfo.is_audio_only` is
   `video_codec is None and audio_codec is not None`, and `_as_optional_codec` maps **both** a
   missing `vcodec` and yt-dlp's explicit `'none'` to `None`. So a format whose video codec is
   merely *unknown* was reported as having no video at all. The resolution column now reads the
   height and declines to assert what it cannot know.

## What this evidence does not cover

**Three columns are not exercised by these sources**, because yt-dlp reports nothing for them:
`fps`, `bitrate` and `vcodec` are `unknown` for every format archive.org serves here. The table
renders the placeholder, which **is** the match — but a source that reports those fields would
exercise more of the projection than this does.

That is a limit of the sources, not of the fixtures, and `ai/TESTING.md` §5 chose them for being
boring and freely licensed. Adding a source that reports fps and codecs would strengthen this
evidence; doing so is a scope change with its own licensing question, and is deliberately not
smuggled in here.

**One platform.** Linux, `kirk`. The comparison is a property of the projection rather than of the
window, so it is not expected to differ on Windows — but it has not been run there.
