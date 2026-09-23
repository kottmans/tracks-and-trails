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
- `writethumbnail` → `<stem>.<ext>`, and **the extension is not knowable in advance**: yt-dlp
  writes whatever the source offered. This is the part that needs a source with a real thumbnail
  to pin down, which `http.server` serving a bare mp4 cannot provide.

**Globbing the staging directory is not the answer**, and the reviewer said so: *"do not simply
keep every staging intermediate"*. `requested_sidecars`' own docstring already rejects globbing for
subtitles, because it finds files that were embedded and then deleted.

## Not done here

The correction itself. It needs the thumbnail extension question answered against a source that
has one, and the contained, collision-safe output family extended to carry the result — which is
`claim_outputs`' contract, not a line in `requested_sidecars`.
