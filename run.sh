#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-src}"

python scripts/run_final_benchmark.py \
  --seed 42 \
  --candidates "${CANDIDATES:-30}" \
  --route-seconds "${ROUTE_SECONDS:-3}"
