"""The generated option table against the audit that authors it (`T-184`, `REQ-031`).

`docs/YTDLP_OPTION_AUDIT.md` is the authority for what every yt-dlp option is and why. The product
cannot read it: markdown in `docs/` is not in the wheel, and putting the boundary's correctness in
a regular expression run on a user's machine would be a poor trade. So
`tools/ytdlp_option_table.py` writes `downloader/option_table.py`, and this compares the two **in
both directions** — the arrangement `persistence/schema.sql` already has with its migrations.

**One comparison does both directions**, because the generator is a pure function of the audit:
regenerating and comparing the text catches a row edited in the audit and not regenerated here, a
row invented here that the audit does not have, and a reason reworded in either place.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

from tracks_and_trails.downloader.option_table import AUDIT_VERSION, OPTION_CLASSES

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
TOOL: Final = REPO_ROOT / "tools" / "ytdlp_option_table.py"


def load() -> ModuleType:
    """Load the generator by path, as `test_job_duration_report.py` loads its own.

    `tools/` is not a package and is not in `mypy`'s `files`, so a plain import is both an
    unresolvable module and a source of `Any`. This is the pattern the project already uses.
    """
    specification = importlib.util.spec_from_file_location("ytdlp_option_table", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


generator = load()

#: The classes the audit defines. `unruled` is absent on purpose: it has been empty since
#: 2026-08-21 and a row that reappears in it is a row `T-184` must not silently permit.
KNOWN: Final = frozenset(
    {"typed", "hatch", "app:sets", "app:plumbing", "app:policy", "app:contained", "excluded"}
)


def test_the_generated_table_is_what_the_audit_says_today() -> None:
    """Edit the audit without regenerating, and this fails with the diff.

    **The whole file, not a sample of rows.** A test that spot-checked entries would pass while
    the table quietly disagreed with the audit about the other two hundred, and the table is what
    the product refuses from.
    """
    written = generator.TARGET.read_text(encoding="utf-8")

    assert written == generator.rendered(), (
        "downloader/option_table.py is out of date with docs/YTDLP_OPTION_AUDIT.md. "
        "Run: python tools/ytdlp_option_table.py"
    )


def test_the_formatter_is_handed_utf_8_whatever_the_locale() -> None:
    """**`T-356`.** `ruff format` reads its stdin as UTF-8, so the generator must write it as UTF-8.

    A text-mode pipe with no `encoding` is written in the locale's encoding. On `STARBASE` that is
    cp1252, and Ruff refused the generated module's em dashes as invalid UTF-8, which failed the
    test above. A UTF-8 locale hides it, so the child runs with UTF-8 mode and locale coercion off
    under `LC_ALL=C`, whose encoding is ASCII. Windows ignores `LC_ALL` and supplies its code page.
    """
    text = 'reason = "forbidden — a secret"\n'
    probe = (
        "import importlib.util, sys\n"
        f"specification = importlib.util.spec_from_file_location('tool', {str(TOOL)!r})\n"
        "module = importlib.util.module_from_spec(specification)\n"
        "sys.modules['tool'] = module\n"
        "specification.loader.exec_module(module)\n"
        # `!a`, not `!r`: the command line is decoded in the same locale, so a literal em dash
        # fails before the generator runs, and the test would pass or fail on that instead.
        f"sys.stdout.buffer.write(module._formatted({text!a}).encode('utf-8'))\n"
    )
    environment = {**os.environ, "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C"}
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, env=environment, check=False, timeout=60
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert result.stdout.decode("utf-8") == text


def test_every_spelling_carries_a_class_the_audit_defines() -> None:
    """A class nobody has ruled on is not a class the hatch may decide from."""
    unknown = {
        spelling: group for spelling, (group, _) in OPTION_CLASSES.items() if group not in KNOWN
    }

    assert unknown == {}, f"these spellings carry a class the audit does not define: {unknown}"


def test_every_refusal_states_a_reason_long_enough_to_be_one() -> None:
    """`REQ-031`: a refused option is refused **with the reason**, never "not permitted".

    The reason a user is shown is the audit's own words, so an empty or stub one would ship as the
    message. Ten characters is the same floor `test_option_audit.py` holds the audit to.
    """
    thin = {
        spelling: reason
        for spelling, (_, reason) in OPTION_CLASSES.items()
        if len(reason.strip()) < 10
    }

    assert thin == {}, f"these rows would refuse a user without telling them why: {thin}"


def test_the_table_names_the_version_it_was_taken_against() -> None:
    """The table is a fact about one yt-dlp release, and says which."""
    import yt_dlp.version

    installed = yt_dlp.version.__version__

    assert installed == AUDIT_VERSION, (
        f"the table was generated against yt-dlp {AUDIT_VERSION} and {installed} is "
        f"installed. Re-run tools/ytdlp_option_table.py after the audit is re-taken (T-183)."
    )


@pytest.mark.parametrize(
    ("spelling", "group"),
    [
        # One row from each refused class, named here so a class that silently empties out is
        # visible as a failure rather than as a table that simply stopped mentioning it.
        ("--xff", "excluded"),
        ("--paths", "app:contained"),
        ("--output", "app:sets"),
        ("--abort-on-error", "app:policy"),
        ("--continue", "hatch"),
    ],
)
def test_the_spellings_a_reader_will_look_up_are_where_they_belong(
    spelling: str, group: str
) -> None:
    """Anchors, so a regeneration that quietly reclassified a row does not pass unnoticed."""
    assert spelling in OPTION_CLASSES, f"{spelling} is not in the generated table at all"
    assert OPTION_CLASSES[spelling][0] == group


def test_both_spellings_of_an_option_reach_the_same_row() -> None:
    """The table is keyed by **spelling**, so a lookup never has to know which name is the alias.

    `-c` and `--continue` are one audit row; a user types one of them and the refusal or the
    permission has to be the same either way.
    """
    assert OPTION_CLASSES["-c"] == OPTION_CLASSES["--continue"]
    assert OPTION_CLASSES["-o"] == OPTION_CLASSES["--output"]
