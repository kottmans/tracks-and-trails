"""SQLite persistence for jobs and queue order (DAT-001).

Jobs are all of it. There is no record of completed downloads: `REQ-020` was withdrawn on
2026-08-06 and migration `0009` dropped the table it had lived in.
"""
