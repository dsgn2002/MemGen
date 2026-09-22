#!/usr/bin/env bash
set -euo pipefail
journey_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
. "$HOME/.config/my-travel-journey/stepfun.env"
set +a
# The user selected the Step Plan subscription endpoint for this project.
export STEP_API_BASE=https://api.stepfun.com/step_plan/v1
journey_python="$HOME/miniforge3/envs/travel_journey_map/bin/python"
exec "$journey_python" "$journey_root/scripts/analyze.py" \
  --env "$HOME/.config/my-travel-journey/stepfun.env" \
  --run "${1:-$journey_root/runs/2026-09-22-demo}" \
  --stage "${2:-observe}"
