"""Qt tests run without a display.

`TESTING.md` §10 and `T-006` both require the UI suite to pass headless on Linux and Windows
CI runners. Setting the platform here rather than relying on the caller's environment means a
plain `pytest` reproduces what CI does.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
