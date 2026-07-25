"""Locates yt-dlp and ffmpeg, reports versions, and installs user yt-dlp updates.

Updates extract a wheel into a user directory rather than using pip: released builds
are frozen and have no pip (OPS-002, REL-001)."""
