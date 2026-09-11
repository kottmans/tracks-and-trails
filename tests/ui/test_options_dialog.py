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
from dataclasses import replace
from typing import Final

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QWidget,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import AudioCodec, Preset
from tracks_and_trails.core.presets import MP3_BITRATES
from tracks_and_trails.downloader.environment import FfmpegFeature
from tracks_and_trails.ui.options_dialog import (
    AUDIO_CODEC_NAME,
    AUDIO_QUALITY_NAME,
    CONTAINER_CHOICE_NAME,
    CONTAINER_KEEP_NAME,
    CONTAINER_NOTE,
    CONTAINER_NOTE_NAME,
    CONTAINER_RECODE_NAME,
    CONTAINER_REMUX_NAME,
    EMBED_CHAPTERS_NAME,
    EMBED_METADATA_NAME,
    EMBED_SUBTITLES_NAME,
    EMBED_THUMBNAIL_NAME,
    FFMPEG_FEATURE_CONTROLS,
    NO_AUDIO_REASON,
    NO_FFMPEG_REASON,
    NO_SINK_REASON,
    NO_SUBTITLES_REASON,
    SAVE_PRESET_NAME,
    SAVE_PRESET_TEXT,
    SAVE_RESULT_NAME,
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
    """Everything offered is accepted — asserted for both kinds, since they no longer match.

    **This used to assert equality with `CONTAINER_FORMATS`** and passed while a video download
    was offered `mp3` (`T-285`). Equality was never the property worth holding: what matters is
    that nothing offered would be refused, and the two directions are now different questions.
    """
    from tracks_and_trails.core.models import CONTAINER_FORMATS

    for preset in (preset_registry.BEST_VIDEO, preset_registry.AUDIO_MP3):
        container = combo(editor(preset), CONTAINER_CHOICE_NAME)
        offered = tuple(container.itemData(index) for index in range(container.count()))
        assert set(offered) <= set(CONTAINER_FORMATS), (
            f"{preset.name} is offered containers the model would refuse: "
            f"{sorted(set(offered) - set(CONTAINER_FORMATS))}"
        )


def test_a_video_preset_is_not_offered_a_container_that_cannot_hold_video(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`T-285`: the picker was filled from the whole list whatever the preset was.

    Measured with ffmpeg on 2026-08-27: remuxing an `h264 + aac` mp4 into `mp3` **fails** after the
    download has been paid for, and recoding into it **succeeds and discards the video**. The
    dialog already read `media_kind` forty lines away to disable the audio group; the container
    list was the one place it did not ask.
    """
    from tracks_and_trails.core.models import AUDIO_ONLY_CONTAINERS

    container = combo(editor(preset_registry.BEST_VIDEO), CONTAINER_CHOICE_NAME)
    offered = {container.itemData(index) for index in range(container.count())}

    assert not offered & set(AUDIO_ONLY_CONTAINERS), (
        f"a download that keeps its video is offered {sorted(offered & set(AUDIO_ONLY_CONTAINERS))}"
    )
    assert {"mp4", "mkv", "webm"} <= offered, "the video containers went with them"


def test_an_audio_preset_is_still_offered_every_container(
    editor: Callable[..., OptionsDialog],
) -> None:
    """Ruled 2026-08-28: an audio stream in `mp4` or `mkv` is legal and nothing about it fails."""
    from tracks_and_trails.core.models import CONTAINER_FORMATS

    container = combo(editor(preset_registry.AUDIO_MP3), CONTAINER_CHOICE_NAME)
    offered = tuple(container.itemData(index) for index in range(container.count()))

    assert offered == CONTAINER_FORMATS


def test_a_container_the_preset_already_carries_is_not_silently_dropped(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`T109-R2`: a control the user can neither see nor clear must not decide anything.

    A video preset holding `mp3` is a state the model accepts and the dialog no longer offers. If
    the list simply omitted it, `findData` would miss and the combo would open on whatever sits at
    index 0 — silently rewriting a setting the user never touched.
    """
    from dataclasses import replace

    carried = replace(preset_registry.BEST_VIDEO, remux_container="mp3", recode_container=None)

    container = combo(editor(carried), CONTAINER_CHOICE_NAME)

    assert container.currentData() == "mp3", (
        f"the editor opened on {container.currentData()!r} for a preset carrying 'mp3', so "
        "opening the dialog changed the preset"
    )


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

    return [label.text() for label in dialog.findChildren(QLabel)]


# --- T109-R1: `all` is a selector, and an untouched accept keeps what the preset promised -----


def test_the_embedded_subtitles_preset_survives_being_opened_and_accepted(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`T109-R1`.** The built-in carries `("all",)`; the list holds what the probe found.

    Matching the selector against those literals checked nothing, so an untouched accept answered
    with no languages and `embed_subtitles` off — the preset silently lost the option its own name
    promises. Not a literal identity assertion: `all` *means* every offered language, so the
    derived preset names them, which is the same download stated precisely.
    """
    preset = preset_registry.VIDEO_WITH_SUBTITLES
    assert preset.subtitle_languages == (preset_registry.ALL_SUBTITLE_LANGUAGES,), (
        "this test is about the `all` selector and the preset no longer carries it"
    )

    result = editor(preset, subtitle_languages=("en", "de")).result_preset()

    assert result.subtitle_languages == ("en", "de"), (
        f"opening and accepting the preset answered with {result.subtitle_languages}; the "
        "languages it asked for were lost"
    )
    assert result.embed_subtitles is True, "the embed flag was lost with the languages"


def test_the_offered_languages_open_already_checked_for_an_all_preset(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The user has to *see* what will happen, not only get it on accept.

    A dialog that answered correctly while showing nothing checked would pass the test above and
    still tell the user their subtitles were off.
    """
    dialog = editor(preset_registry.VIDEO_WITH_SUBTITLES, subtitle_languages=("en", "de"))
    languages = dialog.findChild(QListWidget, SUBTITLE_LANGUAGES_NAME)
    assert languages is not None

    states = [languages.item(index).checkState() for index in range(languages.count())]
    assert states == [Qt.CheckState.Checked, Qt.CheckState.Checked], states


def test_a_source_with_no_subtitles_does_not_rewrite_what_the_preset_asked_for(
    editor: Callable[..., OptionsDialog],
) -> None:
    """A disabled control decides nothing — `T109-R2`'s rule applied to its sibling.

    The list and the checkbox are both disabled where the probe found no languages, so accepting
    must carry the preset's own fields through. Otherwise opening the editor on a source with
    nothing to show would strip a preset that asked for everything.
    """
    result = editor(preset_registry.VIDEO_WITH_SUBTITLES, subtitle_languages=()).result_preset()

    assert result.subtitle_languages == preset_registry.VIDEO_WITH_SUBTITLES.subtitle_languages
    assert result.embed_subtitles is True


def test_a_preset_naming_specific_languages_still_checks_only_those(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The `all` expansion must not swallow the ordinary case, which is the mutation to fear."""
    preset = replace(
        preset_registry.BEST_VIDEO,
        name="just german",
        subtitle_languages=("de",),
        embed_subtitles=True,
    )

    result = editor(preset, subtitle_languages=("en", "de")).result_preset()

    assert result.subtitle_languages == ("de",), (
        "a preset naming one language came back with every offered one"
    )


# --- T109-R2: a disabled control does not decide anything -------------------------------------


@pytest.mark.parametrize("codec", [c for c in AudioCodec if c is not AudioCodec.MP3])
def test_changing_codec_away_from_mp3_clears_its_bitrate(
    editor: Callable[..., OptionsDialog], codec: AudioCodec
) -> None:
    """**`T109-R2`, over every codec rather than the one that was reported.**

    `MP3_BITRATES` is MP3's scale (`T076-R1`), and yt-dlp reads a `preferredquality` above 10 as
    `-b:a 192k` for AAC, Opus, Vorbis and the rest — so a `192` carried through a codec change was
    a control the user could neither see nor clear still changing the output. Asserted on the
    request as well as the preset, because the request is what runs.
    """
    dialog = editor(preset_registry.AUDIO_MP3)
    assert preset_registry.AUDIO_MP3.audio_quality == preset_registry.MP3_QUALITY
    control = combo(dialog, AUDIO_CODEC_NAME)
    control.setCurrentIndex(control.findData(codec))

    result = dialog.result_preset()
    request = preset_registry.to_request(
        result, url="https://example.invalid/x", output_directory="/downloads"
    )

    assert result.audio_codec is codec
    assert result.audio_quality is None, (
        f"{codec.value} kept MP3's {result.audio_quality!r}, which yt-dlp reads as a bitrate"
    )
    assert request.audio_quality is None, "the leaked bitrate reached the request"
    assert preset_registry.MP3_QUALITY not in result.name, (
        f"the row would read {result.name!r}, naming a bitrate this codec does not use"
    )


def test_choosing_mp3_still_carries_its_bitrate(editor: Callable[..., OptionsDialog]) -> None:
    """The clearing must not take the one case the control exists for."""
    dialog = editor(preset_registry.AUDIO_MP3)
    quality = combo(dialog, AUDIO_QUALITY_NAME)
    quality.setCurrentIndex(quality.findData("320"))

    result = dialog.result_preset()

    assert result.audio_codec is AudioCodec.MP3
    assert result.audio_quality == "320"


def test_a_video_preset_keeps_its_audio_fields_untouched(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The whole audio group is disabled for a video download, so it decides nothing.

    The codec combo shows the preset's value and is read anyway — harmless today because the two
    agree, and a defect waiting for the first change that makes them differ. Carrying the preset's
    own fields through is the rule stated once rather than relied on by coincidence.
    """
    preset = preset_registry.with_audio_quality(preset_registry.AUDIO_MP3, "320")
    video = preset_registry.with_post_processing(
        preset_registry.BEST_VIDEO, name="video", embed_thumbnail=True
    )

    assert editor(video).result_preset().audio_quality is video.audio_quality
    assert editor(video).result_preset().audio_codec is video.audio_codec
    # The MP3 preset is audio, so its group *is* live — the contrast is the point.
    assert editor(preset).result_preset().audio_quality == "320"


# --- T109-R5: P-4's explicit Save as preset… --------------------------------------------------


def save_button(dialog: OptionsDialog) -> QPushButton:
    """`P-4`'s control, by the name it is declared under."""
    found = dialog.findChild(QPushButton, SAVE_PRESET_NAME)
    assert found is not None, "the ratified Save as preset… action is absent"
    return found


def collecting(kept: list[Preset]) -> Callable[[Preset], str | None]:
    """A `PresetSink` that records rather than stores, and never refuses."""

    def sink(preset: Preset) -> str | None:
        kept.append(preset)
        return None

    return sink


def test_the_editor_offers_save_as_preset(editor: Callable[..., OptionsDialog]) -> None:
    """`P-4`, ratified by `UX-007`: *the editor offers `Save as preset…` explicitly*.

    An earlier version of this module argued the control should wait for `T-111`. That was a
    description of a gap rather than a reading of the ruling — `T109-R5`.
    """
    dialog = editor(preset_registry.BEST_VIDEO, save_preset=lambda _preset: None)

    assert save_button(dialog).text() == SAVE_PRESET_TEXT


def test_saving_a_preset_hands_over_what_the_user_chose_under_the_name_they_gave(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`REQ-007`'s create, through the seam `T-111` will build its other four operations on."""
    saved: list[Preset] = []
    dialog = editor(
        preset_registry.BEST_VIDEO,
        save_preset=collecting(saved),
        ask_name=lambda: ("Weekend viewing", True),
    )
    box(dialog, EMBED_THUMBNAIL_NAME).setChecked(True)

    save_button(dialog).click()

    assert len(saved) == 1
    kept = saved[0]
    assert kept.name == "Weekend viewing"
    assert kept.embed_thumbnail is True, "the options on screen were not what was saved"
    assert kept.built_in is False
    assert "Saved as Weekend viewing" in dialog.save_result_text()


def test_saving_a_preset_does_not_accept_the_dialog(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`P-4`'s other half**: a one-off never *silently* becomes a preset, and saving one is not
    the same act as committing the one-off. A button that closed the dialog would make
    *Save as preset…* a second OK, and the user would have committed without meaning to."""
    dialog = editor(
        preset_registry.BEST_VIDEO,
        save_preset=lambda _preset: None,
        ask_name=lambda: ("Weekend viewing", True),
    )

    save_button(dialog).click()

    assert dialog.result() != QDialog.DialogCode.Accepted, (
        "saving a preset accepted the one-off too, so the user committed without meaning to"
    )
    assert "Saved as" in dialog.save_result_text(), (
        "the save did not happen, so this proves nothing"
    )


def test_a_cancelled_or_empty_name_saves_nothing(editor: Callable[..., OptionsDialog]) -> None:
    """Two ways of saying *not this time*, and neither is worth a message."""
    saved: list[Preset] = []
    for answer in (("Weekend", False), ("", True), ("   ", True)):
        dialog = editor(
            preset_registry.BEST_VIDEO,
            save_preset=collecting(saved),
            ask_name=lambda answer=answer: answer,
        )
        save_button(dialog).click()
        assert dialog.save_result_text() == "", dialog.save_result_text()

    assert saved == []


def test_a_refused_name_is_reported_beside_the_button(
    editor: Callable[..., OptionsDialog],
) -> None:
    """A refusal is *"that name is taken"*, which the user answers by pressing the button again.

    Reported in the dialog rather than in a second modal for `P-26`'s reason one surface over.
    """
    dialog = editor(
        preset_registry.BEST_VIDEO,
        save_preset=lambda _preset: "a preset called 'Audio only (MP3)' already exists",
        ask_name=lambda: ("Audio only (MP3)", True),
    )

    save_button(dialog).click()

    assert "already exists" in dialog.save_result_text()


def test_without_somewhere_to_save_the_button_is_not_drawn_and_the_reason_is(
    editor: Callable[..., OptionsDialog],
) -> None:
    """`UX-005` §5, and `P-13`'s shape: not drawn, with the reason in its place.

    This is the case the old module docstring was really describing — and it is a property of the
    *caller*, not of the ruling. Every route a user can reach this by supplies a sink.
    """
    dialog = editor(preset_registry.BEST_VIDEO)

    assert dialog.findChild(QPushButton, SAVE_PRESET_NAME) is None
    assert dialog.save_result_text() == NO_SINK_REASON


# --- T-199: what ffmpeg performs is not offered when ffmpeg is absent -------------------------


#: Controls that stay live with ffmpeg absent, and why each one may.
#:
#: **An explicit allowlist, because the assertion below is "everything else is off".** That shape
#: is what makes a control *added* to this screen and never mapped fail the test: it would be
#: enabled, unmapped, and not named here. A mapping-only assertion cannot do that — measured, by
#: emptying a feature's control tuple and watching the first version of this test still pass.
STILL_LIVE_WITHOUT_FFMPEG: Final = {
    # The only container choice that asks for no post-processing at all.
    CONTAINER_KEEP_NAME,
    # Choosing *which* subtitles is not embedding them. yt-dlp writes them beside the file with
    # no ffmpeg involved; only `embed_subtitles` needs it, and that checkbox is gated.
    SUBTITLE_LANGUAGES_NAME,
}


def test_every_ffmpeg_feature_is_withdrawn_from_the_offer(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`UX-005` §5 for the whole screen**, asserted as one agreement (`REQ-024`, `T-199`).

    *Nothing is drawn that would be refused* — and this dialog refused nothing. The format table
    hid its merge mode without ffmpeg (`P-13`), while every option **here** stayed live: audio
    conversion, remuxing, recoding, and all four embeds. Three of the four features
    `FfmpegReport.summary()` tells the user are unavailable were being offered on the same run.

    **Two halves, and the second is the one that survives a mutation.** The first walks
    `FfmpegFeature` and checks each mapped control is off — `KeyError` if a member is added with
    no entry. That alone is weak: emptying a feature's tuple makes it vacuous, which is exactly
    what happened when it was mutated. So the second half asserts the *screen*: every interactive
    control is disabled except `STILL_LIVE_WITHOUT_FFMPEG`. A control added here and never mapped
    fails that, which is the drift `T-199` names — *"two lists that must match are two lists that
    will drift"*.
    """
    dialog = editor(preset_registry.AUDIO_MP3, ffmpeg_available=False)

    for feature in FfmpegFeature:
        for name in FFMPEG_FEATURE_CONTROLS[feature]:
            control = dialog.findChild(QWidget, name)
            assert control is not None, (
                f"{feature.name} names control {name!r}, which this screen does not have — the "
                "mapping and the dialog have drifted apart"
            )
            assert not control.isEnabled(), (
                f"{name!r} is offered with ffmpeg absent, but {feature.value} needs ffmpeg. "
                "UX-005 §5: nothing is drawn that would be refused"
            )

    offered = {
        control.objectName()
        for kind in (QCheckBox, QComboBox, QRadioButton, QListWidget)
        for control in dialog.findChildren(kind)
        if control.objectName() and control.isEnabled()
    }
    assert offered <= STILL_LIVE_WITHOUT_FFMPEG, (
        f"{sorted(offered - STILL_LIVE_WITHOUT_FFMPEG)} stay live with ffmpeg absent. Either they "
        "need ffmpeg — map them to a FfmpegFeature — or they do not, and STILL_LIVE_WITHOUT_FFMPEG "
        "should say so and why"
    )


def test_the_screen_says_why_and_names_what_would_fix_it(
    editor: Callable[..., OptionsDialog],
) -> None:
    """A greyed control with no explanation is a dead end rather than an answer (`T-139`).

    The reason names ffmpeg **and** the Settings screen, because `T-199` builds the location
    override in the same task: a user told only "ffmpeg was not found" on a machine that has it
    somewhere unusual has been told the wrong thing to do about it.
    """
    dialog = editor(preset_registry.AUDIO_MP3, ffmpeg_available=False)

    # Through the module's own label sweep, as every other reason assertion here does, rather
    # than by an object name invented for this test.
    assert NO_FFMPEG_REASON in _labels(dialog)
    assert "Settings" in NO_FFMPEG_REASON, (
        "the reason does not point at the override this task builds, so a user with ffmpeg "
        "installed somewhere unusual is told to install it again"
    )


def test_keeping_the_arriving_container_survives_a_missing_ffmpeg(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The one choice that asks for no post-processing stays available.

    Disabling it would leave the container group with no selectable member, which reads as *the
    container you already have is unavailable too* — and that is not true, it is the only one that
    is. `T-199` gates what ffmpeg performs, not what arrives.
    """
    dialog = editor(preset_registry.BEST_VIDEO, ffmpeg_available=False)

    keep = dialog.findChild(QRadioButton, CONTAINER_KEEP_NAME)
    assert keep is not None
    assert keep.isEnabled(), "the arriving container was withdrawn along with the conversions"


def test_ffmpeg_present_offers_everything_it_performs(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The other direction, so the gate cannot pass by disabling everything always.

    A test that only proved things are hidden without ffmpeg would pass an implementation that
    hides them always — which is the shape `DAT-003` records twice under a different name.
    """
    dialog = editor(preset_registry.AUDIO_MP3, ffmpeg_available=True)

    codec = dialog.findChild(QComboBox, AUDIO_CODEC_NAME)
    assert codec is not None and codec.isEnabled()
    for name in FFMPEG_FEATURE_CONTROLS[FfmpegFeature.EMBED]:
        control = dialog.findChild(QWidget, name)
        assert control is not None
    thumbnail = dialog.findChild(QCheckBox, EMBED_THUMBNAIL_NAME)
    assert thumbnail is not None and thumbnail.isEnabled(), (
        "embedding is refused with ffmpeg present, so the gate is unconditional"
    )


# --- T-222: the explanations are not cut to make the dialog fit ------------------------------


def _shown(dialog: OptionsDialog, size: tuple[int, int] | None = None) -> OptionsDialog:
    """Show the dialog and let it lay out.

    **Shown, because this class of defect does not exist in an unshown widget** — `T-209`'s lesson,
    and the reason this task's entry required the reproduction before the correction. An unshown
    dialog's children have no geometry to be wrong.
    """
    if size is not None:
        dialog.resize(*size)
    dialog.show()
    for _ in range(4):
        QApplication.processEvents()
    return dialog


def _clipped_explanations(dialog: OptionsDialog) -> list[str]:
    """Every wrapping label that has less height than its own text needs at its own width.

    **Every one of them, found by `wordWrap()` rather than by name.** The report named the
    Container note, but three siblings wrap the same way and a fix aimed at one label would leave
    the others one sentence away from the same defect. A label added later is audited by this
    without anyone remembering to add it.
    """
    cut = []
    for label in dialog.findChildren(QLabel):
        if not label.wordWrap() or not label.text():
            continue
        needs = label.heightForWidth(label.width())
        if needs > label.height():
            cut.append(f"{label.text()[:40]!r} has {label.height()}px and needs {needs}px")
    return cut


def test_the_explanations_are_whole_at_the_size_the_dialog_opens_at(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`T-222`, the reported defect.** The Container note lost its second line.

    Measured before the correction: the dialog opened at 302 by 680 — *its own reported minimum* —
    and the note was allotted 17px where its two wrapped lines need 34. So this was not a small
    window a user had dragged down to; it was the size the dialog chose for itself.
    """
    dialog = _shown(editor())

    assert not _clipped_explanations(dialog), (
        "the dialog opened at a size that cuts its own explanatory text: "
        + "; ".join(_clipped_explanations(dialog))
    )


@pytest.mark.parametrize(
    "size",
    [(300, 400), (355, 500), (355, 680), (355, 700), (420, 600), (900, 700)],
    ids=lambda size: f"{size[0]}x{size[1]}",
)
def test_no_explanation_is_cut_at_any_size_a_user_can_drag_to(
    editor: Callable[..., OptionsDialog], size: tuple[int, int]
) -> None:
    """The dialog is resizable, so *"it fits at the default size"* is not the property wanted.

    355 by 700 is the maintainer's screenshot. The rest bracket it, including one window wide
    enough that the note needs only one line — which is where a fix that simply reserved two lines
    everywhere would waste a row and this would not notice, so the assertion is `heightForWidth` at
    the label's *actual* width rather than a fixed number.
    """
    dialog = _shown(editor(), size)

    assert not _clipped_explanations(dialog), "; ".join(_clipped_explanations(dialog))


def test_content_taller_than_the_window_scrolls_rather_than_being_squeezed(
    editor: Callable[..., OptionsDialog],
) -> None:
    """What replaces the squeeze, asserted as the mechanism and not only as its absence.

    Qt's response to a window shorter than its content was to shrink whatever could shrink, and a
    word-wrapping label reports a one-line minimum, so the explanations went first — silently, with
    no scrollbar and no ellipsis to say a sentence had lost half of itself. The four groups now sit
    in a scroll area, so the height that does not fit is *reachable* instead of being taken out of
    the text.
    """
    dialog = _shown(editor(), (355, 400))

    scroller = dialog.findChild(QScrollArea)
    assert scroller is not None, "the option groups are not in a scroll area"
    bar = scroller.verticalScrollBar()
    assert bar.maximum() > 0, (
        "the window is far shorter than the content and nothing scrolls, so the height has gone "
        "somewhere else"
    )
    scrolled = scroller.widget()
    assert scrolled is not None, "the scroll area is empty"
    reachable = bar.maximum() + scroller.viewport().height()
    assert reachable >= scrolled.sizeHint().height(), (
        "scrolling to the bottom still does not reach the end of the options"
    )


def test_the_buttons_stay_out_of_the_scroll_area(
    editor: Callable[..., OptionsDialog],
) -> None:
    """*OK* and *Cancel* are not something a user should have to scroll to find.

    The save line goes with them: `P-13`'s rule is that a control which cannot act keeps its reason
    beside it, and a reason scrolled off the bottom is not beside anything.
    """
    dialog = _shown(editor(), (355, 400))

    scroller = dialog.findChild(QScrollArea)
    assert scroller is not None
    scrolled = scroller.widget()
    assert scrolled is not None, "the scroll area is empty"
    inside = set(scrolled.findChildren(QWidget))

    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None and buttons not in inside, "the buttons scroll with the options"
    result = dialog.findChild(QLabel, SAVE_RESULT_NAME)
    assert result is not None and result not in inside, "the save line scrolls with the options"
    assert buttons.geometry().bottom() <= dialog.height(), "the buttons are below the window"


def test_the_dialog_opens_showing_everything_the_screen_has_room_for(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`T222-R1`.** The scroller fixed the clipping and shrank the opening size.

    `show()` sizes a window with `adjustSize()`, which clamps to **two thirds of the screen** — so
    the dialog's old 680px opening was not a considered default, it was `minimumSizeHint`
    overriding that clamp, and the minimum was itself a claim the layout could not honour. Dropping
    the minimum to 161 removed the accidental floor and left the clamp showing: the reviewer
    measured a shown dialog at **302 by 501**, hiding more of the options at the default size than
    the original defect did.

    The property wanted is not a number. It is that the dialog opens at the height its content
    asks for, unless the display cannot supply it — which is why this is expressed against the
    screen rather than against a constant, and why the previous round's tests, which resized every
    case explicitly, could not have caught the regression.
    """
    dialog = _shown(editor())

    room = dialog.screen().availableGeometry()
    wanted = dialog.sizeHint().height()
    assert dialog.height() >= min(wanted, room.height() - _decoration(dialog)), (
        f"the dialog opened {dialog.height()}px tall; its content asks for {wanted}px and the "
        f"screen has room for {room.height()}px"
    )


def _decoration(dialog: OptionsDialog) -> int:
    """How much taller the window is than its client area — title bar, borders."""
    return max(dialog.frameGeometry().height() - dialog.height(), 0)


def test_the_whole_window_fits_the_screen_frame_and_all(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`T222-R1`, the half the first correction got wrong** — and its own test with it.

    `resize()` sets the **client** area. A window is its client area *plus its frame*, so bounding
    the client to the available height puts the frame past the bottom of the screen: measured at
    **800 client / 804 frame against 800 available**, and a real title bar costs far more than four
    pixels. What goes past the bottom is the button box — which is the exact harm the scroll area
    was introduced to prevent, arrived at from the other direction.

    **The previous version of this compared `dialog.height()` with the screen height**, so it
    encoded the same client/frame mistake it was supposed to be guarding. This compares
    `frameGeometry`, which is the thing that has to fit.
    """
    dialog = _shown(editor())

    room = dialog.screen().availableGeometry()
    frame = dialog.frameGeometry().height()
    assert frame <= room.height(), (
        f"the window is {frame}px tall including its frame, against {room.height()}px of available "
        f"screen — {frame - room.height()}px of it, the buttons included, is off the bottom"
    )


def test_nothing_scrolls_when_the_screen_can_show_it_all(
    editor: Callable[..., OptionsDialog],
) -> None:
    """A scrollbar on a display with room to spare is the scroller taking over the layout.

    The scroll area is here for short windows. On one tall enough for the whole content, the
    dialog should look exactly as it did before this task — no bar, nothing out of reach. Skipped
    rather than failed where the display genuinely cannot fit it, because that is the other case
    and it has its own test.
    """
    dialog = _shown(editor())
    scroller = dialog.findChild(QScrollArea)
    assert scroller is not None
    scrolled = scroller.widget()
    assert scrolled is not None

    if dialog.screen().availableGeometry().height() < dialog.sizeHint().height():
        pytest.skip("this display is shorter than the dialog's content; that is the other test")

    assert scroller.verticalScrollBar().maximum() == 0, (
        "the dialog scrolls at its opening size on a screen with room for all of it"
    )


#: The reviewer's own matrix for `T315-R3`, plus the control that already passed.
#:
#: **All five are accepted domain values.** `audio_quality` is `str | None` on both `Preset` and
#: `DownloadRequest`, so a custom preset can carry yt-dlp's VBR quality `0`, a bitrate outside
#: `MP3_BITRATES` such as `96`, or an AAC quality — none of which this dialog offers as a choice
#: and none of which it may therefore rewrite.
UNCHANGED_AUDIO: Final = (
    (AudioCodec.MP3, "0"),
    (AudioCodec.MP3, None),
    (AudioCodec.MP3, "96"),
    (AudioCodec.AAC, "3"),
    (AudioCodec.MP3, "192"),
)


@pytest.mark.parametrize(("codec", "quality"), UNCHANGED_AUDIO, ids=lambda v: str(v))
def test_accepting_unchanged_keeps_an_audio_quality_this_dialog_cannot_offer(
    editor: Callable[..., OptionsDialog],
    codec: AudioCodec,
    quality: str | None,
) -> None:
    """`T315-R3`: opening the editor and pressing OK must not re-encode the download.

    **Two branches produced this, and either alone still loses the value.** `_show_preset` fell
    back to index `0` when `findData` missed — so a request asking for `96` displayed `320 kbps` —
    and `_chosen_audio` cleared any non-MP3 quality even when the codec had not changed.

    **Measured by the reviewer against the queue's new Options route**, where `T-315` promises
    lossless editing of an arbitrary queued request. The defect predates that route and reaches the
    staging list's editor by the same code, which is why the fix and this test are on the dialog.

    The last row is the control that passed throughout: a listed MP3 bitrate. Without it a test
    that trivially returned its input would look like a fix.
    """
    preset = replace(preset_registry.AUDIO_MP3, audio_codec=codec, audio_quality=quality)
    dialog = editor(preset, ffmpeg_available=True)

    result = dialog.result_preset()

    assert result.audio_codec is codec, f"the codec changed to {result.audio_codec}"
    assert result.audio_quality == quality, (
        f"{codec.value} at {quality!r} came back as {result.audio_quality!r}"
    )


def test_the_bitrate_control_shows_a_value_it_does_not_offer(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The display half of `T315-R3`: the control said `320 kbps` for a request asking for `96`.

    **A control that misreports is worse than one that refuses**, because the user has no way to
    know. The entry is inserted only when it describes the current state — `row_delegate`'s rule
    for a row's own non-catalogue preset, one surface over — so nothing widens the choices offered
    to a request whose bitrate this dialog does list.
    """
    preset = replace(preset_registry.AUDIO_MP3, audio_codec=AudioCodec.MP3, audio_quality="96")
    dialog = editor(preset, ffmpeg_available=True)

    control = combo(dialog, AUDIO_QUALITY_NAME)
    assert "96" in control.currentText(), (
        f"the bitrate control says {control.currentText()!r} for a download asking for 96"
    )

    listed = editor(preset_registry.AUDIO_MP3, ffmpeg_available=True)
    assert combo(listed, AUDIO_QUALITY_NAME).count() == len(MP3_BITRATES), (
        "a request whose bitrate is offered gained an extra entry it does not need"
    )


def test_changing_the_codec_still_clears_a_quality_that_belonged_to_the_old_one(
    editor: Callable[..., OptionsDialog],
) -> None:
    """The half `T315-R3` must **not** break (`T076-R1`, `T-089`).

    `MP3_BITRATES` are MP3's scale, and yt-dlp reads a `preferredquality` above 10 as `-b:a 192k`
    for AAC, Opus and Vorbis alike — so carrying a bitrate through a codec change is a hidden
    control quietly changing the output. The preservation above is for a group nobody touched;
    this is a codec the user actually changed.
    """
    preset = replace(preset_registry.AUDIO_MP3, audio_codec=AudioCodec.MP3, audio_quality="192")
    dialog = editor(preset, ffmpeg_available=True)
    codecs = combo(dialog, AUDIO_CODEC_NAME)
    codecs.setCurrentIndex(codecs.findData(AudioCodec.AAC))

    result = dialog.result_preset()
    assert result.audio_codec is AudioCodec.AAC
    assert result.audio_quality is None, (
        f"MP3's 192 followed the codec change to AAC as {result.audio_quality!r}"
    )


def test_the_container_note_says_what_recoding_is_for(
    editor: Callable[..., OptionsDialog],
) -> None:
    """**`T-286`.** *"Does re-encoding provide any tangible benefit over remuxing? Seems like the
    option is pointless."*

    **It is not pointless, and the dialog leaving that question open was the defect.** The note
    stated only cost — *"recoding re-encodes them and is not [quick]"* — so a reader learned which
    option is slower and nothing about when the slower one is right.

    **The four criteria are asserted separately**, because a single "did the wording change" check
    would pass on any edit at all:

    - it still states the cost, which is what stops a casual click;
    - it names the case — **a player refusing what the site sent**, asserted on those words rather
      than on the sentence as a whole (`T286-R1`). The first version checked only *"only when"* and
      the constant-to-label equality, which between them would pass on *"Recode only when needed"*:
      the bound stayed and the reason vanished, and the equality cannot see it because both sides
      receive the changed constant;
    - it does not advise recoding — format selection answers the ordinary case with no conversion,
      so the sentence is bounded by *only when*;
    - it says why remuxing does not cover that case, which is the measured trap: remuxing a
      `vp9 + opus` webm to mp4 **succeeds and leaves `vp9 opus` inside**.
    """
    dialog = editor(ffmpeg_available=True)
    note = dialog.findChild(QLabel, CONTAINER_NOTE_NAME)
    assert note is not None, "the container section has no note"
    said = note.text()

    assert said == CONTAINER_NOTE, "the drawn note is not the one this module declares"
    assert "quick" in said, "the cost is no longer stated, so nothing stops a casual click"
    assert "only when" in said, "the note reads as advice to recode rather than as a bounded case"
    # **The case itself, not only that the sentence is bounded** (`T286-R1`). "Recode only when
    # needed" satisfies every other check here and says nothing this task was filed to say.
    assert "player" in said and "refuses" in said, (
        f"the note bounds recoding without naming what bounds it: {said!r}"
    )
    assert "does not change what is inside it" in said, (
        "the note does not say why remuxing fails to cover the case it names"
    )
    for codec in ("vp9", "h264", "aac", "opus"):
        assert codec not in said.lower(), (
            f"the note names {codec}, which is not the register the rest of this dialog uses"
        )
