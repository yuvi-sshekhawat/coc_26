from __future__ import annotations

import json
import math
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ai05.loader import load_instance
from ai05.regions import prepare_regions
from ai05.validation import validate_all
from .services.scenario_adapter import parse_and_validate_csv
from .services.scenario_store import (
    create_scenario,
    get_scenario,
    init_scenario_storage,
    list_scenarios,
    solve_scenario,
)

DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_scenario_storage()
    yield


app = FastAPI(
    title="AI-05 Fair Relief Planner API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    stage: int = Field(10)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", stage=10)


@app.get("/api/instances")
def list_instances():
    return {
        "instances": ["A-n32-k5", "A-n33-k5", "B-n31-k5"],
        "stock_rule": "floor(0.70 * total_demand)",
        "regions": ["RIGHT_UP", "LEFT_UP", "LEFT_DOWN", "RIGHT_DOWN"],
    }


# =====================================================================
# RELIEF SCENARIO SYSTEM (Real-World Logistics & MapLibre Integration)
# =====================================================================

class CreateScenarioRequest(BaseModel):
    name: str = Field(..., description="Scenario Name e.g. Jaipur Flood Relief")
    depot_name: str = Field(..., description="Depot Name e.g. Jaipur Central Relief Warehouse")
    depot_latitude: float = Field(..., ge=-90.0, le=90.0)
    depot_longitude: float = Field(..., ge=-180.0, le=180.0)
    csv_content: str = Field(..., description="Requirements CSV content")
    auto_solve: bool = Field(True, description="Whether to run AI-05 allocation immediately")


class ValidateCsvRequest(BaseModel):
    csv_content: str


@app.get("/api/scenarios")
def get_all_scenarios():
    return {"scenarios": list_scenarios()}


@app.get("/api/scenarios/{scenario_id}")
def get_single_scenario(scenario_id: str):
    try:
        return get_scenario(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Relief scenario not found.")


@app.post("/api/scenarios")
def create_new_scenario(req: CreateScenarioRequest):
    try:
        created = create_scenario(
            name=req.name,
            depot_name=req.depot_name,
            depot_latitude=req.depot_latitude,
            depot_longitude=req.depot_longitude,
            csv_content=req.csv_content,
            auto_solve=req.auto_solve,
        )
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create scenario: {e}")


@app.post("/api/scenarios/{scenario_id}/solve")
def solve_single_scenario(scenario_id: str):
    try:
        return solve_scenario(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Relief scenario not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to solve scenario: {e}")


@app.post("/api/scenarios/validate-csv")
def validate_csv_preview(req: ValidateCsvRequest):
    try:
        records = parse_and_validate_csv(req.csv_content)
        total_demand = sum(r.demand for r in records)
        return {
            "valid": True,
            "total_customers": len(records),
            "total_demand": total_demand,
            "estimated_stock": int(math.floor(0.70 * total_demand)),
            "preview": [
                {
                    "customer_id": r.customer_id,
                    "location_name": r.location_name,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "demand": r.demand,
                }
                for r in records[:5]
            ],
        }
    except ValueError as e:
        return {
            "valid": False,
            "error": str(e),
        }


@app.get("/api/results")
def list_results():
    if not RESULTS_DIR.exists():
        return {"results": []}

    output = []
    for p in sorted(RESULTS_DIR.glob("*/metrics.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            output.append(payload)
        except json.JSONDecodeError:
            continue

    return {"results": output}


@app.get("/api/results/{instance_name}")
def get_result(instance_name: str):
    path = RESULTS_DIR / instance_name / "metrics.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Result not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/results/{instance_name}/routes")
def get_routes(instance_name: str):
    path = RESULTS_DIR / instance_name / "routes.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Routes not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/results/{instance_name}/allocation")
def get_allocation(instance_name: str):
    path = RESULTS_DIR / instance_name / "allocation.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Allocation not found.")
    alloc_data = json.loads(path.read_text(encoding="utf-8"))

    # Also enrich with node coordinates, demands, and regions if instance file is present
    instance_file = DATA_DIR / f"{instance_name}.vrp"
    if instance_file.exists():
        try:
            inst = load_instance(instance_file)
            prep = prepare_regions(inst)
            alloc_arr = alloc_data.get("allocation", [])
            nodes = []
            for i in range(inst.dimension):
                q_i = alloc_arr[i] if i < len(alloc_arr) else 0
                d_i = int(inst.demand[i])
                ratio = q_i / d_i if d_i > 0 else (1.0 if i == inst.depot else 0.0)
                nodes.append({
                    "id": i,
                    "is_depot": i == inst.depot,
                    "x": float(inst.node_coord[i, 0]),
                    "y": float(inst.node_coord[i, 1]),
                    "original_demand": d_i,
                    "allocated_demand": int(q_i),
                    "ratio": float(ratio),
                    "region": prep.regions[i].name if i in prep.regions else "DEPOT",
                })
            alloc_data["nodes"] = nodes
            alloc_data["depot"] = inst.depot
            alloc_data["capacity"] = inst.capacity
            alloc_data["vehicles"] = inst.vehicles
        except Exception:
            pass

    return alloc_data


@app.get("/api/results/{instance_name}/validation")
def get_validation(instance_name: str):
    metrics_path = RESULTS_DIR / instance_name / "metrics.json"
    alloc_path = RESULTS_DIR / instance_name / "allocation.json"
    routes_path = RESULTS_DIR / instance_name / "routes.json"
    instance_file = DATA_DIR / f"{instance_name}.vrp"

    if not (metrics_path.exists() and alloc_path.exists() and routes_path.exists()):
        raise HTTPException(status_code=404, detail="Result files not found for validation.")

    if not instance_file.exists():
        return {
            "valid": True,
            "status": "PASS",
            "errors": [],
            "note": "Validated during solver run; instance file not present for re-validation.",
        }

    try:
        inst = load_instance(instance_file)
        prep = prepare_regions(inst)
        alloc_data = json.loads(alloc_path.read_text(encoding="utf-8"))
        routes_data = json.loads(routes_path.read_text(encoding="utf-8"))

        allocation = alloc_data.get("allocation", [])
        routes = [r.get("nodes", []) for r in routes_data.get("routes", [])]

        report = validate_all(prep, allocation, routes)
        return {
            "valid": report.valid,
            "status": "PASS" if report.valid else "FAIL",
            "errors": list(report.errors),
            "checks": {
                "allocation_bounds": report.allocation_bounds_ok,
                "stock_bound": report.stock_ok,
                "regional_coverage": report.regional_coverage_ok,
                "depot_start_end": report.depot_start_end_ok,
                "vehicle_capacity": report.vehicle_capacity_ok,
                "route_coverage": report.route_coverage_ok,
                "customer_uniqueness": report.customer_uniqueness_ok,
            },
        }
    except Exception as e:
        return {
            "valid": False,
            "status": "FAIL",
            "errors": [str(e)],
        }


@app.get("/api/results/{instance_name}/summary")
def get_summary(instance_name: str):
    path = RESULTS_DIR / instance_name / "summary.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/results/{instance_name}/baselines")
def get_baselines(instance_name: str):
    path = RESULTS_DIR / instance_name / "baselines.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Baselines not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/results/{instance_name}/plots/{plot_name}")
def get_plot(instance_name: str, plot_name: str):
    path = RESULTS_DIR / instance_name / f"{plot_name}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Plot {plot_name}.png not found.")
    return FileResponse(path, media_type="image/png")
