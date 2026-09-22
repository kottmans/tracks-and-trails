"""The hatch on the request: stored, persisted, and reaching `build_options` (`T-184`).

The maintainer ruled on 2026-09-20 that the field holds **both** the text the user typed and the
parsed result. The text is what they edit and must be shown back unchanged; the parsed result is
what the worker receives, which is `REQ-031`'s "the parsed result is a declared field of the
download request rather than an untyped dictionary".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.ytdlp_adapter import build_options
from tracks_and_trails.persistence.repositories import _deserialize_request, _serialize_request

BASE: dict[str, Any] = {
    "url": "https://example.invalid/watch?v=x",
    "output_directory": str(Path.home() / "downloads"),
    "format_selector": "bv*+ba/b",
    "output_template": "%(title)s.%(ext)s",
}


def a_request(**overrides: Any) -> DownloadRequest:
    return DownloadRequest(**BASE, **overrides)


# --- the field itself ---------------------------------------------------------------------------


def test_the_text_is_kept_exactly_as_typed() -> None:
    """Storing only the parse would hand `-c` back as `--continue` (the 2026-09-20 ruling)."""
    request = a_request(extra_options="-c  --fragment-retries 10")

    assert request.extra_options == "-c  --fragment-retries 10"


def test_a_mapping_becomes_sorted_pairs() -> None:
    """**Pairs, not a mapping**, for the reason every collection field here is a tuple.

    A frozen dataclass holding a dict is only shallowly frozen, and this object crosses a process
    boundary (`ARC-002`) and is written to the database. Sorting means two requests built from the
    same options compare and serialize identically whatever order the parser produced.
    """
    request = a_request(extra_option_values={"fragment_retries": 10, "continuedl": True})

    assert request.extra_option_values == (("continuedl", True), ("fragment_retries", 10))


def test_a_value_that_cannot_cross_the_boundary_is_refused() -> None:
    """`ARC-002`: the request is pickled to a worker and stored as JSON. Both or neither."""
    with pytest.raises(TypeError, match="JSON and pickle"):
        a_request(extra_option_values={"key": object()})


def test_a_pair_that_is_not_a_pair_is_refused() -> None:
    with pytest.raises(TypeError, match="pair"):
        a_request(extra_option_values=[("only-one",)])


def test_a_request_with_no_hatch_carries_nothing() -> None:
    """The common case, and the default that lets an older stored row load."""
    request = a_request()

    assert request.extra_options == ""
    assert request.extra_option_values == ()


def test_neither_half_of_the_hatch_reaches_the_repr() -> None:
    """**Unrepresentable rather than filtered**, which is `core/logging.py`'s own reasoning.

    Redaction happens on the finished string at the handler, because `f"starting {request}"` is
    the most natural line anyone will write. A hatch value cannot be filtered by shape: the option
    name is innocuous and the value is not, as in `--add-headers "Authorization: Bearer …"`, and
    no pattern separates that from `--concurrent-fragments 4`. So it is kept out of the repr,
    which is the route into a log this application actually takes.
    """
    request = a_request(
        extra_options='--add-headers "Authorization: Bearer s3cr3t"',
        extra_option_values={"http_headers": {"Authorization": "Bearer s3cr3t"}},
    )

    shown = repr(request)

    assert "s3cr3t" not in shown, f"a hatch secret reached the repr: {shown}"
    assert "Authorization" not in shown
    assert "add-headers" not in shown


# --- persistence ---------------------------------------------------------------------------------


def test_the_hatch_survives_a_database_round_trip() -> None:
    """JSON has no tuples, so the pairs come back as lists and the model re-tuples them."""
    request = a_request(
        extra_options="--continue --sub-langs en,de",
        extra_option_values={"continuedl": True, "subtitleslangs": ["en", "de"]},
    )

    back = _deserialize_request(_serialize_request(request))

    assert back == request
    assert back.extra_option_values == (("continuedl", True), ("subtitleslangs", ["en", "de"]))


def test_a_row_written_before_the_field_existed_still_loads() -> None:
    """**And this is why no migration is owed** (`T-048`, measured 2026-09-20).

    The request is one JSON blob rather than columns, and `_deserialize_request` gives a field the
    blob does not carry the dataclass default. A row from an older build is a request that
    genuinely did not ask for the option, and `""` is what "did not ask" means.
    """
    older = json.dumps(BASE)

    request = _deserialize_request(older)

    assert request.extra_options == ""
    assert request.extra_option_values == ()


# --- reaching yt-dlp ------------------------------------------------------------------------------


def test_the_parsed_values_reach_the_option_dictionary() -> None:
    """The acceptance criterion, asserted on the dictionary rather than on a download."""
    request = a_request(
        extra_options="--continue --fragment-retries 10",
        extra_option_values={"continuedl": True, "fragment_retries": 10},
    )

    options = build_options(request, BASE["output_template"])

    assert options["continuedl"] is True
    assert options["fragment_retries"] == 10


def test_the_probe_sees_the_same_options_as_the_download() -> None:
    """Or the user picks a format the download cannot produce.

    `--extractor-args` changes which formats exist. A probe run without it lists one set and the
    download then uses another, and the mismatch surfaces as a format that vanished between
    choosing and downloading.
    """
    request = a_request(
        extra_options="--extractor-args youtube:player_client=web",
        extra_option_values={"extractor_args": {"youtube": {"player_client": ["web"]}}},
    )

    probe = build_options(request, BASE["output_template"], probe_only=True)

    assert probe["extractor_args"] == {"youtube": {"player_client": ["web"]}}


def test_the_application_keeps_its_probe_keys() -> None:
    """The hatch is applied before the probe branch, so the application's own keys still win."""
    request = a_request(
        extra_options="--continue", extra_option_values={"continuedl": True, "skip_download": False}
    )

    probe = build_options(request, BASE["output_template"], probe_only=True)

    assert probe["skip_download"] is True, "a hatch value overrode a key the probe path owns"


def test_a_job_that_embeds_keeps_its_thumbnail_when_the_user_says_no() -> None:
    """`ARC-010`'s amendment, through the real `build_options`.

    `EmbedThumbnail` embeds a file that has to exist first (`T-109`). A user's
    `--no-write-thumbnail` against a job that embeds would leave it with nothing to embed, which
    is a key accepted and silently ineffective — so the union keeps the write.
    """
    request = a_request(
        embed_thumbnail=True,
        extra_options="--no-write-thumbnail",
        extra_option_values={"writethumbnail": False},
    )

    options = build_options(request, BASE["output_template"])

    assert options["writethumbnail"] is True


def test_a_user_asking_for_the_thumbnail_gets_it_without_embedding() -> None:
    """The other direction: the application wanted no picture and the user does."""
    request = a_request(
        extra_options="--write-thumbnail", extra_option_values={"writethumbnail": True}
    )

    options = build_options(request, BASE["output_template"])

    assert options["writethumbnail"] is True
