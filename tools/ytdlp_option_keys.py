"""Which option-dictionary keys does each yt-dlp option change? (`T-184`, `NFR-008`)

`parse_options(argv)` returns the dictionary `YoutubeDL` would be constructed with, so parsing an
empty argv gives the defaults and **the diff is what the option did**. That is the thing
`docs/YTDLP_OPTION_AUDIT.md`'s Finding 4 says the escape hatch must decide on: the normalized
value, not the option string and not the parser's `dest`.

Run it when the pin moves (`NFR-008`) or when the hatch's permitted set is in question:

    PYTHONPATH=tools python -m ytdlp_option_keys            # the summary
    PYTHONPATH=tools python -m ytdlp_option_keys --json out.json

**Nothing here is policy.** It reports, in three groups that each mean something different to the
hatch:

- **changes keys** — the option has an effect the hatch could merge.
- **changes nothing** — the option's value is already the default. `--geo-bypass` is here, and it
  is why a hatch that decides from the diff alone would be blind to the one option Finding 4 is
  about: the behaviour `SEC-003` forbids is **on by default**, so naming it changes no key.
- **cannot be parsed alone** — the value has to mean something (`--xff`, `--color`,
  `--compat-options`), or the option exits the process (`-h`, `--version`).

Values are supplied per optparse type rather than per option name, so an option whose value cannot
be guessed is reported rather than silently skipped.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from optparse import SUPPRESS_HELP, Option
from pathlib import Path
from typing import Any

from yt_dlp import parse_options
from yt_dlp.options import create_parser

#: A value per optparse type, chosen so the parse succeeds rather than so it means anything.
BY_TYPE: dict[str, str] = {"int": "1", "float": "1", "string": "x"}


def quietly(argv: list[str]) -> dict[str, Any]:
    """`parse_options`, with its usage text kept out of this program's own output."""
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        return dict(parse_options(argv).ydl_opts)


def argv_for(option: Option) -> list[str]:
    """The shortest argv that exercises `option`, with a value if it takes one."""
    string = (option._long_opts or option._short_opts)[0]
    if not option.takes_value():
        return [string]
    if option.type == "choice":
        value = (option.choices or ("x",))[0]
    else:
        value = BY_TYPE.get(option.type or "string", "x")
    return [string, *[value] * max(1, option.nargs or 1)]


def survey() -> list[dict[str, Any]]:
    """Every option the parser carries, with the keys it changes or the reason it could not run."""
    base = quietly([])
    rows: list[dict[str, Any]] = []
    for group in create_parser().option_groups:
        for option in group.option_list:
            row: dict[str, Any] = {
                "strings": list(option._short_opts) + list(option._long_opts),
                "dest": option.dest,
                "documented": option.help is not SUPPRESS_HELP and option.help is not None,
            }
            try:
                produced = quietly(argv_for(option))
            # Every failure shape is data here, `SystemExit` from `--help` included.
            except BaseException as error:
                message = str(error).strip().splitlines()
                row["outcome"] = type(error).__name__
                row["detail"] = message[-1][:100] if message else ""
                rows.append(row)
                continue
            row["outcome"] = "parsed"
            row["keys"] = sorted(
                key for key in produced if key not in base or repr(produced[key]) != repr(base[key])
            )
            rows.append(row)
    return rows


def report(rows: list[dict[str, Any]]) -> None:
    parsed = [row for row in rows if row["outcome"] == "parsed"]
    refused_by_the_parser = [row for row in rows if row["outcome"] != "parsed"]
    inert = [row for row in parsed if not row["keys"]]
    several = [row for row in parsed if len(row["keys"]) > 1]

    print(f"parser options: {len(rows)}")
    print(f"  changes keys:            {len(parsed) - len(inert)}")
    print(f"  changes nothing:         {len(inert)}")
    print(f"  cannot be parsed alone:  {len(refused_by_the_parser)}")
    print(f"  changes more than one:   {len(several)}")

    print("\n-- changes nothing, so a diff cannot see it")
    for row in inert:
        print(f"   {'/'.join(row['strings']):44} dest={row['dest']}")

    print("\n-- changes more than one key")
    for row in several:
        print(f"   {'/'.join(row['strings']):44} -> {row['keys']}")

    print("\n-- cannot be parsed alone")
    for row in refused_by_the_parser:
        print(f"   {'/'.join(row['strings']):44} {row['outcome']}: {row.get('detail', '')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write every row to this file as JSON")
    arguments = parser.parse_args()

    rows = survey()
    report(rows)
    if arguments.json:
        arguments.json.write_text(json.dumps(rows, indent=1, default=repr), encoding="utf-8")
        print(f"\nwrote {arguments.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
