# AI-05: Fair Essential-Goods Allocation & Routing — Full Build Plan (2-Person Split)

## 1. Problem in One Picture

```mermaid
flowchart TD
    A[Load CVRPLIB instance via VRPLIB] --> B[Compute S = floor(0.7 * sum demand)]
    B --> C[Assign quadrant region: NE/NW/SW/SE per customer]
    C --> D[Fair Allocation: q_i for every customer]
    D --> E[Drop customers with q_i = 0]
    E --> F[Solve CVRP on remaining customers, demand = q_i]
    F --> G[Compute per-region s_r, Balance, total distance]
    G --> H[Validate all constraints]
    H --> I[Export routes, tables, plots, report]
```

**Quadrant convention** (tie → positive side), depot translated to origin:
```
        NW (x<0,y>=0) | NE (x>=0,y>=0)
        --------------+--------------
        SW (x<0,y<0)  | SE (x>=0,y<0)
```

## 2. The Key Insight (wins 60/100 points almost for free)

Points 40 (min region ratio) + 20 (balance) = 60/100 both reward **equal s_r across regions**.
If `q_i = t * d_i` for **every customer with the same global t**, then for any region:
`s_r = Σ(t*d_i in r) / Σ(d_i in r) = t` — identical for all regions → Balance = 1, min_r(s_r) = t.
`t = S / Σd_i ≈ 0.70`. Only integer rounding perturbs this slightly (handled explicitly in Person A's Step 4).

---

## 3. Team Split

- **Person A — Data & Fairness Lane**: instance parsing, region logic, allocation algorithm, metrics, report.
- **Person B — Routing & Delivery Lane**: distance matrix, CVRP solver, validation, visualization, packaging.
- **Shared contract**: Person A outputs `allocation.json` (schema below) that Person B consumes untouched. Agree on this schema in the first 15 minutes before splitting up — it's the only integration point.

```json
// allocation.json — Person A's output, Person B's input
{
  "instance": "A-n32-k5",
  "S": 450,
  "t": 0.6993,
  "customers": [
    {"id": 1, "x": 12, "y": -5, "demand": 19, "q": 13, "region": "SE"}
  ],
  "region_totals": {"NE": {"demand": 200, "q": 140}, "...": {}}
}
```

---

## 4. Person A — Data & Fairness Lane (Steps 0–4, 9's assertions on allocation, and final report)

### Step A0 — Environment & parsing (`io.py`)
```bash
pip install vrplib numpy pandas
```
- `vrplib.read_instance(path)` → `node_coord`, `demand`, `capacity`, `depot`, `edge_weight_type`.
- Vehicle count K: parse from filename suffix `-kX`, or from instance metadata if present.
- Store depot coords separately; translate all customer coords so depot = (0,0) — needed for region logic AND must be undone (or kept consistent) before Person B computes distances (agree: **keep original untranslated coords for distance matrix**, use translated copy only for region assignment).
- Output a clean `Instance` object/dataclass: `{name, depot_xy, customers: [{id, x, y, demand}], capacity, K, edge_weight_type}`.

### Step A1 — Region assignment
```python
def region(x, y):
    if x >= 0 and y >= 0: return "NE"
    if x < 0 and y >= 0:  return "NW"
    if x < 0 and y < 0:   return "SW"
    return "SE"
```
Apply to depot-relative coordinates. Store on each customer record.

### Step A2 — Compute total stock S
`S = floor(0.70 * sum(d_i for all customers))`. Print/log this per instance — it's a required reported number.

### Step A3 — Fair allocation algorithm (`allocate.py`) — the core deliverable
1. `total_d = sum(d_i)`, `t = S / total_d`.
2. `raw_i = t * d_i` for every customer.
3. `q_i = floor(raw_i)`; `remainder_i = raw_i - q_i`.
4. `leftover = S - sum(q_i)` (small, from flooring — typically < number of customers).
5. **Round-robin leftover distribution** to preserve balance:
   - Compute current `s_r` per region with the floored q_i.
   - Repeat `leftover` times: pick the region with the *lowest current s_r*; within it, give +1 to the customer with the highest `remainder_i` among those with `q_i < d_i`; update that region's `s_r`.
   - This keeps regions converging back toward equal s_r instead of one region absorbing all rounding gain.
6. Hard asserts before writing output:
   - `all(0 <= q_i <= d_i)`
   - `sum(q_i) <= S`
7. Compute final `s_r` per region and `Balance = 1 - (max(s_r) - min(s_r))`.
8. Write `allocation.json` (schema above) + a human-readable `allocation.csv` (columns: id, x, y, demand, q, region).

### Step A4 — Region metrics table (`metrics.py`, allocation half)
Produce `region_table.csv`:
| region | Σdemand | Σq | s_r |
|---|---|---|---|
plus a summary row: `min_r(s_r)`, `Balance`.

### Step A5 — Report writing (after Person B finishes routing)
- Draft `report.md` sections: problem restatement, allocation methodology (cite the §2 proof), region table, and the fairness justification. Leave routing/distance section as a placeholder for Person B to fill.

**Estimated time for Person A: ~2.5–3 hrs** (parsing 30m, region logic 20m, allocation + rounding logic 1–1.5h incl. testing, metrics 20m, report 40m).

---

## 5. Person B — Routing & Delivery Lane (Steps 5–8, 9's routing assertions, packaging)

### Step B0 — Environment
```bash
pip install ortools matplotlib
```

### Step B1 — Distance matrix (per instance's exact rule)
- For `EUC_2D` (all three given instances use this): `d(i,j) = round(sqrt(dx^2+dy^2))` using **nearest-integer rounding**, not floor/ceil — this is CVRPLIB's standard and affects total-distance scoring directly if done wrong.
- Build once per instance over depot + all customers (full matrix, index 0 = depot); index rows so Person A's dropped (q_i=0) customers are simply excluded from the node list passed to the solver — don't remove from the matrix build, just don't include their row/col in the routing model's node list.

### Step B2 — Reduce customer set
- Load `allocation.json` from Person A.
- Routing nodes = depot + `{customer : q_i > 0}`. Demand per node = `q_i` (not original `d_i`).

### Step B3 — CVRP solve (`route.py`) — OR-Tools
- `RoutingIndexManager(num_nodes, K, depot_index)`, `RoutingModel`.
- Distance callback = the precomputed matrix from B1.
- Capacity dimension: demands = `q_i`, vehicle capacities = `[capacity]*K`.
- `first_solution_strategy = PATH_CHEAPEST_ARC`
- `local_search_metaheuristic = GUIDED_LOCAL_SEARCH`
- `time_limit_seconds = 15–20` per instance (fixed value — needed for reproducibility scoring).
- Fix the solver's random seed if exposed; otherwise fix `time_limit` + log solver version for reproducibility.
- Extract per-vehicle route (list of customer ids, in order), per-route load, per-route distance.
- Fallback if OR-Tools infeasible/unavailable: Clarke-Wright savings construction + 2-opt local search (simpler, still valid, slightly worse distance score — use only as backup).

### Step B4 — Validation (`validate.py`) — shared checklist, but Person B owns since routes are the risk area
- [ ] every route starts and ends at depot index 0
- [ ] `sum(q_i for route) <= capacity` for every route
- [ ] every node with `q_i > 0` appears in exactly one route
- [ ] no node repeated across routes
- [ ] `num_routes_used <= K`
- [ ] distances recomputed independently from route sequences and cross-checked against solver's reported total (catches rounding-rule bugs)

### Step B5 — Metrics (routing half)
- `total_distance` = sum of all route distances (int, per instance rounding rule).
- `routes.json`: `[{vehicle_id, sequence: [0, ...ids..., 0], load, distance}]`.

### Step B6 — Visualization (`viz.py`)
- Matplotlib per instance: depot = star marker, customers colored by region (4 colors), routes drawn as distinct-colored polylines, legend showing route # + load/capacity.
- Save `plot.png` per instance.

### Step B7 — Packaging & reproducibility
- `main.py`: single entrypoint looping over the 3 instances, calling Person A's allocation then Person B's routing, writing `results/<instance>/{allocation.csv, allocation.json, region_table.csv, routes.json, metrics.json, plot.png}`.
- Log runtime per instance (`time.time()` deltas) into `metrics.json`.
- Pin package versions (`requirements.txt`) and fix all time limits / seeds so re-runs reproduce near-identical distances.
- Fill in the routing/distance section of `report.md` (methodology: OR-Tools GLS, why chosen, time-limit tradeoff).

**Estimated time for Person B: ~2.5–3 hrs** (distance matrix + rounding correctness 30m, OR-Tools model 1–1.5h incl. debugging capacity/depot constraints, validation 30m, viz 30m, packaging 20m).

---

## 6. Integration Checklist (both, ~30 min at the end)
- [ ] Run `main.py` end-to-end on all 3 instances without manual intervention.
- [ ] Cross-check: Person A's `Σq_i` for an instance ties out exactly with Person B's `sum(demand)` over routed nodes.
- [ ] Confirm `min_r(s_r)`, `Balance`, and `total_distance` are all present in each instance's `metrics.json`.
- [ ] Sanity-check plots visually against the route JSON (no crossed depot skips, no orphan customers).
- [ ] Assemble final `report.md` with both sections + the scoring cheat-sheet below.

## 7. Scoring Alignment Cheat-Sheet
| Criterion | Pts | Owner | How this plan hits it |
|---|---|---|---|
| Min regional ratio | 40 | Person A | Uniform-t allocation ⇒ all s_r ≈ 0.70 |
| Total distance | 30 | Person B | OR-Tools GLS on reduced (q_i>0) node set, correct EUC_2D rounding |
| Regional balance | 20 | Person A | Uniform-t + round-robin rounding ⇒ Balance ≈ 1 |
| Validity | 5 | Person B (checklist), both (asserts) | Explicit asserts in Steps A3 & B4 |
| Runtime/reproducibility | 5 | Person B | Fixed seeds/time-limits, logged runtimes, pinned versions |

Want me to start writing the actual `io.py` / `allocate.py` (Person A) or `route.py` / `validate.py` (Person B) code next?
