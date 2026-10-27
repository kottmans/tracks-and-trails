"""Extractor arguments, as one checked structure (`T-255`).

`--extractor-args KEY:ARG=VALUE,VALUE;ARG=VALUE` passes arguments to one extractor, and yt-dlp
ignores any it does not read, which is `T012-R5`'s *accepted and silently dropped*. Ruled
2026-10-19, all four as recommended:

1. **Six pairs are forbidden** (`SEC-003`, amended): two choose the host requests go to, one is
   impersonation, three switch off the solver's checks. Each is refused where it is typed, with the
   reason. Everything else is permitted.
2. **A pair is known when yt-dlp's source reads it** (`ARC-010`, amended, fourth): the allowlist is
   `core/extractor_arg_table.py`, generated from the pin. A plugin's keys are not on it.
3. **Values are stored as typed** (`DAT-003`, amended), kept out of the model's `repr`, and
   registered for redaction except where they come from a fixed vocabulary.
4. **The editor takes one `KEY:ARG=VALUE;…` per line** (`UX-015`, amended, third), and shows them
   back merged and normalized: one line per key, arguments in order.

**The grammar is yt-dlp's own, transcribed** from `options.py` at the pin, since `core/` may not
import yt-dlp: a key of word characters and `-`, then `:`; arguments split on `;`, each an argument
name, `=` and values split on unescaped commas, each stripped, `\\,` meaning a comma; a name is
lower-cased and its `-` read as `_`. **Where yt-dlp keeps only the last option for a key, this
merges them**, the later argument winning, so two lines for one extractor both count.
"""

from __future__ import annotations

import re
from typing import Final

from tracks_and_trails.core.extractor_arg_table import EXTRACTOR_ARGS

#: One argument: the extractor's key, the argument's name, and its values, as yt-dlp passes them.
ExtractorArg = tuple[str, str, tuple[str, ...]]

#: The pairs `SEC-003` forbids (amended 2026-10-19, `T-255`'s question 1), each with why, in the
#: words the editor shows. A pair here is refused whatever its value.
FORBIDDEN: Final[dict[tuple[str, str], str]] = {
    ("youtube", "innertube_host"): (
        "youtube:innertube_host is not allowed: it sends YouTube's requests, and your sign-in with "
        "them, to whatever host it names, so a typo would be a new place your data goes."
    ),
    ("tiktok", "api_hostname"): (
        "tiktok:api_hostname is not allowed: it sends TikTok's requests, and your session's cookie "
        "with them, to whatever host it names, so a typo would be a new place your data goes."
    ),
    ("generic", "impersonate"): (
        "generic:impersonate is not allowed: it makes requests pretend to be another browser, "
        "which this application does not do."
    ),
    ("youtube-ejs", "dev"): (
        "youtube-ejs:dev is not allowed: it turns off yt-dlp's checks on the script it runs to "
        "read YouTube."
    ),
    ("youtube-ejs", "repo"): (
        "youtube-ejs:repo is not allowed: it fetches the script yt-dlp runs from somewhere other "
        "than where yt-dlp checks it."
    ),
    ("youtube-ejs", "script_version"): (
        "youtube-ejs:script_version is not allowed: it asks for a script yt-dlp has not checked."
    ),
}

#: Arguments whose values come from a fixed vocabulary, so cannot carry a secret, and are left
#: readable in the logs (`DAT-003`, amended 2026-10-19). **Every other value is registered for
#: redaction**, which is the safe direction for an argument this list does not know: a value of
#: `po_token`, `visitor_data`, `hls_key`, `device_id` or `client_id` is a token. Read from each
#: argument's use at the pin; my classification, stated for review.
FIXED_VOCABULARY: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("afreecatvlive", "cdn"),
        ("bilibili", "prefer_multi_flv"),
        ("gamejolt", "comment_sort"),
        ("generic", "is_live"),
        ("hotstar", "dr"),
        ("hotstar", "res"),
        ("hotstar", "vcodec"),
        ("jiosaavn", "bitrate"),
        ("nflplusreplay", "type"),
        ("nhkradirulive", "area"),
        ("niconicochannelplus", "max_comments"),
        ("orfon", "prefer_segments_playlist"),
        ("rokfinchannel", "tab"),
        ("sonylivseries", "sort_order"),
        ("soundcloud", "comments_sort_by"),
        ("soundcloud", "formats"),
        ("tver", "backend"),
        ("twitter", "api"),
        ("vimeo", "client"),
        ("vimeo", "original_format_policy"),
        ("youtube", "comment_sort"),
        ("youtube", "fetch_pot"),
        ("youtube", "formats"),
        ("youtube", "include_duplicate_formats"),
        ("youtube", "jsc_trace"),
        ("youtube", "lang"),
        ("youtube", "max_comments"),
        ("youtube", "player_client"),
        ("youtube", "player_js_variant"),
        ("youtube", "player_skip"),
        ("youtube", "pot_trace"),
        ("youtube", "raise_incomplete_data"),
        ("youtube", "skip"),
        ("youtube", "use_ad_playback_context"),
        ("youtube", "webpage_client"),
        ("youtube", "webpage_skip"),
        ("youtube-ejs", "jitless"),
        ("youtubepot-webpo", "bind_to_visitor_id"),
        ("youtubetab", "approximate_date"),
        ("youtubetab", "skip"),
        ("youtubewebarchive", "check_all"),
        ("zan", "split_angles"),
    }
)

#: yt-dlp's `_dict_from_options_callback` with `multiple_keys=False`: a key, then `:`.
_LINE: Final = re.compile(r"(?is)(?P<key>[\w-]+):(?P<arguments>.*)$")
#: A comma that separates values; `\,` is a comma inside one.
_SEPARATOR: Final = re.compile(r"(?<!\\),")

#: Said when a key or an argument is unknown, and when a line has no shape at all.
NOT_A_LINE: Final = "{line} is not KEY:ARGUMENT=VALUE, such as youtube:player_client=web."
UNKNOWN_KEY: Final = "{key} is not a name yt-dlp reads extractor arguments under."
UNKNOWN_ARGUMENT: Final = "{key} has no argument called {argument}. It has: {known}."
NO_ARGUMENT: Final = "{key}: names no argument."


def parsed(text: str) -> tuple[tuple[ExtractorArg, ...], list[str]]:
    """The arguments `text` holds, one `KEY:ARGUMENTS` per line, merged, and what is wrong.

    **Merged and normalized**: by key and then argument name, the later line winning for one
    argument, so the structure is the same however it was typed. Every problem is reported, one per
    line or argument; the structure holds only what passed.
    """
    merged: dict[tuple[str, str], tuple[str, ...]] = {}
    problems: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        found = _LINE.match(line)
        if found is None:
            problems.append(NOT_A_LINE.format(line=line))
            continue
        key = found.group("key").lower()
        # **An empty segment is a stray `;`**, which yt-dlp reads as an argument with no name and
        # nothing reads; a line with nothing else names no argument at all.
        arguments = [
            argument for argument in found.group("arguments").split(";") if argument.strip()
        ]
        if not arguments:
            problems.append(NO_ARGUMENT.format(key=key))
        for argument in arguments:
            name, _, values = argument.partition("=")
            name = name.strip().lower().replace("-", "_")
            problem = pair_problem(key, name)
            if problem is not None:
                problems.append(problem)
                continue
            merged[(key, name)] = tuple(
                value.replace(r"\,", ",").strip() for value in _SEPARATOR.split(values)
            )
    return tuple((key, name, merged[key, name]) for key, name in sorted(merged)), problems


def pair_problem(key: str, name: str) -> str | None:
    """Why yt-dlp would ignore `key:name`, or why it is forbidden, or `None` (`T-255`)."""
    if not name:
        return NO_ARGUMENT.format(key=key)
    known = EXTRACTOR_ARGS.get(key)
    if known is None:
        return UNKNOWN_KEY.format(key=key)
    if name not in known:
        # **Only what may be used is offered**: a forbidden argument is known, and not one to name.
        offered = sorted(argument for argument in known if (key, argument) not in FORBIDDEN)
        return UNKNOWN_ARGUMENT.format(key=key, argument=name, known=", ".join(offered))
    return FORBIDDEN.get((key, name))


def extractor_args_problem(value: object) -> str | None:
    """Why `value` is not a structure `parsed` produces, or `None`: the model's rule.

    **Exactly what the editor can show back and read again**: sorted, each pair once, every pair
    known and permitted, and no value holding what the grammar cannot carry, a `;`, a line break,
    or space at either end.
    """
    if not isinstance(value, tuple):
        return f"must be a tuple of (key, argument, values), not {type(value).__name__}"
    seen: list[tuple[str, str]] = []
    for item in value:
        if not (
            isinstance(item, tuple)
            and len(item) == 3
            and isinstance(item[0], str)
            and isinstance(item[1], str)
            and isinstance(item[2], tuple)
            and item[2]
            and all(isinstance(v, str) for v in item[2])
        ):
            return f"{item!r} is not (key, argument, values)"
        key, name, values = item
        problem = pair_problem(key, name)
        if problem is not None:
            return problem
        for one in values:
            if ";" in one or "\n" in one or "\r" in one or one != one.strip():
                return f"{key}:{name} has a value the editor cannot show back: {one!r}"
        seen.append((key, name))
    if seen != sorted(set(seen)):
        return "must name each pair once, in order"
    return None


def as_text(value: tuple[ExtractorArg, ...]) -> str:
    """One line per key, `KEY:ARG=VALUE,VALUE;ARG=VALUE`, as the editor shows them back."""
    lines: dict[str, list[str]] = {}
    for key, name, values in value:
        joined = ",".join(one.replace(",", r"\,") for one in values)
        lines.setdefault(key, []).append(f"{name}={joined}")
    return "\n".join(f"{key}:{';'.join(arguments)}" for key, arguments in lines.items())


def as_ytdlp(value: tuple[ExtractorArg, ...]) -> dict[str, dict[str, list[str]]]:
    """What yt-dlp's `extractor_args` option takes: key, then argument, then its values."""
    options: dict[str, dict[str, list[str]]] = {}
    for key, name, values in value:
        options.setdefault(key, {})[name] = list(values)
    return options


def secret_values(value: tuple[ExtractorArg, ...]) -> tuple[str, ...]:
    """The values to register for redaction: all but a fixed vocabulary's (`DAT-003`)."""
    return tuple(
        one
        for key, name, values in value
        if (key, name) not in FIXED_VOCABULARY
        for one in values
        if one
    )
