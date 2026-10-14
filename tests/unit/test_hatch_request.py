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
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.core.models import DownloadRequest, KeptThumbnails
from tracks_and_trails.downloader.extra_options import (
    admit,
    options_for,
    refusal_lines,
    remember_the_hatch,
)
from tracks_and_trails.downloader.ytdlp_adapter import (
    UnusableOptionsError,
    build_options,
    hatch_options,
    options_needing_ffmpeg,
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


def test_a_job_that_embeds_writes_its_thumbnail_when_none_is_kept() -> None:
    """`ARC-010`'s amendment, through the real `build_options`.

    `EmbedThumbnail` embeds a file that has to exist first (`T-109`). Keeping no thumbnail against
    a job that embeds would leave it with nothing to embed, which is a key accepted and silently
    ineffective — so the union keeps the write. *(Through the hatch's `--no-write-thumbnail` until
    `T-249` gave the keep a control, which admission now refuses that spelling for.)*
    """
    request = a_request(embed_thumbnail=True, keep_thumbnails=KeptThumbnails.NONE)

    options = build_options(request, BASE["output_template"])

    assert options["writethumbnail"] is True


@pytest.mark.parametrize("kept", [KeptThumbnails.BEST, KeptThumbnails.ALL])
def test_a_kept_thumbnail_survives_the_embed_that_would_delete_it(kept: KeptThumbnails) -> None:
    """`T184-R11`: the real `EmbedThumbnail` deletes the cover unless told otherwise.

    A job that embeds **and** a user who asked to keep the picture both get what they asked for
    only if the spec carries `already_have_thumbnail`. Without it the union wrote the file and the
    postprocessor removed it, and the download reported success with the thumbnail gone. The keep
    is `T-249`'s control now, and was the hatch's `--write-thumbnail` before it.
    """
    request = a_request(embed_thumbnail=True, keep_thumbnails=kept)

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


@pytest.mark.parametrize("ffmpeg_installed", [False, True])
@pytest.mark.parametrize(
    ("text", "partial"),
    [
        ('--download-sections "*1-2"', True),
        ("--fragment-retries 3", False),
        ("", False),
    ],
)
def test_a_partial_download_needs_ffmpeg_by_yt_dlp_s_own_decision(
    text: str, partial: bool, ffmpeg_installed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T184-R14`, seventh round: downloading counts as ffmpeg work, not only post-processing.

    The preflight read only `postprocessors`, so `--download-sections "*1-2"` said no ffmpeg was
    needed for a resolved single-file format, and yt-dlp then aborted: *"You have requested
    downloading the video partially, but ffmpeg is not installed"*. Here the options the job is
    built with drive yt-dlp's own range callback and downloader choice for an ordinary item.
    yt-dlp aborts exactly when an item has a `section_start` and the choice is not `FFmpegFD`.
    """
    from yt_dlp.downloader import get_suitable_downloader
    from yt_dlp.downloader.external import FFmpegFD

    monkeypatch.setattr(
        FFmpegFD, "available", classmethod(lambda _cls, _path=None: ffmpeg_installed)
    )
    _, argv = options_for(text)
    request = a_request(extra_options=text, extra_option_argv=argv)
    options = build_options(request, BASE["output_template"])
    item = {"id": "t184", "url": "https://example.invalid/t184.mp4", "ext": "mp4", "duration": 10}

    ranges = options.get("download_ranges", lambda *_: [{}])
    sections = [section for section in ranges(item, None) if section]
    cut = [
        {**item, "section_start": section["start_time"], "section_end": section["end_time"]}
        for section in sections
    ]
    aborts = any(get_suitable_downloader(dict(each), options) is not FFmpegFD for each in cut)

    assert requires_ffmpeg(request) is partial
    assert bool(cut) is partial, "the range callback did not cut the item as expected"
    assert aborts is (partial and not ffmpeg_installed), (
        "yt-dlp's own choice disagrees: it aborts only where sections need an absent ffmpeg"
    )


@pytest.mark.parametrize("text", ['--download-sections "intro"', '--download-sections "*from-url"'])
def test_sections_that_depend_on_the_item_are_counted_as_ffmpeg_work(text: str) -> None:
    """A chapter pattern cuts only items with a matching chapter, and `*from-url` only a URL with
    a time in it. Neither is knowable before the item, so both count: a refusal up front costs
    less than an abort after the probe. `download_range_func.__eq__` ignores `from_info`, which is
    why the predicate asks what the ranges hold rather than comparing them with the default.
    """
    _, argv = options_for(text)

    assert requires_ffmpeg(a_request(extra_options=text, extra_option_argv=argv))


@pytest.mark.parametrize(
    ("option", "value"),
    [
        pytest.param(option, f"{prefix}{pattern}", id=f"{option}-{failure}")
        for option, prefix in (
            ("--match-filters", "title~="),
            ("--break-match-filters", "title~="),
            ("--remove-chapters", ""),
            ("--download-sections", ""),
        )
        for pattern, failure in (
            ("a{4294967296}", "overflow"),
            ("(" * 500 + "a" + ")" * 500, "recursion"),
        )
    ],
)
def test_a_stored_pattern_that_cannot_compile_is_the_stored_options_refusal(
    option: str, value: str
) -> None:
    """`T184-R8`, eighth round: stored consumption raised `OverflowError` or `RecursionError`.

    Admission parses nothing, so a hand-edited preset or request can carry such a pair. The job
    must meet the documented `UnusableOptionsError`, and the ffmpeg preflight must answer.
    """
    text = shlex.join([option, value])
    argv = admit(text).accepted
    assert argv, "admission now refuses it, so this would never reach the parse"
    request = a_request(extra_options=text, extra_option_argv=argv)

    with pytest.raises(UnusableOptionsError):
        hatch_options(text, argv)
    with pytest.raises(UnusableOptionsError):
        build_options(request, BASE["output_template"])
    assert requires_ffmpeg(request) is False
    # Defensive, since no route hands it unparsed tokens today; asked directly so it is held.
    assert options_needing_ffmpeg(argv) == ()


def test_stored_options_the_audit_refuses_stop_the_build() -> None:
    """`T184-R5`, through `build_options` itself: a hand-edited preset cannot smuggle one in."""
    request = a_request(extra_options="--continue", extra_option_argv=("--geo-bypass",))

    with pytest.raises(UnusableOptionsError):
        build_options(request, BASE["output_template"])


@pytest.mark.parametrize(
    ("kept", "key"),
    [(KeptThumbnails.BEST, "writethumbnail"), (KeptThumbnails.ALL, "write_all_thumbnails")],
)
def test_a_user_asking_for_the_thumbnail_gets_it_without_embedding(
    kept: KeptThumbnails, key: str
) -> None:
    """The other direction: the application wanted no picture and the user does (`T-249`)."""
    request = a_request(keep_thumbnails=kept)

    options = build_options(request, BASE["output_template"])

    assert options[key] is True


def test_the_hatch_brings_no_processor_it_did_not_name() -> None:
    """`T184-R10`'s correction copied the whole parsed chain, yt-dlp's defaults included.

    Every `parse_options` result carries `FFmpegConcat` with `only_multi_video`, which is
    `--concat-playlist`'s default. The audit refuses that option and the application's chain never
    had it, yet it arrived with any processor the hatch named.
    """
    for text in ("--convert-thumbnails png", "--split-chapters"):
        request = a_request(extra_options=text, extra_option_argv=tuple(text.split()))

        keys = [
            spec.get("key")
            for spec in build_options(request, BASE["output_template"])["postprocessors"]
        ]

        assert "FFmpegConcat" not in keys, f"{text!r} brought in a refused option's default: {keys}"


def test_a_stored_filter_yt_dlp_cannot_read_stops_the_build() -> None:
    """Re-admission asks what the dialog asks, or a hand-edited preset skips the question.

    The parse accepts any text for a filter, so without this the job would start and fail on the
    first item instead of being refused with its reason (`T184-R5`, `T184-R8`).
    """
    value = "duration<5 & title ~~ x"
    request = a_request(
        extra_options=f'--match-filters "{value}"', extra_option_argv=("--match-filters", value)
    )

    with pytest.raises(UnusableOptionsError):
        build_options(request, BASE["output_template"])


@pytest.mark.parametrize(
    ("text", "key", "expected"),
    [
        ("--encoding T184-nope --encoding utf-8", "encoding", "utf-8"),
        ('--replace-in-metadata=title foo ""', "postprocessors", "title"),
    ],
)
def test_what_the_seam_accepts_the_job_builds_the_same_way(
    text: str, key: str, expected: str
) -> None:
    """`T184-R8`: the seam, the stored tokens and the worker agree with yt-dlp's parser.

    Both were refused or cut short before the 2026-09-27 redesign. Re-admission at build time runs
    the same tokenizer and the same effective-value check, so a field the dialog accepted builds.
    """
    admission, argv = options_for(text)
    assert admission.usable, refusal_lines(admission)

    options = build_options(
        a_request(extra_options=text, extra_option_argv=argv), BASE["output_template"]
    )

    assert expected in repr(options[key]), options[key]


def test_a_value_spelled_like_an_option_is_only_a_value() -> None:
    """The merge asked every token which destinations it names, values included.

    So the value in `--output-na-placeholder --fragment-retries` copied `--fragment-retries`'
    destination at its default, an option the user never named. Measured 2026-09-26: 305 fields
    built this way copied a key their named option does not touch. The placeholder takes any text,
    so nothing else refuses it first.
    """
    request = a_request(
        extra_options="--output-na-placeholder --fragment-retries",
        extra_option_argv=("--output-na-placeholder", "--fragment-retries"),
    )

    options = build_options(request, BASE["output_template"])

    assert "fragment_retries" not in options, "a value was read as the option it is spelled like"


def test_an_option_with_several_destinations_brings_only_what_it_changed() -> None:
    """`--compat-options` carried the command line's default for every key it can reach.

    One of them is `ignoreerrors: "only_download"`, which is what `-i/--ignore-errors` sets and
    the audit refuses: the worker reads success from the info dict, so a failed conversion was
    reported as a finished download (`T183-R2`). `T184-R1` still holds for an option with one
    destination, whose value travels even when it equals the default.
    """
    request = a_request(
        extra_options="--compat-options no-live-chat --fragment-retries 10",
        extra_option_argv=("--compat-options", "no-live-chat", "--fragment-retries", "10"),
    )

    options = build_options(request, BASE["output_template"])

    assert options["compat_opts"] == {"no-live-chat"}
    assert not options.get("ignoreerrors"), "a failed download would be reported as a success"
    assert options["fragment_retries"] == 10, "T184-R1: a value equal to the default was dropped"


# --- what a log may carry (`T184-R6`) ------------------------------------------------------------


@pytest.fixture
def registered() -> Iterator[None]:
    """Registered values are process-wide, so each test here starts and ends with none."""
    from tracks_and_trails.core.logging import forget_the_secrets

    forget_the_secrets()
    yield
    forget_the_secrets()


def _shown(message: str) -> str:
    """`message` as the application's own formatter writes it."""
    import logging

    from tracks_and_trails.core.logging import RedactingFormatter

    record = logging.LogRecord("t", logging.INFO, __file__, 1, message, (), None)
    return RedactingFormatter().format(record)


def test_a_hatch_value_is_redacted_where_yt_dlp_itself_prints_it(registered: None) -> None:
    """**`repr=False` was necessary and nowhere near sufficient.**

    The reviewer typed a match filter carrying a canary and watched `YoutubeDL._match_entry` write
    it through `YtdlpLog` and the real formatter, with no verbose mode involved. That the manager
    calls this in the process that formats is `test_worker_logging`'s to prove, across a spawn.
    """
    canary = "T184_FILTER_CANARY_UNIQUE"

    remember_the_hatch(("--match-filters", f"title~={canary}"))

    assert canary not in _shown(f"[download] does not pass filter (title~={canary})")


def test_the_equals_spelling_is_registered_as_well(registered: None) -> None:
    """`--match-filters=title~=X` is one token, and the first correction skipped it entirely.

    It asked whether the token's spelling was an option's, which it is, and registered nothing.
    """
    canary = "T184_EQUALS_CANARY"

    remember_the_hatch((f"--match-filters=title~={canary}",))

    assert canary not in _shown(f"[download] does not pass filter (title~={canary})")


def test_a_header_value_is_redacted_without_its_name(registered: None) -> None:
    """yt-dlp keeps headers as a mapping, so it prints the value apart from `Name:`."""
    canary = "T184_HEADER_CANARY"

    remember_the_hatch((f"--add-headers=Authorization: Bearer {canary}",))

    assert canary not in _shown(f"headers: {{'Authorization': 'Bearer {canary}'}}")


def test_a_piece_of_an_extractor_argument_is_redacted_where_yt_dlp_prints_it_alone(
    registered: None,
) -> None:
    """yt-dlp splits `--extractor-args` before it uses it, and prints one piece by itself.

    A malformed `po_token` is echoed back alone, *Expected "CLIENT.CONTEXT+PO_TOKEN", got "…"*,
    measured 2026-09-26 through the real `YoutubeIE._get_config_po_token`. The whole argument was
    registered and the piece was not.
    """
    canary = "T184_PO_TOKEN_CANARY"

    remember_the_hatch(("--extractor-args", f"youtube:player_client=web;po_token={canary}"))

    assert canary not in _shown(f'Expected "CLIENT.CONTEXT+PO_TOKEN", got "{canary}"')


def test_a_filter_is_redacted_as_yt_dlp_prints_it_trimmed(registered: None) -> None:
    """`match_filter_func` strips each filter before it names one it rejected."""
    canary = "T184_SPACED_FILTER_CANARY"

    remember_the_hatch(("--match-filters", f" title={canary} "))

    assert canary not in _shown(f"Clip does not pass filter (title={canary}), skipping ..")


def test_a_part_of_a_filter_is_redacted_where_yt_dlp_quotes_it_alone(registered: None) -> None:
    """`match_str` splits a filter on `&` and quotes a part it cannot read with `repr`."""
    canary = "T184_FILTER_PART_CANARY"

    remember_the_hatch(("--match-filters", f"duration<5 & {canary} ~~ x"))

    assert canary not in _shown(f"Invalid filter part ' {canary} ~~ x'")


def _yt_dlp_logged(options: dict[str, Any], act: Any) -> str:
    """What yt-dlp printed while `act` ran, through the application's own logger and formatter."""
    import io
    import logging

    from yt_dlp import YoutubeDL

    from tracks_and_trails.core.logging import RedactingFormatter, YtdlpLog

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter())
    logger = logging.getLogger("t184.real-consumer")
    logger.addHandler(handler)
    logger.propagate = False
    try:
        with YoutubeDL({**options, "logger": YtdlpLog(logger)}) as ydl:
            act(ydl)
    finally:
        logger.removeHandler(handler)
    return stream.getvalue()


@pytest.mark.parametrize(
    "spelling", ["$T184_CACHE_ROOT/private-cache-canary", "~/private-cache-canary"]
)
def test_a_cache_path_is_redacted_as_yt_dlp_expands_it(
    registered: None, spelling: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T184-R6`, the Reviewer's reproduction: yt-dlp's own cache warning printed the path expanded.

    The path was registered only as typed, and `$T184_CACHE_ROOT/…` cannot match what it becomes.
    Measured through the real `YoutubeDL.cache.load` and the application's formatter, no verbose
    mode involved.
    """
    monkeypatch.setenv("T184_CACHE_ROOT", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    text = f"--cache-dir '{spelling}'"
    admission, argv = options_for(text)
    assert admission.usable, refusal_lines(admission)
    broken = tmp_path / "private-cache-canary" / "probe" / "key.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{", encoding="utf-8")

    remember_the_hatch(argv)
    options = build_options(
        a_request(extra_options=text, extra_option_argv=argv), BASE["output_template"]
    )
    said = _yt_dlp_logged(options, lambda ydl: ydl.cache.load("probe", "key"))

    assert "Cache retrieval" in said, f"yt-dlp printed nothing to redact: {said!r}"
    assert "private-cache-canary" not in said, said


def test_a_netrc_location_is_redacted_as_yt_dlp_expands_it(
    registered: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other expansion family: `~` alone, which is all yt-dlp does to a netrc location."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    text = "--netrc --netrc-location ~/private-netrc-canary"
    admission, argv = options_for(text)
    assert admission.usable, refusal_lines(admission)
    (tmp_path / "private-netrc-canary").write_text("machine\n", encoding="utf-8")

    remember_the_hatch(argv)
    options = build_options(
        a_request(extra_options=text, extra_option_argv=argv), BASE["output_template"]
    )
    said = _yt_dlp_logged(
        options,
        lambda ydl: ydl.get_info_extractor("Youtube")._get_login_info(netrc_machine="youtube"),
    )

    assert "netrc" in said, f"yt-dlp printed nothing to redact: {said!r}"
    assert "private-netrc-canary" not in said, said


@pytest.mark.parametrize(
    ("argv", "value"),
    [
        (("--default-search", "T184_SEARCH_CANARY"), "T184_SEARCH_CANARY"),
        (("--output-na-placeholder", "T184_PLACEHOLDER_CANARY"), "T184_PLACEHOLDER_CANARY"),
    ],
)
def test_the_two_unrestricted_text_options_are_registered(
    registered: None, argv: tuple[str, ...], value: str
) -> None:
    """The Reviewer's entry-by-entry check of the exemptions: these two take any text at all."""
    remember_the_hatch(argv)

    assert value not in _shown(f"using {value} for this job")


def test_a_path_the_hatch_names_is_redacted_however_short(registered: None) -> None:
    """A path gets `remember_a_path`, which has no length floor (`T197-R1`)."""
    remember_the_hatch(("--client-certificate-key", "/k"))

    assert "/k" not in _shown("could not read /k")


@pytest.mark.parametrize(
    ("argv", "word"),
    [
        (("--sub-format", "best"), "best"),
        # `--retries` was this case until `T-361` refused it, an alias of `-R`, which has a control.
        (("--socket-timeout", "1000"), "1000"),
        (("--fixup", "never"), "never"),
        (("--convert-thumbnails", "webp"), "webp"),
        # `--max-filesize 100M` until `T-247` gave it a control, which refuses it here.
        (("--http-chunk-size", "10M"), "10M"),
        (("--sleep-requests", "1.25"), "1.25"),
        (("--fragment-retries=10",), "10"),
    ],
)
def test_an_ordinary_value_is_not_redacted_into_nonsense(
    registered: None, argv: tuple[str, ...], word: str
) -> None:
    """The first correction registered every argument and claimed the byte floor made it safe.

    The floor is four bytes. `best`, `1000`, `never`, `webp`, `100M` and `1.25` all clear it, so
    each one vanished from every later line of the log.
    """
    remember_the_hatch(argv)

    assert word in _shown(f"chose {word} for this job"), f"{argv} redacted an ordinary word"


def test_the_option_names_themselves_are_not_registered(registered: None) -> None:
    """Arguments carry the user's text; spellings are yt-dlp's own vocabulary."""
    remember_the_hatch(("--write-thumbnail",))

    assert "--write-thumbnail" in _shown("using --write-thumbnail for this job")


def test_only_admitted_options_are_exempt_and_no_credential_carrier_is() -> None:
    """The exemptions stay honest: each names an admitted option that takes a value.

    A stale entry would be harmless, but one that names a credential carrier would not be.
    """
    from tracks_and_trails.downloader.extra_options import (
        NOT_SECRET_VALUES,
        PATH_VALUES,
        _reason_to_refuse,
        option_arity,
    )

    arity = option_arity()
    for spelling in NOT_SECRET_VALUES | PATH_VALUES:
        assert arity.get(spelling, 0) > 0, f"{spelling} takes no value"
        assert _reason_to_refuse(spelling) is None, f"{spelling} is not admitted"

    carriers = {
        "--add-headers",
        "--extractor-args",
        "--match-filters",
        "--break-match-filters",
        "--parse-metadata",
        "--replace-in-metadata",
        "--geo-verification-proxy",
        "--source-address",
        # Unrestricted text, found by the Reviewer's entry-by-entry check (2026-09-27).
        "--default-search",
        "--output-na-placeholder",
    }
    assert not NOT_SECRET_VALUES & (carriers | PATH_VALUES)
