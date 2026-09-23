"""The hatch on the request: stored, persisted, and reaching `build_options` (`T-184`).

The field holds the text the user typed and the **admitted argv** — the tokens admission produced
from it. The parsed dictionary was the first shape, ruled on 2026-09-20 and superseded on
2026-09-22 by `T184-R9`: 13 of 124 admitted options parse to values that cannot cross `ARC-002`'s
process boundary, and a compiled match filter is a closure whose only honest encoding is the text
it came from.

**The tokens are re-admitted where they are used**, which is `T184-R5`: a preset is a file a user
can edit and a request is a JSON blob in a database, so tokens can arrive that no dialog produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.downloader.ytdlp_adapter import (
    UnusableOptionsError,
    build_options,
    requires_ffmpeg,
)
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


def test_a_list_of_tokens_becomes_a_tuple() -> None:
    """**Tokens, not a parsed dictionary** (ruling of 2026-09-22, `T184-R9`).

    13 of 124 admitted options parse to values that cannot cross `ARC-002`'s boundary — a
    `DateRange`, compiled match filters, a `set`. Tokens are text, so they cross it, round-trip
    through JSON and TOML, and cannot be mutated behind an already-created request (`T184-R12`).
    """
    request = a_request(extra_option_argv=["--fragment-retries", "10"])

    assert request.extra_option_argv == ("--fragment-retries", "10")


def test_a_token_that_is_not_text_is_refused() -> None:
    """`ARC-002`: the request is pickled to a worker and stored as JSON. Tokens are text."""
    with pytest.raises(TypeError, match="option token"):
        a_request(extra_option_argv=[object()])


def test_an_empty_argument_is_a_valid_argument() -> None:
    """`T184-R9`: a token is not always an option spelling.

    `--replace-in-metadata title foo ""` asks for the matched text to be **removed**, and the
    empty replacement is the whole request. The real command line accepts it and so does
    admission; this model refused it, so a field the user could type could not be constructed.
    What a token means is the parser's to judge.
    """
    request = a_request(extra_option_argv=["--replace-in-metadata", "title", "foo", ""])

    assert request.extra_option_argv == ("--replace-in-metadata", "title", "foo", "")


def test_no_token_is_repeated_in_a_validation_message() -> None:
    """`T184-R6`: this message reaches a settings problem, and startup logs that.

    The reviewer saved a preset whose header value was a canary, and the reload failure quoted it
    into a line the real formatter then left intact. A message that names positions and types
    instead cannot do that.
    """
    with pytest.raises(TypeError) as refused:
        a_request(extra_option_argv=["--add-headers", b"Authorization: Bearer T184_CANARY"])

    assert "T184_CANARY" not in str(refused.value), f"a token was quoted: {refused.value}"


def test_a_request_with_no_hatch_carries_nothing() -> None:
    """The common case, and the default that lets an older stored row load."""
    request = a_request()

    assert request.extra_options == ""
    assert request.extra_option_argv == ()


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
        extra_option_argv=("--add-headers", "Authorization: Bearer s3cr3t"),
    )

    shown = repr(request)

    assert "s3cr3t" not in shown, f"a hatch secret reached the repr: {shown}"
    assert "Authorization" not in shown
    assert "add-headers" not in shown


# --- persistence ---------------------------------------------------------------------------------


def test_the_hatch_survives_a_database_round_trip() -> None:
    """JSON has no tuples, so the tokens come back as a list and the model re-tuples them."""
    request = a_request(
        extra_options="--continue --sub-langs en,de",
        extra_option_argv=("--continue", "--sub-langs", "en,de"),
    )

    back = _deserialize_request(_serialize_request(request))

    assert back == request
    assert back.extra_option_argv == ("--continue", "--sub-langs", "en,de")


def test_a_row_written_before_the_field_existed_still_loads() -> None:
    """**And this is why no migration is owed** (`T-048`, measured 2026-09-20).

    The request is one JSON blob rather than columns, and `_deserialize_request` gives a field the
    blob does not carry the dataclass default. A row from an older build is a request that
    genuinely did not ask for the option, and `""` is what "did not ask" means.
    """
    older = json.dumps(BASE)

    request = _deserialize_request(older)

    assert request.extra_options == ""
    assert request.extra_option_argv == ()


# --- reaching yt-dlp ------------------------------------------------------------------------------


def test_the_admitted_options_reach_the_option_dictionary() -> None:
    """The acceptance criterion, asserted on the dictionary rather than on a download."""
    request = a_request(
        extra_options="--continue --fragment-retries 10",
        extra_option_argv=("--continue", "--fragment-retries", "10"),
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
        extra_option_argv=("--extractor-args", "youtube:player_client=web"),
    )

    probe = build_options(request, BASE["output_template"], probe_only=True)

    assert probe["extractor_args"] == {"youtube": {"player_client": ["web"]}}


def test_the_application_keeps_its_probe_keys() -> None:
    """The hatch is applied before the probe branch, so the application's own keys still win."""
    request = a_request(extra_options="--continue", extra_option_argv=("--continue",))

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
        extra_option_argv=("--no-write-thumbnail",),
    )

    options = build_options(request, BASE["output_template"])

    assert options["writethumbnail"] is True


def test_a_kept_thumbnail_survives_the_embed_that_would_delete_it() -> None:
    """`T184-R11`: the real `EmbedThumbnail` deletes the cover unless told otherwise.

    A job that embeds **and** a user who asked to keep the picture both get what they asked for
    only if the spec carries `already_have_thumbnail`. Without it the union wrote the file and the
    postprocessor removed it, and the download reported success with the thumbnail gone.
    """
    request = a_request(
        embed_thumbnail=True,
        extra_options="--write-thumbnail",
        extra_option_argv=("--write-thumbnail",),
    )

    options = build_options(request, BASE["output_template"])
    embed = [spec for spec in options["postprocessors"] if spec.get("key") == "EmbedThumbnail"]

    assert embed == [{"key": "EmbedThumbnail", "already_have_thumbnail": True}]


def test_embedding_alone_still_removes_the_picture_afterwards() -> None:
    """**Keyed on what the user asked**, not on the key the application sets to have a picture.

    `build_options` sets `writethumbnail` itself whenever it embeds, purely so there is something
    to embed. Reading that would keep the file for every embedding job, which `REQ-010` does not
    ask for and `T-109` decided against.
    """
    request = a_request(embed_thumbnail=True)

    options = build_options(request, BASE["output_template"])
    embed = [spec for spec in options["postprocessors"] if spec.get("key") == "EmbedThumbnail"]

    assert embed == [{"key": "EmbedThumbnail", "already_have_thumbnail": False}]


def test_the_hatch_s_postprocessors_are_not_thrown_away() -> None:
    """`T184-R10`: this assignment used to replace the hatch's chain with the application's."""
    request = a_request(extra_options="--split-chapters", extra_option_argv=("--split-chapters",))

    keys = [
        spec.get("key")
        for spec in build_options(request, BASE["output_template"])["postprocessors"]
    ]

    assert "FFmpegSplitChapters" in keys, f"the hatch's processors were dropped: {keys}"


def test_the_ffmpeg_preflight_counts_the_hatch_s_work() -> None:
    """The same finding's other half: `REQ-024` asks **before** the bytes are spent."""
    plain = a_request()
    splitting = a_request(extra_options="--split-chapters", extra_option_argv=("--split-chapters",))

    assert not requires_ffmpeg(plain)
    assert requires_ffmpeg(splitting), "a job needing ffmpeg said it did not"


def test_stored_options_the_audit_refuses_stop_the_build() -> None:
    """`T184-R5`, through `build_options` itself: a hand-edited preset cannot smuggle one in."""
    request = a_request(extra_options="--continue", extra_option_argv=("--geo-bypass",))

    with pytest.raises(UnusableOptionsError):
        build_options(request, BASE["output_template"])


def test_a_user_asking_for_the_thumbnail_gets_it_without_embedding() -> None:
    """The other direction: the application wanted no picture and the user does."""
    request = a_request(extra_options="--write-thumbnail", extra_option_argv=("--write-thumbnail",))

    options = build_options(request, BASE["output_template"])

    assert options["writethumbnail"] is True
