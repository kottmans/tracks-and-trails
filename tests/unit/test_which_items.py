"""*Which items*: the seven options `T-247` types, from the model to yt-dlp's own dictionary.

`ARC-010`, amended 2026-10-11, rules where each acts. `-I` and *at most N* are a preset's alone and
choose a playlist's entries when it is expanded; the add dialog's tests hold that half. The size and
date filters are shared with the request and act per job, on the download only, and a preset's
`today-2weeks` is frozen to the day it names when the job is queued. This file holds that half, and
the *"same intent, same dictionary"* check: a typed request against yt-dlp's own `parse_options` of
the options it stands for, key by key.
"""

from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast

import pytest
from yt_dlp import parse_options
from yt_dlp.utils import DateRange

from tracks_and_trails.core import presets
from tracks_and_trails.core.models import EXPANSION_FIELDS, DownloadRequest, Preset
from tracks_and_trails.core.selection import empty_window, in_units, resolved_date, size_words
from tracks_and_trails.core.settings import Settings, add_preset, load, save
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.ytdlp_adapter import build_options
from tracks_and_trails.persistence.repositories import _deserialize_request, _serialize_request
from tracks_and_trails.ui.format_text import derived_preset_name, format_name
from tracks_and_trails.ui.playlist_selection import PlaylistSelection

URL: Final = "https://example.invalid/clip"
TEMPLATE: Final = "%(title)s.%(ext)s"
#: Never written to: nothing here downloads.
DIRECTORY: Final = "downloads"

#: The keys the four filters set, and what yt-dlp means when each is absent.
FILTER_KEYS: Final = {"min_filesize": None, "max_filesize": None, "daterange": DateRange()}


def a_request(**fields_: Any) -> DownloadRequest:
    return DownloadRequest(
        url=URL,
        output_directory=DIRECTORY,
        format_selector="best",
        output_template=TEMPLATE,
        **fields_,
    )


def a_preset(**fields_: Any) -> Preset:
    return replace(presets.BEST_VIDEO, name="Filtered", built_in=False, **fields_)


# --- the model ------------------------------------------------------------------------------------


def test_only_the_entry_rule_is_a_preset_s_alone() -> None:
    """Every other preset field is a request field under the same name; these two act before
    there is a request, and naming them is what keeps the exception from spreading."""
    preset_only = {f.name for f in fields(Preset)} - {f.name for f in fields(DownloadRequest)}

    assert preset_only == EXPANSION_FIELDS | {"name", "built_in"}


@pytest.mark.parametrize(
    ("field", "value", "said"),
    [
        ("playlist_items", "1,,2", "playlist_items"),
        ("playlist_items", "", "playlist_items"),
        ("playlist_items", "1:3:0", "cannot be zero"),
        ("max_downloads", 0, "at least 1"),
        ("max_downloads", True, "an int"),
        ("min_filesize", 0, "at least 1"),
        ("max_filesize", -5, "negative"),
        ("uploaded_after", "tomorrow", "uploaded_after"),
        ("uploaded_before", "20250229", "does not exist"),
    ],
)
def test_a_preset_refuses_what_yt_dlp_would(field: str, value: object, said: str) -> None:
    """Refused when the preset is built, long before a job learns it when it runs."""
    with pytest.raises((TypeError, ValueError), match=said):
        a_preset(**{field: value})


def test_a_preset_refuses_a_smallest_file_larger_than_the_largest() -> None:
    with pytest.raises(ValueError, match="no file could pass both"):
        a_preset(min_filesize=2048, max_filesize=1024)


def test_a_preset_keeps_a_relative_date_as_typed() -> None:
    preset = a_preset(uploaded_after="today-2weeks", uploaded_before="yesterday")

    assert (preset.uploaded_after, preset.uploaded_before) == ("today-2weeks", "yesterday")


@pytest.mark.parametrize(
    "value",
    [
        "today",
        "today-2weeks",
        "2026101",
        "20261301",
        "\uff12\uff10\uff12\uff16\uff10\uff11\uff10\uff11",
    ],
)
def test_a_request_carries_only_a_frozen_day(value: str) -> None:
    """A relative form in a request would move the window under a queued or retried job."""
    with pytest.raises(ValueError, match="YYYYMMDD of a real day"):
        a_request(uploaded_after=value)


def test_a_request_carries_a_window_whose_days_have_crossed() -> None:
    """Not refused: a preset mixing a fixed and a relative date can produce one as days pass, and
    refusing it would break every caller of `to_request`. The worker answers it instead."""
    request = a_request(uploaded_after="20261101", uploaded_before="20261001")

    assert empty_window(request.uploaded_after, request.uploaded_before)


# --- from a preset to a request -------------------------------------------------------------------


def test_a_preset_s_dates_are_frozen_into_the_request() -> None:
    """`ARC-010`, amended 2026-10-11: the job keeps the day the preset named when it was queued."""
    preset = a_preset(
        min_filesize=1024, max_filesize=2048, uploaded_after="today-2weeks", uploaded_before="today"
    )

    request = presets.to_request(preset, url=URL, output_directory=DIRECTORY)

    assert request.uploaded_after == resolved_date("today-2weeks")
    assert request.uploaded_before == resolved_date("today")
    assert (request.min_filesize, request.max_filesize) == (1024, 2048)


def test_a_queued_job_s_preset_holds_its_frozen_days_and_gives_the_same_request_back() -> None:
    """Editing a queued job opens on the window it has, not the relative form it came from."""
    request = presets.to_request(
        a_preset(uploaded_after="today-1week", max_filesize=4096),
        url=URL,
        output_directory=DIRECTORY,
    )

    implied = presets.preset_of(request, name="That job")
    again = presets.to_request(
        implied,
        url=URL,
        output_directory=DIRECTORY,
        default_output_template=request.output_template,
    )

    assert implied.uploaded_after == request.uploaded_after
    assert again == request


# --- reaching yt-dlp ------------------------------------------------------------------------------


def test_the_filters_reach_the_download_and_never_the_probe() -> None:
    """The probe has to describe the item whatever it is, or the item being chosen disappears."""
    request = a_request(
        min_filesize=1024,
        max_filesize=2048,
        uploaded_after="20260101",
        uploaded_before="20261231",
    )

    download = build_options(request, TEMPLATE)
    probe = build_options(request, TEMPLATE, probe_only=True)

    assert download["min_filesize"] == 1024
    assert download["max_filesize"] == 2048
    assert download["daterange"] == DateRange("20260101", "20261231")
    assert not set(FILTER_KEYS) & set(probe), "a filter reached the probe"


def test_no_filter_sets_no_key() -> None:
    """Absent is yt-dlp's own default, and an explicit `None` would be a key nobody asked for."""
    assert not set(FILTER_KEYS) & set(build_options(a_request(), TEMPLATE))


#: The same intent twice: preset fields as the editor holds them, and the options a user would
#: type for them. Sizes are yt-dlp's 1024s; `--date X` is both ends at `X`.
SAME_INTENT: Final = [
    pytest.param({}, [], id="nothing"),
    pytest.param({"min_filesize": 50 * 1024}, ["--min-filesize", "50k"], id="min"),
    pytest.param({"max_filesize": 2 * 1024**3}, ["--max-filesize", "2G"], id="max"),
    pytest.param(
        {"min_filesize": 1024**2, "max_filesize": 3 * 1024**2},
        ["--min-filesize", "1M", "--max-filesize", "3M"],
        id="both sizes",
    ),
    pytest.param({"uploaded_after": "20260101"}, ["--dateafter", "20260101"], id="after"),
    pytest.param({"uploaded_before": "20261231"}, ["--datebefore", "20261231"], id="before"),
    pytest.param(
        {"uploaded_after": "20260301", "uploaded_before": "20260301"},
        ["--date", "20260301"],
        id="date",
    ),
    pytest.param(
        {"uploaded_after": "today-2weeks", "uploaded_before": "yesterday"},
        ["--dateafter", "today-2weeks", "--datebefore", "yesterday"],
        id="relative",
    ),
]


@pytest.mark.parametrize(("typed", "argv"), SAME_INTENT)
def test_the_typed_filters_build_what_yt_dlp_s_own_command_line_builds(
    typed: dict[str, Any], argv: list[str]
) -> None:
    """**The exit criterion the mapping found untested**: same intent, same dictionary.

    Through the whole route a typed value takes — the preset, `to_request`'s freezing, then
    `build_options` — against `parse_options` of the options it stands for, key by key. A relative
    date is resolved by both on the same UTC day; a run spanning midnight could differ.
    """
    request = presets.to_request(a_preset(**typed), url=URL, output_directory=DIRECTORY)
    ours = build_options(request, TEMPLATE)
    theirs = parse_options(argv).ydl_opts

    for key, absent in FILTER_KEYS.items():
        assert ours.get(key, absent) == theirs[key], key


# --- the worker -----------------------------------------------------------------------------------


class _NeverBuilt:
    """An adapter that fails the test if the worker reaches yt-dlp at all."""

    @staticmethod
    def build_options(*_: object, **__: object) -> dict[str, Any]:
        raise AssertionError("a job whose window is empty reached yt-dlp")


def test_a_window_with_no_day_in_it_ends_the_download_before_yt_dlp_is_asked() -> None:
    """`DateRange` refuses such a window, so the worker says what it is: nothing can match."""
    request = a_request(uploaded_after="20261101", uploaded_before="20261001")

    with pytest.raises(worker.NothingDownloadedError) as skipped:
        worker._extract(
            _NeverBuilt,
            request,
            cast(Any, SimpleNamespace(module=None)),
            cast(Any, SimpleNamespace()),
            probe_only=False,
        )

    assert "20261101" in skipped.value.reason and "20261001" in skipped.value.reason


def test_a_window_with_no_day_in_it_still_lets_the_item_be_read() -> None:
    """The probe applies no filter, so it has nothing to refuse."""
    request = a_request(uploaded_after="20261101", uploaded_before="20261001")

    with pytest.raises(AssertionError, match="reached yt-dlp"):
        worker._extract(
            _NeverBuilt,
            request,
            cast(Any, SimpleNamespace(module=None)),
            cast(Any, SimpleNamespace(progress_hook=None, postprocessor_hook=None)),
            probe_only=True,
        )


@pytest.mark.parametrize(
    "typed",
    [
        {"min_filesize": 1},
        {"max_filesize": 1},
        {"uploaded_after": "20260101"},
        {"uploaded_before": "20260101"},
    ],
)
def test_each_filter_lets_a_download_that_wrote_nothing_be_a_skip(typed: dict[str, Any]) -> None:
    assert worker._may_skip(a_request(**typed))


def test_a_job_with_no_filter_and_no_hatch_cannot_be_skipped() -> None:
    assert not worker._may_skip(a_request())


# --- kept: settings and the queue -----------------------------------------------------------------


def test_a_preset_s_rule_and_filters_survive_a_save(tmp_path: Path) -> None:
    """Whole objects compared, so a field written as the wrong TOML type fails here: a count
    written as a string is a value `Preset` refuses on the way back in."""
    target = tmp_path / "settings.toml"
    preset = a_preset(
        playlist_items="-3:",
        max_downloads=2,
        min_filesize=1500,
        max_filesize=2 * 1024**3,
        uploaded_after="today-2weeks",
        uploaded_before="20991231",
    )

    save(add_preset(Settings(), preset), target)
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.presets == (preset,)
    assert "max_downloads = 2\n" in target.read_text(encoding="utf-8")


def test_a_request_s_filters_survive_the_queue() -> None:
    request = a_request(
        min_filesize=1024, max_filesize=2048, uploaded_after="20260101", uploaded_before="20261231"
    )

    assert _deserialize_request(_serialize_request(request)) == request


def test_a_row_written_before_the_filters_existed_still_loads() -> None:
    """**Why no migration is owed** (ruled 2026-10-11): one JSON blob, and a key it lacks is the
    dataclass default, which is a job that asked for no filter."""
    older = json.dumps(
        {
            "url": URL,
            "output_directory": DIRECTORY,
            "format_selector": "best",
            "output_template": TEMPLATE,
        }
    )

    request = _deserialize_request(older)

    assert (request.min_filesize, request.max_filesize) == (None, None)
    assert (request.uploaded_after, request.uploaded_before) == (None, None)


# --- the picker and the names ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("items", "at_most", "checked"),
    [
        (None, None, set(range(7))),
        ("2:4", None, {1, 2, 3}),
        ("2:4", 2, {1, 2}),
        ("-3:", None, {4, 5, 6}),
        ("7,1,7", None, {0, 6}),
        (None, 3, {0, 1, 2}),
        ("50:", None, set()),
    ],
)
def test_a_rule_seeds_the_entries_it_chooses(
    items: str | None, at_most: int | None, checked: set[int]
) -> None:
    assert PlaylistSelection.by_rule(7, items, at_most).checked == checked


def test_a_queued_job_is_named_with_the_days_it_was_frozen_to() -> None:
    request = a_request(max_filesize=100 * 1024**2, uploaded_after="20260927")

    name = format_name(presets.format_choice_of(request))

    assert name.endswith(" · files of at most 100 MiB · uploaded on or after 2026-09-27"), name


def test_a_preset_is_named_with_its_dates_as_typed_and_its_rule() -> None:
    preset = a_preset(
        min_filesize=1024,
        max_filesize=1024**3,
        uploaded_after="today-2weeks",
        uploaded_before="today-2weeks",
        playlist_items="1:5",
        max_downloads=1,
    )

    assert derived_preset_name(preset) == (
        "Best video available · files of 1 KiB to 1 GiB · uploaded on today-2weeks"
        " · items 1:5 · at most 1 item"
    )


@pytest.mark.parametrize(
    ("size", "shown"),
    [(1, "1 byte"), (1500, "1500 bytes"), (1024, "1 KiB"), (3 * 1024**2, "3 MiB")],
)
def test_a_size_is_shown_in_the_largest_unit_that_holds_it_exactly(size: int, shown: str) -> None:
    assert size_words(size) == shown
    amount, unit = in_units(size)
    factor = {"bytes": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}[unit]
    assert amount * factor == size
