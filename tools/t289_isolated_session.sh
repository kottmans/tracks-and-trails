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
set -eu

report=${1:?usage: t289_isolated_session.sh <report-path>}
project=$(cd "$(dirname "$0")/.." && pwd)
profile=$(mktemp -d -t t289-profile-XXXXXX)
mkdir -p "$profile"/{data,config,cache}

cleanup() { rm -rf "$profile"; }
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
timeout 600 dbus-run-session -- env KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 \
    kwin_wayland --virtual --width 1280 --height 800 --socket "wayland-t289-$$" \
    --exit-with-session "$inside" \
    >"${report%.txt}-compositor.log" 2>&1 || true
rm -f "$inside"
