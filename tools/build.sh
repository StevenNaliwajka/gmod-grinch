#!/usr/bin/env bash
# Rebuild the player model from source/: Blender builds the mesh around GMod's ValveBiped
# skeleton, writes SMD + QC, and GMod's own studiomdl (Windows, under wine) compiles it.
#
#   BLENDER=... STUDIOMDL_GAME=... tools/build.sh
#
# BLENDER         blender 4.2 binary            (default ~/sdk/blender/blender-4.2.3-linux-x64/blender)
# STUDIOMDL_BIN   GMod's bin/ with studiomdl.exe (default ~/sdk/gmod-win/bin, from depot 4002)
# STUDIOMDL_GAME  a garrysmod dir with gameinfo.txt (default ~/sdk/gmod-win/garrysmod)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BL="${BLENDER:-$HOME/sdk/blender/blender-4.2.3-linux-x64/blender}"
BIN="${STUDIOMDL_BIN:-$HOME/sdk/gmod-win/bin}"
GAME="${STUDIOMDL_GAME:-$HOME/sdk/gmod-win/garrysmod}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
S="$ROOT/source"
"$BL" -b --python "$S/scripts/build_grinch.py" -- "$S/data/skeleton.json" "$WORK/grinch.blend" | grep BUILT
"$BL" -b "$WORK/grinch.blend" --python "$S/scripts/export_smd.py" -- "$S/data/skeleton.json" "$S/data/meta.json" "$S/data/ref_male07.phy" "$WORK" | grep -E "triangles|QC"
python3 "$S/scripts/make_materials.py" "$ROOT/materials/models/player/burrito/grinch_ultimatum"
( cd "$WORK" && WINEDEBUG=-all wine "$BIN/studiomdl.exe" -game "$(winepath -w "$GAME")" -nop4 grinch.qc | tail -2 )
cp "$GAME"/models/player/burrito/grinch_ultimatum.{mdl,vvd,phy,dx80.vtx,dx90.vtx} "$ROOT/models/player/burrito/"
"$ROOT/tools/build_hands.sh"
echo "built $ROOT/models/player/burrito/grinch_ultimatum.mdl"
