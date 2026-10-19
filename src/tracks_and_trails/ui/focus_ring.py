"""The focus ring is drawn for the keyboard, and not for a click (`T-304`, `UX-016`).

**The maintainer's ruling of 2026-09-09, option (2)**: *"if you are clicking around with a mouse all
of the highlighted boxes are distracting."* The web's answer is `:focus-visible`, a ring for the
keyboard and none for a pointer, and Qt has no equivalent, so it is built: this tracks which kind of
input came last and sets `focusRing` on the widget holding focus, and every `:focus` rule in
`theme.stylesheet` asks for `[focusRing="true"]` (`theme.focused`).

**It does not weaken the keyboard case**, which is what `NFR-005` protects. The ring is on until a
pointer is pressed, so a window opened from the keyboard shows it, and a key pressed after a click
shows it at once on the control the click focused: the handover the ruling named as the case to
check. A style sheet does not look at a property again by itself, so the widget is re-polished
whenever its answer changes.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget

from tracks_and_trails.ui.theme import FOCUS_RING_PROPERTY

#: What a pointer does, as Qt reports it: any of these ends the keyboard's turn.
_POINTER_EVENTS: Final = frozenset(
    {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.TouchBegin,
        QEvent.Type.TabletPress,
    }
)


class FocusRing(QObject):
    """Watches the application's input, and says on the focused widget whether to draw the ring.

    **One per application**, parented to it, and installed by `theme.apply`, the one call that
    themes anything, so a dressed application cannot have the rules without the property.
    """

    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self.setObjectName("focusRing")
        self._keyboard = True
        application.installEventFilter(self)
        application.focusChanged.connect(self._focus_moved)

    @property
    def keyboard(self) -> bool:
        """Whether the last input was the keyboard, which is also how it starts."""
        return self._keyboard

    def reset(self) -> None:
        """Back to the keyboard's turn, as a newly dressed application starts."""
        self._use(keyboard=True)

    # Qt's override name, hence the camelCase.
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.KeyPress:
            self._use(keyboard=True)
        elif kind in _POINTER_EVENTS:
            self._use(keyboard=False)
        return False

    def _use(self, *, keyboard: bool) -> None:
        if keyboard == self._keyboard:
            return
        self._keyboard = keyboard
        focused = QApplication.focusWidget()
        if focused is not None:
            self._mark(focused)

    def _focus_moved(self, _old: QWidget | None, new: QWidget | None) -> None:
        if new is not None:
            self._mark(new)

    def _mark(self, widget: QWidget) -> None:
        """Say the answer on `widget`, re-polished only when it changes.

        **The widget Qt reports as focused is the control that draws the ring**: a spin box and an
        editable combo box report themselves, not the line edit inside them (measured with
        PySide6 6.11).
        """
        if widget.property(FOCUS_RING_PROPERTY) == self._keyboard:
            return
        widget.setProperty(FOCUS_RING_PROPERTY, self._keyboard)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


def install(application: QApplication) -> FocusRing:
    """The application's `FocusRing`, made on first asking and set back to the keyboard's turn."""
    existing = application.findChild(FocusRing, "focusRing")
    if existing is not None:
        existing.reset()
        return existing
    return FocusRing(application)
