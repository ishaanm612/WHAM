# Linux-only WHAM → Mannequin retargeting (no Unreal)

This document describes a **parallel path** to the Unreal IK Retargeter flow ([`tools/unreal/`](../tools/unreal/)): retarget on **Linux** using **headless Blender** and optional alternate pipelines. Unreal and bedlam2 are **not** required for the prototype below.

## When to use this vs Unreal

| Situation | Prefer |
|-----------|--------|
| No UE on Linux; Windows box optional | **Blender retarget** ([prototype](#headless-prototype)) |
| Need Epic IK Retargeter fidelity / batch `AnimSequence` | **Unreal** path + [`ue_retarget_worker.py`](../tools/unreal/ue_retarget_worker.py) |
| Studio already standardizes on Blender for mocap cleanup | **Blender** + manual map tuning |

## Target rig (user-supplied Mannequin FBX)

See [`third_party/mannequin/README.md`](../third_party/mannequin/README.md): place an Epic-exported **SKM_Manny** (or compatible) FBX **locally**. Do not commit Epic-owned assets to public repos without license clearance.

## Bone map (SMPL → Mannequin)

- Reference joint names on the **source** side: [`smpl_to_fbx_blender_backend.py`](../tools/smpl_to_fbx_blender_backend.py) (`JOINT_NAMES`).
- **Example** target mapping (edit names to match *your* FBX): [`smpl_to_manny_retarget_map.example.json`](../tools/smpl_to_manny_retarget_map.example.json).

Open the Mannequin FBX in Blender → select Armature → **Edit Mode** → verify actual bone names (`pelvis` vs `Pelvis`, `thigh_l` vs `thigh_01_l`, etc.) and update the JSON.

## Track A — Blender add-on survey (manual alternative)

The following are **commonly used** for animation retargeting in Blender. None are required for the built-in prototype script; they are options if you want IK solvers, UI workflows, or vendor support.

| Tool | Notes | Headless / batch | License (verify upstream) |
|------|--------|------------------|---------------------------|
| **Blender-Animation-Retargeting** (community, e.g. Mwni/*forks*) | Bone mapping + bake; widely used | Must verify `-b` + enable add-on in startup | GPL-3.0 typical for GPL forks |
| **Auto-Rig Pro** | Strong rigging + retarget | Paid; confirm batch | Commercial |
| **Rokoko Blender plugin** | Studio ↔ Blender | Often UI-driven | Rokoko terms |

**Recommendation:** Try the **headless prototype** first; add an add-on only if you need **IK feet**, **interactive** editing, or **faster iteration** in the GUI.

## Headless prototype (Track B1–B2)

Script: [`wham_manny_retarget_blender_backend.py`](../tools/wham_manny_retarget_blender_backend.py)

For each frame and each mapped bone pair, it sets the **target** pose bone so its **world** matrix matches the **source** bone’s world matrix:

`M_tgt_local = tgt.matrix_world^-1 @ (src.matrix_world @ src_posebone.matrix)`.

**Limits (v0):** Does not fix **T-pose vs A-pose** rest mismatch; may look wrong until you adjust **rest rolls** on the target rig or add offsets (same class of issue as Unreal chain tuning). **Fingers** and **twist** bones are only animated if listed in the mapping.

### Example command

```bash
cd /path/to/WHAM/tools
blender -b --python wham_manny_retarget_blender_backend.py -- \
  --source-fbx /path/to/wham_sid0_UE.fbx \
  --target-rig-fbx /path/to/third_party/mannequin/SKM_Manny.fbx \
  --mapping-json smpl_to_manny_retarget_map.example.json \
  --output-fbx /tmp/manny_out.fbx \
  --blender-verbose
```

### Validation

1. Re-import `manny_out.fbx` in Blender: play animation on **Mannequin** armature.
2. Optional: import into Unreal on **any** OS to confirm skeleton compatibility.

## Track B3 — Optional improvements (not automated here)

- Add **Copy Rotation** constraints + bake instead of raw matrix copy.
- Add **two-bone IK** on legs in Blender for foot lock.
- Pre-align target rest pose to SMPL **bind pose** in Edit Mode.

## Track C — Alternatives if Blender FK quality is insufficient

Use this table to decide whether to invest beyond **B2**. **Gate:** measure B2 on real WHAM clips before starting heavy ML work.

| ID | Family | Idea | Typical deps | Effort (order of magnitude) | Fit: single SMPL→Manny on Linux |
|----|--------|------|--------------|----------------------------|----------------------------------|
| C1 | Optimization / IK | Minimize `‖FK_tgt(θ) − y‖` with joint limits + floor penalty; `y` from SMPL joints | NumPy / PyTorch, small FK tree from rig JSON | Medium | **High** if feet must stick |
| C2 | Learned retarget | Train or fine-tune sequence model SMPL→Mannequin | Data (AMASS, etc.), GPU | High | **Low** unless you have data + team |
| C3 | Via BVH / mocap | WHAM→BVH then BVH→rig in Blender/tooling | Converter + existing BVH retarget | Medium | **Medium** (two-stage error) |
| C4 | Sim / control | Diff sim, trajectory opt | Research code | High | **Low** for game FBX export |

**Practical next step if B2 fails:** spike **C1** on **legs only** (2-bone IK or per-frame foot position solve) before C2.

## Related files

- Unreal batch path: [`docs/BEDLAM2_MANNY_PIPELINE.md`](BEDLAM2_MANNY_PIPELINE.md) (optional; includes Unreal).
- Unreal bone name hints (Editor): [`tools/unreal/wham_manny_ik_retarget_bones.example.json`](../tools/unreal/wham_manny_ik_retarget_bones.example.json).
