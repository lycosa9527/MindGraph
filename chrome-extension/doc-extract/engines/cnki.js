/**
 * CNKI engine — PDF download (session cookies) with flowpdf canvas fallback.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {object} resolved
   * @param {string} pageUrl
   * @returns {string[]}
   */
  function mergeCnkiDownloadCandidates(resolved, pageUrl) {
    const candidates = cnkiDownloadCandidateUrls(resolved);
    if (
      typeof MindGraphDocExtract.buildCnkiReaderDownloadCandidates === "function" &&
      pageUrl
    ) {
      MindGraphDocExtract.buildCnkiReaderDownloadCandidates(pageUrl).forEach((url) => {
        if (url && !candidates.includes(url)) {
          candidates.push(url);
        }
      });
    }
    return candidates;
  }

  /**
   * @param {number} tabId
   * @returns {Promise<object>}
   */
  async function resolveCnkiPdfFromTab(tabId) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["doc-extract/cnki/page-resolve.js"],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        if (!globalThis.__MGDocExtractCnki || !globalThis.__MGDocExtractCnki.resolvePdfDownload) {
          throw new Error("CNKI_RESOLVE_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCnki.resolvePdfDownload();
      },
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || typeof payload !== "object") {
      throw new Error("CNKI_PDF_URL_MISS");
    }
    return payload;
  }

  /**
   * @param {string} url
   * @returns {Promise<Blob>}
   */
  async function fetchCnkiBinaryUrl(url) {
    const res = await fetch(url, { method: "GET", credentials: "include", redirect: "follow" });
    if (!res.ok) {
      throw new Error(`BINARY_HTTP_${res.status}`);
    }
    const blob = await res.blob();
    const type = (blob.type || "").toLowerCase();
    if (type.includes("pdf") || type.includes("octet-stream") || blob.size > 4096) {
      return blob;
    }
    throw new Error("CNKI_PDF_URL_MISS");
  }

  /**
   * @param {object} resolved
   * @returns {string[]}
   */
  function cnkiDownloadCandidateUrls(resolved) {
    /** @type {string[]} */
    const candidates = [];
    if (resolved.pdfUrl) {
      candidates.push(resolved.pdfUrl);
    }
    if (Array.isArray(resolved.guessUrls)) {
      resolved.guessUrls.forEach((url) => {
        if (url && !candidates.includes(url)) {
          candidates.push(url);
        }
      });
    }
    return candidates;
  }

  /**
   * @param {number} tabId
   * @param {string[]} candidateUrls
   * @returns {Promise<Blob | null>}
   */
  async function fetchCnkiPdfBlobInTab(tabId, candidateUrls) {
    if (!candidateUrls.length) {
      return null;
    }
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async (urls) => {
        /**
         * @param {ArrayBuffer} buffer
         * @returns {string}
         */
        function bufferToBase64(buffer) {
          const bytes = new Uint8Array(buffer);
          const chunkSize = 8192;
          let binary = "";
          for (let i = 0; i < bytes.length; i += chunkSize) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
          }
          return btoa(binary);
        }

        for (const url of urls) {
          try {
            const res = await fetch(url, { method: "GET", credentials: "include", redirect: "follow" });
            if (!res.ok) {
              continue;
            }
            const blob = await res.blob();
            const buffer = await blob.arrayBuffer();
            const bytes = new Uint8Array(buffer);
            if (bytes.length < 64) {
              continue;
            }
            const contentType = (res.headers.get("content-type") || blob.type || "").toLowerCase();
            const isPdfMagic =
              bytes.length >= 4 &&
              bytes[0] === 0x25 &&
              bytes[1] === 0x50 &&
              bytes[2] === 0x44 &&
              bytes[3] === 0x46;
            if (!isPdfMagic && !contentType.includes("pdf") && !contentType.includes("octet-stream")) {
              continue;
            }
            return { ok: true, base64: bufferToBase64(buffer), size: bytes.length };
          } catch {
            continue;
          }
        }
        return { ok: false, error: "CNKI_PDF_URL_MISS" };
      },
      args: [candidateUrls],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || !payload.ok || typeof payload.base64 !== "string" || !payload.base64) {
      return null;
    }
    const binary = atob(payload.base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: "application/pdf" });
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<{ text: string, title: string, pageCount: number }>}
   */
  async function collectCnkiReaderTextFromTab(tabId, hostEntry, maxPages, maxChars) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [
        "doc-extract/cnki/page-resolve.js",
        "doc-extract/cnki/reader-surfaces.js",
        "doc-extract/cnki/reader-text.js",
      ],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (hideSelectors, pages, chars) => {
        if (
          !globalThis.__MGDocExtractCollect
          || !globalThis.__MGDocExtractCollect.collectCnkiReaderPlainText
        ) {
          throw new Error("COLLECT_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCollect.collectCnkiReaderPlainText(hideSelectors, pages, chars);
      },
      args: [hostEntry.hideSelectors || [], maxPages, maxChars],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || typeof payload.text !== "string") {
      throw new Error("CNKI_READER_TEXT_EMPTY");
    }
    return payload;
  }

  /**
   * @param {object} resolved
   * @returns {Promise<Blob>}
   */
  async function fetchCnkiPdfCandidates(resolved) {
    const candidates = cnkiDownloadCandidateUrls(resolved);
    let lastError = null;
    for (const url of candidates) {
      try {
        return await fetchCnkiBinaryUrl(url);
      } catch (err) {
        lastError = err;
      }
    }
    if (lastError && lastError.message) {
      throw lastError;
    }
    throw new Error("CNKI_PDF_URL_MISS");
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @returns {Promise<{ images: string[], title: string, pageCount: number, pageWidth: number, pageHeight: number }>}
   */
  async function collectCnkiReaderFromTab(tabId, hostEntry) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [
        "doc-extract/cnki/page-resolve.js",
        "doc-extract/cnki/reader-surfaces.js",
        "doc-extract/cnki/reader-collect.js",
      ],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (hideSelectors, maxPages) => {
        if (!globalThis.__MGDocExtractCollect
          || !globalThis.__MGDocExtractCollect.collectCnkiReaderCanvasImages) {
          throw new Error("COLLECT_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCollect.collectCnkiReaderCanvasImages(hideSelectors, maxPages);
      },
      args: [hostEntry.hideSelectors || [], hostEntry.readerMaxPages || 120],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || !payload.images || !payload.images.length) {
      throw new Error("CANVAS_EMPTY");
    }
    return payload;
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {(stage: string) => void} postProgress
   * @returns {Promise<{ blob: Blob, filename: string }>}
   */
  async function runCnkiCanvasEngine(tabId, hostEntry, postProgress) {
    postProgress("collecting");
    const payload = await collectCnkiReaderFromTab(tabId, hostEntry);
    postProgress("assembling");
    let blob;
    try {
      blob = await MindGraphDocExtract.imagesToPdfBlob(payload.images, payload.title, {
        pageWidth: payload.pageWidth,
        pageHeight: payload.pageHeight,
      });
    } catch {
      blob = await MindGraphDocExtract.imagesToZipBlob(payload.images);
      return {
        blob,
        filename: MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ".zip"),
      };
    }
    return {
      blob,
      filename: MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ".pdf"),
    };
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {string} pageUrl
   * @param {(stage: string) => void} postProgress
   * @returns {Promise<{ blob: Blob, filename: string }>}
   */
  async function runCnkiEngine(tabId, hostEntry, pageUrl, postProgress) {
    const parsed = MindGraphDocExtract.parseCnkiPageUrl(pageUrl);
    const isReader = parsed
      && (parsed.kind === "flowpdf" || parsed.kind === "trial-read" || parsed.kind === "reader");

    if (!isReader) {
      const resolved = await resolveCnkiPdfFromTab(tabId);
      if (resolved.error === "CNKI_CAPTCHA") {
        throw new Error("CNKI_CAPTCHA");
      }
      if (resolved.error === "CNKI_LOGIN_REQUIRED") {
        throw new Error("CNKI_LOGIN_REQUIRED");
      }
      const candidates = mergeCnkiDownloadCandidates(resolved, pageUrl);
      if (!candidates.length) {
        throw new Error("CNKI_PDF_URL_MISS");
      }
      postProgress("collecting");
      let blob = null;
      try {
        blob = await fetchCnkiPdfBlobInTab(tabId, candidates);
      } catch {
        blob = null;
      }
      if (!blob && candidates.length) {
        blob = await fetchCnkiPdfCandidates({ ...resolved, guessUrls: candidates, pdfUrl: candidates[0] });
      }
      postProgress("assembling");
      return {
        blob,
        filename: MindGraphDocExtract.sanitizeDownloadBasename(resolved.title || "cnki-document", ".pdf"),
      };
    }

    const resolved = await resolveCnkiPdfFromTab(tabId);
    if (resolved.error === "CNKI_CAPTCHA") {
      throw new Error("CNKI_CAPTCHA");
    }
    if (resolved.error === "CNKI_LOGIN_REQUIRED") {
      throw new Error("CNKI_LOGIN_REQUIRED");
    }

    try {
      const candidates = mergeCnkiDownloadCandidates(resolved, pageUrl);
      if (candidates.length) {
        postProgress("collecting");
        let blob = null;
        try {
          blob = await fetchCnkiPdfBlobInTab(tabId, candidates);
        } catch {
          blob = null;
        }
        if (!blob) {
          blob = await fetchCnkiPdfCandidates({ ...resolved, guessUrls: candidates, pdfUrl: candidates[0] });
        }
        postProgress("assembling");
        return {
          blob,
          filename: MindGraphDocExtract.sanitizeDownloadBasename(resolved.title || "cnki-document", ".pdf"),
        };
      }
    } catch {
      /* fall through to canvas capture for flowpdf reader */
    }

    return runCnkiCanvasEngine(tabId, hostEntry, postProgress);
  }

  MindGraphDocExtract.resolveCnkiPdfFromTab = resolveCnkiPdfFromTab;
  MindGraphDocExtract.cnkiDownloadCandidateUrls = cnkiDownloadCandidateUrls;
  MindGraphDocExtract.mergeCnkiDownloadCandidates = mergeCnkiDownloadCandidates;
  MindGraphDocExtract.fetchCnkiPdfBlobInTab = fetchCnkiPdfBlobInTab;
  MindGraphDocExtract.collectCnkiReaderTextFromTab = collectCnkiReaderTextFromTab;
  MindGraphDocExtract.fetchCnkiPdfCandidates = fetchCnkiPdfCandidates;
  MindGraphDocExtract.runCnkiCanvasEngine = runCnkiCanvasEngine;
  MindGraphDocExtract.runCnkiEngine = runCnkiEngine;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
