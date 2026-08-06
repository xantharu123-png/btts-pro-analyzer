importScripts("shared.js");

const STORAGE_KEY = "n1Snapshots";

async function storedSnapshots() {
  const stored = await chrome.storage.local.get(STORAGE_KEY);
  return Array.isArray(stored[STORAGE_KEY]) ? stored[STORAGE_KEY] : [];
}

async function saveSnapshot(snapshot, sender) {
  if (!snapshot || !BetBoyN1Shared.isN1Url(snapshot.pageUrl)) {
    throw new Error("Ungueltige N1Bet-Quelle");
  }
  const senderUrl = sender && sender.tab && sender.tab.url;
  if (!BetBoyN1Shared.isN1Url(senderUrl)) throw new Error("Absender ist nicht N1Bet");
  const snapshots = await storedSnapshots();
  const pageKey = new URL(snapshot.pageUrl).origin + new URL(snapshot.pageUrl).pathname;
  const retained = snapshots.filter((item) => item.pageKey !== pageKey);
  retained.push({ ...snapshot, pageKey });
  const recent = retained
    .filter((item) => Date.now() - Date.parse(item.capturedAt) <= 15 * 60 * 1000)
    .slice(-20);
  await chrome.storage.local.set({ [STORAGE_KEY]: recent });
  await updateBadge(recent);
  return BetBoyN1Shared.mergeSnapshots(recent);
}

async function latestSnapshot() {
  const merged = BetBoyN1Shared.mergeSnapshots(await storedSnapshots());
  return merged.diagnostics.pages > 0 ? merged : null;
}

async function updateBadge(snapshots) {
  const merged = BetBoyN1Shared.mergeSnapshots(snapshots);
  const count = merged.records.length;
  await chrome.action.setBadgeBackgroundColor({ color: count ? "#18794e" : "#6b7280" });
  await chrome.action.setBadgeText({ text: count ? String(Math.min(count, 999)) : "" });
}

chrome.runtime.onInstalled.addListener(async () => {
  await updateBadge(await storedSnapshots());
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== "string") return false;
  if (message.type === "N1_SNAPSHOT") {
    saveSnapshot(message.snapshot, sender)
      .then((snapshot) => sendResponse({ ok: true, snapshot }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "GET_LATEST_N1") {
    latestSnapshot()
      .then((snapshot) => sendResponse({ ok: true, snapshot }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "CLEAR_N1") {
    chrome.storage.local.remove(STORAGE_KEY)
      .then(() => updateBadge([]))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message.type === "SCAN_ACTIVE_N1") {
    chrome.tabs.query({ active: true, currentWindow: true })
      .then(([tab]) => {
        if (!tab || !tab.id || !BetBoyN1Shared.isN1Url(tab.url)) {
          throw new Error("Aktiver Tab ist keine N1Bet-Seite");
        }
        return chrome.tabs.sendMessage(tab.id, { type: "SCAN_N1_PAGE" });
      })
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  return false;
});
