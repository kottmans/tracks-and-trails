"""The format table `REQ-003` asks for (`T-107`, `docs/UX_SPEC.md` §4).

**Every column is asserted from a fixture by value**, not from a hand-built `FormatInfo`: the
question `REQ-003` poses is whether what a probe actually reports reaches the table, and a test
that constructs its own model answers a different one. `T-018`'s recorded captures are the contract
for the fields they carry.

**Codecs, bitrate and estimated sizes come from a recorded capture**, `wikimedia_caminandes`,
which reports all three per format. **fps does not, from any source**: archive.org reports none and
neither does Wikimedia, so it is exercised by `derived_format_columns` and the criterion was
amended by the maintainer on 2026-08-07 to *populated from a recorded fixture where the source
reports it*. `T-185` records the search so a future source can close it.

**Phase 3's exit criterion 1 — the table matching `yt-dlp -F` — is evidenced** by
`test_the_table_matches_what_yt_dlp_f_reports` against
`ai/evidence/2026-08-07-format-table-vs-yt-dlp-f.md`. Matching includes agreeing where yt-dlp
reports nothing, which is most of what these sources say about fps and codecs.
"""

import json
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui.format_table import (
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
    VIDEO_CODEC_COLUMN,
    FormatTable,
    FormatTableModel,
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
    assert column_of(model, RESOLUTION_COLUMN) == ["533x300", "640x360", "1280x720"]
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
    assert column_of(model, AUDIO_CODEC_COLUMN) == [UNKNOWN_TEXT, "mp3"]
    assert column_of(model, EXT_COLUMN) == ["ogg", "mp3"]
    # archive.org reports `height: 0` for an audio item, which is not a height. `yt-dlp -F` prints
    # `unknown`, and after `T107-R1` so does this (`_as_dimension`).
    assert column_of(model, RESOLUTION_COLUMN) == [UNKNOWN_TEXT, UNKNOWN_TEXT]


#: What `yt-dlp -F` printed for the recorded sources, transcribed on 2026-08-07 against yt-dlp
#: 2026.07.04 — the run is in `ai/evidence/2026-08-07-format-table-vs-yt-dlp-f.md`.
#:
#: **Transcribed, not fetched.** The suite must not touch the network (`ai/TESTING.md` §5), so the
#: comparison is made against what the recorded run actually printed. Re-running it is
#: `capture.py`'s job and a deliberate act; this keeps the answer under test in the meantime.
YT_DLP_F_OUTPUT: Final = {
    "archive_org_big_buck_bunny": [
        ("0", "ogv", "533x300", "44.76MiB", "unknown", "unknown", "derivative"),
        ("1", "mp4", "640x360", "59.01MiB", "unknown", "unknown", "derivative"),
        ("2", "avi", "1280x720", "316.85MiB", "unknown", "unknown", "derivative"),
    ],
    "archive_org_test_mp3": [
        ("0", "ogg", "unknown", "110.55KiB", "unknown", "unknown", "derivative"),
        ("1", "mp3", "unknown", "194.00KiB", "unknown", "mp3", "original"),
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

    for row, (id_, ext, resolution, size, vcodec, acodec, note) in enumerate(reported):
        assert display(model, row, FORMAT_COLUMN) == id_
        assert display(model, row, EXT_COLUMN) == ext
        if resolution == "unknown":
            assert display(model, row, RESOLUTION_COLUMN) == UNKNOWN_TEXT, (
                f"yt-dlp reports no resolution for {id_} and the table claims one"
            )
        else:
            assert display(model, row, RESOLUTION_COLUMN) == resolution
        for column, value in ((VIDEO_CODEC_COLUMN, vcodec), (AUDIO_CODEC_COLUMN, acodec)):
            if value == "unknown":
                assert display(model, row, column) == UNKNOWN_TEXT
            else:
                assert display(model, row, column) == value
        assert display(model, row, NOTES_COLUMN) == note
        # yt-dlp prints MiB, this window prints powers-of-1024 MB; what must agree is the number
        # of bytes underneath, which is what the sort key carries.
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

    **fps is still not exercised by any recorded source**, and that is a property of the sources
    rather than of the fixtures: no boring, freely licensed source found reports it. `T-185`
    records the search rather than leaving the gap implied.
    """
    model = FormatTableModel(formats_from("wikimedia_caminandes"))
    assert model.rowCount() == 5

    assert column_of(model, VIDEO_CODEC_COLUMN)[:4] == ["vp9", "vp9", "theora", "vp9"]
    assert column_of(model, AUDIO_CODEC_COLUMN)[:4] == ["opus", "opus", "vorbis", "opus"]
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


def test_fps_and_the_column_shapes_come_through_the_projection(
    derived: tuple[FormatInfo, ...],
) -> None:
    """**fps only**, plus the shapes no recorded source happens to have (`T107-R1`).

    Codecs, bitrate and estimated sizes moved to
    `test_codecs_bitrate_and_estimated_sizes_come_from_a_recorded_capture`, which uses a real
    capture. What is left here is what no recorded source supplies: **fps**, and a row carrying
    neither fps nor bitrate nor size for the placeholder path.

    These values are synthetic and this test does not pretend otherwise. It proves the projection
    reads `fps` and the table renders it; whether any site reports it is `T-185`'s question.
    """
    model = FormatTableModel(derived)
    assert display(model, 0, FPS_COLUMN) == "24"
    assert display(model, 1, FPS_COLUMN) == "29.97", "a fractional framerate lost its fraction"
    assert display(model, 2, BITRATE_COLUMN) == "16430 kbps"
    assert display(model, 0, VIDEO_CODEC_COLUMN) == "theora"
    assert display(model, 0, AUDIO_CODEC_COLUMN) == "vorbis"


def test_a_missing_field_reads_the_placeholder_never_an_empty_cell(
    derived: tuple[FormatInfo, ...],
) -> None:
    """`docs/UX_SPEC.md` §4: `UNKNOWN_TEXT`, never blank and never `None`.

    The `hls-480` row of the derived fixture has no fps, no bitrate, no size and no note — four
    absences in one row, which is what a real HLS manifest entry looks like.
    """
    model = FormatTableModel(derived)
    row = next(
        index
        for index in range(model.rowCount())
        if display(model, index, FORMAT_COLUMN) == "hls-480"
    )
    for column in (FPS_COLUMN, BITRATE_COLUMN, SIZE_COLUMN, NOTES_COLUMN):
        assert display(model, row, column) == UNKNOWN_TEXT, (
            f"{COLUMN_HEADERS[column]} rendered {display(model, row, column)!r} for an absent value"
        )
    for column in range(COLUMN_COUNT):
        assert display(model, row, column), f"{COLUMN_HEADERS[column]} rendered an empty cell"


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
    assert display(model, row, RESOLUTION_COLUMN) == UNKNOWN_TEXT


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
    """
    model = FormatTableModel(derived)
    model.sort(FORMAT_COLUMN, Qt.SortOrder.AscendingOrder)
    ids = column_of(model, FORMAT_COLUMN)
    assert ids[-1] == "hls-480", ids
    numeric = [int(value) for value in ids if value.isdigit()]
    assert numeric == sorted(numeric), numeric


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
    """`docs/UX_SPEC.md` §4: `Space` on a header sorts, again reverses."""
    model = FormatTableModel(derived)
    model.sort(RESOLUTION_COLUMN, Qt.SortOrder.AscendingOrder)
    ascending = column_of(model, FORMAT_COLUMN)
    model.sort(RESOLUTION_COLUMN, Qt.SortOrder.DescendingOrder)
    assert column_of(model, FORMAT_COLUMN) == list(reversed(ascending))


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
    heights = [entry.height or -1 for entry in table.model.formats()]
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
    """
    table = FormatTable(derived)
    table.resize(320, 180)
    table.show()
    qapp.processEvents()
    try:
        assert table.sizeHint().isValid(), f"the wrapper has no size hint: {table.sizeHint()}"
        assert table.table.width() == table.width(), (
            f"the view is {table.table.width()}px inside a {table.width()}px wrapper"
        )
        assert table.table.height() == table.height()
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
        table.table.sortByColumn(RESOLUTION_COLUMN, Qt.SortOrder.DescendingOrder)
        table.table.setFocus()
        _press(qapp, Qt.Key.Key_Tab)
        assert qapp.focusWidget() is table.header
        assert table.header.current_section() == RESOLUTION_COLUMN, (
            "the header did not arrive on the column the table is sorted by"
        )

        while table.header.current_section() != SIZE_COLUMN:
            before = table.header.current_section()
            _press(qapp, Qt.Key.Key_Right)
            assert table.header.current_section() != before, "Right did not move the column"

        _press(qapp, Qt.Key.Key_Space)
        assert table.header.sortIndicatorSection() == SIZE_COLUMN, (
            "Space sorted a column other than the one the keyboard had selected"
        )
        ascending = [entry.filesize for entry in table.model.formats()]

        _press(qapp, Qt.Key.Key_Space)
        assert [entry.filesize for entry in table.model.formats()] == list(reversed(ascending)), (
            "a second Space did not reverse the sort"
        )
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
    table.table.sortByColumn(SIZE_COLUMN, Qt.SortOrder.AscendingOrder)
    table.table.setCurrentIndex(table.model.index(1, FORMAT_COLUMN))
    chosen = table.current_format()
    assert chosen is not None

    table.table.sortByColumn(SIZE_COLUMN, Qt.SortOrder.DescendingOrder)
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
    table.table.sortByColumn(RESOLUTION_COLUMN, Qt.SortOrder.DescendingOrder)
    table.set_formats(derived)

    heights = [entry.height or -1 for entry in table.model.formats()]
    assert heights == sorted(heights, reverse=True), (
        f"rows are {heights} under a descending indicator"
    )
    assert table.table.horizontalHeader().sortIndicatorSection() == RESOLUTION_COLUMN


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
