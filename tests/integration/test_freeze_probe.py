"""The frozen-artifact yt-dlp gate (`T-033`).

`run_ytdlp_probe()` is the only thing standing between a build that silently omits yt-dlp's
extractors and a release that launches, looks healthy, and fails every URL as if every site had
broken at once. It runs inside the artifact, so it can only be verified for real in CI — but
its *logic* can be verified here, and `T033-R2` is why that matters: the gate passed while the
artifact was in exactly the state it exists to reject.

Each test drives the probe in a **fresh interpreter**. The checks turn on which modules are
importable, and this interpreter has already imported yt-dlp and its extractors; anything
asserted in-process would be asserting about the test runner's state rather than the gate's.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]


def run_probe_with(preamble: str) -> subprocess.CompletedProcess[str]:
    """Run the probe in a clean interpreter, after `preamble` has rearranged the environment."""
    script = textwrap.dedent(preamble) + textwrap.dedent(
        """
        import sys

        from tracks_and_trails._freeze_probe import run_ytdlp_probe

        sys.exit(run_ytdlp_probe())
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    )


def test_the_probe_passes_against_a_correctly_installed_ytdlp() -> None:
    """The positive case, so a probe that failed unconditionally could not pass for it."""
    result = run_probe_with("")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK:" in result.stdout


BLOCK_THE_REAL_EXTRACTOR = """
    import sys

    BLOCKED = "yt_dlp.extractor.youtube"


    class Blocker:
        def find_spec(self, name, path=None, target=None):
            if name == BLOCKED or name.startswith(BLOCKED + "."):
                raise ModuleNotFoundError(f"deliberately blocked: {name}")
            return None


    sys.meta_path.insert(0, Blocker())
    for module in [m for m in sys.modules if m == BLOCKED or m.startswith(BLOCKED + ".")]:
        del sys.modules[module]
"""


def test_a_missing_extractor_module_fails_the_gate() -> None:
    """`T033-R2`, reproduced. **This is the defect the gate exists to catch, and it passed.**

    `get_info_extractor("Youtube")` returns a class from `yt_dlp.extractor.lazy_extractors` — a
    generated stub table that imports no extractor code whatsoever. With the real
    `yt_dlp.extractor.youtube` unimportable, the probe reported 1751 extractors, "resolved
    youtube", and exit 0, while actually using that extractor raised `ModuleNotFoundError`.

    An artifact in exactly that state ships, launches, and fails every YouTube URL — which is
    indistinguishable, from the user's side, from YouTube having changed. The gate now
    instantiates the class, because instantiation is what makes the lazy placeholder load the
    concrete module.
    """
    result = run_probe_with(BLOCK_THE_REAL_EXTRACTOR)

    assert result.returncode == 1, (
        "the probe passed while the real extractor module was unimportable — "
        f"stdout:\n{result.stdout}"
    )
    assert "lazy extractor table" in result.stderr


def test_the_failure_names_the_packaging_cause() -> None:
    """`OPS-003`: a Windows failure is diagnosed from this log and nothing else.

    `ModuleNotFoundError: yt_dlp.extractor.youtube` does not tell a maintainer that the build
    dropped the extractors — the earlier version of this gate let exactly that escape as a bare
    traceback.
    """
    result = run_probe_with(BLOCK_THE_REAL_EXTRACTOR)

    assert "FAIL:" in result.stderr
    assert "T-033" in result.stderr
    assert "Traceback" not in result.stderr, "the diagnostic escaped as an unhandled exception"


@pytest.mark.parametrize(
    ("pin", "expected"),
    [("2026.7.4", 0), ("2019.1.1", 1)],
)
def test_the_gate_checks_the_bundled_version_against_the_pin(pin: str, expected: int) -> None:
    """`T033-R1`. Parametrised over both outcomes so neither branch can rot unnoticed."""
    result = run_probe_with(
        f"""
        import tracks_and_trails.downloader.environment as env

        env.BASELINE_YTDLP_VERSION = {pin!r}
        """
    )

    assert result.returncode == expected, result.stdout + result.stderr


def test_an_extractor_that_stays_lazy_fails_the_gate() -> None:
    """The belt-and-braces half of `T033-R2`.

    Instantiation is what normally forces the concrete import, so the check that the result is
    no longer a `lazy_extractors` class is redundant *for the blocking scenario above*. It is
    not redundant in general: a class that constructs successfully while remaining the
    generated stub would satisfy every other check here and still carry no extractor code.

    Written because deleting that check survived the suite — the mutation was reporting a
    missing test, not dead code (`ai/TESTING.md` §13).
    """
    result = run_probe_with(
        """
        import yt_dlp.extractor

        from yt_dlp.extractor import lazy_extractors


        class StillLazyIE:
            IE_NAME = "youtube"
            __module__ = lazy_extractors.__name__

            @staticmethod
            def suitable(url):
                return "youtube.com" in url


        yt_dlp.extractor.get_info_extractor = lambda name: StillLazyIE
        """
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "lazy placeholder" in result.stderr


def test_an_extractor_that_does_not_match_its_own_urls_fails_the_gate() -> None:
    """The other survivor: an extractor present, loaded, and useless.

    A concrete module whose URL predicate no longer matches is not the artifact this build
    claims to ship — every URL would fall through to "unsupported" rather than to the
    extractor that exists. Exercised offline; the probe never fetches anything.
    """
    result = run_probe_with(
        """
        import yt_dlp.extractor.youtube

        yt_dlp.extractor.youtube.YoutubeIE.suitable = staticmethod(lambda url: False)
        """
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "does not match its own URL pattern" in result.stderr


def test_an_extractor_that_claims_every_url_fails_the_gate() -> None:
    """The negative half of the predicate check, which the positive half cannot supply.

    An extractor whose `suitable()` always returns `True` passes "does it match its own URL?"
    while telling us nothing — and would, in a real artifact, hijack every URL from the
    extractor that should handle it. Dropping the unrelated-URL half of the check survived the
    suite until this existed.
    """
    result = run_probe_with(
        """
        import yt_dlp.extractor.youtube

        yt_dlp.extractor.youtube.YoutubeIE.suitable = staticmethod(lambda url: True)
        """
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "does not match its own URL pattern" in result.stderr
