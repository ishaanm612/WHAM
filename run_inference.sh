#!/usr/bin/env bash
# Run WHAM on a single video, then export Unity + Unreal-ready FBX (no UE retargeting).
# Usage: see --help. Run from any directory; always uses this repo as WHAM_ROOT.

set -euo pipefail

WHAM_ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$WHAM_ROOT"

PYTHON=${PYTHON:-python}
OUTPUT_PTH="output/demo"
VIDEO=""
CALIB=""
VISUALIZE=false
ESTIMATE_LOCAL_ONLY=false
RUN_SMPLIFY=false
BLENDER_EXE=""
SMPL_TO_FBX_ROOT=""
FBX_SOURCE_PATH=""
CONVERT_BACKEND=""

usage() {
  sed 's/^|//' <<'EOF' | cat
|Usage: run_video_to_unreal_fbx.sh [options] <input_video>
|
|  1) demo.py --save_pkl (inference)
|  2) tools/convert_wham_output_to_smpl2fbx.py --run-convert --run-unreal-convert
|
|Options:
|  -o, --output-pth DIR   Base output dir (default: output/demo). Per-video subfolder
|                         is named from the video basename (see demo.py).
|  -c, --calib FILE       Optional camera calib for SLAM [fx fy cx cy]
|  -v, --visualize        Pass --visualize to demo
|  -l, --estimate-local-only
|                         Pass --estimate_local_only (no global / SLAM)
|  -s, --run-smplify     Pass --run_smplify to demo
|      --blender-exe PATH
|  --smpl-to-fbx-root PATH
|  --fbx-source-path PATH
|  --convert-backend {bpy,fbxsdk}
|  -h, --help
|
|Env: PYTHON=python3 to pick interpreter.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -o|--output-pth) OUTPUT_PTH=$2; shift 2 ;;
    -c|--calib) CALIB=$2; shift 2 ;;
    -v|--visualize) VISUALIZE=true; shift ;;
    -l|--estimate-local-only) ESTIMATE_LOCAL_ONLY=true; shift ;;
    -s|--run-smplify) RUN_SMPLIFY=true; shift ;;
    --blender-exe) BLENDER_EXE=$2; shift 2 ;;
    --smpl-to-fbx-root) SMPL_TO_FBX_ROOT=$2; shift 2 ;;
    --fbx-source-path) FBX_SOURCE_PATH=$2; shift 2 ;;
    --convert-backend) CONVERT_BACKEND=$2; shift 2 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    *)
      if [[ -n "$VIDEO" ]]; then
        echo "Unexpected extra argument: $1" >&2
        exit 1
      fi
      VIDEO=$1
      shift
      ;;
  esac
done

if [[ -z "$VIDEO" ]]; then
  echo "Error: <input_video> is required." >&2
  usage >&2
  exit 1
fi

if [[ ! -f "$VIDEO" ]]; then
  echo "Error: input video not found: $VIDEO" >&2
  exit 1
fi

# Same stem rule as demo.py: basename, strip last extension
base=$(basename "$VIDEO")
seq=${base%.*}
OUT_DIR=${OUTPUT_PTH}/${seq}
WHAM_PKL=${OUT_DIR}/wham_output.pkl

echo "==> WHAM inference: $VIDEO -> $OUT_DIR"
DEMO_CMD=(
  "$PYTHON" demo.py
  --video "$VIDEO"
  --output_pth "$OUTPUT_PTH"
  --save_pkl
)
if [[ -n "$CALIB" ]]; then
  DEMO_CMD+=(--calib "$CALIB")
fi
if $VISUALIZE; then
  DEMO_CMD+=(--visualize)
fi
if $ESTIMATE_LOCAL_ONLY; then
  DEMO_CMD+=(--estimate_local_only)
fi
if $RUN_SMPLIFY; then
  DEMO_CMD+=(--run_smplify)
fi

"${DEMO_CMD[@]}"

if [[ ! -f "$WHAM_PKL" ]]; then
  echo "Error: expected WHAM pkl at $WHAM_PKL" >&2
  exit 1
fi

echo "==> SMPL/FBX + Unreal FBX: $WHAM_PKL"
CONV_CMD=(
  "$PYTHON" tools/convert_wham_output_to_smpl2fbx.py
  --wham-output "$WHAM_PKL"
  --output-pkl-dir "$OUT_DIR/smpl_to_fbx_pkls"
  --run-convert
  --fbx-output-dir "$OUT_DIR/unity_fbx"
  --run-unreal-convert
  --unreal-fbx-dir "$OUT_DIR/unreal_fbx"
)
if [[ -n "$BLENDER_EXE" ]]; then
  CONV_CMD+=(--blender-exe "$BLENDER_EXE")
fi
if [[ -n "$SMPL_TO_FBX_ROOT" ]]; then
  CONV_CMD+=(--smpl-to-fbx-root "$SMPL_TO_FBX_ROOT")
fi
if [[ -n "$FBX_SOURCE_PATH" ]]; then
  CONV_CMD+=(--fbx-source-path "$FBX_SOURCE_PATH")
fi
if [[ -n "$CONVERT_BACKEND" ]]; then
  CONV_CMD+=(--convert-backend "$CONVERT_BACKEND")
fi

"${CONV_CMD[@]}"

echo "Done. Outputs under: $OUT_DIR"
echo "  wham_output.pkl, smpl_to_fbx_pkls/, unity_fbx/, unreal_fbx/"