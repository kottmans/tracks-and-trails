"""The running application holds the mutex the Windows uninstaller looks for (`T322-R3`)."""

import sys

import pytest

from tracks_and_trails.core import app_mutex


@pytest.mark.skipif(sys.platform == "win32", reason="the Windows half is asserted below")
def test_nothing_is_created_where_no_installer_looks() -> None:
    assert app_mutex.hold_running_mutex() is False


@pytest.mark.skipif(sys.platform != "win32", reason="a named mutex is a Windows object")
def test_another_process_can_find_the_mutex_while_this_one_runs() -> None:  # pragma: no cover
    """What Inno does: open the name. `OpenMutexW` succeeds only while some process holds it."""
    import subprocess

    assert app_mutex.hold_running_mutex() is True
    assert app_mutex.hold_running_mutex() is True, "a second call must not fail or leak"

    def found(name: str) -> bool:
        probe = (
            "import ctypes, sys\n"
            "from ctypes import wintypes\n"
            "k = ctypes.WinDLL('kernel32', use_last_error=True)\n"
            "k.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)\n"
            "k.OpenMutexW.restype = wintypes.HANDLE\n"
            f"sys.exit(0 if k.OpenMutexW(0x00100000, False, {name!r}) else 1)\n"
        )
        return subprocess.run([sys.executable, "-c", probe], check=False).returncode == 0

    assert found(app_mutex.APP_MUTEX_NAME), "another process could not see the application's mutex"
    # The probe's positive control: a name nobody holds is not found.
    assert not found("TracksAndTrails.NotThisName")
