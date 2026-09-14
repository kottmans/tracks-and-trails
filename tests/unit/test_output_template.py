"""What an output template may contain, and what its preview may promise (`REQ-011`, `T-112`).

`core/output_template.py` is Qt-free and yt-dlp-free: it declares the field set `P-9` requires the
editor to list, refuses what this application cannot fill, and supplies the words a preview is
labelled with. Rendering is yt-dlp's (`tests/unit/test_ytdlp_adapter.py`), the containment is
`core/paths.py`'s, and the two meeting is `tests/integration/test_end_to_end.py`.
"""

import pytest

from tracks_and_trails.core import output_template
from tracks_and_trails.core.models import MediaInfo
from tracks_and_trails.core.output_template import (
    SUPPORTED_FIELDS,
    SUPPORTED_NAMES,
    OutputPreview,
    named_fields,
    syntax_refusal,
    template_values,
    unsupported_fields,
    unsupported_refusal,
)


def test_every_supported_field_is_one_the_projection_can_fill() -> None:
    """**The list a user reads and the values a preview renders are one set.**

    `P-9`'s whole reason for listing the fields inline is that this application's set is smaller
    than yt-dlp's. A field offered in the list and absent from the projection would render as `NA`
    — which is the failure the supported set exists to prevent, arriving through the control that
    advertises it.

    `duration_string` is the one indirection and it is deliberate: yt-dlp derives it from
    `duration`, so the projection supplies the number and yt-dlp does the formatting.
    """
    media = MediaInfo(url="https://example.invalid/x", title="T", uploader="U", duration_seconds=1)
    values = template_values(media, "mp4")

    fillable = set(values) | {"duration_string"}
    assert fillable >= SUPPORTED_NAMES, (
        f"offered but unfillable: {sorted(SUPPORTED_NAMES - fillable)}"
    )


def test_the_offered_fields_each_say_what_they_are() -> None:
    """`P-9` asks for a list *beside the input*, which is only useful if it explains itself."""
    assert SUPPORTED_FIELDS
    for field in SUPPORTED_FIELDS:
        assert field.name and field.describes, field


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("%(title)s.%(ext)s", ("title", "ext")),
        # yt-dlp's conversion syntax follows the name; the name is what is checked.
        ("%(title).30s", ("title",)),
        ("%(title,alt_title)s", ("title", "alt_title")),
        ("%(playlist_index)03d", ("playlist_index",)),
        ("%(formats.:.format_id)l", ("formats",)),
        ("no fields at all", ()),
        # Repeats are kept: a refusal that folded three into one would make a template look
        # shorter than it is to whoever has to fix it.
        ("%(title)s-%(title)s", ("title", "title")),
    ],
)
def test_the_base_field_names_are_read_out_of_a_template(
    template: str, expected: tuple[str, ...]
) -> None:
    assert named_fields(template) == expected


def test_a_field_this_application_cannot_fill_is_refused_with_its_name() -> None:
    """`P-23`: at edit time, **with the reason** — and the reason has to be actionable.

    yt-dlp renders an unknown field as the literal `NA` and says nothing, so without this the user
    gets a file called `NA.mp4` and a preview that agreed with it.
    """
    refusal = unsupported_refusal("%(id)s - %(title)s.%(ext)s")

    assert refusal is not None
    assert "%(id)s" in refusal, refusal
    assert "NA" in refusal, "the refusal does not say what would actually happen"
    for field in SUPPORTED_FIELDS:
        assert f"%({field.name})s" in refusal, f"{field.name} is not offered as an alternative"


def test_several_unsupported_fields_are_all_named_once() -> None:
    """One round trip per fix is one too many when the template names three unknown fields."""
    assert unsupported_fields("%(id)s/%(uploader)s/%(id)s-%(view_count)s.%(ext)s") == (
        "id",
        "view_count",
    )

    refusal = unsupported_refusal("%(id)s-%(view_count)s.%(ext)s")
    assert refusal is not None and "are not fields" in refusal, refusal


def test_a_template_of_supported_fields_is_not_refused() -> None:
    offered = "".join(f"%({field.name})s-" for field in SUPPORTED_FIELDS)

    assert unsupported_refusal(offered) is None
    assert unsupported_fields(offered) == ()


def test_a_playlist_field_is_refused_rather_than_previewed() -> None:
    """The field whose preview and write would disagree, named explicitly.

    A playlist entry downloads as an ordinary job holding its own URL (`T-137`), so nothing in the
    extraction that names the file knows the entry's position. The dialog *does* know it, so this
    is the one field a well-meaning projection would have been able to fill — and it would have
    rendered `3` in the preview and `NA` in the file.
    """
    assert "playlist_index" not in SUPPORTED_NAMES
    assert unsupported_refusal("%(playlist_index)s - %(title)s.%(ext)s") is not None


def test_yt_dlps_own_complaint_is_kept_and_given_a_subject() -> None:
    """`incomplete format` is accurate, and alone under a text box it reads as a broken app."""
    framed = syntax_refusal("incomplete format")

    assert "incomplete format" in framed, "the message was paraphrased away"
    assert "template" in framed, "the message does not say what it is about"


def test_a_refused_preview_carries_no_path() -> None:
    """Showing the last good path beside an error is how a broken template looks like it works."""
    refused = OutputPreview(refusal="no")

    assert refused.is_refused
    assert refused.path == ""
    assert not OutputPreview(path="/downloads/x.mp4").is_refused


# --- UX-014: naming choices, and renaming one download ---------------------------------------


@pytest.mark.parametrize(
    ("name", "template"),
    [
        ("{Title}", "%(title)s.%(ext)s"),
        ("{Uploader} - {Title}", "%(uploader)s - %(title)s.%(ext)s"),
        ("{Uploader}/{Title}", "%(uploader)s/%(title)s.%(ext)s"),
        ("{Upload date} {Title}", "%(upload_date>%Y-%m-%d)s %(title)s.%(ext)s"),
        ("{Title} ({Duration})", "%(title)s (%(duration_string)s).%(ext)s"),
        ("100% {Title}", "100%% %(title)s.%(ext)s"),
    ],
)
def test_a_readable_name_is_the_template_it_means_and_reads_back(name: str, template: str) -> None:
    """**`UX-014`.** Fields filled, text literal, extension added — and back again, unchanged."""
    assert output_template.readable_to_template(name) == template
    assert output_template.template_to_readable(template) == name
    assert output_template.unsupported_refusal(template) is None, template


def test_a_label_matches_regardless_of_case() -> None:
    assert output_template.readable_to_template("{upload DATE}") == (
        output_template.readable_to_template("{Upload date}")
    )


def test_an_empty_name_is_the_applications_own_naming() -> None:
    assert output_template.readable_to_template("  ") == ""
    assert output_template.template_to_readable("") == "{Title}"


def test_a_label_that_is_not_a_field_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match=r"\{Views\}"):
        output_template.readable_to_template("{Views} {Title}")


@pytest.mark.parametrize(
    "template",
    ["%(title).30s.%(ext)s", "%(id)s.%(ext)s", "%(title)s [%(ext)s]", "{Title}.%(ext)s"],
)
def test_a_template_a_name_cannot_show_reads_back_as_none(template: str) -> None:
    """Kept as it is rather than rewritten into a name that would mean something else."""
    assert output_template.template_to_readable(template) is None


def test_every_offered_field_has_a_label_and_the_extension_is_not_offered() -> None:
    offered = {field.name for field in output_template.OFFERED_FIELDS}
    assert offered == {"title", "uploader", "duration_string", "upload_date"}
    assert all(field.label for field in output_template.OFFERED_FIELDS)


def test_the_upload_date_is_projected_for_the_preview() -> None:
    media = MediaInfo(url="https://example.invalid/x", title="T", upload_date="20260913")
    assert template_values(media, "mp4")["upload_date"] == "20260913"


@pytest.mark.parametrize(
    ("name", "within", "expected"),
    [
        ("My clip", "%(title)s.%(ext)s", "My clip.%(ext)s"),
        ("100% juice", "%(title)s.%(ext)s", "100%% juice.%(ext)s"),
        ("My clip", "%(uploader)s/%(title)s.%(ext)s", "%(uploader)s/My clip.%(ext)s"),
        ("%(title)s", "%(title)s.%(ext)s", "%%(title)s.%(ext)s"),
    ],
)
def test_a_rename_is_written_literally_in_the_settings_folders(
    name: str, within: str, expected: str
) -> None:
    """A `%` is a percent sign and a typed field is text; the folders are the setting's."""
    assert output_template.renamed_template(name, within=within) == expected
    assert output_template.renamed_name_of(expected) == name, "the rename did not read back"


def test_a_pattern_is_not_read_back_as_a_rename() -> None:
    for name in ("{Title}", "{Uploader} - {Title}", "{Upload date} {Title}"):
        pattern = output_template.readable_to_template(name)
        assert output_template.renamed_name_of(pattern) is None, pattern


@pytest.mark.parametrize("name", ["a/b", "a\\b"])
def test_a_name_naming_a_folder_is_refused(name: str) -> None:
    assert output_template.name_refusal(name) == output_template.NAME_SEPARATOR_REFUSAL
    with pytest.raises(ValueError):
        output_template.renamed_template(name, within="%(title)s.%(ext)s")


@pytest.mark.parametrize(
    ("path", "stem"),
    [
        ("C:\\Users\\me\\Downloads\\Up\\A v1.2 clip.ext", "A v1.2 clip"),
        ("/home/me/Downloads/A clip.mp4", "A clip"),
        ("no extension", "no extension"),
    ],
)
def test_the_prefilled_name_is_the_file_without_folders_or_extension(path: str, stem: str) -> None:
    assert output_template.file_stem_of(path) == stem
