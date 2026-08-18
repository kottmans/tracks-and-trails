"""Say how close a job ran to its own timeout, while the margin is still a margin (`T-259`).

`T-259` is `T118-R10` one level up. A bound sitting just above measured runtime does not fail on
faults; it fails on **growth**, and it fails by looking like a hang. The `windows desktop` job had
four minutes of headroom on a 30-minute bound for its whole recorded history, and 154 new tests
walked it through the wall — two consecutive runs died at 30.3 minutes, reported by GitHub as
`cancelled`, which is why the first one looked like somebody had stopped it.

Raising the bound to 40 fixed that run. It does not stop the next one, because nothing was
watching the margin: recovering it meant comparing durations across runs afterwards, by hand, which
is exactly what nobody did for the four healthy runs before the wall.

**So this prints the margin into the log, and warns before the bound is reached.** Elapsed, the
bound, what is left, and the percentage used — then a `::warning::` once the run crosses
`--warn-at-percent`.

## Why 85% and not the margin the job actually has

The warning has to fire early enough to be creep and late enough not to cry wolf. At the 2026-08-17
measurement the job took 32 minutes against 40 — **80% used, 8 minutes clear**. A threshold set at
the observed margin would sit on top of that measurement and flap on how fast the runner feels that
morning, which is `T118-R10`'s defect reproduced inside its own fix.

85% is 34 minutes: two minutes clear of the healthy run, six minutes of warning before the bound.
The growth step that broke the 30-minute bound cost about six minutes, so the window is roughly one
such step of notice — one red-free run in which to act.

## This never fails the job

It exits 0 on every path, including the ones where it cannot do its work at all — an unparseable
stamp, a missing stamp, a clock that went backwards. A reporter that fails the gate turns *slow*
into *broken*, and `T-259` asks for the opposite: the creep visible while the run is still green.
The one thing it must not do is stay quiet, so every giving-up path says so in a `::warning::`
rather than by printing nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

#: Emitted for the cases this cannot report on. GitHub renders `::warning::` in the run summary,
#: which is the whole point: a stamp this could not read is itself something to look at, and a
#: silent reporter is indistinguishable from one that was never wired up.
WARNING = "::warning::"


def parse_timestamp(text: str) -> datetime | None:
    """The instant `text` names, or `None` if it names none.

    Accepts what PowerShell 5.1's `[datetime]::UtcNow.ToString('o')` writes — an ISO-8601 round-trip
    string with seven fractional digits and a `Z` suffix. `datetime.fromisoformat` handles `Z` from
    3.11 and arbitrary fractional precision from 3.13; this project pins 3.14, so neither needs
    working around. A stamp with no timezone is read as UTC, because the only writer stamps UTC.
    """
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def report(
    started_at: str,
    now: datetime,
    bound_minutes: float,
    warn_at_percent: float,
) -> list[str]:
    """The lines to print. Never raises; a case it cannot measure becomes a warning line."""
    started = parse_timestamp(started_at)
    if started is None:
        return [
            f"{WARNING}Job duration not reported: the start stamp "
            f"{started_at.strip()!r} is not a timestamp this could read. The margin against the "
            f"{bound_minutes:g}-minute bound is unknown for this run."
        ]

    elapsed_minutes = (now - started).total_seconds() / 60
    if elapsed_minutes < 0:
        return [
            f"{WARNING}Job duration not reported: the start stamp is "
            f"{abs(elapsed_minutes):.1f} minutes in the future, so the clock moved during the run. "
            f"The margin against the {bound_minutes:g}-minute bound is unknown."
        ]

    remaining = bound_minutes - elapsed_minutes
    used_percent = (elapsed_minutes / bound_minutes) * 100 if bound_minutes else 100.0

    lines = [
        f"Elapsed:   {elapsed_minutes:.1f} min",
        f"Bound:     {bound_minutes:g} min (timeout-minutes)",
        f"Remaining: {remaining:.1f} min",
        f"Used:      {used_percent:.0f}% of the bound",
    ]

    if used_percent >= warn_at_percent:
        lines.append(
            f"{WARNING}This job used {used_percent:.0f}% of its {bound_minutes:g}-minute bound "
            f"({elapsed_minutes:.1f} min, {remaining:.1f} min left), at or past the "
            f"{warn_at_percent:g}% mark. T-259: a bound is crossed by growth, not by faults. "
            f"Re-measure before raising it, and record the measurement."
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--started-at", required=True, help="ISO-8601 instant the job began")
    parser.add_argument(
        "--bound-minutes",
        required=True,
        type=float,
        help="the job's timeout-minutes; `tests/unit/test_job_duration_report.py` pins that the "
        "value passed in CI is the one the job actually carries",
    )
    parser.add_argument("--warn-at-percent", type=float, default=85.0)
    parser.add_argument("--now", default=None, help="override the clock; for tests")
    parser.add_argument("--report", type=Path, default=None, help="also write the lines here")
    args = parser.parse_args(argv)

    now = parse_timestamp(args.now) if args.now else datetime.now(UTC)
    if now is None:
        # `--now` is ours, not the runner's, so an unreadable one is a bug in the caller rather
        # than a condition to report around.
        parser.error(f"--now is not a timestamp: {args.now!r}")

    lines = report(args.started_at, now, args.bound_minutes, args.warn_at_percent)
    text = "\n".join(lines)
    print(text)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
