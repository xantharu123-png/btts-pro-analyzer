(() => {
  "use strict";

  const CHANNEL = "BETBOY_N1_IMPORT";
  window.addEventListener("message", (event) => {
    const message = event.data || {};
    if (message.channel !== CHANNEL || message.type !== "SNAPSHOT_REQUEST") return;
    const targetWindow = event.source;
    const targetOrigin = event.origin && event.origin !== "null" ? event.origin : "*";
    chrome.runtime.sendMessage({ type: "GET_LATEST_N1" })
      .then((response) => {
        targetWindow.postMessage({
          channel: CHANNEL,
          type: "SNAPSHOT_RESPONSE",
          requestId: message.requestId || "",
          force: Boolean(message.force),
          snapshot: response && response.ok ? response.snapshot : null,
        }, targetOrigin);
      })
      .catch(() => {
        targetWindow.postMessage({
          channel: CHANNEL,
          type: "SNAPSHOT_RESPONSE",
          requestId: message.requestId || "",
          force: Boolean(message.force),
          snapshot: null,
        }, targetOrigin);
      });
  });
})();
