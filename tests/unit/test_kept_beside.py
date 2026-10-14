"""*Keep beside the file*: the description, the info JSON and the thumbnails (`T-249`).

Three typed fields for seven of yt-dlp's options, shared by presets and requests, set on the
download only, and held here to yt-dlp's own `parse_options` of the options they stand for. And
the ruling that shaped the info JSON (`DAT-003`, amended 2026-10-11): yt-dlp writes the session's
cookie values and any typed request header into it, and the file is kept without them.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from yt_dlp import parse_options

from tracks_and_trails.core import presets
from tracks_and_trails.core.models import DownloadRequest, KeptThumbnails, Preset
from tracks_and_trails.core.settings import Settings, add_preset, load, save
from tracks_and_trails.downloader import worker
from tracks_and_trails.downloader.ytdlp_adapter import (
    build_options,
    info_json_stripper,
    strip_info_json,
    without_secrets,
)
from tracks_and_trails.persistence.repositories import _deserialize_request, _serialize_request

URL: Final = "https://example.invalid/clip"
DIRECTORY: Final = "downloads"
TEMPLATE: Final = "%(title)s.%(ext)s"

#: The keys the three fields set, and what yt-dlp means when each is absent.
KEPT_KEYS: Final = {
    "writedescription": False,
    "writeinfojson": None,
    "writethumbnail": False,
    "write_all_thumbnails": False,
}


def a_request(**fields: Any) -> DownloadRequest:
    return DownloadRequest(
        url=URL,
        output_directory=DIRECTORY,
        format_selector="best",
        output_template=TEMPLATE,
        **fields,
    )


def a_preset(**fields: Any) -> Preset:
    return replace(presets.BEST_VIDEO, name="Keeping", built_in=False, **fields)


# --- the model and where it is kept -----------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [("keep_thumbnails", "all"), ("write_description", 1), ("write_info_json", "yes")],
)
def test_a_value_of_the_wrong_kind_is_refused(field: str, value: object) -> None:
    """A bare `"all"` compares equal to the member and fails an identity check (`T011-R2`)."""
    with pytest.raises((TypeError, ValueError), match=field):
        a_preset(**{field: value})


def test_a_preset_keeping_files_survives_a_save(tmp_path: Path) -> None:
    target = tmp_path / "settings.toml"
    preset = a_preset(
        write_description=True, write_info_json=True, keep_thumbnails=KeptThumbnails.BEST
    )

    save(add_preset(Settings(), preset), target)
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.presets == (preset,)


def test_a_request_keeping_files_survives_the_queue_and_an_older_row_keeps_none() -> None:
    """One JSON blob, so no migration (`T-109`'s rule): a row without the keys keeps nothing."""
    request = a_request(write_info_json=True, keep_thumbnails=KeptThumbnails.ALL)

    assert _deserialize_request(_serialize_request(request)) == request
    older = _deserialize_request(
        json.dumps(
            {
                "url": URL,
                "output_directory": DIRECTORY,
                "format_selector": "best",
                "output_template": TEMPLATE,
            }
        )
    )
    assert (older.write_description, older.write_info_json, older.keep_thumbnails) == (
        False,
        False,
        KeptThumbnails.NONE,
    )


def test_a_preset_s_kept_files_reach_its_request() -> None:
    preset = a_preset(write_description=True, keep_thumbnails=KeptThumbnails.ALL)

    request = presets.to_request(preset, url=URL, output_directory=DIRECTORY)

    assert (request.write_description, request.keep_thumbnails) == (True, KeptThumbnails.ALL)


# --- reaching yt-dlp --------------------------------------------------------------------------


def test_the_kept_files_are_asked_for_on_the_download_and_never_the_probe() -> None:
    """yt-dlp writes these when it processes the item, which a probe never does."""
    request = a_request(
        write_description=True, write_info_json=True, keep_thumbnails=KeptThumbnails.ALL
    )

    download = build_options(request, TEMPLATE)
    probe = build_options(request, TEMPLATE, probe_only=True)

    assert {key: download.get(key) for key in KEPT_KEYS} == {
        "writedescription": True,
        "writeinfojson": True,
        "writethumbnail": None,
        "write_all_thumbnails": True,
    }
    assert not set(KEPT_KEYS) & set(probe), "a kept file was asked of the probe"


#: The same intent twice: the typed fields, and the options a user would type for them.
SAME_INTENT: Final = [
    pytest.param({}, [], id="nothing"),
    pytest.param({"write_description": True}, ["--write-description"], id="description"),
    pytest.param({"write_info_json": True}, ["--write-info-json"], id="info json"),
    pytest.param({"keep_thumbnails": KeptThumbnails.BEST}, ["--write-thumbnail"], id="best"),
    pytest.param({"keep_thumbnails": KeptThumbnails.ALL}, ["--write-all-thumbnails"], id="all"),
    pytest.param(
        {
            "write_description": True,
            "write_info_json": True,
            "keep_thumbnails": KeptThumbnails.BEST,
        },
        ["--write-description", "--write-info-json", "--write-thumbnail"],
        id="all three",
    ),
]


@pytest.mark.parametrize(("typed", "argv"), SAME_INTENT)
def test_the_kept_files_build_what_yt_dlp_s_own_command_line_builds(
    typed: dict[str, Any], argv: list[str]
) -> None:
    """**Same intent, same dictionary**, through the preset and `to_request`, key by key.

    Embedding is left out: there the application also sets `writethumbnail` so there is a picture
    to embed, which yt-dlp's command line does differently and which
    `test_hatch_request.py`'s union tests hold.
    """
    request = presets.to_request(a_preset(**typed), url=URL, output_directory=DIRECTORY)
    ours = build_options(request, TEMPLATE)
    theirs = parse_options(argv).ydl_opts

    for key, absent in KEPT_KEYS.items():
        assert ours.get(key, absent) == theirs[key], key


# --- the info JSON's secrets (`DAT-003`, amended 2026-10-11) -----------------------------------

#: What yt-dlp wrote into a kept info JSON with a cookies file and `--add-headers`, measured
#: 2026-10-11, reduced to its shape: the cookie in every format and at the top, the header in each
#: format's `http_headers`, and the same again in `requested_formats` under `--no-clean-info-json`.
WRITTEN: Final = {
    "id": "clip",
    "title": "Clip — café",
    "cookies": "session=SECRET_COOKIE; Domain=example.invalid; Path=/",
    "formats": [
        {
            "format_id": "best",
            "url": URL,
            "cookies": "session=SECRET_COOKIE; Domain=example.invalid; Path=/",
            "http_headers": {"Authorization": "Bearer SECRET_HEADER", "User-Agent": "x"},
        }
    ],
    "requested_formats": [{"http_headers": {"Authorization": "Bearer SECRET_HEADER"}}],
    "tags": ["cookies", "http_headers"],
}


def test_every_cookie_and_header_is_removed_wherever_it_sits() -> None:
    """Removed by key at any depth; a value that merely says *cookies* is kept."""
    stripped = without_secrets(WRITTEN)

    assert "SECRET" not in json.dumps(stripped)
    assert stripped["tags"] == ["cookies", "http_headers"]
    assert stripped["formats"] == [{"format_id": "best", "url": URL}]
    assert stripped["title"] == "Clip — café"


def test_a_kept_info_json_is_rewritten_whole_and_as_yt_dlp_writes_it(tmp_path: Path) -> None:
    path = tmp_path / "clip.info.json"
    path.write_text(json.dumps(WRITTEN, ensure_ascii=False), encoding="utf-8")

    strip_info_json(path)

    text = path.read_text(encoding="utf-8")
    assert "SECRET" not in text
    assert "café" in text, "the rewrite escaped what yt-dlp had written plainly"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["clip.info.json"], "a sibling was left"


def test_an_info_json_that_cannot_be_read_is_not_kept_as_it_is(tmp_path: Path) -> None:
    """A file this cannot read is one it cannot vouch for, so it raises rather than passing it."""
    path = tmp_path / "clip.info.json"
    path.write_text('{"cookies": "session=SECRET', encoding="utf-8")

    with pytest.raises(ValueError):
        strip_info_json(path)


def test_the_processor_strips_the_file_yt_dlp_says_it_wrote(tmp_path: Path) -> None:
    """The `before_dl` hook: `process_info` records `infojson_filename` before it runs."""
    path = tmp_path / "clip.info.json"
    path.write_text(json.dumps(WRITTEN), encoding="utf-8")

    files, processed = info_json_stripper().run({"infojson_filename": str(path)})

    assert files == [] and processed["infojson_filename"] == str(path)
    assert "SECRET" not in path.read_text(encoding="utf-8")


def test_the_worker_strips_what_it_is_about_to_claim_and_nothing_else(tmp_path: Path) -> None:
    """The guarantee behind the hook: a yt-dlp that recorded no path still has its file stripped.
    A description is the user's text, and is not touched."""
    from tracks_and_trails.downloader import ytdlp_adapter

    info = tmp_path / "clip.info.json"
    info.write_text(json.dumps(WRITTEN), encoding="utf-8")
    description = tmp_path / "clip.description"
    description.write_text("cookies: session=SECRET_COOKIE", encoding="utf-8")

    worker.strip_kept_info_json([info, description, tmp_path / "absent.info.json"], ytdlp_adapter)

    assert "SECRET" not in info.read_text(encoding="utf-8")
    assert description.read_text(encoding="utf-8") == "cookies: session=SECRET_COOKIE"
