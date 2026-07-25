"""The parent/child IPC contract.

Every object crossing the process boundary is a picklable dataclass declared here.
Raw yt-dlp info dicts are never sent; they are projected first (ARC-002)."""
