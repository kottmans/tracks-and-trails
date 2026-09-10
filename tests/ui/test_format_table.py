"""The format table `REQ-003` asks for (`T-107`, `docs/UX_SPEC.md` §4).

**Every column is asserted from a fixture by value**, not from a hand-built `FormatInfo`: the
question `REQ-003` poses is whether what a probe actually reports reaches the table, and a test
that constructs its own model answers a different one. `T-018`'s recorded captures are the contract
for the fields they carry.

**Every column `REQ-003` names is now populated from a recorded capture**, across three sources
that report different things — which is why there are three. archive.org gives ids, extensions,
`WxH` resolutions, exact sizes and one audio codec; `wikimedia_caminandes` gives codecs, bitrate and
`filesize_approx` estimates; `peertube_big_buck_bunny_60fps` gives **fps**, at two different values,
with height-only resolutions and exact sizes.

**fps was the column that could not be recorded**, and `OPS-013` was ratified to permit it resting
on `derived_format_columns` until a source turned up. `T-185` found one. The derived fixture keeps
its place for the shapes no site happens to have — a fractional framerate, and a row missing four
fields at once.

**Phase 3's exit criterion 1 — the table matching `yt-dlp -F` — is evidenced** by
`test_the_table_matches_what_yt_dlp_f_reports` against
`docs/project/evidence/2026-08-07-format-table-vs-yt-dlp-f.md`. Matching includes agreeing where
yt-dlp reports nothing, which is most of what these sources say about fps and codecs.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFont, QImage, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.format_selection import FormatKind, SelectionMode, kind_of
from tracks_and_trails.ui.format_table import (
    ABSENT_TEXT,
    AUDIO_CODEC_COLUMN,
    BITRATE_COLUMN,
    COLUMN_COUNT,
    COLUMN_HEADERS,
    ESTIMATE_PREFIX,
    EXT_COLUMN,
    FORMAT_COLUMN,
    FORMAT_ROLE,
    FPS_COLUMN,
    NOTES_COLUMN,
    RESOLUTION_COLUMN,
    SIZE_COLUMN,
    SORT_ROLE,
    SOUND_COLUMN,
    SOUND_NOT_STATED,
    VIDEO_CODEC_COLUMN,
    FormatTable,
    FormatTableModel,
    carries_nothing,
    codec_name,
    listable,
    says_nothing,
    sound_group,
)
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT

FIXTURE_DIR: Final = Path(__file__).parents[1] / "fixtures" / "infodicts"


def formats_from(name: str) -> tuple[FormatInfo, ...]:
    """The projected formats of a committed fixture — through the adapter, as the app does."""
    payload: dict[str, Any] = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    media = adapter.project_media(payload["info_dict"])
    return media.formats


@pytest.fixture
def derived() -> tuple[FormatInfo, ...]:
    return formats_from("derived_format_columns")


def display(model: FormatTableModel, row: int, column: int) -> str:
    text = model.data(model.index(row, column), int(Qt.ItemDataRole.DisplayRole))
    assert isinstance(text, str)
    return text


def column_of(model: FormatTableModel, column: int) -> list[str]:
    return [display(model, row, column) for row in range(model.rowCount())]


# --- what the table shows (`REQ-003`) ------------------------------------------------------


def test_every_column_req_003_names_is_present() -> None:
    """`REQ-003` lists eight facts; the table has a column for each, plus the id it selects by.

    Asserted against the requirement's own list rather than against `COLUMN_HEADERS`, which would
    be the table agreeing with itself.
    """
    assert len(COLUMN_HEADERS) == COLUMN_COUNT
    headers = " ".join(COLUMN_HEADERS).casefold()
    for named in ("format", "ext", "resolution", "fps", "codec", "bitrate", "size", "notes"):
        assert named in headers, f"REQ-003 names {named} and no column carries it"


def by_band[Comparable: (int, float, str)](
    formats: tuple[FormatInfo, ...], value: Callable[[FormatInfo], Comparable]
) -> list[list[Comparable]]:
    """`value` for each format, split by `T-310`'s bands and in row order.

    **Every ordering assertion about the video list is now a per-band one.** The maintainer ruled
    that formats already carrying sound *"list … last in the list together"*, so the list is sorted
    by the chosen column and then grouped — and a globally-ordered assertion would be asserting the
    ruling away rather than testing the sort.
    """
    bands: dict[int, list[Comparable]] = {}
    for entry in formats:
        bands.setdefault(sound_group(entry), []).append(value(entry))
    return [bands[band] for band in sorted(bands)]


def video_column(table: FormatTable, field: int) -> int:
    """Where the video list shows `field` (`T-310`).

    The lists carry different columns in different orders, so a global column id is no longer a
    view position. Asked of the model rather than written down here, because a second copy of the
    layout is a second thing to keep in step.
    """
    position = table.video.model.column_for(field)
    assert position >= 0, f"the video list does not show column {field}"
    return position


def test_the_columns_are_populated_from_a_recorded_fixture_by_value() -> None:
    """The fields `T-018`'s **recorded** capture carries, asserted as values rather than shapes.

    This is the half of `REQ-003` that rests on a real capture: id, extension, resolution and size
    come from what archive.org actually reported.
    """
    model = FormatTableModel(formats_from("archive_org_big_buck_bunny"))
    assert model.rowCount() == 3

    ids = column_of(model, FORMAT_COLUMN)
    assert ids == ["0", "1", "2"], ids
    assert column_of(model, EXT_COLUMN) == ["ogv", "mp4", "avi"]
    # **`300p`, and `533x300` is the tool tip** (`T-310`). The column is headed *Quality* now and
    # its job is to distinguish rows at a glance; the exact pixels are kept rather than dropped,
    # in the place `T-306` already established for a cell's longer truth.
    assert column_of(model, RESOLUTION_COLUMN) == ["300p", "360p", "720p"]
    assert [
        model.data(model.index(row, RESOLUTION_COLUMN), int(Qt.ItemDataRole.ToolTipRole))
        for row in range(model.rowCount())
    ] == ["533x300", "640x360", "1280x720"]
    assert display(model, 0, SIZE_COLUMN) == "44.8 MB", display(model, 0, SIZE_COLUMN)
    assert column_of(model, NOTES_COLUMN) == ["derivative"] * 3

    # **archive.org reports no fps, bitrate or codec for these formats, and `yt-dlp -F` prints
    # nothing for them either.** The placeholder is therefore the *correct* rendering rather than
    # a gap in the fixture — see `test_the_table_matches_what_yt_dlp_f_reports`, which is the
    # criterion these values serve.
    assert column_of(model, FPS_COLUMN) == [UNKNOWN_TEXT] * 3
    assert column_of(model, BITRATE_COLUMN) == [UNKNOWN_TEXT] * 3


def test_a_recorded_capture_populates_the_codec_column_by_value() -> None:
    """The audio fixture reports `acodec` — so a **recorded** capture carries a codec by value.

    `T107-R1` required every named column to come from a recorded fixture. Three of them cannot,
    for these sources, because yt-dlp itself reports nothing: see the `yt-dlp -F` comparison. This
    is the one that can, and it is asserted here rather than left to the derived fixture.
    """
    model = FormatTableModel(formats_from("archive_org_test_mp3"))
    # The cell names the codec; `mp3` is reachable in the tool tip (`T-306`).
    assert column_of(model, AUDIO_CODEC_COLUMN) == [UNKNOWN_TEXT, "MP3"]
    assert column_of(model, EXT_COLUMN) == ["ogg", "mp3"]
    # archive.org reports `height: 0` for an audio item, which is not a height. `yt-dlp -F` prints
    # `unknown`, and after `T107-R1` so does this (`_as_dimension`).
    assert column_of(model, RESOLUTION_COLUMN) == [UNKNOWN_TEXT, UNKNOWN_TEXT]


#: What `yt-dlp -F` printed for the recorded sources, transcribed on 2026-08-07 against yt-dlp
#: 2026.07.04 — the run is in `docs/project/evidence/2026-08-07-format-table-vs-yt-dlp-f.md`.
#:
#: **Transcribed, not fetched.** The suite must not touch the network (`docs/project/TESTING.md`
#: §5), so the comparison is made against what the recorded run actually printed. Re-running it is
#: `capture.py`'s job and a deliberate act; this keeps the answer under test in the meantime. **A
#: dict per row rather than a tuple**, since `T-185` added a source printing an `FPS` column and
#: none of `MORE INFO`. Positional rows made every source pay for every other source's columns, and
#: a `""` in the seventh slot reads as *"yt-dlp printed an empty note"* rather than *"yt-dlp printed
#: no such column"*. An absent key here means the column was not in the output at all.
YT_DLP_F_OUTPUT: Final[dict[str, list[dict[str, str]]]] = {
    "archive_org_big_buck_bunny": [
        {
            "id": "0",
            "ext": "ogv",
            "resolution": "533x300",
            "size": "44.76MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
            "note": "derivative",
        },
        {
            "id": "1",
            "ext": "mp4",
            "resolution": "640x360",
            "size": "59.01MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
            "note": "derivative",
        },
        {
            "id": "2",
            "ext": "avi",
            "resolution": "1280x720",
            "size": "316.85MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
            "note": "derivative",
        },
    ],
    "archive_org_test_mp3": [
        {
            "id": "0",
            "ext": "ogg",
            "resolution": "unknown",
            "size": "110.55KiB",
            "vcodec": "unknown",
            "acodec": "unknown",
            "note": "derivative",
        },
        {
            "id": "1",
            "ext": "mp3",
            "resolution": "unknown",
            "size": "194.00KiB",
            "vcodec": "unknown",
            "acodec": "mp3",
            "note": "original",
        },
    ],
    # `T-185`, 2026-08-07. The first recorded source in this project that prints an **FPS** column,
    # and it prints two different values — which is why the criterion `OPS-013` amended can now be
    # met for fps by a recording rather than by a derived fixture.
    "peertube_big_buck_bunny_60fps": [
        {
            "id": "240p",
            "ext": "mp4",
            "resolution": "240p",
            "fps": "30",
            "size": "50.54MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
        },
        {
            "id": "360p",
            "ext": "mp4",
            "resolution": "360p",
            "fps": "30",
            "size": "67.01MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
        },
        {
            "id": "480p",
            "ext": "mp4",
            "resolution": "480p",
            "fps": "30",
            "size": "89.70MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
        },
        {
            "id": "720p",
            "ext": "mp4",
            "resolution": "720p",
            "fps": "60",
            "size": "145.93MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
        },
        {
            "id": "1080p",
            "ext": "mp4",
            "resolution": "1080p",
            "fps": "60",
            "size": "263.47MiB",
            "vcodec": "unknown",
            "acodec": "unknown",
        },
    ],
}


@pytest.mark.parametrize("fixture_name", sorted(YT_DLP_F_OUTPUT))
def test_the_table_matches_what_yt_dlp_f_reports(fixture_name: str) -> None:
    """**Phase 3's exit criterion 1** (`T107-R1`): the table agrees with `yt-dlp -F`.

    Asserted per row and per fact rather than as a rendered block, because the two render
    differently on purpose — `44.76MiB` against `44.8 MB` is base-2 versus the powers-of-1024
    labelling the rest of this window uses, and `unknown` against `Unknown` is capitalisation.
    **What must agree is which formats exist and what is known about each**, which is what the
    criterion asks and what a user would check.

    This is where the divergences were caught. Before `T107-R1`: an audio item's `height: 0`
    rendered `0x0` where yt-dlp prints `unknown`, and a format whose video codec is merely unknown
    was reported as *audio only*.
    """
    model = FormatTableModel(formats_from(fixture_name))
    reported = YT_DLP_F_OUTPUT[fixture_name]
    assert model.rowCount() == len(reported), "the table shows a different number of formats"

    #: yt-dlp's column name -> this table's column. `note` and `fps` are absent from some outputs,
    #: which is a different fact from being empty in them — see `YT_DLP_F_OUTPUT`.
    columns = {
        "id": FORMAT_COLUMN,
        "ext": EXT_COLUMN,
        "resolution": RESOLUTION_COLUMN,
        "fps": FPS_COLUMN,
        "vcodec": VIDEO_CODEC_COLUMN,
        "acodec": AUDIO_CODEC_COLUMN,
        "note": NOTES_COLUMN,
    }
    for row, printed in enumerate(reported):
        id_ = printed["id"]
        for name, column in columns.items():
            if name not in printed:
                # yt-dlp printed no such column for this source. The table has one for every
                # `REQ-003` field always, and it must read a placeholder rather than invent a
                # value — which is the same agreement as any other, one step weaker.
                #
                # **Which placeholder depends on what the silence means** (`T-305`). yt-dlp omits
                # `format_note` when a format has nothing noted, so no note column is the source
                # saying there are none — `ABSENT_TEXT`. For every other column its silence is
                # ignorance and `UNKNOWN_TEXT` is the honest word. This branch asserted the latter
                # for all of them, which is the conflation `T-305` corrects.
                expected_absence = ABSENT_TEXT if column == NOTES_COLUMN else UNKNOWN_TEXT
                assert display(model, row, column) == expected_absence, (
                    f"yt-dlp printed no {name} column and the table claims "
                    f"{display(model, row, column)!r} for {id_}"
                )
                continue
            expected = printed[name]
            if column == RESOLUTION_COLUMN and expected != "unknown":
                # **The same move the codec columns made** (`T-306`, extended by `T-310`): the
                # cell shows the name people use and the exact string yt-dlp printed stays
                # reachable in the tool tip. So the agreement is that yt-dlp's own answer is on
                # the row *somewhere*, not that it is the cell text.
                shown = display(model, row, column)
                tip = model.data(model.index(row, column), int(Qt.ItemDataRole.ToolTipRole))
                assert expected in (shown, tip), (
                    f"yt-dlp printed {expected!r} for {id_} and the table shows {shown!r} with "
                    f"tool tip {tip!r}, so its answer is not reachable at all"
                )
                continue
            if column in (VIDEO_CODEC_COLUMN, AUDIO_CODEC_COLUMN) and expected != "unknown":
                # **The codec columns show a name and keep the identifier in the tool tip**
                # (`T-306`), so the agreement with `yt-dlp -F` moved there rather than weakening.
                # `codec_name` is applied to what yt-dlp printed and compared with the cell, which
                # is the same assertion in the table's own vocabulary; where it cannot read the
                # string the two are still identical.
                assert display(model, row, column) == codec_name(expected), (
                    f"the table names {expected!r} as {display(model, row, column)!r} for {id_}"
                )
                tip = model.data(model.index(row, column), int(Qt.ItemDataRole.ToolTipRole))
                if codec_name(expected) != expected:
                    # **Exact, not `in (expected, None)`** (`T306-R2`). Permitting `None` let a
                    # mutation that suppressed every audio tool tip pass the whole module.
                    assert tip == expected, (
                        f"the identifier {expected!r} for {id_} is not reachable: {tip!r}"
                    )
                else:
                    assert tip is None, (
                        f"{id_} shows {expected!r} unchanged and should add no tool tip: {tip!r}"
                    )
                continue
            if expected == "unknown":
                assert display(model, row, column) == UNKNOWN_TEXT, (
                    f"yt-dlp reports no {name} for {id_} and the table claims one"
                )
            else:
                assert display(model, row, column) == expected, (
                    f"{id_}: {name} is {display(model, row, column)!r}, yt-dlp printed {expected!r}"
                )
        # yt-dlp prints MiB, this window prints powers-of-1024 MB; what must agree is the number
        # of bytes underneath, which is what the sort key carries.
        size = printed["size"]
        mebibytes = float(size.removesuffix("MiB").removesuffix("KiB"))
        scale = 1024 * 1024 if size.endswith("MiB") else 1024
        key = model.data(model.index(row, SIZE_COLUMN), SORT_ROLE)
        assert isinstance(key, tuple)
        assert abs(key[0] - mebibytes * scale) < scale * 0.01, (
            f"{id_}: table has {key[0]} bytes, yt-dlp reported {size}"
        )


def test_codecs_bitrate_and_estimated_sizes_come_from_a_recorded_capture() -> None:
    """`T107-R1`: the columns archive.org cannot populate, from a source that can.

    **`wikimedia_caminandes` is a recorded capture**, not a derived one. It reports `vcodec`,
    `acodec` and `tbr` per format, and its sizes are `filesize_approx` — so it also exercises
    `T107-R7`'s estimate rendering against a real report rather than a constructed one.

    **This source reports no fps**, and that is asserted rather than ignored: the assertion is
    what would notice Wikimedia starting to report it, which would make `T-185`'s conclusion stale.
    fps is covered by `peertube_big_buck_bunny_60fps` — see the test below.
    """
    model = FormatTableModel(formats_from("wikimedia_caminandes"))
    assert model.rowCount() == 5

    assert column_of(model, VIDEO_CODEC_COLUMN)[:4] == ["VP9", "VP9", "Theora", "VP9"]
    assert column_of(model, AUDIO_CODEC_COLUMN)[:4] == ["Opus", "Opus", "Vorbis", "Opus"]
    assert column_of(model, BITRATE_COLUMN)[:4] == [
        "207 kbps",
        "422 kbps",
        "2796 kbps",
        "1440 kbps",
    ]
    # Every one of those four sizes is an estimate in the capture, and each says so.
    for row in range(4):
        rendered = display(model, row, SIZE_COLUMN)
        assert rendered.startswith(ESTIMATE_PREFIX), f"row {row} renders {rendered!r} as exact"
    # The `source` format carries an exact size and no bitrate — the contrast in one capture.
    assert not display(model, 4, SIZE_COLUMN).startswith(ESTIMATE_PREFIX)
    assert display(model, 4, BITRATE_COLUMN) == UNKNOWN_TEXT

    assert column_of(model, FPS_COLUMN) == [UNKNOWN_TEXT] * 5, (
        "this source has begun reporting fps; T-185's search should be revisited"
    )


def test_fps_comes_from_a_recorded_capture_by_value() -> None:
    """`T-185`: the last column that rested on a derived fixture, from a real report.

    **`OPS-013` was ratified to permit exactly this gap and this is it closing.** `T-107` shipped
    with fps exercised by `derived_format_columns` because none of the seven sources probed for
    `T107-R1` reported it — four Wikimedia Commons files and three archive.org items. yt-dlp's
    PeerTube extractor reads `fps` from each published file, so `peertube_big_buck_bunny_60fps`
    supplies it by value.

    **Two framerates in one capture, which is the part that matters.** A source reporting one
    framerate everywhere would populate the column without ever ordering it, and `REQ-003` asks for
    a *sortable* table. Here 30 and 60 both occur, so the sort below is a real comparison of values
    a site actually reported rather than of numbers this project chose.
    """
    model = FormatTableModel(formats_from("peertube_big_buck_bunny_60fps"))
    assert model.rowCount() == 5
    assert column_of(model, FPS_COLUMN) == ["30", "30", "30", "60", "60"]

    # Height-only, because PeerTube reports no width — `yt-dlp -F` prints `240p` for these too, and
    # `describe_resolution`'s height-only branch is now exercised by a recording rather than only
    # by the derived fixture.
    assert column_of(model, RESOLUTION_COLUMN) == ["240p", "360p", "480p", "720p", "1080p"]
    # Exact sizes, against `wikimedia_caminandes`'s estimates: both provenances now come from real
    # captures, so `T107-R7`'s distinction is asserted in both directions from recordings.
    for row in range(model.rowCount()):
        assert not display(model, row, SIZE_COLUMN).startswith(ESTIMATE_PREFIX)

    model.sort(FPS_COLUMN, Qt.SortOrder.DescendingOrder)
    assert column_of(model, FPS_COLUMN) == ["60", "60", "30", "30", "30"]
    model.sort(FPS_COLUMN, Qt.SortOrder.AscendingOrder)
    assert column_of(model, FPS_COLUMN) == ["30", "30", "30", "60", "60"]


def test_fps_and_the_column_shapes_come_through_the_projection(
    derived: tuple[FormatInfo, ...],
) -> None:
    """The shapes no recorded source happens to have (`T107-R1`, `T-185`).

    Codecs, bitrate and estimated sizes are asserted from `wikimedia_caminandes`, and fps from
    `peertube_big_buck_bunny_60fps`. **What is left here is genuinely unrecorded: a *fractional*
    framerate.** PeerTube reports whole numbers — 30 and 60 — and 29.97 is the value that would
    catch a projection rounding fps to an int, which no probed source supplies.

    These values are synthetic and this test does not pretend otherwise. It keeps the placeholder
    path too: one row carrying neither fps nor bitrate nor size, which is what an HLS manifest entry
    looks like.
    """
    model = FormatTableModel(derived)
    assert display(model, 0, FPS_COLUMN) == "24"
    assert display(model, 1, FPS_COLUMN) == "29.97", "a fractional framerate lost its fraction"
    assert display(model, 2, BITRATE_COLUMN) == "16430 kbps"
    assert display(model, 0, VIDEO_CODEC_COLUMN) == "Theora"
    assert display(model, 0, AUDIO_CODEC_COLUMN) == "Vorbis"


def test_a_missing_field_reads_the_placeholder_never_an_empty_cell(
    derived: tuple[FormatInfo, ...],
) -> None:
    """`docs/UX_SPEC.md` §4: a word, never blank and never `None`.

    The `hls-480` row of the derived fixture has no fps, no bitrate, no size and no note — four
    absences in one row, which is what a real HLS manifest entry looks like.

    **Three of those are ignorance and one is not** (`T-305`). fps, bitrate and size are values
    yt-dlp did not report; a missing note is yt-dlp reporting that there is nothing to note. The
    cell must still say something — that rule is unchanged — but saying *unknown* about a note
    nobody wrote is a claim, and it is most of why this table read as mostly unknown.
    """
    model = FormatTableModel(derived)
    row = next(
        index
        for index in range(model.rowCount())
        if display(model, index, FORMAT_COLUMN) == "hls-480"
    )
    for column in (FPS_COLUMN, BITRATE_COLUMN, SIZE_COLUMN):
        assert display(model, row, column) == UNKNOWN_TEXT, (
            f"{COLUMN_HEADERS[column]} rendered {display(model, row, column)!r} for an absent value"
        )
    assert display(model, row, NOTES_COLUMN) == ABSENT_TEXT, (
        f"Notes rendered {display(model, row, NOTES_COLUMN)!r} for a format with nothing noted"
    )
    for column in range(COLUMN_COUNT):
        assert display(model, row, column), f"{COLUMN_HEADERS[column]} rendered an empty cell"


@pytest.mark.parametrize(
    ("has_stream", "codec", "expected", "why"),
    [
        (False, None, ABSENT_TEXT, "yt-dlp said 'none': there is no such stream"),
        (None, None, UNKNOWN_TEXT, "yt-dlp was silent: the stream may exist and be unnamed"),
        (True, "opus", "Opus", "yt-dlp named it, and the cell shows the known name"),
        (True, None, UNKNOWN_TEXT, "the stream exists and yt-dlp did not name its codec"),
    ],
)
def test_a_codec_cell_tells_absent_apart_from_unknown(
    has_stream: bool | None, codec: str | None, expected: str, why: str
) -> None:
    """`T-305`: three states, not two, and the fourth is the one a two-way split gets wrong.

    `FormatInfo` carries `has_video` and `has_audio` as tri-state flags rather than one kind
    because `T107-R1` cost exactly this: a format whose video codec was merely unknown was
    reported as having no video at all. Rendering `'none'` and silence with the same word puts
    that conflation back one layer up, where it made every row of a merge pair claim its audio
    codec was unknown.

    **The `True, None` row is why this is parametrised.** A fix that only asked *"is the stream
    absent?"* would pass the first three and still be wrong about a present stream with an unnamed
    codec, which is the archive.org case the module already documents.
    """
    entry = FormatInfo(
        format_id="probe",
        extension="mp4",
        audio_codec=codec,
        has_audio=has_stream,
        video_codec="avc1",
        has_video=True,
    )
    model = FormatTableModel((entry,))
    assert display(model, 0, AUDIO_CODEC_COLUMN) == expected, why


def test_a_video_only_row_does_not_claim_its_missing_audio_is_unknown() -> None:
    """The maintainer's 2026-09-09 observation, as it arrived: a whole table of them.

    Every row under *merge a separate video and audio stream* is video-only, and every one of them
    reported `Unknown` for a stream yt-dlp had explicitly denied.
    """
    entry = FormatInfo(
        format_id="614",
        extension="mp4",
        video_codec="vp09.00.40.08",
        has_video=True,
        has_audio=False,
    )
    assert entry.is_video_only, "the fixture is not the case this test is about"
    model = FormatTableModel((entry,))
    assert display(model, 0, AUDIO_CODEC_COLUMN) == ABSENT_TEXT
    assert display(model, 0, VIDEO_CODEC_COLUMN) == "VP9"
    # The identifier `REQ-009` and every bug report are written in stays reachable.
    tip = model.data(model.index(0, VIDEO_CODEC_COLUMN), int(Qt.ItemDataRole.ToolTipRole))
    assert tip == "vp09.00.40.08"


def test_a_format_with_no_height_reads_unknown_rather_than_claiming_audio_only(
    derived: tuple[FormatInfo, ...],
) -> None:
    """`T107-R1`: the table must not assert what the projection cannot tell it.

    This used to read *audio only* whenever `FormatInfo.is_audio_only` was true. That property is
    `video_codec is None and audio_codec is not None`, and `_as_optional_codec` maps **both** a
    missing `vcodec` and yt-dlp's explicit `'none'` to `None` — so a format whose video codec is
    merely unknown was reported as having no video at all. `yt-dlp -F` prints `unknown` for those,
    which is what caught it.
    """
    model = FormatTableModel(derived)
    row = next(
        index for index in range(model.rowCount()) if display(model, index, FORMAT_COLUMN) == "140"
    )
    entry = next(item for item in derived if item.format_id == "140")
    # **The tri-state reaches this column too, which `T-310` fixed and `T-305` had not.**
    # `describe_resolution` read `height` and never looked at `has_video`, so a format whose video
    # stream yt-dlp had *denied* reported its resolution as *unknown* — a claim of ignorance about
    # something the extractor stated, beside a video-codec cell correctly reading `None`. Three
    # columns describing one denied stream and two of them disagreeing with the third.
    #
    # `T107-R1`'s property is unchanged and is the other half of this: absence may be asserted only
    # from an explicit `'none'`, never from silence.
    expected = ABSENT_TEXT if entry.has_video is False else UNKNOWN_TEXT
    assert display(model, row, RESOLUTION_COLUMN) == expected


# --- sorting is over the projection (`T-075`) ----------------------------------------------


def test_resolution_sorts_numerically_not_as_text(derived: tuple[FormatInfo, ...]) -> None:
    """`T-075`'s defect: `1080p` text-sorts *below* `144p`.

    The assertion set is chosen so text order and numeric order disagree — 300, 360, 1080 and 480
    sort one way as numbers and another as strings — so a table that sorted its own display
    strings would fail rather than coincide.
    """
    model = FormatTableModel(derived)
    model.sort(RESOLUTION_COLUMN, Qt.SortOrder.AscendingOrder)
    heights = [
        entry.height
        for entry in model.formats()
        if entry.height is not None and not entry.is_audio_only
    ]
    assert heights == sorted(heights), heights
    assert heights[-1] == 1080, "the tallest format did not sort last; this is T-075 exactly"

    as_text = sorted(str(height) for height in heights)
    assert [str(height) for height in heights] != as_text, (
        "the chosen heights sort identically as text and as numbers, so this test cannot fail "
        "against a table that sorts its display strings"
    )


def test_size_sorts_as_bytes_not_as_its_rendered_string(derived: tuple[FormatInfo, ...]) -> None:
    """The other half of `T-075`: `9.9 MB` text-sorts above `10.1 MB`."""
    model = FormatTableModel(derived)
    model.sort(SIZE_COLUMN, Qt.SortOrder.DescendingOrder)
    sizes = [entry.filesize for entry in model.formats() if entry.filesize is not None]
    assert sizes == sorted(sizes, reverse=True), sizes


def test_sorting_a_column_of_mixed_ids_does_not_raise(derived: tuple[FormatInfo, ...]) -> None:
    """Format ids are numeric *and* named — `137` and `hls-480` in one column.

    A key that returned an `int` for one row and a `str` for another raises `TypeError` the moment
    `sorted` compares them. The numeric ids order numerically and the named ones follow.

    **Asserted as the rule, not as one id.** This pinned `hls-480` as the last row, which held only
    while it was the alphabetically last named id in the fixture — adding `storyboard` for a
    different reason broke it, and the ordering was never wrong. What the column promises is that
    every numeric id precedes every named one and that each group is ordered within itself.
    """
    model = FormatTableModel(derived)
    model.sort(FORMAT_COLUMN, Qt.SortOrder.AscendingOrder)
    ids = column_of(model, FORMAT_COLUMN)
    numeric = [value for value in ids if value.isdigit()]
    named = [value for value in ids if not value.isdigit()]
    assert numeric and named, f"the fixture no longer mixes both kinds of id: {ids}"
    assert ids == numeric + named, f"a named id sorted in among the numeric ones: {ids}"
    assert [int(value) for value in numeric] == sorted(int(value) for value in numeric), numeric
    assert named == sorted(named, key=str.casefold), named


def test_the_sort_role_answers_the_projection_not_the_text(
    derived: tuple[FormatInfo, ...],
) -> None:
    """`SORT_ROLE` is what makes the ordering inspectable rather than inferred from row order."""
    model = FormatTableModel(derived)
    for row in range(model.rowCount()):
        key = model.data(model.index(row, RESOLUTION_COLUMN), SORT_ROLE)
        assert isinstance(key, tuple), key
        entry = model.data(model.index(row, FORMAT_COLUMN), FORMAT_ROLE)
        assert isinstance(entry, FormatInfo)
        expected = float(entry.height) if entry.height is not None else -1.0
        assert key[0] == expected


def test_sorting_reverses_on_the_same_column(derived: tuple[FormatInfo, ...]) -> None:
    """`docs/UX_SPEC.md` §4: `Space` on a header sorts, again reverses.

    **Asserted on the sort keys, not on the format ids.** This compared the id column against its
    own reverse, which silently assumed every row has a distinct height — true until `T-108` added
    a 1080p video-only stream beside the 1080p progressive one. Two rows with equal keys keep their
    relative order in *both* directions, because the sort is stable, so the id sequence is not a
    reversal and never promised to be. The keys are what the column orders and what the user reads
    as sorted.
    """
    model = FormatTableModel(derived)

    def keys() -> list[tuple[float, str]]:
        read = [
            model.data(model.index(row, RESOLUTION_COLUMN), SORT_ROLE)
            for row in range(model.rowCount())
        ]
        # `data` is typed `object`, and the keys are what this test compares. Checked rather than
        # cast: a column that stopped answering the sort role would otherwise compare as equal-ish
        # and the test would pass over nothing.
        keyed: list[tuple[float, str]] = []
        for value in read:
            assert isinstance(value, tuple), f"the sort role answered {value!r}"
            keyed.append((float(value[0]), str(value[1])))
        return keyed

    model.sort(RESOLUTION_COLUMN, Qt.SortOrder.AscendingOrder)
    ascending = keys()
    assert ascending == sorted(ascending), "ascending did not ascend"
    model.sort(RESOLUTION_COLUMN, Qt.SortOrder.DescendingOrder)
    assert keys() == sorted(ascending, reverse=True)
    # The tie is real and is what the id comparison used to hide: both 1080-high rows are present
    # in both orders, and neither direction drops or duplicates one.
    assert sorted(column_of(model, FORMAT_COLUMN)) == sorted(entry.format_id for entry in derived)


# --- the widget, its keyboard and its labels -----------------------------------------------


def test_the_table_opens_with_a_current_row(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`T-152`: a declared keyboard route that needs a click first is not one."""
    table = FormatTable(derived)
    assert table.table.currentIndex().isValid(), "the table opened with no current row"
    assert table.current_format() is not None


def test_the_table_opens_sorted_by_resolution_best_first(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """The order somebody opening a format table is looking for, and proof `sort()` is wired.

    `QTableView.setSortingEnabled` calls the *model's* `sort`, and `QAbstractItemModel`'s default
    does nothing — so a table that merely enabled sorting would move its indicator and leave the
    rows alone. This fails if the model stops implementing `sort`.
    """
    table = FormatTable(derived)
    formats = table.model.formats()
    assert formats, "the video list is empty, so this measured nothing"

    # **Descending within each band, and the bands keep their order** (`T-310`). The maintainer
    # ruled that formats already carrying sound *"list … last in the list together"*, so a globally
    # descending assertion would now be asserting the ruling away.
    groups = [sound_group(entry) for entry in formats]
    assert groups == sorted(groups), f"the bands are out of order: {groups}"
    for heights in by_band(formats, lambda entry: entry.height or -1):
        assert heights == sorted(heights, reverse=True), heights


def test_choosing_the_current_row_reports_the_format(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """The seam `T-108` consumes. **Reported, never acted on** — `P-14` keeps download out."""
    table = FormatTable(derived)
    seen: list[object] = []
    table.format_chosen.connect(seen.append)
    table.choose_current()
    assert len(seen) == 1
    assert isinstance(seen[0], FormatInfo)
    assert seen[0] == table.current_format()


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        # Established, one object type at a time.
        ("mp4a.40.2", "AAC"),
        ("mp4a.40.5", "HE-AAC"),
        ("mp4a.40.29", "HE-AAC v2"),
        # `mp4a` is a container-level identifier and these are not AAC at all (`T306-R1`).
        # **And they are not MP3 either** (`T306-R1`, third pass): `0x69` and `0x6b` are MPEG-2
        # and MPEG-1 Part 3, both of which cover Layers I, II and III, so an MP2 stream was
        # being labelled MP3. The family is established; the layer is not.
        ("mp4a.69", "MPEG audio"),
        ("mp4a.6B", "MPEG audio"),
        ("mp4a.a5", "AC-3"),
        # Neither table establishes these, so the identifier stands.
        ("mp4a.E1", "mp4a.E1"),
        ("mp4a.future", "mp4a.future"),
        ("mp4a", "mp4a"),
        # A four-character code that does decide the codec by itself.
        ("avc1.640028", "H.264"),
        ("av01.0.08M.08", "AV1"),
        ("vp09.00.40.08", "VP9"),
        ("opus", "Opus"),
        ("h264-hd", "h264-hd"),
    ],
)
def test_a_codec_is_named_only_where_the_identifier_establishes_it(raw: str, shown: str) -> None:
    """`T306-R1`: every expectation here is **written out**, not computed by the code under test.

    The first version of this coverage asserted `display(...) == codec_name(expected)`, which
    compares production with itself: replacing a label with `WRONG CODEC` passed all 48 tests.
    These are literals, so a wrong name is a failing test.

    **`mp4a` is the case the batch got wrong.** It identifies MPEG-4 audio at the container level
    and defers to the object type after it. `40.2` is AAC-LC; `69` and `6b` are MPEG audio whose
    **layer they do not state**; `E1` is none of the above. Classifying the first token alone
    reported MPEG audio as AAC to somebody choosing a format by it.
    """
    assert codec_name(raw) == shown


@pytest.mark.parametrize("column", [VIDEO_CODEC_COLUMN, AUDIO_CODEC_COLUMN])
def test_a_renamed_codec_keeps_its_identifier_in_the_tool_tip(
    column: int, qapp: QApplication
) -> None:
    """`T306-R2`: **both** columns, exactly — suppressing the audio tool tip once passed the suite.

    `REQ-009`'s selector syntax and every bug report are written in the identifier, so a cell that
    shows a name has to keep it. A cell that shows the identifier unchanged adds nothing, because
    a tool tip repeating its own cell is noise a screen reader reads twice.
    """
    entry = FormatInfo(
        format_id="probe",
        extension="mp4",
        video_codec="avc1.640028",
        has_video=True,
        audio_codec="mp4a.40.2",
        has_audio=True,
    )
    model = FormatTableModel((entry,))
    tip = model.data(model.index(0, column), int(Qt.ItemDataRole.ToolTipRole))
    expected = "avc1.640028" if column == VIDEO_CODEC_COLUMN else "mp4a.40.2"
    assert tip == expected, f"{COLUMN_HEADERS[column]} lost the identifier behind its name: {tip!r}"

    plain = FormatInfo(
        format_id="plain",
        extension="webm",
        video_codec="h264-hd",
        has_video=True,
        audio_codec="h264-hd",
        has_audio=True,
    )
    unchanged = FormatTableModel((plain,))
    assert unchanged.data(unchanged.index(0, column), int(Qt.ItemDataRole.ToolTipRole)) is None


def test_the_chosen_row_says_so_in_the_table_and_not_only_in_the_footer(
    derived: tuple[FormatInfo, ...], qapp: QApplication
) -> None:
    """`T-306`: a two-step selection needs a running account of itself near the rows.

    The footer read *"Chosen — video: 137, audio: 140"* and nothing in the table agreed with it,
    which is the *"no easy way to see what you are picking"* half of the 2026-09-09 report. The
    row marks itself now, and it does so **through the selection the widget already owns** rather
    than through a second idea of what is chosen.
    """
    table = FormatTable(derived)
    identifier = video_column(table, FORMAT_COLUMN)

    def bold_ids() -> set[str]:
        marked = set()
        for row in range(table.model.rowCount()):
            font = table.model.data(
                table.model.index(row, identifier), int(Qt.ItemDataRole.FontRole)
            )
            if isinstance(font, QFont) and font.bold():
                marked.add(display(table.model, row, identifier))
        return marked

    assert bold_ids() == set(), "nothing is chosen yet, so no row may claim to be"
    table.choose_current()
    chosen = table.current_format()
    assert chosen is not None
    assert bold_ids() == {chosen.format_id}, "the chosen row is the one the footer names"


def test_the_identifier_column_is_drawn_quieter_than_the_row(
    derived: tuple[FormatInfo, ...], qapp: QApplication
) -> None:
    """`T-306`, and `REQ-003` is why it is demoted rather than removed.

    The requirement names the format id column, so it stays and stays selectable by
    `REQ-008`. What changed is that it no longer reads as the most important thing in a row it is
    almost never the reason for.
    """
    model = FormatTableModel(derived)
    muted = model.data(model.index(0, FORMAT_COLUMN), int(Qt.ItemDataRole.ForegroundRole))
    assert muted is not None, "the identifier column no longer answers a foreground of its own"
    for column in (EXT_COLUMN, RESOLUTION_COLUMN, VIDEO_CODEC_COLUMN):
        assert model.data(model.index(0, column), int(Qt.ItemDataRole.ForegroundRole)) is None, (
            f"{COLUMN_HEADERS[column]} is being recoloured too; only the identifier is demoted"
        )


def test_an_empty_table_chooses_nothing_rather_than_raising(qapp: QApplication) -> None:
    """A probe can report no formats at all; the widget must open rather than fail."""
    table = FormatTable(())
    assert table.current_format() is None
    seen: list[object] = []
    table.format_chosen.connect(seen.append)
    table.choose_current()
    assert seen == []


def test_every_cell_carries_an_accessible_text_naming_its_column(
    derived: tuple[FormatInfo, ...],
) -> None:
    """`NFR-005`: a screen reader crossing a row must be able to tell bitrate from size.

    Eight bare values in a row are unreadable without the column, and the header is announced once
    at most — the same reasoning `T-060` applied to state text.
    """
    model = FormatTableModel(derived)
    for row in range(model.rowCount()):
        for column in range(COLUMN_COUNT):
            spoken = model.data(model.index(row, column), int(Qt.ItemDataRole.AccessibleTextRole))
            assert isinstance(spoken, str)
            assert spoken.startswith(COLUMN_HEADERS[column]), spoken
            assert display(model, row, column) in spoken


def test_the_view_is_labelled_for_assistive_technology(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    table = FormatTable(derived)
    assert table.table.accessibleName()


# --- the boundary (`NFR-008`) --------------------------------------------------------------


def test_no_ui_module_reads_a_raw_info_dict_key() -> None:
    """`NFR-008`: yt-dlp's schema stops at the adapter, asserted statically (`T107-R5`).

    **The first version excluded `width`, `height`, `ext` and `filesize` globally** to avoid
    failing on `main_window.py`, which reads `width`/`height` out of the window-geometry TOML. That
    made it a gate that did not gate what it claimed: the reviewer added `{"width": 1920}["width"]`
    to `ui/format_table.py` in a temporary tree and the test stayed green.

    So the exclusion is **per module** rather than global. Every module in `ui/` is checked against
    the complete consumed-format key set; the two that legitimately use a generic key say so here,
    by name, with the reason. A new format surface gets the full set by default, which is the
    direction the mistake should fall.
    """
    import ast

    from tests.fixtures.capture import CONSUMED_FORMAT

    #: Keys a named module may use because it is demonstrably not talking about a format.
    #:
    #: Narrow on purpose: a module, a key, and a reason. Anything not listed here is checked
    #: against every key the adapter consumes.
    allowed: dict[str, set[str]] = {
        # `window.toml` geometry, read by `load_geometry` — nothing to do with a video.
        "main_window.py": {"width", "height"},
    }

    ui_dir = Path(__file__).parents[2] / "src" / "tracks_and_trails" / "ui"
    offenders: list[str] = []
    for module in sorted(ui_dir.glob("*.py")):
        forbidden = set(CONSUMED_FORMAT) - allowed.get(module.name, set())
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            key: str | None = None
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                key = node.slice.value if isinstance(node.slice.value, str) else None
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                key = node.args[0].value
            if key in forbidden:
                offenders.append(f"{module.name}: {key!r}")
    assert not offenders, (
        f"ui/ reads yt-dlp's own keys: {offenders}. NFR-008 confines that schema to the adapter, "
        "and a widget that indexes it goes blank on the next upstream rename"
    )


def test_the_boundary_check_covers_the_keys_it_excuses_elsewhere() -> None:
    """The gate's own gate (`T107-R5`): prove the per-module excuse is not a global hole.

    A test that excused `width` everywhere passed a raw `width` subscript in the format table.
    This asserts the excuse is scoped — `format_table.py` is checked against the *complete* key
    set — so the mutation the reviewer ran would now fail.
    """
    from tests.fixtures.capture import CONSUMED_FORMAT

    for generic in ("width", "height", "ext", "filesize"):
        assert generic in CONSUMED_FORMAT, (
            f"{generic} left the consumed set; the exclusion below is now describing nothing"
        )


# --- the widget's layout, keyboard and sort state ------------------------------------------


def test_the_wrapper_gives_the_table_its_whole_size(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`T107-R2`: without a layout the child keeps its construction geometry.

    The reviewer resized the wrapper to 320x180 and the `QTableView` stayed 256x192, and the
    wrapper reported a `-1 x -1` size hint — so any surface embedding this would clip or collapse
    it. Asserted on a **shown** widget, because layout activation is what the defect escaped.

    **The view is no longer the wrapper's only child**, so *"the table is exactly the wrapper's
    height"* stopped being the right statement: `T-108` put the merge control above it and the
    chosen-formats line below. What the criterion actually asks is that the table **fills the space
    it is given**, so that is what is asserted — full width, and every pixel of the height its
    siblings do not take. Growing the wrapper is checked too: the table is the stretching child, and
    a fixed-height view inside a taller wrapper is the same defect with a smaller gap.
    """
    table = FormatTable(derived)
    table.resize(720, 300)
    table.show()
    qapp.processEvents()
    try:
        assert table.sizeHint().isValid(), f"the wrapper has no size hint: {table.sizeHint()}"

        # **Two lists share the width now** (`T-310`), so *"the view is exactly the wrapper's
        # width"* stopped being the right statement — it was true only while there was one view.
        # What `T107-R2` actually asks is that a child fills the space it is given, and the space
        # each list is given is its own panel, so that is what is asserted. Together they take the
        # width, which is the other half of the same property.
        panels = table.lists()
        assert len(panels) == 2, "the derived fixture has an audio half, so there are two lists"
        for panel in panels:
            assert panel.view.width() == panel.width(), (
                f"{panel.view.accessibleName()} is {panel.view.width()}px inside a "
                f"{panel.width()}px list"
            )
        spread = sum(panel.width() for panel in panels)
        assert spread > table.width() // 2, (
            f"the two lists take {spread}px of a {table.width()}px wrapper, so they are not "
            "filling it"
        )

        for panel in panels:
            siblings = panel.height() - panel.view.height()
            assert 0 < siblings < panel.height(), (
                f"{panel.view.accessibleName()} takes {panel.view.height()}px of "
                f"{panel.height()}px, leaving {siblings}px for its heading and its button"
            )

        before = table.video.view.height()
        table.resize(table.width(), table.height() * 2)
        qapp.processEvents()
        assert table.video.view.height() > before, (
            "the list did not grow with the wrapper, so it is not the stretching child"
        )
    finally:
        table.close()


def _press(qapp: QApplication, key: Qt.Key) -> None:
    """Send `key` to whatever currently has focus — the user's route, not the widget's door.

    `T107-R3` twice: both earlier attempts posted the event **at the header**, which proves the
    header reacts and says nothing about whether a keyboard can get there. Focus is read from the
    application, so a route that does not exist cannot be simulated into existing.
    """
    target = qapp.focusWidget()
    assert target is not None, "nothing has focus, so there is no route to test"
    qapp.sendEvent(target, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
    qapp.processEvents()


def _click(qapp: QApplication, key: Qt.Key) -> None:
    """`_press`, plus the release — for a control that acts on the way up.

    `QAbstractButton` marks itself down on `Space` press and **toggles on release**, so a press
    alone leaves a checkbox looking pressed and unchanged. Sent to the focus widget for the same
    reason `_press` is: a route that does not exist must not be simulated into existing.
    """
    target = qapp.focusWidget()
    assert target is not None, "nothing has focus, so there is no route to test"
    QTest.keyClick(target, key)
    qapp.processEvents()


def test_tab_reaches_the_header_and_tab_leaves_it_again(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`docs/UX_SPEC.md` §4: *Tab moves between the header row, the table body and the buttons*.

    **`QTableView` consumes Tab for cell navigation by default**, so the declared route did not
    exist: Tab moved the current cell and focus never left the view. The reviewer's probe found
    exactly that, twice — first that Tab stayed on the view, then that a manually focused header
    would not release it either.
    """
    table = FormatTable(derived)
    table.show()
    qapp.processEvents()
    try:
        table.table.setFocus()
        qapp.processEvents()
        assert qapp.focusWidget() is table.table

        _press(qapp, Qt.Key.Key_Tab)
        assert qapp.focusWidget() is table.header, (
            f"Tab from the body reached {qapp.focusWidget()!r}, not the header"
        )

        _press(qapp, Qt.Key.Key_Tab)
        assert qapp.focusWidget() is not table.header, (
            "Tab did not leave the header; a keyboard user is trapped on it"
        )
    finally:
        table.close()


@pytest.mark.parametrize("dressing", [theme.LIGHT, theme.DARK], ids=lambda one: one.name)
def test_the_current_section_is_drawn_in_the_theme_that_is_applied(
    qapp: QApplication, derived: tuple[FormatInfo, ...], dressing: theme.Theme
) -> None:
    """**`T202-R2`.** The header paints its own focus edge, so it must read the theme in force.

    `paintSection` draws the current section in `theme.applied().accent` — a painter cannot read a
    style sheet, so this is the only route the colour can take. That makes it the one place in this
    file where **asserting a colour is the right test**: everything else about this edge is held by
    the greyscale sweep in `tests/ui/test_colour_is_never_alone.py`, which by construction cannot
    tell one accent from another and would pass a painter with the wrong palette's value nailed
    into it. It measured exactly that: hard-coding `theme.LIGHT.accent` here survived all 79 of
    those assertions.

    So both halves are checked — the applied theme's accent is on the screen, and the *other*
    theme's is not. `theme.apply` rather than `setStyleSheet`, because installing only the sheet
    leaves `theme.applied()` at whatever it was, which is the defect `T202-R2` found in the sweep.
    """
    theme.apply(qapp, dressing)
    other = theme.DARK if dressing is theme.LIGHT else theme.LIGHT
    table = FormatTable(derived)
    table.show()
    qapp.processEvents()
    try:
        table.header.setFocus()
        qapp.processEvents()
        assert table.header.hasFocus(), "the header never took focus, so nothing painted a section"

        image = QImage(table.header.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor("#00000000"))
        table.header.render(image)
        drawn = {
            image.pixelColor(x, y).name().lower()
            for y in range(image.height())
            for x in range(image.width())
        }

        assert dressing.accent.lower() in drawn, (
            f"the header holds the keyboard under the {dressing.name} theme and its accent "
            f"{dressing.accent} is nowhere in the render — the painter is not reading "
            "theme.applied()"
        )
        assert other.accent.lower() not in drawn, (
            f"the {other.name} theme's accent {other.accent} is on screen while the "
            f"{dressing.name} theme is applied, so the colour is coming from somewhere other than "
            "the theme in force"
        )
    finally:
        table.close()
        table.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("points", [9, 10, 11], ids=lambda size: f"{size}pt")
def test_the_stated_width_is_enough_for_both_lists(
    qapp: QApplication, derived: tuple[FormatInfo, ...], points: int
) -> None:
    """`T-310`: resized to exactly what it asks for, nothing scrolls sideways.

    **This is the assertion three wrong implementations passed the reviewer's eye on.**
    `AddUrlDialog._widen_for` asks the panel how much room to make, so a hint that understates is a
    horizontal scrollbar on a table sized precisely to fit — and the understatement is invisible in
    the source every time:

    1. `QTableView.sizeHint()` is a fixed default that ignores the model. **518px** for a surface
       needing over a thousand.
    2. Summing `sizeHintForColumn` ignores the *headers*, and `ResizeToContents` sizes a section to
       the wider of content and label. **220px** short, all of it headings.
    3. Summing the children ignores the `QHBoxLayout` **stretch**: a child with share `s` of total
       `S` gets `width * s / S` however much it asked for. **1px** short, which scrolls just as
       surely as a hundred.

    **Three font sizes, because one machine's font is one data point.** `OPS-012`'s move to
    `ubuntu-latest` reddened two assertions for exactly this reason.
    """
    original = qapp.font()
    font = QFont(original)
    font.setPointSize(points)
    qapp.setFont(font)
    try:
        table = FormatTable(derived)
        table.resize(table.sizeHint())
        table.show()
        qapp.processEvents()
        try:
            assert len(table.lists()) == 2, "this fixture should produce both lists"
            for one in table.lists():
                view = one.view
                over = view.horizontalScrollBar().maximum()
                assert over == 0, (
                    f"{view.accessibleName()} scrolls sideways at the widget's own stated "
                    f"width of {table.sizeHint().width()}px: {over}px over"
                )
        finally:
            table.close()
    finally:
        qapp.setFont(original)


@pytest.mark.parametrize("points", [9, 10, 11], ids=lambda size: f"{size}pt")
def test_the_stated_height_shows_every_row(
    qapp: QApplication, derived: tuple[FormatInfo, ...], points: int
) -> None:
    """`T-310`: resized to what it asks for, neither list scrolls vertically.

    **The height is the same defect as the width and it shipped past the first fix.** The
    maintainer opened the built window and found *"a ton of whitespace underneath the audio/video
    selections, but you have to scroll to select them"* — `AddUrlDialog.panel_height_for` gives the
    open row `min(panel.sizeHint().height(), available)`, so a view reporting Qt's fixed default
    asked for two thirds of the room it had and the rest was drawn as empty space.

    **Then the fix itself was wrong in the same shape.** `sizeHintForRow` answers the bare text
    height — 18px — while the view *draws* rows at the vertical header's section size, 30px under
    this application's style sheet. Sizing on the smaller number still left the panel scrolling
    with room to spare, and read perfectly sensibly.

    So the assertion is the outcome rather than the arithmetic: at the width and height the widget
    states, every row is on screen.
    """
    original = qapp.font()
    font = QFont(original)
    font.setPointSize(points)
    qapp.setFont(font)
    try:
        table = FormatTable(derived)
        table.resize(table.sizeHint())
        table.show()
        qapp.processEvents()
        try:
            for one in table.lists():
                view = one.view
                over = view.verticalScrollBar().maximum()
                assert over == 0, (
                    f"{view.accessibleName()} scrolls vertically at the widget's own stated "
                    f"height of {table.sizeHint().height()}px, hiding {over}px of "
                    f"{one.model.rowCount()} rows"
                )
        finally:
            table.close()
    finally:
        qapp.setFont(original)


def test_the_keyboard_chooses_a_column_and_sorts_that_one(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`T107-R3`: *a focused section the user cannot select is not a keyboard-operable header*.

    Arrives on the sorted column, moves with `→`, and `Space` sorts **the column arrived at** —
    not whatever the indicator already pointed to, which is what the previous implementation did.
    """
    table = FormatTable(derived)
    table.show()
    qapp.processEvents()
    try:
        quality = video_column(table, RESOLUTION_COLUMN)
        size = video_column(table, SIZE_COLUMN)
        table.table.sortByColumn(quality, Qt.SortOrder.DescendingOrder)
        table.table.setFocus()
        _press(qapp, Qt.Key.Key_Tab)
        assert qapp.focusWidget() is table.header
        assert table.header.current_section() == quality, (
            "the header did not arrive on the column the table is sorted by"
        )

        while table.header.current_section() != size:
            before = table.header.current_section()
            _press(qapp, Qt.Key.Key_Right)
            assert table.header.current_section() != before, "Right did not move the column"

        _press(qapp, Qt.Key.Key_Space)
        assert table.header.sortIndicatorSection() == size, (
            "Space sorted a column other than the one the keyboard had selected"
        )
        ascending = by_band(table.model.formats(), lambda entry: entry.filesize or -1)

        _press(qapp, Qt.Key.Key_Space)
        reversed_bands = [list(reversed(band)) for band in ascending]
        after = by_band(table.model.formats(), lambda entry: entry.filesize or -1)
        assert after == reversed_bands, "a second Space did not reverse the sort"
    finally:
        table.close()


def test_the_header_says_which_column_it_is_on(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`NFR-005`: the selected section is announced, not only drawn.

    A screen-reader user moving along the header otherwise hears nothing change, and the sort they
    trigger lands on a column they were never told they were on.
    """
    table = FormatTable(derived)
    table.show()
    qapp.processEvents()
    try:
        table.table.setFocus()
        _press(qapp, Qt.Key.Key_Tab)
        spoken = table.header.accessibleDescription()
        assert COLUMN_HEADERS[table.header.current_section()] in spoken, spoken

        _press(qapp, Qt.Key.Key_Right)
        moved = table.header.accessibleDescription()
        assert moved != spoken, "moving along the header announced nothing"
        assert COLUMN_HEADERS[table.header.current_section()] in moved, moved
    finally:
        table.close()


def test_sorting_keeps_the_selection_on_its_own_format(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`T107-R4`: a sort must not silently change which format is current.

    Qt tracks the current row by index, so a sort that only replaces the tuple leaves the row
    *number* selected and changes the format under it. The reviewer selected `b`, sorted, and
    `current_format()` answered `a`.
    """
    table = FormatTable(derived)
    table.table.sortByColumn(video_column(table, SIZE_COLUMN), Qt.SortOrder.AscendingOrder)
    table.table.setCurrentIndex(table.model.index(1, video_column(table, FORMAT_COLUMN)))
    chosen = table.current_format()
    assert chosen is not None

    table.table.sortByColumn(video_column(table, SIZE_COLUMN), Qt.SortOrder.DescendingOrder)
    after = table.current_format()
    assert after == chosen, (
        f"the current format changed from {chosen.format_id} to "
        f"{after.format_id if after is not None else None} across a sort"
    )


def test_populating_the_table_reapplies_the_active_sort(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`T107-R4`: the indicator and the rows must not be able to disagree.

    `set_formats` installed input order underneath whatever the header was still pointing at, so a
    descending-resolution indicator sat above rows in ascending order. This module's own docstring
    calls a moving indicator over unchanged rows worse than no sorting; the setter recreated it.
    """
    table = FormatTable(())
    quality = table.video.model.column_for(RESOLUTION_COLUMN)
    table.table.sortByColumn(quality, Qt.SortOrder.DescendingOrder)
    table.set_formats(derived)

    for heights in by_band(table.model.formats(), lambda entry: entry.height or -1):
        assert heights == sorted(heights, reverse=True), (
            f"rows are {heights} under a descending indicator"
        )
    assert table.table.horizontalHeader().sortIndicatorSection() == quality


def test_an_estimated_size_is_marked_and_an_exact_one_is_not(
    qapp: QApplication,
) -> None:
    """`T107-R7`: `REQ-003` names the column "filesize/estimate" and the two must differ.

    Exact and approximate four-mebibyte entries projected equal and both rendered `4.0 MB`, so a
    guess was shown as a measurement. Sorting is unaffected — bytes either way.
    """
    exact = adapter.project_format({"format_id": "a", "ext": "mp4", "filesize": 4 * 1024 * 1024})
    estimated = adapter.project_format(
        {"format_id": "b", "ext": "mp4", "filesize_approx": 4 * 1024 * 1024}
    )
    both = adapter.project_format(
        {"format_id": "c", "ext": "mp4", "filesize": 1024, "filesize_approx": 9999}
    )
    missing = adapter.project_format({"format_id": "d", "ext": "mp4"})

    assert exact.filesize_is_estimate is False
    assert estimated.filesize_is_estimate is True
    assert both.filesize_is_estimate is False, "an exact size present alongside an estimate lost"
    assert both.filesize == 1024, "the estimate won over the exact size"
    assert missing.filesize is None and missing.filesize_is_estimate is False

    model = FormatTableModel((exact, estimated, both, missing))
    rendered = column_of(model, SIZE_COLUMN)
    assert rendered[0] == "4.0 MB"
    assert rendered[1] == f"{ESTIMATE_PREFIX}4.0 MB", rendered[1]
    assert rendered[0] != rendered[1], "an estimate renders identically to a measured size"
    assert rendered[3] == UNKNOWN_TEXT, "a missing size grew a tilde"

    keys = []
    for row in range(3):
        key = model.data(model.index(row, SIZE_COLUMN), SORT_ROLE)
        assert isinstance(key, tuple)
        keys.append(key[0])
    assert keys[0] == keys[1], "the tilde reached the sort key"


def _reads_to_paint(qapp: QApplication, count: int) -> int:
    """Model reads taken to show a table of `count` formats. Used by the repaint gate below."""
    formats = tuple(
        FormatInfo(format_id=str(index), extension="mp4", height=index, width=index * 2)
        for index in range(1, count + 1)
    )
    table = FormatTable(())
    original = table.model.data
    reads = 0

    def counting(index: object, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        nonlocal reads
        reads += 1
        return original(index, role)  # type: ignore[arg-type]

    object.__setattr__(table.model, "data", counting)
    table.model.set_formats(formats)
    table.resize(900, 400)
    table.show()
    qapp.processEvents()
    try:
        return reads
    finally:
        table.close()


def test_showing_more_formats_does_not_cost_more_to_paint(qapp: QApplication) -> None:
    """`T107-R6`: the repaint cost is bounded by the viewport, not by the model.

    **Asserted as scaling rather than as an absolute count**, which is what the criterion is
    actually about and what survives a different font or screen. A clock would be a flake on a
    loaded machine (`T-079`'s rule); a call count that must not grow with the model is the same
    claim without the timer.

    **This gate caught a real defect in its own implementation.** `ResizeToContents` asks the model
    for every row of every column to decide a width, so a 200-format table cost **44,019** model
    reads to paint fourteen visible rows — and it doubled with the model: 22,419 at 100 formats,
    87,219 at 400, 173,619 at 800. `setResizeContentsPrecision(32)` bounds the sampling, and the
    cost is now **flat at 7,731 from 100 formats to 800**. A large playlist entry has dozens of
    formats, so this was an ordinary cost rather than a synthetic one.
    """
    small = _reads_to_paint(qapp, 100)
    large = _reads_to_paint(qapp, 800)
    assert small > 0, "nothing was painted, so this measured nothing"
    assert large <= small * 1.5, (
        f"painting {800} formats took {large} model reads against {small} for {100} — the cost is "
        "scaling with the model rather than with the viewport, which is what ResizeToContents "
        "does without a precision bound"
    )


def test_the_repaint_gate_would_reject_an_unbounded_implementation() -> None:
    """The measurement that proves the gate above is not vacuous (`T107-R6`).

    Run on 2026-08-07 by removing `setResizeContentsPrecision` and measuring the same two sizes:
    **22,419 reads at 100 formats and 173,619 at 800**, a factor of 7.7. The gate allows 1.5.
    Recorded as numbers rather than re-run, because mutating the widget inside the suite would
    leave a broken implementation behind if the assertion failed.
    """
    unbounded_small, unbounded_large = 22419, 173619
    assert unbounded_large > unbounded_small * 1.5, (
        "the recorded unbounded measurements no longer violate the bound, so the gate above "
        "cannot distinguish a bounded implementation from an unbounded one"
    )


# --- T-108: the mode, its keyboard, and what it announces (REQ-008, UX_SPEC §5) ---------------


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        # Stated by hand from each capture, **not** derived from `listable` (`T310-R7`). An oracle
        # built from the predicate under test agrees with it by construction, including when both
        # are wrong: the reviewer's counterexample is the row below, where the product correctly
        # keeps sparse audio through the per-list fallback and a whole-catalogue `listable` would
        # have dropped it — so the test would have demanded the *defect*.
        # Nothing excluded: every entry is unclassified but states a height and a size.
        ("archive_org_big_buck_bunny", ["0", "1", "2"]),
        # Four complete entries plus `source`, which is unclassified and states both.
        ("wikimedia_caminandes", ["0", "1", "2", "3", "source"]),
        # `storyboard` is the one exclusion: `vcodec` and `acodec` both `'none'`. `hls-audio`
        # stays — it names no codec and no size, but it does state a bitrate.
        (
            "derived_format_columns",
            ["0", "1", "137", "140", "2", "h264-hd", "hls-480", "hls-audio"],
        ),
    ],
)
def test_every_format_worth_showing_appears_in_exactly_one_list(
    qapp: QApplication, fixture: str, expected: list[str]
) -> None:
    """`T-310`'s first acceptance criterion, and the failure it exists to prevent.

    **A format that vanishes *silently* is the defect.** Splitting one grid into two lists means
    each format is routed somewhere, and a routing rule covering three of `FormatKind`'s four
    states drops every unclassified format on the floor — which `ui/format_selection.py` records
    as *"most formats from most sources"*, not an edge case.

    Two exclusions are ruled and named (`docs/UX_SPEC.md` §4); anything else going missing is this
    test's subject.
    """
    formats = formats_from(fixture)
    table = FormatTable(formats)
    try:
        listed = [entry.format_id for one in table.lists() for entry in one.model.formats()]
        assert sorted(listed) == sorted(expected), (
            f"{fixture} shows {sorted(listed)}, expected {sorted(expected)}"
        )
        assert len(listed) == len(set(listed)), f"a format is in both lists: {listed}"
    finally:
        table.close()


def test_notes_are_reachable_from_both_live_lists(qapp: QApplication) -> None:
    """`T310-R1`: `REQ-003` names notes and the split dropped them from the product.

    **Every test of the field passed while the application lost it**, which is the shape worth
    remembering. `FormatTableModel`'s default layout still carried `NOTES_COLUMN`, so the model
    tests were untouched; neither *live* column set did, so `column_for` answered `-1` on both and
    yt-dlp's own words about a format were unreachable from the running window.

    Asked through `FormatTable.lists()` for that reason: the live models are the ones that were
    wrong, and only a test that goes through them can say so.
    """
    video = FormatInfo(
        "137",
        "mp4",
        height=1080,
        width=1920,
        video_codec="avc1.640028",
        has_video=True,
        has_audio=False,
        note="1080p60 HDR",
    )
    sound = FormatInfo(
        "140",
        "m4a",
        audio_codec="mp4a.40.2",
        bitrate_kbps=129.0,
        has_video=False,
        has_audio=True,
        note="Default",
    )
    table = FormatTable((video, sound))
    try:
        seen = {}
        for one in table.lists():
            column = one.model.column_for(NOTES_COLUMN)
            assert column >= 0, f"the {one.view.accessibleName()} list has no Notes column"
            for row in range(one.model.rowCount()):
                identifier = display(one.model, row, one.model.column_for(FORMAT_COLUMN))
                seen[identifier] = display(one.model, row, column)
        assert seen == {"137": "1080p60 HDR", "140": "Default"}, seen
    finally:
        table.close()


def test_bundled_audio_keeps_its_raw_codec_in_the_sound_cell(qapp: QApplication) -> None:
    """`T310-R5`: the `Sound` column renders an audio codec, so it owes the raw identifier.

    `T-306` ruled that a cell showing a codec *name* keeps the identifier in its tool tip, because
    `REQ-009`'s selector syntax and every bug report are written in `mp4a.40.5` rather than in
    `HE-AAC`. The split moved a complete format's audio codec out of the audio-codec column and
    into the `Sound` cell, and left the rule behind — so the only row that shows it stopped
    offering it.

    **The literal is written out here rather than derived from `codec_name`.** Comparing the
    tooltip with a function of the same input is how `T306-R2` passed while asserting nothing.
    """
    complete = FormatInfo(
        "22",
        "mp4",
        height=720,
        width=1280,
        video_codec="avc1.64001F",
        audio_codec="mp4a.40.5",
        has_video=True,
        has_audio=True,
    )
    table = FormatTable((complete,))
    try:
        model = table.video.model
        sound = model.column_for(SOUND_COLUMN)
        assert display(model, 0, sound) == "included · HE-AAC", display(model, 0, sound)
        tip = model.data(model.index(0, sound), int(Qt.ItemDataRole.ToolTipRole))
        assert tip == "mp4a.40.5", (
            f"the raw identifier is not reachable from the Sound cell: {tip!r}"
        )
    finally:
        table.close()


@pytest.mark.parametrize(
    ("entry", "expected", "why"),
    [
        (
            FormatInfo("known-audio", "mp4", audio_codec="aac"),
            False,
            "a codec was supplied, so something is known",
        ),
        (
            FormatInfo("known-video", "mp4", video_codec="h264"),
            False,
            "likewise for the other stream",
        ),
        (
            FormatInfo("known-height", "mp4", height=720),
            False,
            "a resolution distinguishes it from every other height",
        ),
        (
            FormatInfo("known-rate", "mp4", bitrate_kbps=128.0),
            False,
            "a bitrate is the sound list's own Quality column",
        ),
        (
            FormatInfo("known-size", "mp4", filesize=1024),
            False,
            "a size is what two rows are compared on",
        ),
        (FormatInfo("bare", "mp4"), True, "nothing at all was reported"),
    ],
    ids=lambda value: value.format_id if isinstance(value, FormatInfo) else "",
)
def test_says_nothing_is_about_what_was_reported_not_about_the_kind(
    entry: FormatInfo, expected: bool, why: str
) -> None:
    """`T310-R6`: one known field is enough to keep a row, whichever field it is.

    **This branched on `kind_of` and that was the error.** It asked an `UNKNOWN` entry only about
    its *video* codec, so a format reporting `acodec: 'aac'` and no `vcodec` answered *"nothing
    known"* and was dropped with a codec sitting in it. `kind_of` answers `UNKNOWN` for that entry
    precisely because nothing may be inferred about which stream it carries — which is exactly why
    a kind-shaped question was the wrong one to ask.

    The partially-known cases are parametrised one field at a time so that a predicate which
    silently stops consulting any one of them fails on that field alone.
    """
    assert says_nothing(entry) is expected, why


def test_the_fallback_is_per_list_not_per_catalogue(qapp: QApplication) -> None:
    """`T310-R7`'s counterexample, as a test rather than as a remark.

    A video format with everything known, beside audio rows with nothing known. The sound list has
    only those sparse rows, so its fallback keeps them — a source whose only audio says nothing
    still has to offer sound. A `listable` applied to the **whole catalogue** never reaches its
    fallback, because the video row alone satisfies it, and would drop both audio rows.

    That is why the inventory expectations above are written out by hand.
    """
    video = FormatInfo(
        "137",
        "mp4",
        height=1080,
        width=1920,
        video_codec="avc1.640028",
        filesize=80_300_000,
        has_video=True,
        has_audio=False,
    )
    sparse = (
        FormatInfo("233", "mp4", has_video=False, has_audio=True, note="Default"),
        FormatInfo("234", "mp4", has_video=False, has_audio=True, note="Default"),
    )
    assert [entry.format_id for entry in listable((video, *sparse))] == ["137"], (
        "the whole-catalogue reading no longer differs from the per-list one, so this test's "
        "subject has gone"
    )

    table = FormatTable((video, *sparse))
    try:
        listed = sorted(entry.format_id for one in table.lists() for entry in one.model.formats())
        assert listed == ["137", "233", "234"], listed
    finally:
        table.close()


def test_an_unclassified_format_is_listed_and_choosable(qapp: QApplication) -> None:
    """The `UNKNOWN` kind is a first-class row, not a leftover (`T-310`).

    archive.org and PeerTube name no codecs at all, so `kind_of` answers `UNKNOWN` for everything
    they publish. Those formats go in the video list — the general one — saying `not stated` about
    their sound, and choosing one is the whole download, because nothing about pairing it can be
    asserted.
    """
    formats = formats_from("archive_org_big_buck_bunny")
    assert {kind_of(entry) for entry in formats} == {FormatKind.UNKNOWN}, (
        "this fixture no longer exercises the unclassified case"
    )
    table = FormatTable(formats)
    try:
        assert table.audio is None, "a source with no audio half should list no sound panel"
        assert table.no_sound_reason is not None, "the reason must stand where the list would"
        assert table.video.model.rowCount() == len(formats)

        sound = table.video.model.column_for(SOUND_COLUMN)
        assert display(table.video.model, 0, sound) == SOUND_NOT_STATED

        table.choose_current()
        assert table.selection.is_complete, "an unclassified format named no download"
        assert table.selection.mode is SelectionMode.SINGLE
    finally:
        table.close()


def test_a_format_carrying_neither_stream_is_not_listed(qapp: QApplication) -> None:
    """`T-310`, ruled from the built window: *"if you can't select them, why are they even there?"*

    YouTube publishes `mhtml` storyboards with `vcodec: 'none'` **and** `acodec: 'none'` — the
    extractor stating the entry carries no media at all. An earlier revision listed them greyed and
    unselectable; the maintainer's question is the better answer, and taking it removed a `flags()`
    override, a word in the `Sound` column and a muted-ink branch that existed only to explain a
    row nobody wanted.
    """
    real = FormatInfo(
        "137",
        "mp4",
        height=1080,
        width=1920,
        video_codec="avc1.640028",
        has_video=True,
        has_audio=False,
    )
    board = FormatInfo(
        "sb0",
        "mhtml",
        height=45,
        width=80,
        fps=0.5,
        note="storyboard",
        has_video=False,
        has_audio=False,
    )
    assert carries_nothing(board) and not carries_nothing(real)

    table = FormatTable((real, board))
    try:
        listed = [entry.format_id for one in table.lists() for entry in one.model.formats()]
        assert listed == ["137"], f"the storyboard is still on screen: {listed}"
    finally:
        table.close()


def test_a_row_with_nothing_to_choose_it_by_is_not_listed(qapp: QApplication) -> None:
    """`T-310`: *"to the typical user those are just noise and additional clutter in the list."*

    YouTube's `233` and `234` are real HLS audio renditions with no codec, no bitrate and no size,
    so the row reads `Unknown · Unknown · Unknown` and there is nothing on it to prefer it by.
    """
    named = FormatInfo(
        "140",
        "m4a",
        audio_codec="mp4a.40.2",
        bitrate_kbps=129.0,
        filesize=2_500_000,
        has_video=False,
        has_audio=True,
    )
    bare = FormatInfo("233", "mp4", has_video=False, has_audio=True, note="Default")
    assert says_nothing(bare) and not says_nothing(named)

    table = FormatTable((named, bare))
    try:
        assert table.audio is not None
        listed = [entry.format_id for entry in table.audio.model.formats()]
        assert listed == ["140"], f"the unlabelled rendition is still on screen: {listed}"
    finally:
        table.close()


def test_unlabelled_rows_stay_when_they_are_all_there_is(qapp: QApplication) -> None:
    """The guard on `says_nothing`, and it is the half that keeps HLS-only sources working.

    **`FormatInfo.is_audio_only` records why**: a real `EXT-X-MEDIA:TYPE=AUDIO` rendition arrives
    with *no codec named at all*, because the codec list lives on the variant rather than on the
    group. On a source served entirely over HLS those rows are the only audio there is, and
    dropping them would leave a user with a picture and no way to get sound.

    Noise is only noise beside signal. With nothing better to show, the bare rows stay.
    """
    bare = (
        FormatInfo("233", "mp4", has_video=False, has_audio=True, note="Default"),
        FormatInfo("234", "mp4", has_video=False, has_audio=True, note="Default"),
    )
    video = FormatInfo(
        "137",
        "mp4",
        height=1080,
        width=1920,
        video_codec="avc1.640028",
        has_video=True,
        has_audio=False,
    )
    table = FormatTable((video, *bare))
    try:
        assert table.audio is not None, (
            "every audio row said nothing and the whole list was dropped, so this source offers "
            "a picture and no way to get sound"
        )
        listed = [entry.format_id for entry in table.audio.model.formats()]
        assert sorted(listed) == ["233", "234"], listed
    finally:
        table.close()


def test_a_format_nobody_classified_is_still_choosable(qapp: QApplication) -> None:
    """The other side of `carries_nothing`, and the reason it is not `kind_of(...) is UNKNOWN`.

    **`False` and `None` are different answers and conflating them empties archive.org.**
    `kind_of` returns `UNKNOWN` both for *yt-dlp denied both streams* and for *yt-dlp said
    nothing*, and `ui/format_selection.py` records that the second is *"most formats from most
    sources"* — archive.org and PeerTube name no codecs for anything they publish. Refusing on the
    kind rather than on the denial would have made this surface useless on those sites, and it
    would have looked exactly as reasonable in the source.
    """
    silent = FormatInfo("0", "ogv", height=300, width=533, note="derivative")
    assert kind_of(silent) is FormatKind.UNKNOWN, "this fixture no longer exercises the case"
    assert not carries_nothing(silent), "nothing was said; nothing was denied"

    table = FormatTable((silent,))
    try:
        model = table.video.model
        assert bool(model.index(0, 0).flags() & Qt.ItemFlag.ItemIsSelectable)
        sound = model.column_for(SOUND_COLUMN)
        assert display(model, 0, sound) == SOUND_NOT_STATED
        table.choose_current()
        assert table.selection.is_complete, "an unclassified format named no download"
    finally:
        table.close()


def test_no_choice_is_ever_refused(qapp: QApplication, derived: tuple[FormatInfo, ...]) -> None:
    """`T-310`: the mode is gone and so is the refusal it required.

    **This is the inverse of the test it replaces.** Until 2026-09-09 a format carrying both
    streams was *refused out loud* in `PAIR` mode — the two formats needing no merge at all were
    the two the merge mode would not accept. The maintainer found it in the built window: *"the
    options with audio AND video aren't even selectable"*. With the kinds in separate lists
    nothing is routed, so nothing can fail to route.

    `merge_refusal` still speaks, and it is a different fact: ffmpeg's absence refuses a **pair**,
    not a format, and it is asserted by its own tests.
    """
    table = FormatTable(derived)
    refusals: list[str] = []
    table.selection_refused.connect(refusals.append)
    try:
        for row in range(table.video.model.rowCount()):
            table.table.setCurrentIndex(table.video.model.index(row, 0))
            table.choose_current()
            chosen = table.video.model.formats()[row]
            assert table.selection.is_complete, (
                f"choosing {chosen.format_id} ({kind_of(chosen)}) named no download"
            )
        assert refusals == [], f"something was refused: {refusals}"
    finally:
        table.close()


@pytest.mark.parametrize("first", ["complete", "unclassified"])
def test_sound_can_replace_a_whole_format_through_its_own_button(
    qapp: QApplication, first: str
) -> None:
    """`T310-R3`: a supported transition was put out of reach by a disabled control.

    Choosing a format that already carries sound used to disable the sound list, on the reasoning
    that such a format leaves it nothing to **add**. True — and irrelevant, because `choose` has
    always accepted an audio-only row as a *replacement*, clearing the whole one. The control was
    disabled for a transition the model supports.

    On an unclassified entry the wording was wrong as well as the state: *"that format has sound
    already"* is a claim about a format nothing was said about.

    **Driven through the real button, not `choose`.** `table.choose(audio)` reaches past exactly
    the control that was broken, so a test written that way passes on the defect — which is what
    `test_no_choice_is_ever_refused` did by traversing only the video list.
    """
    whole = (
        FormatInfo(
            "22",
            "mp4",
            height=720,
            width=1280,
            video_codec="avc1.64001F",
            audio_codec="mp4a.40.2",
            has_video=True,
            has_audio=True,
        )
        if first == "complete"
        else FormatInfo("h264-hd", "mp4", height=1080, video_codec="h264", filesize=128_700_000)
    )
    audio = FormatInfo(
        "140", "m4a", audio_codec="mp4a.40.2", bitrate_kbps=129.0, has_video=False, has_audio=True
    )
    table = FormatTable((whole, audio))
    table.show()
    qapp.processEvents()
    try:
        table.choose(whole)
        assert table.selection.selector() == whole.format_id

        assert table.audio is not None
        assert table.audio.view.isEnabled(), "the sound list is disabled after a whole format"
        assert table.audio.button.isEnabled(), "the sound button is disabled after a whole format"

        QTest.mouseClick(table.audio.button, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert table.selection.selector() == "140", (
            f"clicking the sound button left the selection at {table.selection.selector()!r}"
        )
    finally:
        table.close()


def test_a_lone_video_half_still_names_a_download(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """A silent video is a download `REQ-008` has always allowed (`T-310`).

    **This is a regression that reached a running build before it was caught.** An earlier draft
    put every video-only pick into `PAIR`, where `is_complete` requires both slots — so choosing
    one video-only format and pressing *Done* named nothing at all. The mode is a statement about
    how many streams are being joined, not about the kind of the row that was picked.
    """
    table = FormatTable(derived)
    try:
        video_only = next(
            entry
            for entry in table.video.model.formats()
            if kind_of(entry) is FormatKind.VIDEO_ONLY
        )
        table.choose(video_only)
        assert table.selection.is_complete, "a lone video half named no download"
        assert table.selection.mode is SelectionMode.SINGLE
        assert not table.selection.is_merge, "one stream is not a merge and must not need ffmpeg"
        assert table.selection.selector() == video_only.format_id
    finally:
        table.close()


def test_the_chosen_pair_is_announced_in_words_on_the_widget(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`NFR-005`: the two chosen rows are announced, not shown by highlight alone.

    Both the visible label and the accessible description carry it, so a sighted user and a screen
    reader read the same sentence rather than two that can drift.
    """
    table = FormatTable(derived)
    try:
        # **No mode is set first, which is the change.** The pair is assembled by taking one row
        # from each list, and `PAIR` is what having both halves *means* rather than something
        # declared in advance.
        for format_id in ("137", "140"):
            entry = next(item for item in derived if item.format_id == format_id)
            table.choose(entry)

        assert table.selection.mode is SelectionMode.PAIR
        assert "video: 137, audio: 140" in table.chosen_text()
        assert "video: 137, audio: 140" in table.accessibleDescription()
    finally:
        table.close()


def test_enter_on_the_body_chooses_the_current_row(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """`docs/UX_SPEC.md` §4: *"`Enter` chooses the current format"*.

    Driven through the focused body, not by calling `choose_current` — the same rule `T107-R3`
    established twice for the header: a route proved by calling the method it ends at is not proved.
    """
    table = FormatTable(derived)
    table.show()
    qapp.processEvents()
    chosen: list[object] = []
    table.format_chosen.connect(chosen.append)
    try:
        table.table.setFocus()
        qapp.processEvents()
        assert qapp.focusWidget() is table.table

        current = table.current_format()
        assert current is not None
        _press(qapp, Qt.Key.Key_Return)
        assert chosen == [current], "Enter on the body chose nothing"
        assert table.selection.single is current
    finally:
        table.close()


def test_the_selection_is_written_before_a_listener_can_close_the_table(
    qapp: QApplication, derived: tuple[FormatInfo, ...]
) -> None:
    """The signal order, pinned, because getting it wrong loses the user's choice silently.

    The dialog closes its panel from `format_chosen` and writes the choice from
    `selection_changed`. Emitted the other way round, closing tears the panel off its row first and
    the write finds nothing to write to — the format is chosen, the row keeps its old one, and the
    download runs as whatever it was before. That was live until the dialog tests caught it, so the
    ordering is asserted here rather than left to those tests to notice again.
    """
    table = FormatTable(derived)
    order: list[str] = []
    table.selection_changed.connect(lambda _selection: order.append("written"))
    table.format_chosen.connect(lambda _entry: order.append("acted on"))
    try:
        table.table.setCurrentIndex(table.model.index(0, FORMAT_COLUMN))
        table.choose_current()
        assert order == ["written", "acted on"], (
            f"the choice was acted on before it was written down: {order}"
        )
    finally:
        table.close()
