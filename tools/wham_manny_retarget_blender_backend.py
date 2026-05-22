#!/usr/bin/env python3
"""Headless Blender: retarget WHAM/SMPL source FBX animation onto a Mannequin-style target FBX.

Uses **world-space** pose per bone for each mapped pair (v0 prototype).
Child bones are pinned to their parents to prevent mesh distortion, while 
split-root bones maintain translation.

Run via:
    blender -b --python wham_manny_retarget_blender_backend.py -- \
        --source-fbx <wham_anim_fbx> --target-rig-fbx <manny_mesh_fbx> \
        --mapping-json <smpl_to_manny_retarget_map.json> --output-fbx <out.fbx>
"""

from __future__ import annotations

from typing import Any, Optional

import argparse
import json
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
    parser.add_argument("--source-fbx", type=Path, required=True, help="WHAM/SMPL animated FBX")
    parser.add_argument(
        "--target-rig-fbx",
        type=Path,
        required=True,
        help="Mannequin-style skeletal mesh FBX (mesh + armature)",
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        required=True,
        help="JSON with bone_pairs list (source SMPL name -> target rig name)",
    )
    parser.add_argument("--output-fbx", type=Path, required=True, help="Output FBX path")
    parser.add_argument(
        "--blender-verbose",
        action="store_true",
        help="Print diagnostics for bone resolution and frame range",
    )
    return parser.parse_args(argv)


def _reset_scene(bpy):
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _find_bone(pose_bones, name: str):
    if name in pose_bones:
        return pose_bones[name]
    target_norm = _normalize_name(name)
    for pb in pose_bones:
        if _normalize_name(pb.name) == target_norm:
            return pb
    return None


def _pick_armature(
    bpy, objects: Optional[set[Any]] = None, prefer_prefix: str = ""
) -> object:
    if objects is None:
        pool = list(bpy.data.objects)
    else:
        pool = list(objects)
    arms = [o for o in pool if o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError("No armature found after FBX import")
    if prefer_prefix:
        for o in arms:
            if prefer_prefix.lower() in o.name.lower():
                return o
    return max(arms, key=lambda o: len(o.data.bones))


def _load_mapping(path: Path) -> list[tuple[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    pairs = data.get("bone_pairs")
    if not pairs:
        raise ValueError("mapping JSON must contain 'bone_pairs' array")
    out: list[tuple[str, str]] = []
    for item in pairs:
        if isinstance(item, dict):
            s, t = item.get("source"), item.get("target")
            if not s or not t:
                raise ValueError(f"Invalid bone pair entry: {item}")
            out.append((str(s), str(t)))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            out.append((str(item[0]), str(item[1])))
        else:
            raise ValueError(f"Invalid bone pair entry: {item}")
    return out


def _action_frame_range(src_arm) -> tuple[int, int]:
    if not src_arm.animation_data or not src_arm.animation_data.action:
        return 1, 250
    act = src_arm.animation_data.action
    return int(math.floor(act.frame_range[0])), int(math.ceil(act.frame_range[1]))


def _retarget_frames(bpy, src_arm, tgt_arm, pairs: list[tuple[str, str]], verbose: bool):
    import mathutils
    import math
    scene = bpy.context.scene
    
    # Resolve bones
    resolved = []
    for sn, tn in pairs:
        sb = _find_bone(src_arm.pose.bones, sn)
        tb = _find_bone(tgt_arm.pose.bones, tn)
        if sb and tb:
            resolved.append((sb, tb, sn, tn))

    # Sort by depth (Hierarchy order)
    def get_bone_depth(bone):
        depth = 0
        p = bone.parent
        while p: depth += 1; p = p.parent
        return depth
    resolved.sort(key=lambda x: get_bone_depth(x[1].bone))

    f0, f1 = _action_frame_range(src_arm)

    # --- COORDINATE SYSTEM CORRECTION ---
    # WHAM is often Y-up. Blender is Z-up. 
    # This creates a 90-degree offset on the X axis.
    global_correction = mathutils.Euler((math.radians(-90), 0, 0)).to_matrix().to_3x3()

    # Pre-compute Rest States
    R_src_rest = {sn: sb.bone.matrix_local.to_3x3() for sb, tb, sn, tn in resolved}
    R_tgt_rest = {tn: tb.bone.matrix_local.to_3x3() for sb, tb, sn, tn in resolved}
    
    # Cache local rest orientations (Target Space)
    R_tgt_local_rest = {}
    for sb, tb, sn, tn in resolved:
        if tb.bone.parent:
            R_tgt_local_rest[tn] = tb.bone.parent.matrix_local.to_3x3().inverted() @ tb.bone.matrix_local.to_3x3()
        else:
            R_tgt_local_rest[tn] = tb.bone.matrix_local.to_3x3()

    # Action Setup
    if tgt_arm.animation_data is None: tgt_arm.animation_data_create()
    act = bpy.data.actions.new(name="Fixed_Retarget")
    tgt_arm.animation_data.action = act

    for frame in range(f0, f1 + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        computed_world_rots = {}

        for sb, tb, sn, tn in resolved:
            # 1. Get Source Pose Rotation
            R_src_pose = sb.matrix.to_3x3()
            
            # 2. Calculate the "Animation Delta" in Source Space
            # Delta = Pose * Rest_Inv
            Delta_R = R_src_pose @ R_src_rest[sn].inverted()
            
            # 3. Apply the global coordinate correction to the Delta
            # This rotates the "movement" itself to match Blender's Z-up world
            Corrected_Delta = global_correction @ Delta_R @ global_correction.inverted()
            
            # 4. Target World Rotation = Corrected Delta applied to Target Rest
            R_desired_world = Corrected_Delta @ R_tgt_rest[tn]
            computed_world_rots[tn] = R_desired_world

            # 5. Solve for Local Rotation (FK)
            if tb.parent and tb.parent.name in computed_world_rots:
                R_parent_world = computed_world_rots[tb.parent.name]
            elif tb.parent:
                R_parent_world = tb.parent.matrix.to_3x3()
            else:
                R_parent_world = mathutils.Matrix.Identity(3)

            # Local_Pose = (Parent_World * Local_Rest)^-1 * Desired_World
            R_local_pose = (R_parent_world @ R_tgt_local_rest[tn]).inverted() @ R_desired_world
            
            tb.rotation_mode = 'QUATERNION'
            tb.rotation_quaternion = R_local_pose.to_quaternion()
            
            # Pin location for now as requested
            tb.location = (0,0,0)
            
            # Keyframe
            tb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            tb.keyframe_insert(data_path="location", frame=frame)

    scene.frame_set(f0)

def _export_fbx(bpy, filepath: Path, objects: list):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    filepath.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(filepath),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y",
        axis_up="Z",
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_simplify_factor=0.0,
    )


def main(bpy):
    args = _parse_args_from_blender()

    if not args.source_fbx.exists():
        raise FileNotFoundError(f"Source FBX not found: {args.source_fbx}")
    if not args.target_rig_fbx.exists():
        raise FileNotFoundError(f"Target rig FBX not found: {args.target_rig_fbx}")
    if not args.mapping_json.exists():
        raise FileNotFoundError(f"Mapping JSON not found: {args.mapping_json}")

    pairs = _load_mapping(args.mapping_json)
    _reset_scene(bpy)

    bpy.ops.import_scene.fbx(filepath=str(args.source_fbx), use_anim=True)
    objects_after_source = set(bpy.data.objects)
    src_arm = _pick_armature(bpy, objects_after_source)

    bpy.ops.import_scene.fbx(filepath=str(args.target_rig_fbx), use_anim=False)
    objects_after_target = set(bpy.data.objects) - objects_after_source
    tgt_candidates = {o for o in objects_after_target if o.type == "ARMATURE"}
    if not tgt_candidates:
        raise RuntimeError(
            "No new armature in second FBX import; check target-rig-fbx path and content."
        )
    tgt_arm = _pick_armature(bpy, tgt_candidates)

    if tgt_arm.animation_data:
        tgt_arm.animation_data.action = None

    # --- ADD THIS TO NORMALIZE OBJECT TRANSFORMS ---
    bpy.ops.object.select_all(action='SELECT')
    # Apply Location, Rotation, and Scale to all objects (Armatures and Meshes)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action='DESELECT')

    _retarget_frames(bpy, src_arm, tgt_arm, pairs, verbose=args.blender_verbose)

    to_export = [tgt_arm]
    for o in bpy.data.objects:
        if o.type == "MESH" and o.parent == tgt_arm:
            to_export.append(o)

    _export_fbx(bpy, args.output_fbx, to_export)
    print(f"[ok] wrote {args.output_fbx}")


if __name__ == "__main__":
    import bpy  # noqa: E402

    main(bpy)