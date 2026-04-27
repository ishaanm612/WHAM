#!/usr/bin/env python3
"""Unreal Python worker: import a slice of FBX files into UE content browser.

The worker reads its parameters from environment variables so it can be launched
reliably from command line wrappers on different platforms.
"""

from __future__ import annotations

import math
import os
from pathlib import Path


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _chunk(items: list[str], batch_index: int, num_batches: int) -> list[str]:
    if not items:
        return []
    size = int(math.ceil(len(items) / float(num_batches)))
    start = batch_index * size
    end = min(len(items), start + size)
    return items[start:end]


def _fbx_options(unreal, import_animations: bool, source_skeleton_path: str | None):
    options = unreal.FbxImportUI()
    options.import_as_skeletal = True
    options.import_mesh = True
    options.import_animations = import_animations
    options.import_materials = False
    options.import_textures = False
    options.create_physics_asset = False
    if source_skeleton_path:
        skeleton = unreal.load_asset(source_skeleton_path)
        if skeleton is None:
            unreal.log_warning(
                f"Source skeleton '{source_skeleton_path}' not found; importing without explicit skeleton."
            )
        else:
            options.skeleton = skeleton
    return options


def _import_task(unreal, fbx_path: str, destination_path: str, destination_name: str, options):
    task = unreal.AssetImportTask()
    task.automated = True
    task.replace_existing = False
    task.save = False
    task.filename = fbx_path
    task.destination_path = destination_path
    task.destination_name = destination_name
    task.options = options
    return task


def main() -> None:
    unreal = __import__("unreal")

    input_dir = Path(_require_env("WHAM_UNREAL_INPUT_DIR"))
    dest_root = _require_env("WHAM_UNREAL_DEST_ROOT")
    import_animations = _require_env("WHAM_UNREAL_IMPORT_ANIMATIONS") == "1"
    batch_index = int(_require_env("WHAM_UNREAL_BATCH_INDEX"))
    num_batches = int(_require_env("WHAM_UNREAL_NUM_BATCHES"))
    source_skeleton = os.environ.get("WHAM_UNREAL_IMPORT_SKELETON")

    if not input_dir.exists():
        raise FileNotFoundError(f"Input FBX dir not found: {input_dir}")
    if num_batches < 1:
        raise ValueError("WHAM_UNREAL_NUM_BATCHES must be >= 1")

    fbx_paths = sorted(str(p) for p in input_dir.glob("*.fbx"))
    selected = _chunk(fbx_paths, batch_index=batch_index, num_batches=num_batches)

    unreal.log(
        f"Import worker batch={batch_index}/{num_batches - 1} total={len(fbx_paths)} selected={len(selected)}"
    )
    if not selected:
        unreal.log("No FBX files assigned to this worker batch.")
        return

    options = _fbx_options(unreal, import_animations=import_animations, source_skeleton_path=source_skeleton)
    tasks = unreal.Array(unreal.AssetImportTask)
    for fbx in selected:
        stem = Path(fbx).stem
        destination_path = f"{dest_root}/{stem}"
        if not unreal.EditorAssetLibrary.does_directory_exist(destination_path):
            unreal.EditorAssetLibrary.make_directory(destination_path)
        tasks.append(_import_task(unreal, fbx, destination_path, stem, options))

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    unreal.log(f"Import worker completed batch with {len(selected)} FBX file(s).")


if __name__ == "__main__":
    main()
