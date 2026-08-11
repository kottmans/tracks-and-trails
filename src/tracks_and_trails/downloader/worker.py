"""Child-process entry point. The only module that instantiates YoutubeDL.

Must not import Qt and must be import-safe under the 'spawn' start method
(`ARC-002`, `ARCHITECTURE.md` §3).

**Import-safe means importing this module does nothing.** Under `spawn`, Python re-imports the
child's module in a fresh interpreter before calling the target. Any work at import time runs
again on every spawn — and in a frozen build (`REL-001`) it runs in a process that believes it
is the application. `run_session()` is called explicitly; nothing happens on import.

## yt-dlp is imported *here*, and only here

`downloader/environment.py` locates candidates (`OPS-002`); this module walks them, puts the
first on `sys.path`, imports, and falls back on `ImportError`. `ARCHITECTURE.md` §6 requires
that a rejected override be **reported, never silently ignored** — a user who installed a
broken copy and sees the baseline's behaviour with no explanation has been lied to.

The import is deferred into `_import_ytdlp()` rather than done at module scope for the same
reason `app.py` defers Qt: a module that imports yt-dlp at the top cannot be imported by a
test, or by the layering analyser, without paying for it.

## One session, one outcome

A worker runs exactly one probe or one download, emits exactly one outcome, then the sentinel
(`downloader/protocol.py`). Nothing here enforces "one" — that is `validate_sequence()`'s job
on the receiving side — but the control flow is written so there is a single exit path.

## Cancellation, and dying with the parent

`T-013` owns cancellation, but two halves of it can only exist here, because only the child can
observe them (`REQ-015`, `ARCHITECTURE.md` §3):

- **The cooperative path.** The parent sets an event; the progress hooks notice it and raise
  yt-dlp's own `DownloadCancelled`, which unwinds the download through yt-dlp's cleanup rather
  than through a signal, so partial files are left in a known state. The parent still escalates
  to `terminate()` and `kill()` on a timeout — this path is the tidy case, not the guarantee.
- **The orphan guard.** `spawn_session()` — the process entry point, and the only thing here
  that knows it is a child — watches the parent and exits if it disappears. A `daemon=True`
  process is cleaned up when the parent exits *normally*; nothing in the parent runs when it is
  killed, so without this a `SIGKILL`ed application would leave a download running forever.
"""

import logging
import multiprocessing
import os
import platform
import shutil
import sys
import threading
import traceback
from collections.abc import Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

from tracks_and_trails.core.errors import ErrorKind, FailureDetail
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.core.paths import (
    UnsafePathError,
    contained_output_path,
    derived_component,
    is_contained,
    numbered_variant,
)
from tracks_and_trails.core.presets import selector_merges
from tracks_and_trails.downloader import process_tree
from tracks_and_trails.downloader.environment import (
    APP_SLUG,
    FfmpegReport,
    YtdlpCandidate,
    find_ffmpeg,
    ytdlp_candidates,
)
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    Progress,
    ResolutionReport,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)


class SessionCancelledError(Exception):
    """The stand-in used when the resolved yt-dlp has no `DownloadCancelled` of its own.

    yt-dlp's exception is preferred because yt-dlp *knows* it: it unwinds its own download and
    post-processing state rather than being caught as an arbitrary extractor failure. A copy old
    or odd enough not to define it still has to be cancellable, so cancellation falls back to
    this rather than becoming un-cancellable.
    """


class CancelSignal(Protocol):
    """Anything the parent can use to ask this session to stop.

    A `Protocol` for the same reason as `MessageSink`: the real caller passes a
    `multiprocessing.Event`, and a unit test passes a `threading.Event` or a stub. Only
    `is_set()` is named, because setting it is the parent's business (`T-013`).
    """

    def is_set(self) -> bool: ...


class MessageSink(Protocol):
    """Anything the worker can put messages on.

    A `Protocol` rather than `queue.Queue`, because the real caller hands it a
    `multiprocessing.Queue` — a different class with the same shape. Naming the shape rather
    than the class is what lets the same code be driven by a plain queue in a unit test and by
    a real IPC queue in a spawned process (`ARC-002`).
    """

    def put(self, item: Any, /) -> None: ...


#: yt-dlp's own stage names, mapped onto `REQ-014`'s. Anything unrecognised keeps the previous
#: stage rather than inventing one, because a wrong stage is worse than a stale stage.
_POSTPROCESSOR_STAGES: Final[dict[str, Stage]] = {
    "Merger": Stage.MERGING,
    "FFmpegMerger": Stage.MERGING,
    "FFmpegVideoRemuxer": Stage.MERGING,
}


@dataclass(frozen=True, slots=True)
class ResolvedYtdlp:
    """Which yt-dlp the worker actually imported, and what it had to reject to get there.

    `rejected` is not decoration: `ARCHITECTURE.md` §6 requires a rejected override to be
    reported. It is carried here so the caller can log it rather than discovering the fallback
    by noticing that behaviour changed.
    """

    module: Any
    version: str
    source: str
    rejected: tuple[str, ...] = ()


def _origin_of(module: Any, candidate: YtdlpCandidate) -> str:
    """Where the imported module *actually* came from, not where we hoped it would.

    `import yt_dlp` returns whatever is already in `sys.modules`, ignoring `sys.path`. In a
    spawned worker nothing has imported it yet so the candidate order decides — but if anything
    ever does import it first, reporting the candidate we happened to be trying would be a lie:
    the worker would claim "user-managed copy" while running the baseline.

    So the source is derived from `__file__` rather than assumed. Deriving it also means the
    report stays true if the resolution order changes later.

    An earlier attempt purged `yt_dlp` from `sys.modules` instead. That was worse: re-importing
    creates *new* exception classes, so `ytdlp_adapter`'s `isinstance` checks against the ones
    it had already bound would all fail and every failure would classify as `EXTRACTOR_ERROR`.
    A silent, total loss of the taxonomy — found because a classification test failed.
    """
    location = getattr(module, "__file__", None)
    if candidate.path is not None and location is not None:
        try:
            Path(location).resolve().relative_to(Path(candidate.path).resolve())
        except ValueError:
            return f"{candidate.source} requested, but an already-imported yt-dlp was used"
    return candidate.source


def _import_ytdlp(candidates: tuple[YtdlpCandidate, ...]) -> ResolvedYtdlp:
    """Import the first candidate that works, recording every one that did not.

    Raises `ImportError` only if **no** candidate imports, which means the application is
    broken rather than the user's copy being bad.
    """
    rejected: list[str] = []
    for candidate in candidates:
        # Snapshot before the attempt so failure can be rolled back precisely (`T012-R2`).
        before = frozenset(sys.modules)
        if candidate.path is not None:
            path = str(candidate.path)
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        try:
            import yt_dlp  # deferred on purpose; see the module docstring
        except KeyboardInterrupt:
            # The one interruption that is not the candidate's fault. It means the user asked
            # this process to stop, and swallowing it to go try the baseline would ignore them.
            raise
        except BaseException as error:
            # Never silent (`ARCHITECTURE.md` §6). The reason travels with the result.
            #
            # `BaseException`, not `Exception` and certainly not `ImportError` (`T012-R2`). A
            # user copy is arbitrary third-party code being *executed*, and §6's rule is about
            # whether it "imports cleanly" — not about which base class it chose to fail with.
            #
            # `SyntaxError` and `AttributeError` shapes were the first widening. `SystemExit` is
            # the second: a module calling `sys.exit()` at import time is not an `Exception` at
            # all, so it escaped `_import_ytdlp` entirely and the baseline was never tried. A
            # broken override thereby took the whole worker down — the exact outcome `OPS-002`'s
            # fallback exists to prevent, reached by the one route the previous widening missed.
            rejected.append(_redacted_reason(candidate, f"{error.__class__.__name__}: {error}"))
            _discard_partial_ytdlp(before)
            if candidate.path is not None:
                sys.path.remove(str(candidate.path))
            continue
        return ResolvedYtdlp(
            module=yt_dlp,
            version=str(yt_dlp.version.__version__),
            source=_origin_of(yt_dlp, candidate),
            rejected=tuple(rejected),
        )
    raise ImportError(f"no usable yt-dlp: {'; '.join(rejected) or 'no candidates'}")


def _redacted_reason(candidate: YtdlpCandidate, reason: str) -> str:
    """Why a candidate was rejected, with its filesystem path replaced by its label.

    The reason crosses to the parent and is shown and logged, and exception text from a broken
    package routinely embeds the file that failed. `NFR-007` keeps user paths out of records
    that travel and persist, and the *label* is what actually helps: "your yt-dlp folder" tells
    the user which copy was refused, while the absolute path only repeats what they configured.
    """
    cleaned = reason
    if candidate.path is not None:
        cleaned = cleaned.replace(str(candidate.path), f"<{candidate.source}>")
    return f"{candidate.source}: {cleaned}"


def _discard_partial_ytdlp(before: frozenset[str]) -> None:
    """Undo the `sys.modules` damage of one *failed* candidate import (`T012-R2`).

    A package that raises partway through `__init__` leaves whatever it already imported behind
    in `sys.modules`. The next candidate's `import yt_dlp` then reuses those half-initialised
    submodules instead of loading its own, and the baseline fails with an error naming the
    broken copy's internals — so a broken override took the baseline down with it and
    `OPS-002`'s fallback did not happen at all.

    Two constraints make this safe rather than a repeat of the purge that broke classification:

    - **Only on failure.** A module that imported successfully is never touched, so the classes
      `ytdlp_adapter` binds keep their identity and `isinstance` keeps working.
    - **Only what this attempt added.** Anything already in `sys.modules` before the attempt
      belongs to someone else and is left exactly as it was.

    Scoped to the `yt_dlp` namespace: a broken copy may also have imported unrelated
    third-party modules, and evicting those would break code that has nothing to do with us.

    **The `before` guard is deliberately unverified.** Removing it survives the suite, and that
    is honest rather than a coverage gap: this runs only when `import yt_dlp` *failed*, which
    cannot happen while any `yt_dlp` module is already cached — so there is nothing pre-existing
    to protect and no reachable test can distinguish the two. It stays because it states the
    invariant the purge that broke classification violated, and because "only remove what this
    attempt added" must remain true if candidate handling is ever reordered.
    """
    for name in [n for n in sys.modules if n == "yt_dlp" or n.startswith("yt_dlp.")]:
        if name not in before:
            del sys.modules[name]


class _Reporter:
    """Turns yt-dlp's hook callbacks into `T-011` messages on the result queue.

    Holds the last stage so an unrecognised post-processor does not reset progress to a stage
    the job is not in.
    """

    def __init__(self, job_id: str, queue: MessageSink, cancel: CancelSignal | None = None) -> None:
        self._job_id = job_id
        self._queue = queue
        self._stage = Stage.PROBING
        self._cancel = cancel
        self._cancelled_error: type[BaseException] = SessionCancelledError
        #: Hook failures are swallowed so a reporting bug cannot kill a download — but they are
        #: counted, and the count reaches the parent in the outcome's context. Swallowing
        #: silently would make missing progress updates unexplainable.
        self.hook_failures: list[str] = []

    def send(self, message: Any) -> None:
        self._queue.put(message)

    def stage(self, stage: Stage) -> None:
        self._stage = stage

    def use_cancellation_error(self, error: type[BaseException]) -> None:
        """Adopt the resolved yt-dlp's own abort exception, once there is one to adopt."""
        self._cancelled_error = error

    def _abort_if_cancelled(self) -> None:
        """Raise if the parent has asked this session to stop (`REQ-015`).

        Called from the hooks **outside** their `try`, and that placement is the whole
        mechanism: everything inside is swallowed so that a reporting bug cannot kill a
        download, and `DownloadCancelled` is an `Exception`, so a check inside the guard would
        be caught by it and cancellation would be recorded as a hook failure while the download
        carried on.
        """
        if self._cancel is not None and self._cancel.is_set():
            raise self._cancelled_error("the parent process cancelled this session")

    def progress_hook(self, status: dict[str, Any]) -> None:
        """yt-dlp's `progress_hooks` callback. Must not raise: it runs inside the download."""
        self._abort_if_cancelled()
        try:
            info = status.get("info_dict") or {}
            if status.get("status") == "downloading":
                self._stage = (
                    Stage.DOWNLOADING_AUDIO
                    if info.get("vcodec") == "none"
                    else Stage.DOWNLOADING_VIDEO
                )
            self.send(
                Progress(
                    job_id=self._job_id,
                    stage=self._stage,
                    downloaded_bytes=_int_or_none(status.get("downloaded_bytes")),
                    total_bytes=_int_or_none(
                        status.get("total_bytes") or status.get("total_bytes_estimate")
                    ),
                    speed_bytes_per_second=_float_or_none(status.get("speed")),
                    eta_seconds=_int_or_none(status.get("eta")),
                )
            )
        except Exception as error:  # a reporting bug must not kill the download
            self._record_hook_failure("progress", error)

    def postprocessor_hook(self, status: dict[str, Any]) -> None:
        self._abort_if_cancelled()
        try:
            name = str(status.get("postprocessor") or "")
            self._stage = _POSTPROCESSOR_STAGES.get(name, Stage.POST_PROCESSING)
            self.send(Progress(job_id=self._job_id, stage=self._stage))
        except Exception as error:
            self._record_hook_failure("postprocessor", error)

    def _record_hook_failure(self, hook: str, error: Exception) -> None:
        """Keep at most a few, so a hook failing on every chunk cannot flood the outcome."""
        if len(self.hook_failures) < 5:
            self.hook_failures.append(f"{hook}: {type(error).__name__}: {error}")


def run_session(
    kind: SessionKind,
    job_id: str,
    request: DownloadRequest,
    queue: MessageSink,
    *,
    cancel: CancelSignal | None = None,
    user_ytdlp_directory: Path | None = None,
    ffmpeg_override: Path | None = None,
    cookie_file: Path | None = None,
    cookie_browser: str | None = None,
) -> int:
    """Run one probe or one download and return the process exit code.

    **Every path emits exactly one outcome and then `WorkerFinished`.** A worker that exits
    without an outcome is indistinguishable from a crashed one to the parent (`REQ-028`), so
    the sentinel is sent in a `finally` and the outcome is sent before it on every branch.
    """
    reporter = _Reporter(job_id, queue, cancel)
    exit_code = 0
    try:
        resolved = _import_ytdlp(ytdlp_candidates(user_ytdlp_directory))
        _log_the_session_header(kind, resolved)
        reporter.use_cancellation_error(_cancellation_error(resolved))
        # Reported before the work starts, so it reaches the parent even if the job then fails
        # (`T012-R1`, `REQ-025`, `ARCHITECTURE.md` §6).
        reporter.send(
            ResolutionReport(
                job_id=job_id,
                ytdlp_version=resolved.version,
                ytdlp_source=resolved.source,
                rejected=resolved.rejected,
            )
        )
        outcome = _run(
            kind, job_id, request, reporter, resolved, ffmpeg_override, cookie_file, cookie_browser
        )
        reporter.send(outcome)
        exit_code = 0 if not isinstance(outcome, Failed) else 1
    except SessionCancelledError as error:
        # Cancellation before yt-dlp was resolved, so `_run` never ran to classify it. Still an
        # outcome: the parent asked, and a session that stops without saying so is a crash.
        reporter.send(Failed(job_id=job_id, kind=ErrorKind.CANCELLED, message=str(error)))
        exit_code = 1
    except BaseException as error:  # the outcome must reach the parent whatever happened
        detail = _classify_without_ytdlp(error)
        reporter.send(
            Failed(
                job_id=job_id,
                kind=detail.kind,
                message=detail.message,
                context=detail.context,
            )
        )
        exit_code = 1
    finally:
        reporter.send(WorkerFinished(job_id=job_id, exit_code=exit_code))
    return exit_code


def _log_the_session_header(kind: SessionKind, resolved: ResolvedYtdlp) -> None:
    """The versions a bug report needs, at the top of the job's log (`T-084`, `REQ-019`).

    **This is what replaces yt-dlp's `verbose` banner, and writing it ourselves is the point.**
    Verbose would supply the same versions and, measured, also dump `params:` and `Proxy map:` —
    the proxy URL and `cookiesfrombrowser`, which are values *this application supplies* and the
    one row of `DAT-003`'s provenance table that must never reach a log. Here every field is
    chosen, and the line is application-authored, so the full redaction rules apply to it.

    Never raises. A header is a convenience and a job that failed to start because its log banner
    could not be assembled would be an absurd way to lose a download.
    """
    logger = logging.getLogger(f"{APP_SLUG}.worker")
    try:
        logger.info(
            "%s session: yt-dlp %s (%s), Python %s, %s",
            kind.value,
            resolved.version,
            resolved.source,
            platform.python_version(),
            platform.platform(),
        )
    except Exception:  # a header is never worth failing a download over
        logger.debug("the session header could not be assembled", exc_info=True)


def _run(
    kind: SessionKind,
    job_id: str,
    request: DownloadRequest,
    reporter: _Reporter,
    resolved: ResolvedYtdlp,
    ffmpeg_override: Path | None,
    cookie_file: Path | None,
    cookie_browser: str | None,
) -> Probed | Succeeded | Failed:
    """The session body. Returns the outcome rather than sending it, so there is one send."""
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    context: dict[str, str] = {
        "ytdlp_version": resolved.version,
        "ytdlp_source": resolved.source,
    }
    if resolved.rejected:
        # `ARCHITECTURE.md` §6: a rejected override is reported, never silently ignored.
        context["ytdlp_rejected"] = "; ".join(resolved.rejected)

    def with_hook_failures(outcome: Probed | Succeeded | Failed) -> Probed | Succeeded | Failed:
        """Attach any swallowed hook failures, so missing progress is explainable."""
        if reporter.hook_failures and isinstance(outcome, Failed):
            merged = {**dict(outcome.context), "hook_failures": "; ".join(reporter.hook_failures)}
            return Failed(
                job_id=outcome.job_id,
                kind=outcome.kind,
                message=outcome.message,
                context=tuple(sorted(merged.items())),
            )
        return outcome

    ffmpeg = find_ffmpeg(override=ffmpeg_override)
    directory = Path(request.output_directory)

    try:
        if kind is SessionKind.PROBE:
            reporter.stage(Stage.PROBING)
            reporter.send(Progress(job_id=job_id, stage=Stage.PROBING))
            # **Cookies apply to the probe too** (`T197-R3`, and `T012-R5` is the same finding for
            # the proxy): a URL that needs signing in fails while being *read*, before the
            # download that would have used them is ever attempted.
            info = _extract(
                adapter, request, resolved, reporter, probe_only=True, cookie_file=cookie_file
            )
            if adapter.has_drm(info):
                return _drm_failure(job_id, request, context)
            return with_hook_failures(Probed(job_id=job_id, media=adapter.project_media(info)))

        # A download session probes first, so DRM and ffmpeg are caught before any bytes move.
        # Cookies apply here for the same reason as above (`T197-R3`).
        reporter.stage(Stage.PROBING)
        info = _extract(
            adapter, request, resolved, reporter, probe_only=True, cookie_file=cookie_file
        )
        if adapter.has_drm(info):
            return _drm_failure(job_id, request, context)

        missing = _ffmpeg_gap(ffmpeg, request, info, adapter)
        if missing is not None:
            return Failed(
                job_id=job_id,
                kind=ErrorKind.FFMPEG_MISSING,
                message=missing,
                context=tuple(sorted(context.items())),
            )

        # **The download writes into a staging directory, and the real name is claimed after**
        # (`T046-R1`). The obvious shape — reserve the target, hand it to yt-dlp with
        # `overwrites=True` — reserves the wrong file whenever a postprocessor changes the
        # extension. `%(ext)s` renders `webm`, the reservation is `master.webm`, and the MP3
        # extractor then writes `master.mp3` **over the user's existing `master.mp3`**, because
        # `O_EXCL` never covered the name that survived conversion. A reviewer reproduced exactly
        # that against real yt-dlp and ffmpeg: an ID3 file replaced the user's bytes.
        #
        # Predicting the final extension was rejected: it is a function of yt-dlp's postprocessor
        # chain, and a prediction that is wrong is this defect again with more code. Instead the
        # download happens somewhere nothing of the user's can be, and the destination is claimed
        # atomically once yt-dlp has said what it actually produced.
        target = _validated_target(directory, request, adapter, resolved, info)
        # **The same directory every time this job runs** (`T-113`, `REQ-017`). Keyed by the job
        # id rather than by `mkdtemp`, so a `.part` left by a killed attempt is exactly where the
        # next one writes and yt-dlp continues from it. Created here rather than by
        # `staging_directory`, so asking where a job's partial *would* be costs nothing.
        staging = open_staging(directory, job_id)
        result = _extract(
            adapter,
            request,
            resolved,
            reporter,
            probe_only=False,
            # Literal, not a second template — see `as_literal_template`.
            output_template=as_literal_template(staging / target.name),
            # `OPS-001`: yt-dlp must use the binary the worker gated on, not its own lookup.
            ffmpeg_location=ffmpeg.path,
            cookie_file=cookie_file,
            cookie_browser=cookie_browser,
            # Safe **because the directory is this job's alone**. Nothing of the user's is in
            # it, so an overwrite can only ever replace this job's own intermediate files —
            # which is what the flag is for, and is no longer a claim about the output folder.
            overwrites=True,
        )
        produced = _written_path(result, staging / target.name)
        # **The media and everything the user asked to keep, claimed as one family** (`T046-R3`,
        # `T-109`, `T109-R3`, `T109-R4`). The destination keeps the *final* extension, not the
        # template's — that is the name the user will see and the one that has to be free — and the
        # sidecars take the same basename, so a collision moves the whole family rather than
        # separating a subtitle from the file it belongs to. An output that cannot be placed raises,
        # and is caught below as a failed job: the two used to be claimed independently and a
        # sidecar failure was swallowed while the outcome said the download had worked.
        written, _kept = claim_outputs(
            result,
            staging=staging,
            stem=Path(target.name).stem,
            target=target.with_name(produced.name),
            produced=produced,
            # What tells a deleted intermediate from a lost output — see `claim_outputs`.
            writing_subtitles=bool(request.subtitle_languages) and not request.embed_subtitles,
        )
        # **Discarded here, on the success path, and no longer in a `finally`** (`T-113`).
        # A `finally` threw the partial away whichever way the session ended, which is right for
        # a download that landed and wrong for one that failed: a network error is precisely when
        # the retry most wants a head start, and `REQ-017` exists to give it one. The other two
        # ways out are handled where they are caught — cancellation discards, and an unclean death
        # runs no code at all, which is how the partial survives a kill.
        _discard_staging(staging)
        return with_hook_failures(
            Succeeded(
                job_id=job_id,
                output_path=str(written),
                total_bytes=_int_or_none((result or {}).get("filesize_approx")),
            )
        )
    except UnsafePathError as error:
        # Classified here rather than by the adapter, which maps *yt-dlp's* vocabulary. A
        # rejected output template has nothing to do with an extractor, and `EXTRACTOR_ERROR`
        # would tell the user the site failed when their own template is the problem.
        #
        # `DISK` is the taxonomy's filesystem bucket and its consequence — fail, pause the
        # queue — is the right one: the template is shared by every queued job, so continuing
        # would produce the identical failure once per job.
        return with_hook_failures(
            Failed(
                job_id=job_id,
                kind=ErrorKind.DISK,
                message=str(error),
                context=tuple(sorted(context.items())),
            )
        )
    except BaseException as error:
        if _is_cancellation(error, resolved):
            # **The partial is not discarded here, and that is `T113-R2` and `T113-R3`.** This
            # branch used to delete it, which was wrong twice over. It cannot tell *why* it is
            # stopping — a user's Cancel and an orderly shutdown reach it identically, and only
            # one of them means the download is unwanted — and it is not reached at all when the
            # parent escalates to `terminate()` or `kill()`, so an uncooperative worker left the
            # partial behind whatever the intent was. The parent knows the intent and can act
            # *after* the process is gone, which is the only moment at which a cleanup cannot be
            # undone by the process it is cleaning up after. `DownloadManager._release` owns it.
            #
            # Classified here rather than by the adapter for the same reason as `UnsafePathError`
            # above: the user asked for this. `EXTRACTOR_ERROR` would report the site as broken,
            # and `ErrorKind.CANCELLED` is the one kind `core.errors` treats as not a failure to
            # offer a retry for.
            return with_hook_failures(
                Failed(
                    job_id=job_id,
                    kind=ErrorKind.CANCELLED,
                    message=str(error) or "the parent process cancelled this session",
                    context=tuple(sorted(context.items())),
                )
            )
        detail = adapter.classify_exception(error)
        return with_hook_failures(
            Failed(
                job_id=job_id,
                kind=detail.kind,
                message=detail.message,
                context=tuple(sorted({**context, **dict(detail.context)}.items())),
            )
        )


def _cancellation_error(resolved: ResolvedYtdlp) -> type[BaseException]:
    """The exception this session raises to abort a download from a progress hook.

    yt-dlp's own `DownloadCancelled` when the resolved copy has one, because yt-dlp recognises
    it and unwinds cleanly; `SessionCancelledError` otherwise, so an unusual copy is still
    cancellable. Read from the resolved module rather than imported at the top of the file: the
    module docstring's deferred-import rule applies to every yt-dlp name, not just the package.
    """
    utils = getattr(resolved.module, "utils", None)
    candidate = getattr(utils, "DownloadCancelled", None)
    if isinstance(candidate, type) and issubclass(candidate, BaseException):
        return candidate
    return SessionCancelledError


def _is_cancellation(error: BaseException, resolved: ResolvedYtdlp) -> bool:
    """Whether `error` is this session being cancelled rather than failing.

    Both classes are checked because which one the hook raised depends on what the resolved copy
    offered, and by the time the exception is caught that decision is no longer visible.
    """
    return isinstance(error, SessionCancelledError | _cancellation_error(resolved))


#: Exit code of a worker that outlived its parent. Distinct from `1` (a failed session) so a
#: parent examining a reaped process — or a person reading a log — can tell the two apart.
ORPHAN_EXIT_CODE: Final = 66

#: Exit code of a worker that refused to run because it could not be contained (`T019-R3`).
#: Distinct from both of the above for the same reason: these are different corpses.
UNCONTAINED_EXIT_CODE: Final = 67


def _exit_when_the_parent_does() -> None:
    """Exit this process if the parent disappears (`T-013`: no orphan survives the parent).

    `daemon=True` covers only an orderly parent exit, because it is implemented by the parent's
    own `atexit` handling — and a parent that was `SIGKILL`ed runs nothing. A download left
    running after the application is gone writes to the user's disk with no UI able to stop it,
    so the child watches instead of being watched.

    `multiprocessing.parent_process()` is the portable form: its sentinel is a pipe fd on POSIX
    and a process handle on Windows, so `join()` returns exactly when the parent dies. A daemon
    thread, so it can never hold up a session that finishes normally, and `os._exit` rather than
    `sys.exit` because a `SystemExit` raised on this thread would be ignored by the one doing
    the download.
    """
    parent = multiprocessing.parent_process()
    if parent is None:  # not a spawned child at all; nothing to watch
        return

    def watch() -> None:
        parent.join()
        # **Take the descendants first, and expect not to return.** `ffmpeg` is a process of its
        # own: exiting this one used to leave the merge writing to the user's disk after both the
        # application and the worker were gone (`T-019`). Killing the group is what stops it, and
        # this process is *in* that group, so on POSIX the call below is normally the last
        # thing that happens here — by design, and fail-closed. `SIGKILL` cannot be ignored
        # by a descendant, which `SIGTERM` can. On Windows it returns: the Job object reaps
        # the tree when this process's handles close, which the exit below does.
        process_tree.kill_this_group()
        # Reached only when there was no group of our own to kill — containment failed at
        # start-up, so `kill_tree` signalled nothing rather than risk the parent's group. Nothing
        # spawned by this worker is covered in that case, and the exit code says which corpse
        # this is.
        os._exit(ORPHAN_EXIT_CODE)

    threading.Thread(target=watch, name="parent-watchdog", daemon=True).start()


def prepare_this_worker(log_queue: Any | None = None, log_job_id: str | None = None) -> bool:
    """Everything a spawned worker must do before it starts working, in the order it must do it.

    Named and separate because it is the **contract for being a worker**, not an implementation
    detail of `spawn_session`. `DownloadManager`'s `entry_point` seam replaces `spawn_session`
    entirely, so a stand-in worker in a test that did not repeat these two calls would be
    subtly unlike every real one — and it was: the first version of `T-019`'s parent-kill test
    watched a stand-in worker and its child both survive the application, because the stand-in
    had no watchdog. One function, called by production and by the stand-ins, keeps the two the
    same shape. That `spawn_session` calls it is proven separately, against real workers, by
    `test_a_real_worker_leads_its_own_process_group` and
    `test_killing_the_parent_does_not_leave_the_child_running`.

    Returns whether **containment** was established. The caller decides what to do about a
    `False`, and `spawn_session()` refuses to run the session at all — see `T019-R3`.

    **Order matters.** Containment first: it works by capturing every *later* descendant, so
    anything spawned before it escapes. The watchdog second: it depends on the group established
    by the first to take the descendants with it.

    `log_queue` is `T-038`'s worker→parent path. Records travel **unformatted**, so the parent's
    handlers render them and a worker cannot emit an unredacted line even in principle. Optional
    because a worker driven directly by a unit test has no parent to send them to.
    """
    contained = process_tree.contain_this_process()
    _exit_when_the_parent_does()
    if log_queue is not None:
        # Imported here rather than at module scope: `core.logging` is Qt-free and cheap, but
        # this module is re-imported on every spawn and pays for everything at the top.
        from tracks_and_trails.core.logging import worker_logging_handler

        worker_logging_handler(log_queue, job_id=log_job_id)
        if not contained:
            # After the handler, not before: this is the first moment the reason can both be
            # known and reported. A worker that cannot be contained still runs its download —
            # failing the job for it would be a failure the user cannot act on — so the only
            # cost of silence here is that nobody finds out why a descendant survived.
            logging.getLogger(f"{APP_SLUG}.worker").warning(
                "this worker is not contained, so its descendants would outlive it: %s",
                process_tree.containment_error,
            )
    return contained


def _refuse_to_run_uncontained(job_id: str, queue: MessageSink) -> None:
    """Report the refusal in the protocol's own terms, then let the caller exit (`T019-R3`).

    A full, legal session: one outcome and then the sentinel. The parent therefore records an
    ordinary failed job with a message a person can act on, rather than inferring something from
    an exit code — which is the difference between a refusal and a crash.

    `WORKER_CRASH` because the taxonomy has no kind for "this worker cannot run safely", and
    inventing one is an `ARCHITECTURE.md` §7 change with a maintainer decision attached
    (`T-014` needed exactly that for `INTERRUPTED`). The message carries what the kind cannot.
    """
    queue.put(
        Failed(
            job_id=job_id,
            kind=ErrorKind.WORKER_CRASH,
            message=(
                "This download was refused before it started: the worker could not put its child "
                "processes under a handle this application can stop "
                f"({process_tree.containment_error}). Cancelling it would not have stopped the "
                "conversion it spawns, so it was not begun."
            ),
        )
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=UNCONTAINED_EXIT_CODE))


def spawn_session(
    kind: SessionKind,
    job_id: str,
    request: DownloadRequest,
    queue: MessageSink,
    *,
    cancel: CancelSignal | None = None,
    user_ytdlp_directory: Path | None = None,
    ffmpeg_override: Path | None = None,
    cookie_file: Path | None = None,
    cookie_browser: str | None = None,
    log_queue: Any | None = None,
    log_job_id: str | None = None,
) -> None:
    """The `multiprocessing` entry point: run one session, then exit with its code.

    Separate from `run_session()` because the two have genuinely different jobs. `run_session`
    is callable in-process and returns a value; this one is what a spawned child *is*, so it
    installs the orphan guard and turns the result into a process exit code.

    `SystemExit` rather than `return`: a `Process` target's return value is discarded, and the
    exit code is what `REQ-028` requires the parent to record for a session that produced no
    outcome.

    **Containment comes first** (`T-019`): `contain_this_process()` has to run before yt-dlp can
    spawn anything, because it works by making every *later* descendant a member of a set the
    kernel tracks. It cannot retroactively adopt an `ffmpeg` that already exists.

    **And if it fails, the session does not run** (`T019-R3`). The first version logged a warning
    and carried on, on the reasoning that a worker which cannot be contained should still do the
    user's download. That reasoning is wrong here: `T-019`'s criterion — no surviving descendant,
    on any path — has no exception clause, and `REQ-015` promises that cancelling terminates the
    underlying work. Downloading anyway would mean an `ffmpeg` that nothing in the application
    can stop, writing to the user's disk after they pressed cancel. A refusal is visible and
    recoverable; that is not.
    """
    if not prepare_this_worker(log_queue, log_job_id):
        _refuse_to_run_uncontained(job_id, queue)
        raise SystemExit(UNCONTAINED_EXIT_CODE)
    raise SystemExit(
        run_session(
            kind,
            job_id,
            request,
            queue,
            cancel=cancel,
            user_ytdlp_directory=user_ytdlp_directory,
            ffmpeg_override=ffmpeg_override,
            cookie_file=cookie_file,
            cookie_browser=cookie_browser,
        )
    )


def _drm_failure(job_id: str, request: DownloadRequest, context: dict[str, str]) -> Failed:
    """`REQ-EXCL-001`, `SEC-001`. Fail, and do not look for another way in.

    There is deliberately no fallback selector, no retry with different options, and no attempt
    to find a non-DRM format. `ErrorKind.DRM_PROTECTED` is non-retryable in `core.errors`, so
    the UI will not offer a retry either.
    """
    return Failed(
        job_id=job_id,
        kind=ErrorKind.DRM_PROTECTED,
        message=(
            f"{request.url} is DRM-protected. Tracks & Trails does not download DRM-protected "
            "content and will not attempt to work around it."
        ),
        context=tuple(sorted(context.items())),
    )


def _will_merge(info: Mapping[str, Any]) -> bool | None:
    """Whether yt-dlp resolved this request to more than one format (`T-061`).

    **The question is what was chosen, not what was asked for.** This gate used to read
    `"+" in request.format_selector`, and `bestvideo+bestaudio/best` against a source offering one
    progressive format takes the `/best` branch — no merge, no ffmpeg — and was refused anyway.
    Four of the five built-in presets carry a `+`, so a user without ffmpeg had one usable preset
    and the first one they would reach for told them a download was impossible when it was not.

    `requested_formats` is yt-dlp's own record of the decision: a list of the formats it will
    merge, absent when a single format satisfied the selection. It is populated during the same
    probe this gate already runs, so the fact was in scope all along.

    Returns `None` when nothing was resolved — a playlist, or an extraction that stopped early.
    The caller falls back to the selector there rather than guessing "no merge", because a wrong
    *refusal* is recoverable and a wrong *proceed* spends the download first.

    **This is `T-057` again, one module over.** There the adapter matched a truthy string where
    yt-dlp keeps a three-state field; here the worker matched a `+` where yt-dlp keeps the
    resolved format list. Both read a rendering of a decision instead of the decision.
    """
    requested = info.get("requested_formats")
    if isinstance(requested, list):
        return len(requested) > 1
    if info.get("format_id"):
        return False
    return None


def _ffmpeg_gap(
    report: FfmpegReport, request: DownloadRequest, info: dict[str, Any], adapter: Any
) -> str | None:
    """Whether this download needs ffmpeg that is not present (`REQ-024`, `OPS-001`).

    Checked **before** downloading, which is the whole point of `REQ-024`: discovering it at
    merge time means the user's bandwidth is already spent.
    """
    if report.available:
        return None
    needs_merge = _will_merge(info)
    if needs_merge is None:
        # **Nothing was resolved, so fall back to reading the selector** — a playlist, or an
        # extraction that stopped before format selection. Being wrong in this direction costs a
        # refusal; being wrong in the other costs the user's bandwidth and then fails at merge
        # time anyway, which is the thing `REQ-024` exists to prevent.
        needs_merge = "+" in request.format_selector
    # Every post-processor the request will actually install is consulted, not just the two
    # flags that used to be checked here (`T012-R5`). A request naming `FFmpegMetadata` or
    # `EmbedThumbnail` needs ffmpeg exactly as much as an audio one, and previously sailed
    # through this gate to fail after the download had completed.
    if not (needs_merge or adapter.requires_ffmpeg(request)):
        return None
    return (
        f"ffmpeg is required for this download but was not found ({report.source}). "
        + report.summary()
    )


def _validated_target(
    directory: Path,
    request: DownloadRequest,
    adapter: Any,
    resolved: ResolvedYtdlp,
    info: dict[str, Any],
) -> Path:
    """Render the output template through yt-dlp, then put it through `T-034`.

    Rendering uses yt-dlp's own mechanism (`ARCHITECTURE.md` §9) because reimplementing its
    template language would be a second implementation of someone else's syntax. The result is
    then sanitized and contained — a title is attacker-influenced data, and this is the only
    thing standing between it and a path outside the directory the user chose.

    **The rendered path keeps its directories** (`T012-R4`). This previously reduced the result
    to `Path(rendered).name`, which silently discarded the user's own template structure:
    `nested/%(title)s.%(ext)s`, `../outside/%(title)s.%(ext)s` and `/tmp/outside/...` all
    collapsed to the same file in the chosen folder. So a subdirectory layout was ignored, and
    an escape attempt was neither honoured nor refused — it was quietly rewritten into
    something that looked like it had worked.

    Escapes are now **rejected rather than neutralized**, which is what the task requires of a
    *template*. `safe_output_path` still neutralizes what comes from the title, because a video
    named `../../etc/passwd` should download safely rather than fail.
    """
    rendered = resolved.module.YoutubeDL(
        adapter.build_options(request, request.output_template, probe_only=True)
    ).prepare_filename(info)

    # **The same function `REQ-011`'s preview calls** (`T-112`). The escape refusal and the
    # containment call used to be written out here, where the parent process could not reach them —
    # so the preview would have been a second copy, and `docs/UX_SPEC.md` §9.1 says in as many
    # words that two would drift.
    return contained_output_path(directory, rendered)


#: How many alternatives are tried before a collision is called a loop (`T-046`). A directory
#: already holding a thousand files whose names all sanitize to one component is not a collision
#: any more; failing loudly beats spinning while the user waits.
MAX_COLLISION_ATTEMPTS: Final = 999


def _candidates(target: Path) -> Iterator[Path]:
    """`target`, then `target (2)`, `target (3)`, … — the order collisions are resolved in."""
    yield target
    for index in range(2, MAX_COLLISION_ATTEMPTS + 1):
        yield numbered_variant(target, index)


def free_output_path(target: Path) -> Path:
    """The first candidate nothing occupies. **Reads the filesystem and changes nothing.**

    This is the preview's half of `T-046` (`REQ-011`): the resolution has to be visible *before*
    the write, not applied silently afterwards, or the user is shown one filename and gets
    another — which is exactly what `DAT-002` kept `sanitize_component` idempotent to prevent.

    It is deliberately **not** a promise. Between previewing and writing, another job may take
    the name; `reserve_output_path` is what actually decides, and it can land one number further
    on. What this guarantees is that the *policy* is the same one — same candidates, same order,
    one generator — so the preview never shows a name the write would not have considered.
    """
    for candidate in _candidates(target):
        if not candidate.exists():
            return candidate
    raise UnsafePathError(
        f"{str(target)!r} and {MAX_COLLISION_ATTEMPTS} numbered alternatives are all taken"
    )


def reserve_output_path(target: Path) -> Path:
    """Claim the first free candidate **atomically**, and return what was claimed (`T-046`).

    **`O_CREAT | O_EXCL`, because the writers are separate processes.** `ARC-002` gives every job
    its own child process, so two downloads whose titles sanitize identically are two processes
    racing for one name with no shared memory between them. Checking `exists()` and then creating
    is the classic hole: both see nothing, both proceed, and the second silently overwrites the
    first. The kernel deciding is the only check that cannot interleave.

    The reservation is a **zero-byte file**, which is why the download that follows is given
    `overwrites=True`: yt-dlp otherwise sees a file at the target and reports it as already
    downloaded. That flag is safe precisely because of this function — the only thing that can be
    at the reserved path is the reservation this process just made, since any pre-existing file
    fails `O_EXCL` and moves the candidate on.

    Released by `release_output_path` when the download does not fill it, so a failed attempt
    does not consume the name its retry wants.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    for candidate in _candidates(target):
        if _reserve_exactly(candidate):
            return candidate
    raise UnsafePathError(
        f"{str(target)!r} and {MAX_COLLISION_ATTEMPTS} numbered alternatives are all taken"
    )


#: Where a job's download happens before its output is claimed (`T046-R1`).
#:
#: **Inside the user's output directory, not the system temp area**, so the final move is a rename
#: within one filesystem — atomic, and never a copy of a multi-gigabyte file. A dot prefix keeps it
#: out of the way of somebody looking at their downloads folder.
STAGING_PREFIX: Final = ".tracks-and-trails-staging"


def staging_directory(directory: Path, job_id: str) -> Path:
    """This job's private directory, beside where its output will land.

    **Keyed by the job id, and that is what makes `REQ-017` possible** (`T-113`). It used to be
    `tempfile.mkdtemp`, which is unique per *call* — so a download killed halfway left its
    `.part` file in a directory nothing would ever look in again, and the next attempt started
    from zero in a fresh one. The uniqueness argument still holds and is better served: `ARC-002`
    runs every job in its own process and two titles can sanitize to one name, and a job id
    collides with nothing by construction rather than by asking the operating system.

    Nothing else was needed for resume. yt-dlp's `continuedl` is on by default, so it finds the
    `.part` at the path it is told to write and continues from it; the *only* reason this
    application restarted from the beginning was that it never told it the same path twice.

    **The id is hashed, not spelled** (`T113-R1`, **Critical**). The first version wrote the job id
    straight into the name, and `Job.id` is validated as non-empty text and nothing else — it comes
    off a database row that a user can edit and a corrupt write can mangle. An id of
    `../../../../outside` therefore named a real directory outside the chosen download folder,
    which `_run` then created with `parents=True`, wrote into with `overwrites=True`, and
    `discard_staging_for` removed with `shutil.rmtree`. A reviewer deleted a sentinel file that
    way. `derived_component` makes the leaf `[0-9a-f]{32}` whatever the id is, so there is no
    traversal to defend against.

    Not created here. `_run` creates it when it is about to download, so asking where a job's
    partial *would* be — which `resumable_partial` and the manager's cleanup both do — costs no
    directory on disk.
    """
    return directory / f"{STAGING_PREFIX}-{derived_component(job_id)}"


def usable_staging(staging: Path, directory: Path) -> bool:
    """Whether `staging` is a directory of this application's own, inside `directory` (`T113-R1`).

    **A digest makes the *name* safe and says nothing about what is at it.** That was the gap the
    first correction left: `derived_component` removed every traversal spelling from the job id, so
    the path is always one component under the download folder — and a **symlink** already sitting
    at that component points wherever it likes. `mkdir(parents=True, exist_ok=True)` accepts one
    without complaint, because a symlink to a directory *is* a directory to every question `mkdir`
    asks, and the download then writes through it. A reviewer created `outside/Clip.mp4` that way.

    Two questions, and both are needed. `is_symlink` is asked because it is the one shape that
    lies about where it is; `is_contained` resolves, so it also catches a link somewhere in the
    output directory's own path and answers the question that actually matters — *do writes here
    land inside the folder the user chose?*

    A name that does not exist yet is usable: `_run` creates it, and there is no third party
    between the two — see `open_staging`, which is where the ordering is arranged.
    """
    if staging.is_symlink():
        return False
    return not staging.exists() or (staging.is_dir() and is_contained(staging, directory))


def open_staging(directory: Path, job_id: str) -> Path:
    """This job's staging directory, created if need be, **verified before anything writes to it**.

    **Create, then verify, then write** (`T113-R1`, **Critical**). Checking first and creating
    afterwards leaves a window: the check passes on a path that does not exist, and a symlink
    planted before the `mkdir` is then accepted by it. Verifying the directory this call actually
    ended up with closes that — whatever was there, or arrived, is judged after the fact and before
    a single byte is written.

    Raises `UnsafePathError` rather than repairing anything. Deleting or replacing what is there
    would be this application removing something it did not create, at a path it cannot explain;
    refusing is the honest answer and `_run` turns it into a failed job with the reason.

    **A legitimate existing directory is left exactly as it is**, which is the whole point of the
    directory being stable: it holds the `.part` file `REQ-017` resumes from, and a check that
    cleared it to be safe would delete the thing it is protecting.
    """
    staging = staging_directory(directory, job_id)
    if not usable_staging(staging, directory):
        raise UnsafePathError(
            f"{str(staging)!r} is not this download's own working directory — something else is "
            "at that name, and writing through it would put the download outside the folder you "
            "chose"
        )
    staging.mkdir(parents=True, exist_ok=True)
    if not usable_staging(staging, directory):
        raise UnsafePathError(
            f"{str(staging)!r} stopped being this download's own working directory while it was "
            "being created"
        )
    return staging


def resumable_partial(directory: Path, job_id: str) -> Path | None:
    """The partial file a killed attempt left for this job, or `None` if there is none.

    **A fact about the filesystem, not a prediction about the site.** `REQ-017` asks the
    application to say when resumption is *not possible*, and after the fact this is exactly
    knowable: either bytes survived or they did not. Before the fact it is not — see
    `Job.resume_refusal` for the one case a probe can answer, and this function's own limit below.

    **A partial existing does not promise the resume will happen.** A server that ignores `Range`
    makes yt-dlp start from zero and overwrite the file, which is the correct outcome and not one
    this application can detect in advance. Measured against a local server with and without
    `Accept-Ranges`: with it, one range request and the download completed; without it, four full
    requests and the download completed. Both produced the right bytes; only one saved any.
    """
    staging = staging_directory(directory, job_id)
    if not staging.is_dir() or not usable_staging(staging, directory):
        # Something else is at that name (`T113-R1`). Reporting what is inside it as *this job's
        # partial* would be answering for a file the session never wrote.
        return None
    partials = sorted(staging.glob("*.part"))
    return partials[0] if partials else None


def requested_sidecars(result: Mapping[str, Any]) -> tuple[tuple[Path, bool], ...]:
    """Every file yt-dlp was asked to write **beside** the media, and whether it is there.

    Today that means subtitle files: `REQ-010` offers *embed or write*, and a written subtitle is
    an output in its own right rather than an intermediate. Read from `requested_subtitles`, which
    is yt-dlp's own record of what it fetched and where it put it — the decision rather than a
    rendering of it, which is `_will_merge`'s lesson and `T-061`'s. Globbing the staging directory
    for `*.srt` would also find a subtitle that was embedded and then deleted, and would find one
    nobody asked for.

    **Presence is reported rather than filtered** (`T109-R3`). This used to drop the missing ones
    silently, on the reasoning that *"the absence is the embed having worked"* — which is true when
    the request embeds and says nothing at all when it writes. The two cases need different
    answers, and a function that cannot tell them apart cannot give either: `claim_outputs` knows
    which the request asked for, so the fact travels there instead of being decided here.
    """
    requested = result.get("requested_subtitles")
    if not isinstance(requested, Mapping):
        return ()
    found: list[tuple[Path, bool]] = []
    for entry in requested.values():
        if not isinstance(entry, Mapping):
            continue
        filepath = entry.get("filepath")
        if not isinstance(filepath, str) or not filepath:
            continue
        candidate = Path(filepath)
        found.append((candidate, candidate.is_file()))
    return tuple(found)


def _reserve_exactly(path: Path) -> bool:
    """Take `path` with `O_CREAT | O_EXCL`, or answer `False` because something already has it.

    `reserve_output_path`'s primitive, split out for `claim_outputs`, which has to reserve a whole
    family at one index and give the lot back if any member is taken — a per-file loop over
    candidates cannot do that, because it would settle each name independently and that is
    precisely `T109-R4`.
    """
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    except OSError as error:
        raise UnsafePathError(f"cannot write to {str(path)!r}: {error}") from error
    os.close(handle)
    return True


def _inside(path: Path, directory: Path) -> bool:
    """Whether `path` is a **resolved** entry strictly inside `directory` (`T109-R8`).

    **Resolved, because the question is about the file and not about the spelling.**
    `staging in path.parents` is a comparison of path *components*: `staging/../Clip.de.vtt` has
    `staging` among its parents and names a file next to the directory rather than in it. A
    reviewer put user-owned bytes there, had them reported as a requested subtitle, and watched
    them moved into the download's output family — a file this session never created, relocated
    under a name the user had not asked for. `is_contained` resolves both sides, so `..` collapses
    and a symlink is judged by where it points.

    **Strictly inside**: the directory itself is not a file this session produced, and
    `is_contained` answers `True` for `path == directory`.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return resolved != directory.resolve() and is_contained(path, directory)


def _sidecar_suffix(name: str, stem: str) -> str:
    """What follows the media's stem in a sidecar's name — `.en.vtt`, not `.vtt`.

    Two suffixes, which `Path.suffix` alone cannot see, so the stem is stripped rather than the
    name rebuilt.
    """
    return name[len(stem) :] if name.startswith(stem) else name


def claim_outputs(
    result: Mapping[str, Any],
    *,
    staging: Path,
    stem: str,
    target: Path,
    produced: Path,
    writing_subtitles: bool,
) -> tuple[Path, tuple[Path, ...]]:
    """Move the media **and every requested sidecar** out of staging, under one shared name.

    Returns `(written, kept)`. Raises `UnsafePathError` when the outputs the request asked for
    cannot all be placed — which `_run` turns into a failed job, and which leaves the staging
    directory where it is so nothing the download produced is thrown away.

    **One free basename for the whole family** (`T109-R4`). The media and its sidecars used to be
    claimed independently, so with `Clip.mp4` free and `Clip.de.vtt` taken the subtitle landed as
    `Clip.de (2).vtt` — no longer the conventional sidecar for `Clip.mp4`, and a player would
    associate the *old* `Clip.de.vtt` and ignore the one just downloaded. The index is now chosen
    for the family: either `Clip.mp4` and `Clip.de.vtt`, or `Clip (2).mp4` and `Clip (2).de.vtt`,
    and never a mixture. That is also why the reservation is all-or-nothing per index — settling
    the media first and then looking for a subtitle name is how the two came apart.

    **A requested output that cannot be placed fails the job** (`T109-R3`). The failure used to be
    logged and swallowed: `claim_sidecars` returned nothing, `_run` ignored it, the cleanup deleted
    the subtitle still sitting in staging, and the job reported success. The user had asked for that
    file, it had been downloaded, and it was deliberately discarded while the outcome said
    everything worked. `T-109`'s first acceptance criterion is that each option produces a file, so
    an output that did not arrive is not a detail of cleanup.

    **The claim and the move are one step, and the claim comes first** (`T046-R1`). Every member is
    taken with `O_CREAT | O_EXCL`, so the kernel decides between two processes racing for a name;
    `os.replace` then puts each file into the name this process holds. Because a reservation is a
    zero-byte file this process just created, replacing it cannot destroy anything of the user's —
    which is the guarantee `overwrites=True` used to be claimed to have and did not, for every
    extension-changing postprocessor. `os.replace` rather than `shutil.move`: it is atomic within a
    filesystem, and the staging directory is deliberately created inside the destination's own
    directory so that it is one.

    **`writing_subtitles` is what tells a deleted intermediate from a lost output.** With
    `embed_subtitles` set, `FFmpegEmbedSubtitle` runs with `already_have_subtitle` false and yt-dlp
    deletes each file once it is inside the container — the entry stays in `requested_subtitles`
    with a `filepath` that no longer exists, and that absence *is* the embed having worked. With the
    subtitles written instead, the same absence means a file the user asked for is not there.
    """
    # **Every reported source is resolved and contained before anything is reserved or moved**
    # (`T109-R8`, **Critical**). `produced` and each sidecar path come out of yt-dlp's own result
    # dictionary — this function's *inputs*, not its outputs — and the containment machinery in
    # this file all points the other way, at where a file is going. A source outside the staging
    # directory was never written by this session, so moving it is relocating somebody else's
    # file; and the lexical test this replaces let `staging/../Clip.de.vtt` through, which is a
    # file beside the directory rather than in it.
    #
    # **Refused rather than skipped, and refused first.** Skipping the offender would leave a
    # session reporting success without an output the request asked for, which is `T109-R3`. Doing
    # it before the reservation loop is what makes *"without leaving reservations"* true by
    # construction rather than by unwinding.
    outside = [
        path
        for path, exists in ((produced, True), *requested_sidecars(result))
        if exists and not _inside(path, staging)
    ]
    if outside:
        raise UnsafePathError(
            "the download reported a file outside its own working directory: "
            + ", ".join(str(path) for path in sorted(outside))
        )

    sidecars = [(path, exists) for path, exists in requested_sidecars(result)]
    if writing_subtitles:
        absent = [path.name for path, exists in sidecars if not exists]
        if absent:
            raise UnsafePathError(
                "the download finished without the subtitle file(s) it was asked to write: "
                f"{', '.join(sorted(absent))}"
            )
    present = [path for path, exists in sidecars if exists]
    suffixes = [_sidecar_suffix(path.name, stem) for path in present]

    for candidate in _candidates(target):
        family = [candidate, *(candidate.with_name(f"{candidate.stem}{s}") for s in suffixes)]
        reserved: list[Path] = []
        candidate.parent.mkdir(parents=True, exist_ok=True)
        for member in family:
            if not _reserve_exactly(member):
                break
            reserved.append(member)
        if len(reserved) != len(family):
            # Somebody has part of this name. Give back what was taken and try the next index,
            # rather than keeping the free half and splitting the family across two basenames.
            for member in reserved:
                release_output_path(member)
            continue
        sources = [produced, *present]
        placed: list[tuple[Path, Path]] = []
        try:
            for source, destination in zip(sources, family, strict=True):
                source.replace(destination)
                placed.append((destination, source))
        except OSError as error:
            # **Everything already moved goes back into staging first** (`T109-R3`). A reservation
            # is only released while it is still empty — correctly, since one with bytes in it is
            # somebody's file — so releasing after a partial move would leave the media standing at
            # its final name under a session that is about to report failure. Putting each file
            # back restores the invariant a failed session depends on: what the download produced
            # is in staging, all of it, ready for the retry `T-113` keeps it for.
            for destination, source in reversed(placed):
                with suppress(OSError):
                    destination.replace(source)
            for member in family:
                release_output_path(member)
            raise UnsafePathError(
                f"cannot move the finished download to {str(candidate)!r}: {error}"
            ) from error
        return family[0], tuple(family[1:])

    raise UnsafePathError(
        f"{str(target)!r} and {MAX_COLLISION_ATTEMPTS} numbered alternatives are all taken"
    )


def _discard_staging(staging: Path) -> None:
    """Remove the staging directory and anything left in it.

    Anything still here after the claim is yt-dlp's intermediate work — the pre-conversion audio,
    a `.part` file from a failed attempt, a thumbnail that was embedded rather than kept. None of
    it is the user's, because nothing of the user's could ever be in a directory this process
    created for itself. **Except what `claim_outputs` has already taken out of it** (`T-109`):
    a subtitle the request asked to *write* is an output, and it is moved beside the media before
    this runs.

    Failure to clean up is not worth propagating, for `release_output_path`'s reason: the download
    has already succeeded or failed on its own terms, and a leftover directory is a much smaller
    problem than an exception raised from the path that reports the real outcome.
    """
    with suppress(OSError):
        shutil.rmtree(staging)


def discard_staging_for(directory: Path, job_id: str) -> None:
    """Throw away whatever a job's interrupted attempts left behind (`T-113`).

    The other half of keeping a partial: something has to end its life, or a download the user
    abandoned leaves bytes in their download folder for ever. Called when a job is **cancelled by
    the user** and when it is **removed** — the two moments somebody says they do not want it — and
    never on a failure, because a failure is the case a retry most wants a head start for, nor on
    an orderly shutdown, which is an interruption rather than a decision (`T113-R2`, `UX-008`).

    **Checked again before the `rmtree`, and the belt-and-braces is deliberate** (`T113-R1`).
    `derived_component` already makes an escaping name unrepresentable, so this branch is not
    reachable through the id — which is exactly what was said about `safe_output_path`'s final
    containment check until `T034-R1` reached it through a symlink. A recursive delete is the one
    operation in this file where being wrong is unrecoverable, so it asks rather than assumes.
    """
    staging = staging_directory(directory, job_id)
    if not usable_staging(staging, directory):
        # Asked through the same function the create path uses, so the two cannot come to disagree
        # about what counts as this job's own directory — which is how a guard at one end of a
        # lifetime stops covering the other.
        logging.getLogger(f"{APP_SLUG}.worker").error(
            "refusing to remove %s: it is not this job's own directory inside %s",
            staging,
            directory,
        )
        return
    _discard_staging(staging)


def release_output_path(reserved: Path) -> None:
    """Give back a reservation the download never filled.

    **Only when it is still empty.** A reservation that has bytes in it is no longer a
    reservation — it is somebody's file, and deleting it would be the data loss this whole
    policy exists to prevent. Size is the test rather than a flag, because the process that
    reserved it may have died between the two.

    Failure to clean up is not worth propagating: the download has already succeeded or failed
    on its own terms, and a stray zero-byte file is a much smaller problem than an exception
    raised from the path that reports the real outcome.
    """
    try:
        if reserved.stat().st_size == 0:
            reserved.unlink()
    except OSError:
        return


def as_literal_template(path: Path) -> str:
    """Escape `path` so yt-dlp writes it **verbatim** instead of rendering it again.

    The validated path is handed back to yt-dlp as its `outtmpl`, and `outtmpl` is a template:
    a title containing `%(uploader)s` survived sanitisation as literal text, then yt-dlp
    expanded it on the second pass and wrote a different file than the one that was validated
    and previewed (`T012-R4`). Containment was checked against a path that was never used.

    `%%` is yt-dlp's own escape for a literal percent, so this stays inside its template
    language rather than fighting it. The whole path is escaped, not just the filename: a user's
    download folder may legitimately contain a `%`.
    """
    return str(path).replace("%", "%%")


def audio_extension_for(codec: AudioCodec) -> str | None:
    """The container `FFmpegExtractAudio` produces for `codec`, or `None` if it cannot be known.

    **Read from yt-dlp's own `ACODECS` table, not restated here** (`T046-R4`). The codec is not the
    extension: `aac` and `alac` are both copied into **m4a**, and `vorbis` into **ogg**. A previous
    version used `codec.value` directly, which is right for `mp3`/`opus`/`flac`/`wav`/`m4a` and
    wrong for the other three — and being right most of the time is what makes a preview believed.

    **`ORIGINAL` returns `None`, and cannot be derived from the probe either.** "Keep the source
    codec" does not mean "keep the source container": yt-dlp copies AAC out of an `.mp4` into an
    `.m4a`, which is why a previewed `master.mp4` was written as `master.m4a` (`T046-R4`). It is
    tempting to read the codec from the probed `info_dict` instead — but `FFmpegExtractAudioPP.run`
    calls `get_audio_codec(path)`, which runs **ffprobe on the downloaded file**, and it also skips
    conversion entirely when the *downloaded* extension is already a common audio one. Both inputs
    exist only after the write. So this is genuinely unknowable in advance rather than merely
    unimplemented, and `preview_is_provisional` says so.

    Falls back to `None` for a codec yt-dlp's table does not carry, rather than guessing. A new
    `AudioCodec` member would then be previewed as provisional instead of confidently wrong.
    """
    if codec is AudioCodec.ORIGINAL:
        return None
    try:
        from yt_dlp.postprocessor.ffmpeg import ACODECS
    except ImportError:  # pragma: no cover - yt-dlp is a runtime dependency
        return None
    entry = ACODECS.get(codec.value)
    if not entry:
        return None
    extension = entry[0]
    return str(extension) if extension else None


def postprocessed_name(target: Path, request: DownloadRequest) -> Path:
    """`target` under the container the postprocessor chain will actually produce (`T046-R2`).

    **For the preview, and never for the claim.** `T046-R1` established that predicting the final
    name is not safe to *reserve* against — a wrong prediction overwrites somebody's file. It is
    the right thing to *display*: `%(ext)s` renders the pre-conversion container, so an MP3 request
    previewed `Clip.webm` and produced `Clip.mp3`, and `REQ-011` asks for a preview of the
    resulting path.

    Returns `target` unchanged whenever the container is not knowable — which
    `preview_is_provisional` reports, so the two always agree about which cases are exact.

    **A named container wins, and it is the last word** (`T-109`). `build_postprocessors` runs
    `FFmpegExtractAudio`, then the remuxer, then the convertor, so whichever container the request
    *names* is the one the file ends in — a recode to `mkv` after an MP3 extraction produces
    `.mkv`, not `.mp3`. `DownloadRequest` refuses to carry both a remux and a recode, so there is
    no third case to order.

    This is why the preview stopped being provisional for two whole classes of request: an
    `ORIGINAL` audio extraction and a merge are both unknowable *until* something names the
    container, and now something can.

    *(This paragraph used to read: "an arbitrary entry in `request.post_processors` that changes
    the container — a remux or recode — is not derivable from the request alone. Phase 2 exposes
    no such option; `REQ-010` and `T-109` own the general case." That was true of a list of
    postprocessor names, which carries no argument and so cannot say what container it wants.
    `ARC-010` typed the fields, and a typed field names it — which is the concrete thing typing
    them bought, beyond being checkable.)*
    """
    if request.recode_container is not None:
        return target.with_suffix(f".{request.recode_container}")
    if request.remux_container is not None:
        return target.with_suffix(f".{request.remux_container}")
    if request.media_kind is not MediaKind.AUDIO:
        return target
    extension = audio_extension_for(request.audio_codec)
    if extension is None:
        return target
    return target.with_suffix(f".{extension}")


def preview_is_provisional(request: DownloadRequest) -> bool:
    """Whether `preview_path`'s container can still change before the file lands (`T046-R2`).

    **`REQ-011` amended, 2026-08-01 (maintainer).** The requirement asks for a preview of *the
    resulting path*, and this module cannot honestly promise it for every request. `T-046`
    established that a prediction is unsafe to reserve against; the same honesty applies to showing
    it. So those previews are labelled rather than silently wrong, and the UI says *intended path*.

    Two classes cannot be known before the write:

    - **A merge.** yt-dlp picks the container itself. Detected by asking `core/presets` what counts
      as a merge rather than scanning for `+` — `mergeall` merges with no `+` in it at all
      (`T046-R5`), and a single token was the wrong shape of test for a syntax with more than one
      spelling.
    - **`ORIGINAL` audio.** "Keep the source codec" still extracts, and which container it lands in
      depends on the codec the download resolved to (`T046-R4`).

    Audio extraction to a **named** codec is exact: yt-dlp's `ACODECS` table names the container
    outright, and `audio_extension_for` reads it from the library.

    **A remux or a recode settles both classes** (`T-109`). Neither exception is about the request
    being unclear — it is about the *container* being yt-dlp's to choose. A request that names the
    container it wants takes that choice back, so a merge recoded to `mkv` and an `ORIGINAL`
    audio extraction remuxed to `m4a` are both exact. The check is first for that reason: it is
    not a special case of the two below, it is what removes them.
    """
    if request.recode_container is not None or request.remux_container is not None:
        return False
    if request.media_kind is MediaKind.AUDIO:
        return audio_extension_for(request.audio_codec) is None
    return selector_merges(request.format_selector)


def preview_path(request: DownloadRequest, info: dict[str, Any], resolved: ResolvedYtdlp) -> Path:
    """The path a download *would* write (`REQ-011`).

    Deliberately the same code as the real thing rather than a parallel implementation: a
    preview computed differently from the write is a preview that will eventually lie.

    **Including the extension a postprocessor will produce** (`T046-R2`). `_validated_target`
    renders `%(ext)s`, which is the *pre-conversion* container — so an MP3 request previewed
    `Clip.webm` and wrote `Clip.mp3`. The download claims the name it actually produced and never
    trusts this prediction; the preview's job is to be accurate about what the user will see.
    """
    from tracks_and_trails.downloader import ytdlp_adapter as adapter

    return previewed_path(
        _validated_target(Path(request.output_directory), request, adapter, resolved, info),
        request,
    )


def previewed_path(target: Path, request: DownloadRequest) -> Path:
    """`target` as the user will see it: the real container, and the collision already resolved.

    **Split out so the GUI's live preview is this code and not a copy of it** (`T-112`,
    `REQ-011`). `preview_path` above needs a real extraction and a resolved yt-dlp, neither of
    which exists in the parent process; everything after the render does not, and this is that
    part. `DownloadManager.preview_output_path` calls it with a target it produced through
    `contained_output_path` — the same function `_validated_target` ends on.

    Two steps, in this order and for `T-046`'s reasons. `postprocessed_name` puts the container the
    postprocessor chain will actually produce on the name, so an MP3 request does not preview
    `Clip.webm`; `free_output_path` then shows the numbered variant the write would take, because a
    resolution applied silently afterwards means the user is shown one filename and gets another.
    """
    return free_output_path(postprocessed_name(target, request))


def _extract(
    adapter: Any,
    request: DownloadRequest,
    resolved: ResolvedYtdlp,
    reporter: _Reporter,
    *,
    probe_only: bool,
    output_template: str | None = None,
    ffmpeg_location: Path | None = None,
    cookie_file: Path | None = None,
    cookie_browser: str | None = None,
    overwrites: bool | None = None,
) -> dict[str, Any]:
    from tracks_and_trails.core.logging import YtdlpLog, ytdlp_logger

    options = adapter.build_options(
        request,
        output_template if output_template is not None else request.output_template,
        probe_only=probe_only,
        progress_hooks=[reporter.progress_hook],
        postprocessor_hooks=[reporter.postprocessor_hook],
        ffmpeg_location=ffmpeg_location,
        cookie_file=cookie_file,
        cookie_browser=cookie_browser,
        overwrites=overwrites,
        # `REQ-019`. Built here rather than passed in from `spawn_session` because both the probe
        # and the download go through this function, and `REQ-019` wants *the* diagnostic output
        # for the job — a failure during the probe is the case a user most needs the log for.
        logger=YtdlpLog(ytdlp_logger()),
    )
    with resolved.module.YoutubeDL(options) as ydl:
        info = ydl.extract_info(request.url, download=not probe_only)
    return dict(info or {})


def _written_path(result: dict[str, Any], target: Path) -> Path:
    """Where the file actually landed.

    yt-dlp reports the real path in `requested_downloads`, which differs from the template
    target after a merge changes the container. Falling back to the target is honest rather
    than wrong: it is what we asked for.
    """
    downloads = result.get("requested_downloads") or ()
    for entry in downloads:
        filepath = entry.get("filepath") or entry.get("_filename")
        if filepath:
            return Path(str(filepath))
    filename = result.get("_filename")
    return Path(str(filename)) if filename else target


def _classify_without_ytdlp(error: BaseException) -> FailureDetail:
    """Classify a failure that happened before yt-dlp could be imported.

    `ytdlp_adapter` cannot help here — importing it would import yt-dlp, which is the thing
    that just failed. Kept deliberately small: this path exists so an unimportable yt-dlp
    reaches the parent as a classified failure rather than as a silent exit.
    """
    if isinstance(error, UnsafePathError):
        return FailureDetail(kind=ErrorKind.DISK, message=str(error))
    if isinstance(error, ImportError):
        return FailureDetail(
            kind=ErrorKind.EXTRACTOR_ERROR,
            message=f"yt-dlp could not be loaded: {error}",
        )
    if isinstance(error, OSError):
        return FailureDetail(kind=ErrorKind.DISK, message=str(error) or repr(error))
    return FailureDetail(
        kind=ErrorKind.EXTRACTOR_ERROR,
        message=str(error) or "".join(traceback.format_exception_only(error)).strip(),
    )


def _int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    return None


def _float_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return max(float(value), 0.0)


# Deliberately no `if __name__ == "__main__"` block and no module-level work below this point.
# See the module docstring: under `spawn` this module is re-imported in a fresh interpreter, and
# in a frozen build that interpreter is the application binary (`T-020`).
