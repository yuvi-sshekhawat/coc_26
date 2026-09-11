# AI-05 — Final Stage 1–10 Package

## Ten stages completed in code architecture

1. Foundation + constraint contract
2. Exact CVRPLIB ingestion + regions
3. Max-min fair allocation
4. Capacity-constrained CVRP
5. Allocation ↔ routing joint search
6. Local search + 2-opt
7. Production validation + benchmark scaffolding
8. FastAPI backend
9. Neo-brutalist dashboard
10. Final benchmark runner + plots + submission bundle

## What is intentionally NOT included

No fabricated benchmark numbers are included. The official `.vrp` files must be placed in `data/` and executed in the final environment with the solver dependencies installed.

## Final selection rule

The project uses:
1. maximum minimum regional service;
2. minimum total route distance;
3. maximum Balance.

Hard constraints always dominate candidate acceptance.

## Final command

```bash
python scripts/run_final_benchmark.py --seed 42 --candidates 30 --route-seconds 3
```

## Final package

```bash
python scripts/make_submission_bundle.py
```
