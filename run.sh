#!/usr/bin/env bash
set -euo pipefail

python scripts/run_final_benchmark.py \
  --seed 42 \
  --candidates "${CANDIDATES:-30}" \
  --route-seconds "${ROUTE_SECONDS:-3}"
