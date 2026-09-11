

# Stages 4–6

## Stage 4 — Routing
`routing.py` solves CVRP for a fixed allocation q.

- q_i is the routing demand.
- q_i = 0 customers are optional and skipped.
- q_i > 0 customers are mandatory.
- every route starts/ends at the official depot.
- vehicle load <= published capacity.
- the official edge-weight matrix is reused.

## Stage 5 — Joint allocation + routing
`optimization.py`:
1. solves max-min allocation;
2. generates near-optimal allocation candidates that preserve the base region delivered amounts;
3. routes candidates with a small solver portfolio;
4. ranks candidates lexicographically:
   - larger minimum regional service;
   - lower distance;
   - larger Balance.

## Stage 6 — Improvement
- same-region quantity transfers preserve regional delivered totals;
- each candidate move is re-routed and validated;
- 2-opt changes only order, not allocation/capacity;
- no accepted move can weaken the lexicographic objective.

## Smoke tests

```bash
pytest -q
```

The smoke test uses a synthetic instance because this runtime could not fetch raw GitHub files through the container. The official CVRPLIB files should be put in `data/` before final benchmark runs.
