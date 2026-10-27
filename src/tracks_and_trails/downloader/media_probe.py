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

from tracks_and_trails.core.sections import NOT_THROUGH_SEVERAL_PROXIES, NOT_THROUGH_THE_PROXY

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
    """

    proxy: str
    source_address: str | None
    timeout: float

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
        return arguments


def route_for(
    proxy: str | None,
    source_address: str | None,
    timeout: float,
    system_proxies: Mapping[str, str],
) -> Route | str:
    """The route a link's length is read by, or why the request's cannot be followed (`T252-R5`).

    **The proxy yt-dlp would use.** `proxy` is the request's, and `None` means the system's, which
    yt-dlp reads with `urllib.request.getproxies` (`system_proxies`) for each link's scheme.
    **ffmpeg tunnels through an `http://` proxy only**: handed SOCKS or `https://`, it connected
    directly. So any other kind is refused, and so are system settings naming different proxies for
    different schemes, since a redirect from one to another would keep ffmpeg on the first. The
    system's exceptions are not followed: a link they name is read through the proxy, which can
    fail but never goes around it.
    """
    if proxy is None:
        named = {
            value for scheme in ("http", "https", "all") if (value := system_proxies.get(scheme))
        }
        if len(named) > 1:
            return NOT_THROUGH_SEVERAL_PROXIES
        proxy = next(iter(named), "")
    if proxy and urlsplit(proxy).scheme.lower() != "http":
        return NOT_THROUGH_THE_PROXY
    return Route(proxy=proxy, source_address=source_address, timeout=timeout)


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


def _headers(chosen: Mapping[str, Any], info: Mapping[str, Any], parser: Any) -> str:
    """The request's headers as ffmpeg's `-headers` takes them, its cookies among them."""
    headers = dict(chosen.get("http_headers") or info.get("http_headers") or {})
    cookie = _cookie_line(chosen.get("cookies") or info.get("cookies"), parser)
    if cookie:
        headers["Cookie"] = cookie
    return "".join(f"{name}: {value}\r\n" for name, value in headers.items())


def remote_length(
    info: Mapping[str, Any],
    ffprobe: Path,
    run: Run,
    cookie_parser: Any = None,
    *,
    route: Route,
) -> float | None:
    """The length of the media yt-dlp chose for `info`, read from its link (ruling 3).

    `info` is the probe's: yt-dlp merges the format it chose into it, or lists the formats it will
    merge in `requested_formats`, each with its link, headers and cookies. The first link that
    answers gives the length. **Only a format yt-dlp fetches as one file over `http` or `https` is
    asked**, by `route` (`T252-R5`). `None` when none answers.
    """
    for chosen in info.get("requested_formats") or [info]:
        if not isinstance(chosen, Mapping) or chosen.get("protocol") not in ONE_FILE_PROTOCOLS:
            continue
        url = chosen.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        arguments = [
            str(ffprobe),
            "-v",
            "error",
            *route.arguments(),
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
        ]
        headers = _headers(chosen, info, cookie_parser)
        if headers:
            arguments += ["-headers", headers]
        code, output = run([*arguments, url], REMOTE_TIMEOUT_SECONDS)
        seconds = _seconds(output) if code == 0 else None
        if seconds is not None:
            return seconds
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
