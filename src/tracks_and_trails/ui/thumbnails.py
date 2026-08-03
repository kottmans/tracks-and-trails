"""Thumbnails for a queue nobody promised would be small (`T-119`, `REQ-002`, `NFR-004`).

A public application cannot assume a queue of twenty. Everything here follows from that one
sentence, and each rule below is a criterion `T-119` states rather than an optimisation:

- **Bytes are fetched only for a row the view asks to paint.** `pixmap()` is called from the
  delegate's `paint()`, and a fetch starts on the miss it returns. A model with a thousand rows and
  a viewport showing twelve therefore issues twelve requests, not a thousand — which is the
  difference between a queue that opens and one that hammers a site on the user's behalf.
- **The in-memory cache has a stated bound**, `DEFAULT_PIXMAP_LIMIT`, and evicts least-recently
  used beyond it. A cache with no bound is a memory leak with a hit rate.
- **The disk cache lives under `NFR-004`'s cache directory** and is keyed by the *thumbnail URL*,
  so two jobs for one video share one file (`core/paths.thumbnail_cache_path`).
- **Nothing blocks the GUI thread — not a fetch, and not a decode** (`ARC-005`). Disk reads,
  decoding and scaling all run on a worker pool; only the finished `QImage` crosses back.
- **A missing picture is not a failed download.** A URL that will not fetch or will not decode is
  remembered as failed and never asked for again. The row keeps its derived tile and says nothing
  about it, because there is nothing the user could do and nothing has actually gone wrong.

## Why `QImage` in the worker and `QPixmap` on the GUI thread

`QPixmap` may only be touched on the GUI thread — it is a handle to a server-side resource. `QImage`
is plain memory and is safe anywhere. So the expensive half (read, decode, scale) happens on the
pool and produces a `QImage`; the cheap half (`QPixmap.fromImage`) happens in the slot. Scaling in
the worker is what bounds the memory too: a 1920-wide thumbnail becomes a 96-wide one before it is
ever held.
"""

import os
from collections import OrderedDict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

from tracks_and_trails.core.paths import thumbnail_cache_directory, thumbnail_cache_path

#: The size a thumbnail is drawn at, and the size it is scaled to before it is ever cached.
#: 16:9 at the height a row can afford — see `row_delegate.ROW_HEIGHT`.
THUMBNAIL_SIZE: Final = (96, 54)

#: **The stated bound on the in-memory cache** (`T-119`), in decoded pixmaps.
#:
#: Sized to cover several screens of scrolling rather than a whole queue: the point of the cache is
#: that scrolling back up does not re-decode, and holding a thousand pixmaps to achieve that would
#: be holding the queue in memory twice. At `THUMBNAIL_SIZE` in 32-bit colour one entry is ~20 KB,
#: so this bound is a few megabytes rather than an unbounded fraction of the queue.
DEFAULT_PIXMAP_LIMIT: Final = 64

#: How many decode/read jobs run at once. Small on purpose: these are short tasks and the queue of
#: them is drained in viewport order, so more threads would mostly contend for the disk.
_POOL_THREADS: Final = 2


class ThumbnailLoader(Protocol):
    """Fetches thumbnail bytes without blocking the GUI thread.

    Injected rather than constructed inline so a test can hand over bytes without a network. The
    real one is `NetworkThumbnailLoader`; nothing above this line knows the difference.
    """

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None: ...

    def cancel(self) -> None: ...


class NetworkThumbnailLoader(QObject):
    """Fetches thumbnails over HTTP.

    `QNetworkAccessManager` is asynchronous, so this does not block the GUI thread even though it
    runs on it — the reply arrives as an event like any other.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtNetwork import QNetworkAccessManager

        self._network = QNetworkAccessManager(self)
        self._replies: list[Any] = []

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtNetwork import QNetworkRequest

        reply = self._network.get(QNetworkRequest(QUrl(url)))
        self._replies.append(reply)

        def finished() -> None:
            if reply in self._replies:
                self._replies.remove(reply)
            data = (
                bytes(reply.readAll().data())
                if reply.error() == reply.NetworkError.NoError
                else None
            )
            reply.deleteLater()
            done(data)

        reply.finished.connect(finished)

    def cancel(self) -> None:
        for reply in list(self._replies):
            reply.abort()
        self._replies.clear()


def _scaled(image: QImage) -> QImage:
    """`image` at `THUMBNAIL_SIZE`, aspect preserved. On the worker, never on the GUI thread."""
    width, height = THUMBNAIL_SIZE
    return image.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class _ReadFromDisk(QRunnable):
    """Read and decode one cached thumbnail, or report that there is none.

    A `QRunnable` rather than a thread per request: the pool bounds how many decodes run at once,
    and these are short enough that creating a thread for each would cost more than the work.
    """

    def __init__(self, store: ThumbnailStore, url: str, path: Path) -> None:
        super().__init__()
        self._store = store
        self._url = url
        self._path = path

    def run(self) -> None:
        # `finally`, so the store's outstanding count cannot leak on any exit path — a leaked
        # count would leave `close()` waiting for a task that had already finished (`T118-R13`).
        try:
            try:
                data = self._path.read_bytes()
            except OSError:
                # An unreadable cache file is a cache miss, not an error worth telling anyone
                # about. The bytes are regenerable by definition — that is what makes it a cache.
                self._store.disk_missed.emit(self._url)
                return
            image = QImage()
            if not image.loadFromData(data):
                self._store.disk_missed.emit(self._url)
                return
            self._store.decoded.emit(self._url, _scaled(image))
        finally:
            self._store.task_done.emit()


class _DecodeAndStore(QRunnable):
    """Decode fetched bytes and write them to the disk cache, off the GUI thread."""

    def __init__(self, store: ThumbnailStore, url: str, data: bytes, path: Path) -> None:
        super().__init__()
        self._store = store
        self._url = url
        self._data = data
        self._path = path

    def run(self) -> None:
        try:
            image = QImage()
            if not image.loadFromData(self._data):
                # Undecodable bytes and a failed fetch are the same thing to a user: no picture.
                self._store.failed.emit(self._url)
                return
            try:
                # **Written aside and renamed**, not written in place. `write_bytes` creates the
                # file and then fills it, so a reader — the next launch, or another window sharing
                # this URL — can open a name that exists and get a truncated image. A rename is
                # atomic on both platforms' local filesystems, so the cache file either is not
                # there or is complete. Found by a test that raced its own write.
                self._path.parent.mkdir(parents=True, exist_ok=True)
                partial = self._path.with_name(f"{self._path.name}.{os.getpid()}.partial")
                partial.write_bytes(self._data)
                partial.replace(self._path)
            except OSError:
                # A cache that cannot be written still serves this launch from memory. Failing
                # the thumbnail because the cache directory is read-only would be the tail
                # wagging the dog.
                pass
            self._store.decoded.emit(self._url, _scaled(image))
        finally:
            self._store.task_done.emit()


class _SweepTask(QRunnable):
    """Delete cached files nothing names any more, off the GUI thread (`T118-R13`).

    Takes the *names to keep* rather than the store's state, so nothing here reads anything the
    GUI thread may be changing underneath it. The directory listing, the `is_file` stats and the
    unlinks are all disk work of unbounded duration, which is why none of it may happen inline.
    """

    def __init__(self, store: ThumbnailStore, directory: Path, keep: set[str]) -> None:
        super().__init__()
        self._store = store
        self._directory = directory
        self._keep = keep

    def run(self) -> None:
        removed = 0
        try:
            try:
                entries = list(self._directory.iterdir())
            except OSError:
                # No cache directory yet, or one this process cannot read. Nothing to sweep, and
                # nothing worth reporting: the files are regenerable by definition.
                entries = []
            for entry in entries:
                if entry.name in self._keep or not entry.is_file():
                    continue
                try:
                    entry.unlink()
                except OSError:
                    continue
                removed += 1
            self._store.swept.emit(removed)
        finally:
            self._store.task_done.emit()


class ThumbnailStore(QObject):
    """Bounded pixmaps over a disk cache over the network, fetched only for painted rows."""

    #: `(thumbnail_url)` — a pixmap became available and the rows showing it should repaint.
    ready = Signal(str)

    #: `(removed_count)` — a sweep finished. Nothing in the UI needs this; a test waits on it,
    #: which is the honest way to assert work that deliberately no longer happens inline.
    swept = Signal(int)

    #: The store has closed **and** its last pool task has drained. `close()` returns long before
    #: this (`T118-R13`); ownership completes here instead of at a wait.
    closed = Signal()

    # Internal, and emitted from worker threads: Qt queues these onto the GUI thread because the
    # store lives there. They are the only way a `QRunnable` can answer, since it is not a QObject.
    decoded = Signal(str, object)
    disk_missed = Signal(str)
    failed = Signal(str)
    task_done = Signal()

    def __init__(
        self,
        *,
        loader: ThumbnailLoader | None = None,
        cache_root: Path | None = None,
        pixmap_limit: int = DEFAULT_PIXMAP_LIMIT,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._loader: ThumbnailLoader = loader or NetworkThumbnailLoader(self)
        self._cache_root = cache_root
        self._limit = max(pixmap_limit, 1)

        #: The bounded cache. `OrderedDict` rather than a plain dict because eviction needs an
        #: order, and "least recently *used*" means a hit has to move its entry to the end.
        self._pixmaps: OrderedDict[str, QPixmap] = OrderedDict()
        #: Requests in flight. Painting a row twice before its picture arrives must not fetch twice.
        self._inflight: set[str] = set()
        #: URLs that will not produce a picture. **Never retried** — a row that repaints sixty
        #: times a second would otherwise be sixty requests a second at a URL that already failed.
        self._failed: set[str] = set()
        self._fetches = 0
        self._closed = False
        #: Pool tasks started and not yet finished. What `close()` waits on — by callback.
        self._outstanding = 0

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(_POOL_THREADS)

        self.decoded.connect(self._on_decoded)
        self.disk_missed.connect(self._on_disk_missed)
        self.failed.connect(self._on_failed)
        self.task_done.connect(self._on_task_done)

    # --- what the delegate calls ------------------------------------------------------------

    def pixmap(self, thumbnail_url: str | None) -> QPixmap | None:
        """This URL's picture if it is in memory, else `None` — **and start getting it**.

        Called from `paint()`, which is what makes "no fetch for a row the view never asked to
        paint" true by construction rather than by a rule someone has to remember. A row scrolled
        past has never been painted, so it has never been here.

        Returning `None` is not a failure: the delegate draws the derived tile and repaints when
        `ready` says there is something better.
        """
        if not thumbnail_url:
            return None
        existing = self._pixmaps.get(thumbnail_url)
        if existing is not None:
            self._pixmaps.move_to_end(thumbnail_url)
            return existing
        self._begin(thumbnail_url)
        return None

    def peek(self, thumbnail_url: str | None) -> QPixmap | None:
        """This URL's picture if it is already in memory, **without starting anything**.

        The distinction from `pixmap()` is the whole of "no fetch for a row the view never asked to
        paint": anything that merely wants to *know* asks here, and only the paint path asks a
        question that can cause a request.
        """
        if not thumbnail_url:
            return None
        return self._pixmaps.get(thumbnail_url)

    def _begin(self, url: str) -> None:
        """Start looking for `url`'s picture: disk first, network only if it is not there.

        **The one gate.** Every route into this pipeline goes through here, so "already running"
        and "already known to fail" are decided once. A second copy of the `_failed` check further
        down looked like defence in depth and was really an untestable branch: with two gates,
        removing either left the other, so no test could tell whether the rule was enforced —
        which a mutation duly demonstrated by surviving.
        """
        if self._closed or url in self._inflight or url in self._failed:
            return
        self._inflight.add(url)
        self._start(_ReadFromDisk(self, url, thumbnail_cache_path(url, self._cache_root)))

    # --- the pipeline, all of it back on the GUI thread ---------------------------------------

    def _on_disk_missed(self, url: str) -> None:
        """Nothing cached, so ask the network. **This is the only counted fetch.**"""
        if self._closed:
            self._inflight.discard(url)
            return
        self._fetches += 1

        def delivered(data: bytes | None) -> None:
            if self._closed:
                self._inflight.discard(url)
                return
            if data is None:
                self._on_failed(url)
                return
            self._start(
                _DecodeAndStore(self, url, data, thumbnail_cache_path(url, self._cache_root))
            )

        self._loader.load(url, delivered)

    def _on_decoded(self, url: str, image: object) -> None:
        """A picture arrived. Hold it, evict down to the bound, and ask for a repaint."""
        self._inflight.discard(url)
        if self._closed or not isinstance(image, QImage) or image.isNull():
            return
        self._pixmaps[url] = QPixmap.fromImage(image)
        self._pixmaps.move_to_end(url)
        while len(self._pixmaps) > self._limit:
            # **Least recently used, and genuinely released** — `popitem` drops the last reference,
            # so the pixmap's memory goes with it rather than the entry merely being unreachable
            # through the cache.
            self._pixmaps.popitem(last=False)
        self.ready.emit(url)

    def _on_failed(self, url: str) -> None:
        """No picture, and no further asking. Recorded, never reported (`T-119`)."""
        self._inflight.discard(url)
        self._failed.add(url)

    # --- what the queue calls -----------------------------------------------------------------

    def sweep(self, live_thumbnail_urls: Iterable[str]) -> None:
        """Delete cached files no remaining job names. **Returns immediately** (`T118-R13`).

        **This is how "removed with the job" and "two jobs share one file" hold at once.** Keying
        by URL is what makes the sharing work, and it is exactly what makes deleting on one job's
        removal wrong — the other job still wants the picture. So removal is expressed as *what is
        still live*, and a file survives while any job names it.

        **The work is on the pool, not on the GUI thread** (`ARC-005`, `NFR-001`). This enumerated
        the cache directory, stat'd every entry and unlinked inline — and it is called from every
        queue model reset, which is what a removal, a reorder and a clear all cause. A user with a
        long history and a slow or networked cache directory would have paid that on the thread
        drawing their window. The URLs are resolved to names here, where the caller's iterable is
        still safe to read; everything touching the disk happens in `_SweepTask`.

        `swept` reports the count when it is done, which is what a test waits on.
        """
        wanted = {thumbnail_cache_path(url, self._cache_root).name for url in live_thumbnail_urls}
        if self._closed:
            return
        self._start(_SweepTask(self, thumbnail_cache_directory(self._cache_root), wanted))

    def close(self) -> None:
        """Stop fetching and **return**. Safe to call more than once (`T118-R13`).

        This ran `QThreadPool.waitForDone(5000)` inline, on the GUI thread, from the add dialog's
        `done()` and the queue's `detach()` — an explicit five-second stall on the thread that
        draws the window, at exactly the moment the user asked for it to go away. `NFR-001` and
        `ARCHITECTURE.md` §8 are unqualified about that, and this project has rejected a blocking
        shutdown before on the same grounds.

        So closing marks the store closed, cancels network work, and returns. Outstanding pool
        tasks drain on their own and `closed` is emitted when the last one does — ownership
        completes from a callback rather than from a wait.

        **What the wait was for is still handled.** A running task emits into this object, so it
        must not be destroyed underneath one; `QThreadPool`'s own destructor waits for its
        runnables, and it runs when this store is destroyed — after its parent has let it go,
        rather than on the interaction. Every task also checks `_closed` before touching anything.
        """
        if self._closed:
            return
        self._closed = True
        self._loader.cancel()
        if not self._outstanding:
            self.closed.emit()

    def _start(self, task: QRunnable) -> None:
        """Run `task` on the pool, counting it so `close()` knows when the last one is done."""
        self._outstanding += 1
        self._pool.start(task)

    def _on_task_done(self) -> None:
        """One pool task finished. The last one after a close completes the shutdown."""
        self._outstanding = max(self._outstanding - 1, 0)
        if self._closed and not self._outstanding:
            self.closed.emit()

    # --- what tests read ------------------------------------------------------------------------

    @property
    def fetches(self) -> int:
        """How many times the network has been asked. The count `T-119`'s criterion asserts on."""
        return self._fetches

    @property
    def cached_urls(self) -> tuple[str, ...]:
        """What is held in memory, least recently used first."""
        return tuple(self._pixmaps)

    @property
    def pending_urls(self) -> frozenset[str]:
        """What is being looked for right now — **synchronously**, before anything completes.

        `fetches` only rises once a disk miss has come back on the GUI thread, so it cannot answer
        "did that call start any work?" in the same breath as the call. This can, which is what
        lets `peek`'s promise be asserted rather than merely stated: a mutation making `peek` begin
        a fetch is invisible to a fetch count and obvious here.
        """
        return frozenset(self._inflight)

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def outstanding(self) -> int:
        """Pool tasks started and not yet finished. Synchronous, so a test can assert that a UI
        call *scheduled* work rather than doing it (`T118-R13`)."""
        return self._outstanding
