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

## A third source was added, because two columns needed one

**Amended 2026-08-07, after the re-review.** The comparison above establishes agreement for the two
archive.org URLs, and archive.org reports **no codec, bitrate or fps** for any of its derivatives —
so those columns were exercised only against synthetic values. That is a limit of the sources rather
than of the fixtures, and the re-review was right that the task claimed more than it had.

`wikimedia_caminandes` was captured for exactly that gap:

```
ID     EXT  RESOLUTION |  FILESIZE   TBR PROTO | VCODEC  ACODEC
----------------------------------------------------------------
0      webm 426x240    | ≈ 2.22MiB  207k https | vp9     opus
1      webm 854x480    | ≈ 4.52MiB  422k https | vp9     opus
2      ogv  1920x1080  | ≈29.97MiB 2796k https | theora  vorbis
3      webm 1920x1080  | ≈15.43MiB 1440k https | vp9     opus
source ogv  1920x1080  |  29.97MiB       https | unknown unknown
```

`https://commons.wikimedia.org/wiki/File:Caminandes-_Llama_Drama_-_Short_Movie.ogv` — Caminandes:
Llama Drama, © Blender Foundation, CC BY 3.0, unsigned URLs.

**Codecs, bitrate and estimated sizes are now asserted by value from a recorded capture.** The `≈`
sizes are `filesize_approx`, so this exercises `T107-R7`'s estimate rendering against a real report
as well; the `source` format carries an exact size and no bitrate, giving the contrast inside one
capture.

## What is still not covered: fps

**No freely licensed source found reports it.** Probed on 2026-08-07:

| Source | fps | bitrate | codecs |
|---|---|---|---|
| `archive.org/details/BigBuckBunny_124` | no | no | no |
| `archive.org/details/testmp3testfile` | no | no | `acodec` only |
| `commons.wikimedia.org` — Caminandes, Big Buck Bunny, Sintel, Tears of Steel | **no** | yes | yes |

Four Commons files and three archive.org items; **none carries `fps` on any format**. So the fps
column is exercised by `derived_format_columns.json`, and `T-107`'s criterion was amended to
*populated from a recorded fixture **where the source reports it***.

**That amendment is `OPS-013`, ratified by the maintainer on 2026-08-07.** When this section was
first written it said "amended by the maintainer" on the strength of a Reviewer's *offer* of the
wording, which the third re-review correctly refused to treat as a ruling; `T-107` was blocked on
that alone until the ratification. `T-185` stays open as the record of this search, so the next
person has somewhere to add a source rather than rediscovering that there wasn't one — and
`OPS-013` names closing it as *"no acceptable source exists"* a legitimate outcome.

`ai/TESTING.md` §5 wants sources that are freely licensed, unsigned and unlikely to change. A site
that reports fps and churns weekly would satisfy the criterion's letter and break the property §5
chose these sources for.

**One platform.** Linux, `kirk`. The comparison is a property of the projection rather than of the
window, so it is not expected to differ on Windows — but it has not been run there.
