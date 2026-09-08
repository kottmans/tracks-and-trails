"""`T-128` probe — NOT a test, and deliberately not in `tests/` (`T128-R2`).

Run by hand:

    QT_QPA_PLATFORM=offscreen .venv/bin/python \
        docs/project/evidence/T128-cross-thread-timer-probe.py

**Why this is not in the suite.** It works by leaving an orphaned timer registered against freed
memory, which arms a use-after-free *in the process running it* — the process then segfaults, which
is the point. Inside `pytest` that would take the run with it and the autouse detector would fail
every test after. Kept here so the claim it supports is reproducible rather than asserted.

Observed 2026-08-04, three runs of three:

    QObject::killTimer: Timers cannot be stopped from another thread
    QObject::~QObject: Timers cannot be stopped from another thread
    Segmentation fault

and `gdb` on the resulting core gives the same frames as the two soak cores —
`notifyInternal2+0x32`, `activateTimers+0x59a`, the same glib dispatch.
"""

import gc
import sys
import threading
import time

from PySide6.QtCore import QCoreApplication, QObject, QTimer, qInstallMessageHandler

app = QCoreApplication([])

warnings: list[str] = []


def collect_warning(msg_type, context, message):
    warnings.append(str(message))
    print(f"  Qt says: {message}", file=sys.stderr)


qInstallMessageHandler(collect_warning)


class Owner(QObject):
    """A QObject that owns a repeating timer, exactly as DownloadManager does."""

    def __init__(self) -> None:
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.tick)
        self.ticks = 0

    def tick(self) -> None:
        self.ticks += 1


owner = Owner()
owner.timer.start()
for _ in range(50):
    app.processEvents()
    time.sleep(0.001)
print(f"timer is delivering on the main thread: ticks={owner.ticks}")

# Make it collectable only through the cycle collector, as a real one is: the connection to a
# bound method is a cycle through the QTimer child.
holder = [owner]
del owner
gc.collect()

done = threading.Event()


def drop_it_from_another_thread() -> None:
    """Release the last reference and collect — on a thread that is not the timer's."""
    holder.clear()
    gc.collect()
    done.set()


worker = threading.Thread(target=drop_it_from_another_thread, name="ResultPump")
worker.start()
done.wait(5)
worker.join()

print(f"\nQt warnings during the cross-thread drop: {warnings or '(none)'}")
print("now pumping the main loop, which is where activateTimers() runs...")
for _ in range(200):
    app.processEvents()
    time.sleep(0.001)
print("survived the pump")
