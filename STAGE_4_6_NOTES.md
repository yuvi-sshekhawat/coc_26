# Stages 4–6 review notes

## Stage 4 — routing
- Routing demand is q_i.
- Only q_i > 0 customers are routed.
- Each route starts and ends at the official depot.
- Hard vehicle capacity is enforced by OR-Tools.
- A positive-allocation customer must not exceed one vehicle's capacity in the current single-visit implementation.
- The same official edge-weight matrix is used for routing and reported distance.
- 2-opt only changes route order, so it does not alter allocation or capacity.

## Stage 5 — joint search
The first allocation solve maximizes the minimum regional service ratio.

Candidate generation then keeps every region's delivered amount at least as high as the base max-min allocation. This means the candidate set cannot have a worse minimum regional service than the base allocation, subject to exact integer quantities.

Candidates use a route-distance proxy only to diversify / bias allocation search. Final selection always uses the actual CVRP distance.

Lexicographic selection:
1. maximize minimum regional service;
2. minimize total route distance;
3. maximize Balance.

## Stage 6 — local improvement
Same-region quantity transfers preserve regional delivered totals exactly. Therefore service ratios do not decrease; the actual routing cost is re-solved after the move.

This stage is deliberately conservative. Do not add inter-region moves until the integration and validator tests are green.
