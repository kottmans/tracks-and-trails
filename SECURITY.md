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

**Both the route and this section depend on the repository's visibility, not on a release** — so
check which of these describes what you are looking at. Written this way deliberately: visibility can change on
any day, and a section that named only one route would be wrong from that moment until someone
noticed.

**If this repository is public:** use *Security → Report a vulnerability*. That is GitHub's private
vulnerability reporting, and it opens an advisory only the maintainer can see.

**If it is private:** open an issue. Only collaborators can see the repository at all, so only they
can see the issue.

**If it is public and there is no *Report a vulnerability* button**, private reporting has not been
turned on — it is a setting rather than a default, and enabling it is a recorded prerequisite of
publication (`T-299`). Please still do not put the details in a public issue. Open one saying only
that you have a security report and no private route is available; that is the most useful thing
you can do with what you have.

**There is deliberately no email address here.**

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

**What is left outside both mechanisms is anything this application did not supply.**
`error_message` is stored verbatim because `NFR-006` requires the extractor's original message
intact — and **yt-dlp does sometimes name a browser cookie database inside one**, for instance
when a profile cannot be read. That is the accepted residue, not an oversight; two attempts to
scrub such prose both failed, and one corrupted a user's output directory into a relative path.
`DAT-003`'s 2026-07-30 amendment scopes the boundary to values this application supplies, and
makes **no claim at all** about what a third party's diagnostic contains.

An output path is likewise stored and logged as given: it is what the user chose, and it is the
most useful line in a bug report.

### What is actually verified

**Each row is a mechanism with a check behind it. No row says what *cannot* appear** — three
corrections of this section were each undone by a categorical sentence, so there are none here.

| Value | Database | Log |
|---|---|---|
| A cookie path **this application supplies** | Unrepresentable: `cookies_from_browser` takes a browser specification, and the cookie *file* is a `settings.toml` value the database never stores | Registered by literal value and replaced, however ordinary its name |
| A proxy carrying a credential | Refused at construction | Registered by literal value; a bare `user:pass@host` is also matched by shape |
| A URL the user queues | Stored whole, and a second time inside the serialized `request` | Userinfo, query and fragment removed — **scheme, host and path remain** |
| A diagnostic (`error_message`) | Stored exactly as the extractor wrote it, with no filter | Passed through the same pattern set as any other line |
| An output path | Stored as given | Not redacted |

**Redaction recognizes forms, and a credential can arrive in another one.** The forms are a URL's
userinfo, query and fragment; a bare `user:pass@host`; cookie-store filename patterns; and the
exact literals this application registered. A token carried in a URL's **path** is not one of
them and survives into the log. Neither is arbitrary text inside a diagnostic — an
`Authorization: Bearer …` line reaches the log as written.

**The database is the wider of the two, because `error_message` has no filter at all.** Whatever
an extractor writes is stored: a cookie *value* it quotes back as readily as a cookie path.

**So, before sharing a copy of either:** treat the database as potentially holding credentials and
arbitrary third-party text, and the log as a redacted — not sanitized — version of the same
material. Read `DAT-003` before adding a new write to `error_message`.

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
[docs/project/reviews/T-064.md](docs/project/reviews/T-064.md), recording an SSH attempt that timed
out. They are a statement about a past run on a private network, they are not routable, and the
historical record is not rewritten to remove them. *(They were in `REVIEWS.md` until `T-300` split
that file into per-task records; this pointer followed them rather than the file.)*

**What "no personal data" does and does not cover.** It is a rule about what this project writes
into files. It is not a claim about Git metadata: commit author names and addresses are part of
published history, and dated evidence in `docs/project/` quotes real home-directory and Windows
account paths from the machines the runs happened on.

## CI trust boundary

**Every runner this project uses is self-hosted** — the maintainer's own Linux machines and one
Windows desktop — whenever `LINUX_RUNNER`, `WINDOWS_RUNNER`, or `STARBASE_AVAILABLE` is set.
That makes the workflow trigger set a security control rather than a convenience:

- **No workflow carries `pull_request` or `pull_request_target`.** GitHub runs a fork's pull
  request with the fork's own code, and `pytest` executes whatever Python that fork ships. With
  self-hosted runners that is arbitrary code execution on a personal machine, on a home network.
  **This repository is public as of 2026-09-08, so that is a live condition and not a
  hypothetical** — the trigger set is the control that closes it.
- **The rule is enforced by a test, not by prose.** `tests/unit/test_workflow_triggers.py` parses
  every workflow's `on:` block with the same YAML parser GitHub's syntax is defined against, and
  fails if either trigger appears. An earlier text-scanning version was bypassed twice by valid
  YAML — an aliased anchor, and a `#` inside a quoted string — and both bypasses were in the
  accepting direction. That history is `T-262` and `T-264`.
- **Every workflow declares `permissions: contents: read`** at the top level.
- Nothing is given up by the absence of `pull_request`. This is a one-checkout project that
  commits straight to `main`; restoring the trigger requires an explicit decision, not a habit.

**A second layer sits under it**: fork pull-request workflows require approval for
`all_external_contributors`, so even a restored trigger would not run a stranger's code unattended.

**If this repository starts accepting outside contributions, the trigger set is the thing to
revisit first, and the answer is not to switch it back on — it is to move public CI to hosted
runners.**

**What that would cost is speed, not money, and `OPS-012` is explicit that this was never a cost
decision.** It measured the alternatives on 2026-08-05: hosted `ubuntu-latest` ran the suite in
**7m36s** against **4m29s** on the maintainer's desktop, and free was a side effect of choosing the
faster machine rather than the reason. Windows already costs nothing, because `OPS-010` routes it
to `STARBASE`. So publication changes the metering — hosted runners are free for public
repositories — without changing the argument the decision actually rests on.

**The Windows desktop job cannot move at all.** It exists to exercise a real desktop session, which
no hosted image provides; moving it means dropping that coverage, not relocating it. A move is
therefore partial by construction, and it is the maintainer's call rather than one made here.

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
