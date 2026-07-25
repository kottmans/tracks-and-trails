"""Pure domain layer: no Qt, no yt-dlp, no I/O beyond the standard library.

Must remain importable in a headless child process. Enforced by
tests/unit/test_layering.py (ARCHITECTURE.md §4)."""
