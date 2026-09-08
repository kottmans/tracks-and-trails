#!/usr/bin/bash
# Put the **pre-fix** application on your own display so `T-297` can be captured (`T297-R1`).
#
# **Why this exists.** `T-297`'s first criterion asks for the flicker reproduced *on a real display,
# with a capture*. Every measurement so far was taken on a nested `kwin_wayland --virtual`, and the
# image in `docs/project/evidence/` is a labelled reconstruction of the measured geometry rather than a frame
# of the defect. The reviewer ruled that insufficient and the maintainer chose to run it for real.
#
# **Nothing in your checkout is modified.** The pre-fix tree is a `git worktree` at `331845d` — the
# commit before the fix — and `PYTHONPATH` points the interpreter at *that* `src`, which is the trap
# `AGENTS.md` §9 records: `.venv` is an editable install pointing at the primary checkout, so
# without the override you would be running the fixed code and seeing nothing.
#
#     tools/t297_prefix_capture.sh            # set up and launch
#     tools/t297_prefix_capture.sh --clean    # remove the worktree afterwards
set -eu

project=$(cd "$(dirname "$0")/.." && pwd)
tree="$project/../tracks-and-trails-t297-prefix"
prefix=331845d

if [ "${1:-}" = "--clean" ]; then
    git -C "$project" worktree remove --force "$tree" 2>/dev/null || true
    git -C "$project" worktree prune
    echo "t297: pre-fix worktree removed."
    exit 0
fi

if [ ! -d "$tree" ]; then
    git -C "$project" worktree add --detach "$tree" "$prefix"
fi

cat <<'GUIDE'

────────────────────────────────────────────────────────────────────────────
T-297 — capture the flicker on a real display
────────────────────────────────────────────────────────────────────────────

The window that is about to open is the tree **before** the fix, so the defect
is present. Your own checkout is untouched.

1. Paste a URL with a thumbnail and let it resolve.
       https://archive.org/details/TheArtOfWarBySunTzu   (the fixture's row)
2. On that row choose  ⋮ → Naming and folders…   so the panel opens.
3. **Drag the window's bottom edge up and down**, continuously, a few seconds.
   The thumbnail should cut in and out — that is the defect.
4. Capture it while dragging. Any of these is a real capture:
       • KDE screen recording  (Meta+Shift+R, or Spectacle → Record)
       • Spectacle rectangular region, repeatedly, mid-drag
       • a phone video of the screen — genuinely acceptable evidence here
5. Save it as
       docs/project/evidence/2026-09-04-T297-real-display-capture.<ext>

If the flicker does NOT appear, that is a result worth having too — say so and
do not manufacture one. It would mean the nested compositor exaggerates it.

When you are done:  tools/t297_prefix_capture.sh --clean
────────────────────────────────────────────────────────────────────────────

GUIDE

echo "t297: launching the pre-fix tree from $tree"
PYTHONPATH="$tree/src" exec "$project/.venv/bin/python" -m tracks_and_trails
