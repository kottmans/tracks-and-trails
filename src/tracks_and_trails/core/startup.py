"""The one timestamp `NFR-002` is measured against (`T-325`).

**In `core/` because `ui/` has to call it.** `ARCHITECTURE.md` §4 points dependencies downward
only, and the first version of this put the recorder in `_freeze_probe` — a root module — with
`ui/main_window.py` importing it. `tests/unit/test_layering.py` refused that, correctly: a window
reaching into the freeze-probe harness is exactly the sideways dependency the rule exists to
prevent. What the window needs is a timestamp, which is core's kind of thing.

**The other half of the measurement is not here.** `tools/startup_time.py` takes wall clock before
spawning the artifact; this records when the window reached the screen. The delta between two
clocks on one machine is what a user experiences, and neither end is a human with a stopwatch —
which is what `T-325` asks for in terms.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

#: Names a file the application writes **one** line to when its window first reaches the screen.
#: Unset in every ordinary launch, and then this costs one `os.environ` read.
#:
#: The same shape as `_freeze_probe`'s `TT_PROBE_LOG` and `TT_PROBE_REPORT` rather than a fourth
#: mechanism: one variable, set by the caller, ignored when absent.
STARTUP_REPORT_ENV = "TT_STARTUP_REPORT"


def record_first_paint() -> None:
    """Record that the window is on screen, once, with a wall-clock timestamp.

    **Wall clock rather than `monotonic`**, deliberately: two processes have to compare it, and
    `monotonic` has no shared epoch.

    **Called when the compositor says the surface is being shown**, not from `showEvent`. `T-325`
    asks for *first paint*, and `showEvent` fires before the window exists on screen — on Wayland
    the widget is never told at all, which is `T287-R1`. The exposure watch that finding installed
    is the signal, so this rides it rather than adding a second notion of *visible*.

    **Once.** Exposure fires again on every unminimize, and a file with five timestamps in it
    would not say which was the launch.
    """
    destination = os.environ.get(STARTUP_REPORT_ENV)
    if not destination:
        return
    path = Path(destination)
    try:
        if path.exists():
            return
        path.write_text(f"first-paint {time.time():.6f}\n", encoding="utf-8")
    except OSError:
        # A measurement that cannot be written is not a launch that should fail — `T-319`'s rule
        # for the probe report, followed here.
        pass
