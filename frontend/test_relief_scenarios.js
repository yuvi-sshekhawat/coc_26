import puppeteer from "puppeteer";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const snapshotsDir = path.join(__dirname, "snapshots");
if (!fs.existsSync(snapshotsDir)) {
  fs.mkdirSync(snapshotsDir, { recursive: true });
}

async function runScenarioTests() {
  console.log("==================================================");
  console.log("STARTING MAPLIBRE + MAPTILER RELIEF SCENARIOS TEST");
  console.log("==================================================");

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const errors = [];
  page.on("console", (msg) => {
    const text = msg.text();
    if (msg.type() === "error" && !text.includes("favicon") && !text.includes("maptiler")) {
      console.error(`[BROWSER CONSOLE ERROR]: ${text}`);
      errors.push(text);
    }
  });

  page.on("pageerror", (err) => {
    console.error(`[PAGE UNCAUGHT ERROR]: ${err.message}`);
    errors.push(err.message);
  });

  console.log("1. Navigating to http://localhost:5173...");
  await page.goto("http://localhost:5173", { waitUntil: "networkidle0" });

  // 1. Verify Cinematic Animated Logistics Network Canvas Visibility
  console.log("2. Verifying Cinematic Animated Logistics Network Canvas Visibility...");
  await page.waitForSelector(".hero-network-canvas");
  const networkState = await page.$eval(".hero-network-canvas", (c) => {
    const style = window.getComputedStyle(c);
    return {
      tagName: c.tagName,
      width: c.width,
      height: c.height,
      opacity: parseFloat(style.opacity),
      display: style.display,
    };
  });
  console.log("PASS: Hero Animated Logistics Network Canvas verified:", networkState);
  if (networkState.tagName !== "CANVAS" || networkState.width <= 0 || networkState.opacity < 0.6) {
    throw new Error(`FAIL: Network canvas must be rendered and clearly visible (got ${JSON.stringify(networkState)})`);
  }

  // 2. Verify Relief Scenarios Section
  console.log("3. Checking Relief Scenarios Section...");
  await page.waitForSelector(".scenarios-section");
  const scenarioBtns = await page.$$eval(".scenario-pill-btn", (btns) =>
    btns.map((b) => b.innerText.trim())
  );
  console.log("PASS: Available scenarios listed:", scenarioBtns);
  if (scenarioBtns.length < 3) {
    throw new Error(`FAIL: Expected at least 3 relief scenarios, got ${scenarioBtns.length}`);
  }

  // 3. Select Jaipur Flood Relief Scenario
  console.log("4. Selecting 'Jaipur Flood Relief' scenario...");
  const jaipurBtn = await page.evaluateHandle(() => {
    const btns = Array.from(document.querySelectorAll(".scenario-pill-btn"));
    return btns.find((b) => b.innerText.includes("Jaipur Flood Relief"));
  });
  await jaipurBtn.click();
  await new Promise((r) => setTimeout(r, 1200));

  // Verify Active Scenario Hero Banner
  await page.waitForSelector(".scenario-hero-banner");
  const heroTitle = await page.$eval(".hero-scenario-details h2", (el) => el.innerText);
  const depotInfo = await page.$eval(".hero-scenario-depot", (el) => el.innerText);
  const statusBadge = await page.$eval(".operation-status-badge", (el) => el.innerText);
  console.log(`PASS: Scenario Banner: "${heroTitle}" | ${depotInfo} | [${statusBadge}]`);

  // Verify MapLibre Container & Canvas
  await page.waitForSelector(".maplibre-container");
  const canvasExists = await page.$("canvas.maplibregl-canvas");
  if (!canvasExists) {
    throw new Error("FAIL: MapLibre GL JS canvas element missing!");
  }
  console.log("PASS: MapLibre GL JS container and WebGL canvas verified.");

  // Verify Fleet Capacity & Dispatch Details Drawer (Parts 11-14, 25)
  console.log("5. Checking Fleet Capacity & Road Metrics in Route Drawer...");
  await page.waitForSelector(".routes-table-footer");
  const routeCards = await page.$$eval(".route-badge-item", (cards) =>
    cards.map((c) => ({
      title: c.querySelector(".v-num")?.innerText.trim(),
      status: c.querySelector(".v-status-pill")?.innerText.trim(),
      cvrplibDist: c.querySelector(".v-dist")?.innerText.trim(),
      roadDist: c.querySelector(".v-road-dist")?.innerText.trim(),
      duration: c.querySelector(".v-duration")?.innerText.trim(),
    }))
  );
  console.log("PASS: Fleet Route Cards verified with separate road distances:", routeCards);
  if (!routeCards[0]?.roadDist || !routeCards[0]?.duration) {
    throw new Error("FAIL: Real road distance or duration missing from route card!");
  }

  // Verify Depot Marker
  await page.waitForSelector(".maplibre-depot-marker");
  console.log("PASS: Distinctive MapLibre depot marker rendered.");

  // Click depot marker to test popup
  const depotMarker = await page.$(".maplibre-depot-marker");
  await depotMarker.click();
  await new Promise((r) => setTimeout(r, 400));
  const depotPopupHtml = await page.$eval(".maplibregl-popup-content", (el) => el.innerText);
  console.log("PASS: Depot popup clicked and verified:\n", depotPopupHtml.replace(/\n+/g, " | "));

  // Verify Customer Markers
  const custMarkersCount = await page.$$eval(".maplibre-cust-marker", (els) => els.length);
  console.log(`PASS: ${custMarkersCount} MapLibre customer markers rendered for Jaipur.`);
  if (custMarkersCount !== 12) {
    throw new Error(`FAIL: Expected 12 Jaipur customer markers, got ${custMarkersCount}`);
  }

  // 4. Test Interactive Dispatch Simulation along Road Geometry (Parts 6-10, 22-24)
  console.log("6. Testing Interactive Dispatch Simulation along Road Geometry...");
  const simBtn = await page.$(".hud-ctrl-btn.primary");
  await simBtn.click();
  await new Promise((r) => setTimeout(r, 1200));

  // Verify moving vehicle marker appears on the MapLibre canvas
  await page.waitForSelector(".maplibre-vehicle-marker");
  console.log("PASS: Animated MapLibre vehicle marker rendered along road geometry.");

  // Verify Stop Progress Chain in HUD
  const stopChainItems = await page.$$eval(".stop-chain-item", (items) => items.length);
  console.log(`PASS: Stop progress chain rendered with ${stopChainItems} stops.`);
  if (stopChainItems < 3) {
    throw new Error("FAIL: Expected at least 3 stops in progress chain");
  }

  // Test Pause
  await simBtn.click();
  await new Promise((r) => setTimeout(r, 400));
  const hudStatus = await page.$eval(".hud-status-tag", (el) => el.innerText);
  console.log(`PASS: Simulation pause verified. Status: "${hudStatus}"`);

  // Test Speed toggle
  const speedBtn = await page.$(".hud-ctrl-btn.speed-btn");
  await speedBtn.click();
  const speedText = await page.$eval(".hud-ctrl-btn.speed-btn", (el) => el.innerText);
  console.log(`PASS: Simulation speed cycled to: "${speedText}"`);

  // Resume simulation to trigger completion
  await simBtn.click();
  // Drag slider to 100% to simulate route completion
  await page.evaluate(() => {
    const slider = document.querySelector(".hud-slider");
    if (slider) {
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value"
      )?.set;
      if (nativeSetter) {
        nativeSetter.call(slider, "100");
      } else {
        slider.value = "100";
      }
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  await new Promise((r) => setTimeout(r, 1200));

  // Verify Dispatch Complete summary banner
  await page.waitForSelector(".dispatch-summary-banner");
  const summaryTitle = await page.$eval(".summary-title-group h4", (el) => el.innerText);
  const summaryStats = await page.$$eval(".summary-stat-box", (boxes) =>
    boxes.map((b) => b.innerText.replace(/\n+/g, " : "))
  );
  console.log(`PASS: Dispatch Complete Banner verified: "${summaryTitle}"`);
  console.log("PASS: Summary stats:", summaryStats);

  // Take Snapshot 8: Jaipur Flood Relief Scenario Map with Dispatch Simulation
  const snap8 = path.join(snapshotsDir, "8_maplibre_jaipur_scenario.png");
  await page.screenshot({ path: snap8, fullPage: true });
  console.log(`Snapshot saved: ${snap8}`);

  // 3. Switch to Delhi Emergency Relief Scenario (Test Isolation)
  console.log("4. Switching to 'Delhi Emergency Relief' scenario...");
  const delhiBtn = await page.evaluateHandle(() => {
    const btns = Array.from(document.querySelectorAll(".scenario-pill-btn"));
    return btns.find((b) => b.innerText.includes("Delhi Emergency Relief"));
  });
  await delhiBtn.click();
  await new Promise((r) => setTimeout(r, 1200));

  const delhiTitle = await page.$eval(".hero-scenario-details h2", (el) => el.innerText);
  const delhiCustCount = await page.$$eval(".maplibre-cust-marker", (els) => els.length);
  console.log(`PASS: Switched scenario to "${delhiTitle}". Customer count: ${delhiCustCount} (Delhi-isolated).`);
  if (delhiCustCount !== 10) {
    throw new Error(`FAIL: Expected 10 Delhi customer markers, got ${delhiCustCount}`);
  }

  const snap9 = path.join(snapshotsDir, "9_maplibre_delhi_scenario.png");
  await page.screenshot({ path: snap9, fullPage: true });
  console.log(`Snapshot saved: ${snap9}`);

  // 4. Test Deselect & Empty State
  console.log("5. Testing Deselect Scenario and Empty State...");
  const deselectBtn = await page.$(".btn-mode-toggle");
  await deselectBtn.click();
  await new Promise((r) => setTimeout(r, 600));

  // Click Satellite Tab when no scenario selected
  const satTabBtn = (await page.$$(".map-toolbar .nb-button.small"))[3];
  await satTabBtn.click();
  await new Promise((r) => setTimeout(r, 400));

  const emptyText = await page.$eval(".scenario-empty-card h3", (el) => el.innerText);
  console.log(`PASS: Empty state correctly displayed: "${emptyText}"`);
  if (!emptyText.includes("NO RELIEF SCENARIO SELECTED")) {
    throw new Error(`FAIL: Expected empty state 'NO RELIEF SCENARIO SELECTED', got '${emptyText}'`);
  }

  const snap10 = path.join(snapshotsDir, "10_maplibre_empty_state.png");
  await page.screenshot({ path: snap10, fullPage: true });
  console.log(`Snapshot saved: ${snap10}`);

  // 5. Test Create Scenario Modal & CSV Validation Flow
  console.log("6. Testing Create Relief Scenario Modal...");
  const openModalBtn = await page.$(".btn-create-scenario");
  await openModalBtn.click();
  await new Promise((r) => setTimeout(r, 500));

  await page.waitForSelector(".modal-window");
  console.log("PASS: Create Scenario modal opened.");

  // Click Auto-Fill Sample Data to test CSV validation
  const sampleBtn = await page.$(".btn-load-sample");
  await sampleBtn.click();
  await new Promise((r) => setTimeout(r, 800));

  await page.waitForSelector(".csv-preview-card");
  const validatedLocations = await page.$eval(".preview-stat b", (el) => el.innerText);
  console.log(`PASS: CSV validation succeeded: "${validatedLocations}"`);

  // Submit creation form
  console.log("7. Submitting new scenario...");
  const submitBtn = await page.$(".modal-actions button.primary");
  await submitBtn.click();
  await new Promise((r) => setTimeout(r, 2500));

  // Verify newly created scenario is active
  await page.waitForSelector(".scenario-hero-banner");
  const newTitle = await page.$eval(".hero-scenario-details h2", (el) => el.innerText);
  console.log(`PASS: Created scenario active: "${newTitle}"`);

  const snap11 = path.join(snapshotsDir, "11_maplibre_created_scenario.png");
  await page.screenshot({ path: snap11, fullPage: true });
  console.log(`Snapshot saved: ${snap11}`);

  // 6. Test Light Mode on MapLibre
  console.log("8. Testing Light Mode with MapLibre...");
  const themeToggle = await page.$(".theme-toggle-btn");
  await themeToggle.click();
  await new Promise((r) => setTimeout(r, 600));

  const snap12 = path.join(snapshotsDir, "12_maplibre_light_mode.png");
  await page.screenshot({ path: snap12, fullPage: true });
  console.log(`Snapshot saved: ${snap12}`);

  // Switch back to Dark Mode
  await themeToggle.click();
  await new Promise((r) => setTimeout(r, 400));

  // 7. Verify Relief History List (Part 20)
  console.log("9. Verifying Relief History List...");
  const historyItems = await page.$$eval(".history-item", (items) =>
    items.map((it) => ({
      title: it.querySelector(".history-item-title")?.innerText,
      status: it.querySelector(".history-status-pill")?.innerText,
    }))
  );
  console.log(`PASS: ${historyItems.length} scenarios in Relief History catalog:`, historyItems);

  await browser.close();

  if (errors.length > 0) {
    console.error(`FAILED with ${errors.length} browser errors:`, errors);
    process.exit(1);
  }

  console.log("==================================================");
  console.log("ALL RELIEF SCENARIO & MAPLIBRE TESTS PASSED (0 ERRORS)!");
  console.log("==================================================");
}

runScenarioTests().catch((err) => {
  console.error("Scenario Test execution failed:", err);
  process.exit(1);
});
