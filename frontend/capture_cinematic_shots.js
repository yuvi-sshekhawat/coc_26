import puppeteer from "puppeteer";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const snapshotsDir = path.join(__dirname, "snapshots");

async function capture() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto("http://localhost:5173", { waitUntil: "networkidle0" });

  await page.waitForSelector(".hero-network-canvas");

  // Shot A: Wide National Overview (Scene 1)
  await new Promise((r) => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(snapshotsDir, "cinematic_1_wide.png"), fullPage: false });

  // Shot B: Zoomed into Depot & Route Activation (Scene 3)
  await new Promise((r) => setTimeout(r, 8500));
  await page.screenshot({ path: path.join(snapshotsDir, "cinematic_2_depot_focus.png"), fullPage: false });

  // Shot C: Vehicle V1 Follow along Route (Scene 4)
  await new Promise((r) => setTimeout(r, 5500));
  await page.screenshot({ path: path.join(snapshotsDir, "cinematic_3_vehicle_follow.png"), fullPage: false });

  // Shot D: Regional Pan to Sector 3 (Scene 5)
  await new Promise((r) => setTimeout(r, 6000));
  await page.screenshot({ path: path.join(snapshotsDir, "cinematic_4_sector3_pan.png"), fullPage: false });

  await browser.close();
  console.log("Cinematic snapshots captured successfully!");
}

capture().catch(console.error);
