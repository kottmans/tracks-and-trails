"""Job status enum and the state machine.

Illegal transitions raise rather than silently corrupting state: a persisted queue
that lies about its state is worse than a crash (ARCHITECTURE.md §5)."""
