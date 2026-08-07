"""The format table `REQ-003` asks for (`T-107`, `docs/UX_SPEC.md` §4).

**Every column is asserted from a fixture by value**, not from a hand-built `FormatInfo`: the
question `REQ-003` poses is whether what a probe actually reports reaches the table, and a test
that constructs its own model answers a different one. `T-018`'s recorded captures are the contract
for the fields they carry.

**Four columns rest on a *derived* fixture, and that is stated rather than hidden.** The recorded
captures predate `fps`, `tbr`, `vcodec` and `acodec` on a format — `SEC-002` commits only the
fields the projection reads, and the projection did not read them until this task. So
`derived_format_columns` supplies them, and **Phase 3's exit criterion 1 — the table matching
`yt-dlp -F` — is not evidenced by it.** `T-185` owns the re-capture that would.
"""

import json
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui.format_table import (
    AUDIO_ONLY_TEXT,
    BITRATE_COLUMN,
    COLUMN_COUNT,
    COLUMN_HEADERS,
    EXT_COLUMN,
    FORMAT_COLUMN,
    FORMAT_ROLE,
    FPS_COLUMN,
    NOTES_COLUMN,
    RESOLUTION_COLUMN,
    SIZE_COLUMN,
    SORT_ROLE,
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

    # The recorded capture predates fps, bitrate and codecs, so those columns read the
    # placeholder here rather than a value — which is the honest rendering of a fixture that
    # does not carry them, and the reason the derived fixture exists (`SEC-002`, `T-185`).
    assert column_of(model, FPS_COLUMN) == [UNKNOWN_TEXT] * 3
    assert column_of(model, BITRATE_COLUMN) == [UNKNOWN_TEXT] * 3


def test_fps_bitrate_and_codecs_come_through_the_projection(
    derived: tuple[FormatInfo, ...],
) -> None:
    """The four columns the recorded captures predate (`SEC-002`), from the derived fixture.

    **Not evidence for Phase 3's exit criterion 1.** These values are synthetic; what they prove is
    that the adapter projects `fps`/`tbr`/`vcodec`/`acodec` and the table renders them, which is
    this task's claim. Whether yt-dlp reports them the way the fixture says is `T-185`'s.
    """
    model = FormatTableModel(derived)
    assert display(model, 0, FPS_COLUMN) == "24"
    assert display(model, 1, FPS_COLUMN) == "29.97", "a fractional framerate lost its fraction"
    assert display(model, 2, BITRATE_COLUMN) == "16430 kbps"
    assert display(model, 0, 4) == "theora"
    assert display(model, 0, 5) == "vorbis"


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


def test_an_audio_only_format_says_so_rather_than_unknown(
    derived: tuple[FormatInfo, ...],
) -> None:
    """A height an audio stream cannot have is **absent by nature**, not unknown.

    Telling a user the resolution of an audio-only format is "Unknown" invites them to go looking
    for a fact that does not exist.
    """
    model = FormatTableModel(derived)
    row = next(
        index for index in range(model.rowCount()) if display(model, index, FORMAT_COLUMN) == "140"
    )
    assert display(model, row, RESOLUTION_COLUMN) == AUDIO_ONLY_TEXT


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
    """`NFR-008`: yt-dlp's schema stops at the adapter, and this asserts it statically.

    **Derived from the source rather than trusted as a convention**, the way `T-097` checks the
    settings boundary. A widget indexing `entry["vcodec"]` would put upstream churn straight into
    `ui/`, and the failure mode is a user's table going blank after a yt-dlp update.

    **Only the keys that are unambiguously yt-dlp's are checked**, and the exclusions matter more
    than the inclusions. `width` and `height` are *window geometry* in `main_window.py` — the first
    version of this test failed on them, which would have made it a gate that blocks correct code.
    A check that cries wolf gets deleted; one that names distinctive keys keeps working.
    `filesize` and `ext` are excluded for the same reason: they are ordinary words that a widget
    may legitimately use about a file it already knows about.
    """
    import ast

    #: Keys no `ui/` module has any business reading, because only yt-dlp spells them this way.
    distinctive = frozenset(
        {
            "vcodec",
            "acodec",
            "tbr",
            "abr",
            "vbr",
            "format_id",
            "format_note",
            "filesize_approx",
            "has_drm",
            "requested_formats",
            "_has_drm",
        }
    )

    ui_dir = Path(__file__).parents[2] / "src" / "tracks_and_trails" / "ui"
    offenders: list[str] = []
    for module in sorted(ui_dir.glob("*.py")):
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
            if key in distinctive:
                offenders.append(f"{module.name}: {key!r}")
    assert not offenders, (
        f"ui/ reads yt-dlp's own keys: {offenders}. NFR-008 confines that schema to the adapter, "
        "and a widget that indexes it goes blank on the next upstream rename"
    )
