/**
 * routeSimulation.js
 * 
 * High-performance, route-driven vehicle simulation engine for MapLibre GL.
 * Interpolates vehicle positions along verified physical road geometry based on
 * cumulative distance, rather than naive coordinate array indexing.
 * 
 * Features:
 *  - Continuous distance-parameterized polyline interpolation
 *  - Accurate vehicle bearing / heading calculation
 *  - Simultaneous multi-vehicle fleet execution
 *  - Individual vehicle completion & mandatory return-to-depot behavior
 *  - Discrete stop events (houses marked visited when reached)
 *  - Traveled sub-polyline generation for live glow trails
 */

/**
 * Calculate Great-Circle distance between two coordinates in meters.
 */
export function haversineDistanceMeters(lon1, lat1, lon2, lat2) {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Calculate initial compass bearing from Point A to Point B in degrees [0, 360).
 */
export function calculateBearing(lon1, lat1, lon2, lat2) {
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos((lat2 * Math.PI) / 180);
  const x =
    Math.cos((lat1 * Math.PI) / 180) * Math.sin((lat2 * Math.PI) / 180) -
    Math.sin((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.cos(dLon);
  const brng = (Math.atan2(y, x) * 180) / Math.PI;
  return (brng + 360) % 360;
}

/**
 * Clean an array of coordinates: removes duplicates, NaNs, and zero-length sub-segments.
 */
export function cleanCoordinates(coords) {
  if (!Array.isArray(coords) || coords.length === 0) return [];
  const cleaned = [];

  for (let i = 0; i < coords.length; i++) {
    const pt = coords[i];
    if (!pt || !Array.isArray(pt) || pt.length < 2) continue;
    const lon = Number(pt[0]);
    const lat = Number(pt[1]);
    if (isNaN(lon) || isNaN(lat) || !isFinite(lon) || !isFinite(lat)) continue;

    if (cleaned.length > 0) {
      const prev = cleaned[cleaned.length - 1];
      const dx = lon - prev[0];
      const dy = lat - prev[1];
      // Skip duplicate coordinates within ~0.1 meter
      if (dx * dx + dy * dy < 1e-12) continue;
    }
    cleaned.push([lon, lat]);
  }

  return cleaned;
}

/**
 * Prepare physical simulation model for a single vehicle route.
 */
export function prepareVehicleRoute(route, depotCoords, destCoords) {
  const vId = route.vehicle;
  const nodes = route.nodes || [];
  const names = route.location_names || [];

  // 1. Establish full continuous physical polyline
  let rawGeom = route.road_geometry;
  if (!rawGeom || !Array.isArray(rawGeom) || rawGeom.length < 2) {
    // Fall back to segment geometries chained together
    if (route.segments && route.segments.length > 0) {
      const chained = [];
      route.segments.forEach((s) => {
        if (s.geometry && s.geometry.length > 0) {
          if (chained.length === 0) {
            chained.push(...s.geometry);
          } else {
            chained.push(...s.geometry.slice(1));
          }
        }
      });
      rawGeom = chained.length >= 2 ? chained : route.ordered_coords;
    } else {
      rawGeom = route.ordered_coords;
    }
  }

  let fullPath = cleanCoordinates(rawGeom);

  // If path is trivial or empty, ensure at least depot to depot
  if (fullPath.length < 2 && depotCoords) {
    fullPath = [
      [depotCoords[0], depotCoords[1]],
      [depotCoords[0] + 0.00001, depotCoords[1] + 0.00001],
      [depotCoords[0], depotCoords[1]],
    ];
  }

  const N = fullPath.length;

  // 2. Compute cumulative distance array along the physical road
  const cumDist = new Float64Array(N);
  cumDist[0] = 0.0;
  for (let i = 1; i < N; i++) {
    const pPrev = fullPath[i - 1];
    const pCurr = fullPath[i];
    const d = haversineDistanceMeters(pPrev[0], pPrev[1], pCurr[0], pCurr[1]);
    cumDist[i] = cumDist[i - 1] + (d > 0.05 ? d : 0.05); // Enforce strictly increasing
  }
  const totalDistance = cumDist[N - 1];

  // 3. Map each ordered stop to an exact distance along the polyline
  const stops = [];
  const orderedCoords = route.ordered_coords || [];

  let lastDistance = 0.0;

  for (let idx = 0; idx < nodes.length; idx++) {
    const nid = nodes[idx];
    const name = names[idx] || (nid === 0 ? "Depot" : nid === -1 ? "Destination" : `House #${nid}`);
    const isDepot = nid === 0;
    const isDestination = nid === -1;
    const isFirst = idx === 0;
    const isLast = idx === nodes.length - 1;

    let stopDist = 0.0;
    let stopCoords = orderedCoords[idx] || (isDepot ? depotCoords : isDestination ? destCoords : null);

    if (isFirst) {
      stopDist = 0.0;
      if (!stopCoords && fullPath.length > 0) stopCoords = fullPath[0];
    } else if (isLast) {
      stopDist = totalDistance;
      if (!stopCoords && fullPath.length > 0) stopCoords = fullPath[N - 1];
    } else if (stopCoords && Array.isArray(stopCoords) && stopCoords.length >= 2) {
      // Find closest vertex in fullPath that occurs AT OR AFTER lastDistance
      let bestDist = Infinity;
      let bestVertexDist = lastDistance;

      for (let vi = 0; vi < N; vi++) {
        if (cumDist[vi] < lastDistance - 1.0) continue;
        const pt = fullPath[vi];
        const dx = pt[0] - stopCoords[0];
        const dy = pt[1] - stopCoords[1];
        const dSq = dx * dx + dy * dy;
        if (dSq < bestDist) {
          bestDist = dSq;
          bestVertexDist = cumDist[vi];
        }
      }

      stopDist = Math.max(lastDistance, bestVertexDist);
    } else {
      // Proportional fallback
      stopDist = Math.min(totalDistance, lastDistance + (totalDistance / Math.max(1, nodes.length - 1)));
    }

    lastDistance = stopDist;

    stops.push({
      index: idx,
      nodeId: nid,
      name,
      coords: stopCoords || [0, 0],
      distance: stopDist,
      fraction: totalDistance > 0 ? stopDist / totalDistance : 0.0,
      isDepot,
      isDestination,
    });
  }

  // Helper: Find polyline segment for given distance
  function getSegmentForDistance(d) {
    if (d <= 0.0) return 0;
    if (d >= totalDistance) return N - 2;

    // Binary search on sorted cumDist
    let low = 0;
    let high = N - 2;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (cumDist[mid + 1] < d) {
        low = mid + 1;
      } else if (cumDist[mid] > d) {
        high = mid - 1;
      } else {
        return mid;
      }
    }
    return Math.max(0, Math.min(N - 2, low));
  }

  return {
    vehicle: vId,
    load: route.load || 0,
    capacity: route.capacity || 100,
    fullPath,
    cumDist,
    totalDistance,
    roadDistanceKm: route.road_distance_km || totalDistance / 1000,
    roadDurationFormatted: route.road_duration_formatted || "15 min",
    stops,
    assignedHouses: route.assigned_houses || [],

    /**
     * Get position, bearing, and segment index at physical distance d (meters).
     */
    getPositionAtDistance(d) {
      if (N < 2) {
        return {
          lngLat: fullPath[0] || [0, 0],
          bearing: 0,
          segmentIdx: 0,
          fraction: 1.0,
          isCompleted: true,
        };
      }

      if (d <= 0.0) {
        const p0 = fullPath[0];
        const p1 = fullPath[1];
        return {
          lngLat: [p0[0], p0[1]],
          bearing: calculateBearing(p0[0], p0[1], p1[0], p1[1]),
          segmentIdx: 0,
          fraction: 0.0,
          isCompleted: false,
        };
      }

      if (d >= totalDistance) {
        const pLast = fullPath[N - 1];
        const pPrev = fullPath[N - 2];
        return {
          lngLat: [pLast[0], pLast[1]],
          bearing: calculateBearing(pPrev[0], pPrev[1], pLast[0], pLast[1]),
          segmentIdx: N - 2,
          fraction: 1.0,
          isCompleted: true,
        };
      }

      const segIdx = getSegmentForDistance(d);
      const pA = fullPath[segIdx];
      const pB = fullPath[segIdx + 1];
      const distA = cumDist[segIdx];
      const distB = cumDist[segIdx + 1];
      const segLen = distB - distA;

      const alpha = segLen > 0 ? (d - distA) / segLen : 0.0;
      const currLon = pA[0] + alpha * (pB[0] - pA[0]);
      const currLat = pA[1] + alpha * (pB[1] - pA[1]);
      const bearing = calculateBearing(pA[0], pA[1], pB[0], pB[1]);

      return {
        lngLat: [currLon, currLat],
        bearing,
        segmentIdx: segIdx,
        fraction: d / totalDistance,
        isCompleted: false,
      };
    },

    /**
     * Get the sub-polyline array of coordinates already traveled up to distance d.
     */
    getTraveledGeometry(d) {
      if (d <= 0.0 || N < 2) return [fullPath[0]];
      if (d >= totalDistance) return fullPath;

      const segIdx = getSegmentForDistance(d);
      const result = [];
      for (let i = 0; i <= segIdx; i++) {
        result.push(fullPath[i]);
      }

      // Add current interpolated head
      const head = this.getPositionAtDistance(d);
      result.push(head.lngLat);
      return result;
    },

    /**
     * Get stop progression status for this vehicle at distance d.
     */
    getStatusAtDistance(d) {
      const isCompleted = d >= totalDistance - 0.5;
      const isDeparting = d <= 0.5;

      const visitedStopNodeIds = new Set();
      let currentStop = stops[0];
      let nextStop = stops[Math.min(stops.length - 1, 1)];

      for (let sIdx = 0; sIdx < stops.length; sIdx++) {
        const s = stops[sIdx];
        if (d >= s.distance - 2.0) {
          visitedStopNodeIds.add(s.nodeId);
          currentStop = s;
          if (sIdx + 1 < stops.length) {
            nextStop = stops[sIdx + 1];
          }
        }
      }

      let stateText = "EN ROUTE";
      if (isCompleted) {
        stateText = "COMPLETE";
      } else if (isDeparting) {
        stateText = "AT DEPOT";
      } else if (nextStop && nextStop.isDepot) {
        stateText = "RETURNING TO DEPOT";
      } else if (nextStop && nextStop.isDestination) {
        stateText = "HEADING TO TARGET";
      } else if (nextStop) {
        stateText = `APPROACHING ${nextStop.name}`;
      }

      const distRemainingToNext = nextStop ? Math.max(0, nextStop.distance - d) : 0;

      return {
        isCompleted,
        isDeparting,
        stateText,
        currentStop,
        nextStop,
        distRemainingToNextMeters: Math.round(distRemainingToNext),
        visitedStopNodeIds,
        visitedCount: visitedStopNodeIds.size,
        totalStops: stops.length,
      };
    },
  };
}

/**
 * High-level Fleet Simulation Engine coordinating all vehicle routes.
 */
export class FleetSimulationEngine {
  constructor(routes, depotCoords, destCoords, baseDurationSeconds = 24.0) {
    this.routes = routes || [];
    this.depotCoords = depotCoords;
    this.destCoords = destCoords;
    this.baseDurationSeconds = baseDurationSeconds;

    // Build vehicle models
    this.vehicleSims = this.routes.map((r) =>
      prepareVehicleRoute(r, depotCoords, destCoords)
    );

    // Fleet distance bounds
    const distances = this.vehicleSims.map((v) => v.totalDistance);
    this.maxFleetDistance = distances.length > 0 ? Math.max(...distances) : 1000.0;
    if (this.maxFleetDistance <= 0) this.maxFleetDistance = 1000.0;

    // Nominal physical dispatch speed in meters per second
    this.nominalSpeedMps = this.maxFleetDistance / this.baseDurationSeconds;
  }

  /**
   * Evaluate entire fleet state at given elapsed simulation time t (seconds).
   */
  evaluateAtTime(tSeconds) {
    const elapsed = Math.max(0, tSeconds);
    const globalFraction = Math.min(1.0, elapsed / this.baseDurationSeconds);
    const globalPercent = Math.round(globalFraction * 100);

    const vehicleStates = [];
    const allVisitedNodeIds = new Set();
    let allCompleted = true;

    for (let i = 0; i < this.vehicleSims.length; i++) {
      const vSim = this.vehicleSims[i];
      // Physical distance traveled by this vehicle
      const distTraveled = Math.min(vSim.totalDistance, elapsed * this.nominalSpeedMps);

      const pos = vSim.getPositionAtDistance(distTraveled);
      const status = vSim.getStatusAtDistance(distTraveled);

      if (!pos.isCompleted) {
        allCompleted = false;
      }

      // Collect visited houses
      status.visitedStopNodeIds.forEach((nid) => {
        if (nid > 0) allVisitedNodeIds.add(nid);
      });

      vehicleStates.push({
        vehicle: vSim.vehicle,
        load: vSim.load,
        capacity: vSim.capacity,
        totalDistance: vSim.totalDistance,
        roadDistanceKm: vSim.roadDistanceKm,
        distTraveled,
        position: pos.lngLat,
        bearing: pos.bearing,
        isCompleted: pos.isCompleted,
        progressFraction: pos.fraction,
        status,
        stops: vSim.stops,
        assignedHouses: vSim.assignedHouses,
      });
    }

    return {
      elapsedSeconds: elapsed,
      totalDurationSeconds: this.baseDurationSeconds,
      globalPercent,
      isAllCompleted: allCompleted,
      vehicleStates,
      visitedHouseIds: allVisitedNodeIds,
      totalHouses: Array.from(allVisitedNodeIds).length,
    };
  }

  /**
   * Evaluate entire fleet state from percentage progress (0 to 100).
   */
  evaluateAtPercent(pct) {
    const t = (Math.max(0, Math.min(100, pct)) / 100) * this.baseDurationSeconds;
    return this.evaluateAtTime(t);
  }
}
