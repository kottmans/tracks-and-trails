"""The Settings screen (`REQ-023`, built by `T-146`).

**All eight of `REQ-023`'s settings, since `T-196`.** The requirement names default download
directory, default preset, concurrency limit, output template, ffmpeg location, network options,
cookie source and theme — the download directory, theme and concurrency limit from `T-146`, the
ffmpeg location from `T-199`, the cookie source from `T-197`, the default preset and output
template from `T-195`, and the network options from `T-196`.

`SETTINGS_STILL_TO_COME` is shown on the screen itself so it never claims coverage it does not
have — `T-146`'s own criterion, and the failure mode a settings screen has by default. **It is
empty now, and the label is not built**, which is that criterion satisfied rather than retired:
the sentence has shrunk with every task that landed one of the eight, and this is where it runs
out. Anything `REQ-023` gains later puts it back.

*(A module of this name existed until 2026-08-06 holding one control, `Clear download records`. It
went with `REQ-020`. Nothing of it survives here but the shape of the menu route, which was worth
reading before writing this: `T169-R4` recorded that the shell was gone so a later implementer
would not go looking for it.)*

## Changes apply as they are made, and the button says `Close`

Every control here applies and saves as it is changed — the idiom `T-078` established for the
concurrency limit, and the one this screen inherited when `UX-013` made it that limit's only home
(`T-234`). An `OK`/`Cancel` pair would be the other honest shape, and it is the wrong one here:
several of these settings are already visible elsewhere — the theme in every pixel, the default
preset in the preset manager and on the next row a user pastes — so a change that waited for `OK`
would have to either not preview (and make the theme unpickable without guessing) or preview and
then be revertible, which is a transaction this screen has no way to roll back.

*(This paragraph named the toolbar's concurrency spinner twice: as the idiom's origin and as an
example of a setting visible elsewhere. `UX-013` removed that spinner. The idiom's origin is still
`T-078` — the behaviour outlived the widget that first had it — and the concurrency limit is no
longer an example of the second thing, because this screen is where it is seen.)*

## The directory picker is injected

`choose_directory` defaults to `QFileDialog.getExistingDirectory` and is a parameter because a
native modal cannot be driven headlessly (`docs/project/TESTING.md`), and a screen whose one route
to its main setting is untestable is a screen whose main setting is untested. The same seam, and the
same reasoning, as the manager's `entry_point`.
"""

import os
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Final

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import BROWSER_NAMES, NetworkOptions, proxy_refusal
from tracks_and_trails.core.output_template import unsupported_refusal
from tracks_and_trails.core.settings import (
    CONCURRENCY_MAXIMUM,
    CONCURRENCY_MINIMUM,
    RATE_LIMIT_MAXIMUM_BYTES,
    RETRIES_MAXIMUM,
    THEME_NAMES,
)
from tracks_and_trails.ui.keyboard import route_is_elsewhere

__all__ = [
    "COOKIES_EXPLANATION",
    "DEFAULT_RETRIES_LABEL",
    "DOWNLOAD_DIRECTORY_PROBLEM_NAME",
    "FFMPEG_ON_PATH_NOTE",
    "NETWORK_EXPLANATION",
    "NO_COOKIES_NOTE",
    "NO_RATE_LIMIT_LABEL",
    "PROXY_NAME",
    "PROXY_NOTE_NAME",
    "RATE_LIMIT_NAME",
    "RATE_LIMIT_STEP_BYTES",
    "REQ_023_SETTINGS",
    "RETRIES_NAME",
    "SETTINGS_STILL_TO_COME",
    "STEP_BUTTON_PROPERTY",
    "STEP_DOWN_LABEL",
    "STEP_UP_LABEL",
    "THEME_LABELS",
    "YTDLP_NOTE_NAME",
    "YTDLP_REVERT_LABEL",
    "YTDLP_REVERT_NAME",
    "YTDLP_UPDATE_NAME",
    "YTDLP_VERSION_NAME",
    "YTDLP_VERSION_UNKNOWN",
    "YTDLP_WORKING_LABEL",
    "Req023Setting",
    "SettingsDialog",
    "still_to_come",
]

#: What each theme is called on screen. The stored names are lower-case identifiers; these are the
#: words a user reads, and keeping them apart is what lets the file stay stable if the wording
#: changes.
THEME_LABELS: Final = {"light": "Light", "dark": "Dark"}

#: Object names, so tests and composition reach a control without walking the layout (`T-195`).
DEFAULT_PRESET_NAME: Final = "settingsDefaultPreset"
OUTPUT_TEMPLATE_NAME: Final = "settingsOutputTemplate"
OUTPUT_TEMPLATE_NOTE_NAME: Final = "settingsOutputTemplateNote"

#: Shown under the folder when no folder has been chosen. **It names the actual path**, because
#: "the default" is not an answer to *where did my file go*.
#: Where the Downloads section says why a typed folder was refused (`T-292`).
DOWNLOAD_DIRECTORY_PROBLEM_NAME: Final = "downloadDirectoryProblem"

#: What the cookies section says it is for, and what it is not for.
#:
#: **`REQ-EXCL-002` is quoted in spirit because a user should read it here.** This exists so
#: someone reaches content they already have an account for; it is not a way past a paywall, and
#: the sentence says so where the control is rather than only in a requirements file.
COOKIES_EXPLANATION: Final = (
    "Use cookies from a file to download things you are signed in to. This does not unlock "
    "anything your account cannot already reach.\n"
    "A cookies file applies to downloads already in the queue as well as new ones."
)

#: Shown where the path would be when none is set.
NO_COOKIES_NOTE: Final = "No cookies file - downloads are not signed in"

#: Shown where the path would be when none is set. Names the mechanism, because *"not set"* does
#: not tell a user what the application is doing instead.
FFMPEG_ON_PATH_NOTE: Final = "Looked for on PATH"

#: The scrolling region the sections live in, by name, so a test can ask what it did (`T-242`).
SETTINGS_SCROLL_NAME: Final = "settingsScroll"

#: What the dialog assumes it may take when there is no screen to ask — a headless run, an
#: offscreen test (`T-242`).
#:
#: **Generous on purpose.** Guessing small here would make every offscreen test measure a scroll
#: bar rather than the layout underneath it, which is the opposite of what those tests are for.
_NO_SCREEN_WIDTH: Final = 1024
_NO_SCREEN_HEIGHT: Final = 2048

#: The layout's own margins and spacing around the button row, added when sizing the dialog to
#: its contents. A measured constant rather than a walk of the layout's metrics: what it buys is
#: that the last section is not half-hidden behind `Close` on a screen with room for both.
_BUTTON_ROW_ROOM: Final = 24

#: How much room a control keeps around it when focus scrolls it into view (`T-242`).
#:
#: Without it a control lands hard against the viewport edge, where the group box's own frame
#: reads as though the control were cut off — which is the impression this task exists to remove.
_FOCUS_MARGIN: Final = 24

#: Height and width given back to the window manager: a dialog exactly as tall as the working
#: area sits under its own title bar, and that bar's height is not knowable from here.
_WINDOW_CHROME: Final = 48

#: Object names for the network section, so tests and composition reach a control without walking
#: the layout (`T-196`).
PROXY_NAME: Final = "networkProxy"
PROXY_NOTE_NAME: Final = "networkProxyNote"
RATE_LIMIT_NAME: Final = "networkRateLimit"
RETRIES_NAME: Final = "networkRetries"

#: What the network section says about when its settings take effect, and about what the rate
#: limit actually limits.
#:
#: **Both halves are things a user would otherwise have to discover.** `ARCHITECTURE.md` §8 freezes
#: settings into a job when it is queued, so these three bind at *paste* time — the opposite of the
#: cookies file one section up, which is late-bound and whose explanation says so for the same
#: reason. And yt-dlp's `ratelimit` binds one session while every download here is its own process
#: (`ARC-002`), so three at once can use three times the number in the box.
NETWORK_EXPLANATION: Final = (
    "These apply to downloads you add from now on. Anything already in the queue keeps what it "
    "was added with.\n"
    "The speed limit applies to each download on its own, so several at once can add up.\n"
    "Retries here are of the file transfer. Streams delivered in small pieces retry those pieces "
    "on a count of their own, which this does not change."
)

#: What the rate-limit spin box reads at zero (`UX-005` §5: a control says what it does).
#:
#: **Zero is the control's way of saying "no limit", and the file's way of saying nothing.** The
#: setting is stored as an absent key, never as a `0` — `core/settings.py` reports a stored zero
#: rather than reading it as unlimited, because there it is a hand-edit that removes a limit
#: somebody asked for. Here the word is on screen next to the number, so there is nothing to
#: misread.
NO_RATE_LIMIT_LABEL: Final = "No limit"

#: What the retries spin box reads below zero, where "nobody chose" lives.
#:
#: **A sentinel is needed because `0` is a real answer here** — *do not retry inside the attempt* —
#: so the usual trick of treating zero as unset would silently turn that into yt-dlp's default of
#: ten. `-1` is never stored: it is `None`, spelled in the one vocabulary a `QSpinBox` has.
#:
#: The application's own default is deliberately not named as a number. yt-dlp owns it, this
#: module does not import yt-dlp, and a copy of it here would be wrong the day it changes.
DEFAULT_RETRIES_LABEL: Final = "The downloader's own"

#: The rate limit is offered in KiB/s and stored in bytes per second.
#:
#: **The conversion lives here and nowhere else.** `settings.toml`, `NetworkOptions` and yt-dlp's
#: `ratelimit` all speak bytes, because that is what the machinery takes; KiB/s is what a person
#: means. One direction of one conversion in one widget is the smallest surface that can hold both.
#:
#: A stored value that is not a whole number of KiB — a hand-edit, or a file from another tool —
#: is **displayed** rounded down and is *not* rewritten: the box only writes when the user moves
#: it, so an unrelated change elsewhere on the screen cannot quietly re-round a limit they set.
#:
#: **Rounding down can no longer reach zero**, which is what made it a defect rather than a
#: nicety (`T196-R3`): `500` displayed as *No limit* while downloads were capped at 500 B/s.
#: `RATE_LIMIT_MINIMUM_BYTES` is that hole closed at the value — the settings layer holds no rate
#: this control cannot show — so the residual is now bounded to *"1500 B/s reads as 1 KiB/s"*,
#: which understates a limit by less than the limit itself and never denies one.
RATE_LIMIT_STEP_BYTES: Final = 1024

#: What the concurrency control's step buttons read (`UX-005` row 11, `T-141`, `T-236`).
#:
#: A true minus sign rather than a hyphen: at this size a hyphen reads as a dash in a sentence,
#: and the pair has to look like a pair.
#:
#: **These lived in `main_window.py` until `T-234`**, which deleted them with the toolbar's
#: spinner. `UX-005` row 11 rules on *the concurrency control*, not on the toolbar, so they come
#: back with the control rather than staying where the control used to be.
STEP_DOWN_LABEL: Final = "\u2212"
STEP_UP_LABEL: Final = "+"

#: The dynamic property the sheet styles the step buttons against (`T-141`).
#:
#: **A role, not a name.** `theme.py` styles by class so a widget nobody remembered still gets
#: themed, and an object-name selector fails silently when it stops matching — the button just goes
#: back to looking like text.
STEP_BUTTON_PROPERTY: Final = "stepButton"

#: Object names for the yt-dlp section, so tests and composition reach a control without walking
#: the layout (`T-198`).
YTDLP_VERSION_NAME: Final = "ytdlpVersion"
YTDLP_NOTE_NAME: Final = "ytdlpNote"
YTDLP_UPDATE_NAME: Final = "ytdlpUpdate"
YTDLP_REVERT_NAME: Final = "ytdlpRevert"

#: Shown before a child has answered. **Not a version and not a guess** (`REQ-025`): the number
#: comes from a worker's import, which takes a moment, and inventing a placeholder that looks like
#: a version is how a screen ends up reporting one nobody read.
YTDLP_VERSION_UNKNOWN: Final = "Checking…"

#: What the revert button says. Names the destination rather than the gesture: *Revert* asks the
#: user to remember what they reverted to, and the bundled baseline is the thing they get.
YTDLP_REVERT_LABEL: Final = "Use the bundled version"

#: What the update button says while an operation is running, so the screen's own state says why
#: nothing is responding rather than leaving a dead-looking button (`NFR-006`'s spirit).
YTDLP_WORKING_LABEL: Final = "Working…"


@dataclass(frozen=True, slots=True)
class Req023Setting:
    """One of the settings `REQ-023` names, and the control that implements it (`T-227`).

    `key` is the machine-readable name the records are keyed by — it appears in
    `docs/DEVELOPMENT.md` and `docs/UX_SPEC.md` as an HTML comment, which every renderer ignores
    and no rewording can disturb. `name` is what the screen would call it in the *still to come*
    sentence. `control` is the object name of the widget that implements it, or **empty** where
    nothing does yet.
    """

    key: str
    name: str
    control: str

    @property
    def built(self) -> bool:
        return bool(self.control)


#: **The one place that says which `REQ-023` settings this screen implements** (`T-227`).
#:
#: Everything else is derived from it or checked against it: the screen's own *still to come*
#: sentence below, the coverage table in `docs/DEVELOPMENT.md`, and the count in
#: `docs/UX_SPEC.md` §2. That is the whole of this structure's job — before it, five records
#: described the same fact and **all five rotted at once**, hours after the task that changed the
#: fact was approved (`T-195`'s sixth criterion, found by a walkthrough rather than by any gate).
#:
#: **A control name rather than a boolean**, because a boolean is a claim and a name is checkable:
#: `test_every_setting_this_screen_claims_is_actually_on_it` builds the screen and looks each one
#: up, so a setting declared built and not built fails here rather than in a document.
REQ_023_SETTINGS: Final[tuple[Req023Setting, ...]] = (
    Req023Setting("download-directory", "the download folder", "chooseDownloadDirectory"),
    Req023Setting("default-preset", "the default preset", DEFAULT_PRESET_NAME),
    Req023Setting("concurrency", "the concurrency limit", "settingsConcurrencyChoice"),
    Req023Setting("output-template", "the output template", OUTPUT_TEMPLATE_NAME),
    Req023Setting("ffmpeg-location", "the ffmpeg location", "chooseFfmpegLocation"),
    Req023Setting("network-options", "network options", PROXY_NAME),
    Req023Setting("cookie-source", "the cookie source", "cookieSourceNone"),
    Req023Setting("theme", "the theme", "themeLight"),
)


def still_to_come(settings: Sequence[Req023Setting] = REQ_023_SETTINGS) -> str:
    """The screen's own statement of what it does not yet cover (`T-146`, derived by `T-227`).

    **Derived rather than written**, which is the correction: this was a hand-maintained sentence
    beside a hand-maintained screen, and the two agreed only for as long as somebody remembered
    both. Now a setting whose control is empty puts its own name back on the screen, and one that
    gains a control takes it off — there is no edit that can make the sentence lie.

    Empty when every setting is built, and the label is then not built at all: a screen announcing
    *"nothing is missing"* is a claim that goes stale the moment something is, while an absent
    label is simply the shape of a covered requirement.

    **The parameter is what keeps this testable now that all eight are built** (`T-227`). With
    nothing unbuilt, a body replaced by `return ""` is indistinguishable from the real one — the
    mutation survived exactly that way — so the derivation is a function *over a declaration*
    rather than over the module's own, and the gate feeds it one with a gap in it.
    """
    missing = [setting.name for setting in settings if not setting.built]
    return f"Still to come: {', '.join(missing)}." if missing else ""


SETTINGS_STILL_TO_COME: Final = still_to_come()


class SettingsDialog(QDialog):
    """One screen for the settings `REQ-023` names and this phase has built."""

    def __init__(
        self,
        *,
        download_directory: Path,
        directory_is_default: bool,
        theme: str,
        concurrency: int,
        on_directory_chosen: Callable[[Path | None], None],
        on_theme_chosen: Callable[[str], None],
        on_concurrency_chosen: Callable[[int], None],
        choose_directory: Callable[[Path], Path | None] | None = None,
        cookie_file: Path | None = None,
        cookie_browser: str | None = None,
        on_cookie_file_chosen: Callable[[Path | None], None] | None = None,
        on_cookie_browser_chosen: Callable[[str | None], None] | None = None,
        network: NetworkOptions | None = None,
        on_network_chosen: Callable[[NetworkOptions], None] | None = None,
        ffmpeg_location: Path | None = None,
        ffmpeg_summary: str = "",
        on_ffmpeg_location_chosen: Callable[[Path | None], None] | None = None,
        choose_file: Callable[[Path | None], Path | None] | None = None,
        preset_names: Sequence[str] = (),
        default_preset: str = "",
        output_template: str = "",
        shipped_template: str = "",
        on_default_preset_chosen: Callable[[str], None] | None = None,
        on_output_template_chosen: Callable[[str], None] | None = None,
        refuse_template: Callable[[str], str | None] | None = None,
        on_ytdlp_update: Callable[[], None] | None = None,
        on_ytdlp_revert: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_directory_chosen = on_directory_chosen
        self._on_theme_chosen = on_theme_chosen
        self._on_concurrency_chosen = on_concurrency_chosen
        self._choose_directory = choose_directory or self._ask_for_a_directory
        self._directory = download_directory
        self._directory_is_default = directory_is_default
        # Held before the sections are built, because each one reads its own starting value.
        self._theme = theme
        self._initial_concurrency = concurrency
        self._cookie_file = cookie_file
        self._cookie_browser = cookie_browser
        self._on_cookie_file_chosen = on_cookie_file_chosen
        self._on_cookie_browser_chosen = on_cookie_browser_chosen
        #: The network options in force. Held whole rather than as three values, so a change to
        #: one control writes the other two back exactly as they were — a screen that rebuilt the
        #: trio from its own widgets would re-round a hand-edited rate limit on an unrelated edit.
        self._network = network if network is not None else NetworkOptions()
        self._on_network_chosen = on_network_chosen
        self._ffmpeg_location = ffmpeg_location
        self._ffmpeg_summary = ffmpeg_summary
        self._on_ffmpeg_location_chosen = on_ffmpeg_location_chosen
        self._choose_file = choose_file or self._ask_for_a_file
        self._preset_names = tuple(preset_names)
        self._default_preset = default_preset
        self._output_template = output_template
        #: What an empty template resolves to, shown as the field's placeholder so *empty* reads as
        #: a choice with a visible consequence rather than as a blank (`T-195`).
        self._shipped_template = shipped_template
        self._on_default_preset_chosen = on_default_preset_chosen
        #: Why a template cannot be used, or `None` (`T195-R2`).
        #:
        #: **Injected, because the authoritative answer lives behind the manager.** The first build
        #: called `unsupported_refusal` here, which checks *field names only* — so `%(title`, whose
        #: syntax yt-dlp itself rejects, and `../%(title)s.%(ext)s`, which escapes the download
        #: folder, were both accepted and stored. `DownloadManager.preview_output_path` is the
        #: check the per-row editor makes: yt-dlp's own syntax parser, the field names, a real
        #: render, and containment. `ui/` may not reach `ytdlp_adapter` (`ARCHITECTURE.md` §6), so
        #: composition hands the route in rather than this screen learning the syntax.
        #:
        #: `None` falls back to the field-name check, which is what a screen built without a
        #: manager can honestly do — and is why `refuse_template` is what composition always
        #: passes.
        self._refuse_template = refuse_template
        self._on_output_template_chosen = on_output_template_chosen
        self._on_ytdlp_update = on_ytdlp_update
        self._on_ytdlp_revert = on_ytdlp_revert
        #: Whether the yt-dlp in use came from the user's own copy, so reverting means something.
        #: Held here rather than read back off the button — see `show_ytdlp`.
        self._ytdlp_is_user_managed = False

        self.setObjectName("settingsDialog")
        self.setWindowTitle("Settings")

        # **The sections scroll; `Close` does not** (`T-242`). Eight settings ask for 1407 pixels
        # of height, and a 1080p display has about a thousand to give — so without this the whole
        # screen is compressed and what gives way is the wrapped explanatory text. Measured, at the
        # screen's own `sizeHint`: the cookies sentence got 23 pixels of the 51 it needs, and the
        # network one 38 of 85, which cut *"does not unlock anything your account cannot already
        # reach"* and the sentence naming which retry the retry control governs in half.
        #
        # **The button box stays outside**, so the way out of the screen is never scrolled off.
        sections = QWidget(self)
        sections.setObjectName("settingsSections")
        inner = QVBoxLayout(sections)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(self._build_downloads_section())
        inner.addWidget(self._build_naming_section())
        inner.addWidget(self._build_cookies_section())
        inner.addWidget(self._build_network_section())
        inner.addWidget(self._build_ffmpeg_section())
        inner.addWidget(self._build_appearance_section())
        inner.addWidget(self._build_queue_section())
        inner.addWidget(self._build_ytdlp_section())

        if SETTINGS_STILL_TO_COME:
            # **Built only when there is something to say** (`T-196`). An empty label is not
            # nothing: it is a widget in the layout, a stop for a screen reader walking the
            # dialog, and a line of space where the user reads a claim about coverage. With every
            # `REQ-023` setting built there is no claim to make.
            remaining = QLabel(SETTINGS_STILL_TO_COME, sections)
            remaining.setObjectName("settingsRemaining")
            remaining.setTextFormat(Qt.TextFormat.PlainText)
            remaining.setWordWrap(True)
            inner.addWidget(remaining)
        inner.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setObjectName(SETTINGS_SCROLL_NAME)
        # **Resizable, so the sections take the width and give back the height they need.** A
        # non-resizable scroll area would keep the container at its `sizeHint` width and scroll
        # sideways, and a wrapped label's height depends on the width it is given — so the
        # horizontal scroll bar would be buying back the very clipping this exists to remove.
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(sections)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.setObjectName("settingsButtons")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # **Opens at the height its contents want, and no taller than the screen it is on**
        # (`T-242`). Both halves are needed and neither is the dialog's own `sizeHint`: a scroll
        # area asks for very little — 463 pixels, measured — so sizing to the hint would open a
        # screen that scrolls from the first section, and sizing to the contents alone would open
        # one taller than the display, which is the state this task was filed about.
        wanted = QSize(
            sections.sizeHint().width() + scroll.verticalScrollBar().sizeHint().width(),
            sections.sizeHint().height() + buttons.sizeHint().height() + _BUTTON_ROW_ROOM,
        )
        self.resize(wanted.boundedTo(self._room_on_screen()))

        #: The scrolling region and what it holds, kept so focus can be followed into view.
        self._scroll = scroll
        self._sections = sections
        # **Focus has to drag the view with it, and Qt does not do it here** (`T-242`, measured).
        # `QScrollArea` scrolls to a widget when *it* resolves the focus move, and in a dialog the
        # dialog owns the tab chain — so tabbing through this screen left **31 of 40 tab stops
        # focused while invisible** and the scroll bar never moved off zero. That is a worse defect
        # than the clipping this task set out to fix, and it is exactly the shape `T-200` audits.
        #
        # Application-wide because focus arrives from everywhere — Tab, Shift-Tab, a click, a
        # mnemonic — and one signal covers every route rather than the routes anybody listed.
        # `instance()` is typed as the *core* application, which has no focus to change — so the
        # narrowing is the check rather than an assertion dressed as one.
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.focusChanged.connect(self._follow_focus)

        # **No button on this screen answers to Return** (`T196-R1`, found while building its
        # evidence). A `QPushButton` in a dialog is `autoDefault` by default, so Return anywhere —
        # including in a text field — activates the first one, which here is *Choose folder…* and
        # opens a **native modal file picker**. That made Return in the proxy box open a folder
        # chooser instead of finishing the edit, and it was already true of the template field.
        #
        # Safe because this screen has no default action to lose: every control applies as it is
        # changed (see the module docstring), and `Close` is reached by Esc and by clicking it.
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)

    def _follow_focus(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Scroll a control into view when it takes focus (`T-242`, `NFR-005`).

        **Only for controls inside the scrolling region**, because this listens to the whole
        application: focus moving in the main window behind an open Settings screen must not
        scroll this one.

        `ensureWidgetVisible`'s margins are what stop a control landing hard against the edge of
        the viewport, where a group box's own frame reads as though the control were cut off.
        """
        if new is None or not self._sections.isAncestorOf(new):
            return
        self._scroll.ensureWidgetVisible(new, _FOCUS_MARGIN, _FOCUS_MARGIN)

    def _room_on_screen(self) -> QSize:
        """How much of the display this dialog may take, in pixels (`T-242`).

        **The dialog's own screen, and `availableGeometry` rather than the raw size.** Its own,
        because a dialog is parented to the main window and follows it onto whichever display that
        is — `T242-R1` is this reading the primary display instead. Available, because a panel or
        a dock is height this window will never get, and a dialog that opens taller than the
        working area is the state the scroll area exists to survive rather than one to open in.

        Reduced a little further: a dialog exactly as tall as the working area sits under its own
        title bar, whose height is the window manager's and not knowable here.

        Falls back to a generous constant where there is no screen at all — an offscreen test, a
        headless run — because guessing small there would make every such test measure a scroll
        bar rather than the layout.
        """
        # **The display this dialog is *on*, not the primary one** (`T242-R1`). This asked
        # `primaryScreen()` while its own call site claimed *"the screen it is on"*, and on a
        # two-monitor desk those are different answers: a main window on a 768-high secondary
        # display would open Settings against the 1080-high primary's room — recreating the
        # off-screen dialog this task exists to remove, at exactly the working area the acceptance
        # criterion names.
        #
        # **Annotated optional because the stub over-promises.** PySide6 types both `screen()` and
        # `primaryScreen()` as always answering; `primaryScreen()` genuinely returns `None` on a
        # platform with no screen at all, and a crash in the settings screen because a stub said
        # it could not happen is not a trade worth taking. Written as an annotation rather than a
        # `cast` so the guard below stays reachable to `mypy` and the reason stays readable.
        # `screen()` is typed as always answering and is `None` on a widget that has never been
        # shown on any display, which is every offscreen construction — so the fallback is reached
        # in tests as well as in the headless case, and the annotation is what keeps both visible
        # to `mypy`.
        associated: QScreen | None = self.screen()
        screen: QScreen | None = (
            associated if associated is not None else QApplication.primaryScreen()
        )
        if screen is None:
            return QSize(_NO_SCREEN_WIDTH, _NO_SCREEN_HEIGHT)
        room = screen.availableGeometry().size()
        return QSize(room.width() - _WINDOW_CHROME, room.height() - _WINDOW_CHROME)

    # --- downloads ----------------------------------------------------------------------

    def _build_downloads_section(self) -> QWidget:
        box = QGroupBox("Downloads", self)
        box.setObjectName("downloadsSection")
        layout = QVBoxLayout(box)

        # **Typed as well as chosen** (`T-292`). This was a `QLabel`, so a path already on the
        # clipboard could not be pasted and a deep tree had to be walked in the picker.
        #
        # **It commits on `editingFinished` and `Return`, never per keystroke** — a deliberate
        # exception to the screen's *"every control applies as it is changed"* rule
        # (`docs/PHASE_4_CHECKLIST.md` row 6.2), because applying as typed would set `/h`, then
        # `/ho`, then `/hom`, each of them a different destination.
        self._directory_field = QLineEdit(box)
        self._directory_field.setObjectName("downloadDirectoryValue")
        self._directory_field.setAccessibleName("Download folder")
        self._directory_field.setClearButtonEnabled(False)
        self._directory_field.editingFinished.connect(self._directory_typed)
        layout.addWidget(self._directory_field)

        # **The caption is gone** (`T-292`, maintainer's direction). It read *"Your usual downloads
        # folder"* when the folder was the platform default and the empty string otherwise — a
        # label reserving a line to say nothing, which is what the run photographed.
        #
        # **What went with it, recorded so it is not restored as an oversight:** nothing now
        # distinguishes *this is the platform default* from *I chose a folder that happens to be
        # the default*. `Use the default folder` is still the way back, so the capability survives
        # and only the statement is gone.
        #
        # **This is not that caption returning.** It holds a refusal or nothing at all, which is
        # the shape `_template_note` already uses for the same job one section down: the message
        # belongs beside the control it is about, where the user is looking.
        self._directory_problem = QLabel(box)
        self._directory_problem.setObjectName(DOWNLOAD_DIRECTORY_PROBLEM_NAME)
        # The refusal quotes the path, which is the user's own text (`T016-R6`).
        self._directory_problem.setTextFormat(Qt.TextFormat.PlainText)
        self._directory_problem.setWordWrap(True)
        layout.addWidget(self._directory_problem)

        row = QHBoxLayout()
        choose = QPushButton("Choose folder...", box)
        choose.setObjectName("chooseDownloadDirectory")
        choose.setAccessibleName("Choose the download folder")
        choose.clicked.connect(self._pick_a_directory)
        row.addWidget(choose)

        self._use_default = QPushButton("Use the default folder", box)
        self._use_default.setObjectName("useDefaultDownloadDirectory")
        self._use_default.setAccessibleName("Use the default download folder")
        self._use_default.clicked.connect(lambda: self._remember(None))
        row.addWidget(self._use_default)
        row.addStretch(1)
        layout.addLayout(row)

        self._show_directory()
        return box

    def _show_directory(self) -> None:
        """Put the folder in force on screen, clearing any refusal it answers."""
        self._directory_field.setText(str(self._directory))
        self._directory_problem.setText("")
        # Nothing to clear when nothing was chosen. Disabled rather than hidden, so the row does
        # not change shape under the pointer (`T-060`'s rule for the retry button).
        self._use_default.setEnabled(not self._directory_is_default)

    def _ask_for_a_directory(self, start: Path) -> Path | None:
        """The real picker. Replaced in tests, for the reason the module docstring gives."""
        chosen = QFileDialog.getExistingDirectory(self, "Choose the download folder", str(start))
        return Path(chosen) if chosen else None

    def _pick_a_directory(self) -> None:
        chosen = self._choose_directory(self._directory)
        if chosen is None:
            # Cancelled. **Not the same as "use the default"** — that is the other button, and
            # collapsing the two would let a mis-click silently move where files land.
            return
        self._remember(chosen)

    def _directory_typed(self) -> None:
        """Take a typed folder, or refuse it and put the one in force back (`T-292`).

        **A folder that does not exist is refused** — ruled 2026-08-28. It is not created, and the
        user is not offered the chance to create it: a typo would otherwise leave a stray folder
        somewhere in their home directory, silently.

        **The refusal restores the field**, because a screen that keeps showing a path it did not
        accept is a screen that lies about where files will land. `T109-R2`'s rule, one control
        over: what the user can see must be what is in force.

        Whitespace and `~` are handled before the check, so *"it does not exist"* is never said
        about a path the user did not type — `~/Videos` is a folder they can reasonably expect this
        field to understand.

        **Reading the path is itself something that fails, so it is inside the guard** (`T292-R1`).
        `expanduser()` sat above every refusal, and `~someone-who-left/downloads` raises
        `RuntimeError` — measured: *"Could not determine home directory."* — so the exception left
        the slot, no refusal was shown, and the field kept the text that caused it. That is
        `T146-R1` exactly, one layer up: `core.settings` already documents and catches this in its
        never-raises loader. `absolute()` raises `FileNotFoundError` when the working directory has
        been deleted under the process, also measured. `ValueError` is **not** caught, for
        `core.settings`' reason: `is_dir()` answers False for a path holding a NUL rather than
        raising, so `os.access` is never reached with one and nothing here can produce it.

        **A relative path is made absolute before it leaves this screen** (`T292-R2`).
        `PosixPath('.')` went out to composition unchanged, and a stored path with no root is
        resolved against whatever directory the process was started in — so the same setting names
        a different folder on the next launch, silently. `absolute()` rather than `resolve()`: a
        user whose `~/Downloads` is a symlink means the link, and following it would store the
        target and stop the setting tracking the link. The absolute spelling goes back on screen
        through `_remember`, so what was accepted is what is shown.
        """
        typed = self._directory_field.text().strip()
        if not typed:
            self._show_directory()
            return
        try:
            candidate = Path(typed).expanduser().absolute()
        except (OSError, RuntimeError) as error:
            # **Named as written, not as expanded** — when the expansion is what failed there is no
            # expanded path to name. `core.settings` reaches the same wording the same way.
            self._refuse_directory(
                f"{typed} could not be read as a folder. Nothing was changed.\n"
                f"{type(error).__name__}: {error}"
            )
            return
        if candidate == self._directory:
            # Retyping the folder in force is not a change, but a relative spelling of it is still
            # text this screen would rather not leave on display: settle it back to the absolute
            # one, and clear any refusal the retype answers.
            self._show_directory()
            return
        if not candidate.is_dir():
            self._refuse_directory(
                f"{candidate} is not a folder that exists. Nothing was changed."
                if not candidate.exists()
                else f"{candidate} is a file, not a folder. Nothing was changed."
            )
            return
        if not os.access(candidate, os.W_OK):
            self._refuse_directory(f"{candidate} cannot be written to. Nothing was changed.")
            return
        self._remember(candidate)

    def _refuse_directory(self, why: str) -> None:
        """Say why, where the user is looking, and put the folder in force back on screen."""
        self._show_directory()
        self._directory_problem.setText(why)

    def _remember(self, directory: Path | None) -> None:
        self._on_directory_chosen(directory)
        self._directory_is_default = directory is None
        if directory is not None:
            self._directory = directory
            self._show_directory()

    def show_download_directory(self, directory: Path, *, is_default: bool) -> None:
        """Show the folder composition resolved, after this screen asked for a change.

        Called back rather than assumed, because *"use the default"* is a request whose answer —
        the platform's downloads folder — is composition's to compute and not this screen's to
        guess (`ARC-007`: `ui/` holds no settings writer and no platform paths).
        """
        self._directory = directory
        self._directory_is_default = is_default
        self._show_directory()

    # --- cookies ------------------------------------------------------------------------

    def _build_naming_section(self) -> QWidget:
        """What a new paste starts with, and how its file is named (`REQ-023`, `T-195`)."""
        box = QGroupBox("New downloads", self)
        box.setObjectName("namingSection")
        layout = QVBoxLayout(box)

        preset_label = QLabel("Preset a newly pasted URL starts with", box)
        preset_label.setWordWrap(True)
        layout.addWidget(preset_label)

        self._preset_choice = QComboBox(box)
        # **The label is the combo's buddy, and on Linux that is the only thing naming it**
        # (`T200-R7`). `QAccessibleComboBox::text` falls through `Name` to `Value` under
        # `Q_OS_UNIX` — Qt's own comment says *"on Linux we use relations for this"* — so a combo
        # box publishes its **selected item** as its accessible name and discards
        # `setAccessibleName` entirely. Measured: this control announced *"Best video up to 1080p
        # (MP4)"* as both its name and its value, and deleting its accessible name changed nothing.
        # `setBuddy` publishes the `Label` relation the platform reads instead, and costs no
        # layout: the label was already here and already said what the control is for.
        preset_label.setBuddy(self._preset_choice)
        self._preset_choice.setObjectName(DEFAULT_PRESET_NAME)
        self._preset_choice.setAccessibleName("Default preset")
        for name in self._preset_names:
            self._preset_choice.addItem(name, name)
        if self._default_preset:
            found = self._preset_choice.findData(self._default_preset)
            if found >= 0:
                self._preset_choice.setCurrentIndex(found)
        # **Disabled with the reason beside it, never drawn dead** (`UX-005` §5, `P-13`). A caller
        # that supplies no names and no writer has nothing to choose between.
        self._preset_choice.setEnabled(
            bool(self._preset_names) and self._on_default_preset_chosen is not None
        )
        self._preset_choice.currentIndexChanged.connect(self._on_preset_index)
        layout.addWidget(self._preset_choice)

        self._preset_note = QLabel(box)
        self._preset_note.setObjectName("defaultPresetNote")
        self._preset_note.setWordWrap(True)
        self._preset_note.setText(
            "" if self._preset_choice.isEnabled() else "No presets are available to choose between."
        )
        layout.addWidget(self._preset_note)

        template_label = QLabel(
            "How downloads are named, when a preset does not say otherwise", box
        )
        template_label.setWordWrap(True)
        layout.addWidget(template_label)

        self._template_field = QLineEdit(box)
        self._template_field.setObjectName(OUTPUT_TEMPLATE_NAME)
        self._template_field.setAccessibleName("Default output template")
        self._template_field.setText(self._output_template)
        self._template_field.setPlaceholderText(self._shipped_template)
        self._template_field.setEnabled(self._on_output_template_chosen is not None)
        # **Checked as it is typed, written only when it is usable** (`P-23`, `T-195`). `T-112`
        # made the same call for the per-row editor: showing the error and storing the value
        # anyway satisfies the visible half of the criterion and queues a broken download.
        self._template_field.textChanged.connect(self._on_template_text)
        layout.addWidget(self._template_field)

        self._template_note = QLabel(box)
        self._template_note.setObjectName(OUTPUT_TEMPLATE_NOTE_NAME)
        # The refusal quotes the template, which is the user's own text (`T016-R6`).
        self._template_note.setTextFormat(Qt.TextFormat.PlainText)
        self._template_note.setWordWrap(True)
        layout.addWidget(self._template_note)

        return box

    def _on_preset_index(self, index: int) -> None:
        if self._on_default_preset_chosen is None or index < 0:
            return
        chosen = self._preset_choice.itemData(index)
        if isinstance(chosen, str) and chosen:
            self._on_default_preset_chosen(chosen)

    def _on_template_text(self, text: str) -> None:
        """Refuse at edit time, with the reason, and do not store what was refused.

        **The same check the per-row editor makes**, reached through
        `core.output_template.unsupported_refusal` — which is what `manager.preview_output_path`
        calls, so the editor and this screen cannot come to disagree about what a usable template
        is. A second implementation of the rule is the defect `ARC-002` reasons about.
        """
        if self._on_output_template_chosen is None:
            return
        refusal = self._refusal_for(text) if text else None
        self._template_note.setText(refusal or "")
        if refusal is None:
            self._on_output_template_chosen(text)

    def _refusal_for(self, template: str) -> str | None:
        """The authoritative refusal where composition supplied one (`T195-R2`)."""
        if self._refuse_template is not None:
            return self._refuse_template(template)
        return unsupported_refusal(template)

    def show_preset_names(self, names: Sequence[str], default: str) -> None:
        """Re-offer the catalogue, keeping the stored default selected (`T195-R5`).

        **An open screen has to follow a live ffmpeg change.** Accepting an ffmpeg location makes
        presets performable that were not a moment ago, and a combo built when the screen opened
        went on offering the smaller list — so the user saw one preset while the add dialog offered
        four, with restart the only way out and nothing saying so.

        Rebuilt wholesale rather than diffed: the list is five entries, and a patch would be a
        second opinion about what the catalogue is.
        """
        self._preset_names = tuple(names)
        blocked = self._preset_choice.blockSignals(True)
        try:
            self._preset_choice.clear()
            for name in self._preset_names:
                self._preset_choice.addItem(name, name)
            found = self._preset_choice.findData(default)
            if found >= 0:
                self._preset_choice.setCurrentIndex(found)
        finally:
            self._preset_choice.blockSignals(blocked)
        self._preset_choice.setEnabled(
            bool(self._preset_names) and self._on_default_preset_chosen is not None
        )
        self._preset_note.setText(
            "" if self._preset_choice.isEnabled() else "No presets are available to choose between."
        )

    def show_default_preset(self, name: str) -> None:
        """Reflect the stored default, so the screen never disagrees with the file."""
        found = self._preset_choice.findData(name)
        if found >= 0 and found != self._preset_choice.currentIndex():
            blocked = self._preset_choice.blockSignals(True)
            self._preset_choice.setCurrentIndex(found)
            self._preset_choice.blockSignals(blocked)

    def show_output_template(self, template: str) -> None:
        """Reflect the stored template, without echoing it back through the writer."""
        if template == self._template_field.text():
            return
        blocked = self._template_field.blockSignals(True)
        self._template_field.setText(template)
        self._template_field.blockSignals(blocked)
        self._template_note.setText("")

    def _build_cookies_section(self) -> QWidget:
        """A cookies file for content the user is already signed in to (`REQ-026`, `T-197`)."""
        box = QGroupBox("Cookies", self)
        box.setObjectName("cookiesSection")
        layout = QVBoxLayout(box)

        explanation = QLabel(COOKIES_EXPLANATION, box)
        explanation.setObjectName("cookiesExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        #: **Three exclusive sources**, because `REQ-026` says *a browser profile **or** a cookies
        #: file*, and two set at once is a credential chosen by accident (`T197-R4`).
        self._cookie_sources: dict[str, QRadioButton] = {}
        for key, label in (
            ("none", "No cookies"),
            ("browser", "From a browser"),
            ("file", "From a cookies file"),
        ):
            button = QRadioButton(label, box)
            button.setObjectName(f"cookieSource{key.capitalize()}")
            button.setAccessibleName(label)
            button.toggled.connect(partial(self._cookie_source_picked, key))
            layout.addWidget(button)
            self._cookie_sources[key] = button

        # **This control had no label at all**, for anyone (`T200-R7`). It followed three radio
        # buttons, and a `QRadioButton` cannot be a buddy — so the only thing the accessibility
        # tree had to name it with was the group box, *"Cookies"*, which is the name of the section
        # rather than of the choice. Sighted users were reading it from the radio above it by
        # proximity; a screen reader has no proximity.
        browser_label = QLabel("Browser to read cookies from", box)
        browser_label.setObjectName("cookieBrowserLabel")
        browser_label.setWordWrap(True)
        layout.addWidget(browser_label)

        self._cookie_browser_choice = QComboBox(box)
        self._cookie_browser_choice.setObjectName("cookieBrowserChoice")
        self._cookie_browser_choice.setAccessibleName("Browser to read cookies from")
        browser_label.setBuddy(self._cookie_browser_choice)
        for browser in BROWSER_NAMES:
            self._cookie_browser_choice.addItem(browser)
        self._cookie_browser_choice.currentTextChanged.connect(self._cookie_browser_picked)
        layout.addWidget(self._cookie_browser_choice)

        self._cookie_value = QLabel(box)
        self._cookie_value.setObjectName("cookieFileValue")
        # The user's own path (`T016-R6`).
        self._cookie_value.setTextFormat(Qt.TextFormat.PlainText)
        self._cookie_value.setWordWrap(True)
        self._cookie_value.setAccessibleName("Cookies file")
        layout.addWidget(self._cookie_value)

        row = QHBoxLayout()
        choose = QPushButton("Choose cookies file...", box)
        choose.setObjectName("chooseCookieFile")
        choose.setAccessibleName("Choose a cookies file")
        choose.clicked.connect(self._pick_a_cookie_file)
        row.addWidget(choose)

        self._clear_cookies = QPushButton("Use no cookies", box)
        self._clear_cookies.setObjectName("clearCookieFile")
        self._clear_cookies.setAccessibleName("Use no cookies")
        self._clear_cookies.clicked.connect(lambda: self._remember_cookies(None))
        row.addWidget(self._clear_cookies)
        row.addStretch(1)
        layout.addLayout(row)

        self._show_cookie_file()
        return box

    def _show_cookie_file(self) -> None:
        self._cookie_value.setText(
            str(self._cookie_file) if self._cookie_file is not None else NO_COOKIES_NOTE
        )
        self._clear_cookies.setEnabled(self._cookie_file is not None)
        current = (
            "file"
            if self._cookie_file is not None
            else "browser"
            if self._cookie_browser is not None
            else "none"
        )
        for key, button in self._cookie_sources.items():
            blocked = button.blockSignals(True)
            try:
                button.setChecked(key == current)
            finally:
                button.blockSignals(blocked)
        self._cookie_browser_choice.setEnabled(current == "browser")
        self._clear_cookies.setEnabled(self._cookie_file is not None)
        if self._cookie_browser:
            blocked = self._cookie_browser_choice.blockSignals(True)
            try:
                self._cookie_browser_choice.setCurrentText(
                    self._cookie_browser.split(":", 1)[0].split("+", 1)[0]
                )
            finally:
                self._cookie_browser_choice.blockSignals(blocked)

    def _cookie_source_picked(self, key: str, checked: bool) -> None:
        """One source at a time. Choosing *browser* asks for the one the combo shows."""
        if not checked:
            return
        if key == "none":
            self._remember_cookies(None)
        elif key == "browser":
            self._remember_browser(self._cookie_browser_choice.currentText())
        elif key == "file":
            self._pick_a_cookie_file()

    def _cookie_browser_picked(self, browser: str) -> None:
        if self._cookie_sources["browser"].isChecked():
            self._remember_browser(browser)

    def _remember_browser(self, browser: str | None) -> None:
        if self._on_cookie_browser_chosen is not None:
            self._on_cookie_browser_chosen(browser)

    def show_cookie_browser(self, browser: str | None) -> None:
        """Show the browser source composition settled on (`T197-R4`)."""
        self._cookie_browser = browser
        if browser is not None:
            self._cookie_file = None
        self._show_cookie_file()

    def _pick_a_cookie_file(self) -> None:
        chosen = self._choose_file(self._cookie_file)
        if chosen is None:
            # **Cancelled leaves nothing behind, including the radio** (`T197-R4`). Selecting
            # *From a cookies file* moves the button before the dialog opens, so dismissing it left
            # the screen claiming a source that was never set — and *No cookies* still selected
            # underneath in the settings. Redrawn from the state actually in force.
            self._show_cookie_file()
            return
        self._remember_cookies(chosen)

    def _remember_cookies(self, path: Path | None) -> None:
        if self._on_cookie_file_chosen is not None:
            self._on_cookie_file_chosen(path)

    def show_cookie_source(self, file: Path | None, browser: str | None) -> None:
        """Show the source actually in force — **both halves, always** (`T197-R4`).

        `show_cookie_file(None)` used to mean *no file*, which is not the same as *no cookies*: it
        left a previously chosen browser on screen after the user asked for neither. One method
        taking the pair removes the class rather than the instance — there is no way to tell the
        screen half of a change.
        """
        self._cookie_file = file
        self._cookie_browser = browser
        self._show_cookie_file()

    def show_cookie_file(self, path: Path | None) -> None:
        """The file half, kept for callers that only have one (`T-197`)."""
        self.show_cookie_source(path, None if path is not None else self._cookie_browser)

    # --- network ------------------------------------------------------------------------

    def _build_network_section(self) -> QWidget:
        """Proxy, speed limit and retries — `REQ-023`'s network options (`T-196`)."""
        box = QGroupBox("Network", self)
        box.setObjectName("networkSection")
        layout = QVBoxLayout(box)

        explanation = QLabel(NETWORK_EXPLANATION, box)
        explanation.setObjectName("networkExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        proxy_label = QLabel("Proxy", box)
        proxy_label.setObjectName("networkProxyLabel")
        layout.addWidget(proxy_label)

        self._proxy_field = QLineEdit(box)
        self._proxy_field.setObjectName(PROXY_NAME)
        self._proxy_field.setAccessibleName("Proxy")
        self._proxy_field.setText(self._network.proxy or "")
        # The placeholder is what an empty box *means*, not an example to be mistaken for a value
        # in force — the same job `DEFAULT_DIRECTORY_NOTE` and `FFMPEG_ON_PATH_NOTE` do for their
        # settings. The accepted form is in the note under it, where a refusal will appear too.
        self._proxy_field.setPlaceholderText("No proxy")
        self._proxy_field.setEnabled(self._on_network_chosen is not None)
        # **Checked as it is typed; written only when the edit is finished** (`T196-R1`, Critical).
        #
        # The template field one section up writes on `textChanged`, and copying that here put a
        # password in `settings.toml`. Typing `http://alice:hunter2@proxy.invalid:8080` passes
        # through the prefix `http://alice:hunter2` — which is a *valid* proxy by any grammar,
        # because `alice` is a host and `hunter2` is where a port goes — and that prefix was
        # committed and saved one keystroke before the `@` arrived and the value was refused.
        #
        # **No grammar can close this, and that is why the fix is the connection rather than the
        # validator.** `http://alice:12345` is a numeric password and a legal `host:port`; the two
        # are the same string. So a keystroke shows a refusal and nothing else, and the value is
        # committed when the user has finished with the field — `editingFinished` covers Return
        # and focus leaving, and `done` covers the dialog being closed while it still has focus.
        self._proxy_field.textChanged.connect(self._show_proxy_refusal)
        self._proxy_field.editingFinished.connect(self._commit_proxy)
        layout.addWidget(self._proxy_field)

        self._proxy_note = QLabel(box)
        self._proxy_note.setObjectName(PROXY_NOTE_NAME)
        # A refusal quotes the value the user typed, which is their own text (`T016-R6`) — and may
        # be a credential, so it is never given rich-text treatment.
        self._proxy_note.setTextFormat(Qt.TextFormat.PlainText)
        self._proxy_note.setWordWrap(True)
        layout.addWidget(self._proxy_note)

        rate_row = QHBoxLayout()
        rate_label = QLabel("Speed limit for each download", box)
        rate_label.setObjectName("networkRateLimitLabel")
        rate_row.addWidget(rate_label)

        self._rate_limit = QSpinBox(box)
        self._rate_limit.setObjectName(RATE_LIMIT_NAME)
        self._rate_limit.setAccessibleName("Speed limit for each download, in KiB per second")
        # **The bound is the settings layer's**, read from it rather than restated here — the rule
        # `REQ-013`'s concurrency range already follows, and the reason `RATE_LIMIT_MAXIMUM_BYTES`
        # exists at all is that a stored value has to be displayable by this control.
        self._rate_limit.setRange(0, RATE_LIMIT_MAXIMUM_BYTES // RATE_LIMIT_STEP_BYTES)
        self._rate_limit.setSuffix(" KiB/s")
        self._rate_limit.setSpecialValueText(NO_RATE_LIMIT_LABEL)
        self._rate_limit.setValue(self._rate_limit_shown())
        self._rate_limit.setEnabled(self._on_network_chosen is not None)
        self._rate_limit.valueChanged.connect(self._on_rate_limit_value)
        rate_row.addWidget(self._rate_limit)
        rate_row.addStretch(1)
        layout.addLayout(rate_row)

        retries_row = QHBoxLayout()
        retries_label = QLabel("Retries of the file transfer, within one attempt", box)
        retries_label.setObjectName("networkRetriesLabel")
        retries_label.setWordWrap(True)
        retries_row.addWidget(retries_label)

        self._retries = QSpinBox(box)
        self._retries.setObjectName(RETRIES_NAME)
        # **The name says which retry this is, and there are three** (`T-196`, ruled 2026-08-13;
        # sharpened by `T196-R5`). A queued download that fails is offered again by the queue
        # itself (`REQ-015`, `REQ-018`) and a network failure retries by itself — that is the
        # first, and it has no control because two things governing one decision is `T-075`. This
        # is the second: yt-dlp's `--retries`, the file transfer's own, inside one attempt. The
        # third is `--fragment-retries`, which covers the pieces of a segmented stream, is *also*
        # inside one attempt, and is **not** this setting — so "within one attempt" alone did not
        # separate them, and a user setting this to zero would still see pieces retrying.
        self._retries.setAccessibleName("Retries of the file transfer, within one attempt")
        self._retries.setRange(-1, RETRIES_MAXIMUM)
        self._retries.setSpecialValueText(DEFAULT_RETRIES_LABEL)
        self._retries.setValue(self._network.retries if self._network.retries is not None else -1)
        self._retries.setEnabled(self._on_network_chosen is not None)
        self._retries.valueChanged.connect(self._on_retries_value)
        retries_row.addWidget(self._retries)
        retries_row.addStretch(1)
        layout.addLayout(retries_row)

        return box

    def _rate_limit_shown(self) -> int:
        """The stored limit as whole KiB/s, or `0` for none — see `RATE_LIMIT_STEP_BYTES`."""
        stored = self._network.rate_limit_bytes
        return 0 if stored is None else stored // RATE_LIMIT_STEP_BYTES

    def _show_proxy_refusal(self, text: str) -> None:
        """Say whether what is in the box could be used. **Writes nothing** (`T196-R1`).

        Live feedback and committing are two jobs, and joining them is what put a password on
        disk: every accepted intermediate prefix was written. This half runs on every keystroke
        and touches only the note beside the field.

        **The refusal is `core.models.proxy_refusal`**, which is the rule `DownloadRequest` is
        held to (`T-014`) rather than a second opinion about proxies living in a widget.
        """
        self._proxy_note.setText(proxy_refusal(text.strip() or None) or "")

    def _commit_proxy(self) -> None:
        """Hand over the finished proxy, or leave what is in force untouched (`T196-R1`).

        Called when the user leaves the field or presses Return, and once more from `done` — a
        dialog closed while the box still has focus would otherwise drop an edit the user made.
        Committing twice is harmless: the second call sees the value it already stored, and
        `_remember_network` hands composition the same object again.

        **A refused value stores nothing at all** — not a truncation, not a repaired version. The
        field keeps showing what was typed, with the reason under it, and the proxy in force stays
        the one that was there.
        """
        if self._on_network_chosen is None:
            return
        value = self._proxy_field.text().strip() or None
        if proxy_refusal(value) is not None:
            return
        if value != self._network.proxy:
            self._remember_network(replace(self._network, proxy=value))

    def _on_rate_limit_value(self, kib: int) -> None:
        """Zero is *no limit*, which is stored as no value at all — see `NO_RATE_LIMIT_LABEL`."""
        self._remember_network(
            replace(
                self._network,
                rate_limit_bytes=None if kib == 0 else kib * RATE_LIMIT_STEP_BYTES,
            )
        )

    def _on_retries_value(self, count: int) -> None:
        """`-1` is *nobody chose*; `0` is a real answer — see `DEFAULT_RETRIES_LABEL`."""
        self._remember_network(replace(self._network, retries=None if count < 0 else count))

    def _remember_network(self, options: NetworkOptions) -> None:
        """Hold what changed and hand it to composition, which owns the file (`ARC-007`).

        Held here as well as sent because the next control to change builds its value from this
        one: without it, setting a speed limit and then a retry count would write the retry count
        against the network options as they were when the screen opened, and silently drop the
        limit. That is `T195-R1`'s defect — a second edit built from the original state.
        """
        self._network = options
        if self._on_network_chosen is not None:
            self._on_network_chosen(options)

    def done(self, result: int) -> None:
        """Close the screen, committing a proxy edit that never lost focus (`T196-R1`).

        `editingFinished` fires on Return and on focus leaving the field — which covers clicking
        `Close`, because the button takes focus first. It does **not** fire for `Esc`, or for a
        window closed while the box still holds focus, and an edit silently discarded there would
        be the same class of surprise as one silently stored.

        **And the application-wide focus connection goes here** (`T-242`). It is the one thing on
        this screen that outlives the screen if nobody takes it down: `focusChanged` belongs to the
        `QApplication`, so a closed dialog left connected keeps being asked to scroll a viewport
        that is no longer on screen. `T-238` is this project's record of what deferred Qt teardown
        costs when nothing is explicit about it.
        """
        self._commit_proxy()
        application = QApplication.instance()
        if isinstance(application, QApplication):
            with suppress(RuntimeError):
                application.focusChanged.disconnect(self._follow_focus)
        super().done(result)

    def show_network_options(self, options: NetworkOptions) -> None:
        """Show the network options in force, without echoing them back through the writer.

        `show_concurrency`'s rule: composition may store something other than what this screen
        emitted — `with_network_options` bounds what it is given — and a screen showing a value
        that is not in force is a screen that will write it back.
        """
        self._network = options
        blocked = self._proxy_field.blockSignals(True)
        try:
            # Only when it differs, so a redisplay does not move the caret of somebody typing.
            if self._proxy_field.text().strip() != (options.proxy or ""):
                self._proxy_field.setText(options.proxy or "")
                self._proxy_note.setText("")
        finally:
            self._proxy_field.blockSignals(blocked)
        for control, value in (
            (self._rate_limit, self._rate_limit_shown()),
            (self._retries, options.retries if options.retries is not None else -1),
        ):
            blocked = control.blockSignals(True)
            try:
                control.setValue(value)
            finally:
                control.blockSignals(blocked)

    # --- ffmpeg -------------------------------------------------------------------------

    def _build_ffmpeg_section(self) -> QWidget:
        """Where ffmpeg is, and what this application can do as a result (`REQ-024`, `T-199`)."""
        box = QGroupBox("ffmpeg", self)
        box.setObjectName("ffmpegSection")
        layout = QVBoxLayout(box)

        #: **The summary, not just the path.** `REQ-024` asks the application to report *which
        #: features are unavailable*, and this is the screen a user reaches when they want to fix
        #: that — so it says what is lost here rather than only in the status bar.
        self._ffmpeg_state = QLabel(box)
        self._ffmpeg_state.setObjectName("ffmpegState")
        self._ffmpeg_state.setTextFormat(Qt.TextFormat.PlainText)
        self._ffmpeg_state.setWordWrap(True)
        self._ffmpeg_state.setAccessibleName("ffmpeg status")
        layout.addWidget(self._ffmpeg_state)

        self._ffmpeg_path = QLabel(box)
        self._ffmpeg_path.setObjectName("ffmpegLocationValue")
        # A path the user chose is their own text (`T016-R6`).
        self._ffmpeg_path.setTextFormat(Qt.TextFormat.PlainText)
        self._ffmpeg_path.setWordWrap(True)
        self._ffmpeg_path.setAccessibleName("ffmpeg location")
        layout.addWidget(self._ffmpeg_path)

        row = QHBoxLayout()
        choose = QPushButton("Choose ffmpeg...", box)
        choose.setObjectName("chooseFfmpegLocation")
        choose.setAccessibleName("Choose where ffmpeg is")
        choose.clicked.connect(self._pick_an_ffmpeg)
        row.addWidget(choose)

        self._clear_ffmpeg = QPushButton("Look on PATH", box)
        self._clear_ffmpeg.setObjectName("clearFfmpegLocation")
        self._clear_ffmpeg.setAccessibleName("Look for ffmpeg on PATH")
        self._clear_ffmpeg.clicked.connect(lambda: self._remember_ffmpeg(None))
        row.addWidget(self._clear_ffmpeg)
        row.addStretch(1)
        layout.addLayout(row)

        self._show_ffmpeg()
        return box

    def _show_ffmpeg(self) -> None:
        self._ffmpeg_state.setText(self._ffmpeg_summary)
        self._ffmpeg_path.setText(
            str(self._ffmpeg_location) if self._ffmpeg_location is not None else FFMPEG_ON_PATH_NOTE
        )
        self._clear_ffmpeg.setEnabled(self._ffmpeg_location is not None)

    def _ask_for_a_file(self, start: Path | None) -> Path | None:
        """The real picker. Replaced in tests, for the module docstring's reason."""
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Choose where ffmpeg is", str(start) if start is not None else ""
        )
        return Path(chosen) if chosen else None

    def _pick_an_ffmpeg(self) -> None:
        chosen = self._choose_file(self._ffmpeg_location)
        if chosen is None:
            # Cancelled — not the same as *look on PATH*, which is the other button.
            return
        self._remember_ffmpeg(chosen)

    def _remember_ffmpeg(self, location: Path | None) -> None:
        if self._on_ffmpeg_location_chosen is not None:
            self._on_ffmpeg_location_chosen(location)

    def show_ffmpeg_location(self, location: Path | None, summary: str) -> None:
        """Show what composition resolved: the location, and what it bought (`T-199`).

        Both come back rather than being assumed here, for `show_download_directory`'s reason —
        whether a chosen file is a usable ffmpeg is `find_ffmpeg`'s answer, and `ui/` may not ask
        `downloader/` directly.
        """
        self._ffmpeg_location = location
        self._ffmpeg_summary = summary
        self._show_ffmpeg()

    # --- appearance ---------------------------------------------------------------------

    def _build_appearance_section(self) -> QWidget:
        box = QGroupBox("Appearance", self)
        box.setObjectName("appearanceSection")
        layout = QVBoxLayout(box)

        #: Radio buttons rather than a combo, for two mutually exclusive values: both choices are
        #: visible without opening anything, and a screen reader announces "Light, 1 of 2" instead
        #: of a collapsed control's current value alone (`NFR-005`).
        self._themes: dict[str, QRadioButton] = {}
        for name in THEME_NAMES:
            button = QRadioButton(THEME_LABELS[name], box)
            button.setObjectName(f"theme{THEME_LABELS[name]}")
            button.setAccessibleName(f"{THEME_LABELS[name]} theme")
            button.setChecked(name == self._theme)
            # `partial` rather than a lambda with a default argument: the latter is the
            # late-binding workaround mypy cannot type, and this loop rebinds `name`.
            button.toggled.connect(partial(self._theme_picked, name))
            layout.addWidget(button)
            self._themes[name] = button
        return box

    def _theme_picked(self, name: str, checked: bool) -> None:
        # `toggled` fires for the button being cleared as well as the one being set; only the set
        # one is a choice.
        if not checked or name == self._theme:
            return
        self._theme = name
        self._on_theme_chosen(name)

    # --- queue --------------------------------------------------------------------------

    def _build_queue_section(self) -> QWidget:
        box = QGroupBox("Queue", self)
        box.setObjectName("queueSection")
        layout = QVBoxLayout(box)

        row = QHBoxLayout()
        label = QLabel("Downloads at once", box)
        label.setObjectName("settingsConcurrencyLabel")
        row.addWidget(label)

        self._concurrency = QSpinBox(box)
        self._concurrency.setObjectName("settingsConcurrencyChoice")
        self._concurrency.setAccessibleName("Downloads at once")
        # **The range is the settings layer's**, read from it rather than restated — the reason
        # `REQ-013`'s bounds live in `core/` rather than in a widget.
        #
        # **This is the only control for the limit since `UX-013`** (`T-234`), which retires the
        # sentence this explanation used to end with — *"This is the same setting as the
        # toolbar's."* There is no toolbar copy to be the same as.
        self._concurrency.setRange(CONCURRENCY_MINIMUM, CONCURRENCY_MAXIMUM)
        self._concurrency.setValue(self._initial_concurrency)
        # **The steps are labelled buttons, not native arrows** (`UX-005` row 11, `T-141`,
        # rebuilt here by `T-236`). The arrows were reported missing twice: first drawn as solid
        # blocks by the CSS border-triangle trick, then drawn correctly as ~10px native wedges in
        # a 23px control and **still unreadable** — measured on the maintainer's own session at
        # the real size, up `4,6,8,10` and down `8,6,4`. The two step labels are **text**, and no
        # style sheet can silently un-draw text, which is the shared cause of `T-129`, `T-133`
        # and `T-139`.
        #
        # **The ruling names the control, not the toolbar** (`T234-R2`). `UX-013` moved where the
        # control lives; it did not amend how it steps. `T-234` removed the buttons with the
        # toolbar and left this spinner at **57x22 with `UpDownArrows`** — materially the 58x23
        # control `T-141` measured — so the accepted design was unbuilt by a relocation that had
        # no authority to unbuild it.
        self._concurrency.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._concurrency.valueChanged.connect(self._on_concurrency_chosen)

        fewer = self._step_button(box, STEP_DOWN_LABEL, "Fewer concurrent downloads")
        more = self._step_button(box, STEP_UP_LABEL, "More concurrent downloads")
        fewer.clicked.connect(self._concurrency.stepDown)
        more.clicked.connect(self._concurrency.stepUp)
        row.addWidget(fewer)
        row.addWidget(self._concurrency)
        row.addWidget(more)
        row.addStretch(1)
        layout.addLayout(row)

        def _limit_the_steps(value: int) -> None:
            """Neither button offers a step the range will not take (`UX-005` §5)."""
            fewer.setEnabled(value > CONCURRENCY_MINIMUM)
            more.setEnabled(value < CONCURRENCY_MAXIMUM)

        self._concurrency.valueChanged.connect(_limit_the_steps)
        _limit_the_steps(self._concurrency.value())

        explanation = QLabel(
            "Each download is a separate process, so a higher number is not always faster.",
            box,
        )
        explanation.setObjectName("settingsConcurrencyNote")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        return box

    def _build_ytdlp_section(self) -> QWidget:
        """The version in use, and the two actions `REQ-025` asks for (`T-198`, `OPS-002`).

        **The version is displayed, never computed here.** It arrives through `show_ytdlp` from a
        child process that imported yt-dlp, because the promise is to report *what is running* —
        and a screen that derives a number from a pin or a folder name reports what ought to be
        running instead. Until that answer arrives the field says so rather than showing a
        plausible placeholder.

        **Both actions are offered together and disabled together.** Updating and reverting are
        the same operation in opposite directions, and while either is in flight neither may
        start: they write the same directory.
        """
        box = QGroupBox("yt-dlp", self)
        box.setObjectName("ytdlpSection")
        layout = QVBoxLayout(box)

        explanation = QLabel(
            "Sites change constantly, and yt-dlp is what keeps up with them. Updating affects "
            "downloads only — Tracks & Trails itself is not changed.",
            box,
        )
        explanation.setObjectName("ytdlpExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        row = QHBoxLayout()
        label = QLabel("Version in use", box)
        label.setObjectName("ytdlpVersionLabel")
        row.addWidget(label)

        self._ytdlp_version = QLabel(YTDLP_VERSION_UNKNOWN, box)
        self._ytdlp_version.setObjectName(YTDLP_VERSION_NAME)
        self._ytdlp_version.setTextFormat(Qt.TextFormat.PlainText)
        # Selectable because the first thing a bug report needs is this number, and retyping a
        # version from a screenshot is how a report ends up describing a different release.
        self._ytdlp_version.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self._ytdlp_version)
        row.addStretch(1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self._ytdlp_update = QPushButton("Update to the latest version", box)
        self._ytdlp_update.setObjectName(YTDLP_UPDATE_NAME)
        self._ytdlp_update.setAccessibleName("Update yt-dlp to the latest version")
        self._ytdlp_update.clicked.connect(self._start_ytdlp_update)
        buttons.addWidget(self._ytdlp_update)

        self._ytdlp_revert = QPushButton(YTDLP_REVERT_LABEL, box)
        self._ytdlp_revert.setObjectName(YTDLP_REVERT_NAME)
        self._ytdlp_revert.setAccessibleName("Go back to the bundled yt-dlp version")
        self._ytdlp_revert.clicked.connect(self._start_ytdlp_revert)
        buttons.addWidget(self._ytdlp_revert)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._ytdlp_note = QLabel("", box)
        self._ytdlp_note.setObjectName(YTDLP_NOTE_NAME)
        self._ytdlp_note.setTextFormat(Qt.TextFormat.PlainText)
        self._ytdlp_note.setWordWrap(True)
        layout.addWidget(self._ytdlp_note)

        # Nothing to revert *to* until a resolution says a user copy is in use, and nothing to
        # update until composition has supplied a route. Both are re-decided by `show_ytdlp`.
        self._ytdlp_update.setEnabled(self._on_ytdlp_update is not None)
        self._ytdlp_revert.setEnabled(False)
        return box

    def _start_ytdlp_update(self) -> None:
        if self._on_ytdlp_update is not None:
            self._on_ytdlp_update()

    def _start_ytdlp_revert(self) -> None:
        if self._on_ytdlp_revert is not None:
            self._on_ytdlp_revert()

    def show_ytdlp(
        self,
        version: str,
        source: str,
        *,
        is_user_managed: bool,
        rejected: Sequence[str] = (),
    ) -> None:
        """Report which yt-dlp a worker imported (`REQ-025`).

        **`is_user_managed` decides whether reverting is offered**, and it comes from the
        resolution rather than from whether the directory exists. A copy that is present but does
        not import is not in use, and offering *"use the bundled version"* as though it were would
        describe the wrong state — while a rejected copy still needs saying, which is what
        `rejected` is for (`ARCHITECTURE.md` §6: reported, never silently ignored).
        """
        self._ytdlp_version.setText(f"{version} — {source}" if source else version)
        # **Held rather than read back off the button.** `show_ytdlp_busy` disables both controls
        # while an operation runs, so asking the widget afterwards whether reverting is available
        # returns *"no"* because it was just switched off — and the button never comes back. The
        # resolution is the fact; the widget is a rendering of it.
        self._ytdlp_is_user_managed = is_user_managed
        self._ytdlp_revert.setEnabled(is_user_managed and self._on_ytdlp_revert is not None)
        self._ytdlp_note.setText(
            "An installed copy could not be used, so the bundled version is running: "
            + "; ".join(rejected)
            if rejected
            else ""
        )

    def show_ytdlp_problem(self, reason: str) -> None:
        """Say why the last update, revert or check did not happen.

        The reason is passed through as written: `ytdlp_update` composes these sentences for a
        user and they carry no path or URL (`NFR-007`), so rewording here would only risk
        replacing an accurate one with a generic one — the failure `NFR-006` names.
        """
        self._ytdlp_note.setText(reason)

    def show_ytdlp_busy(self, busy: bool) -> None:
        """Disable both actions while either is running, and say the screen is not stuck.

        A positional `bool` because this mirrors the service's `busy_changed(bool)` signal, which
        is what composition connects it to.
        """
        self._ytdlp_update.setEnabled(not busy and self._on_ytdlp_update is not None)
        self._ytdlp_revert.setEnabled(
            not busy and self._ytdlp_is_user_managed and self._on_ytdlp_revert is not None
        )
        self._ytdlp_update.setText(YTDLP_WORKING_LABEL if busy else "Update to the latest version")
        if busy:
            self._ytdlp_note.setText("")

    def _step_button(self, parent: QWidget, label: str, announced: str) -> QToolButton:
        """One of the concurrency control's step buttons (`UX-005` row 11, `T-141`, `T-236`).

        **Its accessible name says the direction *and* the setting** (`NFR-005`). "Plus" read on
        its own says nothing about what it increases, and the visible label is a single character
        that a screen reader may or may not pronounce usefully.
        """
        button = QToolButton(parent)
        button.setObjectName(f"settingsConcurrencyStep{'Up' if label == STEP_UP_LABEL else 'Down'}")
        button.setText(label)
        button.setAccessibleName(announced)
        button.setStatusTip(announced)
        button.setProperty(STEP_BUTTON_PROPERTY, True)
        button.setAutoRepeat(True)
        # **Focus stays on the value, not on the steppers.** A user tabbing to this control wants
        # the number, and `NFR-005` asks the keyboard to reach what the pointer reaches — `Up` and
        # `Down` already do, from the spin box itself, so three tab stops for one setting would be
        # the keyboard reaching it three times rather than once.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # **Declared, so a sweep can tell this from a control that lost its tab stop by accident**
        # (`T200-R2`, `ui/keyboard.py`). Setting *Choose folder…* to `NoFocus` left every
        # accessibility test green, because an unfocusable control simply drops out of the set they
        # inspect. The exemption now has to say where the route went.
        route_is_elsewhere(button, "the concurrency spin box's own Up and Down arrows")
        return button

    def show_concurrency(self, limit: int) -> None:
        """Show the limit **composition applied**, without echoing it back (`T-146`).

        A naive `setValue` here would emit `valueChanged`, call composition again, and make every
        change a round trip. Blocked for exactly the assignment.

        **What this follows changed with `UX-013`** (`T-234`). It existed because two controls
        edited one value (`REQ-013`) and each had to show what the other did; the toolbar's copy is
        gone, and what remains to follow is composition itself — the number it applies is not
        always the number this control emitted, because `settings.toml` clamps
        (`CONCURRENCY_MINIMUM`/`MAXIMUM`) and the applied value is the one in force. A screen
        showing a number the pool is not running is a screen that will write it back.
        """
        blocked = self._concurrency.blockSignals(True)
        try:
            self._concurrency.setValue(limit)
        finally:
            self._concurrency.blockSignals(blocked)
