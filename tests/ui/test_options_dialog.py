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
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QWidget,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import AudioCodec, Preset
from tracks_and_trails.downloader.environment import FfmpegFeature
from tracks_and_trails.ui.options_dialog import (
    AUDIO_CODEC_NAME,
    AUDIO_QUALITY_NAME,
    CONTAINER_CHOICE_NAME,
    CONTAINER_KEEP_NAME,
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
