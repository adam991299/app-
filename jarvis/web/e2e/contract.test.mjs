// Fails if web/lib/api.ts and contracts/api.schema.json disagree on any property name.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const schema = JSON.parse(readFileSync(new URL("../../contracts/api.schema.json", import.meta.url), "utf8"));
const source = readFileSync(new URL("../lib/api.ts", import.meta.url), "utf8");
const block = /export const CONTRACT_KEYS = (\{[\s\S]*?\}) as const;/.exec(source)?.[1];
const keys = new Function(`return ${block}`)();

const models = {};
for (const endpoint of Object.values(schema.endpoints)) {
  models[endpoint.title] = endpoint;
  Object.assign(models, endpoint.$defs ?? {});
}

test("every contract model is mirrored with the same properties", () => {
  assert.deepEqual(Object.keys(keys).sort(), Object.keys(models).sort());
  for (const [name, model] of Object.entries(models)) {
    assert.deepEqual([...keys[name]].sort(), Object.keys(model.properties).sort(), name);
    assert.deepEqual([...model.required].sort(), Object.keys(model.properties).sort(), `${name} required`);
  }
});

test("the TypeScript interfaces declare exactly the mirrored keys", () => {
  const interfaces = { StatusOut: "Status", ReasonOut: "Reason", MarketOut: "Market", PortfolioOut: "Portfolio", PositionOut: "Position", TradesOut: "Trades", TradeOut: "Trade", TodayOut: "Today", DaytradingOut: "Daytrading", DayTradeOut: "DayTrade" };
  for (const [model, name] of Object.entries(interfaces)) {
    const body = new RegExp(`export interface ${name} \\{([\\s\\S]*?)\\n\\}`).exec(source)?.[1] ?? "";
    const declared = [...body.matchAll(/^\s+(\w+):/gm)].map((m) => m[1]);
    assert.deepEqual(declared.sort(), [...keys[model]].sort(), name);
  }
});
