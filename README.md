# WHAM: Reconstructing World-grounded Humans with Accurate 3D Motion

<a href="https://pytorch.org/get-started/locally/"><img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-ee4c2c?logo=pytorch&logoColor=white"></a> [![report](https://img.shields.io/badge/arxiv-report-red)](https://arxiv.org/abs/2312.07531) <a href="https://wham.is.tue.mpg.de/"><img alt="Project" src="https://img.shields.io/badge/-Project%20Page-lightgrey?logo=Google%20Chrome&color=informational&logoColor=white"></a> [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1ysUtGSwidTQIdBQRhq0hj63KbseFujkn?usp=sharing)
 [![PWC](https://img.shields.io/endpoint.svg?url=https://paperswithcode.com/badge/wham-reconstructing-world-grounded-humans/3d-human-pose-estimation-on-3dpw)](https://paperswithcode.com/sota/3d-human-pose-estimation-on-3dpw?p=wham-reconstructing-world-grounded-humans) [![PWC](https://img.shields.io/endpoint.svg?url=https://paperswithcode.com/badge/wham-reconstructing-world-grounded-humans/3d-human-pose-estimation-on-emdb)](https://paperswithcode.com/sota/3d-human-pose-estimation-on-emdb?p=wham-reconstructing-world-grounded-humans)


https://github.com/yohanshin/WHAM/assets/46889727/da4602b4-0597-4e64-8da4-ab06931b23ee


## Introduction
This repository is the official [Pytorch](https://pytorch.org/) implementation of [WHAM: Reconstructing World-grounded Humans with Accurate 3D Motion](https://arxiv.org/abs/2312.07531). For more information, please visit our [project page](https://wham.is.tue.mpg.de/).


## Installation
Please see [Installation](docs/INSTALL.md) for details.


## Quick Demo

### [<img src="https://i.imgur.com/QCojoJk.png" width="30"> Google Colab for WHAM demo is now available](https://colab.research.google.com/drive/1ysUtGSwidTQIdBQRhq0hj63KbseFujkn?usp=sharing)

### Registration

To download SMPL body models (Neutral, Female, and Male), you need to register for [SMPL](https://smpl.is.tue.mpg.de/) and [SMPLify](https://smplify.is.tue.mpg.de/). The username and password for both homepages will be used while fetching the demo data.

Next, run the following script to fetch demo data. This script will download all the required dependencies including trained models and demo videos.

```bash
bash fetch_demo_data.sh
```

You can try with one examplar video:
```
python demo.py --video examples/IMG_9732.mov --visualize
```

We assume camera focal length following [CLIFF](https://github.com/haofanwang/CLIFF). You can specify known camera intrinsics [fx fy cx cy] for SLAM as the demo example below:
```
python demo.py --video examples/drone_video.mp4 --calib examples/drone_calib.txt --visualize
```

You can skip SLAM if you only want to get camera-coordinate motion. You can run as:
```
python demo.py --video examples/IMG_9732.mov --visualize --estimate_local_only
```

You can further refine the results of WHAM using Temporal SMPLify as a post processing. This will allow better 2D alignment as well as 3D accuracy. All you need to do is add `--run_smplify` flag when running demo.

### Export SMPL for FBX pipelines

Save WHAM outputs as pkl:
```bash
python demo.py --video examples/IMG_9732.mov --save_pkl
```

Convert `wham_output.pkl` to the `SMPL-to-FBX` pkl format:
```bash
python tools/convert_wham_output_to_smpl2fbx.py \
  --wham-output output/demo/IMG_9732/wham_output.pkl \
  --output-pkl-dir output/demo/IMG_9732/smpl_to_fbx_pkls
```

Optionally convert PKLs to FBX from the same command (default backend: `bpy` via Blender):
```bash
python tools/convert_wham_output_to_smpl2fbx.py \
  --wham-output output/demo/IMG_9732/wham_output.pkl \
  --output-pkl-dir output/demo/IMG_9732/smpl_to_fbx_pkls \
  --run-convert \
  --fbx-output-dir output/demo/IMG_9732/fbx
```

By default, the script uses Blender in headless mode (`blender -b`) and relies on:
- `--smpl-to-fbx-root=/home/ishaan/projects/Data4D/SMPL-to-FBX`
- `--fbx-source-path=/home/ishaan/projects/Data4D/WHAM/tools/SMPL_m_unityDoubleBlends_lbs_10_scale5_207_v1.0.0.fbx`

If Blender is not on PATH, pass `--blender-exe /path/to/blender`.
You can switch to the Autodesk FBX SDK backend with `--convert-backend fbxsdk`.

### Scriptable Unity-FBX -> Unreal-FBX (UE5 Manny/Quinn)

Generate both Unity-oriented FBX and Unreal-ready FBX in one command:
```bash
python tools/convert_wham_output_to_smpl2fbx.py \
  --wham-output output/demo/IMG_9732/wham_output.pkl \
  --output-pkl-dir output/demo/IMG_9732/smpl_to_fbx_pkls \
  --run-convert \
  --fbx-output-dir output/demo/IMG_9732/unity_fbx \
  --run-unreal-convert \
  --unreal-fbx-dir output/demo/IMG_9732/unreal_fbx
```

Expected output layout:
```text
output/demo/IMG_9732/
  smpl_to_fbx_pkls/    # Intermediate PKLs
  unity_fbx/           # Unity-oriented FBX output from SMPL template
  unreal_fbx/          # Unreal-ready FBX output (suffix: _UE.fbx)
```

Useful Unreal conversion flags:
- `--unity-fbx-dir <dir>`: Input FBX directory for Unreal conversion (defaults to `--fbx-output-dir`)
- `--unreal-name-suffix _UE`: Suffix for Unreal FBX outputs
- `--unreal-convert-dry-run`: Print planned conversions without writing files
- `--unreal-convert-verbose`: Verbose logs from Blender conversion backend

Validate Unreal-ready FBX files before opening Unreal:
```bash
blender -b --python tools/validate_unreal_fbx_blender_backend.py -- \
  --input-fbx-dir output/demo/IMG_9732/unreal_fbx \
  --verbose
```

The validation checks:
- FBX files are present and importable in headless Blender
- At least one animated armature exists per file
- Animation frame range is non-zero
- Sampled object/bone transforms are finite (no NaN/Inf)

#### Unreal import settings checklist

- Import as `Skeletal Mesh` (for the first mesh) and `Import Animations`.
- Keep `Convert Scene` enabled so Unreal applies FBX axis conversion.
- Use scale `1.0` on import unless your project already uses a custom character scale.
- Disable material/texture import if this pipeline is animation-only.
- Reuse the same Skeleton asset across clips after first import.

#### UE5 Manny/Quinn retarget quickstart

1. Import the Unreal-ready FBX once to create a source Skeleton.
2. Create an `IK Rig` for the source Skeleton and map major humanoid chains.
3. Open/create an `IK Rig` + `IK Retargeter` for Manny/Quinn.
4. Set source = WHAM skeleton IK Rig, target = Manny/Quinn IK Rig.
5. Tune retarget root/pelvis settings, preview, then export retargeted animations.

### BEDLAM-style Unreal batch automation (Manny/Quinn)

The repository now includes command-line Unreal automation scripts in `tools/unreal/`
to batch import FBX and batch retarget to the default third-person character skeleton.

#### 1) Configure Unreal paths

Copy `tools/unreal/paths.example.json` to `tools/unreal/paths.json` and edit:
- `unreal_editor_cmd`: Unreal editor commandlet binary
- `uproject_path`: your target `.uproject`
- `default_target_manny_mesh`: target mesh asset path (default UE5 mannequin)
- `default_wham_to_manny_ik_retargeter`: IK Retargeter asset path for WHAM -> Manny
- optional source/target IK rig defaults

#### 2) Import Unreal-ready FBX files in batches

```bash
python tools/unreal/import_batch.py \
  --paths-json tools/unreal/paths.json \
  --input-dir output/demo/IMG_9732/unreal_fbx \
  --destination-root /Game/WHAM/SourceAnimations \
  --num-batches 8 \
  --processes 4
```

#### 3) Retarget imported animations to Manny/Quinn in batches

```bash
python tools/unreal/retarget_batch.py \
  --paths-json tools/unreal/paths.json \
  --source-root /Game/WHAM/SourceAnimations \
  --output-root /Game/WHAM/Retargeted/Manny \
  --num-batches 8 \
  --processes 4
```

#### 4) One-command pipeline (import + retarget)

```bash
python tools/unreal/run_wham_to_manny_pipeline.py \
  --paths-json tools/unreal/paths.json \
  --input-dir output/demo/IMG_9732/unreal_fbx \
  --source-root /Game/WHAM/SourceAnimations \
  --output-root /Game/WHAM/Retargeted/Manny \
  --num-batches 8 \
  --processes 4
```

Notes:
- The Unreal workers use environment variables for robust argument passing.
- Retargeting expects a preconfigured IK Retargeter (chain mapping + preview setup).
- Enable UE Python and IK Rig/IK Retargeter plugins in your project.

## Docker

Please refer to [Docker](docs/DOCKER.md) for details.

## Python API

Please refer to [API](docs/API.md) for details.

## Dataset
Please see [Dataset](docs/DATASET.md) for details.

## Evaluation
```bash
# Evaluate on 3DPW dataset
python -m lib.eval.evaluate_3dpw --cfg configs/yamls/demo.yaml TRAIN.CHECKPOINT checkpoints/wham_vit_w_3dpw.pth.tar

# Evaluate on RICH dataset
python -m lib.eval.evaluate_rich --cfg configs/yamls/demo.yaml TRAIN.CHECKPOINT checkpoints/wham_vit_w_3dpw.pth.tar

# Evaluate on EMDB dataset (also computes W-MPJPE and WA-MPJPE)
python -m lib.eval.evaluate_emdb --cfg configs/yamls/demo.yaml --eval-split 1 TRAIN.CHECKPOINT checkpoints/wham_vit_w_3dpw.pth.tar   # EMDB 1

python -m lib.eval.evaluate_emdb --cfg configs/yamls/demo.yaml --eval-split 2 TRAIN.CHECKPOINT checkpoints/wham_vit_w_3dpw.pth.tar   # EMDB 2
```

## Training
WHAM training involves into two different stages; (1) 2D to SMPL lifting through AMASS dataset and (2) finetuning with feature integration using the video datasets. Please see [Dataset](docs/DATASET.md) for preprocessing the training datasets.

### Stage 1.
```bash
python train.py --cfg configs/yamls/stage1.yaml
```

### Stage 2.
Training stage 2 requires pretrained results from the stage 1. You can use your pretrained results, or download the weight from [Google Drive](https://drive.google.com/file/d/1Erjkho7O0bnZFawarntICRUCroaKabRE/view?usp=sharing) save as `checkpoints/wham_stage1.tar.pth`.
```bash
python train.py --cfg configs/yamls/stage2.yaml TRAIN.CHECKPOINT <PATH-TO-STAGE1-RESULTS>
```

### Train with BEDLAM
TBD

## Acknowledgement
We would like to sincerely appreciate Hongwei Yi and Silvia Zuffi for the discussion and proofreading. Part of this work was done when Soyong Shin was an intern at the Max Planck Institute for Intelligence System.

The base implementation is largely borrowed from [VIBE](https://github.com/mkocabas/VIBE) and [TCMR](https://github.com/hongsukchoi/TCMR_RELEASE). We use [ViTPose](https://github.com/ViTAE-Transformer/ViTPose) for 2D keypoints detection and [DPVO](https://github.com/princeton-vl/DPVO), [DROID-SLAM](https://github.com/princeton-vl/DROID-SLAM) for extracting camera motion. Please visit their official websites for more details.

## TODO

- [ ] Data preprocessing

- [x] Training implementation

- [x] Colab demo release

- [x] Demo for custom videos

## Citation
```
@InProceedings{shin2023wham,  
title={WHAM: Reconstructing World-grounded Humans with Accurate 3D Motion},
author={Shin, Soyong and Kim, Juyong and Halilaj, Eni and Black, Michael J.},  
booktitle={Computer Vision and Pattern Recognition (CVPR)},  
year={2024}  
}  
```

## License
Please see [License](./LICENSE) for details.

## Contact
Please contact soyongs@andrew.cmu.edu for any questions related to this work.
