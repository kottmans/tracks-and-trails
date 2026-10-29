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
   registered for redaction except a value from its argument's fixed vocabulary (`T255-R3`), in
   every spelling yt-dlp can print it in (`secret_values`).
4. **The editor takes one `KEY:ARG=VALUE;…` per line** (`UX-015`, amended, third), and shows them
   back merged and normalized: one line per key, arguments in order.

**The grammar is yt-dlp's own, transcribed** from `options.py` at the pin, since `core/` may not
import yt-dlp: a key of word characters and `-`, then `:`; arguments split on `;`, each an argument
name, `=` and values split on unescaped commas, each stripped, `\\,` meaning a comma; a name is
lower-cased and its `-` read as `_`. **Where yt-dlp keeps only the last option for a key, this
merges them**, the later argument winning, so two lines for one extractor both count.
"""

from __future__ import annotations

import base64
import binascii
import re
import urllib.parse
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """The values one argument may be left readable with (`DAT-003`, amended; `T255-R3`).

    **Words from a fixed set**, and a whole number where yt-dlp reads one as a count, which is
    what `int` reads: `str.isdecimal`, so fullwidth digits are one and a superscript is not. A
    value outside it is registered for redaction, however ordinary it looks: `player_client` takes
    any word, and yt-dlp's warning about one it does not know quotes it.

    **Read as yt-dlp reads it**: `_configuration_arg` lower-cases a value unless the extractor
    asks for its case (`casesense`), so `ANDROID` is the client `android` and stays readable, as
    the word it is. At the pin only YouTube's `lang` keeps its case (`T255-R3`, second round).
    """

    words: frozenset[str] = frozenset()
    counts: bool = False
    casesense: bool = False

    def holds(self, value: str) -> bool:
        read = value if self.casesense else value.lower()
        return read in self.words or (self.counts and read.isdecimal())


#: A flag's two words, which yt-dlp's documentation spells, `Either true or false`. An argument
#: read only for being there takes any value, and these are the two that say so.
_FLAG: Final = Vocabulary(frozenset({"true", "false"}))

#: `INNERTUBE_CLIENTS` at the pin, less the internal ones named with a leading `_`.
YOUTUBE_CLIENTS: Final = frozenset(
    {
        "android", "android_vr", "ios", "mweb", "tv", "tv_downgraded", "tv_simply", "visionos",
        "web", "web_creator", "web_embedded", "web_music", "web_safari",
    }
)  # fmt: skip

#: `YoutubeBaseInfoExtractor._SUPPORTED_LANG_CODES` at the pin, the codes `lang` accepts.
YOUTUBE_LANGUAGES: Final = frozenset(
    {
        "af", "am", "ar", "as", "az", "be", "bg", "bn", "bs", "ca", "cs", "da", "de", "el", "en",
        "en-GB", "en-IN", "es", "es-419", "es-US", "et", "eu", "fa", "fi", "fil", "fr", "fr-CA",
        "gl", "gu", "hi", "hr", "hu", "hy", "id", "is", "it", "iw", "ja", "ka", "kk", "km", "kn",
        "ko", "ky", "lo", "lt", "lv", "mk", "ml", "mn", "mr", "ms", "my", "ne", "nl", "no", "or",
        "pa", "pl", "pt", "pt-PT", "ro", "ru", "si", "sk", "sl", "sq", "sr", "sr-Latn", "sv", "sw",
        "ta", "te", "th", "tr", "uk", "ur", "uz", "vi", "zh-CN", "zh-HK", "zh-TW", "zu",
    }
)  # fmt: skip

#: Each argument whose values come from a fixed vocabulary, and the vocabulary (`DAT-003`, amended
#: 2026-10-19; `T255-R3`). **Only a value in it stays readable in the logs**; every other value is
#: registered for redaction, which is the safe direction: a value of `po_token`, `visitor_data`,
#: `hls_key`, `device_id` or `client_id` is a token, and a token typed where a client's name goes
#: is quoted back by yt-dlp's warning. **Each set is yt-dlp's own**: the class attribute the
#: extractor compares against where it has one, else the words its pinned documentation gives the
#: argument, which `tests/unit/test_extractor_args.py` checks one by one.
#: `soundcloud:comments_sort_by` is not here: its words come from the site at run time.
FIXED_VOCABULARY: Final[dict[tuple[str, str], Vocabulary]] = {
    ("afreecatvlive", "cdn"): Vocabulary(
        frozenset(
            {
                # `_WORKING_CDNS` and `_BAD_CDNS`.
                "aws_cf",
                "azure_cdn",
                "gcp_cdn",
                "gs_cdn",
                "gs_cdn_chromecast",
                "gs_cdn_mobile_web",
                "gs_cdn_pc_app",
                "gs_cdn_pc_web",
                "kt_cdn",
                "lg_cdn_chromecast",
                "lg_cdn_mobile_web",
                "lg_cdn_pc_web",
            }
        )
    ),
    # Read as `int(...)`, a format's quality number.
    ("bilibili", "prefer_multi_flv"): Vocabulary(counts=True),
    ("gamejolt", "comment_sort"): Vocabulary(frozenset({"hot", "you", "top", "new"})),
    ("generic", "is_live"): _FLAG,
    ("hotstar", "dr"): Vocabulary(frozenset({"sdr", "hdr10", "dv"})),
    ("hotstar", "res"): Vocabulary(frozenset({"sd", "hd", "fhd"})),
    ("hotstar", "vcodec"): Vocabulary(frozenset({"h264", "h265", "dvh265"})),
    # `_VALID_BITRATES`.
    ("jiosaavn", "bitrate"): Vocabulary(frozenset({"16", "32", "64", "128", "320"})),
    # `_REPLAY_TYPES`, and `all`.
    ("nflplusreplay", "type"): Vocabulary(
        frozenset({"all", "all_22", "condensed_game", "full_game", "full_game_spanish"})
    ),
    ("nhkradirulive", "area"): Vocabulary(
        frozenset(
            {"sapporo", "sendai", "tokyo", "nagoya", "osaka", "hiroshima", "matsuyama", "fukuoka"}
        )
    ),
    ("niconicochannelplus", "max_comments"): Vocabulary(counts=True),
    ("orfon", "prefer_segments_playlist"): _FLAG,
    # `_TABS`.
    ("rokfinchannel", "tab"): Vocabulary(
        frozenset({"new", "top", "videos", "podcasts", "streams", "stacks"})
    ),
    # `_SORT_ORDERS`.
    ("sonylivseries", "sort_order"): Vocabulary(frozenset({"asc", "desc"})),
    # A pattern over format names, open, so only its two words and `_DEFAULT_FORMATS`.
    ("soundcloud", "formats"): Vocabulary(
        frozenset(
            {"*", "default", "hls_aac", "hls_mp3", "hls_opus", "http_aac", "http_mp3", "http_opus"}
        )
    ),
    ("tver", "backend"): Vocabulary(frozenset({"streaks", "brightcove"})),
    ("twitter", "api"): Vocabulary(frozenset({"graphql", "legacy", "syndication"})),
    # `_CLIENT_CONFIGS`.
    ("vimeo", "client"): Vocabulary(frozenset({"android", "web"})),
    ("vimeo", "original_format_policy"): Vocabulary(frozenset({"always", "never", "auto"})),
    ("youtube", "comment_sort"): Vocabulary(frozenset({"top", "new"})),
    ("youtube", "fetch_pot"): Vocabulary(frozenset({"always", "never", "auto"})),
    ("youtube", "formats"): Vocabulary(
        frozenset({"dashy", "duplicate", "incomplete", "missing_pot"})
    ),
    ("youtube", "include_duplicate_formats"): _FLAG,
    ("youtube", "jsc_trace"): _FLAG,
    ("youtube", "lang"): Vocabulary(YOUTUBE_LANGUAGES, casesense=True),
    # Five counts, each a number or `all`.
    ("youtube", "max_comments"): Vocabulary(frozenset({"all"}), counts=True),
    # A client, `-` and a client to leave one out, `default` or `all`.
    ("youtube", "player_client"): Vocabulary(
        YOUTUBE_CLIENTS | {f"-{client}" for client in YOUTUBE_CLIENTS} | {"default", "all"}
    ),
    # `_PLAYER_JS_VARIANT_MAP`, and `actual`.
    ("youtube", "player_js_variant"): Vocabulary(
        frozenset(
            {
                "actual",
                "es5",
                "es6",
                "es6_tcc",
                "es6_tce",
                "house",
                "main",
                "phone",
                "tcc",
                "tce",
                "tv",
                "tv_es6",
            }
        )
    ),
    ("youtube", "player_skip"): Vocabulary(frozenset({"configs", "webpage", "js", "initial_data"})),
    ("youtube", "pot_trace"): _FLAG,
    ("youtube", "raise_incomplete_data"): _FLAG,
    ("youtube", "skip"): Vocabulary(frozenset({"hls", "dash", "translated_subs"})),
    ("youtube", "use_ad_playback_context"): _FLAG,
    # `_WEBPAGE_CLIENTS`.
    ("youtube", "webpage_client"): Vocabulary(frozenset({"web", "web_safari"})),
    ("youtube", "webpage_skip"): Vocabulary(frozenset({"player_response", "initial_data"})),
    ("youtube-ejs", "jitless"): _FLAG,
    ("youtubepot-webpo", "bind_to_visitor_id"): _FLAG,
    ("youtubetab", "approximate_date"): _FLAG,
    ("youtubetab", "skip"): Vocabulary(frozenset({"webpage", "authcheck"})),
    ("youtubewebarchive", "check_all"): Vocabulary(frozenset({"thumbnails", "captures"})),
    ("zan", "split_angles"): _FLAG,
}

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

    **Exactly what the editor can show back and read again**, tested as that: sorted, each pair
    once, every pair known and permitted, and each one read back from `as_text` unchanged. A value
    holding a `;`, any line break `str.splitlines` breaks on, or space at either end cannot be
    (`T255-R2`).

    **A refusal names nothing that is not on the allowlist** (`T255-R1`). It travels into the
    settings file's report, which is logged at startup before anything has registered the value,
    and a value, or a key or argument no extractor reads, can be a token typed in the wrong place.
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
            return "holds an item that is not (key, argument, values)"
        key, name, _values = item
        known = EXTRACTOR_ARGS.get(key)
        if known is None:
            return "names a key yt-dlp does not read extractor arguments under"
        if name not in known:
            return f"names an argument {key} does not read"
        if (key, name) in FORBIDDEN:
            return FORBIDDEN[key, name]
        if parsed(as_text((item,))) != ((item,), []):
            return f"{key}:{name} holds a value the editor cannot show back"
        seen.append((key, name))
    if seen != sorted(set(seen)):
        return "must name each pair once, in order"
    return None


def as_text(value: tuple[ExtractorArg, ...]) -> str:
    """One line per key, `KEY:ARG=VALUE,VALUE;ARG=VALUE`, as the editor shows them back.

    **A value ending in a backslash is parted from the next by a space** (`T255-R2`): written
    straight before the comma, the backslash escaped it, so `x=` and a backslash, then `y=2`, read
    back as one value. yt-dlp strips the space.
    """
    lines: dict[str, list[str]] = {}
    for key, name, values in value:
        written = [one.replace(",", r"\,") for one in values]
        joined = ",".join(
            f"{one} " if one.endswith("\\") and index < len(written) - 1 else one
            for index, one in enumerate(written)
        )
        lines.setdefault(key, []).append(f"{name}={joined}")
    return "\n".join(f"{key}:{';'.join(arguments)}" for key, arguments in lines.items())


def as_ytdlp(value: tuple[ExtractorArg, ...]) -> dict[str, dict[str, list[str]]]:
    """What yt-dlp's `extractor_args` option takes: key, then argument, then its values."""
    options: dict[str, dict[str, list[str]]] = {}
    for key, name, values in value:
        options.setdefault(key, {})[name] = list(values)
    return options


def _po_token(value: str) -> tuple[str, ...]:
    """`youtube:po_token`'s token as `_get_config_po_token` cleans it, the part after the `+`
    unquoted and through `base64` both ways, which drops what is not of its alphabet. yt-dlp puts
    it in a manifest's path, which a link's redaction keeps. A token it cannot clean, it warns
    about with the whole value, which is registered already, and uses no further."""
    _, plus, token = value.partition("+")
    if not plus:
        return ()
    try:
        cleaned = base64.urlsafe_b64encode(base64.urlsafe_b64decode(urllib.parse.unquote(token)))
    except binascii.Error, ValueError:
        return ()
    return (cleaned.decode(),)


#: The pieces yt-dlp cuts a value of these arguments into and can print alone (`T255-R3`, second
#: round), each transcribed from the pin and held to it by `tests/unit/test_extractor_args.py`.
#: `_parse_data_sync_id` splits at `||`; TikTok's `_get_next_app_info` at `/`, and writes the
#: pieces to a debug line as a `dict`.
_PIECES: Final[dict[tuple[str, str], Callable[[str], Iterable[str]]]] = {
    ("youtube", "po_token"): _po_token,
    ("youtube", "data_sync_id"): lambda value: value.partition("||")[::2],
    ("tiktok", "app_info"): lambda value: value.split("/"),
}


def _spellings(key: str, name: str, value: str) -> Iterator[str]:
    """Every spelling yt-dlp can print `value` in (`T255-R3`, second round).

    **As typed, and lower-cased**, which is how `_configuration_arg` hands it to an extractor
    unless the extractor asks for its case; **the pieces some arguments are cut into**
    (`_PIECES`); and each of those **as `repr` writes it**, less the quotes, since a debug line can
    print a `dict` or a list of them, where a backslash, a quote or an unprintable character is
    escaped. The registry replaces exact text only, so a spelling not registered is printed.
    """
    read = (value, value.lower())
    cut = _PIECES.get((key, name))
    forms = [*read, *(piece for one in read for piece in cut(one))] if cut else list(read)
    for form in forms:
        yield form
        yield repr(form)[1:-1]


def secret_values(value: tuple[ExtractorArg, ...]) -> tuple[str, ...]:
    """What to register for redaction: every spelling yt-dlp can print of each value not in its
    argument's vocabulary (`DAT-003`; `T255-R3`, where a whole argument's values were left
    readable, and then a value was printed lower-cased)."""
    return tuple(
        dict.fromkeys(
            form
            for key, name, values in value
            for one in values
            if one
            and not ((vocabulary := FIXED_VOCABULARY.get((key, name))) and vocabulary.holds(one))
            for form in _spellings(key, name, one)
            if form
        )
    )


#: The argument whose value makes yt-dlp hand a download to ffmpeg (`T255-R4`): Zan's multi-angle
#: split crops each angle and re-encodes it, and yt-dlp's documentation says it requires ffmpeg.
SPLIT_ANGLES: Final = ("zan", "split_angles")


def extractor_args_need_ffmpeg(value: tuple[ExtractorArg, ...]) -> bool:
    """Whether these arguments ask yt-dlp for work ffmpeg performs (`REQ-024`, `T255-R4`).

    **yt-dlp's own reading**: Zan splits the angles unless the first value, lower-cased as its
    `_configuration_arg` reads it, is `false`, so `true`, `yes` and an empty value all split.
    """
    return any(
        (key, name) == SPLIT_ANGLES and values[0].lower() != "false" for key, name, values in value
    )
