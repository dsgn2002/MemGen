#!/usr/bin/env bash
set -euo pipefail
base=/home/Developer/travel_journey_map
run="$base/runs/2026-09-26-sai-kung-map"
export PATH=/home/Developer/miniforge3/envs/travel_journey_map/bin:/usr/local/cuda-13.0/bin:$PATH
export CUDA_HOME=/usr/local/cuda-13.0
export TORCH_CUDA_ARCH_LIST=12.1
export MAX_JOBS=4
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMNI_KIT_ACCEPT_EULA=yes
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
for name in coast traveler boat; do
  if ! test -f "$run/output/$name-style.png"; then
    printf 'Missing styled asset: %s. Run the style stage first.\n' "$name" >&2
    exit 1
  fi
done
python -c 'import torch, cumesh, nvdiffrast.torch, o_voxel; assert torch.cuda.is_available(), "CUDA unavailable"'
python -u "$base/scripts/generate_meshes.py"
python -u "$base/scripts/assemble_omniverse.py"
python -u "$base/scripts/package_browser.py"
cp "$base/scripts/viewer.html" "$run/output/index.html"
printf 'MAP_COMPLETE\n'
