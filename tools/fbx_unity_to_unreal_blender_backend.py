#!/usr/bin/env python3
"""Headless Blender backend to convert Unity-oriented FBX files for Unreal.

Run via:
    blender -b --python fbx_unity_to_unreal_blender_backend.py -- \
        --input-fbx-dir <dir> --output-fbx-dir <dir>
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path


def _parse_args_from_blender() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-fbx-dir", type=Path, required=True)
    parser.add_argument("--output-fbx-dir", type=Path, required=True)
    parser.add_argument(
        "--filename-suffix",
        default="_UE",
        help="Suffix added to converted output names (default: _UE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List conversions without writing output FBX files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print extra diagnostics",
    )
    return parser.parse_args(argv)


def _reset_scene(bpy):
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _find_primary_armature(bpy):
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found after FBX import")

    def _score(arm_obj):
        pose = arm_obj.pose
        if pose is None:
            return -1
        names = {_normalize_name(b.name) for b in pose.bones}
        targets = {"root", "pelvis", "spine1", "spine2", "hips"}
        return (len(names.intersection(targets)), len(pose.bones))

    return max(armatures, key=_score)


def _collect_export_objects(arm_obj):
    keep = {arm_obj}
    keep.update(child for child in arm_obj.children_recursive if child.type in {"MESH", "ARMATURE"})
    return keep


def _set_deterministic_names(arm_obj, action_name: str):
    arm_obj.name = "Armature"
    if arm_obj.data is not None:
        arm_obj.data.name = "Armature"

    arm_obj.animation_data_create()
    if arm_obj.animation_data is not None and arm_obj.animation_data.action is not None:
        arm_obj.animation_data.action.name = action_name


def _set_scene_timing(bpy, arm_obj):
    scene = bpy.context.scene
    scene.render.fps = 60

    action = None
    if arm_obj.animation_data is not None:
        action = arm_obj.animation_data.action

    if action is None:
        scene.frame_start = 1
        scene.frame_end = 1
        return

    start, end = action.frame_range
    scene.frame_start = int(math.floor(start))
    scene.frame_end = int(math.ceil(end))


def _ensure_finite_object_transforms(objects):
    for obj in objects:
        for row in obj.matrix_world:
            for value in row:
                if not math.isfinite(float(value)):
                    raise ValueError(f"Non-finite transform on object '{obj.name}'")


def _select_for_export(bpy, objects, active_obj):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active_obj


def _convert_one(src_fbx: Path, out_fbx: Path, args, bpy):
    _reset_scene(bpy)
    bpy.ops.import_scene.fbx(filepath=str(src_fbx), use_anim=True)

    arm_obj = _find_primary_armature(bpy)
    export_objects = _collect_export_objects(arm_obj)
    _ensure_finite_object_transforms(export_objects)
    _set_deterministic_names(arm_obj, action_name=f"{out_fbx.stem}_Action")
    _set_scene_timing(bpy, arm_obj)
    _select_for_export(bpy, export_objects, active_obj=arm_obj)

    if args.dry_run:
        print(f"[dry-run] {src_fbx} -> {out_fbx}")
        return

    out_fbx.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(out_fbx),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False,
        use_armature_deform_only=True,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y",
        axis_up="Z",
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_simplify_factor=0.0,
        bake_anim_force_startend_keying=True,
    )
    print(f"[ok] wrote {out_fbx}")
    if args.verbose:
        print(
            f"[info] exported objects={len(export_objects)} "
            f"frames={bpy.context.scene.frame_start}-{bpy.context.scene.frame_end}"
        )


def main():
    args = _parse_args_from_blender()
    if not args.input_fbx_dir.exists():
        raise FileNotFoundError(f"Input FBX directory not found: {args.input_fbx_dir}")

    bpy = __import__("bpy")

    src_fbx_paths = sorted(args.input_fbx_dir.glob("*.fbx"))
    if not src_fbx_paths:
        raise RuntimeError(f"No .fbx files found in {args.input_fbx_dir}")

    converted = 0
    for src_path in src_fbx_paths:
        out_path = args.output_fbx_dir / f"{src_path.stem}{args.filename_suffix}.fbx"
        _convert_one(src_path, out_path, args, bpy)
        converted += 1

    mode = "dry-run listed" if args.dry_run else "exported"
    print(f"[done] {mode} {converted} FBX file(s)")


if __name__ == "__main__":
    main()
