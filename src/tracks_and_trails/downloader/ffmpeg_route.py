"""ffmpeg's own downloads, kept to the route yt-dlp would take (`T-368`, `T252-R7`).

yt-dlp hands a download to ffmpeg (`FFmpegFD`) for every section, every live stream and a few
other formats. **At the pin it gives ffmpeg the proxy through the environment only, never the
address to connect from, and no certificate check.** Measured 2026-10-27 and again 2026-10-29: told
to connect from `127.0.0.2`, the cut connected from `127.0.0.1`; through a SOCKS proxy, directly.

`on_the_route` wraps the resolved copy's `FFmpegFD._call_downloader` for one session. Ruled
2026-10-29, as recommended: **carry the route where ffmpeg can follow it, and refuse where it
cannot**, before ffmpeg starts.

- **ffmpeg fetches only a link read as one file over `http` or `https`.** It fetches a manifest's
  pieces without the address to connect from or a certificate check, whatever it is given
  (measured 2026-10-27), so a manifest, and any other link, is refused. That covers a live stream
  and a section of anything that comes in pieces; the whole of a recorded one still downloads, by
  yt-dlp's own downloader. What yt-dlp feeds ffmpeg through its standard input is left alone.
- **Each input is given yt-dlp's route to it** (`media_probe.route_for`), with the certificate
  checked, and a demuxer that opens nothing else. A route ffmpeg cannot take refuses the download,
  and so does one needing an option the ffmpeg in use does not define (`T368-R5`). A plain
  `http://` link may use no TLS, since a redirect could take it to `https://` unchecked.
- **The headers sent are the ones yt-dlp would send**: its own instructions, `Ytdl-Request-Proxy`
  among them, are taken out, where the pin's `FFmpegFD` sent them on to the site, and an input
  left with none does not fall back to the item's (`T368-R1`).
- **ffmpeg's environment carries no proxy variable**: it reads `http_proxy` and `no_proxy`
  itself, and the pin's `FFmpegFD` copied `no_proxy` in beside the request's proxy, which yt-dlp
  does not follow.
"""

from __future__ import annotations

import contextlib
import importlib
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Final

from tracks_and_trails.downloader.media_probe import (
    ONE_FILE_PROTOCOLS,
    Route,
    RouteRefusedError,
    defined_options,
    defines_every,
    route_for,
    run_with,
    without_proxies,
)

#: Why ffmpeg was not started for an item that comes in pieces, or from a link not on the web.
NOT_ONE_WEB_FILE: Final = (
    "Nothing was downloaded: ffmpeg would fetch this item in a way that cannot check the site's "
    "certificate or keep to this computer's network settings. If you asked for part of it, "
    "downloading the whole item may work."
)

#: Why ffmpeg was not started where yt-dlp's route to a link is a proxy ffmpeg goes around.
NOT_THROUGH_THE_PROXY: Final = (
    "Nothing was downloaded: ffmpeg would fetch this item, and it can only go through an http:// "
    "proxy. If you asked for part of it, downloading the whole item may work."
)

#: Why ffmpeg was not started where the build in use does not define an option the route needs,
#: such as stopping at a redirect, which came in FFmpeg 8.1, or the address to connect from.
NOT_WITH_THIS_FFMPEG: Final = (
    "Nothing was downloaded: the ffmpeg in use cannot fetch this item while keeping to this "
    "computer's network settings. A newer ffmpeg may work. If you asked for part of it, "
    "downloading the whole item may work."
)

#: The protocols a plain `http://` input may use. With no TLS among them, a redirect to an
#: `https://` link fails rather than being fetched with no certificate check, which ffmpeg cannot
#: be given for such an input (measured 2026-10-30 on FFmpeg 5.1.9, 6.1.1 and 8.1.3).
PLAIN_LINK_PROTOCOLS: Final = "http,tcp"


def for_the_session(
    ytdlp: Any, proxies: Mapping[str, str], source_address: str | None, timeout: float | None
) -> contextlib.AbstractContextManager[None]:
    """`on_the_route` for the resolved copy `ytdlp`, as the worker installs it around a session.

    `timeout` is the request's, or `None` for that copy's own default. A copy without `FFmpegFD`
    hands ffmpeg nothing, so nothing is wrapped; one with it but without yt-dlp's route functions
    has no route to keep to, and every download ffmpeg would make is refused.
    """
    try:
        external = importlib.import_module(f"{ytdlp.__name__}.downloader.external")
    except ImportError:
        return contextlib.nullcontext()
    if getattr(external, "FFmpegFD", None) is None:
        return contextlib.nullcontext()
    try:
        networking = importlib.import_module(f"{ytdlp.__name__}.utils.networking")
        default = importlib.import_module(f"{ytdlp.__name__}.networking.common").DEFAULT_TIMEOUT
    except ImportError, AttributeError:
        networking, default = None, 0.0
    waits = float(default) if timeout is None else timeout
    return on_the_route(external, networking, proxies, source_address, waits)


@contextlib.contextmanager
def on_the_route(
    external: Any,
    networking: Any,
    proxies: Mapping[str, str],
    source_address: str | None,
    timeout: float,
) -> Iterator[None]:
    """Keep every download yt-dlp gives ffmpeg on yt-dlp's route, for the length of the block.

    `external` is the resolved copy's `yt_dlp.downloader.external` and `networking` its
    `yt_dlp.utils.networking`, or `None` where it has none; `proxies` is the table yt-dlp chooses
    from (`proxy_table`).
    `RouteRefusedError` leaves yt-dlp with the reason when ffmpeg cannot be kept to the route.
    """
    ffmpeg = external.FFmpegFD
    call = ffmpeg._call_downloader
    popen = external.Popen
    # The options each build defines, asked once a session (`T368-R5`).
    known: dict[str, frozenset[str]] = {}

    def defined_for(downloader: Any) -> Callable[[], frozenset[str]]:
        """The options of the ffmpeg `downloader` runs, found as the pin's method finds it, and
        none where there is none."""

        def defined() -> frozenset[str]:
            found = external.FFmpegPostProcessor(downloader=downloader)
            binary = found.executable if found.available else None
            if not binary:
                return frozenset()
            if binary not in known:
                known[binary] = defined_options(binary, run_with(popen))
            return known[binary]

        return defined

    class WithoutProxies(popen):  # type: ignore[misc,valid-type]
        """yt-dlp's `Popen`, with no proxy variable in the child's environment."""

        def __init__(self, *arguments: Any, env: Mapping[str, str] | None = None, **options: Any):
            super().__init__(*arguments, env=without_proxies(env), **options)

    def routed(self: Any, tmpfilename: str, info_dict: dict[str, Any]) -> Any:
        try:
            held = _routed(
                info_dict, networking, proxies, source_address, timeout, defined_for(self)
            )
        except RouteRefusedError:
            # **A format test** (`--check-formats`) catches only yt-dlp's own errors, so a refusal
            # there is ffmpeg failing, which marks the format as not working; elsewhere it ends
            # the item with the reason.
            if self.params.get("test"):
                return 1
            raise
        external.Popen = WithoutProxies
        try:
            return call(self, tmpfilename, held)
        finally:
            external.Popen = popen

    ffmpeg._call_downloader = routed
    try:
        yield
    finally:
        ffmpeg._call_downloader = call


def _for_ffmpeg(route: Route, url: str) -> list[str]:
    """`route`'s options as ffmpeg takes them for `url`.

    **ffmpeg refuses an input option nothing uses**, where ffprobe only warns (measured
    2026-10-29, `Option tls_verify not found`, exit 8), and a plain `http://` link opens no TLS. So
    it is not given the certificate check, and may use no TLS (`PLAIN_LINK_PROTOCOLS`). It once
    followed no redirect instead, which needs `-max_redirects`, and a build before FFmpeg 8.1
    defines none (`T368-R5`).
    """
    arguments = route.arguments()
    if url.startswith("https://"):
        return arguments
    at = arguments.index("-tls_verify")
    del arguments[at : at + 2]
    arguments[arguments.index("-protocol_whitelist") + 1] = PLAIN_LINK_PROTOCOLS
    return arguments


def _routed(
    info_dict: dict[str, Any],
    networking: Any,
    proxies: Mapping[str, str],
    source_address: str | None,
    timeout: float,
    defined: Callable[[], frozenset[str]],
) -> dict[str, Any]:
    """`info_dict` with each of ffmpeg's inputs on yt-dlp's route to it, or `RouteRefusedError`.

    **Each input as `FFmpegFD` reads it**: a merged item's are its `requested_formats`, and an
    input's options are its own `ffmpeg_args` or else the item's, and its headers its own or else
    the item's. The route's options go after the given ones, so an option of the same name given
    earlier cannot undo the route. `defined` is what the ffmpeg in use defines, asked only once
    an input has a route.
    """
    merged = info_dict.get("requested_formats")
    given = (info_dict.get("downloader_options") or {}).get("ffmpeg_args") or []
    kept = []
    for chosen in merged or [info_dict]:
        url = chosen.get("url")
        if url in ("-", "pipe:"):
            # Fed to ffmpeg's standard input by a downloader of yt-dlp's own, the websocket's:
            # ffmpeg itself connects to nothing.
            kept.append(chosen)
            continue
        if (
            networking is None
            or chosen.get("protocol") not in ONE_FILE_PROTOCOLS
            or not isinstance(url, str)
            or not url.startswith(("http://", "https://"))
        ):
            raise RouteRefusedError(NOT_ONE_WEB_FILE)
        way = route_for(
            url,
            chosen.get("http_headers") or info_dict.get("http_headers") or {},
            proxies,
            networking,
            source_address,
            timeout,
        )
        if isinstance(way, str):
            raise RouteRefusedError(NOT_THROUGH_THE_PROXY)
        route, sent = way
        arguments = _for_ffmpeg(route, url)
        if not defines_every(arguments, defined()):
            raise RouteRefusedError(NOT_WITH_THIS_FFMPEG)
        options = dict(chosen.get("downloader_options") or {})
        options["ffmpeg_args"] = [*(options.get("ffmpeg_args") or given), *arguments]
        kept.append({**chosen, "http_headers": dict(sent), "downloader_options": options})
    # **The item's own headers go to no input** (`T368-R1`): each carries the ones yt-dlp sends
    # it, and `FFmpegFD` takes the item's for one whose own are empty, which would send on the
    # instructions just taken out of them.
    return {**info_dict, "http_headers": {}, "requested_formats": kept} if merged else kept[0]
