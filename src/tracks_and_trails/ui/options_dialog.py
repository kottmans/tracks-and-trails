"""The post-processing editor (`REQ-010`, `T-109`, `docs/UX_SPEC.md` §6).

`REQ-010` names seven options: extract/convert audio to a chosen codec and quality; remux
container; recode container; embed thumbnail; embed metadata; embed chapters; embed or write
subtitles with language selection. This is the one screen all seven are set on.

## Reached two ways, and it is the same widget both times

`UX-007`'s `P-3`: as *Options…* on a row's format control, editing a one-off for that download,
and from the preset manager, editing a saved preset. Only the first exists today — the preset
manager is `T-111`, and `T-109`'s scope explicitly excludes its CRUD — so the dialog takes its
title and its accept text from the caller rather than deciding it is always editing a one-off.

**`Save as preset…` is here, and `P-4` is why** (`T109-R5`). *"A one-off options change does not
silently become a preset. The editor offers `Save as preset…` explicitly."* An earlier version of
this module argued the button should wait for `T-111` because there was nowhere to save to — which
was a description of a gap, not a reading of the ruling, and `UX-005` §5's never-draw-what-would-be-
refused does not license omitting a control an accepted decision requires. So the place to put it
exists: `core/settings.add_preset`, in the `settings.toml` `T-111`'s own entry records as already
decided. This screen creates; `T-111`'s manager edits, duplicates, deletes and chooses a default.

**The caller supplies the sink, and without one the button is not drawn.** A control that cannot
save is the thing `UX-005` §5 actually forbids, and the reason takes its place — `P-13`'s shape,
one surface over. Every route a user can reach this by supplies one.

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

**And a disabled control does not decide anything either** (`T109-R2`). Disabling was only half the
rule: `result_preset` went on reading every field, so a value the user could neither see nor clear
still reached the request. Changing codec away from MP3 left its `192` attached, and yt-dlp reads a
quality above 10 as `-b:a 192k` for AAC and every other lossy codec — a hidden control changing the
output, which is the `T-075` shape the disabling was introduced to prevent. Every group now answers
one question first: *could the user have said this?* Where the answer is no, the preset's own value
is carried through untouched, and where a field is meaningless for the choice that **was** made it
is cleared rather than inherited.

## `all` is a selector, and the list is a set of languages

**`T109-R1`.** `VIDEO_WITH_SUBTITLES` carries `subtitle_languages=("all",)` — yt-dlp's way of
saying *every subtitle this source publishes* — and the language list holds what the probe actually
found. Matching the two by string meant a preset promising *all* checked nothing against a source
offering `en` and `de`, so an untouched accept answered with no languages and `embed_subtitles`
off: the built-in silently lost the option its own name promises. Displaying `all` therefore means
checking everything offered, which is what the selector says.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Final, Protocol

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import CONTAINER_FORMATS, AudioCodec, MediaKind, Preset
from tracks_and_trails.core.presets import (
    ALL_SUBTITLE_LANGUAGES,
    MP3_BITRATES,
    format_choice_of,
    with_post_processing,
)
from tracks_and_trails.downloader.environment import FfmpegFeature
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
SAVE_PRESET_NAME: Final = "optionsSavePreset"
SAVE_RESULT_NAME: Final = "optionsSaveResult"

#: Which controls each `FfmpegFeature` owns on this screen (`REQ-024`, `T-199`, `UX-005` §5).
#:
#: **The mapping is here, and the test walks the enum.** `UX-005` §5 — nothing is drawn that would
#: be refused — was three quarters untrue on this dialog: the format table hid its merge mode
#: without ffmpeg (`P-13`) and this screen went on offering audio conversion, remuxing and
#: embedding, every one of which ffmpeg performs. A feature added to `FfmpegFeature` with no entry
#: here fails `test_every_ffmpeg_feature_is_withdrawn_from_the_offer` rather than silently becoming
#: something offered and then refused.
#:
#: `MERGE` names no control **on this screen** and says so with an empty tuple rather than being
#: absent: absence would be indistinguishable from an oversight, which is the failure this mapping
#: exists to make impossible. Its surface is the format table, gated by `P-13` since `T-107`.
FFMPEG_FEATURE_CONTROLS: Final[dict[FfmpegFeature, tuple[str, ...]]] = {
    FfmpegFeature.MERGE: (),
    FfmpegFeature.AUDIO: (AUDIO_CODEC_NAME, AUDIO_QUALITY_NAME),
    FfmpegFeature.CONTAINER: (
        CONTAINER_REMUX_NAME,
        CONTAINER_RECODE_NAME,
        CONTAINER_CHOICE_NAME,
    ),
    FfmpegFeature.EMBED: (
        EMBED_THUMBNAIL_NAME,
        EMBED_METADATA_NAME,
        EMBED_CHAPTERS_NAME,
        EMBED_SUBTITLES_NAME,
    ),
}

#: Said once, where the controls it explains are (`NFR-006`, `REQ-024`).
#:
#: Names the thing to do about it. *"Requires ffmpeg"* on a disabled control tells a user what is
#: wrong and not what would fix it, and this screen is where they are looking when they find out.
NO_FFMPEG_REASON: Final = (
    "ffmpeg was not found, so these options cannot be applied. Install ffmpeg, or set its "
    "location in Settings."
)

#: What `P-4`'s control reads. The ellipsis is the platform's promise that it will ask something.
SAVE_PRESET_TEXT: Final = "Save as preset…"

#: Asked when the button is pressed. The name is the preset's identity everywhere else in this
#: application — the row shows it, and `T-159` makes it what a surface compares — so it is the one
#: thing worth interrupting for.
SAVE_PRESET_PROMPT: Final = "Save these options as a preset called:"

#: Said in the button's place where the caller supplied nowhere to save (`UX-005` §5, `P-13`).
NO_SINK_REASON: Final = "These options cannot be saved as a preset from here."

#: Said where a control is disabled, so the reason is on screen rather than inferred (`T-139`).
NO_AUDIO_REASON: Final = "This download keeps its video, so there is no audio track to convert."
NO_BITRATE_REASON: Final = "A bitrate applies to MP3. Other codecs carry their own quality scale."
NO_SUBTITLES_REASON: Final = "This source publishes no subtitles."
SUBTITLES_HINT: Final = "Chosen languages are written beside the file unless they are embedded."


class PresetSink(Protocol):
    """Where a saved preset goes. Answers `None` on success, or why it was refused.

    **A protocol, so this dialog does not learn where settings live.** `core/settings.add_preset`
    is what composition wires in; a test hands over a list. Refusals travel back as words rather
    than as an exception, because the only refusal that exists — a name already taken — is a thing
    the user fixes by typing a different one, not an error.
    """

    def __call__(self, preset: Preset) -> str | None: ...


class _OptionGroups(QScrollArea):
    """The scroll area the option groups sit in, reporting what it would *like* to be.

    **`QScrollArea` asks for almost nothing** — its `sizeHint` ignores the widget inside it, so a
    dialog built around one opens at whatever the rest of the layout needs and scrolls from the
    first moment. That is `T222-R1`: adding the scroller fixed the clipping and moved the dialog's
    opening size from 302 by 680 down to **302 by 501**, hiding more of the options at the default
    size than the defect it replaced did.

    So `sizeHint` reports the content's own preferred height. `minimumSizeHint` is deliberately
    **not** touched — it is what lets the dialog still shrink to 161px, which is the whole reason
    the scroller is here. The two answer different questions: *what would you like* and *what can
    you survive*, and the first build only had an answer for the second.
    """

    # Qt's override name, hence the camelCase.
    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        content = self.widget()
        if content is None:
            return hint
        frame = 2 * self.frameWidth()
        preferred = content.sizeHint()
        return QSize(max(hint.width(), preferred.width() + frame), preferred.height() + frame)


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
        save_preset: PresetSink | None = None,
        ask_name: Callable[[], tuple[str, bool]] | None = None,
        ffmpeg_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self._preset = preset
        self._offered_languages = tuple(subtitle_languages)
        self._save_preset = save_preset
        #: **What this screen may offer** (`REQ-024`, `T-199`, `UX-005` §5). Every option on it
        #: except *keep what arrives* is post-processing, and post-processing is ffmpeg's — so
        #: with ffmpeg absent this dialog was offering three of the four things `FfmpegFeature`
        #: says do not work. Defaults to `True` so the many tests that predate the gate, and the
        #: preset manager's editor, keep their behaviour; composition passes the real answer.
        self._ffmpeg_available = ffmpeg_available
        #: How the name is asked for. Injected so a test drives `P-4`'s whole route without a modal
        #: — `QInputDialog.getText` runs a nested event loop, and a test that entered one would
        #: never reach its assertions (`open_add_dialog`'s reason for `open()` over `exec()`).
        self._ask_name = ask_name if ask_name is not None else self._ask_name_modally
        self.setWindowTitle(title)
        self.setObjectName("optionsDialog")
        self._build()
        self._show_preset(preset)
        self._update_enabled()
        self._open_at_a_size_that_shows_the_options()

    def _open_at_a_size_that_shows_the_options(self) -> None:
        """Open showing everything the screen has room for (`T222-R1`).

        **`show()` does not use `sizeHint()` for a window; it uses `adjustSize()`, which clamps to
        two thirds of the screen.** That clamp is why this dialog opened at 302 by 680 before the
        scroller and 302 by 501 after it — the old number was not a considered default either, it
        was `minimumSizeHint` overriding the clamp, and the minimum was itself a claim the layout
        could not honour. Lowering the minimum to 161 removed the accidental floor and left the
        clamp showing.

        So the size is asked for explicitly: the content's full preferred height, bounded by the
        screen actually available. **Neither half is a fixed size** — the first is `sizeHint()`,
        which grows if the text does, and the second is the display's.

        **The bound is applied again in `showEvent`, and that is not belt and braces.** `resize()`
        sets the **client** area; a window is its client area *plus its frame*. Bounding the client
        to the available height therefore puts the frame past the bottom of the screen — measured
        at 800 client / 804 frame against 800 of available height, and a real title bar costs far
        more than four pixels. The frame's size is not known until the window has been shown, so
        the correction cannot happen here.
        """
        wanted = self.sizeHint()
        # `QWidget.screen()` is non-optional in Qt's own typing — a widget always belongs to one,
        # falling back to the primary screen before it is shown — so there is no `None` branch to
        # write here; `mypy` reports one as unreachable if it is.
        room = self.screen().availableGeometry()
        self.resize(min(wanted.width(), room.width()), min(wanted.height(), room.height()))

    # Qt's override name, hence the camelCase.
    def showEvent(self, event: QShowEvent) -> None:
        """Bound the **frame** to the screen, now that the frame has a size (`T222-R1`).

        **Every show, not only the first.** A first draft guarded this with a once-only flag, on
        the reasoning that a user who resizes the dialog and reopens it should get the size they
        left. That does not survive being written down: this only ever *shrinks*, and the sole case
        where the flag changes anything is a window left taller than the screen — which is the
        defect, not a preference to preserve. A mutation removing the flag changed no test, which is
        what prompted looking at it; the flag went rather than a test being written to defend it.
        """
        super().showEvent(event)
        room = self.screen().availableGeometry()
        decoration = max(self.frameGeometry().height() - self.height(), 0)
        allowed = room.height() - decoration
        if allowed > 0 and self.height() > allowed:
            self.resize(self.width(), allowed)

    # --- construction -------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        # **The four groups scroll; the save line and the buttons do not** (`T-222`).
        #
        # The reported defect was the Container group's explanation clipped to one of its two
        # wrapped lines. The measured cause is larger than that group: the four groups together
        # want ~760px of height, this dialog is resizable, and **it opened at 302 by 680 — its own
        # reported minimum — with the note already cut.** The minimum was a claim the layout could
        # not honour, because a word-wrapping `QLabel` reports a one-line `minimumSizeHint`, so Qt
        # is free to squeeze an explanation down to its first line to make the arithmetic come out.
        # It does that silently: no scrollbar, no ellipsis, no sign that a sentence lost its
        # second half.
        #
        # **So the fix is not a taller minimum.** Two candidates that took that route were measured
        # and rejected: a `Minimum` vertical policy on the wrapped labels still cut the note by 6px
        # at narrow widths, and a `minimumSizeHint` override reporting `heightForWidth` pushed the
        # dialog's floor to 901px — taller than its own natural 853 and than the usable height of a
        # 768px display, which trades clipped text for an unreachable *OK*. Scrolling drops the
        # floor to 161px instead, and the notes are whole at every size probed, down to 200 by 300.
        #
        # **The buttons stay outside the viewport** so *OK* and *Cancel* are reachable however
        # short the window is, and so is the save line's refusal (`P-13`'s rule — a control that
        # cannot act keeps its reason beside it, which is no use scrolled off).
        groups = QWidget(self)
        stack = QVBoxLayout(groups)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.addWidget(self._build_audio())
        stack.addWidget(self._build_container())
        stack.addWidget(self._build_embedding())
        stack.addWidget(self._build_subtitles())

        scroller = _OptionGroups(self)
        scroller.setWidgetResizable(True)
        # No frame: the groups already draw their own borders, and a second one around them reads
        # as a panel this dialog does not otherwise have.
        scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        scroller.setWidget(groups)
        layout.addWidget(scroller, 1)

        self._save_result = QLabel("", self)
        self._save_result.setObjectName(SAVE_RESULT_NAME)
        self._save_result.setWordWrap(True)
        # A refusal names the preset the user tried to save over, which is their own text
        # (`T016-R6`), and so is the name they typed.
        self._save_result.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._save_result)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        # **`P-4`'s explicit action** (`T109-R5`). `ActionRole`, so pressing it saves and leaves the
        # dialog open: saving a preset is not accepting the one-off, and closing on it would make
        # *Save as preset…* a second OK. That is also what keeps *"never silently"* true from the
        # other side — the user still has to accept, or cancel, on purpose.
        if self._save_preset is not None:
            self._save_button = QPushButton(SAVE_PRESET_TEXT, self)
            self._save_button.setObjectName(SAVE_PRESET_NAME)
            self._save_button.setAccessibleName(SAVE_PRESET_TEXT)
            self._save_button.setAccessibleDescription(
                "Keep these options under a name, so other downloads can use them. This does not "
                "change what happens to this one."
            )
            self._save_button.clicked.connect(self._on_save_preset)
            buttons.addButton(self._save_button, QDialogButtonBox.ButtonRole.ActionRole)
        else:
            self._save_result.setText(NO_SINK_REASON)
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

        # **The label is the buddy, and on Linux it is the only thing naming this** (`T200-R7`).
        # `QAccessibleComboBox::text` falls through `Name` to `Value` under `Q_OS_UNIX`, so a combo
        # publishes its selected item — *"avi"* — where its name should be, and discards
        # `setAccessibleName`. The three radio buttons above cannot be buddies, and the group box
        # is the section rather than the choice, so this control had nothing naming it at all.
        container_label = QLabel("Container to convert to", group)
        container_label.setObjectName("optionsContainerLabel")
        container_label.setWordWrap(True)
        layout.addWidget(container_label)

        self._container_choice = QComboBox(group)
        self._container_choice.setObjectName(CONTAINER_CHOICE_NAME)
        self._container_choice.setAccessibleName("Container to convert to")
        container_label.setBuddy(self._container_choice)
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
        # **`all` is a selector, not a language** (`T109-R1`). It means *every subtitle this source
        # publishes*, so displaying it means every offered language checked. Compared as a set
        # against the literals, a preset carrying `("all",)` matched nothing the probe found and an
        # untouched accept then answered with no languages at all.
        everything = ALL_SUBTITLE_LANGUAGES in preset.subtitle_languages
        wanted = set(preset.subtitle_languages)
        for index in range(self._languages.count()):
            item = self._languages.item(index)
            checked = everything or item.text() in wanted
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _update_enabled(self) -> None:
        """Keep every control live exactly while it can act (`T-139`, `UX-005` §5).

        **Without ffmpeg, nothing here can act** (`REQ-024`, `T-199`). Every option on this screen
        is post-processing, so the ffmpeg answer is applied last and overrides the per-control
        reasoning above it: a control that this method has just enabled because the preset makes
        it relevant is still disabled if nothing can perform it.

        *Keep the container it arrives in* stays live, because it is the one choice that asks for
        no post-processing at all — disabling it would leave the group with no selectable member
        and imply the arriving container was also unavailable.
        """
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

        if not self._ffmpeg_available:
            self._withdraw_what_ffmpeg_performs()

    def _withdraw_what_ffmpeg_performs(self) -> None:
        """Disable every control `FFMPEG_FEATURE_CONTROLS` names, and say why once.

        By object name rather than by attribute, so the mapping the agreement test walks is the
        same mapping this method obeys — one list, not two that must match.
        """
        for names in FFMPEG_FEATURE_CONTROLS.values():
            for name in names:
                control = self.findChild(QWidget, name)
                if control is not None:
                    control.setEnabled(False)
        # On the audio reason line, which is the first thing this screen says about itself, and
        # ahead of the narrower "this preset is not audio" text: a user with no ffmpeg needs the
        # reason that explains the whole screen rather than one group of it.
        self._audio_reason.setText(NO_FFMPEG_REASON)

    # --- `P-4`: saving these options under a name -----------------------------------------

    def _ask_name_modally(self) -> tuple[str, bool]:
        """Ask for a name, offering the one these options already describe as the default.

        `format_name` produces something like *Audio only (MP3), 320 kbps* — descriptive, and
        almost never what the user wants to keep it as, which is the point of putting it in an
        editable field rather than using it silently.
        """
        return QInputDialog.getText(
            self, SAVE_PRESET_TEXT, SAVE_PRESET_PROMPT, text=self.result_preset().name
        )

    def _on_save_preset(self) -> None:
        """Save these options under a name the user gives (`P-4`, `REQ-007`'s create).

        **Nothing happens on a cancelled or empty name.** `QInputDialog` reports the two
        separately — an empty string with `True` is somebody who cleared the field and pressed OK —
        and both mean *not this time*, so neither is worth a message.

        The outcome is said in the dialog rather than in a second modal: a refusal is *"that name
        is taken"*, which the user answers by pressing the button again.
        """
        if self._save_preset is None:  # pragma: no cover - the button only exists with a sink
            return
        name, accepted = self._ask_name()
        if not accepted or not name.strip():
            return
        refusal = self._save_preset(replace(self.result_preset(), name=name.strip()))
        self._save_result.setText(refusal if refusal is not None else f"Saved as {name.strip()}.")

    def save_result_text(self) -> str:
        """What the last save attempt said. A method, so a test reads what the user reads."""
        return self._save_result.text()

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
        codec, quality = self._chosen_audio()
        languages, embed = self._chosen_subtitles()
        derived = replace(
            derived,
            audio_codec=codec,
            audio_quality=quality,
            subtitle_languages=languages,
            embed_subtitles=embed,
        )
        return replace(derived, name=format_name(format_choice_of(derived)))

    def _chosen_audio(self) -> tuple[AudioCodec, str | None]:
        """The codec and quality the user chose — or the preset's own, where they could not choose.

        **A disabled group decides nothing** (`T109-R2`). Disabling the controls was only half the
        rule; reading them anyway is what let a value the user can neither see nor clear reach the
        request. Two cases, and they are different:

        - **The whole group is disabled** — this download keeps its video, so there is no audio to
          convert. Nothing here was a choice, so the preset's own fields are carried through.
        - **The group is live and the codec is not MP3** — the bitrate control is disabled, and its
          value is *cleared* rather than inherited. `MP3_BITRATES` is MP3's scale (`T076-R1`), and
          yt-dlp reads a `preferredquality` above 10 as `-b:a 192k` for AAC, Opus, Vorbis and every
          other lossy codec — so carrying `192` through a codec change was a hidden control quietly
          changing the output, which is exactly the contract `T-076` and `T-089` established
          against.

        The quality goes through `with_audio_quality`, which refuses a bitrate for a codec that has
        no use for one, rather than being set here — a second route to the field is a second
        opinion about when it applies.
        """
        if not self._audio_group.isEnabled():
            return self._preset.audio_codec, self._preset.audio_quality
        codec = self.chosen_codec()
        if codec is not AudioCodec.MP3:
            return codec, None
        quality = self._audio_quality.currentData()
        return codec, quality if isinstance(quality, str) else self._preset.audio_quality

    def _chosen_subtitles(self) -> tuple[tuple[str, ...], bool]:
        """The languages and the embed flag — or the preset's own, where the list was disabled.

        **A source publishing no subtitles offers no choice** (`T109-R1`, `T109-R2`'s rule applied
        to its sibling). The list and the checkbox are both disabled then, so accepting must not
        rewrite what the preset asked for: a preset carrying `("all",)` opened against a source with
        nothing to show would otherwise come back empty, having been told nothing.

        **Embedding needs something to embed.** `build_postprocessors` installs
        `FFmpegEmbedSubtitle` only when both are set, so a ticked box with no language chosen would
        be a control that does nothing — and `writesubtitles` would not be set either, so nothing
        would be written beside the file to notice its absence.
        """
        if not self._languages.isEnabled():
            return self._preset.subtitle_languages, self._preset.embed_subtitles
        languages = self.chosen_languages()
        return languages, self._embed_subtitles.isChecked() and bool(languages)
