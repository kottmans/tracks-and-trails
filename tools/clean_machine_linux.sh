#!/usr/bin/env bash
# Supply the Linux clean machine and run `clean_machine_evidence.sh` on it (`T-318`).
#
#   tools/clean_machine_linux.sh dist/Tracks_and_Trails-0.1.0.dev0-x86_64.AppImage \
#       > docs/project/evidence/linux-0.1.0.dev0.md
#
# **A disposable container rather than a VM**, which is the maintainer's 2026-09-11 narrowing of
# `REL-006`. It is clean the same way Windows Sandbox is clean — by being new — and it costs a
# pull rather than an afternoon.
#
# **`ubuntu:24.04` and not the build image.** `packaging/build_appimage.sh` builds on Debian 12
# (glibc 2.36) so the artifact reaches as far back as possible; this runs it on the oldest LTS the
# README claims. Testing on the machine that built it would prove nothing about either.
#
# **`--appimage-extract-and-run`** because a container has no FUSE. It unpacks and runs the same
# payload; what it does not exercise is the AppImage's own mount, which is the runtime's business
# rather than this application's.
set -euo pipefail

ARTIFACT=${1:?usage: clean_machine_linux.sh <path to .AppImage>}
IMAGE=${IMAGE:-docker.io/library/ubuntu:24.04}
ENGINE=${ENGINE:-podman}

[ -f "$ARTIFACT" ] || { echo "no artifact at $ARTIFACT" >&2; exit 2; }

ROOT=$(cd "$(dirname "$0")/.." && pwd)

# `--pull=always` so a stale local image cannot quietly become the clean machine.
exec "$ENGINE" run --rm --pull=always \
    -v "$(cd "$(dirname "$ARTIFACT")" && pwd)":/artifact:ro,Z \
    -v "$ROOT/tools":/tools:ro,Z \
    -e "RUN_AS=/artifact/$(basename "$ARTIFACT") --appimage-extract-and-run" \
    "$IMAGE" \
    bash -c '
        set -e
        export DEBIAN_FRONTEND=noninteractive
        # Silent because this is the harness setting up, not the evidence. What it installed and
        # why is recorded by the evidence script itself, which also proves what it did *not*.
        apt-get -qq update >/dev/null 2>&1
        apt-get -qq install -y --no-install-recommends ca-certificates libgl1 libegl1 \
            >/dev/null 2>&1
        exec /tools/clean_machine_evidence.sh "'"/artifact/$(basename "$ARTIFACT")"'"
    '
