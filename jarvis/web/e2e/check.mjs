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

async function open(browser, size, data, options = {}, path = "/") {
  const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2, ...options });
  const page = await context.newPage();
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (data === null) return route.fulfill({ status: 503, body: "down" });
    const body = { "/api/status": data.status, "/api/portfolio": data.portfolio, "/api/trades": data.trades, "/api/today": data.today, "/api/daytrading": data.daytrading ?? fx.daytradingEmpty, "/api/economics": data.economics ?? fx.economicsEmpty }[path];
    return route.fulfill({ json: body });
  });
  await page.goto(BASE + path);
  return page;
}

const full = { status: fx.status, portfolio: fx.portfolio, trades: fx.trades, today: fx.today, daytrading: fx.daytrading, economics: fx.economics };
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

  // Day trading: the home card, then the details one tap away.
  await page.getByRole("link", { name: /pausat daytrading/ }).click();
  await page.getByRole("heading", { name: "Daytrading" }).waitFor();
  assert.equal(await page.locator(".status-line").first().getAttribute("data-tone"), "warning");
  assert.match(await page.locator(".facts").innerText(), /1 av 5[\s\S]*▼ −1\s820,40\skr[\s\S]*3 av 3/);
  assert.match(await page.locator("text=NKE · 60 st").locator("xpath=ancestor::li").innerText(), /▼ −89,20\sUSD/);
  assert.match(await page.locator("text=AMD · 20 st").first().locator("xpath=ancestor::li").innerText(), /Öppen/);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
  await page.screenshot({ path: `${SHOTS}daytrading-${name}.png`, fullPage: true });

  page = await open(browser, size, { ...full, daytrading: fx.daytradingEmpty }, {}, "/daytrading");
  await page.getByText("Inga daytrades i dag.").waitFor();
  await page.getByText("Daytrading är avstängd tills strategin har klarat valideringen.").first().waitFor();
  await page.screenshot({ path: `${SHOTS}daytrading-empty-${name}.png`, fullPage: true });

  // Economics: the honest comparison, costs and tax.
  page = await open(browser, size, full);
  await page.getByRole("link", { name: /procentenheter före/ }).click();
  await page.getByRole("heading", { name: "Ekonomi" }).waitFor();
  assert.match(await page.locator(".facts").first().innerText(), /▲ \+4,62\s%[\s\S]*▲ \+3,38\s%[\s\S]*\+1,24 procentenheter/);
  assert.equal(await page.locator("path.series").count(), 2);
  const box = await page.locator(".chart svg").boundingBox();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2);
  await page.locator(".tooltip").waitFor();
  assert.match(await page.locator(".tooltip").innerText(), /Jarvis [+−]/);
  await page.getByText("Break-even").waitFor();
  await page.getByText("Jag gissar dem aldrig.").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
  await page.screenshot({ path: `${SHOTS}economics-${name}.png`, fullPage: true });

  page = await open(browser, size, { ...full, economics: fx.economicsEmpty }, {}, "/ekonomi");
  await page.getByText("Grafen visas när jag har följt både kontot och indexfonden").waitFor();
  await page.getByText("Inga avgifter ännu.").waitFor();
  await page.screenshot({ path: `${SHOTS}economics-empty-${name}.png`, fullPage: true });

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
  return route.fulfill({ json: { "/api/status": fx.status, "/api/portfolio": fx.portfolio, "/api/trades": fx.trades, "/api/today": fx.today, "/api/daytrading": fx.daytrading, "/api/economics": fx.economics }[path] });
});
await page.getByRole("button", { name: "Försök igen" }).click();
await page.getByText("Jarvis handlar").waitFor();

// Paused and reduced motion.
page = await open(browser, SIZES.iphone, { ...full, status: { ...fx.status, trading_state: "paused", reasons: [{ code: "paused", message_sv: "Handeln är pausad." }] } }, { reducedMotion: "reduce" });
await page.getByText("Pausad", { exact: true }).waitFor();
assert.equal(await page.locator(".orb").getAttribute("data-tone"), "dimmed");
assert.equal(await page.locator(".orb-core").evaluate((el) => getComputedStyle(el).animationName), "none");

// Settings: passkey setup with a virtual authenticator (WebAuthn needs the localhost host).
for (const [name, size] of Object.entries(SIZES)) {
  const context = await browser.newContext({ viewport: size, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true },
  });
  let registered = false;
  let controls = { mode: "paper", paused: false, kill_switch_engaged: false, budget_pct: "100", pending_budget_pct: null, pending_budget_from: null };
  let loggedIn = false;
  const sent = {};
  const challenge = "dGVzdC1jaGFsbGVuZ2UtMzItYnl0ZXMtbG9uZy0xMjM0";
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST") {
      sent[path] = { headers: request.headers(), body: request.postDataJSON() };
    }
    if (path === "/api/auth/state") return route.fulfill({ json: { registered, logged_in: loggedIn } });
    if (path === "/api/today") return route.fulfill({ json: fx.today });
    if (path === "/api/portfolio") return route.fulfill({ json: fx.portfolio });
    if (path === "/api/economics") return route.fulfill({ json: fx.economics });
    if (path === "/api/controls") return route.fulfill({ json: controls });
    if (path === "/api/actions/control") { controls = { ...controls, paused: true }; return route.fulfill({ json: { message_sv: "Handeln är pausad. Öppna positioner skyddas av stoppordrarna hos mäklaren." } }); }
    if (path === "/api/actions/trading-mode") { controls = { ...controls, mode: "live", budget_pct: "10" }; return route.fulfill({ json: { message_sv: "Riktig handel är vald med en budget på högst 10 % av kontot." } }); }
    if (path === "/api/auth/register/options") {
      if (request.postDataJSON().setup_code !== "kod-123") return route.fulfill({ status: 403, json: { detail: "Fel engångskod." } });
      return route.fulfill({ json: {
        rp: { name: "Jarvis", id: "localhost" }, user: { id: "YWRhbQ", name: "adam", displayName: "Adam" },
        challenge, pubKeyCredParams: [{ type: "public-key", alg: -7 }], timeout: 60000, excludeCredentials: [],
        authenticatorSelection: { residentKey: "required", requireResidentKey: true, userVerification: "required" }, attestation: "none",
      } });
    }
    if (path === "/api/auth/register/verify") { registered = true; loggedIn = true; return route.fulfill({ json: { ok: true } }); }
    if (path === "/api/actions/options") return route.fulfill({ json: { challenge, timeout: 60000, rpId: "localhost", allowCredentials: [], userVerification: "required" } });
    if (path === "/api/actions/deposit") return route.fulfill({ json: { message_sv: "Jag har registrerat insättningen. Den räknas inte som vinst eller förlust." } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("http://localhost:3111/installningar");
  await page.getByRole("heading", { name: "Skapa din passkey" }).waitFor();
  await page.screenshot({ path: `${SHOTS}settings-setup-${name}.png`, fullPage: true });
  await page.getByLabel("Engångskod").fill("fel");
  await page.getByRole("button", { name: "Skapa passkey" }).click();
  await page.getByText("Fel engångskod.").waitFor();
  await page.getByLabel("Engångskod").fill("kod-123");
  await page.getByRole("button", { name: "Skapa passkey" }).click();
  await page.getByRole("heading", { name: "Insättning eller uttag" }).waitFor();
  const attestation = sent["/api/auth/register/verify"].body.credential;
  assert.equal(attestation.type, "public-key");
  assert.ok(attestation.response.attestationObject.length > 50);
  assert.equal(sent["/api/auth/register/verify"].headers["x-jarvis"], "1");

  await page.getByLabel("Belopp i kronor").fill("12 500,50");
  await page.getByRole("button", { name: "Bekräfta med passkey" }).click();
  await page.getByText("Jag har registrerat insättningen.", { exact: false }).waitFor();
  assert.deepEqual(sent["/api/actions/options"].body, { action: "deposit", payload: { amount: "12500.50", note: "" } });
  assert.equal(sent["/api/actions/deposit"].body.amount, "12500.50");
  assert.ok(sent["/api/actions/deposit"].body.credential.response.signature.length > 20);
  // Pause, the budget preview and switching to live trading.
  await page.getByText("Handeln är igång.").waitFor();
  await page.getByRole("button", { name: "Pausa" }).click();
  await page.getByRole("button", { name: "Återuppta" }).waitFor();
  assert.deepEqual(sent["/api/actions/options"].body, { action: "control", payload: { command: "pause" } });
  assert.match(await page.locator("#budget-h").locator("xpath=..").innerText(), /100 %[\s\S]*Max per affär[\s\S]*ca 10\s048,24\skr/);
  await page.getByRole("button", { name: "Aktivera riktig handel" }).click();
  const liveButton = page.getByRole("button", { name: "Slå på riktig handel med passkey" });
  await page.getByLabel("Skriv JAG FÖRSTÅR RISKEN").fill("jag förstår risken");
  assert.equal(await liveButton.isDisabled(), true);
  await page.getByLabel("Skriv JAG FÖRSTÅR RISKEN").fill("JAG FÖRSTÅR RISKEN");
  await page.screenshot({ path: `${SHOTS}settings-live-${name}.png`, fullPage: true });
  await liveButton.click();
  await page.getByText("Riktig handel är vald.", { exact: true }).waitFor();
  assert.deepEqual(sent["/api/actions/trading-mode"].body.budget_pct, "10");
  await page.getByRole("button", { name: "Tillbaka till papper" }).waitFor();

  await page.getByRole("radio", { name: "Uttag" }).click();
  await page.getByLabel("Belopp i kronor").fill("12,345");
  assert.equal(await page.getByRole("button", { name: "Bekräfta med passkey" }).isDisabled(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
  await page.screenshot({ path: `${SHOTS}settings-${name}.png`, fullPage: true });
  await context.close();
}

await browser.close();
console.log("OK: home, day-trading, economics and settings verified, screenshots saved");
