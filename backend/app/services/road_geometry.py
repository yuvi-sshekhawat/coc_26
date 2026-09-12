from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """Format travel duration in seconds to a clean human-readable string."""
    if seconds <= 0:
        return "0 min"
    if seconds < 60:
        return f"{int(round(seconds))}s"
    total_minutes = int(round(seconds / 60))
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours}h {mins:02d}m" if mins > 0 else f"{hours}h"


def haversine_distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great circle distance between two coordinates in kilometers."""
    radius = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def validate_waypoint(name: str, coords: Sequence[float] | None) -> tuple[bool, str | None]:
    """Validate geographic coordinates for a stop/waypoint."""
    if coords is None or len(coords) < 2:
        return False, f"{name} has missing geographic coordinates."
    try:
        lon = float(coords[0])
        lat = float(coords[1])
    except (ValueError, TypeError):
        return False, f"{name} has invalid latitude/longitude."

    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False, f"{name} has NaN or Infinite coordinates."

    if lat < -90.0 or lat > 90.0:
        return False, f"{name} latitude ({lat:.4f}) is out of bounds (-90 to +90)."

    if lon < -180.0 or lon > 180.0:
        return False, f"{name} longitude ({lon:.4f}) is out of bounds (-180 to +180)."

    return True, None


@dataclass
class RouteSegment:
    from_node_id: int
    to_node_id: int
    from_name: str
    to_name: str
    from_coords: list[float]  # [lon, lat]
    to_coords: list[float]    # [lon, lat]
    connected: bool
    status: str              # "CONNECTED" | "ROUTING_FAILED" | "INVALID_COORDS"
    distance_meters: float
    distance_km: float
    duration_seconds: float
    duration_formatted: str
    geometry: list[list[float]]  # GeoJSON LineString coordinates [[lon, lat], ...]
    error_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VehicleRoadRoute:
    vehicle: int
    status: str  # "READY" | "ROUTING_FAILED" | "PARTIALLY_ROUTED"
    road_distance_meters: float
    road_distance_km: float
    road_duration_seconds: float
    road_duration_minutes: float
    road_duration_formatted: str
    full_geometry: list[list[float]]
    segments: list[RouteSegment]
    connected_segments_count: int
    total_segments_count: int
    has_errors: bool
    error_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["segments"] = [s.to_dict() for s in self.segments]
        return res


def fetch_road_distance_matrix(
    coords_list: list[list[float]],
    timeout_s: float = 6.0,
) -> tuple[np.ndarray, np.ndarray, str, list[str]]:
    """
    Fetch the N x N drivable road distance matrix (meters) and duration matrix (seconds)
    using OSRM's table service.
    
    If OSRM is offline or unreachable, falls back to geodesic Haversine distance with
    a standard 1.25x road winding factor.
    """
    n = len(coords_list)
    warnings: list[str] = []

    if n <= 1:
        return np.zeros((n, n)), np.zeros((n, n)), "TRIVIAL", warnings

    # Try OSRM Table API
    try:
        coord_str = ";".join(f"{c[0]:.6f},{c[1]:.6f}" for c in coords_list)
        url = f"https://router.project-osrm.org/table/v1/driving/{coord_str}?annotations=distance,duration"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AI05-FairReliefPlanner/3.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("code") == "Ok":
                    raw_dist = data.get("distances", [])
                    raw_dur = data.get("durations", [])

                    if len(raw_dist) == n and len(raw_dur) == n:
                        dist_mat = np.zeros((n, n), dtype=float)
                        dur_mat = np.zeros((n, n), dtype=float)
                        has_null = False

                        for i in range(n):
                            for j in range(n):
                                if i == j:
                                    continue
                                d_val = raw_dist[i][j]
                                t_val = raw_dur[i][j]
                                if d_val is None or t_val is None:
                                    has_null = True
                                    # Fallback for unreachable point pair
                                    geo_km = haversine_distance_km(
                                        coords_list[i][0], coords_list[i][1],
                                        coords_list[j][0], coords_list[j][1],
                                    )
                                    dist_mat[i, j] = geo_km * 1000.0 * 1.5
                                    dur_mat[i, j] = (geo_km * 1000.0 * 1.5) / 8.33
                                else:
                                    dist_mat[i, j] = float(d_val)
                                    dur_mat[i, j] = float(t_val)

                        if has_null:
                            warnings.append("Some location pairs had unreachable road connections; filled with circuity estimate.")

                        return dist_mat, dur_mat, "OSRM_TABLE_API", warnings
    except Exception as exc:
        warnings.append(f"OSRM Table service unavailable ({exc}); using geodesic road network estimate.")

    # Geodesic fallback with road circuity multiplier (1.25x)
    dist_mat = np.zeros((n, n), dtype=float)
    dur_mat = np.zeros((n, n), dtype=float)
    speed_mps = 8.33  # ~30 km/h urban/disaster average speed

    for i in range(n):
        for j in range(n):
            if i != j:
                geo_km = haversine_distance_km(
                    coords_list[i][0], coords_list[i][1],
                    coords_list[j][0], coords_list[j][1],
                )
                road_meters = geo_km * 1000.0 * 1.25
                dist_mat[i, j] = road_meters
                dur_mat[i, j] = road_meters / speed_mps

    return dist_mat, dur_mat, "GEODESIC_ROAD_ESTIMATE", warnings


def compute_vehicle_road_route(
    vehicle: int,
    node_ids: list[int],
    node_names: list[str],
    coords_list: list[list[float] | None],
    timeout_s: float = 4.0,
) -> VehicleRoadRoute:
    """
    Compute verified road geometry, distance, and duration for a single vehicle route.
    Validates every segment; failed responses are marked as failed (never faked).
    """
    total_segments = max(0, len(node_ids) - 1)
    if total_segments == 0:
        return VehicleRoadRoute(
            vehicle=vehicle,
            status="READY",
            road_distance_meters=0.0,
            road_distance_km=0.0,
            road_duration_seconds=0.0,
            road_duration_minutes=0.0,
            road_duration_formatted="0 min",
            full_geometry=[],
            segments=[],
            connected_segments_count=0,
            total_segments_count=0,
            has_errors=False,
        )

    # Validate all waypoints upfront
    waypoint_validities: list[tuple[bool, str | None]] = []
    for nid, name, coords in zip(node_ids, node_names, coords_list):
        is_val, err = validate_waypoint(name, coords)
        waypoint_validities.append((is_val, err))

    all_valid = all(v[0] for v in waypoint_validities)
    osrm_data: dict[str, Any] | None = None

    if all_valid and len(coords_list) >= 2:
        try:
            valid_coords = [c for c in coords_list if c is not None]
            coord_str = ";".join(f"{c[0]:.6f},{c[1]:.6f}" for c in valid_coords)
            url = (
                f"https://router.project-osrm.org/route/v1/driving/{coord_str}"
                f"?overview=full&geometries=geojson&steps=true"
            )
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AI05-FairReliefPlanner/3.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                if response.status == 200:
                    parsed = json.loads(response.read().decode("utf-8"))
                    if parsed.get("code") == "Ok" and parsed.get("routes"):
                        osrm_data = parsed
        except Exception as exc:
            logger.debug(f"Multi-stop OSRM query failed ({exc}); falling back to segment-by-segment check.")

    segments: list[RouteSegment] = []
    full_geometry: list[list[float]] = []
    total_meters = 0.0
    total_seconds = 0.0
    failed_count = 0
    errors_list: list[str] = []

    osrm_legs = osrm_data["routes"][0].get("legs", []) if osrm_data else []
    osrm_full_coords = (
        osrm_data["routes"][0].get("geometry", {}).get("coordinates", [])
        if osrm_data
        else []
    )

    if osrm_data and len(osrm_legs) == total_segments:
        # Full multi-leg routing succeeded cleanly
        for i in range(total_segments):
            from_nid = node_ids[i]
            to_nid = node_ids[i + 1]
            from_nm = node_names[i]
            to_nm = node_names[i + 1]
            from_c = coords_list[i] or [0.0, 0.0]
            to_c = coords_list[i + 1] or [0.0, 0.0]
            leg = osrm_legs[i]

            leg_dist = float(leg.get("distance", 0.0))
            leg_dur = float(leg.get("duration", 0.0))
            total_meters += leg_dist
            total_seconds += leg_dur

            leg_coords: list[list[float]] = []
            for step in leg.get("steps", []):
                step_coords = step.get("geometry", {}).get("coordinates", [])
                if step_coords:
                    if not leg_coords:
                        leg_coords.extend(step_coords)
                    else:
                        leg_coords.extend(step_coords[1:] if len(step_coords) > 1 else step_coords)

            if not leg_coords:
                leg_coords = [from_c, to_c]

            seg = RouteSegment(
                from_node_id=from_nid,
                to_node_id=to_nid,
                from_name=from_nm,
                to_name=to_nm,
                from_coords=from_c,
                to_coords=to_c,
                connected=True,
                status="CONNECTED",
                distance_meters=leg_dist,
                distance_km=round(leg_dist / 1000.0, 2),
                duration_seconds=leg_dur,
                duration_formatted=format_duration(leg_dur),
                geometry=leg_coords,
                error_reason=None,
            )
            segments.append(seg)

        full_geometry = (
            osrm_full_coords
            if osrm_full_coords
            else [list(c) for c in coords_list if c is not None]
        )
    else:
        # Segment-by-segment verification
        for i in range(total_segments):
            from_nid = node_ids[i]
            to_nid = node_ids[i + 1]
            from_nm = node_names[i]
            to_nm = node_names[i + 1]
            from_c = coords_list[i]
            to_c = coords_list[i + 1]

            from_valid, from_err = waypoint_validities[i]
            to_valid, to_err = waypoint_validities[i + 1]

            if not from_valid or not to_valid:
                failed_count += 1
                err = from_err or to_err or "Invalid coordinates"
                errors_list.append(err)
                segments.append(
                    RouteSegment(
                        from_node_id=from_nid,
                        to_node_id=to_nid,
                        from_name=from_nm,
                        to_name=to_nm,
                        from_coords=from_c or [0.0, 0.0],
                        to_coords=to_c or [0.0, 0.0],
                        connected=False,
                        status="INVALID_COORDS",
                        distance_meters=0.0,
                        distance_km=0.0,
                        duration_seconds=0.0,
                        duration_formatted="N/A",
                        geometry=[],
                        error_reason=err,
                    )
                )
                continue

            # Query single segment from OSRM
            single_osrm = _fetch_single_segment_osrm(from_c, to_c, timeout_s=2.5)  # type: ignore[arg-type]
            if single_osrm and single_osrm.get("connected"):
                seg_dist = single_osrm["distance_meters"]
                seg_dur = single_osrm["duration_seconds"]
                seg_geom = single_osrm["geometry"]
                total_meters += seg_dist
                total_seconds += seg_dur

                seg = RouteSegment(
                    from_node_id=from_nid,
                    to_node_id=to_nid,
                    from_name=from_nm,
                    to_name=to_nm,
                    from_coords=from_c,  # type: ignore[arg-type]
                    to_coords=to_c,      # type: ignore[arg-type]
                    connected=True,
                    status="CONNECTED",
                    distance_meters=seg_dist,
                    distance_km=round(seg_dist / 1000.0, 2),
                    duration_seconds=seg_dur,
                    duration_formatted=format_duration(seg_dur),
                    geometry=seg_geom,
                    error_reason=None,
                )
                segments.append(seg)
                if not full_geometry:
                    full_geometry.extend(seg_geom)
                else:
                    full_geometry.extend(seg_geom[1:] if len(seg_geom) > 1 else seg_geom)
            else:
                failed_count += 1
                reason = (
                    single_osrm.get("error_reason")
                    if single_osrm
                    else f"Could not find a drivable road between {from_nm} and {to_nm}."
                )
                errors_list.append(reason)
                # NEVER draw fake straight lines
                segments.append(
                    RouteSegment(
                        from_node_id=from_nid,
                        to_node_id=to_nid,
                        from_name=from_nm,
                        to_name=to_nm,
                        from_coords=from_c,  # type: ignore[arg-type]
                        to_coords=to_c,      # type: ignore[arg-type]
                        connected=False,
                        status="ROUTING_FAILED",
                        distance_meters=0.0,
                        distance_km=0.0,
                        duration_seconds=0.0,
                        duration_formatted="N/A",
                        geometry=[],
                        error_reason=reason,
                    )
                )

    has_errors = failed_count > 0
    if failed_count == 0:
        status = "READY"
    elif failed_count < total_segments:
        status = "PARTIALLY_ROUTED"
    else:
        status = "ROUTING_FAILED"

    error_summary = "; ".join(errors_list[:3]) if errors_list else None

    return VehicleRoadRoute(
        vehicle=vehicle,
        status=status,
        road_distance_meters=round(total_meters, 1),
        road_distance_km=round(total_meters / 1000.0, 1),
        road_duration_seconds=round(total_seconds, 1),
        road_duration_minutes=round(total_seconds / 60.0, 1),
        road_duration_formatted=format_duration(total_seconds),
        full_geometry=full_geometry,
        segments=segments,
        connected_segments_count=total_segments - failed_count,
        total_segments_count=total_segments,
        has_errors=has_errors,
        error_summary=error_summary,
    )


def _fetch_single_segment_osrm(
    from_c: list[float],
    to_c: list[float],
    timeout_s: float = 2.5,
) -> dict[str, Any] | None:
    try:
        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{from_c[0]:.6f},{from_c[1]:.6f};{to_c[0]:.6f},{to_c[1]:.6f}"
            f"?overview=full&geometries=geojson"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AI05-FairReliefPlanner/3.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("code") == "Ok" and data.get("routes"):
                    r = data["routes"][0]
                    return {
                        "connected": True,
                        "distance_meters": float(r.get("distance", 0.0)),
                        "duration_seconds": float(r.get("duration", 0.0)),
                        "geometry": r.get("geometry", {}).get("coordinates", [from_c, to_c]),
                    }
                else:
                    return {
                        "connected": False,
                        "error_reason": data.get("message", "No drivable road route found."),
                    }
    except Exception as exc:
        return {
            "connected": False,
            "error_reason": f"Routing query failed: {exc}",
        }
    return None
