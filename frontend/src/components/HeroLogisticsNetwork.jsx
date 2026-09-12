import React, { useRef, useEffect } from "react";

/**
 * HeroLogisticsNetwork
 * High-performance cinematic operating logistics map:
 * - Unified Continuous Logistics Environment spanning Hero -> Scenarios -> Instance -> KPIs -> Judge Scorecard
 * - 9-Scene Cinematic Camera Choreography with smootherstep interpolation
 * - Topographical elevation contours & spatial coordinates
 * - Central Relief Depot with pulsing concentric radar waves
 * - Multi-tier logistics nodes:
 *     Tier 1: Macro & Regional Hubs (Hero)
 *     Tier 2: Scenario Regional Command Hubs (Jaipur, Delhi, Mumbai)
 *     Tier 3: CVRP Instance & KPI Telemetry Corridors
 *     Tier 4: Official Judge Scorecard Audit Network
 * - Moving relief vehicle convoys with glowing heads & luminous comet tails
 * - Scenario-reactive visual illumination (Jaipur Flood, Delhi Emergency, Mumbai Cyclone)
 * - Instance-switching algorithmic pulse ripple (A-n32-k5, A-n33-k5, B-n31-k5)
 * - Smooth scroll-driven parallax depth
 * - 60 FPS HTML5 Canvas 2D, high-DPI scaling, zero DOM overhead
 * - prefers-reduced-motion compliance
 */

// 5th-order smootherstep for cinematic camera ease-in-out (zero 1st & 2nd derivatives at endpoints)
function smootherstep(t) {
  const x = Math.max(0, Math.min(1, t));
  return x * x * x * (x * (x * 6 - 15) + 10);
}

// Cubic Bézier evaluation
function getBezierPoint(p0, cp1, cp2, p1, t) {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const mt3 = mt2 * mt;
  const t2 = t * t;
  const t3 = t2 * t;

  return {
    x: mt3 * p0.x + 3 * mt2 * t * cp1.x + 3 * mt * t2 * cp2.x + t3 * p1.x,
    y: mt3 * p0.y + 3 * mt2 * t * cp1.y + 3 * mt * t2 * cp2.y + t3 * p1.y,
  };
}

// Cubic Bézier heading tangent angle
function getBezierTangent(p0, cp1, cp2, p1, t) {
  const mt = 1 - t;
  const mt2 = mt * mt;
  const t2 = t * t;

  const dx =
    3 * mt2 * (cp1.x - p0.x) +
    6 * mt * t * (cp2.x - cp1.x) +
    3 * t2 * (p1.x - cp2.x);
  const dy =
    3 * mt2 * (cp1.y - p0.y) +
    6 * mt * t * (cp2.y - cp1.y) +
    3 * t2 * (p1.y - cp2.y);

  return Math.atan2(dy, dx);
}

export default function HeroLogisticsNetwork({
  scenario,
  selectedInstance,
  simPlaying = false,
  simSpeed = 1,
  animProgress = 0,
  theme = "dark",
}) {
  const canvasRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const lastTimeRef = useRef(performance.now());
  const scrollYRef = useRef(0);
  const lastInstanceRef = useRef(selectedInstance);

  // Animation timeline state
  const stateRef = useRef({
    cycleTime: 0,
    cycleDuration: 32, // 32 seconds per full cinematic cycle
    camX: 1020,
    camY: 950,
    camZoom: 0.54,
    currentParallax: 0,
    nodeRipples: {},
    instancePulseTime: -999,
  });

  // Track scroll for subtle natural parallax
  useEffect(() => {
    const onScroll = () => {
      scrollYRef.current = window.scrollY || window.pageYOffset || 0;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Trigger pulse ripple when instance switches
  useEffect(() => {
    if (lastInstanceRef.current && lastInstanceRef.current !== selectedInstance) {
      stateRef.current.instancePulseTime = stateRef.current.cycleTime;
    }
    lastInstanceRef.current = selectedInstance;
  }, [selectedInstance]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    let width = 0;
    let height = 0;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      width = rect.width;
      height = rect.height;

      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);

      ctx.resetTransform();
      ctx.scale(dpr, dpr);
    };

    resize();
    const resizeObserver = new ResizeObserver(resize);
    if (canvas.parentElement) {
      resizeObserver.observe(canvas.parentElement);
    }

    const isLight = theme === "light";

    const colors = {
      bgBase: isLight ? "#f8fafc" : "#030611",
      bgGradEdge: isLight ? "#e2e8f0" : "#020409",
      gridLines: isLight ? "rgba(100, 116, 139, 0.07)" : "rgba(56, 189, 248, 0.05)",
      contourLines: isLight ? "rgba(71, 85, 105, 0.09)" : "rgba(99, 102, 241, 0.08)",
      sectorDividers: isLight ? "rgba(100, 116, 139, 0.12)" : "rgba(148, 163, 184, 0.10)",
      depotCore: "#f59e0b",
      depotRing: isLight ? "rgba(217, 119, 6, 0.85)" : "rgba(245, 158, 11, 0.85)",
      depotGlow: isLight ? "rgba(217, 119, 6, 0.22)" : "rgba(245, 158, 11, 0.32)",
      depotRipple: isLight ? "rgba(217, 119, 6, 0.40)" : "rgba(245, 158, 11, 0.50)",
      baseRoute: isLight ? "rgba(59, 130, 246, 0.15)" : "rgba(56, 189, 248, 0.13)",
      macroRoute: isLight ? "rgba(148, 163, 184, 0.20)" : "rgba(99, 102, 241, 0.15)",
      nodeLabelBg: isLight ? "rgba(255, 255, 255, 0.90)" : "rgba(6, 10, 20, 0.85)",
      nodeLabelBorder: isLight ? "rgba(203, 213, 225, 0.8)" : "rgba(56, 189, 248, 0.25)",
      nodeLabelText: isLight ? "#1e293b" : "#e2e8f0",
      nodeLabelSub: isLight ? "#64748b" : "#94a3b8",
    };

    // Canonical Multi-Tier World Coordinate System (X: 0 - 2040, Y: 0 - 2100)
    // Tier 1: Hero Macro Network (Y: 120 - 500)
    // Tier 2: Relief Scenarios (Y: 520 - 800)
    // Tier 3: Instance & KPI Corridors (Y: 820 - 1300)
    // Tier 4: Judge Scorecard Network (Y: 1320 - 1850)

    const depot = {
      x: 1020,
      y: 460,
      name: scenario?.depot_name || "CENTRAL RELIEF WAREHOUSE",
    };

    // Scenario reactivity identification
    const scenName = (scenario?.name || "").toLowerCase();
    const isJaipur = scenName.includes("jaipur");
    const isDelhi = scenName.includes("delhi");
    const isMumbai = scenName.includes("mumbai");

    // Unified Multi-Tier Nodes across all sections
    const nodes = [
      // --- TIER 1: HERO MACRO HUBS ---
      {
        id: "R1",
        name: "R1: NORTH-EAST SECTOR",
        x: 1520,
        y: 250,
        color: "#38bdf8",
        demand: "42u",
        tier: 1,
      },
      {
        id: "R2",
        name: "R2: NORTH-WEST SECTOR",
        x: 520,
        y: 260,
        color: "#818cf8",
        demand: "53u",
        tier: 1,
      },
      {
        id: "D1",
        name: "EASTERN COMMUNITY DROP",
        x: 1760,
        y: 420,
        color: "#38bdf8",
        demand: "24u",
        isFeeder: true,
        tier: 1,
      },
      {
        id: "D2",
        name: "NORTHERN LOGISTICS POST",
        x: 1060,
        y: 130,
        color: "#818cf8",
        demand: "30u",
        isFeeder: true,
        tier: 1,
      },

      // --- TIER 2: RELIEF SCENARIOS REGIONAL HUBS ---
      {
        id: "SCEN_JAIPUR",
        name: "JAIPUR REGIONAL COMMAND",
        x: 500,
        y: 660,
        color: "#f59e0b",
        demand: isJaipur ? "12 LOCATIONS (ACTIVE)" : "JAIPUR HUB",
        isScenarioHub: true,
        key: "jaipur",
        active: isJaipur,
        tier: 2,
      },
      {
        id: "SCEN_DELHI",
        name: "DELHI EMERGENCY COMMAND",
        x: 1020,
        y: 700,
        color: "#38bdf8",
        demand: isDelhi ? "10 LOCATIONS (ACTIVE)" : "DELHI HUB",
        isScenarioHub: true,
        key: "delhi",
        active: isDelhi,
        tier: 2,
      },
      {
        id: "SCEN_MUMBAI",
        name: "MUMBAI MARITIME PORT",
        x: 1540,
        y: 670,
        color: "#10b981",
        demand: isMumbai ? "8 LOCATIONS (ACTIVE)" : "MUMBAI HUB",
        isScenarioHub: true,
        key: "mumbai",
        active: isMumbai,
        tier: 2,
      },

      // --- TIER 3: INSTANCE & KPI TELEMETRY NODES ---
      {
        id: "INST_HUB",
        name: "CVRP BENCHMARK GATEWAY",
        x: 1020,
        y: 920,
        color: "#a855f7",
        demand: selectedInstance || "A-n32-k5",
        isJunction: true,
        tier: 3,
      },
      {
        id: "KPI_DEMAND",
        name: "DEMAND MATRIX NODE",
        x: 420,
        y: 1140,
        color: "#38bdf8",
        demand: "SUPPLY DEMAND",
        isKpiNode: true,
        tier: 3,
      },
      {
        id: "KPI_FAIR",
        name: "EQUITY DISPATCH CENTER",
        x: 1020,
        y: 1180,
        color: "#f43f5e",
        demand: "MAX-MIN FAIR",
        isKpiNode: true,
        tier: 3,
      },
      {
        id: "KPI_FLEET",
        name: "FLEET TRANSPONDER HUB",
        x: 1620,
        y: 1140,
        color: "#06b6d4",
        demand: "FLEET SYNC",
        isKpiNode: true,
        tier: 3,
      },

      // --- TIER 4: JUDGE SCORECARD AUDIT NETWORK ---
      {
        id: "R3",
        name: "R3: SOUTH-WEST SECTOR",
        x: 480,
        y: 1500,
        color: "#34d399",
        demand: "108u",
        tier: 4,
      },
      {
        id: "R4",
        name: "R4: SOUTH-EAST SECTOR",
        x: 1560,
        y: 1520,
        color: "#fbbf24",
        demand: "143u",
        tier: 4,
      },
      {
        id: "SCORECARD_CORE",
        name: "OFFICIAL BENCHMARK AUDIT HUB",
        x: 1020,
        y: 1560,
        color: "#818cf8",
        demand: "100 PTS TOTAL",
        isScorecardCore: true,
        tier: 4,
      },
      {
        id: "D3",
        name: "WESTERN STAGING HUB",
        x: 240,
        y: 1580,
        color: "#34d399",
        demand: "35u",
        isFeeder: true,
        tier: 4,
      },
      {
        id: "D4",
        name: "SOUTHERN DEFENSE OUTPOST",
        x: 1800,
        y: 1600,
        color: "#fbbf24",
        demand: "40u",
        isFeeder: true,
        tier: 4,
      },
    ];

    // Wide Macro Geographic Hubs (visible during wide surveillance view)
    const macroNodes = [
      { id: "M_N", name: "NORTH REGION", x: 1080, y: -120 },
      { id: "M_S", name: "SOUTH REGION", x: 980, y: 1960 },
      { id: "M_W", name: "WEST REGION", x: 60, y: 700 },
      { id: "M_E", name: "EAST REGION", x: 1980, y: 720 },
    ];

    // Arterial Corridors (Cubic Béziers connecting all 4 Tiers)
    const routes = [
      // Route 0: Depot -> R1 (North-East Hero Corridor)
      {
        id: "R0",
        p0: depot,
        cp1: { x: 1180, y: 360 },
        cp2: { x: 1360, y: 300 },
        p1: nodes[0], // R1
        color: "#38bdf8",
        actTime: 9.6,
      },
      // Route 1: Depot -> R2 (North-West Hero Corridor)
      {
        id: "R1",
        p0: depot,
        cp1: { x: 840, y: 380 },
        cp2: { x: 660, y: 320 },
        p1: nodes[1], // R2
        color: "#818cf8",
        actTime: 10.4,
      },
      // Route 2: Depot -> SCEN_JAIPUR (Relief Scenarios West)
      {
        id: "R2_JAIPUR",
        p0: depot,
        cp1: { x: 800, y: 520 },
        cp2: { x: 620, y: 580 },
        p1: nodes[4], // SCEN_JAIPUR
        color: isJaipur ? "#f59e0b" : "rgba(245, 158, 11, 0.45)",
        actTime: 11.0,
        glowBoost: isJaipur,
      },
      // Route 3: Depot -> SCEN_DELHI (Relief Scenarios Central)
      {
        id: "R3_DELHI",
        p0: depot,
        cp1: { x: 1000, y: 540 },
        cp2: { x: 1040, y: 620 },
        p1: nodes[5], // SCEN_DELHI
        color: isDelhi ? "#38bdf8" : "rgba(56, 189, 248, 0.45)",
        actTime: 11.5,
        glowBoost: isDelhi,
      },
      // Route 4: Depot -> SCEN_MUMBAI (Relief Scenarios East)
      {
        id: "R4_MUMBAI",
        p0: depot,
        cp1: { x: 1220, y: 520 },
        cp2: { x: 1420, y: 580 },
        p1: nodes[6], // SCEN_MUMBAI
        color: isMumbai ? "#10b981" : "rgba(16, 185, 129, 0.45)",
        actTime: 12.0,
        glowBoost: isMumbai,
      },
      // Route 5: Central Depot -> Instance Backbone Gateway
      {
        id: "R5_INST",
        p0: depot,
        cp1: { x: 1040, y: 640 },
        cp2: { x: 1000, y: 780 },
        p1: nodes[7], // INST_HUB
        color: "#a855f7",
        actTime: 12.5,
      },
      // Route 6: Instance Gateway -> KPI Demand Node
      {
        id: "R6_KPI_DEMAND",
        p0: nodes[7], // INST_HUB
        cp1: { x: 800, y: 980 },
        cp2: { x: 560, y: 1060 },
        p1: nodes[8], // KPI_DEMAND
        color: "#38bdf8",
        actTime: 13.0,
      },
      // Route 7: Instance Gateway -> KPI Fairness Engine
      {
        id: "R7_KPI_FAIR",
        p0: nodes[7], // INST_HUB
        cp1: { x: 1010, y: 1020 },
        cp2: { x: 1030, y: 1100 },
        p1: nodes[9], // KPI_FAIR
        color: "#f43f5e",
        actTime: 13.5,
      },
      // Route 8: Instance Gateway -> KPI Fleet Hub
      {
        id: "R8_KPI_FLEET",
        p0: nodes[7], // INST_HUB
        cp1: { x: 1240, y: 980 },
        cp2: { x: 1480, y: 1060 },
        p1: nodes[10], // KPI_FLEET
        color: "#06b6d4",
        actTime: 14.0,
      },
      // Route 9: KPI Demand -> Scorecard R3 (South-West)
      {
        id: "R9_SC_R3",
        p0: nodes[8], // KPI_DEMAND
        cp1: { x: 400, y: 1260 },
        cp2: { x: 440, y: 1380 },
        p1: nodes[11], // R3
        color: "#34d399",
        actTime: 14.5,
      },
      // Route 10: KPI Fairness -> Scorecard Audit Core
      {
        id: "R10_SC_CORE",
        p0: nodes[9], // KPI_FAIR
        cp1: { x: 1010, y: 1320 },
        cp2: { x: 1030, y: 1440 },
        p1: nodes[13], // SCORECARD_CORE
        color: "#818cf8",
        actTime: 15.0,
      },
      // Route 11: KPI Fleet -> Scorecard R4 (South-East)
      {
        id: "R11_SC_R4",
        p0: nodes[10], // KPI_FLEET
        cp1: { x: 1640, y: 1260 },
        cp2: { x: 1600, y: 1380 },
        p1: nodes[12], // R4
        color: "#fbbf24",
        actTime: 15.5,
      },
      // Route 12: R1 -> D1 (Eastern Outpost Feeder)
      {
        id: "R12_D1",
        p0: nodes[0],
        cp1: { x: 1620, y: 300 },
        cp2: { x: 1710, y: 360 },
        p1: nodes[2], // D1
        color: "#38bdf8",
        actTime: 16.0,
      },
      // Route 13: Depot -> D2 (Northern Feeder)
      {
        id: "R13_D2",
        p0: depot,
        cp1: { x: 1040, y: 340 },
        cp2: { x: 1050, y: 220 },
        p1: nodes[3], // D2
        color: "#818cf8",
        actTime: 16.5,
      },
      // Route 14: R3 -> D3 (Western Scorecard Perimeter Feeder)
      {
        id: "R14_D3",
        p0: nodes[11], // R3
        cp1: { x: 380, y: 1530 },
        cp2: { x: 300, y: 1560 },
        p1: nodes[14], // D3
        color: "#34d399",
        actTime: 17.0,
      },
      // Route 15: R4 -> D4 (Southern Scorecard Perimeter Feeder)
      {
        id: "R15_D4",
        p0: nodes[12], // R4
        cp1: { x: 1660, y: 1550 },
        cp2: { x: 1740, y: 1580 },
        p1: nodes[15], // D4
        color: "#fbbf24",
        actTime: 17.5,
      },
      // Route 16: Lateral Corridor sweeping behind KPI summary strip
      {
        id: "R16_KPI_LATERAL",
        p0: nodes[8], // KPI_DEMAND
        cp1: { x: 720, y: 1120 },
        cp2: { x: 1320, y: 1120 },
        p1: nodes[10], // KPI_FLEET
        color: "rgba(56, 189, 248, 0.25)",
        actTime: 18.0,
      },
    ];

    // Wide Macro National Links
    const macroRoutes = [
      { p0: macroNodes[0], p1: depot },
      { p0: macroNodes[1], p1: nodes[13] }, // Macro S -> Scorecard Core
      { p0: macroNodes[2], p1: nodes[1] },  // Macro W -> R2
      { p0: macroNodes[3], p1: nodes[0] },  // Macro E -> R1
      { p0: macroNodes[2], p1: nodes[11] }, // Macro W -> R3
      { p0: macroNodes[3], p1: nodes[12] }, // Macro E -> R4
    ];

    // Render loop
    const render = (now) => {
      const dt = Math.min((now - lastTimeRef.current) / 1000, 0.1);
      lastTimeRef.current = now;

      const state = stateRef.current;
      const speedMultiplier = simPlaying ? Math.max(1.7, 1.7 * simSpeed) : 1.0;
      state.cycleTime = (state.cycleTime + dt * speedMultiplier) % state.cycleDuration;
      const ct = state.cycleTime;

      // Smooth scroll parallax damping (shift world camera Y smoothly with scroll)
      const targetParallax = scrollYRef.current * 0.16;
      state.currentParallax += (targetParallax - state.currentParallax) * 0.08;

      // ========================================================
      // 9-SCENE CINEMATIC CAMERA CHOREOGRAPHY
      // ========================================================
      let targetCamX = 1020;
      let targetCamY = 950;
      let targetZoom = 0.54;
      let sceneLabel = "GLOBAL RELIEF NETWORK // MACRO MULTI-REGION VIEW";

      // Compute vehicle V1 position for following
      const v1Time = Math.max(0, Math.min(1, (ct - 12.5) / 6.0));
      const v1Pos = getBezierPoint(routes[0].p0, routes[0].cp1, routes[0].cp2, routes[0].p1, v1Time);
      const v1Heading = getBezierTangent(routes[0].p0, routes[0].cp1, routes[0].cp2, routes[0].p1, v1Time);

      // Compute vehicle V3 position for Sector 3 tracking
      const v3Time = Math.max(0, Math.min(1, (ct - 19.0) / 5.0));
      const v3Pos = getBezierPoint(routes[9].p0, routes[9].cp1, routes[9].cp2, routes[9].p1, v3Time);

      if (ct < 5.0) {
        // SCENE 1: Wide geographic command center overview
        targetCamX = 1020;
        targetCamY = 950;
        targetZoom = 0.54;
        sceneLabel = "WIDE RELIEF LOGISTICS NETWORK // MULTI-REGION SURVEILLANCE";
      } else if (ct < 9.0) {
        // SCENE 2: Smooth Zoom toward active region
        const prog = smootherstep((ct - 5.0) / 4.0);
        targetCamX = 1020 + (depot.x - 1020) * prog;
        targetCamY = 950 + (depot.y - 950) * prog;
        targetZoom = 0.54 + (1.10 - 0.54) * prog;
        sceneLabel = `APPROACHING TARGET REGION // ${scenario?.name ? scenario.name.toUpperCase() : "JAIPUR FLOOD RELIEF SECTOR"}`;
      } else if (ct < 13.0) {
        // SCENE 3: Focus on Central Relief Depot & Sequential Corridor Priming
        targetCamX = depot.x;
        targetCamY = depot.y;
        targetZoom = 1.25;
        sceneLabel = "CENTRAL RELIEF DEPOT // CORRIDOR PRIMING & CONCENTRIC PULSE";
      } else if (ct < 19.0) {
        // SCENE 4: Camera Locks & Follows Vehicle V1 along Route
        const followProg = smootherstep((ct - 13.0) / 1.2);
        const leadX = Math.cos(v1Heading) * 45;
        const leadY = Math.sin(v1Heading) * 45;
        const vTargetX = v1Pos.x + leadX;
        const vTargetY = v1Pos.y + leadY;

        targetCamX = depot.x + (vTargetX - depot.x) * followProg;
        targetCamY = depot.y + (vTargetY - depot.y) * followProg;
        targetZoom = 1.25 + (1.50 - 1.25) * followProg;
        sceneLabel = `FOLLOWING CONVOY V1 // EN ROUTE TO NORTH-EAST SECTOR [${Math.round(v1Time * 100)}%]`;

        if (v1Time >= 0.95 && !state.nodeRipples["R1"]) {
          state.nodeRipples["R1"] = 1.0;
        }
      } else if (ct < 24.0) {
        // SCENE 5 & 6: Smooth Pan & Transition down to Sector 3 (South-West Base & Scorecards)
        const transProg = smootherstep((ct - 19.0) / 5.0);
        targetCamX = nodes[0].x + (v3Pos.x - nodes[0].x) * transProg;
        targetCamY = nodes[0].y + (v3Pos.y - nodes[0].y) * transProg;
        targetZoom = 1.50 + (1.20 - 1.50) * Math.sin(transProg * Math.PI) + (1.35 - 1.50) * transProg;
        sceneLabel = `MONITORING SECTOR 3 DISPATCH // SOUTH-WEST COMMUNITY DISTRIBUTION [${Math.round(v3Time * 100)}%]`;

        if (v3Time >= 0.95 && !state.nodeRipples["R3"]) {
          state.nodeRipples["R3"] = 1.0;
        }
      } else if (ct < 29.0) {
        // SCENE 7 & 8: Pull back to Full Multi-Tier Command Center Overview
        const outProg = smootherstep((ct - 24.0) / 5.0);
        targetCamX = nodes[11].x + (1020 - nodes[11].x) * outProg;
        targetCamY = nodes[11].y + (950 - nodes[11].y) * outProg;
        targetZoom = 1.35 + (0.54 - 1.35) * outProg;
        sceneLabel = "ALL SECTORS SYNCHRONIZED // EQUITABLE RELIEF FLEET IN FLIGHT";
      } else {
        // SCENE 9: Settle & Seamless Continuous Loop Transition
        targetCamX = 1020;
        targetCamY = 950;
        targetZoom = 0.54;
        sceneLabel = "WIDE RELIEF LOGISTICS NETWORK // MULTI-REGION SURVEILLANCE";
      }

      // Smooth camera filter (prevents any micro-jitter)
      state.camX += (targetCamX - state.camX) * 0.10;
      state.camY += (targetCamY - state.camY) * 0.10;
      state.camZoom += (targetZoom - state.camZoom) * 0.10;

      // Coordinate Transform: World -> Screen with Parallax
      const screenCenterX = width * 0.50;
      const screenCenterY = height * 0.45;

      const toScreen = (wx, wy, parallaxFactor = 1.0) => ({
        x: (wx - state.camX) * state.camZoom + screenCenterX,
        y: (wy - (state.camY - state.currentParallax * parallaxFactor)) * state.camZoom + screenCenterY,
      });

      // Clear & draw dark canvas base
      const bgGrad = ctx.createRadialGradient(
        screenCenterX,
        screenCenterY,
        40 * state.camZoom,
        screenCenterX,
        screenCenterY,
        Math.max(width, height) * 1.1
      );
      bgGrad.addColorStop(0, colors.bgBase);
      bgGrad.addColorStop(1, colors.bgGradEdge);
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // ========================================================
      // 1. TOPOGRAPHICAL ELEVATION CONTOURS (BACKGROUND LAYER)
      // ========================================================
      ctx.save();
      ctx.strokeStyle = colors.contourLines;
      ctx.lineWidth = 1.0 * state.camZoom;

      const contourSplines = [
        // Hero & Scenario contours
        [
          { x: 100, y: 350 },
          { x: 600, y: 150 },
          { x: 1200, y: 480 },
          { x: 1950, y: 280 },
        ],
        [
          { x: 50, y: 780 },
          { x: 680, y: 620 },
          { x: 1380, y: 740 },
          { x: 1980, y: 580 },
        ],
        // KPI & Instance contours
        [
          { x: 80, y: 1100 },
          { x: 740, y: 980 },
          { x: 1320, y: 1160 },
          { x: 1950, y: 1040 },
        ],
        // Judge Scorecard contours
        [
          { x: 60, y: 1480 },
          { x: 620, y: 1680 },
          { x: 1360, y: 1420 },
          { x: 1980, y: 1640 },
        ],
        [
          { x: 100, y: 1820 },
          { x: 800, y: 1720 },
          { x: 1280, y: 1880 },
          { x: 1900, y: 1780 },
        ],
      ];

      contourSplines.forEach((c) => {
        const s0 = toScreen(c[0].x, c[0].y, 0.7);
        const s1 = toScreen(c[1].x, c[1].y, 0.7);
        const s2 = toScreen(c[2].x, c[2].y, 0.7);
        const s3 = toScreen(c[3].x, c[3].y, 0.7);

        ctx.beginPath();
        ctx.moveTo(s0.x, s0.y);
        ctx.bezierCurveTo(s1.x, s1.y, s2.x, s2.y, s3.x, s3.y);
        ctx.stroke();
      });

      // ========================================================
      // 2. SPATIAL SECTOR GRID (Screen-aligned for crispness)
      // ========================================================
      ctx.strokeStyle = colors.gridLines;
      ctx.lineWidth = 0.8;
      const gridSize = Math.max(48, Math.round(width / 26));
      ctx.beginPath();
      for (let gx = gridSize; gx < width; gx += gridSize) {
        ctx.moveTo(gx, 0);
        ctx.lineTo(gx, height);
      }
      for (let gy = gridSize; gy < height; gy += gridSize) {
        ctx.moveTo(0, gy);
        ctx.lineTo(width, gy);
      }
      ctx.stroke();

      // ========================================================
      // 3. WIDE MACRO NETWORK LINES (Inter-regional links)
      // ========================================================
      macroRoutes.forEach((mr) => {
        const pA = toScreen(mr.p0.x, mr.p0.y, 0.85);
        const pB = toScreen(mr.p1.x, mr.p1.y, 0.85);
        ctx.strokeStyle = colors.macroRoute;
        ctx.lineWidth = 1.0;
        ctx.setLineDash([3, 8]);
        ctx.beginPath();
        ctx.moveTo(pA.x, pA.y);
        ctx.lineTo(pB.x, pB.y);
        ctx.stroke();
      });
      ctx.setLineDash([]);

      // ========================================================
      // 4. QUADRANT SECTOR DIVIDER CROSSHAIRS AT CENTRAL DEPOT
      // ========================================================
      const sDepot = toScreen(depot.x, depot.y, 1.0);
      ctx.strokeStyle = colors.sectorDividers;
      ctx.lineWidth = 1.0;
      ctx.setLineDash([4, 6]);

      ctx.beginPath();
      ctx.moveTo(sDepot.x, 0);
      ctx.lineTo(sDepot.x, height);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(0, sDepot.y);
      ctx.lineTo(width, sDepot.y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // ========================================================
      // 5. ARTERIAL CORRIDORS WITH PROGRESSIVE ILLUMINATION
      // ========================================================
      routes.forEach((r) => {
        const sp0 = toScreen(r.p0.x, r.p0.y, 1.0);
        const scp1 = toScreen(r.cp1.x, r.cp1.y, 1.0);
        const scp2 = toScreen(r.cp2.x, r.cp2.y, 1.0);
        const sp1 = toScreen(r.p1.x, r.p1.y, 1.0);

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(sp0.x, sp0.y);
        ctx.bezierCurveTo(scp1.x, scp1.y, scp2.x, scp2.y, sp1.x, sp1.y);

        // Faint outer roadway casing
        ctx.strokeStyle = r.glowBoost
          ? isLight ? "rgba(245, 158, 11, 0.35)" : "rgba(245, 158, 11, 0.40)"
          : colors.baseRoute;
        ctx.lineWidth = (r.glowBoost ? 4.2 : 3.5) * state.camZoom;
        ctx.stroke();

        // Contrasting inner corridor lane
        ctx.strokeStyle = isLight ? "rgba(30, 41, 59, 0.22)" : "rgba(255, 255, 255, 0.14)";
        ctx.lineWidth = 1.2 * state.camZoom;
        ctx.stroke();

        // Progressive Route Illumination Beam
        const isPrimed = ct >= r.actTime;
        if (isPrimed || r.glowBoost) {
          const actProgress = r.glowBoost ? ((ct * 0.25) % 1.0) : Math.min(1.0, (ct - r.actTime) / 1.8);
          const headPoint = getBezierPoint(sp0, scp1, scp2, sp1, actProgress);
          const tailPoint = getBezierPoint(sp0, scp1, scp2, sp1, Math.max(0, actProgress - 0.22));

          const beamGrad = ctx.createLinearGradient(tailPoint.x, tailPoint.y, headPoint.x, headPoint.y);
          beamGrad.addColorStop(0, "transparent");
          beamGrad.addColorStop(1, r.color);

          ctx.strokeStyle = beamGrad;
          ctx.lineWidth = (r.glowBoost ? 3.4 : 2.8) * state.camZoom;
          ctx.shadowColor = r.color;
          ctx.shadowBlur = r.glowBoost ? 12 : 8;
          ctx.stroke();
        }

        // Secondary continuous flow wave
        const waveT = (ct * 0.22) % 1.0;
        const waveP = getBezierPoint(sp0, scp1, scp2, sp1, waveT);
        const waveHeadP = getBezierPoint(sp0, scp1, scp2, sp1, Math.max(0, waveT - 0.14));

        const flowGrad = ctx.createLinearGradient(waveHeadP.x, waveHeadP.y, waveP.x, waveP.y);
        flowGrad.addColorStop(0, "transparent");
        flowGrad.addColorStop(1, r.color);

        ctx.strokeStyle = flowGrad;
        ctx.lineWidth = 2.2 * state.camZoom;
        ctx.shadowColor = r.color;
        ctx.shadowBlur = 6;
        ctx.stroke();
        ctx.restore();
      });

      // ========================================================
      // 6. MOVING RELIEF VEHICLES & LOGISTICS PARTICLES
      // ========================================================
      const renderVehicle = (rIdx, tVal, vLabel, color, isHero = false) => {
        const route = routes[rIdx];
        if (!route) return;

        const sp0 = toScreen(route.p0.x, route.p0.y, 1.0);
        const scp1 = toScreen(route.cp1.x, route.cp1.y, 1.0);
        const scp2 = toScreen(route.cp2.x, route.cp2.y, 1.0);
        const sp1 = toScreen(route.p1.x, route.p1.y, 1.0);

        const pos = getBezierPoint(sp0, scp1, scp2, sp1, tVal);
        const heading = getBezierTangent(sp0, scp1, scp2, sp1, tVal);

        ctx.save();

        // Luminous comet tail
        const trailSteps = 8;
        for (let i = 0; i < trailSteps; i++) {
          const trailT = Math.max(0, tVal - (i / trailSteps) * 0.12);
          const tPos = getBezierPoint(sp0, scp1, scp2, sp1, trailT);
          const alpha = (1 - i / trailSteps) * (isLight ? 0.65 : 0.80);

          ctx.fillStyle = color;
          ctx.globalAlpha = alpha;
          ctx.beginPath();
          ctx.arc(tPos.x, tPos.y, Math.max(1, (3.2 - i * 0.30) * state.camZoom), 0, Math.PI * 2);
          ctx.fill();
        }

        // Draw vehicle body oriented along route tangent
        ctx.translate(pos.x, pos.y);
        ctx.rotate(heading);

        ctx.shadowColor = color;
        ctx.shadowBlur = isHero ? 16 : 8;

        // Vehicle core (glowing capsule)
        ctx.fillStyle = "#ffffff";
        ctx.globalAlpha = 1.0;
        ctx.beginPath();
        ctx.ellipse(0, 0, 4.6 * state.camZoom, 2.6 * state.camZoom, 0, 0, Math.PI * 2);
        ctx.fill();

        // Directional aura
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.4 * state.camZoom;
        ctx.beginPath();
        ctx.ellipse(0, 0, 6.8 * state.camZoom, 4.2 * state.camZoom, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Vehicle HUD Label for Hero vehicle
        if (isHero && state.camZoom > 1.2) {
          ctx.rotate(-heading);
          ctx.font = `bold ${Math.round(8.5 * state.camZoom)}px 'JetBrains Mono', monospace`;
          ctx.fillStyle = colors.nodeLabelBg;
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          const textW = ctx.measureText(vLabel).width;
          ctx.beginPath();
          ctx.roundRect(-textW / 2 - 4, -18 * state.camZoom, textW + 8, 13 * state.camZoom, 3);
          ctx.fill();
          ctx.stroke();

          ctx.fillStyle = "#ffffff";
          ctx.textAlign = "center";
          ctx.fillText(vLabel, 0, -8 * state.camZoom);
        }

        ctx.restore();
      };

      // V1: Hero vehicle traveling Route 0 (Depot -> R1)
      const v1Prog = Math.max(0, Math.min(1, (ct - 12.5) / 6.0));
      renderVehicle(0, v1Prog, "V1: RELIEF CONVOY", "#38bdf8", ct >= 13.0 && ct < 19.0);

      // V2: Ambient vehicle on Route 1 (Depot -> R2)
      const v2Prog = ((ct * 0.11) + 0.3) % 1.0;
      renderVehicle(1, v2Prog, "V2", "#818cf8");

      // Tier 2 Scenario Convoys
      renderVehicle(2, ((ct * 0.13) + (isJaipur ? 0.1 : 0.4)) % 1.0, "V_JAIPUR", "#f59e0b", isJaipur);
      renderVehicle(3, ((ct * 0.12) + (isDelhi ? 0.2 : 0.7)) % 1.0, "V_DELHI", "#38bdf8", isDelhi);
      renderVehicle(4, ((ct * 0.11) + (isMumbai ? 0.15 : 0.5)) % 1.0, "V_MUMBAI", "#10b981", isMumbai);

      // Tier 3 Instance & KPI Convoys
      renderVehicle(5, ((ct * 0.10) + 0.2) % 1.0, "V_INST", "#a855f7");
      renderVehicle(6, ((ct * 0.14) + 0.35) % 1.0, "V_DEMAND", "#38bdf8");
      renderVehicle(7, ((ct * 0.12) + 0.6) % 1.0, "V_EQUITY", "#f43f5e");
      renderVehicle(8, ((ct * 0.13) + 0.8) % 1.0, "V_FLEET", "#06b6d4");

      // Tier 4 Scorecard Convoys
      const v3Prog = Math.max(0, Math.min(1, (ct - 18.0) / 5.5));
      renderVehicle(9, v3Prog, "V3: MEDICAL SUPPLY", "#34d399", ct >= 19.0 && ct < 24.0);
      renderVehicle(10, ((ct * 0.09) + 0.45) % 1.0, "V_AUDIT", "#818cf8");
      renderVehicle(11, ((ct * 0.12) + 0.7) % 1.0, "V4", "#fbbf24");

      // Feeder vehicles
      renderVehicle(12, (ct * 0.14) % 1.0, "F1", "#38bdf8");
      renderVehicle(13, (ct * 0.12) % 1.0, "F2", "#818cf8");
      renderVehicle(14, (ct * 0.13) % 1.0, "F3", "#34d399");
      renderVehicle(15, (ct * 0.11) % 1.0, "F4", "#fbbf24");

      // ========================================================
      // 7. DESTINATION & REGIONAL OUTPOST NODES (ALL 4 TIERS)
      // ========================================================
      nodes.forEach((node) => {
        const sNode = toScreen(node.x, node.y, 1.0);

        ctx.save();
        const ripple = state.nodeRipples[node.id] || 0;
        if (ripple > 0) {
          ctx.strokeStyle = node.color;
          ctx.lineWidth = 1.6 * state.camZoom;
          ctx.globalAlpha = ripple;
          ctx.beginPath();
          ctx.arc(sNode.x, sNode.y, (8 + (1 - ripple) * 24) * state.camZoom, 0, Math.PI * 2);
          ctx.stroke();
          state.nodeRipples[node.id] = Math.max(0, ripple - dt * 1.5);
        }

        // Scenario Hub Active Pulsing Ring
        if (node.isScenarioHub && node.active) {
          const sCycle = (ct * 0.8) % 1.0;
          ctx.strokeStyle = node.color;
          ctx.lineWidth = 1.6 * state.camZoom;
          ctx.globalAlpha = (1 - sCycle) * 0.7;
          ctx.beginPath();
          ctx.arc(sNode.x, sNode.y, (10 + sCycle * 32) * state.camZoom, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Soft outer glow aura
        ctx.fillStyle = node.color;
        ctx.globalAlpha = node.active ? 0.38 : isLight ? 0.15 : 0.22;
        ctx.beginPath();
        const glowRad = (node.active ? 16 : node.isFeeder ? 6.5 : 10) * state.camZoom;
        ctx.arc(sNode.x, sNode.y, glowRad, 0, Math.PI * 2);
        ctx.fill();

        // Core circle
        ctx.globalAlpha = 1.0;
        ctx.fillStyle = isLight ? "#ffffff" : "#0f172a";
        ctx.strokeStyle = node.color;
        ctx.lineWidth = (node.active ? 2.6 : 2.0) * state.camZoom;
        ctx.beginPath();
        ctx.arc(sNode.x, sNode.y, (node.active ? 6.5 : node.isFeeder ? 3.5 : 5.0) * state.camZoom, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Inner bright pinpoint
        ctx.fillStyle = node.color;
        ctx.beginPath();
        ctx.arc(sNode.x, sNode.y, (node.active ? 3.2 : node.isFeeder ? 1.8 : 2.6) * state.camZoom, 0, Math.PI * 2);
        ctx.fill();

        // Node HUD Label (visible when zoom > 0.80)
        if (state.camZoom > 0.80 && width >= 768) {
          ctx.font = `bold ${Math.max(8, Math.round(9 * state.camZoom))}px 'JetBrains Mono', monospace`;
          const labelY = sNode.y > height * 0.55 ? sNode.y + 18 * state.camZoom : sNode.y - 12 * state.camZoom;

          ctx.fillStyle = colors.nodeLabelBg;
          ctx.strokeStyle = node.active ? node.color : colors.nodeLabelBorder;
          ctx.lineWidth = node.active ? 1.4 : 1;
          const textW = ctx.measureText(node.name).width;
          ctx.beginPath();
          ctx.roundRect(sNode.x - textW / 2 - 5, labelY - 8, textW + 10, 16, 3);
          ctx.fill();
          ctx.stroke();

          ctx.fillStyle = node.active ? (isLight ? "#b45309" : "#fbbf24") : colors.nodeLabelText;
          ctx.textAlign = "center";
          ctx.fillText(node.name, sNode.x, labelY + 3.5);
        }

        ctx.restore();
      });

      // ========================================================
      // 8. CENTRAL RELIEF DEPOT HUB (Supply Origin)
      // ========================================================
      ctx.save();
      // Concentric expanding radar wave 1
      const waveCycle = (ct * 0.6) % 1.0;
      const rippleRadius = (14 + waveCycle * 65) * state.camZoom;
      const rippleAlpha = (1 - waveCycle) * 0.5;

      ctx.strokeStyle = colors.depotRipple;
      ctx.lineWidth = 1.8 * state.camZoom;
      ctx.globalAlpha = rippleAlpha;
      ctx.beginPath();
      ctx.arc(sDepot.x, sDepot.y, rippleRadius, 0, Math.PI * 2);
      ctx.stroke();

      // Secondary tighter ripple
      const waveCycle2 = ((ct + 0.5) * 0.6) % 1.0;
      const rippleRadius2 = (14 + waveCycle2 * 48) * state.camZoom;
      const rippleAlpha2 = (1 - waveCycle2) * 0.38;
      ctx.globalAlpha = rippleAlpha2;
      ctx.beginPath();
      ctx.arc(sDepot.x, sDepot.y, rippleRadius2, 0, Math.PI * 2);
      ctx.stroke();

      // Instance switching shockwave pulse
      const instElapsed = (ct - state.instancePulseTime + state.cycleDuration) % state.cycleDuration;
      if (instElapsed < 2.5) {
        const instRad = (18 + instElapsed * 480) * state.camZoom;
        const instAlpha = (1 - instElapsed / 2.5) * 0.45;
        ctx.strokeStyle = isLight ? "#0284c7" : "#38bdf8";
        ctx.lineWidth = 2.4 * state.camZoom;
        ctx.globalAlpha = instAlpha;
        ctx.beginPath();
        ctx.arc(sDepot.x, sDepot.y, instRad, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Golden halo glow
      ctx.globalAlpha = 1.0;
      const depotGlowGrad = ctx.createRadialGradient(
        sDepot.x,
        sDepot.y,
        4 * state.camZoom,
        sDepot.x,
        sDepot.y,
        28 * state.camZoom
      );
      depotGlowGrad.addColorStop(0, colors.depotGlow);
      depotGlowGrad.addColorStop(1, "transparent");
      ctx.fillStyle = depotGlowGrad;
      ctx.beginPath();
      ctx.arc(sDepot.x, sDepot.y, 28 * state.camZoom, 0, Math.PI * 2);
      ctx.fill();

      // Solid boundary ring
      ctx.strokeStyle = colors.depotRing;
      ctx.lineWidth = 2.4 * state.camZoom;
      ctx.shadowColor = colors.depotCore;
      ctx.shadowBlur = simPlaying ? 18 : 10;
      ctx.beginPath();
      ctx.arc(sDepot.x, sDepot.y, 11 * state.camZoom, 0, Math.PI * 2);
      ctx.stroke();

      // Central core star / hub
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(sDepot.x, sDepot.y, 6.0 * state.camZoom, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = colors.depotCore;
      ctx.beginPath();
      ctx.arc(sDepot.x, sDepot.y, 3.2 * state.camZoom, 0, Math.PI * 2);
      ctx.fill();

      // Central Depot HUD Badge Pill (visible when zoom > 0.8)
      if (state.camZoom > 0.8 && width >= 720) {
        ctx.font = `bold ${Math.max(8.5, Math.round(9.5 * state.camZoom))}px 'JetBrains Mono', monospace`;
        const depotTag = "★ CENTRAL RELIEF DEPOT";
        const depotLatStr = scenario ? `${scenario.depot_latitude?.toFixed(4)}°N` : "26.9124°N";
        const depotLonStr = scenario ? `${scenario.depot_longitude?.toFixed(4)}°E` : "75.7873°E";
        const subTag = scenario
          ? `${scenario.depot_name.toUpperCase()} [${depotLatStr}, ${depotLonStr}]`
          : "PRIMARY DISPATCH BASE • S=70% CAPACITY";

        const tagW = Math.max(ctx.measureText(depotTag).width, ctx.measureText(subTag).width);
        const badgeY = sDepot.y - 34 * state.camZoom;

        ctx.fillStyle = colors.nodeLabelBg;
        ctx.strokeStyle = "rgba(245, 158, 11, 0.45)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.roundRect(sDepot.x - tagW / 2 - 8, badgeY - 10, tagW + 16, 26, 4);
        ctx.fill();
        ctx.stroke();

        ctx.textAlign = "center";
        ctx.fillStyle = isLight ? "#b45309" : "#fbbf24";
        ctx.fillText(depotTag, sDepot.x, badgeY);

        ctx.font = "8px 'JetBrains Mono', monospace";
        ctx.fillStyle = colors.nodeLabelSub;
        ctx.fillText(subTag, sDepot.x, badgeY + 11.5);
      }
      ctx.restore();

      // ========================================================
      // 9. CAMERA HUD STATUS & CHOREOGRAPHY READOUT
      // ========================================================
      ctx.save();
      ctx.fillStyle = isLight ? "rgba(100, 116, 139, 0.55)" : "rgba(148, 163, 184, 0.45)";
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.textAlign = "right";
      ctx.fillText(`CHOREOGRAPHY: [${sceneLabel}]`, width - 24, 20);
      ctx.fillText(`CAM-TRANSFORM: ZOOM=${state.camZoom.toFixed(2)}x // COORDS: [${Math.round(state.camX)}, ${Math.round(state.camY)}]`, width - 24, 33);

      // Bottom Right Dispatch Status Badge
      ctx.font = "bold 9.5px 'JetBrains Mono', monospace";
      const statusText = simPlaying
        ? `▶ FLEET DISPATCH ACTIVE [${simSpeed}x]`
        : animProgress >= 100
        ? "✓ ALL FLEET RETURNED TO BASE"
        : "● CINEMATIC RELIEF SURVEILLANCE";
      const statusColor = simPlaying ? "#38bdf8" : animProgress >= 100 ? "#34d399" : "#94a3b8";

      ctx.fillStyle = statusColor;
      ctx.fillText(statusText, width - 24, height - 16);
      ctx.restore();

      animFrameIdRef.current = requestAnimationFrame(render);
    };

    // Check for prefers-reduced-motion
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mediaQuery.matches) {
      render(performance.now());
    } else {
      animFrameIdRef.current = requestAnimationFrame(render);
    }

    return () => {
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
      resizeObserver.disconnect();
    };
  }, [scenario, selectedInstance, simPlaying, simSpeed, animProgress, theme]);

  return (
    <div className="hero-network-wrapper" aria-hidden="true">
      <canvas
        ref={canvasRef}
        className="hero-network-canvas hero-video-bg"
        style={{
          width: "100%",
          height: "100%",
          display: "block",
          pointerEvents: "none",
        }}
      />
      <div className="hero-text-protection-gradient" />
      <div className="stage-bottom-blend" />
    </div>
  );
}
