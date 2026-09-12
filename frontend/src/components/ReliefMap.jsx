import React, { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Compass,
  FastForward,
  Info,
  MapPin,
  Navigation,
  Pause,
  Play,
  RotateCcw,
  Route,
  Truck,
  X,
} from "lucide-react";

const serviceColors = {
  RIGHT_UP: "#f43f5e",
  LEFT_UP: "#38bdf8",
  LEFT_DOWN: "#10b981",
  RIGHT_DOWN: "#fb923c",
  DEPOT: "#ffd84d",
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

// Calculate geographic bearing between two [lon, lat] points
function calculateBearing(lon1, lat1, lon2, lat2) {
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const lat1Rad = (lat1 * Math.PI) / 180;
  const lat2Rad = (lat2 * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos(lat2Rad);
  const x =
    Math.cos(lat1Rad) * Math.sin(lat2Rad) -
    Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);
  let brng = (Math.atan2(y, x) * 180) / Math.PI;
  return (brng + 360) % 360;
}

export default function ReliefMap({
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
  simStep = 0,
  onSetSimStep,
  maxRouteLength = 1,
}) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const vehicleMarkersRef = useRef({});
  const brokenMarkersRef = useRef([]);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [styleError, setStyleError] = useState(false);
  const [activeVehFilter, setActiveVehFilter] = useState("all");
  const [dispatchSummaryOpen, setDispatchSummaryOpen] = useState(false);

  // Internal smooth animation progress: 0 to 100
  const [animProgress, setAnimProgress] = useState(0);

  const apiKey = import.meta.env.VITE_MAPTILER_API_KEY;
  const mapStyle = apiKey
    ? `https://api.maptiler.com/maps/hybrid/style.json?key=${apiKey}`
    : fallbackStyle;

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainerRef.current) return;

    const depotLat = scenario?.depot_latitude ?? 26.9124;
    const depotLon = scenario?.depot_longitude ?? 75.7873;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: mapStyle,
      center: [depotLon, depotLat],
      zoom: 11,
      pitch: 35,
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
      Object.values(vehicleMarkersRef.current).forEach((m) => m.remove());
      vehicleMarkersRef.current = {};
      brokenMarkersRef.current.forEach((m) => m.remove());
      brokenMarkersRef.current = [];
      map.remove();
      mapRef.current = null;
      setMapLoaded(false);
    };
  }, [scenario?.id, apiKey]);

  // Precompute waypoint fractions along each route's road geometry
  const routeWaypoints = useMemo(() => {
    if (!solution?.routes) return [];
    return solution.routes.map((r) => {
      const geom = r.road_geometry || r.ordered_coords || [];
      const geomLen = geom.length;
      const coords = r.ordered_coords || [];

      // Find closest geom index for each waypoint
      const waypointsWithFraction = r.nodes.map((nid, idx) => {
        const c = coords[idx];
        let bestIdx = 0;
        let bestDist = Infinity;
        if (c && Array.isArray(c) && c.length >= 2 && geomLen > 0) {
          for (let gi = 0; gi < geomLen; gi++) {
            if (!geom[gi] || !Array.isArray(geom[gi]) || geom[gi].length < 2) continue;
            const dx = geom[gi][0] - c[0];
            const dy = geom[gi][1] - c[1];
            const d = dx * dx + dy * dy;
            if (d < bestDist) {
              bestDist = d;
              bestIdx = gi;
            }
          }
        } else {
          bestIdx = Math.floor((idx / Math.max(1, r.nodes.length - 1)) * (geomLen - 1));
        }

        const fraction = geomLen > 1 ? bestIdx / (geomLen - 1) : idx / Math.max(1, r.nodes.length - 1);
        const name = r.location_names?.[idx] || (nid === 0 ? scenario?.depot_name : `Customer #${nid}`);

        return {
          nodeId: nid,
          index: idx,
          name,
          fraction,
          geomIndex: bestIdx,
        };
      });

      return {
        vehicle: r.vehicle,
        waypoints: waypointsWithFraction,
        geom,
      };
    });
  }, [solution, scenario]);

  // Animation Loop along actual road geometry
  useEffect(() => {
    if (!simPlaying) return;

    let animId;
    let lastTime = performance.now();

    const tick = (now) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Base complete route takes ~18 seconds at 1x speed
      const stepDelta = (100 / 18) * simSpeed * dt;

      setAnimProgress((prev) => {
        const next = prev + stepDelta;
        if (next >= 100) {
          if (onToggleSim) onToggleSim(false);
          setDispatchSummaryOpen(true);
          return 100;
        }
        return next;
      });

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [simPlaying, simSpeed, onToggleSim]);

  // Sync external simStep changes (e.g. from parent scrubber)
  useEffect(() => {
    if (maxRouteLength > 1 && !simPlaying) {
      const pct = (simStep / (maxRouteLength - 1)) * 100;
      setAnimProgress(Math.min(100, Math.max(0, pct)));
      if (pct >= 99.5) {
        setDispatchSummaryOpen(true);
      }
    }
  }, [simStep, maxRouteLength, simPlaying]);

  // Update animated vehicle markers and visited stops
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !solution?.routes) return;

    const currentF = animProgress / 100;
    const routesToSimulate = solution.routes.filter((r) => {
      if (activeVehFilter !== "all" && r.vehicle !== Number(activeVehFilter)) {
        return false;
      }
      if (hoveredVehicle !== null && hoveredVehicle !== undefined && r.vehicle !== hoveredVehicle) {
        return false;
      }
      return true;
    });

    routesToSimulate.forEach((r) => {
      const geom = r.road_geometry || r.ordered_coords || [];
      if (geom.length < 2) return;

      const vIdx = r.vehicle;
      const color = vehicleColors[(vIdx - 1) % vehicleColors.length];

      // Calculate position along road geometry
      const totalPts = geom.length;
      const exactIndex = currentF * (totalPts - 1);
      const floorIdx = Math.min(totalPts - 1, Math.floor(exactIndex));
      const ceilIdx = Math.min(totalPts - 1, floorIdx + 1);
      const alpha = exactIndex - floorIdx;

      const pA = geom[floorIdx];
      const pB = geom[ceilIdx] || pA;
      if (!pA || !Array.isArray(pA) || pA.length < 2) return;
      const bLon = pB && Array.isArray(pB) && pB.length >= 2 ? pB[0] : pA[0];
      const bLat = pB && Array.isArray(pB) && pB.length >= 2 ? pB[1] : pA[1];

      const currLon = pA[0] + alpha * (bLon - pA[0]);
      const currLat = pA[1] + alpha * (bLat - pA[1]);

      // Calculate heading angle
      const bearing = calculateBearing(pA[0], pA[1], bLon, bLat);

      let vMarker = vehicleMarkersRef.current[vIdx];
      if (!vMarker) {
        const vEl = document.createElement("div");
        vEl.className = "maplibre-vehicle-marker";
        vEl.style.setProperty("--veh-color", color);
        vEl.innerHTML = `
          <div class="veh-marker-pin" id="veh-pin-${vIdx}">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 17h4V5H2v12h3m9 0h2l3-3V9h-5v8z"/>
              <circle cx="7.5" cy="17.5" r="2.5"/>
              <circle cx="17.5" cy="17.5" r="2.5"/>
            </svg>
          </div>
          <div class="veh-marker-label">V${vIdx}</div>
        `;

        vMarker = new maplibregl.Marker({ element: vEl, anchor: "center" })
          .setLngLat([currLon, currLat])
          .addTo(map);

        vehicleMarkersRef.current[vIdx] = vMarker;
      } else {
        vMarker.setLngLat([currLon, currLat]);
        const pin = vMarker.getElement().querySelector(".veh-marker-pin");
        if (pin) {
          pin.style.transform = `rotate(${bearing}deg)`;
        }
      }
    });

    // Remove inactive vehicle markers
    Object.keys(vehicleMarkersRef.current).forEach((k) => {
      const vId = Number(k);
      const stillActive = routesToSimulate.some((r) => r.vehicle === vId);
      if (!stillActive) {
        vehicleMarkersRef.current[vId].remove();
        delete vehicleMarkersRef.current[vId];
      }
    });
  }, [animProgress, solution, mapLoaded, activeVehFilter, hoveredVehicle]);

  // Update bounds, static markers, and route layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !scenario) return;

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    brokenMarkersRef.current.forEach((m) => m.remove());
    brokenMarkersRef.current = [];

    const bounds = new maplibregl.LngLatBounds();

    // 1. Add Depot Marker
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
        <div class="popup-kicker">CENTRAL RELIEF WAREHOUSE</div>
        <div class="popup-title">${scenario.depot_name}</div>
        <div class="popup-row"><span>Latitude:</span> <b>${depotLat.toFixed(5)}° N</b></div>
        <div class="popup-row"><span>Longitude:</span> <b>${depotLon.toFixed(5)}° E</b></div>
        <div class="popup-tag">ALL VEHICLES DEPART & RETURN HERE</div>
      </div>
    `);

    const depotMarker = new maplibregl.Marker({ element: depotEl, anchor: "bottom" })
      .setLngLat([depotLon, depotLat])
      .setPopup(depotPopup)
      .addTo(map);

    markersRef.current.push(depotMarker);

    // 2. Add Customer Markers
    const nodes = solution?.nodes || [];
    nodes.forEach((node) => {
      if (node.is_depot || !node.geographic) return;

      const lat = node.geographic.latitude;
      const lon = node.geographic.longitude;
      bounds.extend([lon, lat]);

      const regionColor = serviceColors[node.region] || "#38bdf8";
      const demandScale = Math.min(36, Math.max(22, 18 + (node.original_demand || 30) / 3));

      const custEl = document.createElement("div");
      custEl.className = `maplibre-cust-marker ${selectedNode?.id === node.id ? "selected" : ""}`;
      custEl.style.setProperty("--cust-color", regionColor);
      custEl.style.width = `${demandScale}px`;
      custEl.style.height = `${demandScale}px`;
      custEl.innerHTML = `<span class="cust-id">${node.id}</span>`;

      custEl.addEventListener("click", () => {
        if (onSelectNode) onSelectNode(node);
      });

      const fulfillmentPct = (node.ratio * 100).toFixed(1);
      const custPopup = new maplibregl.Popup({ offset: 20, closeButton: true }).setHTML(`
        <div class="map-popup customer-popup">
          <div class="popup-kicker">COMMUNITY RELIEF RECIPIENT #${node.id}</div>
          <div class="popup-title">${node.location_name}</div>
          <div class="popup-divider"></div>
          <div class="popup-row"><span>Requirement:</span> <b>${node.original_demand} units</b></div>
          <div class="popup-row"><span>Allocated Supply:</span> <b style="color: #10b981">${node.allocated_demand} units</b></div>
          <div class="popup-row"><span>Fulfillment:</span> <b style="color: ${regionColor}">${fulfillmentPct}%</b></div>
          <div class="popup-row"><span>Region Quadrant:</span> <b style="color: ${regionColor}">${node.region}</b></div>
          <div class="popup-coord-sub">${lat.toFixed(5)}° N, ${lon.toFixed(5)}° E</div>
        </div>
      `);

      const marker = new maplibregl.Marker({ element: custEl, anchor: "center" })
        .setLngLat([lon, lat])
        .setPopup(custPopup)
        .addTo(map);

      markersRef.current.push(marker);
    });

    // 3. Render Road Geometry & Broken Segment Warnings
    const renderRoutes = () => {
      if (!map || !map.isStyleLoaded()) return;
      const routes = solution?.routes || [];

      routes.forEach((r) => {
        const vId = r.vehicle;
        const color = vehicleColors[(vId - 1) % vehicleColors.length];

        // Valid Route Lines
        const sourceId = `route-source-${vId}`;
        const casingLayerId = `route-casing-${vId}`;
        const lineLayerId = `route-line-${vId}`;

        if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId);
        if (map.getLayer(casingLayerId)) map.removeLayer(casingLayerId);
        if (map.getSource(sourceId)) map.removeSource(sourceId);

        const coords = r.road_geometry && r.road_geometry.length >= 2
          ? r.road_geometry
          : r.ordered_coords;

        if (coords && coords.length >= 2) {
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

          // Contrasting Casing
          map.addLayer({
            id: casingLayerId,
            type: "line",
            source: sourceId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: { "line-color": "#05070a", "line-width": 6, "line-opacity": 0.7 },
          });

          // Primary Route Line
          map.addLayer({
            id: lineLayerId,
            type: "line",
            source: sourceId,
            layout: { "line-join": "round", "line-cap": "round" },
            paint: { "line-color": color, "line-width": 3.8, "line-opacity": 0.95 },
          });

          map.on("click", lineLayerId, () => {
            if (onSelectVehicle) onSelectVehicle(r.vehicle);
          });
          map.on("mouseenter", lineLayerId, () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", lineLayerId, () => {
            map.getCanvas().style.cursor = "";
          });
        }

        // Check for Disconnected / Broken Segments (Parts 15-18)
        const brokenSegments = (r.segments || []).filter((s) => s.connected === false);
        brokenSegments.forEach((seg, sIdx) => {
          const brokenSrcId = `broken-src-${vId}-${sIdx}`;
          const brokenLayerId = `broken-line-${vId}-${sIdx}`;

          if (map.getLayer(brokenLayerId)) map.removeLayer(brokenLayerId);
          if (map.getSource(brokenSrcId)) map.removeSource(brokenSrcId);

          if (
            seg.from_coords &&
            Array.isArray(seg.from_coords) &&
            seg.from_coords.length >= 2 &&
            seg.to_coords &&
            Array.isArray(seg.to_coords) &&
            seg.to_coords.length >= 2
          ) {
            map.addSource(brokenSrcId, {
              type: "geojson",
              data: {
                type: "Feature",
                properties: {
                  vehicle: vId,
                  reason: seg.error_reason,
                },
                geometry: {
                  type: "LineString",
                  coordinates: [seg.from_coords, seg.to_coords],
                },
              },
            });

            // Dashed Warning Line for Broken Connection
            map.addLayer({
              id: brokenLayerId,
              type: "line",
              source: brokenSrcId,
              layout: { "line-join": "round", "line-cap": "round" },
              paint: {
                "line-color": "#ef4444",
                "line-width": 3.5,
                "line-dasharray": [2, 4],
                "line-opacity": 0.9,
              },
            });

            // Warning Marker at mid-point
            const midLon = (seg.from_coords[0] + seg.to_coords[0]) / 2;
            const midLat = (seg.from_coords[1] + seg.to_coords[1]) / 2;

            const warnEl = document.createElement("div");
            warnEl.className = "broken-segment-marker";
            warnEl.innerHTML = `<span>⚠</span>`;

            const warnPopup = new maplibregl.Popup({ offset: 15, closeButton: true }).setHTML(`
              <div class="map-popup broken-segment-popup">
                <div class="popup-kicker" style="color: #ef4444">⚠ ROUTE CONNECTION BROKEN</div>
                <div class="popup-title">Vehicle ${vId}: ${seg.from_name} → ${seg.to_name}</div>
                <div class="popup-divider"></div>
                <div class="popup-row"><span>Error Reason:</span></div>
                <div class="broken-reason-text">${seg.error_reason || "Could not find a drivable road connection."}</div>
              </div>
            `);

            const warnMarker = new maplibregl.Marker({ element: warnEl, anchor: "center" })
              .setLngLat([midLon, midLat])
              .setPopup(warnPopup)
              .addTo(map);

            brokenMarkersRef.current.push(warnMarker);
          }
        });
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
  }, [solution, scenario, mapLoaded]);

  // Handle vehicle route highlight on hover
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !solution?.routes) return;

    solution.routes.forEach((r) => {
      const lineLayerId = `route-line-${r.vehicle}`;
      const casingLayerId = `route-casing-${r.vehicle}`;
      if (!map.getLayer(lineLayerId)) return;

      const isHovered = hoveredVehicle === r.vehicle;
      const hasHover = hoveredVehicle !== null && hoveredVehicle !== undefined;

      const targetWidth = isHovered ? 6.5 : hasHover ? 2.5 : 3.8;
      const targetOpacity = isHovered ? 1.0 : hasHover ? 0.35 : 0.95;
      const casingWidth = isHovered ? 9.5 : 6.0;

      map.setPaintProperty(lineLayerId, "line-width", targetWidth);
      map.setPaintProperty(lineLayerId, "line-opacity", targetOpacity);
      if (map.getLayer(casingLayerId)) {
        map.setPaintProperty(casingLayerId, "line-width", casingWidth);
      }
    });
  }, [hoveredVehicle, mapLoaded, solution]);

  // Active Vehicle Route for HUD progress list
  const activeRouteData = useMemo(() => {
    if (!solution?.routes || solution.routes.length === 0) return null;
    if (activeVehFilter !== "all") {
      return solution.routes.find((r) => r.vehicle === Number(activeVehFilter)) || solution.routes[0];
    }
    if (hoveredVehicle !== null && hoveredVehicle !== undefined) {
      return solution.routes.find((r) => r.vehicle === hoveredVehicle) || solution.routes[0];
    }
    return solution.routes[0];
  }, [solution, activeVehFilter, hoveredVehicle]);

  const activeWaypointsMeta = useMemo(() => {
    if (!activeRouteData) return [];
    const rMeta = routeWaypoints.find((rw) => rw.vehicle === activeRouteData.vehicle);
    if (!rMeta) return [];

    const curF = animProgress / 100;
    return rMeta.waypoints.map((wp, idx) => {
      const isVisited = curF >= wp.fraction;
      const isCurrent =
        !isVisited &&
        (idx === 0 || curF >= (rMeta.waypoints[idx - 1]?.fraction ?? 0));
      return {
        ...wp,
        isVisited,
        isCurrent,
      };
    });
  }, [activeRouteData, routeWaypoints, animProgress]);

  // Overall totals
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

  const completedRoutesCount = useMemo(() => {
    if (animProgress >= 99) return solution?.routes?.length || 0;
    return 0;
  }, [animProgress, solution]);

  const handleResetSimulation = () => {
    if (onToggleSim) onToggleSim(false);
    setAnimProgress(0);
    if (onSetSimStep) onSetSimStep(0);
    setDispatchSummaryOpen(false);
  };

  return (
    <div className="relief-map-wrapper">
      {/* MapLibre Canvas Container */}
      <div ref={mapContainerRef} className="maplibre-container" />

      {/* Satellite / Hybrid HUD Header */}
      <div className="map-hud-overlay">
        <div className="hud-badge">
          <Compass size={13} color="var(--amber)" />
          <span>MAPLIBRE GL JS + MAPTILER HYBRID SATELLITE</span>
        </div>
        <div className="hud-scenario-info">
          <b>{scenario?.name}</b> • Depot: {scenario?.depot_name}
        </div>
      </div>

      {/* TACTICAL DISPATCH SIMULATION HUD (Parts 6-10, 22-24) */}
      <div className="dispatch-hud-panel">
        <div className="hud-panel-header">
          <div className="hud-panel-title">
            <Truck size={14} color="var(--amber)" />
            <span>DISPATCH SIMULATION</span>
          </div>
          <div className="hud-status-tag">
            {animProgress >= 100
              ? "COMPLETED"
              : simPlaying
              ? "EN ROUTE"
              : animProgress > 0
              ? "PAUSED"
              : "READY"}
          </div>
        </div>

        {/* Simulation Controls */}
        <div className="hud-sim-controls">
          <button
            className={`hud-ctrl-btn primary ${simPlaying ? "playing" : ""}`}
            onClick={() => {
              if (animProgress >= 100) setAnimProgress(0);
              if (onToggleSim) onToggleSim(!simPlaying);
            }}
            title={simPlaying ? "Pause simulation" : "Start dispatch simulation"}
          >
            {simPlaying ? <Pause size={13} /> : <Play size={13} />}
            <span>{simPlaying ? "PAUSE" : "SIMULATE DISPATCH"}</span>
          </button>

          <button
            className="hud-ctrl-btn"
            onClick={handleResetSimulation}
            title="Reset simulation to depot start"
          >
            <RotateCcw size={12} />
            <span>RESET</span>
          </button>

          <button
            className="hud-ctrl-btn speed-btn"
            onClick={() => {
              const next = simSpeed === 1 ? 2 : simSpeed === 2 ? 4 : 1;
              if (onSetSimSpeed) onSetSimSpeed(next);
            }}
            title="Cycle simulation speed"
          >
            <FastForward size={12} />
            <span>{simSpeed}x</span>
          </button>
        </div>

        {/* Scrubber Slider */}
        <div className="hud-scrubber-row">
          <input
            type="range"
            min="0"
            max="100"
            step="0.5"
            value={animProgress}
            onInput={(e) => {
              const val = Number(e.target.value);
              setAnimProgress(val);
              if (val >= 99.5) {
                if (onToggleSim) onToggleSim(false);
                setDispatchSummaryOpen(true);
              }
              if (onSetSimStep && maxRouteLength > 1) {
                onSetSimStep(Math.round((val / 100) * (maxRouteLength - 1)));
              }
            }}
            onChange={(e) => {
              const val = Number(e.target.value);
              setAnimProgress(val);
              if (val >= 99.5) {
                if (onToggleSim) onToggleSim(false);
                setDispatchSummaryOpen(true);
              }
              if (onSetSimStep && maxRouteLength > 1) {
                onSetSimStep(Math.round((val / 100) * (maxRouteLength - 1)));
              }
            }}
            className="hud-slider"
          />
          <span className="hud-scrubber-pct">{Math.round(animProgress)}%</span>
        </div>

        {/* Vehicle Isolation Selector */}
        {solution?.routes && solution.routes.length > 1 && (
          <div className="hud-vehicle-selector">
            <span className="selector-kicker">SIMULATE:</span>
            <button
              className={`hud-pill ${activeVehFilter === "all" ? "active" : ""}`}
              onClick={() => setActiveVehFilter("all")}
            >
              ALL FLEET ({solution.routes.length})
            </button>
            {solution.routes.map((r, i) => (
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
              </button>
            ))}
          </div>
        )}

        {/* Stop Progress Progression Drawer (Part 10) */}
        {activeRouteData && (
          <div className="hud-stop-progress">
            <div className="stop-progress-header">
              <span>VEHICLE {activeRouteData.vehicle} STOPS PROGRESS</span>
              <span className="stop-dist-stat">
                Road: <b>{activeRouteData.road_distance_km ? `${activeRouteData.road_distance_km} km` : "—"}</b>
                {" • "}
                Est: <b>{activeRouteData.road_duration_formatted || "—"}</b>
              </span>
            </div>

            <div className="stop-progress-chain">
              {activeWaypointsMeta.map((wp, idx) => (
                <div
                  key={idx}
                  className={`stop-chain-item ${
                    wp.isVisited ? "visited" : wp.isCurrent ? "current" : "upcoming"
                  }`}
                >
                  <div className="stop-chain-node">
                    {wp.isVisited ? (
                      <Check size={10} color="#fff" />
                    ) : wp.isCurrent ? (
                      <div className="current-pulse" />
                    ) : (
                      <span className="stop-dot" />
                    )}
                  </div>
                  <div className="stop-chain-label">
                    <span className="stop-name">{wp.name}</span>
                    {wp.isVisited && <span className="stop-status-tag done">✓ VISITED</span>}
                    {wp.isCurrent && <span className="stop-status-tag current">→ CURRENT</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* DISPATCH COMPLETE SUMMARY MODAL / BANNER (Part 24) */}
      {dispatchSummaryOpen && (
        <div className="dispatch-summary-banner">
          <div className="summary-banner-top">
            <div className="summary-title-group">
              <CheckCircle2 size={20} color="var(--green)" />
              <div>
                <h4>DISPATCH SIMULATION COMPLETE</h4>
                <p>All emergency fleet vehicles reached their final depot destinations safely.</p>
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
            </div>
            <div className="summary-stat-box">
              <span className="stat-label">ROUTES COMPLETED</span>
              <span className="stat-val" style={{ color: "var(--green)" }}>
                {completedRoutesCount} / {solution?.routes?.length || 0}
              </span>
            </div>
            <div className="summary-stat-box">
              <span className="stat-label">TOTAL ROAD DISTANCE</span>
              <span className="stat-val">{totalRoadDistanceKm.toFixed(1)} km</span>
              <span className="stat-sub">Real street network geometry</span>
            </div>
            <div className="summary-stat-box">
              <span className="stat-label">TOTAL TRAVEL DURATION</span>
              <span className="stat-val">{formatTotalTime(totalRoadDurationSeconds)}</span>
              <span className="stat-sub">Estimated travel time</span>
            </div>
          </div>

          <div className="summary-metric-note">
            <Info size={13} color="var(--amber)" />
            <span>
              <b>SEPARATION NOTE:</b> Official CVRPLIB optimization distance remains strictly{" "}
              <b>{solution?.metrics?.total_distance || 0}</b> for academic scoring and judging.
            </span>
          </div>
        </div>
      )}

      {/* MapTiler API Key Notice if key missing */}
      {(!apiKey || styleError) && (
        <div className="maptiler-notice-banner">
          <Info size={15} />
          <span>
            MapTiler Key Not Configured: Add <code>VITE_MAPTILER_API_KEY=your_key</code> in{" "}
            <code>frontend/.env</code> for high-resolution satellite imagery tiles. Operating with
            vector basemap fallback.
          </span>
        </div>
      )}
    </div>
  );
}

