# Mannequin / Manny target rig (user-supplied)

This directory is **intentionally empty** in the public repo.

## Why

Epic’s **SKM_Manny** / **Mannequin** skeletal mesh and skeleton are **Epic Games content** subject to the [Unreal Engine license terms](https://www.unrealengine.com/en-US/eula). You must **not** commit Epic-owned FBX or `.uasset` files here unless your project’s license allows redistribution.

## What to place here (local use only)

1. Export or copy a **Mannequin (Manny) skeletal mesh** as **FBX** from an Unreal project you are entitled to use (e.g. Third Person template, Fab, or your own project).
2. Save a single file such as:
   - `SKM_Manny.fbx` (suggested name), or  
   - any `*.fbx` you reference from [`WHAM/docs/LINUX_MANNY_RETARGET.md`](../docs/LINUX_MANNY_RETARGET.md) and from [`../tools/wham_manny_retarget_blender_backend.py`](../tools/wham_manny_retarget_blender_backend.py).

## How to get the file (typical)

- On a machine with Unreal: create a project with **Third Person** content, find **SKM_Manny** in the Content Browser, **right-click → Asset Actions → Export** to FBX (options depend on your UE version), or use a project-specific export plugin.
- Adjust [`../tools/smpl_to_manny_retarget_map.example.json`](../tools/smpl_to_manny_retarget_map.example.json) **target** bone names to match the **actual** bone names in *your* exported FBX (open in Blender, Armature, Edit Mode → list bone names if needed).

## .gitignore

`WHAM/.gitignore` or repo `.gitignore` can list `*.fbx` under this folder to avoid accidental commits; verify before pushing.
