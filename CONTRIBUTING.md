# Contributing to Tracks & Trails

**Purpose:** How to report bugs, ask for features, and what happens to a pull request.
**Owner:** Documentation Maintainer · **Maintainer:** Sean Kottman
**Last updated:** 2026-09-13
**Update when:** The project's stance on outside contributions, or its reporting routes, change.

## The short version

Tracks & Trails is one person's project, and it is **not accepting code contributions right now**.
A pull request from outside the repository will be closed without review. **Bug reports and
feature requests are welcome**, and they are the most useful thing you can send.

This is not a judgement of anyone's code. There are two concrete reasons:

- **Pull requests get no CI.** Every runner this project uses is a self-hosted machine, so no
  workflow runs on a pull request. Running a stranger's code there would be arbitrary code
  execution on a personal machine. [SECURITY.md](SECURITY.md#ci-trust-boundary) explains this.
- **Every change goes through a task and an independent review**, under the rules in
  [AGENTS.md](AGENTS.md). A pull request from outside the repository has no way into that
  process.

If that changes, this file will say so first. Contributions would then be accepted under the
[MIT License](LICENSE).

## Reporting a bug

Open a [bug report](https://github.com/kottmans/tracks-and-trails/issues/new/choose). The form
asks for what is needed to reproduce the problem.

**If a site stopped working, update yt-dlp from inside the app first.** Most site breakage is
fixed in yt-dlp itself, and the app can update its copy without a new release. If the same URL
also fails with yt-dlp on the command line, the bug belongs in the
[yt-dlp issue tracker](https://github.com/yt-dlp/yt-dlp/issues).

**Read a log before you paste it.** The log is redacted, not sanitized. Your output paths appear
in full. A token in a URL's path, or text quoted inside a yt-dlp error message, can also survive.
[SECURITY.md](SECURITY.md#what-this-application-handles-that-matters) lists exactly what is and is
not removed. `tracks-and-trails --help` prints where the log is. Never attach a cookie file or a
copy of the application's database.

## Requesting a feature

Open a [feature request](https://github.com/kottmans/tracks-and-trails/issues/new/choose). Say
what you are trying to do, not only which button you want. There may already be a way to do it,
or a better shape for the feature.

Some requests will be closed, whatever their merit, because they are outside the project's scope.
Tracks & Trails does **not** circumvent access controls: no DRM stripping, no paywall or
geo-restriction bypass, no authentication bypass, no rate-limit evasion, and no bulk scraping
(decision `SEC-001`).

## Security problems

**Do not open a public issue.** Follow [SECURITY.md](SECURITY.md#reporting-a-vulnerability).

## Conduct

Everyone taking part in this project's issues and discussions is expected to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Reading or building the code

- [README](README.md#installing) covers installing from source.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) covers the development setup, the tests, and
  day-to-day commands.
- [AGENTS.md](AGENTS.md) is the set of rules every change in this repository is made under.
