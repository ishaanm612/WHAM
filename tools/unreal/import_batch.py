#!/usr/bin/env python3
"""Batch-import Unreal-ready FBX files into a UE project.

This launcher runs Unreal in commandlet mode and executes `ue_import_fbx_worker.py`
multiple times (one subset per process), similar to BEDLAM batch import.
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
    input_dir: Path,
    destination_root: str,
    import_animations: bool,
    source_skeleton_path: str | None,
) -> int:
    env = os.environ.copy()
    env["WHAM_UNREAL_INPUT_DIR"] = str(input_dir)
    env["WHAM_UNREAL_DEST_ROOT"] = destination_root
    env["WHAM_UNREAL_IMPORT_ANIMATIONS"] = "1" if import_animations else "0"
    env["WHAM_UNREAL_BATCH_INDEX"] = str(batch_index)
    env["WHAM_UNREAL_NUM_BATCHES"] = str(num_batches)
    if source_skeleton_path:
        env["WHAM_UNREAL_IMPORT_SKELETON"] = source_skeleton_path
    else:
        env.pop("WHAM_UNREAL_IMPORT_SKELETON", None)

    command = (
        f"\"{unreal_editor_cmd}\" \"{uproject_path}\" "
        f"-run=pythonscript -script=\"{worker_script}\""
    )
    print(f"[run] batch={batch_index}/{num_batches - 1} {command}")
    return subprocess.run(command, shell=True, env=env, check=False).returncode


def _worker_entry(args: tuple) -> None:
    rc = _run_worker(*args)
    if rc != 0:
        raise RuntimeError(f"Unreal import worker failed with exit code {rc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-json",
        type=Path,
        default=Path(__file__).with_name("paths.json"),
        help="Path to paths.json with unreal_editor_cmd and uproject_path",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Absolute or local filesystem path containing FBX files",
    )
    parser.add_argument(
        "--destination-root",
        default="/Game/WHAM/SourceAnimations",
        help="UE content root for imported sources (default: /Game/WHAM/SourceAnimations)",
    )
    parser.add_argument(
        "--import-animations",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Import animation tracks from FBX (default: true)",
    )
    parser.add_argument(
        "--source-skeleton-path",
        default=None,
        help="Optional UE skeleton asset path to reuse during import",
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

    if not args.input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {args.input_dir}")
    if args.num_batches < 1:
        raise ValueError("--num-batches must be >= 1")
    if args.processes < 1:
        raise ValueError("--processes must be >= 1")

    paths = _read_paths(args.paths_json)
    worker_script = Path(__file__).with_name("ue_import_fbx_worker.py")
    if not worker_script.exists():
        raise FileNotFoundError(f"Worker script not found: {worker_script}")

    job_args = [
        (
            batch_idx,
            args.num_batches,
            paths["unreal_editor_cmd"],
            paths["uproject_path"],
            worker_script,
            args.input_dir,
            args.destination_root,
            args.import_animations,
            args.source_skeleton_path,
        )
        for batch_idx in range(args.num_batches)
    ]

    print(f"[info] spawning {args.processes} process(es), {args.num_batches} batch(es)")
    with mp.Pool(processes=args.processes) as pool:
        pool.map(_worker_entry, job_args)
    print("[done] import batch completed")


if __name__ == "__main__":
    main()
