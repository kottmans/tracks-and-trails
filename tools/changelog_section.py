"""One version's section of `CHANGELOG.md`, for a release body (`T-324`).

`T-324`'s draft release uses the changelog section for the version being tagged as its body. That
is a small piece of text-handling with three ways to be quietly wrong — the wrong section, an
empty section, or *no* section reported as an empty one — and a draft release with an empty body
is worse than a workflow that stopped, because a human then publishes it.

    python3 tools/changelog_section.py --version 0.1.0

A function with a CLI rather than shell inside a workflow step, which is `T240-R1`'s rule: a
decision buried in `yq` and `sed` is a decision nobody reviews. Exits 1 and says which headings it
*did* find when the one asked for is absent.

**There is no `CHANGELOG.md` yet.** `docs/RELEASE.md` makes creating it a release-commit step, so
this tool's first real run is the first release. It is written now because the workflow needs it,
and its absence is reported as the missing file it is rather than as an empty body.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
CHANGELOG = REPOSITORY / "CHANGELOG.md"

#: A second-level heading, whatever it says. Which of them name a version is `_version_of`'s
#: question, and keeping the two separate is what lets a body contain its own `###` and `##`
#: subheadings without the scan mistaking one for the next release.
_HEADING = re.compile(r"^##[ \t]+(?P<rest>.*)$")


def _version_of(heading: str) -> str | None:
    """The version a heading names, or `None` when it names something else.

    **Tolerant about decoration, strict about the number.** `## [0.1.0] - 2026-09-12`,
    `## 0.1.0` and `## [v0.1.0] (2026-09-12)` all name the same release; `## [Unreleased]` and a
    bare date name none.

    Written as a small parse rather than one regex because the regex version had two defects the
    tests found immediately: it matched up to the `]` and left `- 2026-09-12` as the first line of
    the release body, and it required a separator before a pre-release suffix so `0.1.0rc1` was
    not a version at all.
    """
    candidate = heading.strip().removeprefix("[")
    if candidate[:1] in {"v", "V"}:
        candidate = candidate[1:]
    match = re.match(r"[0-9][\w.+-]*", candidate)
    if match is None:
        return None
    version = match.group(0)
    # `\d+\.\d+\.\d+` anchored, so a date heading and a two-part number are not versions.
    return version if re.fullmatch(r"\d+\.\d+\.\d+[\w.+-]*", version) else None


def sections(text: str) -> dict[str, str]:
    """Every version heading in `text`, mapped to the body beneath it.

    **A body runs from the end of its heading *line* to the next version heading**, so the date on
    the heading stays out of it and a `### Added` inside it stays in. The order of headings is what
    decides where each body ends, which is what makes a leading `## [Unreleased]` harmless rather
    than something to special-case.

    The topmost heading wins a duplicate version, which is a changelog mistake either way; taking
    the first at least makes the choice predictable.
    """
    lines = text.splitlines(keepends=True)
    marks: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match is None:
            continue
        version = _version_of(match.group("rest"))
        if version is not None:
            marks.append((index, version))

    found: dict[str, str] = {}
    for position, (index, version) in enumerate(marks):
        end = marks[position + 1][0] if position + 1 < len(marks) else len(lines)
        found.setdefault(version, "".join(lines[index + 1 : end]).strip("\n"))
    return found


def section_for(version: str, text: str) -> tuple[str | None, str | None]:
    """The body for `version`, or `(None, complaint)`.

    Two failures, told apart on purpose: a heading that is not there at all, and one that is there
    with nothing under it. The second is the one a release body would carry silently.
    """
    found = sections(text)
    if version not in found:
        listed = ", ".join(sorted(found)) or "none"
        return None, (
            f"CHANGELOG.md has no section for {version}. Headings found: {listed}. "
            f"REL-003 fixes the version in __init__.py; the changelog has to name the same one."
        )
    body = found[version].strip()
    if not body:
        return None, (
            f"CHANGELOG.md's section for {version} is empty. A draft release with an empty body "
            f"is worse than a workflow that stopped, because somebody then publishes it."
        )
    return body, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print one version's changelog section.")
    parser.add_argument("--version", required=True, help="the version, without a leading v")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    arguments = parser.parse_args(argv)

    if not arguments.changelog.is_file():
        print(
            f"changelog-section: {arguments.changelog} does not exist. docs/RELEASE.md makes "
            f"creating it a release-commit step.",
            file=sys.stderr,
        )
        return 1

    body, complaint = section_for(
        arguments.version.lstrip("v"), arguments.changelog.read_text(encoding="utf-8")
    )
    if complaint is not None:
        print(f"changelog-section: {complaint}", file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through `main`
    raise SystemExit(main())
