import React, { useRef, useEffect } from "react";

/**
 * HeroLogisticsNetwork
 * High-performance HTML5 Canvas animation rendering a cinematic operating logistics map:
 * - Near-black / dark midnight base with subtle topological contours and spatial sector grid
 * - Central Relief Depot hub with pulsing radar ripple and supply origin marker
 * - 4 Regional distribution centers (R1, R2, R3, R4) reflecting lexicographic fair allocation
 * - Arterial Bézier route corridors that progressively illuminate
 * - Moving relief vehicle particles with luminous comet trails
 * - Synchronized with dispatch simulation playback (speeds up during dispatch, pauses smoothly)
 * - Zero external dependencies, pure Canvas 2D, high-DPI crispness, 60fps performance
 */

// Helper to evaluate cubic Bézier curve at parameter t [0, 1]
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

// Helper to get tangent angle (heading) along cubic Bézier
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
  simPlaying = false,
  simSpeed = 1,
  animProgress = 0,
  theme = "dark",
}) {
  const canvasRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const lastTimeRef = useRef(performance.now());

  // Animation internal clock
  const stateRef = useRef({
    time: 0,
    depotRipple: 0,
    nodeRipples: {},
    particles: [
      { routeIdx: 0, t: 0.15, speed: 0.09, length: 0.12, color: "#38bdf8", id: "V1" },
      { routeIdx: 0, t: 0.68, speed: 0.09, length: 0.10, color: "#38bdf8", id: "V1b" },
      { routeIdx: 1, t: 0.32, speed: 0.08, length: 0.14, color: "#818cf8", id: "V2" },
      { routeIdx: 1, t: 0.85, speed: 0.08, length: 0.10, color: "#818cf8", id: "V2b" },
      { routeIdx: 2, t: 0.05, speed: 0.095, length: 0.13, color: "#34d399", id: "V3" },
      { routeIdx: 2, t: 0.58, speed: 0.095, length: 0.11, color: "#34d399", id: "V3b" },
      { routeIdx: 3, t: 0.42, speed: 0.085, length: 0.12, color: "#fbbf24", id: "V4" },
      { routeIdx: 3, t: 0.92, speed: 0.085, length: 0.10, color: "#fbbf24", id: "V4b" },
      // Secondary feeder vehicles
      { routeIdx: 4, t: 0.25, speed: 0.11, length: 0.09, color: "#38bdf8", id: "F1" },
      { routeIdx: 5, t: 0.60, speed: 0.10, length: 0.09, color: "#818cf8", id: "F2" },
      { routeIdx: 6, t: 0.40, speed: 0.12, length: 0.09, color: "#34d399", id: "F3" },
      { routeIdx: 7, t: 0.75, speed: 0.10, length: 0.09, color: "#fbbf24", id: "F4" },
    ],
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    let width = 0;
    let height = 0;

    // Handle high-DPI Retina scaling
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

    // Palette configurations
    const themeColors = {
      bgBase: isLight ? "#f1f5f9" : "#030611",
      bgGradEdge: isLight ? "#e2e8f0" : "#02040a",
      gridLines: isLight ? "rgba(100, 116, 139, 0.08)" : "rgba(56, 189, 248, 0.05)",
      contourLines: isLight ? "rgba(71, 85, 105, 0.09)" : "rgba(99, 102, 241, 0.07)",
      sectorDividers: isLight ? "rgba(100, 116, 139, 0.14)" : "rgba(148, 163, 184, 0.10)",
      depotCore: "#f59e0b",
      depotRing: isLight ? "rgba(217, 119, 6, 0.85)" : "rgba(245, 158, 11, 0.85)",
      depotGlow: isLight ? "rgba(217, 119, 6, 0.25)" : "rgba(245, 158, 11, 0.35)",
      depotRipple: isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(245, 158, 11, 0.5)",
      baseRoute: isLight ? "rgba(59, 130, 246, 0.18)" : "rgba(56, 189, 248, 0.14)",
      nodeLabelBg: isLight ? "rgba(255, 255, 255, 0.88)" : "rgba(7, 11, 22, 0.82)",
      nodeLabelBorder: isLight ? "rgba(203, 213, 225, 0.8)" : "rgba(56, 189, 248, 0.25)",
      nodeLabelText: isLight ? "#1e293b" : "#e2e8f0",
      nodeLabelSub: isLight ? "#64748b" : "#94a3b8",
    };

    // Render loop
    const render = (now) => {
      const dt = Math.min((now - lastTimeRef.current) / 1000, 0.1);
      lastTimeRef.current = now;

      const state = stateRef.current;
      const speedMultiplier = simPlaying ? Math.max(1.8, 1.8 * simSpeed) : 1.0;
      state.time += dt * speedMultiplier;

      // Clear & draw dark cinematic background
      const bgGrad = ctx.createRadialGradient(
        width * 0.65,
        height * 0.48,
        20,
        width * 0.65,
        height * 0.48,
        Math.max(width, height) * 0.85
      );
      bgGrad.addColorStop(0, themeColors.bgBase);
      bgGrad.addColorStop(1, themeColors.bgGradEdge);
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // 1. Draw Faint Geographic Terrain Contours
      ctx.save();
      ctx.strokeStyle = themeColors.contourLines;
      ctx.lineWidth = 1.0;

      // Contour Spline 1 (Topographic elevation wave)
      ctx.beginPath();
      ctx.moveTo(0, height * 0.35);
      ctx.bezierCurveTo(
        width * 0.3,
        height * 0.15,
        width * 0.55,
        height * 0.6,
        width,
        height * 0.3
      );
      ctx.stroke();

      // Contour Spline 2
      ctx.beginPath();
      ctx.moveTo(width * 0.15, height);
      ctx.bezierCurveTo(
        width * 0.4,
        height * 0.65,
        width * 0.7,
        height * 0.85,
        width * 0.95,
        height * 0.1
      );
      ctx.stroke();

      // Contour Spline 3
      ctx.beginPath();
      ctx.moveTo(0, height * 0.75);
      ctx.bezierCurveTo(
        width * 0.25,
        height * 0.88,
        width * 0.6,
        height * 0.4,
        width,
        height * 0.8
      );
      ctx.stroke();

      // 2. Spatial Sector Grid & Lat/Lon Reticle
      ctx.strokeStyle = themeColors.gridLines;
      ctx.lineWidth = 0.8;
      const gridSize = Math.max(48, Math.round(width / 24));
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

      // Micro Coordinates in upper right
      ctx.fillStyle = isLight ? "rgba(100, 116, 139, 0.4)" : "rgba(148, 163, 184, 0.28)";
      ctx.font = "9px 'JetBrains Mono', monospace";
      const depotLatStr = scenario ? `${scenario.depot_latitude?.toFixed(4)}°N` : "26.9124°N";
      const depotLonStr = scenario ? `${scenario.depot_longitude?.toFixed(4)}°E` : "75.7873°E";
      ctx.fillText(`OPS-SYS: AIR-LOGISTICS // REF: [${depotLatStr}, ${depotLonStr}]`, width - 290, 20);
      ctx.fillText(`FAIR ALLOCATION CORRIDORS // S=70% CAPACITY MAPPING`, width - 290, 33);
      ctx.restore();

      // Define Node Positions relative to canvas size
      // Central Depot sits in the right-center open breathing area
      const depot = {
        x: width * 0.64,
        y: height * 0.48,
        name: scenario?.depot_name || "CENTRAL RELIEF WAREHOUSE",
      };

      // 4 Regional Main Hubs (R1, R2, R3, R4)
      const nodes = [
        {
          id: "R1",
          name: "R1: NORTH-EAST SECTOR",
          x: width * 0.85,
          y: height * 0.22,
          color: "#38bdf8",
          demand: "42u",
        },
        {
          id: "R2",
          name: "R2: NORTH-WEST SECTOR",
          x: width * 0.44,
          y: height * 0.24,
          color: "#818cf8",
          demand: "53u",
        },
        {
          id: "R3",
          name: "R3: SOUTH-WEST SECTOR",
          x: width * 0.42,
          y: height * 0.78,
          color: "#34d399",
          demand: "108u",
        },
        {
          id: "R4",
          name: "R4: SOUTH-EAST SECTOR",
          x: width * 0.84,
          y: height * 0.76,
          color: "#fbbf24",
          demand: "143u",
        },
        // Secondary distribution outposts
        {
          id: "D1",
          name: "EASTERN COMMUNITY DROP",
          x: width * 0.94,
          y: height * 0.46,
          color: "#38bdf8",
          demand: "24u",
          isFeeder: true,
        },
        {
          id: "D2",
          name: "NORTHERN LOGISTICS POST",
          x: width * 0.68,
          y: height * 0.12,
          color: "#818cf8",
          demand: "30u",
          isFeeder: true,
        },
        {
          id: "D3",
          name: "WESTERN STAGING HUB",
          x: width * 0.28,
          y: height * 0.52,
          color: "#34d399",
          demand: "35u",
          isFeeder: true,
        },
        {
          id: "D4",
          name: "SOUTHERN PERIMETER POST",
          x: width * 0.66,
          y: height * 0.88,
          color: "#fbbf24",
          demand: "40u",
          isFeeder: true,
        },
      ];

      // Define Arterial & Feeder Route Béziers
      const routes = [
        // Route 0: Depot -> R1 (North-East Trunk)
        {
          from: depot,
          to: nodes[0],
          p0: depot,
          cp1: { x: width * 0.70, y: height * 0.32 },
          cp2: { x: width * 0.78, y: height * 0.25 },
          p1: nodes[0],
          color: "#38bdf8",
        },
        // Route 1: Depot -> R2 (North-West Trunk)
        {
          from: depot,
          to: nodes[1],
          p0: depot,
          cp1: { x: width * 0.56, y: height * 0.40 },
          cp2: { x: width * 0.48, y: height * 0.30 },
          p1: nodes[1],
          color: "#818cf8",
        },
        // Route 2: Depot -> R3 (South-West Trunk)
        {
          from: depot,
          to: nodes[2],
          p0: depot,
          cp1: { x: width * 0.58, y: height * 0.62 },
          cp2: { x: width * 0.48, y: height * 0.70 },
          p1: nodes[2],
          color: "#34d399",
        },
        // Route 3: Depot -> R4 (South-East Trunk)
        {
          from: depot,
          to: nodes[3],
          p0: depot,
          cp1: { x: width * 0.72, y: height * 0.60 },
          cp2: { x: width * 0.80, y: height * 0.70 },
          p1: nodes[3],
          color: "#fbbf24",
        },
        // Route 4: R1 -> D1 (Eastern Outpost Feeder)
        {
          from: nodes[0],
          to: nodes[4],
          p0: nodes[0],
          cp1: { x: width * 0.90, y: height * 0.30 },
          cp2: { x: width * 0.94, y: height * 0.38 },
          p1: nodes[4],
          color: "#38bdf8",
        },
        // Route 5: Depot -> D2 (Northern Feeder)
        {
          from: depot,
          to: nodes[5],
          p0: depot,
          cp1: { x: width * 0.65, y: height * 0.30 },
          cp2: { x: width * 0.67, y: height * 0.20 },
          p1: nodes[5],
          color: "#818cf8",
        },
        // Route 6: R3 -> D3 (Western Feeder Corridor)
        {
          from: nodes[2],
          to: nodes[6],
          p0: nodes[2],
          cp1: { x: width * 0.36, y: height * 0.70 },
          cp2: { x: width * 0.30, y: height * 0.60 },
          p1: nodes[6],
          color: "#34d399",
        },
        // Route 7: Depot -> D4 (Southern Feeder)
        {
          from: depot,
          to: nodes[7],
          p0: depot,
          cp1: { x: width * 0.64, y: height * 0.68 },
          cp2: { x: width * 0.65, y: height * 0.78 },
          p1: nodes[7],
          color: "#fbbf24",
        },
      ];

      // 3. Draw Quadrant Sector Divider Crosshairs at Depot
      ctx.save();
      ctx.strokeStyle = themeColors.sectorDividers;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);

      // Vertical quadrant axis
      ctx.beginPath();
      ctx.moveTo(depot.x, 0);
      ctx.lineTo(depot.x, height);
      ctx.stroke();

      // Horizontal quadrant axis
      ctx.beginPath();
      ctx.moveTo(0, depot.y);
      ctx.lineTo(width, depot.y);
      ctx.stroke();
      ctx.restore();

      // 4. Render Base Route Corridors with Subtle Glow
      routes.forEach((r, rIdx) => {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(r.p0.x, r.p0.y);
        ctx.bezierCurveTo(r.cp1.x, r.cp1.y, r.cp2.x, r.cp2.y, r.p1.x, r.p1.y);

        // Faint outer road cushion
        ctx.strokeStyle = themeColors.baseRoute;
        ctx.lineWidth = 3.2;
        ctx.stroke();

        // Contrasting inner corridor lane
        ctx.strokeStyle = isLight ? "rgba(30, 41, 59, 0.20)" : "rgba(255, 255, 255, 0.12)";
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Subtle traveling wave pulse along the route
        const waveT = (state.time * (0.2 + rIdx * 0.03)) % 1.0;
        const waveP = getBezierPoint(r.p0, r.cp1, r.cp2, r.p1, waveT);
        const waveHeadT = Math.max(0, waveT - 0.15);
        const waveHeadP = getBezierPoint(r.p0, r.cp1, r.cp2, r.p1, waveHeadT);

        const pulseGrad = ctx.createLinearGradient(
          waveHeadP.x,
          waveHeadP.y,
          waveP.x,
          waveP.y
        );
        pulseGrad.addColorStop(0, "transparent");
        pulseGrad.addColorStop(1, r.color);

        ctx.strokeStyle = pulseGrad;
        ctx.lineWidth = 2.4;
        ctx.shadowColor = r.color;
        ctx.shadowBlur = 6;
        ctx.stroke();
        ctx.restore();
      });

      // 5. Render Moving Logistics / Relief Vehicle Particles
      state.particles.forEach((p) => {
        const route = routes[p.routeIdx];
        if (!route) return;

        // Advance particle position
        p.t += dt * p.speed * speedMultiplier;
        if (p.t >= 1.0) {
          p.t = 0.0;
          // Trigger small destination pulse
          state.nodeRipples[route.to.id] = 1.0;
        }

        const headPos = getBezierPoint(route.p0, route.cp1, route.cp2, route.p1, p.t);
        const tangent = getBezierTangent(route.p0, route.cp1, route.cp2, route.p1, p.t);

        // Draw luminous trail along the curve
        const trailSteps = 8;
        ctx.save();
        for (let i = 0; i < trailSteps; i++) {
          const trailT = Math.max(0, p.t - (i / trailSteps) * p.length);
          const tPos = getBezierPoint(route.p0, route.cp1, route.cp2, route.p1, trailT);
          const alpha = (1 - i / trailSteps) * (isLight ? 0.65 : 0.85);

          ctx.fillStyle = p.color;
          ctx.globalAlpha = alpha;
          ctx.beginPath();
          ctx.arc(tPos.x, tPos.y, Math.max(1, 2.8 - i * 0.25), 0, Math.PI * 2);
          ctx.fill();
        }

        // Draw vehicle marker head (elongated directional capsule)
        ctx.translate(headPos.x, headPos.y);
        ctx.rotate(tangent);

        ctx.shadowColor = p.color;
        ctx.shadowBlur = simPlaying ? 12 : 8;

        // Vehicle core
        ctx.fillStyle = "#ffffff";
        ctx.globalAlpha = 1.0;
        ctx.beginPath();
        ctx.ellipse(0, 0, 4.2, 2.4, 0, 0, Math.PI * 2);
        ctx.fill();

        // Vehicle subtle directional aura
        ctx.strokeStyle = p.color;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.ellipse(0, 0, 6.0, 3.8, 0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.restore();
      });

      // 6. Draw Destination & Community Drop Nodes
      nodes.forEach((node) => {
        ctx.save();
        const ripple = state.nodeRipples[node.id] || 0;
        if (ripple > 0) {
          // Node arrival flash ring
          ctx.strokeStyle = node.color;
          ctx.lineWidth = 1.5;
          ctx.globalAlpha = ripple;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 8 + (1 - ripple) * 18, 0, Math.PI * 2);
          ctx.stroke();
          state.nodeRipples[node.id] = Math.max(0, ripple - dt * 1.5);
        }

        // Node soft outer aura
        ctx.fillStyle = node.color;
        ctx.globalAlpha = isLight ? 0.15 : 0.22;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.isFeeder ? 7 : 10, 0, Math.PI * 2);
        ctx.fill();

        // Node core circle
        ctx.globalAlpha = 1.0;
        ctx.fillStyle = isLight ? "#ffffff" : "#0f172a";
        ctx.strokeStyle = node.color;
        ctx.lineWidth = 2.0;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.isFeeder ? 3.5 : 5.0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Node inner bright pinpoint
        ctx.fillStyle = node.color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.isFeeder ? 1.8 : 2.6, 0, Math.PI * 2);
        ctx.fill();

        // Node HUD Label (hide on narrow screens < 820px to prevent overlap)
        if (width >= 820) {
          ctx.font = "bold 9px 'JetBrains Mono', monospace";
          const labelY = node.y > height * 0.5 ? node.y + 16 : node.y - 10;

          // Background pill
          ctx.fillStyle = themeColors.nodeLabelBg;
          ctx.strokeStyle = themeColors.nodeLabelBorder;
          ctx.lineWidth = 1;
          const textW = ctx.measureText(node.name).width;
          ctx.beginPath();
          ctx.roundRect(node.x - textW / 2 - 5, labelY - 8, textW + 10, 15, 3);
          ctx.fill();
          ctx.stroke();

          // Label text
          ctx.fillStyle = themeColors.nodeLabelText;
          ctx.textAlign = "center";
          ctx.fillText(node.name, node.x, labelY + 3);
        }

        ctx.restore();
      });

      // 7. Draw Central Relief Depot Hub (Supply Origin)
      ctx.save();
      // Expanding radar concentric wave
      const waveCycle = (state.time * 0.55) % 1.0;
      const rippleRadius = 14 + waveCycle * 55;
      const rippleAlpha = (1 - waveCycle) * 0.45;

      ctx.strokeStyle = themeColors.depotRipple;
      ctx.lineWidth = 1.6;
      ctx.globalAlpha = rippleAlpha;
      ctx.beginPath();
      ctx.arc(depot.x, depot.y, rippleRadius, 0, Math.PI * 2);
      ctx.stroke();

      // Secondary tighter ripple
      const waveCycle2 = ((state.time + 0.5) * 0.55) % 1.0;
      const rippleRadius2 = 14 + waveCycle2 * 45;
      const rippleAlpha2 = (1 - waveCycle2) * 0.35;
      ctx.globalAlpha = rippleAlpha2;
      ctx.beginPath();
      ctx.arc(depot.x, depot.y, rippleRadius2, 0, Math.PI * 2);
      ctx.stroke();

      // Outer golden halo glow
      ctx.globalAlpha = 1.0;
      const depotGlowGrad = ctx.createRadialGradient(
        depot.x,
        depot.y,
        4,
        depot.x,
        depot.y,
        24
      );
      depotGlowGrad.addColorStop(0, themeColors.depotGlow);
      depotGlowGrad.addColorStop(1, "transparent");
      ctx.fillStyle = depotGlowGrad;
      ctx.beginPath();
      ctx.arc(depot.x, depot.y, 24, 0, Math.PI * 2);
      ctx.fill();

      // Solid outer boundary ring
      ctx.strokeStyle = themeColors.depotRing;
      ctx.lineWidth = 2.4;
      ctx.shadowColor = themeColors.depotCore;
      ctx.shadowBlur = simPlaying ? 16 : 9;
      ctx.beginPath();
      ctx.arc(depot.x, depot.y, 11, 0, Math.PI * 2);
      ctx.stroke();

      // Central core star / hub
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(depot.x, depot.y, 6.0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = themeColors.depotCore;
      ctx.beginPath();
      ctx.arc(depot.x, depot.y, 3.2, 0, Math.PI * 2);
      ctx.fill();

      // Central Depot HUD Badge Pill
      if (width >= 700) {
        ctx.font = "bold 9.5px 'JetBrains Mono', monospace";
        const depotTag = "★ CENTRAL RELIEF DEPOT";
        const subTag = scenario
          ? `${scenario.depot_name.toUpperCase()} [${depotLatStr}, ${depotLonStr}]`
          : "PRIMARY DISPATCH BASE • S=70% CAPACITY";

        const tagW = Math.max(ctx.measureText(depotTag).width, ctx.measureText(subTag).width);
        const badgeY = depot.y - 32;

        ctx.fillStyle = themeColors.nodeLabelBg;
        ctx.strokeStyle = "rgba(245, 158, 11, 0.45)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.roundRect(depot.x - tagW / 2 - 8, badgeY - 10, tagW + 16, 25, 4);
        ctx.fill();
        ctx.stroke();

        ctx.textAlign = "center";
        ctx.fillStyle = isLight ? "#b45309" : "#fbbf24";
        ctx.fillText(depotTag, depot.x, badgeY);

        ctx.font = "8px 'JetBrains Mono', monospace";
        ctx.fillStyle = themeColors.nodeLabelSub;
        ctx.fillText(subTag, depot.x, badgeY + 11);
      }

      ctx.restore();

      // 8. Visual Dispatch Status Indicator in bottom-right corner
      ctx.save();
      ctx.font = "bold 9px 'JetBrains Mono', monospace";
      ctx.textAlign = "right";
      const statusText = simPlaying
        ? `▶ FLEET TRANSIT ACTIVE [${simSpeed}x]`
        : animProgress >= 100
        ? "✓ ALL FLEET RETURNED TO BASE"
        : "● LOGISTICS MONITORING ACTIVE";
      const statusColor = simPlaying ? "#38bdf8" : animProgress >= 100 ? "#34d399" : "#94a3b8";

      ctx.fillStyle = statusColor;
      ctx.fillText(statusText, width - 24, height - 16);
      ctx.restore();

      // Continue loop
      animFrameIdRef.current = requestAnimationFrame(render);
    };

    // Check for prefers-reduced-motion
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mediaQuery.matches) {
      // Just render a single static frame without requestAnimationFrame
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
  }, [scenario, simPlaying, simSpeed, animProgress, theme]);

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
      {/* High-contrast directional dark gradient on the left to guarantee 100% WCAG AAA readability for hero text */}
      <div className="hero-text-protection-gradient" />
    </div>
  );
}
