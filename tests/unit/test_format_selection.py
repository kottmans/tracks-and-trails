"""What choosing formats means (`REQ-008`, `T-108`, `docs/UX_SPEC.md` §5).

**No `QApplication` anywhere in this file**, which is the point of `ui/format_selection.py` being
Qt-free: these are the rules `REQ-008` states, and a test that had to build a widget to reach them
would be asserting the widget as well.

**The fixture is loaded through the adapter**, not hand-built, wherever the question is *"does what
a probe reports reach the rule"*. `derived_format_columns` is the only fixture carrying an
explicitly video-only and an explicitly audio-only format, and it says so in its own
`what_is_synthetic` — no acceptable recorded source publishes such a pair, which is `T-188`.
"""

import json
from pathlib import Path
from typing import Any, Final

import pytest

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.ui.format_selection import (
    NOTHING_CHOSEN,
    FormatKind,
    FormatSelection,
    SelectionMode,
    UnplaceableFormatError,
    kind_of,
    merge_refusal,
    pairable,
)

FIXTURE_DIR: Final = Path(__file__).parents[1] / "fixtures" / "infodicts"


def formats_from(name: str) -> tuple[FormatInfo, ...]:
    payload: dict[str, Any] = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return adapter.project_media(payload["info_dict"]).formats


def by_id(formats: tuple[FormatInfo, ...], format_id: str) -> FormatInfo:
    return next(entry for entry in formats if entry.format_id == format_id)


@pytest.fixture
def pair() -> tuple[FormatInfo, FormatInfo]:
    """The video-only and audio-only formats, projected from the fixture."""
    formats = formats_from("derived_format_columns")
    return by_id(formats, "137"), by_id(formats, "140")


# --- which slot a format can fill ------------------------------------------------------------


def test_kind_comes_from_the_fixture_and_not_from_a_codec_name(
    pair: tuple[FormatInfo, FormatInfo],
) -> None:
    """`vcodec: none` and a missing `vcodec` are different facts (`T107-R1`, `T-108`).

    Asserted through the adapter from a committed fixture, because the question is whether yt-dlp's
    own spelling survives the projection — a hand-built `FormatInfo` would be this test agreeing
    with itself about what `has_video` means.
    """
    video, audio = pair
    assert kind_of(video) is FormatKind.VIDEO_ONLY
    assert kind_of(audio) is FormatKind.AUDIO_ONLY


def test_a_format_the_source_said_nothing_about_is_unknown_rather_than_video() -> None:
    """The commonest case for the sources this project records, and it must not be guessed.

    archive.org names no codec for any derivative and PeerTube names none at all. Reading that
    silence as *"video, no audio"* would offer every one of them as the video half of a merge — and
    they are progressive files, so the merge would be of a file that already has sound.
    """
    for name in ("archive_org_big_buck_bunny", "peertube_big_buck_bunny_60fps"):
        formats = formats_from(name)
        assert formats, f"{name} has no formats to classify"
        kinds = {kind_of(entry) for entry in formats}
        assert kinds == {FormatKind.UNKNOWN}, f"{name} classified something as {kinds}"


def test_video_with_nothing_said_about_audio_is_unknown_not_video_only() -> None:
    """**Both answers must be known**, and half of one is not half the answer (`T-108`).

    media.ccc.de publishes exactly this shape — `vcodec: 'h264'` with no `acodec` key at all — for
    recordings of talks, which certainly have sound. Reading it as *video-only* would offer it as
    the video half of a merge and produce `h264-hd+140`: audio merged into a file that already has
    it.

    **This case is here because a mutation found its absence.** Dropping `has_audio is None` from
    `kind_of` survived every other fixture, because the sources this project records say *nothing*
    about either stream rather than something about one — so `derived_format_columns` gained the
    shape, declared synthetic, rather than leaving the boundary unasserted.
    """
    entry = by_id(formats_from("derived_format_columns"), "h264-hd")
    assert (entry.has_video, entry.has_audio) == (True, None), (
        "the fixture no longer carries video-with-unstated-audio, so this asserts nothing"
    )
    assert kind_of(entry) is FormatKind.UNKNOWN
    assert not entry.is_video_only

    with pytest.raises(UnplaceableFormatError):
        FormatSelection(mode=SelectionMode.PAIR).choose(entry)


def test_an_audio_rendition_is_the_audio_half_even_with_no_codec_named() -> None:
    """The `'none'` is the signal; the other side may be silent (`T108-R1`).

    **Found by driving a real HLS presentation through yt-dlp**, not by reading the spec. An
    `EXT-X-MEDIA:TYPE=AUDIO` group comes through as `vcodec: 'none'` with **no `acodec` at all**,
    because the `CODECS` list lives on the variant rather than on the group. The first version of
    `kind_of` required both answers, which made the commonest real audio half unpairable — the
    end-to-end test for the merge criterion is what surfaced it.

    Contrast `h264-hd` above: silence about audio, with video *named* rather than denied, stays
    unknown. An explicit `none` on the other stream is what distinguishes them.
    """
    entry = by_id(formats_from("derived_format_columns"), "hls-audio")
    assert (entry.has_video, entry.has_audio) == (False, None)
    assert kind_of(entry) is FormatKind.AUDIO_ONLY
    assert entry.is_audio_only and not entry.is_video_only


def test_a_format_denied_both_streams_is_neither_half() -> None:
    """A storyboard is `vcodec: 'none'` **and** `acodec: 'none'` — not the audio half.

    The rule keys on one stream being denied, so the case where *both* are has to be excluded
    deliberately rather than falling out of the ordering of two branches.
    """
    entry = by_id(formats_from("derived_format_columns"), "storyboard")
    assert (entry.has_video, entry.has_audio) == (False, False)
    assert kind_of(entry) is FormatKind.UNKNOWN
    assert not entry.is_audio_only and not entry.is_video_only

    with pytest.raises(UnplaceableFormatError):
        FormatSelection(mode=SelectionMode.PAIR).choose(entry)
    # Still choosable on its own: `REQ-008` is about picking format ids, and a user may want one.
    assert FormatSelection().choose(entry).selector() == "storyboard"


def test_the_routing_and_the_projection_cannot_disagree() -> None:
    """`kind_of` is defined in terms of `is_video_only`/`is_audio_only`, and stays that way.

    Two spellings of *"is this the audio half"* is two places for it to drift, and this project has
    a standing record of exactly that — a value computed in one place and re-derived in another.
    Asserted across every format of every fixture rather than on an example.
    """
    for name in (
        "derived_format_columns",
        "archive_org_big_buck_bunny",
        "wikimedia_caminandes",
        "peertube_big_buck_bunny_60fps",
    ):
        for entry in formats_from(name):
            kind = kind_of(entry)
            assert (kind is FormatKind.VIDEO_ONLY) == entry.is_video_only, entry.format_id
            assert (kind is FormatKind.AUDIO_ONLY) == entry.is_audio_only, entry.format_id


def test_a_format_carrying_both_streams_is_complete_not_a_half() -> None:
    """`wikimedia_caminandes` names a vcodec **and** an acodec per format — a real recording."""
    formats = formats_from("wikimedia_caminandes")
    complete = [entry for entry in formats if kind_of(entry) is FormatKind.COMPLETE]
    assert len(complete) == 4, [kind_of(entry) for entry in formats]
    assert not any(entry.is_video_only or entry.is_audio_only for entry in complete)


def test_only_a_source_with_both_halves_can_be_paired() -> None:
    """`pairable` is the *source's* reason a merge is impossible, distinct from ffmpeg's.

    Every recorded source publishes complete files only, so offering *video + audio* on one is
    offering a mode that can never be completed (`UX-005` §5).
    """
    assert pairable(formats_from("derived_format_columns"))
    for name in ("archive_org_big_buck_bunny", "wikimedia_caminandes"):
        assert not pairable(formats_from(name)), f"{name} was reported pairable"


# --- routing, and what a mode switch keeps ---------------------------------------------------


def test_a_row_goes_into_the_slot_its_kind_matches(pair: tuple[FormatInfo, FormatInfo]) -> None:
    """`UX-007`'s `P-2`: *"chosen into whichever of the two slots its own kind matches"*.

    Order-independent on purpose: the audio half is chosen first here, because a user scrolling a
    table meets the formats in whatever order they are sorted and the rule must not depend on it.
    """
    video, audio = pair
    selection = FormatSelection(mode=SelectionMode.PAIR).choose(audio).choose(video)
    assert selection.audio is audio
    assert selection.video is video
    assert selection.is_complete and selection.is_merge
    assert selection.selector() == "137+140", "the selector is not video+audio"


def test_the_pair_selector_puts_video_first_whatever_order_it_was_chosen_in(
    pair: tuple[FormatInfo, FormatInfo],
) -> None:
    """yt-dlp's `+` is ordered, and the container follows the first stream.

    Choosing audio first must not produce `140+137`: same two streams, and yt-dlp would pick the
    output container from the audio one.
    """
    video, audio = pair
    forwards = FormatSelection(mode=SelectionMode.PAIR).choose(video).choose(audio)
    backwards = FormatSelection(mode=SelectionMode.PAIR).choose(audio).choose(video)
    assert forwards.selector() == backwards.selector() == "137+140"


def test_a_complete_format_is_refused_from_a_slot_and_says_why() -> None:
    """A refusal is a sentence, never silence (`UX-005` §5, and `T-075` is what silence costs)."""
    complete = by_id(formats_from("wikimedia_caminandes"), "0")
    with pytest.raises(UnplaceableFormatError) as refusal:
        FormatSelection(mode=SelectionMode.PAIR).choose(complete)
    message = str(refusal.value)
    assert complete.format_id in message, "the refusal does not name the format"
    assert "nothing to merge" in message
    assert SelectionMode.SINGLE in message, "the refusal names no way forward"


def test_an_unclassified_format_is_refused_for_a_different_reason() -> None:
    """The two refusals must not share a sentence: one is a limit of the source, one is not.

    Telling a user that a progressive file "already has both" when the site never said so would be
    stating something this application does not know — the `T107-R1` habit, in prose.
    """
    unknown = formats_from("archive_org_big_buck_bunny")[0]
    with pytest.raises(UnplaceableFormatError) as refusal:
        FormatSelection(mode=SelectionMode.PAIR).choose(unknown)
    assert "does not say whether" in str(refusal.value)


def test_every_format_can_be_chosen_in_single_mode() -> None:
    """`REQ-008` is about picking format ids; the table must not refuse what yt-dlp offers.

    Including the ones nothing is known about, which is most of them.
    """
    for name in ("archive_org_big_buck_bunny", "wikimedia_caminandes", "derived_format_columns"):
        for entry in formats_from(name):
            selection = FormatSelection().choose(entry)
            assert selection.selector() == entry.format_id


def test_switching_mode_keeps_the_half_that_still_fits(
    pair: tuple[FormatInfo, FormatInfo],
) -> None:
    """Switching is not a reset: a chosen video-only stream becomes the video half."""
    video, _audio = pair
    switched = FormatSelection().choose(video).with_mode(SelectionMode.PAIR)
    assert switched.video is video
    assert switched.audio is None
    assert not switched.is_complete


def test_switching_mode_drops_a_choice_that_cannot_be_half_of_a_merge() -> None:
    """A complete format has no half to be, and coercing it would ask for `0+140`."""
    complete = by_id(formats_from("wikimedia_caminandes"), "0")
    switched = FormatSelection().choose(complete).with_mode(SelectionMode.PAIR)
    assert switched.video is None and switched.audio is None


def test_switching_back_keeps_the_video_half_as_the_single_choice(
    pair: tuple[FormatInfo, FormatInfo],
) -> None:
    """The way back is a choice too, and silently emptying the table would lose the user's work."""
    video, audio = pair
    back = (FormatSelection(mode=SelectionMode.PAIR).choose(video).choose(audio)).with_mode(
        SelectionMode.SINGLE
    )
    assert back.single is video
    assert back.selector() == "137"


def test_switching_to_the_mode_already_active_changes_nothing(
    pair: tuple[FormatInfo, FormatInfo],
) -> None:
    """Otherwise a control that re-emits its state would quietly empty a completed pair."""
    video, audio = pair
    selection = FormatSelection(mode=SelectionMode.PAIR).choose(video).choose(audio)
    assert selection.with_mode(SelectionMode.PAIR) is selection


# --- what it says, and what it refuses to say ------------------------------------------------


def test_an_incomplete_selection_refuses_to_produce_a_selector() -> None:
    """An empty selector means yt-dlp's **default**, not "no choice" (`T-010`).

    Returning `""` would hand `custom_preset` a string `DownloadRequest` refuses — or worse, one it
    accepted, which downloads something the user never picked.
    """
    with pytest.raises(ValueError, match="names no download yet"):
        FormatSelection().selector()
    with pytest.raises(ValueError, match="names no download yet"):
        FormatSelection(mode=SelectionMode.PAIR).selector()


def test_the_pair_is_announced_in_words_with_both_slots_named(
    pair: tuple[FormatInfo, FormatInfo],
) -> None:
    """`docs/UX_SPEC.md` §5: announced as *"video: 137, audio: 140"*, not by highlight.

    `NFR-005` forbids conveying state by colour alone, and a highlighted row is exactly that.
    """
    video, audio = pair
    both = FormatSelection(mode=SelectionMode.PAIR).choose(video).choose(audio)
    assert both.describe() == "video: 137, audio: 140"

    half = FormatSelection(mode=SelectionMode.PAIR).choose(video)
    assert half.describe() == f"video: 137, audio: {NOTHING_CHOSEN}"
    assert NOTHING_CHOSEN in FormatSelection().describe()


# --- the first of the two ffmpeg facts (`REQ-024`) --------------------------------------------


def test_a_stated_merge_is_refused_without_ffmpeg(pair: tuple[FormatInfo, FormatInfo]) -> None:
    """`REQ-024`: refused **before** the download, and the sentence names ffmpeg."""
    video, audio = pair
    stated = FormatSelection(mode=SelectionMode.PAIR).choose(video).choose(audio)
    refusal = merge_refusal(stated, ffmpeg_available=False)
    assert refusal is not None and "ffmpeg" in refusal
    assert merge_refusal(stated, ffmpeg_available=True) is None


def test_a_single_choice_is_never_refused_for_ffmpeg(pair: tuple[FormatInfo, FormatInfo]) -> None:
    """**`T-061`, in the direction it actually failed.**

    The gate that broke was a *selector-reading* one: `bestvideo+bestaudio/best` against a source
    offering one progressive format resolves through `/best` to no merge, and it was refused anyway.
    Nothing here reads a selector — a half-filled pair and a single choice are both statements that
    no merge has been asked for, so neither can be refused for ffmpeg.

    The video-only format is used deliberately: its id is one half of `137+140`, so a check that had
    drifted into scanning ids or selectors would have something to find.
    """
    video, audio = pair
    for selection in (
        FormatSelection().choose(video),
        FormatSelection().choose(audio),
        FormatSelection(mode=SelectionMode.PAIR).choose(video),
    ):
        assert merge_refusal(selection, ffmpeg_available=False) is None, (
            f"{selection.describe()!r} was refused for ffmpeg without a merge being stated"
        )
