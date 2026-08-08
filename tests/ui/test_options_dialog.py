"""The post-processing editor and the route to it (`REQ-010`, `T-109`, `docs/UX_SPEC.md` §6).

What the options *do* to a file is asserted in `tests/integration/test_post_processing.py`, with
real yt-dlp and real ffmpeg. What is asserted here is the surface: that the editor opens on what
the row already asks for, hands back a preset describing what the user chose, and keeps every
control live exactly while it can act.

**`T-139` is the rule this file exists to keep.** The MP3 bitrate control stayed live for a preset
that converts nothing, so it looked like a choice and was not. Three controls here can be in that
position — the audio group, the bitrate, and the subtitle list — and each is asserted disabled with
its reason on screen rather than merely absent.
"""

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QListWidget, QRadioButton

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import AudioCodec
from tracks_and_trails.ui.options_dialog import (
    AUDIO_QUALITY_NAME,
    CONTAINER_CHOICE_NAME,
    CONTAINER_KEEP_NAME,
    CONTAINER_RECODE_NAME,
    CONTAINER_REMUX_NAME,
    EMBED_CHAPTERS_NAME,
    EMBED_METADATA_NAME,
    EMBED_SUBTITLES_NAME,
    EMBED_THUMBNAIL_NAME,
    NO_AUDIO_REASON,
    NO_SUBTITLES_REASON,
    SUBTITLE_LANGUAGES_NAME,
    OptionsDialog,
)


@pytest.fixture
def editor(qapp: QApplication) -> Iterator[Callable[..., OptionsDialog]]:
    """Build an editor and keep it alive for the test, closing it afterwards."""
    built: list[OptionsDialog] = []

    def build(preset: object = None, **options: object) -> OptionsDialog:
        dialog = OptionsDialog(
            preset if preset is not None else preset_registry.BEST_VIDEO,  # type: ignore[arg-type]
            **options,  # type: ignore[arg-type]
        )
        built.append(dialog)
        return dialog

    yield build

    for dialog in built:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


def box(dialog: OptionsDialog, name: str) -> QCheckBox:
    found = dialog.findChild(QCheckBox, name)
    assert found is not None, f"no checkbox named {name}"
    return found


def radio(dialog: OptionsDialog, name: str) -> QRadioButton:
    found = dialog.findChild(QRadioButton, name)
    assert found is not None, f"no radio button named {name}"
    return found


def combo(dialog: OptionsDialog, name: str) -> QComboBox:
    found = dialog.findChild(QComboBox, name)
    assert found is not None, f"no combo box named {name}"
    return found


# --- the round trip -----------------------------------------------------------------------------


def test_the_editor_opens_showing_what_the_preset_already_asks_for(
    editor: Callable[..., OptionsDialog],
) -> None:
    """Opening the editor must not be a way to lose a choice already made.

    The row's own preset is what it opens on (`UX-004`), so every control has to start where that
    preset left it — otherwise pressing OK without touching anything would silently reset the
    options the user set last time.
    """
    preset = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO,
        name="adjusted",
        recode_container="webm",
        embed_metadata=True,
        embed_chapters=True,
    )
    dialog = editor(preset)

    assert radio(dialog, CONTAINER_RECODE_NAME).isChecked()
    assert combo(dialog, CONTAINER_CHOICE_NAME).currentData() == "webm"
    assert box(dialog, EMBED_METADATA_NAME).isChecked()
    assert box(dialog, EMBED_CHAPTERS_NAME).isChecked()
    assert not box(dialog, EMBED_THUMBNAIL_NAME).isChecked()


def test_accepting_an_untouched_editor_changes_nothing_but_the_name(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The identity round trip: open, accept, and the download is the one it was."""
    preset = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO, name="adjusted", remux_container="mkv", embed_thumbnail=True
    )
    result = editor(preset).result_preset()

    assert preset_registry.post_processing_of(result) == preset_registry.post_processing_of(preset)
    assert result.format_selector == preset.format_selector


def test_what_the_user_chooses_is_what_the_derived_preset_carries(
    editor: Callable[..., OptionsDialog],
) -> None:
    """Every control, read back off the preset the editor answers with."""
    dialog = editor(preset_registry.BEST_VIDEO, subtitle_languages=("en", "de"))

    radio(dialog, CONTAINER_REMUX_NAME).setChecked(True)
    container = combo(dialog, CONTAINER_CHOICE_NAME)
    container.setCurrentIndex(container.findData("mkv"))
    box(dialog, EMBED_THUMBNAIL_NAME).setChecked(True)
    box(dialog, EMBED_CHAPTERS_NAME).setChecked(True)
    languages = dialog.findChild(QListWidget, SUBTITLE_LANGUAGES_NAME)
    assert languages is not None
    from PySide6.QtCore import Qt

    languages.item(1).setCheckState(Qt.CheckState.Checked)
    box(dialog, EMBED_SUBTITLES_NAME).setChecked(True)

    result = dialog.result_preset()

    assert result.remux_container == "mkv"
    assert result.recode_container is None
    assert result.embed_thumbnail is True
    assert result.embed_chapters is True
    assert result.embed_metadata is False
    assert result.subtitle_languages == ("de",)
    assert result.embed_subtitles is True


def test_the_derived_preset_is_named_by_the_rule_every_surface_shares(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**A derived preset may not keep its parent's name** (`T-109`).

    `StagingModel.setData` decides *"this row already has that"* by comparing a row's own preset
    to the catalogue **by name**, so an adjusted preset called `Best video available` would make
    re-selecting that catalogue entry a silent no-op — the row would keep the adjustments while
    the control said it had been set back. A wrong download rather than a no-op, which is the
    consequence `CHOOSE_FORMATS_DATA` is an unspellable sentinel to avoid.
    """
    dialog = editor(preset_registry.BEST_VIDEO)
    box(dialog, EMBED_METADATA_NAME).setChecked(True)

    result = dialog.result_preset()

    assert result.name != preset_registry.BEST_VIDEO.name
    assert result.name == "Best video available · embedding metadata", result.name


def test_a_ticked_embed_with_no_language_chosen_does_not_claim_to_embed(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`build_postprocessors` installs `FFmpegEmbedSubtitle` only when both are set.

    So a ticked box with no language selected would be a control that does nothing, and nothing
    would be written beside the file to notice its absence either.
    """
    dialog = editor(preset_registry.BEST_VIDEO, subtitle_languages=("en",))
    box(dialog, EMBED_SUBTITLES_NAME).setChecked(True)

    assert dialog.result_preset().embed_subtitles is False


# --- controls that cannot act are disabled, with the reason -------------------------------------


def test_the_audio_group_is_dead_for_a_video_request_and_says_why(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`T-139`: a live control that cannot act is worse than an absent one.

    `build_postprocessors` installs `FFmpegExtractAudio` only for an audio request, so a codec
    chosen on a video preset would change nothing at all.
    """
    dialog = editor(preset_registry.BEST_VIDEO)

    assert not combo(dialog, AUDIO_QUALITY_NAME).isEnabled()
    assert NO_AUDIO_REASON in _labels(dialog)


def test_the_bitrate_is_live_only_for_mp3(editor: Callable[..., OptionsDialog]) -> None:
    """`MP3_BITRATES` is MP3's scale, and `with_audio_quality` refuses every other codec.

    A control offering 320 kbps for FLAC is offering a number the model will not accept.
    """
    for_mp3 = editor(preset_registry.AUDIO_MP3)
    assert combo(for_mp3, AUDIO_QUALITY_NAME).isEnabled()

    for_original = editor(preset_registry.AUDIO_ORIGINAL)
    assert not combo(for_original, AUDIO_QUALITY_NAME).isEnabled()


def test_the_codec_the_control_shows_is_the_codec_the_request_gets(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**Qt does not hand back the object that was put in** (`T-109`).

    `currentData()` returns the plain string for a `StrEnum`, so a reader guarding with
    `isinstance(data, AudioCodec)` answers its fallback for every entry — and the codec control
    becomes a control that converts nothing, which is `T-075`. Asserted for every codec rather
    than for one, because the defect was uniform and a single case could pass on the fallback.
    """
    for codec in AudioCodec:
        dialog = editor(preset_registry.AUDIO_MP3)
        control = combo(dialog, "optionsAudioCodec")
        control.setCurrentIndex(control.findData(codec))
        assert dialog.chosen_codec() is codec, f"{codec} came back as {dialog.chosen_codec()}"
        assert dialog.result_preset().audio_codec is codec


def test_a_source_with_no_subtitles_says_so_rather_than_offering_an_empty_list(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`P-17`: the list comes from the probe, so an empty one is a fact rather than a gap."""
    dialog = editor(preset_registry.BEST_VIDEO)
    languages = dialog.findChild(QListWidget, SUBTITLE_LANGUAGES_NAME)

    assert languages is not None and not languages.isEnabled()
    assert not box(dialog, EMBED_SUBTITLES_NAME).isEnabled()
    assert NO_SUBTITLES_REASON in _labels(dialog)


def test_the_container_choice_is_dead_while_the_container_is_kept(
    editor: Callable[..., OptionsDialog],
) -> None:
    """Nothing to choose between while nothing is being converted."""
    dialog = editor(preset_registry.BEST_VIDEO)

    assert radio(dialog, CONTAINER_KEEP_NAME).isChecked()
    assert not combo(dialog, CONTAINER_CHOICE_NAME).isEnabled()

    radio(dialog, CONTAINER_REMUX_NAME).setChecked(True)
    assert combo(dialog, CONTAINER_CHOICE_NAME).isEnabled()


def test_remux_and_recode_cannot_both_be_chosen(editor: Callable[..., OptionsDialog]) -> None:
    """The model refuses the pair, so the control must not be able to express it.

    Radio buttons in one group rather than two checkboxes, which is what makes this structural
    rather than a rule somebody has to remember.
    """
    dialog = editor(preset_registry.BEST_VIDEO)

    radio(dialog, CONTAINER_REMUX_NAME).setChecked(True)
    radio(dialog, CONTAINER_RECODE_NAME).setChecked(True)

    assert not radio(dialog, CONTAINER_REMUX_NAME).isChecked()
    result = dialog.result_preset()
    assert (result.remux_container, result.recode_container) != (None, None)
    assert None in (result.remux_container, result.recode_container)


def test_every_container_the_editor_offers_is_one_the_model_accepts(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The control's list and the constructor's list are the same list."""
    from tracks_and_trails.core.models import CONTAINER_FORMATS

    container = combo(editor(preset_registry.BEST_VIDEO), CONTAINER_CHOICE_NAME)
    offered = tuple(container.itemData(index) for index in range(container.count()))

    assert offered == CONTAINER_FORMATS


# --- the keyboard and the screen reader ----------------------------------------------------------


def test_every_control_carries_a_name_a_screen_reader_can_announce(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`NFR-005`, and `docs/UX_SPEC.md` §6's own clause.

    The checkboxes and radio buttons carry their own text, which Qt exposes as the accessible
    name; the two combo boxes and the list have no visible text of their own and are asserted
    here, because a control whose label sits in a form row beside it announces as nothing.
    """
    dialog = editor(preset_registry.AUDIO_MP3, subtitle_languages=("en",))

    for name in (AUDIO_QUALITY_NAME, CONTAINER_CHOICE_NAME):
        assert combo(dialog, name).accessibleName(), name
    languages = dialog.findChild(QListWidget, SUBTITLE_LANGUAGES_NAME)
    assert languages is not None and languages.accessibleName()


def test_a_language_is_chosen_by_a_check_rather_than_by_a_highlight(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`NFR-005`: no information conveyed by colour alone.

    A selection highlight is a colour; a check state is announced by a screen reader and visible
    to somebody who cannot tell the two backgrounds apart.
    """
    dialog = editor(preset_registry.BEST_VIDEO, subtitle_languages=("en", "de"))
    languages = dialog.findChild(QListWidget, SUBTITLE_LANGUAGES_NAME)

    assert languages is not None
    assert languages.selectionMode() is QListWidget.SelectionMode.NoSelection
    from PySide6.QtCore import Qt

    assert all(
        languages.item(index).flags() & Qt.ItemFlag.ItemIsUserCheckable
        for index in range(languages.count())
    )


def _labels(dialog: OptionsDialog) -> list[str]:
    from PySide6.QtWidgets import QLabel

    return [label.text() for label in dialog.findChildren(QLabel)]
