#!/usr/bin/env python3
"""Unreal Python worker: export retargeted AnimSequence assets to FBX on disk.

Uses the same Unreal API pattern as bedlam2_retargeting's ``export_fbx.py``
(``AnimSequenceExporterFBX`` + ``AssetExportTask``), but selects assets by
content path and env-driven batching instead of editor selection.

Environment:

- ``WHAM_UNREAL_EXPORT_SOURCE_ROOT`` (required): UE content path root to scan
  for ``AnimSequence`` assets (e.g. ``/Game/WHAM/Retargeted/Manny``).
- ``WHAM_UNREAL_HOST_EXPORT_DIR`` (required): Absolute host directory for
  ``*.fbx`` files (created if missing).
- ``WHAM_UNREAL_EXPORT_MESH`` (optional): ``1`` to set ``bExportPreviewMesh``
  on ``FbxExportOption``, else ``0`` (animation-only).
- ``WHAM_UNREAL_BATCH_INDEX``, ``WHAM_UNREAL_NUM_BATCHES``: batch slicing
  (same convention as other WHAM Unreal workers).
"""

from __future__ import annotations

import math
import os


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


def _class_name(asset) -> str:
    return asset.get_class().get_name()


def _list_anim_sequences(unreal, source_root: str) -> list[str]:
    if not unreal.EditorAssetLibrary.does_directory_exist(source_root):
        raise RuntimeError(
            f"Export source root does not exist in content browser: {source_root}"
        )
    candidates = unreal.EditorAssetLibrary.list_assets(
        source_root, recursive=True, include_folder=False
    )
    anims: list[str] = []
    for path in candidates:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset is None:
            continue
        if _class_name(asset) == "AnimSequence":
            anims.append(path)
    anims.sort()
    return anims


def main() -> None:
    unreal = __import__("unreal")

    source_root = _require_env("WHAM_UNREAL_EXPORT_SOURCE_ROOT")
    host_dir = _require_env("WHAM_UNREAL_HOST_EXPORT_DIR")
    export_mesh = os.environ.get("WHAM_UNREAL_EXPORT_MESH", "0") == "1"
    batch_index = int(_require_env("WHAM_UNREAL_BATCH_INDEX"))
    num_batches = int(_require_env("WHAM_UNREAL_NUM_BATCHES"))

    if num_batches < 1:
        raise ValueError("WHAM_UNREAL_NUM_BATCHES must be >= 1")

    os.makedirs(host_dir, exist_ok=True)

    all_anims = _list_anim_sequences(unreal, source_root=source_root)
    selected = _chunk(all_anims, batch_index=batch_index, num_batches=num_batches)
    unreal.log(
        f"Export FBX worker batch={batch_index}/{num_batches - 1} "
        f"total={len(all_anims)} selected={len(selected)} -> {host_dir}"
    )
    if not selected:
        unreal.log("No AnimSequence assets assigned to this export batch.")
        return

    failures: list[str] = []
    for anim_path in selected:
        try:
            anim = unreal.load_asset(anim_path)
            if anim is None:
                failures.append(f"{anim_path}: load_asset returned None")
                continue
            if not isinstance(anim, unreal.AnimSequence):
                failures.append(f"{anim_path}: not an AnimSequence")
                continue
            name = str(anim.get_name())
            export_task = unreal.AssetExportTask()
            export_task.automated = True
            export_task.object = anim
            export_task.prompt = False
            export_task.filename = os.path.join(host_dir, f"{name}.fbx")
            export_task.options = unreal.FbxExportOption()
            export_task.options.set_editor_property(
                name="bExportPreviewMesh",
                value=export_mesh,
            )
            fbx_exporter = unreal.AnimSequenceExporterFBX()
            export_task.exporter = fbx_exporter
            fbx_exporter.run_asset_export_task(export_task)
            unreal.log(f"[ok] exported {name}.fbx")
        except Exception as exc:
            failures.append(f"{anim_path}: {exc}")

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    if failures:
        raise RuntimeError(
            "FBX export worker failures:\n- " + "\n- ".join(failures)
        )

    unreal.log(f"Export worker completed batch with {len(selected)} file(s).")


if __name__ == "__main__":
    main()
