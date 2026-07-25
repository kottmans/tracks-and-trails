"""QThread that drains the multiprocessing result queue and re-emits Qt signals.

The single bridge from worker processes to the GUI thread (ARCHITECTURE.md §3)."""
