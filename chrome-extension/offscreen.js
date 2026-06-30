/**
 * Offscreen document — URL.createObjectURL / revokeObjectURL for Blobs.
 * Extension service workers generally cannot use these for Blobs; Chrome documents
 * offscreen "BLOBS" for this (developer.chrome.com offscreen / Reason.BLOBS).
 *
 * Payload: ArrayBuffer + mimeType (preferred) or base64 + mimeType (fallback).
 */
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || !MindGraphExtensionSecurity.isExtensionSender(sender)) {
    return false;
  }
  if (msg.type === "MINDGRAPH_BLOB_URL") {
    try {
      let blob;
      if (msg.buffer instanceof ArrayBuffer) {
        blob = new Blob([msg.buffer], { type: msg.mimeType || "application/octet-stream" });
      } else if (typeof msg.base64 === "string") {
        const binaryStr = atob(msg.base64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i += 1) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        blob = new Blob([bytes], { type: msg.mimeType || "application/octet-stream" });
      } else {
        sendResponse({ ok: false, error: "NO_BLOB_PAYLOAD" });
        return true;
      }
      const href = URL.createObjectURL(blob);
      sendResponse({ ok: true, href });
    } catch (err) {
      sendResponse({ ok: false, error: err && err.message ? err.message : String(err) });
    }
    return true;
  }
  if (msg.type === "MINDGRAPH_REVOKE_BLOB_URL" && typeof msg.href === "string") {
    try {
      URL.revokeObjectURL(msg.href);
      sendResponse({ ok: true });
    } catch (err) {
      sendResponse({ ok: false, error: err && err.message ? err.message : String(err) });
    }
    return true;
  }
  if (msg.type === "MINDGRAPH_PDF_TEXT_EXTRACT") {
    void (async () => {
      try {
        if (
          !globalThis.__MGDocExtractPdf ||
          typeof globalThis.__MGDocExtractPdf.extractTextFromPdfBuffer !== "function"
        ) {
          sendResponse({ ok: false, error: "PDFJS_NOT_LOADED" });
          return;
        }
        let pdfBuffer = null;
        if (msg.buffer instanceof ArrayBuffer) {
          pdfBuffer = msg.buffer;
        } else if (typeof msg.base64 === "string" && msg.base64.length > 0) {
          const binaryStr = atob(msg.base64);
          const bytes = new Uint8Array(binaryStr.length);
          for (let i = 0; i < binaryStr.length; i += 1) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          pdfBuffer = bytes.buffer;
        } else {
          sendResponse({ ok: false, error: "NO_PDF_PAYLOAD" });
          return;
        }
        const maxPages = typeof msg.maxPages === "number" ? msg.maxPages : 120;
        const maxChars = typeof msg.maxChars === "number" ? msg.maxChars : 8000;
        const text = await globalThis.__MGDocExtractPdf.extractTextFromPdfBuffer(
          pdfBuffer,
          maxPages,
          maxChars,
        );
        sendResponse({ ok: true, text: typeof text === "string" ? text : "" });
      } catch (err) {
        sendResponse({ ok: false, error: err && err.message ? err.message : String(err) });
      }
    })();
    return true;
  }
  return false;
});
