"""Tracks & Trails -- a desktop GUI for yt-dlp.

Layer map (ARCHITECTURE.md §4). Dependencies point downward only:

    ui/            Qt widgets and view models.  Must not import yt_dlp.
    downloader/    Process pool, IPC, worker entry point, yt-dlp adapter.
    persistence/   SQLite repositories, schema, migrations.
    core/          Domain models, state machine, settings, paths.  Must not import Qt.

Both rules are enforced by tests/unit/test_layering.py, not by convention.
"""

__version__ = "0.1.0.dev0"

__all__ = ["__version__"]
