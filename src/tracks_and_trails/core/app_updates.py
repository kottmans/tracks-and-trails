"""Whether a newer Tracks & Trails has been released, and when to ask (`T-338`, `NFR-007`).

**Notify only.** The maintainer's ruling on 2026-09-13: the application says a newer release exists
and links to its page; it never downloads or runs anything. An unsigned installer (`REL-005`) would
raise SmartScreen on every self-applied update, and the AppImage updates another way entirely.

**What is sent.** One `GET` for the repository's latest *published* release, which GitHub answers
without drafts or pre-releases. No identifier, no version number, no settings: the comparison is
made here, against the answer. `NFR-007` names the destination.

**The page is built here, never taken from the answer.** A release body carries URLs; opening one
would let whatever wrote the response choose where the user's browser goes. The version is parsed,
refused unless it is a version, and put into the one page address this module knows.

This module is pure apart from the small record of when the last check ran, which is `core/`'s
kind of file handling (`settings.toml` lives beside it) and needs no Qt.
"""

import re
import tomllib
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from tracks_and_trails.core.settings import settings_path

#: The repository's releases. Constants rather than settings for `ytdlp_update.PYPI_INDEX`'s
#: reason: an address a user can set is an address a user can be told to set.
RELEASES_PAGE: Final = "https://github.com/kottmans/tracks-and-trails/releases"
LATEST_RELEASE_API: Final = (
    "https://api.github.com/repos/kottmans/tracks-and-trails/releases/latest"
)

#: How often an automatic check may run. A day: releases are weeks apart, and a user who launches
#: the application ten times in an afternoon should cost GitHub one request, not ten.
CHECK_INTERVAL: Final = timedelta(days=1)

#: Beside `settings.toml`, and **not in it**: this is a fact about the last run rather than a
#: preference, and writing it into the user's settings would rewrite that file once a day.
UPDATE_CHECK_FILENAME: Final = "updates.toml"
_LAST_CHECKED_KEY: Final = "last_checked"

#: `REL-003`'s versions and the tags that carry them: `0.1.0`, `v0.1.0`, `1.2.3rc1`,
#: `0.1.0.dev0`. PEP 440's subset this project uses, and nothing looser.
#: **ASCII digits only**: `\d` alone also matches fullwidth and other scripts' digits, which would
#: turn a tag no release uses into a version and a page address.
_VERSION: Final = re.compile(
    r"v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:(a|b|rc)([0-9]+))?(?:\.dev([0-9]+))?", re.ASCII
)
_PRE_RANK: Final = {"a": 0, "b": 1, "rc": 2}


@dataclass(frozen=True)
class Version:
    """A parsed version: its text without a `v`, and the key it sorts by."""

    text: str
    key: tuple[int, ...]


def parse_version(text: str) -> Version | None:
    """`text` as a version, or `None` when it is not one. **Never raises.**"""
    match = _VERSION.fullmatch(text.strip())
    if match is None:
        return None
    major, minor, patch, pre, pre_number, dev = match.groups()
    if pre is not None:
        pre_rank, pre_value = _PRE_RANK[pre], int(pre_number)
    elif dev is not None:
        # PEP 440: `0.1.0.dev0` comes before every pre-release of `0.1.0`, not after them.
        pre_rank, pre_value = -1, 0
    else:
        pre_rank, pre_value = 3, 0
    # A development build of a version comes before that version itself.
    dev_rank, dev_value = (0, int(dev)) if dev is not None else (1, 0)
    key = (int(major), int(minor), int(patch), pre_rank, pre_value, dev_rank, dev_value)
    return Version(match.group(0).removeprefix("v"), key)


def is_newer(candidate: str, current: str) -> bool:
    """Whether `candidate` is a later version than `current`. `False` if either is not a version.

    Unparseable is *not newer*, deliberately: a malformed answer must not put an update notice in
    front of the user.
    """
    new, running = parse_version(candidate), parse_version(current)
    return new is not None and running is not None and new.key > running.key


def release_page(version: Version) -> str:
    """The one page this application sends a browser to for `version`."""
    return f"{RELEASES_PAGE}/tag/v{version.text}"


def check_is_due(last_checked: datetime | None, now: datetime) -> bool:
    """Whether an automatic check may run now.

    **A clock that went backwards makes a check due** rather than postponing it until the clock
    catches up: a record dated next year would otherwise silence checks for a year.
    """
    if last_checked is None or last_checked > now:
        return True
    return now - last_checked >= CHECK_INTERVAL


def update_check_path() -> Path:
    """`updates.toml`, beside `settings.toml` in `user_config_dir/tracksandtrails`."""
    return settings_path().with_name(UPDATE_CHECK_FILENAME)


def read_last_check(path: Path | None = None) -> datetime | None:
    """When the last successful check ran, or `None`. **Never raises.**

    Anything unreadable reads as *never checked*, which costs one request and nothing else.
    """
    target = update_check_path() if path is None else path
    try:
        with target.open("rb") as stream:
            document = tomllib.load(stream)
        stamp = datetime.fromisoformat(str(document[_LAST_CHECKED_KEY]))
    except OSError, tomllib.TOMLDecodeError, UnicodeDecodeError, KeyError, ValueError:
        return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


def record_check(when: datetime, path: Path | None = None) -> None:
    """Remember that a check ran at `when`. **Never raises**: a record that cannot be written
    means the next launch checks again, which is harmless."""
    target = update_check_path() if path is None else path
    scratch = target.with_name(f"{target.name}.writing")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_text(
            "# When Tracks & Trails last checked for a newer version. Safe to delete.\n"
            f'{_LAST_CHECKED_KEY} = "{when.astimezone(UTC).isoformat()}"\n',
            encoding="utf-8",
        )
        scratch.replace(target)
    except OSError:
        with suppress(OSError):
            scratch.unlink(missing_ok=True)
