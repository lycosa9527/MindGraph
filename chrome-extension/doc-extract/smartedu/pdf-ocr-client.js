/**
 * Send an image-only SmartEdu PDF to the MindGraph account for OCR.
 * Local pdf.js cannot read these transcodes; the server rasterizes pages.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const OCR_TIMEOUT_MS = 90000;

  /**
   * @returns {{ log: Function } | null}
   */
  function captureDebug() {
    const root = global.MindGraphMindMate;
    return root && root.captureDebug ? root.captureDebug : null;
  }

  /**
   * @returns {Promise<{ baseUrl: string, account: string, token: string } | null>}
   */
  async function readMindGraphApiCredentials() {
    if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.local) {
      return null;
    }
    const shared = global.MindGraphShared;
    if (!shared || typeof shared.resolveMindGraphSettings !== "function") {
      return null;
    }
    const settings = await chrome.storage.local.get(["baseUrl", "baseUrlPresetId", "account", "token"]);
    const resolved = shared.resolveMindGraphSettings(settings);
    const baseUrl = resolved && resolved.baseUrl ? String(resolved.baseUrl) : "";
    const account = settings && settings.account ? String(settings.account).trim() : "";
    const token = settings && settings.token ? String(settings.token).trim() : "";
    if (!baseUrl || !account || !token) {
      return null;
    }
    return { baseUrl, account, token };
  }

  /**
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {{ baseUrl: string, account: string, token: string }} creds
   * @param {typeof fetch} [fetchImpl]
   * @returns {Promise<string>}
   */
  async function postSmartEduPdfForOcr(blob, maxPages, creds, fetchImpl) {
    const shared = global.MindGraphShared;
    const doFetch = fetchImpl || fetch;
    const form = new FormData();
    form.append("file", blob, "lesson.pdf");
    form.append("max_pages", String(maxPages));
    form.append("image_based", "true");
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), OCR_TIMEOUT_MS);
    try {
      const init = {
        method: "POST",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${creds.token}`,
          "X-MG-Account": creds.account,
          "X-MG-Client": shared && shared.mgClientHeader ? shared.mgClientHeader() : "chrome-extension",
          "X-Request-Id": shared && shared.newRequestId ? shared.newRequestId() : "",
        },
        body: form,
      };
      const requestInit = shared && shared.mgatFetchInit ? shared.mgatFetchInit(init) : init;
      const res = await doFetch(`${creds.baseUrl}/api/extension/extract_pdf_text`, requestInit);
      if (!res.ok) {
        const dbg = captureDebug();
        if (dbg) {
          dbg.log("smartedu.ocr", "server OCR HTTP error", { status: res.status });
        }
        return "";
      }
      const data = await res.json();
      return data && typeof data.text === "string" ? data.text.trim() : "";
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {string} [title]
   * @returns {Promise<string>}
   */
  async function ocrSmartEduPdfBlob(blob, maxPages, title) {
    const dbg = captureDebug();
    const pages = Math.max(1, Math.min(8, Number(maxPages) || 1));
    if (!blob || blob.size < 64) {
      return "";
    }
    const creds = await readMindGraphApiCredentials();
    if (!creds) {
      if (dbg) {
        dbg.log("smartedu.ocr", "skipped, MindGraph account not configured", { title: title || "" });
      }
      return "";
    }
    if (dbg) {
      dbg.log("smartedu.ocr", "sending image PDF for OCR", {
        title: title || "",
        bytes: blob.size,
        maxPages: pages,
      });
    }
    try {
      const text = await postSmartEduPdfForOcr(blob, pages, creds);
      if (dbg) {
        dbg.log("smartedu.ocr", "server OCR returned", {
          title: title || "",
          chars: text ? text.length : 0,
        });
      }
      return text;
    } catch (err) {
      if (dbg) {
        dbg.log("smartedu.ocr", "server OCR failed", {
          title: title || "",
          message: err instanceof Error ? err.message : "unknown",
        });
      }
      return "";
    }
  }

  /**
   * Keep a text layer. When the PDF is image-only, ask the account to OCR it.
   * @param {number} tabId
   * @param {Blob} blob
   * @param {string} localText
   * @param {number} maxPages
   * @param {number} maxChars
   * @param {string} [title]
   * @returns {Promise<string>}
   */
  async function finishPdfBlobText(tabId, blob, localText, maxPages, maxChars, title) {
    const local = (localText || "").trim();
    if (local.length >= 80) {
      return local;
    }
    let imageBased = false;
    let text = local;
    const classify = MindGraphDocExtract.classifyPdfBlobWithFallback;
    if (typeof classify === "function" && blob) {
      try {
        const classified = await classify(tabId, blob, maxPages, maxChars);
        const classifiedText =
          classified && typeof classified.text === "string" ? classified.text.trim() : "";
        if (classifiedText.length > text.length) {
          text = classifiedText;
        }
        imageBased = Boolean(classified && classified.imageBased);
      } catch {
        imageBased = false;
      }
    }
    if (text.length >= 80 || !imageBased) {
      return text;
    }
    const ocrPages = Math.max(1, Math.min(8, Number(maxPages) || 1));
    const ocrText = (await ocrSmartEduPdfBlob(blob, ocrPages, title || "")).trim();
    const merge = MindGraphDocExtract.mergePdfTextAndOcr;
    if (typeof merge === "function") {
      return merge(text, ocrText, 80);
    }
    return ocrText.length > text.length ? ocrText : text;
  }

  MindGraphDocExtract.postSmartEduPdfForOcr = postSmartEduPdfForOcr;
  MindGraphDocExtract.ocrSmartEduPdfBlob = ocrSmartEduPdfBlob;
  MindGraphDocExtract.finishPdfBlobText = finishPdfBlobText;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
