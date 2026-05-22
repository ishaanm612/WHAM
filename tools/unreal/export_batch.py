#!/usr/bin/env python3
"""Batch-export retargeted AnimSequence assets to Manny-skeleton FBX on disk.

Runs Unreal in commandlet mode and executes ``ue_export_fbx_worker.py`` with
batch slicing, matching ``import_batch`` / ``retarget_batch`` patterns and
bedlam2-style parallel workers.
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
    host_export_dir: str,
    export_mesh: bool,
) -> int:
    env = os.environ.copy()
    env["WHAM_UNREAL_EXPORT_SOURCE_ROOT"] = source_root
    env["WHAM_UNREAL_HOST_EXPORT_DIR"] = host_export_dir
    env["WHAM_UNREAL_EXPORT_MESH"] = "1" if export_mesh else "0"
    env["WHAM_UNREAL_BATCH_INDEX"] = str(batch_index)
    env["WHAM_UNREAL_NUM_BATCHES"] = str(num_batches)

    command = (
        f"\"{unreal_editor_cmd}\" \"{uproject_path}\" "
        f"-run=pythonscript -script=\"{worker_script}\""
    )
    print(f"[run] batch={batch_index}/{num_batches - 1} {command}")
    return subprocess.run(command, shell=True, env=env, check=False).returncode


def _worker_entry(args: tuple) -> None:
    rc = _run_worker(*args)
    if rc != 0:
        raise RuntimeError(f"Unreal export worker failed with exit code {rc}")


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
        default="/Game/WHAM/Retargeted/Manny",
        help="UE content root containing retargeted AnimSequence assets to export",
    )
    parser.add_argument(
        "--host-export-dir",
        type=Path,
        required=True,
        help="Absolute host directory where .fbx files are written (must be writable)",
    )
    parser.add_argument(
        "--export-mesh",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Set FbxExportOption bExportPreviewMesh (default: false, animation only)",
    )
    parser.add_argument(
        "--num-batches",
        type=int,
        default=4,
        help="How many data slices to create (default: 4)",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=2,
        help="How many Unreal processes to run in parallel (default: 2)",
    )
    args = parser.parse_args()

    if args.num_batches < 1:
        raise ValueError("--num-batches must be >= 1")
    if args.processes < 1:
        raise ValueError("--processes must be >= 1")
    host_dir = args.host_export_dir.resolve()
    host_dir.mkdir(parents=True, exist_ok=True)

    paths = _read_paths(args.paths_json)
    worker_script = Path(__file__).with_name("ue_export_fbx_worker.py")
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
            str(host_dir),
            args.export_mesh,
        )
        for batch_idx in range(args.num_batches)
    ]

    print(f"[info] spawning {args.processes} process(es), {args.num_batches} batch(es)")
    print(f"[info] host export dir: {host_dir}")
    with mp.Pool(processes=args.processes) as pool:
        pool.map(_worker_entry, job_args)
    print("[done] export batch completed")


if __name__ == "__main__":
    main()
