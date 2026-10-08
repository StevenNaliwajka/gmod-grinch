#!/usr/bin/env bash
# First-person hands (c_arms) from the same Blender build; called by tools/build.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BL="${BLENDER:-$HOME/sdk/blender/blender-4.2.3-linux-x64/blender}"
BIN="${STUDIOMDL_BIN:-$HOME/sdk/gmod-win/bin}"
GAME="${STUDIOMDL_GAME:-$HOME/sdk/gmod-win/garrysmod}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
S="$ROOT/source"
"$BL" -b --python "$S/scripts/build_grinch.py" -- "$S/data/skeleton.json" "$WORK/grinch.blend" | grep BUILT
"$BL" -b "$WORK/grinch.blend" --python "$S/scripts/export_hands.py" -- "$S/data/skeleton.json" "$S/data/carms_skeleton.json" "$WORK" | grep triangles
( cd "$WORK" && WINEDEBUG=-all wine "$BIN/studiomdl.exe" -game "$(winepath -w "$GAME")" -nop4 c_arms_grinch.qc | tail -1 )
mkdir -p "$ROOT/models/weapons/burrito"
cp "$GAME"/models/weapons/burrito/c_arms_grinch.{mdl,vvd,dx80.vtx,dx90.vtx} "$ROOT/models/weapons/burrito/"
