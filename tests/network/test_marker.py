"""Placeholder proving the `network` marker exists and is excluded by default.

Real network tests arrive with T-018. Until then this test's only job is to be *skipped* by a
bare `pytest` run and *collected* by `pytest -m network` -- which is exactly T-001's
acceptance criterion for the marker configuration (TESTING.md §2).
"""

import socket

import pytest


@pytest.mark.network
def test_network_marker_is_opt_in() -> None:
    """Trivially touches the network so that mis-marking it would be obvious."""
    socket.getaddrinfo("pypi.org", 443)
