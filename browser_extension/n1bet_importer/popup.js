(() => {
  "use strict";

  const status = document.getElementById("status");
  const scan = document.getElementById("scan");
  const clear = document.getElementById("clear");

  function ageLabel(capturedAt) {
    const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(capturedAt)) / 1000));
    return seconds < 60 ? `vor ${seconds} Sek.` : `vor ${Math.floor(seconds / 60)} Min.`;
  }

  async function refresh() {
    const response = await chrome.runtime.sendMessage({ type: "GET_LATEST_N1" });
    const snapshot = response && response.snapshot;
    if (!snapshot || !snapshot.records || !snapshot.records.length) {
      status.textContent = "Noch keine sichtbaren N1Bet-Quoten erfasst.";
      return;
    }
    status.textContent = `${snapshot.records.length} Quoten, ${ageLabel(snapshot.capturedAt)}`;
  }

  scan.addEventListener("click", async () => {
    scan.disabled = true;
    const response = await chrome.runtime.sendMessage({ type: "SCAN_ACTIVE_N1" });
    status.textContent = response && response.ok
      ? `${response.snapshot.records.length} Quoten erfasst.`
      : (response && response.error) || "N1Bet-Seite konnte nicht gelesen werden.";
    scan.disabled = false;
  });

  clear.addEventListener("click", async () => {
    await chrome.runtime.sendMessage({ type: "CLEAR_N1" });
    await refresh();
  });

  refresh().catch(() => {
    status.textContent = "Importer konnte nicht gestartet werden.";
  });
})();
