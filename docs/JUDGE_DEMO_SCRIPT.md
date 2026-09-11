# 90-second judge demo

### 0–15s — Problem
“Only 70% of aggregate demand is available. A naive nearest-customer policy can make one geographic region substantially less served than another.”

### 15–30s — Fairness engine
“We model q_i as delivered quantity and maximize t, the minimum regional service ratio, subject to stock and customer demand constraints.”

### 30–45s — Routing
“Once we have a fair allocation, q_i becomes the routing demand. Five vehicles must start and end at the depot and stay within capacity.”

### 45–60s — Joint improvement
“We evaluate multiple near-optimal fair allocations, then use actual route distance—not a proxy—to choose among them. Same-region quantity moves preserve fairness while improving routeability.”

### 60–75s — Evidence
Show:
- minimum regional service
- Balance
- total distance
- validation = PASS
- route map

### 75–90s — Why it is robust
“Every candidate goes through the same constraint validator, the same edge-weight matrix, and a fixed seed. The final benchmark contains outputs for all three required instances.”
