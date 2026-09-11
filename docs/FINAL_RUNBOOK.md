# AI-05 Final Runbook

## 1. Install

Backend solver requirements:

```bash
python -m pip install -r requirements.txt
```

Dashboard:

```bash
cd frontend
npm install
```

## 2. Put official data in place

`data/` must contain:

- A-n32-k5.vrp
- A-n33-k5.vrp
- B-n31-k5.vrp

Do not rename a different instance to one of these names.

## 3. Run all three instances

From repository root:

```bash
python scripts/run_final_benchmark.py --seed 42 --candidates 30 --route-seconds 3
```

For final tuning you can raise `--candidates` and `--route-seconds`, provided the event's runtime limit allows it.

## 4. Inspect the generated result

Each instance receives:

- metrics.json
- allocation.json
- routes.json
- routes.txt
- summary.json
- routes.png
- regional_service.png
- allocation.png

## 5. Non-negotiable validation

A final candidate must pass:
- q_i bounds
- stock
- quadrant coverage
- route start/end at depot
- vehicle capacity
- exact active-customer coverage
- no duplicate customer visits
- route distance computed from the same official edge-weight matrix

## 6. UI

Start API:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Start frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown by the terminal.

## 7. Before submission

Never report placeholder values.

Copy only the values from `results/*/summary.json` and `metrics.json`.

Record:
- seed
- candidate count
- routing time limit
- runtime per instance
- minimum service
- balance
- route distance
- fairness gap
- validation status
