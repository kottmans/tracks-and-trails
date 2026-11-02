"""A section's length is read from its link by yt-dlp's route to it, or not at all (`T252-R5`).

**Real ffprobe, through the worker's own placement**, against servers on loopback, the exception
`docs/project/TESTING.md` grants the localhost suites. Measured on 2026-10-27 by the review and
again here: ffprobe left to itself read the length directly while the request named a proxy, and
from any address while it named one to connect from (`T253-R3`), and checked no certificate. The
second round (2026-10-28): the read sent a link to a system proxy yt-dlp goes around for it.

**The origin tells a direct read from one through the proxy** because the proxy here connects out
from `127.0.0.3`; an address to connect from is told the same way, by `127.0.0.2`. Each case has
a control showing the instrument sees what the read is checked against, most of them yt-dlp itself
reaching the same server the way the read must.
"""

from __future__ import annotations

import functools
import ssl
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import truststore
import yt_dlp
from yt_dlp.cookies import LenientSimpleCookie
from yt_dlp.networking.exceptions import HTTPError, TransportError
from yt_dlp.utils import Popen

from tests.capabilities import resolve_ffmpeg
from tests.integration.loopback import (
    BOUND,
    HOSTS_COOKIE,
    ISSUED_COOKIE,
    PROXY_SIDE,
    SERVER_CONTEXT,
    Origin,
    Proxy,
    Redirect,
    clear_ambient_proxies,
    cookie_file,
    defined_by,
    make_certificate,
    make_site,
    needs_loopback_addresses,
    origin_on,
    proxy_on,
    redirect_on,
    serve,
)
from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.core.sections import (
    NO_LENGTH,
    NOT_KEEPING_THE_COOKIES,
    NOT_THROUGH_THE_PROXY,
    NOT_WITH_THIS_FFPROBE,
)
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.media_probe import (
    PROTOCOL_OPTIONS,
    Route,
    defined_options,
    run_with,
)
from tracks_and_trails.downloader.tls import verify_with_the_operating_system


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_site(tmp_path_factory)


@pytest.fixture
def origin(site: Path) -> Iterator[tuple[str, type[Origin]]]:
    yield from origin_on(site, "127.0.0.1")


@pytest.fixture
def redirect(site: Path) -> Iterator[tuple[str, type[Redirect], type[Origin]]]:
    yield from redirect_on(site)


@pytest.fixture
def proxy() -> Iterator[tuple[str, type[Proxy]]]:
    yield from proxy_on()


@pytest.fixture(autouse=True)
def no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_ambient_proxies(monkeypatch)


def _placed(
    url: str, headers: dict[str, str] | None = None, cookies: str | None = None, **fields: Any
) -> float | None:
    """`_place_the_sections` on a link that gives no length, with the real ffprobe and yt-dlp's
    own route functions; `cookies` is the format's field (`_cookies_for`)."""
    request = DownloadRequest(
        url=url,
        output_directory="/unused",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        download_sections=("*-2-inf",),
        **fields,
    )
    _, ffprobe = resolve_ffmpeg()
    info: dict[str, Any] = {"url": url, "protocol": urlsplit(url).scheme}
    if headers is not None:
        info["http_headers"] = headers
    if cookies is not None:
        info["cookies"] = cookies
    return worker._place_the_sections(
        request,
        info,
        Path(ffprobe),
        run_with(Popen),
        LenientSimpleCookie,
        20.0,
        yt_dlp.utils.networking,
    )


def _lacks(option: str) -> bool:
    """Whether the ffprobe in use does not define `option` (`T368-R5`), so a read needing it is
    cancelled with `NOT_WITH_THIS_FFPROBE` before any link is asked."""
    return option not in defined_by(resolve_ffmpeg()[1])


def _placed_unless_lacking(
    option: str, url: str, reason: str = NOT_WITH_THIS_FFPROBE, **given: Any
) -> float | None:
    """`_placed`, or, where the ffprobe in use lacks `option`, `None` once the item is cancelled
    with `reason`, which is what this build does instead."""
    if not _lacks(option):
        return _placed(url, **given)
    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, **given)
    assert cancelled.value.reason == reason
    return None


def _cookies_for(url: str, jar: Path) -> str:
    """The `cookies` field yt-dlp gives a format at `url` from the cookie file `jar`, which is how
    the probe hands the worker a link's cookies (`T252-R9`)."""
    fields: dict[str, Any] = {"url": url}
    with yt_dlp.YoutubeDL({"cookiefile": str(jar), "quiet": True}) as ydl:
        ydl._calc_headers(fields)
    return str(fields["cookies"])


def _cookie_sent(heard: list[dict[str, str]]) -> list[str | None]:
    """The `Cookie` header of each request a server heard, `None` where it had none."""
    return [request.get("cookie") for request in heard]


@needs_loopback_addresses
def test_the_length_is_read_through_the_request_s_proxy(
    origin: tuple[str, type[Origin]], proxy: tuple[str, type[Proxy]]
) -> None:
    """**The review's case, `T252-R5`**: the same proxy on the request that yt-dlp goes through.
    The read had gone around it, reaching the origin directly with no request to the proxy."""
    url, served = origin
    address, forwarded = proxy
    with yt_dlp.YoutubeDL({"proxy": address, "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert forwarded.asked and served.callers == [PROXY_SIDE], "the control did not go through"
    forwarded.asked.clear()
    served.callers.clear()

    assert _placed(url, proxy=address) == pytest.approx(6, abs=0.1)

    assert forwarded.asked, "the proxy was not asked"
    assert set(served.callers) == {PROXY_SIDE}, f"the origin was reached directly: {served.callers}"


@needs_loopback_addresses
def test_a_link_the_system_exempts_is_read_directly(
    origin: tuple[str, type[Origin]],
    proxy: tuple[str, type[Proxy]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The review's case, second round**: with `http_proxy` set and `no_proxy` naming the origin,
    yt-dlp reaches it directly, and the read had sent the link and its headers to the proxy."""
    url, served = origin
    address, forwarded = proxy
    monkeypatch.setenv("http_proxy", address)
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == ["127.0.0.1"], "the control did not go around the proxy"
    assert forwarded.asked == [], "the control asked the proxy"
    served.callers.clear()

    # A proxy and exceptions to it: the route passes `-max_redirects` (`T368-R5`).
    length = _placed_unless_lacking("max_redirects", url)

    assert forwarded.asked == [], "the read went to a proxy yt-dlp goes around for this link"
    if length is None:
        assert served.callers == [], "this ffprobe cannot keep to the route, and was started"
    else:
        assert length == pytest.approx(6, abs=0.1)
        assert served.callers and set(served.callers) == {"127.0.0.1"}, served.callers


@needs_loopback_addresses
def test_an_http_link_is_read_directly_where_the_system_proxies_only_https(
    origin: tuple[str, type[Origin]],
    proxy: tuple[str, type[Proxy]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The review's case, second round**: `https_proxy` alone leaves yt-dlp's `http://` links
    direct, and the read had sent this one to that proxy."""
    url, served = origin
    address, forwarded = proxy
    monkeypatch.setenv("https_proxy", address)
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == ["127.0.0.1"] and forwarded.asked == [], "the control was proxied"
    served.callers.clear()

    # A different proxy for each kind of link: the route passes `-max_redirects` (`T368-R5`).
    length = _placed_unless_lacking("max_redirects", url)

    assert forwarded.asked == [], "the read went to a proxy yt-dlp does not use for this link"
    if length is None:
        assert served.callers == [], "this ffprobe cannot keep to the route, and was started"
    else:
        assert length == pytest.approx(6, abs=0.1)
        assert served.callers and set(served.callers) == {"127.0.0.1"}, served.callers


@needs_loopback_addresses
def test_a_redirect_is_not_followed_where_it_could_change_the_route(
    redirect: tuple[str, type[Redirect], type[Origin]],
    proxy: tuple[str, type[Proxy]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """yt-dlp chooses the route again for each link it is sent to, and ffmpeg keeps one for all.
    With `no_proxy` naming only the first host, yt-dlp reaches it directly and the second through
    the proxy; the read follows no redirect, and gives no length.

    The control has two halves: yt-dlp changes route at the redirect, and the read's direct route
    followed on its own reaches the second host directly, which yt-dlp would not."""
    url, sent_on, served = redirect
    address, forwarded = proxy
    monkeypatch.setenv("http_proxy", address)
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert sent_on.callers == ["127.0.0.1"], "the control was proxied to the first host"
    assert served.callers == [PROXY_SIDE], "the control did not take the proxy to the second"
    served.callers.clear()
    _, ffprobe = resolve_ffmpeg()
    code, _ = run_with(Popen)([ffprobe, "-v", "error", *Route("", None, 20.0).arguments(), url], 30)
    assert code == 0 and served.callers == ["127.0.0.1"], "the direct route did not follow it"
    sent_on.callers.clear()
    served.callers.clear()
    forwarded.asked.clear()

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url)

    if _lacks("max_redirects"):
        # A build before FFmpeg 8.1 cannot be stopped at the redirect, so it asks nothing.
        assert cancelled.value.reason == NOT_WITH_THIS_FFPROBE
        assert sent_on.callers == [], "this ffprobe cannot stop at a redirect, and was started"
    else:
        assert cancelled.value.reason == NO_LENGTH
        assert sent_on.callers == ["127.0.0.1"], "the first link was not read as yt-dlp reads it"
    assert served.callers == [], "the redirect was followed by a route yt-dlp would not take"
    assert forwarded.asked == []


@needs_loopback_addresses
def test_a_redirect_is_followed_where_exceptions_have_no_proxy_to_go_around(
    redirect: tuple[str, type[Redirect], type[Origin]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`no_proxy` with no proxy leaves every link direct, so a redirect cannot change the route
    and is followed, by any build, with no `-max_redirects` to need (`T368-R5`)."""
    url, sent_on, served = redirect
    monkeypatch.setenv("no_proxy", "127.0.0.1")

    assert _placed(url) == pytest.approx(6, abs=0.1)

    assert sent_on.callers and set(sent_on.callers) == {"127.0.0.1"}, sent_on.callers
    assert served.callers and set(served.callers) == {"127.0.0.1"}, served.callers


@needs_loopback_addresses
def test_a_redirect_is_followed_where_every_link_goes_the_same_way(
    redirect: tuple[str, type[Redirect], type[Origin]], proxy: tuple[str, type[Proxy]]
) -> None:
    """The request's own proxy is yt-dlp's for every link, so a redirect cannot change the route:
    the read follows it, and both hosts see only the proxy."""
    url, sent_on, served = redirect
    address, forwarded = proxy

    assert _placed(url, proxy=address) == pytest.approx(6, abs=0.1)

    assert len(forwarded.asked) >= 2, forwarded.asked
    assert set(sent_on.callers) == {PROXY_SIDE}, sent_on.callers
    assert served.callers and set(served.callers) == {PROXY_SIDE}, served.callers


@needs_loopback_addresses
def test_a_cookie_goes_to_its_link_and_not_on_through_a_redirect(
    redirect: tuple[str, type[Redirect], type[Origin]], tmp_path: Path
) -> None:
    """**The review's case, `T252-R9`**: a cookie for `127.0.0.1`, whose link there sends the read
    on to `127.0.0.5`. yt-dlp sends it to the first host alone, and the read sent it to both. A
    link read with a cookie now follows no redirect, and gives no length.

    The control has two halves: yt-dlp keeps the cookie to the first host, and ffprobe given it as
    a header sends it on to the second."""
    url, sent_on, served = redirect
    jar = cookie_file(tmp_path, f"127.0.0.1 FALSE / FALSE {HOSTS_COOKIE}")
    with yt_dlp.YoutubeDL({"cookiefile": str(jar), "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert _cookie_sent(sent_on.heard) == [HOSTS_COOKIE], "the control: not sent to the first"
    assert served.heard and _cookie_sent(served.heard) == [None] * len(served.heard), "sent on"
    served.heard.clear()
    _, ffprobe = resolve_ffmpeg()
    header = ["-headers", f"Cookie: {HOSTS_COOKIE}\r\n"]
    direct = Route("", None, 20.0).arguments()
    code, _ = run_with(Popen)([ffprobe, "-v", "error", *direct, *header, url], 30)
    assert code == 0 and served.heard, "the control: ffprobe did not follow the redirect"
    assert set(_cookie_sent(served.heard)) == {HOSTS_COOKIE}, "the control: ffprobe kept it"
    sent_on.heard.clear()
    served.heard.clear()

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, cookies=_cookies_for(url, jar))

    if _lacks("max_redirects"):
        # A build without `max_redirects` cannot be stopped at the redirect, so it asks nothing.
        assert cancelled.value.reason == NOT_KEEPING_THE_COOKIES
        assert sent_on.heard == [], "this ffprobe cannot stop at a redirect, and was started"
    else:
        assert cancelled.value.reason == NO_LENGTH
        assert _cookie_sent(sent_on.heard) == [HOSTS_COOKIE], "the first host was not sent it"
    assert served.heard == [], "the read was sent on with the cookie"


def test_a_site_that_needs_its_cookie_is_sent_it_and_the_length_is_read(
    site: Path, tmp_path: Path
) -> None:
    """**`T252-R9`, the cookie's own host**: a site that serves only a request carrying its
    cookie. The control: without it, the site refuses yt-dlp."""
    for url, served in origin_on(site, "127.0.0.1", needs=HOSTS_COOKIE):
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl, pytest.raises(HTTPError):
            ydl.urlopen(url)
        served.heard.clear()
        jar = cookie_file(tmp_path, f"127.0.0.1 FALSE / FALSE {HOSTS_COOKIE}")

        length = _placed_unless_lacking(
            "max_redirects", url, NOT_KEEPING_THE_COOKIES, cookies=_cookies_for(url, jar)
        )

        if length is None:
            assert served.heard == [], "this ffprobe cannot stop at a redirect, and was started"
        else:
            assert length == pytest.approx(6, abs=0.1)
            assert served.heard and set(_cookie_sent(served.heard)) == {HOSTS_COOKIE}


def test_a_link_is_sent_exactly_the_cookies_yt_dlp_sends_it(
    origin: tuple[str, type[Origin]], tmp_path: Path
) -> None:
    """**`T252-R9`'s scope**: cookies for this host, for a path on it and another, for `https`
    only, and for another host. yt-dlp's jar chooses which a link is sent, and the read sends the
    ones yt-dlp's own request does: the host's and this path's."""
    url, served = origin
    jar = cookie_file(
        tmp_path,
        f"127.0.0.1 FALSE / FALSE {HOSTS_COOKIE}",
        "127.0.0.1 FALSE /clip.mp4 FALSE here=this-path",
        "127.0.0.1 FALSE /elsewhere FALSE there=another-path",
        "127.0.0.1 FALSE / TRUE secure=https-only",
        "127.0.0.5 FALSE / FALSE other=another-host",
    )
    with yt_dlp.YoutubeDL({"cookiefile": str(jar), "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    (control,) = _cookie_sent(served.heard)
    chosen = set((control or "").split("; "))
    assert chosen == {HOSTS_COOKIE, "here=this-path"}, "the control: the jar chose otherwise"
    served.heard.clear()

    length = _placed_unless_lacking(
        "max_redirects", url, NOT_KEEPING_THE_COOKIES, cookies=_cookies_for(url, jar)
    )

    if length is None:
        assert served.heard == [], "this ffprobe cannot stop at a redirect, and was started"
    else:
        assert length == pytest.approx(6, abs=0.1)
        sent = [set((cookie or "").split("; ")) for cookie in _cookie_sent(served.heard)]
        assert sent and all(each == chosen for each in sent), sent


def _read_by_ffprobe_alone(url: str) -> int:
    """ffprobe's exit code reading `url` on the direct route with no header given, so with the
    cookies it keeps from replies its own to send."""
    _, ffprobe = resolve_ffmpeg()
    direct = Route("", None, 20.0).arguments()
    code, _ = run_with(Popen)([ffprobe, "-v", "error", *direct, url], 30)
    return code


@needs_loopback_addresses
def test_a_cookie_a_site_sets_on_its_redirect_is_not_sent_on(site: Path) -> None:
    """**The second review's case, `T252-R9`**: no cookie of the user's, and a link on `127.0.0.1`
    that sets one on its redirect to `127.0.0.5`, as a site logging its visitor in does. ffprobe
    keeps a cookie set in a reply and sends it to every link after, so the other host was handed
    the login; yt-dlp keeps it to the host that set it. The read now sends every link the jar's
    header, empty where it holds none, which turns ffprobe's own cookies off.

    The control has two halves: yt-dlp sends the second host nothing, and ffprobe given no header
    sends it the cookie."""
    for url, _, served in redirect_on(site, sets=ISSUED_COOKIE):
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            ydl.urlopen(url).read()
        assert served.heard and set(_cookie_sent(served.heard)) == {None}, "the control: sent on"
        served.heard.clear()
        assert _read_by_ffprobe_alone(url) == 0, "the control: ffprobe did not follow"
        assert ISSUED_COOKIE in _cookie_sent(served.heard), "the control: ffprobe did not keep it"
        served.heard.clear()

        length = _placed(url)

        assert length == pytest.approx(6, abs=0.1)
        assert served.heard and set(_cookie_sent(served.heard)) <= {None, ""}, "it was sent on"


def test_a_cookie_a_site_sets_on_a_redirect_to_itself_is_not_sent_back(site: Path) -> None:
    """**What the empty header costs, ruled 2026-11-01**: a site that sets its cookie on a
    redirect to itself and serves only a request carrying it. yt-dlp sends the cookie back and is
    served, and so is ffprobe left to itself. The read sends no cookie it was not given, so this
    length is not read, and the item is cancelled as one with none."""
    for url, _, served in redirect_on(site, ISSUED_COOKIE, "127.0.0.1", needs=ISSUED_COOKIE):
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            ydl.urlopen(url).read()
        assert _cookie_sent(served.heard) == [ISSUED_COOKIE], "the control: yt-dlp did not"
        served.heard.clear()
        assert _read_by_ffprobe_alone(url) == 0, "the control: ffprobe was not served"
        served.heard.clear()

        with pytest.raises(worker.NothingDownloadedError) as cancelled:
            _placed(url)

        assert cancelled.value.reason == NO_LENGTH
        assert served.heard and set(_cookie_sent(served.heard)) <= {None, ""}


@needs_loopback_addresses
def test_a_proxy_a_header_names_is_the_one_used_and_is_never_sent(
    origin: tuple[str, type[Origin]], proxy: tuple[str, type[Proxy]]
) -> None:
    """yt-dlp takes a `Ytdl-Request-Proxy` header as the proxy for every request, over any other,
    and sends the header to nobody; `--add-headers` in the options field can set it."""
    url, served = origin
    address, forwarded = proxy
    headers = {"Ytdl-Request-Proxy": address}
    with yt_dlp.YoutubeDL({"quiet": True, "http_headers": headers}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == [PROXY_SIDE], "the control did not take the header's proxy"
    assert all("ytdl-request-proxy" not in heard for heard in served.heard), "the control sent it"
    served.callers.clear()
    served.heard.clear()

    assert _placed(url, headers=headers) == pytest.approx(6, abs=0.1)

    assert forwarded.asked, "the header's proxy was not asked"
    assert served.callers and set(served.callers) == {PROXY_SIDE}, served.callers
    assert all("ytdl-request-proxy" not in heard for heard in served.heard), "the header was sent"


@needs_loopback_addresses
def test_a_proxy_written_in_capitals_is_the_one_read_through(
    origin: tuple[str, type[Origin]], proxy: tuple[str, type[Proxy]]
) -> None:
    """**`T252-R5` as narrowed, and `T368-R4`**: yt-dlp goes through `HTTP://…`, and ffprobe
    handed it as written read the length directly, since ffmpeg takes a proxy only where the text
    starts `http://`."""
    url, served = origin
    address, forwarded = proxy
    written = address.replace("http://", "HTTP://", 1)
    with yt_dlp.YoutubeDL({"proxy": written, "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == [PROXY_SIDE], "the control: yt-dlp did not go through it"
    served.callers.clear()
    _, ffprobe = resolve_ffmpeg()
    code, _ = run_with(Popen)(
        [ffprobe, "-v", "error", *Route(written, None, 20.0).arguments(), url], 30
    )
    assert code == 0 and served.callers == ["127.0.0.1"], "the control: ffprobe went through it"
    served.callers.clear()
    forwarded.asked.clear()

    assert _placed(url, proxy=written) == pytest.approx(6, abs=0.1)

    assert forwarded.asked, "the proxy was not asked"
    assert set(served.callers) == {PROXY_SIDE}, f"the origin was reached directly: {served.callers}"


def test_a_proxy_ffprobe_would_go_around_is_never_tried(origin: tuple[str, type[Origin]]) -> None:
    """ffmpeg handed a SOCKS proxy connected directly (measured 2026-10-27), so it is not handed
    one: the item is cancelled and the origin never asked."""
    url, served = origin

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, proxy="socks5://127.0.0.1:9")

    assert cancelled.value.reason == NOT_THROUGH_THE_PROXY
    assert served.callers == []


@needs_loopback_addresses
def test_the_length_is_read_from_the_request_s_address(origin: tuple[str, type[Origin]]) -> None:
    """`T253-R3`: connections are made from the address the request names, as yt-dlp's are."""
    url, served = origin
    with yt_dlp.YoutubeDL({"source_address": BOUND, "quiet": True}) as ydl:
        ydl.urlopen(url).read()
    assert served.callers == [BOUND], "the control did not connect from the address"
    served.callers.clear()

    length = _placed_unless_lacking("local_addr", url, source_address=BOUND)

    if length is None:
        assert served.callers == [], "this ffprobe cannot connect from the address, and was started"
    else:
        assert length == pytest.approx(6, abs=0.1)
        assert served.callers and set(served.callers) == {BOUND}, served.callers


def test_an_ffprobe_without_an_option_the_route_needs_is_never_started_on_the_link(
    origin: tuple[str, type[Origin]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T368-R5`, on any build**: the one in use made to lack `local_addr`, as Debian 12's 5.1.9
    does. Asking it is what tells the two apart; the build is asked through the worker."""
    url, served = origin
    monkeypatch.setattr(
        worker, "defined_options", lambda *given: defined_options(*given) - {"local_addr"}
    )

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, source_address=BOUND)

    assert cancelled.value.reason == NOT_WITH_THIS_FFPROBE
    assert served.callers == []


#: A value for each option a route can pass, to give ffprobe with a file on disk.
OPTION_VALUES: dict[str, str] = {
    "http_proxy": "http://127.0.0.1:9",
    "max_redirects": "0",
    "timeout": "1000000",
    "local_addr": "127.0.0.1",
    "tls_verify": "1",
}


@pytest.mark.parametrize("option", sorted(OPTION_VALUES))
def test_the_ffprobe_in_use_takes_exactly_the_options_it_lists(site: Path, option: str) -> None:
    """`defined_options` held to the build: one it does not define fails ffprobe before it reads
    anything, and one it defines does not, on a file on disk. Measured 2026-10-30 on FFmpeg
    5.1.9, 6.1.1 and 8.1.3, each lacking a different one or none."""
    assert set(OPTION_VALUES) == frozenset().union(*PROTOCOL_OPTIONS.values())
    _, ffprobe = resolve_ffmpeg()
    shown = ["-show_entries", "format=duration", "-of", "csv=p=0", str(site / "clip.mp4")]

    code, _ = run_with(Popen)(
        [ffprobe, "-v", "error", f"-{option}", OPTION_VALUES[option], *shown], 30
    )

    assert (code == 0) is (option in defined_options(ffprobe, run_with(Popen)))


def test_ipv6_only_does_not_reach_an_ipv4_origin(origin: tuple[str, type[Origin]]) -> None:
    """**The review's case, `T253-R3`**: yt-dlp told to use IPv6 only cannot reach this origin,
    which is IPv4 only, and the read had reached it and returned six seconds."""
    url, served = origin
    with (
        yt_dlp.YoutubeDL({"source_address": "::", "quiet": True}) as ydl,
        pytest.raises(TransportError, match="No remote IPv6 addresses"),
    ):
        ydl.urlopen(url).read()

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(url, source_address="::")

    assert cancelled.value.reason == (NOT_WITH_THIS_FFPROBE if _lacks("local_addr") else NO_LENGTH)
    assert served.callers == []


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    return make_certificate(tmp_path_factory)


@pytest.fixture
def verified_as_windows_does() -> Iterator[None]:
    """The process as Windows leaves it once a session has run: `ssl.SSLContext` is
    `truststore`'s. It runs on Linux too, so the server is built under that patch everywhere."""
    before = ssl.SSLContext
    verify_with_the_operating_system(os_name="nt")
    try:
        yield
    finally:
        if ssl.SSLContext is not before:
            truststore.extract_from_ssl()


@pytest.mark.usefixtures("verified_as_windows_does")
def test_a_certificate_nobody_signed_is_refused(site: Path, certificate: tuple[Path, Path]) -> None:
    """The read sends the site's cookies, and ffmpeg checks no certificate unless asked, which
    `SEC-004` forbids yt-dlp. The control: ffprobe left to itself reads this server."""
    assert ssl.SSLContext is not SERVER_CONTEXT, "the application's patch is not in place"
    handler: type[Origin] = type("Origin", (Origin,), {"callers": [], "heard": []})
    for server in serve(functools.partial(handler, directory=str(site))):  # type: ignore[arg-type]
        context = SERVER_CONTEXT(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(*certificate)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        url = f"https://127.0.0.1:{server.server_address[1]}/clip.mp4"
        _, ffprobe = resolve_ffmpeg()
        unchecked = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", url],
            capture_output=True,
            text=True,
            check=False,
        )
        assert float(unchecked.stdout) == pytest.approx(6, abs=0.1), "the control read nothing"
        handler.callers.clear()

        with pytest.raises(worker.NothingDownloadedError) as cancelled:
            _placed(url)

        assert cancelled.value.reason == NO_LENGTH
        assert handler.callers == [], "a request was sent to a server nobody vouched for"


def test_a_manifest_is_not_read_even_as_one_file(origin: tuple[str, type[Origin]]) -> None:
    """ffmpeg fetches HLS pieces from wherever the playlist says, without the address to connect
    from or a certificate check (measured 2026-10-27), so only a demuxer that reads one file may
    read the length: a playlist served as a plain link is not read past itself. The control:
    ffprobe left to itself reads it and its pieces."""
    url, served = origin
    playlist = url.replace("clip.mp4", "clip.m3u8")
    _, ffprobe = resolve_ffmpeg()
    unchecked = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", playlist],
        capture_output=True,
        text=True,
        check=False,
    )
    assert float(unchecked.stdout) == pytest.approx(6, abs=0.1), "the control read nothing"
    assert len(served.callers) > 1, "the control fetched no piece"
    served.callers.clear()

    with pytest.raises(worker.NothingDownloadedError) as cancelled:
        _placed(playlist)

    assert cancelled.value.reason == NO_LENGTH
    assert len(served.callers) == 1, "a piece was fetched past the playlist"
