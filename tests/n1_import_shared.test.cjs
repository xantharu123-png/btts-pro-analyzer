const test = require("node:test");
const assert = require("node:assert/strict");
const shared = require("../browser_extension/n1bet_importer/shared.js");

test("decimal odds parser accepts one exact decimal price", () => {
  assert.equal(shared.parseDecimalOdds("Luciano Darderi 2.60"), 2.6);
  assert.equal(shared.parseDecimalOdds("Over 2.5 1.91"), 1.91);
  assert.equal(shared.parseDecimalOdds("1.90 2.10"), null);
  assert.equal(shared.parseDecimalOdds("Kickoff 19:30"), null);
});

test("snapshot merge keeps recent observations and latest duplicate", () => {
  const now = Date.parse("2026-08-06T18:30:00Z");
  const base = {
    version: 1,
    bookmaker: "N1Bet",
    capturedAt: "2026-08-06T18:29:00Z",
    diagnostics: { scannedElements: 4 },
  };
  const merged = shared.mergeSnapshots([
    { ...base, records: [{ id: "a", odds: 1.9, capturedAt: base.capturedAt }] },
    {
      ...base,
      capturedAt: "2026-08-06T18:29:30Z",
      records: [{ id: "a", odds: 2.0, capturedAt: "2026-08-06T18:29:30Z" }],
    },
  ], now);
  assert.equal(merged.records.length, 1);
  assert.equal(merged.records[0].odds, 2.0);
  assert.equal(merged.diagnostics.pages, 2);
});

test("only real N1Bet HTTPS origins are accepted", () => {
  assert.equal(shared.isN1Url("https://bet.n1bet.com/sportsbook"), true);
  assert.equal(shared.isN1Url("https://n1bet.com/sports"), true);
  assert.equal(shared.isN1Url("https://n1bet.com.example.org"), false);
  assert.equal(shared.isN1Url("http://n1bet.com/sports"), false);
});
