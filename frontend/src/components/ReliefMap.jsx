import React, { useEffect, useRef, useState, useMemo } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  Truck,
  Play,
  Pause,
  RotateCcw,
  FastForward,
  CheckCircle2,
  Check,
  Info,
  Building2,
  Compass,
  X,
  Target,
  ChevronRight,
  ListOrdered,
  Crosshair,
  ShieldAlert,
} from "lucide-react";
import {
  FleetSimulationEngine,
  calculateBearing,
} from "../utils/routeSimulation";

const serviceColors = {
  RIGHT_UP: "#f43f5e",
  LEFT_UP: "#38bdf8",
  LEFT_DOWN: "#10b981",
  RIGHT_DOWN: "#fb923c",
  DEPOT: "#ffd84d",
  DESTINATION: "#a855f7",
};

const vehicleColors = [
  "#38bdf8", // Sky Blue
  "#f43f5e", // Rose
  "#10b981", // Emerald
  "#fb923c", // Amber Orange
  "#a855f7", // Violet
  "#facc15", // Gold
];

const fallbackStyle = {
  version: 8,
  sources: {
    "osm-tiles": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "osm-tiles-layer",
      type: "raster",
      source: "osm-tiles",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

export default function ReliefMap({
  isStagingMode = false,
  stagingDepot,
  stagingDestination,
  stagingHouses = [],
  activePickingTarget,
  onMapClickPoint,
  scenario,
  solution,
  hoveredVehicle,
  onSelectVehicle,
  selectedNode,
  onSelectNode,
  theme = "dark",
  simPlaying = false,
  onToggleSim,
  simSpeed = 1,
  onSetSimSpeed,
}) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const stagingMarkersRef = useRef([]);
  const vehicleMarkersRef = useRef({});
  const houseMarkerElementsRef = useRef({});
  const brokenMarkersRef = useRef([]);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [styleError, setStyleError] = useState(false);
  const [activeVehFilter, setActiveVehFilter] = useState("all");
  const [dispatchSummaryOpen, setDispatchSummaryOpen] = useState(false);
  const [showDirectionsTab, setShowDirectionsTab] = useState(false);

  const [animProgress, setAnimProgress] = useState(0);
  const animTimeRef = useRef(0.0);
  const [fleetState, setFleetState] = useState(null);

  const apiKey = import.meta.env.VITE_MAPTILER_API_KEY;
  const mapStyle = apiKey
    ? `https://api.maptiler.com/maps/hybrid/style.json?key=${apiKey}`
    : fallbackStyle;

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const initialLat = stagingDepot?.latitude || scenario?.depot_latitude || 26.9124;
    const initialLon = stagingDepot?.longitude || scenario?.depot_longitude || 75.7873;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: mapStyle,
      center: [initialLon, initialLat],
      zoom: 11,
      pitch: isStagingMode ? 0 : 35,
      attributionControl: true,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");

    const onReady = () => {
      setMapLoaded(true);
      map.resize();
    };

    map.on("load", onReady);
    if (map.isStyleLoaded()) {
      onReady();
    }

    map.on("error", (e) => {
      if (e?.error?.status === 403 || e?.error?.status === 401 || !apiKey) {
        setStyleError(true);
      }
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      stagingMarkersRef.current.forEach((m) => m.remove());
      stagingMarkersRef.current = [];
      Object.values(vehicleMarkersRef.current).forEach((m) => m.remove());
      vehicleMarkersRef.current = {};
      brokenMarkersRef.current.forEach((m) => m.remove());
      brokenMarkersRef.current = [];
      houseMarkerElementsRef.current = {};
      map.remove();
      mapRef.current = null;
      setMapLoaded(false);
    };
  }, [apiKey]);

  // Handle map click in picking mode
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const handleClick = (e) => {
      if (activePickingTarget && onMapClickPoint) {
        onMapClickPoint([e.lngLat.lng, e.lngLat.lat], activePickingTarget);
      }
    };

    map.on("click", handleClick);
    if (activePickingTarget) {
      map.getCanvas().style.cursor = "crosshair";
    } else {
      map.getCanvas().style.cursor = "";
    }

    return () => {
      map.off("click", handleClick);
    };
  }, [activePickingTarget, onMapClickPoint]);

  // ==========================================
  // STAGING MODE: RENDER LIVE INPUT PINS
  // ==========================================
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !isStagingMode) return;

    stagingMarkersRef.current.forEach((m) => m.remove());
    stagingMarkersRef.current = [];

    const bounds = new maplibregl.LngLatBounds();
    let hasPoints = false;

    // 1. Staging Depot
    if (stagingDepot?.latitude && stagingDepot?.longitude) {
      bounds.extend([stagingDepot.longitude, stagingDepot.latitude]);
      hasPoints = true;

      const depotEl = document.createElement("div");
      depotEl.className = `maplibre-depot-marker ${activePickingTarget === "depot" ? "pulse-active" : ""}`;
      depotEl.innerHTML = `
        <div class="depot-marker-pin">
          <span class="star-icon">★</span>
        </div>
        <div class="depot-marker-label">DEPOT</div>
      `;

      const m = new maplibregl.Marker({ element: depotEl, anchor: "bottom" })
        .setLngLat([stagingDepot.longitude, stagingDepot.latitude])
        .addTo(map);
      stagingMarkersRef.current.push(m);
    }

    // 2. Staging Destination
    if (stagingDestination?.latitude && stagingDestination?.longitude) {
      bounds.extend([stagingDestination.longitude, stagingDestination.latitude]);
      hasPoints = true;

      const destEl = document.createElement("div");
      destEl.className = `maplibre-dest-marker ${activePickingTarget === "destination" ? "pulse-active" : ""}`;
      destEl.innerHTML = `
        <div class="dest-marker-pin">
          <span class="target-icon">🎯</span>
        </div>
        <div class="dest-marker-label">DESTINATION</div>
      `;

      const m = new maplibregl.Marker({ element: destEl, anchor: "bottom" })
        .setLngLat([stagingDestination.longitude, stagingDestination.latitude])
        .addTo(map);
      stagingMarkersRef.current.push(m);
    }

    // 3. Staging Houses
    stagingHouses.forEach((house, idx) => {
      if (typeof house.latitude === "number" && typeof house.longitude === "number") {
        bounds.extend([house.longitude, house.latitude]);
        hasPoints = true;

        const isCurrentPicking = activePickingTarget === `house_${idx}`;
        const houseEl = document.createElement("div");
        houseEl.className = `maplibre-cust-marker staging-house-pin ${isCurrentPicking ? "pulse-active" : ""}`;
        houseEl.style.setProperty("--cust-color", "#38bdf8");
        houseEl.style.width = "18px";
        houseEl.style.height = "18px";
        houseEl.style.minWidth = "18px";
        houseEl.style.minHeight = "18px";
        houseEl.style.maxWidth = "18px";
        houseEl.style.maxHeight = "18px";
        houseEl.style.borderRadius = "50%";
        houseEl.innerHTML = `<span class="cust-id">#${idx + 1}</span>`;

        const m = new maplibregl.Marker({ element: houseEl, anchor: "center" })
          .setLngLat([house.longitude, house.latitude])
          .addTo(map);
        stagingMarkersRef.current.push(m);
      }
    });

    if (hasPoints && !bounds.isEmpty()) {
      map.fitBounds(bounds, {
        padding: { top: 60, bottom: 60, left: 60, right: 60 },
        maxZoom: 14,
        duration: 600,
      });
    }
  }, [isStagingMode, stagingDepot, stagingDestination, stagingHouses, activePickingTarget, mapLoaded]);

  // ==========================================
  // PHYSICAL ROUTE SIMULATION ENGINE
  // ==========================================
  const depotCoords = useMemo(() => {
    if (!scenario?.depot_latitude || !scenario?.depot_longitude) return null;
    return [scenario.depot_longitude, scenario.depot_latitude];
  }, [scenario]);

  const destCoords = useMemo(() => {
    const dest = scenario?.destination || solution?.destination;
    if (!dest?.latitude || !dest?.longitude) return null;
    return [dest.longitude, dest.latitude];
  }, [scenario, solution]);

  // Build high-performance route simulation engine
  const simEngine = useMemo(() => {
    if (!solution?.routes || solution.routes.length === 0 || isStagingMode) return null;
    return new FleetSimulationEngine(solution.routes, depotCoords, destCoords, 24.0);
  }, [solution, depotCoords, destCoords, isStagingMode]);

  // Direct map updates during simulation without React re-renders
  const updateVehicleMarkersOnMap = (vehicleStates) => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    vehicleStates.forEach((vs) => {
      const vId = vs.vehicle;
      if (activeVehFilter !== "all" && vId !== Number(activeVehFilter)) {
        if (vehicleMarkersRef.current[vId]) {
          vehicleMarkersRef.current[vId].remove();
          delete vehicleMarkersRef.current[vId];
        }
        return;
      }

      const color = vehicleColors[(vId - 1) % vehicleColors.length];
      let vMarker = vehicleMarkersRef.current[vId];

      if (!vMarker) {
        const vEl = document.createElement("div");
        vEl.className = "maplibre-vehicle-marker";
        vEl.id = `veh-marker-${vId}`;
        vEl.style.setProperty("--veh-color", color);
        vEl.innerHTML = `
          <div class="veh-marker-pin" id="veh-pin-${vId}">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 17h4V5H2v12h3m9 0h2l3-3V9h-5v8z"/>
              <circle cx="7.5" cy="17.5" r="2.5"/>
              <circle cx="17.5" cy="17.5" r="2.5"/>
            </svg>
          </div>
          <div class="veh-marker-label" id="veh-label-${vId}">V${vId}</div>
        `;

        vMarker = new maplibregl.Marker({ element: vEl, anchor: "center" })
          .setLngLat(vs.position)
          .addTo(map);

        vehicleMarkersRef.current[vId] = vMarker;
      } else {
        vMarker.setLngLat(vs.position);
        const pin = vMarker.getElement().querySelector(".veh-marker-pin");
        if (pin) {
          pin.style.transform = `rotate(${Math.round(vs.bearing)}deg)`;
        }
        const label = vMarker.getElement().querySelector(".veh-marker-label");
        if (label) {
          if (vs.isCompleted) {
            label.textContent = `V${vId} ✓`;
            label.classList.add("completed");
          } else {
            label.textContent = `V${vId}`;
            label.classList.remove("completed");
          }
        }
      }
    });

    // Cleanup markers for filtered-out vehicles
    Object.keys(vehicleMarkersRef.current).forEach((k) => {
      const vId = Number(k);
      const isVisible =
        activeVehFilter === "all" || vId === Number(activeVehFilter);
      if (!isVisible && vehicleMarkersRef.current[vId]) {
        vehicleMarkersRef.current[vId].remove();
        delete vehicleMarkersRef.current[vId];
      }
    });
  };

  const updateHouseMarkerStates = (visitedHouseIds) => {
    if (!houseMarkerElementsRef.current) return;
    Object.entries(houseMarkerElementsRef.current).forEach(([nodeIdStr, el]) => {
      if (!el) return;
      const nid = Number(nodeIdStr);
      const isVisited = visitedHouseIds.has(nid);

      if (isVisited) {
        if (!el.classList.contains("visited")) {
          el.classList.add("visited");
          el.classList.add("just-visited");
          setTimeout(() => el.classList.remove("just-visited"), 500);
          const badge = el.querySelector(".cust-visited-badge");
          if (badge) badge.style.display = "flex";
        }
      } else {
        el.classList.remove("visited");
        el.classList.remove("just-visited");
        const badge = el.querySelector(".cust-visited-badge");
        if (badge) badge.style.display = "none";
      }
    });
  };

  const updateTraveledRoutePaths = (vehicleStates) => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    vehicleStates.forEach((vs) => {
      const vSim = simEngine?.vehicleSims?.find((s) => s.vehicle === vs.vehicle);
      if (!vSim) return;
      const sourceId = `sim-traveled-source-${vs.vehicle}`;
      const src = map.getSource(sourceId);
      if (src) {
        const traveledGeom = vSim.getTraveledGeometry(vs.distTraveled);
        src.setData({
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: traveledGeom.length >= 2 ? traveledGeom : [traveledGeom[0], traveledGeom[0]],
          },
        });
      }
    });
  };

  // Main 60 FPS Route-Driven Animation Loop
  useEffect(() => {
    if (!simPlaying || !simEngine || isStagingMode) return;

    let animId;
    let lastTime = performance.now();

    const tick = (now) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Advance physical simulation time by dt * simSpeed
      animTimeRef.current += dt * simSpeed;
      const t = animTimeRef.current;
      const state = simEngine.evaluateAtTime(t);

      // Direct, hardware-accelerated MapLibre updates
      updateVehicleMarkersOnMap(state.vehicleStates);
      updateHouseMarkerStates(state.visitedHouseIds);
      updateTraveledRoutePaths(state.vehicleStates);

      setFleetState(state);
      setAnimProgress(state.globalPercent);

      if (state.isAllCompleted) {
        if (onToggleSim) onToggleSim(false);
        setDispatchSummaryOpen(true);
        setAnimProgress(100);
        return;
      }

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [simPlaying, simSpeed, simEngine, isStagingMode]);

  // Render Base Routes and Traveled Layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || isStagingMode || !scenario) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    brokenMarkersRef.current.forEach((m) => m.remove());
    brokenMarkersRef.current = [];
    houseMarkerElementsRef.current = {};

    const bounds = new maplibregl.LngLatBounds();

    // 1. Depot Marker
    const depotLat = scenario.depot_latitude;
    const depotLon = scenario.depot_longitude;
    bounds.extend([depotLon, depotLat]);

    const depotEl = document.createElement("div");
    depotEl.className = "maplibre-depot-marker";
    depotEl.innerHTML = `
      <div class="depot-marker-pin">
        <span class="star-icon">★</span>
      </div>
      <div class="depot-marker-label">DEPOT</div>
    `;

    const depotPopup = new maplibregl.Popup({ offset: 25, closeButton: true }).setHTML(`
      <div class="map-popup depot-popup">
        <div class="popup-kicker">CENTRAL RELIEF WAREHOUSE (SOURCE)</div>
        <div class="popup-title">${scenario.depot_name}</div>
        <div class="popup-row"><span>Latitude:</span> <b>${depotLat.toFixed(5)}° N</b></div>
        <div class="popup-row"><span>Longitude:</span> <b>${depotLon.toFixed(5)}° E</b></div>
        <div class="popup-tag">ALL FLEET VEHICLES DEPART & RETURN HERE</div>
      </div>
    `);

    const depotMarker = new maplibregl.Marker({ element: depotEl, anchor: "bottom" })
      .setLngLat([depotLon, depotLat])
      .setPopup(depotPopup)
      .addTo(map);
    markersRef.current.push(depotMarker);

    // 2. Destination Marker (Target Staging)
    const dest =
      scenario.destination ||
      solution?.destination ||
      (scenario.destination_name && scenario.destination_latitude && scenario.destination_longitude
        ? {
            name: scenario.destination_name,
            latitude: scenario.destination_latitude,
            longitude: scenario.destination_longitude,
          }
        : null);

    if (dest && dest.latitude && dest.longitude) {
      bounds.extend([dest.longitude, dest.latitude]);

      const destEl = document.createElement("div");
      destEl.className = "maplibre-dest-marker";
      destEl.innerHTML = `
        <div class="dest-marker-pin">
          <span class="target-icon">🎯</span>
        </div>
        <div class="dest-marker-label">DESTINATION</div>
      `;

      const destPopup = new maplibregl.Popup({ offset: 25, closeButton: true }).setHTML(`
        <div class="map-popup dest-popup">
          <div class="popup-kicker" style="color: #a855f7">TARGET / DESTINATION FACILITY</div>
          <div class="popup-title">${dest.name}</div>
          <div class="popup-row"><span>Latitude:</span> <b>${dest.latitude.toFixed(5)}° N</b></div>
          <div class="popup-row"><span>Longitude:</span> <b>${dest.longitude.toFixed(5)}° E</b></div>
          <div class="popup-tag" style="background: rgba(168, 85, 247, 0.15); color: #c084fc">PRIMARY DISASTER RELIEF DESTINATION</div>
        </div>
      `);

      const destMarker = new maplibregl.Marker({ element: destEl, anchor: "bottom" })
        .setLngLat([dest.longitude, dest.latitude])
        .setPopup(destPopup)
        .addTo(map);
      markersRef.current.push(destMarker);
    }

    // 3. House Markers (Up to 50 Houses)
    const nodes = solution?.nodes || [];
    nodes.forEach((node) => {
      if (node.is_depot || !node.geographic) return;

      const lat = node.geographic.latitude;
      const lon = node.geographic.longitude;
      bounds.extend([lon, lat]);

      const assignedRoute = solution?.routes?.find((r) => r.nodes.includes(node.id));
      const vehId = assignedRoute ? assignedRoute.vehicle : null;
      const vehColor = vehId ? vehicleColors[(vehId - 1) % vehicleColors.length] : "#38bdf8";
      const regionColor = serviceColors[node.region] || "#38bdf8";

      const houseEl = document.createElement("div");
      houseEl.className = `maplibre-cust-marker ${selectedNode?.id === node.id ? "selected" : ""}`;
      houseEl.style.setProperty("--cust-color", vehColor);
      houseEl.style.width = "18px";
      houseEl.style.height = "18px";
      houseEl.style.minWidth = "18px";
      houseEl.style.minHeight = "18px";
      houseEl.style.maxWidth = "18px";
      houseEl.style.maxHeight = "18px";
      houseEl.style.borderRadius = "50%";
      houseEl.innerHTML = `
        <span class="cust-id">${node.id}</span>
        <span class="cust-visited-badge" style="display: none;">✓</span>
      `;

      houseEl.addEventListener("click", () => {
        if (onSelectNode) onSelectNode(node);
      });

      // Cache element reference for instant 60fps visited status toggles
      houseMarkerElementsRef.current[node.id] = houseEl;

      const fulfillmentPct = (node.ratio * 100).toFixed(1);
      const housePopup = new maplibregl.Popup({ offset: 20, closeButton: true }).setHTML(`
        <div class="map-popup customer-popup">
          <div class="popup-kicker">COMMUNITY HOUSE #${node.id}</div>
          <div class="popup-title">${node.location_name}</div>
          <div class="popup-divider"></div>
          <div class="popup-row"><span>Allocated Relief:</span> <b style="color: #10b981">${node.allocated_demand} / ${node.original_demand} units</b></div>
          <div class="popup-row"><span>Fulfillment:</span> <b style="color: ${regionColor}">${fulfillmentPct}%</b></div>
          <div class="popup-row"><span>Regional Quadrant:</span> <b style="color: ${regionColor}">${node.region}</b></div>
          <div class="popup-row"><span>Assigned Fleet:</span> <b style="color: ${vehColor}">${vehId ? `Vehicle ${vehId}` : "Unserved"}</b></div>
          <div class="popup-coord-sub">${lat.toFixed(5)}° N, ${lon.toFixed(5)}° E</div>
        </div>
      `);

      const marker = new maplibregl.Marker({ element: houseEl, anchor: "center" })
        .setLngLat([lon, lat])
        .setPopup(housePopup)
        .addTo(map);

      markersRef.current.push(marker);
    });

    // 4. Render Route Network and Traveled Polyline Layers
    const renderRoutes = () => {
      if (!map || !map.isStyleLoaded()) return;
      const routes = solution?.routes || [];

      routes.forEach((r) => {
        const vId = r.vehicle;
        const color = vehicleColors[(vId - 1) % vehicleColors.length];

        const sourceId = `route-source-${vId}`;
        const casingLayerId = `route-casing-${vId}`;
        const lineLayerId = `route-line-${vId}`;
        const traveledSourceId = `sim-traveled-source-${vId}`;
        const traveledLayerId = `sim-traveled-line-${vId}`;

        // Remove existing layers if reloading
        [traveledLayerId, lineLayerId, casingLayerId].forEach((lid) => {
          if (map.getLayer(lid)) map.removeLayer(lid);
        });
        [traveledSourceId, sourceId].forEach((sid) => {
          if (map.getSource(sid)) map.removeSource(sid);
        });

        const coords =
          r.road_geometry && r.road_geometry.length >= 2 ? r.road_geometry : r.ordered_coords;

        if (coords && coords.length >= 2) {
          // Full Planned Route Source
          map.addSource(sourceId, {
            type: "geojson",
            data: {
              type: "Feature",
              properties: {
                vehicle: r.vehicle,
                load: r.load,
                distance: r.distance,
                road_km: r.road_distance_km,
                duration: r.road_duration_formatted,
              },
              geometry: {
                type: "LineString",
                coordinates: coords,
              },
            },
          });

          // Casing Layer (Black Outline)
          map.addLayer({
            id: casingLayerId,
            type: "line",
            source: sourceId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: { "line-color": "#05070a", "line-width": 5.5, "line-opacity": 0.65 },
          });

          // Base Planned Route (Faint / Dash indicator)
          map.addLayer({
            id: lineLayerId,
            type: "line",
            source: sourceId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: {
              "line-color": color,
              "line-width": 2.8,
              "line-opacity": 0.4,
              "line-dasharray": [2, 2],
            },
          });

          // Dynamic Traveled Path Source
          map.addSource(traveledSourceId, {
            type: "geojson",
            data: {
              type: "Feature",
              properties: {},
              geometry: {
                type: "LineString",
                coordinates: [coords[0], coords[0]],
              },
            },
          });

          // Dynamic Traveled Path Layer (Bright Glowing Solid Line)
          map.addLayer({
            id: traveledLayerId,
            type: "line",
            source: traveledSourceId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: {
              "line-color": color,
              "line-width": 4.2,
              "line-opacity": 0.95,
            },
          });

          map.on("click", lineLayerId, () => {
            if (onSelectVehicle) onSelectVehicle(r.vehicle);
          });
        }
      });
    };

    if (map.isStyleLoaded()) {
      renderRoutes();
    } else {
      map.once("styledata", renderRoutes);
    }

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, {
        padding: { top: 60, bottom: 60, left: 60, right: 60 },
        maxZoom: 14,
        duration: 900,
      });
    }

    // Initialize fleet positions at depot
    if (simEngine) {
      const initialFleet = simEngine.evaluateAtTime(0);
      updateVehicleMarkersOnMap(initialFleet.vehicleStates);
      setFleetState(initialFleet);
    }
  }, [solution, scenario, mapLoaded, isStagingMode]);

  // Handle Scrubber Interaction
  const handleScrub = (val) => {
    const pct = Math.max(0, Math.min(100, Number(val)));
    setAnimProgress(pct);
    if (!simEngine) return;

    const t = (pct / 100) * simEngine.baseDurationSeconds;
    animTimeRef.current = t;
    const state = simEngine.evaluateAtTime(t);

    updateVehicleMarkersOnMap(state.vehicleStates);
    updateHouseMarkerStates(state.visitedHouseIds);
    updateTraveledRoutePaths(state.vehicleStates);
    setFleetState(state);

    if (pct >= 99.9) {
      if (onToggleSim) onToggleSim(false);
      setDispatchSummaryOpen(true);
    }
  };

  // Handle Play/Pause
  const handleTogglePlay = () => {
    if (animProgress >= 100) {
      animTimeRef.current = 0;
      setAnimProgress(0);
      setDispatchSummaryOpen(false);
      if (simEngine) {
        const resetState = simEngine.evaluateAtTime(0);
        updateVehicleMarkersOnMap(resetState.vehicleStates);
        updateHouseMarkerStates(new Set());
        updateTraveledRoutePaths(resetState.vehicleStates);
        setFleetState(resetState);
      }
    }
    if (onToggleSim) onToggleSim(!simPlaying);
  };

  // Handle Restart / Reset to Depot
  const handleResetSimulation = () => {
    if (onToggleSim) onToggleSim(false);
    animTimeRef.current = 0;
    setAnimProgress(0);
    setDispatchSummaryOpen(false);

    if (simEngine) {
      const resetState = simEngine.evaluateAtTime(0);
      updateVehicleMarkersOnMap(resetState.vehicleStates);
      updateHouseMarkerStates(new Set());
      updateTraveledRoutePaths(resetState.vehicleStates);
      setFleetState(resetState);
    }
  };

  // Handle Speed Cycling
  const handleCycleSpeed = () => {
    const next = simSpeed === 1 ? 2 : simSpeed === 2 ? 4 : simSpeed === 4 ? 8 : 1;
    if (onSetSimSpeed) onSetSimSpeed(next);
  };

  const activeRouteData = useMemo(() => {
    if (!solution?.routes || solution.routes.length === 0 || isStagingMode) return null;
    if (activeVehFilter !== "all") {
      return solution.routes.find((r) => r.vehicle === Number(activeVehFilter)) || solution.routes[0];
    }
    if (hoveredVehicle !== null && hoveredVehicle !== undefined) {
      return solution.routes.find((r) => r.vehicle === hoveredVehicle) || solution.routes[0];
    }
    return solution.routes[0];
  }, [solution, activeVehFilter, hoveredVehicle, isStagingMode]);

  const totalRoadDistanceKm = useMemo(() => {
    if (!solution?.routes) return 0;
    return solution.routes.reduce((acc, r) => acc + (r.road_distance_km || 0), 0);
  }, [solution]);

  const totalRoadDurationSeconds = useMemo(() => {
    if (!solution?.routes) return 0;
    return solution.routes.reduce((acc, r) => acc + (r.road_duration_seconds || 0), 0);
  }, [solution]);

  const formatTotalTime = (sec) => {
    if (sec <= 0) return "0 min";
    const totalMin = Math.round(sec / 60);
    const hrs = Math.floor(totalMin / 60);
    const mins = totalMin % 60;
    return hrs > 0 ? `${hrs}h ${mins}m` : `${mins} min`;
  };

  const isAllCompleted = fleetState?.isAllCompleted ?? (animProgress >= 100);

  return (
    <div className="relief-map-wrapper">
      <div ref={mapContainerRef} className="maplibre-container" />

      {/* Picking Banner when picking target is active */}
      {isStagingMode && activePickingTarget && (
        <div className="map-picking-banner">
          <Crosshair size={14} className="pulse" />
          <span>
            CLICK ANYWHERE ON THE MAP TO SET: <b>{activePickingTarget.toUpperCase().replace("_", " ")}</b>
          </span>
        </div>
      )}

      {/* Staging HUD Header */}
      {isStagingMode && (
        <div className="map-hud-overlay">
          <div className="hud-badge">
            <Compass size={13} color="var(--amber)" />
            <span>REAL GEOGRAPHIC MAP • INTERACTIVE STAGING</span>
          </div>
          <div className="hud-scenario-info">
            Depot: <b>{stagingDepot?.name || "Not set"}</b>
            {stagingDestination?.name && <span> • Target: <b>{stagingDestination.name}</b></span>}
            <span> • <b>{stagingHouses.filter((h) => h.latitude).length}</b> / {stagingHouses.length} Houses Positioned</span>
          </div>
        </div>
      )}

      {/* Operational Solution HUD Header */}
      {!isStagingMode && (
        <div className="map-hud-overlay">
          <div className="hud-badge">
            <Compass size={13} color="var(--amber)" />
            <span>REAL GEOGRAPHIC DISASTER MAP</span>
          </div>
          <div className="hud-scenario-info">
            <b>{scenario?.name}</b> • Depot: {scenario?.depot_name}
            {scenario?.destination?.name && (
              <span> • Target: <b>{scenario.destination.name}</b></span>
            )}
          </div>
        </div>
      )}

      {/* TACTICAL SIMULATION CONTROL PANEL (Solution Mode Only) */}
      {!isStagingMode && solution?.routes && (
        <div className="dispatch-hud-panel">
          <div className="hud-panel-header">
            <div className="hud-panel-title">
              <Truck size={14} color="var(--amber)" />
              <span>SIMULATION</span>
            </div>
            <div
              className={`hud-status-tag ${
                isAllCompleted ? "complete" : simPlaying ? "active" : ""
              }`}
            >
              {isAllCompleted
                ? "ALL RETURNED ✓"
                : simPlaying
                ? "EN ROUTE"
                : animProgress > 0
                ? "PAUSED"
                : "AT DEPOT"}
            </div>
          </div>

          <div className="hud-sim-controls">
            <button
              className={`hud-ctrl-btn primary ${simPlaying ? "playing" : ""}`}
              onClick={handleTogglePlay}
              title={simPlaying ? "Pause simulation" : "Start physical route simulation"}
            >
              {simPlaying ? <Pause size={13} /> : <Play size={13} />}
              <span>{simPlaying ? "PAUSE" : isAllCompleted ? "REPLAY" : "PLAY"}</span>
            </button>

            <button
              className="hud-ctrl-btn"
              onClick={handleResetSimulation}
              title="Restart simulation from depot"
            >
              <RotateCcw size={12} />
              <span>RESTART</span>
            </button>

            <button
              className="hud-ctrl-btn speed-btn"
              onClick={handleCycleSpeed}
              title="Cycle physical simulation speed"
            >
              <FastForward size={12} />
              <span>{simSpeed}x</span>
            </button>

            <button
              className={`hud-ctrl-btn ${showDirectionsTab ? "active" : ""}`}
              onClick={() => setShowDirectionsTab((prev) => !prev)}
              title="Toggle detailed road directions"
            >
              <ListOrdered size={12} />
              <span>LEGS</span>
            </button>
          </div>

          <div className="hud-scrubber-row">
            <input
              type="range"
              min="0"
              max="100"
              step="0.2"
              value={animProgress}
              onInput={(e) => handleScrub(e.target.value)}
              onChange={(e) => handleScrub(e.target.value)}
              className="hud-slider"
            />
            <span className="hud-scrubber-pct">{Math.round(animProgress)}%</span>
          </div>

          {/* FLEET SELECTOR */}
          {solution?.routes && solution.routes.length > 1 && (
            <div className="hud-vehicle-selector">
              <span className="selector-kicker">FLEET:</span>
              <button
                className={`hud-pill ${activeVehFilter === "all" ? "active" : ""}`}
                onClick={() => setActiveVehFilter("all")}
              >
                ALL ({solution.routes.length})
              </button>
              {solution.routes.map((r, i) => {
                const vs = fleetState?.vehicleStates?.find((v) => v.vehicle === r.vehicle);
                const isVehDone = vs?.isCompleted;
                return (
                  <button
                    key={r.vehicle}
                    className={`hud-pill ${activeVehFilter === String(r.vehicle) ? "active" : ""}`}
                    style={{
                      borderColor:
                        activeVehFilter === String(r.vehicle)
                          ? vehicleColors[i % vehicleColors.length]
                          : "transparent",
                    }}
                    onClick={() => setActiveVehFilter(String(r.vehicle))}
                  >
                    <span
                      className="hud-dot"
                      style={{ background: vehicleColors[i % vehicleColors.length] }}
                    />
                    V{r.vehicle}
                    {isVehDone ? " ✓" : ""}
                  </button>
                );
              })}
            </div>
          )}

          {/* LIVE FLEET VEHICLE STATUS CARDS */}
          {!showDirectionsTab && fleetState?.vehicleStates && (
            <div className="hud-fleet-status-list">
              {fleetState.vehicleStates
                .filter((vs) => activeVehFilter === "all" || vs.vehicle === Number(activeVehFilter))
                .map((vs) => {
                  const color = vehicleColors[(vs.vehicle - 1) % vehicleColors.length];
                  const isDone = vs.isCompleted;
                  const isDeparting = vs.distTraveled <= 0.5;
                  const nextStopName = vs.status?.nextStop?.name || "Depot";

                  return (
                    <div
                      key={vs.vehicle}
                      className={`fleet-vcard ${isDone ? "is-complete" : ""} ${
                        hoveredVehicle === vs.vehicle ? "focused" : ""
                      }`}
                      onMouseEnter={() => onSelectVehicle && onSelectVehicle(vs.vehicle)}
                      onMouseLeave={() => onSelectVehicle && onSelectVehicle(null)}
                    >
                      <div className="fleet-vcard-header">
                        <div className="fleet-vcard-title">
                          <span className="hud-dot" style={{ background: color }} />
                          <span>VEHICLE {vs.vehicle}</span>
                        </div>
                        <span
                          className={`fleet-vcard-status-badge ${
                            isDone ? "complete" : isDeparting ? "at-depot" : "en-route"
                          }`}
                        >
                          {isDone ? "COMPLETE ✓" : isDeparting ? "AT DEPOT" : "EN ROUTE"}
                        </span>
                      </div>

                      <div className="fleet-vcard-body">
                        <span className="fleet-vcard-target">
                          {isDone
                            ? "Returned to Depot"
                            : vs.status?.stateText || `→ ${nextStopName}`}
                        </span>
                        <span>
                          {vs.status?.visitedCount || 0} / {vs.stops?.length || 0} stops
                        </span>
                      </div>

                      <div className="fleet-vcard-progress-bar">
                        <div
                          className="fleet-vcard-progress-fill"
                          style={{
                            width: `${Math.round(vs.progressFraction * 100)}%`,
                            background: isDone ? "#10b981" : color,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          )}

          {/* DETAILED ROAD DIRECTIONS DRAWER */}
          {showDirectionsTab && activeRouteData && (
            <div className="hud-directions-drawer">
              <div className="directions-drawer-header">
                <span>VEHICLE {activeRouteData.vehicle} ROAD LEGS</span>
                <span>
                  Road: <b>{activeRouteData.road_distance_km} km</b> • Est Time:{" "}
                  <b>{activeRouteData.road_duration_formatted}</b>
                </span>
              </div>
              <div className="directions-legs-list">
                {activeRouteData.segments && activeRouteData.segments.length > 0 ? (
                  activeRouteData.segments.map((seg, sIdx) => (
                    <div key={sIdx} className="direction-leg-item">
                      <span className="leg-num">{sIdx + 1}.</span>
                      <div className="leg-path">
                        <span className="leg-from">{seg.from_name}</span>
                        <span className="leg-arrow">→</span>
                        <span className="leg-to">{seg.to_name}</span>
                      </div>
                      <div className="leg-metrics">
                        <span>{seg.distance_km} km</span>
                        <span>•</span>
                        <span>{seg.duration_formatted}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="direction-leg-item">
                    <span>{activeRouteData.location_names?.join(" → ")}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* DISPATCH COMPLETE SUMMARY BANNER */}
      {dispatchSummaryOpen && !isStagingMode && (
        <div className="dispatch-summary-banner">
          <div className="summary-banner-top">
            <div className="summary-title-group">
              <CheckCircle2 size={20} color="var(--green)" />
              <div>
                <h4>DISPATCH SIMULATION COMPLETE</h4>
                <p>
                  All {solution?.routes?.length || 0} vehicles have visited their assigned
                  community houses and safely returned to the depot.
                </p>
              </div>
            </div>
            <button
              className="summary-close-btn"
              onClick={() => setDispatchSummaryOpen(false)}
              title="Dismiss"
            >
              <X size={16} />
            </button>
          </div>

          <div className="summary-stats-grid">
            <div className="summary-stat-box">
              <span className="stat-label">VEHICLES DISPATCHED</span>
              <span className="stat-val">{solution?.routes?.length || 0}</span>
              <span className="stat-sub">All returned to depot</span>
            </div>
            <div className="summary-stat-box">
              <span className="stat-label">HOUSES SERVED</span>
              <span className="stat-val" style={{ color: "var(--green)" }}>
                {solution?.nodes
                  ? solution.nodes.filter((n) => !n.is_depot && n.allocated_demand > 0).length
                  : 0}{" "}
                / {solution?.nodes ? solution.nodes.length - 1 : 0}
              </span>
              <span className="stat-sub">100% active coverage</span>
            </div>
            <div className="summary-stat-box">
              <span className="stat-label">TOTAL ROAD DISTANCE</span>
              <span className="stat-val">{totalRoadDistanceKm.toFixed(1)} km</span>
              <span className="stat-sub">Street network traversal</span>
            </div>
            <div className="summary-stat-box">
              <span className="stat-label">TOTAL TRAVEL TIME</span>
              <span className="stat-val">{formatTotalTime(totalRoadDurationSeconds)}</span>
              <span className="stat-sub">Estimated travel time</span>
            </div>
          </div>
        </div>
      )}

      {(!apiKey || styleError) && (
        <div className="maptiler-notice-banner">
          <Info size={15} />
          <span>
            Operating with OpenStreetMap vector basemap fallback. (Configure{" "}
            <code>VITE_MAPTILER_API_KEY</code> for high-resolution satellite imagery tiles).
          </span>
        </div>
      )}
    </div>
  );
}
