#!/usr/bin/bash
# One T-289 session, isolated from the maintainer's desktop and from their yt-dlp (`T-289`).
#
# **Nothing here touches the live session.** A disposable `kwin_wayland --virtual` renders to a
# framebuffer, `dbus-run-session` gives it a private bus, and `KWIN_WAYLAND_NO_PERMISSION_CHECKS`
# is set **only on that process** — the override `T-287`'s measurement documented, which is what
# makes an isolated run possible at all. The maintainer's KWin is untouched.
#
# **And nothing touches their yt-dlp.** The whole session gets its own XDG roots, so the update the
# route performs installs into a directory this script created and deletes. That is `T-298`'s
# isolation applied to a measurement instead of to a build gate.
#
#     tools/t289_isolated_session.sh <report-path>
#
# **One session, and it fails when the session fails.** A batch that wants to keep going after a
# bad sample says so itself — `... || true` in the caller's loop — rather than having that choice
# baked in here where the single-session caller cannot see it (`T289-R14`).
set -eu

report=${1:?usage: t289_isolated_session.sh <report-path>}
project=$(cd "$(dirname "$0")/.." && pwd)
# **The postconditions below must be about *this* run** (`T289-R14`, second pass). A report left at
# the target path by an earlier session satisfies every one of them without this session having
# written a byte: seeded with a complete report, a compositor that exits 0 having produced nothing
# passed. Clearing the path first is what makes "the report says the route ran" a statement about
# the run that just happened. The two sidecar logs go with it so a failed run cannot be read
# alongside an earlier run's output.
if ! rm -f "$report" "${report%.txt}-app.log" "${report%.txt}-compositor.log"; then
    echo "t289: cannot clear an earlier report at $report" >&2
    exit 1
fi

profile=$(mktemp -d -t t289-profile-XXXXXX)
mkdir -p "$profile"/{data,config,cache}

cleanup() { rm -rf "$profile" "${inside:-}"; }
trap cleanup EXIT

inside=$(mktemp -t t289-inside-XXXXXX.sh)
cat > "$inside" <<INNER
#!/usr/bin/bash
export XDG_DATA_HOME="$profile/data"
export XDG_CONFIG_HOME="$profile/config"
export XDG_CACHE_HOME="$profile/cache"
"$project/.venv/bin/python" -u "$project/tools/t289_session_watch.py" --drive --report "$report" \
    >"${report%.txt}-app.log" 2>&1
INNER
chmod +x "$inside"

# **`--exit-with-session`, not a bare session argument.** With the positional form the compositor
# outlives the application and the run only ends when `timeout` kills it, which costs ten minutes
# per session and makes a batch impossible. The timeout stays as the backstop it was meant to be.
status=0
timeout 600 dbus-run-session -- env KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 \
    kwin_wayland --virtual --width 1280 --height 800 --socket "wayland-t289-$$" \
    --exit-with-session "$inside" \
    >"${report%.txt}-compositor.log" 2>&1 || status=$?

# **This script used to end that line with `|| true`, and a failed measurement exited 0**
# (`T289-R14`). A replay that put a `dbus-run-session` exiting 42 ahead of the real binary produced
# a wrapper exit of 0 and no report at all — so a timeout, a compositor that never started, and
# plausibly the native abort this instrument exists to expose all arrived looking like a clean
# session. Cleanup is the `trap`'s job and never needed that branch.
#
# **The exit status alone is not enough to trust**, because it comes through `timeout`,
# `dbus-run-session` and a compositor before it reaches here, and none of them promises to
# forward the application's. So the report is checked for what a complete session must contain:
# a `VERDICT` line, and a route that actually ran. An incomplete report is a failed measurement
# even when every process involved exited 0.
if [ "$status" -ne 0 ]; then
    echo "t289: session command failed (exit $status); see ${report%.txt}-compositor.log" >&2
    exit "$status"
fi
if [ ! -s "$report" ]; then
    echo "t289: no report at $report — the session produced nothing" >&2
    exit 1
fi
if ! grep -q 'VERDICT: ' "$report"; then
    echo "t289: $report has no VERDICT line — the session did not finish" >&2
    exit 1
fi
if ! grep -q 'route: settings=True update_started=True update_finished=True' "$report"; then
    echo "t289: $report records an incomplete route — the measurement did not happen" >&2
    exit 1
fi
