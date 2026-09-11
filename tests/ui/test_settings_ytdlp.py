"""`T-198`: the yt-dlp section of the Settings screen — what it reports and what it offers.

Driven through the screen's own controls by object name, the way every other settings test
reaches one: what `REQ-025` promises is that a *user* can see which yt-dlp is running and change
it, and a test calling `_start_ytdlp_update` would prove a method exists.

**This screen computes no version.** Everything it shows arrives through `show_ytdlp`, from a
child that imported yt-dlp — so these tests supply that answer directly and assert the rendering.
The proof that the number is real lives in `tests/integration/test_ytdlp_service.py`, which
spawns the child.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from tracks_and_trails.ui.settings_dialog import (
    YTDLP_NOTE_NAME,
    YTDLP_REVERT_NAME,
    YTDLP_UPDATE_LABEL,
    YTDLP_UPDATE_NAME,
    YTDLP_VERSION_NAME,
    YTDLP_VERSION_UNKNOWN,
    YTDLP_WORKING_LABEL,
    SettingsDialog,
)


@pytest.fixture
def screens(
    qapp: QApplication, tmp_path: Path
) -> Iterator[Callable[..., tuple[SettingsDialog, dict[str, Any]]]]:
    """Build settings screens, and hand back what each one asked composition to do."""
    built: list[SettingsDialog] = []

    def build(**overrides: Any) -> tuple[SettingsDialog, dict[str, Any]]:
        asked: dict[str, Any] = {"calls": []}
        overrides.setdefault("download_directory", tmp_path / "downloads")
        overrides.setdefault("directory_is_default", True)
        overrides.setdefault("theme", "light")
        overrides.setdefault("concurrency", 3)
        overrides.setdefault("on_directory_chosen", lambda value: None)
        overrides.setdefault("on_theme_chosen", lambda value: None)
        overrides.setdefault("on_concurrency_chosen", lambda value: None)
        overrides.setdefault("on_ytdlp_update", lambda: asked["calls"].append("update"))
        overrides.setdefault("on_ytdlp_revert", lambda: asked["calls"].append("revert"))
        screen = SettingsDialog(**overrides)
        built.append(screen)
        return screen, asked

    yield build

    for screen in built:
        screen.close()
    QApplication.processEvents()


def control(screen: SettingsDialog, kind: type, name: str) -> Any:
    found: Any = screen.findChild(kind, name)
    assert found is not None, f"the settings screen has no {kind.__name__} named {name!r}"
    return found


def test_the_version_is_unknown_until_a_worker_has_answered(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**A screen that has not been told must not invent a number.**

    The resolution takes a spawned child and an import, so there is a real window before the
    answer arrives. Showing the pinned baseline in the meantime would be showing the one thing
    `REQ-025` says not to report — what *should* be running rather than what is.
    """
    screen, _ = screens()

    assert control(screen, QLabel, YTDLP_VERSION_NAME).text() == YTDLP_VERSION_UNKNOWN


def test_the_reported_version_and_its_source_are_both_shown(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The source is half the answer: the same version means different things from each place."""
    screen, _ = screens()

    screen.show_ytdlp("2026.7.4", "bundled baseline", is_user_managed=False)

    shown = control(screen, QLabel, YTDLP_VERSION_NAME).text()
    assert "2026.7.4" in shown
    assert "bundled baseline" in shown


def test_reverting_is_offered_only_when_a_user_copy_is_in_use(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`UX-005` §5: nothing is drawn that would be refused.

    On the baseline there is nothing to revert *to*, and a button that would do nothing is a
    button that has to be explained.
    """
    screen, _ = screens()
    revert = control(screen, QPushButton, YTDLP_REVERT_NAME)

    screen.show_ytdlp("2026.7.4", "bundled baseline", is_user_managed=False)
    assert revert.isEnabled() is False

    screen.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)
    assert revert.isEnabled() is True


def test_a_rejected_copy_is_reported_rather_than_silently_skipped(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`ARCHITECTURE.md` §6, on the one screen where a user could act on it.

    Without this the user installs a copy, sees the baseline's version, and has nothing telling
    them the copy they installed was refused.
    """
    screen, _ = screens()

    screen.show_ytdlp(
        "2026.7.4",
        "bundled baseline",
        is_user_managed=False,
        rejected=("user-managed copy (OPS-002): ImportError: no module named 'yt_dlp'",),
    )

    note = control(screen, QLabel, YTDLP_NOTE_NAME).text()
    assert "could not be used" in note
    assert "ImportError" in note


def test_a_clean_resolution_clears_a_previous_rejection(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """A note about a copy that is no longer installed is a false statement about now."""
    screen, _ = screens()
    screen.show_ytdlp("2026.7.4", "bundled baseline", is_user_managed=False, rejected=("broken",))

    screen.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)

    assert control(screen, QLabel, YTDLP_NOTE_NAME).text() == ""


def test_both_actions_are_withdrawn_while_one_is_running(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """They write the same directory, so neither may start while the other is in flight."""
    screen, _ = screens()
    screen.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)
    update = control(screen, QPushButton, YTDLP_UPDATE_NAME)
    revert = control(screen, QPushButton, YTDLP_REVERT_NAME)

    screen.show_ytdlp_busy(True)

    assert update.isEnabled() is False
    assert revert.isEnabled() is False
    assert update.text() == YTDLP_WORKING_LABEL


def test_the_revert_button_comes_back_after_an_operation_finishes(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**Written for a defect this screen had.**

    `show_ytdlp_busy` restored the revert button from `isEnabled()` — which it had just switched
    off — so once anything ran, reverting was unavailable until the screen was reopened. The
    resolution is the fact and the widget is a rendering of it, so the state is held rather than
    read back.
    """
    screen, _ = screens()
    screen.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)
    revert = control(screen, QPushButton, YTDLP_REVERT_NAME)

    screen.show_ytdlp_busy(True)
    screen.show_ytdlp_busy(False)

    assert revert.isEnabled() is True, "reverting was lost by an operation that has finished"


def test_a_finished_operation_on_the_baseline_still_offers_no_revert(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The other direction of the same fix: restoring must not enable what was never available."""
    screen, _ = screens()
    screen.show_ytdlp("2026.7.4", "bundled baseline", is_user_managed=False)
    revert = control(screen, QPushButton, YTDLP_REVERT_NAME)

    screen.show_ytdlp_busy(True)
    screen.show_ytdlp_busy(False)

    assert revert.isEnabled() is False


def test_pressing_update_asks_composition_to_do_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """The screen owns no network and no filesystem; it asks."""
    screen, asked = screens()

    control(screen, QPushButton, YTDLP_UPDATE_NAME).click()

    assert asked["calls"] == ["update"]


def test_pressing_revert_asks_composition_to_do_it(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    screen, asked = screens()
    screen.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)

    control(screen, QPushButton, YTDLP_REVERT_NAME).click()

    assert asked["calls"] == ["revert"]


def test_a_screen_with_no_route_behind_it_offers_neither_action(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """A screen built without composition — as several tests build one — must not look usable."""
    screen, _ = screens(on_ytdlp_update=None, on_ytdlp_revert=None)
    screen.show_ytdlp("2026.9.1", "user-managed copy (OPS-002)", is_user_managed=True)

    assert control(screen, QPushButton, YTDLP_UPDATE_NAME).isEnabled() is False
    assert control(screen, QPushButton, YTDLP_REVERT_NAME).isEnabled() is False


def test_a_failure_is_shown_in_the_words_it_was_given(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`NFR-006`: the reason is not replaced by a generic message.

    `ytdlp_update` writes these sentences for a user and they carry no path or URL (`NFR-007`);
    rewording here could only make an accurate one vaguer.
    """
    screen, _ = screens()
    reason = "The package index could not be reached. Check your connection and try again."

    screen.show_ytdlp_problem(reason)

    assert control(screen, QLabel, YTDLP_NOTE_NAME).text() == reason


def test_both_buttons_announce_what_they_change(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`NFR-005`: *Update* alone does not say what is updated, on a screen full of settings."""
    screen, _ = screens()

    update = control(screen, QPushButton, YTDLP_UPDATE_NAME).accessibleName()
    revert = control(screen, QPushButton, YTDLP_REVERT_NAME).accessibleName()

    assert "yt-dlp" in update
    assert "yt-dlp" in revert


def test_the_section_says_updating_does_not_change_the_application(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """`REQ-025` is explicit — *"without reinstalling Tracks & Trails"* — and the screen is where
    a user decides whether pressing the button is safe."""
    screen, _ = screens()

    explanation = control(screen, QLabel, "ytdlpExplanation").text()

    assert "Tracks & Trails itself is not changed" in explanation


def test_the_recovery_label_survives_every_settled_screen(
    screens: Callable[..., tuple[SettingsDialog, dict[str, Any]]],
) -> None:
    """**`T290-R1`.** `T-290` changed the resting label at construction and left `show_ytdlp_busy`
    restoring the words it replaced.

    **Every settled screen comes through that restore.** `MainWindow.open_settings` asks the
    service to resolve, and a resolution *and* a failure both end the busy state — so the screen a
    user actually looks at reverted to *"Update to the latest version"* before they had done
    anything at all. `T-290`'s own regression checked a **freshly constructed** dialog, which is
    the one state that never passes through it.

    **Driven through the busy transition rather than around it**, in all three lifecycles the
    finding names: opening resolution, opening failure, and an operation completing. Asserting the
    text after `show_ytdlp` alone would bypass the exact call that was wrong.
    """
    screen, _ = screens()
    update = control(screen, QPushButton, YTDLP_UPDATE_NAME)
    assert update.text() == YTDLP_UPDATE_LABEL, "construction alone is already wrong"

    # 1 · Opening resolution: busy while the service looks, then the answer.
    screen.show_ytdlp_busy(True)
    assert update.text() == YTDLP_WORKING_LABEL, "the screen does not say it is working"
    screen.show_ytdlp("2026.9.1", "bundled baseline", is_user_managed=False)
    screen.show_ytdlp_busy(False)
    assert update.text() == YTDLP_UPDATE_LABEL, (
        "opening the screen restored the old label, so the settled screen a user reads is the one "
        "T-290 replaced"
    )

    # 2 · Opening failure: the same transition, the other outcome.
    screen.show_ytdlp_busy(True)
    screen.show_ytdlp_problem("could not resolve yt-dlp")
    screen.show_ytdlp_busy(False)
    assert update.text() == YTDLP_UPDATE_LABEL, "a failed resolution restored the old label"

    # 3 · An operation finishing, which is the route the label was written for in the first place.
    screen.show_ytdlp_busy(True)
    screen.show_ytdlp("2026.9.2", "user-managed copy (OPS-002)", is_user_managed=True)
    screen.show_ytdlp_busy(False)
    assert update.text() == YTDLP_UPDATE_LABEL, "completing an update restored the old label"
    assert control(screen, QPushButton, YTDLP_REVERT_NAME).isEnabled(), (
        "reverting was lost, so this asserts the label on a screen that is broken another way"
    )
