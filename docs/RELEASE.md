# Cutting a release

**Purpose:** Everything needed to publish a release of Tracks & Trails, and what to do when one
has to be withdrawn.
**Owner:** Implementer
**Maintainer:** Sean Kottman
**Status:** Active
**Last updated:** 2026-09-11 — created with Phase 5, per `DOC-002`.
**Related:** [`REL-003`](project/DECISIONS.md#rel-003--semver-and-the-first-release-is-010) the
version scheme · [`REL-004`](project/DECISIONS.md#rel-004--the-linux-artifact-ships-as-an-appimage)
the Linux format · [`REL-005`](project/DECISIONS.md#rel-005--the-first-windows-installer-ships-unsigned)
signing · [`REL-006`](project/DECISIONS.md#rel-006--a-clean-machine-is-a-disposable-vm-the-maintainer-owns)
clean-machine evidence · [TESTING §8](project/TESTING.md#8-release-gate) the gate ·
[`DAT-001`](project/DECISIONS.md#dat-001--sqlite-for-queue-and-history-toml-for-settings) migrations

---

## Before anything else: the gate

**[TESTING §8](project/TESTING.md#8-release-gate) is the list, and it is not repeated here.** A
copy would drift from the original, and the one that drifts is always the copy somebody is reading.
Fifteen items, on **both platforms**, before any tag or distributed build.

Three of them are not things a workflow can do for you, so plan them first:

| Gate item | What it needs |
|---|---|
| 6 — MVP acceptance criteria | `REQUIREMENTS.md` §11, verified by hand and recorded |
| 7 — clean-machine install | A disposable VM per `REL-006`; Windows Sandbox and a throwaway Ubuntu LTS |
| 15 — Windows manual verification | `TESTING` §9, on a real desktop, recorded in the review record |

## The version

`REL-003`: SemVer, `0.y.z` until the maintainer declares `1.0`.

1. `main` carries `X.Y.Z.devN` between releases.
2. The **release commit** sets `__version__ = "X.Y.Z"` in `src/tracks_and_trails/__init__.py`.
   That is the only place it is declared — `pyproject.toml` reads it through
   `[tool.hatch.version]`.
3. Tag that commit **`vX.Y.Z`**.
4. The **next** commit bumps to `X.Y.(Z+1).dev0`.

**Patch releases carry fixes only.** A yt-dlp baseline bump is at least a **minor** release, because
it changes behaviour on every site — and gate item 10a applies: the `yt-dlp canary` workflow must be
green at the version being bumped to.

**Check the tag against the tree before pushing it**, because a tag is the one thing here that
cannot be quietly corrected — it is what a user's download is named after:

```bash
python3 tools/version_tag_check.py --tag v0.1.0
```

It refuses a tag that disagrees with `__version__`, and it refuses a tag on a commit still carrying
`.devN` — a release that would report itself as a development build for as long as it exists.

## The release commit itself

Three files change only here, never in advance:

- **`CHANGELOG.md`** is *created in the release commit* (`DOC-002`). An empty changelog written
  ahead of time is the speculative document that decision forbids.
- **`SECURITY.md` §Supported versions** is filled at the first tag: the latest minor receives
  fixes, older ones do not. It currently says there are no released versions, which is true until
  this step.
- **`README.md`**'s capability table says *"you cannot install it from a release — there are no
  installers or packages yet."* That line is **true until the first release exists**; replace it
  with an install section pointing at the release page in the same commit, not before. **That
  section must carry the SmartScreen click-through verbatim** — *More info* → *Run anyway* — and
  the two system requirements above it. `T-317` asks for that wording in the README specifically,
  and this is the commit where a README section can exist without claiming something untrue.

**The README must make no yt-dlp parity claim.** `REQ-030`'s parity is deferred to Phase 4.5,
*after* the first release, so claiming it at release would be false. Check before tagging:

```bash
grep -rniE "parity|everything yt-dlp|all of yt-dlp" README.md
```

## Building and publishing

`T-324` owns the workflow that builds, gates and drafts on a `v*` tag. **Until it exists**, the
artifacts are built by hand from the same specs CI uses — `T-319` for Windows, `T-321` for the
Linux AppImage, `T-322` for the installer — and the gate is run as §8 describes.

**Draft, then publish — never publish directly.** The workflow drafts a release and stops; a human
publishes it after checking the artifacts attached are the ones the gate passed. Nothing in this
project publishes automatically, and `T-324`'s criteria say so.

### What the release page must state

Two system requirements, neither of which the artifacts can or should satisfy themselves
([`REL-007`](project/DECISIONS.md#rel-007--the-artifacts-use-the-system-certificate-store-and-bundle-none),
[`REL-004`](project/DECISIONS.md#rel-004--the-linux-artifact-ships-as-an-appimage)):

- **Linux: glibc 2.36 or newer** — Debian 12, Ubuntu 24.04 LTS and later. `packaging/build_appimage.sh`
  builds on Debian 12 deliberately, so this is the floor that buys. **Ubuntu 22.04 is glibc 2.35
  and out of reach.**
- **A working system certificate store** — `ca-certificates` on a Debian or Ubuntu machine. Every
  desktop distribution ships it; a container or a stripped image may not, and without it no HTTPS
  request can be verified. `REL-007` records why the artifact uses the system store rather than
  bundling its own: bundling one would make the application ignore a corporate or user-added CA.
- **Linux: ffmpeg from the distribution**, for merging and audio extraction (`OPS-001`). Bundled on
  Windows, not on Linux, and `REQ-024` finds it on `PATH`.

**These belong in the README's Install section too, and it does not have one yet.** `T-320`
deferred that while *"there are no installers or packages yet"* is still true — so the first
release commit that makes it false adds the section and these three lines with it. Until then this
is their only home, which is stated here so the next person does not have to rediscover them from
a build script's comments.

### The clean machine (§8 item 7)

Neither runner is clean any more — `OPS-010` gave that up for Windows and `OPS-012` for Linux,
each in writing — so this is taken per candidate, by hand, and kept:

```
tools/clean_machine_linux.sh dist/Tracks_and_Trails-<version>-x86_64.AppImage \
    > docs/project/evidence/linux-<version>.md
```

It supplies a disposable `ubuntu:24.04` — the oldest LTS the README claims, which is deliberately
*not* the Debian 12 the artifact is built on — runs a pre-install check that **fails the run** if
Python, a toolchain, Qt or ffmpeg is present, then every probe including `--download-probe`, and
finally holds a real launch offscreen for 20 seconds. `--version` is not a launch test; it returns
before a `QApplication` exists, which is how a build with no platform plugins passed everything
once.

Windows is the same evidence taken by hand in Windows Sandbox on `STARBASE`, against
`docs/project/evidence/TEMPLATE-windows.md`. That half covers §8 item 8's *cancel another*, which
no probe can: cancellation is a parent-side signal and a probe has no parent.

**Commit both files with the release commit.** They are evidence about one artifact, identified by
digest, taken on a machine that no longer exists.

### What a Windows user will see, and why

`REL-005`: the first installer **ships unsigned**. On a first install Windows SmartScreen shows

> **Windows protected your PC** — *Microsoft Defender SmartScreen prevented an unrecognised app
> from starting.*

The way through is **More info** → **Run anyway**. Say exactly that on the release page and in the
README install section, so support is a link rather than a conversation. Reputation never accrues
without a certificate, so the prompt does not go away with downloads; `REL-005` names a certificate
as the `1.0` condition.

The Linux AppImage is unsigned too, deliberately — AppImage signatures are optional and rarely
checked. `REL-005` records that as a choice rather than an oversight.

## Rolling back

Three different questions, and only two of them have answers.

**The project.** Delete or unpublish the release, and re-point *latest* at the previous one. The
tag can stay; a withdrawn release with its tag intact is a clearer history than a deleted tag that
somebody has already fetched.

**A user.** Reinstall the previous version from its release page, which is why old releases are not
deleted when a new one lands.

**Their data — not promised, and this is the important half.** `DAT-001`'s migrations are
**forward-only**. A database migrated by a newer version is not readable by an older one, and the
application **refuses** it rather than opening it and corrupting it silently: the older build
shows a message naming the file and exits 4, having written nothing. So a user who downgrades
across a schema change keeps their files and loses their queue and history.

*(Until 2026-09-12 this paragraph described a refusal the code did not perform — `migrate()` skips
every migration at or below the database's version, so a newer database matched nothing and
opened. `T320-R2` found it; `persistence/db.NewerSchemaError` is the refusal it described.)*

**Say this on the release page whenever a release contains a migration.** A rollback path that
quietly does not exist is worse than one the user was warned about, and this document states it
rather than implying a symmetry the data layer does not have.

## The release review

`T-328` runs this before anything is published, and `TESTING` §14 governs where the verdict is
recorded. *(Moved here on 2026-09-11 from the removed `docs/project/PROMPTS.md` — a release
prompt belongs with the release procedure.)*

```text
Act as the Release Manager for Tracks & Trails.

Release candidate: <version / tag / commit>

Work through the docs/project/TESTING.md §8 release gate item by item, on Linux AND Windows. Do not
mark an item passed without the actual evidence, and quote the evidence you used.

§8 items 9, 11, 12 and 13 are executable. Run the gate on each platform's own artifact and paste
its output rather than restating the items; it is the evidence for those four:

    python3 packaging/artifact_gates.py <the built artifact>

Two caveats it will not tell you. On Windows it checks Qt's libraries are present and cannot ask
the loader anything, which is a narrower guarantee than the Linux run. And item 13's *repository*
half is not covered by it at all — that stays manual.

Version consistency across sources is its own check, against the tag you are about to push:

    python3 tools/version_tag_check.py --tag <the tag>

What is left for you to read and judge: the CHANGELOG is current, the pinned yt-dlp baseline is
recorded (OPS-002), and every §8 item with no tool behind it. Say which platform each piece of
evidence came from; a gate answers for the artifact it was run against and no other.

Record the verdict and blockers in the canonical review record chosen under TESTING §14
and ensure REVIEWS.md indexes it. Continue an existing release review in its existing file.
Do not tag, commit, push, or publish unless explicitly instructed.
```
