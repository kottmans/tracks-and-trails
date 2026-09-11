"""Refuse a release tag that disagrees with the version the artifact will report (`T-320`).

`REL-003` fixes the scheme: SemVer, `0.y.z` until `1.0` is declared. `main` carries `X.Y.Z.devN`
between releases; a release commit sets `__version__ = "X.Y.Z"` and is tagged `vX.Y.Z`; the next
commit bumps to `X.Y.(Z+1).dev0`.

**Two ways that goes wrong, and both ship.** A tag whose number does not match the package, so
`--version` reports something the release page does not; and a tag placed on a commit still
carrying `.devN`, so the release reports itself as a development build forever. Neither is visible
in a diff, both are permanent once published, and a tag is the one thing in this project that
cannot be quietly corrected — it is what a user's installer is named after.

**The decision is in Python, not in the workflow.** `T240-R1` is the precedent, and
`tools/job_duration_report.py` is the other instance: logic written in a workflow step cannot be
tested where it is written. `check` is a pure function over two strings, so
`tests/unit/test_version_tag_check.py` can drive the cases a release only produces once.

    python3 tools/version_tag_check.py --tag v0.1.0
    python3 tools/version_tag_check.py --tag v0.1.0 --version 0.1.0

With no `--version` it reads `tracks_and_trails.__version__` from the checkout it is run in, which
is what `T-324`'s workflow wants: the tag comes from the ref, the version from the tree the ref
points at.
"""

from __future__ import annotations

import argparse
import re
import sys

#: A release tag. `v` then exactly three dot-separated numbers — no suffix, because a pre-release
#: or build-metadata tag is a thing this project has not decided and must not ship by accident.
RELEASE_TAG = re.compile(r"^v(?P<number>\d+\.\d+\.\d+)$")

#: The version a *released* package carries. `REL-003`'s `X.Y.Z`, and nothing else: `0.1.0.dev0`
#: deliberately fails this, which is the second of the two defects above.
RELEASE_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def check(tag: str, version: str) -> str | None:
    """The rule, as one function. `None` means the pair may be published.

    Returns the reason rather than raising, so the caller decides what a failure is worth — the
    CLI exits non-zero, and the test reads the sentence.
    """
    match = RELEASE_TAG.match(tag)
    if match is None:
        return (
            f"{tag!r} is not a release tag. REL-003 tags a release vX.Y.Z with three numbers and "
            f"no suffix; a pre-release spelling is not a decision this project has taken"
        )
    if not RELEASE_VERSION.match(version):
        return (
            f"the tree at {tag} reports __version__ = {version!r}, which is not a released "
            f"version. REL-003 keeps .devN on main and sets X.Y.Z in the release commit — tagging "
            f"this would publish a release that calls itself a development build"
        )
    expected = match.group("number")
    if version != expected:
        return (
            f"{tag} would publish a package reporting {version!r}. The tag and the version have "
            f"to be the same number, or --version tells a user something the release page does not"
        )
    return None


def installed_version() -> str:
    """`__version__` from the checkout this runs in."""
    sys.path.insert(0, "src")
    from tracks_and_trails import __version__

    return __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="the release tag, e.g. v0.1.0")
    parser.add_argument(
        "--version",
        help="the version to check it against; read from this checkout when omitted",
    )
    arguments = parser.parse_args(argv)

    version = arguments.version if arguments.version is not None else installed_version()
    problem = check(arguments.tag, version)
    if problem is not None:
        print(f"version-tag-check: {problem}", file=sys.stderr)
        return 1
    print(f"version-tag-check: {arguments.tag} matches __version__ {version}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through `main`
    raise SystemExit(main())
