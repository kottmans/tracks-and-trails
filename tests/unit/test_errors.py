"""The error taxonomy (`T-010`, `ARCHITECTURE.md` §7).

The taxonomy is asserted against §7's own table rather than restated here. Restating it would
let the table and the code drift apart silently, which is the failure this file exists to stop
— the retry policy hangs off these names.
"""

import pickle

import pytest

from tracks_and_trails.core.errors import (
    ErrorKind,
    FailureDetail,
    classify,
    is_auto_retryable,
    is_retryable,
)

#: Transcribed from `ARCHITECTURE.md` §7's table. Note it lists ten *rows*, one of which
#: declares two kinds (`FFMPEG_MISSING` / `FFMPEG_ERROR`), so there are eleven kinds. `T-010`'s
#: acceptance criterion says "the ten kinds"; that wording counts rows, and is reported in the
#: task record rather than resolved by quietly dropping one.
ARCHITECTURE_SECTION_7_KINDS = {
    "UNSUPPORTED_URL",
    "EXTRACTOR_ERROR",
    "AUTH_REQUIRED",
    "GEO_RESTRICTED",
    "DRM_PROTECTED",
    "NETWORK",
    "FFMPEG_MISSING",
    "FFMPEG_ERROR",
    "DISK",
    "WORKER_CRASH",
    "CANCELLED",
}


def test_the_taxonomy_matches_the_architecture_table_exactly() -> None:
    """Both directions: no kind missing, and none invented that §7 does not name."""
    assert {kind.name for kind in ErrorKind} == ARCHITECTURE_SECTION_7_KINDS


def test_network_is_the_only_auto_retryable_kind() -> None:
    """`REQ-018`: everything else waits for the user rather than hammering the site."""
    auto = {kind for kind in ErrorKind if is_auto_retryable(kind)}
    assert auto == {ErrorKind.NETWORK}


def test_drm_and_cancelled_are_never_retryable() -> None:
    """`REQ-EXCL-001` and `SEC-001`: no DRM workaround, not even an implied one.

    Offering retry on a DRM failure suggests a bypass exists. It does not, and this project
    will not add one.
    """
    assert not is_retryable(ErrorKind.DRM_PROTECTED)
    assert not is_retryable(ErrorKind.CANCELLED)


def test_every_other_kind_is_retryable_by_the_user() -> None:
    """Retryable-at-all is broader than auto-retryable, and the two must not be conflated."""
    for kind in ErrorKind:
        if kind in (ErrorKind.DRM_PROTECTED, ErrorKind.CANCELLED):
            continue
        assert is_retryable(kind), f"{kind} should be retryable on request"


def test_auto_retryable_implies_retryable() -> None:
    """A kind retried automatically but not retryable at all would be incoherent."""
    for kind in ErrorKind:
        if is_auto_retryable(kind):
            assert is_retryable(kind)


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable",
        "Sign in to confirm your age",
        "  leading and trailing whitespace  ",
        "unicode: café — naïve 日本語",
        "multi\nline\nmessage",
    ],
)
def test_the_original_message_is_preserved_verbatim(message: str) -> None:
    """`NFR-006` and `REQ-005`: surfaced, never swallowed, never paraphrased.

    Whitespace and newlines included — "tidying" an extractor message is still altering it.
    """
    detail = classify(message)
    assert detail.message == message


def test_classification_is_additive_and_does_not_replace_the_text() -> None:
    """The kind is a hint carried *alongside* the message, never instead of it."""
    detail = classify("Video unavailable", ErrorKind.EXTRACTOR_ERROR)
    assert detail.kind is ErrorKind.EXTRACTOR_ERROR
    assert detail.message == "Video unavailable"


def test_an_unclassified_failure_defaults_to_extractor_error() -> None:
    """§7 pairs `EXTRACTOR_ERROR` with showing the message verbatim.

    That is the honest default when the only trustworthy information is the message itself.
    """
    assert classify("something went wrong").kind is ErrorKind.EXTRACTOR_ERROR


def test_a_failure_without_a_message_is_rejected() -> None:
    """An empty message discards the only actionable information the user had."""
    with pytest.raises(ValueError, match="NFR-006"):
        FailureDetail(kind=ErrorKind.NETWORK, message="")


def test_context_is_carried_separately_from_the_message() -> None:
    """So presentation can use structured detail without parsing prose."""
    detail = classify("ffmpeg exited non-zero", ErrorKind.FFMPEG_ERROR, exit_code="1")
    assert detail.context == {"exit_code": "1"}
    assert "exit_code" not in detail.message


def test_failure_detail_is_immutable() -> None:
    """It is persisted and crosses a process boundary; editing one in flight is corruption."""
    detail = classify("nope", ErrorKind.DISK)
    with pytest.raises(AttributeError):
        detail.kind = ErrorKind.NETWORK  # type: ignore[misc]


def test_failure_detail_round_trips_through_pickle() -> None:
    """`ARC-002`: this travels from the worker process back to the GUI."""
    detail = classify("disk full", ErrorKind.DISK, path="/output/clip.mp4")
    restored = pickle.loads(pickle.dumps(detail))
    assert restored == detail
    assert restored.retryable == detail.retryable


def test_error_kind_values_are_stable_strings() -> None:
    """They are persisted (`T-014`); an ordinal would shift when a member is inserted."""
    assert ErrorKind.DRM_PROTECTED.value == "drm_protected"
    assert ErrorKind("drm_protected") is ErrorKind.DRM_PROTECTED
