"""What ffprobe says about a section, before it is cut and after (`T252-R1`).

yt-dlp hands each section to ffmpeg and reports success whatever ffmpeg writes. `T252-R1` measured
three silent wrong results on a six-second clip: a cut of **262 bytes and no streams** from a
server that cannot seek, and the **whole item** for `*99-100` and for `*-2-inf` on a direct link,
which reports no length, so yt-dlp could neither place the range nor resolve its end. The
maintainer's rulings of 2026-10-25 (`ARC-010` amended) answer each with ffprobe:

- **Where the site gives no length, it is read from the link** (`remote_length`), with the
  request's own headers and cookies, before anything downloads.
- **Every section is read before it is claimed** (`holds_media`), and one with no picture or sound
  fails the attempt.

**The ffprobe is the one beside the ffmpeg in use** (`ffprobe_beside`), which is where yt-dlp's
own postprocessors look for it, so this reads media with the same build that wrote it.

**Run as yt-dlp runs ffmpeg**, through its `Popen`, which hides the console on Windows and kills
the process when it outlives its timeout. The worker passes that class in, and the cookie parser
with it, because yt-dlp's names are resolved at run time rather than imported (`ARCHITECTURE.md`
§6). **Nothing ffprobe prints is logged**: its errors can quote the link, and a link can carry a
token.

**A link is read by the connection yt-dlp would make, or not at all** (`T252-R5`, `T253-R3`).
ffprobe left to itself connected directly while the request named a proxy or an address to connect
from, and checked no certificate while sending the site's cookies, which `SEC-004` forbids yt-dlp
to do. Each part is now passed to it (`Route`), and where ffmpeg cannot carry one the length is not
read and the item is cancelled with the reason.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from tracks_and_trails.core.sections import NOT_THROUGH_THE_PROXY

#: How long ffprobe is given to read a link's length. A link to a file with its index at the end,
#: on a server that cannot seek, is read through to the index, so this is a ceiling on that.
REMOTE_TIMEOUT_SECONDS: Final = 60

#: How long ffprobe is given to read a section already on disk.
LOCAL_TIMEOUT_SECONDS: Final = 30

#: One run of ffprobe: its arguments and timeout in, its exit code and standard output back. `-1`
#: and nothing when it could not be run or did not finish.
Run = Callable[[Sequence[str], float], tuple[int, str]]

#: The demuxers a link's length is read with (`T252-R5`). Each reads the one file and opens nothing
#: else. HLS's and DASH's fetch their pieces without the address to connect from or a certificate
#: check, whatever ffprobe is given (measured 2026-10-27, ffmpeg 8.1.3), so a manifest is not read.
ONE_FILE_DEMUXERS: Final = "mov,matroska,flv,mp3,aac,ogg,wav,flac,mpegts,avi,asf"

#: The protocols a read of one link uses; `httpproxy` is how ffmpeg reaches an `https` link through
#: a proxy. A redirect to any other is refused.
LINK_PROTOCOLS: Final = "http,https,tls,tcp,httpproxy"

#: yt-dlp's names for a format fetched as one file, the only kind whose length is read.
ONE_FILE_PROTOCOLS: Final = frozenset({"http", "https"})


@dataclass(frozen=True, slots=True)
class Route:
    """The connection yt-dlp would make for a link, as ffprobe's arguments (`T252-R5`).

    **Every part is passed, none left to ffmpeg's defaults**, each measured on 2026-10-27:

    - `proxy`, `""` for none: ffmpeg otherwise takes `http_proxy` from its environment, which is
      not how yt-dlp chooses (`route_for`), so the variables are also kept from it (`run_with`).
    - `source_address`, as `-local_addr`: an address of the other family fails the connection
      rather than making it another way, as yt-dlp's does (`T253-R3`).
    - `timeout`, the socket timeout yt-dlp would wait, where ffmpeg waits for ever.
    - certificates checked, chain and host name, where ffmpeg checks neither by default.
    - `follows_redirects`, `False` where the next link could be reached another way: yt-dlp
      chooses the route again for each link it is sent to, and ffmpeg keeps one for all of them
      (`route_for`). `-max_redirects 0` stops ffprobe at the redirect, which gives no length.
    """

    proxy: str
    source_address: str | None
    timeout: float
    follows_redirects: bool = True

    def arguments(self) -> list[str]:
        arguments = [
            "-http_proxy",
            self.proxy,
            "-tls_verify",
            "1",
            "-timeout",
            str(round(self.timeout * 1_000_000)),
            "-protocol_whitelist",
            LINK_PROTOCOLS,
            "-format_whitelist",
            ONE_FILE_DEMUXERS,
        ]
        if self.source_address is not None:
            arguments += ["-local_addr", self.source_address]
        if not self.follows_redirects:
            arguments += ["-max_redirects", "0"]
        return arguments


#: The route to one link, from the link and the headers yt-dlp would send it: the route and the
#: headers sent along it, or why ffprobe cannot take it (`route_for`).
RouteTo = Callable[[str, Mapping[str, str]], "tuple[Route, Mapping[str, str]] | str"]


class RouteRefusedError(Exception):
    """No link was asked, since ffprobe could take yt-dlp's route to none; `reason` says why."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def proxy_table(proxy: str | None, system: Mapping[str, str]) -> dict[str, str]:
    """The proxies yt-dlp chooses from, as `YoutubeDL.proxies` builds them at the pin.

    The request's own for every kind of link, or else the system's as `urllib.request.getproxies`
    reads them (`system`), where an `https` link takes the `http` one if the system names none for
    it. The adapter hands yt-dlp a request's proxy only when it is not empty, so neither is this.
    """
    if proxy:
        return {"all": proxy}
    table = dict(system)
    if "http" in table and "https" not in table:
        table["https"] = table["http"]
    return table


def route_for(
    url: str,
    headers: Mapping[str, str],
    proxies: Mapping[str, str],
    networking: Any,
    source_address: str | None,
    timeout: float,
) -> tuple[Route, Mapping[str, str]] | str:
    """yt-dlp's route to `url` and the headers it sends there, or why ffprobe cannot take it.

    **Chosen by yt-dlp's own functions, as its handlers choose for each request** (`T252-R5`,
    second round), `networking` being the resolved copy's `yt_dlp.utils.networking`.
    `clean_proxies` lets a `Ytdl-Request-Proxy` header stand for every proxy and takes it out of
    the headers, gives a proxy written without a scheme `http://`, and reads `__noproxy__` as none;
    `clean_headers` takes yt-dlp's other instructions out of what is sent; `select_proxy` then
    picks this link's proxy by its scheme, unless the system's exceptions (`no_proxy`) name its
    host. `proxies` is the table yt-dlp starts from (`proxy_table`).

    **A redirect is followed only where it cannot change the route.** yt-dlp chooses again for
    each link it is sent to, and ffmpeg keeps its one proxy for all of them, so where the table
    has exceptions, or a different proxy for `http` and `https`, ffprobe follows none.

    **ffmpeg tunnels through an `http://` proxy only**: handed SOCKS or `https://`, it connected
    directly (measured 2026-10-27), so any other is refused.
    """
    sent = networking.HTTPHeaderDict(headers)
    table = dict(proxies)
    networking.clean_proxies(table, sent)
    networking.clean_headers(sent)
    proxy = networking.select_proxy(url, table) or ""
    if proxy and urlsplit(proxy).scheme.lower() != "http":
        return NOT_THROUGH_THE_PROXY
    same_for_every_link = "no" not in table and networking.select_proxy(
        "http://any.invalid/", table
    ) == networking.select_proxy("https://any.invalid/", table)
    route = Route(proxy, source_address, timeout, follows_redirects=same_for_every_link)
    return route, sent.sensitive()


def _without_proxies() -> dict[str, str]:
    """This process's environment without its proxy variables, which ffmpeg would read (`Route`)."""
    return {
        name: value for name, value in os.environ.items() if not name.lower().endswith("_proxy")
    }


def ffprobe_beside(ffmpeg: Path) -> Path | None:
    """The ffprobe in ffmpeg's own directory, if it is there and can be run.

    yt-dlp's `FFmpegPostProcessor` looks for it exactly there when it is given ffmpeg's location,
    with ffmpeg's extension, so `ffmpeg.exe` has `ffprobe.exe` beside it.
    """
    candidate = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
    found = shutil.which(str(candidate)) if candidate.is_file() else None
    return Path(found) if found else None


def run_with(popen: Any) -> Run:
    """A `Run` through yt-dlp's `Popen.run`, or `subprocess.run` where the copy has none."""

    def run(arguments: Sequence[str], timeout: float) -> tuple[int, str]:
        try:
            if popen is not None and callable(getattr(popen, "run", None)):
                stdout, _stderr, code = popen.run(
                    list(arguments),
                    timeout=timeout,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=_without_proxies(),
                )
                return int(code), str(stdout or "")
            done = subprocess.run(  # noqa: S603 - a fixed program and arguments, no shell
                list(arguments),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                env=_without_proxies(),
            )
            return done.returncode, done.stdout or ""
        except OSError, subprocess.SubprocessError, ValueError:
            return -1, ""

    return run


def _seconds(text: object) -> float | None:
    """A positive, finite number of seconds as ffprobe prints one, or `None` (`N/A` included)."""
    try:
        seconds = float(str(text).strip())
    except ValueError, OverflowError:
        return None
    return seconds if math.isfinite(seconds) and seconds > 0 else None


def _cookie_line(cookies: object, parser: Any) -> str | None:
    """The `Cookie` header for a format's `cookies` field, which yt-dlp writes as `Set-Cookie`.

    `name=value; Domain=…; Path=…`, one cookie after another, so it is read with yt-dlp's own
    lenient parser and only the names and values go back on the wire, as yt-dlp's ffmpeg
    downloader sends them.
    """
    if not isinstance(cookies, str) or not cookies or parser is None:
        return None
    try:
        jar = parser(cookies)
        pairs = [f"{morsel.key}={morsel.coded_value}" for morsel in jar.values()]
    except Exception:  # an unreadable field is no cookies, never a failed download
        return None
    return "; ".join(pairs) or None


def _headers(sent: Mapping[str, str], cookies: Any, parser: Any) -> str:
    """The headers yt-dlp sends, as ffmpeg's `-headers` takes them, with the cookies among them."""
    headers = dict(sent)
    cookie = _cookie_line(cookies, parser)
    if cookie:
        headers["Cookie"] = cookie
    return "".join(f"{name}: {value}\r\n" for name, value in headers.items())


def remote_length(
    info: Mapping[str, Any],
    ffprobe: Path,
    run: Run,
    cookie_parser: Any = None,
    *,
    route: RouteTo,
) -> float | None:
    """The length of the media yt-dlp chose for `info`, read from its link (ruling 3).

    `info` is the probe's: yt-dlp merges the format it chose into it, or lists the formats it will
    merge in `requested_formats`, each with its link, headers and cookies. The first link that
    answers gives the length. **Only a format yt-dlp fetches as one file over `http` or `https` is
    asked**, each by yt-dlp's route to it, `route` (`T252-R5`). `None` when none answers;
    `RouteRefusedError` when there was a link to ask and no route ffprobe could take to any.
    """
    refused: str | None = None
    for chosen in info.get("requested_formats") or [info]:
        if not isinstance(chosen, Mapping) or chosen.get("protocol") not in ONE_FILE_PROTOCOLS:
            continue
        url = chosen.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        routed = route(url, chosen.get("http_headers") or info.get("http_headers") or {})
        if isinstance(routed, str):
            refused = routed
            continue
        link_route, sent = routed
        arguments = [
            str(ffprobe),
            "-v",
            "error",
            *link_route.arguments(),
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
        ]
        headers = _headers(sent, chosen.get("cookies") or info.get("cookies"), cookie_parser)
        if headers:
            arguments += ["-headers", headers]
        code, output = run([*arguments, url], REMOTE_TIMEOUT_SECONDS)
        seconds = _seconds(output) if code == 0 else None
        if seconds is not None:
            return seconds
    if refused is not None:
        raise RouteRefusedError(refused)
    return None


def holds_media(path: Path, ffprobe: Path, run: Run) -> bool:
    """Whether the file at `path` has a picture or a sound, as ffprobe reads it (ruling 2).

    **A stream of either kind, and no length of zero**: the cut from a server that could not seek
    was a valid MP4 with no streams at all. A length ffprobe does not report is not held against
    the file, since some containers carry none; one it reports as zero or unreadable is.
    """
    code, output = run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type:format=duration",
            "-of",
            "json",
            str(path),
        ],
        LOCAL_TIMEOUT_SECONDS,
    )
    if code != 0:
        return False
    try:
        read = json.loads(output)
    except ValueError:
        return False
    if not isinstance(read, Mapping):
        return False
    kinds = {
        stream.get("codec_type")
        for stream in read.get("streams") or ()
        if isinstance(stream, Mapping)
    }
    if not kinds & {"video", "audio"}:
        return False
    container = read.get("format") or {}
    reported = container.get("duration") if isinstance(container, Mapping) else None
    return reported is None or _seconds(reported) is not None
