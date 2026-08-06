(function initialiseShared(root, factory) {
  const api = factory();
  root.BetBoyN1Shared = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function sharedFactory() {
  "use strict";

  const MAX_ODDS = 1000;

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/ß/g, "ss")
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function plausibleOdds(value) {
    const number = Number(String(value).replace(",", "."));
    return Number.isFinite(number) && number > 1 && number <= MAX_ODDS
      ? Math.round(number * 10000) / 10000
      : null;
  }

  function oddsTokens(value) {
    const text = String(value || "");
    const matches = text.match(/(?:^|\s)(\d{1,3}[.,]\d{2,3})(?=\s|$)/g) || [];
    return matches
      .map((token) => plausibleOdds(token.trim()))
      .filter((number) => number !== null);
  }

  function parseDecimalOdds(value) {
    const tokens = oddsTokens(value);
    if (tokens.length !== 1) return null;
    return tokens[0];
  }

  function stripOdds(value, odds) {
    const escaped = String(odds).replace(".", "[.,]");
    return String(value || "")
      .replace(new RegExp(`(?:^|\\s)${escaped}0*(?=\\s|$)`, "g"), " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function shortHash(value) {
    let hash = 2166136261;
    const text = String(value || "");
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function isN1Url(value) {
    try {
      const url = new URL(String(value));
      const host = url.hostname.toLowerCase();
      return url.protocol === "https:"
        && (host === "n1bet.com" || host.endsWith(".n1bet.com"));
    } catch (_error) {
      return false;
    }
  }

  function mergeSnapshots(snapshots, now = Date.now()) {
    const recent = (Array.isArray(snapshots) ? snapshots : [])
      .filter((snapshot) => {
        const timestamp = Date.parse(snapshot && snapshot.capturedAt);
        return Number.isFinite(timestamp) && now - timestamp <= 15 * 60 * 1000;
      })
      .slice(-20);
    const records = new Map();
    let scannedElements = 0;
    for (const snapshot of recent) {
      scannedElements += Number(snapshot.diagnostics && snapshot.diagnostics.scannedElements) || 0;
      for (const record of Array.isArray(snapshot.records) ? snapshot.records : []) {
        if (!record || !record.id) continue;
        const existing = records.get(record.id);
        if (!existing || Date.parse(record.capturedAt) >= Date.parse(existing.capturedAt)) {
          records.set(record.id, record);
        }
      }
    }
    const capturedAt = recent.reduce((latest, snapshot) => {
      return Date.parse(snapshot.capturedAt) > Date.parse(latest)
        ? snapshot.capturedAt
        : latest;
    }, "1970-01-01T00:00:00.000Z");
    return {
      version: 1,
      bookmaker: "N1Bet",
      capturedAt,
      records: Array.from(records.values()).slice(0, 1200),
      diagnostics: {
        pages: recent.length,
        scannedElements,
      },
    };
  }

  return {
    isN1Url,
    mergeSnapshots,
    normalizeText,
    oddsTokens,
    parseDecimalOdds,
    plausibleOdds,
    shortHash,
    stripOdds,
  };
});
