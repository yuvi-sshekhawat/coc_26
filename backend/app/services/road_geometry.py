from __future__ import annotations

import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Sequence

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """
    Format travel duration in seconds to a clean human-readable string.
    e.g. 58s, 14 min, 1h 14m, 3h 45m.
    """
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
    """
    Calculate the great circle distance between two points on the earth (in kilometers).
    """
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
    """
    Validate geographic coordinates for a stop/waypoint.
    Returns (is_valid, error_reason).
    """
    if coords is None or len(coords) < 2:
        return False, f"{name} has no geographic coordinates."
    try:
        lon = float(coords[0])
        lat = float(coords[1])
    except (ValueError, TypeError):
        return False, f"{name} has invalid latitude/longitude."

    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False, f"{name} has invalid latitude/longitude."

    if lat < -90.0 or lat > 90.0:
        return False, f"{name} latitude ({lat:.4f}) is outside the valid range (-90 to +90)."

    if lon < -180.0 or lon > 180.0:
        return False, f"{name} longitude ({lon:.4f}) is outside the valid range (-180 to +180)."

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
    status: str              # "CONNECTED" | "FAILED" | "INVALID_COORDS"
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


def compute_vehicle_road_route(
    vehicle: int,
    node_ids: list[int],
    node_names: list[str],
    coords_list: list[list[float] | None],
    timeout_s: float = 4.0,
) -> VehicleRoadRoute:
    """
    Compute real road geometry, distance, and duration for a single vehicle route.
    Validates every segment and detects disconnected points with exact root-cause reasons.
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
    for idx, (nid, name, coords) in enumerate(zip(node_ids, node_names, coords_list)):
        is_val, err = validate_waypoint(name, coords)
        waypoint_validities.append((is_val, err))

    # Try multi-waypoint OSRM query if all waypoints are valid
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
                headers={"User-Agent": "AI05-FairReliefPlanner/2.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                if response.status == 200:
                    parsed = json.loads(response.read().decode("utf-8"))
                    if parsed.get("code") == "Ok" and parsed.get("routes"):
                        osrm_data = parsed
        except urllib.error.HTTPError as http_err:
            try:
                err_body = json.loads(http_err.read().decode("utf-8"))
                logger.debug(f"OSRM HTTP error: {err_body}")
            except Exception:
                pass
        except Exception as exc:
            logger.debug(f"OSRM route fetch failed: {exc}")

    segments: list[RouteSegment] = []
    full_geometry: list[list[float]] = []
    total_meters = 0.0
    total_seconds = 0.0
    failed_count = 0
    errors_list: list[str] = []

    # If OSRM multi-waypoint returned valid legs matching segment count
    osrm_legs = osrm_data["routes"][0].get("legs", []) if osrm_data else []
    osrm_full_coords = (
        osrm_data["routes"][0].get("geometry", {}).get("coordinates", [])
        if osrm_data
        else []
    )

    if osrm_data and len(osrm_legs) == total_segments:
        # Full multi-leg routing succeeded
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

            # Extract step geometry for this segment
            leg_coords: list[list[float]] = []
            for step in leg.get("steps", []):
                step_coords = step.get("geometry", {}).get("coordinates", [])
                if step_coords:
                    if not leg_coords:
                        leg_coords.extend(step_coords)
                    else:
                        leg_coords.extend(
                            step_coords[1:] if len(step_coords) > 1 else step_coords
                        )

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
        # Step segment by segment to diagnose any breaks accurately
        for i in range(total_segments):
            from_nid = node_ids[i]
            to_nid = node_ids[i + 1]
            from_nm = node_names[i]
            to_nm = node_names[i + 1]
            from_c = coords_list[i]
            to_c = coords_list[i + 1]

            from_valid, from_err = waypoint_validities[i]
            to_valid, to_err = waypoint_validities[i + 1]

            if not from_valid:
                failed_count += 1
                errors_list.append(from_err or "Invalid coordinates")
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
                        error_reason=from_err,
                    )
                )
                continue

            if not to_valid:
                failed_count += 1
                errors_list.append(to_err or "Invalid coordinates")
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
                        error_reason=to_err,
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
                # DO NOT draw fake straight line connection!
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
            headers={"User-Agent": "AI05-FairReliefPlanner/2.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("code") == "Ok" and data.get("routes"):
                    r = data["routes"][0]
                    coords = r.get("geometry", {}).get("coordinates", [])
                    return {
                        "connected": True,
                        "distance_meters": float(r.get("distance", 0.0)),
                        "duration_seconds": float(r.get("duration", 0.0)),
                        "geometry": [[float(p[0]), float(p[1])] for p in coords],
                    }
                elif data.get("code") == "NoRoute":
                    return {
                        "connected": False,
                        "error_reason": "Could not find a drivable road between these locations.",
                    }
    except urllib.error.HTTPError as http_err:
        try:
            body = json.loads(http_err.read().decode("utf-8"))
            code = body.get("code")
            msg = body.get("message", "")
            if code == "NoRoute" or code == "NoSegment":
                return {
                    "connected": False,
                    "error_reason": "Could not find a drivable road between these locations.",
                }
            return {
                "connected": False,
                "error_reason": f"Routing API failure: {msg or code}",
            }
        except Exception:
            return {
                "connected": False,
                "error_reason": f"Routing API HTTP error ({http_err.code}).",
            }
    except Exception as exc:
        return {
            "connected": False,
            "error_reason": f"Road-routing service failed ({exc}).",
        }

    return None


def get_road_geometry_for_route(
    coordinates: Sequence[Sequence[float]],
    timeout_s: float = 3.0,
    chunk_size: int = 25,
) -> list[list[float]]:
    """
    Backward-compatible helper function for obtaining road geometry coordinates.
    """
    if not coordinates or len(coordinates) < 2:
        return [list(c) for c in coordinates]

    names = [f"Stop #{i}" for i in range(len(coordinates))]
    coords_list = [list(c) for c in coordinates]
    res = compute_vehicle_road_route(
        vehicle=1,
        node_ids=list(range(len(coordinates))),
        node_names=names,
        coords_list=coords_list,  # type: ignore[arg-type]
        timeout_s=timeout_s,
    )
    return res.full_geometry if res.full_geometry else coords_list
