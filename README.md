# AI-05 — Fair Essential-Goods Allocation and Routing Platform

High-performance, constraint-abiding disaster relief logistics optimization engine, FastAPI REST service, and interactive web dashboard.

---

## Architecture Overview

1. **Exact CVRPLIB & Regional Ingestion**: Parses standard `.vrp` instances and real-world disaster coordination CSVs, computing exact edge weight matrices and geographic quadrants.
2. **Max-Min Fair Allocation**: Mathematically prioritizes worst-served regions and customers under bounded supply constraints.
3. **Capacity-Constrained Vehicle Routing (CVRP)**: Solves multi-vehicle route schedules strictly respecting vehicle capacity and customer delivery quotas.
4. **Joint Optimization & Local Search**: Iterative candidate exploration and 2-opt route refinement maximizing regional service balance while minimizing travel distance.
5. **Strict Constraint Contract & Validation**: Centralized validation verifying zero depot allocation, capacity bounds, and non-negativity.
6. **FastAPI Backend & Interactive Web UI**: RESTful endpoints and interactive dashboard with MapLibre geospatial mapping.

---

## Quick Start

### 1. Python Environment & Dependencies

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

### 2. Run Test Suite

```bash
python -m pytest tests
```

### 3. Run Benchmark Suite

```bash
python scripts/run_final_benchmark.py --seed 42 --candidates 30 --route-seconds 3
```
*Or on Windows:*
```cmd
run.bat
```

### 4. Start the Application

**Backend:**
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

The frontend dashboard will be available at `http://localhost:5173`.
API documentation will be available at `http://localhost:8000/docs`.

---

## Official Benchmark Instances

- `data/A-n32-k5.vrp`
- `data/A-n33-k5.vrp`
- `data/B-n31-k5.vrp`
