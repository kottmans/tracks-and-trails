"""Where a control's keyboard route is, when it is not the control itself (`NFR-005`, `T-200`).

**`NFR-005` asks that every *function* be reachable, not that every *widget* be a tab stop**, and
those differ in exactly one situation: a control that duplicates something the keyboard already
reaches. The concurrency steppers are the case — a spin box's own `Up` and `Down` arrows do what
they do, so giving each stepper a tab stop would be the keyboard reaching one setting three times.

**The problem is that "deliberately unfocusable" and "forgotten" look identical to a sweep.**
`T200-R2` is the record: setting the Settings screen's *Choose folder…* button to `NoFocus` left
every accessibility test green, because a control that stops being focusable simply drops out of
the set the sweep inspects. A rule that only checks the controls it can still see cannot notice one
being removed from view.

So the exemption is **declared on the widget, with its reason**, rather than kept as a list of
object names in a test — which is the list that drifts, and which `T-200`'s own criterion refuses
when it asks for the whole tree *"rather than per widget"*. A sweep can then require that every
operable control is either focusable or says where its route is, and a control that quietly loses
its tab stop fails because it declares nothing.
"""

from typing import Final

from PySide6.QtWidgets import QWidget

__all__ = ["ROUTE_ELSEWHERE_PROPERTY", "route_is_elsewhere"]

#: The dynamic property naming where an unfocusable control's keyboard route actually is.
#:
#: A **sentence**, not a flag. `True` would say only that somebody thought about it; the value has
#: to survive being read by whoever is deciding whether the exemption is still true, and *"the spin
#: box's own Up and Down arrows do this"* is checkable in a way that `True` is not.
ROUTE_ELSEWHERE_PROPERTY: Final = "keyboardRouteElsewhere"


def route_is_elsewhere(widget: QWidget, route: str) -> None:
    """Declare that `widget` is deliberately unfocusable because `route` already reaches it.

    Call this beside the `setFocusPolicy(NoFocus)` it explains, never apart from it: the two are
    one decision, and the accessibility sweep reads this to tell that decision from an oversight.
    """
    widget.setProperty(ROUTE_ELSEWHERE_PROPERTY, route)
