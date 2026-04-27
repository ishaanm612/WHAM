#!/usr/bin/env python3
"""Batch retarget imported WHAM animations to UE5 Manny/Quinn in Unreal.

This launcher runs Unreal in commandlet mode and executes
`ue_retarget_worker.py` with batch slicing, following the BEDLAM pattern.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import subprocess
from pathlib import Path


def _read_paths(paths_json: Path) -> dict:
    with paths_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    for key in ("unreal_editor_cmd", "uproject_path"):
        if not data.get(key):
            raise ValueError(f"Missing '{key}' in {paths_json}")
    return data


def _run_worker(
    batch_index: int,
    num_batches: int,
    unreal_editor_cmd: str,
    uproject_path: str,
    worker_script: Path,
    source_root: str,
    output_root: str,
    ik_retargeter: str,
    target_mesh: str,
    source_ik_rig: str | None,
    target_ik_rig: str | None,
    overwrite_output: bool,
) -> int:
    env = os.environ.copy()
    env["WHAM_UNREAL_SOURCE_ROOT"] = source_root
    env["WHAM_UNREAL_RETARGET_OUT_DIR"] = output_root
    env["WHAM_UNREAL_IK_RETARGETER"] = ik_retargeter
    env["WHAM_UNREAL_TARGET_MESH"] = target_mesh
    env["WHAM_UNREAL_BATCH_INDEX"] = str(batch_index)
    env["WHAM_UNREAL_NUM_BATCHES"] = str(num_batches)
    env["WHAM_UNREAL_OVERWRITE"] = "1" if overwrite_output else "0"
    if source_ik_rig:
        env["WHAM_UNREAL_SOURCE_IK_RIG"] = source_ik_rig
    else:
        env.pop("WHAM_UNREAL_SOURCE_IK_RIG", None)
    if target_ik_rig:
        env["WHAM_UNREAL_TARGET_IK_RIG"] = target_ik_rig
    else:
        env.pop("WHAM_UNREAL_TARGET_IK_RIG", None)

    command = (
        f"\"{unreal_editor_cmd}\" \"{uproject_path}\" "
        f"-run=pythonscript -script=\"{worker_script}\""
    )
    print(f"[run] batch={batch_index}/{num_batches - 1} {command}")
    return subprocess.run(command, shell=True, env=env, check=False).returncode


def _worker_entry(args: tuple) -> None:
    rc = _run_worker(*args)
    if rc != 0:
        raise RuntimeError(f"Unreal retarget worker failed with exit code {rc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-json",
        type=Path,
        default=Path(__file__).with_name("paths.json"),
        help="Path to paths.json with unreal_editor_cmd and uproject_path",
    )
    parser.add_argument(
        "--source-root",
        default="/Game/WHAM/SourceAnimations",
        help="UE content root containing imported source animations",
    )
    parser.add_argument(
        "--output-root",
        default="/Game/WHAM/Retargeted/Manny",
        help="UE content root for retargeted output assets",
    )
    parser.add_argument(
        "--ik-retargeter",
        default=None,
        help="IK Retargeter asset path (if omitted, taken from paths.json)",
    )
    parser.add_argument(
        "--target-mesh",
        default=None,
        help="Target skeletal mesh path (if omitted, taken from paths.json)",
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
        help="Delete existing output assets with same names before writing",
    )
    parser.add_argument(
        "--num-batches",
        type=int,
        default=8,
        help="How many data slices to create (default: 8)",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=4,
        help="How many Unreal processes to run in parallel (default: 4)",
    )
    args = parser.parse_args()

    if args.num_batches < 1:
        raise ValueError("--num-batches must be >= 1")
    if args.processes < 1:
        raise ValueError("--processes must be >= 1")

    paths = _read_paths(args.paths_json)
    ik_retargeter = args.ik_retargeter or paths.get("default_wham_to_manny_ik_retargeter")
    target_mesh = args.target_mesh or paths.get("default_target_manny_mesh")
    source_ik_rig = args.source_ik_rig or paths.get("default_source_ik_rig")
    target_ik_rig = args.target_ik_rig or paths.get("default_target_ik_rig")

    if not ik_retargeter:
        raise ValueError("--ik-retargeter missing and no default in paths.json")
    if not target_mesh:
        raise ValueError("--target-mesh missing and no default in paths.json")

    worker_script = Path(__file__).with_name("ue_retarget_worker.py")
    if not worker_script.exists():
        raise FileNotFoundError(f"Worker script not found: {worker_script}")

    job_args = [
        (
            batch_idx,
            args.num_batches,
            paths["unreal_editor_cmd"],
            paths["uproject_path"],
            worker_script,
            args.source_root,
            args.output_root,
            ik_retargeter,
            target_mesh,
            source_ik_rig,
            target_ik_rig,
            args.overwrite_output,
        )
        for batch_idx in range(args.num_batches)
    ]

    print(f"[info] spawning {args.processes} process(es), {args.num_batches} batch(es)")
    with mp.Pool(processes=args.processes) as pool:
        pool.map(_worker_entry, job_args)
    print("[done] retarget batch completed")


if __name__ == "__main__":
    main()
