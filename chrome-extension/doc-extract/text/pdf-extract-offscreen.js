/**
 * PDF text extraction via offscreen document (native browser PDF tabs cannot be scripted).
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const PDF_EXTRACT_RETRY_MS = 80;
  const PDF_EXTRACT_MAX_ATTEMPTS = 3;

  /**
   * @returns {Promise<void>}
   */
  async function ensureOffscreenForPdfExtract() {
    if (
      typeof MindGraphOffscreenBlobs !== "undefined" &&
      MindGraphOffscreenBlobs &&
      typeof MindGraphOffscreenBlobs.ensureOffscreenDocumentReady === "function"
    ) {
      await MindGraphOffscreenBlobs.ensureOffscreenDocumentReady();
      return;
    }
    const offApi =
      typeof chrome !== "undefined" && chrome.offscreen ? chrome.offscreen : null;
    if (!offApi) {
      throw new Error("OFFSCREEN_UNAVAILABLE");
    }
    const offscreenUrl = chrome.runtime.getURL("offscreen.html");
    if (chrome.runtime.getContexts) {
      const existing = await chrome.runtime.getContexts({
        contextTypes: ["OFFSCREEN_DOCUMENT"],
        documentUrls: [offscreenUrl],
      });
      if (existing && existing.length > 0) {
        return;
      }
    }
    try {
      await offApi.createDocument({
        url: offscreenUrl,
        reasons: ["BLOBS"],
        justification: "MindGraph extracts PDF text in an offscreen document for MindMate.",
      });
    } catch (err) {
      if (
        typeof MindGraphShared !== "undefined" &&
        MindGraphShared &&
        typeof MindGraphShared.isOffscreenDuplicateError === "function" &&
        MindGraphShared.isOffscreenDuplicateError(err)
      ) {
        return;
      }
      throw err;
    }
  }

  /**
   * @param {ArrayBuffer} arrayBuffer
   * @returns {string}
   */
  function arrayBufferToBase64(arrayBuffer) {
    if (
      typeof MindGraphOffscreenBlobs !== "undefined" &&
      MindGraphOffscreenBlobs &&
      typeof MindGraphOffscreenBlobs.arrayBufferToBase64 === "function"
    ) {
      return MindGraphOffscreenBlobs.arrayBufferToBase64(arrayBuffer);
    }
    const bytes = new Uint8Array(arrayBuffer);
    const chunkSize = 8192;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  /**
   * @param {object} payload
   * @returns {Promise<string>}
   */
  function sendPdfExtractRequest(payload) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(payload, (response) => {
        const last = chrome.runtime.lastError;
        if (last) {
          reject(new Error(last.message));
          return;
        }
        if (response && response.ok && typeof response.text === "string") {
          resolve(response.text);
          return;
        }
        reject(new Error((response && response.error) || "PDF_TEXT_EXTRACT_FAILED"));
      });
    });
  }

  /**
   * @param {ArrayBuffer} pdfBuffer
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractPdfTextViaOffscreen(pdfBuffer, maxPages, maxChars) {
    const common = {
      type: "MINDGRAPH_PDF_TEXT_EXTRACT",
      maxPages,
      maxChars,
    };
    try {
      return await sendPdfExtractRequest({ ...common, buffer: pdfBuffer });
    } catch (bufferErr) {
      const base64 = arrayBufferToBase64(pdfBuffer);
      try {
        return await sendPdfExtractRequest({ ...common, base64 });
      } catch (base64Err) {
        const bufferMessage = bufferErr instanceof Error ? bufferErr.message : String(bufferErr);
        const base64Message = base64Err instanceof Error ? base64Err.message : String(base64Err);
        throw new Error(`${bufferMessage}; base64: ${base64Message}`);
      }
    }
  }

  /**
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractPdfBlobTextOffscreen(blob, maxPages, maxChars) {
    if (!blob || blob.size < 64) {
      return "";
    }
    await ensureOffscreenForPdfExtract();
    const buffer = await blob.arrayBuffer();
    let lastError = null;
    for (let attempt = 0; attempt < PDF_EXTRACT_MAX_ATTEMPTS; attempt += 1) {
      if (attempt > 0) {
        await new Promise((resolve) => {
          setTimeout(resolve, PDF_EXTRACT_RETRY_MS * attempt);
        });
      }
      try {
        const text = await extractPdfTextViaOffscreen(buffer, maxPages, maxChars);
        if (text && text.trim()) {
          return text.trim();
        }
      } catch (err) {
        lastError = err;
      }
    }
    if (lastError) {
      throw lastError;
    }
    return "";
  }

  /**
   * @param {object} payload
   * @returns {Promise<{ text: string, imageBased: boolean, pageCount: number }>}
   */
  function sendPdfClassifyRequest(payload) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(payload, (response) => {
        const last = chrome.runtime.lastError;
        if (last) {
          reject(new Error(last.message));
          return;
        }
        if (response && response.ok) {
          resolve({
            text: typeof response.text === "string" ? response.text.trim() : "",
            imageBased: Boolean(response.imageBased),
            pageCount: typeof response.pageCount === "number" ? response.pageCount : 0,
          });
          return;
        }
        reject(new Error((response && response.error) || "PDF_CLASSIFY_FAILED"));
      });
    });
  }

  /**
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<{ text: string, imageBased: boolean, pageCount: number }>}
   */
  async function classifyPdfBlobOffscreen(blob, maxPages, maxChars) {
    if (!blob || blob.size < 64) {
      return { text: "", imageBased: false, pageCount: 0 };
    }
    await ensureOffscreenForPdfExtract();
    const buffer = await blob.arrayBuffer();
    const common = {
      type: "MINDGRAPH_PDF_TEXT_EXTRACT",
      classify: true,
      maxPages,
      maxChars,
    };
    try {
      return await sendPdfClassifyRequest({ ...common, buffer });
    } catch (bufferErr) {
      const base64 = arrayBufferToBase64(buffer);
      try {
        return await sendPdfClassifyRequest({ ...common, base64 });
      } catch (base64Err) {
        const bufferMessage = bufferErr instanceof Error ? bufferErr.message : String(bufferErr);
        const base64Message = base64Err instanceof Error ? base64Err.message : String(base64Err);
        throw new Error(`${bufferMessage}; base64: ${base64Message}`);
      }
    }
  }

  MindGraphDocExtract.ensureOffscreenForPdfExtract = ensureOffscreenForPdfExtract;
  MindGraphDocExtract.extractPdfBlobTextOffscreen = extractPdfBlobTextOffscreen;
  MindGraphDocExtract.classifyPdfBlobOffscreen = classifyPdfBlobOffscreen;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
