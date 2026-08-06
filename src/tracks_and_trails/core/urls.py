"""The completion ledger's lookup key (`DAT-006`, `REQ-022`, `T-170`).

**One question, and it is narrower than "are these the same page".** `REQ-022` warns that a URL has
been downloaded before. Answering it needs a key two pastes of the same thing agree on — not a
canonical form, and not an opinion about which query parameters matter.

## Why the normalisation is so small

`DAT-006` §2 decides it: lower-case the scheme and host, drop the fragment, and **nothing else**.

The tempting additions all strip query parameters, and the query is where the identity lives on the
largest site this application serves — `watch?v=…` *is* the video. A rule clever enough to drop
`utm_source` and keep `v` is a per-site rule, and a per-site rule is wrong the first time a site
changes or a new one appears.

**The two failure directions are not symmetric.** A missed duplicate costs a warning that does not
appear, and the user downloads something they already had — recoverable, and exactly what today
does. A false duplicate warns about the wrong file, and a user who trusts it skips a download they
wanted. Only the second one lies, so the rule stays conservative.

## What it deliberately does not do

- **No credential handling.** This is given the URL the *user typed*, never the signed CDN address
  yt-dlp resolves — `DAT-006` §1 and §6. A token inside a pasted URL is the user's own input,
  stored because they will paste it again, and removed when they clear their records.
- **No network, no DNS, no percent-decoding.** Decoding would make `%2F` and `/` compare equal,
  which is a different question and one nobody asked.
"""

from urllib.parse import urlsplit, urlunsplit

__all__ = ["normalise_url"]


def normalise_url(url: str) -> str | None:
    """`url` as the ledger keys it, or `None` when it cannot be keyed.

    `None` rather than a fallback to the raw string: a value that cannot be parsed has no key, and a
    row that stores one anyway would match some other unparseable string. Never matching is the
    honest outcome, and it is the missed-duplicate side of the trade this module's docstring makes.
    """
    text = url.strip()
    if not text:
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        # `urlsplit` raises on a malformed IPv6 literal, which a user can paste.
        return None
    if not parts.scheme or not parts.netloc:
        # A bare `example.com/watch` is not something this application downloads either — the
        # request carries it verbatim to yt-dlp, so keying it would invent an identity the
        # downloader does not share.
        return None
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
