#!/usr/bin/env python3
"""Headless Blender backend for SMPL-to-FBX conversion.

Run via:
    blender -b --python smpl_to_fbx_blender_backend.py -- \
        --input-pkl-base <dir> --fbx-source-path <template.fbx> --output-base <out_dir>
"""

from __future__ import annotations

import argparse
import math
import os
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np

JOINT_NAMES = [
    "Pelvis",
    "L_Hip",
    "R_Hip",
    "Spine1",
    "L_Knee",
    "R_Knee",
    "Spine2",
    "L_Ankle",
    "R_Ankle",
    "Spine3",
    "L_Foot",
    "R_Foot",
    "Neck",
    "L_Collar",
    "R_Collar",
    "Head",
    "L_Shoulder",
    "R_Shoulder",
    "L_Elbow",
    "R_Elbow",
    "L_Wrist",
    "R_Wrist",
    "L_Hand",
    "R_Hand",
]


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _lookup_bone(pose_bones, target_name: str):
    bone = pose_bones.get(target_name)
    if bone is not None:
        return bone

    target_norm = _normalize_name(target_name)
    candidates = []
    for candidate in pose_bones:
        name_norm = _normalize_name(candidate.name)
        if name_norm == target_norm:
            candidates.append((0, len(candidate.name), candidate))
        elif name_norm.endswith(target_norm):
            candidates.append((1, len(candidate.name), candidate))
        elif target_norm in name_norm:
            candidates.append((2, len(candidate.name), candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _parse_args_from_blender() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-pkl-base", type=Path, required=True)
    parser.add_argument("--fbx-source-path", type=Path, required=True)
    parser.add_argument("--output-base", type=Path, required=True)
    return parser.parse_args(argv)


def _rotvec_to_euler_xyz(rotvec, mathutils):
    x, y, z = float(rotvec[0]), float(rotvec[1]), float(rotvec[2])
    angle = math.sqrt(x * x + y * y + z * z)
    if angle < 1e-8:
        return mathutils.Euler((0.0, 0.0, 0.0), "XYZ")
    axis = (x / angle, y / angle, z / angle)
    quat = mathutils.Quaternion(axis, angle)
    return quat.to_euler("XYZ")


def _load_smpl_payload(path: Path):
    with path.open("rb") as f:
        warnings.filterwarnings(
            "ignore",
            message=r".*numpy\.core\.numeric is deprecated.*",
            category=DeprecationWarning,
        )
        data = pickle.load(f)
    if "smpl_poses" not in data or "smpl_trans" not in data:
        raise KeyError(f"{path} must contain keys 'smpl_poses' and 'smpl_trans'")

    poses = np.asarray(data["smpl_poses"], dtype=np.float64)
    trans = np.asarray(data["smpl_trans"], dtype=np.float64)

    if poses.ndim != 2 or poses.shape[1] != 72:
        raise ValueError(f"{path}: expected smpl_poses shape (N,72), got {poses.shape}")
    if trans.ndim != 2 or trans.shape[1] != 3:
        raise ValueError(f"{path}: expected smpl_trans shape (N,3), got {trans.shape}")
    if poses.shape[0] != trans.shape[0]:
        raise ValueError(f"{path}: frame count mismatch between smpl_poses and smpl_trans")

    # Match SMPL-to-FBX loader behavior.
    scaling = float(np.asarray(data.get("smpl_scaling", [1.0])).reshape(-1)[0])
    trans = trans / (scaling * 100.0)
    return poses, trans


def _reset_scene(bpy):
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _find_armature_object(bpy):
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found after importing FBX template")

    def _score(arm_obj):
        if arm_obj.pose is None:
            return -1
        pose_bones = arm_obj.pose.bones
        checks = ("root", "Pelvis", "Spine1", "L_Hip", "R_Hip")
        match_count = sum(1 for name in checks if _lookup_bone(pose_bones, name) is not None)
        return (match_count, len(pose_bones))

    return max(armatures, key=_score)


def _find_root_bone(arm_obj):
    pose_bones = arm_obj.pose.bones
    for name in ("root", "Root", "Pelvis", "Hips"):
        bone = _lookup_bone(pose_bones, name)
        if bone is not None:
            return bone

    roots = [bone for bone in pose_bones if bone.parent is None]
    if roots:
        preferred = [b for b in roots if ("root" in b.name.lower() or "pelvis" in b.name.lower())]
        if preferred:
            return preferred[0]
        return roots[0]

    names_preview = ", ".join(b.name for b in pose_bones[:20])
    raise RuntimeError(
        "No root-like bone found. Tried root/Root/Pelvis/Hips and parentless fallback. "
        f"First bones: {names_preview}"
    )


def _apply_animation(arm_obj, poses, trans, bpy, mathutils):
    arm_obj.animation_data_create()
    action = bpy.data.actions.new(name="SMPL motion")
    arm_obj.animation_data.action = action

    pose_bones = arm_obj.pose.bones
    resolved_joint_bones = {name: _lookup_bone(pose_bones, name) for name in JOINT_NAMES}
    for bone in resolved_joint_bones.values():
        if bone is not None:
            bone.rotation_mode = "XYZ"

    root_bone = _lookup_bone(pose_bones, "root")
    if root_bone is None:
        root_bone = resolved_joint_bones.get("Pelvis")
    if root_bone is None:
        root_bone = _find_root_bone(arm_obj)
    root_bone.rotation_mode = "XYZ"

    n_frames = poses.shape[0]
    for frame_idx in range(n_frames):
        frame_no = frame_idx + 1

        for joint_idx, name in enumerate(JOINT_NAMES):
            bone = resolved_joint_bones[name]
            if bone is None:
                continue
            rotvec = poses[frame_idx, joint_idx * 3 : joint_idx * 3 + 3]
            bone.rotation_euler = _rotvec_to_euler_xyz(rotvec, mathutils)
            bone.keyframe_insert(data_path="rotation_euler", frame=frame_no)

        # Match FbxReadWriter axis mapping:
        # X <- trans[z], Y <- trans[x], Z <- trans[y]
        root_bone.location = (trans[frame_idx, 2], trans[frame_idx, 0], trans[frame_idx, 1])
        root_bone.keyframe_insert(data_path="location", frame=frame_no)

    scene = bpy.context.scene
    scene.render.fps = 60
    scene.frame_start = 1
    scene.frame_end = n_frames


def _convert_one(pkl_path: Path, fbx_source_path: Path, output_base: Path, bpy, mathutils):
    poses, trans = _load_smpl_payload(pkl_path)
    _reset_scene(bpy)
    bpy.ops.import_scene.fbx(filepath=str(fbx_source_path))

    arm_obj = _find_armature_object(bpy)
    _apply_animation(arm_obj, poses, trans, bpy, mathutils)

    output_base.mkdir(parents=True, exist_ok=True)
    out_fbx = output_base / f"{pkl_path.stem}.fbx"
    bpy.ops.export_scene.fbx(
        filepath=str(out_fbx),
        use_selection=False,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_simplify_factor=0.0,
    )
    print(f"[ok] wrote {out_fbx}")


def main():
    args = _parse_args_from_blender()
    if not args.input_pkl_base.exists():
        raise FileNotFoundError(f"Input PKL dir not found: {args.input_pkl_base}")
    if not args.fbx_source_path.exists():
        raise FileNotFoundError(f"FBX source template not found: {args.fbx_source_path}")

    import bpy
    import mathutils

    pkl_paths = sorted(args.input_pkl_base.glob("*.pkl"))
    if not pkl_paths:
        raise RuntimeError(f"No .pkl files found in {args.input_pkl_base}")

    for pkl_path in pkl_paths:
        _convert_one(pkl_path, args.fbx_source_path, args.output_base, bpy, mathutils)

    print(f"[done] exported {len(pkl_paths)} FBX file(s) to {args.output_base}")


if __name__ == "__main__":
    main()
