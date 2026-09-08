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

Use **GitHub's private vulnerability reporting** on this repository: *Security → Report a
vulnerability*. That opens a private advisory visible only to the maintainer.

Please do not open a public issue for a security problem.

There is no bounty, and no guaranteed response time — this is one person's project. What you
will get is an honest answer about whether it is a real finding and whether it will be fixed.

## What this application handles that matters

Tracks & Trails is a local desktop application. It has no server, no accounts, no network
listener, and no telemetry of any kind. The sensitive material it touches is all the user's own:

| Material | Where it can appear | Rule |
|---|---|---|
| Browser cookies / cookie files | Settings, passed to yt-dlp | Never persisted to the database; never written to the log |
| Proxy credentials | Settings, `DownloadRequest` | Stripped before a request is serialized; refused at entry |
| Output paths and filenames | Queue, log, database | Redacted in the log where they can carry a home directory |
| URLs the user queues | Database, log | Stored verbatim, by explicit decision — this is the one exception, and it is recorded |

The governing requirements are `REQ-026` and `NFR-007`; the structural database boundary is
`DAT-003`. All three are in [docs/project/REQUIREMENTS.md](docs/project/REQUIREMENTS.md) and
[docs/project/DECISIONS.md](docs/project/DECISIONS.md).

### Logging

The application log is **redacted at every level**, including `--log-level=DEBUG`, and `DEBUG`
does not enable yt-dlp's own verbose output. Redaction is not a filter applied on the way out; it
is enforced at the sink, so a new caller cannot bypass it by accident.

This boundary was wrong three times before it was right — a scheme-less proxy, a Unicode host, a
cookie path that did not look like one — and each failure is recorded with the probe that found
it in [docs/project/REVIEWS.md](docs/project/REVIEWS.md). The regression gates are
`tests/unit/test_log_redaction.py` and `tests/unit/test_redaction_gate.py`.

### Secrets in the repository

No credential, token, key, or personal data belongs in version control. `.gitignore` refuses the
obvious carriers — `cookies.txt`, `*.cookies`, `*.sqlite3`, `.env`, downloaded media — and
`AGENTS.md` §7 states the rule for anything it does not anticipate.

Machine addresses and account names are not committed either: `tools/windows/run-on-starbase.sh`
takes its host from `STARBASE_HOST` and refuses to run without it, rather than carrying a default.

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
