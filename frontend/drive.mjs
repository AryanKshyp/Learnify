/**
 * Headless driver for verifying the UI actually renders.
 *
 * Uses the Chrome already installed on this machine (playwright-core, no browser download).
 * Not part of the app — a dev-time smoke check, run by hand:
 *
 *     node drive.mjs
 */

import { chromium } from "playwright-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForSelector("#cy canvas", { timeout: 20000 });
await page.waitForTimeout(1200);
await page.screenshot({ path: "shot-1-graph.png" });
console.log("1. graph home rendered");

// Select a node through cytoscape's own API rather than guessing pixel coordinates -
// a blind mouse.click silently misses and produces a false pass.
const picked = await page.evaluate(() => {
  const cy = window.__cy;
  if (!cy) return null;
  const node = cy.nodes().first();
  node.emit("tap");
  return { id: node.id(), total: cy.nodes().length };
});
console.log(`   frontier nodes: ${picked?.total}, clicked: ${picked?.id}`);
await page.waitForSelector(".inspector h2", { timeout: 15000 });
await page.waitForTimeout(1800);
await page.screenshot({ path: "shot-2-focused.png" });
console.log("2. clicked a node");

// recommendations tab
await page.getByRole("button", { name: "What next" }).click();
await page.waitForSelector(".rec", { timeout: 15000 });
await page.waitForTimeout(600);
await page.screenshot({ path: "shot-3-recommendations.png" });
console.log("3. recommendations rendered");

// readiness tab
await page.getByRole("button", { name: "Readiness" }).click();
await page.waitForSelector(".big-number", { timeout: 15000 });
await page.waitForTimeout(600);
await page.screenshot({ path: "shot-4-readiness.png" });
console.log("4. readiness rendered");

console.log(errors.length ? `CONSOLE ERRORS:\n  ${errors.join("\n  ")}` : "no console errors");
await browser.close();
