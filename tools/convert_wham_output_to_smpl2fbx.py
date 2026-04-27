#!/usr/bin/env python3
"""Convert WHAM outputs to SMPL-to-FBX input format.

This utility converts WHAM's ``wham_output.pkl`` (saved by ``demo.py --save_pkl``)
into one or more ``.pkl`` files expected by SMPL-to-FBX pipelines:

    - ``smpl_poses``: (N, 72) axis-angle rotations
    - ``smpl_trans``: (N, 3) root translations
    - ``smpl_scaling``: scalar array used by that converter

It can optionally invoke FBX conversion in one command (default backend: bpy).
"""

from __future__ import annotations

import argparse
import importlib
import os
import pickle
import subprocess
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

DEFAULT_SMPL_TO_FBX_ROOT = Path("/home/ishaan/projects/Data4D/SMPL-to-FBX")
DEFAULT_FBX_SOURCE_PATH = Path(
    "/home/ishaan/projects/Data4D/WHAM/tools/SMPL_m_unityDoubleBlends_lbs_10_scale5_207_v1.0.0.fbx"
)
DEFAULT_BLENDER_EXECUTABLE = "blender"


def _sanitize_token(value: object) -> str:
    return str(value).replace(os.sep, "_").replace(" ", "_")


def _iter_selected_subjects(results: dict, selected: set[str] | None) -> Iterable[tuple[object, dict]]:
    for sid, payload in results.items():
        if selected is not None and _sanitize_token(sid) not in selected and str(sid) not in selected:
            continue
        yield sid, payload


def _convert_subject(
    sid: object,
    payload: dict,
    pose_key: str,
    trans_key: str,
    smpl_scaling: float,
    output_pkl_dir: Path,
    filename_prefix: str,
) -> Path:
    if pose_key not in payload:
        raise KeyError(f"Subject {sid!r} is missing '{pose_key}'")
    if trans_key not in payload:
        raise KeyError(f"Subject {sid!r} is missing '{trans_key}'")

    poses = np.asarray(payload[pose_key], dtype=np.float32)
    trans = np.asarray(payload[trans_key], dtype=np.float32)

    if poses.ndim != 2 or poses.shape[1] != 72:
        raise ValueError(
            f"Subject {sid!r}: expected {pose_key} shape (N, 72), got {poses.shape}"
        )
    if trans.ndim != 2 or trans.shape[1] != 3:
        raise ValueError(
            f"Subject {sid!r}: expected {trans_key} shape (N, 3), got {trans.shape}"
        )
    if poses.shape[0] != trans.shape[0]:
        raise ValueError(
            f"Subject {sid!r}: frame mismatch between pose ({poses.shape[0]}) and "
            f"trans ({trans.shape[0]})"
        )

    sid_token = _sanitize_token(sid)
    out_name = f"{filename_prefix}_sid{sid_token}.pkl"
    out_path = output_pkl_dir / out_name

    data = {
        "smpl_poses": poses,
        "smpl_trans": trans,
        # SMPL-to-FBX loader divides translations by (smpl_scaling * 100)
        "smpl_scaling": np.array([smpl_scaling], dtype=np.float32),
    }
    with out_path.open("wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    return out_path


def _ensure_blender_runnable(blender_exe: str) -> None:
    blender_preflight = subprocess.run(
        [blender_exe, "--version"], capture_output=True, text=True
    )
    if blender_preflight.returncode != 0:
        raise RuntimeError(
            "Blender executable is not runnable.\n"
            f"Executable: {blender_exe}\n"
            "Install Blender and/or pass --blender-exe with a valid binary path.\n"
            f"stderr:\n{(blender_preflight.stderr or '').strip()}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wham-output",
        type=Path,
        required=True,
        help="Path to WHAM wham_output.pkl (from demo.py --save_pkl)",
    )
    parser.add_argument(
        "--output-pkl-dir",
        type=Path,
        required=True,
        help="Directory to write SMPL-to-FBX-compatible .pkl files",
    )
    parser.add_argument(
        "--pose-space",
        choices=["world", "camera"],
        default="world",
        help="Use WHAM pose_world or pose (default: world)",
    )
    parser.add_argument(
        "--trans-space",
        choices=["world", "camera"],
        default="world",
        help="Use WHAM trans_world or trans (default: world)",
    )
    parser.add_argument(
        "--smpl-scaling",
        type=float,
        default=0.01,
        help="smpl_scaling value written to output pkls (default: 0.01)",
    )
    parser.add_argument(
        "--subjects",
        nargs="*",
        default=None,
        help="Optional subject IDs to export (space-separated)",
    )
    parser.add_argument(
        "--filename-prefix",
        default="wham",
        help="Prefix for exported pkl files (default: wham)",
    )

    parser.add_argument(
        "--run-convert",
        action="store_true",
        help="Also convert generated PKLs to FBX after writing them",
    )
    parser.add_argument(
        "--convert-backend",
        choices=["bpy", "fbxsdk"],
        default="bpy",
        help="FBX conversion backend (default: bpy)",
    )
    parser.add_argument(
        "--smpl-to-fbx-root",
        type=Path,
        default=DEFAULT_SMPL_TO_FBX_ROOT,
        help="Path to SMPL-to-FBX repo root",
    )
    parser.add_argument(
        "--blender-exe",
        default=DEFAULT_BLENDER_EXECUTABLE,
        help="Blender executable used for bpy backend (default: blender)",
    )
    parser.add_argument(
        "--fbx-source-path",
        type=Path,
        default=DEFAULT_FBX_SOURCE_PATH,
        help="Path to SMPL Unity FBX template",
    )
    parser.add_argument(
        "--fbx-output-dir",
        type=Path,
        default=None,
        help="Directory for exported FBX files (required with --run-convert)",
    )
    parser.add_argument(
        "--run-unreal-convert",
        action="store_true",
        help="Convert Unity-oriented FBX outputs into Unreal-ready FBX files",
    )
    parser.add_argument(
        "--unity-fbx-dir",
        type=Path,
        default=None,
        help="Directory with Unity-oriented FBX files (default: --fbx-output-dir)",
    )
    parser.add_argument(
        "--unreal-fbx-dir",
        type=Path,
        default=None,
        help="Directory for Unreal-ready FBX files (required with --run-unreal-convert)",
    )
    parser.add_argument(
        "--unreal-name-suffix",
        default="_UE",
        help="Filename suffix for Unreal-ready FBX files (default: _UE)",
    )
    parser.add_argument(
        "--unreal-convert-dry-run",
        action="store_true",
        help="Only list Unity->Unreal conversion actions without writing files",
    )
    parser.add_argument(
        "--unreal-convert-verbose",
        action="store_true",
        help="Enable verbose logs for Unity->Unreal Blender backend",
    )
    args = parser.parse_args()

    if not args.wham_output.exists():
        raise FileNotFoundError(f"WHAM output file not found: {args.wham_output}")

    pose_key = "pose_world" if args.pose_space == "world" else "pose"
    trans_key = "trans_world" if args.trans_space == "world" else "trans"

    joblib = importlib.import_module("joblib")
    results = joblib.load(args.wham_output)
    if not isinstance(results, dict):
        raise TypeError(f"Expected dict in {args.wham_output}, got {type(results)}")

    args.output_pkl_dir.mkdir(parents=True, exist_ok=True)
    selected = set(args.subjects) if args.subjects else None

    written: list[Path] = []
    for sid, payload in _iter_selected_subjects(results, selected):
        out_path = _convert_subject(
            sid=sid,
            payload=payload,
            pose_key=pose_key,
            trans_key=trans_key,
            smpl_scaling=args.smpl_scaling,
            output_pkl_dir=args.output_pkl_dir,
            filename_prefix=args.filename_prefix,
        )
        written.append(out_path)
        print(f"[ok] wrote {out_path}")

    if not written:
        raise RuntimeError("No subjects exported. Check --subjects values and input file.")

    print(f"[done] exported {len(written)} pkl file(s) to {args.output_pkl_dir}")

    if args.run_convert:
        if args.fbx_output_dir is None:
            raise ValueError(
                "--run-convert requires --fbx-output-dir."
            )
        if not args.fbx_source_path.exists():
            raise FileNotFoundError(f"FBX source template not found: {args.fbx_source_path}")

        args.fbx_output_dir.mkdir(parents=True, exist_ok=True)

        if args.convert_backend == "bpy":
            _ensure_blender_runnable(args.blender_exe)
            bpy_backend_py = Path(__file__).with_name("smpl_to_fbx_blender_backend.py")
            if not bpy_backend_py.exists():
                raise FileNotFoundError(f"Blender backend script not found at {bpy_backend_py}")

            cmd = [
                args.blender_exe,
                "-b",
                "--python-exit-code",
                "1",
                "--python",
                str(bpy_backend_py),
                "--",
                "--input-pkl-base",
                str(args.output_pkl_dir),
                "--fbx-source-path",
                str(args.fbx_source_path),
                "--output-base",
                str(args.fbx_output_dir),
            ]
        else:
            convert_py = args.smpl_to_fbx_root / "Convert.py"
            if not convert_py.exists():
                raise FileNotFoundError(f"Convert.py not found at {convert_py}")

            # Preflight check: SMPL-to-FBX Convert.py requires Autodesk FBX Python SDK
            # modules (FbxCommon, fbx) in the current Python environment.
            preflight_cmd = [sys.executable, "-c", "import FbxCommon, fbx"]
            preflight = subprocess.run(preflight_cmd, capture_output=True, text=True)
            if preflight.returncode != 0:
                raise RuntimeError(
                    "fbxsdk backend selected, but Autodesk FBX Python SDK modules "
                    "'FbxCommon' and 'fbx' are not importable in this environment.\n"
                    "WHAM->SMPL PKLs were exported successfully. To enable this backend, "
                    "install Autodesk FBX Python bindings for this Python version.\n"
                    f"Python: {sys.executable}\n"
                    f"Import error output:\n{(preflight.stderr or preflight.stdout).strip()}"
                )

            cmd = [
                sys.executable,
                str(convert_py),
                "--input_pkl_base",
                str(args.output_pkl_dir),
                "--fbx_source_path",
                str(args.fbx_source_path),
                "--output_base",
                str(args.fbx_output_dir),
            ]

        print("[run]", " ".join(cmd))
        subprocess.run(cmd, check=True)
        print(f"[done] FBX files exported to {args.fbx_output_dir} (backend={args.convert_backend})")

    if args.run_unreal_convert:
        if args.unreal_fbx_dir is None:
            raise ValueError("--run-unreal-convert requires --unreal-fbx-dir.")

        unity_fbx_dir = args.unity_fbx_dir or args.fbx_output_dir
        if unity_fbx_dir is None:
            raise ValueError(
                "--run-unreal-convert requires --unity-fbx-dir or --fbx-output-dir."
            )
        if not unity_fbx_dir.exists():
            raise FileNotFoundError(f"Unity FBX directory not found: {unity_fbx_dir}")

        _ensure_blender_runnable(args.blender_exe)
        unreal_backend_py = Path(__file__).with_name("fbx_unity_to_unreal_blender_backend.py")
        if not unreal_backend_py.exists():
            raise FileNotFoundError(f"Unreal Blender backend script not found at {unreal_backend_py}")

        args.unreal_fbx_dir.mkdir(parents=True, exist_ok=True)

        unreal_cmd = [
            args.blender_exe,
            "-b",
            "--python-exit-code",
            "1",
            "--python",
            str(unreal_backend_py),
            "--",
            "--input-fbx-dir",
            str(unity_fbx_dir),
            "--output-fbx-dir",
            str(args.unreal_fbx_dir),
            "--filename-suffix",
            args.unreal_name_suffix,
        ]
        if args.unreal_convert_dry_run:
            unreal_cmd.append("--dry-run")
        if args.unreal_convert_verbose:
            unreal_cmd.append("--verbose")

        print("[run]", " ".join(unreal_cmd))
        subprocess.run(unreal_cmd, check=True)
        mode = "dry-run" if args.unreal_convert_dry_run else "export"
        print(
            f"[done] Unreal FBX {mode} completed from {unity_fbx_dir} "
            f"to {args.unreal_fbx_dir}"
        )


if __name__ == "__main__":
    main()
