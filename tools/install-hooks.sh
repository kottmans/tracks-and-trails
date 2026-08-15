#!/usr/bin/env bash
# Point this clone's hooks at the version-controlled ones in `.githooks/` (`T-240`).
#
#     tools/install-hooks.sh
#
# **`core.hooksPath` rather than copying into `.git/hooks`.** A copy is a second version that goes
# stale the moment the hook changes, and nothing would say so. This way the hook under review is
# the hook that runs.
#
# It is a **per-clone** step, like `git config user.email`, because repo-local config does not
# survive a fresh clone. That is the gap this cannot close on its own, and it is why the CI check
# exists beside it: a hook catches the defect while amending is still free, and a hook that was
# never installed catches nothing.
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
chmod +x .githooks/*
echo "core.hooksPath -> .githooks"
echo "Hooks active in this clone:"
for hook in .githooks/*; do
    [ -f "$hook" ] && echo "  $(basename "$hook")"
done
