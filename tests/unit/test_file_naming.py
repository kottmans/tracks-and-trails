"""How a name is shaped and a file dated, from the setting to yt-dlp (`T-248`).

Built on the task's recommended answers, which the maintainer ruled on 2026-10-19: a Settings
preference beside *How files are named*, frozen into each request as the template is (question 3),
with the Windows pair refused as `app:policy` (question 2). The sessions that prove where files
land are in `tests/integration/test_shaping_containment.py`; these hold the value on its way there.
"""

from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import pytest
from yt_dlp import parse_options

from tracks_and_trails.core import presets
from tracks_and_trails.core import settings as app_settings
from tracks_and_trails.core.models import MOST_NAME_CHARACTERS, DownloadRequest, FileNaming
from tracks_and_trails.downloader import ytdlp_adapter
from tracks_and_trails.downloader.ytdlp_adapter import (
    RENDER_ONLY_KEYS,
    SHAPING_KEYS,
    build_options,
    render_output_template,
    shaping_options,
)

#: A value for each field that differs from its default, so a carry that dropped one cannot pass by
#: both sides holding the default.
EVERY_FIELD_SET: dict[str, Any] = {
    "restrict_filenames": True,
    "trim_filenames": 80,
    "use_last_modified": True,
}


def a_request(**fields_: Any) -> DownloadRequest:
    return DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="/home/someone/Videos",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
        **fields_,
    )


def test_the_samples_name_every_field() -> None:
    assert {item.name for item in fields(FileNaming)} == set(EVERY_FIELD_SET)


# --- the value -------------------------------------------------------------------------------


@pytest.mark.parametrize("owner", [FileNaming, a_request])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trim_filenames", 0),
        ("trim_filenames", MOST_NAME_CHARACTERS + 1),
        ("trim_filenames", -3),
        ("trim_filenames", True),
        ("trim_filenames", "80"),
        ("restrict_filenames", 1),
        ("use_last_modified", "yes"),
    ],
)
def test_a_value_no_control_can_show_is_refused(owner: Any, field: str, value: Any) -> None:
    """The model and the request share the rule: a length from 1 to 255 or none, and two flags."""
    with pytest.raises((TypeError, ValueError)):
        owner(**{field: value})


def test_the_longest_length_is_allowed() -> None:
    assert FileNaming(trim_filenames=MOST_NAME_CHARACTERS).trim_filenames == MOST_NAME_CHARACTERS


def test_a_request_carries_the_naming_it_was_given_and_gives_it_back() -> None:
    naming = FileNaming(**EVERY_FIELD_SET)

    request = presets.with_naming(a_request(), naming)

    assert presets.naming_of(request) == naming


def test_the_naming_survives_a_retarget() -> None:
    """`_retarget_to` rebuilds the request from a preset, which carries no naming, then puts the
    job's back. Derived from `FileNaming`, so a fourth field cannot be forgotten in the carry."""
    queued = presets.with_naming(
        presets.to_request(
            presets.BEST_VIDEO, url="https://example.invalid/a", output_directory="/d"
        ),
        FileNaming(**EVERY_FIELD_SET),
    )
    rebuilt = presets.to_request(
        presets.AUDIO_MP3, url=queued.url, output_directory=queued.output_directory
    )
    assert presets.naming_of(rebuilt) == FileNaming(), "sanity: a preset carries no naming"

    kept = presets.with_naming(rebuilt, presets.naming_of(queued))

    assert presets.naming_of(kept) == FileNaming(**EVERY_FIELD_SET)


# --- the file --------------------------------------------------------------------------------


def _saved_and_loaded(tmp_path: Path, settings: app_settings.Settings) -> app_settings.SettingsFile:
    target = tmp_path / "settings.toml"
    assert app_settings.save(settings, target) is None
    return app_settings.load(target)


def test_the_naming_is_saved_and_read_back(tmp_path: Path) -> None:
    naming = FileNaming(**EVERY_FIELD_SET)

    read = _saved_and_loaded(
        tmp_path, app_settings.with_file_naming(app_settings.Settings(), naming)
    )

    assert read.settings.naming == naming
    assert read.problem is None


def test_the_defaults_write_no_naming_table(tmp_path: Path) -> None:
    read = _saved_and_loaded(tmp_path, app_settings.Settings())

    assert "[naming]" not in (tmp_path / "settings.toml").read_text(encoding="utf-8")
    assert read.settings.naming == FileNaming()


@pytest.mark.parametrize(
    ("lines", "expected", "reported"),
    [
        # yt-dlp's own spelling of no limit, read as that without a word.
        ("trim_filenames = 0", FileNaming(), False),
        ("trim_filenames = 300", FileNaming(trim_filenames=MOST_NAME_CHARACTERS), True),
        ('trim_filenames = "80"', FileNaming(), True),
        ("trim_filenames = -1", FileNaming(), True),
        ("trim_filenames = true", FileNaming(), True),
        ('restrict_filenames = "yes"', FileNaming(), True),
        # One bad key costs only itself.
        (
            "restrict_filenames = 1\ntrim_filenames = 40\nuse_last_modified = true",
            FileNaming(trim_filenames=40, use_last_modified=True),
            True,
        ),
    ],
)
def test_a_hand_edited_table_is_read_key_by_key_and_never_raises(
    tmp_path: Path, lines: str, expected: FileNaming, reported: bool
) -> None:
    target = tmp_path / "settings.toml"
    target.write_text(f"[naming]\n{lines}\n", encoding="utf-8")

    read = app_settings.load(target)

    assert read.settings.naming == expected
    assert (read.problem is not None) is reported, read.problem


def test_a_naming_that_is_not_a_table_is_reported(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    target.write_text('naming = "plain"\n', encoding="utf-8")

    read = app_settings.load(target)

    assert read.settings.naming == FileNaming()
    assert read.problem is not None


# --- what yt-dlp is handed -------------------------------------------------------------------


def test_each_field_sets_the_key_yt_dlp_s_own_option_sets() -> None:
    """**The mapping held to yt-dlp's parser**, so the setting means what `--restrict-filenames`,
    `--trim-filenames` and `--mtime` mean."""
    parsed = parse_options(["--restrict-filenames", "--trim-filenames", "80", "--mtime"]).ydl_opts
    request = a_request(**EVERY_FIELD_SET)

    rendered = build_options(request, request.output_template, probe_only=True)
    downloaded = build_options(request, "/home/someone/Videos/staging/clip.mp4")

    assert rendered["restrictfilenames"] is parsed["restrictfilenames"]
    assert rendered["trim_file_name"] == parsed["trim_file_name"]
    assert downloaded["updatetime"] is parsed["updatetime"]


def test_where_each_key_acts() -> None:
    """The shape on the pass that renders the name, the trim never on the download's literal path,
    the restriction on both since it acts on no literal text, and the date on the download only."""
    request = a_request(**EVERY_FIELD_SET)

    rendered = build_options(request, request.output_template, probe_only=True)
    downloaded = build_options(request, "/home/someone/Videos/staging/clip.mp4")

    assert set(rendered) >= SHAPING_KEYS
    assert "trim_file_name" in RENDER_ONLY_KEYS and "trim_file_name" not in downloaded
    assert downloaded["restrictfilenames"] is True
    assert "updatetime" not in rendered
    assert downloaded["updatetime"] is True


def test_the_defaults_send_nothing() -> None:
    request = a_request()

    rendered = build_options(request, request.output_template, probe_only=True)
    downloaded = build_options(request, "/home/someone/Videos/staging/clip.mp4")

    assert not (SHAPING_KEYS | {"updatetime"}) & (set(rendered) | set(downloaded))


def test_the_write_and_the_preview_share_one_derivation() -> None:
    request = a_request(**EVERY_FIELD_SET)

    assert shaping_options(request) == {
        key: value
        for key, value in build_options(request, request.output_template, probe_only=True).items()
        if key in SHAPING_KEYS
    }


def test_one_preview_s_shape_does_not_reach_the_next() -> None:
    """The preview's renderer is shared, so every key is set on every render."""
    values = {"id": "clip", "title": "Café & Crème: live", "ext": "ext"}
    shaped = shaping_options(a_request(restrict_filenames=True, trim_filenames=4))

    first = render_output_template("%(title)s.%(ext)s", values, shaped)
    second = render_output_template("%(title)s.%(ext)s", values)

    assert first == "Cafe.ext"
    assert second == render_output_template("%(title)s.%(ext)s", values, {})
    assert second.startswith("Café & Crème")
    assert all(ytdlp_adapter._preview_renderer().params.get(key) is None for key in SHAPING_KEYS)


def test_replace_keeps_the_naming_a_request_was_frozen_with() -> None:
    """A rename on a queue row is `replace(job.request, output_template=…)`, which keeps it."""
    request = presets.with_naming(a_request(), FileNaming(**EVERY_FIELD_SET))

    renamed = replace(request, output_template="Other.%(ext)s")

    assert presets.naming_of(renamed) == FileNaming(**EVERY_FIELD_SET)
