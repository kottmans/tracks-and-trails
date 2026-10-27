"""`T-253`: where connections are made from, and the wait before each file, in Settings, Network.

Driven through the screen's own controls by object name, as every other settings test reaches one.
Ruled 2026-10-19 (`ARC-010` amended, second): one choice of four for the address, which absorbs
`--source-address`; the wait beside the speed limit, saying that downloads running together do not
take turns; and the longest wait refused without the shortest, at edit time.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
)

from tracks_and_trails.core.models import IPV4_ONLY, IPV6_ONLY, MOST_WAIT_SECONDS, NetworkOptions
from tracks_and_trails.ui.settings_dialog import (
    ADDRESS_CHOICE_NAMES,
    ADDRESS_FIELD_NAME,
    ADDRESS_HINT,
    ADDRESS_NOTE_NAME,
    ADDRESS_REFUSAL,
    LONGEST_WAIT_NAME,
    NO_WAIT_LABEL,
    RATE_LIMIT_EXACT_NAME,
    RATE_LIMIT_NAME,
    SAME_WAIT_LABEL,
    WAIT_NAME,
    WAIT_NOTE,
    SettingsDialog,
)


@pytest.fixture
def screens(
    qapp: QApplication, tmp_path: Path
) -> Iterator[Callable[..., tuple[SettingsDialog, list[NetworkOptions]]]]:
    """Build settings screens, and hand back every network value each one asked to store."""
    built: list[SettingsDialog] = []

    def build(**overrides: Any) -> tuple[SettingsDialog, list[NetworkOptions]]:
        chosen: list[NetworkOptions] = []
        overrides.setdefault("download_directory", tmp_path / "downloads")
        overrides.setdefault("directory_is_default", True)
        overrides.setdefault("theme", "light")
        overrides.setdefault("concurrency", 3)
        overrides.setdefault("on_directory_chosen", lambda value: None)
        overrides.setdefault("on_theme_chosen", lambda value: None)
        overrides.setdefault("on_concurrency_chosen", lambda value: None)
        overrides.setdefault("on_network_chosen", chosen.append)
        screen = SettingsDialog(**overrides)
        built.append(screen)
        return screen, chosen

    yield build

    for screen in built:
        screen.close()
    QApplication.processEvents()


def control(screen: SettingsDialog, kind: type, name: str) -> Any:
    found: Any = screen.findChild(kind, name)
    assert found is not None, f"the settings screen has no {kind.__name__} named {name!r}"
    return found


def choice(screen: SettingsDialog, key: str) -> QRadioButton:
    button: QRadioButton = control(screen, QRadioButton, ADDRESS_CHOICE_NAMES[key])
    return button


def checked(screen: SettingsDialog) -> list[str]:
    return [key for key in ADDRESS_CHOICE_NAMES if choice(screen, key).isChecked()]


def type_an_address(screen: SettingsDialog, text: str) -> QLineEdit:
    """Keystroke by keystroke, as a user does, for the proxy field's reason (`T196-R1`)."""
    field: QLineEdit = control(screen, QLineEdit, ADDRESS_FIELD_NAME)
    field.clear()
    QTest.keyClicks(field, text)
    return field


# --- the address ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "key"),
    [(None, "automatic"), (IPV4_ONLY, "ipv4"), (IPV6_ONLY, "ipv6"), ("192.0.2.7", "own")],
)
def test_the_screen_opens_on_the_choice_in_force(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
    address: str | None,
    key: str,
) -> None:
    screen, _ = screens(network=NetworkOptions(source_address=address))

    assert checked(screen) == [key]
    field = control(screen, QLineEdit, ADDRESS_FIELD_NAME)
    assert field.isEnabled() is (key == "own")
    assert field.text() == ("192.0.2.7" if key == "own" else "")


@pytest.mark.parametrize(("key", "address"), [("ipv4", IPV4_ONLY), ("ipv6", IPV6_ONLY)])
def test_a_family_is_stored_as_it_is_picked_and_automatic_takes_it_back(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]], key: str, address: str
) -> None:
    screen, chosen = screens(network=NetworkOptions(retries=2))

    choice(screen, key).click()
    assert chosen[-1] == NetworkOptions(retries=2, source_address=address)

    choice(screen, "automatic").click()
    assert chosen[-1] == NetworkOptions(retries=2)


def test_no_keystroke_of_an_address_is_stored_and_the_finished_one_is(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    """**A prefix of an address is an address**: `192.0.2.1` on the way to `192.0.2.17` would have
    bound connections to the wrong one, so the box stores only when the edit is finished."""
    screen, chosen = screens()
    choice(screen, "own").click()

    field = type_an_address(screen, "192.0.2.17")

    assert chosen == [], "a keystroke reached the writer"
    QTest.keyClick(field, Qt.Key.Key_Return)
    assert chosen[-1].source_address == "192.0.2.17"
    assert control(screen, QLabel, ADDRESS_NOTE_NAME).text() == ""


def test_an_address_is_stored_the_shortest_way(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, chosen = screens()
    choice(screen, "own").click()

    QTest.keyClick(type_an_address(screen, "2001:DB8:0:0::20"), Qt.Key.Key_Return)

    assert chosen[-1].source_address == "2001:db8::20"


@pytest.mark.parametrize("typed", ["example.com", "192.0.2.300", "nowhere"])
def test_what_is_not_an_address_is_refused_with_the_reason_and_not_stored(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]], typed: str
) -> None:
    screen, chosen = screens(network=NetworkOptions(source_address=IPV4_ONLY))
    choice(screen, "own").click()

    QTest.keyClick(type_an_address(screen, typed), Qt.Key.Key_Return)

    assert chosen == []
    assert control(screen, QLabel, ADDRESS_NOTE_NAME).text() == ADDRESS_REFUSAL
    assert "\u2014" not in ADDRESS_REFUSAL and "\u2013" not in ADDRESS_REFUSAL


def test_picking_this_address_with_an_empty_box_says_nothing_changes_yet(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    """**The earlier choice stays in force until there is an address**, and the screen says so,
    rather than showing a choice that is not the one connections use. Another edit meanwhile does
    not move the pick back under the user's hands."""
    screen, chosen = screens(network=NetworkOptions(source_address=IPV6_ONLY))

    choice(screen, "own").click()

    assert chosen == []
    assert control(screen, QLabel, ADDRESS_NOTE_NAME).text() == ADDRESS_HINT
    assert control(screen, QLineEdit, ADDRESS_FIELD_NAME).isEnabled()

    control(screen, QDoubleSpinBox, WAIT_NAME).setValue(2.0)
    screen.show_network_options(chosen[-1])

    assert chosen[-1] == NetworkOptions(source_address=IPV6_ONLY, sleep_interval=2.0)
    assert checked(screen) == ["own"]


def test_an_address_typed_but_not_finished_is_stored_when_the_screen_closes(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, chosen = screens()
    choice(screen, "own").click()
    type_an_address(screen, "192.0.2.7")

    screen.reject()

    assert chosen[-1].source_address == "192.0.2.7"


def test_show_network_options_moves_the_choice_without_writing_it_back(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, chosen = screens()

    screen.show_network_options(NetworkOptions(source_address="2001:db8::20"))

    assert chosen == []
    assert checked(screen) == ["own"]
    assert control(screen, QLineEdit, ADDRESS_FIELD_NAME).text() == "2001:db8::20"

    screen.show_network_options(NetworkOptions(source_address=IPV4_ONLY))

    assert chosen == []
    assert checked(screen) == ["ipv4"]


def test_each_choice_is_named_for_a_screen_reader(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, _ = screens()

    names = [choice(screen, key).accessibleName() for key in ADDRESS_CHOICE_NAMES]

    assert names == ["Automatic", "IPv4 only", "IPv6 only", "From this address"]
    assert control(screen, QLineEdit, ADDRESS_FIELD_NAME).accessibleName()


# --- the wait --------------------------------------------------------------------------------


def test_a_longest_beside_no_wait_is_a_random_wait_from_nothing(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    """**`T253-R1`**: yt-dlp's wait from zero up to a longest is its own setting, not a wait from a
    tenth, and not no wait. A longest is never stored without a shortest (`T-253`'s criterion):
    beside no wait, the shortest stored is zero, and the wait box stops saying *No wait*."""
    screen, chosen = screens()
    wait = control(screen, QDoubleSpinBox, WAIT_NAME)
    longest = control(screen, QDoubleSpinBox, LONGEST_WAIT_NAME)
    assert wait.text() == NO_WAIT_LABEL
    assert longest.isEnabled() and longest.text() == SAME_WAIT_LABEL

    longest.setValue(5.0)

    assert chosen[-1] == NetworkOptions(sleep_interval=0.0, max_sleep_interval=5.0)
    assert wait.text() == "0.0 s"

    longest.setValue(0.0)

    assert chosen[-1] == NetworkOptions()
    assert wait.text() == NO_WAIT_LABEL


def test_a_stored_wait_from_nothing_opens_as_it_is(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, chosen = screens(network=NetworkOptions(sleep_interval=0.0, max_sleep_interval=5.0))
    wait = control(screen, QDoubleSpinBox, WAIT_NAME)
    longest = control(screen, QDoubleSpinBox, LONGEST_WAIT_NAME)

    assert (wait.text(), longest.text()) == ("0.0 s", "5.0 s")

    control(screen, QSpinBox, RATE_LIMIT_NAME).setValue(64)

    assert chosen[-1].sleep_interval == 0.0 and chosen[-1].max_sleep_interval == 5.0


def test_a_wait_is_stored_and_its_longest_cannot_go_below_it(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, chosen = screens()
    wait = control(screen, QDoubleSpinBox, WAIT_NAME)
    longest = control(screen, QDoubleSpinBox, LONGEST_WAIT_NAME)

    wait.setValue(3.0)

    assert chosen[-1] == NetworkOptions(sleep_interval=3.0)
    assert longest.isEnabled() and longest.minimum() == 3.0
    assert longest.text() == SAME_WAIT_LABEL

    longest.setValue(1.0)
    assert longest.value() == 3.0
    longest.setValue(9.5)
    assert chosen[-1] == NetworkOptions(sleep_interval=3.0, max_sleep_interval=9.5)


def test_the_longest_back_at_the_wait_is_the_same_every_time_stored_as_none(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    screen, chosen = screens(network=NetworkOptions(sleep_interval=3.0, max_sleep_interval=9.5))

    control(screen, QDoubleSpinBox, LONGEST_WAIT_NAME).setValue(3.0)

    assert chosen[-1] == NetworkOptions(sleep_interval=3.0)


@pytest.mark.parametrize(
    ("wait", "expected"),
    [
        (0.0, NetworkOptions(sleep_interval=0.0, max_sleep_interval=9.5)),
        (12.0, NetworkOptions(sleep_interval=12.0)),
        (5.0, NetworkOptions(sleep_interval=5.0, max_sleep_interval=9.5)),
    ],
)
def test_moving_the_wait_takes_the_longest_with_it_where_it_no_longer_holds(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
    wait: float,
    expected: NetworkOptions,
) -> None:
    """A wait past the longest makes the longest the same as it; a wait below it keeps it, zero
    included (`T253-R1`). Every value stored is one the model holds."""
    screen, chosen = screens(network=NetworkOptions(sleep_interval=3.0, max_sleep_interval=9.5))

    control(screen, QDoubleSpinBox, WAIT_NAME).setValue(wait)

    assert chosen[-1] == expected
    assert control(screen, QDoubleSpinBox, LONGEST_WAIT_NAME).isEnabled()


def test_the_wait_keeps_what_the_other_controls_hold(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    """`T195-R1`'s rule: each edit is built from the value in force."""
    screen, chosen = screens(network=NetworkOptions(retries=2, source_address=IPV6_ONLY))

    control(screen, QDoubleSpinBox, WAIT_NAME).setValue(2.5)

    assert chosen[-1] == NetworkOptions(retries=2, source_address=IPV6_ONLY, sleep_interval=2.5)


def test_the_wait_sits_beside_the_speed_limit_and_says_downloads_do_not_take_turns(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    """**The ruling's question 2**: yt-dlp's meaning, per file, and the control says that downloads
    running together do not take turns."""
    screen, _ = screens()
    wait = control(screen, QDoubleSpinBox, WAIT_NAME)

    assert wait.accessibleDescription() == WAIT_NOTE
    assert "do not take turns" in WAIT_NOTE and "waits twice" in WAIT_NOTE
    assert "\u2014" not in WAIT_NOTE and "\u2013" not in WAIT_NOTE
    assert WAIT_NOTE in [label.text() for label in screen.findChildren(QLabel)]
    assert wait.maximum() == MOST_WAIT_SECONDS
    # Beside it: the two waits are laid out straight after the speed limit, in the order built.
    order = [spin.objectName() for spin in screen.findChildren(QAbstractSpinBox)]
    at = order.index(RATE_LIMIT_NAME)
    assert order[at + 1 : at + 3] == [WAIT_NAME, LONGEST_WAIT_NAME], order


# --- the speed limit's exact value (`T253-R5`, `T252-R6`) ------------------------------------


def _exact(screen: SettingsDialog) -> QLabel:
    found = screen.findChild(QLabel, RATE_LIMIT_EXACT_NAME)
    assert found is not None
    return found


def test_a_limit_the_box_rounds_down_is_said_exactly(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]],
) -> None:
    """**The review's case**: 1,500 bytes per second opened as *1 KiB/s* and was sent as 1,500, with
    nothing on screen saying so. Said under the box and to a screen reader, until it is moved."""
    screen, chosen = screens(network=NetworkOptions(rate_limit_bytes=1500))
    rate = control(screen, QSpinBox, RATE_LIMIT_NAME)
    expected = (
        "This limit is 1,500 bytes per second, which the box shows rounded down to 1 KiB/s. "
        "Changing the box sets a whole number of KiB/s."
    )

    assert rate.text() == "1 KiB/s"
    assert not _exact(screen).isHidden() and _exact(screen).text() == expected
    assert rate.accessibleDescription() == expected
    assert "\u2014" not in expected and "\u2013" not in expected

    rate.setValue(2)

    assert chosen[-1].rate_limit_bytes == 2048
    assert _exact(screen).isHidden() and rate.accessibleDescription() == ""


@pytest.mark.parametrize("stored", [None, 1024, 2048])
def test_a_whole_limit_says_nothing_more(
    screens: Callable[..., tuple[SettingsDialog, list[NetworkOptions]]], stored: int | None
) -> None:
    screen, _ = screens(network=NetworkOptions(rate_limit_bytes=stored))

    assert _exact(screen).isHidden()
    assert control(screen, QSpinBox, RATE_LIMIT_NAME).accessibleDescription() == ""
