"""Downloads retry as yt-dlp's command line does; a missing fragment fails the attempt (`T-364`).

Measured at `8b0aad6`: yt-dlp the library reads an absent `retries` or `fragment_retries` as zero,
where its command line sends ten, and skips a fragment it could not fetch. One 503 on one fragment
of a local stream ended the job *Done* with 250 of 300 frames. Ruled 2026-10-15: when nobody chose
a count, `build_options` sends the command line's, read from `parse_options([])` at the pin; and a
fragment still missing after its retries fails the attempt, unless the user typed
`--skip-unavailable-fragments`, which wins (`ARC-010`, amended 2026-10-15, third).

The real downloads are `tests/integration/test_fragment_retries.py`; these hold the options and the
classification the worker gives a spent retry count.
"""

from __future__ import annotations

import io
from dataclasses import replace
from typing import Any, Final

import pytest
import yt_dlp
from yt_dlp import YoutubeDL, parse_options
from yt_dlp.downloader.common import FileDownloader
from yt_dlp.networking import Response
from yt_dlp.networking.exceptions import HTTPError, TransportError
from yt_dlp.utils import DownloadError

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.downloader.extra_options import options_for

#: yt-dlp's command line's two counts at the pin, written down so the pin moving fails here.
PINNED_COUNTS: Final = {"retries": 10, "fragment_retries": 10}


def a_request(text: str = "", **fields: Any) -> DownloadRequest:
    admission, argv = options_for(text)
    assert admission.usable, admission.refusals
    return DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="downloads",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        extra_options=text,
        extra_option_argv=argv,
        **fields,
    )


def an_http_error(status: int) -> HTTPError:
    response = Response(
        fp=io.BytesIO(b""), url="https://example.invalid/x", headers={}, status=status
    )
    return HTTPError(response)


# --- the counts ---------------------------------------------------------------------------------


def test_the_pin_s_command_line_counts_are_the_ones_written_here() -> None:
    """**The test that fails when the pin's defaults change**, the first criterion's own words."""
    command_line = parse_options([]).ydl_opts

    assert {key: command_line[key] for key in PINNED_COUNTS} == PINNED_COUNTS
    assert adapter.default_retries() == PINNED_COUNTS["retries"]


@pytest.mark.parametrize("probe_only", [False, True])
def test_nobody_choosing_sends_the_command_line_s_counts(probe_only: bool) -> None:
    """Not the keys left out, which the library reads as no retries at all."""
    options = adapter.build_options(a_request(), "%(title)s.%(ext)s", probe_only=probe_only)
    command_line = parse_options([]).ydl_opts

    assert options["retries"] == command_line["retries"]
    assert options["fragment_retries"] == command_line["fragment_retries"]


@pytest.mark.parametrize("chosen", [0, 3])
def test_a_chosen_count_is_sent_as_chosen_and_zero_stays_zero(chosen: int) -> None:
    options = adapter.build_options(a_request(retries=chosen), "%(title)s.%(ext)s")

    assert options["retries"] == chosen
    assert options["fragment_retries"] == PINNED_COUNTS["fragment_retries"]


def test_a_fragment_count_chosen_in_settings_wins() -> None:
    """*(A count typed in the options field won until `T-252` gave the count a setting, which
    refuses the spelling there.)*"""
    request = replace(a_request(), fragment_retries=3)

    options = adapter.build_options(request, "%(title)s.%(ext)s")

    assert options["fragment_retries"] == 3


# --- a missing fragment, and the key the user shares --------------------------------------------


@pytest.mark.parametrize("probe_only", [False, True])
def test_a_fragment_still_missing_fails_the_attempt_by_default(probe_only: bool) -> None:
    options = adapter.build_options(a_request(), "%(title)s.%(ext)s", probe_only=probe_only)

    assert options["skip_unavailable_fragments"] is False


@pytest.mark.parametrize(
    ("text", "skips"),
    [
        ("--skip-unavailable-fragments", True),
        ("--no-abort-on-unavailable-fragments", True),
        ("--abort-on-unavailable-fragments", False),
        ("--no-skip-unavailable-fragments", False),
    ],
)
def test_the_user_s_choice_in_the_options_field_wins(text: str, skips: bool) -> None:
    """The user's explicit opt-in to a partial file, merged after the application's value."""
    options = adapter.build_options(a_request(text), "%(title)s.%(ext)s")

    assert options["skip_unavailable_fragments"] is skips


# --- what a spent retry count gave up on --------------------------------------------------------


def _report(given_up_count: int, retries: int, *, fatal: bool, error: BaseException) -> None:
    """Call every downloader's `report_retry` as yt-dlp's fragment loop does."""
    with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        FileDownloader(ydl, {}).report_retry(error, given_up_count, retries, 4, fatal)


def test_a_fatal_give_up_is_kept_and_put_where_yt_dlp_keeps_a_cause() -> None:
    """yt-dlp raises a `DownloadError` with no cause once a count is spent; the worker supplies
    the error it gave up on, so a fragment the server kept failing is the network failure it is."""
    failure = an_http_error(503)

    with adapter.retries_given_up(yt_dlp) as given_up, pytest.raises(DownloadError) as raised:
        _report(11, 10, fatal=True, error=failure)
    assert raised.value.exc_info[1] is None, "yt-dlp started keeping the cause; recheck T-364"

    adapter.attribute_given_up(raised.value, given_up)

    assert given_up == [failure]
    assert adapter.unwrap(raised.value) is failure
    assert adapter.classify_exception(raised.value).kind is ErrorKind.NETWORK


@pytest.mark.parametrize(
    ("failure", "kind"),
    [
        (an_http_error(404), ErrorKind.EXTRACTOR_ERROR),
        (TransportError("the connection dropped"), ErrorKind.NETWORK),
    ],
)
def test_the_given_up_error_is_classified_as_any_other(
    failure: BaseException, kind: ErrorKind
) -> None:
    """A fragment that is gone stays a failure the queue does not repeat by itself."""
    with adapter.retries_given_up(yt_dlp) as given_up, pytest.raises(DownloadError) as raised:
        _report(11, 10, fatal=True, error=failure)

    adapter.attribute_given_up(raised.value, given_up)

    assert adapter.classify_exception(raised.value).kind is kind


@pytest.mark.parametrize(("count", "fatal"), [(3, True), (11, False)])
def test_a_retry_still_going_or_a_fragment_skipped_is_not_kept(count: int, fatal: bool) -> None:
    """Only a fatal give-up is the failure; a fragment the user chose to skip is not one."""
    with adapter.retries_given_up(yt_dlp) as given_up:
        _report(count, 10, fatal=fatal, error=an_http_error(503))

    assert given_up == []


def test_the_downloader_is_put_back_however_the_download_ends() -> None:
    original = FileDownloader.report_retry

    with pytest.raises(RuntimeError), adapter.retries_given_up(yt_dlp):
        assert FileDownloader.report_retry is not original
        raise RuntimeError("the download failed")

    assert FileDownloader.report_retry is original


def test_a_failure_that_has_a_cause_keeps_it() -> None:
    """Attribution fills only the cause yt-dlp left empty."""
    own = TransportError("its own")
    error = DownloadError("ERROR: something", (type(own), own, None))

    adapter.attribute_given_up(error, [an_http_error(404)])

    assert adapter.unwrap(error) is own
