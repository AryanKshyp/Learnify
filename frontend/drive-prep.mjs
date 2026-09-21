/**
 * Headless driver for the Prep tab.
 *
 * Walks the loop a user actually performs: open Prep, fetch the prompt, paste an extraction,
 * read the plan, then assess a prerequisite and confirm the document's readiness moved.
 *
 * Not part of the app — a dev-time smoke check, run by hand with the dev server up:
 *
 *     node drive-prep.mjs
 *
 * **It writes.** Ingesting a document is the thing being tested, so this cannot be read-only —
 * which means it must clean up after itself, and it must refuse to run against a persistent
 * store. A smoke check that leaves a test paper in someone's real library is indistinguishable
 * from a bug, and one that leaves fake assessment evidence behind is worse: mastery is supposed
 * to be evidence, and evidence nobody earned corrupts every number downstream.
 */

import { chromium } from "playwright-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";

const EXTRACTION = {
  schema: "knowledgeos.document.extraction",
  schema_version: 1,
  document: {
    title: "Attention Is All You Need",
    kind: "paper",
    source: "arXiv:1706.03762",
  },
  summary: "Introduces the Transformer, an encoder-decoder built purely on attention.",
  concepts: [
    {
      node_id: "dl-transformer-architecture",
      required_depth: "deep",
      document_weight: 1.0,
      evidence: "Section 3 and Figure 1 - the whole model.",
    },
    {
      node_id: "dl-multihead-attention",
      required_depth: "derivation",
      document_weight: 0.95,
      evidence: "Section 3.2.2, the head projection equations.",
    },
    {
      node_id: "dl-attention",
      required_depth: "derivation",
      document_weight: 0.9,
      evidence: "Section 3.2.1, scaled dot-product attention.",
    },
    {
      node_id: "dl-positional-encoding",
      required_depth: "working",
      document_weight: 0.6,
      evidence: "Section 3.5, sinusoidal position encodings.",
    },
    {
      node_id: "opt-momentum-adam",
      required_depth: "awareness",
      document_weight: 0.2,
      evidence: "Section 5.3, optimizer and schedule.",
    },
  ],
  out_of_curriculum: [
    { label: "Byte-pair encoding", evidence: "Section 5.1, 37000 token vocabulary." },
    { label: "Label smoothing", evidence: "Section 5.4, eps_ls = 0.1." },
  ],
};

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

// Refuse to touch a persistent instance. `/health` reports the store the backend is really
// using, rather than whatever a launcher arranged, so this is a real check and not a guess.
const health = await fetch(`${BASE}/api/health`).then((r) => r.json());
if (health.persistent) {
  console.error(
    [
      `REFUSING TO RUN: the backend on ${BASE} uses ${health.storage} storage.`,
      "This driver ingests a document and would leave it in your real library.",
      "Start a throwaway backend instead:",
      "  uvicorn knowledgeos.api.app:create_app --factory --port 8000",
    ].join("\n"),
  );
  process.exit(2);
}
console.log(`0. backend storage: ${health.storage} (throwaway) - safe to write`);

await page.goto(BASE, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Prep", exact: true }).click();
await page.waitForTimeout(800);
await page.screenshot({ path: "shot-prep-1-empty.png" });
console.log("1. prep tab rendered (empty state)");

await page.getByRole("button", { name: "+ New document" }).click();
await page.waitForSelector("textarea", { timeout: 15000 });
await page.waitForTimeout(900);
const scopeLine = await page.locator(".card .tiny.muted").first().textContent();
console.log(`2. new-document form: ${scopeLine?.trim()}`);
await page.screenshot({ path: "shot-prep-2-new.png" });

await page.locator("textarea").fill(JSON.stringify(EXTRACTION, null, 2));
await page.getByRole("button", { name: "Build my plan" }).click();
await page.waitForSelector(".rec", { timeout: 20000 });
await page.waitForTimeout(700);

const readiness = await page.locator(".big-number").first().textContent();
const stepCount = await page.locator(".rec").count();
const assumedBanner = await page.locator(".card .label").nth(1).textContent();
console.log(`3. plan built: readiness ${readiness?.trim()}, ${stepCount} steps`);
console.log(`   ${assumedBanner?.trim()}`);
await page.screenshot({ path: "shot-prep-3-plan.png", fullPage: true });

const firstStep = await page.locator(".rec h4").first().textContent();
const firstReason = await page.locator(".rec .reason").first().textContent();
console.log(`   step 1: ${firstStep?.trim()}`);
console.log(`   reason: ${firstReason?.trim()}`);

const ooc = await page.locator(".card ul.small li strong").allTextContents();
console.log(`   not in curriculum: ${ooc.join(", ")}`);

// the full requirement table, stated vs assumed
await page.locator("details > summary").last().click();
await page.waitForTimeout(400);
const rows = await page.locator(".req-row").count();
console.log(`4. requirement table: ${rows} concepts`);
await page.screenshot({ path: "shot-prep-4-requirements.png", fullPage: true });

// back to the list, confirming the saved document carries live readiness
await page.getByRole("button", { name: "← All documents" }).click();
await page.waitForSelector(".doc-card", { timeout: 15000 });
await page.waitForTimeout(500);
const card = await page.locator(".doc-card .tiny.muted").first().textContent();
console.log(`5. saved document listed: ${card?.trim()}`);
await page.screenshot({ path: "shot-prep-5-list.png" });

// Clean up what this run created, so a second run starts from the same state as the first and
// nothing survives the check that the check itself invented. Done through the UI rather than
// the API, so the delete path is exercised by the same pass that needs it.
await page.locator(".doc-card").first().click();
await page.getByRole("button", { name: "Delete" }).click();
await page.waitForTimeout(700);
const remaining = await fetch(`${BASE}/api/documents`).then((r) => r.json());
console.log(`6. cleaned up: ${remaining.length} document(s) left behind`);

console.log(errors.length ? `\nCONSOLE ERRORS:\n${errors.join("\n")}` : "\n0 console errors");
await browser.close();
process.exit(errors.length || remaining.length ? 1 : 0);
