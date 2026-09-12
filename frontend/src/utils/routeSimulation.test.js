import test from "node:test";
import assert from "node:assert/strict";
import {
  haversineDistanceMeters,
  calculateBearing,
  cleanCoordinates,
  prepareVehicleRoute,
  FleetSimulationEngine,
} from "./routeSimulation.js";

test("haversineDistanceMeters calculates accurate physical distance", () => {
  const dZero = haversineDistanceMeters(75.7873, 26.9124, 75.7873, 26.9124);
  assert.equal(dZero, 0);

  // Jaipur to Delhi ~238 km
  const dJaipurDelhi = haversineDistanceMeters(75.7873, 26.9124, 77.1025, 28.7041);
  assert.ok(dJaipurDelhi > 230000 && dJaipurDelhi < 250000);
});

test("calculateBearing returns correct directional azimuth", () => {
  // Directly North: lon same, lat increases -> ~0°
  const bNorth = calculateBearing(75.0, 26.0, 75.0, 27.0);
  assert.ok(Math.abs(bNorth - 0) < 0.1 || Math.abs(bNorth - 360) < 0.1);

  // Directly East: lon increases, lat same -> ~90°
  const bEast = calculateBearing(75.0, 26.0, 76.0, 26.0);
  assert.ok(Math.abs(bEast - 90) < 1.0);

  // Directly South: lon same, lat decreases -> ~180°
  const bSouth = calculateBearing(75.0, 26.0, 75.0, 25.0);
  assert.ok(Math.abs(bSouth - 180) < 0.1);
});

test("cleanCoordinates removes consecutive duplicates and NaNs", () => {
  const raw = [
    [75.7873, 26.9124],
    [75.7873, 26.9124], // duplicate
    [NaN, 26.9124],     // invalid
    [75.7900, 26.9150],
    null,               // invalid
    [75.7900, 26.9150], // duplicate
    [75.8000, 26.9200],
  ];
  const cleaned = cleanCoordinates(raw);
  assert.equal(cleaned.length, 3);
  assert.deepEqual(cleaned[0], [75.7873, 26.9124]);
  assert.deepEqual(cleaned[1], [75.7900, 26.9150]);
  assert.deepEqual(cleaned[2], [75.8000, 26.9200]);
});

test("prepareVehicleRoute builds strictly monotonic distance model and stops", () => {
  const depot = [75.7873, 26.9124];
  const h1 = [75.8000, 26.9150];
  const h2 = [75.8100, 26.9200];
  const mockRoute = {
    vehicle: 1,
    nodes: [0, 1, 2, 0],
    location_names: ["Depot Hub", "Community 1", "Community 2", "Depot Hub"],
    ordered_coords: [depot, h1, h2, depot],
    road_geometry: [
      depot,
      [75.7900, 26.9130],
      [75.7950, 26.9140],
      h1,
      [75.8050, 26.9170],
      h2,
      [75.8000, 26.9160],
      depot,
    ],
    load: 45,
    capacity: 100,
  };

  const vSim = prepareVehicleRoute(mockRoute, depot, null);

  assert.equal(vSim.vehicle, 1);
  assert.ok(vSim.totalDistance > 0);
  assert.equal(vSim.stops.length, 4);

  // Stop 0 is depot start at dist 0
  assert.equal(vSim.stops[0].nodeId, 0);
  assert.equal(vSim.stops[0].distance, 0);

  // Stop 3 is depot return at totalDistance
  assert.equal(vSim.stops[3].nodeId, 0);
  assert.equal(vSim.stops[3].distance, vSim.totalDistance);

  // Stop 1 and 2 must be strictly ordered along route
  assert.ok(vSim.stops[1].distance > 0);
  assert.ok(vSim.stops[2].distance >= vSim.stops[1].distance);
  assert.ok(vSim.stops[2].distance <= vSim.totalDistance);

  // Position at distance 0 is at depot
  const posStart = vSim.getPositionAtDistance(0);
  assert.deepEqual(posStart.lngLat, depot);
  assert.equal(posStart.isCompleted, false);

  // Position at total distance is at depot
  const posEnd = vSim.getPositionAtDistance(vSim.totalDistance);
  assert.deepEqual(posEnd.lngLat, depot);
  assert.equal(posEnd.isCompleted, true);

  // Intermediate position follows the physical road polyline
  const posMid = vSim.getPositionAtDistance(vSim.totalDistance * 0.5);
  assert.ok(posMid.lngLat[0] >= 75.7873 && posMid.lngLat[0] <= 75.8100);
  assert.ok(posMid.bearing >= 0 && posMid.bearing <= 360);

  // Status checks
  const statusStart = vSim.getStatusAtDistance(0);
  assert.equal(statusStart.isDeparting, true);
  assert.equal(statusStart.isCompleted, false);

  const statusEnd = vSim.getStatusAtDistance(vSim.totalDistance);
  assert.equal(statusEnd.isCompleted, true);
  assert.ok(statusEnd.visitedStopNodeIds.has(1));
  assert.ok(statusEnd.visitedStopNodeIds.has(2));
});

test("FleetSimulationEngine coordinates multiple simultaneous vehicles and return to depot", () => {
  const depot = [75.7873, 26.9124];
  const r1 = {
    vehicle: 1,
    nodes: [0, 1, 0],
    ordered_coords: [depot, [75.795, 26.915], depot],
    road_geometry: [depot, [75.790, 26.913], [75.795, 26.915], [75.790, 26.913], depot],
    load: 20,
    capacity: 100,
  };
  const r2 = {
    vehicle: 2,
    nodes: [0, 2, 3, 0],
    ordered_coords: [depot, [75.810, 26.925], [75.820, 26.930], depot],
    road_geometry: [depot, [75.800, 26.920], [75.810, 26.925], [75.815, 26.928], [75.820, 26.930], [75.800, 26.920], depot],
    load: 40,
    capacity: 100,
  };

  const fleetEngine = new FleetSimulationEngine([r1, r2], depot, null, 10.0);

  // Initial State: t = 0
  const state0 = fleetEngine.evaluateAtTime(0);
  assert.equal(state0.isAllCompleted, false);
  assert.equal(state0.visitedHouseIds.size, 0);
  assert.deepEqual(state0.vehicleStates[0].position, depot);
  assert.deepEqual(state0.vehicleStates[1].position, depot);

  // Mid State: t = 5.0 (Vehicle 1 with shorter route has progressed further proportionally)
  const stateMid = fleetEngine.evaluateAtTime(5.0);
  assert.ok(stateMid.globalPercent > 40 && stateMid.globalPercent < 60);
  assert.ok(stateMid.vehicleStates[0].distTraveled > 0);
  assert.ok(stateMid.vehicleStates[1].distTraveled > 0);

  // Final State: t = 10.0 (All vehicles must have returned to depot)
  const stateEnd = fleetEngine.evaluateAtTime(10.0);
  assert.equal(stateEnd.isAllCompleted, true);
  assert.equal(stateEnd.globalPercent, 100);

  // Mandatory return to depot verification:
  assert.equal(stateEnd.vehicleStates[0].isCompleted, true);
  assert.equal(stateEnd.vehicleStates[1].isCompleted, true);
  assert.deepEqual(stateEnd.vehicleStates[0].position, depot);
  assert.deepEqual(stateEnd.vehicleStates[1].position, depot);

  // Both vehicles' houses visited
  assert.ok(stateEnd.visitedHouseIds.has(1));
  assert.ok(stateEnd.visitedHouseIds.has(2));
  assert.ok(stateEnd.visitedHouseIds.has(3));
});
