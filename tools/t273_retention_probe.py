"""What retains the composed window after its own shutdown (`T-273`)?

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t273_retention_probe.py

Composes, shuts down, waits for `OrderlyShutdown.finished`, then asks what still refers to the
`MainWindow`.

**Every measurement happens inside a function, and that is the point rather than style.** `T-273`
records an earlier attribution *"contaminated by the diagnostic's own lists"*, and the first
version of this probe reproduced it exactly: run at module level, its own loop variables became
module globals and therefore referrers, and it reported `module` as a holder of the window. A
probe whose locals outlive its frame is measuring itself.

**What it establishes and what it does not** — see `T-273`'s entry. It names the Python edges; the
final anchor is on the Qt side and is not named here.
"""

import gc
import os
import sys
import time
import weakref

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path, PurePath
from tempfile import TemporaryDirectory

from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application
from tracks_and_trails.downloader.ytdlp_service import YtdlpService


class _QuietYtdlp(YtdlpService):
    def __init__(self) -> None:
        super().__init__(directory=Path("/nonexistent-in-probes"))

    def refresh(self) -> None: ...


def compose_and_shut(qapp, tmp):
    c = application.compose(
        qapp,
        database=tmp / "q.sqlite3",
        output_directory=tmp / "d",
        geometry_file=tmp / "w.toml",
        settings_file=tmp / "s.toml",
        cache_directory=tmp / "c",
        entry_point=lambda *a, **k: None,
        ytdlp_service=_QuietYtdlp(),
    )
    c.window.show()
    qapp.processEvents()
    watch = weakref.ref(c.window)
    c.shutdown.begin()
    end = time.monotonic() + 10
    while not c.shutdown.finished and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.02)
    return watch


def describe(o):
    t = type(o).__name__
    if isinstance(o, dict):
        for owner in gc.get_referrers(o):
            if getattr(owner, "__dict__", None) is o:
                return f"__dict__ of {type(owner).__name__}"
        return f"dict[{len(o)}]"
    if t == "cell":
        return "closure cell"
    if t == "method":
        return f"method {getattr(o, '__qualname__', '?')}"
    if t == "function":
        return f"function {getattr(o, '__qualname__', '?')}"
    if t in ("list", "tuple", "set"):
        return f"{t}[{len(o)}]"
    if t == "frame":
        return f"frame {o.f_code.co_name} ({PurePath(o.f_code.co_filename).name})"
    return t


def report(watch):
    w = watch()
    if w is None:
        print("  window was released")
        return
    here = sys._getframe()
    refs = [
        r
        for r in gc.get_referrers(w)
        if r is not here and r is not here.f_locals and not isinstance(r, type(here))
    ]
    counts = {}
    for r in refs:
        counts[describe(r)] = counts.get(describe(r), 0) + 1
    print(f"  referrers: {len(refs)}")
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"    {n:3}  {k}")

    print("\n  each closure cell belongs to:")
    for r in refs:
        if type(r).__name__ != "cell":
            continue
        for f in gc.get_referrers(r):
            if type(f).__name__ == "tuple":
                for fn in gc.get_referrers(f):
                    if getattr(fn, "__closure__", None) is f:
                        code = fn.__code__
                        print(
                            f"    {fn.__qualname__}  ({PurePath(code.co_filename).name}"
                            f":{code.co_firstlineno})"
                        )
    print("\n  the bound method is held by:")
    for r in refs:
        if type(r).__name__ != "method":
            continue
        for d in gc.get_referrers(r):
            if isinstance(d, dict):
                for host in gc.get_referrers(d):
                    if getattr(host, "__dict__", None) is d:
                        keys = [k for k, v in d.items() if v is r]
                        print(f"    {type(host).__name__}.{keys[0] if keys else '?'}")


def main():
    qapp = QApplication(sys.argv)
    with TemporaryDirectory() as raw:
        watch = compose_and_shut(qapp, Path(raw))
        for _ in range(3):
            gc.collect()
            qapp.processEvents()

        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        gc.set_debug(0)
        parked = gc.garbage
        target = watch()
        print("gc DEBUG_SAVEALL: unreachable objects parked:", len(parked))
        print("  window among them (i.e. gc calls it garbage):", any(o is target for o in parked))
        del target, parked
        gc.garbage.clear()
        gc.collect()
        print("after shutdown, no module-level names held:")
        print("  window alive:", watch() is not None)
        print("  live QWidgets:", len(QApplication.allWidgets()))
        print("  gc.garbage:", len(gc.garbage))
        report(watch)

        from PySide6.QtCore import QObject

        alive = {}
        for o in gc.get_objects():
            if isinstance(o, QObject):
                alive[type(o).__name__] = alive.get(type(o).__name__, 0) + 1
        print("\n  live QObjects by type (top 12):")
        for k, n in sorted(alive.items(), key=lambda kv: -kv[1])[:12]:
            print(f"    {n:4}  {k}")
        print("  total live QObjects:", sum(alive.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
