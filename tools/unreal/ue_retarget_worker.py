#!/usr/bin/env python3
"""Unreal Python worker: retarget a slice of imported source animations.

Requires UE5 IK Rig/Retargeter plugins enabled and a preconfigured IK Retargeter
asset that maps WHAM source chains to Manny/Quinn.
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
    candidates = unreal.EditorAssetLibrary.list_assets(source_root, recursive=True, include_folder=False)
    anims = []
    for path in candidates:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset is None:
            continue
        if _class_name(asset) == "AnimSequence":
            anims.append(path)
    anims.sort()
    return anims


def _find_skeletal_mesh_in_same_folder(unreal, anim_asset_path: str):
    folder = anim_asset_path.rsplit("/", 1)[0]
    for path in unreal.EditorAssetLibrary.list_assets(folder, recursive=False, include_folder=False):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset is None:
            continue
        if _class_name(asset) == "SkeletalMesh":
            return asset
    return None


def _basename(asset_path: str) -> str:
    return asset_path.rsplit("/", 1)[-1]


def main() -> None:
    unreal = __import__("unreal")

    source_root = _require_env("WHAM_UNREAL_SOURCE_ROOT")
    out_dir = _require_env("WHAM_UNREAL_RETARGET_OUT_DIR")
    ik_retargeter_path = _require_env("WHAM_UNREAL_IK_RETARGETER")
    target_mesh_path = _require_env("WHAM_UNREAL_TARGET_MESH")
    batch_index = int(_require_env("WHAM_UNREAL_BATCH_INDEX"))
    num_batches = int(_require_env("WHAM_UNREAL_NUM_BATCHES"))
    overwrite_output = os.environ.get("WHAM_UNREAL_OVERWRITE", "0") == "1"
    source_ik_rig_path = os.environ.get("WHAM_UNREAL_SOURCE_IK_RIG")
    target_ik_rig_path = os.environ.get("WHAM_UNREAL_TARGET_IK_RIG")

    if not unreal.EditorAssetLibrary.does_directory_exist(source_root):
        raise RuntimeError(f"Source root does not exist in UE content browser: {source_root}")
    if not unreal.EditorAssetLibrary.does_directory_exist(out_dir):
        unreal.EditorAssetLibrary.make_directory(out_dir)

    target_mesh = unreal.load_asset(target_mesh_path)
    if target_mesh is None:
        raise RuntimeError(f"Could not load target skeletal mesh: {target_mesh_path}")
    retargeter = unreal.load_asset(ik_retargeter_path)
    if retargeter is None:
        raise RuntimeError(f"Could not load IK Retargeter: {ik_retargeter_path}")

    controller = unreal.IKRetargeterController.get_controller(retargeter)
    if source_ik_rig_path:
        src_ik_rig = unreal.load_asset(source_ik_rig_path)
        if src_ik_rig is None:
            raise RuntimeError(f"Could not load source IK Rig: {source_ik_rig_path}")
        controller.set_ik_rig(unreal.RetargetSourceOrTarget.SOURCE, src_ik_rig)
    if target_ik_rig_path:
        tgt_ik_rig = unreal.load_asset(target_ik_rig_path)
        if tgt_ik_rig is None:
            raise RuntimeError(f"Could not load target IK Rig: {target_ik_rig_path}")
        controller.set_ik_rig(unreal.RetargetSourceOrTarget.TARGET, tgt_ik_rig)

    all_anims = _list_anim_sequences(unreal, source_root=source_root)
    selected_anims = _chunk(all_anims, batch_index=batch_index, num_batches=num_batches)
    unreal.log(
        f"Retarget worker batch={batch_index}/{num_batches - 1} total={len(all_anims)} selected={len(selected_anims)}"
    )
    if not selected_anims:
        unreal.log("No animation assets assigned to this worker batch.")
        return

    asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    failures: list[str] = []
    for anim_path in selected_anims:
        source_mesh = _find_skeletal_mesh_in_same_folder(unreal, anim_path)
        if source_mesh is None:
            failures.append(f"{anim_path}: missing source SkeletalMesh in same folder")
            continue

        controller.set_preview_mesh(unreal.RetargetSourceOrTarget.SOURCE, source_mesh)
        controller.set_preview_mesh(unreal.RetargetSourceOrTarget.TARGET, target_mesh)
        controller.auto_map_chains(unreal.AutoMapChainType.FUZZY, True)

        anim_data = asset_subsystem.find_asset_data(anim_path)
        if not anim_data.is_valid():
            failures.append(f"{anim_path}: invalid asset data")
            continue

        source_token = _basename(anim_path)
        prefix = f"{source_token}+"
        outputs = unreal.IKRetargetBatchOperation.duplicate_and_retarget(
            [anim_data],
            source_mesh,
            target_mesh,
            retargeter,
            search="",
            replace="",
            prefix=prefix,
            suffix="",
        )

        for created in outputs:
            old_path = str(created.package_name)
            old_name = old_path.rsplit("/", 1)[-1]
            new_path = f"{out_dir}/{old_name}"
            if overwrite_output and unreal.EditorAssetLibrary.does_asset_exist(new_path):
                unreal.EditorAssetLibrary.delete_asset(new_path)
            renamed = unreal.EditorAssetLibrary.rename_asset(old_path, new_path)
            if not renamed:
                failures.append(f"{anim_path}: failed to move '{old_path}' -> '{new_path}'")

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
        save_map_packages=True,
        save_content_packages=True,
    )
    if failures:
        raise RuntimeError("Retarget worker failures:\n- " + "\n- ".join(failures))

    unreal.log(f"Retarget worker completed batch with {len(selected_anims)} AnimSequence asset(s).")


if __name__ == "__main__":
    main()
