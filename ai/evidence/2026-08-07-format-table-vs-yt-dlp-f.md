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

## fps — found, after all

**Amended 2026-08-07, by `T-185`.** Everything below this heading was written when the answer was
*"no acceptable source reports it"*, and it is kept because the search is the useful part. It is no
longer the conclusion.

### `https://video.blender.org/w/dmhvQNzwBnrWy1iYzVv5g7`

```
ID    EXT RESOLUTION FPS |   FILESIZE PROTO | VCODEC  ACODEC
-------------------------------------------------------------
240p  mp4 240p        30 |   50.54MiB https | unknown unknown
360p  mp4 360p        30 |   67.01MiB https | unknown unknown
480p  mp4 480p        30 |   89.70MiB https | unknown unknown
720p  mp4 720p        60 |  145.93MiB https | unknown unknown
1080p mp4 1080p       60 |  263.47MiB https | unknown unknown
```

*Big Buck Bunny 60fps 4K*, © Blender Foundation, CC BY 3.0, on the Blender Foundation's own PeerTube
instance. Media URLs are plain object-storage paths with no query string.

**`yt-dlp -F` prints an `FPS` column here, and two different values in it.** The table agrees, and
the agreement is asserted per row by `test_the_table_matches_what_yt_dlp_f_reports` like the other
two sources. **Two framerates rather than one is the part that matters**: a source reporting 30
everywhere would fill the column without ever ordering it, and `REQ-003` asks for a *sortable*
table — so `test_fps_comes_from_a_recorded_capture_by_value` sorts on it in both directions.

Three further shapes come free, each previously exercised only by the derived fixture:

- **Height with no width.** yt-dlp prints `240p`, not `426x240`, and so does this window —
  `describe_resolution`'s height-only branch, from a recording.
- **Exact sizes.** Against `wikimedia_caminandes`'s `filesize_approx`, so both halves of
  `T107-R7`'s exact-vs-estimate distinction now rest on real reports.
- **`unknown` codecs beside known framerates**, which is a combination neither other source has.

### How it was found, which is more reusable than the URL

The seven earlier probes were all **sources**. This one came from asking a different question:
**which extractors populate `fps` at all** — grepping yt-dlp's own extractor modules — and then
looking for a freely licensed instance of one. `peertube.py` reads `fps` from each published file;
`archiveorg.py` matches only inside `YoutubeWebArchive`'s itag table, which is why archive.org
itself never reports it.

*The original conclusion follows, unedited.*

## What was still not covered: fps

**No freely licensed source found reports it.** Probed on 2026-08-07:

| Source | fps | bitrate | codecs |
|---|---|---|---|
| `archive.org/details/BigBuckBunny_124` | no | no | no |
| `archive.org/details/testmp3testfile` | no | no | `acodec` only |
| `commons.wikimedia.org` — Caminandes, Big Buck Bunny, Sintel, Tears of Steel | **no** | yes | yes |

Four Commons files and three archive.org items; **none carries `fps` on any format**. So the fps
column was exercised by `derived_format_columns.json`, and `T-107`'s criterion was amended to
*populated from a recorded fixture **where the source reports it***. *(That is no longer where this
ends — see the section above. The amendment was still the right call at the time: it unblocked
`T-107` and its dependants against a search that had failed seven times, and `OPS-013` required the
gap to stay owned by an open task, which is what produced the eighth attempt.)*

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
