# SECURITY.md — Tracks & Trails

**Purpose:** Security expectations, the trust boundaries this project actually enforces, and how
to report a vulnerability.
**Authority:** Canonical for security policy and reporting. **Not** canonical for the mechanisms
themselves — those live in the code, the workflows, and the tests named below.
**Owner:** Maintainer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-09-08
**Update when:** A trust boundary, secret-handling rule, supported version, or reporting route
changes.

---

## Supported versions

**There are no released versions.** Phase 5 — packaging and the first tagged release — is not
built. The only supported state is the tip of `main`, run from source. When releases begin, this
section will name which of them receive fixes.

## Reporting a vulnerability

**Open an issue on this repository.** It is private, so an issue on it is already visible only to
its collaborators — who are also the only people who can read the code, and therefore the only
people positioned to find a vulnerability in it.

**There is deliberately no email address here, and GitHub's private vulnerability reporting is not
available.** That feature is a public-repository one; this repository is private. Both change at
the same moment: when Phase 5 makes the repository public and ships a release, private reporting
gets enabled and this section is rewritten to point at it, because an issue will no longer be
private and a reporter will no longer be a collaborator.

There is no bounty, and no guaranteed response time — this is one person's project. What you
will get is an honest answer about whether it is a real finding and whether it will be fixed.

## What this application handles that matters

Tracks & Trails is a local desktop application. It has no server, no accounts, no network
listener, and no telemetry of any kind. The sensitive material it touches is all the user's own:

| Material | Database | Log |
|---|---|---|
| Cookie paths and browser profiles | **Refused at construction.** `cookies_from_browser` must parse as a browser *specification*, so a path cannot enter a stored request. A cookie **file** is configured in `settings.toml` and never reaches the model at all | Two different mechanisms, and which one applies depends on **who supplied the path**. A path *this application* supplied — the `settings.toml` cookie file — is registered by exact value with `remember_a_path` as settings load, before the value can be logged, so `~/session.txt` is redacted however ordinary its name. A path this application never supplied — one yt-dlp quoted back inside a diagnostic — has only the shape rules: `cookies.txt`, `cookies.sqlite` and the documented patterns are recognized, and an ordinary name such as `session.txt` is **not** and survives |
| Proxy credentials | **Refused at construction**, including scheme-less and network-path forms | Userinfo stripped from a URL or a bare `user:pass@host` |
| URLs the user queues | **Stored verbatim** — query string *and* userinfo included, by explicit decision | Query string, userinfo and fragment stripped |
| Output paths and filenames | Stored as given | **Not redacted.** An output path under a home directory appears in full |
| Diagnostics (`error_message`) | **Stored as given.** The repository does not filter this column | Redacted like any other line |

**The rows that are not guarantees are deliberate, and one of them is a recorded decision.**

`DAT-003` narrows `REQ-026` to values *this application supplies*, and two separate mechanisms
hold that line. **In the database, a cookie path is unrepresentable:** `cookies_from_browser`
carries a browser specification and refuses anything that is not one, and the configured cookie
*file* lives in `settings.toml`, which the database never stores. **In the log, a configured
cookie path is redacted by its literal value, not by its shape:** it is registered as settings
load and before any refusal naming it is composed, because guessing which filenames look like
cookie jars is the enumeration failure `DAT-003` records twice.

What is left outside both is a path this application never supplied. `error_message` is stored
verbatim because `NFR-006` requires the extractor's original message intact — and **yt-dlp does
sometimes name a browser cookie database inside one**, for instance when a profile cannot be read.
That path is the accepted residue, not an oversight; two attempts to scrub such prose both failed,
and one corrupted a user's output directory into a relative path.

An output path is likewise stored and logged as given: it is what the user chose, and it is the
most useful line in a bug report.

**So the practical rule differs by artifact, and the database is the more sensitive of the two.**

**Treat a copy of the database as capable of containing credentials.** `jobs.url` holds the
address the user pasted, exactly as pasted — the serialized `request` beside it holds the same
string a second time — so userinfo or a credential-bearing query parameter in a queued URL is
stored. Nothing rejects it: `DownloadRequest` refuses a credential in the **proxy** field, not in
the URL being downloaded. `error_message` is likewise stored as the extractor wrote it, including
any path or URL that diagnostic quotes.

**Treat a copy of the log as containing local file paths.** Every URL loses its userinfo, query
and fragment there, so the queued-URL credential does not reach it; what survives is paths —
an output path in full, and a cookie path that this application did not configure and whose name
the pattern set does not recognize.

Neither artifact stores cookie *contents*. Read `DAT-003` before adding a new write to
`error_message`.

The governing requirements are `REQ-026` and `NFR-007`; the structural database boundary is
`DAT-003`. All three are in [docs/project/REQUIREMENTS.md](docs/project/REQUIREMENTS.md) and
[docs/project/DECISIONS.md](docs/project/DECISIONS.md).

### Logging

The application log is **redacted at every level**, including `--log-level=DEBUG`, and `DEBUG`
does not enable yt-dlp's own verbose output. Redaction is enforced at the sink —
`RedactingFormatter.format` wraps every record — so a new caller cannot bypass it by accident.

**What it catches is a pattern set, not a category.** It recognizes URLs with an authority, bare
`user:pass@host` userinfo, cookie headers, cookie stores named as such, and literals registered
through `remember_a_secret()`. It follows that **a secret it has no pattern for reaches the log**:
the known gap is a cookie file whose name does not look like one. Treat the log as redacted against
the listed forms, not as sanitized in general.

This boundary was wrong three times before it was right — a scheme-less proxy, a Unicode host, a
cookie path that did not look like one — and each failure is recorded with the probe that found
it in [docs/project/REVIEWS.md](docs/project/REVIEWS.md). The regression gates are
`tests/unit/test_log_redaction.py` and `tests/unit/test_redaction_gate.py`.

### Secrets in the repository

No credential, token, key, or personal data belongs in version control. `.gitignore` refuses the
obvious carriers — `cookies.txt`, `*.cookies`, `*.sqlite3`, `.env`, downloaded media — and
`AGENTS.md` §7 states the rule for anything it does not anticipate.

`tools/windows/run-on-starbase.sh` no longer carries an account and a LAN address as its default;
it takes `STARBASE_HOST` and refuses to run without it. **Two RFC1918 addresses do remain**, in
review entries in [docs/project/REVIEWS.md](docs/project/REVIEWS.md) that record an SSH attempt
timing out. They are a statement about a past run on a private network, they are not routable, and
the historical record is not rewritten to remove them.

## CI trust boundary

**Every runner this project uses is self-hosted** — the maintainer's own Linux machines and one
Windows desktop — whenever `LINUX_RUNNER`, `WINDOWS_RUNNER`, or `STARBASE_AVAILABLE` is set.
That makes the workflow trigger set a security control rather than a convenience:

- **No workflow carries `pull_request` or `pull_request_target`.** GitHub runs a fork's pull
  request with the fork's own code, and `pytest` executes whatever Python that fork ships. On a
  public repository with self-hosted runners, that is arbitrary code execution on a personal
  machine, on a home network.
- **The rule is enforced by a test, not by prose.** `tests/unit/test_workflow_triggers.py` parses
  every workflow's `on:` block with the same YAML parser GitHub's syntax is defined against, and
  fails if either trigger appears. An earlier text-scanning version was bypassed twice by valid
  YAML — an aliased anchor, and a `#` inside a quoted string — and both bypasses were in the
  accepting direction. That history is `T-262` and `T-264`.
- **Every workflow declares `permissions: contents: read`** at the top level.
- Nothing is given up by the absence of `pull_request`. This is a one-checkout project that
  commits straight to `main`; restoring the trigger requires an explicit decision, not a habit.

If this repository ever accepts outside contributions, that trigger set is the thing to revisit
first, and the answer is not to switch it back on — it is to move public CI to hosted runners.

## Dependencies

**yt-dlp is pinned exactly**, not floated (`OPS-002`). A floating dependency means the code ships
against a version nobody tested. Users update their own copy in-app instead, and
`.github/workflows/ytdlp-canary.yml` runs the suite weekly against a newer yt-dlp so upstream
drift is discovered here rather than by a user.

`ruff` and `mypy` are pinned exactly for the same reason, and
`tests/unit/test_toolchain_versions.py` fails when the running environment does not match what
`pyproject.toml` declares.

## What this application deliberately does not do

Tracks & Trails does **not** circumvent access controls: no DRM stripping, no paywall or
geo-restriction bypass, no authentication bypass, no rate-limit evasion, no bulk scraping. Cookie
support exists so a user can reach content they already have an account for. This is `SEC-001`,
and it is a scope boundary rather than a limitation waiting to be lifted.

## Incident response

There is no deployed service to take offline. If a defect in a released build turns out to expose
user material, the response is: record it in [docs/project/REVIEWS.md](docs/project/REVIEWS.md)
with its reproduction, fix it under a task with a regression gate, and say so plainly in the
release notes for the version that fixes it. A Critical finding is not eligible to be closed as
accepted risk by anyone but the maintainer, and that decision is recorded with its reasoning.
