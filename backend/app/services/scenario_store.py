from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scenario_adapter import (
    CustomerRecord,
    ScenarioInput,
    parse_and_validate_csv,
    sanitize_scenario_id,
    solve_scenario_relief,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_DIR = ROOT / "relief_scenarios"


DEFAULT_SCENARIOS = [
    {
        "name": "Jaipur Flood Relief",
        "depot_name": "Jaipur Central Relief Warehouse",
        "depot_latitude": 26.9124,
        "depot_longitude": 75.7873,
        "csv": """customer_id,location_name,latitude,longitude,demand
1,Mansarovar Relief Center,26.8500,75.7600,45
2,Vaishali Nagar Community Shelter,26.9050,75.7420,35
3,Malviya Nagar Camp,26.8540,75.8150,50
4,C-Scheme Emergency Hub,26.9100,75.8020,30
5,Amer Relief Point,26.9850,75.8500,60
6,Sanganer Distribution Post,26.8150,75.7700,40
7,Vidyadhar Nagar Shelter,26.9600,75.7800,35
8,Jagatpura Relief Camp,26.8200,75.8450,55
9,Jhotwara Logistics Center,26.9400,75.7200,40
10,Raja Park Supply Point,26.8920,75.8280,25
11,Sitapura Medical Post,26.7750,75.8350,45
12,Ajmer Road Transit Camp,26.8800,75.6900,35
""",
    },
    {
        "name": "Delhi Emergency Relief",
        "depot_name": "Delhi Central Warehouse",
        "depot_latitude": 28.6139,
        "depot_longitude": 77.2090,
        "csv": """customer_id,location_name,latitude,longitude,demand
1,Rohini Emergency Hub,28.7150,77.1150,50
2,Dwarka Sector 10 Shelter,28.5820,77.0500,45
3,Saket Community Center,28.5240,77.2100,40
4,Mayur Vihar Relief Post,28.6050,77.3000,35
5,Karol Bagh Depot Annex,28.6500,77.1900,30
6,Shahdara Supply Center,28.6700,77.2900,55
7,Janakpuri Crisis Post,28.6250,77.0850,40
8,Okhla Industrial Relief,28.5350,77.2750,45
9,Civil Lines Shelter,28.6800,77.2200,30
10,Lajpat Nagar Hub,28.5700,77.2400,35
""",
    },
    {
        "name": "Mumbai Cyclone Relief",
        "depot_name": "Mumbai Harbor Relief Terminal",
        "depot_latitude": 18.9400,
        "depot_longitude": 72.8400,
        "csv": """customer_id,location_name,latitude,longitude,demand
1,Colaba Coastal Center,18.9100,72.8250,40
2,Dadar Transit Camp,19.0200,72.8450,50
3,Bandra West Relief Point,19.0550,72.8300,45
4,Kurla Crisis Warehouse,19.0700,72.8800,60
5,Andheri Emergency Shelter,19.1200,72.8400,55
6,Worli Evacuation Hub,19.0050,72.8150,35
7,Chembur Distribution Base,19.0600,72.9000,40
8,Ghatkopar Relief Center,19.0850,72.9100,45
""",
    },
]


def init_scenario_storage() -> None:
    """Ensure SCENARIOS_DIR exists and default relief scenarios are provisioned."""
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    for s_def in DEFAULT_SCENARIOS:
        s_id = sanitize_scenario_id(s_def["name"])
        s_dir = SCENARIOS_DIR / s_id
        if not (s_dir / "scenario.json").exists():
            try:
                create_scenario(
                    name=s_def["name"],
                    depot_name=s_def["depot_name"],
                    depot_latitude=s_def["depot_latitude"],
                    depot_longitude=s_def["depot_longitude"],
                    csv_content=s_def["csv"],
                    auto_solve=True,
                )
            except Exception as e:
                logger.warning(f"Could not pre-seed scenario {s_def['name']}: {e}")


def list_scenarios() -> list[dict[str, Any]]:
    """List all available relief scenarios with metadata."""
    if not SCENARIOS_DIR.exists():
        init_scenario_storage()

    scenarios = []
    for s_dir in sorted(SCENARIOS_DIR.iterdir()):
        if not s_dir.is_dir():
            continue
        meta_file = s_dir / "scenario.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            sol_file = s_dir / "solution.json"
            meta["is_solved"] = sol_file.exists()
            scenarios.append(meta)
        except Exception:
            continue

    return scenarios


def get_scenario(scenario_id: str) -> dict[str, Any]:
    """Load full details for a scenario, including solution if solved."""
    s_id = sanitize_scenario_id(scenario_id)
    s_dir = SCENARIOS_DIR / s_id
    if not s_dir.exists() or not (s_dir / "scenario.json").exists():
        raise FileNotFoundError(f"Scenario '{scenario_id}' not found.")

    meta = json.loads((s_dir / "scenario.json").read_text(encoding="utf-8"))
    locations = json.loads((s_dir / "locations.json").read_text(encoding="utf-8"))
    
    result = {
        "metadata": meta,
        "locations": locations,
        "is_solved": False,
    }

    sol_file = s_dir / "solution.json"
    if sol_file.exists():
        solution = json.loads(sol_file.read_text(encoding="utf-8"))
        result["is_solved"] = True
        result["solution"] = solution

    return result


def create_scenario(
    name: str,
    depot_name: str,
    depot_latitude: float,
    depot_longitude: float,
    csv_content: str,
    auto_solve: bool = True,
) -> dict[str, Any]:
    """Create a new relief scenario and optionally solve it immediately."""
    if not name or not name.strip():
        raise ValueError("Scenario name cannot be empty.")
    if not depot_name or not depot_name.strip():
        raise ValueError("Depot name cannot be empty.")
    if not (-90.0 <= depot_latitude <= 90.0):
        raise ValueError(f"Depot latitude {depot_latitude} is invalid (-90.0 to 90.0).")
    if not (-180.0 <= depot_longitude <= 180.0):
        raise ValueError(f"Depot longitude {depot_longitude} is invalid (-180.0 to 180.0).")

    customers = parse_and_validate_csv(csv_content)
    scenario_id = sanitize_scenario_id(name)

    s_dir = SCENARIOS_DIR / scenario_id
    s_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save requirements.csv
    (s_dir / "requirements.csv").write_text(csv_content.strip(), encoding="utf-8")

    # 2. Save locations.json
    locations_payload = {
        "depot": {
            "name": depot_name.strip(),
            "latitude": float(depot_latitude),
            "longitude": float(depot_longitude),
        },
        "customers": [
            {
                "customer_id": c.customer_id,
                "location_name": c.location_name,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "demand": c.demand,
            }
            for c in customers
        ],
    }
    (s_dir / "locations.json").write_text(
        json.dumps(locations_payload, indent=2), encoding="utf-8"
    )

    total_demand = sum(c.demand for c in customers)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 3. Save scenario.json
    meta_payload = {
        "id": scenario_id,
        "name": name.strip(),
        "depot_name": depot_name.strip(),
        "depot_latitude": float(depot_latitude),
        "depot_longitude": float(depot_longitude),
        "total_customers": len(customers),
        "total_demand": total_demand,
        "created_at": now_iso,
        "status": "ready",
    }

    scen_input = ScenarioInput(
        name=name.strip(),
        depot_name=depot_name.strip(),
        depot_latitude=float(depot_latitude),
        depot_longitude=float(depot_longitude),
        customers=customers,
    )

    if auto_solve:
        try:
            solution = solve_scenario_relief(scen_input)
            meta_payload["status"] = "active"
            (s_dir / "solution.json").write_text(
                json.dumps(solution, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Error solving scenario {scenario_id}: {e}")
            meta_payload["solve_error"] = str(e)

    (s_dir / "scenario.json").write_text(
        json.dumps(meta_payload, indent=2), encoding="utf-8"
    )

    return get_scenario(scenario_id)


def solve_scenario(scenario_id: str) -> dict[str, Any]:
    """Execute or re-execute AI-05 Fair Relief optimization for an existing scenario."""
    s_id = sanitize_scenario_id(scenario_id)
    s_dir = SCENARIOS_DIR / s_id
    if not s_dir.exists() or not (s_dir / "locations.json").exists():
        raise FileNotFoundError(f"Scenario '{scenario_id}' not found.")

    meta = json.loads((s_dir / "scenario.json").read_text(encoding="utf-8"))
    locs = json.loads((s_dir / "locations.json").read_text(encoding="utf-8"))

    depot = locs["depot"]
    customers = [
        CustomerRecord(
            customer_id=c["customer_id"],
            location_name=c["location_name"],
            latitude=c["latitude"],
            longitude=c["longitude"],
            demand=c["demand"],
        )
        for c in locs["customers"]
    ]

    scen_input = ScenarioInput(
        name=meta["name"],
        depot_name=depot["name"],
        depot_latitude=depot["latitude"],
        depot_longitude=depot["longitude"],
        customers=customers,
    )

    solution = solve_scenario_relief(scen_input)
    meta["status"] = "active"
    (s_dir / "scenario.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (s_dir / "solution.json").write_text(json.dumps(solution, indent=2), encoding="utf-8")

    return get_scenario(scenario_id)
