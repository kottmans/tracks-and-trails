"""How a download says what it is, on every surface that says it (`T-159`, `T-156`, `REQ-009`).

**These tests moved here from `test_history_view.py` when `T-170` deleted that surface**, and the
move is the point rather than a tidy-up. `ui/format_text.py` exists because the project wrote the
same naming rule three times and still shipped it wrong the third — `T126-R2` fixed the queue row,
`T140-R3` fixed the playlist header, and `T-159` found History printing yt-dlp's format id. Tests
for a rule shared by several surfaces belong beside the rule, not inside whichever surface happened
to be built last; keeping them in History's file is why deleting History nearly deleted them.

One surface fewer is asserted than before, because there is one fewer surface. What each remaining
one is asked has not changed.
"""

from pathlib import Path
from typing import Final

from PySide6.QtWidgets import QApplication

from tests.qt_lifecycle import drain
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.presets import (
    AUDIO_MP3,
    BUILT_IN_PRESETS,
    MP3_QUALITY,
    format_choice_of,
    to_request,
    with_audio_quality,
)
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.add_dialog import describe_preset
from tracks_and_trails.ui.format_text import format_name, preset_name_for
from tracks_and_trails.ui.queue_view import QueueModel
from tracks_and_trails.ui.row_delegate import PRESET_ROLE
from tracks_and_trails.ui.row_delegate import SELECTOR_ROLE as QUEUE_SELECTOR
from tracks_and_trails.ui.staging import Row

#: What every surface must call a default MP3 download (`T-156`).
#:
#: **The wording is transcribed here and the two values are read from the catalogue**
#: (`ai/TESTING.md` §13). Writing `"Audio only (MP3), 192 kbps"` outright would restate the preset
#: name and the bitrate that production already declares, and the test would then pass while the
#: catalogue said something else; asking `format_name` for the answer would be asking production
#: what to expect. This states the *rule* — the name, a comma, the bitrate, `kbps` — and takes the
#: facts from `presets.py`.
MP3_TEXT: Final = f"{AUDIO_MP3.name}, {MP3_QUALITY} kbps"


def surfaces_naming(url: str, preset: object, tmp_path: Path, qapp: QApplication) -> dict[str, str]:
    """What each surface says about one download, built once and asked of both.

    The queue is driven through its real model over a real manager, and the add dialog through the
    very function its row draws with — so a surface that grew a second opinion shows up here rather
    than in a test written against the opinion.
    """
    from tests.ui.test_queue_view import FakeQueue, make_job

    request = to_request(preset, url=url, output_directory=str(tmp_path))  # type: ignore[arg-type]
    queue = FakeQueue()
    queue.add(make_job("job-1", tmp_path, request=request, url=url, status=JobStatus.COMPLETED))
    manager = DownloadManager(queue)
    try:
        model = QueueModel(jobs=queue, manager=manager)
        return {
            "queue row": model.data(model.index(0, 0), QUEUE_SELECTOR),
            "add dialog": describe_preset(Row(url=url, generation=0), preset),  # type: ignore[arg-type]
        }
    finally:
        manager.shutdown()
        drain(qapp, [manager])


def test_every_surface_names_one_download_the_same_way(qapp: QApplication, tmp_path: Path) -> None:
    """`T-159`: the project fixed this rule twice and still shipped it a third time.

    **They are not required to say identical strings**, and that would be the wrong assertion: the
    add dialog deliberately spells out the literal selector beside the name, because `T118-R8`'s
    promise is that *the effective selector shown stays the one that will run*. What must hold is
    that both name it with the **same words**, and that neither shows a yt-dlp id.
    """
    said = surfaces_naming("https://example.invalid/watch?v=abc123", AUDIO_MP3, tmp_path, qapp)

    for surface, text in said.items():
        assert text, f"{surface} says nothing about the format"
        assert MP3_TEXT in text, (
            f"{surface} reads {text!r}, which does not name the download the way the other "
            "surface does — this is T140-R3's defect one surface over"
        )
        assert "251" not in text, (
            f"{surface} reads {text!r}, which is the yt-dlp id the user was told is useless"
        )


def test_a_bitrate_the_catalogue_does_not_offer_is_named_on_every_surface(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-156`, at the bitrate that makes naming hard, and the line it must not cross.

    **A 320 kbps MP3 matches no built-in**, because `audio_quality` is preset-owned and
    `preset_name_for` compares every such field. Before this it therefore had no name at all: the
    queue read `bestaudio/best` — the selector twice over — and the add dialog read
    *Audio only (MP3)* with the bitrate bolted on beside it.

    **Describing and identifying are answered separately, and this asserts both halves.** The row
    says *Audio only (MP3), 320 kbps*, which is exactly true. `PRESET_ROLE` still answers `None`,
    because that is what the row's *dropdown* shows as selected and a control claiming the 192 kbps
    preset for a 320 kbps download is `T126-R4` — a control reading a built-in that does not
    describe its row. The row speaks because the control cannot.
    """
    from tests.ui.test_queue_view import FakeQueue, make_job

    url = "https://example.invalid/watch?v=abc123"
    loud = with_audio_quality(AUDIO_MP3, "320")
    expected = f"{AUDIO_MP3.name}, 320 kbps"

    said = surfaces_naming(url, loud, tmp_path, qapp)
    for surface, text in said.items():
        assert expected in text, (
            f"{surface} reads {text!r}, which does not name a 320 kbps download the way the other "
            "surface does"
        )

    request = to_request(loud, url=url, output_directory=str(tmp_path))
    assert preset_name_for(format_choice_of(request)) is None, (
        "a 320 kbps download now identifies as a built-in preset, so the row's dropdown would "
        "show a preset that does not describe it and a retarget would be refused as a no-op"
    )

    queue = FakeQueue()
    queue.add(make_job("job-1", tmp_path, request=request, url=url, status=JobStatus.COMPLETED))
    manager = DownloadManager(queue)
    try:
        model = QueueModel(jobs=queue, manager=manager)
        assert model.data(model.index(0, 0), PRESET_ROLE) is None, (
            "the queue row's control claims a preset for a bitrate the catalogue does not offer"
        )
    finally:
        manager.shutdown()
        drain(qapp, [manager])


def test_a_preset_that_converts_nothing_says_nothing_about_a_bitrate() -> None:
    """`T-156`'s third criterion: silence, not a zero and not an "n/a".

    `Audio only (original)` extracts the stream as the site served it, and `MP3_BITRATES` is MP3's
    scale — `with_audio_quality` refuses every other codec outright. A name implying a bitrate
    where none applies would be worse than the omission this task fixes.
    """
    named = {preset.name: format_name(format_choice_of(preset)) for preset in BUILT_IN_PRESETS}
    silent = [name for preset, name in named.items() if preset != AUDIO_MP3.name]

    assert named[AUDIO_MP3.name] == MP3_TEXT, (
        f"the one preset that converts at a bitrate reads {named[AUDIO_MP3.name]!r}"
    )
    for text in silent:
        assert "kbps" not in text, (
            f"{text!r} mentions a bitrate for a download that converts at none"
        )


def test_a_custom_selector_is_named_by_its_own_syntax() -> None:
    """`REQ-009`: a request no built-in describes still says what it is.

    The fallback is the selector and never yt-dlp's format id — `bestaudio/best` is a request a
    user can recognise and act on, while `251` is what yt-dlp resolved it to on one site on one day.
    """
    from dataclasses import replace

    described = format_choice_of(
        to_request(AUDIO_MP3, url="https://example.invalid/x", output_directory="/downloads")
    )
    custom = replace(described, format_selector="bestvideo[height<=480]+bestaudio")

    assert format_name(custom) == "bestvideo[height<=480]+bestaudio"


def test_the_ledger_keeps_no_opinion_about_naming() -> None:
    """`T-170`: History was the third surface, and its removal must not take the rule with it.

    A regression guard rather than a behaviour: `format_text` is imported and exercised above by
    the two surfaces that remain, and this states in one place that a third one leaving is not the
    same as the rule leaving. `completed_at` is the only thing the ledger now records about a
    finished download besides its URL.
    """
    from tracks_and_trails.persistence.repositories import HistoryEntry

    modelled = set(HistoryEntry.__dataclass_fields__)

    assert modelled == {"id", "url", "completed_at"}, (
        f"the ledger models {sorted(modelled)}; DAT-006 §3 keeps three fields, and a format among "
        "them would be a presentation field for a surface that no longer exists"
    )
