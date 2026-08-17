# The yt-dlp option audit — every option, in exactly one class

**Purpose:** Classify every option in yt-dlp's *Usage and Options* so that `REQ-030`'s parity claim
is a checked statement rather than an intention, and so Phase 4.5 can be decomposed from a list
rather than from a blank page.
**Authority:** Canonical for the classification. `ARC-010` is canonical for the *scheme*, `SEC-003`
and `SEC-004` for the excluded families, and `build_options` for what the application owns.
**Owner:** Planner · `T-183`
**Status:** Written 2026-08-16. **Reclassified the same day by `SEC-004`**, which ruled the fifteen
options this audit refused to classify — all forbidden, so the `unruled` class is now empty and the
refusal list is 79 rather than 64.
**yt-dlp version:** **2026.07.04**, the exact pin in `pyproject.toml`. An audit of an unnamed
version cannot be re-run when upstream moves, so the version is part of the claim and
`tests/unit/test_option_audit.py` fails if the installed one stops matching.
**Rows:** **250** — every option yt-dlp documents, each appearing exactly once. Counted from the
installed option parser, not from the README and not estimated.

---

## How this was derived, and how to re-run it

Three of the four classes are **derived from something that can disagree with them**, which is what
keeps this document from being a list somebody wrote from memory:

| Input | Read from | What it decides |
|---|---|---|
| The option inventory | `yt_dlp.options.create_parser()` — the parser, not the README | Which options exist, their strings, their `dest` |
| The application-owned keys | `build_options`, exercised over every branch | Which keys the application actually sets |
| The excluded families | `SEC-003`, `SEC-004` | Which options are forbidden |

`tests/unit/test_option_audit.py` re-derives all three and fails when this file disagrees with any
of them. **It is the audit's only defence against the thing this project keeps finding** — a
statement written once, left standing, and read later as though it were still checked.

### The 42 suppressed options, which are not inert

yt-dlp's parser carries **292** options; **42** have their help suppressed and do not appear in
*Usage and Options*. `T-183`'s criterion is about the documented surface, so those 42 are not
classified here — **but they still parse, and six of them reach a key this audit refuses.** That is
Finding 4, and it changes how the refusal list has to be built. The test asserts the 250/42 split,
so a suppressed option that becomes documented upstream turns into a failure rather than a silent
gap.

---

## The classes

`ARC-010` names four. Applying them to a real inventory split one of them into three, because
*application-owned* turned out to be three different reasons that behave differently:

| Class | Rows | What it means |
|---|---|---|
| `typed` | 65 | Gets a control, an owner task and a phase position. 21 already have one |
| `hatch` | 106 | Reachable through `REQ-031` only. Every row carries a reason |
| `app:sets` | 19 | **`build_options` sets this key.** Derived, and drift-checked in both directions |
| `app:plumbing` | 36 | It *is* the command line rather than a capability — `REQ-030`'s own words |
| `app:contained` | 1 | It redirects where files land, and `T-034` owns that |
| `excluded` | 23 | Forbidden — 8 by `SEC-003`, **15 by `SEC-004`** |
| `unruled` | **0** | The class still exists, and is empty |

*(**The `unruled` class held 15 rows until 2026-08-16** — options that reach code execution, a
runtime-fetched component, TLS validation or a credential, and which no decision covered. `SEC-004`
ruled all fifteen **forbidden**, so they moved to `excluded`. The class is kept rather than deleted:
the next yt-dlp version can produce another one, and a class that has to be re-invented under
deadline is a class that gets skipped. Counts here are **recounted from the tables below**, not
adjusted by hand — and a test asserts they agree.)*

**The refusal list is `app:sets` + `app:contained` + `app:plumbing` + `excluded` — 79 rows**, and it
is the list `T-184` enforces. `typed` is not refused: where a typed field and the hatch name the same
user-owned key, `ARC-010`'s precedence rule applies and the typed field wins, because it is the one
with a visible control.

### Why `app:sets` is not the same list as *what the application owns*

`build_options` can emit **24 distinct keys**. Only **19 of them are reachable from the command
line at all** — `logger`, `progress_hooks`, `postprocessor_hooks`, `postprocessors` and `no_color`
are library parameters with no option string, so they can never be typed into the hatch and never
need refusing. Deriving the refusal list from the emitted keys alone would therefore have produced
five entries that refuse nothing.

The invariant the test actually enforces is the useful one, and it holds with no exceptions:

> **No key `build_options` sets is reachable through the hatch.** Every documented option whose
> `dest` is a key `build_options` emits is classified `app:sets` or `typed` — never `hatch`,
> `app:plumbing`, `excluded` or `unruled`.

---

## Findings

Seven things the audit found that were not visible before it. **Three of them are records
disagreeing with the code or with themselves** — Findings 1, 3 and 5 — which is this project's
recurring class, and none of the seven was reachable from a green suite.

### Finding 1 — `ARC-010`'s application-owned list and the derived one each catch what the other misses

`ARC-010` §4 names the application-owned keys as *"`outtmpl`, `format`, `progress_hooks`, `logger`,
`quiet`, `paths` and the simulation flags"*. **`build_options` never sets `paths`.** The output
directory reaches yt-dlp already joined into `output_template` by `worker.py`, so a derivation from
the code alone would have left `-P/--paths` unrefused — and `-P` is exactly the option that
redirects where files land, which is the boundary `T-034` exists to hold.

The reverse is also true: the derived list contains `noplaylist`, `extract_flat`, `overwrites`,
`consoletitle`, `no_warnings`, `noprogress`, `cookiefile` and `ffmpeg_location`, **none of which
`ARC-010` names.**

*This is what `T-183`'s criterion means by "derived from `build_options` rather than written from
memory" — and the derivation alone would still have been wrong.* `-P/--paths` gets its own class,
`app:contained`, so the reason it is refused is recorded where it is refused.

### Finding 2 — fifteen options reach code execution, a new network destination, or a secret, and no decision covers any of them

`SEC-003` ruled six families. It did not see these, and each has the shape of something it forbade:

| Options | Shape | Nearest ruling |
|---|---|---|
| `--plugin-dirs`, `--no-plugin-dirs`, `--use-postprocessor` | Loads arbitrary Python from a path the user names | `--exec`, forbidden |
| `--downloader`, `--downloader-args` | Executes an external binary with arguments the user names | `--exec`, forbidden |
| `--postprocessor-args` | Arbitrary arguments into the ffmpeg subprocess | `--exec`, forbidden |
| `--js-runtimes`, `--no-js-runtimes` | Names an external interpreter to execute | `--exec`, forbidden |
| `--remote-components`, `--no-remote-components` | Fetches code at runtime from a remote host | `NFR-007`'s outbound-traffic promise |
| `--no-check-certificates`, `--prefer-insecure` | Disables TLS validation | nothing |
| `-2/--twofactor`, `--ap-username`, `--ap-password` | A credential inside the persisted request | `-u`/`-p`, forbidden |

**These were filed unclassified rather than forced into a class**, per `T-183`'s fifth criterion —
and **that is what got them ruled**. `SEC-004`, 2026-08-16, forbids all fifteen on one rule: *an
option that runs code, fetches code, weakens transport security, or carries a secret is refused
where it is typed, with the reason.* `T-184` is unblocked, and the refusal list is 79 rather than
64.

**`--downloader` is the one that cost something**, and the decision says so: `aria2c` is materially
faster on fragmented downloads and is more constrained than `--exec`, since yt-dlp accepts a fixed
set of downloader names as well as a path. It is refused anyway, with a **named lifting
condition** — a user asks for it, and the permitted form is an allowlist of those names with no
path form and `--downloader-args` still refused. That is `SEC-003`'s own pattern for
`--download-archive` and `DAT-005` §1's for *Clear all*: a refusal that names what would change it
is not a wall.

*(**This section is left in the past tense rather than deleted.** The fifteen are what the audit's
fifth criterion was for, and an audit that quietly showed 23 excluded rows would not show that
fifteen of them were invisible until somebody read the parser.)*

### Finding 3 — `SEC-003` permits two options that its own rationale forbids

`SEC-003` permits *"`--netrc`, `--netrc-cmd`, `--netrc-location` and the client-certificate
options"*, on the reasoning that *"a `--netrc` flag asks for nothing: the secret lives in the user's
own file, which this application neither reads nor writes."*

**That reasoning does not reach two of the options it permits:**

- **`--netrc-cmd` is not a file.** yt-dlp's own help reads *"Command to execute to get the
  credentials for an extractor"* — it executes a command. That is the property `--exec` was
  forbidden for, in the same table, four rows down.
- **`--client-certificate-password` is a secret**, not a path to one. It is the shape
  `_require_credential_free_proxy` makes unrepresentable, and the shape `-u`/`-p` were forbidden for.

Both are classified `hatch` here **because that is what the accepted decision says**, and this
document does not overrule a decision. A **proposed** amendment is in `T-256`; nobody has ruled on
it.

### Finding 4 — a refusal list keyed on option strings is routed around by six deprecated aliases

**This is the finding that changes how `T-184` is built.** `SEC-003` names the forbidden options as
strings, and `ARC-010` names the application-owned ones as strings. yt-dlp's parser maps several
strings onto one `dest`, and **six of the suppressed 42 share a `dest` with something this audit
refuses**:

| Suppressed option | `dest` | What it reaches |
|---|---|---|
| `--geo-bypass` | `geo_bypass` | **`--xff`, forbidden by `SEC-003`** |
| `--no-geo-bypass` | `geo_bypass` | the same |
| `--geo-bypass-country` | `geo_bypass` | the same |
| `--geo-bypass-ip-block` | `geo_bypass` | the same |
| `--all-formats` | `format` | `format`, which `build_options` sets |
| `--no-colors` `--no-colours` | `color` | `color`, which `no_color` overrides |

A refusal list that names `--xff` and stops **permits `--geo-bypass`, which sets the identical
parameter.** `REQ-EXCL-002` would be enforced against one spelling out of five.

**So the refusal list keys on `dest`, not on the option string** — and the message the user reads
still names the string they typed, because refusal is stated where it was typed.

**A further 36 suppressed options have a `dest` no documented option has**, so keying on `dest`
does not reach them either. Two are the forbidden family outright — `--exec-before-download` and
`--no-exec-before-download`, dest `exec_before_dl_cmd`, which is *why* `SEC-003` named it — and the
rest are the printing family (`-e/--get-title`, `-g/--get-url`, `--print-json` and six siblings),
`--load-pages`, `--test`, `--user-agent`, `--referer` and `--allow-unplayable-formats`. **`T-184`
must decide the whole parser, not the documented part of it**, and that is an acceptance criterion
on it now.

*(This section first claimed `--exec-before-download` does not exist in 2026.07.04. It does — it is
suppressed, which is why it was absent from the documented inventory this audit was reading. The
claim was checked against the parser before it stood, and checking it is what turned a wrong
parenthetical into the finding above.)*

### Finding 5 — `SEC-003` says its refusal list gains five entries and then lists seven

Its consequences read: *"`T-184`'s refusal list gains five entries: `-u`, `-p`, `--video-password`,
`--impersonate`, `--xff`, `--exec` and `--exec-before-download`."* **That is seven strings.** The
list is right and the count is wrong — the same shape as `T-212`'s row count, which said forty-one
from an estimate and was forty-seven when counted. Correcting it is a records fix in an Accepted
decision, so it is proposed in `T-256` rather than made here.

### Finding 6 — `--write-thumbnail` is a capability the application refuses, and it shares a key with one it sets

`build_options` sets `writethumbnail` when `embed_thumbnail` is on, and deliberately does **not**
keep the picture: `already_have_thumbnail` is left false so yt-dlp deletes it after embedding,
because `REQ-010` asks to embed a thumbnail and not to write one beside the media.

But *writing the thumbnail beside the media* is a capability reachable from the command line, so
under `REQ-030` it has to be reachable here. `--write-thumbnail`, `--no-write-thumbnail` and
`--write-all-thumbnails` all set the same key the application already sets, which makes this the
one place where a typed control has to **share** a key rather than own it. `T-249` owns the
tri-state, and it is the reason `--write-all-thumbnails` is `typed` rather than `hatch`: left in the
hatch it would have been the only documented route to a key `build_options` sets.

### Finding 7 — four hatch options interact with `T-046`'s reservation, and nothing tests that

`--continue`, `--no-continue`, `--part`, `--no-part` and `--post-overwrites` all change how yt-dlp
treats a file already at the target path. The download session claims that path with
`O_CREAT | O_EXCL` and leaves a zero-byte reservation, and `build_options` sets `overwrites` to
match. **The interaction is unmeasured.** It is recorded as an acceptance criterion on `T-184`
rather than guessed at here.

---

## The decomposition

**65 typed rows: 21 already have a field, 44 do not.** Nothing is unassigned and nothing is in two
tasks — counted, and the test asserts the partition.

| Task | Rows | What it adds |
|---|---|---|
| — | 21 | Already built: the format, audio, container, subtitle-language, embedding, proxy, rate-limit, retry and browser-cookie fields |
| `T-247` | 7 | Video selection: which items, how big, how old |
| `T-248` | 7 | Filename shaping and the modification time |
| `T-249` | 7 | The sidecar writers: description, info JSON and thumbnail files |
| `T-250` | 4 | Format depth: sorting, checking and the merge container |
| `T-251` | 4 | Subtitle depth: automatic captions, format and conversion |
| `T-252` | 7 | Download tuning and the whole retry policy |
| `T-253` | 4 | Network reachability: address family and politeness delays |
| `T-254` | 3 | SponsorBlock, opt-in per preset |
| `T-255` | 1 | Per-extractor arguments |
| ~~`T-256`~~ | — | **Done — `SEC-004`, 2026-08-16.** All fifteen forbidden; `T-184` unblocked |

**`T-256` was first and is done; `T-184` is next.** The hatch could not be built before the
refusal list was known, and it was not known while fifteen options that reach code execution had no
ruling. `SEC-004` closed that on 2026-08-16. Every typed-field task is independent of the rest and
of the hatch.

---

## The tables

Every documented option in yt-dlp 2026.07.04, by the group *Usage and Options* puts it in. The
`Option` column carries every string the parser accepts for that option, so a row covers its
aliases and its `--no-` counterpart wherever they share one entry.

### General Options — 33

| Option | Class | Reason |
|---|---|---|
| `--abort-on-error` `--no-ignore-errors` | `hatch` | Counterpart of --ignore-errors |
| `--alias` | `app:plumbing` | REQ-030 names --alias as the command line itself |
| `--color` | `app:plumbing` | Console formatting; the worker has no console |
| `--compat-options` | `hatch` | youtube-dl compatibility; expert-only |
| `--config-locations` | `app:plumbing` | Config files are refused as an input route |
| `--default-search` | `hatch` | The add dialog takes URLs, not search terms |
| `--extractor-descriptions` | `app:plumbing` | A listing command, not a download option |
| `--flat-playlist` | `app:sets` | build_options sets extract_flat for the probe (T-137) |
| `-h` `--help` | `app:plumbing` | The command line's own help |
| `--ignore-config` `--no-config` | `app:plumbing` | T-184 refuses config files as a second invisible source |
| `-i` `--ignore-errors` | `hatch` | The queue owns per-job failure; T-110 owns per-entry |
| `--js-runtimes` | `excluded` | SEC-004: forbidden — Names an external interpreter to execute |
| `--list-extractors` | `app:plumbing` | A listing command, not a download option |
| `--live-from-start` | `typed` | Download tuning; T-183 names it thin |
| `--mark-watched` | `hatch` | Needs site auth this application refuses to hold |
| `--no-abort-on-error` | `hatch` | Counterpart of --ignore-errors |
| `--no-config-locations` | `app:plumbing` | Config files are refused as an input route |
| `--no-flat-playlist` | `app:sets` | Counterpart; same key |
| `--no-js-runtimes` | `excluded` | SEC-004: forbidden — Counterpart of --js-runtimes |
| `--no-live-from-start` | `typed` | Counterpart of --live-from-start |
| `--no-mark-watched` | `hatch` | Counterpart of --mark-watched |
| `--no-plugin-dirs` | `excluded` | SEC-004: forbidden — Counterpart of --plugin-dirs |
| `--no-remote-components` | `excluded` | SEC-004: forbidden — Counterpart of --remote-components |
| `--no-update` | `app:plumbing` | Counterpart of --update |
| `--no-wait-for-video` | `hatch` | Counterpart of --wait-for-video |
| `--plugin-dirs` | `excluded` | SEC-004: forbidden — Loads arbitrary Python from a directory - the --exec shape |
| `-t` `--preset-alias` | `app:plumbing` | core/presets.py owns presets |
| `--remote-components` | `excluded` | SEC-004: forbidden — Fetches code at runtime: a new destination under NFR-007 |
| `-U` `--update` | `app:plumbing` | OPS-002 pins yt-dlp exactly; the application owns which one runs |
| `--update-to` | `app:plumbing` | Counterpart of --update |
| `--use-extractors` `--ies` | `hatch` | Expert extractor routing; nobody has asked |
| `--version` | `app:plumbing` | About screen reports the pinned version (OPS-002) |
| `--wait-for-video` | `hatch` | Scheduled streams; the queue has no waiting state for it |

### Network Options — 8

| Option | Class | Reason |
|---|---|---|
| `--enable-file-urls` | `hatch` | Reads the user's own filesystem; no exclusion names it |
| `-4` `--force-ipv4` | `typed` | Common troubleshooting toggle |
| `-6` `--force-ipv6` | `typed` | Common troubleshooting toggle |
| `--impersonate` | `excluded` | SEC-003: forbidden |
| `--list-impersonate-targets` | `app:plumbing` | A listing command |
| `--proxy` | `typed` | REQ-023; DownloadRequest.proxy exists |
| `--socket-timeout` | `typed` | Network tuning, alongside the retry policy |
| `--source-address` | `hatch` | Binding a local address is expert-only |

### Geo-restriction — 2

| Option | Class | Reason |
|---|---|---|
| `--geo-verification-proxy` | `hatch` | SEC-003 permits it; expert-only |
| `--xff` | `excluded` | SEC-003: forbidden (REQ-EXCL-002) |

### Video Selection — 21

| Option | Class | Reason |
|---|---|---|
| `--age-limit` | `hatch` | Nobody has asked |
| `--break-match-filters` | `hatch` | Counterpart family of --match-filters |
| `--break-on-existing` | `hatch` | Goes with --download-archive |
| `--break-per-input` | `hatch` | Alters the break options above |
| `--date` | `typed` | T-183 names it thin |
| `--dateafter` | `typed` | T-183 names it thin |
| `--datebefore` | `typed` | T-183 names it thin |
| `--download-archive` | `hatch` | SEC-003: permitted as a user-named file only, never defaulted |
| `--match-filters` | `hatch` | Its own expression language; REQ-009's argument applies |
| `--max-downloads` | `typed` | T-183 names it thin |
| `--max-filesize` | `typed` | T-183 names it thin |
| `--min-filesize` | `typed` | T-183 names it thin |
| `--no-break-match-filters` | `hatch` | Counterpart of --break-match-filters |
| `--no-break-on-existing` | `hatch` | Counterpart of --break-on-existing |
| `--no-break-per-input` | `hatch` | Counterpart of --break-per-input |
| `--no-download-archive` | `hatch` | Counterpart of --download-archive |
| `--no-match-filters` | `hatch` | Counterpart of --match-filters |
| `--no-playlist` | `app:sets` | build_options sets noplaylist; the app models playlists itself |
| `-I` `--playlist-items` | `typed` | T-183 names it thin; playlist selection |
| `--skip-playlist-after-errors` | `hatch` | The queue owns failure policy |
| `--yes-playlist` | `app:sets` | Counterpart; same key |

### Download Options — 23

| Option | Class | Reason |
|---|---|---|
| `--abort-on-unavailable-fragments` `--no-skip-unavailable-fragments` | `hatch` | Counterpart of --skip-unavailable-fragments |
| `--buffer-size` | `hatch` | Expert tuning |
| `-N` `--concurrent-fragments` | `typed` | T-183 names it thin (-N) |
| `--download-sections` | `typed` | T-183 names it thin |
| `--downloader` `--external-downloader` | `excluded` | SEC-004: forbidden — Executes an external binary the user names - the --exec shape |
| `--downloader-args` `--external-downloader-args` | `excluded` | SEC-004: forbidden — Arguments into that subprocess; same family |
| `--file-access-retries` | `hatch` | Expert tuning |
| `--fragment-retries` | `typed` | The adapter defers it here by name (T-196 comment) |
| `--hls-use-mpegts` | `hatch` | Expert container choice |
| `--http-chunk-size` | `hatch` | Expert tuning |
| `--keep-fragments` | `hatch` | Debugging aid |
| `--lazy-playlist` | `hatch` | Conflicts with the projected-entry model (T-137) |
| `-r` `--limit-rate` `--rate-limit` | `typed` | DownloadRequest.rate_limit_bytes exists |
| `--no-hls-use-mpegts` | `hatch` | Counterpart of --hls-use-mpegts |
| `--no-keep-fragments` | `hatch` | Counterpart of --keep-fragments |
| `--no-lazy-playlist` | `hatch` | Counterpart of --lazy-playlist |
| `--no-resize-buffer` | `hatch` | Counterpart of --resize-buffer |
| `--playlist-random` | `hatch` | The queue owns ordering |
| `--resize-buffer` | `hatch` | Expert tuning |
| `-R` `--retries` | `typed` | DownloadRequest.retries exists (T-196) |
| `--retry-sleep` | `hatch` | Expert tuning |
| `--skip-unavailable-fragments` `--no-abort-on-unavailable-fragments` | `hatch` | Expert tuning |
| `--throttled-rate` | `hatch` | Expert tuning |

### Filesystem Options — 37

| Option | Class | Reason |
|---|---|---|
| `-a` `--batch-file` | `app:plumbing` | REQ-030 names batch files as the command line |
| `--cache-dir` | `hatch` | yt-dlp's own cache; nobody has asked |
| `--clean-info-json` `--clean-infojson` | `hatch` | Detail of --write-info-json |
| `-c` `--continue` | `hatch` | Interacts with T-046's reservation; T-184 must test that |
| `--cookies` | `app:sets` | build_options sets cookiefile from settings (REQ-026, T-197) |
| `--cookies-from-browser` | `typed` | DownloadRequest.cookies_from_browser exists (T-197) |
| `--force-overwrites` `--yes-overwrites` | `app:sets` | Counterpart; same key |
| `--load-info-json` | `app:plumbing` | A second input route that bypasses the probe |
| `--mtime` | `typed` | T-183 names it thin |
| `--no-batch-file` | `app:plumbing` | Counterpart of --batch-file |
| `--no-cache-dir` | `hatch` | Counterpart of --cache-dir |
| `--no-clean-info-json` `--no-clean-infojson` | `hatch` | Counterpart |
| `--no-continue` | `hatch` | Counterpart of --continue; same interaction |
| `--no-cookies` | `app:sets` | Counterpart; same key |
| `--no-cookies-from-browser` | `typed` | Counterpart; same field |
| `--no-force-overwrites` | `app:sets` | Counterpart; same key |
| `--no-mtime` | `typed` | Counterpart of --mtime |
| `-w` `--no-overwrites` | `app:sets` | build_options sets overwrites; T-046's reservation owns it |
| `--no-part` | `hatch` | Counterpart of --part; same interaction |
| `--no-restrict-filenames` | `typed` | Counterpart of --restrict-filenames |
| `--no-windows-filenames` | `typed` | Counterpart of --windows-filenames |
| `--no-write-comments` `--no-get-comments` | `hatch` | Counterpart of --write-comments |
| `--no-write-description` | `typed` | Counterpart of --write-description |
| `--no-write-info-json` | `typed` | Counterpart of --write-info-json |
| `--no-write-playlist-metafiles` | `hatch` | Counterpart |
| `-o` `--output` | `app:sets` | build_options sets outtmpl; worker.py runs it through T-034 |
| `--output-na-placeholder` | `hatch` | Cosmetic template detail |
| `--part` | `hatch` | Interacts with T-046's reservation; T-184 must test that |
| `-P` `--paths` | `app:contained` | Redirects where files land; T-034 owns that (ARC-010 §3) |
| `--restrict-filenames` | `typed` | T-183 names it thin |
| `--rm-cache-dir` | `app:plumbing` | A maintenance command, not a download option |
| `--trim-filenames` `--trim-file-names` | `typed` | T-183 names it thin |
| `--windows-filenames` | `typed` | T-183 names it thin |
| `--write-comments` `--get-comments` | `hatch` | Expensive extraction nobody has asked for |
| `--write-description` | `typed` | T-183 names the metadata writers thin |
| `--write-info-json` | `typed` | T-183 names the metadata writers thin |
| `--write-playlist-metafiles` | `hatch` | Goes with --write-info-json for playlists |

### Thumbnail Options — 4

| Option | Class | Reason |
|---|---|---|
| `--list-thumbnails` | `app:plumbing` | A listing command that implies --simulate |
| `--no-write-thumbnail` | `typed` | Counterpart of --write-thumbnail |
| `--write-all-thumbnails` | `typed` | Shares writethumbnail with the app; the control is tri-state |
| `--write-thumbnail` | `typed` | A capability the app refuses today (REQ-010); collides with writethumbnail |

### Internet Shortcut Options — 4

| Option | Class | Reason |
|---|---|---|
| `--write-desktop-link` | `hatch` | Nobody has asked |
| `--write-link` | `hatch` | Nobody has asked |
| `--write-url-link` | `hatch` | Nobody has asked |
| `--write-webloc-link` | `hatch` | Nobody has asked; macOS is not a target |

### Verbosity and Simulation Options — 23

| Option | Class | Reason |
|---|---|---|
| `--console-title` | `app:sets` | build_options sets consoletitle |
| `-j` `--dump-json` | `app:plumbing` | REQ-030 names JSON dumping as the command line |
| `--dump-pages` | `app:plumbing` | Debug output to a console there is not |
| `-J` `--dump-single-json` | `app:plumbing` | REQ-030 names JSON dumping as the command line |
| `--force-write-archive` `--force-write-download-archive` `--force-download-archive` | `hatch` | Goes with --download-archive |
| `--ignore-no-formats-error` | `hatch` | Metadata-only extraction; expert-only |
| `--newline` | `app:plumbing` | REQ-030 names progress formatting as the command line |
| `--no-ignore-no-formats-error` | `hatch` | Counterpart |
| `--no-progress` | `app:sets` | build_options sets noprogress; progress reaches the GUI by hook |
| `--no-quiet` | `app:sets` | Counterpart; same key |
| `--no-simulate` | `app:plumbing` | Counterpart of --simulate |
| `--no-warnings` | `app:sets` | build_options sets no_warnings |
| `-O` `--print` | `app:plumbing` | REQ-030 names printing as the command line |
| `--print-to-file` | `app:plumbing` | Printing, and it writes a file outside T-034 |
| `--print-traffic` | `app:plumbing` | Debug output, and it prints request bodies (DAT-003) |
| `--progress` | `app:sets` | Counterpart; same key |
| `--progress-delta` | `app:plumbing` | Progress formatting for a console there is not |
| `--progress-template` | `app:plumbing` | Progress formatting for a console there is not |
| `-q` `--quiet` | `app:sets` | build_options sets quiet |
| `-s` `--simulate` | `app:plumbing` | REQ-030 names simulation as the command line |
| `--skip-download` `--no-download` | `app:sets` | build_options sets skip_download for the probe |
| `-v` `--verbose` | `app:plumbing` | REQ-019 owns diagnostics; YtdlpLog deliberately omits verbose |
| `--write-pages` | `app:plumbing` | Writes to the working directory, outside T-034 |

### Workarounds — 10

| Option | Class | Reason |
|---|---|---|
| `--add-headers` | `hatch` | Can carry a secret; T-184 must redact the value (DAT-004) |
| `--bidi-workaround` | `app:plumbing` | A terminal workaround; there is no terminal |
| `--encoding` | `hatch` | Experimental, per yt-dlp's own help |
| `--legacy-server-connect` | `hatch` | Narrow TLS workaround |
| `--max-sleep-interval` | `typed` | Pairs with --sleep-interval |
| `--no-check-certificates` | `excluded` | SEC-004: forbidden — Disables TLS validation; no decision covers it |
| `--prefer-insecure` `--prefer-unsecure` | `excluded` | SEC-004: forbidden — Retrieves over plaintext; no decision covers it |
| `--sleep-interval` `--min-sleep-interval` | `typed` | Politeness delay is commonly reached for |
| `--sleep-requests` | `hatch` | Expert politeness tuning |
| `--sleep-subtitles` | `hatch` | Expert politeness tuning |

### Video Format Options — 16

| Option | Class | Reason |
|---|---|---|
| `--audio-multistreams` | `hatch` | Expert merging |
| `--check-all-formats` | `hatch` | Costly variant of --check-formats |
| `--check-formats` | `typed` | T-183 names format depth thin |
| `-f` `--format` | `app:sets` | build_options sets format from REQ-009's selector field |
| `-S` `--format-sort` | `typed` | T-183 names format depth thin |
| `--format-sort-force` `--S-force` | `hatch` | Detail of --format-sort |
| `--format-sort-reset` | `hatch` | Detail of --format-sort |
| `-F` `--list-formats` | `app:plumbing` | The format table is the application's own surface (T-107) |
| `--merge-output-format` | `typed` | T-183 names format depth thin |
| `--no-audio-multistreams` | `hatch` | Counterpart |
| `--no-check-formats` | `typed` | Counterpart of --check-formats |
| `--no-format-sort-force` | `hatch` | Counterpart |
| `--no-prefer-free-formats` | `hatch` | Counterpart |
| `--no-video-multistreams` | `hatch` | Counterpart |
| `--prefer-free-formats` | `hatch` | Preference the format table already exposes by hand |
| `--video-multistreams` | `hatch` | Expert merging |

### Subtitle Options — 7

| Option | Class | Reason |
|---|---|---|
| `--list-subs` | `app:plumbing` | A listing command that implies --simulate |
| `--no-write-auto-subs` `--no-write-automatic-subs` | `typed` | Counterpart of --write-auto-subs |
| `--no-write-subs` `--no-write-srt` | `typed` | Counterpart; same field |
| `--sub-format` | `typed` | T-183 names subtitle depth thin |
| `--sub-langs` `--srt-langs` | `typed` | DownloadRequest.subtitle_languages exists |
| `--write-auto-subs` `--write-automatic-subs` | `typed` | T-183 names subtitle depth thin |
| `--write-subs` `--write-srt` | `typed` | Driven by DownloadRequest.subtitle_languages |

### Authentication Options — 14

| Option | Class | Reason |
|---|---|---|
| `--ap-list-mso` | `app:plumbing` | A listing command |
| `--ap-mso` | `hatch` | An operator identifier, not a secret |
| `--ap-password` | `excluded` | SEC-004: forbidden — A secret in the request; SEC-003 did not name it |
| `--ap-username` | `excluded` | SEC-004: forbidden — A credential; SEC-003's -u rationale applies but did not name it |
| `--client-certificate` | `hatch` | SEC-003: permitted - a path to the user's own file |
| `--client-certificate-key` | `hatch` | SEC-003: permitted - a path to the user's own file |
| `--client-certificate-password` | `hatch` | SEC-003 permits it, and it is a secret - see Finding 3 |
| `-n` `--netrc` | `hatch` | SEC-003: permitted - the secret stays in the user's own file |
| `--netrc-cmd` | `hatch` | SEC-003 permits it, and it executes a command - see Finding 3 |
| `--netrc-location` | `hatch` | SEC-003: permitted - a path to the user's own file |
| `-p` `--password` | `excluded` | SEC-003: forbidden (REQ-EXCL-003) |
| `-2` `--twofactor` | `excluded` | SEC-004: forbidden — A secret in the request; SEC-003 did not name it |
| `-u` `--username` | `excluded` | SEC-003: forbidden (REQ-EXCL-003) |
| `--video-password` | `excluded` | SEC-003: forbidden (REQ-EXCL-003) |

### Post-Processing Options — 37

| Option | Class | Reason |
|---|---|---|
| `--audio-format` | `typed` | DownloadRequest.audio_codec exists |
| `--audio-quality` | `typed` | DownloadRequest.audio_quality exists |
| `--concat-playlist` | `hatch` | Conflicts with one-row-per-entry (UX-005) |
| `--convert-subs` `--convert-sub` `--convert-subtitles` | `typed` | T-183 names subtitle depth thin |
| `--convert-thumbnails` | `hatch` | Nobody has asked |
| `--embed-chapters` `--add-chapters` | `typed` | DownloadRequest.embed_chapters exists |
| `--embed-info-json` | `hatch` | mkv attachment; nobody has asked |
| `--embed-metadata` `--add-metadata` | `typed` | DownloadRequest.embed_metadata exists |
| `--embed-subs` | `typed` | DownloadRequest.embed_subtitles exists |
| `--embed-thumbnail` | `typed` | DownloadRequest.embed_thumbnail exists |
| `--exec` | `excluded` | SEC-003: forbidden - containment cannot reach a shell command |
| `-x` `--extract-audio` | `typed` | DownloadRequest.media_kind exists |
| `--ffmpeg-location` | `app:sets` | OPS-001: the worker resolves ffmpeg and gates on it |
| `--fixup` | `hatch` | yt-dlp's default is correct; expert override |
| `--force-keyframes-at-cuts` | `hatch` | Detail of --download-sections |
| `-k` `--keep-video` | `hatch` | Intermediate files; nobody has asked |
| `--no-embed-chapters` `--no-add-chapters` | `typed` | Counterpart; same field |
| `--no-embed-info-json` | `hatch` | Counterpart of --embed-info-json |
| `--no-embed-metadata` `--no-add-metadata` | `typed` | Counterpart; same field |
| `--no-embed-subs` | `typed` | Counterpart; same field |
| `--no-embed-thumbnail` | `typed` | Counterpart; same field |
| `--no-exec` | `excluded` | Counterpart of --exec |
| `--no-force-keyframes-at-cuts` | `hatch` | Counterpart |
| `--no-keep-video` | `hatch` | Counterpart of --keep-video |
| `--no-post-overwrites` | `hatch` | Counterpart of --post-overwrites |
| `--no-remove-chapters` | `hatch` | Counterpart of --remove-chapters |
| `--no-split-chapters` `--no-split-tracks` | `hatch` | Counterpart of --split-chapters |
| `--parse-metadata` | `hatch` | Its own template language; REQ-009's argument applies |
| `--post-overwrites` | `hatch` | Interacts with T-046's reservation; T-184 must test that |
| `--postprocessor-args` `--ppa` | `excluded` | SEC-004: forbidden — Arbitrary arguments into the ffmpeg subprocess |
| `--recode-video` | `typed` | DownloadRequest.recode_container exists |
| `--remove-chapters` | `hatch` | Its own regex language; expert-only |
| `--remux-video` | `typed` | DownloadRequest.remux_container exists |
| `--replace-in-metadata` | `hatch` | Its own regex language; REQ-009's argument applies |
| `--split-chapters` `--split-tracks` | `hatch` | Writes several files; T-184 must contain them |
| `--use-postprocessor` | `excluded` | SEC-004: forbidden — Enables plugin post-processors - the --plugin-dirs shape |
| `--xattrs` `--xattr` | `hatch` | Nobody has asked; no Windows equivalent |

### SponsorBlock Options — 5

| Option | Class | Reason |
|---|---|---|
| `--no-sponsorblock` | `typed` | The off position of the SponsorBlock control |
| `--sponsorblock-api` | `excluded` | SEC-003: a configurable endpoint was declined |
| `--sponsorblock-chapter-title` | `hatch` | Cosmetic detail of --sponsorblock-mark |
| `--sponsorblock-mark` | `typed` | SEC-003: permitted, opt-in per preset (NFR-007 amended) |
| `--sponsorblock-remove` | `typed` | SEC-003: permitted, opt-in per preset |

### Extractor Options — 6

| Option | Class | Reason |
|---|---|---|
| `--allow-dynamic-mpd` `--no-ignore-dynamic-mpd` | `hatch` | yt-dlp's default is correct; expert override |
| `--extractor-args` | `typed` | T-183 names it thin; per-extractor arguments |
| `--extractor-retries` | `typed` | Part of the retry policy T-183 names thin |
| `--hls-split-discontinuity` | `hatch` | Expert HLS handling |
| `--ignore-dynamic-mpd` `--no-allow-dynamic-mpd` | `hatch` | Counterpart of --allow-dynamic-mpd |
| `--no-hls-split-discontinuity` | `hatch` | Counterpart |
