"""A windowed build has no `stdout`, so the probes write their reports to a file too (`T-319`).

`REL-001`'s release artifact is built `console=False` — a user must not get a console window
behind the application — and on Windows that means the four probes CI depends on print into
nothing. `TT_PROBE_REPORT` is the same shape as `TT_PROBE_LOG` beside it rather than a fifth
mechanism: one variable, set by the caller, ignored when unset.

**The failure this prevents is a silent one.** A windowed build whose probes report nothing looks
exactly like a windowed build whose probes passed, and `frozen_smoke.py` reads a file precisely
because it cannot read a console that does not exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tracks_and_trails import _freeze_probe


def test_a_report_line_reaches_the_file_and_the_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both, never either — the console is what a person reads, the file is what CI reads."""
    report = tmp_path / "probe-report.txt"
    monkeypatch.setenv(_freeze_probe.PROBE_REPORT_ENV, str(report))

    _freeze_probe.say("extractors      1234")

    assert capsys.readouterr().out == "extractors      1234\n"
    assert report.read_text(encoding="utf-8") == "extractors      1234\n"


def test_a_failure_line_keeps_its_stream_and_still_reaches_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A `FAIL:` line goes to `stderr` as it always did, and to the file as well.

    Keeping the stream matters: CI and a person both read failures from `stderr`, and moving them
    would be a change to how every existing probe reports while claiming to add a file.
    """
    report = tmp_path / "probe-report.txt"
    monkeypatch.setenv(_freeze_probe.PROBE_REPORT_ENV, str(report))

    _freeze_probe.say("FAIL: nothing resolved", error=True)

    captured = capsys.readouterr()
    assert captured.err == "FAIL: nothing resolved\n"
    assert captured.out == ""
    assert "FAIL: nothing resolved" in report.read_text(encoding="utf-8")


def test_lines_accumulate_rather_than_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A probe reports several lines, and the last one is not the report."""
    report = tmp_path / "probe-report.txt"
    monkeypatch.setenv(_freeze_probe.PROBE_REPORT_ENV, str(report))

    for line in ("frozen           True", "child pid        4321", "OK: it worked"):
        _freeze_probe.say(line)

    assert report.read_text(encoding="utf-8").splitlines() == [
        "frozen           True",
        "child pid        4321",
        "OK: it worked",
    ]


def test_no_file_is_written_when_the_caller_asked_for_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Normal use sets nothing, and this must cost that path an environment lookup and no more."""
    monkeypatch.delenv(_freeze_probe.PROBE_REPORT_ENV, raising=False)

    _freeze_probe.say("frozen           False")

    assert capsys.readouterr().out == "frozen           False\n"
    assert list(tmp_path.iterdir()) == []


def test_an_unwritable_report_does_not_fail_the_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The report is evidence, not the probe's purpose.**

    A probe that failed because it could not write its own log would be reporting on the log. The
    console line still goes out, which is the half a person is reading when they notice.
    """
    monkeypatch.setenv(_freeze_probe.PROBE_REPORT_ENV, str(tmp_path / "no-such-dir" / "r.txt"))

    _freeze_probe.say("extractors      1234")

    assert capsys.readouterr().out == "extractors      1234\n"


def test_every_probe_reports_through_the_helper() -> None:
    """The scope's own rule: *"extend the pattern to all four rather than adding a fifth"*.

    A probe that kept a bare `print` would report nothing in a windowed build while its siblings
    reported normally — the hardest kind of gap to notice, because the file is not empty.
    """
    source = Path(_freeze_probe.__file__).read_text(encoding="utf-8")
    bare = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith("print(") and "file=sys.stderr if error" not in line
    ]
    assert not bare, f"probe output bypassing say(): {bare}"
