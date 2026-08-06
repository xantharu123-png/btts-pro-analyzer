(() => {
  "use strict";

  const shared = globalThis.BetBoyN1Shared;
  if (!shared || !shared.isN1Url(location.href)) return;

  const QUOTE_SELECTOR = [
    "button",
    "[role='button']",
    "[data-testid*='odd' i]",
    "[data-testid*='outcome' i]",
    "[class*='odd' i]",
    "[class*='outcome' i]",
    "[class*='selection' i]",
  ].join(",");
  const HEADING_SELECTOR = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "[role='heading']",
    "[class*='market-name' i]",
    "[class*='market-title' i]",
    "[class*='event-name' i]",
    "[class*='event-title' i]",
  ].join(",");
  let scanTimer = null;
  let lastFingerprint = "";

  function cleanText(value, limit = 4000) {
    return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
  }

  function isVisible(element) {
    if (!(element instanceof Element)) return false;
    const style = getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
      return false;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 2 && rect.height > 2;
  }

  function ownLabel(element, odds) {
    const sources = [
      element.getAttribute("aria-label"),
      element.getAttribute("title"),
      element.getAttribute("data-selection-name"),
      element.getAttribute("data-outcome-name"),
      element.innerText,
      element.textContent,
    ];
    for (const source of sources) {
      const cleaned = cleanText(source, 300);
      if (!cleaned) continue;
      const stripped = shared.stripOdds(cleaned, odds);
      if (stripped && shared.parseDecimalOdds(stripped) === null) return stripped;
    }
    const parent = element.parentElement;
    if (!parent) return "";
    const siblings = Array.from(parent.children)
      .filter((node) => node !== element)
      .map((node) => cleanText(node.textContent, 120))
      .filter(Boolean);
    return siblings.join(" ").slice(0, 300);
  }

  function ancestorContexts(element) {
    const contexts = [];
    let current = element.parentElement;
    for (let depth = 0; current && depth < 9; depth += 1, current = current.parentElement) {
      const text = cleanText(current.innerText || current.textContent);
      if (text.length >= 12 && text.length <= 4000) {
        contexts.push({ element: current, text, depth });
      }
    }
    return contexts;
  }

  function usefulHeading(element, contexts) {
    for (const context of contexts) {
      const headings = Array.from(context.element.querySelectorAll(HEADING_SELECTOR))
        .filter((heading) => heading !== element && isVisible(heading))
        .map((heading) => cleanText(heading.innerText || heading.textContent, 180))
        .filter((text) => text.length >= 2 && text.length <= 180);
      if (headings.length) return headings[headings.length - 1];

      let sibling = context.element.previousElementSibling;
      for (let steps = 0; sibling && steps < 3; steps += 1, sibling = sibling.previousElementSibling) {
        const text = cleanText(sibling.innerText || sibling.textContent, 180);
        if (text.length >= 2 && text.length <= 180 && shared.parseDecimalOdds(text) === null) {
          return text;
        }
      }
    }
    return "";
  }

  function eventContext(contexts) {
    const withMultiplePrices = contexts.find(({ element, text }) => {
      if (text.length > 2500) return false;
      let priceCount = 0;
      for (const child of element.querySelectorAll(QUOTE_SELECTOR)) {
        if (shared.parseDecimalOdds(cleanText(child.innerText || child.textContent, 180)) !== null) {
          priceCount += 1;
          if (priceCount >= 2) return true;
        }
      }
      return false;
    });
    return (withMultiplePrices || contexts[0] || {}).text || "";
  }

  function inferLine(label, market) {
    const text = `${label} ${market}`;
    const match = text.match(/(?:over|under|ueber|über|unter|total)?\s*(\d{1,3}[.,]\d{1,2})/i);
    if (!match) return null;
    const number = Number(match[1].replace(",", "."));
    return Number.isFinite(number) && number >= 0 && number <= 1000 ? number : null;
  }

  function recordFromElement(element, capturedAt) {
    if (!isVisible(element) || element.closest("[aria-disabled='true'],[disabled]")) return null;
    const elementText = cleanText(element.innerText || element.textContent, 180);
    const odds = shared.parseDecimalOdds(elementText);
    if (odds === null) return null;
    const contexts = ancestorContexts(element);
    const context = eventContext(contexts);
    if (context.length < 12) return null;
    const selection = ownLabel(element, odds);
    const market = usefulHeading(element, contexts);
    if (!selection && !market) return null;
    const event = contexts
      .flatMap(({ element: contextElement }) => Array.from(contextElement.querySelectorAll(
        "[class*='event-name' i],[class*='event-title' i],[data-testid*='event' i]"
      )))
      .map((node) => cleanText(node.innerText || node.textContent, 300))
      .find((text) => text && shared.parseDecimalOdds(text) === null) || "";
    const stableContext = context.replace(/\b\d{1,3}[.,]\d{2,3}\b/g, " ");
    const normalized = shared.normalizeText(
      `${event}|${market}|${selection}|${stableContext}`
    );
    return {
      id: shared.shortHash(normalized),
      odds,
      event,
      market,
      selection,
      context,
      line: inferLine(selection, market),
      live: /(?:^|\s)(live|in play|jetzt live)(?:\s|$)/i.test(context),
      capturedAt,
      sourcePage: location.href,
    };
  }

  function scan() {
    const capturedAt = new Date().toISOString();
    const candidates = Array.from(document.querySelectorAll(QUOTE_SELECTOR));
    const seenElements = new Set();
    const records = [];
    const recordIds = new Set();
    for (const element of candidates) {
      if (seenElements.has(element)) continue;
      seenElements.add(element);
      const record = recordFromElement(element, capturedAt);
      if (!record || recordIds.has(record.id)) continue;
      recordIds.add(record.id);
      records.push(record);
      if (records.length >= 500) break;
    }
    const snapshot = {
      version: 1,
      bookmaker: "N1Bet",
      capturedAt,
      pageUrl: location.href,
      pageTitle: document.title,
      records,
      diagnostics: {
        scannedElements: candidates.length,
        pages: 1,
      },
    };
    const fingerprint = shared.shortHash(JSON.stringify(records.map((record) => [record.id, record.odds])));
    if (fingerprint !== lastFingerprint) {
      lastFingerprint = fingerprint;
      chrome.runtime.sendMessage({ type: "N1_SNAPSHOT", snapshot }).catch(() => {});
    }
    return snapshot;
  }

  function scheduleScan() {
    if (scanTimer) window.clearTimeout(scanTimer);
    scanTimer = window.setTimeout(scan, 800);
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== "SCAN_N1_PAGE") return false;
    sendResponse({ ok: true, snapshot: scan() });
    return false;
  });

  new MutationObserver(scheduleScan).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  scan();
})();
