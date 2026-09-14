/**
 * Headless check for the per-session role selector. Dev-time only, run by hand:
 *
 *     node drive-role.mjs
 */

import { chromium } from "playwright-core";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = "http://localhost:5173";

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(BASE, { waitUntil: "networkidle" });

await page.getByRole("button", { name: /browse/i }).click();
await page.waitForTimeout(800);

const search = page.locator("input").first();
await search.fill("Big-O");
await page.waitForTimeout(1000);
await page.screenshot({ path: "shot-role-1-search.png" });

await page.getByText("Big-O & Complexity Analysis").first().click();
await page.waitForTimeout(1000);
await page.screenshot({ path: "shot-role-2-inspector.png" });

await page.getByRole("button", { name: /start assessment/i }).first().click();
await page.waitForSelector(".inspector select", { timeout: 15000 });
await page.waitForTimeout(1500);
await page.screenshot({ path: "shot-role-3-default.png" });

const sel = page.locator(".inspector select").first();
console.log("DEFAULT value:", JSON.stringify(await sel.inputValue()));
console.log("OPTIONS:", await sel.locator("option").allTextContents());
console.log("BLURB:", (await page.locator(".inspector .card p.tiny").first().textContent())?.trim());

await page.getByText("Preview the prompt").click();
await page.waitForTimeout(800);

const readPrompt = async () => {
  const text = await page.locator(".inspector pre.payload").first().textContent();
  return {
    depth: /Target depth: `(\w+)`/.exec(text ?? "")?.[1],
    role: /preparing for \*\*([\w-]+)\*\*/.exec(text ?? "")?.[1],
  };
};

console.log("DEFAULT prompt:", await readPrompt());

await sel.selectOption("ai-research");
await page.waitForTimeout(1800);
await page.screenshot({ path: "shot-role-4-ai-research.png" });
console.log("AI-RESEARCH prompt:", await readPrompt());

await sel.selectOption("software-engineering");
await page.waitForTimeout(1800);
console.log("SWE prompt:", await readPrompt());

console.log("CONSOLE ERRORS:", errors.length, errors.slice(0, 5));
await browser.close();
