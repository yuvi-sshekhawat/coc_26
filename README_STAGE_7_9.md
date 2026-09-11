# AI-05 Stages 7–9

## Stage 7 — production validation + benchmark runner

Added:
- shared validation service
- score/lexicographic comparison service
- benchmark execution skeleton
- result manifest API support

Hard constraint philosophy:
- invalid allocation never gets scored
- invalid route never gets scored
- candidate selection follows:
  1. maximum minimum regional service
  2. minimum route distance
  3. maximum Balance

Before final benchmark, put the official instance files into the cumulative backend/data directory and run the existing stage modules on all three instances.

## Stage 8 — API

FastAPI exposes:
- `GET /api/health`
- `GET /api/instances`
- `GET /api/results`
- `GET /api/results/{instance_name}`
- `GET /api/results/{instance_name}/routes`

Run:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Stage 9 — neo-brutalist dashboard

The frontend uses React/Vite plus a small custom neo-brutalist system. It deliberately keeps the visual language simple:
- thick black outlines
- offset black shadows
- hard edges
- high-contrast blocks
- monospace technical labels
- no glossy gradients

Tailwind/shadcn are deliberately not required yet. The current UI is easier to run as a minimal Vite app while preserving freedom to adopt shadcn components later. Tailwind supports utility-first styling and responsive/state variants, while shadcn's current approach gives source-owned components that can be customized deeply. Official docs: Tailwind utility classes and responsive variants; shadcn installation/components.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard currently becomes informative once result JSON files exist.
Stage 9 is the UI foundation; exact route maps/plots are finalized in Stage 10.
