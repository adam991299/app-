// Runs the built app against example data, asserts the key states and saves screenshots.
// Usage: next build, next start -p 3111, then: node e2e/check.mjs
import assert from "node:assert/strict";
import { createRequire } from "node:module";

import * as fx from "./fixtures.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = "http://127.0.0.1:3111";
const SHOTS = new URL("../../docs/screenshots/", import.meta.url).pathname;
const SIZES = { iphone: { width: 390, height: 844 }, desktop: { width: 1440, height: 900 } };

async function open(browser, size, data, options = {}) {
  const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2, ...options });
  const page = await context.newPage();
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (data === null) return route.fulfill({ status: 503, body: "down" });
    const body = { "/api/status": data.status, "/api/portfolio": data.portfolio, "/api/trades": data.trades, "/api/today": data.today }[path];
    return route.fulfill({ json: body });
  });
  await page.goto(BASE);
  return page;
}

const full = { status: fx.status, portfolio: fx.portfolio, trades: fx.trades, today: fx.today };
const kill = { ...full, status: fx.killSwitch };
const browser = await chromium.launch();

for (const [name, size] of Object.entries(SIZES)) {
  let page = await open(browser, size, full);
  await page.getByText("Jarvis handlar").waitFor();
  assert.equal(await page.locator(".big-number").innerText(), "100 482,35 kr");
  assert.match(await page.locator(".hero .change").innerText(), /▲ \+482,35 kr \(\+0,48 %\)/);
  assert.match(await page.locator("text=XOM").first().locator("xpath=ancestor::li").innerText(), /▼ −259,75 kr \(−1,03 %\)/);
  assert.equal(await page.locator(".badge").innerText(), "PAPPER");
  assert.equal(await page.locator(".orb").getAttribute("data-tone"), "calm");
  assert.match(await page.locator("text=Köpt 40 XOM").locator("xpath=ancestor::li").innerText(), /16 nov\.? 16:12/);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
  await page.screenshot({ path: `${SHOTS}home-${name}.png`, fullPage: true });

  page = await open(browser, size, fx.empty);
  await page.getByText("Jarvis väntar – marknaden stängd").waitFor();
  await page.getByText("Inga innehav just nu.").waitFor();
  await page.getByText("Inga affärer ännu.").waitFor();
  assert.equal(await page.locator(".orb").getAttribute("data-tone"), "waiting");
  await page.screenshot({ path: `${SHOTS}home-empty-${name}.png`, fullPage: true });

  page = await open(browser, size, kill);
  await page.getByText("Kill switch aktiv").waitFor();
  await page.getByText("Du behöver starta handeln igen i appen.").waitFor();
  assert.equal(await page.locator(".orb").getAttribute("data-tone"), "warning");
  await page.screenshot({ path: `${SHOTS}home-kill-switch-${name}.png`, fullPage: true });
}

// Server unreachable: a calm error state with retry, never a blank page.
let page = await open(browser, SIZES.iphone, null);
await page.getByText("Jag når inte servern just nu.").waitFor({ timeout: 20000 });
await page.unroute("**/api/**");
await page.route("**/api/**", (route) => {
  const path = new URL(route.request().url()).pathname;
  return route.fulfill({ json: { "/api/status": fx.status, "/api/portfolio": fx.portfolio, "/api/trades": fx.trades, "/api/today": fx.today }[path] });
});
await page.getByRole("button", { name: "Försök igen" }).click();
await page.getByText("Jarvis handlar").waitFor();

// Paused and reduced motion.
page = await open(browser, SIZES.iphone, { ...full, status: { ...fx.status, trading_state: "paused", reasons: [{ code: "paused", message_sv: "Handeln är pausad." }] } }, { reducedMotion: "reduce" });
await page.getByText("Pausad", { exact: true }).waitFor();
assert.equal(await page.locator(".orb").getAttribute("data-tone"), "dimmed");
assert.equal(await page.locator(".orb-core").evaluate((el) => getComputedStyle(el).animationName), "none");

await browser.close();
console.log("OK: home screen states verified, screenshots saved");
