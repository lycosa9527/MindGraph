/**
 * Product-rule capture: web markdown + document PDFs (with OCR) + canvas fallback.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MAX_LINKED_PDFS = 3;
  const THIN_MARKDOWN_CHARS = 400;
  const CANVAS_OCR_MAX_PAGES = 4;
  const PDF_MAX_PAGES = 120;
  const LINKED_PDF_MIN_CHARS = 80;

  /**
   * @param {string} base
   * @param {string} addition
   * @param {number} maxChars
   * @returns {string}
   */
  function appendMarkdownBlocks(base, addition, maxChars) {
    const left = (base || "").trim();
    const right = (addition || "").trim();
    if (!right) {
      return left;
    }
    if (!left) {
      return maxChars && right.length > maxChars ? right.slice(0, maxChars) : right;
    }
    let combined = `${left}\n\n${right}`;
    if (maxChars && combined.length > maxChars) {
      combined = combined.slice(0, maxChars - 3).trim() + "\n\n…";
    }
    return combined.trim();
  }

  /**
   * @param {number} tabId
   * @returns {Promise<string[]>}
   */
  async function discoverLinkedPdfUrlsInTab(tabId) {
    if (!tabId) {
      return [];
    }
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          /** @type {string[]} */
          const urls = [];
          const seen = new Set();
          const add = (raw) => {
            const value = (raw || "").trim();
            if (!value) {
              return;
            }
            try {
              const resolved = new URL(value, location.href).href;
              if (!/\.pdf(\?|#|$)/i.test(resolved) || seen.has(resolved)) {
                return;
              }
              seen.add(resolved);
              urls.push(resolved);
            } catch {
              /* ignore */
            }
          };
          document.querySelectorAll("a[href]").forEach((node) => add(node.href));
          document.querySelectorAll("embed[src], iframe[src], object[data]").forEach((node) => {
            add(node.src || node.getAttribute("data") || "");
          });
          return urls.slice(0, 3);
        },
      });
      const list = results && results[0] && results[0].result;
      return Array.isArray(list) ? list : [];
    } catch {
      return [];
    }
  }

  /**
   * @param {number} tabId
   * @param {string} pdfUrl
   * @returns {Promise<Blob | null>}
   */
  async function fetchPdfBlobInTab(tabId, pdfUrl) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: async (url) => {
          const res = await fetch(url, { credentials: "include", redirect: "follow" });
          if (!res.ok) {
            return null;
          }
          const buf = await res.arrayBuffer();
          if (buf.byteLength < 64 || buf.byteLength > 8 * 1024 * 1024) {
            return null;
          }
          const head = new Uint8Array(buf, 0, 4);
          if (String.fromCharCode(head[0], head[1], head[2], head[3]) !== "%PDF") {
            return null;
          }
          const bytes = new Uint8Array(buf);
          const chunkSize = 8192;
          let binary = "";
          for (let i = 0; i < bytes.length; i += chunkSize) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
          }
          return btoa(binary);
        },
        args: [pdfUrl],
      });
      const encoded = results && results[0] && results[0].result;
      if (!encoded || typeof encoded !== "string") {
        return null;
      }
      const binary = atob(encoded);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      return new Blob([bytes], { type: "application/pdf" });
    } catch {
      return null;
    }
  }

  /**
   * @param {string} pdfUrl
   * @returns {string}
   */
  function titleFromLinkedPdfUrl(pdfUrl) {
    try {
      const base = decodeURIComponent(new URL(pdfUrl).pathname.split("/").pop() || "document.pdf");
      return base.replace(/\.pdf$/i, "") || "PDF";
    } catch {
      return "PDF";
    }
  }

  /**
   * @param {object} api
   * @param {number} tabId
   * @param {string} pageUrl
   * @param {number} maxChars
   * @param {string} existingDocMarkdown
   * @returns {Promise<string>}
   */
  async function collectLinkedPdfMarkdown(api, tabId, pageUrl, maxChars, existingDocMarkdown) {
    const urls = await discoverLinkedPdfUrlsInTab(tabId);
    if (!urls.length || typeof api.pdfBlobToDocumentMarkdown !== "function") {
      return (existingDocMarkdown || "").trim();
    }
    let combined = (existingDocMarkdown || "").trim();
    for (const pdfUrl of urls.slice(0, MAX_LINKED_PDFS)) {
      if (combined.includes(pdfUrl)) {
        continue;
      }
      const blob = await fetchPdfBlobInTab(tabId, pdfUrl);
      if (!blob) {
        continue;
      }
      const title = titleFromLinkedPdfUrl(pdfUrl);
      const section = await api.pdfBlobToDocumentMarkdown(tabId, blob, title, pdfUrl, maxChars);
      if (section && section.length >= LINKED_PDF_MIN_CHARS) {
        combined = appendMarkdownBlocks(combined, section, maxChars);
      }
    }
    return combined.trim();
  }

  /**
   * @param {object} api
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function tryCanvasRasterOcrMarkdown(api, tabId, hostEntry, maxChars) {
    if (
      typeof MindGraphDocExtract.collectCanvasFromTab !== "function" ||
      typeof MindGraphDocExtract.imagesToPdfBlob !== "function" ||
      typeof MindGraphDocExtract.ocrSmartEduPdfBlob !== "function"
    ) {
      return "";
    }
    try {
      if (typeof api.runPrepOnTab === "function") {
        await api.runPrepOnTab(tabId, hostEntry, () => {});
      }
      const payload = await MindGraphDocExtract.collectCanvasFromTab(tabId, hostEntry);
      const blob = await MindGraphDocExtract.imagesToPdfBlob(payload.images, payload.title, {
        pageWidth: payload.pageWidth,
        pageHeight: payload.pageHeight,
      });
      const ocrText = await MindGraphDocExtract.ocrSmartEduPdfBlob(
        blob,
        Math.min(CANVAS_OCR_MAX_PAGES, payload.pageCount || CANVAS_OCR_MAX_PAGES),
        payload.title || "document",
      );
      const text = (ocrText || "").trim();
      if (text.length < LINKED_PDF_MIN_CHARS || typeof api.formatDocumentMarkdown !== "function") {
        return "";
      }
      return api.formatDocumentMarkdown(
        payload.title || "Document images",
        text,
        "",
        maxChars,
      );
    } catch {
      return "";
    }
  }

  /**
   * @param {object} api
   * @param {object} input
   * @returns {Promise<object>}
   */
  async function runProductRuleCapture(api, input) {
    const {
      ctx,
      tabId,
      tab,
      pageUrl,
      hostEntry,
      fileFirst,
      maxChars,
      options,
      isKnownHost,
      finalizeCaptureResult,
    } = input;
    const dbg = typeof api.captureDebug === "function" ? api.captureDebug() : null;
    const title = tab.title || "";
    const mergeShell = MindGraphDocExtract.mergePageShellWithDocuments;

    const browserPdf = await api.tryBrowserPdfTabMarkdown(tabId, pageUrl, title, maxChars);
    if (browserPdf && browserPdf.markdown) {
      return finalizeCaptureResult(ctx, { ok: true, fromSelection: false, ...browserPdf });
    }

    /** @type {{ markdown: string, source: string, assetTotal: number, fatalError: string | null, title: string }} */
    const doc = { markdown: "", source: "", assetTotal: 0, fatalError: null, title: "" };

    if (hostEntry.id === "smartedu" && typeof MindGraphDocExtract.trySmartEduPdfMarkdown === "function") {
      const smarteduResult = await MindGraphDocExtract.trySmartEduPdfMarkdown(
        tabId,
        pageUrl,
        maxChars,
        options || {},
      );
      if (smarteduResult && smarteduResult.ok === false) {
        return finalizeCaptureResult(ctx, smarteduResult);
      }
      if (smarteduResult && smarteduResult.markdown) {
        doc.markdown = smarteduResult.markdown;
        doc.source = smarteduResult.source || "smartedu-pdf";
        doc.assetTotal = smarteduResult.assetTotal || 0;
        doc.title = smarteduResult.title || "";
      } else if (fileFirst) {
        return finalizeCaptureResult(ctx, { ok: false, error: "errExtractWrongPage" });
      }
    } else if (isKnownHost) {
      if (typeof api.runPrepOnTab === "function") {
        await api.runPrepOnTab(tabId, hostEntry, () => {});
      }
      const embeddedText = await api.extractEmbeddedPdfTextFromTab(tabId, PDF_MAX_PAGES, maxChars);
      if (embeddedText.length >= LINKED_PDF_MIN_CHARS && typeof api.formatDocumentMarkdown === "function") {
        doc.markdown = api.formatDocumentMarkdown(title, embeddedText, pageUrl, maxChars);
        doc.source = "page-pdfjs";
      }
      if (!doc.markdown && hostEntry.id === "cnki") {
        const cnkiReader = await api.tryCnkiReaderTextMarkdown(tabId, hostEntry, pageUrl, maxChars);
        if (cnkiReader && cnkiReader.markdown) {
          doc.markdown = cnkiReader.markdown;
          doc.source = cnkiReader.source || "cnki-reader-text";
        }
      }
      if (!doc.markdown) {
        const cnkiPdf = await api.tryCnkiPdfMarkdown(tabId, hostEntry, pageUrl, maxChars);
        if (cnkiPdf && cnkiPdf.ok === false) {
          doc.fatalError = cnkiPdf.error || null;
        } else if (cnkiPdf && cnkiPdf.markdown) {
          doc.markdown = cnkiPdf.markdown;
          doc.source = cnkiPdf.source || "cnki-pdf";
        }
      }
      if (!doc.markdown) {
        const wenkuPdf = await api.tryWenkuPdfMarkdown(tabId, hostEntry, pageUrl, maxChars);
        if (wenkuPdf && wenkuPdf.markdown) {
          doc.markdown = wenkuPdf.markdown;
          doc.source = wenkuPdf.source || "wenku-pdf";
        }
      }
      if (!doc.markdown && !fileFirst) {
        const domArticle = await api.tryDomArticleMarkdown(tabId, hostEntry, maxChars, pageUrl);
        if (domArticle && domArticle.markdown) {
          doc.markdown = domArticle.markdown;
          doc.source = domArticle.source || "dom-article";
        }
      }
    }

    doc.markdown = await collectLinkedPdfMarkdown(api, tabId, pageUrl, maxChars, doc.markdown);

    let webMarkdown = "";
    let fromSelection = false;
    let webSource = "page-markdown";
    if (!fileFirst) {
      const selection = await api.captureSelectionMarkdown(tabId, maxChars);
      if (selection && selection.markdown) {
        webMarkdown = selection.markdown;
        fromSelection = true;
        webSource = selection.source || "selection";
      }
    }
    if (!webMarkdown) {
      const autoScanGeneric = hostEntry.id === "generic";
      const pagePayload = await api.collectInPageMarkdown(tabId, maxChars, pageUrl, title, {
        skipSelection: autoScanGeneric || fileFirst,
      });
      webMarkdown = pagePayload.markdown || "";
      webSource = pagePayload.source || webSource;
    }

    let combined = "";
    if (typeof mergeShell === "function") {
      combined = mergeShell(webMarkdown, doc.markdown, maxChars).trim();
    } else {
      combined = appendMarkdownBlocks(webMarkdown, doc.markdown, maxChars);
    }

    const thin = combined.length < THIN_MARKDOWN_CHARS;
    if (
      thin &&
      MindGraphDocExtract.isCanvasRenderHost &&
      MindGraphDocExtract.isCanvasRenderHost(hostEntry)
    ) {
      const canvasMd = await tryCanvasRasterOcrMarkdown(api, tabId, hostEntry, maxChars);
      if (canvasMd) {
        combined = appendMarkdownBlocks(combined, canvasMd, maxChars);
        doc.source = doc.source ? `${doc.source}+canvas-ocr` : "canvas-ocr";
      }
    }

    if (typeof api.applyHostPreviewNotice === "function") {
      combined = api.applyHostPreviewNotice(combined, hostEntry, maxChars);
    }

    if (combined.length >= 40) {
      const source = doc.source && webMarkdown ? `${webSource}+${doc.source}` : doc.source || webSource;
      if (dbg) {
        dbg.log("mixed-capture", "assembled markdown", {
          markdownLen: combined.length,
          source,
          fromSelection,
        });
      }
      return finalizeCaptureResult(ctx, {
        ok: true,
        title: doc.title || title || pageUrl,
        url: pageUrl,
        markdown: combined,
        fromSelection,
        source,
        assetTotal: doc.assetTotal,
      });
    }

    if (fileFirst) {
      let fileFirstError = "errMindMatePageEmpty";
      if (hostEntry.id === "cnki" && doc.fatalError) {
        const loginLike =
          doc.fatalError === "CNKI_LOGIN_REQUIRED" ||
          doc.fatalError === "CNKI_CAPTCHA" ||
          /BINARY_HTTP_401|BINARY_HTTP_403|LOGIN/i.test(doc.fatalError);
        if (loginLike && typeof MindGraphDocExtract.resolveExtractErrorKey === "function") {
          fileFirstError = MindGraphDocExtract.resolveExtractErrorKey(doc.fatalError, hostEntry);
        }
      } else if (hostEntry.id === "wenku") {
        fileFirstError = "errExtractWenkuNoPreview";
      }
      return finalizeCaptureResult(ctx, { ok: false, error: fileFirstError });
    }

    if (
      MindGraphDocExtract.isCanvasRenderHost &&
      MindGraphDocExtract.isCanvasRenderHost(hostEntry) &&
      MindGraphDocExtract.countCanvasPagesInTab
    ) {
      const canvasCount = await MindGraphDocExtract.countCanvasPagesInTab(tabId, hostEntry);
      if (canvasCount && canvasCount > 0) {
        return finalizeCaptureResult(ctx, { ok: false, error: "errMindMateCanvasPreviewEmpty" });
      }
    }

    return finalizeCaptureResult(ctx, { ok: false, error: "errMindMatePageEmpty" });
  }

  MindGraphDocExtract.runProductRuleCapture = runProductRuleCapture;
  MindGraphDocExtract.discoverLinkedPdfUrlsInTab = discoverLinkedPdfUrlsInTab;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
