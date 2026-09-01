#!/usr/bin/bash
# One `T-297` reading, on a compositor, isolated from the maintainer's desktop.
#
# **Offscreen cannot answer this question and the probe says why**: it coalesces paints, so ~110
# resize steps produced 29 of them. A drag on a real compositor paints per frame, and what `T-297`
# is about is the frames *between* two settled states. So the same instrument is run again here.
#
# **Nothing touches the live session.** A disposable `kwin_wayland --virtual` renders to its own
# framebuffer, `dbus-run-session` gives it a private bus, and the whole run gets its own XDG roots
# — the isolation `tools/t289_isolated_session.sh` established, reused rather than re-argued.
#
#     tools/t297_resize_session.sh <report-path>
set -eu

report=${1:?usage: t297_resize_session.sh <report-path>}
project=$(cd "$(dirname "$0")/.." && pwd)

# The report must be about *this* run: a file left by an earlier session satisfies every check
# below without a byte being written now (`T289-R14`).
rm -f "$report" "${report%.txt}-run.log" "${report%.txt}-compositor.log"

profile=$(mktemp -d -t t297-profile-XXXXXX)
mkdir -p "$profile"/{data,config,cache}
inside=$(mktemp -t t297-inside-XXXXXX.sh)
cleanup() { rm -rf "$profile" "$inside"; }
trap cleanup EXIT

cat > "$inside" <<INNER
#!/usr/bin/bash
export XDG_DATA_HOME="$profile/data"
export XDG_CONFIG_HOME="$profile/config"
export XDG_CACHE_HOME="$profile/cache"
# **Exported, not defaulted.** \`tests/ui/conftest.py\` uses \`setdefault\`, so an explicit value
# from here is what makes the run use the compositor instead of the offscreen platform.
export QT_QPA_PLATFORM=wayland
export T297_REPORT="$report"
export T297_CAPTURE="${report%.txt}-exposed.png"
"$project/.venv/bin/python" -u -m pytest \
    "$project/tests/ui/_t297_resize_probe.py" -q -s -p no:randomly \
    >"${report%.txt}-run.log" 2>&1
INNER
chmod +x "$inside"

status=0
timeout 600 dbus-run-session -- env KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 \
    kwin_wayland --virtual --width 1400 --height 900 --socket "wayland-t297-$$" \
    --exit-with-session "$inside" \
    >"${report%.txt}-compositor.log" 2>&1 || status=$?

if [ "$status" -ne 0 ]; then
    echo "t297: session failed (exit $status); see ${report%.txt}-run.log" >&2
    exit "$status"
fi
if [ ! -s "$report" ]; then
    echo "t297: no report at $report — the session produced nothing" >&2
    exit 1
fi
if ! grep -q 'VERDICT: ' "$report"; then
    echo "t297: $report has no VERDICT line — the session did not finish" >&2
    exit 1
fi
cat "$report"
