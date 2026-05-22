# WHAM Unreal: WHAM FBX → Manny batch automation
#
# Copy paths.example.json to paths.json and set unreal_editor_cmd + uproject_path.
#
# Examples:
#   make import IN=/abs/path/to/unreal_fbx
#   make retarget
#   make export OUT=/abs/path/out/manny_fbx
#   make all IN=... OUT=...

PATHS ?= paths.json
PY := python3

.PHONY: import retarget export all

import:
	@test -n "$(IN)" || (echo "Set IN=/abs/path/to/unreal_fbx" && exit 1)
	$(PY) import_batch.py --paths-json "$(PATHS)" --input-dir "$(IN)" --destination-root /Game/WHAM/SourceAnimations --import-animations

retarget:
	$(PY) retarget_batch.py --paths-json "$(PATHS)" --source-root /Game/WHAM/SourceAnimations --output-root /Game/WHAM/Retargeted/Manny

export:
	@test -n "$(OUT)" || (echo "Set OUT=/abs/path/for/host_fbx_files" && exit 1)
	$(PY) export_batch.py --paths-json "$(PATHS)" --source-root /Game/WHAM/Retargeted/Manny --host-export-dir "$(OUT)"

all:
	@test -n "$(IN)" || (echo "Set IN and OUT for all target" && exit 1)
	@test -n "$(OUT)" || (echo "Set IN and OUT for all target" && exit 1)
	$(MAKE) import IN="$(IN)" PATHS="$(PATHS)" PY="$(PY)"
	$(MAKE) retarget PATHS="$(PATHS)" PY="$(PY)"
	$(MAKE) export OUT="$(OUT)" PATHS="$(PATHS)" PY="$(PY)"
