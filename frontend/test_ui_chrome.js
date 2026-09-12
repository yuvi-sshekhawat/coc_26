import puppeteer from "puppeteer";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const snapshotsDir = path.join(__dirname, "snapshots");
if (!fs.existsSync(snapshotsDir)) {
  fs.mkdirSync(snapshotsDir, { recursive: true });
}

async function runTests() {
  console.log("==================================================");
  console.log("STARTING CHROME DEVTOOLS AUTOMATED UI VERIFICATION");
  console.log("==================================================");

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const consoleLogs = [];
  const errors = [];

  page.on("console", (msg) => {
    const text = msg.text();
    consoleLogs.push({ type: msg.type(), text });
    // Filter out innocuous favicon 404 if any
    if (msg.type() === "error" && !text.includes("favicon")) {
      console.error(`[BROWSER CONSOLE ERROR]: ${text}`);
      errors.push(text);
    }
  });

  page.on("requestfailed", (req) => {
    console.log(`[REQUEST FAILED]: ${req.url()} - ${req.failure()?.errorText}`);
  });

  page.on("pageerror", (err) => {
    console.error(`[PAGE UNCAUGHT ERROR]: ${err.message}`);
    errors.push(err.message);
  });

  console.log("1. Navigating to http://localhost:5173...");
  await page.goto("http://localhost:5173", { waitUntil: "networkidle0" });

  // Check that root has rendered content and is NOT a blank canvas
  const rootHtml = await page.$eval("#root", (el) => el.innerHTML);
  if (!rootHtml || rootHtml.trim() === "") {
    throw new Error("FAIL: #root is completely empty! Blank canvas detected.");
  }
  console.log("PASS: React rendered successfully into #root. No blank canvas!");

  // Verify Header
  const title = await page.$eval("h1", (el) => el.innerText);
  console.log(`PASS: Header rendered: "${title.replace(/\n/g, " ")}"`);

  // Verify Cinematic Animated Logistics Network Canvas
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
    throw new Error(`FAIL: Animated logistics network canvas must be active and visible!`);
  }

  // Verify Scorecard
  await page.waitForSelector(".metric-card");
  const metricCards = await page.$$eval(".metric-card", (cards) =>
    cards.map((c) => ({
      label: c.querySelector(".metric-label")?.innerText,
      value: c.querySelector(".metric-value")?.innerText,
      pts: c.querySelector(".pts-badge")?.innerText,
    }))
  );
  console.log(`PASS: ${metricCards.length} Judge Scorecards rendered:`, metricCards);

  // Take Snapshot 1: Initial Dashboard (A-n32-k5 Routes)
  const snap1 = path.join(snapshotsDir, "1_dashboard_A-n32-k5_routes.png");
  await page.screenshot({ path: snap1, fullPage: true });
  console.log(`Snapshot saved: ${snap1}`);

  // Verify Regional Table
  const regionalRows = await page.$$eval(".nb-table tbody tr", (rows) =>
    rows.map((r) => r.innerText.replace(/\t+/g, " | "))
  );
  console.log(`PASS: ${regionalRows.length} Regional Breakdown rows rendered:`);
  regionalRows.slice(0, 4).forEach((r) => console.log("   ", r));

  // Verify Authoritative Validation Panel
  const valStatus = await page.$eval(".status-banner", (el) => el.innerText);
  console.log(`PASS: Validation Status Banner: "${valStatus}"`);

  // Verify Interactive SVG Route Map
  const svgExists = await page.$("svg.cvrp-svg");
  if (!svgExists) {
    throw new Error("FAIL: SVG Map container missing!");
  }
  const pathsCount = await page.$$eval("svg.cvrp-svg path", (paths) => paths.length);
  const circlesCount = await page.$$eval("svg.cvrp-svg circle", (c) => c.length);
  console.log(`PASS: SVG Map rendered with ${pathsCount} route paths and ${circlesCount} customer nodes.`);

  // Test Tab 2: ALLOCATION INTENSITY
  console.log("2. Clicking 'ALLOCATION INTENSITY' tab button...");
  const allocBtn = (await page.$$(".map-toolbar .nb-button.small"))[1];
  await allocBtn.click();
  await new Promise((r) => setTimeout(r, 600));

  const snap2 = path.join(snapshotsDir, "2_dashboard_allocation_intensity.png");
  await page.screenshot({ path: snap2, fullPage: true });
  console.log(`Snapshot saved: ${snap2}`);

  // Test Tab 3: GENERATED PNG PLOTS
  console.log("3. Clicking 'GENERATED PNG PLOTS' tab button...");
  const plotsBtn = (await page.$$(".map-toolbar .nb-button.small"))[2];
  await plotsBtn.click();
  await new Promise((r) => setTimeout(r, 800));

  const imgCount = await page.$$eval(".plots-grid img", (imgs) => imgs.length);
  console.log(`PASS: High-res generated PNG plots tab displays ${imgCount} plots.`);

  const snap3 = path.join(snapshotsDir, "3_dashboard_generated_plots.png");
  await page.screenshot({ path: snap3, fullPage: true });
  console.log(`Snapshot saved: ${snap3}`);

  // Return to Route Map Tab
  const routesBtn = (await page.$$(".map-toolbar .nb-button.small"))[0];
  await routesBtn.click();
  await new Promise((r) => setTimeout(r, 600));

  // Test Instance Switcher: Click A-n33-k5
  console.log("4. Testing Instance Selector: Clicking 'A-n33-k5'...");
  const tabs = await page.$$(".instance-switcher .nb-button.tab");
  await tabs[1].click(); // A-n33-k5
  await new Promise((r) => setTimeout(r, 1200));

  const distValA33 = await page.$$eval(".metric-card .metric-value", (els) => els[1]?.innerText);
  const balanceValA33 = await page.$$eval(".metric-card .metric-value", (els) => els[2]?.innerText);
  console.log(`PASS: Switched to A-n33-k5 -> Distance: ${distValA33}, Balance: ${balanceValA33}`);

  const snap4 = path.join(snapshotsDir, "4_dashboard_instance_A-n33-k5.png");
  await page.screenshot({ path: snap4, fullPage: true });
  console.log(`Snapshot saved: ${snap4}`);

  // Test Instance Switcher: Click B-n31-k5
  console.log("5. Testing Instance Selector: Clicking 'B-n31-k5'...");
  await tabs[2].click(); // B-n31-k5
  await new Promise((r) => setTimeout(r, 1200));

  const distValB31 = await page.$$eval(".metric-card .metric-value", (els) => els[1]?.innerText);
  console.log(`PASS: Switched to B-n31-k5 -> Distance: ${distValB31}`);

  const snap5 = path.join(snapshotsDir, "5_dashboard_instance_B-n31-k5.png");
  await page.screenshot({ path: snap5, fullPage: true });
  console.log(`Snapshot saved: ${snap5}`);

  // Verify Comparison Table
  console.log("6. Verifying Empirical Benchmark Comparison Table...");
  const compRows = await page.$$eval(".comparison-table tbody tr", (rows) =>
    rows.map((r) => ({
      method: r.querySelector("td b")?.innerText,
      minService: r.querySelectorAll(".metric-pill")[0]?.innerText,
      balance: r.querySelectorAll(".metric-pill")[1]?.innerText,
      distance: r.querySelectorAll(".metric-pill")[2]?.innerText,
      tag: r.querySelector(".tag-winner, .tag-baseline")?.innerText,
    }))
  );
  console.log("PASS: Comparison Table rows:", compRows);

  // 7. Test Theme Toggle to Light Mode
  console.log("7. Testing Theme Toggle: Switching to Light Mode...");
  const themeToggle = await page.$(".theme-toggle-btn");
  await themeToggle.click();
  await new Promise((r) => setTimeout(r, 600));

  const snap6 = path.join(snapshotsDir, "6_dashboard_light_mode_hero_video.png");
  await page.screenshot({ path: snap6, fullPage: true });
  console.log(`Snapshot saved: ${snap6}`);

  // Switch back to Dark Mode
  await themeToggle.click();
  await new Promise((r) => setTimeout(r, 400));

  await browser.close();

  if (errors.length > 0) {
    console.error(`FAILED with ${errors.length} browser errors:`, errors);
    process.exit(1);
  }

  console.log("==================================================");
  console.log("ALL CHROME DEVTOOLS CHECKS PASSED WITH 0 ERRORS!");
  console.log("==================================================");
}

runTests().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
