"""The ffmpeg capability's two answers, and which run gets which (`T-189`, `T-070`).

`tests/capabilities.py` decides whether a machine without ffmpeg **skips** a conversion test or
**fails** it. Both answers are correct and they belong to different runs: a developer's checkout
skips with a reason they can act on, and the CI jobs carrying `T-108`'s cross-platform merge proof
fail, because there a missing tool means exit criterion 2 is evidenced by nothing.

**Why this file exists at all.** The defect `T-189` names is not a wrong answer — it is a *silent*
one. `test_a_chosen_video_and_audio_pair_produce_one_merged_file` is a required end-to-end case, and
before this it took a fixture that skips, on a self-hosted Windows runner that *records* ffmpeg
rather than installing it. The day that machine loses the tool, the proof becomes a `SKIPPED` line
inside a green job and nothing goes red. A test that only ever runs where the tool is present cannot
observe that, so the decision is asserted here directly rather than inferred from a CI run nobody
can reproduce locally.

No Qt and no network. This module is `tests/` reading its own helper.
"""

import pytest

from tests.capabilities import (
    FFMPEG_REQUIRED_BUT_MISSING,
    NO_FFMPEG,
    REQUIRE_FFMPEG_VAR,
    ffmpeg_is_required,
    ffmpeg_tools,
    resolve_ffmpeg,
)

# --- which run requires the tool -----------------------------------------------------------


def test_an_ordinary_run_does_not_require_ffmpeg() -> None:
    """The default is the developer's: absent tools skip, and the suite still runs (`T-070`)."""
    assert ffmpeg_is_required({}) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "anything"])
def test_the_variable_being_set_requires_it(value: str) -> None:
    """A workflow writing `1`, `true` or `yes` all mean the same thing.

    Permissive on purpose: the failure mode being guarded against is a CI job that *meant* to
    require the tool and did not, so an unrecognised-but-present value must not read as "off".
    """
    assert ffmpeg_is_required({REQUIRE_FFMPEG_VAR: value}) is True


@pytest.mark.parametrize("value", ["", "   ", "0", "false", "FALSE", "no", "off"])
def test_an_explicit_negative_does_not_require_it(value: str) -> None:
    """Someone who exported the variable as `0` to turn this **off** must not turn it on.

    The empty string is here for the same reason: `env: FOO: ""` in a workflow is a variable that
    exists and says nothing, and treating presence alone as truth would make it impossible to
    disable this on a job that inherits it.
    """
    assert ffmpeg_is_required({REQUIRE_FFMPEG_VAR: value}) is False


def test_the_environment_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read per call rather than captured at import, which is what makes the gate observable.

    A module-level constant would freeze whatever the environment held when `pytest` started, so
    the probe below could not change the answer and `T-189`'s "a deterministic probe makes the gate
    fail" criterion would be untestable.
    """
    monkeypatch.delenv(REQUIRE_FFMPEG_VAR, raising=False)
    assert ffmpeg_is_required() is False

    monkeypatch.setenv(REQUIRE_FFMPEG_VAR, "1")
    assert ffmpeg_is_required() is True


# --- the gate itself, probed by hiding the tool ---------------------------------------------


def _hide_ffmpeg(monkeypatch: pytest.MonkeyPatch, *, required: bool) -> None:
    """Put this process on a machine with no ffmpeg, equipped however the caller asks.

    **`PATH` is emptied rather than the tools mocked.** `ffmpeg_tools` asks `shutil.which`, so
    hiding the executable is the same question a runner that lost the tool will ask — which is what
    makes this the *deterministic probe* `T-189`'s fourth criterion requires, rather than a stub
    that agrees with the code by construction.
    """
    monkeypatch.setenv("PATH", "")
    if required:
        monkeypatch.setenv(REQUIRE_FFMPEG_VAR, "1")
    else:
        monkeypatch.delenv(REQUIRE_FFMPEG_VAR, raising=False)


def test_a_developer_machine_without_ffmpeg_skips_with_an_actionable_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**`T-189`'s second criterion.** The helpful local skip survives the change.

    Asserted on the reason as well as the outcome, because a skip whose message does not name the
    tool reads as a broken checkout — which is the whole of `T-070`'s argument for this module.
    """
    _hide_ffmpeg(monkeypatch, required=False)

    with pytest.raises(pytest.skip.Exception) as skipped:
        resolve_ffmpeg()

    assert "ffmpeg" in str(skipped.value)
    assert str(skipped.value) == NO_FFMPEG


def test_hiding_ffmpeg_from_a_required_run_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**`T-189`'s first and fourth criteria**, which are one assertion: the probe makes it red.

    This is the case that did not exist. Before it, a runner losing ffmpeg produced a skip inside a
    passing job — so the gate that proves exit criterion 2 on both platforms could evaporate with
    nothing to show for it. **Fails rather than skips, and the distinction is the whole task.**

    **The `try` is not stylistic, and the first version of this test got it wrong.** Written as
    `pytest.raises(pytest.fail.Exception)`, a regression to skipping raises `Skipped`, which
    `raises` does not catch — so it propagates and **turns this test into a skip**. Mutating the
    fail branch away left the suite reporting `18 passed, 1 skipped` and nothing red. That is the
    exact shape `T-189` exists to close, reproduced inside the test written to close it: an
    assertion that silently stops asserting is worse than no assertion, because it still looks
    like coverage.
    """
    _hide_ffmpeg(monkeypatch, required=True)

    try:
        resolve_ffmpeg()
    except pytest.fail.Exception as failure:
        assert REQUIRE_FFMPEG_VAR in str(failure)
    except pytest.skip.Exception as skipped:  # pragma: no cover - the regression this guards
        pytest.fail(
            "a required run SKIPPED instead of failing when ffmpeg was hidden — the defect "
            f"T-189 closes. The skip said: {skipped}"
        )
    else:  # pragma: no cover - only reachable if the tool was not actually hidden
        pytest.fail("a required run with no ffmpeg on PATH neither failed nor skipped")


def test_the_tools_are_returned_untouched_when_they_are_present() -> None:
    """The anti-vacuity half: on a machine that has ffmpeg, neither branch fires.

    Without this, deleting `resolve_ffmpeg`'s `return` and leaving only the two raises would keep
    both cases above green while breaking every conversion test in the suite.
    """
    if ffmpeg_tools() is None:
        pytest.skip("this machine has no ffmpeg; the present-tools branch cannot be observed here")

    assert resolve_ffmpeg() == ffmpeg_tools()


def test_the_refusal_says_it_is_a_provisioning_failure_not_a_test_defect() -> None:
    """Whoever meets this message is looking at a runner, not at the suite.

    Worth asserting rather than trusting to prose: the reader arrives at a red required job and the
    first question is whether the code broke. `OPS-005` is why nothing installs the tool for them.
    """
    message = FFMPEG_REQUIRED_BUT_MISSING.format(var=REQUIRE_FFMPEG_VAR)

    assert REQUIRE_FFMPEG_VAR in message
    assert "provisioning failure" in message
    assert "T-189" in message
