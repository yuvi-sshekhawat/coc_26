You are the final senior engineer + QA auditor for this AI-05 project.

Inspect the ENTIRE repository before changing anything. Do not rewrite everything from scratch. Reuse correct code and fix/refactor what is wrong.

==================================================
1. STRICT PROBLEM COMPLIANCE
==================================================

Audit the code against the exact AI-05 problem statement:

- Required instances:
  A-n32-k5
  A-n33-k5
  B-n31-k5

- Use ONLY the instance-published:
  depot
  coordinates
  demands
  vehicle count
  vehicle capacity
  edge-weight rules

- Stock:
  S = floor(0.70 * total_demand)

- Allocation:
  0 <= q_i <= d_i
  sum(q_i) <= S

- 4 quadrant regions relative to depot.

Axis rules:
- x == depot_x -> positive/right
- y == depot_y -> positive/up

- Regional service:
  s_r = delivered_region_demand / original_region_demand

- Balance:
  1 - (max(s_r) - min(s_r))

- Every route:
  depot -> customers -> depot

- Vehicle capacity must be respected.

- Routing demand must be q_i, NOT original d_i.

- Use the exact CVRPLIB edge-weight / rounding semantics.

Judging priority:
1. maximize minimum regional service
2. minimize total route distance
3. maximize Balance

Never let distance optimization violate fairness or hard constraints.

==================================================
2. HARDCODE AUDIT
==================================================

Search the ENTIRE repo for hardcoded instance-specific data.

Remove hardcoded:
- coordinates
- demands
- depot
- capacity
- vehicle count
- distance matrix
- routes
- benchmark results
- service ratios
- Balance
- runtime results

These must come dynamically from the official instance/results.

Allowed:
- problem constant 0.70
- region names
- algorithm defaults
- UI styling values
- test fixture data

If you genuinely need a value that cannot be obtained from the problem, repository, or official instance/documentation, ASK ME instead of inventing it.

==================================================
3. TEST EVERYTHING
==================================================

Run and fix:

- unit tests
- integration tests
- allocation tests
- region/axis tests
- routing tests
- capacity tests
- metric tests
- API tests
- frontend build

Then run ALL THREE real instances.

Do not claim success unless actually verified.

For every final solution verify:

- allocation bounds
- stock
- regional assignment
- regional service
- Balance
- depot start/end
- capacity
- customer coverage
- no duplicates
- q_i exactly matches routed quantity
- official distance semantics

==================================================
4. OPTIMIZATION AUDIT
==================================================

Verify that the system really performs:

fair allocation
→ multiple/near-optimal candidate allocations
→ actual CVRP routing
→ route improvement
→ lexicographic comparison

Do not use a proxy as the final route score.

Do not optimize only distance.

Keep the validator as the final authority.

==================================================
5. UI REDESIGN
==================================================

The current UI contains too much unnecessary “hackathon/explanation/scorecard” content.

REDUCE IT.

Remove UI text/content that does not directly help the user operate or understand the planner.

Keep the UI focused on:

- instance selection
- map
- vehicle routes
- live vehicle status
- allocation
- regional service
- distance
- Balance
- minimum service
- validation state
- useful controls

Do NOT show excessive:
- judging explanations
- essay-like problem statements
- unnecessary marketing copy
- repeated optimization explanations
- decorative “AI” content

The app should feel like a REAL operational planning dashboard, not a presentation slide.

Keep the neo-brutalist design:
- thick borders
- hard shadows
- bold typography
- flat/high-contrast blocks
- minimal rounded corners

==================================================
6. REAL DYNAMIC GOOGLE MAP
==================================================

Replace the current placeholder/static map with a REAL Google Maps integration.

Use Google Maps JavaScript API or the official modern React integration.

Do not hardcode:
- customer positions
- depot positions
- routes

Read them from actual project data.

The map must dynamically show:

- depot
- customer locations
- region information
- assigned delivery quantities
- vehicle routes
- route direction
- route distance

Use different route colors for different vehicles.

Clicking a customer should show useful data such as:
- customer ID
- original demand
- allocated quantity
- service %
- region

==================================================
7. GPS / LIVE VEHICLE TRACKING
==================================================

Add a realistic GPS tracking feature.

Architecture:

backend vehicle state
        ↓
API / WebSocket
        ↓
frontend live map
        ↓
vehicle marker moves along route

For demo/development:

Create a SIMULATED GPS mode that moves vehicles along their assigned route automatically.

Clearly label it:

“SIMULATION”

Do NOT pretend it is real GPS hardware.

Also create an architecture that can later accept real GPS coordinates.

The UI should show:
- vehicle marker
- vehicle ID
- current location
- current route
- load
- delivery progress
- active/inactive state

Vehicles should visibly move on the map during simulation.

Use WebSocket/SSE/polling as appropriate.

==================================================
8. BACKEND / API
==================================================

Keep the solver separate from the UI.

API should provide actual generated data for:

- instances
- final metrics
- allocation
- routes
- vehicle state
- validation
- tracking state

The frontend must NOT contain optimization logic.

==================================================
9. FINAL RESULTS
==================================================

For:

A-n32-k5
A-n33-k5
B-n31-k5

Generate actual:

- allocation
- routes
- metrics
- regional service
- Balance
- distance
- runtime
- validation
- visualizations

Never fabricate values.

==================================================
10. FINAL DOCUMENTATION
==================================================

At the VERY END create:

PROJECT_DOCUMENTATION.md

This must explain the ENTIRE project from beginning to end.

Include:

1. Project overview
2. Complete original problem statement
3. Objectives and judging criteria
4. Mathematical formulation
5. Constraints
6. Allocation algorithm
7. Routing algorithm
8. Joint optimization
9. Local search
10. Validation system
11. Distance semantics
12. Region logic
13. Full repository/file structure
14. Purpose of EVERY important file
15. Backend architecture
16. API endpoints
17. Frontend architecture
18. Every major UI section
19. Explanation of EVERY visible UI text/label
20. How the map works
21. How dynamic routes work
22. How GPS simulation works
23. How real GPS could be connected
24. Installation
25. How to run backend
26. How to run frontend
27. How to run benchmark
28. How to generate results
29. How to interpret metrics
30. How to use every major website control
31. Troubleshooting
32. Testing
33. Reproducibility
34. Limitations
35. Future improvements
36. Final benchmark results

Write it so a completely new developer can understand and operate the project without asking the original developer.

==================================================
11. FINAL QUALITY GATE
==================================================

Before declaring completion:

[ ] all 3 official instances work
[ ] no illegal hardcoded instance values
[ ] all hard constraints pass
[ ] fairness objective verified
[ ] routing objective verified
[ ] Balance verified
[ ] tests pass
[ ] benchmark generated
[ ] API works
[ ] frontend builds
[ ] Google Map works
[ ] route lines are dynamic
[ ] simulated GPS vehicles move
[ ] UI contains only relevant operational content
[ ] documentation complete

Create:

FINAL_AUDIT_REPORT.md

with a simple table:

Requirement | PASS/FAIL/BLOCKED | Evidence | Fix

Never say READY unless all critical items are verified.

Start by inspecting the repo, then audit, fix, test, benchmark, improve UI, integrate the real map/tracking, and finally generate PROJECT_DOCUMENTATION.md and FINAL_AUDIT_REPORT.md.