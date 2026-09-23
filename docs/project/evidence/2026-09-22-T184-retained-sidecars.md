# Why the worker deletes a file the hatch asked to keep (`T184-R11`, second half)

**Measured 2026-09-22**, against pinned yt-dlp 2026.08.19, Python 3.14.7, over `http.server` on
`127.0.0.1` — the same exception `TESTING.md` grants the reservation tests, and no network.

The download runs through **this application's own `build_options`**, so what is measured is the
route that ships rather than a reconstruction of it.

## What happens

| Typed | Written into staging | Recorded in the result |
|---|---|---|
| `--write-info-json` | `clip.info.json` | **nothing** |
| `--write-description` | nothing (the generic extractor has none) | — |
| `--write-thumbnail` | nothing (no thumbnail for a bare mp4) | — |

`clip.info.json` is written and then **deleted**, because `_discard_staging` removes everything in
the job's staging directory that `claim_outputs` did not claim, and `requested_sidecars` claims
only what `requested_subtitles` names. The job reports success with the MP4 alone.

## Why the obvious fix does not work

yt-dlp **does** record the path internally — `YoutubeDL.process_info` sets
`info_dict['infojson_filename']`, and `_write_thumbnails` returns the written names, which the
caller folds into `__files_to_move`. Neither survives to the caller:

```text
files on disk:            ['clip.info.json', 'clip.mp4']
infojson_filename present: False
__files_to_move present  : False
keys containing 'file'   : ['filesize_approx']
```

Both keys are stripped from what `extract_info` hands back. So **the result cannot be asked which
sidecars were written**, and the reading that works for subtitles does not generalise: it works
only because `requested_subtitles` is one of the few such keys that does survive.

## What that leaves

The paths have to come from **what was asked for** rather than from what came back, which is the
shape `claim_outputs` already has — it takes `writing_subtitles=` derived from the request rather
than inferred from the result.

- `writeinfojson` → `<stem>.info.json`, deterministic.
- `writedescription` → `<stem>.description`, deterministic.
- `writethumbnail` → **read from the result after all.** The first pass here said the extension
  was not knowable in advance, because a bare mp4 has no thumbnail to write. Served an HTML page
  carrying `og:image`, yt-dlp writes `clip.jpg` **and records it**:

```text
files:                     ['clip.jpg', 'clip.mp4']
thumbnails key present:     True
entries: [{"url": ".../cover.jpg", "id": "0", "filepath": "/tmp/…/clip.jpg"}]
```

  `thumbnails[*]["filepath"]` survives where `infojson_filename` and `__files_to_move` do not. So
  no extension list is needed and none is pinned: the thumbnail is claimed by the path yt-dlp
  reports, exactly as subtitles already are.

**Globbing the staging directory is not the answer**, and the reviewer said so: *"do not simply
keep every staging intermediate"*. `requested_sidecars`' own docstring already rejects globbing for
subtitles, because it finds files that were embedded and then deleted. The mutation that replaces
the derivation with `staging.iterdir()` fails the control test, which is a download that asked for
nothing extra and must keep nothing extra.

## The correction

`retained_sidecars(options, staging, stem)` derives the two the result does not report;
`requested_sidecars` reads subtitles and the thumbnail from the result; `claim_outputs` takes both
and moves the whole family under one index, so a kept thumbnail cannot land as `clip.jpg` beside a
`clip (2).mp4` (`T109-R4`). Three real downloads cover it in
`tests/integration/test_retained_sidecars.py`, and three mutations are caught: dropping the
thumbnail, dropping the derived pair, and keeping everything in staging.
