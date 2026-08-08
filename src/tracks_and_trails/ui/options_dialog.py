"""The post-processing editor (`REQ-010`, `T-109`, `docs/UX_SPEC.md` §6).

`REQ-010` names seven options: extract/convert audio to a chosen codec and quality; remux
container; recode container; embed thumbnail; embed metadata; embed chapters; embed or write
subtitles with language selection. This is the one screen all seven are set on.

## Reached two ways, and it is the same widget both times

`UX-007`'s `P-3`: as *Options…* on a row's format control, editing a one-off for that download,
and from the preset manager, editing a saved preset. Only the first exists today — the preset
manager is `T-111`, and `T-109`'s scope explicitly excludes its CRUD — so the dialog takes its
title and its accept text from the caller rather than deciding it is always editing a one-off.

**There is no `Save as preset…` button yet, and its absence is deliberate.** `P-4` requires that a
one-off never silently becomes a preset, and offering a control that cannot save anywhere would be
worse than not offering it: `UX-005` §5 forbids drawing what would be refused. `T-111` owns where a
saved preset lives, and the button arrives with the place to put it.

## Everything the model refuses is unreachable here

`DownloadRequest` and `Preset` refuse a remux **and** a recode together, and refuse a container
yt-dlp does not accept. The container control is therefore one exclusive choice — *keep*, *remux
to*, *recode to* — over a list built from `CONTAINER_FORMATS`, so the invalid state cannot be
expressed rather than being expressed and rejected. That is `T-014`'s rule: making a value
unrepresentable is the version of a bound that holds.

## A control that cannot act is disabled, with the reason beside it

`T-139` was the defect: the MP3 bitrate control stayed live for a preset that converts nothing, so
it looked like a choice and was not. The same rule is applied three times here — the audio group is
live only for an audio request, the bitrate only for MP3, and the subtitle list only where the
probe found languages. Each disabled control keeps a sentence saying why, because a greyed control
with no explanation is a dead end rather than an answer.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import CONTAINER_FORMATS, AudioCodec, MediaKind, Preset
from tracks_and_trails.core.presets import (
    MP3_BITRATES,
    format_choice_of,
    with_audio_quality,
    with_post_processing,
)
from tracks_and_trails.ui.format_text import format_name

__all__ = ["OptionsDialog"]

#: Object names, so tests and stylesheets reach a control without walking the layout.
CONTAINER_KEEP_NAME: Final = "optionsContainerKeep"
CONTAINER_REMUX_NAME: Final = "optionsContainerRemux"
CONTAINER_RECODE_NAME: Final = "optionsContainerRecode"
CONTAINER_CHOICE_NAME: Final = "optionsContainerChoice"
AUDIO_CODEC_NAME: Final = "optionsAudioCodec"
AUDIO_QUALITY_NAME: Final = "optionsAudioQuality"
EMBED_THUMBNAIL_NAME: Final = "optionsEmbedThumbnail"
EMBED_METADATA_NAME: Final = "optionsEmbedMetadata"
EMBED_CHAPTERS_NAME: Final = "optionsEmbedChapters"
SUBTITLE_LANGUAGES_NAME: Final = "optionsSubtitleLanguages"
EMBED_SUBTITLES_NAME: Final = "optionsEmbedSubtitles"

#: Said where a control is disabled, so the reason is on screen rather than inferred (`T-139`).
NO_AUDIO_REASON: Final = "This download keeps its video, so there is no audio track to convert."
NO_BITRATE_REASON: Final = "A bitrate applies to MP3. Other codecs carry their own quality scale."
NO_SUBTITLES_REASON: Final = "This source publishes no subtitles."
SUBTITLES_HINT: Final = "Chosen languages are written beside the file unless they are embedded."


class OptionsDialog(QDialog):
    """Set `REQ-010`'s seven options for one download, or for a preset.

    Takes the `Preset` being edited and the languages the probe found, and answers with a derived
    preset. It never edits the preset it was given: `Preset` is frozen, and the caller decides
    whether the answer replaces a row's own choice or a saved entry.
    """

    def __init__(
        self,
        preset: Preset,
        *,
        subtitle_languages: Sequence[str] = (),
        parent: QWidget | None = None,
        title: str = "Options for this download",
    ) -> None:
        super().__init__(parent)
        self._preset = preset
        self._offered_languages = tuple(subtitle_languages)
        self.setWindowTitle(title)
        self.setObjectName("optionsDialog")
        self._build()
        self._show_preset(preset)
        self._update_enabled()

    # --- construction -------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._build_audio())
        layout.addWidget(self._build_container())
        layout.addWidget(self._build_embedding())
        layout.addWidget(self._build_subtitles())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        # `docs/UX_SPEC.md` §6: *Enter commits, Esc cancels* — which is what a `QDialogButtonBox`
        # with a default Ok already does, so the keyboard path is the platform's rather than a
        # second implementation of it.
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._buttons = buttons

    def _build_audio(self) -> QWidget:
        group = QGroupBox("Audio", self)
        form = QFormLayout(group)

        self._audio_codec = QComboBox(group)
        self._audio_codec.setObjectName(AUDIO_CODEC_NAME)
        self._audio_codec.setAccessibleName("Audio codec")
        for codec in AudioCodec:
            # `ORIGINAL` is spelled for the user rather than as yt-dlp's `best`, which means "no
            # conversion" and reads as "the best codec" to everyone who has not read the source.
            label = "Keep the original codec" if codec is AudioCodec.ORIGINAL else codec.value
            self._audio_codec.addItem(label, codec)
        self._audio_codec.currentIndexChanged.connect(self._update_enabled)
        form.addRow("Convert to", self._audio_codec)

        self._audio_quality = QComboBox(group)
        self._audio_quality.setObjectName(AUDIO_QUALITY_NAME)
        self._audio_quality.setAccessibleName("MP3 bitrate")
        for bitrate in MP3_BITRATES:
            self._audio_quality.addItem(f"{bitrate} kbps", bitrate)
        form.addRow("Bitrate", self._audio_quality)

        self._audio_reason = QLabel("", group)
        self._audio_reason.setWordWrap(True)
        form.addRow(self._audio_reason)
        self._audio_group = group
        return group

    def _build_container(self) -> QWidget:
        group = QGroupBox("Container", self)
        layout = QVBoxLayout(group)

        self._container_keep = QRadioButton("Keep the container it arrives in", group)
        self._container_keep.setObjectName(CONTAINER_KEEP_NAME)
        self._container_remux = QRadioButton("Remux — rewrap the same streams", group)
        self._container_remux.setObjectName(CONTAINER_REMUX_NAME)
        self._container_recode = QRadioButton("Recode — re-encode the streams", group)
        self._container_recode.setObjectName(CONTAINER_RECODE_NAME)
        for button in self._container_buttons():
            button.toggled.connect(self._update_enabled)
            layout.addWidget(button)

        self._container_choice = QComboBox(group)
        self._container_choice.setObjectName(CONTAINER_CHOICE_NAME)
        self._container_choice.setAccessibleName("Container to convert to")
        for container in CONTAINER_FORMATS:
            self._container_choice.addItem(container, container)
        layout.addWidget(self._container_choice)

        note = QLabel(
            "Remuxing keeps the streams and is quick; recoding re-encodes them and is not.",
            group,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        return group

    def _build_embedding(self) -> QWidget:
        group = QGroupBox("Embed in the file", self)
        layout = QVBoxLayout(group)
        self._embed_thumbnail = QCheckBox("The source's thumbnail", group)
        self._embed_thumbnail.setObjectName(EMBED_THUMBNAIL_NAME)
        self._embed_metadata = QCheckBox("Title, uploader and description", group)
        self._embed_metadata.setObjectName(EMBED_METADATA_NAME)
        self._embed_chapters = QCheckBox("Chapters", group)
        self._embed_chapters.setObjectName(EMBED_CHAPTERS_NAME)
        for box in (self._embed_thumbnail, self._embed_metadata, self._embed_chapters):
            layout.addWidget(box)
        return group

    def _build_subtitles(self) -> QWidget:
        group = QGroupBox("Subtitles", self)
        layout = QVBoxLayout(group)

        self._languages = QListWidget(group)
        self._languages.setObjectName(SUBTITLE_LANGUAGES_NAME)
        self._languages.setAccessibleName("Subtitle languages")
        self._languages.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        # **Checkboxes rather than a multi-select highlight** (`P-17`, `NFR-005`). A selection
        # highlight is conveyed by colour, which `NFR-005` forbids as the only distinction, and a
        # screen reader announces a checked item without being asked what the colour means.
        for language in self._offered_languages:
            item = QListWidgetItem(language, self._languages)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
        layout.addWidget(self._languages)

        self._embed_subtitles = QCheckBox("Embed them in the file", group)
        self._embed_subtitles.setObjectName(EMBED_SUBTITLES_NAME)
        layout.addWidget(self._embed_subtitles)

        self._subtitle_reason = QLabel("", group)
        self._subtitle_reason.setWordWrap(True)
        layout.addWidget(self._subtitle_reason)
        return group

    def _container_buttons(self) -> tuple[QRadioButton, QRadioButton, QRadioButton]:
        return (self._container_keep, self._container_remux, self._container_recode)

    # --- state --------------------------------------------------------------------------

    def _show_preset(self, preset: Preset) -> None:
        """Open showing what the preset already asks for, so nothing is lost by opening it."""
        self._audio_codec.setCurrentIndex(self._audio_codec.findData(preset.audio_codec))
        quality = self._audio_quality.findData(preset.audio_quality)
        self._audio_quality.setCurrentIndex(quality if quality >= 0 else 0)

        if preset.remux_container is not None:
            self._container_remux.setChecked(True)
            self._container_choice.setCurrentIndex(
                self._container_choice.findData(preset.remux_container)
            )
        elif preset.recode_container is not None:
            self._container_recode.setChecked(True)
            self._container_choice.setCurrentIndex(
                self._container_choice.findData(preset.recode_container)
            )
        else:
            self._container_keep.setChecked(True)

        self._embed_thumbnail.setChecked(preset.embed_thumbnail)
        self._embed_metadata.setChecked(preset.embed_metadata)
        self._embed_chapters.setChecked(preset.embed_chapters)
        self._embed_subtitles.setChecked(preset.embed_subtitles)
        wanted = set(preset.subtitle_languages)
        for index in range(self._languages.count()):
            item = self._languages.item(index)
            checked = item.text() in wanted
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _update_enabled(self) -> None:
        """Keep every control live exactly while it can act (`T-139`, `UX-005` §5)."""
        converts = self._preset.media_kind is MediaKind.AUDIO
        self._audio_group.setEnabled(converts)
        self._audio_reason.setText("" if converts else NO_AUDIO_REASON)

        is_mp3 = self.chosen_codec() is AudioCodec.MP3
        self._audio_quality.setEnabled(converts and is_mp3)
        if converts and not is_mp3:
            self._audio_reason.setText(NO_BITRATE_REASON)

        self._container_choice.setEnabled(not self._container_keep.isChecked())

        offered = bool(self._offered_languages)
        self._languages.setEnabled(offered)
        self._embed_subtitles.setEnabled(offered)
        self._subtitle_reason.setText(SUBTITLES_HINT if offered else NO_SUBTITLES_REASON)

    # --- what the user chose ------------------------------------------------------------

    def chosen_codec(self) -> AudioCodec:
        """The codec the control is showing, rebuilt from its value rather than cast to it.

        **Qt does not hand back the object that was put in.** `addItem(label, AudioCodec.MP3)`
        stores the enum, and `currentData()` returns the plain `str` `"mp3"` — `AudioCodec` is a
        `StrEnum`, and PySide unwraps it on the way out. An `isinstance(data, AudioCodec)` check
        therefore fails for **every** entry, so a version of this that guarded with one answered
        `ORIGINAL` no matter what the user chose: the codec control would have looked like a
        choice and converted nothing, which is `T-075` exactly. Caught by
        `test_the_bitrate_is_live_only_for_mp3`, which noticed the bitrate staying dead for the
        MP3 preset — the symptom one control over from the cause.
        """
        try:
            return AudioCodec(self._audio_codec.currentData())
        except ValueError:  # pragma: no cover - every entry is built from the enum
            return AudioCodec.ORIGINAL

    def chosen_languages(self) -> tuple[str, ...]:
        """The checked languages, in the order the source listed them."""
        return tuple(
            self._languages.item(index).text()
            for index in range(self._languages.count())
            if self._languages.item(index).checkState() is Qt.CheckState.Checked
        )

    def result_preset(self) -> Preset:
        """The preset the user has described — derived, never the one that was passed in.

        **Named through `format_name`, the rule every surface shares** (`T-159`). A derived preset
        keeping its parent's name would make two different downloads answer to one name, and the
        staging list decides *"this row already has that"* by comparing names — so re-selecting the
        catalogue entry would silently keep the adjustments. `with_post_processing` refuses to
        derive without a name for that reason; this is where the name comes from.

        The audio quality goes through `with_audio_quality`, which refuses a bitrate for a codec
        that has no use for one, rather than being set directly here — a second route to the same
        field is a second opinion about when it applies.
        """
        derived = with_post_processing(
            self._preset,
            # Provisional: replaced below, once the derived preset is what gets named. A preset
            # cannot be built without a name, and the name depends on the fields being set.
            name=self._preset.name,
            remux_container=(
                str(self._container_choice.currentData())
                if self._container_remux.isChecked()
                else None
            ),
            recode_container=(
                str(self._container_choice.currentData())
                if self._container_recode.isChecked()
                else None
            ),
            embed_thumbnail=self._embed_thumbnail.isChecked(),
            embed_metadata=self._embed_metadata.isChecked(),
            embed_chapters=self._embed_chapters.isChecked(),
        )
        languages = self.chosen_languages()
        derived = replace(
            derived,
            audio_codec=self.chosen_codec(),
            subtitle_languages=languages,
            # **Embedding needs something to embed.** `build_postprocessors` installs
            # `FFmpegEmbedSubtitle` only when both are set, so a ticked box with no language
            # chosen would be a control that does nothing — and `writesubtitles` would not be set
            # either, so nothing would be written beside the file to notice its absence.
            embed_subtitles=self._embed_subtitles.isChecked() and bool(languages),
        )
        if derived.audio_codec is AudioCodec.MP3 and self._audio_quality.isEnabled():
            quality = self._audio_quality.currentData()
            if isinstance(quality, str):
                derived = with_audio_quality(derived, quality)
        return replace(derived, name=format_name(format_choice_of(derived)))
