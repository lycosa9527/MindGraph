/**
 * Offscreen document — URL.createObjectURL / revokeObjectURL for Blobs.
 * Extension service workers generally cannot use these for Blobs; Chrome documents
 * offscreen "BLOBS" for this (developer.chrome.com offscreen / Reason.BLOBS).
 *
 * chrome.runtime.sendMessage is JSON-serialized, so Blob objects cannot be transferred
 * directly. The service worker sends base64 + mimeType; we reconstruct the Blob here.
 */
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg) {
    return false;
  }
  if (msg.type === "MINDGRAPH_BLOB_URL" && typeof msg.base64 === "string") {
    try {
      const binaryStr = atob(msg.base64);
      const bytes = new Uint8Array(binaryStr.length);
      for (let i = 0; i < binaryStr.length; i += 1) {
        bytes[i] = binaryStr.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: msg.mimeType || "image/png" });
      const href = URL.createObjectURL(blob);
      sendResponse({ ok: true, href });
    } catch (err) {
      sendResponse({ ok: false, error: err && err.message ? err.message : String(err) });
    }
    return false;
  }
  if (msg.type === "MINDGRAPH_REVOKE_BLOB_URL" && typeof msg.href === "string") {
    try {
      URL.revokeObjectURL(msg.href);
      sendResponse({ ok: true });
    } catch (err) {
      sendResponse({ ok: false, error: err && err.message ? err.message : String(err) });
    }
    return false;
  }
  return false;
});
