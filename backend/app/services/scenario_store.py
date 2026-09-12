from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scenario_adapter import (
    HouseRecord,
    LocationPoint,
    ScenarioInput,
    sanitize_scenario_id,
    solve_scenario_relief,
    validate_house_records,
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
        "destination_name": "Jaipur SMS Medical Center",
        "destination_latitude": 26.8920,
        "destination_longitude": 75.8150,
        "houses": [
            {"house_id": 1, "location_name": "Mansarovar Relief Center", "latitude": 26.8500, "longitude": 75.7600, "demand": 45},
            {"house_id": 2, "location_name": "Vaishali Nagar Community Shelter", "latitude": 26.9050, "longitude": 75.7420, "demand": 35},
            {"house_id": 3, "location_name": "Malviya Nagar Camp", "latitude": 26.8540, "longitude": 75.8150, "demand": 50},
            {"house_id": 4, "location_name": "C-Scheme Emergency Hub", "latitude": 26.9100, "longitude": 75.8020, "demand": 30},
            {"house_id": 5, "location_name": "Amer Relief Point", "latitude": 26.9850, "longitude": 75.8500, "demand": 60},
            {"house_id": 6, "location_name": "Sanganer Distribution Post", "latitude": 26.8150, "longitude": 75.7700, "demand": 40},
            {"house_id": 7, "location_name": "Vidyadhar Nagar Shelter", "latitude": 26.9600, "longitude": 75.7800, "demand": 35},
            {"house_id": 8, "location_name": "Jagatpura Relief Camp", "latitude": 26.8200, "longitude": 75.8450, "demand": 55},
            {"house_id": 9, "location_name": "Jhotwara Logistics Center", "latitude": 26.9400, "longitude": 75.7200, "demand": 40},
            {"house_id": 10, "location_name": "Raja Park Supply Point", "latitude": 26.8920, "longitude": 75.8280, "demand": 25},
            {"house_id": 11, "location_name": "Sitapura Medical Post", "latitude": 26.7750, "longitude": 75.8350, "demand": 45},
            {"house_id": 12, "location_name": "Ajmer Road Transit Camp", "latitude": 26.8800, "longitude": 75.6900, "demand": 35},
        ],
    },
    {
        "name": "Delhi Emergency Relief",
        "depot_name": "Delhi Central Warehouse",
        "depot_latitude": 28.6139,
        "depot_longitude": 77.2090,
        "destination_name": "AIIMS Emergency Staging Terminal",
        "destination_latitude": 28.5672,
        "destination_longitude": 77.2100,
        "houses": [
            {"house_id": 1, "location_name": "Rohini Emergency Hub", "latitude": 28.7150, "longitude": 77.1150, "demand": 50},
            {"house_id": 2, "location_name": "Dwarka Sector 10 Shelter", "latitude": 28.5820, "longitude": 77.0500, "demand": 45},
            {"house_id": 3, "location_name": "Saket Community Center", "latitude": 28.5240, "longitude": 77.2100, "demand": 40},
            {"house_id": 4, "location_name": "Mayur Vihar Relief Post", "latitude": 28.6050, "longitude": 77.3000, "demand": 35},
            {"house_id": 5, "location_name": "Karol Bagh Depot Annex", "latitude": 28.6500, "longitude": 77.1900, "demand": 30},
            {"house_id": 6, "location_name": "Shahdara Supply Center", "latitude": 28.6700, "longitude": 77.2900, "demand": 55},
            {"house_id": 7, "location_name": "Janakpuri Crisis Post", "latitude": 28.6250, "longitude": 77.0850, "demand": 40},
            {"house_id": 8, "location_name": "Okhla Industrial Relief", "latitude": 28.5350, "longitude": 77.2750, "demand": 45},
            {"house_id": 9, "location_name": "Civil Lines Shelter", "latitude": 28.6800, "longitude": 77.2200, "demand": 30},
            {"house_id": 10, "location_name": "Lajpat Nagar Hub", "latitude": 28.5700, "longitude": 77.2400, "demand": 35},
        ],
    },
    {
        "name": "Mumbai Cyclone Relief",
        "depot_name": "Mumbai Harbor Relief Terminal",
        "depot_latitude": 18.9400,
        "depot_longitude": 72.8400,
        "destination_name": "KEM Emergency Disaster Facility",
        "destination_latitude": 19.0020,
        "destination_longitude": 72.8420,
        "houses": [
            {"house_id": 1, "location_name": "Colaba Coastal Center", "latitude": 18.9100, "longitude": 72.8250, "demand": 40},
            {"house_id": 2, "location_name": "Dadar Transit Camp", "latitude": 19.0200, "longitude": 72.8450, "demand": 50},
            {"house_id": 3, "location_name": "Bandra West Relief Point", "latitude": 19.0550, "longitude": 72.8300, "demand": 45},
            {"house_id": 4, "location_name": "Kurla Crisis Warehouse", "latitude": 19.0700, "longitude": 72.8800, "demand": 60},
            {"house_id": 5, "location_name": "Andheri Emergency Shelter", "latitude": 19.1200, "longitude": 72.8400, "demand": 55},
            {"house_id": 6, "location_name": "Worli Evacuation Hub", "latitude": 19.0050, "longitude": 72.8150, "demand": 35},
            {"house_id": 7, "location_name": "Chembur Distribution Base", "latitude": 19.0600, "longitude": 72.9000, "demand": 40},
            {"house_id": 8, "location_name": "Ghatkopar Relief Center", "latitude": 19.0850, "longitude": 72.9100, "demand": 45},
        ],
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
                    destination_name=s_def.get("destination_name"),
                    destination_latitude=s_def.get("destination_latitude"),
                    destination_longitude=s_def.get("destination_longitude"),
                    houses=s_def["houses"],
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
        "id": meta.get("id", s_id),
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
    houses: list[dict[str, Any] | HouseRecord],
    destination_name: str | None = None,
    destination_latitude: float | None = None,
    destination_longitude: float | None = None,
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

    # Validate destination if provided
    dest_point: LocationPoint | None = None
    if destination_name and destination_name.strip() and destination_latitude is not None and destination_longitude is not None:
        if not (-90.0 <= destination_latitude <= 90.0):
            raise ValueError(f"Destination latitude {destination_latitude} is invalid (-90.0 to 90.0).")
        if not (-180.0 <= destination_longitude <= 180.0):
            raise ValueError(f"Destination longitude {destination_longitude} is invalid (-180.0 to 180.0).")
        dest_point = LocationPoint(
            name=destination_name.strip(),
            latitude=float(destination_latitude),
            longitude=float(destination_longitude),
        )

    # Convert raw house dicts to HouseRecord objects
    house_records: list[HouseRecord] = []
    for idx, h in enumerate(houses, start=1):
        if isinstance(h, HouseRecord):
            house_records.append(h)
        else:
            hid = int(h.get("house_id") or h.get("customer_id") or idx)
            hname = str(h.get("location_name") or f"House #{hid}").strip()
            hlat = float(h["latitude"])
            hlon = float(h["longitude"])
            hdem = int(h.get("demand") or 10)
            house_records.append(
                HouseRecord(
                    house_id=hid,
                    location_name=hname,
                    latitude=hlat,
                    longitude=hlon,
                    demand=hdem,
                )
            )

    validate_house_records(house_records)
    scenario_id = sanitize_scenario_id(name)

    s_dir = SCENARIOS_DIR / scenario_id
    s_dir.mkdir(parents=True, exist_ok=True)

    # Save locations.json (No CSV dependencies!)
    locations_payload = {
        "depot": {
            "name": depot_name.strip(),
            "latitude": float(depot_latitude),
            "longitude": float(depot_longitude),
        },
        "destination": {
            "name": dest_point.name,
            "latitude": dest_point.latitude,
            "longitude": dest_point.longitude,
        } if dest_point else None,
        "houses": [
            {
                "house_id": h.house_id,
                "location_name": h.location_name,
                "latitude": h.latitude,
                "longitude": h.longitude,
                "demand": h.demand,
            }
            for h in house_records
        ],
    }
    (s_dir / "locations.json").write_text(
        json.dumps(locations_payload, indent=2), encoding="utf-8"
    )

    total_demand = sum(h.demand for h in house_records)
    now_iso = datetime.now(timezone.utc).isoformat()

    meta_payload = {
        "id": scenario_id,
        "name": name.strip(),
        "depot_name": depot_name.strip(),
        "depot_latitude": float(depot_latitude),
        "depot_longitude": float(depot_longitude),
        "destination_name": dest_point.name if dest_point else None,
        "destination_latitude": dest_point.latitude if dest_point else None,
        "destination_longitude": dest_point.longitude if dest_point else None,
        "total_houses": len(house_records),
        "total_customers": len(house_records),
        "total_demand": total_demand,
        "created_at": now_iso,
        "status": "ready",
    }

    scen_input = ScenarioInput(
        name=name.strip(),
        depot=LocationPoint(
            name=depot_name.strip(),
            latitude=float(depot_latitude),
            longitude=float(depot_longitude),
        ),
        destination=dest_point,
        houses=house_records,
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
    dest = locs.get("destination")
    houses_raw = locs.get("houses") or locs.get("customers", [])

    dest_point = None
    if dest and dest.get("name") and dest.get("latitude") is not None and dest.get("longitude") is not None:
        dest_point = LocationPoint(
            name=dest["name"],
            latitude=float(dest["latitude"]),
            longitude=float(dest["longitude"]),
        )

    house_records = [
        HouseRecord(
            house_id=h.get("house_id") or h.get("customer_id") or idx,
            location_name=h.get("location_name") or f"House #{idx}",
            latitude=float(h["latitude"]),
            longitude=float(h["longitude"]),
            demand=int(h.get("demand") or 10),
        )
        for idx, h in enumerate(houses_raw, start=1)
    ]

    scen_input = ScenarioInput(
        name=meta["name"],
        depot=LocationPoint(
            name=depot["name"],
            latitude=float(depot["latitude"]),
            longitude=float(depot["longitude"]),
        ),
        destination=dest_point,
        houses=house_records,
    )

    solution = solve_scenario_relief(scen_input)
    meta["status"] = "active"
    (s_dir / "scenario.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (s_dir / "solution.json").write_text(json.dumps(solution, indent=2), encoding="utf-8")

    return get_scenario(scenario_id)
