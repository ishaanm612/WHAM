#!/usr/bin/env python3
"""Headless Blender validation for Unreal-ready FBX assets.

Run via:
    blender -b --python validate_unreal_fbx_blender_backend.py -- \
        --input-fbx-dir <dir>
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
    parser.add_argument(
        "--sample-frames",
        type=int,
        default=3,
        help="Number of frames to sample for transform checks (default: 3)",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def _reset_scene(bpy):
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _find_primary_armature(bpy):
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found in imported FBX")
    return max(armatures, key=lambda obj: len(obj.pose.bones) if obj.pose else 0)


def _assert_finite_matrix(name: str, matrix):
    for row in matrix:
        for value in row:
            if not math.isfinite(float(value)):
                raise ValueError(f"Non-finite transform in '{name}'")


def _frame_samples(start: int, end: int, count: int) -> list[int]:
    if end <= start or count <= 1:
        return [start, end]
    if count == 2:
        return [start, end]
    span = end - start
    samples = {start, end}
    for i in range(1, count - 1):
        frac = i / float(count - 1)
        samples.add(int(round(start + frac * span)))
    return sorted(samples)


def _validate_one_fbx(fbx_path: Path, args, bpy):
    _reset_scene(bpy)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path), use_anim=True)

    arm_obj = _find_primary_armature(bpy)
    action = None
    if arm_obj.animation_data is not None:
        action = arm_obj.animation_data.action
    if action is None:
        raise RuntimeError("No animation action found on primary armature")

    frame_start, frame_end = action.frame_range
    frame_start_i = int(math.floor(frame_start))
    frame_end_i = int(math.ceil(frame_end))
    if frame_end_i <= frame_start_i:
        raise RuntimeError(
            f"Invalid animation range: start={frame_start_i}, end={frame_end_i}"
        )

    scene = bpy.context.scene
    samples = _frame_samples(frame_start_i, frame_end_i, max(args.sample_frames, 2))
    for frame_no in samples:
        scene.frame_set(frame_no)
        _assert_finite_matrix(arm_obj.name, arm_obj.matrix_world)
        if arm_obj.pose is not None:
            for bone in arm_obj.pose.bones:
                _assert_finite_matrix(f"{arm_obj.name}:{bone.name}", bone.matrix)

    duration = frame_end_i - frame_start_i + 1
    if args.verbose:
        print(
            f"[ok] {fbx_path.name}: frames={frame_start_i}-{frame_end_i} "
            f"duration={duration} sampled={samples}"
        )
    else:
        print(f"[ok] {fbx_path.name}: duration={duration} frames")


def main():
    args = _parse_args_from_blender()
    if not args.input_fbx_dir.exists():
        raise FileNotFoundError(f"Input FBX directory not found: {args.input_fbx_dir}")

    bpy = __import__("bpy")

    fbx_paths = sorted(args.input_fbx_dir.glob("*.fbx"))
    if not fbx_paths:
        raise RuntimeError(f"No .fbx files found in {args.input_fbx_dir}")

    failures: list[str] = []
    for fbx_path in fbx_paths:
        try:
            _validate_one_fbx(fbx_path, args, bpy)
        except Exception as exc:  # pragma: no cover - Blender runtime guard
            failures.append(f"{fbx_path.name}: {exc}")
            print(f"[error] {fbx_path.name}: {exc}")

    if failures:
        raise RuntimeError(
            "FBX validation failed:\n" + "\n".join(f"- {item}" for item in failures)
        )

    print(f"[done] validated {len(fbx_paths)} FBX file(s) in {args.input_fbx_dir}")


if __name__ == "__main__":
    main()
