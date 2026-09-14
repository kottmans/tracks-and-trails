"""Which release is newer, when to ask, and the record of the last answer (`T-338`)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tracks_and_trails.core import app_updates
from tracks_and_trails.core.app_updates import (
    CHECK_INTERVAL,
    check_is_due,
    is_newer,
    parse_version,
    read_last_check,
    record_check,
    release_page,
)
from tracks_and_trails.core.settings import settings_path


@pytest.mark.parametrize(
    ("earlier", "later"),
    [
        ("0.1.0", "0.1.1"),
        ("0.1.9", "0.2.0"),
        ("0.9.9", "1.0.0"),
        # The version this build carries today, against the release it becomes.
        ("0.1.0.dev0", "0.1.0"),
        # PEP 440's order within one version: development, then pre-releases, then the release.
        ("0.1.0.dev0", "0.1.0a1"),
        ("0.1.0a1", "0.1.0a2"),
        ("0.1.0a2", "0.1.0b1"),
        ("0.1.0b1", "0.1.0rc1"),
        ("0.1.0rc1", "0.1.0"),
        ("0.1.0rc1.dev1", "0.1.0rc1"),
        ("0.1.0", "0.1.1.dev0"),
        # Numbers, not strings: `10` is after `9`.
        ("0.9.0", "0.10.0"),
    ],
)
def test_versions_sort_the_way_releases_are_made(earlier: str, later: str) -> None:
    assert is_newer(later, earlier)
    assert not is_newer(earlier, later)


def test_a_tag_and_its_version_are_the_same_version() -> None:
    assert not is_newer("v0.1.0", "0.1.0")
    assert not is_newer("0.1.0", "v0.1.0")
    parsed = parse_version("v0.2.0")
    assert parsed is not None and parsed.text == "0.2.0"


@pytest.mark.parametrize(
    "text",
    ["", "latest", "1.0", "1.0.0.0", "v1.0.0-beta", "1.0.0/../x", "\uff11.0.0", "1.\u0660.0"],
)
def test_anything_that_is_not_a_version_is_never_newer(text: str) -> None:
    """A malformed answer must not put an update notice in front of anyone. The last two are
    digits from other scripts, which a bare `\\d` accepts."""
    assert parse_version(text) is None
    assert not is_newer(text, "0.1.0")


def test_the_page_is_built_from_the_version_alone() -> None:
    parsed = parse_version("v1.2.3")
    assert parsed is not None
    assert release_page(parsed) == (
        "https://github.com/kottmans/tracks-and-trails/releases/tag/v1.2.3"
    )


def test_a_check_is_due_once_a_day() -> None:
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    assert check_is_due(None, now)
    assert not check_is_due(now - CHECK_INTERVAL + timedelta(minutes=1), now)
    assert check_is_due(now - CHECK_INTERVAL, now)
    assert timedelta(days=1) == CHECK_INTERVAL


def test_a_record_from_the_future_does_not_silence_checks() -> None:
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    assert check_is_due(now + timedelta(days=300), now)


def test_the_record_round_trips(tmp_path: Path) -> None:
    record = tmp_path / "updates.toml"
    when = datetime(2026, 9, 13, 8, 30, tzinfo=UTC)
    record_check(when, record)
    assert read_last_check(record) == when
    assert not record.with_name("updates.toml.writing").exists()


@pytest.mark.parametrize(
    "content",
    [b"", b"not toml [", b'last_checked = "yesterday"', b"other = 1", b"\xff\xfe"],
)
def test_an_unreadable_record_reads_as_never_checked(tmp_path: Path, content: bytes) -> None:
    record = tmp_path / "updates.toml"
    record.write_bytes(content)
    assert read_last_check(record) is None
    assert read_last_check(tmp_path / "absent.toml") is None


def test_a_record_that_cannot_be_written_raises_nothing(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("in the way", encoding="utf-8")
    record_check(datetime.now(UTC), blocker / "updates.toml")


def test_the_record_lives_beside_the_settings_not_inside_them() -> None:
    assert app_updates.update_check_path() == settings_path().with_name("updates.toml")
