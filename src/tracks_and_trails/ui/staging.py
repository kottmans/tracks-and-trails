"""What a pasted batch of URLs looks like while it resolves (`T-118`, `UX-003`).

**Qt-free on purpose.** This is the state machine the add dialog drives, and keeping it out of
`QWidget` means the rules below are tested directly rather than through a widget that needs a
`QApplication` and an event loop to say anything. `ui/reveal.py` and `ui/log_view.py` are the same
split for the same reason.

## The rule this exists to enforce

`UX-003`: **a job enters the queue only once it has been probed.** Probing used to be a button
covering the first URL alone, so everything else a user pasted was queued having never been looked
at — a row with no title, no duration and no thumbnail until it reached the front of the queue.
Here every entered line is a `Row`, every row resolves, and only resolved rows can be committed.

## A row belongs to a line, not to a job id

`T016-R1` was Critical and its lesson survives the rewrite intact. A result is bound to **the text
of the line it was started for** and to the generation of the input box at that moment — not to
`MediaInfo.url`, which is yt-dlp's canonical `webpage_url` and routinely differs from what was
pasted. A row whose line is gone is marked `SUPERSEDED` rather than deleted, because a result
already queued as a signal still arrives and something has to refuse it **by name**. Deleting the
record would make that refusal unreachable, which `ai/TESTING.md` §13 is about.

## Two identical lines are two rows

`REQ-001`, and `T016-R1` again: `split_urls` keeps both, so the user asked for both. Rows are
matched to lines **positionally within a URL**, so pasting the same link twice resolves twice and
commits twice.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class RowState(StrEnum):
    """Where one pasted line has got to.

    A `StrEnum` so a test failure names the state rather than an ordinal, and so the accessible
    text `NFR-005` requires can be derived from it rather than duplicated beside it.
    """

    #: Entered, and nothing has happened to it yet.
    PENDING = "pending"
    #: Its job is being written. No worker has been asked anything (`REQ-012`).
    SAVING = "saving"
    #: Admitted, and waiting for a slot in the probe lane (`T-116`).
    #:
    #: **Distinct from `PROBING`, and the distinction is not pedantry.** The lane holds
    #: `DEFAULT_PROBE_CONCURRENCY` at a time, so a paste of five hundred has four rows being read
    #: and four hundred and ninety-six waiting. Calling them all "Reading" tells the user four
    #: hundred network requests are in flight, and leaves them wondering why nothing is finishing.
    WAITING = "waiting"
    #: A probe session is running.
    PROBING = "probing"
    #: The probe answered. This row can be committed.
    READY = "ready"
    #: The probe refused, and `message` carries the extractor's own words (`NFR-006`).
    FAILED = "failed"
    #: The line this belonged to is gone. Kept so a late result can be refused by name.
    SUPERSEDED = "superseded"


#: States a row can still leave under its own steam — something is running, or about to.
IN_FLIGHT: Final = frozenset({RowState.SAVING, RowState.WAITING, RowState.PROBING})

#: States from which a row will never resolve without being asked again.
SETTLED: Final = frozenset({RowState.READY, RowState.FAILED, RowState.SUPERSEDED})


@dataclass(eq=False)
class Row:
    """One entered line, and everything known about it.

    `media` and `message` are deliberately separate rather than one "result" field: a row can hold
    a failure *message* and no media, and conflating them would make "did this resolve" a question
    about which of two shapes a value has.

    **`eq=False`, so a row is an identity rather than a value** (`REQ-001`). Two identical pasted
    lines are two rows holding the same URL in the same generation, and a generated `__eq__` would
    make them interchangeable to anything reaching for `in`, `remove`, `index` or a `set`.

    Stated as what it is: this file no longer *depends* on it. `reconcile` tracks the rows it
    creates directly rather than asking which ones it had before, which is what an earlier version
    got wrong. So `eq=False` buys the semantics rather than fixing a live defect — and the
    semantics are pinned by a test, because an unfalsifiable justification in a docstring is the
    thing `ai/TESTING.md` §13 is about. A mutation removing it survived the whole battery until
    that test existed.
    """

    url: str
    generation: int
    state: RowState = RowState.PENDING
    job_id: str | None = None

    #: What the probe found. `None` until `READY`.
    media: object | None = None
    #: This row's own preset, or `None` to follow the batch (`UX-004`, `T118-R4`).
    #:
    #: **`None` means inherited, not "none"**, and the row says so in words rather than leaving a
    #: blank — a blank reads as no choice at all rather than as the one above it.
    preset: object | None = None
    #: The extractor's own words, character for character (`NFR-006`). `None` unless `FAILED`.
    message: str | None = None

    @property
    def in_flight(self) -> bool:
        """Something is running for this row and its answer is still wanted."""
        return self.state in IN_FLIGHT

    @property
    def committable(self) -> bool:
        """This row resolved, so `UX-003` allows it into the queue."""
        return self.state is RowState.READY

    @property
    def wants_resolving(self) -> bool:
        """Nothing has been started for this row and something should be."""
        return self.state is RowState.PENDING


class Staging:
    """Every row of the current paste, in the order the lines were entered.

    A class rather than a bare list because three questions are asked of the collection often
    enough that answering them in the widget would mean answering them in several places: which
    row owns a job id, what may be committed, and what is still in flight.
    """

    def __init__(self) -> None:
        self._rows: list[Row] = []
        #: Bumped whenever the entered text changes. A row carries the generation it was created
        #: in, so a line that is typed, cleared and retyped produces a row that cannot be confused
        #: with the first one (`T016-R1`).
        self.generation = 0

    def __iter__(self) -> Iterator[Row]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> tuple[Row, ...]:
        """Every row, live and superseded alike, in entry order."""
        return tuple(self._rows)

    @property
    def visible(self) -> tuple[Row, ...]:
        """The rows that describe what the user is looking at."""
        return tuple(row for row in self._rows if row.state is not RowState.SUPERSEDED)

    def reconcile(self, urls: Sequence[str]) -> tuple[Row, ...]:
        """Make the rows describe `urls`, and return the ones newly created.

        **Existing rows are kept where the line is still there.** Retyping the tail of a paste must
        not restart the probes for the lines above it — that would make a batch of twenty
        unresolvable by editing, and it would spend twenty worker processes doing it.

        Matched positionally within a URL, so two identical lines keep two distinct rows
        (`REQ-001`). A row whose line has gone is superseded rather than dropped, so a result
        already in flight for it can still be refused by name.
        """
        self.generation += 1
        available = [row for row in self._rows if row.state is not RowState.SUPERSEDED]
        already_superseded = [row for row in self._rows if row.state is RowState.SUPERSEDED]

        kept: list[Row] = []
        fresh: list[Row] = []
        for url in urls:
            match = next((row for row in available if row.url == url), None)
            if match is None:
                created = Row(url=url, generation=self.generation)
                fresh.append(created)
                kept.append(created)
                continue
            # By identity, which `Row.eq=False` is what makes correct for two identical lines.
            available.remove(match)
            kept.append(match)

        # Whatever is left over described a line that is no longer entered.
        for orphan in available:
            orphan.state = RowState.SUPERSEDED

        # Entry order is what the queue will be built in, so the visible rows keep the user's
        # order and the superseded ones sit outside it rather than interleaved.
        self._rows = [*already_superseded, *available, *kept]
        return tuple(fresh)

    def for_job(self, job_id: str) -> Row | None:
        """The row that owns `job_id`, superseded or not.

        Superseded rows are searched deliberately: a late result has to find its row in order to
        be refused. Returning `None` for them would make the refusal indistinguishable from a
        message for a job this dialog never had.
        """
        return next((row for row in self._rows if row.job_id == job_id), None)

    def overrides(self) -> tuple[Row, ...]:
        """The rows carrying a preset of their own (`UX-004`)."""
        return tuple(row for row in self.visible if row.preset is not None)

    def committable(self) -> tuple[Row, ...]:
        """The rows `UX-003` allows into the queue, in entry order."""
        return tuple(row for row in self.visible if row.committable)

    def failed(self) -> tuple[Row, ...]:
        """The rows that would not resolve. They stay on screen and are never committed."""
        return tuple(row for row in self.visible if row.state is RowState.FAILED)

    def in_flight(self) -> tuple[Row, ...]:
        """The rows something is running for."""
        return tuple(row for row in self._rows if row.in_flight)

    def pending(self) -> tuple[Row, ...]:
        """The visible rows nothing has been started for yet."""
        return tuple(row for row in self.visible if row.wants_resolving)

    def staged_job_ids(self) -> tuple[str, ...]:
        """Every staging job this batch currently holds, resolved or not.

        What `done()` unstages. **Nothing here is durable** — a staging probe never writes a row
        (`T118-R1`) — so this answers "what has a transient job to stop", not "what is on disk".

        *(It replaces `unresolved_job_ids()` and `written_job_ids()`, which split that question
        along a line that stopped existing: one returned what Add must leave behind and the other
        what close must withdraw, and both described rows persisted before probing. `T118-R11`
        found them still saying so. With nothing written, close stops everything and Add stops what
        it committed, so one answer serves and neither caller has to reason about durability.)*
        """
        return tuple(row.job_id for row in self._rows if row.job_id is not None)

    def settled(self) -> bool:
        """Every visible row has an answer, so the batch is as resolved as it will get."""
        return bool(self.visible) and all(row.state in SETTLED for row in self.visible)


def placeholder_hue(url: str) -> int:
    """A hue in degrees for `url`'s tile, stable for a given link (`UX-003`).

    **Every row is filled from the moment it appears.** A thumbnail exists only after a probe, so
    without this a fresh paste is a column of empty wells — which reads as a broken application
    rather than as work in progress, and reads worse the more URLs are pasted.

    Derived rather than random so a link keeps its tile across a retype and a restart, and derived
    *here* rather than in the widget so it can be asserted without a `QApplication`.

    `hash()` is deliberately not used: it is salted per process, so the same URL would get a
    different tile on every launch. The arithmetic is trivial on purpose — this is decoration, and
    `NFR-005` forbids it from being the only thing distinguishing two rows, so nothing rests on it
    being hard to collide.
    """
    total = 0
    for index, character in enumerate(url):
        total = (total * 31 + ord(character) + index) % 360
    return total


def summarise(rows: Iterable[Row]) -> str:
    """One line describing where a batch has got to, in words rather than by colour (`NFR-005`).

    Written here rather than in the widget so the wording is asserted without building a dialog,
    and so the counts cannot disagree with `Staging`'s own answers.
    """
    rows = tuple(rows)
    if not rows:
        return "Paste one URL per line."

    ready = sum(1 for row in rows if row.state is RowState.READY)
    failed = sum(1 for row in rows if row.state is RowState.FAILED)
    working = sum(1 for row in rows if row.state in IN_FLIGHT or row.wants_resolving)

    if working:
        return f"Reading {len(rows)} URLs — {ready} done"
    if failed:
        noun = "URL" if failed == 1 else "URLs"
        return f"{ready} ready · {failed} {noun} could not be read"
    return f"{ready} ready"
