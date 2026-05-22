# BEDLAM 2 retargeting + WHAM → Manny-compatible FBX

This document ties together **PerceivingSystems/bedlam2_retargeting** (UE 5.3/5.4) and the **WHAM** Unreal automation under [`tools/unreal/`](../tools/unreal/).

## Vendored reference clone

A reference clone of the upstream project lives next to this repo (from the WHAM root: `../../bedlam2_retargeting/`, branch `5.4`).

Use it for:

- `retargeting/retargeting.uproject` as an alternative Unreal hub
- `retargeting/Content/Python/import_batch.py`, `retarget_batch.py`, and `export_fbx.py` (selection-based FBX export)
- `README.md` for plugin requirements (Python, Python Foundation Packages, Remote Execution, numpy)

WHAM ships **host-side** launchers that mirror the same batch pattern but point at **your** `.uproject` via [`tools/unreal/paths.json`](../tools/unreal/paths.example.json).

## Required Unreal plugins

- **Python**
- **Python Foundation Packages** (numpy, as used by bedlam2)
- **Python Remote Execution** (bedlam2 README)
- **IK Rig** and **IK Retargeter** (WHAM → Manny)

## Phase 1–2: Project and WHAM FBX import

1. Open your game `.uproject` (or open `bedlam2_retargeting/retargeting/retargeting.uproject` if you work inside the reference project).
2. Import WHAM `*_UE.fbx` files with **animations** and **without** forcing an Epic skeleton (first import creates the WHAM / SMPL source skeleton).

From the host (paths in `paths.json`):

```bash
cd WHAM/tools/unreal
cp paths.example.json paths.json   # edit unreal_editor_cmd + uproject_path

python import_batch.py \
  --input-dir /abs/path/to/unreal_fbx \
  --destination-root /Game/WHAM/SourceAnimations \
  --import-animations \
  --num-batches 4 --processes 2
```

Do **not** pass `--source-skeleton-path` on the first import unless you are re-importing compatible clips.

## Phase 3: IK Rigs and IK Retargeter (one-time, in Editor)

You must author and save in the **Content Browser**:

- **Source IK Rig** for the skeleton imported from WHAM
- **Target IK Rig** for Epic **Manny** (e.g. migrate `SKM_Manny` + `IKR_Manny` from the Third Person template)
- **IK Retargeter** asset mapping source chains → target chains

See [`wham_manny_ik_retarget_bones.example.json`](../tools/unreal/wham_manny_ik_retarget_bones.example.json) for **SMPL bone names** (from the Unity template used in WHAM) to help map chains. Final mapping is still done in the **IK Retargeter** UI.

## Phase 4: Batch retarget (scripted)

Requires `default_wham_to_manny_ik_retargeter` and `default_target_manny_mesh` in `paths.json` (or CLI overrides).

```bash
python retarget_batch.py \
  --source-root /Game/WHAM/SourceAnimations \
  --output-root /Game/WHAM/Retargeted/Manny \
  --num-batches 8 --processes 4
```

## Phase 5: Headless Manny FBX export (scripted)

WHAM’s [`ue_export_fbx_worker.py`](../tools/unreal/ue_export_fbx_worker.py) uses the same Unreal classes as bedlam2’s `export_fbx.py` (`AnimSequenceExporterFBX` / `FbxExportOption`), but scans a **content root** for `AnimSequence` assets instead of using the content browser selection.

```bash
python export_batch.py \
  --source-root /Game/WHAM/Retargeted/Manny \
  --host-export-dir /abs/path/out/manny_fbx \
  --num-batches 4 --processes 2
```

Add `--export-mesh` if you need the preview mesh in each FBX.

## End-to-end host orchestration

```bash
python run_wham_to_manny_pipeline.py \
  --input-dir /abs/path/to/unreal_fbx \
  --host-export-dir /abs/path/out/manny_fbx
```

Omit `--host-export-dir` to run **import + retarget only** (no FBX on disk).

## `Makefile` shortcuts

From `WHAM/tools/unreal/`:

- `make import` — requires `IN` (WHAM `unreal_fbx` directory)
- `make retarget`
- `make export` — requires `OUT` (host directory for `.fbx`)
- `make all` — `import` + `retarget` + `export`

Set `PATHS=paths.json` if not using the default. Example:

`make all IN=/abs/.../unreal_fbx OUT=/abs/.../manny_fbx`

**Linux-only (no Unreal):** see [LINUX_MANNY_RETARGET.md](LINUX_MANNY_RETARGET.md) for a Blender-headless WHAM → Mannequin prototype.

## License note

`bedlam2_retargeting` is subject to the [Max Planck BEDLAM 2.0 license](https://bedlam2.is.tuebingen.mpg.de/license.html). WHAM’s workers are separate glue code; keep license files from the clone intact.
