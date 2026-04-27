#!/usr/bin/env python3
"""Run import + retarget stages for WHAM Unreal FBX files.

This script mirrors BEDLAM's two-stage batch flow:
1) Import FBX files into Unreal
2) Retarget imported AnimSequence assets to Manny/Quinn
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    print("[run]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-json",
        type=Path,
        default=Path(__file__).with_name("paths.json"),
        help="Path to Unreal launcher configuration JSON",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory with Unreal-ready WHAM FBX files (e.g. *_UE.fbx)",
    )
    parser.add_argument(
        "--source-root",
        default="/Game/WHAM/SourceAnimations",
        help="UE destination root for imported source assets",
    )
    parser.add_argument(
        "--output-root",
        default="/Game/WHAM/Retargeted/Manny",
        help="UE destination root for retargeted AnimSequence assets",
    )
    parser.add_argument(
        "--num-batches",
        type=int,
        default=8,
        help="Number of slices used by import/retarget workers",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=4,
        help="Concurrent Unreal processes for each stage",
    )
    parser.add_argument(
        "--ik-retargeter",
        default=None,
        help="Optional IK Retargeter path override",
    )
    parser.add_argument(
        "--target-mesh",
        default=None,
        help="Optional target skeletal mesh path override",
    )
    parser.add_argument(
        "--source-ik-rig",
        default=None,
        help="Optional source IK Rig path override",
    )
    parser.add_argument(
        "--target-ik-rig",
        default=None,
        help="Optional target IK Rig path override",
    )
    parser.add_argument(
        "--overwrite-output",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Overwrite existing retargeted output assets when names collide",
    )
    args = parser.parse_args()

    import_script = Path(__file__).with_name("import_batch.py")
    retarget_script = Path(__file__).with_name("retarget_batch.py")

    import_cmd = [
        sys.executable,
        str(import_script),
        "--paths-json",
        str(args.paths_json),
        "--input-dir",
        str(args.input_dir),
        "--destination-root",
        args.source_root,
        "--num-batches",
        str(args.num_batches),
        "--processes",
        str(args.processes),
    ]
    _run(import_cmd)

    retarget_cmd = [
        sys.executable,
        str(retarget_script),
        "--paths-json",
        str(args.paths_json),
        "--source-root",
        args.source_root,
        "--output-root",
        args.output_root,
        "--num-batches",
        str(args.num_batches),
        "--processes",
        str(args.processes),
    ]
    if args.ik_retargeter:
        retarget_cmd.extend(["--ik-retargeter", args.ik_retargeter])
    if args.target_mesh:
        retarget_cmd.extend(["--target-mesh", args.target_mesh])
    if args.source_ik_rig:
        retarget_cmd.extend(["--source-ik-rig", args.source_ik_rig])
    if args.target_ik_rig:
        retarget_cmd.extend(["--target-ik-rig", args.target_ik_rig])
    if args.overwrite_output:
        retarget_cmd.append("--overwrite-output")
    _run(retarget_cmd)

    print("[done] WHAM->Manny automation pipeline completed")


if __name__ == "__main__":
    main()
