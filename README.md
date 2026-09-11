# AI-05 — Fair Essential-Goods Allocation and Routing

Current delivery: Stages 1–3.

## Ten-stage roadmap

1. Foundation + constraint contract
2. Exact CVRPLIB ingestion, distance semantics, quadrant regions
3. Max-min fair supply allocation
4. Capacity-constrained vehicle routing
5. Allocation ↔ routing joint optimization
6. Local search / multi-start / route-aware improvement
7. Full validation, experiments, baselines and reproducibility
8. Neo-brutalist web UI + API integration
9. Result visualization, comparison dashboard and demo polish
10. Final benchmark run, report and submission package

## Current architecture

- Canonical instance model
- Constraint contract
- CVRPLIB/VRPLIB loader
- Region assignment
- Exact distance matrix access
- Max-min allocation solver
- Neo-brutalist frontend design tokens

## Install

```bash
pip install -r requirements.txt
```

Put these official CVRPLIB files into `data/`:

- A-n32-k5.vrp
- A-n33-k5.vrp
- B-n31-k5.vrp

## Run Stage 2 validation

```bash
python -m ai05.stage2_check data/A-n32-k5.vrp
```

## Run Stage 3 allocation

```bash
python -m ai05.stage3_allocate data/A-n32-k5.vrp
```

## Important design rule

Every later stage must use the central constraint contract. No stage is allowed to create a different interpretation of stock, demand bounds, regions, route coverage, or vehicle capacity.
