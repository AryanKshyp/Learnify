/** Smoke-check the session flow specifically. Run with the dev server up: node drive2.mjs */
import { chromium } from "playwright-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
await page.waitForSelector("#cy canvas", { timeout: 20000 });
await page.evaluate(() => window.__cy?.nodes().first().emit("tap"));
await page.waitForSelector(".inspector h2", { timeout: 15000 });

await page.getByRole("button", { name: "Start assessment" }).click();
await page.waitForSelector("button:has-text('Copy the Study prompt')", { timeout: 20000 });
await page.waitForTimeout(800);
await page.screenshot({ path: "shot-5-session-study.png" });
console.log("study step rendered");

await page.getByRole("button", { name: "3 · Wrap up" }).click();
await page.waitForSelector("textarea", { timeout: 15000 });
await page.waitForTimeout(900);
await page.screenshot({ path: "shot-6-session-wrapup.png" });
console.log("wrapup step rendered");

const len = await page.evaluate(
  () => document.querySelector("pre.payload")?.textContent?.length ?? 0,
);
console.log("wrapup prompt chars:", len);
console.log(errors.length ? "CONSOLE ERRORS:\n  " + errors.join("\n  ") : "no console errors");

await browser.close();
